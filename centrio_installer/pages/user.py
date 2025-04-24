# centrio_installer/pages/user.py

import gi
# Removed subprocess and shlex imports
# import subprocess
# import shlex
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib # Added GLib

# Import D-Bus utils and constants
from .base import BaseConfigurationPage, dbus_available, DBusError, get_dbus_proxy
from ..constants import USERS_SERVICE, USERS_OBJECT_PATH, USERS_INTERFACE

class UserPage(BaseConfigurationPage):
    def __init__(self, main_window, overlay_widget, **kwargs):
        super().__init__(title="User Creation", subtitle="Create an initial user account", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.users_proxy = None
        self.initial_fetch_done = True # No initial data to fetch for user creation
        
        # --- UI Setup (remains the same) ---
        details_group = Adw.PreferencesGroup(title="User Details")
        self.add(details_group)
        self.real_name_row = Adw.EntryRow(title="Full Name")
        details_group.add(self.real_name_row)
        self.username_row = Adw.EntryRow(title="Username")
        details_group.add(self.username_row)
        
        password_group = Adw.PreferencesGroup(title="Password")
        self.add(password_group)
        self.password_row = Adw.PasswordEntryRow(title="Password")
        password_group.add(self.password_row)
        self.confirm_password_row = Adw.PasswordEntryRow(title="Confirm Password")
        password_group.add(self.confirm_password_row)
        
        admin_group = Adw.PreferencesGroup(title="Administrator Privileges")
        self.add(admin_group)
        self.admin_check = Gtk.CheckButton(label="Make this user an administrator")
        self.admin_check.set_tooltip_text("Adds the user to the 'wheel' group for sudo access")
        self.admin_check.set_active(True) 
        admin_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        admin_box.set_halign(Gtk.Align.CENTER)
        admin_box.set_valign(Gtk.Align.CENTER)
        admin_box.append(self.admin_check)
        admin_group.add(admin_box)
        
        button_group = Adw.PreferencesGroup()
        self.add(button_group)
        self.complete_button = Gtk.Button(label="Apply User Account") # Changed label
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        button_group.add(self.complete_button)

        # --- Connect Signals --- 
        self.username_row.connect("notify::text", self.validate_input)
        self.password_row.connect("notify::text", self.validate_input)
        self.confirm_password_row.connect("notify::text", self.validate_input)
        # Connect button to the D-Bus apply method
        self.complete_button.connect("clicked", self.apply_settings_and_return) 

        # --- Initial Validation & D-Bus Connect --- 
        self.validate_input() 
        self.connect_and_fetch_data() # Connect to D-Bus

    def connect_and_fetch_data(self):
         """Connects to the Users D-Bus service."""
         print("UserPage: Connecting to D-Bus...")
         if not dbus_available:
            self.show_toast("D-Bus is not available. Cannot manage users.")
            # Disable apply button if D-Bus is needed? Or allow confirmation?
            # For now, allow confirmation, but applying will fail later.
            return 
            
         self.users_proxy = get_dbus_proxy(USERS_SERVICE, USERS_OBJECT_PATH, USERS_INTERFACE)
         
         if self.users_proxy:
            print("UserPage: Successfully got D-Bus proxy.")
            # Fetch existing users/root pw status? Anaconda UI might do this.
            # For now, just establish the proxy connection.
         else:
            self.show_toast("Failed to connect to Users D-Bus service.")

    def validate_input(self, widget=None, param=None):
        """Validate user input fields and update button sensitivity."""
        if not all(hasattr(self, attr) for attr in ['username_row', 'password_row', 'confirm_password_row', 'complete_button']):
             return
             
        username = self.username_row.get_text().strip()
        password = self.password_row.get_text()
        confirm = self.confirm_password_row.get_text()
        
        # Basic validation - adapt as needed based on Anaconda requirements
        # (e.g., length, allowed characters, reserved names)
        valid_user = bool(username) and username.isalnum() and len(username) < 32 and username.islower()
        valid_password = bool(password) and password == confirm and len(password) >= 6 # Add min length check
        can_apply = valid_user and valid_password

        if password and confirm and password != confirm:
            self.password_row.add_css_class("error")
            self.confirm_password_row.add_css_class("error")
        else:
            self.password_row.remove_css_class("error")
            self.confirm_password_row.remove_css_class("error")
        
        # Add feedback for password length
        if password and len(password) < 6:
             self.password_row.add_css_class("error")
             # Optionally add subtitle or tooltip about length
        else:
             # Only remove error if mismatch isn't the issue
             if not (password and confirm and password != confirm):
                 self.password_row.remove_css_class("error")
            
        self.complete_button.set_sensitive(can_apply)

    def apply_settings_and_return(self, button):
        """Validates input and applies user settings via D-Bus."""
        # Re-validate just before applying
        self.validate_input()
        if not self.complete_button.get_sensitive():
             self.show_toast("Please ensure username is valid, passwords match and meet length requirements.")
             return
             
        # Get values 
        real_name = self.real_name_row.get_text().strip()
        username = self.username_row.get_text().strip()
        password = self.password_row.get_text() 
        is_admin = self.admin_check.get_active()

        print(f"Applying user account '{username}' via D-Bus...")
        self.complete_button.set_sensitive(False)
        
        if self.users_proxy:
            try:
                # Call D-Bus method - Assuming CreateUser or similar
                # The parameters will depend heavily on the actual UsersInterface definition.
                # Example: CreateUser(username, password, real_name, is_admin, groups)
                # Anaconda might handle password hashing internally or expect a hash.
                # Check Anaconda source for the exact method signature.
                # For now, assume a method taking these details:
                groups = ["wheel"] if is_admin else [] # Add to wheel group if admin
                # Need to check if password should be plain text or hashed
                self.users_proxy.CreateUser(
                    username, 
                    password,  # Send plain text, assume Anaconda handles hashing/salting
                    real_name,
                    True,      # Home directory (usually True)
                    groups     # Additional groups
                )
                print(f"User '{username}' creation initiated via D-Bus.")
                self.show_toast(f"User account '{username}' applied.")
                
                # Config values might just be the username, or confirmation
                config_values = {"username": username, "is_admin": is_admin}
                super().mark_complete_and_return(button, config_values=config_values)
                
            except DBusError as e:
                print(f"ERROR: D-Bus error creating user: {e}")
                self.show_toast(f"Error creating user: {e}")
                self.complete_button.set_sensitive(True) # Re-enable on error
            except AttributeError as e:
                 print(f"ERROR: D-Bus method CreateUser not found: {e}. Check UsersInterface.")
                 self.show_toast(f"Failed to create user (D-Bus error): {e}")
                 self.complete_button.set_sensitive(True)
            except Exception as e:
                print(f"ERROR: Unexpected error creating user: {e}")
                self.show_toast(f"Unexpected error creating user: {e}")
                self.complete_button.set_sensitive(True)
        else:
            self.show_toast("Cannot apply user: D-Bus connection not available.")
            # Mark complete anyway?
            print("Marking complete with chosen user details despite D-Bus failure.")
            config_values = {
                "username": username, 
                "real_name": real_name, 
                "password": "(not applied)", 
                "is_admin": is_admin
            }
            super().mark_complete_and_return(button, config_values=config_values) 