import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio
import re # For basic username validation

@Gtk.Template(filename='ui/user_creation.ui')
class UserCreationView(Gtk.Box):
    __gtype_name__ = 'UserCreationView'

    # Template children
    full_name_row = Gtk.Template.Child()
    username_row = Gtk.Template.Child()
    password_row = Gtk.Template.Child()
    confirm_password_row = Gtk.Template.Child()
    admin_check = Gtk.Template.Child()
    root_enable_check = Gtk.Template.Child()
    root_password_row = Gtk.Template.Child()
    root_confirm_password_row = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Connect signals for validation (optional - can be done in main window)
        self.username_row.connect("notify::text", self.validate_username)
        self.password_row.connect("notify::text", self.validate_passwords)
        self.confirm_password_row.connect("notify::text", self.validate_passwords)
        self.root_password_row.connect("notify::text", self.validate_root_passwords)
        self.root_confirm_password_row.connect("notify::text", self.validate_root_passwords)
        print("UserCreationView initialized")

    def validate_username(self, *args):
        username = self.username_row.get_text().strip()
        is_valid = bool(username) and re.match("^[a-z_][a-z0-9_-]*$", username)
        # Basic validation: not empty, starts with lowercase/underscore, contains valid chars
        if not username: # Don't show error for empty field yet
             self.username_row.set_property("error-level", Gtk.InputError.NONE)
             # self.username_row.props.secondary_icon_tooltip_text = ""
        elif not is_valid:
             self.username_row.set_property("error-level", Gtk.InputError.ERROR)
             # self.username_row.props.secondary_icon_tooltip_text = "Invalid username format" # Needs Gtk >= 4.12
        else:
             self.username_row.set_property("error-level", Gtk.InputError.NONE)
             # self.username_row.props.secondary_icon_tooltip_text = ""
        return is_valid

    def validate_passwords(self, *args):
        pw1 = self.password_row.get_text()
        pw2 = self.confirm_password_row.get_text()
        match = bool(pw1) and (pw1 == pw2) # Must not be empty and must match
        pass_ok = bool(pw1) # Password field has content
        confirm_ok = bool(pw2) # Confirm field has content
        
        if not pw1 and not pw2:
             self.password_row.set_property("error-level", Gtk.InputError.NONE)
             self.confirm_password_row.set_property("error-level", Gtk.InputError.NONE)
        elif not match:
            if pass_ok:
                self.password_row.set_property("error-level", Gtk.InputError.NONE)
            if confirm_ok:
                self.confirm_password_row.set_property("error-level", Gtk.InputError.ERROR)
        else: # Match and not empty
            self.password_row.set_property("error-level", Gtk.InputError.NONE)
            self.confirm_password_row.set_property("error-level", Gtk.InputError.NONE)

        return match

    def validate_root_passwords(self, *args):
        if not self.root_enable_check.get_active():
             self.root_password_row.set_property("error-level", Gtk.InputError.NONE)
             self.root_confirm_password_row.set_property("error-level", Gtk.InputError.NONE)
             return True # Not enabled, so valid
             
        pw1 = self.root_password_row.get_text()
        pw2 = self.root_confirm_password_row.get_text()
        match = bool(pw1) and (pw1 == pw2)
        pass_ok = bool(pw1)
        confirm_ok = bool(pw2)

        if not pw1 and not pw2:
            self.root_password_row.set_property("error-level", Gtk.InputError.NONE)
            self.root_confirm_password_row.set_property("error-level", Gtk.InputError.NONE)
        elif not match:
            if pass_ok:
                 self.root_password_row.set_property("error-level", Gtk.InputError.NONE)
            if confirm_ok:
                 self.root_confirm_password_row.set_property("error-level", Gtk.InputError.ERROR)
        else: # Match and not empty
            self.root_password_row.set_property("error-level", Gtk.InputError.NONE)
            self.root_confirm_password_row.set_property("error-level", Gtk.InputError.NONE)
        
        return match

    def get_user_details(self):
        """Returns the entered user details after basic validation."""
        details = {
            "full_name": self.full_name_row.get_text().strip(),
            "username": self.username_row.get_text().strip(),
            "password": self.password_row.get_text(),
            "is_admin": self.admin_check.get_active(),
            "root_enabled": self.root_enable_check.get_active(),
            "root_password": self.root_password_row.get_text() if self.root_enable_check.get_active() else None
        }

        # Perform validation checks
        valid_username = self.validate_username()
        valid_password = self.validate_passwords()
        valid_root_password = self.validate_root_passwords()

        if not details["username"] or not valid_username:
            print("Validation Error: Invalid or empty username.")
            return None
        if not details["password"] or not valid_password:
            print("Validation Error: Passwords do not match or are empty.")
            return None
        if details["root_enabled"] and (not details["root_password"] or not valid_root_password):
            print("Validation Error: Root passwords do not match or are empty.")
            return None
            
        # Return the user details including the password
        # The password is needed by the installer to create the user account
        result = {
            "full_name": details["full_name"],
            "username": details["username"],
            "password": details["password"],  # Include the actual password
            "is_admin": details["is_admin"],
            "root_enabled": details["root_enabled"],
            "root_password": details["root_password"] if details["root_enabled"] else None
        }
        
        # For debugging
        print(f"User details collected: { {k: '***' if 'password' in k else v for k, v in result.items()} }")
        return result 