"""
Test module for error_handling/fallback.py

This module contains unit tests for the fallback mechanisms that handle error recovery.
"""

import os
import sys
import unittest
import time
import threading
from unittest.mock import patch, MagicMock, call
from pathlib import Path

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, project_root)

# Import the module and exceptions
from error_handling.fallback import (
    FallbackManager, FallbackStrategy, RecoveryState,
    retry_operation, with_recovery, RetryContext,
    OperationCheckpoint, switch_account_fallback,
    emergency_shutdown, get_fallback_manager,
    retry_with_fallback_strategies
)

from core.exceptions import (
    FloodWaitError, PeerFloodError, NetworkError,
    SessionExpiredError, APIError, AccountError,
    TelegramAdderError, OperationError
)


class TestFallbackManager(unittest.TestCase):
    """Test suite for the FallbackManager class."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: error_handling/fallback.py - FallbackManager")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: FallbackManager")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        self.manager = FallbackManager(max_retries=3, base_delay=1.0, max_delay=10.0)
        self.operation_id = "test_operation"

    def tearDown(self):
        """Tear down test fixtures."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_retry_count_management(self):
        """Test retry count management."""
        # Initial retry count should be 0
        self.assertEqual(self.manager.get_retry_count(self.operation_id), 0)

        # Increment retry count
        new_count = self.manager.increment_retry_count(self.operation_id)
        self.assertEqual(new_count, 1)
        self.assertEqual(self.manager.get_retry_count(self.operation_id), 1)

        # Increment again
        new_count = self.manager.increment_retry_count(self.operation_id)
        self.assertEqual(new_count, 2)

        # Reset retry count
        self.manager.reset_retry_count(self.operation_id)
        self.assertEqual(self.manager.get_retry_count(self.operation_id), 0)

    def test_can_retry(self):
        """Test the can_retry method."""
        # Should be able to retry initially
        self.assertTrue(self.manager.can_retry(self.operation_id))

        # Increment to max_retries - 1
        for _ in range(self.manager.max_retries - 1):
            self.manager.increment_retry_count(self.operation_id)
            self.assertTrue(self.manager.can_retry(self.operation_id))

        # Increment to max_retries
        self.manager.increment_retry_count(self.operation_id)
        self.assertFalse(self.manager.can_retry(self.operation_id))

    def test_calculate_delay(self):
        """Test delay calculation."""
        # Test initial delay
        delay = self.manager.calculate_delay(self.operation_id)
        self.assertGreaterEqual(delay, self.manager.base_delay)
        self.assertLessEqual(delay, self.manager.base_delay * 1.2)  # Allow for jitter

        # Test exponential backoff
        self.manager.increment_retry_count(self.operation_id)  # count = 1
        delay = self.manager.calculate_delay(self.operation_id)
        self.assertGreaterEqual(delay, self.manager.base_delay * 2 * 0.8)  # 2^1 with jitter
        self.assertLessEqual(delay, self.manager.base_delay * 2 * 1.2)

        # Test with FloodWaitError
        flood_wait_error = FloodWaitError(seconds=5)
        delay = self.manager.calculate_delay(self.operation_id, flood_wait_error)
        self.assertEqual(delay, 5)  # Should use the seconds from the error

        # Test max delay cap
        for _ in range(10):  # Ensure we hit the cap
            self.manager.increment_retry_count(self.operation_id)
        delay = self.manager.calculate_delay(self.operation_id)
        self.assertLessEqual(delay, self.manager.max_delay)

    def test_recovery_point_management(self):
        """Test recovery point management."""
        # Save a recovery point
        test_data = {"position": 42, "data": "test"}
        self.manager.save_recovery_point(self.operation_id, test_data)

        # Check that recovery point exists
        self.assertTrue(self.manager.has_recovery_point(self.operation_id))

        # Get the recovery point
        recovery_data = self.manager.get_recovery_point(self.operation_id)
        self.assertEqual(recovery_data, test_data)

        # Mark recovery as complete
        self.manager.mark_recovery_complete(self.operation_id, True)
        recovery_info = self.manager.recovery_data.get(self.operation_id)
        self.assertEqual(recovery_info["state"], RecoveryState.RECOVERED)

        # Clear the recovery point
        self.manager.clear_recovery_point(self.operation_id)
        self.assertFalse(self.manager.has_recovery_point(self.operation_id))

    def test_get_fallback_strategy(self):
        """Test fallback strategy selection based on exception type."""
        # Test FloodWaitError
        strategy = FallbackManager.get_fallback_strategy(FloodWaitError())
        self.assertEqual(strategy, FallbackStrategy.WAIT_AND_RETRY)

        # Test PeerFloodError
        strategy = FallbackManager.get_fallback_strategy(PeerFloodError())
        self.assertEqual(strategy, FallbackStrategy.SWITCH_ACCOUNT)

        # Test NetworkError
        strategy = FallbackManager.get_fallback_strategy(NetworkError())
        self.assertEqual(strategy, FallbackStrategy.SWITCH_PROXY)

        # Test SessionExpiredError
        strategy = FallbackManager.get_fallback_strategy(SessionExpiredError())
        self.assertEqual(strategy, FallbackStrategy.SWITCH_ACCOUNT)

        # Test APIError
        strategy = FallbackManager.get_fallback_strategy(APIError())
        self.assertEqual(strategy, FallbackStrategy.RETRY)

        # Test AccountError
        strategy = FallbackManager.get_fallback_strategy(AccountError())
        self.assertEqual(strategy, FallbackStrategy.SWITCH_ACCOUNT)

        # Test TelegramAdderError
        strategy = FallbackManager.get_fallback_strategy(TelegramAdderError())
        self.assertEqual(strategy, FallbackStrategy.RETRY)

        # Test unknown error
        strategy = FallbackManager.get_fallback_strategy(ValueError())
        self.assertEqual(strategy, FallbackStrategy.ABORT)


class TestRetryOperation(unittest.TestCase):
    """Test suite for the retry_operation function."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: error_handling/fallback.py - retry_operation")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: retry_operation")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        self.operation_id = "test_retry_operation"
        # Create a mock fallback manager
        self.fallback_manager = MagicMock(spec=FallbackManager)
        self.fallback_manager.can_retry.return_value = True
        self.fallback_manager.get_retry_count.return_value = 0
        self.fallback_manager.calculate_delay.return_value = 0.01  # Small delay for tests

    def tearDown(self):
        """Tear down test fixtures."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_successful_operation(self):
        """Test retry_operation with a successful function call."""
        # Mock function that succeeds
        mock_func = MagicMock(return_value="success")

        # Call retry_operation
        result = retry_operation(
            mock_func, self.operation_id, self.fallback_manager,
            max_retries=3, base_delay=0.01
        )

        # Check that function was called once and succeeded
        mock_func.assert_called_once()
        self.assertEqual(result, "success")
        self.fallback_manager.reset_retry_count.assert_called_with(self.operation_id)

    def test_retry_after_failure(self):
        """Test retry_operation with a function that fails initially but succeeds later."""
        # Mock function that fails once then succeeds
        mock_func = MagicMock(side_effect=[ValueError("First call fails"), "success"])

        # Mock fallback manager behavior
        self.fallback_manager.get_fallback_strategy.return_value = FallbackStrategy.RETRY
        self.fallback_manager.increment_retry_count.return_value = 1

        # Call retry_operation
        result = retry_operation(
            mock_func, self.operation_id, self.fallback_manager,
            max_retries=3, base_delay=0.01
        )

        # Check that function was called twice and eventually succeeded
        self.assertEqual(mock_func.call_count, 2)
        self.assertEqual(result, "success")
        self.fallback_manager.reset_retry_count.assert_called_with(self.operation_id)
        self.fallback_manager.get_fallback_strategy.assert_called_once()

    def test_max_retries_reached(self):
        """Test retry_operation when max retries is reached."""
        # Mock function that always fails
        error = ValueError("Always fails")
        mock_func = MagicMock(side_effect=error)

        # Mock fallback manager behavior
        self.fallback_manager.get_fallback_strategy.return_value = FallbackStrategy.RETRY

        # Set up increment_retry_count to increment a counter properly
        retry_count = 0
        def increment_mock(*args, **kwargs):
            nonlocal retry_count
            retry_count += 1
            return retry_count
        self.fallback_manager.increment_retry_count.side_effect = increment_mock

        # Set up can_retry to return False after a few tries
        def can_retry_mock(*args, **kwargs):
            return retry_count < 3
        self.fallback_manager.can_retry.side_effect = can_retry_mock

        # Call retry_operation and expect it to eventually raise the error
        with self.assertRaises(ValueError) as context:
            retry_operation(
                mock_func, self.operation_id, self.fallback_manager,
                max_retries=3, base_delay=0.01
            )

        # Check that function was called the expected number of times
        self.assertEqual(mock_func.call_count, 3)  # Initial + 2 retries
        self.assertEqual(str(context.exception), "Always fails")

    def test_error_callback(self):
        """Test retry_operation with an error callback."""
        # Mock function that fails
        error = ValueError("Test error")
        mock_func = MagicMock(side_effect=error)

        # Mock error callback
        error_callback = MagicMock()

        # Mock fallback manager behavior
        self.fallback_manager.get_fallback_strategy.return_value = FallbackStrategy.RETRY

        # Set up increment_retry_count to increment a counter properly
        retry_count = 0
        def increment_mock(*args, **kwargs):
            nonlocal retry_count
            retry_count += 1
            return retry_count
        self.fallback_manager.increment_retry_count.side_effect = increment_mock

        # Set up can_retry to return False after one try
        def can_retry_mock(*args, **kwargs):
            return retry_count < 1
        self.fallback_manager.can_retry.side_effect = can_retry_mock

        # Call retry_operation and expect it to eventually raise the error
        with self.assertRaises(ValueError):
            retry_operation(
                mock_func, self.operation_id, self.fallback_manager,
                max_retries=3, base_delay=0.01, error_callback=error_callback
            )

        # Check that error callback was called
        error_callback.assert_called_once_with(error, 1)  # Called with error and retry count

    def test_abort_strategy(self):
        """Test retry_operation with ABORT strategy."""
        # Mock function that fails
        mock_func = MagicMock(side_effect=ValueError("Test error"))

        # Mock fallback manager to return ABORT strategy
        self.fallback_manager.get_fallback_strategy.return_value = FallbackStrategy.ABORT

        # Call retry_operation and expect it to abort immediately
        with self.assertRaises(ValueError):
            retry_operation(
                mock_func, self.operation_id, self.fallback_manager,
                max_retries=3, base_delay=0.01
            )

        # Check that function was called only once (no retries)
        self.assertEqual(mock_func.call_count, 1)
        self.fallback_manager.get_fallback_strategy.assert_called_once()


class TestWithRecovery(unittest.TestCase):
    """Test suite for the with_recovery function."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: error_handling/fallback.py - with_recovery")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: with_recovery")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        self.operation_id = "test_with_recovery"
        # Create a mock fallback manager
        self.fallback_manager = MagicMock(spec=FallbackManager)

        # Mock function and state getter
        self.mock_func = MagicMock(return_value="success")
        self.mock_state_getter = MagicMock(return_value={"position": 42})

    def tearDown(self):
        """Tear down test fixtures."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_normal_execution(self):
        """Test with_recovery during normal execution."""
        # Setup manager behavior
        self.fallback_manager.has_recovery_point.return_value = False

        # Call with_recovery
        result = with_recovery(
            self.mock_func, self.operation_id,
            self.mock_state_getter, self.fallback_manager,
            arg1="value1"
        )

        # Check function calls
        self.mock_func.assert_called_once_with(arg1="value1")
        self.mock_state_getter.assert_called_once_with(arg1="value1")
        self.fallback_manager.save_recovery_point.assert_called_once_with(
            self.operation_id, {"position": 42}
        )
        self.fallback_manager.mark_recovery_complete.assert_called_once_with(
            self.operation_id, success=True
        )
        self.fallback_manager.clear_recovery_point.assert_called_once_with(
            self.operation_id
        )

        # Check result
        self.assertEqual(result, "success")

    def test_recovery_from_checkpoint(self):
        """Test with_recovery when recovering from a checkpoint."""
        # Setup manager behavior
        self.fallback_manager.has_recovery_point.return_value = True
        self.fallback_manager.get_recovery_point.return_value = {
            "position": 42, "recovered": True
        }

        # Call with_recovery
        result = with_recovery(
            self.mock_func, self.operation_id,
            self.mock_state_getter, self.fallback_manager,
            arg1="value1"
        )

        # Check function calls - should include recovery data in kwargs
        expected_kwargs = {"arg1": "value1", "position": 42, "recovered": True}
        self.mock_func.assert_called_once_with(**expected_kwargs)

        # Should update state with the merged data
        self.mock_state_getter.assert_called_once_with(**expected_kwargs)

        # Check result
        self.assertEqual(result, "success")

    def test_error_handling(self):
        """Test with_recovery when function raises an error."""
        # Mock function to raise error
        error = ValueError("Test error")
        self.mock_func.side_effect = error

        # Setup manager behavior
        self.fallback_manager.has_recovery_point.return_value = False

        # Call with_recovery and expect it to re-raise the error
        with self.assertRaises(ValueError) as context:
            with_recovery(
                self.mock_func, self.operation_id,
                self.mock_state_getter, self.fallback_manager,
                arg1="value1"
            )

        # Check that error was re-raised
        self.assertEqual(str(context.exception), "Test error")

        # Recovery should be marked as failed
        self.fallback_manager.mark_recovery_complete.assert_called_once_with(
            self.operation_id, success=False
        )


class TestRetryContext(unittest.TestCase):
    """Test suite for the RetryContext class."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: error_handling/fallback.py - RetryContext")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: RetryContext")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        self.operation_id = "test_retry_context"

    def tearDown(self):
        """Tear down test fixtures."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_successful_execution(self):
        """Test RetryContext with successful execution."""
        # Create retry context
        context = RetryContext(self.operation_id, max_retries=3, base_delay=0.01)

        # Use context manager
        with context:
            # No exception raised
            result = "success"

        # Check state
        self.assertFalse(context.has_error)
        self.assertEqual(context.retry_count, 0)
        self.assertIsNone(context.error)
        self.assertIsNone(context.strategy)

    def test_retry_strategy(self):
        """Test RetryContext with a retryable error."""
        # Create retry context with a mock FallbackManager
        with patch('error_handling.fallback.FallbackManager') as MockManager:
            # Set up mock behavior
            mock_instance = MockManager.return_value
            mock_instance.increment_retry_count.return_value = 1
            mock_instance.get_retry_count.return_value = 1
            mock_instance.get_fallback_strategy.return_value = FallbackStrategy.RETRY
            mock_instance.can_retry.return_value = True
            mock_instance.calculate_delay.return_value = 0.01

            # Create context
            context = RetryContext(self.operation_id, max_retries=3, base_delay=0.01)

            # First attempt will raise an error
            try:
                with context:
                    raise ValueError("Test error")
            except ValueError:
                # Exception should be suppressed by context manager
                pass

            # Check state
            self.assertTrue(context.has_error)
            self.assertEqual(context.retry_count, 1)
            self.assertIsInstance(context.error, ValueError)
            self.assertEqual(context.strategy, FallbackStrategy.RETRY)

            # Check mock calls
            mock_instance.increment_retry_count.assert_called_once_with(self.operation_id)
            mock_instance.get_fallback_strategy.assert_called_once()
            mock_instance.calculate_delay.assert_called_once()

    def test_non_retry_strategy(self):
        """Test RetryContext with a non-retryable error."""
        # Create retry context with a mock FallbackManager
        with patch('error_handling.fallback.FallbackManager') as MockManager:
            # Set up mock behavior
            mock_instance = MockManager.return_value
            mock_instance.increment_retry_count.return_value = 1
            mock_instance.get_retry_count.return_value = 1
            mock_instance.get_fallback_strategy.return_value = FallbackStrategy.ABORT
            # Even if can_retry is True, the strategy is ABORT
            mock_instance.can_retry.return_value = True

            # Create context
            context = RetryContext(self.operation_id, max_retries=3, base_delay=0.01)

            # Attempt will raise an error that should not be suppressed
            with self.assertRaises(ValueError):
                with context:
                    raise ValueError("Test error")

            # Check state
            self.assertTrue(context.has_error)
            self.assertEqual(context.strategy, FallbackStrategy.ABORT)

            # should_retry should return False for ABORT strategy
            self.assertFalse(context.should_retry())

    def test_reset(self):
        """Test RetryContext reset method."""
        # Create retry context with a mock FallbackManager
        with patch('error_handling.fallback.FallbackManager') as MockManager:
            # Set up mock instance
            mock_instance = MockManager.return_value

            # Create context
            context = RetryContext(self.operation_id)

            # Set some state
            context.current_attempt = 2
            context.error = ValueError("Test error")
            context.strategy = FallbackStrategy.RETRY

            # Reset
            context.reset()

            # Check state is reset
            self.assertEqual(context.current_attempt, 0)
            self.assertIsNone(context.error)
            self.assertIsNone(context.strategy)

            # Check reset_retry_count was called
            mock_instance.reset_retry_count.assert_called_once_with(self.operation_id)


class TestOperationCheckpoint(unittest.TestCase):
    """Test suite for the OperationCheckpoint class."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: error_handling/fallback.py - OperationCheckpoint")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: OperationCheckpoint")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        self.operation_id = "test_checkpoint"
        # Create mock functions
        self.mock_save_func = MagicMock()
        self.mock_load_func = MagicMock(return_value={"position": 42})

        # Create checkpoint with mock fallback manager
        self.mock_manager = MagicMock(spec=FallbackManager)
        with patch('error_handling.fallback.FallbackManager', return_value=self.mock_manager):
            self.checkpoint = OperationCheckpoint(
                self.operation_id,
                checkpoint_interval=5,
                save_func=self.mock_save_func,
                load_func=self.mock_load_func
            )

    def tearDown(self):
        """Tear down test fixtures."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_checkpoint_interval(self):
        """Test that checkpoints are saved at the correct interval."""
        # State for testing
        state = {"position": 1, "data": "test"}

        # Save checkpoint multiple times, should only save at interval
        for i in range(1, 11):  # 1 to 10
            self.checkpoint.checkpoint(state)

            # Check if saved based on interval
            if i % 5 == 0:  # Every 5 items
                self.mock_manager.save_recovery_point.assert_called_with(self.operation_id, state)
                self.mock_save_func.assert_called_with(state)

                # Reset mock for next check
                self.mock_manager.save_recovery_point.reset_mock()
                self.mock_save_func.reset_mock()

        # Check final item count
        self.assertEqual(self.checkpoint.item_count, 10)

    def test_load_last_checkpoint(self):
        """Test loading the last checkpoint."""
        # Set up mock behavior
        self.mock_manager.get_recovery_point.return_value = {"position": 42, "from_manager": True}

        # Load checkpoint - should prefer manager over load_func
        state = self.checkpoint.load_last_checkpoint()

        # Check result
        self.assertEqual(state, {"position": 42, "from_manager": True})
        self.mock_manager.get_recovery_point.assert_called_once_with(self.operation_id)

        # Test fallback to load_func
        self.mock_manager.get_recovery_point.return_value = None
        state = self.checkpoint.load_last_checkpoint()

        # Check result
        self.assertEqual(state, {"position": 42})  # From mock_load_func
        self.mock_load_func.assert_called_once()

    def test_clear_checkpoints(self):
        """Test clearing all checkpoints."""
        # Save some checkpoints
        for i in range(10):
            self.checkpoint.checkpoint({"position": i})

        # Clear checkpoints
        self.checkpoint.clear_checkpoints()

        # Check state
        self.assertEqual(self.checkpoint.item_count, 0)
        self.mock_manager.clear_recovery_point.assert_called_once_with(self.operation_id)

    def test_load_func_error(self):
        """Test error handling when load_func raises an exception."""
        # Set up mock to raise an error
        self.mock_manager.get_recovery_point.return_value = None
        self.mock_load_func.side_effect = ValueError("Load error")

        # Load checkpoint - should handle error
        state = self.checkpoint.load_last_checkpoint()

        # Should return None due to error
        self.assertIsNone(state)


class TestFallbackHelpers(unittest.TestCase):
    """Test suite for fallback helper functions."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: error_handling/fallback.py - Helper Functions")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: Helper Functions")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

    def tearDown(self):
        """Tear down test fixtures."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_switch_account_fallback(self):
        """Test the switch_account_fallback function."""
        # Mock function, account provider, and error
        mock_func = MagicMock(return_value="success")
        mock_account_provider = MagicMock()
        mock_account_provider.get_next_available_account.return_value = ("new_account", 1)
        error = AccountError("Test error")

        # Call the function
        result = switch_account_fallback(
            mock_func, mock_account_provider, error,
            arg1="value1", account="old_account", account_index=0
        )

        # Check results
        mock_account_provider.get_next_available_account.assert_called_once()
        mock_func.assert_called_once_with(
            arg1="value1", account="new_account", account_index=1
        )
        self.assertEqual(result, "success")

    def test_switch_account_fallback_no_accounts(self):
        """Test switch_account_fallback when no accounts are available."""
        # Mock function, account provider, and error
        mock_func = MagicMock()
        mock_account_provider = MagicMock()
        mock_account_provider.get_next_available_account.return_value = (None, -1)
        error = AccountError("Test error")

        # Call the function and expect an error
        with self.assertRaises(OperationError) as context:
            switch_account_fallback(
                mock_func, mock_account_provider, error,
                arg1="value1"
            )

        # Check error message
        self.assertEqual(str(context.exception), "No alternative accounts available")

        # Check that mock_func was not called
        mock_func.assert_not_called()

    def test_emergency_shutdown(self):
        """Test the emergency_shutdown function."""
        # Mock cleanup function
        mock_cleanup = MagicMock()

        # Mock FallbackManager
        with patch('error_handling.fallback.FallbackManager') as MockManager:
            mock_instance = MockManager.return_value

            # Test data
            operation_id = "test_emergency"
            state = {"position": 42, "data": "important"}
            error = RuntimeError("Critical error")

            # Call emergency_shutdown
            emergency_shutdown(operation_id, state, error, mock_cleanup)

            # Check function calls
            mock_instance.save_recovery_point.assert_called_once_with(operation_id, state)
            mock_instance.mark_recovery_complete.assert_called_once_with(
                operation_id, success=False
            )
            mock_cleanup.assert_called_once()

    def test_get_fallback_manager(self):
        """Test the get_fallback_manager function."""
        # Test that it returns a FallbackManager instance
        manager = get_fallback_manager()
        self.assertIsInstance(manager, FallbackManager)

    def test_retry_with_fallback_strategies(self):
        """Test the retry_with_fallback_strategies function."""
        # Mock function and fallback manager
        mock_func = MagicMock(return_value="success")

        # Patch relevant functions
        with patch('error_handling.fallback.retry_operation') as mock_retry, \
             patch('error_handling.fallback.switch_account_fallback') as mock_switch, \
             patch('error_handling.fallback.FallbackManager') as MockManager:

            # Set up return values
            mock_retry.return_value = "retry_success"
            mock_switch.return_value = "switch_success"

            # Define strategies
            strategies = [FallbackStrategy.RETRY, FallbackStrategy.SWITCH_ACCOUNT]

            # Call function
            result = retry_with_fallback_strategies(
                mock_func, "test_op", strategies,
                arg1="value1", account_provider="provider"
            )

            # First strategy should be used (RETRY)
            self.assertEqual(result, "retry_success")
            mock_retry.assert_called_once_with(
                mock_func, "test_op", MockManager.return_value,
                arg1="value1", account_provider="provider"
            )

            # Second strategy should not be used
            mock_switch.assert_not_called()

            # Reset mocks
            mock_retry.reset_mock()
            mock_switch.reset_mock()

            # Make first strategy fail
            mock_retry.side_effect = ValueError("Retry failed")

            # Call function again
            result = retry_with_fallback_strategies(
                mock_func, "test_op", strategies,
                arg1="value1", account_provider="provider"
            )

            # Second strategy should be used after first fails
            self.assertEqual(result, "switch_success")
            mock_switch.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)