import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gio', '2.0')
from gi.repository import Gtk, Adw, Gio, GLib
import json

# Anaconda DBus service constants
BOSS_BUS_NAME = 'org.fedoraproject.Anaconda.Boss'
BOSS_OBJECT_PATH = '/org/fedoraproject/Anaconda/Boss'
BOSS_INTERFACE = 'org.fedoraproject.Anaconda.Boss'

@Gtk.Template(filename='ui/installation_summary.ui')
class InstallationSummaryView(Gtk.Box):
    __gtype_name__ = 'InstallationSummaryView'

    # Template Children (specific rows to update)
    summary_lang_row = Gtk.Template.Child()
    summary_keyboard_row = Gtk.Template.Child()
    summary_destination_row = Gtk.Template.Child()
    summary_user_row = Gtk.Template.Child()
    summary_root_row = Gtk.Template.Child()
    summary_timezone_row = None # Will create this row dynamically or add to UI
    summary_software_row = None # Will create this row dynamically

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._config_data = {}
        self._boss_proxy = None
        
        # Add rows dynamically or ensure they exist in UI
        summary_group = self.get_first_child().get_next_sibling().get_next_sibling()
        if isinstance(summary_group, Adw.PreferencesGroup):
            if not hasattr(self, 'summary_timezone_row') or not self.summary_timezone_row:
                self.summary_timezone_row = Adw.ActionRow(title="Timezone")
                summary_group.add(self.summary_timezone_row)
            if not hasattr(self, 'summary_software_row') or not self.summary_software_row:
                self.summary_software_row = Adw.ActionRow(title="Software")
                summary_group.add(self.summary_software_row)
        else:
            print("Warning: Could not find summary group to add dynamic rows.")
        
        self._connect_to_anaconda()
        print("InstallationSummaryView initialized")
    
    def _connect_to_anaconda(self):
        """Connect to Anaconda's DBus service."""
        try:
            self._boss_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                BOSS_BUS_NAME,
                BOSS_OBJECT_PATH,
                BOSS_INTERFACE,
                None
            )
            print("Connected to Anaconda Boss service")
            return True
        except GLib.Error as e:
            print(f"Failed to connect to Anaconda Boss service: {e}")
            return False

    def update_summary(self, config_data):
        """Populates the summary view based on collected configuration."""
        print("Updating summary view with:", config_data)
        
        if not config_data:
            print("Error: No config data provided to summary view")
            return
        
        self._config_data = config_data.copy()
        
        # Update UI with the configuration data
        # Language
        lang_name = config_data.get('language', 'N/A')
        self.summary_lang_row.set_subtitle(lang_name.upper() if lang_name != 'N/A' else 'N/A')
        
        # Keyboard Layout
        keyboard_layout = config_data.get('keyboard_layout', 'N/A')
        self.summary_keyboard_row.set_subtitle(keyboard_layout)
        
        # Timezone
        timezone = config_data.get('timezone', 'N/A')
        if isinstance(timezone, dict):
            timezone_str = timezone.get('timezone', 'N/A')
            ntp_status = "(NTP Enabled)" if timezone.get('ntp_enabled', False) else "(NTP Disabled)"
            self.summary_timezone_row.set_subtitle(f"{timezone_str} {ntp_status}")
        else:
            self.summary_timezone_row.set_subtitle(str(timezone))
        
        # Software Selection
        software = config_data.get('software', {})
        if not software:
            self.summary_software_row.set_subtitle("No software selected")
            return
            
        if software.get('source_type') == 'kickstart':
            ks_path = software.get('kickstart_path', 'Unknown')
            ks_name = os.path.basename(ks_path) if ks_path else 'Unknown'
            self.summary_software_row.set_subtitle(f"Kickstart: {ks_name}")
        else:
            # Live image packages
            self.summary_software_row.set_subtitle("Using packages from live image")
            
        # Show Flatpak status if enabled
        if any(cmd and 'flatpak' in ' '.join(cmd) for cmd in software.get('post_install_commands', [])):
            self.summary_software_row.set_subtitle(
                f"{self.summary_software_row.get_subtitle()} • Flatpak enabled"
            )
        
        # Installation Destination
        install_disk = config_data.get('installation_disk', 'N/A')
        self.summary_destination_row.set_subtitle(install_disk)
        
        # User Account
        username = config_data.get('username', 'N/A')
        self.summary_user_row.set_subtitle(username)
        
        # Root Account
        root_setup = "Enabled" if config_data.get('set_root_password', False) else "Disabled"
        self.summary_root_row.set_subtitle(root_setup)
        
        # Software Selection
        software = config_data.get('software_selection', 'N/A')
        self.summary_software_row.set_subtitle(software)
    
    def get_installation_config(self):
        """Prepare the installation configuration for Anaconda."""
        if not self._config_data:
            return {}
        
        # Map our configuration to Anaconda's expected format
        config = {
            "Keyboard": {
                "x_layouts": [self._config_data.get('keyboard_layout', 'us')],
                "vc_keymap": self._config_data.get('keyboard_layout', 'us')
            },
            "Localization": {
                "language": self._config_data.get('language', 'en_US.UTF-8'),
                "keyboard": self._config_data.get('keyboard_layout', 'us'),
                "timezone": self._config_data.get('timezone', 'UTC')
            },
            "User": {
                "name": self._config_data.get('username', ''),
                "password": self._config_data.get('password', ''),
                "groups": ["wheel"],
                "is_admin": True
            },
            "Root": {
                "password": self._config_data.get('root_password', ''),
                "account_locked": not self._config_data.get('set_root_password', False)
            },
            "Storage": {
                "disks": [self._config_data.get('installation_disk', '')],
                "default_partitioning": True
            },
            "Payload": {
                "source_type": "CDROM",
                "base_repo": "/run/install/repo"
            }
        }
        
        # Add software selection if specified
        if 'software_selection' in self._config_data:
            config["Payload"]["packages"] = self._get_packages_for_selection(
                self._config_data['software_selection']
            )
        
        return config
    
    def _get_packages_for_selection(self, selection):
        """Map software selection to package groups."""
        # This is a simplified mapping - in a real app, you'd want more comprehensive package lists
        packages = []
        
        if selection == "GNOME Desktop":
            packages.extend(["@gnome-desktop", "gnome-terminal", "gnome-tweaks"])
        elif selection == "KDE Plasma Workspaces":
            packages.extend(["@kde-desktop", "konsole"])
        elif selection == "Xfce Desktop":
            packages.extend(["@xfce-desktop", "xfce4-terminal"])
        elif selection == "Minimal Install":
            packages.extend(["@core"])
        
        return packages
    
    def start_installation(self):
        """Start the installation with the current configuration."""
        if not self._boss_proxy:
            print("Error: Not connected to Anaconda Boss service")
            return False, "Not connected to installation service"
        
        config = self.get_installation_config()
        print("Starting installation with config:", json.dumps(config, indent=2))
        
        try:
            # Convert config to JSON string for DBus
            config_json = json.dumps(config)
            
            # Start the installation
            self._boss_proxy.call_sync(
                'StartWithConfiguration',
                GLib.Variant('(s)', (config_json,)),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            
            return True, "Installation started successfully"
            
        except GLib.Error as e:
            error_msg = f"Failed to start installation: {e.message}"
            print(error_msg)
            return False, error_msg

        # Keyboard Layout
        keyboard_layout = config_data.get('keyboard', 'N/A')
        self.summary_keyboard_row.set_subtitle(keyboard_layout)

        # Installation Destination
        dest_config = config_data.get('destination', {})
        disks = ", ".join(dest_config.get('disks', [])) or "None"
        config_mode = dest_config.get('config_mode', 'N/A')
        dest_summary = f"{disks} ({config_mode})"
        self.summary_destination_row.set_subtitle(dest_summary)

        # User Account
        user_config = config_data.get('user', {})
        username = user_config.get('username', 'N/A')
        is_admin = "Administrator" if user_config.get('is_admin', False) else "Standard User"
        user_summary = f"User '{username}', {is_admin}"
        self.summary_user_row.set_subtitle(user_summary)

        # Root Account
        root_enabled = user_config.get('root_enabled', False)
        root_summary = "Enabled" if root_enabled else "Disabled"
        self.summary_root_row.set_subtitle(root_summary)

        # Timezone (Added)
        if self.summary_timezone_row: # Check if row exists
            tz_config = config_data.get('timezone', {})
            timezone = tz_config.get('timezone', 'N/A')
            ntp = "Enabled" if tz_config.get('ntp_enabled', False) else "Disabled"
            tz_summary = f"{timezone} (NTP: {ntp})"
            self.summary_timezone_row.set_subtitle(tz_summary)

        # Software Selection (Added)
        if self.summary_software_row:
            sw_config = config_data.get('software', {})
            packages = ", ".join(sw_config.get('packages', [])) or "None"
            # In real app, map IDs like '@workstation-product-environment' to human names
            sw_summary = f"{packages} (Placeholder)"
            self.summary_software_row.set_subtitle(sw_summary)

        # TODO: Add summary for Software Selection etc. if added 