"""
Account Manager Service
"""

import os
import json
import logging
import threading
from datetime import datetime, timedelta
import uuid

# Import from other modules
try:
    from core.constants import AccountStatus
    from core.exceptions import (
        AccountNotFoundError
    )
    from core.config import Config
    from models.account import Account
    from data.encryption import Encryptor
    from data.file_manager import JsonFileManager
    from logging_.logging_manager import get_logger
except ImportError:
    # For development
    from enum import Enum, auto

# pylint: disable=C0115  # Missing class docstring
    class AccountStatus(Enum):
        ACTIVE = auto()
        COOLDOWN = auto()
        BLOCKED = auto()
        UNVERIFIED = auto()
        DAILY_LIMIT_REACHED = auto()

    class Account:
        def __init__(self, account_id, api_id, api_hash, phone, session_string=None):
            self.account_id = account_id
            self.api_id = api_id
            self.api_hash = api_hash
            self.phone = phone
            self.session_string = session_string
            self.status = AccountStatus.ACTIVE
            self.status_changed_at = datetime.now()
            self.cooldown_until = None
            self.daily_reset_time = datetime.now().isoformat()
            self.members_added_today = 0
            self.members_extracted_today = 0
            self.failure_count = 0
            self.total_usage_count = 0
            self.last_used = None
            self.creation_date = datetime.now().isoformat()
            self.notes = ""

        def to_dict(self):
            return {
                "account_id": self.account_id,
                "api_id": self.api_id,
                "api_hash": self.api_hash,
                "phone": self.phone,
                "session_string": self.session_string,
                "status": self.status.name,
                "status_changed_at": (
                    self.status_changed_at.isoformat()
                    if self.status_changed_at
                    else None
                ),
                "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
                "daily_reset_time": self.daily_reset_time,
                "members_added_today": self.members_added_today,
                "members_extracted_today": self.members_extracted_today,
                "failure_count": self.failure_count,
                "total_usage_count": self.total_usage_count,
                "last_used": self.last_used.isoformat() if self.last_used else None,
                "creation_date": self.creation_date,
                "notes": self.notes
            }

        @classmethod
        # pylint: disable=C0116  # Missing function or method docstring
        def from_dict(cls, data):
            account = cls(
                account_id=data.get("account_id"),
                api_id=data.get("api_id"),
                api_hash=data.get("api_hash"),
                phone=data.get("phone"),
                session_string=data.get("session_string")
            )
            account.status = AccountStatus[data.get("status", "ACTIVE")]
            account.status_changed_at = datetime.fromisoformat(
                data.get("status_changed_at")) if data.get("status_changed_at") else None
            account.cooldown_until = datetime.fromisoformat(
                data.get("cooldown_until")) if data.get("cooldown_until") else None
            account.daily_reset_time = data.get(
                "daily_reset_time", datetime.now().isoformat())
            account.members_added_today = data.get("members_added_today", 0)
            account.members_extracted_today = data.get(
                "members_extracted_today", 0)
            account.failure_count = data.get("failure_count", 0)
            account.total_usage_count = data.get("total_usage_count", 0)
            account.last_used = datetime.fromisoformat(
                data.get("last_used")) if data.get("last_used") else None
            account.creation_date = data.get(
                "creation_date", datetime.now().isoformat())
            account.notes = data.get("notes", "")
            return account

# pylint: disable=C0116  # Missing function or method docstring
    def get_logger(name): return logging.getLogger(name)
    JsonFileManager = None
    Encryptor = None
    FileManager = None

    class Config:
        _instance = None

        def __new__(cls):
            if cls._instance is None:
                cls._instance = super(Config, cls).__new__(cls)
                cls._instance._config_data = {
                    "accounts_file": "telegram_accounts.json",
                    "encryption_enabled": True,
                    "max_members_per_day": 20
                }
            return cls._instance

        def get(self, key, default=None):
            return self._config_data.get(key, default)

# Constants
MAX_MEMBERS_PER_DAY = 20
DEFAULT_COOL_DOWN_HOURS = 6
MAX_FAILURES_BEFORE_BLOCK = 3
ACCOUNTS_FILE = "telegram_accounts.json"
ENCRYPTION_KEY_FILE = "encryption.key"

# Logger setup
logger = get_logger("AccountManager")

# pylint: disable=C0115  # Missing class docstring


class AccountManager:
    _instance = None
    _lock = threading.RLock()

# pylint: disable=C0116  # Missing function or method docstring
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AccountManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, accounts_file=None, encryption_key_file=None):
        with self._lock:
            if self._initialized:
                return

            self.config = Config()
            self.accounts_file = accounts_file or self.config.get(
                'accounts_file', ACCOUNTS_FILE)
            self.encryption_key_file = encryption_key_file or self.config.get(
                'encryption_key_file', ENCRYPTION_KEY_FILE)
            self.max_members_per_day = self.config.get(
                'max_members_per_day', MAX_MEMBERS_PER_DAY)
            self.encryption_enabled = self.config.get(
                'encryption_enabled', True)

            self.accounts = {}
            self.encryptor = None
            self.file_manager = JsonFileManager() if JsonFileManager else None

            if self.encryption_enabled and Encryptor:
                try:
                    self.encryptor = Encryptor(
                        key_file=self.encryption_key_file)
                except (ValueError, TypeError, AttributeError):
                    logger.error("Error initializing encryption: %s", e)
                    self.encryption_enabled = False

            self._load_accounts()
            self._initialized = True
            logger.info("AccountManager initialized")

    def _load_accounts(self):
        try:
            if not os.path.exists(self.accounts_file):
                logger.info(
                    "Accounts file not found: %s. Creating new file.", self.accounts_file)
                self.accounts = {}
                self._save_accounts()
                return

            if self.encryption_enabled and self.encryptor:
                try:
                    with open(self.accounts_file, 'r') as file:
                        encrypted_data = file.read()
                        decrypted_data = self.encryptor.decrypt(encrypted_data)
                        accounts_data = json.loads(decrypted_data)
                except Exception as e:
                    logger.error("Error decrypting accounts file: %s", e)
                    accounts_data = {}
            else:
                if self.file_manager:
                    accounts_data = self.file_manager.read_json(
                        self.accounts_file, default={})
                else:
                    with open(self.accounts_file, 'r') as file:
                        accounts_data = json.loads(file.read())

            self.accounts = {}
            for account_data in accounts_data.get('accounts', []):
                account = Account.from_dict(account_data)
                self.accounts[account.account_id] = account

            self._check_account_statuses()
            logger.info("Loaded %s accounts from %s", len(
                self.accounts), self.accounts_file)
        except Exception as e:
            logger.error("Error loading accounts: %s", e)
            self.accounts = {}

    def _save_accounts(self):
        try:
            accounts_data = {
                'last_updated': datetime.now().isoformat(),
                'accounts': [account.to_dict() for account in self.accounts.values()]
            }

            if self.encryption_enabled and self.encryptor:
                try:
                    encrypted_data = self.encryptor.encrypt(
                        json.dumps(accounts_data))
                    with open(self.accounts_file, 'w') as file:
                        file.write(encrypted_data)
                except Exception as e:
                    logger.error("Error encrypting accounts data: %s", e)
                    raise
            else:
                if self.file_manager:
                    self.file_manager.write_json(
                        self.accounts_file, accounts_data)
                else:
                    with open(self.accounts_file, 'w') as file:
                        json.dump(accounts_data, file, indent=4)

            logger.debug("Saved %s accounts to %s", len(
                self.accounts), self.accounts_file)
            return True
        except Exception as e:
            logger.error("Error saving accounts: %s", e)
            return False

    def _check_account_statuses(self):
        now = datetime.now()

        for account_id, account in list(self.accounts.items()):
            # Check if cooldown period is over
            if account.status == AccountStatus.COOLDOWN and account.cooldown_until:
                if now > account.cooldown_until:
                    account.status = AccountStatus.ACTIVE
                    account.status_changed_at = now
                    account.cooldown_until = None
                    logger.info(
                        "Account %s is now active (cooldown ended)", account.phone)

            # Check if daily limits should be reset
            try:
                last_reset = datetime.fromisoformat(account.daily_reset_time)
                if (now - last_reset).total_seconds() > 86400:  # 24 hours
                    account.members_added_today = 0
                    account.members_extracted_today = 0
                    account.daily_reset_time = now.isoformat()

                    # If account was daily limit reached, set it back to active
                    if account.status == AccountStatus.DAILY_LIMIT_REACHED:
                        account.status = AccountStatus.ACTIVE
                        account.status_changed_at = now
                        logger.info(
                            "Account %s is now active (daily limits reset)", account.phone)
            except (ValueError, TypeError):
                # If there's an error parsing the date, just reset it
                account.daily_reset_time = now.isoformat()

    def add_account(self, api_id, api_hash, phone, session_string=None, notes=""):
        account_id = str(uuid.uuid4())

        # Check if phone number already exists
        for existing_account in self.accounts.values():
            if existing_account.phone == phone:
                logger.warning("Account with phone %s already exists", phone)
                return existing_account.account_id

        # Create new account
        account = Account(
            account_id=account_id,
            api_id=api_id,
            api_hash=api_hash,
            phone=phone,
            session_string=session_string
        )

        account.status = AccountStatus.ACTIVE if session_string else AccountStatus.UNVERIFIED
        account.notes = notes
        account.creation_date = datetime.now().isoformat()

        self.accounts[account_id] = account
        self._save_accounts()

        logger.info("Added new account: %s (ID: %s)", phone, account_id)
        return account_id

    def get_account(self, account_id):
        if account_id not in self.accounts:
            raise AccountNotFoundError(
                f"Account with ID {account_id} not found")
        return self.accounts[account_id]

    def get_account_by_phone(self, phone):
        for account in self.accounts.values():
            if account.phone == phone:
                return account
        raise AccountNotFoundError(f"Account with phone {phone} not found")

    def update_account(self, account_id, **kwargs):
        if account_id not in self.accounts:
            raise AccountNotFoundError(
                f"Account with ID {account_id} not found")

        account = self.accounts[account_id]

        # Update account properties
        for key, value in kwargs.items():
            if hasattr(account, key):
                setattr(account, key, value)

        # If updating session_string, make sure account is active
        if 'session_string' in kwargs and kwargs['session_string']:
            account.status = AccountStatus.ACTIVE
            account.status_changed_at = datetime.now()

        self._save_accounts()
        logger.info("Updated account %s (ID: %s)", account.phone, account_id)
        return True

    def remove_account(self, account_id):
        if account_id not in self.accounts:
            raise AccountNotFoundError(
                f"Account with ID {account_id} not found")

        account = self.accounts.pop(account_id)
        self._save_accounts()

        logger.info("Removed account %s (ID: %s)", account.phone, account_id)
        return True

    def get_all_accounts(self):
        return list(self.accounts.values())

    def get_accounts_by_status(self, status):
        if isinstance(status, str):
            status = AccountStatus[status]

        return [account for account in self.accounts.values() if account.status == status]

    def get_available_accounts(self, count=1, for_adding=True):
        self._check_account_statuses()

        active_accounts = self.get_accounts_by_status(AccountStatus.ACTIVE)

        # Filter accounts that haven't reached their daily limit
        if for_adding:
            active_accounts = [
                account for account in active_accounts
                if account.members_added_today < self.max_members_per_day
            ]
        else:
            active_accounts = [
                account for account in active_accounts
                if account.members_extracted_today < self.max_members_per_day
            ]

        # Sort by least used today
        if for_adding:
            active_accounts.sort(key=lambda acc: acc.members_added_today)
        else:
            active_accounts.sort(key=lambda acc: acc.members_extracted_today)

        return active_accounts[:count]

    def update_account_status(self, account_id, status, cooldown_hours=None):
        if account_id not in self.accounts:
            raise AccountNotFoundError(
                f"Account with ID {account_id} not found")

        account = self.accounts[account_id]

        if isinstance(status, str):
            status = AccountStatus[status]

        account.status = status
        account.status_changed_at = datetime.now()

        if status == AccountStatus.COOLDOWN and cooldown_hours:
            account.cooldown_until = datetime.now() + timedelta(hours=cooldown_hours)
            logger.info("Account %s placed in cooldown for %s hours",
                        account.phone, cooldown_hours)
        elif status == AccountStatus.ACTIVE:
            account.cooldown_until = None
            account.failure_count = 0
            logger.info("Account %s set to active status", account.phone)
        elif status == AccountStatus.BLOCKED:
            logger.warning("Account %s has been blocked", account.phone)
        elif status == AccountStatus.DAILY_LIMIT_REACHED:
            logger.info("Account %s has reached daily limit", account.phone)

        self._save_accounts()
        return True

    def increment_member_count(self, account_id, count_type="added"):
        if account_id not in self.accounts:
            raise AccountNotFoundError(
                f"Account with ID {account_id} not found")

        account = self.accounts[account_id]

        if count_type == "added":
            account.members_added_today += 1

            # Check if daily limit reached
            if account.members_added_today >= self.max_members_per_day:
                account.status = AccountStatus.DAILY_LIMIT_REACHED
                account.status_changed_at = datetime.now()
                logger.info(
                    "Account %s reached daily adding limit", account.phone)
        elif count_type == "extracted":
            account.members_extracted_today += 1

            # Check if daily limit reached
            if account.members_extracted_today >= self.max_members_per_day:
                account.status = AccountStatus.DAILY_LIMIT_REACHED
                account.status_changed_at = datetime.now()
                logger.info(
                    "Account %s reached daily extraction limit", account.phone)

        account.total_usage_count += 1
        account.last_used = datetime.now()

        self._save_accounts()
        return True

    def reset_daily_limits(self, account_id=None):
        now = datetime.now()

        if account_id:
            if account_id not in self.accounts:
                raise AccountNotFoundError(
                    f"Account with ID {account_id} not found")

            account = self.accounts[account_id]
            account.members_added_today = 0
            account.members_extracted_today = 0
            account.daily_reset_time = now.isoformat()

            # If account was daily limit reached, set it back to active
            if account.status == AccountStatus.DAILY_LIMIT_REACHED:
                account.status = AccountStatus.ACTIVE
                account.status_changed_at = now

            logger.info("Daily limits reset for account %s", account.phone)
        else:
            # Reset all accounts
            for account in self.accounts.values():
                account.members_added_today = 0
                account.members_extracted_today = 0
                account.daily_reset_time = now.isoformat()

                # If account was daily limit reached, set it back to active
                if account.status == AccountStatus.DAILY_LIMIT_REACHED:
                    account.status = AccountStatus.ACTIVE
                    account.status_changed_at = now

            logger.info("Daily limits reset for all accounts")

        self._save_accounts()
        return True

    def increment_failure_count(self, account_id):
        if account_id not in self.accounts:
            raise AccountNotFoundError(
                f"Account with ID {account_id} not found")

        account = self.accounts[account_id]
        account.failure_count += 1

        # If too many failures, put account in cooldown
        if account.failure_count >= MAX_FAILURES_BEFORE_BLOCK:
            account.status = AccountStatus.COOLDOWN
            account.status_changed_at = datetime.now()
            account.cooldown_until = datetime.now() + timedelta(hours=DEFAULT_COOL_DOWN_HOURS)
            logger.warning(
                "Account %s placed in cooldown due to excessive failures", account.phone)

        self._save_accounts()
        return account.failure_count

    def reset_failure_count(self, account_id):
        if account_id not in self.accounts:
            raise AccountNotFoundError(
                f"Account with ID {account_id} not found")

        account = self.accounts[account_id]
        account.failure_count = 0

        self._save_accounts()
        logger.debug("Reset failure count for account %s", account.phone)
        return True

    def get_account_stats(self):
        total = len(self.accounts)
        active = len([a for a in self.accounts.values()
                     if a.status == AccountStatus.ACTIVE])
        cooldown = len([a for a in self.accounts.values()
                       if a.status == AccountStatus.COOLDOWN])
        blocked = len([a for a in self.accounts.values()
                      if a.status == AccountStatus.BLOCKED])
        unverified = len([a for a in self.accounts.values()
                         if a.status == AccountStatus.UNVERIFIED])
        daily_limit = len([a for a in self.accounts.values()
                          if a.status == AccountStatus.DAILY_LIMIT_REACHED])

        added_today = sum(
            a.members_added_today for a in self.accounts.values())
        extracted_today = sum(
            a.members_extracted_today for a in self.accounts.values())
        total_usage = sum(a.total_usage_count for a in self.accounts.values())

        return {
            "total": total,
            "active": active,
            "cooldown": cooldown,
            "blocked": blocked,
            "unverified": unverified,
            "daily_limit_reached": daily_limit,
            "added_today": added_today,
            "extracted_today": extracted_today,
            "total_usage": total_usage
        }

    def set_session_string(self, account_id, session_string):
        if account_id not in self.accounts:
            raise AccountNotFoundError(
                f"Account with ID {account_id} not found")

        account = self.accounts[account_id]
        account.session_string = session_string

        if account.status == AccountStatus.UNVERIFIED:
            account.status = AccountStatus.ACTIVE
            account.status_changed_at = datetime.now()

        self._save_accounts()
        logger.info("Set session string for account %s", account.phone)
        return True

    def backup_accounts(self, backup_file=None):
        if not backup_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"accounts_backup_{timestamp}.json"

        try:
            accounts_data = {
                'timestamp': datetime.now().isoformat(),
                'accounts': [account.to_dict() for account in self.accounts.values()]
            }

            with open(backup_file, 'w') as file:
                json.dump(accounts_data, file, indent=4)

            logger.info("Accounts backed up to %s", backup_file)
            return backup_file
        except Exception as e:
            logger.error("Error backing up accounts: %s", e)
            return None

    def restore_accounts(self, backup_file):
        try:
            with open(backup_file, 'r') as file:
                accounts_data = json.load(file)

            new_accounts = {}
            for account_data in accounts_data.get('accounts', []):
                account = Account.from_dict(account_data)
                new_accounts[account.account_id] = account

            # Replace current accounts with restored ones
            self.accounts = new_accounts
            self._save_accounts()

            logger.info("Restored %s accounts from %s",
                        len(self.accounts), backup_file)
            return True
        except Exception as e:
            logger.error("Error restoring accounts from backup: %s", e)
            return False

# pylint: disable=C0116  # Missing function or method docstring


def get_account_manager():
    return AccountManager()
