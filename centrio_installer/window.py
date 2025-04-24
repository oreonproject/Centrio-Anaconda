# centrio_installer/window.py

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

# Import Page classes (Reverted to relative imports)
from .pages.welcome import WelcomePage
from .pages.summary import SummaryPage
from .pages.progress import ProgressPage
from .pages.finished import FinishedPage
from .pages.keyboard import KeyboardPage
from .pages.language import LanguagePage
from .pages.timedate import TimeDatePage
from .pages.disk import DiskPage
from .pages.network import NetworkPage
from .pages.user import UserPage
from .pages.payload import PayloadPage
from .pages.bootloader import BootloaderPage

# Import D-Bus utils and constants
from .utils import dbus_available, DBusError, get_dbus_proxy
from .constants import BOSS_SERVICE, BOSS_OBJECT_PATH, BOSS_INTERFACE

class CentrioInstallerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.boss_proxy = None # Add proxy for Boss
        self.config_state = {} # Stores completion status (True/False) for each config key
        self.required_configs = set() # Set of keys for required configurations
        self.main_page_order = ["welcome", "summary", "progress", "finished"]
        # All known configuration page keys
        self.config_page_keys = ["keyboard", "language", "timedate", "disk", "network", "user", "payload", "bootloader"]
        self.final_config = {} # Stores final selected values (may contain D-Bus object paths)

        self.set_title("Centrio Installer")
        self.set_default_size(850, 650)
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)
        
        # --- Create the single Toast Overlay --- 
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_vexpand(True)
        main_box.append(self.toast_overlay)

        # --- View Stack (inside the overlay) --- 
        self.view_stack = Adw.ViewStack()
        self.toast_overlay.set_child(self.view_stack)

        # --- Add pages to the stack --- 
        # Main flow pages
        self.welcome_page = WelcomePage()
        self.view_stack.add_titled(self.welcome_page, self.main_page_order[0], "Welcome")

        # Create Summary Page - this will also populate config_state and required_configs
        self.summary_page = SummaryPage(main_window=self)
        self.view_stack.add_titled(self.summary_page, self.main_page_order[1], "Installation Summary")

        self.progress_page = ProgressPage()
        self.view_stack.add_titled(self.progress_page, self.main_page_order[2], "Installation Progress")

        self.finished_page = FinishedPage(app=self.get_application())
        self.view_stack.add_titled(self.finished_page, self.main_page_order[3], "Finished")

        # Configuration pages - Pass main_window and the overlay
        self.keyboard_page = KeyboardPage(main_window=self, overlay_widget=self.toast_overlay)
        self.view_stack.add_titled(self.keyboard_page, "keyboard", "Keyboard Settings")
        
        self.language_page = LanguagePage(main_window=self, overlay_widget=self.toast_overlay)
        self.view_stack.add_titled(self.language_page, "language", "Language Settings")
        
        self.timedate_page = TimeDatePage(main_window=self, overlay_widget=self.toast_overlay)
        self.view_stack.add_titled(self.timedate_page, "timedate", "Time & Date Settings")
        
        self.disk_page = DiskPage(main_window=self, overlay_widget=self.toast_overlay)
        self.view_stack.add_titled(self.disk_page, "disk", "Disk Settings")
        
        self.network_page = NetworkPage(main_window=self, overlay_widget=self.toast_overlay)
        self.view_stack.add_titled(self.network_page, "network", "Network Settings")
        
        self.user_page = UserPage(main_window=self, overlay_widget=self.toast_overlay)
        self.view_stack.add_titled(self.user_page, "user", "User Settings")
        
        self.payload_page = PayloadPage(main_window=self, overlay_widget=self.toast_overlay)
        self.view_stack.add_titled(self.payload_page, "payload", "Payload Settings")
        
        self.bootloader_page = BootloaderPage(main_window=self, overlay_widget=self.toast_overlay)
        self.view_stack.add_titled(self.bootloader_page, "bootloader", "Bootloader Settings")
        
        # Ensure required_configs is populated based on SummaryPage rows
        # (Should be done within SummaryPage._add_config_row now)
        for key, config in self.summary_page.config_rows.items():
            if config["required"]:
                self.required_configs.add(key)
            # Ensure config_state has an entry for every row added
            if key not in self.config_state:
                self.config_state[key] = False 

        # --- Navigation Buttons (below the overlay) --- 
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nav_box.set_halign(Gtk.Align.END)
        nav_box.set_margin_top(6)
        nav_box.set_margin_bottom(6)
        nav_box.set_margin_start(12)
        nav_box.set_margin_end(12)
        main_box.append(nav_box)

        self.back_button = Gtk.Button(label="Back")
        self.back_button.connect("clicked", self.go_back)
        nav_box.append(self.back_button)
        
        self.next_button = Gtk.Button(label="Next")
        self.next_button.add_css_class("suggested-action")
        self.next_button.connect("clicked", self.go_next)
        nav_box.append(self.next_button)

        # Update navigation state when the visible child changes
        self.view_stack.connect("notify::visible-child-name", self.update_navigation)
        # Set initial navigation state
        self.update_navigation()

        # --- Connect to Boss D-Bus --- 
        self._connect_to_boss()

    def _connect_to_boss(self):
        """Try to connect to the Anaconda Boss D-Bus service."""
        print("Window: Connecting to Anaconda Boss D-Bus...")
        if not dbus_available:
             # Handle case where D-Bus is unavailable (show error, disable features)
             print("Window: D-Bus not available. Cannot interact with Anaconda backend.")
             # Maybe show a persistent error banner?
             toast = Adw.Toast.new("Error: Cannot connect to Anaconda backend (D-Bus unavailable).")
             self.toast_overlay.add_toast(toast)
             # Disable Summary page next button? Or allow proceeding and fail later?
             return
             
        self.boss_proxy = get_dbus_proxy(BOSS_SERVICE, BOSS_OBJECT_PATH, BOSS_INTERFACE)
        if self.boss_proxy:
             print("Window: Successfully connected to Anaconda Boss.")
             # Could potentially fetch initial state or start modules here if needed
             # try:
             #    self.boss_proxy.StartModulesWithTask() # Example: Start modules early
             # except Exception as e:
             #    print(f"Warning: Failed to pre-start modules: {e}")
        else:
             print("Window: Failed to connect to Anaconda Boss D-Bus service.")
             toast = Adw.Toast.new("Error: Failed to connect to Anaconda backend.")
             self.toast_overlay.add_toast(toast)
             # Disable Summary page next button?

    def get_current_page_info(self):
        """Helper to get information about the currently visible page."""
        current_page_name = self.view_stack.get_visible_child_name()
        is_main_page = current_page_name in self.main_page_order
        is_config_page = current_page_name in self.config_page_keys
        try:
            main_index = self.main_page_order.index(current_page_name) if is_main_page else -1
        except ValueError:
            main_index = -1
        return current_page_name, is_main_page, is_config_page, main_index

    def navigate_to_page(self, page_name):
        """Sets the visible page in the view stack."""
        # Ensure this runs in the main GTK thread
        GLib.idle_add(self.view_stack.set_visible_child_name, page_name)

    def navigate_to_config(self, config_key):
        """Navigates to a specific configuration page by its key."""
        if config_key in self.config_page_keys:
            self.navigate_to_page(config_key)

    def return_to_summary(self):
        """Navigates back to the summary page."""
        self.navigate_to_page("summary")

    def mark_config_complete(self, key, is_complete, config_values=None):
        """Mark config as complete, store identifying info/results, and update summary."""
        if key in self.config_state:
            print(f">>> mark_config_complete called for key='{key}', is_complete={is_complete}, has_config_values={config_values is not None}")
            
            was_already_complete = self.config_state.get(key, False)
            self.config_state[key] = is_complete
            
            # Store config_values if provided and newly complete or if marked incomplete
            if is_complete and config_values is not None:
                 self.final_config[key] = config_values
                 print(f"  Stored final config for '{key}': {config_values}")
            elif not is_complete and key in self.final_config:
                 print(f"  Removing final config for '{key}'")
                 del self.final_config[key]
            elif is_complete and config_values is None:
                 print(f"  Marking '{key}' complete without storing new config values.")
                 
            if hasattr(self, 'summary_page'):
                self.summary_page.update_row_status(key, is_complete)
                
            current_page_name, _, _, _ = self.get_current_page_info()
            if current_page_name == "summary":
                self.update_navigation()
        else:
             print(f"Warning: Attempted to mark completion for unknown key: {key}")

    def go_next(self, button=None):
        """Handles the action for the Next/Confirm/Begin button."""
        current_page_name, is_main_page, is_config_page, main_index = self.get_current_page_info()

        if is_config_page:
            print(f"'Next' clicked on config page '{current_page_name}', returning to summary.")
            self.return_to_summary()
        elif is_main_page:
            if current_page_name == "summary":
                # --- Begin Installation via D-Bus --- 
                print("Configuration complete, initiating installation via Anaconda Boss...")
                if not self.boss_proxy:
                     toast = Adw.Toast.new("Error: Cannot start installation - connection to backend failed.")
                     self.toast_overlay.add_toast(toast)
                     print("Error: Boss proxy not available.")
                     return
                 
                # 1. Collect Installation Tasks from Boss
                try:
                    print("Collecting installation tasks from Boss...")
                    # Example: Collect main install tasks and bootloader tasks
                    install_tasks_data = self.boss_proxy.CollectInstallSystemTasks()
                    bootloader_tasks_data = []
                    if self.final_config.get("bootloader", {}).get("install_bootloader", True):
                         # Need kernel versions? Anaconda usually handles this.
                         # For now, assume no specific kernel versions needed here.
                         bootloader_tasks_data = self.boss_proxy.CollectConfigureBootloaderTasks([]) 
                         
                    # Combine task data (list of tuples: (service_name, task_object_path))
                    all_tasks_data = install_tasks_data + bootloader_tasks_data
                    
                    if not all_tasks_data:
                         print("Error: Boss returned no installation tasks.")
                         toast = Adw.Toast.new("Error: Failed to retrieve installation tasks from backend.")
                         self.toast_overlay.add_toast(toast)
                         return
                         
                    print(f"Collected {len(all_tasks_data)} tasks:")
                    for service, path in all_tasks_data:
                         print(f"  - {service} : {path}")
                         
                    # 2. Navigate to Progress Page
                    self.navigate_to_page("progress")
                    
                    # 3. Start Installation on Progress Page using collected tasks
                    # Pass the list of (service, path) tuples
                    GLib.idle_add(self.progress_page.start_installation_dbus, self, all_tasks_data)

                except DBusError as e:
                     print(f"ERROR: D-Bus error collecting tasks: {e}")
                     toast = Adw.Toast.new(f"Error starting installation: {e}")
                     self.toast_overlay.add_toast(toast)
                except AttributeError as e:
                     print(f"ERROR: D-Bus method for collecting tasks not found: {e}. Check BossInterface.")
                     toast = Adw.Toast.new("Error starting installation (Backend interface error).")
                     self.toast_overlay.add_toast(toast)
                except Exception as e:
                     print(f"ERROR: Unexpected error collecting tasks: {e}")
                     toast = Adw.Toast.new("Unexpected error starting installation.")
                     self.toast_overlay.add_toast(toast)
                     
            elif main_index < len(self.main_page_order) - 1:
                # --- Navigate to Next Main Page --- 
                next_page_name = self.main_page_order[main_index + 1]
                print(f"Navigating from '{current_page_name}' to '{next_page_name}'")
                self.navigate_to_page(next_page_name)
            elif current_page_name == "finished": # Should be handled by finished page button
                 print("'Next' clicked on finished page - Quitting.")
                 self.get_application().quit()
            else:
                 print(f"Warning: 'Next' clicked on unexpected main page: {current_page_name}")

    def go_back(self, button=None):
        """Handles the action for the Back/Cancel button."""
        current_page_name, is_main_page, is_config_page, main_index = self.get_current_page_info()

        if is_config_page:
            # If on a config page, 'Back' means cancel and return to summary
            print(f"'Back' (Cancel) clicked on config page '{current_page_name}', returning to summary.")
            # Optionally, mark the config as incomplete again?
            # self.mark_config_complete(current_page_name, False)
            self.return_to_summary()
        elif is_main_page and main_index > 0:
            # --- Navigate to Previous Main Page --- 
            prev_page_name = self.main_page_order[main_index - 1]
            print(f"Navigating back from '{current_page_name}' to '{prev_page_name}'")
            if current_page_name == "progress": # Stop installation if going back from progress
                 self.progress_page.stop_installation()
            self.navigate_to_page(prev_page_name)
        else:
             print(f"Warning: 'Back' clicked on first page ('{current_page_name}') or unknown page.")

    def update_navigation(self, stack=None, param=None):
        """Update the state of back/next buttons based on the current page."""
        # Use idle_add to prevent issues if called during stack transitions
        GLib.idle_add(self._update_navigation_idle)

    def _update_navigation_idle(self):
        """Actual navigation update logic, called via GLib.idle_add."""
        current_page_name, is_main_page, is_config_page, main_index = self.get_current_page_info()

        if not current_page_name:
             # Should not happen, but handle defensively
             self.back_button.set_sensitive(False)
             self.next_button.set_sensitive(False)
             return

        # --- Back Button Logic --- 
        if is_config_page:
            self.back_button.set_sensitive(True)
            self.back_button.set_label("Cancel")
            self.back_button.set_visible(True)
        elif is_main_page:
            self.back_button.set_label("Back")
            # Can go back if not on welcome or progress page
            can_go_back = main_index > 0 and current_page_name != "progress" and current_page_name != "finished"
            self.back_button.set_sensitive(can_go_back)
            self.back_button.set_visible(current_page_name != "finished") # Hide on finished
        else:
            # Should be unreachable if pages are named correctly
            self.back_button.set_sensitive(False)
            self.back_button.set_visible(True)

        # --- Next Button Logic --- 
        can_go_next = False
        next_label = "Next"

        if is_config_page:
            # Next button on config pages usually just returns to summary
            # The real 'apply' is handled by the page's apply button
            can_go_next = True 
            next_label = "Done"
        elif is_main_page:
            if current_page_name == "welcome":
                can_go_next = True
            elif current_page_name == "summary":
                # Check if all required configs are marked complete
                all_required_done = all(self.config_state.get(key, False) for key in self.required_configs)
                # Also check if D-Bus connection to Boss is OK
                can_go_next = all_required_done and (self.boss_proxy is not None)
                next_label = "Begin Installation" if can_go_next else "Complete Required Steps"
            elif current_page_name == "progress":
                # Next button usually disabled on progress page
                can_go_next = False 
            elif current_page_name == "finished":
                can_go_next = True
                next_label = "Reboot" # Or Quit?
            else: # Should not happen
                can_go_next = False
                
        self.next_button.set_sensitive(can_go_next)
        self.next_button.set_label(next_label)
        self.next_button.set_visible(current_page_name != "progress") # Hide on progress page
        
        if is_config_page:
            # Config pages handle their own primary action via their own buttons.
            # The main 'Next' button should ideally just return to summary.
            self.next_button.set_label("Return to Summary")
            self.next_button.set_sensitive(True)
            # We could hide this button and rely only on the page's button + Cancel?
            # self.next_button.set_visible(False) 
        elif current_page_name == "welcome":
            self.next_button.set_label("Next")
            self.next_button.set_sensitive(True)
        elif current_page_name == "summary":
            self.next_button.set_label("Begin Installation")
            # Enable only if all required configurations are marked complete
            all_required_complete = all(self.config_state.get(key, False) for key in self.required_configs)
            self.next_button.set_sensitive(all_required_complete)
        elif current_page_name == "progress":
            self.next_button.set_label("Installing...")
            self.next_button.set_sensitive(False) # Cannot navigate next from progress
        elif current_page_name == "finished":
            self.next_button.set_visible(False) # No next button on finished page
        else:
             # Should be unreachable
             self.next_button.set_label("Next")
             self.next_button.set_sensitive(False) 