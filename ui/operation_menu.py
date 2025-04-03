"""
Operation Menu Module

This module provides the user interface for configuring and executing
member transfer operations between Telegram groups. It allows users to:
- Select source and destination groups
- Configure operation parameters
- Execute member transfer operations
- Monitor progress and results
- Save and load operation configurations

It integrates with the account_manager, session_manager, and various
transfer strategies to provide a comprehensive interface for member management.
"""

import os
import time
import logging
import threading
from datetime import datetime
from typing import Optional, Any, Dict

# Try to import logging system
try:
    from logging_.logging_manager import get_logger
    logger = get_logger("OperationMenu")
except ImportError:
    # Fallback logger
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("OperationMenu")

# Try to import UI utilities
try:
    from ui.colors import Colors
    from ui.display import (
        Display, clear_screen, print_banner, print_header,
        print_success, print_error, print_info
    )
    has_ui_utils = True
except ImportError:
    has_ui_utils = False
    # Define fallback classes

    class Colors:
        """Fallback Colors class."""
        RESET = BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ""
        BG_BLACK = BG_RED = BG_GREEN = BG_YELLOW = BG_BLUE = BG_MAGENTA = BG_CYAN = BG_WHITE = ""

    class Display:
        """Fallback Display class."""
        @staticmethod
        def clear_screen():
            os.system('cls' if os.name == 'nt' else 'clear')

        @staticmethod
        def print_header(title):
            print(f"\n--- {title} ---\n")

        @staticmethod
        def print_info(message):
            print(f"INFO: {message}")

        @staticmethod
        def print_error(message):
            print(f"ERROR: {message}")

        @staticmethod
        def print_success(message):
            print(f"SUCCESS: {message}")

        @staticmethod
        def get_input(prompt):
            return input(prompt)

        @staticmethod
        def print_item(message):
            print(f"- {message}")

    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_banner(text, width=None, style='double'):
        print(f"\n{'=' * 50}\n{text}\n{'=' * 50}\n")

    def print_header(text, width=None, char='=', centered=True):
        print(f"\n{char * 10} {text} {char * 10}\n")

    def print_success(message, details=None):
        print(f"SUCCESS: {message}")
        if details:
            print(f"  {details}")

    def print_error(message, details=None):
        print(f"ERROR: {message}")
        if details:
            print(f"  {details}")

    def print_info(message, details=None):
        print(f"INFO: {message}")
        if details:
            print(f"  {details}")

# Import menu system and utilities
try:
    from ui.menu_system import Menu, MenuItem, MenuSystem, create_action_item, create_submenu_item
except ImportError:
    # Define fallback classes for Menu System
    class Menu:
        def __init__(self, title, parent=None):
            self.title = title
            self.parent = parent
            self.items = []

        def add_item(self, item):
            self.items.append(item)
            return self

    class MenuItem:
        def __init__(self, key, title, action=None, item_type=None, submenu=None):
            self.key = key
            self.title = title
            self.action = action
            self.item_type = item_type
            self.submenu = submenu

    class MenuSystem:
        def __init__(self):
            self.menus = {}
            self.current_menu = None

        def add_menu(self, name, menu):
            self.menus[name] = menu
            return self

        def show_menu(self, name):
            self.current_menu = self.menus.get(name)
            return self.current_menu

    def create_action_item(key, title, action, **kwargs):
        return MenuItem(key, title, action)

    def create_submenu_item(key, title, submenu, **kwargs):
        return MenuItem(key, title, submenu=submenu)

# Import other utilities
try:
    from utils.app_context import get_app_context
except ImportError:
    # Fallback implementation
    def get_app_context():
        return None

# Define a progress bar class for command line progress display


class ProgressBar:
    def __init__(self, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
        """
        Initialize progress bar parameters
        """
        self.total = total
        self.prefix = prefix
        self.suffix = suffix
        self.decimals = decimals
        self.length = length
        self.fill = fill
        self.print_end = print_end
        self.current = 0

    def update(self, current):
        """
        Update the progress bar with current progress
        """
        self.current = current
        self._print()

    def _print(self):
        """
        Print the progress bar
        """
        percent = ("{0:." + str(self.decimals) + "f}").format(100 *
                                                              (self.current / float(self.total)))
        filled_length = int(self.length * self.current // self.total)
        bar = self.fill * filled_length + '-' * (self.length - filled_length)
        print(f'\r{self.prefix} |{bar}| {percent}% {self.suffix}',
              end=self.print_end)
        if self.current == self.total:
            print()

# Define a status indicator for command line animations


class StatusIndicator:
    def __init__(self, message="Processing"):
        """
        Initialize status indicator
        """
        self.message = message
        self.running = False
        self._thread = None

    def start(self):
        """
        Start the spinning indicator
        """
        self.running = True
        self._thread = threading.Thread(target=self._animate)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        """
        Stop the spinning indicator
        """
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        print("\r" + " " * (len(self.message) + 10) + "\r", end="")

    def _animate(self):
        """
        Animation function for the spinning indicator
        """
        chars = "|/-\\"
        idx = 0
        while self.running:
            print(f"\r{self.message} {chars[idx % len(chars)]}", end="")
            idx += 1
            time.sleep(0.1)


class OperationMenu:
    """
    Menu for configuring and executing member transfer operations.

    This class provides a user interface for:
    - Setting up source and destination groups
    - Configuring transfer parameters
    - Selecting transfer strategies
    - Starting and monitoring operations
    - Reviewing results and reports
    - Managing and resuming interrupted operations
    """

    def __init__(self, menu_system=None, account_manager=None, session_manager=None, strategy_selector=None):
        """
        Initialize the operation menu.

        Args:
            menu_system: The main menu system for navigation
            account_manager: Account manager instance for account operations
            session_manager: Session manager for state persistence
            strategy_selector: Strategy selector for choosing transfer strategies
        """
        self.menu_system = menu_system
        self.display = Display() if has_ui_utils else Display()

        # Try to get services from app context if not provided
        app_context = get_app_context()
        if app_context:
            if account_manager is None and app_context.has_service('account_manager'):
                account_manager = app_context.get_service('account_manager')
            if session_manager is None and app_context.has_service('session_manager'):
                session_manager = app_context.get_service('session_manager')
            if strategy_selector is None and app_context.has_service('strategy_selector'):
                strategy_selector = app_context.get_service(
                    'strategy_selector')
            # Get config from context
            self.config = app_context.get_service(
                'config') if app_context.has_service('config') else None
        else:
            self.config = None

        # Store services
        self.account_manager = account_manager
        self.session_manager = session_manager
        self.strategy_selector = strategy_selector

        # Current operation state
        self.current_operation = None
        self.source_group = None
        self.target_group = None
        self.member_limit = 20  # Default limit
        self.selected_strategy = "sequential"
        self.selected_accounts = []

        # Operation results
        self.last_operation_results = None

        # Create operation menus
        if menu_system:
            self.create_menus()

        # Logger for this class
        self.logger = logger

    def create_menus(self):
        """Create all menus related to operations."""
        if not self.menu_system:
            logger.warning("No menu system provided, skipping menu creation")
            return

        # Main operation menu
        operation_menu = Menu("Member Transfer Operations")
        operation_menu.add_item(create_action_item(
            "1", "Select Source Group", self.select_source_group))
        operation_menu.add_item(create_action_item(
            "2", "Select Target Group", self.select_target_group))
        operation_menu.add_item(create_action_item(
            "3", "Configure Operation Parameters", self.configure_parameters))
        operation_menu.add_item(create_action_item(
            "4", "Select Transfer Strategy", self.select_strategy))
        operation_menu.add_item(create_action_item(
            "5", "Select Accounts", self.select_accounts))
        operation_menu.add_item(create_action_item(
            "6", "Start Operation", self.start_operation))
        operation_menu.add_item(create_action_item(
            "7", "Resume Interrupted Operation", self.resume_operation))
        operation_menu.add_item(create_action_item(
            "8", "View Last Operation Results", self.view_results))
        operation_menu.add_item(create_action_item(
            "b", "Back to Main Menu", self.back_to_main_menu))

        # Strategy selection menu
        strategy_menu = Menu("Select Transfer Strategy")
        strategy_menu.add_item(create_action_item(
            "1", "Sequential (One account at a time)",
            lambda: self._set_strategy("sequential")))
        strategy_menu.add_item(create_action_item(
            "2", "Parallel Low (2-3 accounts)",
            lambda: self._set_strategy("parallel_low")))
        strategy_menu.add_item(create_action_item(
            "3", "Parallel Medium (4-6 accounts)",
            lambda: self._set_strategy("parallel_medium")))
        strategy_menu.add_item(create_action_item(
            "4", "Parallel High (7+ accounts)",
            lambda: self._set_strategy("parallel_high")))
        strategy_menu.add_item(create_action_item(
            "5", "Distributed Cautious (24/7 Operation)",
            lambda: self._set_strategy("distributed_cautious")))
        strategy_menu.add_item(create_action_item(
            "b", "Back to Operation Menu",
            lambda: self.menu_system.show_menu("operation_menu")))

        # Add menus to menu system
        self.menu_system.add_menu("operation_menu", operation_menu)
        self.menu_system.add_menu("strategy_menu", strategy_menu)

    def show(self):
        """Show the operation menu."""
        if self.menu_system:
            return self.menu_system.show_menu("operation_menu")
        else:
            self.display.print_error("Menu system not available")
            return None

    def create_menu(self, parent_menu):
        """
        Create the operation menu.

        Args:
            parent_menu: The parent menu.

        Returns:
            The operation menu.
        """
        operation_menu = Menu("Member Transfer Operations", parent=parent_menu)

        operation_menu.add_item(create_action_item(
            "1", "Select Source Group", self.select_source_group))
        operation_menu.add_item(create_action_item(
            "2", "Select Target Group", self.select_target_group))
        operation_menu.add_item(create_action_item(
            "3", "Configure Operation Parameters", self.configure_parameters))
        operation_menu.add_item(create_action_item(
            "4", "Select Transfer Strategy", self.select_strategy))
        operation_menu.add_item(create_action_item(
            "5", "Select Accounts", self.select_accounts))
        operation_menu.add_item(create_action_item(
            "6", "Start Operation", self.start_operation))
        operation_menu.add_item(create_action_item(
            "7", "Resume Interrupted Operation", self.resume_operation))
        operation_menu.add_item(create_action_item(
            "8", "View Last Operation Results", self.view_results))

        return operation_menu

    def select_source_group(self):
        """Interactive selection of the source group."""
        self.display.clear_screen()
        self.display.print_header("Select Source Group")

        # Check if accounts are available
        if not self._check_accounts_available():
            return

        # Currently a placeholder - in a full implementation, this would:
        # 1. Get a list of available groups from Telegram
        # 2. Display them to the user for selection
        # 3. Store the selected group for the operation

        # Mock implementation for now
        print("This would connect to Telegram and show a list of available groups.")
        print("Currently this is just a placeholder.")

        group_id = self.display.get_input(
            "\nEnter group ID or link (or leave empty to cancel): ")

        if group_id.strip():
            # Simple mock implementation
            self.source_group = {"id": group_id, "title": f"Group {group_id}"}
            self.display.print_success(
                f"Selected source group: {self.source_group['title']}")

            # Save to session if available
            if self.current_operation:
                self.current_operation.set_custom_data(
                    "source_group", self.source_group)

        input("\nPress Enter to continue...")

    def select_target_group(self):
        """Interactive selection of the target group."""
        self.display.clear_screen()
        self.display.print_header("Select Target Group")

        # Check if accounts are available
        if not self._check_accounts_available():
            return

        # Mock implementation for now
        print("This would connect to Telegram and show a list of available groups.")
        print("Currently this is just a placeholder.")

        group_id = self.display.get_input(
            "\nEnter group ID or link (or leave empty to cancel): ")

        if group_id.strip():
            # Simple mock implementation
            self.target_group = {"id": group_id, "title": f"Group {group_id}"}
            self.display.print_success(
                f"Selected target group: {self.target_group['title']}")

            # Save to session if available
            if self.current_operation:
                self.current_operation.set_custom_data(
                    "target_group", self.target_group)

        input("\nPress Enter to continue...")

    def configure_parameters(self):
        """
        Configure operation parameters.

        This method allows the user to set various parameters for the operation,
        such as the number of members to transfer, delay between requests, etc.
        """
        self.display.clear_screen()
        self.display.print_header("Configure Operation Parameters")

        # Display current configuration
        self._display_current_configuration()

        # Parameters to configure
        parameters = [
            ("member_limit", "Number of members to transfer", int),
            ("delay", "Delay between requests (seconds)", int),
            ("max_retries", "Maximum retry attempts", int),
            ("timeout", "Operation timeout (minutes)", int),
        ]

        # Configure each parameter
        for param_key, param_desc, param_type in parameters:
            current_value = None
            if self.current_operation:
                current_value = self.current_operation.get_custom_data(
                    param_key)

            if param_key == "member_limit":
                # Direct assignment to instance variable for member_limit
                if self.member_limit:
                    current_value = self.member_limit

            value_str = str(current_value) if current_value is not None else ""

            user_input = self.display.get_input(
                f"\n{param_desc} [{value_str}]: "
            )

            if user_input.strip():
                try:
                    value = param_type(user_input)

                    # Basic validation
                    if param_key == "member_limit" and value <= 0:
                        self.display.print_error(
                            "Number of members must be greater than zero.")
                        continue
                    elif param_key == "delay" and value < 0:
                        self.display.print_error("Delay cannot be negative.")
                        continue

                    # Store the parameter
                    if param_key == "member_limit":
                        self.member_limit = value

                    # Save to session
                    if self.current_operation:
                        self.current_operation.set_custom_data(
                            param_key, value)
                        logger.info(f"Parameter {param_key} set to {value}")

                    self.display.print_success(f"{param_desc} set to {value}")
                except ValueError:
                    self.display.print_error(
                        f"Invalid value. Expected {param_type.__name__}.")

        # Save operation state
        self._save_operation_state()

        input("\nPress Enter to continue...")

    def select_strategy(self):
        """Show the strategy selection menu."""
        if self.menu_system:
            self.menu_system.show_menu("strategy_menu")
        else:
            self.display.clear_screen()
            self.display.print_header("Select Transfer Strategy")

            print("1. Sequential (One account at a time)")
            print("2. Parallel Low (2-3 accounts)")
            print("3. Parallel Medium (4-6 accounts)")
            print("4. Parallel High (7+ accounts)")
            print("5. Distributed Cautious (24/7 Operation)")
            print("0. Back")

            choice = self.display.get_input("\nSelect a strategy: ")

            strategy_map = {
                "1": "sequential",
                "2": "parallel_low",
                "3": "parallel_medium",
                "4": "parallel_high",
                "5": "distributed_cautious"
            }

            if choice in strategy_map:
                self._set_strategy(strategy_map[choice])

    def _set_strategy(self, strategy):
        """
        Set the selected transfer strategy.

        Args:
            strategy: Strategy type to use
        """
        self.selected_strategy = strategy

        # Save to session
        if self.current_operation:
            self.current_operation.set_custom_data("strategy", strategy)
            logger.info(f"Strategy set to {strategy}")

        self.display.print_success(f"Selected strategy: {strategy}")
        input("\nPress Enter to continue...")

        # Return to operation menu
        if self.menu_system:
            self.menu_system.show_menu("operation_menu")

    def select_accounts(self):
        """
        Select accounts to use for the operation.

        This method allows the user to select which accounts to use for
        the member transfer operation.
        """
        self.display.clear_screen()
        self.display.print_header("Select Accounts for Operation")

        # Check if account manager is available
        if not self.account_manager:
            self.display.print_error("Account manager not available.")
            input("\nPress Enter to continue...")
            return

        # Get all accounts
        accounts = self.account_manager.get_all_accounts()

        if not accounts:
            self.display.print_error(
                "No accounts found. Please add accounts first.")
            input("\nPress Enter to continue...")
            return

        # Display accounts with selection status
        self.display.print_header("\nAvailable Accounts:")
        for i, account in enumerate(accounts, 1):
            # Determine if account is already selected
            account_id = account.get("id", "")
            selected = "✓" if account_id in self.selected_accounts else " "
            status = account.get("status", "unknown")

            # Get status color if available
            status_color = self._get_status_color(status)

            # Display account info
            self.display.print_item(
                f"{i}. [{selected}] Phone: {account.get('phone', 'Unknown')} - "
                f"Status: {status_color}{status}{Colors.RESET} - "
                f"Added Today: {account.get('members_added_today', 0)}"
            )

        # Selection options
        print("\nOptions:")
        print("  Enter account number to toggle selection")
        print("  A: Select all accounts")
        print("  C: Clear selection")
        print("  S: Save selection and return")
        print("  0: Cancel and return")

        # Get user input
        while True:
            selection = self.display.get_input(
                "\nEnter your choice: ").strip().upper()

            if selection == '0':
                return
            elif selection == 'A':
                self.selected_accounts = [account.get(
                    "id", "") for account in accounts]
                self.display.print_success("All accounts selected.")
                break
            elif selection == 'C':
                self.selected_accounts = []
                self.display.print_success("Selection cleared.")
                break
            elif selection == 'S':
                break
            elif selection.isdigit():
                index = int(selection) - 1
                if 0 <= index < len(accounts):
                    account_id = accounts[index].get("id", "")
                    if account_id in self.selected_accounts:
                        self.selected_accounts.remove(account_id)
                        self.display.print_info(
                            f"Account {accounts[index].get('phone', 'Unknown')} removed from selection.")
                    else:
                        self.selected_accounts.append(account_id)
                        self.display.print_info(
                            f"Account {accounts[index].get('phone', 'Unknown')} added to selection.")
                else:
                    self.display.print_error("Invalid account number.")
            else:
                self.display.print_error("Invalid option.")

        # Save to session
        if self.current_operation:
            self.current_operation.set_custom_data(
                "selected_accounts", self.selected_accounts)
            logger.info(
                f"Selected {len(self.selected_accounts)} accounts for operation")

        self.display.print_success(
            f"Selected {len(self.selected_accounts)} accounts for operation.")
        input("\nPress Enter to continue...")

    def start_operation(self):
        """
        Start the member transfer operation.

        This method validates the operation parameters, confirms with the user,
        and starts the transfer process using the selected strategy.
        """
        self.display.clear_screen()
        self.display.print_header("Start Member Transfer Operation")

        # Check if everything is configured properly
        validation_result = self._validate_operation_settings()
        if not validation_result[0]:
            self.display.print_error(
                f"Cannot start operation: {validation_result[1]}")
            input("\nPress Enter to continue...")
            return

        # Display operation summary
        self._display_operation_summary()

        # Get user confirmation
        confirmation = self.display.get_input(
            "\nDo you want to start the operation? (y/n): ").strip().lower()
        if confirmation != 'y':
            self.display.print_info("Operation cancelled.")
            input("\nPress Enter to continue...")
            return

        # Start a mock operation for demo purposes
        self.display.print_info("Starting operation...")
        print("This is a placeholder for the actual operation.")
        print("In a complete implementation, this would:")
        print("1. Initialize the selected strategy")
        print("2. Extract members from the source group")
        print("3. Add them to the target group")
        print("4. Track and display progress")

        # Mock progress display
        total = self.member_limit
        progress_bar = ProgressBar(
            total=total, prefix='Progress:', suffix='Complete', length=50)

        for i in range(total + 1):
            progress_bar.update(i)
            time.sleep(0.1)  # Simulate processing time

        # Mock results
        self.last_operation_results = {
            "status": "completed",
            "processed": total,
            "success_count": int(total * 0.8),  # 80% success rate for demo
            "failure_count": int(total * 0.2),  # 20% failure rate for demo
            "completion_time": total * 0.1  # Simulated completion time
        }

        self.display.print_success("\nOperation completed!")
        self.display.print_info(
            f"Processed: {self.last_operation_results['processed']} members")
        self.display.print_info(
            f"Success: {self.last_operation_results['success_count']} members")
        self.display.print_info(
            f"Failed: {self.last_operation_results['failure_count']} members")

        input("\nPress Enter to continue...")

    def resume_operation(self):
        """
        Resume an interrupted operation.

        This method looks for interrupted operations in the session manager
        and allows the user to resume them.
        """
        self.display.clear_screen()
        self.display.print_header("Resume Interrupted Operation")

        # Check if session manager is available
        if not self.session_manager:
            self.display.print_error("Session manager not available.")
            input("\nPress Enter to continue...")
            return

        # Mock implementation for now
        print("This would check for interrupted operations and allow resuming them.")
        print("Currently this is just a placeholder.")

        self.display.print_info("No interrupted operations found.")
        input("\nPress Enter to continue...")

    def view_results(self):
        """View the results of the last operation."""
        self.display.clear_screen()
        self.display.print_header("Last Operation Results")

        if not self.last_operation_results:
            self.display.print_info("No operation results available.")
            input("\nPress Enter to continue...")
            return

        # Format and display results
        results = self.last_operation_results
        self.display.print_info(
            f"Operation Status: {results.get('status', 'Unknown')}")
        self.display.print_info(
            f"Processed Members: {results.get('processed', 0)}")
        self.display.print_info(
            f"Successful: {results.get('success_count', 0)}")
        self.display.print_info(f"Failed: {results.get('failure_count', 0)}")

        completion_time = results.get('completion_time', 0)
        self.display.print_info(
            f"Completion Time: {completion_time:.2f} seconds")

        if 'error' in results:
            self.display.print_error(f"Error: {results['error']}")

        input("\nPress Enter to continue...")

    def back_to_main_menu(self):
        """Return to the main menu."""
        return "BACK"

    def _check_accounts_available(self):
        """Check if accounts are available for operations."""
        if not self.account_manager:
            self.display.print_error("Account manager not available.")
            input("\nPress Enter to continue...")
            return False

        accounts = self.account_manager.get_all_accounts()
        if not accounts:
            self.display.print_error(
                "No accounts found. Please add accounts first.")
            input("\nPress Enter to continue...")
            return False

        return True

    def _validate_operation_settings(self):
        """
        Validate operation settings.

        Returns:
            Tuple containing:
            - Boolean indicating if settings are valid
            - Error message if invalid
        """
        if not self.source_group:
            return False, "Source group not selected"

        if not self.target_group:
            return False, "Target group not selected"

        if isinstance(self.source_group, dict) and isinstance(self.target_group, dict):
            if self.source_group.get("id") == self.target_group.get("id"):
                return False, "Source and target groups cannot be the same"

        if not self.member_limit or self.member_limit <= 0:
            return False, "Invalid member limit"

        if not self.selected_strategy:
            return False, "Transfer strategy not selected"

        if not self.selected_accounts:
            return False, "No accounts selected for operation"

        return True, ""

    def _display_current_configuration(self):
        """Display the current operation configuration."""
        print("\nCurrent Configuration:")

        source_title = "Not selected"
        if self.source_group:
            if isinstance(self.source_group, dict):
                source_title = self.source_group.get("title", "Unknown")
            else:
                source_title = getattr(self.source_group, "title", "Unknown")

        target_title = "Not selected"
        if self.target_group:
            if isinstance(self.target_group, dict):
                target_title = self.target_group.get("title", "Unknown")
            else:
                target_title = getattr(self.target_group, "title", "Unknown")

        print(f"Source Group: {source_title}")
        print(f"Target Group: {target_title}")
        print(f"Member Limit: {self.member_limit}")
        print(f"Strategy: {self.selected_strategy}")
        print(f"Selected Accounts: {len(self.selected_accounts)}")

    def _display_operation_summary(self):
        """Display a summary of the operation to be started."""
        print("\nOperation Summary:")

        source_title = "Unknown"
        if self.source_group:
            if isinstance(self.source_group, dict):
                source_title = self.source_group.get("title", "Unknown")
            else:
                source_title = getattr(self.source_group, "title", "Unknown")

        target_title = "Unknown"
        if self.target_group:
            if isinstance(self.target_group, dict):
                target_title = self.target_group.get("title", "Unknown")
            else:
                target_title = getattr(self.target_group, "title", "Unknown")

        print(f"From: {source_title}")
        print(f"To: {target_title}")
        print(f"Members to transfer: {self.member_limit}")
        print(f"Strategy: {self.selected_strategy}")
        print(f"Using {len(self.selected_accounts)} accounts")

    def _get_status_color(self, status):
        """Get color code for account status."""
        status_colors = {
            "active": Colors.GREEN,
            "cooldown": Colors.YELLOW,
            "blocked": Colors.RED,
            "unverified": Colors.MAGENTA,
            "daily_limit_reached": Colors.CYAN
        }

        return status_colors.get(status.lower(), "")

    def _save_operation_state(self):
        """Save the current operation state to the session."""
        if not self.current_operation:
            return

        # Update operation state in session
        self.current_operation.update_state({
            "source_group": self.source_group,
            "target_group": self.target_group,
            "member_limit": self.member_limit,
            "strategy": self.selected_strategy,
            "selected_accounts": self.selected_accounts
        })

        logger.debug("Saved operation state to session")

    def _create_operation_session(self):
        """Create a new session for the operation."""
        if not self.session_manager:
            logger.warning(
                "Session manager not available, cannot create session")
            return None

        # Create session with operation data
        session = self.session_manager.create_session(
            session_type="member_transfer"
        )

        if session:
            # Set common data
            session.set_custom_data("operation_type", "member_transfer")
            session.set_custom_data("created_at", datetime.now().isoformat())

            # Set specific operation data
            if self.source_group:
                session.set_custom_data("source_group", self.source_group)
            if self.target_group:
                session.set_custom_data("target_group", self.target_group)

            session.set_custom_data("member_limit", self.member_limit)
            session.set_custom_data("strategy", self.selected_strategy)
            session.set_custom_data(
                "selected_accounts", self.selected_accounts)

            logger.info(f"Created new operation session: {session.session_id}")

            return session
        else:
            logger.error("Failed to create operation session")
            return None

    def _load_operation_state(self, session):
        """Load operation state from a session."""
        if not session:
            return

        # Load source group
        self.source_group = session.get_custom_data("source_group")

        # Load target group
        self.target_group = session.get_custom_data("target_group")

        # Load other settings
        self.member_limit = session.get_custom_data("member_limit", 20)
        self.selected_strategy = session.get_custom_data(
            "strategy", "sequential")
        self.selected_accounts = session.get_custom_data(
            "selected_accounts", [])

        logger.info("Loaded operation state from session")


def create_operation_menu(parent_menu=None):
    """
    Create and return the operation menu.

    Args:
        parent_menu: The parent menu.

    Returns:
        The operation menu instance
    """
    # Get the app_context
    app_context = get_app_context()

    # Get required services
    account_manager = None
    session_manager = None
    strategy_selector = None

    if app_context:
        if app_context.has_service('account_manager'):
            account_manager = app_context.get_service('account_manager')
        if app_context.has_service('session_manager'):
            session_manager = app_context.get_service('session_manager')
        if app_context.has_service('strategy_selector'):
            strategy_selector = app_context.get_service('strategy_selector')

    # Create the menu handler with necessary dependencies
    operation_menu_handler = OperationMenu(
        account_manager=account_manager,
        session_manager=session_manager,
        strategy_selector=strategy_selector
    )

    # If parent menu is provided, create a menu object
    if parent_menu:
        return operation_menu_handler.create_menu(parent_menu)

    # Otherwise, return the handler itself
    return operation_menu_handler
