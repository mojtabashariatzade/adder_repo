"""
Exceptions Module

This module defines custom exceptions used throughout the application.
Exceptions are organized hierarchically for better error handling and reporting.

Usage:
    from core.exceptions import AccountNotFoundError

    try:
        # Some operation that might fail
        raise AccountNotFoundError("Account with phone +1234567890 not found")
    except AccountNotFoundError as e:
        # Handle the specific error
        print(f"Specific error handling: {e}")
    except AccountError as e:
        # Handle any account-related error
        print(f"Generic account error handling: {e}")
    except TelegramAdderError as e:
        # Handle any application error
        print(f"Application error handling: {e}")
"""


class TelegramAdderError(Exception):
    """Base exception class for all application-specific exceptions."""

    def __init__(self, message="An error occurred in the Telegram Account Manager"):
        self.message = message
        super().__init__(self.message)


# Account-related exceptions
class AccountError(TelegramAdderError):
    """Base exception for all account-related errors."""

    def __init__(self, message="An account-related error occurred"):
        super().__init__(message)


class AccountNotFoundError(AccountError):
    """Raised when trying to access a non-existent account."""

    def __init__(self, message="The specified account was not found"):
        super().__init__(message)


class AccountLimitReachedError(AccountError):
    """Raised when an account has reached its daily limit for adding/extracting members."""

    def __init__(self, message="The account has reached its daily limit"):
        super().__init__(message)


class AccountBlockedError(AccountError):
    """Raised when an account is blocked by Telegram."""

    def __init__(self, message="The account is blocked by Telegram"):
        super().__init__(message)


class AccountInCooldownError(AccountError):
    """Raised when an account is in cooldown period."""

    def __init__(self, message="The account is in cooldown period"):
        super().__init__(message)


class AccountVerificationError(AccountError):
    """Raised when there's an issue with account verification."""

    def __init__(self, message="Account verification failed"):
        super().__init__(message)


# API-related exceptions
class APIError(TelegramAdderError):
    """Base exception for all API-related errors."""

    def __init__(self, message="An API-related error occurred"):
        super().__init__(message)


class FloodWaitError(APIError):
    """Raised when Telegram API returns a flood wait error."""

    def __init__(self, seconds=None):
        message = (
            f"Flood wait error. Wait for {seconds} seconds before next request"
            if seconds else "Flood wait error"
        )
        super().__init__(message)
        self.seconds = seconds


class PeerFloodError(APIError):
    """Raised when Telegram API returns a peer flood error."""

    def __init__(self, message="Too many requests to add members. Please slow down"):
        super().__init__(message)


class UserPrivacyRestrictedError(APIError):
    """Raised when a user's privacy settings restrict adding them to a group."""

    def __init__(self, message="User's privacy settings prevent adding them to the group"):
        super().__init__(message)


class PhoneNumberBannedError(APIError):
    """Raised when a phone number is banned by Telegram."""

    def __init__(self, message="The phone number is banned by Telegram"):
        super().__init__(message)


class ApiIdInvalidError(APIError):
    """Raised when the provided API ID is invalid."""

    def __init__(self, message="The provided API ID is invalid"):
        super().__init__(message)


class ApiHashInvalidError(APIError):
    """Raised when the provided API hash is invalid."""

    def __init__(self, message="The provided API hash is invalid"):
        super().__init__(message)


# Configuration-related exceptions
class ConfigError(TelegramAdderError):
    """Base exception for all configuration-related errors."""

    def __init__(self, message="A configuration error occurred"):
        super().__init__(message)


class ConfigFileNotFoundError(ConfigError):
    """Raised when a configuration file is not found."""

    def __init__(self, file_path=None):
        message = (
            f"Configuration file not found: {file_path}"
            if file_path else "Configuration file not found"
        )
        super().__init__(message)
        self.file_path = file_path


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""

    def __init__(self, issues=None):
        message = (
            f"Configuration validation failed: {', '.join(issues)}"
            if issues else "Configuration validation failed"
        )
        super().__init__(message)
        self.issues = issues or []


class ConfigEncryptionError(ConfigError):
    """Raised when there's an issue with configuration encryption."""

    def __init__(self, message="Configuration encryption error"):
        super().__init__(message)


# File-related exceptions
class FileError(TelegramAdderError):
    """Base exception for all file-related errors."""

    def __init__(self, message="A file-related error occurred"):
        super().__init__(message)


class FileReadError(FileError):
    """Raised when a file cannot be read."""

    def __init__(self, file_path=None, original_error=None):
        message = f"Error reading file: {file_path}"
        if original_error:
            message += f" ({original_error})"
        super().__init__(message)
        self.file_path = file_path
        self.original_error = original_error


class FileWriteError(FileError):
    """Raised when a file cannot be written."""

    def __init__(self, file_path=None, original_error=None):
        message = f"Error writing to file: {file_path}"
        if original_error:
            message += f" ({original_error})"
        super().__init__(message)
        self.file_path = file_path
        self.original_error = original_error


class FileFormatError(FileError):
    """Raised when a file has an invalid format (e.g., malformed JSON)."""

    def __init__(self, file_path=None, original_error=None):
        message = f"Invalid file format: {file_path}"
        if original_error:
            message += f" ({original_error})"
        super().__init__(message)
        self.file_path = file_path
        self.original_error = original_error


# Network-related exceptions
class NetworkError(TelegramAdderError):
    """Base exception for all network-related errors."""

    def __init__(self, message="A network error occurred"):
        super().__init__(message)


class ConnectionErrors(NetworkError):
    """Raised when there's a connection issue."""

    def __init__(self, message="Failed to establish connection"):
        super().__init__(message)


class ProxyError(NetworkError):
    """Raised when there's an issue with the proxy."""

    def __init__(self, message="Proxy connection error"):
        super().__init__(message)


class TimeoutErrors(NetworkError):
    """Raised when a network operation times out."""

    def __init__(self, message="Network operation timed out"):
        super().__init__(message)


# Operation-related exceptions
class OperationError(TelegramAdderError):
    """Base exception for all operation-related errors."""

    def __init__(self, message="An operation error occurred"):
        super().__init__(message)


class GroupNotFoundError(OperationError):
    """Raised when a Telegram group is not found."""

    def __init__(self, message="The specified group was not found"):
        super().__init__(message)


class NotGroupAdminError(OperationError):
    """Raised when the account is not an admin of the group."""

    def __init__(self, message="The account is not an admin of the group"):
        super().__init__(message)


class NoActiveAccountsError(OperationError):
    """Raised when there are no active accounts available."""

    def __init__(self, message="No active accounts available"):
        super().__init__(message)


class SessionExpiredError(OperationError):
    """Raised when a session has expired."""

    def __init__(self, message="Session has expired"):
        super().__init__(message)


class MemberExtractionError(OperationError):
    """Raised when there's an error extracting members from a group."""

    def __init__(self, message="Failed to extract members from the group"):
        super().__init__(message)


class MemberAdditionError(OperationError):
    """Raised when there's an error adding members to a group."""

    def __init__(self, message="Failed to add members to the group"):
        super().__init__(message)


# Authentication-related exceptions
class AuthenticationError(TelegramAdderError):
    """Base exception for all authentication-related errors."""

    def __init__(self, message="An authentication error occurred"):
        super().__init__(message)


class LoginFailedError(AuthenticationError):
    """Raised when login to Telegram fails."""

    def __init__(self, message="Failed to log in to Telegram"):
        super().__init__(message)


class CodeRequestFailedError(AuthenticationError):
    """Raised when requesting a login code from Telegram fails."""

    def __init__(self, message="Failed to request a login code from Telegram"):
        super().__init__(message)


class CodeInvalidError(AuthenticationError):
    """Raised when the provided login code is invalid."""

    def __init__(self, message="The provided login code is invalid"):
        super().__init__(message)


class TwoFactorRequiredError(AuthenticationError):
    """Raised when two-factor authentication is required but not provided."""

    def __init__(self, message="Two-factor authentication is required"):
        super().__init__(message)


class TwoFactorInvalidError(AuthenticationError):
    """Raised when the provided two-factor authentication password is invalid."""

    def __init__(self, message="The provided two-factor authentication password is invalid"):
        super().__init__(message)


# Strategy-related exceptions
class StrategyError(TelegramAdderError):
    """Base exception for all strategy-related errors."""

    def __init__(self, message="A strategy error occurred"):
        super().__init__(message)


class StrategyNotFoundError(StrategyError):
    """Raised when a requested strategy is not found."""

    def __init__(self, strategy_name=None):
        message = f"Strategy not found: {strategy_name}" if strategy_name else "Strategy not found"
        super().__init__(message)
        self.strategy_name = strategy_name


class StrategyExecutionError(StrategyError):
    """Raised when a strategy execution fails."""

    def __init__(self, message="Strategy execution failed"):
        super().__init__(message)


# Utils-related exceptions
class UtilsError(TelegramAdderError):
    """Base exception for all utils-related errors."""

    def __init__(self, message="A utility error occurred"):
        super().__init__(message)


class ValidationError(UtilsError):
    """Raised when validation fails."""

    def __init__(self, field=None, message=None):
        error_message = (
            f"Validation failed for field '{field}': {message}"
            if field else message or "Validation failed"
        )
        super().__init__(error_message)
        self.field = field


class EncryptionError(UtilsError):
    """Raised when encryption or decryption fails."""

    def __init__(self, message="Encryption or decryption failed"):
        super().__init__(message)


class DecryptionError(EncryptionError):
    """Raised when decryption specifically fails (e.g., wrong password)."""

    def __init__(self, message="Decryption failed. Wrong password?"):
        super().__init__(message)


# Add these mappings to convert Telethon exceptions to our custom exceptions
def map_telethon_exception(telethon_exception):
    """
    Map Telethon exceptions to our custom exceptions.

    Args:
        telethon_exception: Exception from Telethon library

    Returns:
        Corresponding custom exception instance
    """
    # This function assumes telethon's errors module is imported
    # The actual mapping should be done in the error_handling module
    # This is just a skeleton to show the concept
    exception_name = type(telethon_exception).__name__

    exception_map = {
        "FloodWaitError": lambda e: FloodWaitError(getattr(e, "seconds", None)),
        "PeerFloodError": lambda e: PeerFloodError(),
        "UserPrivacyRestrictedError": lambda e: UserPrivacyRestrictedError(),
        "PhoneNumberBannedError": lambda e: PhoneNumberBannedError(),
        "ApiIdInvalidError": lambda e: ApiIdInvalidError(),
        "ApiHashInvalidError": lambda e: ApiHashInvalidError(),
        # Add more mappings as needed
    }

    if exception_name in exception_map:
        return exception_map[exception_name](telethon_exception)

    # Default to a generic API error if no specific mapping is found
    return APIError(str(telethon_exception))
