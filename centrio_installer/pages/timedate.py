# centrio_installer/pages/timedate.py

import gi
# Remove subprocess and re imports
# import subprocess
# import re
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib # Added GLib

# Import D-Bus utils and constants
from .base import BaseConfigurationPage, dbus_available, DBusError, get_dbus_proxy
from ..constants import TIMEZONE_SERVICE, TIMEZONE_OBJECT_PATH, TIMEZONE_INTERFACE
# Import timezone list helper from utils (keep using this)
from ..utils import ana_get_all_regions_and_timezones

class TimeDatePage(BaseConfigurationPage):
    def __init__(self, main_window, overlay_widget, **kwargs):
        super().__init__(title="Time & Date", subtitle="Set timezone and time settings", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.timezone_proxy = None
        self.current_timezone = "UTC" # Default
        self.current_ntp = False    # Default
        self.timezone_list = []
        self.initial_fetch_done = False

        # --- Populate List (Still use utils helper for the list) --- 
        self.timezone_list = ana_get_all_regions_and_timezones()

        # --- UI Setup --- 
        time_group = Adw.PreferencesGroup()
        self.add(time_group)
        
        # Model uses the list populated above
        tz_model = Gtk.StringList.new(self.timezone_list)
        self.timezone_row = Adw.ComboRow(title="Timezone", model=tz_model)
        time_group.add(self.timezone_row)
        
        self.network_time_row = Adw.SwitchRow(
            title="Network Time",
            subtitle="Automatically synchronize time from the network"
        )
        time_group.add(self.network_time_row)
        
        button_group = Adw.PreferencesGroup()
        self.add(button_group) 
        self.complete_button = Gtk.Button(label="Apply Time & Date Settings")
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        self.complete_button.connect("clicked", self.apply_settings_and_return)
        # Start insensitive
        self.complete_button.set_sensitive(False)
        self.timezone_row.set_sensitive(False)
        self.network_time_row.set_sensitive(False)
        button_group.add(self.complete_button)

        # --- Fetch Current Settings --- 
        self.connect_and_fetch_data()

    def connect_and_fetch_data(self):
        """Connects to Timezone D-Bus service and fetches settings."""
        print("TimeDatePage: Connecting to D-Bus...")
        if not dbus_available:
            self.show_toast("D-Bus is not available. Cannot fetch time settings.")
            self._update_ui_with_settings(self.current_timezone, self.current_ntp) # Use defaults
            self.initial_fetch_done = True
            return
            
        self.timezone_proxy = get_dbus_proxy(TIMEZONE_SERVICE, TIMEZONE_OBJECT_PATH, TIMEZONE_INTERFACE)
        
        if self.timezone_proxy:
            print("TimeDatePage: Successfully got D-Bus proxy.")
            GLib.idle_add(self._fetch_time_data)
        else:
            self.show_toast("Failed to connect to Timezone D-Bus service.")
            self._update_ui_with_settings(self.current_timezone, self.current_ntp) # Use defaults
            self.initial_fetch_done = True

    def _fetch_time_data(self):
        """Fetches current timezone and NTP status from D-Bus proxy."""
        if not self.timezone_proxy:
             return False 

        fetched_tz = None
        fetched_ntp = None
        try:
            # Fetch timezone - Assuming property Timezone or method GetTimezone()
            fetched_tz = self.timezone_proxy.GetTimezone()
            print(f"TimeDatePage: Fetched timezone via D-Bus: {fetched_tz}")
            
            # Fetch NTP status - Assuming property NTP or method GetNTP()
            fetched_ntp = self.timezone_proxy.GetNTP()
            print(f"TimeDatePage: Fetched NTP status via D-Bus: {fetched_ntp}")
            
        except DBusError as e:
            print(f"ERROR: D-Bus error fetching time data: {e}")
            self.show_toast(f"Error fetching time data: {e}")
            # Keep defaults if fetch fails
            fetched_tz = self.current_timezone
            fetched_ntp = self.current_ntp
        except AttributeError as e:
             print(f"ERROR: D-Bus method/property not found: {e}. Check TimezoneInterface.")
             self.show_toast(f"D-Bus call failed: {e}")
             fetched_tz = self.current_timezone
             fetched_ntp = self.current_ntp
        except Exception as e:
            print(f"ERROR: Unexpected error fetching time data: {e}")
            self.show_toast("Unexpected error fetching time data.")
            fetched_tz = self.current_timezone
            fetched_ntp = self.current_ntp
        finally:
             # Update UI with fetched data (or defaults on error)
             self._update_ui_with_settings(fetched_tz, fetched_ntp)
             self.initial_fetch_done = True
             
        return False # Stop GLib.idle_add

    def _update_ui_with_settings(self, timezone, ntp_status):
        """Updates the UI elements with the fetched or default settings."""
        self.current_timezone = timezone if timezone else "UTC"
        self.current_ntp = bool(ntp_status)
        
        # Update Timezone Combo
        if self.current_timezone in self.timezone_list:
            try:
                idx = self.timezone_list.index(self.current_timezone)
                self.timezone_row.set_selected(idx)
            except ValueError:
                print(f"Warning: Current timezone '{self.current_timezone}' not in list.")
                if self.timezone_list: self.timezone_row.set_selected(0)
        elif self.timezone_list:
            self.timezone_row.set_selected(0)
            
        # Update NTP Switch
        self.network_time_row.set_active(self.current_ntp)
        
        # Enable UI
        self.timezone_row.set_sensitive(bool(self.timezone_list))
        self.network_time_row.set_sensitive(True) # Allow toggling NTP
        self.complete_button.set_sensitive(bool(self.timezone_list))
        if not self.timezone_list:
            self.timezone_row.set_subtitle("Failed to load timezones")

    def apply_settings_and_return(self, button):
        """Applies timezone and NTP settings via D-Bus."""
        if not self.initial_fetch_done:
            self.show_toast("Still fetching initial configuration...")
            return
            
        selected_idx = self.timezone_row.get_selected()
        if not self.timezone_list or selected_idx < 0 or selected_idx >= len(self.timezone_list):
             self.show_toast("Invalid timezone selection.")
             return
             
        selected_tz = self.timezone_list[selected_idx]
        network_time_enabled = self.network_time_row.get_active()

        print(f"Applying Timezone='{selected_tz}', NTP={network_time_enabled} via D-Bus...")
        self.complete_button.set_sensitive(False) 
        
        if self.timezone_proxy:
            errors = []
            try:
                # Apply Timezone - Assuming method SetTimezone(tz_string)
                self.timezone_proxy.SetTimezone(selected_tz)
                print("Timezone successfully set via D-Bus.")
            except DBusError as e:
                err_msg = f"Error setting timezone: {e}"
                print(f"ERROR: {err_msg}")
                errors.append(err_msg)
            except AttributeError as e:
                 err_msg = f"Error setting timezone (Method not found): {e}"
                 print(f"ERROR: {err_msg}")
                 errors.append(err_msg)
            except Exception as e:
                err_msg = f"Unexpected error setting timezone: {e}"
                print(f"ERROR: {err_msg}")
                errors.append(err_msg)

            try:
                # Apply NTP - Assuming method SetNTP(boolean)
                self.timezone_proxy.SetNTP(network_time_enabled)
                print("NTP status successfully set via D-Bus.")
            except DBusError as e:
                err_msg = f"Error setting NTP: {e}"
                print(f"ERROR: {err_msg}")
                errors.append(err_msg)
            except AttributeError as e:
                 err_msg = f"Error setting NTP (Method not found): {e}"
                 print(f"ERROR: {err_msg}")
                 errors.append(err_msg)
            except Exception as e:
                err_msg = f"Unexpected error setting NTP: {e}"
                print(f"ERROR: {err_msg}")
                errors.append(err_msg)

            # Handle outcome
            if not errors:
                self.show_toast("Time settings applied successfully!")
                config_values = {"timezone": selected_tz, "ntp": network_time_enabled}
                super().mark_complete_and_return(button, config_values=config_values)
            else:
                full_error_message = "Error applying time settings: " + "; ".join(errors)
                print(f"ERROR: {full_error_message}")
                self.show_toast(full_error_message)
                self.complete_button.set_sensitive(True) # Re-enable on error
        else:
            self.show_toast("Cannot apply settings: D-Bus connection not available.")
            # Mark complete with selected values anyway?
            print("Marking complete with chosen time settings despite D-Bus failure.")
            config_values = {"timezone": selected_tz, "ntp": network_time_enabled}
            super().mark_complete_and_return(button, config_values=config_values) 