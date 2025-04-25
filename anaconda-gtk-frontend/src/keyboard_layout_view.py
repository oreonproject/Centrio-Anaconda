import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
import subprocess
import locale


@Gtk.Template(filename='ui/keyboard_layout.ui')
class KeyboardLayoutView(Gtk.Box):
    __gtype_name__ = 'KeyboardLayoutView'

    # Template children
    search_entry = Gtk.Template.Child()
    layout_list_box = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_layout = None
        self._all_layouts = []
        self.populate_layouts()
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.layout_list_box.connect("row-selected", self.on_row_selected)
        print("KeyboardLayoutView initialized and populated")

    def get_available_layouts(self):
        """Fetches available X11 keyboard layouts using localectl."""
        try:
            # Run localectl command
            result = subprocess.run(["localectl", "list-x11-keymap-layouts"], 
                                    capture_output=True, text=True, check=True)
            layouts = result.stdout.strip().split('\n')
            # Use locale to sort layouts based on the current language if possible
            try:
                locale.setlocale(locale.LC_COLLATE, '')
            except locale.Error:
                pass # Keep default C locale if setting fails
            layouts.sort(key=locale.strxfrm)
            print(f"Found {len(layouts)} layouts.")
            return layouts
        except FileNotFoundError:
            print("Error: 'localectl' command not found. Returning default list.")
            return ["us", "gb", "de", "fr"] # Fallback
        except subprocess.CalledProcessError as e:
            print(f"Error running localectl: {e}")
            return ["us", "gb", "de", "fr"] # Fallback

    def populate_layouts(self):
        """Populates the list box with available layouts."""
        self._all_layouts = self.get_available_layouts()
        self.update_list_filter(None) # Show all initially

    def update_list_filter(self, search_term):
        """Filters the list box based on the search term."""
        # Clear existing rows before adding filtered ones
        child = self.layout_list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.layout_list_box.remove(child)
            child = next_child

        # Add rows that match the search term (case-insensitive)
        term = search_term.lower() if search_term else None
        for layout in self._all_layouts:
            if term is None or term in layout.lower():
                row = Gtk.Label(label=layout, xalign=0) # Align text left
                self.layout_list_box.append(row)
        
        # Select the first item if list is not empty and something was selected previously or nothing was
        if self.selected_layout and any(c.get_label() == self.selected_layout for c in self.get_list_rows()):
             self.select_layout_in_list(self.selected_layout)
        elif not self.selected_layout and self.layout_list_box.get_first_child():
             self.layout_list_box.select_row(self.layout_list_box.get_row_at_index(0))

    def on_search_changed(self, entry):
        """Called when the search text changes."""
        search_term = entry.get_text()
        self.update_list_filter(search_term)

    def on_row_selected(self, list_box, row):
        """Called when a layout is selected in the list."""
        if row:
            self.selected_layout = row.get_child().get_label()
            print(f"Selected layout: {self.selected_layout}")
        else:
            self.selected_layout = None
            print("Layout deselected")
            
    def get_list_rows(self):
        """Helper to get all GtkLabel children from the listbox rows."""
        rows = []
        child = self.layout_list_box.get_first_child()
        while child:
            if isinstance(child, Gtk.ListBoxRow) and isinstance(child.get_child(), Gtk.Label):
                 rows.append(child.get_child())
            child = child.get_next_sibling()
        return rows

    def select_layout_in_list(self, layout_name):
        """Programmatically selects a layout in the list."""
        child = self.layout_list_box.get_first_child()
        while child:
            if isinstance(child, Gtk.ListBoxRow) and isinstance(child.get_child(), Gtk.Label):
                if child.get_child().get_label() == layout_name:
                    self.layout_list_box.select_row(child)
                    break
            child = child.get_next_sibling()

    def get_selected_layout(self):
        """Returns the currently selected layout name."""
        return self.selected_layout 