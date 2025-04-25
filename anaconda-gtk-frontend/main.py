import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio
from src.window import ExampleWindow


class ExampleApplication(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id='com.example.AnacondaGtk', 
                         flags=Gio.ApplicationFlags.FLAGS_NONE,
                         **kwargs)
        self.win = None

        # Add quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit)
        self.add_action(quit_action)

    def do_activate(self):
        # Activities within the application
        if not self.win:
            self.win = ExampleWindow(application=self)
        self.win.present()

    def on_quit(self, action, param):
        self.quit() # Closes the application


if __name__ == "__main__":
    app = ExampleApplication()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status) 