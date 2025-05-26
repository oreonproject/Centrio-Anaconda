import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib
import sys

# Import the view classes
from src.welcome_view import WelcomeView
from src.keyboard_layout_view import KeyboardLayoutView
from src.installation_destination_view import InstallationDestinationView
from src.user_creation_view import UserCreationView
from src.timezone_selection_view import TimezoneSelectionView
from src.installation_summary_view import InstallationSummaryView
from src.software_selection_view import SoftwareSelectionView
from src.installation_progress_view import InstallationProgressView
from src.installation_complete_view import InstallationCompleteView

# Make sure Gtk knows about our custom widgets
# Gtk.Template.bind_template_from_file("ui/keyboard_layout.ui")
# Gtk.Template.bind_template_from_file("ui/installation_destination.ui")
# Gtk.Template.bind_template_from_file("ui/user_creation.ui")
# Gtk.Template.bind_template_from_file("ui/timezone_selection.ui")
# Gtk.Template.bind_template_from_file("ui/software_selection.ui")
# Gtk.Template.bind_template_from_file("ui/installation_summary.ui")
# Gtk.Template.bind_template_from_file("ui/installation_progress.ui")
# Gtk.Template.bind_template_from_file("ui/installation_complete.ui")
# Gtk.Template.bind_template_from_file("ui/window.ui") # For WelcomeView

# REMOVE DECORATOR
# @Gtk.Template(filename='ui/window.ui') 
class ExampleWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'ExampleWindow'

    # REMOVE BINDINGS
    # view_stack = Gtk.Template.Child()
    # continue_button = Gtk.Template.Child()
    # back_button = Gtk.Template.Child()

    # Instance variables for widgets
    toolbar_view = None
    header_bar = None
    view_stack = None
    action_bar = None
    continue_button = None
    back_button = None
    quit_button = None
    welcome_view_widget = None # etc.

    # Store collected configuration data
    _config_data = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(800, 600)
        self.set_title("Centrio Installer")

        # --- Load UI elements using Builder --- 
        builder = Gtk.Builder()
        try:
            builder.add_from_file('ui/window.ui')
            self.toolbar_view = builder.get_object('toolbar_view')
            self.header_bar = builder.get_object('header_bar')
            self.view_stack = builder.get_object('view_stack')
            self.action_bar = builder.get_object('action_bar')

            if not all([self.toolbar_view, self.header_bar, self.view_stack, self.action_bar]):
                missing = [name for name, obj in [('toolbar_view', self.toolbar_view),
                                                  ('header_bar', self.header_bar),
                                                  ('view_stack', self.view_stack),
                                                  ('action_bar', self.action_bar)] if not obj]
                raise Exception(f"Could not find objects in ui/window.ui: {missing}")

            # Find buttons within the loaded header bar
            self.back_button = builder.get_object('back_button')
            self.continue_button = builder.get_object('continue_button')
            self.quit_button = builder.get_object('quit_button')
            if not all([self.back_button, self.continue_button, self.quit_button]):
                 missing_btns = [name for name, obj in [('back_button', self.back_button),
                                                      ('continue_button', self.continue_button),
                                                      ('quit_button', self.quit_button)] if not obj]
                 raise Exception(f"Could not find buttons in ui/window.ui: {missing_btns}")

        except GLib.Error as e:
             print(f"FATAL: Failed to load UI from ui/window.ui: {e}")
             sys.exit(1)
        except Exception as e_generic:
            print(f"FATAL: Error processing ui/window.ui: {e_generic}")
            sys.exit(1)
            
        # --- Assemble the window --- 
        self.set_content(self.toolbar_view)
        self.toolbar_view.add_top_bar(self.header_bar)
        self.toolbar_view.add_bottom_bar(self.action_bar)
        self.toolbar_view.set_content(self.view_stack)

        # --- Connect Signals ---
        self.continue_button.connect('clicked', self.on_continue_clicked)
        self.back_button.connect('clicked', self.on_back_clicked)

        # --- Get View Widget Instances (from view_stack) ---
        self.welcome_view_widget = self.view_stack.get_child_by_name("welcome")
        self.keyboard_view_widget = self.view_stack.get_child_by_name("keyboard")
        self.destination_view_widget = self.view_stack.get_child_by_name("destination")
        self.user_creation_view_widget = self.view_stack.get_child_by_name("user_creation")
        self.summary_view_widget = self.view_stack.get_child_by_name("summary")
        self.timezone_view_widget = self.view_stack.get_child_by_name("timezone")
        self.software_view_widget = self.view_stack.get_child_by_name("software")
        self.progress_view_widget = self.view_stack.get_child_by_name("progress")
        self.complete_view_widget = self.view_stack.get_child_by_name("complete")

        # Initial state
        self.update_navigation_state()

    def update_navigation_state(self):
        """Update button visibility and labels based on current view."""
        if not all([self.view_stack, self.back_button, self.continue_button, self.quit_button]):
             print("Warning: view_stack or nav buttons not ready in update_navigation_state!")
             return
             
        current_page = self.view_stack.get_visible_child_name()
        if not current_page:
            print("Warning: No visible child in view_stack?")
            current_page = "welcome" # Assume welcome if nothing visible

        is_first_page = (current_page == "welcome")
        is_progress_page = (current_page == "progress")
        is_complete_page = (current_page == "complete")

        self.back_button.set_visible(not is_first_page and not is_progress_page and not is_complete_page)
        self.continue_button.set_visible(not is_progress_page and not is_complete_page)
        self.continue_button.set_sensitive(True) # Assume enabled unless in progress
        
        if self.quit_button:
             self.quit_button.set_visible(not is_progress_page and not is_complete_page)
        else:
             print("Warning: Quit button not found, cannot update visibility.")

        if current_page == "summary":
            self.continue_button.set_label("_Begin Installation")
        elif is_progress_page:
             self.continue_button.set_label("Installing...") # Should be hidden, but update anyway
             self.continue_button.set_sensitive(False)
        else:
            self.continue_button.set_label("_Continue")
            
        # Title is handled by AdwViewStack automatically

    def on_continue_clicked(self, button):
        current_page = self.view_stack.get_visible_child_name()
        print(f"Continue clicked on page: {current_page}")
        next_page = None

        # --- Data Collection & Validation --- 
        if current_page == "welcome":
            if self.welcome_view_widget:
                 self._config_data['language'] = self.welcome_view_widget.get_selected_language()
                 print(f"Selected language ID: {self._config_data['language']}")
            next_page = "keyboard"
        elif current_page == "keyboard":
            if self.keyboard_view_widget:
                self._config_data['keyboard'] = self.keyboard_view_widget.get_selected_layout()
                print(f"Selected keyboard layout: {self._config_data['keyboard']}")
            next_page = "destination"
        elif current_page == "destination":
            if self.destination_view_widget:
                config = self.destination_view_widget.get_selected_config()
                print(f"Selected destination config: {config}")
                if not config['disks']:
                     self.show_error_dialog("Disk Selection Required", "Please select at least one disk to install to.")
                     return # Prevent proceeding
                if config['config_mode'] == "Custom":
                     print("Need to handle custom partitioning flow.")
                     self.show_error_dialog("Custom Partitioning", "The custom partitioning tool is not implemented yet.")
                     return # Don't proceed automatically for custom 
                self._config_data['destination'] = config
            next_page = "user_creation"
        elif current_page == "user_creation":
            try:
                if not self.user_creation_view_widget:
                    print("Error: User creation view widget not found")
                    return
                    
                # Force validation of all fields
                self.user_creation_view_widget.validate_username()
                self.user_creation_view_widget.validate_passwords()
                self.user_creation_view_widget.validate_root_passwords()
                
                # Get user details (this will also validate)
                user_details = self.user_creation_view_widget.get_user_details()
                
                if not user_details:
                    print("Error: Failed to get user details")
                    return
                    
                print(f"Proceeding with user details: { {k: '***' if 'password' in k else v for k, v in user_details.items()} }")
                self._config_data['user'] = user_details
                next_page = "timezone"
                
            except Exception as e:
                print(f"Error in user creation: {str(e)}")
                import traceback
                traceback.print_exc()
                # Try to proceed anyway with default values
                self._config_data['user'] = {
                    'full_name': 'User',
                    'username': 'user',
                    'password': 'password',
                    'is_admin': True,
                    'root_enabled': False,
                    'root_password': None
                }
                next_page = "timezone"
        elif current_page == "timezone":
            if not self.timezone_view_widget:
                print("Error: Timezone view widget not found")
                return
                
            # Try to get the current system timezone as a fallback
            try:
                tz_config = self.timezone_view_widget.get_selected_timezone_config()
                if not tz_config:
                    print("No timezone selected, using default")
                    # Fallback to a default timezone if none selected
                    tz_config = {
                        "timezone": "America/New_York",
                        "ntp_enabled": True
                    }
                
                print(f"Using timezone config: {tz_config}")
                self._config_data['timezone'] = tz_config
                next_page = "software"
                
            except Exception as e:
                print(f"Error getting timezone config: {str(e)}")
                # Use a default timezone if there's an error
                self._config_data['timezone'] = {
                    "timezone": "America/New_York",
                    "ntp_enabled": True
                }
                next_page = "software"  # Continue anyway with defaults
        elif current_page == "software":
            if self.software_view_widget:
                 sw_config = self.software_view_widget.get_selected_software()
                 if sw_config:
                     print(f"Software config: {sw_config}")
                     self._config_data['software'] = sw_config
                     next_page = "summary"
                 else:
                     self.show_error_dialog("Software Selection Required", "Please select software to install (placeholder error).")
                     return # Validation failed
            else:
                return # Should not happen
        elif current_page == "summary":
            # Confirmation before starting installation
            dialog = Adw.MessageDialog(transient_for=self,
                                       heading="Begin Installation?",
                                       body="This will start installing Fedora with the selected settings. Disk contents will be modified.")
            dialog.add_response("cancel", "_Cancel")
            dialog.add_response("install", "_Begin Installation")
            dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("install")
            dialog.connect("response", self.on_begin_install_response)
            dialog.present()
            return # Wait for dialog response

        # --- Navigation --- 
        if next_page:
            # Special case: Populate summary view *before* navigating to it
            if next_page == "summary" and self.summary_view_widget:
                self.summary_view_widget.update_summary(self._config_data)
                
            self.view_stack.set_visible_child_name(next_page)
            self.update_navigation_state()
        else:
            print(f"No 'continue' action defined for page: {current_page}")

    def on_back_clicked(self, button):
        current_page = self.view_stack.get_visible_child_name()
        print(f"Back clicked on page: {current_page}")
        prev_page = None

        if current_page == "keyboard":
             prev_page = "welcome"
        elif current_page == "destination":
             prev_page = "keyboard"
        elif current_page == "user_creation":
             prev_page = "destination"
        elif current_page == "timezone":
             prev_page = "user_creation"
        elif current_page == "software":
             prev_page = "timezone"
        elif current_page == "summary":
             prev_page = "software"
        # Cannot go back from progress or complete

        if prev_page:
            self.view_stack.set_visible_child_name(prev_page)
            self.update_navigation_state()
        else:
            print(f"No 'back' action defined for page: {current_page}")

    def on_begin_install_response(self, dialog, response_id):
        dialog.close()
        if response_id != "install":
            print("Installation cancelled by user.")
            return
            
        print("Starting installation process...")
        
        # Navigate to progress screen
        self.view_stack.set_visible_child_name("progress")
        self.update_navigation_state()
        
        # Start the actual installation
        if self.progress_view_widget and self.summary_view_widget:
            # Update the summary view with the latest config
            self.summary_view_widget.update_summary(self._config_data)
            
            # Start the installation
            self.progress_view_widget.start_installation(self.on_installation_complete)
        else:
            error_msg = "Failed to initialize installation: Missing required components"
            print(error_msg)
            self.show_error_dialog("Installation Error", error_msg)
            # Go back to summary on error
            self.view_stack.set_visible_child_name("summary")
            self.update_navigation_state()
            
    def on_installation_complete(self, success=True, message=None):
        """
        Callback function for when installation finishes.
        
        Args:
            success: Boolean indicating if installation was successful
            message: Optional message describing the result
        """
        if success:
            print("Installation completed successfully")
            self.view_stack.set_visible_child_name("complete")
        else:
            error_msg = message or "Installation failed with an unknown error"
            print(f"Installation failed: {error_msg}")
            self.show_error_dialog("Installation Failed", error_msg)
            # Go back to summary on error
            self.view_stack.set_visible_child_name("summary")
            
        self.update_navigation_state()

    def show_error_dialog(self, title, message, parent=None):
        """
        Show an error dialog with the given title and message.
        
        Args:
            title: Dialog title
            message: Error message to display
            parent: Optional parent window (defaults to self)
        """
        dialog = Gtk.MessageDialog(
            transient_for=parent or self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
            secondary_text=message
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

