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
import sys
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
import threading
from concurrent.futures import ThreadPoolExecutor

# Import internal modules
try:
    from core.config import Config
    from core.constants import Constants
    from core.exceptions import TelegramAdderError, OperationError, GroupNotFoundError
    from data.session_manager import SessionManager, Session, SessionStatus
    from services.account_manager import AccountManager
    from strategies.strategy_selector import StrategySelector
    from ui.colors import Colors
    from ui.display import Display, ProgressBar, StatusIndicator
    from ui.menu_system import Menu, MenuItem, MenuSystem
    from logging_.logging_manager import get_logger
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    # For development, provide fallbacks or mock objects
    class Config:
        def __init__(self):
            self._config_data = {}
        def get(self, key, default=None):
            return self._config_data.get(key, default)

    class Constants:
        class TimeDelays:
            DEFAULT = 20
            MAXIMUM = 300
            ACCOUNT_CHANGE = 60
        class Limits:
            MAX_MEMBERS_PER_DAY = 20

    class Colors:
        @staticmethod
        def colorize(text, color):
            return text

    class Display:
        @staticmethod
        def clear_screen():
            pass
        @staticmethod
        def print_header(title):
            print(title)
        @staticmethod
        def print_menu(items):
            for i, item in enumerate(items, 1):
                print(f"{i}. {item}")
        @staticmethod
        def get_input(prompt):
            return input(prompt)

    class ProgressBar:
        def __init__(self, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
            self.total = total
            self.prefix = prefix
            self.suffix = suffix
            self.decimals = decimals
            self.length = length
            self.fill = fill
            self.print_end = print_end
            self.current = 0

        def update(self, current):
            self.current = current
            self._print()

        def _print(self):
            percent = ("{0:." + str(self.decimals) + "f}").format(100 * (self.current / float(self.total)))
            filled_length = int(self.length * self.current // self.total)
            bar = self.fill * filled_length + '-' * (self.length - filled_length)
            print(f'\r{self.prefix} |{bar}| {percent}% {self.suffix}', end=self.print_end)
            if self.current == self.total:
                print()

    class StatusIndicator:
        def __init__(self, message="Processing"):
            self.message = message
            self.running = False
            self._thread = None

        def start(self):
            self.running = True
            self._thread = threading.Thread(target=self._animate)
            self._thread.daemon = True
            self._thread.start()

        def stop(self):
            self.running = False
            if self._thread:
                self._thread.join()
            print("\r" + " " * (len(self.message) + 10) + "\r", end="")

        def _animate(self):
            chars = "|/-\\"
            idx = 0
            while self.running:
                print(f"\r{self.message} {chars[idx % len(chars)]}", end="")
                idx += 1
                time.sleep(0.1)

    class Menu:
        def __init__(self, title):
            self.title = title
            self.items = []

        def add_item(self, title, callback=None):
            self.items.append({"title": title, "callback": callback})
            return self

    class MenuItem:
        def __init__(self, title, callback=None):
            self.title = title
            self.callback = callback

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

    class SessionManager:
        @staticmethod
        def get_session_manager():
            return SessionManager()

        def create_session(self, session_type=None):
            return Session()

    class Session:
        def __init__(self):
            self.custom_data = {}
            self.state = {}

        def update_state(self, state):
            self.state.update(state)

        def set_custom_data(self, key, value):
            self.custom_data[key] = value

        def get_custom_data(self, key, default=None):
            return self.custom_data.get(key, default)

    SessionStatus = type('SessionStatus', (), {
        'CREATED': 'created',
        'RUNNING': 'running',
        'COMPLETED': 'completed',
        'FAILED': 'failed'
    })

    class StrategySelector:
        @staticmethod
        def get_strategy(strategy_type, accounts=None):
            return lambda *args, **kwargs: None

    # Mock exceptions
    class TelegramAdderError(Exception):
        pass

    class OperationError(TelegramAdderError):
        pass

    class GroupNotFoundError(OperationError):
        pass

    # Mock logger
    def get_logger(name):
        return logging.getLogger(name)

# Setup logger
logger = get_logger("OperationMenu")


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

    It integrates with various services and strategies to provide a robust
    and user-friendly interface for Telegram group member management.
    """

    def __init__(self, menu_system: MenuSystem, account_manager: Optional[Any] = None,
                 session_manager: Optional[Any] = None, strategy_selector: Optional[Any] = None):
        """
        Initialize the operation menu.

        Args:
            menu_system: The main menu system for navigation
            account_manager: Account manager instance for account operations (optional)
            session_manager: Session manager for state persistence (optional)
            strategy_selector: Strategy selector for choosing transfer strategies (optional)
        """
        self.menu_system = menu_system
        self.config = Config()
        self.display = Display()

        # Use provided services or initialize defaults
        self.account_manager = account_manager
        self.session_manager = session_manager or SessionManager.get_session_manager()
        self.strategy_selector = strategy_selector or StrategySelector()

        # Current operation state
        self.current_operation = None
        self.source_group = None
        self.target_group = None
        self.member_limit = 0
        self.selected_strategy = "sequential"
        self.selected_accounts = []

        # Operation results
        self.last_operation_results = None

        # Create operation menu
        self._create_menus()

        # Logger for this class
        self.logger = logger

    def _create_menus(self):
        """Create all menus related to operations."""
        # Main operation menu
        operation_menu = Menu("Member Transfer Operations")
        operation_menu.add_item("Select Source Group", self.select_source_group)
        operation_menu.add_item("Select Target Group", self.select_target_group)
        operation_menu.add_item("Configure Operation Parameters", self.configure_parameters)
        operation_menu.add_item("Select Transfer Strategy", self.select_strategy)
        operation_menu.add_item("Select Accounts", self.select_accounts)
        operation_menu.add_item("Start Operation", self.start_operation)
        operation_menu.add_item("Resume Interrupted Operation", self.resume_operation)
        operation_menu.add_item("View Last Operation Results", self.view_results)
        operation_menu.add_item("Back to Main Menu", self.back_to_main_menu)

        # Strategy selection menu
        strategy_menu = Menu("Select Transfer Strategy")
        strategy_menu.add_item("Sequential (One account at a time)", lambda: self._set_strategy("sequential"))
        strategy_menu.add_item("Parallel Low (2-3 accounts)", lambda: self._set_strategy("parallel_low"))
        strategy_menu.add_item("Parallel Medium (4-6 accounts)", lambda: self._set_strategy("parallel_medium"))
        strategy_menu.add_item("Parallel High (7+ accounts)", lambda: self._set_strategy("parallel_high"))
        strategy_menu.add_item("Back to Operation Menu", lambda: self.menu_system.show_menu("operation_menu"))

        # Add menus to menu system
        self.menu_system.add_menu("operation_menu", operation_menu)
        self.menu_system.add_menu("strategy_menu", strategy_menu)

    def show(self):
        """Show the operation menu."""
        return self.menu_system.show_menu("operation_menu")

    async def select_source_group(self):
        """
        Interactive selection of the source group.

        This method allows the user to select a source group for member extraction.
        It first checks if any accounts are available, then guides the user through
        selecting a group from the account's groups.
        """
        self.display.clear_screen()
        self.display.print_header("Select Source Group")

        # Check if accounts are available
        if not self._check_accounts_available():
            return

        # Select an account to use for group selection
        account = await self._select_account_for_connection()
        if not account:
            return

        # Connect to the account
        client = await self._connect_to_account(account)
        if not client:
            return

        try:
            # Get and display account's dialogs (groups and channels)
            status_indicator = StatusIndicator("Loading groups")
            status_indicator.start()

            try:
                # Get dialogs asynchronously
                dialogs = await client.get_dialogs()

                # Filter for groups and channels only
                groups = [d for d in dialogs if d.is_group or d.is_channel]

                if not groups:
                    status_indicator.stop()
                    self.display.print_error("No groups or channels found for this account.")
                    input("\nPress Enter to continue...")
                    return

                status_indicator.stop()

                # Display groups for selection
                self.display.print_header("\nAvailable Groups and Channels:")
                for i, group in enumerate(groups, 1):
                    group_type = "Group" if group.is_group else "Channel"
                    members_count = getattr(group.entity, 'participants_count', 'Unknown')
                    self.display.print_item(f"{i}. {group.title} ({group_type}, Members: {members_count})")

                # Get user selection
                selection = self.display.get_input("\nSelect a source group (number) or 0 to cancel: ")

                if selection.isdigit():
                    selection = int(selection)
                    if selection == 0:
                        return
                    elif 1 <= selection <= len(groups):
                        self.source_group = groups[selection - 1]
                        logger.info(f"Source group selected: {self.source_group.title}")
                        self.display.print_success(f"Selected source group: {self.source_group.title}")

                        # Save to session
                        if self.current_operation:
                            self.current_operation.set_custom_data("source_group", {
                                "id": self.source_group.id,
                                "title": self.source_group.title,
                                "is_group": self.source_group.is_group,
                                "is_channel": self.source_group.is_channel
                            })

                        input("\nPress Enter to continue...")
                    else:
                        self.display.print_error("Invalid selection.")
                        input("\nPress Enter to continue...")
                else:
                    self.display.print_error("Please enter a number.")
                    input("\nPress Enter to continue...")

            except Exception as e:
                status_indicator.stop()
                logger.error(f"Error retrieving groups: {e}")
                self.display.print_error(f"Error retrieving groups: {e}")
                input("\nPress Enter to continue...")
        finally:
            # Disconnect client
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")

    async def select_target_group(self):
        """
        Interactive selection of the target group.

        This method allows the user to select a target group for member addition.
        Similar to source group selection, it guides the user through selecting
        a group from the account's groups.
        """
        self.display.clear_screen()
        self.display.print_header("Select Target Group")

        # Similar implementation to select_source_group but for target group
        # Check if accounts are available
        if not self._check_accounts_available():
            return

        # Select an account to use for group selection
        account = await self._select_account_for_connection()
        if not account:
            return

        # Connect to the account
        client = await self._connect_to_account(account)
        if not client:
            return

        try:
            # Get and display account's dialogs (groups and channels)
            status_indicator = StatusIndicator("Loading groups")
            status_indicator.start()

            try:
                # Get dialogs asynchronously
                dialogs = await client.get_dialogs()

                # Filter for groups and channels only
                groups = [d for d in dialogs if d.is_group or d.is_channel]

                if not groups:
                    status_indicator.stop()
                    self.display.print_error("No groups or channels found for this account.")
                    input("\nPress Enter to continue...")
                    return

                status_indicator.stop()

                # Display groups for selection
                self.display.print_header("\nAvailable Groups and Channels:")
                for i, group in enumerate(groups, 1):
                    group_type = "Group" if group.is_group else "Channel"
                    members_count = getattr(group.entity, 'participants_count', 'Unknown')
                    self.display.print_item(f"{i}. {group.title} ({group_type}, Members: {members_count})")

                # Get user selection
                selection = self.display.get_input("\nSelect a target group (number) or 0 to cancel: ")

                if selection.isdigit():
                    selection = int(selection)
                    if selection == 0:
                        return
                    elif 1 <= selection <= len(groups):
                        self.target_group = groups[selection - 1]
                        logger.info(f"Target group selected: {self.target_group.title}")
                        self.display.print_success(f"Selected target group: {self.target_group.title}")

                        # Save to session
                        if self.current_operation:
                            self.current_operation.set_custom_data("target_group", {
                                "id": self.target_group.id,
                                "title": self.target_group.title,
                                "is_group": self.target_group.is_group,
                                "is_channel": self.target_group.is_channel
                            })

                        input("\nPress Enter to continue...")
                    else:
                        self.display.print_error("Invalid selection.")
                        input("\nPress Enter to continue...")
                else:
                    self.display.print_error("Please enter a number.")
                    input("\nPress Enter to continue...")

            except Exception as e:
                status_indicator.stop()
                logger.error(f"Error retrieving groups: {e}")
                self.display.print_error(f"Error retrieving groups: {e}")
                input("\nPress Enter to continue...")
        finally:
            # Disconnect client
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")

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
                current_value = self.current_operation.get_custom_data(param_key)

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
                        self.display.print_error("Number of members must be greater than zero.")
                        continue
                    elif param_key == "delay" and value < 0:
                        self.display.print_error("Delay cannot be negative.")
                        continue

                    # Store the parameter
                    if param_key == "member_limit":
                        self.member_limit = value

                    # Save to session
                    if self.current_operation:
                        self.current_operation.set_custom_data(param_key, value)
                        logger.info(f"Parameter {param_key} set to {value}")

                    self.display.print_success(f"{param_desc} set to {value}")
                except ValueError:
                    self.display.print_error(f"Invalid value. Expected {param_type.__name__}.")

        # Save operation state
        self._save_operation_state()

        input("\nPress Enter to continue...")

    def select_strategy(self):
        """Show the strategy selection menu."""
        self.menu_system.show_menu("strategy_menu")

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
            self.display.print_error("No accounts found. Please add accounts first.")
            input("\nPress Enter to continue...")
            return

        # Display accounts with selection status
        self.display.print_header("\nAvailable Accounts:")
        for i, account in enumerate(accounts, 1):
            # Determine if account is already selected
            selected = "✓" if account.get("id") in self.selected_accounts else " "
            status = account.get("status", "unknown")
            status_color = self._get_status_color(status)

            # Display account info
            self.display.print_item(
                f"{i}. [{selected}] Phone: {account.get('phone', 'Unknown')} - "
                f"Status: {status_color}{status}{Colors.RESET} - "
                f"Added Today: {account.get('members_added_today', 0)} - "
                f"Extracted Today: {account.get('members_extracted_today', 0)}"
            )

        # Selection options
        self.display.print_info("\nOptions:")
        self.display.print_info("  Enter account number to toggle selection")
        self.display.print_info("  A: Select all accounts")
        self.display.print_info("  C: Clear selection")
        self.display.print_info("  S: Save selection and return")
        self.display.print_info("  0: Cancel and return")

        # Get user input
        while True:
            selection = self.display.get_input("\nEnter your choice: ").strip().upper()

            if selection == '0':
                return
            elif selection == 'A':
                self.selected_accounts = [account.get("id") for account in accounts]
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
                    account_id = accounts[index].get("id")
                    if account_id in self.selected_accounts:
                        self.selected_accounts.remove(account_id)
                        self.display.print_info(f"Account {accounts[index].get('phone', 'Unknown')} removed from selection.")
                    else:
                        self.selected_accounts.append(account_id)
                        self.display.print_info(f"Account {accounts[index].get('phone', 'Unknown')} added to selection.")
                else:
                    self.display.print_error("Invalid account number.")
            else:
                self.display.print_error("Invalid option.")

        # Save to session
        if self.current_operation:
            self.current_operation.set_custom_data("selected_accounts", self.selected_accounts)
            logger.info(f"Selected {len(self.selected_accounts)} accounts for operation")

        self.display.print_success(f"Selected {len(self.selected_accounts)} accounts for operation.")
        input("\nPress Enter to continue...")

    async def start_operation(self):
        """
        Start the member transfer operation.

        This method validates the operation parameters, confirms with the user,
        and starts the transfer process using the selected strategy. It tracks
        the progress of the operation and updates the session state accordingly.
        """
        self.display.clear_screen()
        self.display.print_header("Start Member Transfer Operation")

        # Check if everything is configured properly
        validation_result = self._validate_operation_settings()
        if not validation_result[0]:
            self.display.print_error(f"Cannot start operation: {validation_result[1]}")
            input("\nPress Enter to continue...")
            return

        # Display operation summary
        self._display_operation_summary()

        # Get user confirmation
        confirmation = self.display.get_input("\nDo you want to start the operation? (y/n): ").strip().lower()
        if confirmation != 'y':
            self.display.print_info("Operation cancelled.")
            input("\nPress Enter to continue...")
            return

        # Create or update session
        session = self.current_operation
        if not session:
            session = self._create_operation_session()
            self.current_operation = session

        session.update_state({
            "status": "starting",
            "start_time": datetime.now().isoformat(),
            "progress": 0.0,
            "processed": 0,
            "total": self.member_limit,
            "success_count": 0,
            "failure_count": 0
        })

        # Save operation settings to session
        self._save_operation_state()

        # Create a progress bar
        progress_bar = ProgressBar(total=self.member_limit,
                                 prefix='Progress:',
                                 suffix='Complete',
                                 length=50)

        # Get selected strategy
        strategy = self.strategy_selector.get_strategy(
            self.selected_strategy,
            accounts=self.selected_accounts
        )

        try:
            # Update session status
            session.update_state({"status": "running"})

            # Define progress callback
            def progress_callback(data):
                processed = data.get("processed", 0)
                success_count = data.get("success_count", 0)

                # Update progress bar
                progress_bar.update(processed)

                # Update session state
                session.update_state({
                    "progress": (processed / self.member_limit * 100) if self.member_limit > 0 else 0,
                    "processed": processed,
                    "success_count": success_count,
                    "current_account": data.get("current_account", "unknown"),
                    "current_delay": data.get("current_delay", Constants.TimeDelays.DEFAULT)
                })

            # Start the operation with the strategy
            result = await strategy.execute(
                source_group=self.source_group,
                target_group=self.target_group,
                member_limit=self.member_limit,
                progress_callback=progress_callback
            )

            # Save operation results
            self.last_operation_results = result

            # Update session with final results
            session.update_state({
                "status": "completed",
                "end_time": datetime.now().isoformat(),
                "progress": 100.0,
                "processed": result.get("processed", 0),
                "success_count": result.get("success_count", 0),
                "failure_count": result.get("failure_count", 0),
                "completion_time": result.get("completion_time", 0)
            })

            # Display operation results
            self.display.print_success("\nOperation completed successfully!")
            self.display.print_info(f"Processed: {result.get('processed', 0)} members")
            self.display.print_info(f"Success: {result.get('success_count', 0)} members")
            self.display.print_info(f"Failed: {result.get('failure_count', 0)} members")
            self.display.print_info(f"Completion time: {result.get('completion_time', 0):.2f} seconds")

            logger.info(f"Operation resumed and completed: {result}")

        except Exception as e:
            logger.error(f"Operation resumption failed: {e}")

            # Update session with error information
            session.update_state({
                "status": "failed",
                "end_time": datetime.now().isoformat(),
                "error": str(e)
            })

            self.display.print_error(f"Operation resumption failed: {e}")

        input("\nPress Enter to continue...")0):.2f} seconds")

            logger.info(f"Operation completed: {result}")

        except Exception as e:
            logger.error(f"Operation failed: {e}")

            # Update session with error information
            session.update_state({
                "status": "failed",
                "end_time": datetime.now().isoformat(),
                "error": str(e)
            })

            self.display.print_error(f"Operation failed: {e}")

        input("\nPress Enter to continue...")

    async def resume_operation(self):
        """
        Resume an interrupted operation.

        This method looks for interrupted operations in the session manager
        and allows the user to resume them. It loads the operation state from
        the selected session and continues execution from where it left off.
        """
        self.display.clear_screen()
        self.display.print_header("Resume Interrupted Operation")

        # Find incomplete sessions
        session_manager = self.session_manager
        incomplete_sessions = session_manager.find_incomplete_sessions()

        if not incomplete_sessions:
            self.display.print_info("No interrupted operations found.")
            input("\nPress Enter to continue...")
            return

        # Display incomplete sessions
        self.display.print_header("\nInterrupted Operations:")

        sessions = []
        for session_id in incomplete_sessions:
            session = session_manager.get_session(session_id)
            if session and session.get_custom_data("operation_type") == "member_transfer":
                sessions.append(session)

                # Extract session details
                source_group = session.get_custom_data("source_group", {}).get("title", "Unknown")
                target_group = session.get_custom_data("target_group", {}).get("title", "Unknown")
                progress = session.state.get("progress", 0)
                processed = session.state.get("processed", 0)
                total = session.state.get("total", 0)
                start_time = session.state.get("start_time", "Unknown")

                # Format the time
                try:
                    start_time = datetime.fromisoformat(start_time).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

                # Display session info
                index = len(sessions)
                self.display.print_item(
                    f"{index}. From '{source_group}' to '{target_group}' - "
                    f"Progress: {progress:.1f}% ({processed}/{total}) - "
                    f"Started: {start_time}"
                )

        if not sessions:
            self.display.print_info("No member transfer operations found.")
            input("\nPress Enter to continue...")
            return

        # Get user selection
        selection = self.display.get_input("\nSelect an operation to resume (number) or 0 to cancel: ")

        if selection.isdigit():
            selection = int(selection)
            if selection == 0:
                return
            elif 1 <= selection <= len(sessions):
                selected_session = sessions[selection - 1]

                # Confirm resumption
                confirmation = self.display.get_input("\nAre you sure you want to resume this operation? (y/n): ").strip().lower()
                if confirmation != 'y':
                    self.display.print_info("Operation resumption cancelled.")
                    input("\nPress Enter to continue...")
                    return

                # Load operation state from session
                self._load_operation_state(selected_session)
                self.current_operation = selected_session

                # Resume operation
                await self._resume_operation(selected_session)
            else:
                self.display.print_error("Invalid selection.")
                input("\nPress Enter to continue...")
        else:
            self.display.print_error("Please enter a number.")
            input("\nPress Enter to continue...")