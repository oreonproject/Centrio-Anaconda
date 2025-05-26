import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio
import os # For simulating reboot (e.g., via systemctl)

@Gtk.Template(filename='ui/installation_complete.ui')
class InstallationCompleteView(Gtk.Box):
    __gtype_name__ = 'InstallationCompleteView'

    # Template Children
    reboot_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.reboot_button.connect('clicked', self.on_reboot_clicked)
        print("InstallationCompleteView initialized")

    def on_reboot_clicked(self, button):
        print("Reboot button clicked. Simulating reboot...")
        # In a real installer, this would trigger the actual reboot
        # For example, using os.system or subprocess:
        # try:
        #     os.system("systemctl reboot")
        # except Exception as e:
        #     print(f"Failed to initiate reboot: {e}")
        
        # For simulation purposes, just quit the app
        app = self.get_ancestor(Adw.Application)
        if app:
            app.quit() 