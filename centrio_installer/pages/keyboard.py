# centrio_installer/pages/keyboard.py

import gi
# Remove subprocess and re imports
# import subprocess
# import re
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib # Added GLib

# Import D-Bus utils and constants
from .base import BaseConfigurationPage, dbus_available, DBusError, get_dbus_proxy
from ..constants import LOCALIZATION_SERVICE, LOCALIZATION_OBJECT_PATH, LOCALIZATION_INTERFACE
from ..utils import ana_get_keyboard_layouts # Keep layout list getter

class KeyboardPage(BaseConfigurationPage):
    def __init__(self, main_window, overlay_widget, **kwargs):
        super().__init__(title="Keyboard Layout", subtitle="Select your keyboard layout", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.localization_proxy = None
        self.layout_list = ana_get_keyboard_layouts()
        self.initial_fetch_done = False

        # --- UI Setup --- 
        key_group = Adw.PreferencesGroup()
        self.add(key_group)
        # Model will be populated after fetching data
        model = Gtk.StringList.new(self.layout_list)
        self.layout_row = Adw.ComboRow(title="Keyboard Layout", model=model)
        key_group.add(self.layout_row)
        
        test_row = Adw.ActionRow(title="Test your keyboard settings")
        test_entry = Gtk.Entry()
        test_entry.set_placeholder_text("Type here to test layout...")
        test_row.add_suffix(test_entry)
        test_row.set_activatable_widget(test_entry)
        key_group.add(test_row)

        button_group = Adw.PreferencesGroup()
        self.add(button_group) 
        self.complete_button = Gtk.Button(label="Apply Keyboard Layout")
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        self.complete_button.connect("clicked", self.apply_settings_and_return)
        # Start insensitive until data is fetched
        self.complete_button.set_sensitive(False)
        self.layout_row.set_sensitive(False)
        button_group.add(self.complete_button)
        
        # --- Fetch Current Settings --- 
        self.connect_and_fetch_data()
            
    def connect_and_fetch_data(self):
        """Connects to Localization D-Bus service and fetches keyboard layouts."""
        print("KeyboardPage: Connecting to D-Bus...")
        if not dbus_available:
            self.show_toast("D-Bus is not available. Cannot fetch keyboard layouts.")
            self._update_ui_with_layouts(self.layout_list, None) # Use fallback
            self.initial_fetch_done = True
            return
            
        self.localization_proxy = get_dbus_proxy(LOCALIZATION_SERVICE, LOCALIZATION_OBJECT_PATH, LOCALIZATION_INTERFACE)
        
        if self.localization_proxy:
            print("KeyboardPage: Successfully got D-Bus proxy.")
            # Fetch layouts and current setting asynchronously
            GLib.idle_add(self._fetch_keyboard_data)
        else:
            self.show_toast("Failed to connect to Localization D-Bus service.")
            self._update_ui_with_layouts(self.layout_list, None) # Use fallback
            self.initial_fetch_done = True

    def _fetch_keyboard_data(self):
        """Fetches keyboard layouts and current setting (async via idle_add)."""
        # Check proxy validity
        if not self.localization_proxy:
             self.show_toast("Localization D-Bus service is not available.")
             self._update_ui_with_layouts(self.layout_list, None, success=False)
             self.initial_fetch_done = True
             return False

        fetched_layouts = []
        current_keymap = None
        success = False
        try:
            print("KeyboardPage: Fetching keyboard data via D-Bus...")
            # Assuming ListConsoleKeymaps() -> list[str]
            fetched_layouts = self.localization_proxy.ListConsoleKeymaps()
            # Assuming VirtualConsoleKeymap property -> str
            current_keymap = self.localization_proxy.get_VirtualConsoleKeymap()
            print(f"KeyboardPage: Fetched layouts: {len(fetched_layouts)}, current: {current_keymap}")
            success = True
        except (DBusError, AttributeError) as e: 
            print(f"ERROR: D-Bus error fetching keyboard data: {e}")
            self.show_toast(f"Error fetching keyboard data: {e}")
            fetched_layouts = self.layout_list # Use fallback
            current_keymap = None # Cannot determine current
        except Exception as e:
            print(f"ERROR: Unexpected error fetching keyboard data: {e}")
            self.show_toast("Unexpected error fetching keyboard data.")
            fetched_layouts = self.layout_list
            current_keymap = None
        finally:
            self._update_ui_with_layouts(fetched_layouts, current_keymap, success)
            self.initial_fetch_done = True
             
        return False

    def _update_ui_with_layouts(self, layouts, current_layout, success=True):
        """Populates the layout list and selects the current one."""
        self.available_layouts = sorted(layouts)
        
        model = Gtk.StringList.new(self.available_layouts)
        self.layout_row.set_model(model)
        
        selected_idx = -1
        if current_layout and current_layout in self.available_layouts:
            try:
                selected_idx = self.available_layouts.index(current_layout)
            except ValueError:
                 pass # Should not happen if check passes
                 
        if selected_idx >= 0:
            self.layout_row.set_selected(selected_idx)
        elif self.available_layouts:
            self.layout_row.set_selected(0) # Default to first if current not found
            
        # Enable/disable UI based on success
        can_proceed = success and bool(self.available_layouts)
        self.layout_row.set_sensitive(can_proceed)
        self.complete_button.set_sensitive(can_proceed)
        if not can_proceed:
            subtitle = "Failed to load layouts" if not success else "No layouts available"
            self.layout_row.set_subtitle(subtitle)
        else:
            self.layout_row.set_subtitle(None) # Clear subtitle on success

    def apply_settings_and_return(self, button):
        """Applies the selected keyboard layout via D-Bus."""
        # Check proxy validity first
        if not self.localization_proxy:
            self.show_toast("Cannot apply layout: Localization D-Bus service is not available.")
            self.complete_button.set_sensitive(False)
            return
            
        if not self.initial_fetch_done:
            self.show_toast("Still fetching initial configuration...")
            return
            
        selected_idx = self.layout_row.get_selected()
        if not self.available_layouts or selected_idx < 0 or selected_idx >= len(self.available_layouts):
             self.show_toast("Invalid layout selection.")
             return
             
        selected_layout = self.available_layouts[selected_idx]
        print(f"Applying Keyboard Layout '{selected_layout}' via D-Bus...")
        self.complete_button.set_sensitive(False)
        
        try:
            # Assuming SetConsoleKeymap(layout_name)
            self.localization_proxy.SetConsoleKeymap(selected_layout)
            print("Keyboard layout successfully set via D-Bus.")
            self.show_toast(f"Keyboard layout '{selected_layout}' applied.")
            
            config_values = {"layout": selected_layout}
            super().mark_complete_and_return(button, config_values=config_values)
            
        except (DBusError, AttributeError) as e: 
            print(f"ERROR: D-Bus error setting keyboard layout: {e}")
            self.show_toast(f"Error setting keyboard layout: {e}")
            self.complete_button.set_sensitive(True) # Re-enable on error
        except Exception as e:
            print(f"ERROR: Unexpected error setting keyboard layout: {e}")
            self.show_toast(f"Unexpected error setting layout: {e}")
            self.complete_button.set_sensitive(True) # Re-enable on error 