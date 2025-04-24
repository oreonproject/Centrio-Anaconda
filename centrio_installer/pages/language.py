# centrio_installer/pages/language.py

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

class LanguagePage(BaseConfigurationPage):
    def __init__(self, main_window, overlay_widget, **kwargs):
        # Changed title and subtitle to reflect setting system locale
        super().__init__(title="System Language", subtitle="Select the primary language for the installed system", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.localization_proxy = None
        # Use dict {code: display_name} for available locales
        self.available_locales = {"en_US.UTF-8": "English (US)"} # Default fallback
        self.locale_codes = list(self.available_locales.keys()) # Codes for model
        self.initial_fetch_done = False

        # --- UI Setup --- 
        lang_group = Adw.PreferencesGroup(title="System Locale")
        self.add(lang_group)
        
        # Model needs codes, Expression for display name
        self.locale_row = Adw.ComboRow(title="Locale", model=Gtk.StringList.new([]))
        # We will set the model and potentially an expression after fetching data
        lang_group.add(self.locale_row)

        button_group = Adw.PreferencesGroup()
        self.add(button_group)
        self.complete_button = Gtk.Button(label="Apply System Locale")
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        self.complete_button.connect("clicked", self.apply_settings_and_return)
        # Start insensitive
        self.complete_button.set_sensitive(False)
        self.locale_row.set_sensitive(False)
        button_group.add(self.complete_button)

        # --- Fetch Current Settings --- 
        self.connect_and_fetch_data() 

    def connect_and_fetch_data(self):
        """Connects to Localization D-Bus service and fetches locales."""
        print("LanguagePage: Connecting to D-Bus...")
        if not dbus_available:
            self.show_toast("D-Bus is not available. Cannot fetch locales.")
            self._update_ui_with_locales(self.available_locales, None) # Use fallback
            self.initial_fetch_done = True
            return
            
        self.localization_proxy = get_dbus_proxy(LOCALIZATION_SERVICE, LOCALIZATION_OBJECT_PATH, LOCALIZATION_INTERFACE)
        
        if self.localization_proxy:
            print("LanguagePage: Successfully got D-Bus proxy.")
            GLib.idle_add(self._fetch_locale_data)
        else:
            self.show_toast("Failed to connect to Localization D-Bus service.")
            self._update_ui_with_locales(self.available_locales, None) # Use fallback
            self.initial_fetch_done = True

    def _fetch_locale_data(self):
        """Fetches available locales and current locale from D-Bus proxy."""
        if not self.localization_proxy:
             return False 

        available_locales_dict = {} # {code: display_name}
        current_locale_code = None
        try:
            # Fetch available locales
            # Assuming GetAvailableLocales() returns a list or dict
            locales_data = self.localization_proxy.GetAvailableLocales()
            # Adapt based on actual return type (list of strings, list of tuples, dict)
            if isinstance(locales_data, dict):
                 available_locales_dict = locales_data
            elif isinstance(locales_data, (list, tuple)):
                 # Assume list of strings (codes) for now
                 # TODO: Ideally, Anaconda provides display names too.
                 # If only codes, generate basic display names.
                 for code in locales_data:
                     parts = code.split('.')[0].split('_')
                     lang = parts[0]
                     country = f"({parts[1]})" if len(parts) > 1 else ""
                     display_name = f"{lang.capitalize()} {country}".strip() or code
                     available_locales_dict[code] = display_name
            else:
                 print(f"Warning: Received unexpected format for available locales: {type(locales_data)}")
                 available_locales_dict = self.available_locales # Use fallback
                 
            print(f"LanguagePage: Fetched {len(available_locales_dict)} locales via D-Bus.")
            
            # Fetch the current locale
            # Assuming a property like Locale or GetLocale()
            current_locale_code = self.localization_proxy.GetLocale()
            print(f"LanguagePage: Fetched current locale via D-Bus: {current_locale_code}")

            if not available_locales_dict:
                 available_locales_dict = self.available_locales # Use fallback
                 print("Warning: D-Bus returned empty locale list, using fallback.")

        except DBusError as e:
            print(f"ERROR: D-Bus error fetching locale data: {e}")
            self.show_toast(f"Error fetching locale data: {e}")
            available_locales_dict = self.available_locales # Use fallback
        except AttributeError as e:
             print(f"ERROR: D-Bus method/property not found: {e}. Check LocalizationInterface.")
             self.show_toast(f"D-Bus call failed: {e}")
             available_locales_dict = self.available_locales # Use fallback
        except Exception as e:
            print(f"ERROR: Unexpected error fetching locale data: {e}")
            self.show_toast("Unexpected error fetching locale data.")
            available_locales_dict = self.available_locales # Use fallback
        finally:
             # Update UI with fetched data (or fallback)
             self._update_ui_with_locales(available_locales_dict, current_locale_code)
             self.initial_fetch_done = True
             
        return False # Stop GLib.idle_add
        
    def _update_ui_with_locales(self, locales_dict, current_code):
         """Updates the ComboRow model and selection."""
         # Sort by display name for UI friendliness
         self.available_locales = dict(sorted(locales_dict.items(), key=lambda item: item[1]))
         self.locale_codes = list(self.available_locales.keys())
         
         model = Gtk.StringList.new(self.locale_codes)
         self.locale_row.set_model(model)
         
         # TODO: Use an expression to show display names from self.available_locales[code]
         # if Gtk version supports it well. For now, dropdown shows codes.
         
         selected_idx = -1
         if current_code and current_code in self.locale_codes:
             try:
                 selected_idx = self.locale_codes.index(current_code)
             except ValueError:
                 pass
         
         if selected_idx >= 0:
             self.locale_row.set_selected(selected_idx)
         elif self.locale_codes:
             self.locale_row.set_selected(0)
             
         self.locale_row.set_sensitive(True)
         self.complete_button.set_sensitive(True)
         if not self.locale_codes:
              self.locale_row.set_subtitle("No locales available")
              self.complete_button.set_sensitive(False)

    def apply_settings_and_return(self, button):
        """Applies the selected system locale via D-Bus."""
        if not self.initial_fetch_done:
            self.show_toast("Still fetching initial configuration...")
            return
            
        selected_idx = self.locale_row.get_selected()
        if not self.locale_codes or selected_idx < 0 or selected_idx >= len(self.locale_codes):
             self.show_toast("Invalid locale selection.")
             return
             
        selected_locale = self.locale_codes[selected_idx]
            
        print(f"Applying System Locale '{selected_locale}' via D-Bus...")
        self.complete_button.set_sensitive(False) 
        
        if self.localization_proxy:
            try:
                # Call the SetLocale method on the D-Bus proxy
                self.localization_proxy.SetLocale(selected_locale)
                print("System locale successfully set via D-Bus.")
                self.show_toast(f"System locale '{selected_locale}' applied.")
                
                config_values = {"locale": selected_locale}
                super().mark_complete_and_return(button, config_values=config_values)
                
            except DBusError as e:
                print(f"ERROR: D-Bus error setting locale: {e}")
                self.show_toast(f"Error setting locale: {e}")
                self.complete_button.set_sensitive(True) 
            except AttributeError as e:
                 print(f"ERROR: D-Bus method SetLocale not found: {e}. Check LocalizationInterface.")
                 self.show_toast(f"Failed to apply locale (D-Bus error): {e}")
                 self.complete_button.set_sensitive(True)
            except Exception as e:
                print(f"ERROR: Unexpected error applying system locale: {e}")
                self.show_toast(f"Unexpected error setting system locale: {e}")
                self.complete_button.set_sensitive(True) 
        else:
            self.show_toast("Cannot apply locale: D-Bus connection not available.")
            # Mark complete with selected value anyway?
            print("Marking complete with chosen locale despite D-Bus failure.")
            config_values = {"locale": selected_locale}
            super().mark_complete_and_return(button, config_values=config_values) 