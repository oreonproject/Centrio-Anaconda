import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib
import os # For listing /usr/share/zoneinfo
from collections import defaultdict
import time

# systemd timedate DBus constants
TIMEDATE_BUS_NAME = 'org.freedesktop.timedate1'
TIMEDATE_OBJECT_PATH = '/org/freedesktop/timedate1'
PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties'
TIMEDATE_INTERFACE = 'org.freedesktop.timedate1'
ZONEINFO_BASE_PATH = '/usr/share/zoneinfo'

# Regions to potentially ignore (often links or special files)
IGNORE_REGIONS = ['Etc', 'SystemV', 'US', 'posix', 'right'] 

@Gtk.Template(filename='ui/timezone_selection.ui')
class TimezoneSelectionView(Gtk.Box):
    __gtype_name__ = 'TimezoneSelectionView'

    # Template Children
    region_search_entry = Gtk.Template.Child()
    region_list_box = Gtk.Template.Child()
    city_search_entry = Gtk.Template.Child()
    city_list_box = Gtk.Template.Child()
    selected_timezone_label = Gtk.Template.Child()
    ntp_switch = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected_timezone = None
        self._current_region = None
        self._timezone_map = defaultdict(list)
        self._timedate_proxy = None
        
        self._load_timezones_from_fs()
        self._populate_region_list()
        self._fetch_initial_timedate_settings()

        # Connect signals
        self.region_list_box.connect("row-selected", self.on_region_selected)
        self.city_list_box.connect("row-selected", self.on_city_selected)
        self.region_search_entry.connect("search-changed", self.on_region_search_changed)
        self.city_search_entry.connect("search-changed", self.on_city_search_changed)
        self.ntp_switch.connect("notify::active", self.on_ntp_toggled)
        
        self.update_display()
        print("TimezoneSelectionView initialized")

    def _get_timedate_proxy(self):
        """Gets the Gio DBus proxy for timedate service properties."""
        if self._timedate_proxy:
            return self._timedate_proxy
        try:
            # We need the Properties interface to get values
            self._timedate_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None, 
                TIMEDATE_BUS_NAME,
                TIMEDATE_OBJECT_PATH,
                PROPERTIES_INTERFACE, # Get the properties interface
                None 
            )
            print("Successfully connected to timedate1 DBus service.")
            return self._timedate_proxy
        except GLib.Error as e:
            print(f"Error connecting to timedate1 DBus: {e}")
            # Non-fatal, maybe just can't get defaults
            return None

    def _fetch_initial_timedate_settings(self):
        """Fetches current timezone and NTP status via DBus."""
        proxy = self._get_timedate_proxy()
        if not proxy:
            print("Cannot fetch initial timezone settings (DBus proxy failed)")
            return

        try:
            # Get Timezone property
            variant = proxy.call_sync('Get', 
                                      GLib.Variant('(ss)', (TIMEDATE_INTERFACE, 'Timezone')),
                                      Gio.DBusCallFlags.NONE, -1, None)
            if variant:
                # Property Get returns Variant('(v)',) where v contains the actual value
                # Unpack once to get the inner value
                value_variant = variant.unpack()[0] 
                # Now check type before using
                current_tz = value_variant.unpack() if isinstance(value_variant, GLib.Variant) else value_variant
                if not isinstance(current_tz, str):
                    current_tz = str(current_tz) # Ensure it's a string
                    
                print(f"Current system timezone: {current_tz}")
                self.set_selected_timezone(current_tz)
            else:
                print("Failed to get Timezone property.")

            # Get NTP property
            variant = proxy.call_sync('Get', 
                                      GLib.Variant('(ss)', (TIMEDATE_INTERFACE, 'NTP')),
                                      Gio.DBusCallFlags.NONE, -1, None)
            if variant:
                 # Property Get returns Variant('(v)',) where v contains the actual value
                 value_variant = variant.unpack()[0]
                 ntp_enabled = value_variant.unpack() if isinstance(value_variant, GLib.Variant) else value_variant
                 print(f"Current NTP status: {'Enabled' if ntp_enabled else 'Disabled'}")
                 self.ntp_switch.set_active(bool(ntp_enabled)) # Ensure boolean
            else:
                 print("Failed to get NTP property.")

        except GLib.Error as e:
            print(f"DBus error fetching timedate properties: {e}")
        except Exception as e:
             print(f"Unexpected error fetching timedate properties: {e}")
             import traceback
             traceback.print_exc()
             
    def _load_timezones_from_fs(self):
        """Scans ZONEINFO_BASE_PATH to build the timezone map."""
        print(f"Loading timezones from {ZONEINFO_BASE_PATH}...")
        self._timezone_map = defaultdict(list)
        if not os.path.isdir(ZONEINFO_BASE_PATH):
            print(f"Error: Zoneinfo directory not found: {ZONEINFO_BASE_PATH}")
            # TODO: Show error in UI?
            return

        for region in sorted(os.listdir(ZONEINFO_BASE_PATH)):
            region_path = os.path.join(ZONEINFO_BASE_PATH, region)
            # Skip ignored regions and non-directories/links
            if region in IGNORE_REGIONS or not (os.path.isdir(region_path) or os.path.islink(region_path)):
                continue

            # If it's a link, check if it points to a directory we might process
            if os.path.islink(region_path):
                 target = os.path.realpath(region_path)
                 if not os.path.isdir(target):
                     continue # Skip links to non-directories
                 # Use the link name as the region name if it's outside ignored
                 region_path = target # Process the target directory
                 if region in IGNORE_REGIONS:
                      continue # Still ignore if link name is bad
            
            # List cities/areas within the region
            try:
                 for city in sorted(os.listdir(region_path)):
                     city_path = os.path.join(region_path, city)
                     # Check if it's a timezone file (not a directory, not ending in .tab etc.)
                     if os.path.isfile(city_path) and not city.endswith('.tab') and '/' not in city:
                         # City might contain subdirs, replace / with _ for display? No, keep original.
                         # But the ID is Region/City
                         tz_id = f"{region}/{city}"
                         self._timezone_map[region].append(city)
                     elif os.path.isdir(city_path): # Handle Region/SubRegion/City structure like America/Argentina/Buenos_Aires
                         sub_region = city
                         sub_region_path = city_path
                         for sub_city in sorted(os.listdir(sub_region_path)):
                              sub_city_path = os.path.join(sub_region_path, sub_city)
                              if os.path.isfile(sub_city_path) and not sub_city.endswith('.tab') and '/' not in sub_city:
                                   city_name_with_sub = f"{sub_region}/{sub_city}"
                                   tz_id = f"{region}/{city_name_with_sub}"
                                   self._timezone_map[region].append(city_name_with_sub)
            except OSError as e:
                 print(f"Warning: Could not read {region_path}: {e}")

        print(f"Loaded {len(self._timezone_map)} regions.")

    def _populate_region_list(self, search_term=None):
        """Populates the region list box, optionally filtered."""
        self._clear_list_box(self.region_list_box)
        term = search_term.lower() if search_term else None
        regions = sorted(self._timezone_map.keys())
        
        for region in regions:
             if term is None or term in region.lower():
                 row = Gtk.Label(label=region, xalign=0)
                 self.region_list_box.append(row)
                 
        # Try to select the current region if it exists
        if self._selected_timezone:
            current_region = self._selected_timezone.split('/')[0]
            self._select_item_in_list(self.region_list_box, current_region)
        elif self.region_list_box.get_first_child(): # Select first if nothing else
              self.region_list_box.select_row(self.region_list_box.get_row_at_index(0))

    def _populate_city_list(self, search_term=None):
        """Populates the city list box based on the selected region and search term."""
        self._clear_list_box(self.city_list_box)
        self.city_search_entry.set_sensitive(bool(self._current_region))
        if not self._current_region:
            return
            
        term = search_term.lower() if search_term else None
        cities = sorted(self._timezone_map.get(self._current_region, []))
        
        for city in cities:
             # Replace underscores for slightly nicer display? Maybe not.
             display_city = city # .replace('_', ' ') 
             if term is None or term in city.lower().replace('_', ' '): # Search ignores underscore
                 row = Gtk.Label(label=display_city, xalign=0)
                 self.city_list_box.append(row)
                 
        # Try to select the current city if it exists in this region
        if self._selected_timezone and self._selected_timezone.startswith(self._current_region + '/'):
             current_city = '/'.join(self._selected_timezone.split('/')[1:])
             self._select_item_in_list(self.city_list_box, current_city)
        elif self.city_list_box.get_first_child(): # Select first if nothing else
             self.city_list_box.select_row(self.city_list_box.get_row_at_index(0))

    def _clear_list_box(self, list_box):
         child = list_box.get_first_child()
         while child:
             next_child = child.get_next_sibling()
             list_box.remove(child)
             child = next_child

    def _select_item_in_list(self, list_box, item_text):
         child = list_box.get_first_child()
         idx = 0
         while child:
             if isinstance(child, Gtk.ListBoxRow) and isinstance(child.get_child(), Gtk.Label):
                 if child.get_child().get_label() == item_text:
                     list_box.select_row(child)
                     # Scroll to selection? Gtk.Scrollable policy might handle it
                     adj = list_box.get_parent().get_vadjustment() # Get adjustment from ScrolledWindow
                     if adj:
                          # Calculate position (approximate)
                          row_height = child.get_height()
                          pos = idx * row_height - (adj.get_page_size() / 2) + (row_height / 2)
                          # Use idle_add to ensure layout is done before scrolling
                          GLib.idle_add(adj.set_value, max(0, pos))
                     return True
             child = child.get_next_sibling()
             idx += 1
         return False

    def set_selected_timezone(self, timezone_id):
        """Sets the timezone and updates the UI selections."""
        if not timezone_id or '/' not in timezone_id:
             print(f"Invalid timezone format received: {timezone_id}")
             self._selected_timezone = None
             self._current_region = None
             self._populate_region_list()
             self._populate_city_list()
             self.update_display()
             return

        region, city = timezone_id.split('/', 1) # Split only once
        if region in self._timezone_map and city in self._timezone_map[region]:
             self._selected_timezone = timezone_id
             self._current_region = region
             # Update lists and selections
             self._select_item_in_list(self.region_list_box, region)
             self._populate_city_list() # This will select the city
        else:
             print(f"Warning: Timezone '{timezone_id}' not found in loaded map.")
             self._selected_timezone = None # Clear if invalid
             self._current_region = None
             # Reset selections? Or keep region selected?
             # Let's try keeping region selected if it was valid
             if region in self._timezone_map:
                  self._current_region = region
                  self._select_item_in_list(self.region_list_box, region)
                  self._populate_city_list()
             else:
                  # Invalid region, clear all
                  self.region_list_box.unselect_all()
                  self._populate_city_list()
                  
        self.update_display()

    # --- Signal Handlers ---
    def on_region_selected(self, list_box, row):
        if row and isinstance(row.get_child(), Gtk.Label):
            self._current_region = row.get_child().get_label()
            print(f"Region selected: {self._current_region}")
            self.city_search_entry.set_text("") # Clear city search
            self._populate_city_list()
            # Clear overall selection until city is chosen
            self._selected_timezone = None 
            self.update_display()
        else:
             self._current_region = None
             self._populate_city_list() # Clear city list
             self._selected_timezone = None 
             self.update_display()

    def on_city_selected(self, list_box, row):
        if row and isinstance(row.get_child(), Gtk.Label) and self._current_region:
            city = row.get_child().get_label()
            self._selected_timezone = f"{self._current_region}/{city}"
            print(f"Timezone selected: {self._selected_timezone}")
        else:
            # Deselection or invalid state
            self._selected_timezone = None
        self.update_display()

    def on_region_search_changed(self, entry):
        search_term = entry.get_text()
        self._populate_region_list(search_term)

    def on_city_search_changed(self, entry):
        search_term = entry.get_text()
        self._populate_city_list(search_term)

    def on_ntp_toggled(self, switch, param):
        is_active = switch.get_active()
        print(f"Network Time (NTP) {'enabled' if is_active else 'disabled'}")
        # TODO: Call SetNTP on timedate1 DBus interface?

    # --- Public Methods ---
    def update_display(self):
        """Updates the display label with the current selection."""
        display_tz = self._selected_timezone if self._selected_timezone else "None"
        self.selected_timezone_label.set_label(f"Selected Timezone: {display_tz}")

    def get_selected_timezone_config(self):
        """Returns the selected timezone and NTP setting."""
        if not self._selected_timezone:
             print("Validation Error: No timezone selected.")
             return None 
        return {
            "timezone": self._selected_timezone,
            "ntp_enabled": self.ntp_switch.get_active()
        }

    # --- Placeholder for future implementation ---
    # def _fetch_available_timezones(self):
    #     # Use subprocess.run(['timedatectl', 'list-timezones'])
    #     # or preferably Gio.DBusProxy to talk to systemd-timedated
    #     pass
    #
    # def _set_timezone_via_dbus(self, timezone_id):
    #     # Use Gio.DBusProxy to call SetTimezone on systemd-timedated
    #     pass 