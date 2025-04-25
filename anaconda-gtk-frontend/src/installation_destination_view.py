import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib
import locale

# UDisks2 DBus constants
UDISKS_BUS_NAME = 'org.freedesktop.UDisks2'
UDISKS_OBJECT_PATH = '/org/freedesktop/UDisks2'
OBJECT_MANAGER_INTERFACE = 'org.freedesktop.DBus.ObjectManager'
BLOCK_INTERFACE = 'org.freedesktop.UDisks2.Block'
DRIVE_INTERFACE = 'org.freedesktop.UDisks2.Drive'
PARTITION_TABLE_INTERFACE = 'org.freedesktop.UDisks2.PartitionTable'
PARTITION_INTERFACE = 'org.freedesktop.UDisks2.Partition'

def format_size(size_bytes):
    """Converts bytes to human-readable format (GiB)."""
    if size_bytes == 0:
        return "0 B"
    # Using locale for potential grouping, though GB/GiB might not use it
    locale.setlocale(locale.LC_ALL, '')
    # Using GiB (1024^3)
    gib = size_bytes / (1024 ** 3)
    return locale.format_string("%.1f GiB", gib, grouping=True)

@Gtk.Template(filename='ui/installation_destination.ui')
class InstallationDestinationView(Gtk.Box):
    __gtype_name__ = 'InstallationDestinationView'

    # Template children
    disk_list_box = Gtk.Template.Child()
    config_auto_check = Gtk.Template.Child()
    config_custom_check = Gtk.Template.Child()
    space_summary_label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected_disks = []
        self._dbus_proxy = None
        self.populate_disk_list()
        self.disk_list_box.connect("selected-rows-changed", self.on_disk_selection_changed)
        self.config_auto_check.connect("toggled", self.on_config_option_changed)
        self.config_custom_check.connect("toggled", self.on_config_option_changed)
        print("InstallationDestinationView initialized")
        self.update_summary()

    def _get_dbus_proxy(self):
        """Gets the Gio DBus proxy for UDisks2 ObjectManager."""
        if self._dbus_proxy:
            return self._dbus_proxy
        try:
            self._dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None, # GDBusInterfaceInfo
                UDISKS_BUS_NAME,
                UDISKS_OBJECT_PATH,
                OBJECT_MANAGER_INTERFACE,
                None # GCancellable
            )
            print("Successfully connected to UDisks2 DBus service.")
            return self._dbus_proxy
        except GLib.Error as e:
            print(f"Error connecting to UDisks2 DBus: {e}")
            self.show_error_dialog("Disk Detection Error", 
                                   f"Could not connect to the UDisks2 service: {e.message}")
            return None

    def populate_disk_list(self):
        """Populates the list box with detected disks via UDisks2 DBus."""
        # Clear existing items first
        child = self.disk_list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.disk_list_box.remove(child)
            child = next_child
            
        proxy = self._get_dbus_proxy()
        if not proxy:
            return

        try:
            # Get all managed objects from UDisks2
            variant = proxy.call_sync('GetManagedObjects', None, Gio.DBusCallFlags.NONE, -1, None)
            if not variant:
                print("GetManagedObjects returned None")
                self.show_error_dialog("Disk Detection Error", "Failed to get objects from UDisks2.")
                return

            # The result is a Variant of type a{oa{sa{sv}}} 
            # (dict of object_path -> dict of interface_name -> dict of property_name -> variant)
            objects = variant.unpack()[0] 
            
            print(f"Found {len(objects)} UDisks2 objects. Filtering for installable disks...")
            found_disks = []

            for obj_path, interfaces in objects.items():
                # We are interested in Block devices that are NOT partitions and NOT loop devices
                if BLOCK_INTERFACE in interfaces:
                    block_props = interfaces[BLOCK_INTERFACE]

                    # Safely get Drive property
                    drive_path_variant = block_props.get('Drive', GLib.Variant('o', '/'))
                    drive_path = drive_path_variant.unpack() if isinstance(drive_path_variant, GLib.Variant) else drive_path_variant

                    # Safely get Device property
                    device_file_bytes_variant = block_props.get('Device', GLib.Variant('ay', b''))
                    device_file_raw = device_file_bytes_variant.unpack() if isinstance(device_file_bytes_variant, GLib.Variant) else device_file_bytes_variant

                    # Decode the device path robustly
                    device_file = "/unknown/device"
                    if isinstance(device_file_raw, bytes):
                        # Standard case: decode bytes
                        device_file = device_file_raw.decode('utf-8', errors='replace').rstrip('\\x00')
                    elif isinstance(device_file_raw, list):
                         # Handle list of integers (bytes)
                         try:
                              device_file = bytes(device_file_raw).decode('utf-8', errors='replace').rstrip('\\x00')
                              print(f"  Decoded byte list {device_file_raw} to '{device_file}'")
                         except Exception as e_decode:
                              print(f"  Warning: Failed to decode byte list {device_file_raw}: {e_decode}")
                              device_file = str(device_file_raw) # Fallback
                    elif isinstance(device_file_raw, str):
                         # If it's already a string, use it directly (unless it's the weird byte list)
                         if device_file_raw.startswith('[') and device_file_raw.endswith(']'):
                              # Attempt to parse stringified byte list (less safe)
                              try:
                                   # Extract numbers, convert to bytes, decode
                                   byte_values = [int(b.strip()) for b in device_file_raw[1:-1].split(',')]
                                   device_file = bytes(byte_values).decode('utf-8', errors='replace').rstrip('\\x00')
                                   print(f"  Decoded byte string '{device_file_raw}' to '{device_file}'")
                              except Exception as e_parse:
                                   print(f"  Warning: Failed to parse byte string '{device_file_raw}': {e_parse}")
                                   device_file = device_file_raw # Fallback to the raw string
                         else:
                              # Assume it's a regular string path
                              device_file = device_file_raw
                    else:
                        # Fallback for other unexpected types
                        print(f"  Warning: Unexpected type for device path: {type(device_file_raw)}, value: {device_file_raw}")
                        device_file = str(device_file_raw)

                    # Safely get Size property
                    size_variant = block_props.get('Size', GLib.Variant('t', 0))
                    size = size_variant.unpack() if isinstance(size_variant, GLib.Variant) else size_variant
                    # Ensure size is an integer
                    size = int(size) if size is not None else 0

                    is_partition = PARTITION_INTERFACE in interfaces
                    # Assuming LOOP_INTERFACE is defined elsewhere or check property
                    is_loop = LOOP_INTERFACE in interfaces if 'LOOP_INTERFACE' in globals() else ('Loop' in block_props and block_props['Loop'])

                    # Safely get HintIgnore property
                    is_ignored_variant = block_props.get('HintIgnore', GLib.Variant('b', False))
                    is_ignored = is_ignored_variant.unpack() if isinstance(is_ignored_variant, GLib.Variant) else is_ignored_variant

                    # Safely get HintSystem property
                    is_system_variant = block_props.get('HintSystem', GLib.Variant('b', False))
                    is_system = is_system_variant.unpack() if isinstance(is_system_variant, GLib.Variant) else is_system_variant

                    # Safely get IdUsage property
                    id_usage_variant = block_props.get('IdUsage', GLib.Variant('s', ''))
                    id_usage = id_usage_variant.unpack() if isinstance(id_usage_variant, GLib.Variant) else id_usage_variant
                    is_crypto = (id_usage == 'crypto')

                    # --- Filtering Logic ---
                    # Skip partitions, loop devices, ignored devices, crypto placeholders
                    # Skip devices smaller than a certain threshold (e.g., 1GB)? Maybe later.
                    if is_partition or is_loop or is_ignored or is_crypto:
                        # print(f"Skipping {device_file}: partition={is_partition}, loop={is_loop}, ignored={is_ignored}, crypto={is_crypto}")
                        continue

                    # Get Drive info for model/vendor (Safely unpack these too)
                    model = "Unknown Model"
                    vendor = "Unknown Vendor"
                    if drive_path != '/' and drive_path in objects and DRIVE_INTERFACE in objects[drive_path]:
                         drive_props = objects[drive_path][DRIVE_INTERFACE]
                         model_variant = drive_props.get('Model', GLib.Variant('s', model))
                         model = model_variant.unpack() if isinstance(model_variant, GLib.Variant) else model_variant
                         vendor_variant = drive_props.get('Vendor', GLib.Variant('s', vendor))
                         vendor = vendor_variant.unpack() if isinstance(vendor_variant, GLib.Variant) else vendor_variant

                    # Clean the final device file path
                    clean_device_file = device_file.rstrip('\x00')
                    disk_info = {
                        "name": clean_device_file.split('/')[-1], # e.g., sda
                        "size": format_size(size),
                        "model": f"{vendor} {model}".strip(),
                        "path": clean_device_file # Full path, e.g., /dev/sda
                    }
                    found_disks.append(disk_info)
                    print(f"  Found suitable disk: {disk_info}")

            # Sort disks alphabetically by name (e.g., sda, sdb, nvme0n1)
            found_disks.sort(key=lambda d: d['name'])

            # Populate the ListBox
            if not found_disks:
                 print("No suitable installation disks found.")
                 # Add a placeholder row indicating no disks found
                 row = Adw.ActionRow(title="No installable disks found", 
                                     subtitle="Check your system configuration.")
                 row.set_activatable(False)
                 self.disk_list_box.append(row)
            else:
                for disk in found_disks:
                    row = Adw.ActionRow(title=f"{disk['model']} ({disk['name']})")
                    row.add_suffix(Gtk.Label(label=disk['size']))
                    row.set_activatable(True)
                    row.disk_path = disk['path']
                    self.disk_list_box.append(row)

        except GLib.Error as e:
            print(f"Error during UDisks2 interaction: {e}")
            self.show_error_dialog("Disk Detection Error", 
                                   f"Failed to retrieve disk information: {e.message}")
        except Exception as e:
            print(f"Unexpected error processing UDisks2 data: {e}")
            import traceback
            traceback.print_exc()
            self.show_error_dialog("Disk Detection Error", f"An unexpected error occurred: {e}")

    def on_disk_selection_changed(self, list_box):
        """Called when the selected disks change."""
        selected_rows = list_box.get_selected_rows()
        self._selected_disks = [row.disk_path for row in selected_rows if hasattr(row, 'disk_path')]
        print(f"Selected disks: {self._selected_disks}")
        self.update_summary()

    def on_config_option_changed(self, check_button):
        """Called when Automatic/Custom configuration option changes."""
        if not check_button.get_active(): # Only react when one is activated
            return
        if check_button == self.config_auto_check:
            print("Configuration set to Automatic")
        elif check_button == self.config_custom_check:
            print("Configuration set to Custom")
            # TODO: Enable/trigger custom partitioning tool/dialog
        self.update_summary()

    def update_summary(self):
        """Updates the summary label based on selections."""
        num_selected = len(self._selected_disks)
        config_mode = "Automatic" if self.config_auto_check.get_active() else "Custom"
        summary = f"Selected {num_selected} disk(s). Configuration: {config_mode}."
        if config_mode == "Custom" and num_selected > 0:
            summary += " (Manual partitioning required)"
        elif num_selected == 0:
            summary = "Please select at least one disk."
            # TODO: Possibly disable the 'Continue' button via a signal/property

        self.space_summary_label.set_label(summary)

    def get_selected_config(self):
        """Returns the selected disks and configuration mode."""
        return {
            "disks": self._selected_disks,
            "config_mode": "Automatic" if self.config_auto_check.get_active() else "Custom"
        }
        
    def show_error_dialog(self, title, message):
         # Helper to show errors - find the top-level window
         top_level = self.get_ancestor(Gtk.Window)
         dialog = Adw.MessageDialog.new(top_level, title, message)
         dialog.add_response("ok", "OK")
         dialog.set_default_response("ok")
         dialog.connect("response", lambda d, r: d.close())
         dialog.present() 