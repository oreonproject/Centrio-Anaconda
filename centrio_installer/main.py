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

def launch_dbus_daemon():
    """Starts a dbus-daemon using a custom config file, captures its address/PID, and sets environment."""
    global _process_pids
    logging.info("Attempting to launch D-Bus daemon with custom config...")
    config_file = "/tmp/centrio_dbus.conf" # Path to the file we just created
    
    # Ensure the config file exists
    if not os.path.isfile(config_file):
         err = f"D-Bus config file not found: {config_file}"
         logging.critical(err)
         return False, err
         
    try:
        # --- Prepare Environment --- 
        script_dir = os.path.dirname(__file__)
        anaconda_root = os.path.abspath(os.path.join(script_dir, '..', 'ANACONDA'))
        anaconda_scripts_dir = os.path.join(anaconda_root, 'scripts') # Path to scripts
        
        if not os.path.isdir(anaconda_scripts_dir):
            raise RuntimeError(f"Anaconda scripts directory not found: {anaconda_scripts_dir}")
            
        # Remove XDG_DATA_DIRS manipulation - handled by config file's <servicedir>
        # original_xdg_data_dirs = os.environ.get('XDG_DATA_DIRS', '')
        # ... (removed related code)
            
        # Prepend Anaconda scripts dir to PATH so dbus-daemon finds start-module
        original_path = os.environ.get('PATH', '')
        if anaconda_scripts_dir not in original_path.split(':'):
            new_path = f"{anaconda_scripts_dir}:{original_path}" if original_path else anaconda_scripts_dir
            logging.info(f"Setting PATH to: {new_path}")
            os.environ['PATH'] = new_path
        else:
             logging.info(f"Anaconda scripts dir already in PATH: {os.environ['PATH']}")
             
        # Ensure PYTHONPATH includes the Anaconda root for module imports by start-module
        anaconda_pythonpath = anaconda_root # The dir containing pyanaconda
        original_pythonpath = os.environ.get('PYTHONPATH', '')
        if anaconda_pythonpath not in original_pythonpath.split(':'):
             new_pythonpath = f"{anaconda_pythonpath}:{original_pythonpath}" if original_pythonpath else anaconda_pythonpath
             logging.info(f"Setting PYTHONPATH to: {new_pythonpath}")
             os.environ['PYTHONPATH'] = new_pythonpath
        else:
             logging.info(f"Anaconda root already in PYTHONPATH: {os.environ['PYTHONPATH']}")
        # --- End Environment Prep ---
            
        # Command using dbus-daemon with the custom config file
        cmd = [
            "dbus-daemon", 
            f"--config-file={config_file}",
            # "--nofork", # Keep commented out, fork is needed
            "--fork",   # Keep fork to daemonize
            "--print-address=1", 
            "--print-pid=1",
            # "--session" # REMOVE this, as config file specifies type=session
        ]
        
        logging.info(f"Launching dbus-daemon with command: {' '.join(cmd)}")
        
        # We still need to capture stdout for address/pid
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ.copy())
        stdout, stderr = proc.communicate(timeout=10)
        
        if proc.returncode != 0:
             # Check stderr for clues if dbus-daemon fails with config
             raise RuntimeError(f"dbus-daemon command failed (rc={proc.returncode}): {stderr}")
             
        # Parse stdout (should contain address on first line, pid on second)
        lines = stdout.strip().splitlines()
        if len(lines) < 2:
            raise RuntimeError(f"Unexpected output from dbus-daemon: {stdout}")
            
        dbus_address = lines[0].strip()
        dbus_pid_str = lines[1].strip()
        dbus_pid = int(dbus_pid_str)
        
        if not dbus_address or not dbus_address.startswith("unix:"):
             raise RuntimeError(f"Invalid D-Bus address received: {dbus_address}")
             
        logging.info(f"Launched D-Bus daemon (PID: {dbus_pid}) at address: {dbus_address}")
        # Set the address for subsequent processes (like Anaconda Boss)
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = dbus_address
        
        # Important: We don't own the dbus-daemon process directly anymore if it forks.
        # We track the PID reported by dbus-daemon itself.
        _process_pids.append(dbus_pid) 
        # Do NOT store proc in _dbus_daemon_proc as it exits after fork.
        global _dbus_daemon_proc
        _dbus_daemon_proc = None # Explicitly set to None as we don't manage it directly
        
        return True, None # Success
        
    except FileNotFoundError:
         err = "Error: dbus-daemon command not found. Cannot start session bus."
         logging.critical(err)
         return False, err
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, RuntimeError, ValueError) as e:
         err = f"Error launching or parsing dbus-daemon output: {e}"
         logging.critical(err)
         return False, err
    except Exception as e:
        err = f"Unexpected error launching D-Bus daemon with config: {e}"
        logging.critical(err, exc_info=True)
        return False, err

def launch_anaconda_boss():
    """Launches the Anaconda Boss module as a subprocess."""
    global _anaconda_boss_proc
    logging.info("Attempting to launch Anaconda Boss module...")
    # Adjust path as necessary
    anaconda_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ANACONDA'))
    boss_script = os.path.join(anaconda_root, "pyanaconda", "modules", "boss", "__main__.py")
    python_executable = sys.executable # Use the same python interpreter
    
    if not os.path.exists(boss_script):
        err = f"Anaconda Boss script not found at: {boss_script}"
        logging.critical(err)
        return False, err
        
    # Ensure DBUS_SESSION_BUS_ADDRESS is in the environment
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
         err = "DBUS_SESSION_BUS_ADDRESS not set. Cannot launch Boss." 
         logging.critical(err)
         return False, err
         
    try:
        cmd = [python_executable, boss_script]
        logging.info(f"Launching Boss with command: {' '.join(cmd)}")
        # Launch and don't wait for it
        # Pass current environment (which includes DBUS_SESSION_BUS_ADDRESS)
        _anaconda_boss_proc = subprocess.Popen(cmd, env=os.environ.copy(), 
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, # Capture output for logging
                                               text=True)
        logging.info(f"Anaconda Boss process launched (PID: {_anaconda_boss_proc.pid})")
        # TODO: Optionally monitor the stdout/stderr of the Boss process in a thread?
        return True, None
    except Exception as e:
        err = f"Failed to launch Anaconda Boss: {e}"
        logging.critical(err, exc_info=True)
        _anaconda_boss_proc = None
        return False, err

def main():
    """Main function to initialize D-Bus, Anaconda, and run the application."""
    global _dbus_daemon_proc, _anaconda_boss_proc
    try:
        logging.info("Centrio Installer starting...")
        
        # 1. Launch D-Bus Daemon
        dbus_ok, dbus_err = launch_dbus_daemon()
        if not dbus_ok:
            # Show critical error to user? GTK isn't running yet.
            print(f"FATAL: {dbus_err}", file=sys.stderr)
            return 1
            
        # Allow D-Bus daemon time to initialize
        import time
        time.sleep(1) 
        
        # 2. Launch Anaconda Boss
        boss_ok, boss_err = launch_anaconda_boss()
        if not boss_ok:
             print(f"FATAL: {boss_err}", file=sys.stderr)
             # Cleanup D-Bus daemon before exiting
             cleanup_processes()
             return 1
             
        # Allow Boss time to start and register on D-Bus
        time.sleep(2)
             
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