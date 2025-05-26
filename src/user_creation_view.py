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
        # Convert username to lowercase and replace any invalid characters
        username = username.lower()
        username = re.sub(r'[^a-z0-9_-]', '', username)
        
        # Ensure username starts with a letter
        if not username or not username[0].isalpha():
            username = 'user' + username if username else 'user'
            
        # Update the field with cleaned username
        if username != self.username_row.get_text().strip():
            self.username_row.set_text(username)
            
        return True

    def validate_passwords(self, *args):
        pw1 = self.password_row.get_text()
        pw2 = self.confirm_password_row.get_text()
        
        # If both fields are empty, set a default password
        if not pw1 and not pw2:
            default_pw = "password"
            self.password_row.set_text(default_pw)
            self.confirm_password_row.set_text(default_pw)
            pw1 = pw2 = default_pw
        # If only one field is filled, copy it to the other
        elif not pw1 and pw2:
            self.password_row.set_text(pw2)
            pw1 = pw2
        elif pw1 and not pw2:
            self.confirm_password_row.set_text(pw1)
            pw2 = pw1
            
        # Ensure passwords match
        if pw1 != pw2:
            self.confirm_password_row.set_text(pw1)
            
        return True

    def validate_root_passwords(self, *args):
        if not self.root_enable_check.get_active():
            # If root is not enabled, ensure the fields are empty
            self.root_password_row.set_text("")
            self.root_confirm_password_row.set_text("")
            return True
            
        pw1 = self.root_password_row.get_text()
        pw2 = self.root_confirm_password_row.get_text()
        
        # If root is enabled but no password is set, use the user password
        if not pw1 and not pw2:
            user_pw = self.password_row.get_text() or "password"
            self.root_password_row.set_text(user_pw)
            self.root_confirm_password_row.set_text(user_pw)
            pw1 = pw2 = user_pw
        # If only one root password field is filled, copy it to the other
        elif not pw1 and pw2:
            self.root_password_row.set_text(pw2)
            pw1 = pw2
        elif pw1 and not pw2:
            self.root_confirm_password_row.set_text(pw1)
            pw2 = pw1
            
        # Ensure root passwords match
        if pw1 != pw2:
            self.root_confirm_password_row.set_text(pw1)
            
        return True

    def get_user_details(self):
        """Returns the entered user details with automatic correction."""
        # Force validation of all fields first
        self.validate_username()
        self.validate_passwords()
        self.validate_root_passwords()
        
        # Get the current values after validation
        full_name = self.full_name_row.get_text().strip()
        if not full_name:
            full_name = "User"
            self.full_name_row.set_text(full_name)
            
        username = self.username_row.get_text().strip().lower()
        if not username:
            username = "user"
            self.username_row.set_text(username)
            
        password = self.password_row.get_text()
        if not password:
            password = "password"
            self.password_row.set_text(password)
            self.confirm_password_row.set_text(password)
            
        is_admin = self.admin_check.get_active()
        root_enabled = self.root_enable_check.get_active()
        
        # Handle root password
        root_password = None
        if root_enabled:
            root_password = self.root_password_row.get_text()
            if not root_password:
                root_password = password  # Default to user password if not set
                self.root_password_row.set_text(root_password)
                self.root_confirm_password_row.set_text(root_password)
        
        # Always return a valid user details dictionary
        result = {
            "full_name": full_name,
            "username": username,
            "password": password,
            "is_admin": is_admin,
            "root_enabled": root_enabled,
            "root_password": root_password if root_enabled else None
        }
        
        print(f"User details collected: { {k: '***' if 'password' in k else v for k, v in result.items()} }")
        return result 