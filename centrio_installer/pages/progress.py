# centrio_installer/pages/progress.py

import gi
import threading
import time
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

# Import D-Bus utils and constants
from ..utils import dbus_available, DBusError, get_dbus_proxy
from ..constants import TASK_INTERFACE # Interface for monitoring tasks

class ProgressPage(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, **kwargs)
        # Main box contains ScrolledWindow and potentially other fixed elements if needed
        self.set_vexpand(True)

        # --- Scrolled Window for Content --- 
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC) # Allow vertical scroll
        scrolled_window.set_vexpand(True)
        self.append(scrolled_window)
        
        # --- Content Box (Inside Scrolled Window) --- 
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content_box.set_margin_top(36)
        content_box.set_margin_bottom(36)
        content_box.set_margin_start(48)
        content_box.set_margin_end(48)
        # Removed valign=CENTER and vexpand=True from content_box, ScrolledWindow handles expansion
        scrolled_window.set_child(content_box)

        # Add widgets to the content_box
        title = Gtk.Label(label="Installing System")
        title.add_css_class("title-1")
        content_box.append(title)

        self.progress_bar = Gtk.ProgressBar(show_text=True, text="Preparing installation...")
        self.progress_bar.set_pulse_step(0.1)
        content_box.append(self.progress_bar)

        self.progress_label = Gtk.Label(label="")
        self.progress_label.set_wrap(True)
        self.progress_label.set_xalign(0.0) # Align text to the left
        content_box.append(self.progress_label)

        # --- State Variables --- 
        self.installation_error = None
        self.main_window = None
        self.stop_requested = False
        self.task_list = [] # List of (service, path) tuples from Boss
        self.current_task_index = -1
        self.current_task_proxy = None
        self.current_task_monitor_id = None
        self.current_task_progress = 0.0 # Progress within the current task (0.0 to 1.0)
        self.overall_progress = 0.0 # Estimated overall progress (0.0 to 1.0)

    def _update_progress(self, text, task_fraction=None):
        """Updates progress bar and label based on current task progress."""
        def update():
            self.progress_label.set_text(text)
            if task_fraction is not None:
                self.current_task_progress = max(0.0, min(task_fraction, 1.0))
            
            # Estimate overall progress based on completed tasks and current task progress
            if self.task_list:
                tasks_completed = max(0, self.current_task_index)
                num_tasks = len(self.task_list)
                # Simple linear scaling: each task contributes equally
                self.overall_progress = (tasks_completed + self.current_task_progress) / num_tasks
                self.overall_progress = max(0.0, min(self.overall_progress, 1.0))
            else:
                self.overall_progress = 0.0 # Or 1.0 if no tasks?

            self.progress_bar.set_fraction(self.overall_progress)
            self.progress_bar.set_text(f"{int(self.overall_progress * 100)}%")
            print(f"Progress Update: [Task {self.current_task_index+1}/{len(self.task_list)}] {text} (Current Task: {self.current_task_progress:.2f}, Overall: {self.overall_progress:.2f})")
        
        # Ensure UI updates happen in the main GTK thread
        GLib.idle_add(update)

    # --- D-Bus Based Installation Flow --- 

    def start_installation_dbus(self, main_window, tasks_data):
        """Start the installation process by executing D-Bus tasks sequentially."""
        self.main_window = main_window
        self.stop_requested = False
        self.installation_error = None
        self.task_list = tasks_data # Store [(service, path), ...]
        self.current_task_index = -1
        self.overall_progress = 0.0
        self.progress_bar.set_fraction(0.0)
        self._update_progress("Starting installation...")

        if not dbus_available:
             self._installation_finished(False, "D-Bus is not available. Cannot run installation tasks.")
             return
             
        if not self.task_list:
            self._installation_finished(False, "No installation tasks provided by the backend.")
            return
            
        print(f"Starting D-Bus installation with {len(self.task_list)} tasks.")
        # Start the first task
        self._run_next_task()

    def _run_next_task(self):
        """Initiates the next task in the list."""
        if self.stop_requested:
            self._installation_finished(False, "Installation stopped by user.")
            return

        self.current_task_index += 1
        self.current_task_proxy = None
        self.current_task_progress = 0.0 # Reset progress for the new task

        if self.current_task_index >= len(self.task_list):
            # All tasks completed successfully
            self._installation_finished(True, "Installation completed successfully.")
            return

        service_name, task_path = self.task_list[self.current_task_index]
        task_num = self.current_task_index + 1
        total_tasks = len(self.task_list)
        self._update_progress(f"Starting task {task_num}/{total_tasks}: {task_path}")
        
        try:
            # Get proxy for the task
            self.current_task_proxy = get_dbus_proxy(service_name, task_path, TASK_INTERFACE)
            if not self.current_task_proxy:
                raise Exception(f"Failed to get proxy for task {task_path}")

            # Connect to task signals (ProgressChanged, Finished) - Hypothetical names
            # Use dasbus proxy signal connection mechanism
            # self.current_task_proxy.ProgressChanged.connect(self._on_task_progress)
            # self.current_task_proxy.Finished.connect(self._on_task_finished)
            # print(f"Connected signals for task {task_path}")
            # TODO: Actual signal connection depends on dasbus and exact signal names/signatures.
            # For now, we will poll status instead of using signals.

            # Start the task - Assuming a Start() method
            self.current_task_proxy.Start()
            print(f"Task {task_path} started.")
            
            # Start polling task status
            if self.current_task_monitor_id: GLib.source_remove(self.current_task_monitor_id)
            self.current_task_monitor_id = GLib.timeout_add(500, self._check_current_task_status) # Poll every 500ms

        except Exception as e:
            error_msg = f"Error starting or monitoring task {task_path}: {e}"
            print(f"ERROR: {error_msg}")
            self._installation_finished(False, error_msg)

    def _check_current_task_status(self):
        """Polls the current task's status and progress."""
        if not self.current_task_proxy or self.stop_requested:
            return False # Stop polling

        try:
            # Check Status - Assuming GetStatus()
            status = self.current_task_proxy.GetStatus()
            # Check Progress - Assuming GetProgress() -> float (0.0-1.0)
            progress_frac = self.current_task_proxy.GetProgress()
            # Get Description/Message - Assuming GetDescription()
            description = self.current_task_proxy.GetDescription()
            
            self._update_progress(description or f"Executing task {self.current_task_index+1}...", progress_frac)

            if status == "FINISHED":
                print(f"Task {self.current_task_index+1} finished successfully.")
                self._run_next_task() # Start the next task
                return False # Stop polling this task
            elif status == "FAILED":
                error_msg = f"Task {self.current_task_index+1} failed."
                try: 
                    error_msg = self.current_task_proxy.GetErrorMessage() or error_msg
                except Exception: pass
                print(f"ERROR: {error_msg}")
                self._installation_finished(False, error_msg)
                return False # Stop polling
            elif status == "RUNNING" or status == "WAITING": # Continue polling if running or waiting
                 return True
            else: # Unknown status?
                 print(f"Warning: Unknown task status '{status}' for task {self.current_task_index+1}")
                 return True # Keep polling for now
                 
        except DBusError as e:
            error_msg = f"D-Bus error checking task {self.current_task_index+1} status: {e}"
            print(f"ERROR: {error_msg}")
            self._installation_finished(False, error_msg)
            return False # Stop polling
        except AttributeError as e:
            error_msg = f"Task interface method/property not found: {e}. Cannot monitor task {self.current_task_index+1}."
            print(f"ERROR: {error_msg}")
            # Treat as failure or try to proceed? For now, fail.
            self._installation_finished(False, error_msg)
            return False # Stop polling
        except Exception as e:
            error_msg = f"Unexpected error checking task {self.current_task_index+1} status: {e}"
            print(f"ERROR: {error_msg}")
            self._installation_finished(False, error_msg)
            return False # Stop polling

    # Placeholder signal handlers (replace polling if signals work)
    # def _on_task_progress(self, progress_fraction, message):
    #     """Handles ProgressChanged signal from a task."""
    #     if self.stop_requested: return
    #     print(f"Signal: Task {self.current_task_index+1} progress: {progress_fraction*100:.1f}% - {message}")
    #     self._update_progress(message, progress_fraction)
    
    # def _on_task_finished(self, success, error_message):
    #     """Handles Finished signal from a task."""
    #     if self.stop_requested: return
    #     
    #     print(f"Signal: Task {self.current_task_index+1} finished. Success: {success}, Error: '{error_message}'")
    #     # Disconnect signals for this task?
    #     # self.current_task_proxy.ProgressChanged.disconnect(...)
    #     # self.current_task_proxy.Finished.disconnect(...)
    #     self.current_task_proxy = None
    #     
    #     if success:
    #         self._run_next_task() # Start the next task
    #     else:
    #         self._installation_finished(False, error_message or f"Task {self.current_task_index+1} failed.")

    def _installation_finished(self, success, message):
        """Handles the end of the installation (success or failure)."""
        print(f"Installation finished. Success: {success}, Message: {message}")
        # Clean up polling timer if it's still active
        if self.current_task_monitor_id:
            GLib.source_remove(self.current_task_monitor_id)
            self.current_task_monitor_id = None
            
        self.current_task_proxy = None
        self.stop_requested = True # Prevent further actions
        
        # Update UI in main thread
        def finalize_ui():
            if success:
                self.overall_progress = 1.0
                self.progress_bar.set_fraction(1.0)
                self.progress_bar.set_text("Complete")
                self.progress_label.set_text(message)
                if self.main_window:
                     self.main_window.navigate_to_page("finished")
            else:
                self.installation_error = message
                # Set progress bar to 100% but red?
                self.progress_bar.set_fraction(1.0) 
                self.progress_bar.set_text("Failed")
                self.progress_bar.add_css_class("error")
                self.progress_label.set_markup(f"<span color='red'><b>Installation Failed:</b>\n{GLib.markup_escape_text(message)}</span>")
                # Do not navigate away automatically on failure? User might want logs.
                # Or navigate to a specific failure page?
                # For now, stay on progress page showing the error.

        GLib.idle_add(finalize_ui)

    def stop_installation(self):
        """Attempts to stop the currently running installation task."""
        print("Stop installation requested.")
        self.stop_requested = True
        
        if self.current_task_monitor_id:
             GLib.source_remove(self.current_task_monitor_id)
             self.current_task_monitor_id = None
             
        if self.current_task_proxy:
            print(f"Attempting to stop task {self.current_task_index + 1}...")
            try:
                # Assuming a Cancel() or Stop() method exists on the task interface
                self.current_task_proxy.Cancel() # Hypothetical
                self.show_toast("Installation stop requested.")
            except Exception as e:
                print(f"Warning: Failed to send stop signal to task: {e}")
                # Installation might continue, but UI flow should stop.
        
        # Update UI to reflect cancellation attempt
        self._installation_finished(False, "Installation stopped by user.")