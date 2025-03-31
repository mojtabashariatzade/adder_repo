"""
Account Manager Service

This module provides a centralized service for managing Telegram accounts,
including adding, removing, validating, and tracking usage statistics.
It follows the Singleton pattern to ensure only one instance exists across the application.

Features:
- Account addition and removal
- Account validation and status checks
- Daily limit tracking and resets
- Account rotation and selection strategies
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from utils.app_context import get_app_context
from typing import Dict, List, Optional, Tuple, Any, Union

from core.config import Config
from core.constants import (
    ACCOUNTS_FILE,
    MAX_MEMBERS_PER_DAY,
    MAX_FAILURES_BEFORE_BLOCK,
    AccountStatus
)

from core.exceptions import (
    AccountNotFoundError,
    AccountLimitReachedError,
    AccountBlockedError,
    AccountInCooldownError,
    FileReadError,
    FileWriteError
)

from data.json_file_manager import JsonFileManager
from utils.app_context import AppContext, get_app_context

# Setup logger
logger = logging.getLogger(__name__)


class AccountManager:
    """
    Manager for Telegram accounts.

    This class follows the Singleton pattern to ensure only one instance
    exists across the application. It provides methods for account
    management, including adding, removing, and checking account status.
    """

    _instance = None
    _lock = threading.RLock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """
        Create a new AccountManager instance if one doesn't exist (Singleton pattern).

        Returns:
            AccountManager: The singleton AccountManager instance
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AccountManager, cls).__new__(cls)
            return cls._instance


"""
این متد __init__ را در کلاس AccountManager جایگزین کنید
"""


def __init__(self, app_context: Optional[AppContext] = None):
    """
    Initialize the AccountManager.

    Args:
        app_context (AppContext, optional): Application context for dependency injection.
    """
    # Skip initialization if already initialized (Singleton pattern)
    with self._lock:
        if self._initialized:
            return

        self.app_context = app_context or get_app_context()
        self.config = self.app_context.get_service('config')

        # Use file manager from context or create a new one
        file_manager_service = self.app_context.get_service('file_manager')
        if file_manager_service:
            self.file_manager = file_manager_service
        else:
            self.file_manager = JsonFileManager()

        # Path to the accounts file
        self.accounts_file = self.config.get(
            'accounts_file', ACCOUNTS_FILE)

        # Dictionary to store account data
        # Key: phone number, Value: account data
        self.accounts = {}

        # Load accounts if the file exists
        try:
            self._load_accounts()
        except (FileReadError, FileWriteError) as err:
            logger.error("Error loading accounts: %s", str(err))
            # Create empty accounts file
            self._save_accounts()

        # Keep track of current account index for rotation
        self.current_account_index = 0

        # Setup scheduled task for daily limit reset
        self._setup_daily_reset()

        self._initialized = True
        logger.info("AccountManager initialized successfully.")

    def _load_accounts(self):
        """
        Load accounts from the accounts file.

        Raises:
            FileReadError: If the accounts file cannot be read.
        """
        if not os.path.exists(self.accounts_file):
            logger.info("Accounts file not found: %s", self.accounts_file)
            return

        try:
            with open(self.accounts_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, dict) and "accounts" in data:
                    self.accounts = data["accounts"]
                elif isinstance(data, list):
                    # Convert list to dict for backwards compatibility
                    self.accounts = {
                        account["phone"]: account for account in data}
                else:
                    logger.warning(
                        "Invalid accounts data format in %s", self.accounts_file)
        except json.JSONDecodeError as err:
            logger.error("Error parsing accounts file: %s", err)
            raise FileReadError(self.accounts_file,
                                "Invalid JSON format") from err
        except (IOError, OSError) as err:
            logger.error("Error reading accounts file: %s", err)
            raise FileReadError(self.accounts_file, str(err)) from err

    def _save_accounts(self):
        """
        Save accounts to the accounts file.

        Raises:
            FileWriteError: If the accounts file cannot be written.
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(
                self.accounts_file)), exist_ok=True)

            # Prepare data structure - now using a standardized format
            data = {
                "accounts": self.accounts,
                "last_updated": datetime.now().isoformat()
            }

            with open(self.accounts_file, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4)
                logger.debug("Accounts saved to %s", self.accounts_file)
        except (IOError, OSError) as err:
            logger.error("Error writing accounts file: %s", err)
            raise FileWriteError(self.accounts_file, str(err)) from err

    def add_account(self, phone: str, api_id: int, api_hash: str,
                    session_string: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a new account or update an existing one.

        Args:
            phone (str): Phone number (used as unique identifier)
            api_id (int): Telegram API ID
            api_hash (str): Telegram API hash
            session_string (str, optional): Telethon session string if available

        Returns:
            Dict[str, Any]: The account data
        """
        # Create or update account data
        account_data = {
            "phone": phone,
            "api_id": api_id,
            "api_hash": api_hash,
            "added_on": datetime.now().isoformat(),
            "last_used": None,
            "status": AccountStatus.to_str(AccountStatus.ACTIVE),
            "daily_usage": {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "count": 0
            },
            "total_usage": 0,
            "failures": 0,
            "cooldown_until": None
        }

        # Add session string if provided
        if session_string:
            account_data["session_string"] = session_string

        # Store in accounts dictionary
        with self._lock:
            # Check if account exists and merge with existing data
            if phone in self.accounts:
                existing_data = self.accounts[phone]
                # Preserve statistics
                account_data["last_used"] = existing_data.get("last_used")
                account_data["daily_usage"] = existing_data.get(
                    "daily_usage", account_data["daily_usage"])
                account_data["total_usage"] = existing_data.get(
                    "total_usage", 0)
                account_data["failures"] = existing_data.get("failures", 0)
                account_data["cooldown_until"] = existing_data.get(
                    "cooldown_until")
                logger.info("Updated existing account: %s", phone)
            else:
                logger.info("Added new account: %s", phone)

            self.accounts[phone] = account_data

            # Save to file
            try:
                self._save_accounts()
            except FileWriteError as err:
                logger.error("Failed to save account: %s", err)

            return account_data

    def remove_account(self, phone: str) -> bool:
        """
        Remove an account.

        Args:
            phone (str): Phone number of the account to remove

        Returns:
            bool: True if the account was removed, False if not found

        Raises:
            AccountNotFoundError: If the account is not found
        """
        with self._lock:
            if phone not in self.accounts:
                logger.warning("Account not found for removal: %s", phone)
                raise AccountNotFoundError(
                    f"Account with phone {phone} not found")

            # Remove from dictionary
            del self.accounts[phone]
            logger.info("Removed account: %s", phone)

            # Save to file
            try:
                self._save_accounts()
                return True
            except FileWriteError as err:
                logger.error("Failed to save after account removal: %s", err)
                return False

    def get_account(self, phone: str) -> Dict[str, Any]:
        """
        Get account data by phone number.

        Args:
            phone (str): Phone number of the account

        Returns:
            Dict[str, Any]: Account data

        Raises:
            AccountNotFoundError: If the account is not found
        """
        if phone not in self.accounts:
            logger.warning("Account not found: %s", phone)
            raise AccountNotFoundError(f"Account with phone {phone} not found")

        return self.accounts[phone]

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """
        Get all accounts.

        Returns:
            List[Dict[str, Any]]: List of all account data
        """
        return list(self.accounts.values())

    def get_account_by_phone(self, phone: str) -> int:
        """
        Find an account index by phone number.

        Args:
            phone (str): Phone number to search for

        Returns:
            int: Index of the account if found, -1 otherwise
        """
        # Convert accounts dictionary to list for consistent indexing
        accounts_list = list(self.accounts.values())

        # Search for the phone number
        for i, account in enumerate(accounts_list):
            if account.get("phone") == phone:
                return i

        # Account not found
        return -1

    def get_active_accounts(self) -> List[Dict[str, Any]]:
        """
        Get all active accounts (not blocked, not in cooldown, and within daily limits).

        Returns:
            List[Dict[str, Any]]: List of active account data
        """
        active_accounts = []

        for account in self.accounts.values():
            # Skip blocked accounts
            if account.get("status") == AccountStatus.to_str(AccountStatus.BLOCKED):
                continue

            # Check cooldown
            cooldown_until = account.get("cooldown_until")
            if cooldown_until:
                try:
                    cooldown_time = datetime.fromisoformat(cooldown_until)
                    if cooldown_time > datetime.now():
                        # Still in cooldown
                        continue
                    else:
                        # Cooldown expired, clear it
                        account["cooldown_until"] = None
                        account["status"] = AccountStatus.to_str(
                            AccountStatus.ACTIVE)
                except (ValueError, TypeError):
                    # Invalid datetime format, clear it
                    account["cooldown_until"] = None

            # Check daily usage
            if not self._check_daily_limit(account):
                continue

            active_accounts.append(account)

        return active_accounts

    def update_account_status(self, phone: str, status: Union[AccountStatus, str]) -> None:
        """
        Update an account's status.

        Args:
            phone (str): Phone number of the account
            status (Union[AccountStatus, str]): New status

        Raises:
            AccountNotFoundError: If the account is not found
        """
        with self._lock:
            if phone not in self.accounts:
                logger.warning(
                    "Account not found for status update: %s", phone)
                raise AccountNotFoundError(
                    f"Account with phone {phone} not found")

            # Convert enum to string if needed
            status_str = status if isinstance(
                status, str) else AccountStatus.to_str(status)

            # Update status
            self.accounts[phone]["status"] = status_str

            # Special handling for COOLDOWN status
            if status_str == AccountStatus.to_str(AccountStatus.COOLDOWN):
                # Set cooldown for 3 hours
                cooldown_until = datetime.now() + timedelta(hours=3)
                self.accounts[phone]["cooldown_until"] = cooldown_until.isoformat()

            logger.info("Updated account %s status to %s", phone, status_str)

            # Save to file
            try:
                self._save_accounts()
            except FileWriteError as err:
                logger.error("Failed to save account status update: %s", err)

    def record_usage(self, phone: str, count: int = 1) -> None:
        """
        Record usage for an account.

        Args:
            phone (str): Phone number of the account
            count (int): Number of operations to record

        Raises:
            AccountNotFoundError: If the account is not found
            AccountLimitReachedError: If the account has reached its daily limit
        """
        with self._lock:
            if phone not in self.accounts:
                logger.warning(
                    "Account not found for usage recording: %s", phone)
                raise AccountNotFoundError(
                    f"Account with phone {phone} not found")

            account = self.accounts[phone]

            # Check if blocked
            if account.get("status") == AccountStatus.to_str(AccountStatus.BLOCKED):
                logger.warning(
                    "Cannot record usage for blocked account: %s", phone)
                raise AccountBlockedError(f"Account {phone} is blocked")

            # Check if in cooldown
            cooldown_until = account.get("cooldown_until")
            if cooldown_until:
                try:
                    cooldown_time = datetime.fromisoformat(cooldown_until)
                    if cooldown_time > datetime.now():
                        logger.warning(
                            "Account %s is in cooldown until %s", phone, cooldown_until)
                        raise AccountInCooldownError(
                            f"Account {phone} is in cooldown until {cooldown_until}")
                    else:
                        # Cooldown expired, clear it
                        account["cooldown_until"] = None
                        account["status"] = AccountStatus.to_str(
                            AccountStatus.ACTIVE)
                except (ValueError, TypeError):
                    # Invalid datetime format, clear it
                    account["cooldown_until"] = None

            # Check and update daily usage
            today = datetime.now().strftime("%Y-%m-%d")

            # Initialize daily usage if needed
            if "daily_usage" not in account or not isinstance(account["daily_usage"], dict):
                account["daily_usage"] = {"date": today, "count": 0}

            # Check if it's a new day
            if account["daily_usage"].get("date") != today:
                # Reset for new day
                account["daily_usage"] = {"date": today, "count": 0}

            # Check limit
            current_count = account["daily_usage"].get("count", 0)
            max_per_day = self.config.get(
                "max_members_per_day", MAX_MEMBERS_PER_DAY)

            if current_count + count > max_per_day:
                logger.warning(
                    "Account %s has reached daily limit: %d/%d",
                    phone, current_count, max_per_day
                )
                # Update status
                account["status"] = AccountStatus.to_str(
                    AccountStatus.DAILY_LIMIT_REACHED)
                raise AccountLimitReachedError(
                    f"Account {phone} has reached its daily limit of {max_per_day}")

            # Update usage
            account["daily_usage"]["count"] = current_count + count
            account["total_usage"] = account.get("total_usage", 0) + count
            account["last_used"] = datetime.now().isoformat()

            logger.debug(
                "Recorded usage for account %s: %d (daily: %d/%d)",
                phone, count, account["daily_usage"]["count"], max_per_day
            )

            # Save to file
            try:
                self._save_accounts()
            except FileWriteError as err:
                logger.error("Failed to save account usage update: %s", err)

    def record_failure(self, phone: str) -> bool:
        """
        Record a failure for an account and block if threshold is reached.

        Args:
            phone (str): Phone number of the account

        Returns:
            bool: True if the account was blocked, False otherwise

        Raises:
            AccountNotFoundError: If the account is not found
        """
        with self._lock:
            if phone not in self.accounts:
                logger.warning(
                    "Account not found for failure recording: %s", phone)
                raise AccountNotFoundError(
                    f"Account with phone {phone} not found")

            account = self.accounts[phone]

            # Increment failure count
            account["failures"] = account.get("failures", 0) + 1

            # Check if threshold is reached
            max_failures = self.config.get(
                "max_failures_before_block", MAX_FAILURES_BEFORE_BLOCK)

            if account["failures"] >= max_failures:
                # Block the account
                account["status"] = AccountStatus.to_str(AccountStatus.BLOCKED)
                logger.warning(
                    "Account %s blocked after %d failures",
                    phone, account["failures"]
                )
                blocked = True
            else:
                logger.debug(
                    "Recorded failure for account %s: %d/%d",
                    phone, account["failures"], max_failures
                )
                blocked = False

            # Save to file
            try:
                self._save_accounts()
            except FileWriteError as err:
                logger.error("Failed to save account failure update: %s", err)

            return blocked

    def reset_failures(self, phone: str) -> None:
        """
        Reset failure count for an account.

        Args:
            phone (str): Phone number of the account

        Raises:
            AccountNotFoundError: If the account is not found
        """
        with self._lock:
            if phone not in self.accounts:
                logger.warning(
                    "Account not found for failure reset: %s", phone)
                raise AccountNotFoundError(
                    f"Account with phone {phone} not found")

            self.accounts[phone]["failures"] = 0
            logger.debug("Reset failures for account %s", phone)

            # Save to file
            try:
                self._save_accounts()
            except FileWriteError as err:
                logger.error("Failed to save account failure reset: %s", err)

    def unblock_account(self, phone: str) -> None:
        """
        Unblock an account.

        Args:
            phone (str): Phone number of the account

        Raises:
            AccountNotFoundError: If the account is not found
        """
        with self._lock:
            if phone not in self.accounts:
                logger.warning("Account not found for unblocking: %s", phone)
                raise AccountNotFoundError(
                    f"Account with phone {phone} not found")

            account = self.accounts[phone]

            # Reset status and failures
            account["status"] = AccountStatus.to_str(AccountStatus.ACTIVE)
            account["failures"] = 0
            account["cooldown_until"] = None

            logger.info("Unblocked account: %s", phone)

            # Save to file
            try:
                self._save_accounts()
            except FileWriteError as err:
                logger.error("Failed to save account unblock: %s", err)

    def _check_daily_limit(self, account: Dict[str, Any]) -> bool:
        """
        Check if an account has reached its daily limit.

        Args:
            account (Dict[str, Any]): Account data

        Returns:
            bool: True if the account is within limits, False otherwise
        """
        # Check if daily usage is initialized
        if "daily_usage" not in account or not isinstance(account["daily_usage"], dict):
            return True

        # Check if it's a new day
        today = datetime.now().strftime("%Y-%m-%d")
        if account["daily_usage"].get("date") != today:
            # New day, limit not reached
            return True

        # Check current usage against limit
        current_count = account["daily_usage"].get("count", 0)
        max_per_day = self.config.get(
            "max_members_per_day", MAX_MEMBERS_PER_DAY)

        return current_count < max_per_day

    def _setup_daily_reset(self):
        """Set up a background thread to reset daily limits at midnight."""
        reset_thread = threading.Thread(
            target=self._daily_reset_worker,
            daemon=True,
            name="AccountDailyReset"
        )
        reset_thread.start()
        logger.debug("Started daily reset thread")

    def _daily_reset_worker(self):
        """Worker function to reset daily limits at midnight."""
        while True:
            try:
                # Calculate time until next midnight
                now = datetime.now()
                tomorrow = now.replace(
                    hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                seconds_until_midnight = (tomorrow - now).total_seconds()

                # Sleep until midnight
                time.sleep(seconds_until_midnight)

                # Reset daily limits
                self._reset_daily_limits()

            except (ValueError, TypeError, AttributeError) as err:
                logger.error("Error in daily reset thread: %s", err)
                # Sleep for an hour before retrying
                time.sleep(3600)

    def _reset_daily_limits(self):
        """Reset daily usage limits for all accounts."""
        with self._lock:
            today = datetime.now().strftime("%Y-%m-%d")
            updated = False

            for phone, account in self.accounts.items():
                if (
                    "daily_usage" in account and
                    isinstance(account["daily_usage"], dict) and
                    account["daily_usage"].get("date") != today
                ):
                    # Reset daily usage
                    account["daily_usage"] = {"date": today, "count": 0}

                    # Reset daily limit reached status if applicable
                    if account.get("status") == AccountStatus.to_str(
                            AccountStatus.DAILY_LIMIT_REACHED):
                        account["status"] = AccountStatus.to_str(
                            AccountStatus.ACTIVE)

                    updated = True
                    logger.debug("Reset daily limit for account %s", phone)

            if updated:
                # Save changes
                try:
                    self._save_accounts()
                    logger.info("Daily limits reset for accounts")
                except FileWriteError as err:
                    logger.error("Failed to save daily limit reset: %s", err)

    def get_next_account(self) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Get the next available account using round-robin rotation.

        Returns:
            Tuple[Optional[Dict[str, Any]], int]:
                The next available account and its index, or (None, -1) if no accounts are available
        """
        with self._lock:
            active_accounts = self.get_active_accounts()

            if not active_accounts:
                logger.warning("No active accounts available")
                return None, -1

            # If index is out of range, reset it
            if self.current_account_index >= len(active_accounts):
                self.current_account_index = 0

            # Get the next account
            account = active_accounts[self.current_account_index]
            index = self.current_account_index

            # Increment for next time
            self.current_account_index = (
                self.current_account_index + 1) % len(active_accounts)

            logger.debug("Selected account %s (index %d)",
                         account["phone"], index)
            return account, index

    def get_next_available_account(self) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Get the next available account, potentially skipping the current one.

        Returns:
            Tuple[Optional[Dict[str, Any]], int]:
                The next available account and its index, or (None, -1) if no accounts are available
        """
        return self.get_next_account()

    def get_account_count(self) -> Dict[str, int]:
        """
        Get count of accounts by status.

        Returns:
            Dict[str, int]: Dictionary with counts by status
        """
        counts = {
            "total": len(self.accounts),
            "active": 0,
            "blocked": 0,
            "cooldown": 0,
            "daily_limit_reached": 0,
            "unverified": 0
        }

        for account in self.accounts.values():
            status = account.get("status", "active").lower()

            if status == "active":
                # Check if it's really active (not in cooldown and within daily limits)
                if account.get("cooldown_until"):
                    try:
                        cooldown_time = datetime.fromisoformat(
                            account["cooldown_until"])
                        if cooldown_time > datetime.now():
                            status = "cooldown"
                    except (ValueError, TypeError):
                        pass

                # Check daily limit
                if not self._check_daily_limit(account):
                    status = "daily_limit_reached"

            if status in counts:
                counts[status] += 1
            else:
                counts[status] = 1

        return counts

    def export_accounts(self, file_path: Optional[str] = None) -> str:
        """
        Export accounts to a JSON file.

        Args:
            file_path (str, optional): Path to export to. If None, uses a timestamped file name.

        Returns:
            str: Path to the exported file
        """
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"accounts_export_{timestamp}.json"

        # Create data structure for export
        export_data = {
            "accounts": self.accounts,
            "export_date": datetime.now().isoformat(),
            "account_count": len(self.accounts)
        }

        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(
                os.path.abspath(file_path)), exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(export_data, file, indent=4)
                logger.info("Accounts exported to %s", file_path)
                return file_path
        except (IOError, OSError) as err:
            logger.error("Error exporting accounts: %s", err)
            raise FileWriteError(file_path, str(err)) from err

    def import_accounts(self, file_path: str, overwrite: bool = False) -> int:
        """
        Import accounts from a JSON file.

        Args:
            file_path (str): Path to the file to import
            overwrite (bool): Whether to overwrite existing accounts

        Returns:
            int: Number of accounts imported

        Raises:
            FileReadError: If the file cannot be read
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                import_data = json.load(file)
        except json.JSONDecodeError as err:
            logger.error("Error parsing import file: %s", err)
            raise FileReadError(file_path, "Invalid JSON format") from err
        except (IOError, OSError) as err:
            logger.error("Error reading import file: %s", err)
            raise FileReadError(file_path, str(err)) from err

        imported_count = 0

        with self._lock:
            # Handle different formats
            if isinstance(import_data, dict) and "accounts" in import_data:
                accounts_to_import = import_data["accounts"]
            elif isinstance(import_data, list):
                accounts_to_import = {
                    account["phone"]: account for account in import_data
                    if "phone" in account
                }
            else:
                # Line was too long (104/100), breaking it up
                logger.error("Invalid import format")
                error_msg = "Invalid accounts format"
                raise FileReadError(file_path, error_msg)

            # Import accounts
            if isinstance(accounts_to_import, dict):
                for phone, account in accounts_to_import.items():
                    if phone not in self.accounts or overwrite:
                        self.accounts[phone] = account
                        imported_count += 1

            # Save changes
            if imported_count > 0:
                try:
                    self._save_accounts()
                    logger.info("Imported %d accounts", imported_count)
                except FileWriteError as err:
                    logger.error("Failed to save imported accounts: %s", err)

            return imported_count
