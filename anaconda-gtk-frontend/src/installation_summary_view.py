import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

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
        # Add rows dynamically or ensure they exist in UI
        summary_group = self.get_first_child().get_next_sibling().get_next_sibling() # Fragile
        if isinstance(summary_group, Adw.PreferencesGroup):
            if not hasattr(self, 'summary_timezone_row') or not self.summary_timezone_row:
                 self.summary_timezone_row = Adw.ActionRow(title="Timezone")
                 summary_group.add(self.summary_timezone_row)
            if not hasattr(self, 'summary_software_row') or not self.summary_software_row:
                 self.summary_software_row = Adw.ActionRow(title="Software")
                 summary_group.add(self.summary_software_row)
        else:
             print("Warning: Could not find summary group to add dynamic rows.")
        print("InstallationSummaryView initialized")

    def update_summary(self, config_data):
        """Populates the summary view based on collected configuration."""
        print("Updating summary view with:", config_data)

        if not config_data:
            print("Error: No config data provided to summary view")
            # Optionally display an error state in the UI
            return

        # Language (assuming config_data['language'] holds the ID like 'en')
        # In a real app, you'd map ID to the display name
        lang_name = config_data.get('language', 'N/A').upper()
        self.summary_lang_row.set_subtitle(lang_name)

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