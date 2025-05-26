import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib
import os
import subprocess
from pathlib import Path

@Gtk.Template(filename='ui/software_selection.ui')
class SoftwareSelectionView(Gtk.Box):
    __gtype_name__ = 'SoftwareSelectionView'

    # Template Children
    kickstart_file_chooser = Gtk.Template.Child()
    use_live_image_radio = Gtk.Template.Child()
    use_kickstart_radio = Gtk.Template.Child()
    flatpak_switch = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kickstart_path = None
        self._use_kickstart = False
        self._enable_flatpak = False
        
        # Set up file filter for .ks files
        filter_ks = Gtk.FileFilter()
        filter_ks.set_name("Kickstart files")
        filter_ks.add_pattern("*.ks")
        self.kickstart_file_chooser.add_filter(filter_ks)
        
        # Connect signals
        self.kickstart_file_chooser.connect("file-selected", self._on_file_selected)
        self.use_kickstart_radio.connect("toggled", self._on_selection_changed)
        self.flatpak_switch.connect("notify::active", self._on_flatpak_toggled)
        
        # Default to using live image packages
        self.use_live_image_radio.set_active(True)
        self._update_ui()
        print("SoftwareSelectionView initialized")
    
    def _on_file_selected(self, chooser):
        """Handle selection of a kickstart file."""
        self._kickstart_path = chooser.get_filename()
        self._update_status(f"Selected kickstart file: {os.path.basename(self._kickstart_path)}")
    
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
        self.kickstart_file_chooser.set_sensitive(self._use_kickstart)
        if not self._use_kickstart:
            self._update_status("Using packages from the live image")
    
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