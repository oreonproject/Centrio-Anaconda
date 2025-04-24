# centrio_installer/pages/timedate.py

import gi
# Remove subprocess and re imports
# import subprocess
# import re
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib # Added GLib

# Import D-Bus utils and constants
from .base import BaseConfigurationPage, dbus_available, DBusError, get_dbus_proxy, ServiceInfo # Import ServiceInfo
from ..constants import TIMEZONE_SERVICE, TIMEZONE_OBJECT_PATH, TIMEZONE_INTERFACE
# Import timezone list helper from utils (keep using this)
# from ..utils import ana_get_all_regions_and_timezones
import threading

class TimeDatePage(BaseConfigurationPage):
    def __init__(self, main_window, overlay_widget, **kwargs):
        super().__init__(
            title="Time & Date", 
            subtitle="Set the system timezone and NTP configuration",
            main_window=main_window, 
            overlay_widget=overlay_widget,
            **kwargs
        )
        self.page_name = "timedate"
        self.service_info = ServiceInfo(name=TIMEZONE_SERVICE, 
                                       object_path=TIMEZONE_OBJECT_PATH, 
                                       interface_name=TIMEZONE_INTERFACE)
        self.timezone_proxy = None
        self.available_timezones = []
        self.current_timezone = None
        self.current_is_utc = True
        self.current_ntp_servers = []

        # --- UI Elements ---
        # No main_box needed for Adw.PreferencesPage
        self.time_group = Adw.PreferencesGroup(title="Timezone Settings")
        # self.main_box.append(self.time_group) # Removed
        self.add(self.time_group) # Add directly to page
        
        # Timezone Selection Combo Row
        self.timezone_model = Gtk.StringList.new([])
        self.timezone_row = Adw.ComboRow(
            title="Timezone",
            model=self.timezone_model,
            subtitle="System timezone",
            use_markup=False
        )
        self.time_group.add(self.timezone_row)

        # UTC Switch
        self.utc_switch_row = Adw.SwitchRow(title="System Clock Uses UTC")
        self.time_group.add(self.utc_switch_row)

        # NTP Settings
        self.ntp_group = Adw.PreferencesGroup(title="Network Time Protocol (NTP)")
        # self.main_box.append(self.ntp_group) # Removed
        self.add(self.ntp_group) # Add directly to page

        # NTP Enable Switch
        self.ntp_enable_switch_row = Adw.SwitchRow(title="Use Network Time")
        self.ntp_group.add(self.ntp_enable_switch_row)
        
        # NTP Servers Entry
        self.ntp_servers_row = Adw.EntryRow(title="NTP Servers", text="")
        self.ntp_servers_row.set_tooltip_text("Comma-separated list of NTP server hostnames or IPs")
        self.ntp_group.add(self.ntp_servers_row)

        # Initially disable NTP server entry
        self.ntp_servers_row.set_sensitive(False)
        self.ntp_enable_switch_row.connect("notify::active", self._on_ntp_switch_toggled)
        
        # Button Group (following pattern from other pages)
        button_group = Adw.PreferencesGroup()
        self.add(button_group)
        # Reuse complete_button defined in BaseConfigurationPage
        self.complete_button = Gtk.Button(label="Apply Time && Date Settings") # TODO: Base class should handle button?
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        self.complete_button.connect("clicked", self.apply_settings_and_return)
        button_group.add(self.complete_button)

        # Start insensitive until fetch completes
        self.complete_button.set_sensitive(False)
        self.timezone_row.set_sensitive(False)
        self.utc_switch_row.set_sensitive(False)
        self.ntp_enable_switch_row.set_sensitive(False)

        # Connect to D-Bus and Fetch Initial Data
        self.connect("show", self.connect_and_fetch_data)
        self.initial_fetch_done = False

    def connect_and_fetch_data(self, widget=None):
        if self.initial_fetch_done or not dbus_available():
            # Attempt fetch only if D-Bus is available and not already done
            # Or if D-Bus is not available, update UI with defaults/fallbacks
            if not dbus_available():
                print("TimeDatePage: D-Bus not available, using defaults.")
                self._update_ui_with_data(self.available_timezones, self.current_timezone, self.current_is_utc, self.current_ntp_servers)
            return

        self.show_spinner(True)
        threading.Thread(target=self._fetch_timedate_data, daemon=True).start()

    def _fetch_timedate_data(self):
        if self.timezone_proxy is None:
            self.timezone_proxy = get_dbus_proxy(
                self.service_info.name,          # Use attribute access
                self.service_info.object_path,   # Use attribute access
                self.service_info.interface_name # Use attribute access
            )
            # Explicitly check if proxy creation failed
            if self.timezone_proxy is None:
                print(f"TimeDatePage: CRITICAL - Failed to get D-Bus proxy for {self.service_info.name} at {self.service_info.object_path}. Service might not be running or registered.") 
                GLib.idle_add(self._update_ui_with_data, [], None, True, []) # Update UI with empty/defaults
                GLib.idle_add(self.show_spinner, False)
                return
            else:
                print(f"TimeDatePage: Successfully got proxy for {self.service_info.name}")

        # Fetch data using corrected D-Bus calls
        fetched_timezones = []
        fetched_current_timezone = None
        fetched_is_utc = True # Default
        fetched_ntp_servers = []
        try:
            print("TimeDatePage: Fetching timezone data via D-Bus...")
            fetched_timezones = self.timezone_proxy.ListTimezones()
            fetched_current_timezone = self.timezone_proxy.get_Timezone()
            fetched_is_utc = self.timezone_proxy.get_IsUTC()
            fetched_ntp_servers = self.timezone_proxy.get_NTPServers()
            print(f"TimeDatePage: Fetched data - Zone: {fetched_current_timezone}, UTC: {fetched_is_utc}, NTP: {fetched_ntp_servers}")
            print(f"TimeDatePage: Fetched {len(fetched_timezones)} available timezones.")
        except DBusError as e:
            print(f"ERROR: D-Bus error fetching timezone data: {e}")
        except AttributeError as e:
            print(f"ERROR: D-Bus method/property not found: {e}. Check TimezoneInterface.")
        except Exception as e:
            print(f"ERROR: Unexpected error fetching timezone data: {e}")
        finally:
            # Schedule UI update on the main thread
            GLib.idle_add(self._update_ui_with_data, fetched_timezones, fetched_current_timezone, fetched_is_utc, fetched_ntp_servers)
            self.initial_fetch_done = True
            GLib.idle_add(self.show_spinner, False)

    def _update_ui_with_data(self, timezones, current_zone, is_utc, ntp_servers):
        self.available_timezones = sorted(timezones)
        self.current_timezone = current_zone
        self.current_is_utc = is_utc
        self.current_ntp_servers = ntp_servers
        
        # Update Timezone Combo Row
        self.timezone_model.splice(0, self.timezone_model.get_n_items(), self.available_timezones)
        if current_zone and current_zone in self.available_timezones:
            try:
                idx = self.available_timezones.index(current_zone)
                self.timezone_row.set_selected(idx)
            except ValueError:
                print(f"Warn: Current timezone '{current_zone}' not found in available list.")
                self.timezone_row.set_selected(Gtk.INVALID_LIST_POSITION) # Reset if not found
        else:
            self.timezone_row.set_selected(Gtk.INVALID_LIST_POSITION) # Reset if no current zone
            if not current_zone and self.available_timezones:
                 print("Warn: No current timezone set, but timezones are available.")
            elif not self.available_timezones:
                 print("Warn: No timezones available to select.")

        # Update UTC Switch
        self.utc_switch_row.set_active(is_utc)

        # Update NTP Settings
        use_ntp = bool(ntp_servers) # Enable switch if servers are configured
        self.ntp_enable_switch_row.set_active(use_ntp)
        self.ntp_servers_row.set_text(",".join(ntp_servers))
        self.ntp_servers_row.set_sensitive(use_ntp)

        # Enable widgets
        self.complete_button.set_sensitive(bool(self.available_timezones))
        self.timezone_row.set_sensitive(bool(self.available_timezones))
        self.utc_switch_row.set_sensitive(True)
        self.ntp_enable_switch_row.set_sensitive(True)
        
        print("TimeDatePage: UI updated.")

    def _on_ntp_switch_toggled(self, switch, param):
        is_active = switch.get_active()
        self.ntp_servers_row.set_sensitive(is_active)
        if not is_active:
            # Clear servers if NTP is disabled
            self.ntp_servers_row.set_text("")
        else:
             # Maybe restore previous servers or set defaults if enabling?
             # For now, just enables the field.
             pass 

    def apply_settings_and_return(self, button):
        selected_idx = self.timezone_row.get_selected()
        if selected_idx == Gtk.INVALID_LIST_POSITION:
             print("TimeDatePage: No timezone selected.")
             # Show dialog?
             return

        selected_zone = self.available_timezones[selected_idx]
        is_utc = self.utc_switch_row.get_active()
        use_ntp = self.ntp_enable_switch_row.get_active()
        ntp_servers_text = self.ntp_servers_row.get_text().strip()
        ntp_servers = []
        if use_ntp and ntp_servers_text:
             ntp_servers = [s.strip() for s in ntp_servers_text.split(',') if s.strip()]
        elif use_ntp and not ntp_servers_text:
             print("TimeDatePage: NTP enabled but no servers specified. Disabling NTP.")
             use_ntp = False # Force disable if empty
             # TODO: Maybe show a warning dialog here?

        print(f"Applying Timezone: {selected_zone}, UTC: {is_utc}, NTP Servers: {ntp_servers} via D-Bus...")
        self.show_spinner(True)
        self.set_sensitive(False) # Disable whole page during apply

        if self.timezone_proxy:
            try:
                # Apply settings using corrected D-Bus methods
                self.timezone_proxy.SetTimezone(selected_zone, is_utc)
                self.timezone_proxy.SetNTPServers(ntp_servers)
                print("Timezone and NTP settings successfully applied via D-Bus.")
                # Navigate back after successful application
                GLib.idle_add(self.navigate_back)
            except DBusError as e:
                print(f"ERROR: D-Bus error applying timezone settings: {e}")
                # Re-enable UI on error
                GLib.idle_add(self.set_sensitive, True)
                GLib.idle_add(self.show_spinner, False)
                # TODO: Show error dialog
            except AttributeError as e:
                 print(f"ERROR: D-Bus method not found: {e}. Check TimezoneInterface.")
                 GLib.idle_add(self.set_sensitive, True)
                 GLib.idle_add(self.show_spinner, False)
                 # TODO: Show error dialog
            except Exception as e:
                print(f"ERROR: Unexpected error applying timezone settings: {e}")
                GLib.idle_add(self.set_sensitive, True)
                GLib.idle_add(self.show_spinner, False)
                # TODO: Show error dialog
        else:
            print("ERROR: Timezone D-Bus proxy not available.")
            # Re-enable UI on error
            GLib.idle_add(self.set_sensitive, True)
            GLib.idle_add(self.show_spinner, False)
            # TODO: Show error dialog

    def set_sensitive(self, sensitive):
        """Enable/disable interactive widgets on the page."""
        self.timezone_row.set_sensitive(sensitive and bool(self.available_timezones))
        self.utc_switch_row.set_sensitive(sensitive)
        self.ntp_enable_switch_row.set_sensitive(sensitive)
        # NTP servers row sensitivity depends on the switch AND the page sensitivity
        ntp_enabled = self.ntp_enable_switch_row.get_active()
        self.ntp_servers_row.set_sensitive(sensitive and ntp_enabled)
        self.complete_button.set_sensitive(sensitive and bool(self.available_timezones))
        # Do not call super().set_sensitive() as it controls the back button etc. 