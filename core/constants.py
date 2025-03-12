"""
Constants Module

This module defines all global constants used throughout the application.
Constants are organized by category for better maintainability.
"""

from dataclasses import dataclass
from enum import Enum, auto

# File paths
CONFIG_FILE = ".env.encrypted"
SALT_FILE = ".env.salt"
ENCRYPTION_KEY_FILE = "encryption.key"
ACCOUNTS_FILE = "telegram_accounts.json"
REQUEST_LOG_FILE = "request_log.json"
AI_DATA_FILE = "ai_training_data.json"

# Time-related constants (in seconds)
DEFAULT_DELAY = 20  # Default delay between requests
MAX_DELAY = 300  # Maximum delay between requests
ACCOUNT_CHANGE_DELAY = 60  # Delay between switching accounts

# Limits
MAX_RETRY_COUNT = 5  # Maximum number of retry attempts
MAX_MEMORY_RECORDS = 1000  # Maximum number of records to keep in memory
MAX_FAILURES_BEFORE_BLOCK = 3  # Number of consecutive failures before considering account blocked
MAX_MEMBERS_PER_DAY = 20  # Maximum number of members to extract or add per account per day

# Account statuses
class AccountStatus(Enum):
    """Enum for account status values."""
    ACTIVE = auto()
    COOLDOWN = auto()
    BLOCKED = auto()
    UNVERIFIED = auto()
    DAILY_LIMIT_REACHED = auto()

    @classmethod
    def to_str(cls, status):
        """Convert enum value to string representation."""
        status_map = {
            cls.ACTIVE: "active",
            cls.COOLDOWN: "cooldown",
            cls.BLOCKED: "blocked",
            cls.UNVERIFIED: "unverified",
            cls.DAILY_LIMIT_REACHED: "daily_limit_reached"
        }
        return status_map.get(status, "unknown")

    @classmethod
    def from_str(cls, status_str):
        """Convert string to enum value."""
        status_map = {
            "active": cls.ACTIVE,
            "cooldown": cls.COOLDOWN,
            "blocked": cls.BLOCKED,
            "unverified": cls.UNVERIFIED,
            "daily_limit_reached": cls.DAILY_LIMIT_REACHED
        }
        return status_map.get(status_str.lower(), cls.ACTIVE)


@dataclass(frozen=True)
class Constants:
    """
    Container class for application constants.
    This class groups constants by category for better organization.
    """

    class Files:
        """File-related constants."""
        CONFIG = CONFIG_FILE
        SALT = SALT_FILE
        ENCRYPTION_KEY = ENCRYPTION_KEY_FILE
        ACCOUNTS = ACCOUNTS_FILE
        REQUEST_LOG = REQUEST_LOG_FILE
        AI_DATA = AI_DATA_FILE
        LOG_FILE = "telegram_adder.log"

    class TimeDelays:
        """Time-related constants in seconds."""
        DEFAULT = DEFAULT_DELAY
        MAXIMUM = MAX_DELAY
        ACCOUNT_CHANGE = ACCOUNT_CHANGE_DELAY

    class Limits:
        """Operation limit constants."""
        MAX_RETRY = MAX_RETRY_COUNT
        MAX_MEMORY_RECORDS = MAX_MEMORY_RECORDS
        MAX_FAILURES = MAX_FAILURES_BEFORE_BLOCK
        MAX_MEMBERS_PER_DAY = MAX_MEMBERS_PER_DAY

    class ProxyDefaults:
        """Default proxy settings."""
        TYPE = "socks5"
        PORT = 1080
        TIMEOUT = 30

    # Account statuses
    AccountStatus = AccountStatus