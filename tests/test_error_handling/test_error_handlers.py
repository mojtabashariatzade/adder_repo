import unittest
import os
import sys
import time
from unittest.mock import MagicMock, patch
import logging

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from error_handling.error_handlers import (
    BaseErrorHandler, AccountErrorHandler, TelegramErrorHandler,
    GroupErrorHandler, SessionErrorHandler, CompositeErrorHandler,
    create_default_error_handler, handle_error, execute_with_error_handling
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

class TestBaseErrorHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing BaseErrorHandler ===")

    def setUp(self):
        self.handler = BaseErrorHandler()

    def test_handle_error_known_type(self):
        # Create a mock handler method
        self.handler.handle_ValueError = MagicMock(return_value={"message": "Test handled"})

        # Call handle_error with a ValueError
        exception = ValueError("Test error")
        response = self.handler.handle_error(exception)

        # Check that the mock method was called
        self.handler.handle_ValueError.assert_called_once()

        # Check response
        self.assertTrue(response["handled"])
        self.assertEqual(response["message"], "Test handled")

    def test_handle_error_unknown_type(self):
        # Call handle_error with an exception type that doesn't have a handler
        exception = KeyError("Test error")
        response = self.handler.handle_error(exception)

        # Check response
        self.assertTrue(response["handled"])
        self.assertEqual(response["message"], "Unknown error occurred")
        self.assertTrue(response["should_abort"])

    def test_handle_error_with_fallback(self):
        # Create a fallback handler
        fallback = BaseErrorHandler()
        fallback.handle_KeyError = MagicMock(return_value={"message": "Fallback handled"})

        # Create a handler with the fallback
        handler = BaseErrorHandler(fallback_handler=fallback)

        # Call handle_error with a KeyError
        exception = KeyError("Test error")
        response = handler.handle_error(exception)

        # Check that the fallback was used
        fallback.handle_KeyError.assert_called_once()

        # Check response
        self.assertEqual(response["message"], "Fallback handled")

    def test_execute_with_retry_success(self):
        # Mock function that succeeds
        mock_func = MagicMock(return_value="Success")

        # Call execute_with_retry
        result = self.handler.execute_with_retry(mock_func, "arg1", kwarg1="value1")

        # Check that the function was called with the right arguments
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

        # Check the result
        self.assertEqual(result, "Success")

    def test_execute_with_retry_failure_then_success(self):
        # Mock function that fails once then succeeds
        mock_func = MagicMock(side_effect=[ValueError("Test error"), "Success"])

        # Mock handle_error to allow retry
        self.handler.handle_error = MagicMock(return_value={"retry": True, "should_abort": False})

        # Call execute_with_retry with a short delay
        result = self.handler.execute_with_retry(mock_func, retry_delay=0.1)

        # Check that the function was called twice
        self.assertEqual(mock_func.call_count, 2)

        # Check that handle_error was called
        self.handler.handle_error.assert_called_once()

        # Check the result
        self.assertEqual(result, "Success")

    def test_execute_with_retry_max_retries(self):
        # Mock function that always fails
        error = ValueError("Test error")
        mock_func = MagicMock(side_effect=error)

        # Mock handle_error to allow retry
        self.handler.handle_error = MagicMock(return_value={"retry": True, "should_abort": False})

        # Call execute_with_retry with a short delay and 2 retries
        with self.assertRaises(ValueError) as context:
            self.handler.execute_with_retry(mock_func, retry_count=2, retry_delay=0.1)

        # Check that the function was called 3 times (initial + 2 retries)
        self.assertEqual(mock_func.call_count, 3)

        # Check that handle_error was called twice
        self.assertEqual(self.handler.handle_error.call_count, 2)

        # Check that the right exception was raised
        self.assertEqual(str(context.exception), "Test error")

    def test_execute_with_retry_abort(self):
        # Mock function that fails
        error = ValueError("Test error")
        mock_func = MagicMock(side_effect=error)

        # Mock handle_error to abort retry
        self.handler.handle_error = MagicMock(return_value={"retry": False, "should_abort": True})

        # Call execute_with_retry
        with self.assertRaises(ValueError) as context:
            self.handler.execute_with_retry(mock_func, retry_count=3, retry_delay=0.1)

        # Check that the function was called only once
        mock_func.assert_called_once()

        # Check that handle_error was called
        self.handler.handle_error.assert_called_once()

        # Check that the right exception was raised
        self.assertEqual(str(context.exception), "Test error")

class TestAccountErrorHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing AccountErrorHandler ===")

    def setUp(self):
        self.handler = AccountErrorHandler()

    def test_handle_account_not_found(self):
        exception = AccountNotFoundError("Test account not found")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertTrue(response["switch_account"])
        self.assertFalse(response["should_abort"])

    def test_handle_account_limit_reached(self):
        exception = AccountLimitReachedError("Test account limit reached")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertTrue(response["switch_account"])
        self.assertFalse(response["should_abort"])

    def test_handle_account_blocked(self):
        exception = AccountBlockedError("Test account blocked")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertTrue(response["switch_account"])
        self.assertFalse(response["should_abort"])

    def test_handle_account_in_cooldown(self):
        # Create an exception with a custom cooldown time
        exception = AccountInCooldownError("Test account in cooldown")
        exception.cooldown_time = 300

        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertTrue(response["switch_account"])
        self.assertTrue(response["cooldown"])
        self.assertEqual(response["cooldown_time"], 300)
        self.assertFalse(response["should_abort"])

    def test_handle_phone_number_banned(self):
        exception = PhoneNumberBannedError("Test phone banned")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertTrue(response["switch_account"])
        self.assertFalse(response["should_abort"])

class TestTelegramErrorHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing TelegramErrorHandler ===")

    def setUp(self):
        self.handler = TelegramErrorHandler()

    def test_handle_flood_wait_error_short(self):
        # Create an exception with a short wait time
        exception = FloodWaitError("Test flood wait")
        exception.seconds = 60

        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertTrue(response["retry"])
        self.assertFalse(response["switch_account"])
        self.assertTrue(response["cooldown"])
        self.assertEqual(response["cooldown_time"], 60)
        self.assertFalse(response["should_abort"])

    def test_handle_flood_wait_error_long(self):
        # Create an exception with a long wait time
        exception = FloodWaitError("Test flood wait")
        exception.seconds = 600

        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertTrue(response["retry"])
        self.assertTrue(response["switch_account"])  # Should switch for long waits
        self.assertTrue(response["cooldown"])
        self.assertEqual(response["cooldown_time"], 600)
        self.assertFalse(response["should_abort"])

    def test_handle_peer_flood_error(self):
        exception = PeerFloodError("Test peer flood")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertFalse(response["retry"])
        self.assertTrue(response["switch_account"])
        self.assertTrue(response["cooldown"])
        self.assertEqual(response["cooldown_time"], 1800)
        self.assertFalse(response["should_abort"])

    def test_handle_user_privacy_restricted(self):
        exception = UserPrivacyRestrictedError("Test privacy settings")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertFalse(response["retry"])
        self.assertFalse(response["switch_account"])
        self.assertFalse(response["should_abort"])

    def test_handle_api_id_invalid(self):
        exception = ApiIdInvalidError("Test invalid API ID")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertFalse(response["retry"])
        self.assertTrue(response["switch_account"])
        self.assertTrue(response["should_abort"])

class TestGroupErrorHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing GroupErrorHandler ===")

    def setUp(self):
        self.handler = GroupErrorHandler()

    def test_handle_group_not_found(self):
        exception = GroupNotFoundError("Test group not found")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertFalse(response["retry"])
        self.assertTrue(response["should_abort"])

    def test_handle_not_group_admin(self):
        exception = NotGroupAdminError("Test not admin")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertFalse(response["retry"])
        self.assertTrue(response["switch_account"])
        self.assertFalse(response["should_abort"])

    def test_handle_member_extraction_error(self):
        exception = MemberExtractionError("Test extraction error")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertTrue(response["retry"])
        self.assertTrue(response["cooldown"])
        self.assertEqual(response["cooldown_time"], 60)
        self.assertFalse(response["should_abort"])

    def test_handle_member_addition_error(self):
        exception = MemberAdditionError("Test addition error")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertTrue(response["retry"])
        self.assertTrue(response["cooldown"])
        self.assertEqual(response["cooldown_time"], 60)
        self.assertFalse(response["should_abort"])

class TestSessionErrorHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing SessionErrorHandler ===")

    def setUp(self):
        self.handler = SessionErrorHandler()

    def test_handle_session_expired(self):
        exception = SessionExpiredError("Test session expired")
        response = self.handler.handle_error(exception)

        self.assertTrue(response["handled"])
        self.assertFalse(response["retry"])
        self.assertTrue(response["switch_account"])
        self.assertFalse(response["should_abort"])

class TestCompositeErrorHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing CompositeErrorHandler ===")

    def setUp(self):
        self.account_handler = AccountErrorHandler()
        self.telegram_handler = TelegramErrorHandler()
        self.composite_handler = CompositeErrorHandler([
            self.account_handler,
            self.telegram_handler
        ])

    def test_add_handler(self):
        # Create a new handler
        group_handler = GroupErrorHandler()

        # Add it to the composite handler
        self.composite_handler.add_handler(group_handler)

        # Check that it was added
        self.assertIn(group_handler, self.composite_handler.handlers)

    def test_handle_error_first_handler(self):
        # Mock the handlers
        self.account_handler.handle_error = MagicMock(return_value={"handled": True, "message": "Account handler"})
        self.telegram_handler.handle_error = MagicMock(return_value={"handled": True, "message": "Telegram handler"})

        # Call handle_error with an AccountError
        exception = AccountNotFoundError("Test error")
        response = self.composite_handler.handle_error(exception)

        # Check that only the first handler was called
        self.account_handler.handle_error.assert_called_once()
        self.telegram_handler.handle_error.assert_not_called()

        # Check response
        self.assertEqual(response["message"], "Account handler")

    def test_handle_error_second_handler(self):
        # Mock the handlers
        self.account_handler.handle_error = MagicMock(return_value={"handled": False})
        self.telegram_handler.handle_error = MagicMock(return_value={"handled": True, "message": "Telegram handler"})

        # Call handle_error with a TelegramError
        exception = FloodWaitError("Test error")
        response = self.composite_handler.handle_error(exception)

        # Check that both handlers were called
        self.account_handler.handle_error.assert_called_once()
        self.telegram_handler.handle_error.assert_called_once()

        # Check response
        self.assertEqual(response["message"], "Telegram handler")

    def test_handle_error_no_handler(self):
        # Mock the handlers
        self.account_handler.handle_error = MagicMock(return_value={"handled": False})
        self.telegram_handler.handle_error = MagicMock(return_value={"handled": False})

        # Call handle_error with an exception that no handler handles
        exception = KeyError("Test error")
        response = self.composite_handler.handle_error(exception)

        # Check that both handlers were called
        self.account_handler.handle_error.assert_called_once()
        self.telegram_handler.handle_error.assert_called_once()

        # Check response
        self.assertTrue(response["handled"])
        self.assertEqual(response["message"], "Unknown error occurred")

class TestHelperFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Testing Helper Functions ===")

    def test_create_default_error_handler(self):
        handler = create_default_error_handler()

        # Check that it's a CompositeErrorHandler
        self.assertIsInstance(handler, CompositeErrorHandler)

        # Check that it has all the expected handlers
        self.assertEqual(len(handler.handlers), 4)

        # Check the types of handlers
        handler_types = [type(h) for h in handler.handlers]
        self.assertIn(AccountErrorHandler, handler_types)
        self.assertIn(TelegramErrorHandler, handler_types)
        self.assertIn(GroupErrorHandler, handler_types)
        self.assertIn(SessionErrorHandler, handler_types)

    def test_handle_error(self):
        # Mock the default error handler
        with patch('error_handling.error_handlers.default_error_handler.handle_error') as mock_handle:
            mock_handle.return_value = {"handled": True, "message": "Test handled"}

            # Call handle_error
            exception = ValueError("Test error")
            response = handle_error(exception)

            # Check that the default handler was called
            mock_handle.assert_called_once_with(exception, None)

            # Check response
            self.assertEqual(response, {"handled": True, "message": "Test handled"})

    def test_execute_with_error_handling(self):
        # Create a test function
        def test_func(arg1, arg2=None):
            if arg1 == "fail":
                raise ValueError("Test error")
            return f"Success: {arg1}, {arg2}"

        # Mock the default error handler's execute_with_retry
        with patch('error_handling.error_handlers.default_error_handler.execute_with_retry') as mock_execute:
            mock_execute.return_value = "Success from mock"

            # Call execute_with_error_handling
            result = execute_with_error_handling(test_func, "test", arg2="value")

            # Check that the default handler was called with the right arguments
            mock_execute.assert_called_once_with(
                test_func, "test", arg2="value",
                retry_count=3, retry_delay=5, context=None
            )

            # Check result
            self.assertEqual(result, "Success from mock")

if __name__ == "__main__":
    unittest.main(verbosity=2)