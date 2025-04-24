# centrio_installer/pages/network.py

import socket # Keep for fallback/default
# Remove subprocess import
# import subprocess

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib # Added GLib

from .base import BaseConfigurationPage, dbus_available, DBusError, get_dbus_proxy
# Import D-Bus constants
from ..constants import NETWORK_SERVICE, NETWORK_OBJECT_PATH, NETWORK_INTERFACE

class NetworkPage(BaseConfigurationPage):
    def __init__(self, main_window, overlay_widget, **kwargs):
        super().__init__(title="Network & Hostname", subtitle="Configure hostname for the installed system", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.network_proxy = None
        self.default_hostname = "localhost" # Default if D-Bus fails
        # Try to get a more sensible default from the system if D-Bus fails
        try:
             self.default_hostname = socket.gethostname().split('.')[0] 
        except Exception:
             pass # Keep "localhost"
             
        self.initial_hostname_fetch_done = False

        # --- UI Setup --- 
        net_group = Adw.PreferencesGroup()
        self.add(net_group)
        self.hostname_row = Adw.EntryRow(title="Target Hostname")
        self.hostname_row.set_text(self.default_hostname) # Start with default
        net_group.add(self.hostname_row)
        
        info_row = Adw.ActionRow(title="Network Configuration", 
                                   subtitle="Requires NetworkManager integration (Not Implemented)")
        info_row.set_activatable(False)
        net_group.add(info_row)

        button_group = Adw.PreferencesGroup()
        self.add(button_group)
        self.complete_button = Gtk.Button(label="Apply Hostname") # Changed label 
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        # Connect to the new D-Bus based apply method
        self.complete_button.connect("clicked", self.apply_settings_and_return) 
        # Start insensitive until data is fetched
        self.complete_button.set_sensitive(False)
        self.hostname_row.set_sensitive(False)
        button_group.add(self.complete_button)

        # --- Connect to D-Bus and Fetch Initial Data --- 
        self.connect_and_fetch_data()

    def connect_and_fetch_data(self):
        """Connects to Network D-Bus service and fetches the current hostname."""
        print("NetworkPage: Connecting to D-Bus...")
        if not dbus_available:
            self.show_toast("D-Bus is not available. Cannot fetch network settings.")
            # Enable with default hostname
            self.hostname_row.set_text(self.default_hostname)
            self.hostname_row.set_sensitive(True)
            self.complete_button.set_sensitive(True) # Allow saving default
            self.initial_hostname_fetch_done = True
            return
            
        self.network_proxy = get_dbus_proxy(NETWORK_SERVICE, NETWORK_OBJECT_PATH, NETWORK_INTERFACE)
        
        if self.network_proxy:
            print("NetworkPage: Successfully got D-Bus proxy.")
            # Fetch initial hostname asynchronously using GLib.idle_add
            GLib.idle_add(self._fetch_initial_hostname)
        else:
            self.show_toast("Failed to connect to Network D-Bus service.")
            # Enable with default hostname
            self.hostname_row.set_text(self.default_hostname)
            self.hostname_row.set_sensitive(True)
            self.complete_button.set_sensitive(True) # Allow saving default
            self.initial_hostname_fetch_done = True

    def _fetch_initial_hostname(self):
        """Fetches the hostname from the D-Bus proxy (called via idle_add)."""
        # Check proxy validity first
        if not self.network_proxy:
             self.show_toast("Network D-Bus service is not available.")
             self._update_ui_with_hostname(self.default_hostname, success=False)
             self.initial_hostname_fetch_done = True # Mark done even on failure
             return False # Stop GLib.idle_add
             
        current_hostname = None
        success = False
        try:
            # Call the Hostname property getter
            current_hostname = self.network_proxy.get_Hostname() 
            print(f"NetworkPage: Fetched hostname via D-Bus: {current_hostname}")
            success = True
        except (DBusError, AttributeError) as e: 
            print(f"ERROR: D-Bus error fetching hostname: {e}")
            self.show_toast(f"Error fetching hostname: {e}")
            current_hostname = self.default_hostname # Use default on error
        except Exception as e:
            print(f"ERROR: Unexpected error fetching hostname: {e}")
            self.show_toast(f"Unexpected error fetching hostname.")
            current_hostname = self.default_hostname
        finally:
             # Update UI regardless of success/failure after fetch attempt
             self._update_ui_with_hostname(current_hostname, success)
             self.initial_hostname_fetch_done = True
             
        return False # Prevents GLib.idle_add from repeating the call

    def _update_ui_with_hostname(self, hostname, success=True):
        """Updates the hostname entry and enables/disables UI."""
        if hostname:
             self.hostname_row.set_text(hostname)
        else:
             self.hostname_row.set_text(self.default_hostname) # Fallback if empty
             
        # Enable widgets 
        can_proceed = success # Only allow apply if fetch worked
        self.hostname_row.set_sensitive(True) # Always allow editing, even if fetch failed
        self.complete_button.set_sensitive(can_proceed)
        if not success:
            # Adw.EntryRow does not have subtitle, show toast instead?
            self.show_toast("Failed to load current hostname from backend.")
        else:
            self.hostname_row.set_subtitle("") # Clear subtitle

    def apply_settings_and_return(self, button):
        """Validates and applies hostname setting via D-Bus."""
        # Check proxy validity first
        if not self.network_proxy:
            self.show_toast("Cannot apply hostname: Network D-Bus service is not available.")
            self.complete_button.set_sensitive(False)
            return
            
        if not self.initial_hostname_fetch_done:
            self.show_toast("Still fetching initial configuration...")
            return

        new_hostname = self.hostname_row.get_text().strip()
        if not new_hostname: # Basic validation
            self.show_toast("Hostname cannot be empty.")
            return
            
        print(f"Applying Hostname '{new_hostname}' via D-Bus...")
        self.complete_button.set_sensitive(False)

        try:
            # Call the SetHostname method (or property setter)
            self.network_proxy.SetHostname(new_hostname) 
            print("Hostname successfully set via D-Bus.")
            self.show_toast(f"Hostname '{new_hostname}' applied.")
            
            config_values = {"hostname": new_hostname}
            super().mark_complete_and_return(button, config_values=config_values)
            
        except (DBusError, AttributeError) as e: 
            print(f"ERROR: D-Bus error setting hostname: {e}")
            self.show_toast(f"Error setting hostname: {e}")
            self.complete_button.set_sensitive(True) # Re-enable on error
        except Exception as e:
            print(f"ERROR: Unexpected error setting hostname: {e}")
            self.show_toast(f"Unexpected error setting hostname: {e}")
            self.complete_button.set_sensitive(True) # Re-enable on error 