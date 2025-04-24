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
        """Fetches current bootloader installation setting."""
        if not self.bootloader_proxy:
             return False

        enabled_status = True # Default
        try:
            # Fetch status - Assuming property InstallBootloader or method GetInstallBootloader()
            enabled_status = self.bootloader_proxy.GetInstallBootloader() # Hypothetical
            print(f"BootloaderPage: Fetched install status via D-Bus: {enabled_status}")
            
        except DBusError as e:
            print(f"ERROR: D-Bus error fetching bootloader data: {e}")
            self.show_toast(f"Error fetching bootloader data: {e}")
            # Keep default
        except AttributeError as e:
             print(f"ERROR: D-Bus method/property not found: {e}. Check BootloaderInterface.")
             self.show_toast(f"D-Bus call failed: {e}")
             # Keep default
        except Exception as e:
            print(f"ERROR: Unexpected error fetching bootloader data: {e}")
            self.show_toast("Unexpected error fetching bootloader data.")
            # Keep default
        finally:
             self._update_ui_with_settings(enabled_status)
             self.initial_fetch_done = True
             
        return False
        
    def _update_ui_with_settings(self, is_enabled):
         """Updates the switch and enables UI."""
         self.bootloader_enabled = bool(is_enabled)
         self.enable_switch_row.set_active(self.bootloader_enabled)
         self.enable_switch_row.set_sensitive(True)
         self.complete_button.set_sensitive(True)
         self.on_enable_toggled(self.enable_switch_row, None) # Update subtitle

    def on_enable_toggled(self, switch, param):
        self.bootloader_enabled = switch.get_active()
        print(f"Bootloader install choice toggled: {'Install' if self.bootloader_enabled else 'Skip'}")
        if self.bootloader_enabled:
            self.enable_switch_row.set_subtitle("A bootloader (GRUB2) will be installed")
        else:
            self.enable_switch_row.set_subtitle("Bootloader installation will be skipped (System may not be bootable!)")

    def apply_settings_and_return(self, button):
        """Applies the bootloader setting via D-Bus."""
        if not self.initial_fetch_done:
             self.show_toast("Still fetching initial configuration...")
             return
             
        mode_str = "Install" if self.bootloader_enabled else "Skip"
        print(f"Applying Bootloader choice ({mode_str}) via D-Bus...")
        self.complete_button.set_sensitive(False)

        if self.bootloader_proxy:
            try:
                # Call D-Bus method - Assuming SetInstallBootloader(boolean)
                self.bootloader_proxy.SetInstallBootloader(self.bootloader_enabled) # Hypothetical
                print(f"Bootloader choice '{mode_str}' applied via D-Bus.")
                self.show_toast(f"Bootloader choice confirmed: {mode_str}")
                
                config_values = {"install_bootloader": self.bootloader_enabled}
                super().mark_complete_and_return(button, config_values=config_values)

            except DBusError as e:
                print(f"ERROR: D-Bus error applying bootloader setting: {e}")
                self.show_toast(f"Error applying bootloader setting: {e}")
                self.complete_button.set_sensitive(True)
            except AttributeError as e:
                 print(f"ERROR: D-Bus method SetInstallBootloader not found: {e}. Check BootloaderInterface.")
                 self.show_toast(f"Failed to apply bootloader setting (D-Bus error): {e}")
                 self.complete_button.set_sensitive(True)
            except Exception as e:
                print(f"ERROR: Unexpected error applying bootloader setting: {e}")
                self.show_toast(f"Unexpected error applying bootloader setting: {e}")
                self.complete_button.set_sensitive(True)
        else:
            self.show_toast("Cannot apply bootloader setting: D-Bus connection not available.")
            # Mark complete anyway?
            print("Marking complete with chosen bootloader setting despite D-Bus failure.")
            config_values = {"install_bootloader": self.bootloader_enabled}
            super().mark_complete_and_return(button, config_values=config_values)