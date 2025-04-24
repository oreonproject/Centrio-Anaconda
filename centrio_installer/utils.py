# centrio_installer/utils.py
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio # Added Gio for file operations

import os
import re
import subprocess

# Attempt D-Bus import
try:
    # Use dasbus
    import dasbus.connection
    from dasbus.error import DBusError
    dbus_available = True
except ImportError:
    dasbus = None
    DBusError = Exception # Placeholder
    dbus_available = False
    print("WARNING: dasbus library not found. D-Bus communication will be disabled.")

# --- Timezone Helpers (Simulated from pyanaconda.timezone) ---
# In a real integration, import these from pyanaconda.timezone
# For now, provide dummy implementations

def ana_get_keyboard_layouts():
    """Fetches available console keyboard layouts using localectl."""
    print("Fetching keyboard layouts using localectl...")
    layouts = []
    try:
        # Use localectl list-keymaps
        result = subprocess.run(['localectl', 'list-keymaps'], capture_output=True, text=True, check=True)
        layouts = result.stdout.strip().split('\n')
        print(f"Found {len(layouts)} keyboard layouts.")
    except FileNotFoundError:
        print("ERROR: 'localectl' command not found. Cannot list keymaps.")
        # Provide minimal fallback data
        layouts = ['us', 'uk', 'de', 'fr', 'es']
        print("Using fallback keyboard layout data.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: 'localectl list-keymaps' failed: {e}")
        # Provide minimal fallback data
        layouts = ['us', 'uk', 'de', 'fr', 'es']
        print("Using fallback keyboard layout data.")
    return layouts

def ana_get_available_locales():
    """Fetches available locales using localectl."""
    print("Fetching available locales using localectl...")
    locales = {}
    try:
        result = subprocess.run(["localectl", "list-locales"], 
                                capture_output=True, text=True, check=True)
        raw_locales = [line.strip() for line in result.stdout.split('\n') if line and '.' in line]
        # Attempt to generate a display name (basic)
        for locale_code in raw_locales:
             # Simple conversion for display: en_US.UTF-8 -> English (US) UTF-8
             parts = locale_code.split('.')[0].split('_')
             lang = parts[0]
             country = f"({parts[1]})" if len(parts) > 1 else ""
             # This name generation is very basic, ideally use a locale library
             display_name = f"{lang.capitalize()} {country}".strip()
             # Use code as key, display name as value (or vice-versa if needed by UI)
             locales[locale_code] = display_name 
             
        print(f"  Found {len(locales)} locales.")
        # Sort by display name for UI
        sorted_locales = dict(sorted(locales.items(), key=lambda item: item[1]))
        return sorted_locales if sorted_locales else {"en_US.UTF-8": "English (US)"} # Fallback
        
    except FileNotFoundError:
        print("ERROR: localectl command not found. Using fallback locales.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: localectl list-locales failed: {e}. Using fallback locales.")
    except Exception as e:
        print(f"ERROR: Unexpected error fetching locales: {e}. Using fallback locales.")
        
    # Fallback list if errors occurred
    return {
        "en_US.UTF-8": "English (US)",
        "es_ES.UTF-8": "Spanish (Spain)",
        "fr_FR.UTF-8": "French (France)",
        "de_DE.UTF-8": "German (Germany)"
    } 

from .constants import APP_ID, ANACONDA_BUS_ADDR_FILE, DBUS_ANACONDA_SESSION_ADDRESS # Import constants

def get_os_release_info(target_root=None):
    """Parses /etc/os-release (or /usr/lib/os-release) to get NAME and VERSION_ID.
    If target_root is provided, reads from within that root.
    """
    info = {"NAME": "Linux", "VERSION_ID": None, "ID": None} # Defaults
    release_file_path = None
    base_path = target_root if target_root else "/"
    
    # Check standard locations relative to base_path
    etc_path = os.path.join(base_path, "etc/os-release")
    usr_lib_path = os.path.join(base_path, "usr/lib/os-release")
    
    if os.path.exists(etc_path):
        release_file_path = etc_path
    elif os.path.exists(usr_lib_path):
        release_file_path = usr_lib_path
    
    if release_file_path:
        try:
            with open(release_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes from value if present
                        value = value.strip('"\'') 
                        # Store common keys
                        if key in ["NAME", "VERSION_ID", "ID"]:
                            info[key] = value
        except Exception as e:
            print(f"Warning: Failed to parse {release_file_path}: {e}")
            
    return info

# --- D-Bus Helper Functions ---
_anaconda_bus = None # Cache the bus connection

def get_anaconda_bus():
    """Gets a connection to the Anaconda D-Bus session bus.
    
    Assumes DBUS_SESSION_BUS_ADDRESS is set correctly externally
    (e.g., by dbus-launch).
    Caches the connection for reuse.
    Returns None if dasbus is not available or connection fails.
    """
    global _anaconda_bus
    if not dbus_available:
        print("D-Bus connection requested, but dasbus is not available.")
        return None
        
    if _anaconda_bus is None:
        try:
            print(f"Connecting to session D-Bus (expecting DBUS_SESSION_BUS_ADDRESS)...")
            _anaconda_bus = dasbus.connection.SessionMessageBus()
            print("Successfully connected to session D-Bus (connection object created).")
        except DBusError as e:
            print(f"ERROR: Failed to connect to session D-Bus: {e}")
            _anaconda_bus = None
        except KeyError as e:
             # This likely means DBUS_SESSION_BUS_ADDRESS wasn't set
             print(f"ERROR: Failed to connect to session D-Bus - Environment variable likely missing: {e}")
             _anaconda_bus = None
        except Exception as e:
            print(f"ERROR: Unexpected error connecting to session D-Bus: {e}")
            _anaconda_bus = None

    return _anaconda_bus

def get_dbus_proxy(service_name, object_path, interface_name):
    """Gets a dasbus proxy object for a given service/path/interface.
    
    Returns None if connection fails or proxy cannot be created.
    """
    bus = get_anaconda_bus()
    if not bus:
        return None
        
    try:
        # Create a proxy object
        proxy = bus.get_proxy(service_name, object_path)
        # You might need to explicitly select the interface if methods clash,
        # but often dasbus handles this. If needed:
        # return proxy[interface_name] 
        return proxy
    except DBusError as e:
        print(f"ERROR: Failed to get D-Bus proxy for {service_name} at {object_path}: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error getting D-Bus proxy: {e}")
        return None

# Constants
# ANACONDA_BUS_NAME = "org.fedoraproject.Anaconda.Boss"
# ANACONDA_OBJECT_PATH = "/org/fedoraproject/Anaconda/Boss" 