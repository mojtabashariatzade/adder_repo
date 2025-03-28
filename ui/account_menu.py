"""
Account Menu Module

This module provides a user interface for managing Telegram accounts within the application.
It allows users to list, add, remove, and modify Telegram accounts.

Features:
- Display a list of all registered accounts with their statuses
- Add new Telegram accounts with API credentials
- Remove existing accounts
- Reset account daily limits
- View detailed account information
- Enable/disable accounts
- Testing account connectivity

Usage:
    from ui.account_menu import create_account_menu
    from ui.menu_system import MenuSystem, Menu

    # Create the main menu
    main_menu = Menu("Main Menu")

    # Add the account menu as a submenu
    account_menu = create_account_menu(main_menu)
    main_menu.add_item(create_submenu_item("1", "Account Management", account_menu))

    # Create and run the menu system
    menu_system = MenuSystem(main_menu)
    menu_system.run()
"""
# pylint: disable=unused-import, unused-argument

import os
import sys
import time

# Import menu system components
from ui.menu_system import (
    Menu,
    create_action_item, create_submenu_item
)

# Try to import display utilities
try:
    from ui.display import clear_screen, print_heading, print_error, print_table
except ImportError:
    # Fallback implementations if display module is not available
    def clear_screen():
        """Clear the console screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_colored(text, color=None, end='\n'):
        """Print text with color."""
        print(text, end=end)

    def print_heading(text, width=60):
        """Print a formatted heading."""
        print("\n" + "=" * width)
        print(text.center(width))
        print("=" * width)

    def print_error(text):
        """Print an error message."""
        print(f"Error: {text}")

    def print_table(headers, rows, title=None):
        """Print data in tabular format."""
        if title:
            print(f"\n{title}")

        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Print headers
        header_row = " | ".join(
            h.ljust(col_widths[i]) for i, h in enumerate(headers))
        print(header_row)
        print("-" * len(header_row))

        # Print rows
        for row in rows:
            print(" | ".join(str(cell).ljust(
                col_widths[i]) for i, cell in enumerate(row)))

# Try to import services
try:
    from services.account_manager import AccountManager
    from models.account import Account, AccountStatus
except ImportError:
    # Mock classes if imports fail (for development/testing)

    class AccountStatus:
        """Mock AccountStatus enum."""
        ACTIVE = "active"
        COOLDOWN = "cooldown"
        BLOCKED = "blocked"
        UNVERIFIED = "unverified"
        DAILY_LIMIT_REACHED = "daily_limit_reached"

    class Account:
        """Mock Account class."""

        def __init__(self, api_id, api_hash, phone, session_string=None, status="active"):
            self.api_id = api_id
            self.api_hash = api_hash
            self.phone = phone
            self.session_string = session_string
            self.status = status
            self.cooldown_until = None
            self.last_used = None
            self.failure_count = 0
            self.members_added_today = 0
            self.members_extracted_today = 0
            self.daily_reset_time = None

    class AccountManager:
        """Mock AccountManager for development."""

        def __init__(self):
            self.accounts = []

        def get_all_accounts(self):
            return self.accounts

        def add_account(self, api_id, api_hash, phone, session_string=None):
            account = Account(api_id, api_hash, phone, session_string)
            self.accounts.append(account)
            return len(self.accounts) - 1

        def remove_account(self, index):
            if 0 <= index < len(self.accounts):
                phone = self.accounts[index].phone
                del self.accounts[index]
                return True, phone
            return False, None

        def get_account_by_phone(self, phone):
            for i, account in enumerate(self.accounts):
                if account.phone == phone:
                    return i
            return -1

        def reset_daily_limits(self, index=None):
            if index is not None:
                if 0 <= index < len(self.accounts):
                    self.accounts[index].members_added_today = 0
                    self.accounts[index].members_extracted_today = 0
                    return True
                return False
            else:
                for account in self.accounts:
                    account.members_added_today = 0
                    account.members_extracted_today = 0
                return True

        def get_account_stats(self):
            total = len(self.accounts)
            active = sum(1 for acc in self.accounts if acc.status ==
                         AccountStatus.ACTIVE)
            cooldown = sum(
                1 for acc in self.accounts if acc.status == AccountStatus.COOLDOWN)
            blocked = sum(
                1 for acc in self.accounts if acc.status == AccountStatus.BLOCKED)
            unverified = sum(
                1 for acc in self.accounts if acc.status == AccountStatus.UNVERIFIED)
            daily_limit = sum(
                1 for acc in self.accounts if acc.status == AccountStatus.DAILY_LIMIT_REACHED)

            return {
                "total": total,
                "active": active,
                "cooldown": cooldown,
                "blocked": blocked,
                "unverified": unverified,
                "daily_limit_reached": daily_limit
            }

        def test_account_connection(self, index):
            # Mock result - always success
            return True, "Connection successful"

# Try to import logging system
try:
    from logging_.logging_manager import get_logger
    logger = get_logger("AccountMenu")
except ImportError:
    # Fallback logger
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("AccountMenu")


class AccountMenu:
    """
    UI component for managing Telegram accounts.

    This class provides methods for displaying account-related menus and handling
    user interactions for managing Telegram accounts.
    """

    def __init__(self, app_context=None):
        """Initialize the AccountMenu component.
        Args:
        app_context: The application context
        """
        self.app_context = app_context
        # Get account manager from app context if available
        if app_context and app_context.has_service('account_manager'):
            self.account_manager = app_context.get_service('account_manager')
        else:
            self.account_manager = AccountManager()

    def create_menu(self, parent_menu: Menu) -> Menu:
        """
        Create the account management menu.

        Args:
            parent_menu (Menu): The parent menu.

        Returns:
            Menu: The account management menu.
        """
        # Create the account management menu
        account_menu = Menu("Account Management", parent=parent_menu)

        # Add menu items
        account_menu.add_item(create_action_item(
            "1", "List Accounts", self.list_accounts))
        account_menu.add_item(create_action_item(
            "2", "Add Account", self.add_account))
        account_menu.add_item(create_action_item(
            "3", "Remove Account", self.remove_account))
        account_menu.add_item(create_action_item(
            "4", "Reset Daily Limits", self.reset_daily_limits))
        account_menu.add_item(create_action_item(
            "5", "Test Account Connection", self.test_account))
        account_menu.add_item(create_action_item(
            "6", "View Account Details", self.view_account_details))

        return account_menu

    def list_accounts(self) -> None:
        """Display a list of all registered accounts with their statuses."""
        clear_screen()
        print_heading("Account List")

        # Get accounts
        accounts = self.account_manager.get_all_accounts()

        if not accounts:
            print("No accounts found.")
            input("\nPress Enter to continue...")
            return

        # Prepare data for tabular display
        headers = ["Index", "Phone", "Status",
                   "Added Today", "Extracted Today", "Last Used"]
        rows = []

        for i, account in enumerate(accounts):
            # Format status
            status_text = account.status

            # Format cooldown time if applicable
            if status_text == AccountStatus.COOLDOWN and account.get("cooldown_until"):
                import datetime
                try:
                    cooldown_until = datetime.datetime.fromisoformat(
                        account.get("cooldown_until"))
                    now = datetime.datetime.now()
                    if cooldown_until > now:
                        minutes_left = (cooldown_until -
                                        now).total_seconds() / 60
                        status_text = f"{status_text} ({minutes_left:.0f}m left)"
                except Exception:
                    pass

            # Format last used time
            last_used = "Never"
            if account.get("last_used"):
                try:
                    import datetime
                    last_used_time = datetime.datetime.fromisoformat(
                        account.get("last_used"))
                    last_used = last_used_time.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    last_used = "Invalid date"

            # Add row
            rows.append([
                i,
                account.get("phone", "Unknown"),
                status_text,
                account.get("daily_usage", {}).get("count", 0),
                account.get("daily_usage", {}).get("count", 0),
                last_used
            ])

        # Display table
        print_table(headers, rows)

        # Display account stats
        stats = self.account_manager.get_account_stats()
        print("\nAccount Statistics:")
        print(f"Total: {stats['total']}, Active: {stats['active']}, Cooldown: {stats['cooldown']}, "
              f"Blocked: {stats['blocked']}, Unverified: {stats['unverified']}, "
              f"Daily Limit Reached: {stats['daily_limit_reached']}")

        input("\nPress Enter to continue...")

    def add_account(self) -> None:
        """Add a new Telegram account to the system."""
        clear_screen()
        print_heading("Add New Account")

        try:
            # Get account details
            api_id = input("API ID: ").strip()
            if not api_id:
                print_error("API ID cannot be empty")
                input("\nPress Enter to continue...")
                return

            try:
                api_id = int(api_id)
            except ValueError:
                print_error("API ID must be a number")
                input("\nPress Enter to continue...")
                return

            api_hash = input("API Hash: ").strip()
            if not api_hash:
                print_error("API Hash cannot be empty")
                input("\nPress Enter to continue...")
                return

            phone = input("Phone Number (with country code): ").strip()
            if not phone:
                print_error("Phone number cannot be empty")
                input("\nPress Enter to continue...")
                return

            # Check if account already exists
            existing_index = -1
            for i, acc in enumerate(self.account_manager.get_all_accounts()):
                if acc.get("phone") == phone:
                    existing_index = i
                    break
            if existing_index >= 0:
                print(
                    f"This account already exists at index {existing_index}.")
                input("\nPress Enter to continue...")
                return

            # Add the account
            index = self.account_manager.add_account(api_id, api_hash, phone)
            print(f"Account added successfully with index {index}.")
            input("\nPress Enter to continue...")

        except Exception as e:
            logger.error("Error adding account: %s", e)
            print_error(f"Error adding account: {e}")
            input("\nPress Enter to continue...")

    def remove_account(self) -> None:
        """Remove an existing Telegram account from the system."""
        # First, display the list of accounts
        self.list_accounts()

        try:
            index_str = input(
                "\nEnter the index of the account to remove (-1 to cancel): ").strip()

            if index_str == "-1":
                print("Operation cancelled.")
                input("\nPress Enter to continue...")
                return

            try:
                index = int(index_str)
            except ValueError:
                print_error("Invalid input. Please enter a number.")
                input("\nPress Enter to continue...")
                return

            # Confirm removal
            confirm = input(
                f"Are you sure you want to remove account {index}? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Operation cancelled.")
                input("\nPress Enter to continue...")
                return

            # Remove the account
            success, phone = self.account_manager.remove_account(index)
            if success:
                print(f"Account {phone} removed successfully.")
            else:
                print_error("Invalid account index.")

            input("\nPress Enter to continue...")

        except Exception as e:
            logger.error("Error removing account: %s", e)
            print_error(f"Error removing account: {e}")
            input("\nPress Enter to continue...")

    def reset_daily_limits(self) -> None:
        """Reset daily account limits for adding/extracting members."""
        # First, display the list of accounts
        self.list_accounts()

        try:
            index_str = input(
                "\nEnter the index of the account to reset limits, or 'all' to reset all accounts (-1 to cancel): ").strip()

            if index_str == "-1":
                print("Operation cancelled.")
                input("\nPress Enter to continue...")
                return

            if index_str.lower() == "all":
                # Reset all accounts
                confirm = input(
                    "Are you sure you want to reset limits for ALL accounts? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("Operation cancelled.")
                    input("\nPress Enter to continue...")
                    return

                success = self.account_manager.reset_daily_limits()
                if success:
                    print("Daily limits reset for all accounts.")
                else:
                    print_error("Error resetting daily limits.")
            else:
                # Reset specific account
                try:
                    index = int(index_str)
                except ValueError:
                    print_error(
                        "Invalid input. Please enter a number or 'all'.")
                    input("\nPress Enter to continue...")
                    return

                success = self.account_manager.reset_daily_limits(index)
                if success:
                    print(f"Daily limits reset for account at index {index}.")
                else:
                    print_error("Invalid account index.")

            input("\nPress Enter to continue...")

        except Exception as e:
            logger.error("Error resetting daily limits: %s", e)
            print_error(f"Error resetting daily limits: {e}")
            input("\nPress Enter to continue...")

    def test_account(self) -> None:
        """Test the connection to a Telegram account."""
        # First, display the list of accounts
        self.list_accounts()

        try:
            index_str = input(
                "\nEnter the index of the account to test (-1 to cancel): ").strip()

            if index_str == "-1":
                print("Operation cancelled.")
                input("\nPress Enter to continue...")
                return

            try:
                index = int(index_str)
            except ValueError:
                print_error("Invalid input. Please enter a number.")
                input("\nPress Enter to continue...")
                return

            # Show testing message
            print("\nTesting account connection... This may take a moment.")

            # Test the account
            success, message = self.account_manager.test_account_connection(
                index)

            if success:
                print(f"Connection test successful: {message}")
            else:
                print_error(f"Connection test failed: {message}")

            input("\nPress Enter to continue...")

        except Exception as e:
            logger.error("Error testing account: %s", e)
            print_error(f"Error testing account: {e}")
            input("\nPress Enter to continue...")

    def view_account_details(self) -> None:
        """View detailed information about a specific account."""
        # First, display the list of accounts
        self.list_accounts()

        try:
            index_str = input(
                "\nEnter the index of the account to view details (-1 to cancel): ").strip()

            if index_str == "-1":
                print("Operation cancelled.")
                input("\nPress Enter to continue...")
                return

            try:
                index = int(index_str)
            except ValueError:
                print_error("Invalid input. Please enter a number.")
                input("\nPress Enter to continue...")
                return

            # Get accounts
            accounts = self.account_manager.get_all_accounts()

            if not 0 <= index < len(accounts):
                print_error("Invalid account index.")
                input("\nPress Enter to continue...")
                return

            # Display account details
            account = accounts[index]
            clear_screen()
            print_heading(f"Account Details - {account.phone}")

            # Format account details
            details = [
                ("API ID", account.api_id),
                ("API Hash",
                 f"{account.api_hash[:5]}...{account.api_hash[-5:]}" if account.api_hash else "None"),
                ("Phone", account.phone),
                ("Session String",
                 f"{account.session_string[:10]}...{account.session_string[-10:]}" if account.session_string else "None"),
                ("Status", account.status),
                ("Cooldown Until", account.cooldown_until or "N/A"),
                ("Last Used", account.last_used or "Never"),
                ("Failure Count", account.failure_count),
                ("Members Added Today", account.members_added_today),
                ("Members Extracted Today", account.members_extracted_today),
                ("Daily Reset Time", account.daily_reset_time or "N/A")
            ]

            # Print details
            for label, value in details:
                print(f"{label:25}: {value}")

            input("\nPress Enter to continue...")

        except Exception as e:
            logger.error("Error viewing account details: %s", e)
            print_error(f"Error viewing account details: {e}")
            input("\nPress Enter to continue...")


def create_account_menu(parent_menu: Menu) -> Menu:
    """
    Create and return the account management menu.

    Args:
        parent_menu (Menu): The parent menu.

    Returns:
        Menu: The account management menu.
    """
    account_menu_handler = AccountMenu()
    return account_menu_handler.create_menu(parent_menu)


# Example usage when run directly
if __name__ == "__main__":
    from ui.menu_system import MenuSystem

    # Create a simple main menu
    main_menu = Menu("Main Menu")

    # Create the account menu
    account_menu = create_account_menu(main_menu)

    # Add the account menu to the main menu
    main_menu.add_item(create_submenu_item(
        "1", "Account Management", account_menu))
    main_menu.add_item(create_action_item("q", "Quit", lambda: sys.exit(0)))

    # Create and run the menu system
    menu_system = MenuSystem(main_menu)
    try:
        menu_system.run()
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
        sys.exit(0)
