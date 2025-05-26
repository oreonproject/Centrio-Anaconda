import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
import subprocess
import locale

# Anaconda DBus service constants
ANACONDA_BUS_NAME = 'org.fedoraproject.Anaconda.Modules.Localization'
ANACONDA_OBJECT_PATH = '/org/fedoraproject/Anaconda/Modules/Localization'
ANACONDA_INTERFACE = 'org.fedoraproject.Anaconda.Modules.Localization'


@Gtk.Template(filename='ui/keyboard_layout.ui')
class KeyboardLayoutView(Gtk.Box):
    __gtype_name__ = 'KeyboardLayoutView'

    # Template children
    search_entry = Gtk.Template.Child()
    layout_list_box = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_layout = None
        self._all_layouts = []
        self._dbus_proxy = None
        self._connect_to_anaconda()
        self.populate_layouts()
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.layout_list_box.connect("row-selected", self.on_row_selected)
        print("KeyboardLayoutView initialized and populated")
        
    def _connect_to_anaconda(self):
        """Connect to Anaconda's DBus service."""
        try:
            self._dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                ANACONDA_BUS_NAME,
                ANACONDA_OBJECT_PATH,
                ANACONDA_INTERFACE,
                None
            )
            print("Connected to Anaconda Localization service")
        except GLib.Error as e:
            print(f"Failed to connect to Anaconda Localization service: {e}")
            self._show_error("Connection Error", 
                           "Could not connect to the Anaconda Localization service. "
                           "Running in offline mode with limited functionality.")
    
    def _show_error(self, title, message):
        """Show an error dialog."""
        dialog = Adw.MessageDialog.new(
            transient_for=self.get_root(),
            heading=title,
            body=message
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def get_available_layouts(self):
        """Fetches available X11 keyboard layouts using Anaconda's DBus service."""
        if not self._dbus_proxy:
            print("DBus proxy not available, using fallback method")
            return self._get_layouts_fallback()
            
        try:
            # Call the GetXLayouts method on the DBus interface
            result = self._dbus_proxy.call_sync(
                'GetXLayouts',
                None,  # No parameters
                Gio.DBusCallFlags.NONE,
                -1,  # Default timeout
                None  # Cancellable
            )
            
            # The result should be a list of layout strings
            layouts = result.unpack()[0] if result else []
            print(f"Found {len(layouts)} layouts via DBus")
            return layouts
            
        except GLib.Error as e:
            print(f"Error getting layouts from Anaconda: {e}")
            return self._get_layouts_fallback()
    
    def _get_layouts_fallback(self):
        """Fallback method to get layouts using localectl."""
        try:
            result = subprocess.run(["localectl", "list-x11-keymap-layouts"], 
                                  capture_output=True, text=True, check=True)
            layouts = result.stdout.strip().split('\n')
            try:
                locale.setlocale(locale.LC_COLLATE, '')
            except locale.Error:
                pass  # Keep default C locale if setting fails
            layouts.sort(key=locale.strxfrm)
            print(f"Found {len(layouts)} layouts via localectl")
            return layouts
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"Error running localectl: {e}")
            return ["us", "gb", "de", "fr"]  # Default fallback

    def populate_layouts(self):
        """Populates the list box with available layouts."""
        self._all_layouts = self.get_available_layouts()
        self.update_list_filter(None) # Show all initially

    def update_list_filter(self, search_term):
        """Filters the list box based on the search term."""
        # Clear existing rows before adding filtered ones
        child = self.layout_list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.layout_list_box.remove(child)
            child = next_child

        # Add rows that match the search term (case-insensitive)
        term = search_term.lower() if search_term else None
        for layout in self._all_layouts:
            if term is None or term in layout.lower():
                # Create a new ListBoxRow
                row = Gtk.ListBoxRow()
                # Create a box to hold the layout label
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                # Create the layout label
                label = Gtk.Label(label=layout, xalign=0)
                label.set_hexpand(True)
                box.append(label)
                # Add the box to the row
                row.set_child(box)
                # Add the row to the list box
                self.layout_list_box.append(row)
        
        # Select the first item if list is not empty and something was selected previously or nothing was
        if self.selected_layout and any(c.get_label() == self.selected_layout for c in self.get_list_rows()):
             self.select_layout_in_list(self.selected_layout)
        elif not self.selected_layout and self.layout_list_box.get_first_child():
             self.layout_list_box.select_row(self.layout_list_box.get_row_at_index(0))

    def on_search_changed(self, entry):
        """Called when the search text changes."""
        search_term = entry.get_text()
        self.update_list_filter(search_term)

    def on_row_selected(self, list_box, row):
        """Called when a layout is selected in the list."""
        if row:
            # Get the box containing the label
            box = row.get_child()
            # Get the first child of the box, which is our label
            label = box.get_first_child()
            if label and isinstance(label, Gtk.Label):
                self.selected_layout = label.get_label()
                print(f"Selected layout: {self.selected_layout}")
                self._set_keyboard_layout(self.selected_layout)
        else:
            self.selected_layout = None
            print("Layout deselected")
    
    def _set_keyboard_layout(self, layout):
        """Set the keyboard layout using Anaconda's DBus service."""
        if not self._dbus_proxy:
            print("DBus proxy not available, cannot set keyboard layout")
            return
            
        try:
            # Set the X layout using Anaconda's DBus interface
            self._dbus_proxy.call_sync(
                'SetXLayouts',
                GLib.Variant('(as)', ([layout],)),  # Method expects an array of strings
                Gio.DBusCallFlags.NONE,
                -1,  # Default timeout
                None  # Cancellable
            )
            print(f"Successfully set keyboard layout to: {layout}")
            
            # Also set the virtual console keymap if it's a simple layout
            if ' ' not in layout and '(' not in layout:
                self._dbus_proxy.call_sync(
                    'SetVirtualConsoleKeymap',
                    GLib.Variant('(s)', (layout,)),
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None
                )
                print(f"Set virtual console keymap to: {layout}")
                
        except GLib.Error as e:
            print(f"Error setting keyboard layout: {e}")
            self._show_error("Keyboard Error", 
                           f"Failed to set keyboard layout: {e.message}")
            
    def get_list_rows(self):
        """Helper to get all GtkLabel children from the listbox rows."""
        rows = []
        child = self.layout_list_box.get_first_child()
        while child:
            if isinstance(child, Gtk.ListBoxRow):
                box = child.get_child()
                if box and isinstance(box, Gtk.Box):
                    label = box.get_first_child()
                    if label and isinstance(label, Gtk.Label):
                        rows.append(label)
            child = child.get_next_sibling()
        return rows

    def select_layout_in_list(self, layout_name):
        """Programmatically selects a layout in the list."""
        child = self.layout_list_box.get_first_child()
        while child:
            if isinstance(child, Gtk.ListBoxRow):
                box = child.get_child()
                if box and isinstance(box, Gtk.Box):
                    label = box.get_first_child()
                    if label and isinstance(label, Gtk.Label) and label.get_label() == layout_name:
                        self.layout_list_box.select_row(child)
                        break
            child = child.get_next_sibling()

    def get_selected_layout(self):
        """Returns the currently selected layout name."""
        return self.selected_layout 