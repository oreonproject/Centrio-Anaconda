import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, GObject
import os
import subprocess
from pathlib import Path

@Gtk.Template(filename='ui/software_selection.ui')
class SoftwareSelectionView(Gtk.Box):
    __gtype_name__ = 'SoftwareSelectionView'

    # Template Children
    kickstart_file_button = Gtk.Template.Child()
    kickstart_file_label = Gtk.Template.Child()
    use_live_image_radio = Gtk.Template.Child()
    use_kickstart_radio = Gtk.Template.Child()
    flatpak_switch = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    
    # File chooser dialog
    _file_chooser = None
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kickstart_path = None
        self._use_kickstart = False
        self._enable_flatpak = False
        
        # Connect signals
        self.kickstart_file_button.connect("clicked", self._on_file_chooser_clicked)
        self.use_kickstart_radio.connect("toggled", self._on_selection_changed)
        self.flatpak_switch.connect("notify::active", self._on_flatpak_toggled)
        
        # Default to using live image packages
        self.use_live_image_radio.set_active(True)
        self._update_ui()
        print("SoftwareSelectionView initialized")
    
    def _on_file_chooser_clicked(self, button):
        """Handle click on the file chooser button."""
        if self._file_chooser is None:
            self._file_chooser = Gtk.FileChooserNative.new(
                "Select Kickstart File",
                self.get_native(),
                Gtk.FileChooserAction.OPEN,
                "_Open",
                "_Cancel"
            )
            
            # Set up file filter for .ks files
            filter_ks = Gtk.FileFilter()
            filter_ks.set_name("Kickstart files (*.ks)")
            filter_ks.add_pattern("*.ks")
            self._file_chooser.add_filter(filter_ks)
            
            # Connect to response signal
            self._file_chooser.connect("response", self._on_file_chooser_response)
        
        self._file_chooser.show()
    
    def _on_file_chooser_response(self, dialog, response):
        """Handle response from the file chooser dialog."""
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                self._kickstart_path = file.get_path()
                self.kickstart_file_label.set_label(os.path.basename(self._kickstart_path))
                self._update_status(f"Selected kickstart file: {os.path.basename(self._kickstart_path)}")
        
        # Don't destroy the dialog, just hide it for reuse
        dialog.hide()
    
    def _on_selection_changed(self, button):
        """Handle changes in the selection method."""
        self._use_kickstart = self.use_kickstart_radio.get_active()
        self._update_ui()
    
    def _on_flatpak_toggled(self, switch, _):
        """Handle Flatpak enable/disable toggle."""
        self._enable_flatpak = switch.get_active()
        self._update_status(f"Flatpak will be {'enabled' if self._enable_flatpak else 'disabled'} after installation")
    
    def _update_ui(self):
        """Update UI based on current state."""
        self.kickstart_file_button.set_sensitive(self._use_kickstart)
        if not self._use_kickstart:
            self._update_status("Using packages from the live image")
            self.kickstart_file_label.set_label("")
    
    def _update_status(self, message):
        """Update the status label with the given message."""
        self.status_label.set_label(message)
    
    def _setup_flatpak(self):
        """Set up Flatpak repository if enabled."""
        if not self._enable_flatpak:
            return []
            
        return [
            "flatpak",
            "remote-add",
            "--if-not-exists",
            "flathub",
            "https://dl.flathub.org/repo/flathub.flatpakrepo"
        ]
    
    def get_selected_software(self):
        """
        Get the selected software configuration.
        
        Returns:
            dict: Dictionary containing software configuration including
                  kickstart path (if any) and post-installation commands.
        """
        post_install_commands = []
        
        # Add Flatpak setup if enabled
        flatpak_cmd = self._setup_flatpak()
        if flatpak_cmd:
            post_install_commands.append(flatpak_cmd)
        
        if self._use_kickstart and self._kickstart_path:
            return {
                'source_type': 'kickstart',
                'kickstart_path': self._kickstart_path,
                'post_install_commands': post_install_commands
            }
        else:
            # Use packages from live image
            return {
                'source_type': 'live_image',
                'post_install_commands': post_install_commands
            }