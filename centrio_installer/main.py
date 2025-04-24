#!/usr/bin/env python3

# centrio_installer/main.py

import sys
import os
import subprocess
import signal
import gi
import logging # Import logging
import atexit # For cleanup
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, GLib

# Import the main window and constants
from .window import CentrioInstallerWindow
from .constants import APP_ID

# --- Setup Logging ---
log_format = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)
# You could also log to a file:
# logging.basicConfig(filename='/tmp/centrio-installer.log', filemode='w', level=logging.DEBUG, format=log_format)

# --- Global Process Management --- 
_dbus_daemon_proc = None
_anaconda_boss_proc = None
_process_pids = [] # Store PIDs for cleanup

def cleanup_processes():
    """Terminate launched background processes on exit."""
    logging.info("Cleaning up launched processes...")
    global _dbus_daemon_proc, _anaconda_boss_proc, _process_pids
    
    # Terminate Anaconda Boss first (if running)
    if _anaconda_boss_proc and _anaconda_boss_proc.poll() is None:
        logging.info(f"Terminating Anaconda Boss (PID: {_anaconda_boss_proc.pid})...")
        _anaconda_boss_proc.terminate()
        try:
            _anaconda_boss_proc.wait(timeout=5)
            logging.info("Anaconda Boss terminated.")
        except subprocess.TimeoutExpired:
            logging.warning("Timeout waiting for Anaconda Boss termination, killing...")
            _anaconda_boss_proc.kill()
            
    # Terminate D-Bus daemon (if running)
    if _dbus_daemon_proc and _dbus_daemon_proc.poll() is None:
        logging.info(f"Terminating D-Bus daemon (PID: {_dbus_daemon_proc.pid})...")
        _dbus_daemon_proc.terminate()
        try:
            _dbus_daemon_proc.wait(timeout=5)
            logging.info("D-Bus daemon terminated.")
        except subprocess.TimeoutExpired:
            logging.warning("Timeout waiting for D-Bus daemon termination, killing...")
            _dbus_daemon_proc.kill()
            
    # Ensure any other tracked PIDs are killed (e.g., from dbus-launch)
    for pid in _process_pids:
        try:
             if os.kill(pid, 0): # Check if PID exists
                 logging.info(f"Sending SIGTERM to process PID: {pid}")
                 os.kill(pid, signal.SIGTERM)
                 # Optionally wait briefly or send SIGKILL after timeout
        except OSError as e:
             # Process likely already exited
             logging.debug(f"Could not signal PID {pid} (may have already exited): {e}")
        except Exception as e:
             logging.error(f"Error terminating process PID {pid}: {e}")

atexit.register(cleanup_processes) # Register cleanup function

# --- Restore D-Bus Config Creation (pointing to correct system path) ---

def create_dbus_config():
    """Creates the /tmp/centrio_dbus.conf file needed by the custom dbus-daemon."""
    config_file_path = "/tmp/centrio_dbus.conf"
    # Path identified by dnf provides
    service_dir = "/usr/share/anaconda/dbus/services"
    
    # Check if the Anaconda D-Bus service directory exists 
    if not os.path.isdir(service_dir):
        logging.warning(f"Anaconda D-Bus service directory not found: {service_dir}. D-Bus services might not load correctly.")
        # We should probably fail here if the dir is missing
        return False
        
    config_content = f"""<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <keep_umask/>
  <!-- Listen on a socket in /tmp for simplicity -->
  <listen>unix:tmpdir=/tmp</listen> 
  <!-- Point to Anaconda's actual D-Bus service file directory -->
  <servicedir>{service_dir}</servicedir> 
  <!-- Include standard session service directories too -->
  <standard_session_servicedirs/> 
  <!-- Basic policy allowing local connections -->
  <policy context="default">
    <allow send_destination="*" eavesdrop="false"/> 
    <allow eavesdrop="false"/> <!-- Be restrictive on eavesdropping -->
    <allow own="*"/>
    <allow user="*"/> 
  </policy>
</busconfig>
"""
    
    try:
        # Ensure we remove the old file if it exists (needed when running as diff users)
        if os.path.exists(config_file_path):
            os.remove(config_file_path)
        with open(config_file_path, "w") as f:
            f.write(config_content)
        logging.info(f"Successfully created D-Bus config file: {config_file_path} pointing to service dir: {service_dir}")
        return True
    except (IOError, OSError) as e:
        logging.critical(f"Failed to write D-Bus config file {config_file_path}: {e}", exc_info=True)
        return False
    except Exception as e:
        logging.critical(f"Unexpected error creating D-Bus config file {config_file_path}: {e}", exc_info=True)
        return False

# --- End D-Bus Config Creation ---

class CentrioInstallerApp(Adw.Application):
    """The main GTK application class."""
    def __init__(self, **kwargs):
        super().__init__(application_id=APP_ID, **kwargs)
        self.connect('activate', self.on_activate)
        self.win = None

    def on_activate(self, app):
        """Called when the application is activated."""
        if not self.win:
             # Create the main window
             self.win = CentrioInstallerWindow(application=app)
        self.win.present()

    def do_shutdown(self):
        """Called when the application is shutting down."""
        logging.info("Application shutdown requested.")
        # Custom cleanup can go here if needed before atexit handler
        Adw.Application.do_shutdown(self)

# --- Restore D-Bus Daemon Launch (without PATH/PYTHONPATH mods) ---
def launch_dbus_daemon():
    """Starts a dbus-daemon using a custom config file, captures its address/PID, and sets environment."""
    global _process_pids
    logging.info("Attempting to launch D-Bus daemon with custom config...")
    config_file = "/tmp/centrio_dbus.conf" # Path to the file we just created
    
    # Ensure the config file exists (create_dbus_config should have made it)
    if not os.path.isfile(config_file):
         err = f"D-Bus config file not found: {config_file}"
         logging.critical(err)
         return False, err
         
    try:
        # --- Environment Prep Removed ---
        # Rely on system environment for dbus-daemon
        env = os.environ.copy() # Start with current env
            
        # Command using dbus-daemon with the custom config file
        cmd = [
            "dbus-daemon", 
            f"--config-file={config_file}",
            "--fork",
            "--print-address=1", 
            "--print-pid=1",
        ]
        
        logging.info(f"Launching dbus-daemon with command: {' '.join(cmd)}")
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        stdout, stderr = proc.communicate(timeout=10)
        
        if proc.returncode != 0:
             raise RuntimeError(f"dbus-daemon command failed (rc={proc.returncode}): {stderr}")
             
        lines = stdout.strip().splitlines()
        if len(lines) < 2:
            raise RuntimeError(f"Unexpected output from dbus-daemon: {stdout}")
            
        dbus_address = lines[0].strip()
        dbus_pid_str = lines[1].strip()
        dbus_pid = int(dbus_pid_str)
        
        if not dbus_address or not dbus_address.startswith("unix:"):
             raise RuntimeError(f"Invalid D-Bus address received: {dbus_address}")
             
        logging.info(f"Launched D-Bus daemon (PID: {dbus_pid}) at address: {dbus_address}")
        # Set the address for subsequent processes (like Anaconda Boss and UI connections)
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = dbus_address
        
        _process_pids.append(dbus_pid)
        # Don't store proc itself as it exits after fork 
        global _dbus_daemon_proc
        _dbus_daemon_proc = None # Process is managed by PID via atexit
        
        return True, None # Success
        
    except FileNotFoundError:
         err = "Error: dbus-daemon command not found. Cannot start session bus."
         logging.critical(err)
         return False, err
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, RuntimeError, ValueError) as e:
         err = f"Error launching or parsing dbus-daemon output: {e}"
         logging.critical(err, exc_info=True)
         return False, err
    except Exception as e:
        err = f"Unexpected error launching D-Bus daemon with config: {e}"
        logging.critical(err, exc_info=True)
        return False
# --- End D-Bus Daemon Launch ---

def main():
    """Main function to initialize D-Bus, Anaconda, and run the application."""
    global _dbus_daemon_proc, _anaconda_boss_proc
    try:
        logging.info("Centrio Installer starting...")
        
        # 0. Create the D-Bus config file
        if not create_dbus_config():
             print("FATAL: Could not create D-Bus configuration file.", file=sys.stderr)
             # Check logs for why create_dbus_config failed (e.g., service dir missing)
             return 1
             
        # 1. Launch D-Bus Daemon
        dbus_ok, dbus_err = launch_dbus_daemon()
        if not dbus_ok:
            print(f"FATAL: {dbus_err}", file=sys.stderr)
            return 1
            
        # Allow D-Bus daemon and services time to initialize
        import time
        logging.info("Waiting for D-Bus services (including Boss) to activate...")
        time.sleep(20) # Significantly increased sleep duration

        # 3. Start GTK Application
        Adw.init()
        app = CentrioInstallerApp()
        exit_status = app.run(sys.argv)
        logging.info(f"Centrio Installer finished with exit status: {exit_status}")
        # atexit handler will call cleanup_processes
        return exit_status
        
    except Exception as e:
        logging.critical("Unhandled exception caused installer to crash!", exc_info=True)
        return 1

if __name__ == '__main__':
    # Ensure the application exits with the correct status code
    sys.exit(main()) 