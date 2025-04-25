import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
import time

@Gtk.Template(filename='ui/installation_progress.ui')
class InstallationProgressView(Gtk.Box):
    __gtype_name__ = 'InstallationProgressView'

    # Template Children
    progress_bar = Gtk.Template.Child()
    progress_label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._timeout_id = None
        self._completion_callback = None
        print("InstallationProgressView initialized")

    def start_installation_simulation(self, completion_callback):
        """Simulates the installation process."""
        print("Starting installation simulation...")
        self._completion_callback = completion_callback
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("Starting...")
        self.progress_label.set_text("Preparing installation environment.")
        # Use GLib timeout to simulate progress updates
        self._timeout_id = GLib.timeout_add_seconds(1, self.simulate_progress_step)

    def simulate_progress_step(self):
        """Updates progress periodically. Returns True to continue, False to stop."""
        current_fraction = self.progress_bar.get_fraction()
        new_fraction = min(current_fraction + 0.1, 1.0) # Increment by 10%
        self.progress_bar.set_fraction(new_fraction)

        # Update text based on progress
        if new_fraction < 0.3:
            msg = f"Setting up storage ({int(new_fraction*100)}%)"
        elif new_fraction < 0.7:
            msg = f"Copying system files ({int(new_fraction*100)}%)"
        elif new_fraction < 0.9:
            msg = f"Configuring system ({int(new_fraction*100)}%)"
        else:
            msg = f"Finalizing installation ({int(new_fraction*100)}%)"
        
        self.progress_bar.set_text(f"{int(new_fraction*100)}%")
        self.progress_label.set_text(msg)

        if new_fraction >= 1.0:
            print("Installation simulation complete.")
            if self._completion_callback:
                self._completion_callback() # Signal completion
            self._timeout_id = None # Clear timeout ID
            return GLib.SOURCE_REMOVE # Stop the timeout
        else:
            return GLib.SOURCE_CONTINUE # Continue the timeout

    def cancel_simulation(self):
        """Stops the simulation if running."""
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
            print("Installation simulation cancelled.") 