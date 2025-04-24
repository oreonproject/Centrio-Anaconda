# centrio_installer/pages/disk.py

import gi
# Remove subprocess, json, shlex, os, re imports as D-Bus handles this
# import subprocess
# import json
# import shlex
# import os
# import re
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

# Import D-Bus utils and constants
from .base import BaseConfigurationPage, dbus_available, DBusError, get_dbus_proxy
from ..constants import (STORAGE_SERVICE, STORAGE_OBJECT_PATH, STORAGE_INTERFACE, 
                       TASK_INTERFACE) # Added TASK_INTERFACE

# Helper function to format size
def format_bytes(size_bytes):
    if size_bytes is None:
        return "N/A"
    # Simple GB conversion for display
    gb = size_bytes / (1024**3)
    if gb < 0.1:
        mb = size_bytes / (1024**2)
        return f"{mb:.1f} MiB"
    return f"{gb:.1f} GiB"

# Remove partitioning command generation functions
# def generate_wipefs_command(...):
# def generate_gpt_commands(...):
# def generate_mkfs_commands(...):

# Remove host usage check functions
# def get_host_mounts():
# def get_host_lvm_pvs():

class DiskPage(BaseConfigurationPage):
    def __init__(self, main_window, overlay_widget, **kwargs):
        super().__init__(title="Installation Destination", subtitle="Select disks and configure partitioning", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.storage_proxy = None
        self.scan_task_proxy = None
        self.scan_timer_id = None
        self.device_tree_proxy = None # For getting device details
        
        # State variables
        self.detected_disks = [] # List of dicts {name, path, size, model, type}
        self.selected_disks = set()
        self.scan_in_progress = False
        self.scan_completed_successfully = False
        self.partitioning_method = None # "AUTOMATIC" or "MANUAL" or None
        self.disk_widgets = {} # Map path to row/check widgets
        
        # --- UI Setup --- 
        info_group = Adw.PreferencesGroup()
        self.add(info_group)
        self.info_label = Gtk.Label(label="Connect to storage service to detect devices.") # Updated text
        self.info_label.set_margin_top(12)
        self.info_label.set_margin_bottom(12)
        self.info_label.set_wrap(True) 
        info_group.add(self.info_label)
        
        scan_button_group = Adw.PreferencesGroup()
        self.add(scan_button_group)
        self.scan_button = Gtk.Button(label="Scan for Disks")
        self.scan_button.set_halign(Gtk.Align.CENTER)
        self.scan_button.connect("clicked", self.start_device_scan) # Connect to D-Bus scan
        # Initially insensitive until D-Bus is connected
        self.scan_button.set_sensitive(False)
        scan_button_group.add(self.scan_button)

        # Progress Bar for scan
        self.scan_progress_bar = Gtk.ProgressBar()
        self.scan_progress_bar.set_visible(False)
        self.scan_progress_bar.set_margin_top(6)
        scan_button_group.add(self.scan_progress_bar)

        # --- Disk List (Populated after scan) ---
        self.disk_list_group = Adw.PreferencesGroup(title="Detected Disks")
        self.disk_list_group.set_description("Select the disk(s) for installation.")
        self.disk_list_group.set_visible(False)
        self.add(self.disk_list_group)
        self.disk_list_box = Gtk.ListBox()
        self.disk_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.disk_list_box.set_visible(False)
        self.disk_list_group.add(self.disk_list_box)

        # --- Partitioning Options --- 
        self.part_group = Adw.PreferencesGroup(title="Storage Configuration")
        self.part_group.set_description("Choose a partitioning method.")
        self.part_group.set_visible(False)
        self.add(self.part_group)
        
        self.auto_part_check = Gtk.CheckButton(label="Automatic Partitioning")
        self.auto_part_check.set_tooltip_text("Use selected disk(s) with a default layout")
        self.manual_part_check = Gtk.CheckButton(label="Manual Partitioning (Not Implemented)", group=self.auto_part_check)
        self.manual_part_check.set_sensitive(False)
        self.auto_part_check.connect("toggled", self.on_partitioning_method_toggled)
        
        part_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        part_box.append(self.auto_part_check)
        part_box.append(self.manual_part_check)
        self.part_group.add(part_box)

        # --- Confirmation Button --- 
        button_group = Adw.PreferencesGroup()
        self.add(button_group)
        self.complete_button = Gtk.Button(label="Confirm Storage Plan") 
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        self.complete_button.connect("clicked", self.apply_settings_and_return) 
        self.complete_button.set_sensitive(False)
        button_group.add(self.complete_button)

        # --- Connect to D-Bus --- 
        self.connect_and_fetch_data()

    # Remove find_physical_disk_for_path - D-Bus should provide clearer device info
    # def find_physical_disk_for_path(...):

    def connect_and_fetch_data(self):
        """Connects to Storage D-Bus service."""
        print("DiskPage: Connecting to D-Bus...")
        if not dbus_available:
            self.show_toast("D-Bus is not available. Cannot manage storage.")
            self.info_label.set_text("D-Bus connection failed. Cannot scan for disks.")
            return
            
        self.storage_proxy = get_dbus_proxy(STORAGE_SERVICE, STORAGE_OBJECT_PATH, STORAGE_INTERFACE)
        
        if self.storage_proxy:
            print("DiskPage: Successfully got Storage D-Bus proxy.")
            self.info_label.set_text("Click \"Scan for Disks\" to detect storage devices.")
            self.scan_button.set_sensitive(True)
            # Optionally, try to get DeviceTree proxy here too
            # device_tree_path = self.storage_proxy.GetDeviceTree()? # Example method
            # if device_tree_path:
            #    self.device_tree_proxy = get_dbus_proxy(STORAGE_SERVICE, device_tree_path, DEVICE_TREE_INTERFACE) # Need constants
        else:
            self.show_toast("Failed to connect to Storage D-Bus service.")
            self.info_label.set_text("Failed to connect to Storage service. Cannot scan for disks.")

    def start_device_scan(self, button):
        """Initiates device scanning via Storage D-Bus interface."""
        if not self.storage_proxy or self.scan_in_progress:
            return

        print("DiskPage: Starting device scan via D-Bus...")
        self.scan_in_progress = True
        self.scan_button.set_sensitive(False)
        self.info_label.set_text("Scanning storage devices...")
        self.scan_progress_bar.set_visible(True)
        self.scan_progress_bar.pulse() # Use pulse for indeterminate task
        self.disk_list_group.set_visible(False) # Hide old list
        self.part_group.set_visible(False)
        self.complete_button.set_sensitive(False)
        self.detected_disks = [] # Clear previous results
        self.selected_disks = set()
        self.disk_widgets = {}

        try:
            # Call the ScanDevicesWithTask method
            scan_task_path = self.storage_proxy.ScanDevicesWithTask()
            print(f"  Scan task path: {scan_task_path}")
            
            # Get a proxy for the task object
            self.scan_task_proxy = get_dbus_proxy(STORAGE_SERVICE, scan_task_path, TASK_INTERFACE)
            
            if self.scan_task_proxy:
                # Monitor the task completion (could use signals if available)
                # For simplicity, poll the status using a timer
                self.scan_timer_id = GLib.timeout_add(500, self._check_scan_task_status) # Poll every 500ms
            else:
                raise Exception("Failed to get proxy for scan task.")
                
        except DBusError as e:
            print(f"ERROR: D-Bus error starting scan: {e}")
            self.show_toast(f"Error starting disk scan: {e}")
            self._scan_finished(success=False)
        except AttributeError as e:
             print(f"ERROR: D-Bus ScanDevicesWithTask method not found: {e}")
             self.show_toast("Failed to start scan (D-Bus error).")
             self._scan_finished(success=False)
        except Exception as e:
            print(f"ERROR: Unexpected error starting scan: {e}")
            self.show_toast("Unexpected error starting disk scan.")
            self._scan_finished(success=False)

    def _check_scan_task_status(self):
        """Called by timer to check the scan task status."""
        if not self.scan_task_proxy:
            return False # Stop timer

        try:
            # Check task status - Assuming methods like GetStatus() or IsFinished()
            status = self.scan_task_proxy.GetStatus() # Example method
            print(f"  Scan task status: {status}")
            
            # Assuming status is a string like "RUNNING", "FINISHED", "FAILED"
            if status == "FINISHED":
                print("  Scan task finished successfully.")
                # Get results if needed (task might return device list or signal completion)
                self._scan_finished(success=True)
                return False # Stop timer
            elif status == "FAILED":
                 print("ERROR: Scan task failed.")
                 # Get error message if possible
                 error_msg = "Scan task failed."
                 try: 
                     error_msg = self.scan_task_proxy.GetErrorMessage() # Example
                 except Exception: pass
                 self.show_toast(f"Disk scan failed: {error_msg}")
                 self._scan_finished(success=False)
                 return False # Stop timer
            elif status == "RUNNING":
                 # Continue pulsing progress bar
                 self.scan_progress_bar.pulse()
                 return True # Continue timer
            else: # Unknown status
                 print(f"Warning: Unknown scan task status: {status}")
                 return True # Continue timer for now
                 
        except DBusError as e:
            print(f"ERROR: D-Bus error checking scan task status: {e}")
            self.show_toast("Error monitoring disk scan task.")
            self._scan_finished(success=False)
            return False # Stop timer
        except Exception as e:
            print(f"ERROR: Unexpected error checking scan task status: {e}")
            self._scan_finished(success=False)
            return False # Stop timer

    def _scan_finished(self, success):
        """Handles UI updates when the scan task completes (or fails)."""
        print(f"Scan finished. Success: {success}")
        self.scan_in_progress = False
        self.scan_task_proxy = None
        if self.scan_timer_id:
            GLib.source_remove(self.scan_timer_id)
            self.scan_timer_id = None
            
        self.scan_progress_bar.set_visible(False)
        self.scan_button.set_sensitive(True)

        if success:
            self.scan_completed_successfully = True
            # Fetch device details now that scan is done
            GLib.idle_add(self._fetch_device_details)
        else:
            self.scan_completed_successfully = False
            self.info_label.set_text("Disk scan failed. Click \"Scan for Disks\" to try again.")
            self.disk_list_group.set_visible(False)
            self.part_group.set_visible(False)
            self.complete_button.set_sensitive(False)
            
    def _fetch_device_details(self):
        """Fetches device details from the Storage/DeviceTree interface after scan."""
        print("Fetching device details from storage service...")
        if not self.storage_proxy:
             self.info_label.set_text("Storage service connection lost.")
             return False
             
        try:
             # How to get details? Anaconda has complex structures (blivet/DeviceTree).
             # Option 1: Get a DeviceTree proxy and query it.
             # Option 2: Call a specific method on StorageInterface that returns a list of disks.
             # Assume Option 2: A method GetAvailableDisks() returning list of structs/dicts.
             # The actual method and return structure needs verification from Anaconda source.
             # Example structure: [{'path': '/dev/sda', 'model': '...', 'size': ..., 'type': 'disk', ...}]
             raw_disks = self.storage_proxy.GetAvailableDisks() # ** Hypothetical Method **
             
             self.detected_disks = []
             for disk_data in raw_disks:
                 # Filter for actual disks (type=='disk') and maybe size > 0
                 if isinstance(disk_data, dict) and disk_data.get('type') == 'disk' and disk_data.get('size', 0) > 0:
                      self.detected_disks.append(disk_data)
                 # TODO: Add filtering for mounted/LVM devices based on D-Bus properties
                 # (e.g., IsMounted, IsLVM_PV attributes on the device data)
                 
             print(f"Filtered Disks: {self.detected_disks}")
             
             if not self.detected_disks:
                  self.info_label.set_text("Scan complete, but no suitable installation disks found.")
                  self.show_toast("No suitable disks found for installation.")
             else:
                  self.info_label.set_text("Scan complete. Select disks below.")
                  self.update_disk_list_ui()
                  self.disk_list_group.set_visible(True)
                  self.disk_list_box.set_visible(True)
                  self.part_group.set_visible(True)
                  # Reset partitioning method choice
                  self.auto_part_check.set_active(False)
                  self.manual_part_check.set_active(False)
                  self.partitioning_method = None

        except DBusError as e:
            print(f"ERROR: D-Bus error fetching device details: {e}")
            self.show_toast(f"Error fetching disk details: {e}")
            self.info_label.set_text("Error fetching disk details after scan.")
        except AttributeError as e:
            print(f"ERROR: D-Bus method GetAvailableDisks not found: {e}. Check StorageInterface.")
            self.show_toast("Failed to get disk list (D-Bus error).")
            self.info_label.set_text("Could not retrieve disk list from storage service.")
        except Exception as e:
            print(f"ERROR: Unexpected error fetching device details: {e}")
            self.show_toast("Unexpected error fetching disk details.")
            self.info_label.set_text("Unexpected error fetching disk details.")
            
        return False # Stop idle_add

    def update_disk_list_ui(self):
        """Populates the ListBox with detected disks."""
        # Clear previous rows
        widget = self.disk_list_box.get_first_child()
        while widget:
            next_widget = widget.get_next_sibling()
            self.disk_list_box.remove(widget)
            widget = next_widget
        self.disk_widgets = {}
        
        if not self.detected_disks:
             # Add a placeholder row? Handled by info_label currently.
             pass
             
        for disk in self.detected_disks:
            path = disk.get('path', 'N/A')
            model = disk.get('model', 'Unknown Model')
            size_bytes = disk.get('size')
            size_str = format_bytes(size_bytes)
            # is_mounted = disk.get('is_mounted', False) # Need to check if D-Bus provides this
            # is_lvm_pv = disk.get('is_lvm_pv', False)
            is_mounted = False # Placeholder
            is_lvm_pv = False # Placeholder

            row = Adw.ActionRow(title=f"{path} ({size_str})")
            row.set_subtitle(model)
            
            check_button = Gtk.CheckButton()
            check_button.set_valign(Gtk.Align.CENTER)
            # Disable checkbox if disk appears to be in use by the host
            if is_mounted or is_lvm_pv:
                 row.set_subtitle(f"{model} (In use by host - cannot select)")
                 check_button.set_sensitive(False)
                 check_button.set_tooltip_text("This disk appears to contain mounted filesystems or LVM data used by the host system and cannot be used for installation.")
            else:
                 check_button.connect("toggled", self.on_disk_toggled, path)
                 
            row.add_prefix(check_button)
            row.set_activatable_widget(check_button)
            self.disk_list_box.append(row)
            self.disk_widgets[path] = {"row": row, "check": check_button}

    def on_disk_toggled(self, check_button, disk_path):
        """Handles disk selection changes."""
        if check_button.get_active():
            self.selected_disks.add(disk_path)
            print(f"Disk selected: {disk_path}")
        else:
            self.selected_disks.discard(disk_path)
            print(f"Disk deselected: {disk_path}")
        self.update_complete_button_state()

    def on_partitioning_method_toggled(self, button):
        """Handles partitioning method selection."""
        if self.auto_part_check.get_active():
            self.partitioning_method = "AUTOMATIC"
            print("Partitioning method: AUTOMATIC")
        elif self.manual_part_check.get_active():
            self.partitioning_method = "MANUAL" # Not fully supported yet
            print("Partitioning method: MANUAL (Not Implemented)")
        else:
             # Should not happen with radio buttons, but handle anyway
             self.partitioning_method = None
             print("Partitioning method: None")
        self.update_complete_button_state()

    def update_complete_button_state(self):
        """Enables the confirm button if prerequisites are met."""
        # Need scan completed, at least one disk selected, and a partitioning method chosen
        can_complete = (self.scan_completed_successfully and 
                        len(self.selected_disks) > 0 and 
                        self.partitioning_method is not None)
        self.complete_button.set_sensitive(can_complete)

    def apply_settings_and_return(self, button):
        """Confirms the storage plan and passes it back via D-Bus (initiates partitioning)."""
        if not self.scan_completed_successfully or len(self.selected_disks) == 0 or self.partitioning_method is None:
            self.show_toast("Please complete disk scan, select disk(s), and choose partitioning method.")
            return

        print("--- Confirming Storage Plan ---")
        print(f"  Method: {self.partitioning_method}")
        print(f"  Target Disks: {list(self.selected_disks)}")
        
        # TODO: Add warning dialog about data loss
        # dialog = Adw.MessageDialog(...) etc.
        # if dialog.run() != Gtk.ResponseType.ACCEPT:
        #    return
            
        self.complete_button.set_sensitive(False) # Disable during D-Bus call
        
        if self.storage_proxy:
            try:
                if self.partitioning_method == "AUTOMATIC":
                    # Create Automatic Partitioning via D-Bus
                    # Call CreatePartitioning with "AUTOMATIC"
                    # This likely returns a path to a partitioning object
                    print(f"Initiating AUTOMATIC partitioning via D-Bus for disks: {list(self.selected_disks)}...")
                    partitioning_obj_path = self.storage_proxy.CreatePartitioning("AUTOMATIC")
                    print(f"  Created partitioning object path: {partitioning_obj_path}")
                    
                    # Get proxy for the partitioning object (if needed to configure targets)
                    # The interface might be specific (e.g., AutomaticPartitioningInterface)
                    # auto_part_proxy = get_dbus_proxy(STORAGE_SERVICE, partitioning_obj_path, "org.fedoraproject.Anaconda.Modules.Storage.AutomaticPartitioningInterface")
                    # if auto_part_proxy:
                    #     auto_part_proxy.SetTargetDisks(list(self.selected_disks)) # Hypothetical method
                    # else: 
                    #     raise Exception("Failed to get auto partitioning proxy")
                        
                    # Apply the partitioning
                    # This might be asynchronous (return a task) or synchronous
                    print(f"Applying partitioning object: {partitioning_obj_path}")
                    self.storage_proxy.ApplyPartitioning(partitioning_obj_path)
                    print("  ApplyPartitioning called.")
                    
                    # TODO: Monitor the ApplyPartitioning task if it's async.
                    # How to know if ApplyPartitioning succeeded? Check properties? Signals?
                    # Assuming ApplyPartitioning is synchronous or we don't monitor yet.

                    # Prepare config values for main window (just the method and disks?)
                    config_values = {
                        "method": self.partitioning_method,
                        "target_disks": list(self.selected_disks),
                        "partitioning_object": partitioning_obj_path # Store reference
                    }
                    self.show_toast("Automatic partitioning plan applied.")
                    super().mark_complete_and_return(button, config_values=config_values)
                    
                elif self.partitioning_method == "MANUAL":
                     # Manual partitioning logic via D-Bus would go here (complex)
                     # Would involve CreatePartitioning("MANUAL"), getting proxy,
                     # calling methods like CreatePartition, SetMountpoint, etc.
                     # then ApplyPartitioning.
                     self.show_toast("Manual partitioning via D-Bus is not implemented.")
                     self.complete_button.set_sensitive(True) # Re-enable button
                     return
                else:
                     # Should not happen
                     self.show_toast("Invalid partitioning method selected.")
                     self.complete_button.set_sensitive(True)
                     return

            except DBusError as e:
                print(f"ERROR: D-Bus error applying storage plan: {e}")
                self.show_toast(f"Error applying storage plan: {e}")
                self.complete_button.set_sensitive(True)
            except AttributeError as e:
                 print(f"ERROR: D-Bus method not found: {e}. Check StorageInterface.")
                 self.show_toast(f"Failed to apply storage plan (D-Bus error): {e}")
                 self.complete_button.set_sensitive(True)
            except Exception as e:
                print(f"ERROR: Unexpected error applying storage plan: {e}")
                self.show_toast(f"Unexpected error applying storage plan: {e}")
                self.complete_button.set_sensitive(True)
        else:
            self.show_toast("Cannot apply storage plan: D-Bus connection not available.")
            # Mark complete anyway?
            print("Marking complete with chosen storage plan despite D-Bus failure.")
            config_values = {
                "method": self.partitioning_method,
                "target_disks": list(self.selected_disks),
                "partitioning_object": "(not applied)"
            }
            super().mark_complete_and_return(button, config_values=config_values) 