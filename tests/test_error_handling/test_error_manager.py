import unittest
import os
import sys
import json
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import logging

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from error_handling.error_manager import (
    ErrorManager, get_error_manager, handle_error, execute_safely
)

from error_handling.error_handlers import (
    BaseErrorHandler, AccountErrorHandler, TelegramErrorHandler
)

from core.exceptions import (
    TelegramAdderError, AccountError, AccountNotFoundError, AccountLimitReachedError,
    AccountBlockedError, AccountInCooldownError, AccountVerificationError,
    APIError, FloodWaitError, PeerFloodError, UserPrivacyRestrictedError,
    PhoneNumberBannedError, ApiIdInvalidError, ApiHashInvalidError,
    GroupNotFoundError, NotGroupAdminError, MemberExtractionError, MemberAdditionError,
    NetworkError, ConnectionError, ProxyError, TimeoutError,
    SessionExpiredError, OperationError
)

class MockTelethonError:
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class MockTelethonFloodWaitError(MockTelethonError):
    def __init__(self, message, seconds):
        super().__init__(message)
        self.seconds = seconds

class TestErrorManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing ErrorManager ===")

    def setUp(self):
        # Create a temporary directory for error logs
        self.temp_dir = tempfile.mkdtemp()

        # Reset the ErrorManager singleton
        ErrorManager._instance = None

        # Create a new ErrorManager with the temporary directory
        self.error_manager = ErrorManager(error_log_dir=self.temp_dir)

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_singleton_pattern(self):
        # Create another ErrorManager
        another_manager = ErrorManager()

        # Check that they are the same instance
        self.assertIs(another_manager, self.error_manager)

    def test_register_handler(self):
        # Create a mock handler
        mock_handler = MagicMock(spec=BaseErrorHandler)

        # Register the handler
        self.error_manager.register_handler(ValueError, mock_handler)

        # Check that it was registered
        self.assertIn("ValueError", self.error_manager.handlers)
        self.assertIs(self.error_manager.handlers["ValueError"], mock_handler)

    def test_register_converter(self):
        # Create a mock converter
        mock_converter = MagicMock(return_value=ValueError("Converted"))

        # Register the converter
        self.error_manager.register_converter("test.CustomError", mock_converter)

        # Check that it was registered
        self.assertIn("test.CustomError", self.error_manager.converters)
        self.assertIs(self.error_manager.converters["test.CustomError"], mock_converter)

    def test_convert_exception(self):
        # Create a mock exception with a module
        class CustomError(Exception):
            pass

        CustomError.__module__ = "test"

        # Register a converter
        mock_converter = MagicMock(return_value=ValueError("Converted"))
        self.error_manager.register_converter("test.CustomError", mock_converter)

        # Test converting the exception
        exception = CustomError("Test")
        converted = self.error_manager.convert_exception(exception)

        # Check that the converter was called
        mock_converter.assert_called_once_with(exception)

        # Check the converted exception
        self.assertIsInstance(converted, ValueError)
        self.assertEqual(str(converted), "Converted")

    def test_convert_telethon_flood_wait(self):
        # Create a mock Telethon FloodWaitError
        exception = MockTelethonFloodWaitError("Wait", 120)
        exception.__class__.__module__ = "telethon.errors"
        exception.__class__.__name__ = "FloodWaitError"

        # Convert it using the built-in converter
        converted = self.error_manager.convert_exception(exception)

        # Check the converted exception
        self.assertIsInstance(converted, FloodWaitError)
        self.assertEqual("Flood wait for 120 seconds", str(converted))

    def test_handle_with_registered_handler(self):
        # Create a mock handler
        mock_handler = MagicMock(spec=BaseErrorHandler)
        mock_handler.handle_error.return_value = {"handled": True, "message": "Test handled"}

        # Register the handler
        self.error_manager.register_handler(ValueError, mock_handler)

        # Handle a ValueError
        exception = ValueError("Test error")
        response = self.error_manager.handle(exception)

        # Check that the handler was called
        mock_handler.handle_error.assert_called_once()

        # Check the response
        self.assertEqual(response["message"], "Test handled")

    def test_handle_with_default_handler(self):
        # Mock the default handler
        self.error_manager.default_handler.handle_error = MagicMock(
            return_value={"handled": True, "message": "Default handled"}
        )

        # Handle an exception without a registered handler
        exception = KeyError("Test error")
        response = self.error_manager.handle(exception)

        # Check that the default handler was called
        self.error_manager.default_handler.handle_error.assert_called_once()

        # Check the response
        self.assertEqual(response["message"], "Default handled")

    def test_log_error(self):
        # Handle an error to trigger logging
        exception = ValueError("Test error")
        self.error_manager.handle(exception, {"test_context": True})

        # Check that a log file was created
        log_files = os.listdir(self.temp_dir)
        self.assertTrue(any(f.startswith("error_log_") for f in log_files))

        # Read the log file
        log_file = os.path.join(self.temp_dir, log_files[0])
        with open(log_file, 'r') as f:
            errors = json.load(f)

        # Check that our error was logged
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["error_type"], "ValueError")
        self.assertEqual(errors[0]["error_message"], "Test error")
        self.assertEqual(errors[0]["context"], {"test_context": True})

    def test_get_recent_errors(self):
        # Handle some errors
        self.error_manager.handle(ValueError("Error 1"))
        self.error_manager.handle(KeyError("Error 2"))

        # Get recent errors
        recent_errors = self.error_manager.get_recent_errors()

        # Check the errors
        self.assertEqual(len(recent_errors), 2)
        self.assertEqual(recent_errors[0]["error_type"], "ValueError")
        self.assertEqual(recent_errors[1]["error_type"], "KeyError")

    def test_clear_recent_errors(self):
        # Handle some errors
        self.error_manager.handle(ValueError("Error 1"))
        self.error_manager.handle(KeyError("Error 2"))

        # Clear recent errors
        self.error_manager.clear_recent_errors()

        # Check that they were cleared
        recent_errors = self.error_manager.get_recent_errors()
        self.assertEqual(len(recent_errors), 0)

    def test_get_error_stats(self):
        # Handle some errors with different responses
        with patch.object(self.error_manager.default_handler, 'handle_error') as mock_handle:
            mock_handle.side_effect = [
                {"handled": True, "retry": True, "should_abort": False},
                {"handled": True, "retry": False, "should_abort": True},
                {"handled": True, "retry": True, "switch_account": True}
            ]

            self.error_manager.handle(ValueError("Error 1"))
            self.error_manager.handle(KeyError("Error 2"))
            self.error_manager.handle(TypeError("Error 3"))

        # Get error stats
        stats = self.error_manager.get_error_stats()

        # Check the stats
        self.assertEqual(stats["total_errors"], 3)
        self.assertEqual(len(stats["error_types"]), 3)
        self.assertIn("ValueError", stats["error_types"])
        self.assertIn("KeyError", stats["error_types"])
        self.assertIn("TypeError", stats["error_types"])
        self.assertEqual(stats["retry_rate"], 200.0 / 3)  # 2 out of 3 have retry=True
        self.assertEqual(stats["abort_rate"], 100.0 / 3)  # 1 out of 3 has should_abort=True
        self.assertEqual(stats["switch_account_rate"], 100.0 / 3)  # 1 out of 3 has switch_account=True

    def test_execute_with_error_handling_success(self):
        # Create a function that succeeds
        func = MagicMock(return_value="Success")

        # Call execute_with_error_handling
        result = self.error_manager.execute_with_error_handling(func, "arg1", kwarg1="value")

        # Check that the function was called with the right arguments
        func.assert_called_once_with("arg1", kwarg1="value")

        # Check the result
        self.assertEqual(result, "Success")

    def test_execute_with_error_handling_retry_then_success(self):
        # Create a function that fails once then succeeds
        func = MagicMock(side_effect=[ValueError("Test error"), "Success"])

        # Mock handle to allow retry
        self.error_manager.handle = MagicMock(return_value={"retry": True, "should_abort": False})

        # Call execute_with_error_handling with a very short delay
        result = self.error_manager.execute_with_error_handling(func, retry_delay=0.001)

        # Check that the function was called twice
        self.assertEqual(func.call_count, 2)

        # Check that handle was called
        self.error_manager.handle.assert_called_once()

        # Check the result
        self.assertEqual(result, "Success")

    def test_execute_with_error_handling_max_retries(self):
        # Create a function that always fails
        error = ValueError("Test error")
        func = MagicMock(side_effect=error)

        # Mock handle to allow retry
        self.error_manager.handle = MagicMock(return_value={"retry": True, "should_abort": False})

        # Call execute_with_error_handling with a very short delay and 2 retries
        with self.assertRaises(ValueError) as context:
            self.error_manager.execute_with_error_handling(func, retry_count=2, retry_delay=0.001)

        # Check that the function was called 3 times (initial + 2 retries)
        self.assertEqual(func.call_count, 3)

        # Check that handle was called twice
        self.assertEqual(self.error_manager.handle.call_count, 2)

        # Check that the right exception was raised
        self.assertEqual(str(context.exception), "Test error")

    def test_execute_with_error_handling_abort(self):
        # Create a function that fails
        error = ValueError("Test error")
        func = MagicMock(side_effect=error)

        # Mock handle to abort retry
        self.error_manager.handle = MagicMock(return_value={"retry": False, "should_abort": True})

        # Call execute_with_error_handling
        with self.assertRaises(ValueError) as context:
            self.error_manager.execute_with_error_handling(func, retry_count=3, retry_delay=0.001)

        # Check that the function was called only once
        func.assert_called_once()

        # Check that handle was called
        self.error_manager.handle.assert_called_once()

        # Check that the right exception was raised
        self.assertEqual(str(context.exception), "Test error")

class TestHelperFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing Error Manager Helper Functions ===")

    def setUp(self):
        # Create a temporary directory for error logs
        self.temp_dir = tempfile.mkdtemp()

        # Reset the ErrorManager singleton
        ErrorManager._instance = None

        # Create a new ErrorManager with the temporary directory
        self.error_manager = ErrorManager(error_log_dir=self.temp_dir)

        # Store the original error_manager for module functions
        self.original_error_manager = self.error_manager

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_get_error_manager(self):
        # Get the error manager
        manager = get_error_manager()

        # Check that it's the singleton instance
        self.assertIs(manager, self.original_error_manager)

    def test_handle_error(self):
        # Mock the error manager's handle method
        with patch.object(self.error_manager, 'handle') as mock_handle:
            mock_handle.return_value = {"handled": True, "message": "Test handled"}

            # Call handle_error
            exception = ValueError("Test error")
            response = handle_error(exception, {"test": True})

            # Check that the error manager's handle method was called
            mock_handle.assert_called_once_with(exception, {"test": True})

            # Check the response
            self.assertEqual(response, {"handled": True, "message": "Test handled"})

    def test_execute_safely(self):
        # Mock the error manager's execute_with_error_handling method
        with patch.object(self.error_manager, 'execute_with_error_handling') as mock_execute:
            mock_execute.return_value = "Test result"

            # Call execute_safely
            result = execute_safely(lambda x: x * 2, 21)

            # Check that the error manager's execute_with_error_handling method was called
            mock_execute.assert_called_once_with(lambda x: x * 2, 21)

            # Check the result
            self.assertEqual(result, "Test result")

class TestErrorManagerWithTelethon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing ErrorManager with Telethon Errors ===")

    def setUp(self):
        # Create a temporary directory for error logs
        self.temp_dir = tempfile.mkdtemp()

        # Reset the ErrorManager singleton
        ErrorManager._instance = None

        # Create a new ErrorManager with the temporary directory
        self.error_manager = ErrorManager(error_log_dir=self.temp_dir)

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_convert_telethon_flood_wait(self):
        # Create a mock Telethon FloodWaitError
        class TelethonFloodWaitError(Exception):
            def __init__(self, seconds):
                self.seconds = seconds
                super().__init__(f"A wait of {seconds} seconds is required")

        TelethonFloodWaitError.__module__ = "telethon.errors"

        # Create an instance
        error = TelethonFloodWaitError(120)

        # Convert it
        converted = self.error_manager.convert_exception(error)

        # Check that it was converted to our custom exception
        self.assertIsInstance(converted, FloodWaitError)
        self.assertEqual("Flood wait for 120 seconds", str(converted))

    def test_convert_telethon_peer_flood(self):
        # Create a mock Telethon PeerFloodError
        class TelethonPeerFloodError(Exception):
            pass

        TelethonPeerFloodError.__module__ = "telethon.errors"

        # Create an instance
        error = TelethonPeerFloodError("Too many requests")

        # Convert it
        converted = self.error_manager.convert_exception(error)

        # Check that it was converted to our custom exception
        self.assertIsInstance(converted, PeerFloodError)

    def test_convert_telethon_privacy(self):
        # Create a mock Telethon UserPrivacyRestrictedError
        class TelethonUserPrivacyRestrictedError(Exception):
            pass

        TelethonUserPrivacyRestrictedError.__module__ = "telethon.errors"

        # Create an instance
        error = TelethonUserPrivacyRestrictedError("Privacy settings prevent this action")

        # Convert it
        converted = self.error_manager.convert_exception(error)

        # Check that it was converted to our custom exception
        self.assertIsInstance(converted, UserPrivacyRestrictedError)

    def test_handle_converted_exception(self):
        # Create a mock Telethon error
        class TelethonPhoneNumberBannedError(Exception):
            pass

        TelethonPhoneNumberBannedError.__module__ = "telethon.errors"

        # Create an instance
        error = TelethonPhoneNumberBannedError("This phone number is banned")

        # Mock the default handler
        self.error_manager.default_handler.handle_error = MagicMock(
            return_value={"handled": True, "message": "Handled phone banned"}
        )

        # Handle the error
        response = self.error_manager.handle(error)

        # Check the response
        self.assertEqual(response["message"], "Handled phone banned")

        # Check that the handler was called with the converted exception
        args, _ = self.error_manager.default_handler.handle_error.call_args
        self.assertIsInstance(args[0], PhoneNumberBannedError)

if __name__ == "__main__":
    unittest.main(verbosity=2)