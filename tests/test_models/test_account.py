"""
Test module for models/account.py

This module contains unit tests for the Account class and related components
in the models/account.py module.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json
from datetime import datetime, timedelta
import time

# Fallback in case import from constants fails
if 'MAX_FAILURES_BEFORE_BLOCK' not in globals():
    MAX_FAILURES_BEFORE_BLOCK = 3

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the module being tested
from models.account import Account, AccountMetrics, AccountFactory, AccountStatus
from core.constants import MAX_FAILURES_BEFORE_BLOCK


class TestAccountMetrics(unittest.TestCase):
    """Test case for the AccountMetrics class."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: models/account.py - AccountMetrics")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: AccountMetrics")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up before each test method."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        # Create a test metrics instance
        self.metrics = AccountMetrics()

    def tearDown(self):
        """Tear down after each test method."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_reset_daily_metrics(self):
        """Test resetting daily metrics."""
        # Set some initial values
        self.metrics.members_added_today = 10
        self.metrics.members_extracted_today = 5
        self.metrics.operations_succeeded_today = 15
        self.metrics.operations_failed_today = 3

        # Keep track of old reset time
        old_reset_time = self.metrics.daily_reset_time

        # Reset daily metrics
        self.metrics.reset_daily_metrics()

        # Check that daily metrics were reset to zero
        self.assertEqual(self.metrics.members_added_today, 0)
        self.assertEqual(self.metrics.members_extracted_today, 0)
        self.assertEqual(self.metrics.operations_succeeded_today, 0)
        self.assertEqual(self.metrics.operations_failed_today, 0)

        # Check that reset time was updated
        self.assertNotEqual(self.metrics.daily_reset_time, old_reset_time)

    def test_check_daily_reset_not_needed(self):
        """Test checking if daily reset is needed when it's not."""
        # Set reset time to current time
        self.metrics.daily_reset_time = datetime.now().isoformat()
        self.metrics.members_added_today = 10

        # Check if reset is needed (should not be)
        reset_occurred = self.metrics.check_daily_reset()

        # Verify reset did not occur
        self.assertFalse(reset_occurred)
        self.assertEqual(self.metrics.members_added_today, 10)

    def test_check_daily_reset_needed(self):
        """Test checking if daily reset is needed when it is."""
        # Set reset time to more than 24 hours ago
        past_time = datetime.now() - timedelta(hours=25)
        self.metrics.daily_reset_time = past_time.isoformat()
        self.metrics.members_added_today = 10

        # Check if reset is needed (should be)
        reset_occurred = self.metrics.check_daily_reset()

        # Verify reset occurred
        self.assertTrue(reset_occurred)
        self.assertEqual(self.metrics.members_added_today, 0)

    def test_check_daily_reset_invalid_format(self):
        """Test checking daily reset with invalid datetime format."""
        # Set invalid reset time
        self.metrics.daily_reset_time = "not-a-datetime"
        self.metrics.members_added_today = 10

        # Check if reset is needed (should reset due to invalid format)
        reset_occurred = self.metrics.check_daily_reset()

        # Verify reset occurred
        self.assertTrue(reset_occurred)
        self.assertEqual(self.metrics.members_added_today, 0)

    def test_increment_metric(self):
        """Test incrementing a metric."""
        # Initialize with zero
        self.assertEqual(self.metrics.members_added_today, 0)

        # Increment by default value (1)
        self.metrics.increment_metric("members_added_today")
        self.assertEqual(self.metrics.members_added_today, 1)

        # Increment by specific value
        self.metrics.increment_metric("members_added_today", 5)
        self.assertEqual(self.metrics.members_added_today, 6)

        # Verify hourly usage tracking
        hour = datetime.now().hour
        self.assertIn(hour, self.metrics.hourly_usage)
        self.assertEqual(self.metrics.hourly_usage[hour], 6)

        # Verify daily usage tracking
        day = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(day, self.metrics.daily_usage)
        self.assertEqual(self.metrics.daily_usage[day], 6)

    def test_increment_invalid_metric(self):
        """Test incrementing a non-existent metric."""
        # Try to increment non-existent metric (should log warning, not error)
        self.metrics.increment_metric("non_existent_metric")
        # No assertion needed - just checking it doesn't raise an exception

    def test_increment_non_numeric_metric(self):
        """Test incrementing a non-numeric metric."""
        # Add a non-numeric attribute
        self.metrics.string_attribute = "string"

        # Try to increment non-numeric metric (should log warning, not error)
        self.metrics.increment_metric("string_attribute")
        self.assertEqual(self.metrics.string_attribute, "string")  # Should remain unchanged

    def test_is_daily_limit_reached(self):
        """Test checking if daily limit is reached."""
        # Set daily limit
        self.metrics.daily_limit = 20

        # Test when neither limit is reached
        self.metrics.members_added_today = 10
        self.metrics.members_extracted_today = 15
        self.assertFalse(self.metrics.is_daily_limit_reached())

        # Test when adding limit is reached
        self.metrics.members_added_today = 20
        self.metrics.members_extracted_today = 15
        self.assertTrue(self.metrics.is_daily_limit_reached())

        # Test when extracting limit is reached
        self.metrics.members_added_today = 10
        self.metrics.members_extracted_today = 20
        self.assertTrue(self.metrics.is_daily_limit_reached())

        # Test when both limits are reached
        self.metrics.members_added_today = 20
        self.metrics.members_extracted_today = 20
        self.assertTrue(self.metrics.is_daily_limit_reached())

    def test_update_success_rate(self):
        """Test updating success rate calculation."""
        # Set initial values
        self.metrics.total_operations_succeeded = 80
        self.metrics.total_operations_failed = 20

        # Update success rate
        rate = self.metrics.update_success_rate()

        # Verify calculation (80 / (80 + 20) * 100 = 80%)
        self.assertEqual(rate, 80.0)
        self.assertEqual(self.metrics.average_success_rate, 80.0)

        # Test with no operations
        self.metrics.total_operations_succeeded = 0
        self.metrics.total_operations_failed = 0
        rate = self.metrics.update_success_rate()

        # Should default to 100% when no operations
        self.assertEqual(rate, 100.0)
        self.assertEqual(self.metrics.average_success_rate, 100.0)

    def test_to_from_dict(self):
        """Test conversion to and from dictionary representation."""
        # Set some values
        self.metrics.members_added_today = 10
        self.metrics.total_members_added = 100
        self.metrics.daily_limit = 30
        self.metrics.average_success_rate = 85.5
        self.metrics.hourly_usage = {10: 25, 14: 75}

        # Convert to dictionary
        metrics_dict = self.metrics.to_dict()

        # Verify dictionary contains expected keys and values
        self.assertEqual(metrics_dict["members_added_today"], 10)
        self.assertEqual(metrics_dict["total_members_added"], 100)
        self.assertEqual(metrics_dict["daily_limit"], 30)
        self.assertEqual(metrics_dict["average_success_rate"], 85.5)
        self.assertEqual(metrics_dict["hourly_usage"], {10: 25, 14: 75})

        # Create a new metrics instance from the dictionary
        new_metrics = AccountMetrics.from_dict(metrics_dict)

        # Verify values are preserved
        self.assertEqual(new_metrics.members_added_today, 10)
        self.assertEqual(new_metrics.total_members_added, 100)
        self.assertEqual(new_metrics.daily_limit, 30)
        self.assertEqual(new_metrics.average_success_rate, 85.5)
        self.assertEqual(new_metrics.hourly_usage, {10: 25, 14: 75})

    def test_from_dict_with_unknown_fields(self):
        """Test creating metrics from dict with unknown fields."""
        # Create dict with valid and invalid fields
        metrics_dict = {
            "members_added_today": 10,
            "total_members_added": 100,
            "invalid_field": "should be ignored",
            "another_invalid": 123
        }

        # Create metrics from dict - should not raise exception
        metrics = AccountMetrics.from_dict(metrics_dict)

        # Check that valid fields were set
        self.assertEqual(metrics.members_added_today, 10)
        self.assertEqual(metrics.total_members_added, 100)

        # Check that invalid fields were ignored
        self.assertFalse(hasattr(metrics, "invalid_field"))
        self.assertFalse(hasattr(metrics, "another_invalid"))


class TestAccount(unittest.TestCase):
    """Test case for the Account class."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: models/account.py - Account")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: Account")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up before each test method."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        # Create a test account
        self.account = Account(
            api_id=12345,
            api_hash="test_hash",
            phone="+1234567890",
            session_string="test_session_string",
            account_id="test_account_id",
            status=AccountStatus.ACTIVE
        )

    def tearDown(self):
        """Tear down after each test method."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_initialization(self):
        """Test account initialization."""
        # Check core attributes
        self.assertEqual(self.account.api_id, 12345)
        self.assertEqual(self.account.api_hash, "test_hash")
        self.assertEqual(self.account.phone, "+1234567890")
        self.assertEqual(self.account.session_string, "test_session_string")
        self.assertEqual(self.account.account_id, "test_account_id")
        self.assertEqual(self.account.status, AccountStatus.ACTIVE)

        # Check default values
        self.assertIsNone(self.account.cooldown_until)
        self.assertIsNone(self.account.last_used)
        self.assertEqual(self.account.failure_count, 0)
        self.assertIsInstance(self.account.metrics, AccountMetrics)
        self.assertEqual(self.account.notes, "")
        self.assertEqual(self.account.custom_data, {})

    def test_initialization_with_string_status(self):
        """Test account initialization with string status."""
        account = Account(
            api_id=12345,
            api_hash="test_hash",
            phone="+1234567890",
            status="cooldown"
        )

        self.assertEqual(account.status, AccountStatus.COOLDOWN)

    def test_initialization_with_metrics_dict(self):
        """Test account initialization with metrics dictionary."""
        metrics_dict = {
            "members_added_today": 10,
            "total_members_added": 100,
            "daily_limit": 30
        }

        account = Account(
            api_id=12345,
            api_hash="test_hash",
            phone="+1234567890",
            metrics=metrics_dict
        )

        self.assertEqual(account.metrics.members_added_today, 10)
        self.assertEqual(account.metrics.total_members_added, 100)
        self.assertEqual(account.metrics.daily_limit, 30)

    def test_update_last_used(self):
        """Test updating last used timestamp."""
        initial_last_updated = self.account.last_updated

        # Sleep a short time to ensure timestamp changes
        time.sleep(0.01)

        # Update last used
        self.account.update_last_used()

        # Check that timestamps were updated
        self.assertIsNotNone(self.account.last_used)
        self.assertIsNotNone(self.account.last_updated)
        self.assertNotEqual(self.account.last_updated, initial_last_updated)

        # Check correct format
        try:
            datetime.fromisoformat(self.account.last_used)
            datetime.fromisoformat(self.account.last_updated)
        except ValueError:
            self.fail("Invalid datetime format in last_used or last_updated")

    def test_set_status_active(self):
        """Test setting account status to active."""
        # Set up account in cooldown
        self.account.failure_count = 5
        self.account.cooldown_until = datetime.now().isoformat()

        # Set to active
        self.account.set_status(AccountStatus.ACTIVE)

        # Check status changes
        self.assertEqual(self.account.status, AccountStatus.ACTIVE)
        self.assertEqual(self.account.failure_count, 0)
        self.assertIsNone(self.account.cooldown_until)

    def test_set_status_cooldown(self):
        """Test setting account status to cooldown."""
        # Set to cooldown with cooldown hours
        cooldown_hours = 6
        self.account.set_status(AccountStatus.COOLDOWN, cooldown_hours=cooldown_hours)

        # Check status changes
        self.assertEqual(self.account.status, AccountStatus.COOLDOWN)
        self.assertIsNotNone(self.account.cooldown_until)

        # Verify cooldown time is approximately correct (within 5 seconds)
        expected_time = datetime.now() + timedelta(hours=cooldown_hours)
        cooldown_time = datetime.fromisoformat(self.account.cooldown_until)
        time_diff = abs((expected_time - cooldown_time).total_seconds())
        self.assertLess(time_diff, 5)

    def test_set_status_with_string(self):
        """Test setting account status with string value."""
        # Set to cooldown using string
        self.account.set_status("cooldown", cooldown_hours=1)

        # Check status changes
        self.assertEqual(self.account.status, AccountStatus.COOLDOWN)
        self.assertIsNotNone(self.account.cooldown_until)

    def test_increment_failure_count(self):
        """Test incrementing failure count."""
        # Check initial count
        self.assertEqual(self.account.failure_count, 0)
        self.assertEqual(self.account.metrics.consecutive_failures, 0)

        # Increment once
        self.account.increment_failure_count()
        self.assertEqual(self.account.failure_count, 1)
        self.assertEqual(self.account.metrics.consecutive_failures, 1)
        self.assertEqual(self.account.metrics.operations_failed_today, 1)
        self.assertEqual(self.account.metrics.total_operations_failed, 1)

        # Increment again
        self.account.increment_failure_count()
        self.assertEqual(self.account.failure_count, 2)
        self.assertEqual(self.account.metrics.consecutive_failures, 2)

        # Increment to trigger cooldown
        for _ in range(MAX_FAILURES_BEFORE_BLOCK - 2):
            self.account.increment_failure_count()

        # Check cooldown was triggered
        self.assertEqual(self.account.status, AccountStatus.COOLDOWN)
        self.assertIsNotNone(self.account.cooldown_until)

    def test_reset_failure_count(self):
        """Test resetting failure count."""
        # Set up non-zero counts
        self.account.failure_count = 3
        self.account.metrics.consecutive_failures = 3

        # Reset count
        self.account.reset_failure_count()

        # Check counts were reset
        self.assertEqual(self.account.failure_count, 0)
        self.assertEqual(self.account.metrics.consecutive_failures, 0)

    def test_record_success(self):
        """Test recording a successful operation."""
        # Set up non-zero failure counts
        self.account.failure_count = 3
        self.account.metrics.consecutive_failures = 3

        # Record generic success
        self.account.record_success()

        # Check counts were reset
        self.assertEqual(self.account.failure_count, 0)
        self.assertEqual(self.account.metrics.consecutive_failures, 0)

        # Check success metrics
        self.assertEqual(self.account.metrics.operations_succeeded_today, 1)
        self.assertEqual(self.account.metrics.total_operations_succeeded, 1)

        # Record add success
        self.account.record_success("add")

        # Check specific metrics
        self.assertEqual(self.account.metrics.members_added_today, 1)
        self.assertEqual(self.account.metrics.total_members_added, 1)

        # Record extract success
        self.account.record_success("extract")

        # Check specific metrics
        self.assertEqual(self.account.metrics.members_extracted_today, 1)
        self.assertEqual(self.account.metrics.total_members_extracted, 1)

    def test_is_active_with_active_status(self):
        """Test is_active method with ACTIVE status."""
        # Set status to ACTIVE
        self.account.status = AccountStatus.ACTIVE

        # Check is_active
        self.assertTrue(self.account.is_active())

    def test_is_active_with_daily_limit_reached(self):
        """Test is_active method with daily limit reached."""
        # Set status to ACTIVE but daily limit reached
        self.account.status = AccountStatus.ACTIVE
        self.account.metrics.members_added_today = self.account.metrics.daily_limit

        # Check is_active (should change status to DAILY_LIMIT_REACHED)
        self.assertFalse(self.account.is_active())
        self.assertEqual(self.account.status, AccountStatus.DAILY_LIMIT_REACHED)

    def test_is_active_with_cooldown_expired(self):
        """Test is_active method with expired cooldown."""
        # Set status to COOLDOWN but cooldown period expired
        self.account.status = AccountStatus.COOLDOWN
        self.account.cooldown_until = (datetime.now() - timedelta(hours=1)).isoformat()

        # Check is_active (should change status to ACTIVE)
        self.assertTrue(self.account.is_active())
        self.assertEqual(self.account.status, AccountStatus.ACTIVE)

    def test_is_active_with_cooldown_not_expired(self):
        """Test is_active method with not expired cooldown."""
        # Set status to COOLDOWN with future cooldown time
        self.account.status = AccountStatus.COOLDOWN
        self.account.cooldown_until = (datetime.now() + timedelta(hours=1)).isoformat()

        # Check is_active
        self.assertFalse(self.account.is_active())
        self.assertEqual(self.account.status, AccountStatus.COOLDOWN)

    def test_is_active_with_daily_limit_reached_but_day_reset(self):
        """Test is_active with DAILY_LIMIT_REACHED but day has reset."""
        # Set status to DAILY_LIMIT_REACHED but reset day
        self.account.status = AccountStatus.DAILY_LIMIT_REACHED
        self.account.metrics.daily_reset_time = (datetime.now() - timedelta(hours=25)).isoformat()
        self.account.metrics.members_added_today = self.account.metrics.daily_limit

        # Check is_active (should reset daily metrics and change status to ACTIVE)
        self.assertTrue(self.account.is_active())
        self.assertEqual(self.account.status, AccountStatus.ACTIVE)
        self.assertEqual(self.account.metrics.members_added_today, 0)

    def test_is_in_cooldown(self):
        """Test is_in_cooldown method."""
        # Not in cooldown
        self.account.status = AccountStatus.ACTIVE
        self.assertFalse(self.account.is_in_cooldown())

        # In cooldown but no cooldown_until
        self.account.status = AccountStatus.COOLDOWN
        self.account.cooldown_until = None
        self.assertFalse(self.account.is_in_cooldown())

        # In cooldown with future cooldown_until
        self.account.status = AccountStatus.COOLDOWN
        self.account.cooldown_until = (datetime.now() + timedelta(hours=1)).isoformat()
        self.assertTrue(self.account.is_in_cooldown())

        # In cooldown but cooldown_until in past
        self.account.cooldown_until = (datetime.now() - timedelta(hours=1)).isoformat()
        self.assertFalse(self.account.is_in_cooldown())

        # In cooldown with invalid cooldown_until
        self.account.cooldown_until = "invalid-date"
        self.assertFalse(self.account.is_in_cooldown())

    def test_get_cooldown_remaining(self):
        """Test get_cooldown_remaining method."""
        # Not in cooldown
        self.account.status = AccountStatus.ACTIVE
        self.assertEqual(self.account.get_cooldown_remaining(), 0)

        # In cooldown but no cooldown_until
        self.account.status = AccountStatus.COOLDOWN
        self.account.cooldown_until = None
        self.assertEqual(self.account.get_cooldown_remaining(), 0)

        # In cooldown with future cooldown_until
        self.account.status = AccountStatus.COOLDOWN
        cooldown_seconds = 3600  # 1 hour
        self.account.cooldown_until = (datetime.now() + timedelta(seconds=cooldown_seconds)).isoformat()

        # Should return approximate seconds remaining (within 5 seconds)
        remaining = self.account.get_cooldown_remaining()
        self.assertGreaterEqual(remaining, cooldown_seconds - 5)
        self.assertLessEqual(remaining, cooldown_seconds + 5)

        # In cooldown but cooldown_until in past
        self.account.cooldown_until = (datetime.now() - timedelta(hours=1)).isoformat()
        self.assertEqual(self.account.get_cooldown_remaining(), 0)

        # In cooldown with invalid cooldown_until
        self.account.cooldown_until = "invalid-date"
        self.assertEqual(self.account.get_cooldown_remaining(), 0)

    def test_can_add_members(self):
        """Test can_add_members method."""
        # Active account below limit
        self.account.status = AccountStatus.ACTIVE
        self.account.metrics.members_added_today = 0
        self.assertTrue(self.account.can_add_members())

        # Active account at limit
        self.account.metrics.members_added_today = self.account.metrics.daily_limit
        self.assertFalse(self.account.can_add_members())

        # Inactive account below limit
        self.account.status = AccountStatus.COOLDOWN
        self.account.metrics.members_added_today = 0
        self.assertFalse(self.account.can_add_members())

    def test_can_extract_members(self):
        """Test can_extract_members method."""
        # Active account below limit
        self.account.status = AccountStatus.ACTIVE
        self.account.metrics.members_extracted_today = 0
        self.assertTrue(self.account.can_extract_members())

        # Active account at limit
        self.account.metrics.members_extracted_today = self.account.metrics.daily_limit
        self.assertFalse(self.account.can_extract_members())

        # Inactive account below limit
        self.account.status = AccountStatus.COOLDOWN
        self.account.metrics.members_extracted_today = 0
        self.assertFalse(self.account.can_extract_members())

    def test_reset_daily_limits(self):
        """Test reset_daily_limits method."""
        # Set up account with daily limits reached
        self.account.status = AccountStatus.DAILY_LIMIT_REACHED
        self.account.metrics.members_added_today = self.account.metrics.daily_limit
        self.account.metrics.members_extracted_today = self.account.metrics.daily_limit

        # Reset daily limits
        self.account.reset_daily_limits()

        # Check limits reset
        self.assertEqual(self.account.metrics.members_added_today, 0)
        self.assertEqual(self.account.metrics.members_extracted_today, 0)

        # Check status changed
        self.assertEqual(self.account.status, AccountStatus.ACTIVE)

    def test_set_proxy_config(self):
        """Test set_proxy_config method."""
        proxy_config = {
            "type": "socks5",
            "host": "proxy.example.com",
            "port": 1080,
            "username": "user",
            "password": "pass"
        }

        # Set proxy config
        self.account.set_proxy_config(proxy_config)

        # Check config stored
        self.assertEqual(self.account.proxy_config, proxy_config)

        # Check last_updated changed
        try:
            datetime.fromisoformat(self.account.last_updated)
        except ValueError:
            self.fail("Invalid datetime format in last_updated")

    def test_get_remaining_daily_capacity(self):
        """Test get_remaining_daily_capacity method."""
        # Set daily limit and current usage
        self.account.metrics.daily_limit = 20
        self.account.metrics.members_added_today = 5
        self.account.metrics.members_extracted_today = 10

        # Get capacity
        capacity = self.account.get_remaining_daily_capacity()

        # Check capacity values
        self.assertEqual(capacity["add"], 15)  # 20 - 5
        self.assertEqual(capacity["extract"], 10)  # 20 - 10

        # Test at limit
        self.account.metrics.members_added_today = 20
        capacity = self.account.get_remaining_daily_capacity()
        self.assertEqual(capacity["add"], 0)

        # Test over limit
        self.account.metrics.members_added_today = 25
        capacity = self.account.get_remaining_daily_capacity()
        self.assertEqual(capacity["add"], 0)

    def test_to_dict(self):
        """Test to_dict method."""
        # Set some values for testing
        self.account.cooldown_until = "2023-01-01T12:00:00"
        self.account.last_used = "2023-01-01T10:00:00"
        self.account.last_error = "Test error"
        self.account.failure_count = 3
        self.account.notes = "Test notes"
        self.account.proxy_config = {"type": "socks5", "host": "proxy.example.com"}
        self.account.custom_data = {"test_key": "test_value"}

        # Convert to dict
        account_dict = self.account.to_dict()

        # Check values
        self.assertEqual(account_dict["account_id"], "test_account_id")
        self.assertEqual(account_dict["api_id"], 12345)
        self.assertEqual(account_dict["api_hash"], "test_hash")
        self.assertEqual(account_dict["phone"], "+1234567890")
        self.assertEqual(account_dict["session_string"], "test_session_string")
        self.assertEqual(account_dict["status"], "active")
        self.assertEqual(account_dict["cooldown_until"], "2023-01-01T12:00:00")
        self.assertEqual(account_dict["last_used"], "2023-01-01T10:00:00")
        self.assertEqual(account_dict["last_error"], "Test error")
        self.assertEqual(account_dict["failure_count"], 3)
        self.assertEqual(account_dict["notes"], "Test notes")
        self.assertEqual(account_dict["proxy_config"], {"type": "socks5", "host": "proxy.example.com"})
        self.assertEqual(account_dict["custom_data"], {"test_key": "test_value"})

        # Check that metrics were included
        self.assertIsInstance(account_dict["metrics"], dict)

    def test_from_dict(self):
        """Test from_dict method."""
        # Create dict with account data
        account_data = {
            "account_id": "dict_account_id",
            "api_id": 67890,
            "api_hash": "dict_hash",
            "phone": "+9876543210",
            "session_string": "dict_session_string",
            "status": "cooldown",
            "cooldown_until": "2023-01-01T12:00:00",
            "last_used": "2023-01-01T10:00:00",
            "last_error": "Dict error",
            "failure_count": 2,
            "added_date": "2023-01-01T09:00:00",
            "last_updated": "2023-01-01T11:00:00",
            "notes": "Dict notes",
            "proxy_config": {"type": "http", "host": "dict-proxy.example.com"},
            "metrics": {
                "members_added_today": 5,
                "total_members_added": 50
            },
            "custom_data": {"dict_key": "dict_value"}
        }

        # Create account from dict
        account = Account.from_dict(account_data)

        # Check values
        self.assertEqual(account.account_id, "dict_account_id")
        self.assertEqual(account.api_id, 67890)
        self.assertEqual(account.api_hash, "dict_hash")
        self.assertEqual(account.phone, "+9876543210")
        self.assertEqual(account.session_string, "dict_session_string")
        self.assertEqual(account.status, AccountStatus.COOLDOWN)
        self.assertEqual(account.cooldown_until, "2023-01-01T12:00:00")
        self.assertEqual(account.last_used, "2023-01-01T10:00:00")
        self.assertEqual(account.last_error, "Dict error")
        self.assertEqual(account.failure_count, 2)
        self.assertEqual(account.added_date, "2023-01-01T09:00:00")
        self.assertEqual(account.last_updated, "2023-01-01T11:00:00")
        self.assertEqual(account.notes, "Dict notes")
        self.assertEqual(account.proxy_config, {"type": "http", "host": "dict-proxy.example.com"})
        self.assertEqual(account.custom_data, {"dict_key": "dict_value"})

        # Check metrics
        self.assertEqual(account.metrics.members_added_today, 5)
        self.assertEqual(account.metrics.total_members_added, 50)

    def test_from_dict_missing_required(self):
        """Test from_dict method with missing required fields."""
        # Missing api_id
        account_data = {
            "api_hash": "hash",
            "phone": "+1234567890"
        }

        with self.assertRaises(ValueError):
            Account.from_dict(account_data)

        # Missing api_hash
        account_data = {
            "api_id": 12345,
            "phone": "+1234567890"
        }

        with self.assertRaises(ValueError):
            Account.from_dict(account_data)

        # Missing phone
        account_data = {
            "api_id": 12345,
            "api_hash": "hash"
        }

        with self.assertRaises(ValueError):
            Account.from_dict(account_data)

    def test_string_representation(self):
        """Test string representation methods."""
        # Test __str__
        str_repr = str(self.account)
        self.assertIn("+1234567890", str_repr)
        self.assertIn("active", str_repr)
        self.assertIn("test_account_id", str_repr)

        # Test __repr__
        repr_str = repr(self.account)
        self.assertIn("Account(", repr_str)
        self.assertIn("account_id='test_account_id'", repr_str)
        self.assertIn("phone='+1234567890'", repr_str)
        self.assertIn("api_id=12345", repr_str)
        self.assertIn("status='active'", repr_str)


class TestAccountFactory(unittest.TestCase):
    """Test case for the AccountFactory class."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: models/account.py - AccountFactory")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: AccountFactory")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up before each test method."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

    def tearDown(self):
        """Tear down after each test method."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_create_account(self):
        """Test creating an account with the factory."""
        # Create account with minimal parameters
        account = AccountFactory.create_account(
            api_id=12345,
            api_hash="test_hash",
            phone="+1234567890"
        )

        # Check account properties
        self.assertEqual(account.api_id, 12345)
        self.assertEqual(account.api_hash, "test_hash")
        self.assertEqual(account.phone, "+1234567890")
        self.assertIsNone(account.session_string)
        self.assertEqual(account.status, AccountStatus.UNVERIFIED)

        # Create account with session_string
        account = AccountFactory.create_account(
            api_id=12345,
            api_hash="test_hash",
            phone="+1234567890",
            session_string="test_session_string"
        )

        # Check status is ACTIVE with session_string
        self.assertEqual(account.status, AccountStatus.ACTIVE)

        # Create account with explicit status
        account = AccountFactory.create_account(
            api_id=12345,
            api_hash="test_hash",
            phone="+1234567890",
            status=AccountStatus.BLOCKED
        )

        # Check status is as specified
        self.assertEqual(account.status, AccountStatus.BLOCKED)

        # Create account with additional parameters
        account = AccountFactory.create_account(
            api_id=12345,
            api_hash="test_hash",
            phone="+1234567890",
            account_id="custom_id",
            notes="Test notes"
        )

        # Check additional parameters were set
        self.assertEqual(account.account_id, "custom_id")
        self.assertEqual(account.notes, "Test notes")

    def test_validate_account_data_valid(self):
        """Test account data validation with valid data."""
        # Valid data should not raise exceptions
        AccountFactory.validate_account_data(
            api_id=12345,
            api_hash="valid_hash",
            phone="+1234567890"
        )

        # Valid data with string API ID
        AccountFactory.validate_account_data(
            api_id="12345",  # String, but convertible to int
            api_hash="valid_hash",
            phone="+1234567890"
        )

    def test_validate_account_data_invalid_api_id(self):
        """Test account data validation with invalid API ID."""
        # Negative API ID
        with self.assertRaises(ValueError):
            AccountFactory.validate_account_data(
                api_id=-1,
                api_hash="valid_hash",
                phone="+1234567890"
            )

        # Non-numeric API ID
        with self.assertRaises(ValueError):
            AccountFactory.validate_account_data(
                api_id="abc",
                api_hash="valid_hash",
                phone="+1234567890"
            )

    def test_validate_account_data_invalid_api_hash(self):
        """Test account data validation with invalid API hash."""
        # Empty API hash
        with self.assertRaises(ValueError):
            AccountFactory.validate_account_data(
                api_id=12345,
                api_hash="",
                phone="+1234567890"
            )

        # Non-string API hash
        with self.assertRaises(ValueError):
            AccountFactory.validate_account_data(
                api_id=12345,
                api_hash=12345,  # Not a string
                phone="+1234567890"
            )

    def test_validate_account_data_invalid_phone(self):
        """Test account data validation with invalid phone."""
        # Empty phone
        with self.assertRaises(ValueError):
            AccountFactory.validate_account_data(
                api_id=12345,
                api_hash="valid_hash",
                phone=""
            )

        # Phone without + prefix
        with self.assertRaises(ValueError):
            AccountFactory.validate_account_data(
                api_id=12345,
                api_hash="valid_hash",
                phone="1234567890"  # Missing +
            )

        # Phone with non-digits after +
        with self.assertRaises(ValueError):
            AccountFactory.validate_account_data(
                api_id=12345,
                api_hash="valid_hash",
                phone="+123abc"  # Contains non-digits
            )

    @patch('models.account.AccountFactory.create_account')
    def test_from_telethon_client(self, mock_create_account):
        """Test creating account from Telethon client."""
        # Create mock client
        mock_client = MagicMock()
        mock_client.api_id = 12345
        mock_client.api_hash = "client_hash"
        mock_client.session.save.return_value = "client_session_string"

        # Set up mock create_account
        mock_account = MagicMock()
        mock_create_account.return_value = mock_account

        # Call from_telethon_client
        result = AccountFactory.from_telethon_client(mock_client, phone="+1234567890")

        # Check create_account was called correctly
        mock_create_account.assert_called_once_with(
            api_id=12345,
            api_hash="client_hash",
            phone="+1234567890",
            session_string="client_session_string",
            status=AccountStatus.ACTIVE
        )

        # Check result
        self.assertEqual(result, mock_account)

    @patch('models.account.AccountFactory.create_account')
    def test_from_telethon_client_without_phone(self, mock_create_account):
        """Test creating account from Telethon client without phone parameter."""
        # Create mock client with phone attribute
        mock_client = MagicMock()
        mock_client.api_id = 12345
        mock_client.api_hash = "client_hash"
        mock_client.phone = "+1234567890"

        # Call from_telethon_client without phone
        AccountFactory.from_telethon_client(mock_client)

        # Check create_account was called with client's phone
        mock_create_account.assert_called_once()
        args, kwargs = mock_create_account.call_args
        self.assertEqual(kwargs['phone'], "+1234567890")

    def test_from_telethon_client_invalid_client(self):
        """Test creating account from invalid Telethon client."""
        # Client missing api_id
        mock_client = MagicMock()
        mock_client.api_hash = "hash"

        with self.assertRaises(ValueError):
            AccountFactory.from_telethon_client(mock_client, phone="+1234567890")

        # Client missing api_hash
        mock_client = MagicMock()
        mock_client.api_id = 12345

        with self.assertRaises(ValueError):
            AccountFactory.from_telethon_client(mock_client, phone="+1234567890")

        # Missing phone
        mock_client = MagicMock()
        mock_client.api_id = 12345
        mock_client.api_hash = "hash"

        with self.assertRaises(ValueError):
            AccountFactory.from_telethon_client(mock_client)


if __name__ == "__main__":
    unittest.main(verbosity=2)