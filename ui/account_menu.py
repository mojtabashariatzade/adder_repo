"""
Account Menu Module

This module provides a user interface for managing Telegram accounts within the application.
It allows users to list, add, remove, and modify Telegram accounts.
"""

import os
import sys
import time

# Import menu system components
try:
    from ui.menu_system import Menu, create_action_item, create_submenu_item
except ImportError:
    # For development or testing
    class Menu:
        def __init__(self, title, parent=None):
            self.title = title
            self.parent = parent
            self.items = []

        def add_item(self, item):
            self.items.append(item)

    def create_action_item(key, title, action, **kwargs):
        return {"key": key, "title": title, "action": action}

    def create_submenu_item(key, title, submenu, **kwargs):
        return {"key": key, "title": title, "submenu": submenu}

# Try to import display utilities
try:
    from ui.display import clear_screen, print_heading, print_error, print_table, print_success
except ImportError:
    # Fallback implementations
    def clear_screen():
        """Clear the console screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_heading(text, width=60):
        """Print a formatted heading."""
        print("\n" + "=" * width)
        print(text.center(width))
        print("=" * width)

    def print_error(text):
        """Print an error message."""
        print(f"Error: {text}")

    def print_success(text):
        """Print a success message."""
        print(f"Success: {text}")

    def print_table(headers, rows, title=None):
        """Print data in tabular format."""
        if title:
            print(f"\n{title}")

        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):  # Protect against row length mismatch
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        # Print headers
        header_row = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(
            headers) if i < len(col_widths))
        print(header_row)
        print("-" * len(header_row))

        # Print rows
        for row in rows:
            formatted_row = [str(cell).ljust(col_widths[i])
                             for i, cell in enumerate(row) if i < len(col_widths)]
            print(" | ".join(formatted_row))

# Try to import services
try:
    from services.account_manager import AccountManager
    from core.constants import AccountStatus
except ImportError:
    # Mock classes for development
    class AccountStatus:
        """Mock AccountStatus enum."""
        ACTIVE = "active"
        COOLDOWN = "cooldown"
        BLOCKED = "blocked"
        UNVERIFIED = "unverified"
        DAILY_LIMIT_REACHED = "daily_limit_reached"

        @classmethod
        def to_str(cls, status):
            return status

        @classmethod
        def from_str(cls, status_str):
            return status_str

    class AccountManager:
        """Mock AccountManager for development."""

        def __init__(self):
            self.accounts = {}

        def get_all_accounts(self):
            return list(self.accounts.values())

        def add_account(self, phone, api_id=None, api_hash=None, session_string=None):
            self.accounts[phone] = {
                "phone": phone,
                "api_id": api_id,
                "api_hash": api_hash,
                "session_string": session_string,
                "status": AccountStatus.ACTIVE,
                "daily_usage": {"date": "2025-04-02", "count": 0}
            }
            return list(self.accounts.keys()).index(phone)

        def remove_account(self, phone):
            if phone in self.accounts:
                del self.accounts[phone]
                return True
            return False

        def get_account_count(self):
            return {
                "total": len(self.accounts),
                "active": len([a for a in self.accounts.values() if a.get("status") == AccountStatus.ACTIVE]),
                "cooldown": 0,
                "blocked": 0,
                "unverified": 0,
                "daily_limit_reached": 0
            }

        def reset_daily_limits(self, index=None):
            return True

        def test_account_connection(self, index):
            return True, "Connection successful"

# Try to import logging
try:
    from logging_.logging_manager import get_logger
    logger = get_logger("AccountMenu")
except ImportError:
    # Fallback logger
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("AccountMenu")

# Try to import app context
try:
    from utils.app_context import get_app_context
except ImportError:
    def get_app_context():
        """Mock app context."""
        return None


class AccountMenu:
    """User interface for managing Telegram accounts."""

    def __init__(self, app_context=None):
        """
        Initialize the AccountMenu component.

        Args:
            app_context: The application context
        """
        self.app_context = app_context or get_app_context()

        # Get account manager from app context if available
        if self.app_context and self.app_context.has_service('account_manager'):
            self.account_manager = self.app_context.get_service(
                'account_manager')
        else:
            # Create standalone account manager
            self.account_manager = AccountManager()

    def create_menu(self, parent_menu: Menu) -> Menu:
        """
        Create the account management menu.

        Args:
            parent_menu: The parent menu

        Returns:
            Menu: The account management menu
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
            status_text = account.get("status", "unknown")

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

            # Extract daily usage data safely
            daily_usage = account.get("daily_usage", {})
            if not isinstance(daily_usage, dict):
                daily_usage = {}

            usage_count = daily_usage.get("count", 0)

            # Add row
            rows.append([
                i,
                account.get("phone", "Unknown"),
                status_text,
                usage_count,
                usage_count,  # Using the same count for extracted
                last_used
            ])

        # Display table
        print_table(headers, rows)

        # Display account stats
        stats = self.account_manager.get_account_count()
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
            phone = input("Phone Number (with country code): ").strip()
            if not phone:
                print_error("Phone number cannot be empty")
                input("\nPress Enter to continue...")
                return

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

            session_string = input(
                "Optional - Session String: ").strip() or None

            # Display a summary of the account details
            print("\nAccount Details:")
            print(f"Phone: {phone}")
            print(f"API ID: {api_id}")
            print(
                f"API Hash: {api_hash[:4]}...{api_hash[-4:]}" if api_hash else "API Hash: None")
            print(
                f"Session String: {'Provided' if session_string else 'None'}")

            # Confirm addition
            confirm = input("\nAdd this account? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Operation cancelled.")
                input("\nPress Enter to continue...")
                return

            # Add the account
            index = self.account_manager.add_account(
                phone, api_id, api_hash, session_string)

            print_success(f"Account added successfully with index {index}.")
            input("\nPress Enter to continue...")

        except Exception as e:
            logger.error("Error adding account: %s", e)
            print_error(f"Error adding account: {e}")
            input("\nPress Enter to continue...")

    def remove_account(self) -> None:
        """Remove an existing Telegram account from the system."""
        # First, display the list of accounts
        self.list_accounts()

        # Get all accounts
        accounts = self.account_manager.get_all_accounts()
        if not accounts:
            return

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

            # Check if index is valid
            if not 0 <= index < len(accounts):
                print_error("Invalid account index.")
                input("\nPress Enter to continue...")
                return

            # Get phone number for this index
            account = accounts[index]
            phone = account.get("phone")

            if not phone:
                print_error("Invalid account data - missing phone number.")
                input("\nPress Enter to continue...")
                return

            # Confirm removal
            confirm = input(
                f"Are you sure you want to remove account {phone}? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Operation cancelled.")
                input("\nPress Enter to continue...")
                return

            # Remove the account
            try:
                success = self.account_manager.remove_account(phone)
                if success:
                    print_success(f"Account {phone} removed successfully.")
                else:
                    print_error(f"Failed to remove account {phone}.")
            except Exception as e:
                print_error(f"Error removing account: {e}")

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
                    print_success("Daily limits reset for all accounts.")
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
                    print_success(
                        f"Daily limits reset for account at index {index}.")
                else:
                    print_error("Invalid account index or reset failed.")

            input("\nPress Enter to continue...")

        except Exception as e:
            logger.error("Error resetting daily limits: %s", e)
            print_error(f"Error resetting daily limits: {e}")
            input("\nPress Enter to continue...")

    def test_account(self) -> None:
        """Test the connection to a Telegram account."""
        # First, display the list of accounts
        self.list_accounts()

        # Get all accounts
        accounts = self.account_manager.get_all_accounts()
        if not accounts:
            return

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

            # Check if index is valid
            if not 0 <= index < len(accounts):
                print_error("Invalid account index.")
                input("\nPress Enter to continue...")
                return

            # Show testing message
            print("\nTesting account connection... This may take a moment.")

            # Test the account
            try:
                success, message = self.account_manager.test_account_connection(
                    index)

                if success:
                    print_success(f"Connection test successful: {message}")
                else:
                    print_error(f"Connection test failed: {message}")
            except Exception as e:
                print_error(f"Connection test error: {e}")

            input("\nPress Enter to continue...")

        except Exception as e:
            logger.error("Error testing account: %s", e)
            print_error(f"Error testing account: {e}")
            input("\nPress Enter to continue...")

    def view_account_details(self) -> None:
        """View detailed information about a specific account."""
        # First, display the list of accounts
        self.list_accounts()

        # Get all accounts
        accounts = self.account_manager.get_all_accounts()
        if not accounts:
            return

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

            # Check if index is valid
            if not 0 <= index < len(accounts):
                print_error("Invalid account index.")
                input("\nPress Enter to continue...")
                return

            # Display account details
            account = accounts[index]
            clear_screen()
            print_heading(
                f"Account Details - {account.get('phone', 'Unknown')}")

            # Format account details
            details = [
                ("API ID", account.get("api_id")),
                ("API Hash", f"{account.get('api_hash', '')[:5]}...{account.get('api_hash', '')[-5:]}" if account.get(
                    "api_hash") else "None"),
                ("Phone", account.get("phone", "Unknown")),
                ("Session String", "Provided" if account.get(
                    "session_string") else "None"),
                ("Status", account.get("status", "unknown")),
                ("Cooldown Until", account.get("cooldown_until") or "N/A"),
                ("Last Used", account.get("last_used") or "Never"),
                ("Failure Count", account.get("failures", 0)),
                ("Daily Usage", account.get("daily_usage", {}).get("count", 0)
                 if isinstance(account.get("daily_usage"), dict) else 0),
                ("Added On", account.get("added_on") or "Unknown")
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
