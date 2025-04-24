# centrio_installer/constants.py

# Application ID
APP_ID = "org.example.CentrioInstaller"

# --- Anaconda D-Bus Constants --- 
ANACONDA_BUS_ADDR_FILE = "/run/anaconda/bus-addr" # Standard location
DBUS_ANACONDA_SESSION_ADDRESS = "DBUS_ANACONDA_SESSION_ADDRESS" # Env var name

# Timezone Service
TIMEZONE_SERVICE = "org.fedoraproject.Anaconda.Modules.Timezone"
TIMEZONE_OBJECT_PATH = "/org/fedoraproject.Anaconda/Modules/Timezone"
TIMEZONE_INTERFACE = "org.fedoraproject.Anaconda.Modules.TimezoneInterface"

# Localization/Keyboard Service
LOCALIZATION_SERVICE = "org.fedoraproject.Anaconda.Modules.Localization"
LOCALIZATION_OBJECT_PATH = "/org/fedoraproject.Anaconda/Modules/Localization"
LOCALIZATION_INTERFACE = "org.fedoraproject.Anaconda.Modules.LocalizationInterface"

# Network Service
NETWORK_SERVICE = "org.fedoraproject.Anaconda.Modules.Network"
NETWORK_OBJECT_PATH = "/org/fedoraproject.Anaconda/Modules/Network"
NETWORK_INTERFACE = "org.fedoraproject.Anaconda.Modules.NetworkInterface"

# Users Service
USERS_SERVICE = "org.fedoraproject.Anaconda.Modules.Users"
USERS_OBJECT_PATH = "/org/fedoraproject.Anaconda/Modules/Users"
USERS_INTERFACE = "org.fedoraproject.Anaconda.Modules.UsersInterface"

# Storage Service
STORAGE_SERVICE = "org.fedoraproject.Anaconda.Modules.Storage"
STORAGE_OBJECT_PATH = "/org/fedoraproject.Anaconda/Modules/Storage"
STORAGE_INTERFACE = "org.fedoraproject.Anaconda.Modules.StorageInterface"

# Payloads Service
PAYLOADS_SERVICE = "org.fedoraproject.Anaconda.Modules.Payloads"
PAYLOADS_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Payloads"
PAYLOADS_INTERFACE = "org.fedoraproject.Anaconda.Modules.PayloadsInterface"

# Bootloader Service (part of Storage module, but distinct interface)
# Assuming the Bootloader interface is on the Storage object path
BOOTLOADER_SERVICE = STORAGE_SERVICE 
BOOTLOADER_OBJECT_PATH = STORAGE_OBJECT_PATH 
BOOTLOADER_INTERFACE = "org.fedoraproject.Anaconda.Modules.Storage.BootloaderInterface" 

# Boss Service (Installation Manager)
BOSS_SERVICE = "org.fedoraproject.Anaconda.Boss"
BOSS_OBJECT_PATH = "/org/fedoraproject/Anaconda/Boss"
BOSS_INTERFACE = "org.fedoraproject.Anaconda.BossInterface"

# Task Interface (Common for monitoring progress)
TASK_INTERFACE = "org.fedoraproject.Anaconda.TaskInterface" 