# centrio_installer/pages/base.py

import gi
import os
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib

# Use D-Bus helper functions from utils
try:
    from ..utils import dbus_available, DBusError, get_dbus_proxy
except ImportError:
    dbus_available = False
    DBusError = Exception
    get_dbus_proxy = None # Define as None if utils fails
    print("Warning: Failed to import D-Bus utilities (utils.py). D-Bus functionality will be limited.")

# D-Bus imports and utils
# from ..constants import ANACONDA_BUS_NAME, ANACONDA_OBJECT_PATH, ANACONDA_INTERFACE # Remove this line

import time
from collections import namedtuple # Import namedtuple

# Define a namedtuple for service information
ServiceInfo = namedtuple("ServiceInfo", ["name", "object_path", "interface_name"])

class BaseConfigurationPage(Adw.PreferencesPage):
    """Base class for configuration pages.
    
    Handles passing the main window and overlay references.
    Subclasses handle their own content, D-Bus connection, and toast display.
    """
    def __init__(self, title, subtitle, main_window, overlay_widget, **kwargs):
        super().__init__(title=title, **kwargs)
        self.main_window = main_window
        self.toast_overlay = overlay_widget # Store reference from main window

    def show_toast(self, text):
        """Displays an Adw.Toast message on the main window overlay."""
        if self.toast_overlay:
            # Ensure this runs in the main GTK thread if called from elsewhere
            GLib.idle_add(self.toast_overlay.add_toast, Adw.Toast.new(text))
        else:
            # Fallback if overlay wasn't passed correctly
            print(f"TOAST (no overlay): {text}")
            
    def get_page_name(self):
        """Gets the Adw.ViewStack page name for this page instance."""
        if self.main_window and self.main_window.view_stack and self.main_window.view_stack.get_page(self):
             page = self.main_window.view_stack.get_page(self)
             return page.get_name()
        return None
        
    # Placeholder for subclasses that need to fetch data
    def connect_and_fetch_data(self):
        """Subclasses should override this to connect to D-Bus and fetch initial data."""
        print(f"{self.__class__.__name__}: connect_and_fetch_data not implemented.")
        pass
        
    # Default apply/mark methods (subclasses override apply)
    def apply_settings_and_return(self, button, config_values=None):
        print(f"Base apply_settings_and_return called for {self.__class__.__name__} - marking complete.")
        # Default behavior is just to mark complete and return
        self.mark_complete_and_return(button, config_values=config_values) 

    def mark_complete_and_return(self, button, config_values=None):
        """Marks the page complete in the main window and navigates back."""
        config_key = self.get_page_name() 
        if config_key:
            print(f"Marking '{config_key}' as complete.")
            # Use GLib.idle_add to ensure UI updates happen in the main loop
            GLib.idle_add(self.main_window.mark_config_complete, config_key, True, config_values)
            GLib.idle_add(self.main_window.return_to_summary)
        else:
            print("Warning: Could not determine page name to mark complete.")
            GLib.idle_add(self.main_window.return_to_summary) # Still try to return
        
    # Removed placeholder _connect_dbus method
    # Subclasses should call get_dbus_proxy directly in connect_and_fetch_data or __init__ 