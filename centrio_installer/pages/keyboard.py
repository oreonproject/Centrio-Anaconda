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

class KeyboardPage(BaseConfigurationPage):
    def __init__(self, main_window, overlay_widget, **kwargs):
        super().__init__(title="Keyboard Layout", subtitle="Select your keyboard layout", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.localization_proxy = None
        self.layout_list = ["us"] # Default fallback
        self.initial_fetch_done = False

        # --- UI Setup --- 
        key_group = Adw.PreferencesGroup()
        self.add(key_group)
        # Model will be populated after fetching data
        self.layout_row = Adw.ComboRow(title="Keyboard Layout", model=Gtk.StringList.new([]))
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
        """Fetches available layouts and current layout from D-Bus proxy."""
        if not self.localization_proxy:
             return False 

        available_layouts = []
        current_layout = None
        try:
            # Fetch available keyboard layouts
            # Assuming a method like GetAvailableKeyboardLayouts() exists
            # The actual method name might differ, check LocalizationInterface
            available_layouts = self.localization_proxy.GetAvailableKeyboardLayouts()
            print(f"KeyboardPage: Fetched {len(available_layouts)} layouts via D-Bus.")
            
            # Fetch the current keyboard layout
            # Assuming a property or method like KeyboardLayout or GetKeyboardLayout()
            current_layout_struct = self.localization_proxy.GetKeyboard()
            # The structure might be complex, e.g., ("us", "", "") for layout, variant, options
            # Extract the primary layout part
            if isinstance(current_layout_struct, (list, tuple)) and len(current_layout_struct) > 0:
                 current_layout = current_layout_struct[0]
                 print(f"KeyboardPage: Fetched current layout via D-Bus: {current_layout}")
            else:
                 print(f"KeyboardPage: Received unexpected format for current layout: {current_layout_struct}")
                 current_layout = None # Fallback if format is wrong

            if not available_layouts:
                 available_layouts = self.layout_list # Use fallback if D-Bus returns empty
                 print("Warning: D-Bus returned empty layout list, using fallback.")

        except DBusError as e:
            print(f"ERROR: D-Bus error fetching keyboard data: {e}")
            self.show_toast(f"Error fetching keyboard data: {e}")
            available_layouts = self.layout_list # Use fallback
        except AttributeError as e:
             print(f"ERROR: D-Bus method/property not found: {e}. Check LocalizationInterface definition.")
             self.show_toast(f"D-Bus call failed: {e}")
             available_layouts = self.layout_list # Use fallback
        except Exception as e:
            print(f"ERROR: Unexpected error fetching keyboard data: {e}")
            self.show_toast("Unexpected error fetching keyboard data.")
            available_layouts = self.layout_list # Use fallback
        finally:
             # Update UI with fetched data (or fallback)
             self._update_ui_with_layouts(available_layouts, current_layout)
             self.initial_fetch_done = True
             
        return False # Stop GLib.idle_add
        
    def _update_ui_with_layouts(self, layouts, current_layout):
         """Updates the ComboRow model and selection."""
         self.layout_list = sorted(layouts) # Store sorted list
         model = Gtk.StringList.new(self.layout_list)
         self.layout_row.set_model(model)
         
         selected_idx = -1
         if current_layout and current_layout in self.layout_list:
             try:
                 selected_idx = self.layout_list.index(current_layout)
             except ValueError:
                 pass # Not found
         
         if selected_idx >= 0:
             self.layout_row.set_selected(selected_idx)
         elif self.layout_list: # Default to first item if current not found or None
             self.layout_row.set_selected(0)
             
         # Enable UI elements
         self.layout_row.set_sensitive(True)
         self.complete_button.set_sensitive(True)
         if not self.layout_list:
              self.layout_row.set_subtitle("No layouts available")
              self.complete_button.set_sensitive(False)

    def apply_settings_and_return(self, button):
        """Applies the selected keyboard layout via D-Bus."""
        if not self.initial_fetch_done:
            self.show_toast("Still fetching initial configuration...")
            return
            
        selected_idx = self.layout_row.get_selected()
        if not self.layout_list or selected_idx < 0 or selected_idx >= len(self.layout_list):
            self.show_toast("Invalid keyboard layout selection.")
            return
            
        selected_layout = self.layout_list[selected_idx]
            
        print(f"Applying Keyboard Layout '{selected_layout}' via D-Bus...")
        self.complete_button.set_sensitive(False)
        
        if self.localization_proxy:
            try:
                # Call the SetKeyboard method on the D-Bus proxy
                # Anaconda expects a tuple (or list): (layout, variant, options)
                # For simplicity, we'll set variant and options to empty strings.
                self.localization_proxy.SetKeyboard([selected_layout, "", ""])
                print("Keyboard layout successfully set via D-Bus.")
                self.show_toast(f"Keyboard layout '{selected_layout}' applied.")
                
                config_values = {"layout": selected_layout}
                super().mark_complete_and_return(button, config_values=config_values)
                
            except DBusError as e:
                print(f"ERROR: D-Bus error setting keyboard layout: {e}")
                self.show_toast(f"Error setting keyboard layout: {e}")
                self.complete_button.set_sensitive(True) 
            except AttributeError as e:
                 print(f"ERROR: D-Bus method SetKeyboard not found: {e}. Check LocalizationInterface.")
                 self.show_toast(f"Failed to apply layout (D-Bus error): {e}")
                 self.complete_button.set_sensitive(True)
            except Exception as e:
                print(f"ERROR: Unexpected error applying keyboard settings: {e}")
                self.show_toast(f"Unexpected error setting keyboard layout: {e}")
                self.complete_button.set_sensitive(True) 
        else:
            self.show_toast("Cannot apply layout: D-Bus connection not available.")
            # Mark complete with selected value even if D-Bus failed?
            print("Marking complete with chosen layout despite D-Bus failure.")
            config_values = {"layout": selected_layout}
            super().mark_complete_and_return(button, config_values=config_values) 