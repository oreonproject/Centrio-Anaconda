import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gio', '2.0')
from gi.repository import Gtk, Adw, GLib, Gio
import json
import os
import subprocess

# Anaconda DBus service constants
BOSS_BUS_NAME = 'org.fedoraproject.Anaconda.Boss'
BOSS_OBJECT_PATH = '/org/fedoraproject/Anaconda/Boss'
BOSS_INTERFACE = 'org.fedoraproject.Anaconda.Boss'

STORAGE_BUS_NAME = 'org.fedoraproject.Anaconda.Modules.Storage'
STORAGE_OBJECT_PATH = '/org/fedoraproject/Anaconda/Modules/Storage'
STORAGE_INTERFACE = 'org.fedoraproject.Anaconda.Modules.Storage'

PAYLOAD_BUS_NAME = 'org.fedoraproject.Anaconda.Modules.Payloads'
PAYLOAD_OBJECT_PATH = '/org/fedoraproject/Anaconda/Modules/Payloads'
PAYLOAD_INTERFACE = 'org.fedoraproject.Anaconda.Modules.Payloads'

class AnacondaDBusClient:
    """Helper class to interact with Anaconda's DBus services."""
    
    def __init__(self):
        self._boss_proxy = None
        self._storage_proxy = None
        self._payload_proxy = None
        self._connect_services()
    
    def _connect_services(self):
        """Connect to all required Anaconda DBus services."""
        try:
            self._boss_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                BOSS_BUS_NAME,
                BOSS_OBJECT_PATH,
                BOSS_INTERFACE,
                None
            )
            
            self._storage_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                STORAGE_BUS_NAME,
                STORAGE_OBJECT_PATH,
                STORAGE_INTERFACE,
                None
            )
            
            self._payload_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                PAYLOAD_BUS_NAME,
                PAYLOAD_OBJECT_PATH,
                PAYLOAD_INTERFACE,
                None
            )
            
            print("Connected to Anaconda DBus services")
            return True
            
        except GLib.Error as e:
            print(f"Failed to connect to Anaconda DBus services: {e}")
            return False
    
    def start_installation(self):
        """Start the installation process."""
        if not self._boss_proxy:
            return False, "Not connected to Anaconda Boss service"
            
        try:
            # Start the installation process
            self._boss_proxy.call_sync(
                'StartWithConfiguration',
                GLib.Variant('(s)', (json.dumps({}),)),  # Empty config for now
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            return True, "Installation started successfully"
            
        except GLib.Error as e:
            return False, f"Failed to start installation: {e.message}"
    
    def get_installation_progress(self):
        """Get the current installation progress."""
        if not self._payload_proxy:
            return 0.0, "Error: Not connected to Payload service"
            
        try:
            # Get progress from payload service
            result = self._payload_proxy.call_sync(
                'GetProgress',
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            
            # Parse the result (assuming it returns a tuple with progress and message)
            if result:
                progress, message = result.unpack()
                return float(progress), str(message)
            
            return 0.0, "Starting installation..."
            
        except GLib.Error as e:
            return 0.0, f"Error getting progress: {e.message}"
    
    def get_storage_status(self):
        """Get the current storage configuration status."""
        if not self._storage_proxy:
            return "Error: Not connected to Storage service"
            
        try:
            result = self._storage_proxy.call_sync(
                'GetStorageStatus',
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            
            if result:
                return result.unpack()[0]
            return "Storage status unknown"
            
        except GLib.Error as e:
            return f"Error getting storage status: {e.message}"

@Gtk.Template(filename='ui/installation_progress.ui')
class InstallationProgressView(Gtk.Box):
    __gtype_name__ = 'InstallationProgressView'

    # Template Children
    progress_bar = Gtk.Template.Child()
    progress_label = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    cancel_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._timeout_id = None
        self._completion_callback = None
        self._anaconda = AnacondaDBusClient()
        self._is_installing = False
        self._last_progress = 0.0
        print("InstallationProgressView initialized")
        
        # Connect cancel button
        self.cancel_button.connect("clicked", self._on_cancel_clicked)
    
    def _on_cancel_clicked(self, button):
        """Handle cancel button click."""
        if self._is_installing:
            self.cancel_installation()
        elif self._completion_callback:
            self._completion_callback()

    def start_installation(self, completion_callback):
        """
        Start the actual installation process.
        
        Args:
            completion_callback: Callback function to call when installation is complete
                              or fails. Will be called with (success, message) parameters.
        """
        print("Starting installation...")
        self._completion_callback = completion_callback
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("0%")
        self.status_label.set_text("Preparing installation environment...")
        self.progress_label.set_text("Initializing...")
        self.cancel_button.set_label("Cancel")
        self._is_installing = True
        
        # Start the installation in a separate thread to avoid blocking the UI
        GLib.idle_add(self._start_installation_thread)
    
    def _start_installation_thread(self):
        """Start the installation in a separate thread."""
        try:
            # First, verify we can connect to Anaconda
            if not self._anaconda._connect_services():
                error_msg = "Failed to connect to Anaconda installation service"
                self._show_error("Connection Error", error_msg)
                self._installation_failed(error_msg)
                return False
            
            # Start the installation
            success, message = self._anaconda.start_installation()
            
            if not success:
                self._show_error("Installation Error", message)
                self._installation_failed(message)
                return False
            
            # Start monitoring progress
            self._timeout_id = GLib.timeout_add(500, self._update_progress)  # Update every 500ms
            return False  # Don't repeat
            
        except Exception as e:
            error_msg = f"Failed to start installation: {str(e)}"
            print(error_msg)
            self._show_error("Installation Error", error_msg)
            self._installation_failed(error_msg)
            return False
    
    def _update_progress(self):
        """Update the installation progress."""
        if not self._is_installing:
            return GLib.SOURCE_REMOVE
        
        try:
            # Get progress from Anaconda
            progress, message = self._anaconda.get_installation_progress()
            
            # Update UI
            progress_fraction = max(0.0, min(1.0, progress / 100.0))  # Ensure between 0-1
            self.progress_bar.set_fraction(progress_fraction)
            self.progress_bar.set_text(f"{int(progress)}%")
            self.progress_label.set_text(message or "Installing...")
            
            # Update status with storage info periodically
            if progress - self._last_progress >= 5.0:  # Every 5% or so
                try:
                    storage_status = self._anaconda.get_storage_status()
                    self.status_label.set_text(f"Status: {storage_status}")
                except Exception as e:
                    print(f"Error getting storage status: {e}")
                    self.status_label.set_text("Status: Installing...")
                
                self._last_progress = progress
            
            # Check if installation is complete
            if progress >= 100.0:
                self._installation_complete()
                return GLib.SOURCE_REMOVE
                
            return GLib.SOURCE_CONTINUE
            
        except Exception as e:
            error_msg = f"Error updating progress: {str(e)}"
            print(error_msg)
            self._installation_failed(error_msg)
            return GLib.SOURCE_REMOVE
    
    def _installation_complete(self):
        """Handle installation completion."""
        print("Installation completed successfully")
        self._is_installing = False
        self.progress_bar.set_fraction(1.0)
        self.progress_bar.set_text("100%")
        self.progress_label.set_text("Installation complete!")
        self.status_label.set_text("The system will now restart...")
        self.cancel_button.set_label("Finish")
        
        # Call completion callback with success=True
        if self._completion_callback:
            GLib.idle_add(lambda: self._completion_callback(True, "Installation completed successfully"))
        
        # Schedule system reboot after a short delay
        GLib.timeout_add_seconds(5, self._reboot_system)
    
    def _installation_failed(self, error_message):
        """Handle installation failure."""
        print(f"Installation failed: {error_message}")
        self._is_installing = False
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("0%")
        self.progress_label.set_text("Installation failed!")
        self.status_label.set_text(f"Error: {error_message}")
        self.cancel_button.set_label("Close")
        
        # Call completion callback with failure
        if self._completion_callback:
            GLib.idle_add(lambda: self._completion_callback(False, error_message))
    
    def _reboot_system(self):
        """Reboot the system after successful installation."""
        try:
            print("Rebooting system...")
            # Use systemd to schedule a reboot
            subprocess.run(["systemctl", "reboot"], check=True)
        except Exception as e:
            print(f"Failed to reboot system: {e}")
            # If reboot fails, show a message to the user
            self.status_label.set_text("Please restart your system to complete the installation.")
        
        return False  # Don't repeat
    
    def cancel_installation(self):
        """Cancel the installation process."""
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
        
        self._is_installing = False
        print("Installation cancelled by user")
        self.progress_label.set_text("Installation cancelled")
        self.status_label.set_text("The installation was cancelled.")
        self.cancel_button.set_label("Close")
    
    def _show_error(self, title, message):
        """Show an error dialog."""
        dialog = Adw.MessageDialog.new(
            transient_for=self.get_root(),
            heading=title,
            body=message
        )
        dialog.add_response("ok", "OK")
        dialog.present() 