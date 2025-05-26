import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
import os # Import os
import re # Import re

# Note: This class now refers to the WelcomeView template in window.ui
@Gtk.Template(filename='ui/welcome_view.ui')
class WelcomeView(Gtk.Box):
    __gtype_name__ = 'WelcomeView'

    # Bind the new widgets
    preferences_page = Gtk.Template.Child()
    language_combo_row = Gtk.Template.Child()

    # Map combo row index to language ID
    _language_map = { 
        0: "en",
        1: "es",
        2: "fr"
        # Add more mappings corresponding to items in UI file
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print("WelcomeView initialized")
        self.update_welcome_label()
        # Pre-select language based on locale? Maybe later.

    def get_distro_name(self):
        """Reads /etc/os-release to get the distribution name."""
        distro_name = "this distribution" # Default
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('PRETTY_NAME='):
                        # Extract value, remove quotes
                        distro_name = re.match(r'PRETTY_NAME="?(.*?)"?$', line).group(1)
                        break # Prefer PRETTY_NAME
                    elif line.startswith('NAME=') and distro_name == "this distribution":
                         # Use NAME as fallback
                         distro_name = re.match(r'NAME="?(.*?)"?$', line).group(1)
        except FileNotFoundError:
            print("Warning: /etc/os-release not found.")
        except Exception as e:
            print(f"Warning: Could not parse /etc/os-release: {e}")
        return distro_name

    def update_welcome_label(self):
        """Sets the preferences page title text with the detected distro name."""
        distro = self.get_distro_name()
        # Set the 'title' property of AdwPreferencesPage
        if self.preferences_page: 
             self.preferences_page.set_title(f"Welcome to {distro}!") 
             print(f"Set PreferencesPage title to: {self.preferences_page.get_title()}")
        else:
             print("Warning: preferences_page not bound when update_welcome_label called.")

    def get_selected_language(self):
        """Gets the language ID from the selected item in the combo row."""
        if self.language_combo_row:
             selected_index = self.language_combo_row.get_selected()
             lang_id = self._language_map.get(selected_index, "en") # Default to 'en' if mapping missing
             print(f"Language combo index {selected_index} maps to ID: {lang_id}")
             return lang_id
        else:
             print("Warning: language_combo_row not bound in get_selected_language")
             return "en" # Default language ID 