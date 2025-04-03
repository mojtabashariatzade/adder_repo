"""
Settings Menu Module

This module provides a menu-based interface for viewing and modifying application settings.
It integrates with the Config class to ensure all changes are properly stored and applied.

This module provides a menu system for configuring application
settings in the Telegram Account Manager.
It allows users to view and modify various settings, including:
- Application settings (e.g., debug mode)
- Time delays
- Operation limits
- Proxy settings
- Encryption settings
- File paths

The module uses the Config class from core.config to read and save the modified settings.
It follows a similar design pattern to other UI modules in the project, ensuring consistency
in the user interface.

Usage:
    from ui.settings_menu import create_settings_menu
    from ui.menu_system import Menu

    # Create a settings menu
    settings_menu = create_settings_menu(parent_menu)

    # Or run it standalone
    settings_menu.display()
"""

import os
import sys
import logging
from ui.menu_system import Menu, create_action_item, create_submenu_item, create_toggle_item

# Import core modules
try:
    from core.config import Config
    from core.constants import Constants
except ImportError:
    # For development or testing without the full project structure
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..')))
    from core.config import Config
    from core.constants import Constants

# Import UI utilities if available
try:
    from ui.colors import Colors
    from ui.display import Display, clear_screen, print_header, print_error, print_success
except ImportError:
    # Fallback if UI utilities are not available
    class Colors:
        """Fallback class for terminal colors."""
        @staticmethod
        def colorize(text, color=None):
            return text

        @staticmethod
        def bold(text):
            return text

        CYAN = ''
        GREEN = ''
        YELLOW = ''
        RED = ''
        RESET = ''

    class Display:
        """Fallback class for display utilities."""
        @staticmethod
        def clear_screen():
            os.system('cls' if os.name == 'nt' else 'clear')

        @staticmethod
        def print_header(title):
            print("\n" + "=" * 60)
            print(f" {title}")
            print("=" * 60)

        @staticmethod
        def print_message(message, color=None):
            print(message)

        @staticmethod
        def print_error(message):
            print(f"ERROR: {message}")

        @staticmethod
        def print_success(message):
            print(f"SUCCESS: {message}")

        @staticmethod
        def input_with_prompt(prompt):
            return input(f"{prompt}: ")

    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(title):
        print("\n" + "=" * 60)
        print(f" {title}")
        print("=" * 60)

    def print_error(message):
        print(f"ERROR: {message}")

    def print_success(message):
        print(f"SUCCESS: {message}")

# Setup logger
logger = logging.getLogger(__name__)


def create_settings_menu(parent_menu: Menu) -> Menu:
    """
    Create a settings menu and its submenus.

    Args:
        parent_menu: The parent menu

    Returns:
        Menu: The settings menu
    """
    config = Config()
    settings_menu = Menu("Settings", parent=parent_menu)

    # Create submenus
    app_settings_menu = create_app_settings_menu(settings_menu)
    time_delays_menu = create_time_delays_menu(settings_menu)
    operation_limits_menu = create_operation_limits_menu(settings_menu)
    proxy_settings_menu = create_proxy_settings_menu(settings_menu)
    encryption_settings_menu = create_encryption_settings_menu(settings_menu)
    file_paths_menu = create_file_paths_menu(settings_menu)

    # Add submenus to settings menu
    settings_menu.add_item(create_submenu_item(
        "1", "Application Settings", app_settings_menu))
    settings_menu.add_item(create_submenu_item(
        "2", "Time Delays", time_delays_menu))
    settings_menu.add_item(create_submenu_item(
        "3", "Operation Limits", operation_limits_menu))
    settings_menu.add_item(create_submenu_item(
        "4", "Proxy Settings", proxy_settings_menu))
    settings_menu.add_item(create_submenu_item(
        "5", "Encryption Settings", encryption_settings_menu))
    settings_menu.add_item(create_submenu_item(
        "6", "File Paths", file_paths_menu))
    settings_menu.add_item(create_action_item(
        "7", "Save All Changes", lambda: save_all_changes(config)))
    settings_menu.add_item(create_action_item(
        "8", "Reset to Defaults", lambda: reset_to_defaults(config)))

    return settings_menu


def create_app_settings_menu(parent_menu: Menu) -> Menu:
    """Create application settings submenu."""
    config = Config()
    app_settings_menu = Menu("Application Settings", parent=parent_menu)

    # Get current settings for toggle items
    debug_mode = config.get('debug_mode', False)

    # Add menu items
    app_settings_menu.add_item(create_action_item(
        "1", "Edit Application Name",
        lambda: edit_app_name(config)
    ))

    app_settings_menu.add_item(create_action_item(
        "2", "Edit Application Version",
        lambda: edit_app_version(config)
    ))

    app_settings_menu.add_item(create_toggle_item(
        "3", "Debug Mode",
        debug_mode,
        lambda value: config.set('debug_mode', value)
    ))

    return app_settings_menu


def create_time_delays_menu(parent_menu: Menu) -> Menu:
    """Create time delays settings submenu."""
    config = Config()
    time_delays_menu = Menu("Time Delay Settings", parent=parent_menu)

    # Add menu items
    time_delays_menu.add_item(create_action_item(
        "1", "Edit Default Delay",
        lambda: edit_numeric_setting(config, 'default_delay', "Default delay (seconds)",
                                     Constants.TimeDelays.DEFAULT, 1, 300)
    ))

    time_delays_menu.add_item(create_action_item(
        "2", "Edit Maximum Delay",
        lambda: edit_numeric_setting(config, 'max_delay', "Maximum delay (seconds)",
                                     Constants.TimeDelays.MAXIMUM, 60, 3600)
    ))

    time_delays_menu.add_item(create_action_item(
        "3", "Edit Account Change Delay",
        lambda: edit_numeric_setting(config, 'account_change_delay', "Account change delay (seconds)",
                                     Constants.TimeDelays.ACCOUNT_CHANGE, 10, 600)
    ))

    return time_delays_menu


def create_operation_limits_menu(parent_menu: Menu) -> Menu:
    """Create operation limits settings submenu."""
    config = Config()
    operation_limits_menu = Menu(
        "Operation Limit Settings", parent=parent_menu)

    # Add menu items
    operation_limits_menu.add_item(create_action_item(
        "1", "Edit Maximum Retry Count",
        lambda: edit_numeric_setting(config, 'max_retry_count', "Maximum retry count",
                                     Constants.Limits.MAX_RETRY, 1, 20)
    ))

    operation_limits_menu.add_item(create_action_item(
        "2", "Edit Maximum Failures Before Block",
        lambda: edit_numeric_setting(config, 'max_failures_before_block', "Maximum failures before block",
                                     Constants.Limits.MAX_FAILURES, 1, 10)
    ))

    operation_limits_menu.add_item(create_action_item(
        "3", "Edit Maximum Members Per Day",
        lambda: edit_numeric_setting(config, 'max_members_per_day', "Maximum members per day",
                                     Constants.Limits.MAX_MEMBERS_PER_DAY, 10, 100)
    ))

    operation_limits_menu.add_item(create_action_item(
        "4", "Edit Maximum Memory Records",
        lambda: edit_numeric_setting(config, 'max_memory_records', "Maximum memory records",
                                     Constants.Limits.MAX_MEMORY_RECORDS, 100, 10000)
    ))

    return operation_limits_menu


def create_proxy_settings_menu(parent_menu: Menu) -> Menu:
    """Create proxy settings submenu."""
    config = Config()
    proxy_settings_menu = Menu("Proxy Settings", parent=parent_menu)

    # Get current settings for toggle items
    use_proxy = config.get('use_proxy', False)
    proxy_rotation_enabled = config.get('proxy_rotation_enabled', False)

    # Add menu items
    proxy_settings_menu.add_item(create_toggle_item(
        "1", "Use Proxy",
        use_proxy,
        lambda value: config.set('use_proxy', value)
    ))

    proxy_settings_menu.add_item(create_action_item(
        "2", "Edit Default Proxy Type",
        lambda: edit_proxy_type(config)
    ))

    proxy_settings_menu.add_item(create_toggle_item(
        "3", "Proxy Rotation",
        proxy_rotation_enabled,
        lambda value: config.set('proxy_rotation_enabled', value)
    ))

    proxy_settings_menu.add_item(create_action_item(
        "4", "Edit Proxy Rotation Interval",
        lambda: edit_numeric_setting(config, 'proxy_rotation_interval', "Proxy rotation interval (seconds)",
                                     3600, 300, 86400)
    ))

    proxy_servers_menu = create_proxy_servers_menu(proxy_settings_menu)
    proxy_settings_menu.add_item(create_submenu_item(
        "5", "Configure Proxy Servers",
        proxy_servers_menu
    ))

    return proxy_settings_menu


def create_proxy_servers_menu(parent_menu: Menu) -> Menu:
    """Create proxy servers configuration submenu."""
    config = Config()
    proxy_servers_menu = Menu("Proxy Server Configuration", parent=parent_menu)

    proxy_servers_menu.add_item(create_action_item(
        "1", "Add New Proxy",
        lambda: add_new_proxy(config)
    ))

    proxy_servers_menu.add_item(create_action_item(
        "2", "Edit Existing Proxy",
        lambda: edit_existing_proxy(config)
    ))

    proxy_servers_menu.add_item(create_action_item(
        "3", "Remove Proxy",
        lambda: remove_proxy(config)
    ))

    proxy_servers_menu.add_item(create_action_item(
        "4", "List All Proxies",
        lambda: list_all_proxies(config)
    ))

    return proxy_servers_menu


def create_encryption_settings_menu(parent_menu: Menu) -> Menu:
    """Create encryption settings submenu."""
    config = Config()
    encryption_settings_menu = Menu("Encryption Settings", parent=parent_menu)

    # Get current settings for toggle items
    encryption_enabled = config.get('encryption_enabled', True)
    encryption_required = config.get(
        'encryption_required_for_sensitive_data', True)

    # Add menu items
    encryption_settings_menu.add_item(create_toggle_item(
        "1", "Encryption Enabled",
        encryption_enabled,
        lambda value: config.set('encryption_enabled', value)
    ))

    encryption_settings_menu.add_item(create_action_item(
        "2", "Show Encryption Algorithm",
        lambda: show_encryption_algorithm(config)
    ))

    encryption_settings_menu.add_item(create_toggle_item(
        "3", "Require Encryption for Sensitive Data",
        encryption_required,
        lambda value: config.set(
            'encryption_required_for_sensitive_data', value)
    ))

    return encryption_settings_menu


def create_file_paths_menu(parent_menu: Menu) -> Menu:
    """Create file paths settings submenu."""
    config = Config()
    file_paths_menu = Menu("File Path Settings", parent=parent_menu)

    # Add menu items
    file_paths_menu.add_item(create_action_item(
        "1", "Edit Log File Path",
        lambda: edit_file_path(config, 'log_file', "Log file path")
    ))

    file_paths_menu.add_item(create_action_item(
        "2", "Edit Request Log File Path",
        lambda: edit_file_path(config, 'request_log_file',
                               "Request log file path")
    ))

    file_paths_menu.add_item(create_action_item(
        "3", "Edit AI Data File Path",
        lambda: edit_file_path(config, 'ai_data_file', "AI data file path")
    ))

    file_paths_menu.add_item(create_action_item(
        "4", "Edit Accounts File Path",
        lambda: edit_file_path(config, 'accounts_file', "Accounts file path")
    ))

    return file_paths_menu


# Actions for Application Settings
def edit_app_name(config: Config) -> None:
    """Edit application name."""
    current_name = config.get('app_name', 'Telegram Account Manager')

    clear_screen()
    print_header("Edit Application Name")
    print(f"\nCurrent application name: {current_name}")

    new_name = input(
        f"\nEnter new application name (or leave empty to keep current): ")

    if new_name.strip():
        config.set('app_name', new_name)
        print_success(f"Application name updated to: {new_name}")
    else:
        print("No changes made.")

    input("\nPress Enter to continue...")


def edit_app_version(config: Config) -> None:
    """Edit application version."""
    current_version = config.get('app_version', '1.0.0')

    clear_screen()
    print_header("Edit Application Version")
    print(f"\nCurrent application version: {current_version}")

    new_version = input(
        f"\nEnter new application version (or leave empty to keep current): ")

    if new_version.strip():
        config.set('app_version', new_version)
        print_success(f"Application version updated to: {new_version}")
    else:
        print("No changes made.")

    input("\nPress Enter to continue...")


# Actions for Proxy Settings
def edit_proxy_type(config: Config) -> None:
    """Edit default proxy type."""
    current_type = config.get('default_proxy_type', 'socks5')

    clear_screen()
    print_header("Edit Default Proxy Type")
    print(f"\nCurrent default proxy type: {current_type}")
    print("\nAvailable proxy types:")
    print("1. socks5")
    print("2. http")

    choice = input(
        "\nEnter your choice (1-2) or leave empty to keep current: ")

    if choice == "1":
        config.set('default_proxy_type', 'socks5')
        print_success("Default proxy type set to: socks5")
    elif choice == "2":
        config.set('default_proxy_type', 'http')
        print_success("Default proxy type set to: http")
    else:
        print("No changes made.")

    input("\nPress Enter to continue...")


def add_new_proxy(config: Config) -> None:
    """Add a new proxy server configuration."""
    clear_screen()
    print_header("Add New Proxy")

    name = input("Enter proxy name (e.g., 'default', 'backup1'): ")
    if not name or name.strip() == "":
        print_error("Proxy name cannot be empty.")
        input("\nPress Enter to continue...")
        return

    # Get current proxy settings
    proxy_settings = config.get('proxy_settings', {})

    # Check if name already exists
    if name in proxy_settings:
        overwrite = input(
            f"Proxy '{name}' already exists. Overwrite? (y/n): ").lower()
        if overwrite != 'y':
            print("Operation canceled.")
            input("\nPress Enter to continue...")
            return

    # Get proxy details
    proxy_type = input(
        "Enter proxy type (socks5/http) [socks5]: ").lower() or 'socks5'
    if proxy_type not in ('socks5', 'http'):
        print_error("Invalid proxy type. Using 'socks5'.")
        proxy_type = 'socks5'

    addr = input("Enter proxy server address: ")
    if not addr or addr.strip() == "":
        print_error("Proxy address cannot be empty.")
        input("\nPress Enter to continue...")
        return

    port_str = input("Enter proxy server port [1080]: ") or '1080'
    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            raise ValueError("Port out of range")
    except ValueError:
        print_error("Invalid port number. Using default 1080.")
        port = 1080

    use_auth = input(
        "Does this proxy require authentication? (y/n) [n]: ").lower() or 'n'
    username = ""
    password = ""
    if use_auth == 'y':
        username = input("Enter proxy username: ")
        password = input("Enter proxy password: ")

    rdns = input("Use remote DNS resolution? (y/n) [y]: ").lower() or 'y'

    # Create proxy configuration
    proxy_config = {
        'proxy_type': proxy_type,
        'addr': addr,
        'port': port,
        'username': username,
        'password': password,
        'rdns': rdns == 'y'
    }

    # Update configuration
    if not isinstance(proxy_settings, dict):
        proxy_settings = {}

    proxy_settings[name] = proxy_config
    config.set('proxy_settings', proxy_settings)

    # If this is the first proxy, enable proxy usage
    if len(proxy_settings) == 1:
        config.set('use_proxy', True)

    print_success(f"Proxy '{name}' added successfully.")
    input("\nPress Enter to continue...")


def edit_existing_proxy(config: Config) -> None:
    """Edit an existing proxy server configuration."""
    clear_screen()
    print_header("Edit Existing Proxy")

    # Get current proxy settings
    proxy_settings = config.get('proxy_settings', {})

    if not proxy_settings:
        print_error("No proxy servers configured.")
        input("\nPress Enter to continue...")
        return

    # Display current proxies
    print("\nCurrent Proxy Servers:")
    proxy_names = list(proxy_settings.keys())
    for i, name in enumerate(proxy_names, 1):
        proxy = proxy_settings[name]
        addr = proxy.get('addr', '')
        port = proxy.get('port', 0)
        proxy_type = proxy.get('proxy_type', 'socks5')
        has_auth = bool(proxy.get('username'))
        print(
            f"{i}. {name}: {proxy_type}://{addr}:{port} {'(Auth)' if has_auth else ''}")

    # Get proxy to edit
    proxy_index_str = input(
        "\nEnter the number of the proxy to edit (or 0 to cancel): ")
    try:
        proxy_index = int(proxy_index_str)
        if proxy_index == 0:
            return
        if proxy_index < 1 or proxy_index > len(proxy_names):
            raise ValueError("Index out of range")
    except ValueError:
        print_error("Invalid selection.")
        input("\nPress Enter to continue...")
        return

    proxy_name = proxy_names[proxy_index - 1]
    proxy = proxy_settings[proxy_name]

    # Edit proxy details
    print(f"\nEditing proxy '{proxy_name}':")

    proxy_type = input(
        f"Enter proxy type (socks5/http) [{proxy.get('proxy_type', 'socks5')}]: ").lower() or proxy.get('proxy_type', 'socks5')
    if proxy_type not in ('socks5', 'http'):
        print_error("Invalid proxy type. Using previous value.")
        proxy_type = proxy.get('proxy_type', 'socks5')

    addr = input(
        f"Enter proxy server address [{proxy.get('addr', '')}]: ") or proxy.get('addr', '')

    port_str = input(f"Enter proxy server port [{proxy.get('port', 1080)}]: ") or str(
        proxy.get('port', 1080))
    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            raise ValueError("Port out of range")
    except ValueError:
        print_error("Invalid port number. Using previous value.")
        port = proxy.get('port', 1080)

    current_has_auth = bool(proxy.get('username'))
    use_auth = input(f"Does this proxy require authentication? (y/n) [{'y' if current_has_auth else 'n'}]: ").lower(
    ) or ('y' if current_has_auth else 'n')

    username = proxy.get('username', '')
    password = proxy.get('password', '')
    if use_auth == 'y':
        username = input(f"Enter proxy username [{username}]: ") or username
        password = input(f"Enter proxy password [{password}]: ") or password
    else:
        username = ""
        password = ""

    current_rdns = proxy.get('rdns', True)
    rdns = input(f"Use remote DNS resolution? (y/n) [{'y' if current_rdns else 'n'}]: ").lower(
    ) or ('y' if current_rdns else 'n')

    # Update proxy configuration
    proxy_config = {
        'proxy_type': proxy_type,
        'addr': addr,
        'port': port,
        'username': username,
        'password': password,
        'rdns': rdns == 'y'
    }

    # Update configuration
    proxy_settings[proxy_name] = proxy_config
    config.set('proxy_settings', proxy_settings)

    print_success(f"Proxy '{proxy_name}' updated successfully.")
    input("\nPress Enter to continue...")


def remove_proxy(config: Config) -> None:
    """Remove an existing proxy server configuration."""
    clear_screen()
    print_header("Remove Proxy")

    # Get current proxy settings
    proxy_settings = config.get('proxy_settings', {})

    if not proxy_settings:
        print_error("No proxy servers configured.")
        input("\nPress Enter to continue...")
        return

    # Display current proxies
    print("\nCurrent Proxy Servers:")
    proxy_names = list(proxy_settings.keys())
    for i, name in enumerate(proxy_names, 1):
        proxy = proxy_settings[name]
        addr = proxy.get('addr', '')
        port = proxy.get('port', 0)
        proxy_type = proxy.get('proxy_type', 'socks5')
        has_auth = bool(proxy.get('username'))
        print(
            f"{i}. {name}: {proxy_type}://{addr}:{port} {'(Auth)' if has_auth else ''}")

    # Get proxy to remove
    proxy_index_str = input(
        "\nEnter the number of the proxy to remove (or 0 to cancel): ")
    try:
        proxy_index = int(proxy_index_str)
        if proxy_index == 0:
            return
        if proxy_index < 1 or proxy_index > len(proxy_names):
            raise ValueError("Index out of range")
    except ValueError:
        print_error("Invalid selection.")
        input("\nPress Enter to continue...")
        return

    proxy_name = proxy_names[proxy_index - 1]

    # Confirm removal
    confirm = input(
        f"Are you sure you want to remove proxy '{proxy_name}'? (y/n): ").lower()
    if confirm != 'y':
        print("Operation canceled.")
        input("\nPress Enter to continue...")
        return

    # Remove proxy
    del proxy_settings[proxy_name]
    config.set('proxy_settings', proxy_settings)

    # If no proxies left, disable proxy usage
    if not proxy_settings:
        config.set('use_proxy', False)

    print_success(f"Proxy '{proxy_name}' removed successfully.")
    input("\nPress Enter to continue...")


def list_all_proxies(config: Config) -> None:
    """List all configured proxies with details."""
    clear_screen()
    print_header("All Configured Proxies")

    # Get current proxy settings
    proxy_settings = config.get('proxy_settings', {})

    if not proxy_settings:
        print("\nNo proxy servers configured.")
        input("\nPress Enter to continue...")
        return

    # Display proxy details
    for name, proxy in proxy_settings.items():
        print(f"\nProxy: {name}")
        print(f"  Type: {proxy.get('proxy_type', 'socks5')}")
        print(f"  Address: {proxy.get('addr', '')}")
        print(f"  Port: {proxy.get('port', 1080)}")
        if proxy.get('username'):
            print(f"  Authentication: Yes (Username: {proxy.get('username')})")
        else:
            print("  Authentication: No")
        print(f"  Remote DNS: {'Yes' if proxy.get('rdns', True) else 'No'}")
        print("-" * 40)

    input("\nPress Enter to continue...")


# Actions for Encryption Settings
def show_encryption_algorithm(config: Config) -> None:
    """Show the current encryption algorithm and information."""
    clear_screen()
    print_header("Encryption Algorithm Information")

    encryption_algorithm = config.get('encryption_algorithm', 'fernet')

    print(f"\nCurrent encryption algorithm: {encryption_algorithm}")
    print("\nEncryption Information:")

    if encryption_algorithm.lower() == 'fernet':
        print("  Fernet (AES-128-CBC with HMAC-SHA256)")
        print("  - Symmetric encryption method")
        print("  - Includes authentication to prevent tampering")
        print("  - Uses Base64 encoding for the ciphertext")
        print("  - Includes timestamp to prevent replay attacks")
    else:
        print(f"  Information for {encryption_algorithm} is not available")

    print("\nNote: Currently only 'fernet' encryption is supported in this version.")

    input("\nPress Enter to continue...")


# Utility functions
def edit_numeric_setting(config: Config, setting_name: str, prompt_text: str,
                         default_value: int, min_value: int, max_value: int) -> None:
    """
    Edit a numeric configuration setting with validation.

    Args:
        config: Configuration instance
        setting_name: The name of the setting to update
        prompt_text: The prompt to display to the user
        default_value: Default value if not set
        min_value: Minimum allowed value
        max_value: Maximum allowed value
    """
    current_value = config.get(setting_name, default_value)

    clear_screen()
    print_header(f"Edit {prompt_text}")
    print(f"\nCurrent value: {current_value}")
    print(f"Valid range: {min_value} to {max_value}")

    new_value_str = input(
        f"\nEnter new value (or leave empty to keep current): ")

    if not new_value_str.strip():
        print("No changes made.")
    else:
        try:
            new_value = int(new_value_str)

            if new_value < min_value or new_value > max_value:
                print_error(
                    f"Value must be between {min_value} and {max_value}.")
            else:
                config.set(setting_name, new_value)
                print_success(f"{prompt_text} updated to: {new_value}")
        except ValueError:
            print_error("Invalid input. Please enter a number.")

    input("\nPress Enter to continue...")


def edit_file_path(config: Config, setting_name: str, prompt_text: str) -> None:
    """
    Edit a file path configuration setting.

    Args:
        config: Configuration instance
        setting_name: The name of the setting to update
        prompt_text: The prompt to display to the user
    """
    current_path = config.get(setting_name, "")

    clear_screen()
    print_header(f"Edit {prompt_text}")
    print(f"\nCurrent path: {current_path}")

    new_path = input(
        f"\nEnter new file path (or leave empty to keep current): ")

    if new_path.strip():
        config.set(setting_name, new_path)
        print_success(f"{prompt_text} updated to: {new_path}")
    else:
        print("No changes made.")

    input("\nPress Enter to continue...")


def save_all_changes(config: Config) -> None:
    """Save all configuration changes to file."""
    clear_screen()
    print_header("Save Configuration")

    try:
        result = config.save()
        if result:
            print_success("All configuration changes saved successfully.")
        else:
            print_error("Failed to save configuration changes.")
    except Exception as e:
        print_error(f"Error saving configuration: {str(e)}")

    input("\nPress Enter to continue...")


def reset_to_defaults(config: Config) -> None:
    """Reset configuration to default values."""
    clear_screen()
    print_header("Reset to Defaults")

    confirm = input(
        "\nAre you sure you want to reset all settings to defaults? (y/n): ").lower()
    if confirm != 'y':
        print("Operation canceled.")
        input("\nPress Enter to continue...")
        return

    try:
        config.reset_defaults()
        print_success("All settings have been reset to default values.")
        print("You may need to restart the application for some changes to take effect.")
    except Exception as e:
        print_error(f"Error resetting to defaults: {str(e)}")

    input("\nPress Enter to continue...")
