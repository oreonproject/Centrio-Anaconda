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
from ..utils import ana_get_available_locales # Keep locale list getter

class LanguagePage(BaseConfigurationPage):
    def __init__(self, main_window, overlay_widget, **kwargs):
        # Changed title and subtitle to reflect setting system locale
        super().__init__(title="System Language", subtitle="Select the primary language for the installed system", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.localization_proxy = None
        # Use dict {code: display_name} for available locales
        self.available_locales = ana_get_available_locales()
        self.locale_codes = list(self.available_locales.keys()) # Codes for model
        self.initial_fetch_done = False

        # --- UI Setup --- 
        lang_group = Adw.PreferencesGroup(title="System Locale")
        self.add(lang_group)
        
        # Model uses the list populated above
        model = Gtk.StringList.new(self.locale_codes)
        self.locale_row = Adw.ComboRow(title="Locale", model=model)
        lang_group.add(self.locale_row)

        button_group = Adw.PreferencesGroup()
        self.add(button_group)
        self.complete_button = Gtk.Button(label="Apply System Locale")
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        self.complete_button.connect("clicked", self.apply_settings_and_return)
        # Start insensitive until fetch completes
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
        """Fetches available locales and current setting (async via idle_add)."""
        # Check proxy validity
        if not self.localization_proxy:
            self.show_toast("Localization D-Bus service is not available.")
            self._update_ui_with_locales(self.available_locales, None, success=False) # Use fallback
            self.initial_fetch_done = True
            return False

        fetched_locales = []
        current_locale = None
        success = False
        try:
            print("LanguagePage: Fetching locale data via D-Bus...")
            # Assuming ListLocales() -> list[str]
            fetched_locales = self.localization_proxy.ListLocales()
            # Assuming Language property -> str
            current_locale = self.localization_proxy.get_Language()
            print(f"LanguagePage: Fetched locales: {len(fetched_locales)}, current: {current_locale}")
            success = True
        except (DBusError, AttributeError) as e: 
            print(f"ERROR: D-Bus error fetching locale data: {e}")
            self.show_toast(f"Error fetching locale data: {e}")
            fetched_locales = self.available_locales # Use fallback
            current_locale = None # Cannot determine current
        except Exception as e:
            print(f"ERROR: Unexpected error fetching locale data: {e}")
            self.show_toast("Unexpected error fetching locale data.")
            fetched_locales = self.available_locales
            current_locale = None
        finally:
            self._update_ui_with_locales(fetched_locales, current_locale, success)
            self.initial_fetch_done = True
        
        return False

    def _update_ui_with_locales(self, locales, current_locale, success=True):
        """Populates the locale list and selects the current one."""
        # Store sorted list of available locales
        self.available_locales = sorted(locales)
        
        # Use simple StringList with locale codes for the model
        model = Gtk.StringList.new(self.available_locales)

        self.locale_row.set_model(model)
        
        # Select current locale if found
        selected_idx = -1
        if current_locale and current_locale in self.available_locales:
            try:
                selected_idx = self.available_locales.index(current_locale)
            except ValueError:
                pass

        if selected_idx >= 0:
             self.locale_row.set_selected(selected_idx)
        elif self.available_locales: # Default to first if current not found
             self.locale_row.set_selected(0)

        # Enable/disable UI based on success
        can_proceed = success and len(model) > 0
        self.locale_row.set_sensitive(can_proceed)
        self.complete_button.set_sensitive(can_proceed)
        if not can_proceed:
            subtitle = "Failed to load locales" if not success else "No locales available"
            self.locale_row.set_subtitle(subtitle)
        else:
            self.locale_row.set_subtitle(None) # Clear subtitle

    def apply_settings_and_return(self, button):
        """Applies the selected locale via D-Bus."""
        # Check proxy validity first
        if not self.localization_proxy:
            self.show_toast("Cannot apply language: Localization D-Bus service is not available.")
            self.complete_button.set_sensitive(False)
            return
            
        if not self.initial_fetch_done:
            self.show_toast("Still fetching initial configuration...")
            return

        selected_idx = self.locale_row.get_selected()
        if not self.available_locales or selected_idx < 0 or selected_idx >= len(self.available_locales):
            self.show_toast("Please select a language.")
            return

        selected_locale = self.available_locales[selected_idx] # Get locale code from list

        print(f"Applying Language '{selected_locale}' via D-Bus...")
        self.complete_button.set_sensitive(False)

        try:
            # Assuming SetLanguage(locale_code)
            self.localization_proxy.SetLanguage(selected_locale)
            print("Language successfully set via D-Bus.")
            self.show_toast(f"Language '{selected_locale}' applied.")
            
            config_values = {"language": selected_locale}
            super().mark_complete_and_return(button, config_values=config_values)
            
        except (DBusError, AttributeError) as e: 
            print(f"ERROR: D-Bus error setting language: {e}")
            self.show_toast(f"Error setting language: {e}")
            self.complete_button.set_sensitive(True) # Re-enable on error
        except Exception as e:
            print(f"ERROR: Unexpected error setting language: {e}")
            self.show_toast(f"Unexpected error setting language: {e}")
            self.complete_button.set_sensitive(True) # Re-enable on error 