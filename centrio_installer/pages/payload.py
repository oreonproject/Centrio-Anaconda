# centrio_installer/pages/payload.py

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

# Import D-Bus utils and constants
from .base import BaseConfigurationPage, dbus_available, DBusError, get_dbus_proxy
from ..constants import PAYLOADS_SERVICE, PAYLOADS_OBJECT_PATH, PAYLOADS_INTERFACE

class PayloadPage(BaseConfigurationPage):
    """Page for Payload (Installation Source) Configuration."""
    def __init__(self, main_window, overlay_widget, **kwargs):
        super().__init__(title="Installation Source", subtitle="Configure package source", main_window=main_window, overlay_widget=overlay_widget, **kwargs)
        
        self.payloads_proxy = None
        self.available_sources = [] # List of available source types (e.g., DNF, RPM-OSTree)
        self.current_source_type = None # e.g., "dnf"
        self.initial_fetch_done = False

        # --- UI Elements --- 
        source_group = Adw.PreferencesGroup(title="Installation Source Type")
        self.add(source_group)
        
        # ComboRow for selecting source type
        self.source_row = Adw.ComboRow(title="Source Type", model=Gtk.StringList.new([]))
        source_group.add(self.source_row)
        
        # Placeholder for source-specific configuration (e.g., repo URLs)
        self.config_placeholder_group = Adw.PreferencesGroup(title="Source Configuration")
        self.config_placeholder_group.set_description("Source-specific options appear here.")
        self.config_placeholder_group.set_visible(False) # Hide initially
        self.add(self.config_placeholder_group)
        self.config_placeholder_label = Gtk.Label(label="(Configuration options not implemented)")
        self.config_placeholder_group.add(self.config_placeholder_label)

        # --- Confirmation Button --- 
        button_group = Adw.PreferencesGroup()
        self.add(button_group)
        self.complete_button = Gtk.Button(label="Apply Payload Source")
        self.complete_button.set_halign(Gtk.Align.CENTER)
        self.complete_button.set_margin_top(24)
        self.complete_button.add_css_class("suggested-action")
        self.complete_button.connect("clicked", self.apply_settings_and_return) 
        # Start insensitive
        self.complete_button.set_sensitive(False)
        self.source_row.set_sensitive(False)
        button_group.add(self.complete_button)
        
        # Connect to D-Bus
        self.connect_and_fetch_data()
            
    def connect_and_fetch_data(self):
        """Connects to Payloads D-Bus service and fetches available source types."""
        print("PayloadPage: Connecting to D-Bus...")
        if not dbus_available:
            self.show_toast("D-Bus is not available. Cannot configure payload source.")
            self._update_ui_with_sources(["DNF"], "DNF") # Fallback
            self.initial_fetch_done = True
            return
            
        self.payloads_proxy = get_dbus_proxy(PAYLOADS_SERVICE, PAYLOADS_OBJECT_PATH, PAYLOADS_INTERFACE)
        
        if self.payloads_proxy:
            print("PayloadPage: Successfully got D-Bus proxy.")
            GLib.idle_add(self._fetch_payload_data)
        else:
            self.show_toast("Failed to connect to Payloads D-Bus service.")
            self._update_ui_with_sources(["DNF"], "DNF") # Fallback
            self.initial_fetch_done = True

    def _fetch_payload_data(self):
        """Fetches available source types and the currently configured one."""
        if not self.payloads_proxy:
             return False

        available = []
        current = None
        try:
            # Fetch available sources - Assuming GetAvailableSources() -> list[str]
            available = self.payloads_proxy.GetAvailableSources()
            print(f"PayloadPage: Fetched sources via D-Bus: {available}")
            
            # Fetch current source - Assuming GetSource() -> str or None
            current = self.payloads_proxy.GetSource() # Might return object path or type name
            print(f"PayloadPage: Fetched current source via D-Bus: {current}")
            
            # TODO: Adapt based on actual return types. If GetSource returns an object path,
            # we might need to query that object for its type.
            # For now, assume GetSource returns the type string directly.
            
            if not available: available = ["DNF"] # Fallback
            if not current and available: current = available[0] # Default to first

        except DBusError as e:
            print(f"ERROR: D-Bus error fetching payload data: {e}")
            self.show_toast(f"Error fetching payload data: {e}")
            available = ["DNF"]
            current = "DNF"
        except AttributeError as e:
             print(f"ERROR: D-Bus method/property not found: {e}. Check PayloadsInterface.")
             self.show_toast(f"D-Bus call failed: {e}")
             available = ["DNF"]
             current = "DNF"
        except Exception as e:
            print(f"ERROR: Unexpected error fetching payload data: {e}")
            self.show_toast("Unexpected error fetching payload data.")
            available = ["DNF"]
            current = "DNF"
        finally:
             self._update_ui_with_sources(available, current)
             self.initial_fetch_done = True
             
        return False
        
    def _update_ui_with_sources(self, sources, current_source):
         """Updates the source ComboRow."""
         self.available_sources = sorted(sources)
         self.current_source_type = current_source
         
         model = Gtk.StringList.new(self.available_sources)
         self.source_row.set_model(model)
         
         selected_idx = -1
         if self.current_source_type and self.current_source_type in self.available_sources:
             try:
                 selected_idx = self.available_sources.index(self.current_source_type)
             except ValueError:
                 pass
                 
         if selected_idx >= 0:
             self.source_row.set_selected(selected_idx)
         elif self.available_sources:
             self.source_row.set_selected(0)
             self.current_source_type = self.available_sources[0]
             
         # Enable UI
         self.source_row.set_sensitive(bool(self.available_sources))
         self.complete_button.set_sensitive(bool(self.available_sources))
         if not self.available_sources:
              self.source_row.set_subtitle("No sources available")
         
         # TODO: Show/hide source-specific config group based on selected type
         # self.config_placeholder_group.set_visible(True/False)

    def apply_settings_and_return(self, button):
        """Applies the selected payload source via D-Bus."""
        if not self.initial_fetch_done:
            self.show_toast("Still fetching initial configuration...")
            return
            
        selected_idx = self.source_row.get_selected()
        if not self.available_sources or selected_idx < 0 or selected_idx >= len(self.available_sources):
            self.show_toast("Invalid payload source selection.")
            return
            
        selected_source = self.available_sources[selected_idx]
            
        print(f"Applying Payload Source '{selected_source}' via D-Bus...")
        self.complete_button.set_sensitive(False)
        
        if self.payloads_proxy:
            try:
                # Call SetSource method - Check actual method signature
                # It might take the type string, or require creating/getting an object path
                self.payloads_proxy.SetSource(selected_source) 
                print("Payload source successfully set via D-Bus.")
                self.show_toast(f"Payload source '{selected_source}' applied.")
                
                config_values = {"payload_type": selected_source}
                super().mark_complete_and_return(button, config_values=config_values)
                
            except DBusError as e:
                print(f"ERROR: D-Bus error setting payload source: {e}")
                self.show_toast(f"Error setting payload source: {e}")
                self.complete_button.set_sensitive(True) 
            except AttributeError as e:
                 print(f"ERROR: D-Bus method SetSource not found: {e}. Check PayloadsInterface.")
                 self.show_toast(f"Failed to apply source (D-Bus error): {e}")
                 self.complete_button.set_sensitive(True)
            except Exception as e:
                print(f"ERROR: Unexpected error applying payload source: {e}")
                self.show_toast(f"Unexpected error setting payload source: {e}")
                self.complete_button.set_sensitive(True) 
        else:
            self.show_toast("Cannot apply source: D-Bus connection not available.")
            # Mark complete anyway?
            print("Marking complete with chosen source despite D-Bus failure.")
            config_values = {"payload_type": selected_source}
            super().mark_complete_and_return(button, config_values=config_values) 