# centrio_installer/pages/bootloader.py

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

from .base import BaseConfigurationPage, dbus_available, DBusError, get_dbus_proxy
from ..constants import BOOTLOADER_SERVICE, BOOTLOADER_OBJECT_PATH, BOOTLOADER_INTERFACE

class BootloaderPage(BaseConfigurationPage):
    """Page for Bootloader Configuration."""
    def __init__(self, main_window, overlay_widget, **kwargs):
        super().__init__(title="Bootloader Configuration", subtitle="Configure bootloader installation", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.bootloader_proxy = None
        self.bootloader_enabled = True
        self.initial_fetch_done = False

        # --- UI Elements --- 
        mode_group = Adw.PreferencesGroup()
        self.add(mode_group)
        self.enable_switch_row = Adw.SwitchRow(
            title="Install Bootloader",
            subtitle="A bootloader (GRUB2) will be installed"
        )
        self.enable_switch_row.connect("notify::active", self.on_enable_toggled)
        mode_group.add(self.enable_switch_row)

        # Placeholder for location/advanced options
        info_group = Adw.PreferencesGroup(title="Configuration")
        info_group.set_description("Default location and settings will be used.")
        self.add(info_group)
        info_label = Gtk.Label(label="(Advanced configuration not implemented)")
        info_group.add(info_label)

        # --- Confirmation Button --- 
        button_group = Adw.PreferencesGroup()
        self.add(button_group)
        self.complete_button = Gtk.Button(label="Apply Bootloader Settings")
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        self.complete_button.connect("clicked", self.apply_settings_and_return)
        # Start insensitive
        self.complete_button.set_sensitive(False)
        self.enable_switch_row.set_sensitive(False)
        button_group.add(self.complete_button)

        # Connect to D-Bus
        self.connect_and_fetch_data()

    def connect_and_fetch_data(self):
        """Connects to Bootloader D-Bus interface and fetches current state."""
        print("BootloaderPage: Connecting to D-Bus...")
        if not dbus_available:
            self.show_toast("D-Bus is not available. Cannot configure bootloader.")
            self._update_ui_with_settings(self.bootloader_enabled) # Use default
            self.initial_fetch_done = True
            return
            
        # Use constants defined for Bootloader (might be same service/path as Storage)
        self.bootloader_proxy = get_dbus_proxy(BOOTLOADER_SERVICE, BOOTLOADER_OBJECT_PATH, BOOTLOADER_INTERFACE)
        
        if self.bootloader_proxy:
            print("BootloaderPage: Successfully got D-Bus proxy.")
            GLib.idle_add(self._fetch_bootloader_data)
        else:
            self.show_toast("Failed to connect to Bootloader D-Bus service.")
            self._update_ui_with_settings(self.bootloader_enabled) # Use default
            self.initial_fetch_done = True

    def _fetch_bootloader_data(self):
        """Fetches bootloader config (async via idle_add)."""
        # Check proxy validity
        if not self.bootloader_proxy:
            self.show_toast("Bootloader D-Bus service is not available.")
            self._update_ui_with_settings(self.bootloader_enabled, success=False)
            self.initial_fetch_done = True
            return False
            
        fetched_enabled = False
        fetched_location = None
        success = False
        try:
            print("BootloaderPage: Fetching bootloader data via D-Bus...")
            # Assuming properties: InstallBootloader (bool), BootloaderLocation (str)
            fetched_enabled = self.bootloader_proxy.get_InstallBootloader()
            fetched_location = self.bootloader_proxy.get_BootloaderLocation() 
            print(f"BootloaderPage: Fetched - Enabled: {fetched_enabled}, Location: {fetched_location}")
            success = True
        except (DBusError, AttributeError) as e:
            print(f"ERROR: D-Bus error fetching bootloader data: {e}")
            self.show_toast(f"Error fetching bootloader data: {e}")
            # Use defaults on error
            fetched_enabled = self.bootloader_enabled 
            fetched_location = "(unknown)"
        except Exception as e:
            print(f"ERROR: Unexpected error fetching bootloader data: {e}")
            self.show_toast("Unexpected error fetching bootloader data.")
            fetched_enabled = self.bootloader_enabled
            fetched_location = "(unknown)"
        finally:
            self._update_ui_with_settings(fetched_enabled, fetched_location, success)
            self.initial_fetch_done = True
            
        return False

    def _update_ui_with_settings(self, enabled, location=None, success=True):
        """Updates the UI based on fetched settings."""
        self.bootloader_enabled = enabled
        self.enable_switch_row.set_active(self.bootloader_enabled)
        
        # Removed references to non-existent location_label
        # if location:
        #      self.location_label.set_text(f"Detected Location: {location}")
        # else:
        #      self.location_label.set_text("Location: (Not detected)")
             
        # Enable/disable UI based on success
        can_proceed = success # Can always proceed, but might use defaults
        self.enable_switch_row.set_sensitive(success) # Only allow toggle if fetch worked
        self.complete_button.set_sensitive(True) # Always allow apply (might apply defaults)
        
        if not success:
            self.enable_switch_row.set_subtitle("Failed to load current setting")
        else:
            self.enable_switch_row.set_subtitle("Install a bootloader on the selected disk")

    def on_enable_toggled(self, switch_row, state):
        """Handle the enable switch being toggled."""
        self.bootloader_enabled = state
        print(f"Bootloader install choice toggled: {'Install' if state else 'Do Not Install'}")
        # Maybe trigger apply immediately or just update state?
        # For now, just update state. Button click will apply.

    def apply_settings_and_return(self, button):
        """Applies the bootloader settings via D-Bus."""
        # Check proxy validity first
        if not self.bootloader_proxy:
            self.show_toast("Cannot apply bootloader settings: D-Bus service is not available.")
            self.complete_button.set_sensitive(False)
            return
            
        if not self.initial_fetch_done:
             # This shouldn't happen if button is sensitive, but check anyway
             self.show_toast("Still fetching initial configuration...")
             return

        enabled_state = self.enable_switch_row.get_active()
        print(f"Applying Bootloader Setting (Install={enabled_state}) via D-Bus...")
        self.complete_button.set_sensitive(False)

        try:
            # Call the appropriate method/property setter
            # Assuming SetInstallBootloader(bool)
            self.bootloader_proxy.SetInstallBootloader(enabled_state)
            print("Bootloader setting successfully applied via D-Bus.")
            self.show_toast(f"Bootloader setting (Install={enabled_state}) applied.")
            
            config_values = {"install_bootloader": enabled_state}
            super().mark_complete_and_return(button, config_values=config_values)
            
        except (DBusError, AttributeError) as e:
            print(f"ERROR: D-Bus error setting bootloader option: {e}")
            self.show_toast(f"Error setting bootloader option: {e}")
            self.complete_button.set_sensitive(True) # Re-enable on error
        except Exception as e:
            print(f"ERROR: Unexpected error applying bootloader setting: {e}")
            self.show_toast(f"Unexpected error applying bootloader setting: {e}")
            self.complete_button.set_sensitive(True) # Re-enable on error