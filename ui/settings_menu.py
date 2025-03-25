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
    from ui.settings_menu import SettingsMenu
    from ui.menu_system import MenuSystem

    # Create a settings menu
    settings_menu = SettingsMenu()

    # Add it to the main menu system
    menu_system = MenuSystem()
    menu_system.add_submenu('settings', 'Settings', settings_menu)

    # Or run it standalone
    settings_menu.display()
"""

import os
import sys
import logging

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
    from ui.display import Display
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

# Setup logger
logger = logging.getLogger(__name__)


class SettingsMenu:
    """
    Menu system for viewing and modifying application settings.

    This class provides a user interface for interacting with the application's
    configuration settings. It allows users to view current settings, modify them,
    and save the changes. The menu is organized into categories for easier navigation
    and follows a consistent design pattern with other UI components.
    """

    def __init__(self):
        """Initialize the Settings Menu."""
        self.config = Config()
        self.display = Display()
        self.colors = Colors()
        self.exit_requested = False

    def display(self) -> None:
        """Display the settings menu and handle user interaction."""
        while not self.exit_requested:
            self._show_main_menu()
            choice = self._get_user_choice()
            self._handle_main_menu_choice(choice)

    def _show_main_menu(self) -> None:
        """Display the main settings menu options."""
        self.display.clear_screen()
        self.display.print_header("Settings Menu")

        print("\nSelect a category to configure:")
        print("1. Application Settings")
        print("2. Time Delays")
        print("3. Operation Limits")
        print("4. Proxy Settings")
        print("5. Encryption Settings")
        print("6. File Paths")
        print("7. Save All Changes")
        print("8. Reset to Defaults")
        print("9. Return to Main Menu")

    def _get_user_choice(self) -> str:
        """
        Get the user's menu choice.

        Returns:
            str: The user's menu choice.
        """
        return input(f"\n{self.colors.colorize('Enter your choice (1-9): ', self.colors.CYAN)}")

    def _handle_main_menu_choice(self, choice: str) -> None:
        """
        Handle the user's main menu choice.

        Args:
            choice (str): The user's menu choice.
        """
        if choice == '1':
            self._show_application_settings()
        elif choice == '2':
            self._show_time_delay_settings()
        elif choice == '3':
            self._show_operation_limit_settings()
        elif choice == '4':
            self._show_proxy_settings()
        elif choice == '5':
            self._show_encryption_settings()
        elif choice == '6':
            self._show_file_path_settings()
        elif choice == '7':
            self._save_all_changes()
        elif choice == '8':
            self._reset_to_defaults()
        elif choice == '9':
            self.exit_requested = True
        else:
            self.display.print_error(
                "Invalid choice. Please enter a number between 1 and 9.")
            input("\nPress Enter to continue...")

    def _show_application_settings(self) -> None:
        """Display and modify application settings."""
        while True:
            self.display.clear_screen()
            self.display.print_header("Application Settings")

            # Get current settings
            app_name = self.config.get('app_name', 'Telegram Account Manager')
            app_version = self.config.get('app_version', '1.0.0')
            debug_mode = self.config.get('debug_mode', False)

            # Display current settings
            print(f"\nCurrent Application Settings:")
            print(f"1. Application Name: {app_name}")
            print(f"2. Application Version: {app_version}")
            print(f"3. Debug Mode: {'Enabled' if debug_mode else 'Disabled'}")
            print("\n0. Back to Settings Menu")

            choice = input(
                f"\n{self.colors.colorize('Enter your choice (0-3): ', self.colors.CYAN)}")

            if choice == '0':
                break
            elif choice == '1':
                new_name = input("Enter new application name: ")
                if new_name.strip():
                    self.config.set('app_name', new_name)
                    self.display.print_success("Application name updated.")
            elif choice == '2':
                new_version = input("Enter new application version: ")
                if new_version.strip():
                    self.config.set('app_version', new_version)
                    self.display.print_success("Application version updated.")
            elif choice == '3':
                new_debug = input("Enable debug mode? (y/n): ").lower()
                if new_debug in ('y', 'n'):
                    self.config.set('debug_mode', new_debug == 'y')
                    self.display.print_success("Debug mode setting updated.")
            else:
                self.display.print_error("Invalid choice.")

            input("\nPress Enter to continue...")

    def _show_time_delay_settings(self) -> None:
        """Display and modify time delay settings."""
        while True:
            self.display.clear_screen()
            self.display.print_header("Time Delay Settings")

            # Get current settings
            default_delay = self.config.get(
                'default_delay', Constants.TimeDelays.DEFAULT)
            max_delay = self.config.get(
                'max_delay', Constants.TimeDelays.MAXIMUM)
            account_change_delay = self.config.get(
                'account_change_delay', Constants.TimeDelays.ACCOUNT_CHANGE)

            # Display current settings
            print(f"\nCurrent Time Delay Settings:")
            print(f"1. Default Delay: {default_delay} seconds")
            print(f"2. Maximum Delay: {max_delay} seconds")
            print(f"3. Account Change Delay: {account_change_delay} seconds")
            print("\n0. Back to Settings Menu")

            choice = input(
                f"\n{self.colors.colorize('Enter your choice (0-3): ', self.colors.CYAN)}")

            if choice == '0':
                break
            elif choice == '1':
                self._update_numeric_setting('default_delay', "Enter new default delay (seconds)",
                                             min_value=1, max_value=300)
            elif choice == '2':
                self._update_numeric_setting('max_delay', "Enter new maximum delay (seconds)",
                                             min_value=60, max_value=3600)
            elif choice == '3':
                self._update_numeric_setting(
                    'account_change_delay', "Enter new account change delay (seconds)",
                    min_value=10, max_value=600)
            else:
                self.display.print_error("Invalid choice.")

            input("\nPress Enter to continue...")

    def _show_operation_limit_settings(self) -> None:
        """Display and modify operation limit settings."""
        while True:
            self.display.clear_screen()
            self.display.print_header("Operation Limit Settings")

            # Get current settings
            max_retry_count = self.config.get(
                'max_retry_count', Constants.Limits.MAX_RETRY)
            max_failures = self.config.get(
                'max_failures_before_block', Constants.Limits.MAX_FAILURES)
            max_members_per_day = self.config.get(
                'max_members_per_day', Constants.Limits.MAX_MEMBERS_PER_DAY)
            max_memory_records = self.config.get(
                'max_memory_records', Constants.Limits.MAX_MEMORY_RECORDS)

            # Display current settings
            print(f"\nCurrent Operation Limit Settings:")
            print(f"1. Maximum Retry Count: {max_retry_count}")
            print(f"2. Maximum Failures Before Block: {max_failures}")
            print(f"3. Maximum Members Per Day: {max_members_per_day}")
            print(f"4. Maximum Memory Records: {max_memory_records}")
            print("\n0. Back to Settings Menu")

            choice = input(
                f"\n{self.colors.colorize('Enter your choice (0-4): ', self.colors.CYAN)}")

            if choice == '0':
                break
            elif choice == '1':
                self._update_numeric_setting('max_retry_count', "Enter new maximum retry count",
                                             min_value=1, max_value=20)
            elif choice == '2':
                self._update_numeric_setting('max_failures_before_block',
                                             "Enter new maximum failures before block",
                                             min_value=1, max_value=10)
            elif choice == '3':
                self._update_numeric_setting('max_members_per_day',
                                             "Enter new maximum members per day",
                                             min_value=10, max_value=100)
            elif choice == '4':
                self._update_numeric_setting('max_memory_records',
                                             "Enter new maximum memory records",
                                             min_value=100, max_value=10000)
            else:
                self.display.print_error("Invalid choice.")

            input("\nPress Enter to continue...")

    def _show_proxy_settings(self) -> None:
        """Display and modify proxy settings."""
        while True:
            self.display.clear_screen()
            self.display.print_header("Proxy Settings")

            # Get current settings
            use_proxy = self.config.get('use_proxy', False)
            default_proxy_type = self.config.get(
                'default_proxy_type', 'socks5')
            proxy_rotation_enabled = self.config.get(
                'proxy_rotation_enabled', False)
            proxy_rotation_interval = self.config.get(
                'proxy_rotation_interval', 3600)
            proxy_settings = self.config.get('proxy_settings', {})

            # Display current settings
            print(f"\nCurrent Proxy Settings:")
            print(f"1. Use Proxy: {'Enabled' if use_proxy else 'Disabled'}")
            print(f"2. Default Proxy Type: {default_proxy_type}")
            print(
                f"3. Proxy Rotation: {'Enabled' if proxy_rotation_enabled else 'Disabled'}")
            print(
                f"4. Proxy Rotation Interval: {proxy_rotation_interval} seconds")
            print(f"5. Configure Proxy Servers")
            print("\n0. Back to Settings Menu")

            choice = input(
                f"\n{self.colors.colorize('Enter your choice (0-5): ', self.colors.CYAN)}")

            if choice == '0':
                break
            elif choice == '1':
                new_use_proxy = input("Enable proxy usage? (y/n): ").lower()
                if new_use_proxy in ('y', 'n'):
                    self.config.set('use_proxy', new_use_proxy == 'y')
                    self.display.print_success("Proxy usage setting updated.")
            elif choice == '2':
                new_type = input(
                    "Enter default proxy type (socks5/http): ").lower()
                if new_type in ('socks5', 'http'):
                    self.config.set('default_proxy_type', new_type)
                    self.display.print_success("Default proxy type updated.")
                else:
                    self.display.print_error(
                        "Invalid proxy type. Use 'socks5' or 'http'.")
            elif choice == '3':
                new_rotation = input("Enable proxy rotation? (y/n): ").lower()
                if new_rotation in ('y', 'n'):
                    self.config.set('proxy_rotation_enabled',
                                    new_rotation == 'y')
                    self.display.print_success(
                        "Proxy rotation setting updated.")
            elif choice == '4':
                self._update_numeric_setting('proxy_rotation_interval',
                                             "Enter new rotation interval (seconds)",
                                             min_value=300, max_value=86400)
            elif choice == '5':
                self._configure_proxy_servers()
            else:
                self.display.print_error("Invalid choice.")

            input("\nPress Enter to continue...")

    def _configure_proxy_servers(self) -> None:
        """Configure proxy server settings."""
        while True:
            self.display.clear_screen()
            self.display.print_header("Proxy Server Configuration")

            # Get current proxy settings
            proxy_settings = self.config.get('proxy_settings', {})

            # Display current proxies
            print("\nCurrent Proxy Servers:")
            if not proxy_settings:
                print("No proxy servers configured.")
            else:
                for i, (name, proxy) in enumerate(proxy_settings.items(), 1):
                    addr = proxy.get('addr', '')
                    port = proxy.get('port', 0)
                    proxy_type = proxy.get('proxy_type', 'socks5')
                    has_auth = bool(proxy.get('username'))
                    print(
                        f"{i}. {name}: {proxy_type}://{addr}:{port} {'(Auth)' if has_auth else ''}")

            print("\n1. Add New Proxy")
            print("2. Edit Existing Proxy")
            print("3. Remove Proxy")
            print("0. Back to Proxy Settings")

            choice = input(
                f"\n{self.colors.colorize('Enter your choice (0-3): ', self.colors.CYAN)}")

            if choice == '0':
                break
            elif choice == '1':
                self._add_new_proxy()
            elif choice == '2':
                self._edit_existing_proxy()
            elif choice == '3':
                self._remove_proxy()
            else:
                self.display.print_error("Invalid choice.")

            input("\nPress Enter to continue...")

    def _add_new_proxy(self) -> None:
        """Add a new proxy server configuration."""
        self.display.clear_screen()
        self.display.print_header("Add New Proxy")

        name = input("Enter proxy name (e.g., 'default', 'backup1'): ")
        if not name or name.strip() == "":
            self.display.print_error("Proxy name cannot be empty.")
            return

        # Get current proxy settings
        proxy_settings = self.config.get('proxy_settings', {})

        # Check if name already exists
        if name in proxy_settings:
            overwrite = input(
                f"Proxy '{name}' already exists. Overwrite? (y/n): ").lower()
            if overwrite != 'y':
                self.display.print_message("Operation canceled.")
                return

        # Get proxy details
        proxy_type = input(
            "Enter proxy type (socks5/http) [socks5]: ").lower() or 'socks5'
        if proxy_type not in ('socks5', 'http'):
            self.display.print_error("Invalid proxy type. Using 'socks5'.")
            proxy_type = 'socks5'

        addr = input("Enter proxy server address: ")
        if not addr or addr.strip() == "":
            self.display.print_error("Proxy address cannot be empty.")
            return

        port_str = input("Enter proxy server port [1080]: ") or '1080'
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError("Port out of range")
        except ValueError:
            self.display.print_error(
                "Invalid port number. Using default 1080.")
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
        proxy_settings[name] = proxy_config
        self.config.set('proxy_settings', proxy_settings)

        # If this is the first proxy, enable proxy usage
        if len(proxy_settings) == 1:
            self.config.set('use_proxy', True)

        self.display.print_success(f"Proxy '{name}' added successfully.")

    def _edit_existing_proxy(self) -> None:
        """Edit an existing proxy server configuration."""
        self.display.clear_screen()
        self.display.print_header("Edit Existing Proxy")

        # Get current proxy settings
        proxy_settings = self.config.get('proxy_settings', {})

        if not proxy_settings:
            self.display.print_error("No proxy servers configured.")
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
            self.display.print_error("Invalid selection.")
            return

        proxy_name = proxy_names[proxy_index - 1]
        proxy = proxy_settings[proxy_name]

        # Edit proxy details
        print(f"\nEditing proxy '{proxy_name}':")

        proxy_type = input(
            f"Enter proxy type (socks5/http) [{
                proxy.get('proxy_type', 'socks5')}]: ").lower() or proxy.get('proxy_type', 'socks5')
        if proxy_type not in ('socks5', 'http'):
            self.display.print_error(
                "Invalid proxy type. Using previous value.")
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
            self.display.print_error(
                "Invalid port number. Using previous value.")
            port = proxy.get('port', 1080)

        current_has_auth = bool(proxy.get('username'))
        use_auth = input(f"Does this proxy require authentication? (y/n) [{
            'y' if current_has_auth else 'n'}]: ").lower(
        ) or ('y' if current_has_auth else 'n')

        username = proxy.get('username', '')
        password = proxy.get('password', '')
        if use_auth == 'y':
            username = input(
                f"Enter proxy username [{username}]: ") or username
            password = input(
                f"Enter proxy password [{password}]: ") or password
        else:
            username = ""
            password = ""

        current_rdns = proxy.get('rdns', True)
        rdns = input(f"Use remote DNS resolution? (y/n) [{
            'y' if current_rdns else 'n'}]: ").lower() or ('y' if current_rdns else 'n')

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
        self.config.set('proxy_settings', proxy_settings)

        self.display.print_success(
            f"Proxy '{proxy_name}' updated successfully.")

    def _remove_proxy(self) -> None:
        """Remove an existing proxy server configuration."""
        self.display.clear_screen()
        self.display.print_header("Remove Proxy")

        # Get current proxy settings
        proxy_settings = self.config.get('proxy_settings', {})

        if not proxy_settings:
            self.display.print_error("No proxy servers configured.")
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
            self.display.print_error("Invalid selection.")
            return

        proxy_name = proxy_names[proxy_index - 1]

        # Confirm removal
        confirm = input(
            f"Are you sure you want to remove proxy '{proxy_name}'? (y/n): ").lower()
        if confirm != 'y':
            self.display.print_message("Operation canceled.")
            return

        # Remove proxy
        del proxy_settings[proxy_name]
        self.config.set('proxy_settings', proxy_settings)

        # If no proxies left, disable proxy usage
        if not proxy_settings:
            self.config.set('use_proxy', False)

        self.display.print_success(
            f"Proxy '{proxy_name}' removed successfully.")

    def _show_encryption_settings(self) -> None:
        """Display and modify encryption settings."""
        while True:
            self.display.clear_screen()
            self.display.print_header("Encryption Settings")

            # Get current settings
            encryption_enabled = self.config.get('encryption_enabled', True)
            encryption_algorithm = self.config.get(
                'encryption_algorithm', 'fernet')
            encryption_required = self.config.get(
                'encryption_required_for_sensitive_data', True)

            # Display current settings
            print(f"\nCurrent Encryption Settings:")
            print(
                f"1. Encryption Enabled: {'Yes' if encryption_enabled else 'No'}")
            print(f"2. Encryption Algorithm: {encryption_algorithm}")
            print(f"3. Require Encryption for Sensitive Data: {
                'Yes' if encryption_required else 'No'}")
            print("\n0. Back to Settings Menu")

            choice = input(
                f"\n{self.colors.colorize('Enter your choice (0-3): ', self.colors.CYAN)}")

            if choice == '0':
                break
            elif choice == '1':
                new_value = input("Enable encryption? (y/n): ").lower()
                if new_value in ('y', 'n'):
                    self.config.set('encryption_enabled', new_value == 'y')
                    self.display.print_success("Encryption setting updated.")
            elif choice == '2':
                self.display.print_message(
                    "Currently only 'fernet' encryption is supported.")
                input("\nPress Enter to continue...")
            elif choice == '3':
                new_value = input(
                    "Require encryption for sensitive data? (y/n): ").lower()
                if new_value in ('y', 'n'):
                    self.config.set(
                        'encryption_required_for_sensitive_data', new_value == 'y')
                    self.display.print_success(
                        "Encryption requirement setting updated.")
            else:
                self.display.print_error("Invalid choice.")

            if choice != '2':  # Skip input for option 2 as it already has one
                input("\nPress Enter to continue...")

    def _show_file_path_settings(self) -> None:
        """Display and modify file path settings."""
        while True:
            self.display.clear_screen()
            self.display.print_header("File Path Settings")

            # Get current settings
            log_file = self.config.get('log_file', 'telegram_adder.log')
            request_log_file = self.config.get(
                'request_log_file', 'request_log.json')
            ai_data_file = self.config.get(
                'ai_data_file', 'ai_training_data.json')
            accounts_file = self.config.get(
                'accounts_file', 'telegram_accounts.json')

            # Display current settings
            print(f"\nCurrent File Path Settings:")
            print(f"1. Log File: {log_file}")
            print(f"2. Request Log File: {request_log_file}")
            print(f"3. AI Data File: {ai_data_file}")
            print(f"4. Accounts File: {accounts_file}")
            print("\n0. Back to Settings Menu")

            choice = input(
                f"\n{self.colors.colorize('Enter your choice (0-4): ', self.colors.CYAN)}")

            if choice == '0':
                break
            elif choice == '1':
                new_path = input(
                    f"Enter new log file path [{log_file}]: ") or log_file
                self.config.set('log_file', new_path)
                self.display.print_success("Log file path updated.")
            elif choice == '2':
                new_path = input(
                    f"Enter new request log file path [{request_log_file}]: ") or request_log_file
                self.config.set('request_log_file', new_path)
                self.display.print_success("Request log file path updated.")
            elif choice == '3':
                new_path = input(
                    f"Enter new AI data file path [{ai_data_file}]: ") or ai_data_file
                self.config.set('ai_data_file', new_path)
                self.display.print_success("AI data file path updated.")
            elif choice == '4':
                new_path = input(
                    f"Enter new accounts file path [{accounts_file}]: ") or accounts_file
                self.config.set('accounts_file', new_path)
                self.display.print_success("Accounts file path updated.")
            else:
                self.display.print_error("Invalid choice.")

            input("\nPress Enter to continue...")

    def _update_numeric_setting(self, setting_name: str, prompt: str,
                                min_value: int = 0, max_value: int = sys.maxsize) -> None:
        """
        Update a numeric configuration setting with validation.

        Args:
            setting_name (str): The name of the setting to update.
            prompt (str): The prompt to display to the user.
            min_value (int): The minimum allowed value.
            max_value (int): The maximum allowed value.
        """
        current_value = self.config.get(setting_name, 0)
        new_value_str = input(
            f"{prompt} [{current_value}]: ") or str(current_value)

        try:
            new_value = int(new_value_str)
            if new_value < min_value or new_value > max_value:
                self.display.print_error(
                    f"Value must be between {min_value} and {max_value}.")
                return

            self.config.set(setting_name, new_value)
            self.display.print_success(
                f"{setting_name} updated to {new_value}.")
        except ValueError:
            self.display.print_error("Please enter a valid number.")
            return
