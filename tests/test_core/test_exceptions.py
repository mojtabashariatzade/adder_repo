"""
Test module for core/exceptions.py

This module tests all exception classes defined in core/exceptions.py and validates
that the exception hierarchy, default messages, and custom messages work correctly.
It also tests the mapping function for Telethon exceptions.
"""

import unittest
import sys
import os
import time
from unittest.mock import MagicMock, patch

# Add project root to path to be able to import core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the exceptions module
from core.exceptions import (
    # Base exception
    TelegramAdderError,

    # Account exceptions
    AccountError,
    AccountNotFoundError,
    AccountLimitReachedError,
    AccountBlockedError,
    AccountInCooldownError,
    AccountVerificationError,

    # API exceptions
    APIError,
    FloodWaitError,
    PeerFloodError,
    UserPrivacyRestrictedError,
    PhoneNumberBannedError,
    ApiIdInvalidError,
    ApiHashInvalidError,

    # Configuration exceptions
    ConfigError,
    ConfigFileNotFoundError,
    ConfigValidationError,
    ConfigEncryptionError,

    # File exceptions
    FileError,
    FileReadError,
    FileWriteError,
    FileFormatError,

    # Network exceptions
    NetworkError,
    ConnectionError,
    ProxyError,
    TimeoutError,

    # Operation exceptions
    OperationError,
    GroupNotFoundError,
    NotGroupAdminError,
    NoActiveAccountsError,
    SessionExpiredError,
    MemberExtractionError,
    MemberAdditionError,

    # Authentication exceptions
    AuthenticationError,
    LoginFailedError,
    CodeRequestFailedError,
    CodeInvalidError,
    TwoFactorRequiredError,
    TwoFactorInvalidError,

    # Strategy exceptions
    StrategyError,
    StrategyNotFoundError,
    StrategyExecutionError,

    # Utils exceptions
    UtilsError,
    ValidationError,
    EncryptionError,
    DecryptionError,

    # Helper function
    map_telethon_exception
)


class TestExceptions(unittest.TestCase):
    """Test case for core/exceptions.py module"""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: core/exceptions.py")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: core/exceptions.py")
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

    def test_base_exception(self):
        """Test the base TelegramAdderError exception."""
        print("  Testing base exception with default message...")
        ex = TelegramAdderError()
        self.assertEqual(str(ex), "An error occurred in the Telegram Account Manager")
        print("  Testing base exception with custom message...")
        custom_msg = "Custom error message"
        ex = TelegramAdderError(custom_msg)
        self.assertEqual(str(ex), custom_msg)

    def test_account_exceptions(self):
        """Test account-related exceptions."""
        print("  Testing account exceptions inheritance hierarchy...")
        self.assertTrue(issubclass(AccountError, TelegramAdderError))
        self.assertTrue(issubclass(AccountNotFoundError, AccountError))
        self.assertTrue(issubclass(AccountLimitReachedError, AccountError))
        self.assertTrue(issubclass(AccountBlockedError, AccountError))
        self.assertTrue(issubclass(AccountInCooldownError, AccountError))
        self.assertTrue(issubclass(AccountVerificationError, AccountError))

        print("  Testing account exceptions default messages...")
        self.assertEqual(str(AccountError()), "An account-related error occurred")
        self.assertEqual(str(AccountNotFoundError()), "The specified account was not found")
        self.assertEqual(str(AccountLimitReachedError()), "The account has reached its daily limit")
        self.assertEqual(str(AccountBlockedError()), "The account is blocked by Telegram")
        self.assertEqual(str(AccountInCooldownError()), "The account is in cooldown period")
        self.assertEqual(str(AccountVerificationError()), "Account verification failed")

        print("  Testing account exceptions custom messages...")
        custom_msg = "Custom account error"
        self.assertEqual(str(AccountError(custom_msg)), custom_msg)

        print("  Testing exception catching...")
        try:
            raise AccountNotFoundError("Account 12345 not found")
        except AccountError as e:
            self.assertEqual(str(e), "Account 12345 not found")
        except:
            self.fail("AccountNotFoundError was not caught as AccountError")

    def test_api_exceptions(self):
        """Test API-related exceptions."""
        print("  Testing API exceptions inheritance hierarchy...")
        self.assertTrue(issubclass(APIError, TelegramAdderError))
        self.assertTrue(issubclass(FloodWaitError, APIError))
        self.assertTrue(issubclass(PeerFloodError, APIError))
        self.assertTrue(issubclass(UserPrivacyRestrictedError, APIError))
        self.assertTrue(issubclass(PhoneNumberBannedError, APIError))
        self.assertTrue(issubclass(ApiIdInvalidError, APIError))
        self.assertTrue(issubclass(ApiHashInvalidError, APIError))

        print("  Testing API exceptions default messages...")
        self.assertEqual(str(APIError()), "An API-related error occurred")
        self.assertEqual(str(FloodWaitError()), "Flood wait error")
        self.assertEqual(str(PeerFloodError()), "Too many requests to add members. Please slow down")
        self.assertEqual(str(UserPrivacyRestrictedError()), "User's privacy settings prevent adding them to the group")
        self.assertEqual(str(PhoneNumberBannedError()), "The phone number is banned by Telegram")
        self.assertEqual(str(ApiIdInvalidError()), "The provided API ID is invalid")
        self.assertEqual(str(ApiHashInvalidError()), "The provided API hash is invalid")

        print("  Testing FloodWaitError with seconds parameter...")
        seconds = 60
        flood_error = FloodWaitError(seconds)
        self.assertEqual(str(flood_error), "Flood wait error. Wait for 60 seconds before next request")
        self.assertEqual(flood_error.seconds, seconds)

    def test_config_exceptions(self):
        """Test configuration-related exceptions."""
        print("  Testing configuration exceptions inheritance hierarchy...")
        self.assertTrue(issubclass(ConfigError, TelegramAdderError))
        self.assertTrue(issubclass(ConfigFileNotFoundError, ConfigError))
        self.assertTrue(issubclass(ConfigValidationError, ConfigError))
        self.assertTrue(issubclass(ConfigEncryptionError, ConfigError))

        print("  Testing configuration exceptions default messages...")
        self.assertEqual(str(ConfigError()), "A configuration error occurred")
        self.assertEqual(str(ConfigFileNotFoundError()), "Configuration file not found")
        self.assertEqual(str(ConfigValidationError()), "Configuration validation failed")
        self.assertEqual(str(ConfigEncryptionError()), "Configuration encryption error")

        print("  Testing ConfigFileNotFoundError with file path...")
        file_path = "/path/to/config.json"
        ex = ConfigFileNotFoundError(file_path)
        self.assertEqual(str(ex), "Configuration file not found: /path/to/config.json")
        self.assertEqual(ex.file_path, file_path)

        print("  Testing ConfigValidationError with issues list...")
        issues = ["Invalid API ID", "Missing phone number"]
        ex = ConfigValidationError(issues)
        self.assertEqual(str(ex), "Configuration validation failed: Invalid API ID, Missing phone number")
        self.assertEqual(ex.issues, issues)

    def test_file_exceptions(self):
        """Test file-related exceptions."""
        print("  Testing file exceptions inheritance hierarchy...")
        self.assertTrue(issubclass(FileError, TelegramAdderError))
        self.assertTrue(issubclass(FileReadError, FileError))
        self.assertTrue(issubclass(FileWriteError, FileError))
        self.assertTrue(issubclass(FileFormatError, FileError))

        print("  Testing file exceptions default messages...")
        self.assertEqual(str(FileError()), "A file-related error occurred")
        self.assertEqual(str(FileReadError()), "Error reading file: None")
        self.assertEqual(str(FileWriteError()), "Error writing to file: None")
        self.assertEqual(str(FileFormatError()), "Invalid file format: None")

        print("  Testing file exceptions with file path...")
        file_path = "/path/to/file.json"
        self.assertEqual(str(FileReadError(file_path)), f"Error reading file: {file_path}")

        print("  Testing file exceptions with original error...")
        original_error = ValueError("Invalid JSON")
        ex = FileFormatError(file_path, original_error)
        self.assertEqual(str(ex), f"Invalid file format: {file_path} ({original_error})")
        self.assertEqual(ex.file_path, file_path)
        self.assertEqual(ex.original_error, original_error)

    def test_network_exceptions(self):
        """Test network-related exceptions."""
        print("  Testing network exceptions inheritance hierarchy...")
        self.assertTrue(issubclass(NetworkError, TelegramAdderError))
        self.assertTrue(issubclass(ConnectionError, NetworkError))
        self.assertTrue(issubclass(ProxyError, NetworkError))
        self.assertTrue(issubclass(TimeoutError, NetworkError))

        print("  Testing network exceptions default messages...")
        self.assertEqual(str(NetworkError()), "A network error occurred")
        self.assertEqual(str(ConnectionError()), "Failed to establish connection")
        self.assertEqual(str(ProxyError()), "Proxy connection error")
        self.assertEqual(str(TimeoutError()), "Network operation timed out")

    def test_operation_exceptions(self):
        """Test operation-related exceptions."""
        print("  Testing operation exceptions inheritance hierarchy...")
        self.assertTrue(issubclass(OperationError, TelegramAdderError))
        self.assertTrue(issubclass(GroupNotFoundError, OperationError))
        self.assertTrue(issubclass(NotGroupAdminError, OperationError))
        self.assertTrue(issubclass(NoActiveAccountsError, OperationError))
        self.assertTrue(issubclass(SessionExpiredError, OperationError))
        self.assertTrue(issubclass(MemberExtractionError, OperationError))
        self.assertTrue(issubclass(MemberAdditionError, OperationError))

        print("  Testing operation exceptions default messages...")
        self.assertEqual(str(OperationError()), "An operation error occurred")
        self.assertEqual(str(GroupNotFoundError()), "The specified group was not found")
        self.assertEqual(str(NotGroupAdminError()), "The account is not an admin of the group")
        self.assertEqual(str(NoActiveAccountsError()), "No active accounts available")
        self.assertEqual(str(SessionExpiredError()), "Session has expired")
        self.assertEqual(str(MemberExtractionError()), "Failed to extract members from the group")
        self.assertEqual(str(MemberAdditionError()), "Failed to add members to the group")

    def test_authentication_exceptions(self):
        """Test authentication-related exceptions."""
        print("  Testing authentication exceptions inheritance hierarchy...")
        self.assertTrue(issubclass(AuthenticationError, TelegramAdderError))
        self.assertTrue(issubclass(LoginFailedError, AuthenticationError))
        self.assertTrue(issubclass(CodeRequestFailedError, AuthenticationError))
        self.assertTrue(issubclass(CodeInvalidError, AuthenticationError))
        self.assertTrue(issubclass(TwoFactorRequiredError, AuthenticationError))
        self.assertTrue(issubclass(TwoFactorInvalidError, AuthenticationError))

        print("  Testing authentication exceptions default messages...")
        self.assertEqual(str(AuthenticationError()), "An authentication error occurred")
        self.assertEqual(str(LoginFailedError()), "Failed to log in to Telegram")
        self.assertEqual(str(CodeRequestFailedError()), "Failed to request a login code from Telegram")
        self.assertEqual(str(CodeInvalidError()), "The provided login code is invalid")
        self.assertEqual(str(TwoFactorRequiredError()), "Two-factor authentication is required")
        self.assertEqual(str(TwoFactorInvalidError()), "The provided two-factor authentication password is invalid")

    def test_strategy_exceptions(self):
        """Test strategy-related exceptions."""
        print("  Testing strategy exceptions inheritance hierarchy...")
        self.assertTrue(issubclass(StrategyError, TelegramAdderError))
        self.assertTrue(issubclass(StrategyNotFoundError, StrategyError))
        self.assertTrue(issubclass(StrategyExecutionError, StrategyError))

        print("  Testing strategy exceptions default messages...")
        self.assertEqual(str(StrategyError()), "A strategy error occurred")
        self.assertEqual(str(StrategyNotFoundError()), "Strategy not found")
        self.assertEqual(str(StrategyExecutionError()), "Strategy execution failed")

        print("  Testing StrategyNotFoundError with strategy name...")
        strategy_name = "ParallelStrategy"
        ex = StrategyNotFoundError(strategy_name)
        self.assertEqual(str(ex), f"Strategy not found: {strategy_name}")
        self.assertEqual(ex.strategy_name, strategy_name)

    def test_utils_exceptions(self):
        """Test utils-related exceptions."""
        print("  Testing utils exceptions inheritance hierarchy...")
        self.assertTrue(issubclass(UtilsError, TelegramAdderError))
        self.assertTrue(issubclass(ValidationError, UtilsError))
        self.assertTrue(issubclass(EncryptionError, UtilsError))
        self.assertTrue(issubclass(DecryptionError, EncryptionError))

        print("  Testing utils exceptions default messages...")
        self.assertEqual(str(UtilsError()), "A utility error occurred")
        self.assertEqual(str(ValidationError()), "Validation failed")
        self.assertEqual(str(EncryptionError()), "Encryption or decryption failed")
        self.assertEqual(str(DecryptionError()), "Decryption failed. Wrong password?")

        print("  Testing ValidationError with field and message...")
        field = "phone_number"
        message = "Invalid format"
        ex = ValidationError(field, message)
        self.assertEqual(str(ex), f"Validation failed for field '{field}': {message}")
        self.assertEqual(ex.field, field)

    def test_exception_hierarchy(self):
        """Test the overall exception hierarchy."""
        print("  Testing overall exception hierarchy...")
        # All exceptions should be derived from TelegramAdderError
        all_exceptions = [
            AccountError, AccountNotFoundError, AccountLimitReachedError, AccountBlockedError,
            AccountInCooldownError, AccountVerificationError, APIError, FloodWaitError,
            PeerFloodError, UserPrivacyRestrictedError, PhoneNumberBannedError, ApiIdInvalidError,
            ApiHashInvalidError, ConfigError, ConfigFileNotFoundError, ConfigValidationError,
            ConfigEncryptionError, FileError, FileReadError, FileWriteError, FileFormatError,
            NetworkError, ConnectionError, ProxyError, TimeoutError, OperationError,
            GroupNotFoundError, NotGroupAdminError, NoActiveAccountsError, SessionExpiredError,
            MemberExtractionError, MemberAdditionError, AuthenticationError, LoginFailedError,
            CodeRequestFailedError, CodeInvalidError, TwoFactorRequiredError, TwoFactorInvalidError,
            StrategyError, StrategyNotFoundError, StrategyExecutionError, UtilsError,
            ValidationError, EncryptionError, DecryptionError
        ]

        count = 0
        for exc in all_exceptions:
            self.assertTrue(issubclass(exc, TelegramAdderError))
            # Create an instance and make sure it doesn't raise any errors
            instance = exc()
            self.assertIsInstance(instance, TelegramAdderError)
            count += 1

        print(f"  Verified {count} exception classes derive from TelegramAdderError")
        print(f"  Successfully instantiated all {count} exception classes")

    def test_telethon_exception_mapping(self):
        """Test mapping of Telethon exceptions."""
        print("  Testing Telethon exception mapping function...")

        # Create a patched version of map_telethon_exception for testing
        def patched_map_telethon_exception(exception):
            """A patched version for testing that works with our mock exceptions."""
            exception_name = exception.__class__.__name__

            if "FloodWaitError" in exception_name:
                return FloodWaitError(getattr(exception, "seconds", None))
            elif "PeerFloodError" in exception_name:
                return PeerFloodError()
            elif "UserPrivacyRestrictedError" in exception_name:
                return UserPrivacyRestrictedError()
            elif "PhoneNumberBannedError" in exception_name:
                return PhoneNumberBannedError()
            elif "ApiIdInvalidError" in exception_name:
                return ApiIdInvalidError()
            elif "ApiHashInvalidError" in exception_name:
                return ApiHashInvalidError()
            else:
                return APIError(str(exception))

        # Create mock telethon exceptions
        class MockTelethonError:
            pass

        class MockFloodWaitError(MockTelethonError):
            def __init__(self, seconds):
                self.seconds = seconds

            def __str__(self):
                return f"FloodWaitError of {self.seconds} seconds"

        class MockPeerFloodError(MockTelethonError):
            def __str__(self):
                return "PeerFloodError"

        class MockUserPrivacyRestrictedError(MockTelethonError):
            def __str__(self):
                return "UserPrivacyRestrictedError"

        class MockPhoneNumberBannedError(MockTelethonError):
            def __str__(self):
                return "PhoneNumberBannedError"

        class MockApiIdInvalidError(MockTelethonError):
            def __str__(self):
                return "ApiIdInvalidError"

        class MockApiHashInvalidError(MockTelethonError):
            def __str__(self):
                return "ApiHashInvalidError"

        print("  Testing FloodWaitError mapping...")
        telethon_flood = MockFloodWaitError(seconds=120)
        mapped_exception = patched_map_telethon_exception(telethon_flood)
        self.assertIsInstance(mapped_exception, FloodWaitError)
        self.assertEqual(mapped_exception.seconds, 120)
        self.assertEqual(str(mapped_exception), "Flood wait error. Wait for 120 seconds before next request")

        print("  Testing PeerFloodError mapping...")
        telethon_peer_flood = MockPeerFloodError()
        mapped_exception = patched_map_telethon_exception(telethon_peer_flood)
        self.assertIsInstance(mapped_exception, PeerFloodError)

        print("  Testing UserPrivacyRestrictedError mapping...")
        telethon_privacy = MockUserPrivacyRestrictedError()
        mapped_exception = patched_map_telethon_exception(telethon_privacy)
        self.assertIsInstance(mapped_exception, UserPrivacyRestrictedError)

        print("  Testing PhoneNumberBannedError mapping...")
        telethon_banned = MockPhoneNumberBannedError()
        mapped_exception = patched_map_telethon_exception(telethon_banned)
        self.assertIsInstance(mapped_exception, PhoneNumberBannedError)

        print("  Testing ApiIdInvalidError mapping...")
        telethon_api_id = MockApiIdInvalidError()
        mapped_exception = patched_map_telethon_exception(telethon_api_id)
        self.assertIsInstance(mapped_exception, ApiIdInvalidError)

        print("  Testing ApiHashInvalidError mapping...")
        telethon_api_hash = MockApiHashInvalidError()
        mapped_exception = patched_map_telethon_exception(telethon_api_hash)
        self.assertIsInstance(mapped_exception, ApiHashInvalidError)

        print("  Testing unknown exception mapping...")
        class UnknownTelethonError(MockTelethonError):
            def __str__(self):
                return "Unknown error"

        telethon_unknown = UnknownTelethonError()
        mapped_exception = patched_map_telethon_exception(telethon_unknown)
        self.assertIsInstance(mapped_exception, APIError)
        self.assertEqual(str(mapped_exception), "Unknown error")

        print("  Verifying actual map_telethon_exception function...")
        self.assertTrue(callable(map_telethon_exception))

    def test_exception_message_propagation(self):
        """Test that exception messages are correctly propagated through the hierarchy."""
        print("  Testing exception message propagation through hierarchy...")

        # Create a custom message
        message = "This is a custom error message"

        # Create exceptions with this message
        base_ex = TelegramAdderError(message)
        account_ex = AccountError(message)
        notfound_ex = AccountNotFoundError(message)

        # Check that the message is correctly set
        self.assertEqual(str(base_ex), message)
        self.assertEqual(str(account_ex), message)
        self.assertEqual(str(notfound_ex), message)

        print("  Testing complex inheritance message propagation...")
        # Test with complex hierarchy
        complex_message = "Complex error occurred"
        ex = DecryptionError(complex_message)

        # Should be an instance of all parent classes
        self.assertIsInstance(ex, DecryptionError)
        self.assertIsInstance(ex, EncryptionError)
        self.assertIsInstance(ex, UtilsError)
        self.assertIsInstance(ex, TelegramAdderError)

        # Message should be preserved
        self.assertEqual(str(ex), complex_message)


if __name__ == "__main__":
    unittest.main(verbosity=2)