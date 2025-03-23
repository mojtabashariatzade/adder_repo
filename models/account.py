"""
Account Models Module

This module defines data models for Telegram accounts used in the application.
It provides classes for managing account data, status tracking, and usage metrics.

Key features:
- Account class for storing and managing Telegram account details
- AccountStatus management (active, cooldown, blocked, etc.)
- AccountMetrics for tracking usage statistics
- Daily limits management for account operations
- Methods for account validation and status checks
- Support for serialization/deserialization

Usage:
    from models.account import Account, AccountMetrics, AccountFactory

    # Create a new account
    account = Account(api_id=12345, api_hash="hash", phone="+123456789")

    # Check account status
    if account.is_active():
        # Use account
        account.increment_usage_metric("members_added")

    # Handle cooldown
    if account.is_in_cooldown():
        cooldown_remaining = account.get_cooldown_remaining()
        print(f"Account in cooldown for {cooldown_remaining} more seconds")

    # Track metrics
    metrics = account.get_metrics()
    print(f"Today's usage: {metrics.members_added_today}/{metrics.daily_limit}")
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
import uuid
import logging
from dataclasses import dataclass, field, asdict
import time

# Import from core modules
from core.constants import AccountStatus, MAX_MEMBERS_PER_DAY, MAX_FAILURES_BEFORE_BLOCK

# Setup logger
try:
    from logging_.logging_manager import get_logger
    logger = get_logger("AccountModel")
except ImportError:
    # Fallback to standard logging if custom logger is not available
    logger = logging.getLogger("AccountModel")


@dataclass
class AccountMetrics:
    """
    Data class for tracking account usage metrics.

    This class tracks various metrics related to account usage,
    such as number of members added/extracted, success rates,
    and historical usage patterns.
    """
    # Daily usage metrics (reset daily)
    members_added_today: int = 0
    members_extracted_today: int = 0
    operations_succeeded_today: int = 0
    operations_failed_today: int = 0

    # All-time metrics
    total_members_added: int = 0
    total_members_extracted: int = 0
    total_operations_succeeded: int = 0
    total_operations_failed: int = 0

    # Limit tracking
    daily_limit: int = MAX_MEMBERS_PER_DAY
    daily_reset_time: str = field(
        default_factory=lambda: datetime.now().isoformat())

    # Performance metrics
    average_success_rate: float = 100.0
    consecutive_failures: int = 0

    # Advanced metrics for analytics
    hourly_usage: Dict[int, int] = field(default_factory=dict)
    daily_usage: Dict[str, int] = field(default_factory=dict)

    def reset_daily_metrics(self) -> None:
        """Reset all daily metrics to zero and update reset time."""
        self.members_added_today = 0
        self.members_extracted_today = 0
        self.operations_succeeded_today = 0
        self.operations_failed_today = 0
        # Force a small sleep to ensure a different timestamp
        time.sleep(0.001)
        self.daily_reset_time = datetime.now().isoformat()

    def check_daily_reset(self) -> bool:
        """Check if daily metrics need to be reset based on time elapsed."""
        try:
            last_reset = datetime.fromisoformat(self.daily_reset_time)
            now = datetime.now()

            # Reset if it's been more than 24 hours since the last reset
            if (now - last_reset).total_seconds() > 86400:  # 24 hours in seconds
                self.reset_daily_metrics()
                return True
        except (ValueError, TypeError):
            # Handle invalid datetime format
            self.reset_daily_metrics()
            return True

        return False

    def increment_metric(self, metric_name: str, value: int = 1) -> None:
        """
        Increment a specific metric by the given value.

        Args:
            metric_name: Name of the metric to increment
            value: Value to increment by (default: 1)
        """
        # Check for daily reset first
        self.check_daily_reset()

        # Update the specified metric
        if hasattr(self, metric_name):
            current_value = getattr(self, metric_name)
            if isinstance(current_value, (int, float)):
                setattr(self, metric_name, current_value + value)

                # Track hourly usage for analytics
                hour = datetime.now().hour
                self.hourly_usage[hour] = self.hourly_usage.get(
                    hour, 0) + value

                # Track daily usage for analytics
                day = datetime.now().strftime("%Y-%m-%d")
                self.daily_usage[day] = self.daily_usage.get(day, 0) + value
            else:
                logger.warning(
                    "Cannot increment non-numeric metric: %s", metric_name)
        else:
            logger.warning("Unknown metric: %s", metric_name)

    def is_daily_limit_reached(self) -> bool:
        """Check if daily membership limit has been reached."""
        # Check for daily reset first
        self.check_daily_reset()

        # Check if either adding or extracting limit is reached
        return (self.members_added_today >= self.daily_limit or
                self.members_extracted_today >= self.daily_limit)

    def update_success_rate(self) -> float:
        """Update and return the average success rate."""
        total_ops = self.total_operations_succeeded + self.total_operations_failed
        if total_ops > 0:
            self.average_success_rate = (
                self.total_operations_succeeded / total_ops) * 100.0
        else:
            self.average_success_rate = 100.0

        return self.average_success_rate

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccountMetrics':
        """Create an AccountMetrics instance from a dictionary."""
        # Filter out unknown fields to prevent __init__ errors
        known_fields = {k: v for k,
                        v in data.items() if k in cls.__annotations__}
        return cls(**known_fields)


class Account:
    """
    Class representing a Telegram account.

    This class manages all aspects of a Telegram account, including
    credentials, status, metrics, and related functionality.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_string: Optional[str] = None,
        account_id: Optional[str] = None,
        status: Union[AccountStatus, str] = AccountStatus.UNVERIFIED,
        metrics: Optional[Union[AccountMetrics, Dict[str, Any]]] = None,
        notes: str = "",
        **kwargs
    ):
        """
        Initialize a new Account instance.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
            phone: Phone number with country code
            session_string: Telethon session string if available
            account_id: Unique identifier for the account (generated if None)
            status: Initial account status
            metrics: AccountMetrics instance or dict for account metrics
            notes: Additional notes about the account
            **kwargs: Additional custom data for the account
        """
        # Core account details
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_string = session_string
        self.account_id = account_id or str(uuid.uuid4())

        # Set status (convert from string if needed)
        if isinstance(status, str):
            self.status = AccountStatus.from_str(status)
        else:
            self.status = status

        # Status-related fields
        self.cooldown_until = None
        self.last_used = None
        self.last_error = None
        self.failure_count = 0

        # Set or create metrics
        if metrics is None:
            self.metrics = AccountMetrics()
        elif isinstance(metrics, dict):
            self.metrics = AccountMetrics.from_dict(metrics)
        else:
            self.metrics = metrics

        # Additional properties
        self.added_date = datetime.now().isoformat()
        self.last_updated = self.added_date
        self.notes = notes
        self.proxy_config = None
        self.custom_data = kwargs.pop(
            "custom_data", {}) if "custom_data" in kwargs else {}

    def update_last_used(self) -> None:
        """Update the last used timestamp to current time."""
        self.last_used = datetime.now().isoformat()
        self.last_updated = self.last_used

    def set_status(self, status: Union[AccountStatus, str],
                   cooldown_hours: Optional[int] = None) -> None:
        """
        Set the account status and handle related state changes.

        Args:
            status: New status value
            cooldown_hours: Hours to set cooldown for (if status is COOLDOWN)
        """
        # Convert string status to enum if needed
        if isinstance(status, str):
            status = AccountStatus.from_str(status)

        # Handle specific status transitions
        if status == AccountStatus.ACTIVE:
            # Reset failure count when activating
            self.failure_count = 0
            self.cooldown_until = None

        elif status == AccountStatus.COOLDOWN and cooldown_hours:
            # Set cooldown expiration time
            cooldown_until = datetime.now() + timedelta(hours=cooldown_hours)
            self.cooldown_until = cooldown_until.isoformat()
            logger.info(
                "Account %s set to cooldown until %s", self.phone, self.cooldown_until
            )

        elif status == AccountStatus.DAILY_LIMIT_REACHED:
            # Log when daily limit is reached
            logger.warning("Daily limit reached for account %s", self.phone)

        # Update the status and timestamps
        self.status = status
        self.update_last_used()

        logger.info(
            "Account %s status changed to %s", self.phone, AccountStatus.to_str(
                status)
        )

    def increment_failure_count(self) -> int:
        """
        Increment the failure count and handle cooldown if needed.

        Returns:
            int: Updated failure count
        """
        self.failure_count += 1
        self.metrics.consecutive_failures += 1
        self.metrics.increment_metric("operations_failed_today")
        self.metrics.increment_metric("total_operations_failed")

        # Update timestamp
        self.update_last_used()

        # Check if account should be put in cooldown
        if self.failure_count >= MAX_FAILURES_BEFORE_BLOCK:
            logger.warning(
                "Account %s reached max failures (%d), setting to cooldown",
                self.phone, self.failure_count
            )
            self.set_status(AccountStatus.COOLDOWN, cooldown_hours=6)

        return self.failure_count

    def reset_failure_count(self) -> None:
        """Reset the failure count to zero."""
        self.failure_count = 0
        self.metrics.consecutive_failures = 0
        self.update_last_used()

    def record_success(self, operation_type: str = None) -> None:
        """
        Record a successful operation and update metrics.

        Args:
            operation_type: Type of operation (e.g., 'add', 'extract')
        """
        # Reset failure counters
        self.reset_failure_count()

        # Update metrics
        self.metrics.increment_metric("operations_succeeded_today")
        self.metrics.increment_metric("total_operations_succeeded")

        # Update specific operation metrics if provided
        if operation_type == 'add':
            self.metrics.increment_metric("members_added_today")
            self.metrics.increment_metric("total_members_added")
        elif operation_type == 'extract':
            self.metrics.increment_metric("members_extracted_today")
            self.metrics.increment_metric("total_members_extracted")

        # Update success rate
        self.metrics.update_success_rate()

        # Update timestamp
        self.update_last_used()

    def is_active(self) -> bool:
        """Check if account is in active status and ready to use."""
        # First check for daily reset
        self.metrics.check_daily_reset()

        # If account is in ACTIVE status but has reached daily limit,
        # update status to DAILY_LIMIT_REACHED
        if (self.status == AccountStatus.ACTIVE and
                self.metrics.is_daily_limit_reached()):
            self.set_status(AccountStatus.DAILY_LIMIT_REACHED)
            return False

        # Check if account is in COOLDOWN but cooldown period has expired
        if self.status == AccountStatus.COOLDOWN and self.cooldown_until:
            try:
                cooldown_until = datetime.fromisoformat(self.cooldown_until)
                if datetime.now() > cooldown_until:
                    # Cooldown period has expired, set to ACTIVE
                    self.set_status(AccountStatus.ACTIVE)
                    return True
                return False
            except (ValueError, TypeError):
                # Invalid datetime format
                logger.warning(
                    "Invalid cooldown_until format for account %s", self.phone
                )
                self.cooldown_until = None
                return False

        # Check if account is in DAILY_LIMIT_REACHED but day has reset
        if self.status == AccountStatus.DAILY_LIMIT_REACHED:
            if not self.metrics.is_daily_limit_reached():
                # Daily limit no longer reached, set to ACTIVE
                self.set_status(AccountStatus.ACTIVE)
                return True
            return False

        # Return True only if status is ACTIVE
        return self.status == AccountStatus.ACTIVE

    def is_in_cooldown(self) -> bool:
        """Check if account is in cooldown period."""
        if self.status != AccountStatus.COOLDOWN:
            return False

        if not self.cooldown_until:
            return False

        try:
            cooldown_until = datetime.fromisoformat(self.cooldown_until)
            return datetime.now() < cooldown_until
        except (ValueError, TypeError):
            return False

    def get_cooldown_remaining(self) -> int:
        """
        Get the remaining cooldown time in seconds.

        Returns:
            int: Seconds remaining in cooldown, or 0 if not in cooldown
        """
        if not self.is_in_cooldown() or not self.cooldown_until:
            return 0

        try:
            cooldown_until = datetime.fromisoformat(self.cooldown_until)
            remaining = (cooldown_until - datetime.now()).total_seconds()
            return max(0, int(remaining))
        except (ValueError, TypeError):
            return 0

    def can_add_members(self) -> bool:
        """Check if account can add members (active and below daily limit)."""
        if not self.is_active():
            return False

        # Check if daily adding limit is reached
        return self.metrics.members_added_today < self.metrics.daily_limit

    def can_extract_members(self) -> bool:
        """Check if account can extract members (active and below daily limit)."""
        if not self.is_active():
            return False

        # Check if daily extraction limit is reached
        return self.metrics.members_extracted_today < self.metrics.daily_limit

    def reset_daily_limits(self) -> None:
        """Reset daily usage limits and update status if needed."""
        self.metrics.reset_daily_metrics()

        # If account was in DAILY_LIMIT_REACHED, set back to ACTIVE
        if self.status == AccountStatus.DAILY_LIMIT_REACHED:
            self.set_status(AccountStatus.ACTIVE)

        self.update_last_used()
        logger.info("Daily limits reset for account %s", self.phone)

    def set_proxy_config(self, proxy_config: Dict[str, Any]) -> None:
        """
        Set proxy configuration for this account.

        Args:
            proxy_config: Proxy configuration dict
        """
        self.proxy_config = proxy_config
        self.last_updated = datetime.now().isoformat()

    def get_remaining_daily_capacity(self) -> Dict[str, int]:
        """
        Get the remaining capacity for daily operations.

        Returns:
            Dict with remaining add and extract capacity
        """
        # Check for daily reset first
        self.metrics.check_daily_reset()

        return {
            "add": max(0, self.metrics.daily_limit - self.metrics.members_added_today),
            "extract": max(0, self.metrics.daily_limit - self.metrics.members_extracted_today)
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the account to a dictionary for serialization.

        Returns:
            Dict: Account data in dictionary format
        """
        return {
            "account_id": self.account_id,
            "api_id": self.api_id,
            "api_hash": self.api_hash,
            "phone": self.phone,
            "session_string": self.session_string,
            "status": AccountStatus.to_str(self.status),
            "cooldown_until": self.cooldown_until,
            "last_used": self.last_used,
            "last_error": self.last_error,
            "failure_count": self.failure_count,
            "added_date": self.added_date,
            "last_updated": self.last_updated,
            "notes": self.notes,
            "proxy_config": self.proxy_config,
            "metrics": self.metrics.to_dict(),
            "custom_data": self.custom_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Account':
        """
        Create an Account instance from a dictionary.

        Args:
            data: Dictionary containing account data

        Returns:
            Account: The created Account instance
        """
        # Extract core parameters
        api_id = data.get("api_id")
        api_hash = data.get("api_hash")
        phone = data.get("phone")

        if not all([api_id, api_hash, phone]):
            raise ValueError(
                "Missing required account data: api_id, api_hash, and phone are required")

        # Extract other parameters
        session_string = data.get("session_string")
        account_id = data.get("account_id")
        status = data.get("status", AccountStatus.UNVERIFIED)
        metrics = data.get("metrics", {})
        notes = data.get("notes", "")

        # Create account with core parameters
        account = cls(
            api_id=api_id,
            api_hash=api_hash,
            phone=phone,
            session_string=session_string,
            account_id=account_id,
            status=status,
            metrics=metrics,
            notes=notes
        )

        # Set additional fields
        account.cooldown_until = data.get("cooldown_until")
        account.last_used = data.get("last_used")
        account.last_error = data.get("last_error")
        account.failure_count = data.get("failure_count", 0)
        account.added_date = data.get("added_date", account.added_date)
        account.last_updated = data.get("last_updated", account.last_updated)
        account.proxy_config = data.get("proxy_config")
        account.custom_data = data.get("custom_data", {})

        return account

    def __str__(self) -> str:
        """String representation of the account."""
        status_str = AccountStatus.to_str(self.status)
        return f"Account(phone={self.phone}, status={status_str}, id={self.account_id})"

    def __repr__(self) -> str:
        """Detailed representation of the account."""
        return (f"Account(account_id={self.account_id!r}, "
                f"phone={self.phone!r}, "
                f"api_id={self.api_id!r}, "
                f"status={AccountStatus.to_str(self.status)!r})")


class AccountFactory:
    """
    Factory class for creating and managing Account instances.

    This class provides utility methods for creating accounts with
    different configurations and validating account data.
    """

    @staticmethod
    def create_account(api_id: int, api_hash: str, phone: str,
                       session_string: Optional[str] = None,
                       **kwargs) -> Account:
        """
        Create a new account with the given parameters.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
            phone: Phone number with country code
            session_string: Telethon session string if available
            **kwargs: Additional account parameters

        Returns:
            Account: The created Account instance
        """
        # Validate input
        AccountFactory.validate_account_data(api_id, api_hash, phone)

        # Determine initial status
        status = AccountStatus.ACTIVE if session_string else AccountStatus.UNVERIFIED
        if 'status' in kwargs:
            status = kwargs.pop('status')

        # Create account
        account = Account(
            api_id=api_id,
            api_hash=api_hash,
            phone=phone,
            session_string=session_string,
            status=status,
            **kwargs
        )

        logger.info("Created new account: %s", account)
        return account

    @staticmethod
    def validate_account_data(api_id: Any, api_hash: Any, phone: Any) -> None:
        """
        Validate account data formats.

        Args:
            api_id: Telegram API ID to validate
            api_hash: Telegram API hash to validate
            phone: Phone number to validate

        Raises:
            ValueError: If any validation fails
        """
        # Validate API ID
        try:
            api_id_int = int(api_id)
            if api_id_int <= 0:
                raise ValueError("API ID must be a positive integer")
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid API ID: {api_id}. Must be a positive integer.") from exc

        # Validate API hash
        if not isinstance(api_hash, str) or len(api_hash) < 5:
            raise ValueError(
                f"Invalid API hash: {api_hash}. Must be a non-empty string.")

        # Basic phone validation (could be enhanced)
        if not isinstance(phone, str) or not phone.strip():
            raise ValueError(
                f"Invalid phone number: {phone}. Must be a non-empty string.")

        # Check phone format
        phone = phone.strip()
        if not (phone.startswith('+') and phone[1:].isdigit()):
            raise ValueError(
                f"Invalid phone format: {phone}. Must start with '+' followed by digits.")

    @staticmethod
    def from_telethon_client(client, phone: Optional[str] = None) -> Account:
        """
        Create an Account instance from a Telethon client.

        Args:
            client: The Telethon client object
            phone: Phone number (if not available from client)

        Returns:
            Account: The created Account instance
        """
        if not hasattr(client, 'api_id') or not hasattr(client, 'api_hash'):
            raise ValueError(
                "Invalid Telethon client: missing api_id or api_hash")

        # Get phone from client if not provided
        if not phone and hasattr(client, 'phone'):
            phone = client.phone

        if not phone:
            raise ValueError("Phone number is required")

        # Get session string if available
        session_string = None
        if hasattr(client, 'session') and hasattr(client.session, 'save'):
            try:
                session_string = client.session.save()
            except (AttributeError, IOError) as e:
                logger.warning("Failed to save session string: %s", e)

        # Create account
        return AccountFactory.create_account(
            api_id=client.api_id,
            api_hash=client.api_hash,
            phone=phone,
            session_string=session_string,
            status=AccountStatus.ACTIVE if session_string else AccountStatus.UNVERIFIED
        )
