import logging
import traceback
import time
import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, Type
from pathlib import Path

from core.exceptions import (
    TelegramAdderError, AccountError, AccountNotFoundError, AccountLimitReachedError,
    AccountBlockedError, AccountInCooldownError, AccountVerificationError,
    APIError, FloodWaitError, PeerFloodError, UserPrivacyRestrictedError,
    PhoneNumberBannedError, ApiIdInvalidError, ApiHashInvalidError,
    GroupNotFoundError, NotGroupAdminError, MemberExtractionError, MemberAdditionError,
    NetworkError, ConnectionError, ProxyError, TimeoutError,
    SessionExpiredError, OperationError
)

from error_handling.error_handlers import (
    BaseErrorHandler, AccountErrorHandler, TelegramErrorHandler,
    GroupErrorHandler, SessionErrorHandler, CompositeErrorHandler,
    create_default_error_handler, handle_error, execute_with_error_handling
)

logger = logging.getLogger(__name__)

class ErrorManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ErrorManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, error_log_dir: str = "logs/errors",
                 max_log_files: int = 10,
                 keep_in_memory: int = 100):
        if self._initialized:
            return

        self.error_log_dir = error_log_dir
        self.max_log_files = max_log_files
        self.keep_in_memory = keep_in_memory
        self.recent_errors = []
        self.handlers = {}
        self.converters = {}

        self.default_handler = create_default_error_handler()

        self._setup_log_directory()
        self._register_default_converters()
        self._initialized = True

    def _setup_log_directory(self):
        os.makedirs(self.error_log_dir, exist_ok=True)

    def _register_default_converters(self):
        self.register_converter("telethon.errors.FloodWaitError", self._convert_telethon_flood_wait)
        self.register_converter("telethon.errors.PeerFloodError", self._convert_telethon_peer_flood)
        self.register_converter("telethon.errors.UserPrivacyRestrictedError", self._convert_telethon_privacy)
        self.register_converter("telethon.errors.PhoneNumberBannedError", self._convert_telethon_banned)
        self.register_converter("telethon.errors.AuthKeyError", self._convert_telethon_auth_key)
        self.register_converter("telethon.errors.SessionPasswordNeededError", self._convert_telethon_session_password)
        self.register_converter("telethon.errors.PhoneCodeInvalidError", self._convert_telethon_phone_code)

    def register_handler(self, error_type: Union[Type[Exception], str], handler: BaseErrorHandler) -> None:
        if isinstance(error_type, type):
            error_type = error_type.__name__

        self.handlers[error_type] = handler
        logger.debug(f"Registered handler {handler.__class__.__name__} for {error_type}")

    def register_converter(self, error_type: str, converter: Callable[[Exception], Exception]) -> None:
        self.converters[error_type] = converter
        logger.debug(f"Registered converter for {error_type}")

    def _convert_telethon_flood_wait(self, exception):
        wait_seconds = getattr(exception, 'seconds', 60)
        return FloodWaitError(f"Flood wait for {wait_seconds} seconds")

    def _convert_telethon_peer_flood(self, exception):
        return PeerFloodError("Too many requests to add members")

    def _convert_telethon_privacy(self, exception):
        return UserPrivacyRestrictedError("User's privacy settings prevent adding them")

    def _convert_telethon_banned(self, exception):
        return PhoneNumberBannedError("The phone number is banned by Telegram")

    def _convert_telethon_auth_key(self, exception):
        return SessionExpiredError("Session has expired or is invalid")

    def _convert_telethon_session_password(self, exception):
        return AccountVerificationError("Two-factor authentication is required")

    def _convert_telethon_phone_code(self, exception):
        return AccountVerificationError("Invalid phone code provided")

    def convert_exception(self, exception: Exception) -> Exception:
        exception_type = type(exception).__name__
        exception_module = exception.__class__.__module__
        qualified_name = f"{exception_module}.{exception_type}"

        converter = self.converters.get(qualified_name)
        if converter:
            try:
                converted = converter(exception)
                logger.debug(f"Converted {qualified_name} to {type(converted).__name__}")
                return converted
            except Exception as e:
                logger.error(f"Error converting exception {qualified_name}: {e}")

        return exception

    def handle(self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if context is None:
            context = {}

        try:
            # First, try to convert the exception
            converted_exception = self.convert_exception(exception)

            # Then, try to find a specific handler
            exception_type = type(converted_exception).__name__
            handler = self.handlers.get(exception_type, self.default_handler)

            # Handle the exception
            response = handler.handle_error(converted_exception, context)

            # Add to recent errors
            self._add_to_recent_errors(converted_exception, context, response)

            # Log the error
            self._log_error(converted_exception, context, response)

            return response
        except Exception as e:
            logger.error(f"Error in ErrorManager.handle: {e}")
            logger.debug(traceback.format_exc())

            # Fallback to a simple response
            return {
                "success": False,
                "error_type": type(exception).__name__,
                "error_message": str(exception),
                "handled": False,
                "retry": False,
                "should_abort": True
            }

    def _add_to_recent_errors(self, exception: Exception, context: Dict[str, Any], response: Dict[str, Any]) -> None:
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(exception).__name__,
            "error_message": str(exception),
            "context": context.copy() if context else {},
            "response": response.copy(),
            "traceback": traceback.format_exc()
        }

        self.recent_errors.append(error_entry)

        # Trim if needed
        if len(self.recent_errors) > self.keep_in_memory:
            self.recent_errors = self.recent_errors[-self.keep_in_memory:]

    def _log_error(self, exception: Exception, context: Dict[str, Any], response: Dict[str, Any]) -> None:
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(exception).__name__,
            "error_message": str(exception),
            "context": context.copy() if context else {},
            "response": response.copy(),
            "traceback": traceback.format_exc()
        }

        # Create a filename based on current date
        today = datetime.now().strftime("%Y%m%d")
        log_filename = f"error_log_{today}.json"
        log_path = os.path.join(self.error_log_dir, log_filename)

        # Load existing log file or create a new one
        errors = []
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    errors = json.load(f)
            except Exception as e:
                logger.error(f"Error loading error log file {log_path}: {e}")
                errors = []

        # Add the new error and save
        errors.append(error_entry)
        try:
            with open(log_path, 'w') as f:
                json.dump(errors, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving error log file {log_path}: {e}")

        # Manage log file rotation
        self._rotate_log_files()

    def _rotate_log_files(self) -> None:
        log_files = [f for f in os.listdir(self.error_log_dir) if f.startswith("error_log_") and f.endswith(".json")]
        if len(log_files) <= self.max_log_files:
            return

        log_files.sort()
        files_to_delete = log_files[:-self.max_log_files]

        for file_name in files_to_delete:
            try:
                os.remove(os.path.join(self.error_log_dir, file_name))
                logger.debug(f"Deleted old error log file: {file_name}")
            except Exception as e:
                logger.error(f"Error deleting old error log file {file_name}: {e}")

    def get_recent_errors(self) -> List[Dict[str, Any]]:
        return self.recent_errors.copy()

    def clear_recent_errors(self) -> None:
        self.recent_errors.clear()

    def get_error_stats(self) -> Dict[str, Any]:
        stats = {}

        if not self.recent_errors:
            return {
                "total_errors": 0,
                "error_types": {},
                "retry_rate": 0.0,
                "abort_rate": 0.0,
                "switch_account_rate": 0.0
            }

        total_errors = len(self.recent_errors)
        error_types = {}
        retry_count = 0
        abort_count = 0
        switch_account_count = 0

        for error in self.recent_errors:
            error_type = error.get("error_type", "Unknown")

            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1

            response = error.get("response", {})
            if response.get("retry", False):
                retry_count += 1
            if response.get("should_abort", False):
                abort_count += 1
            if response.get("switch_account", False):
                switch_account_count += 1

        return {
            "total_errors": total_errors,
            "error_types": error_types,
            "retry_rate": (retry_count / total_errors) * 100 if total_errors > 0 else 0.0,
            "abort_rate": (abort_count / total_errors) * 100 if total_errors > 0 else 0.0,
            "switch_account_rate": (switch_account_count / total_errors) * 100 if total_errors > 0 else 0.0
        }

    def execute_with_error_handling(self, func: Callable, *args,
                                  retry_count: int = 3, retry_delay: int = 5,
                                  context: Optional[Dict[str, Any]] = None,
                                  **kwargs) -> Any:
        if context is None:
            context = {}

        current_try = 0
        last_exception = None

        while current_try <= retry_count:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                current_try += 1

                if current_try > retry_count:
                    break

                error_response = self.handle(e, context)

                if error_response.get("should_abort", False):
                    logger.warning(f"Aborting retry due to error: {e}")
                    break

                if error_response.get("retry", True):
                    cooldown_time = error_response.get("cooldown_time", retry_delay)
                    logger.info(f"Retrying in {cooldown_time} seconds (attempt {current_try}/{retry_count})")
                    time.sleep(cooldown_time)
                else:
                    logger.info(f"Not retrying due to error handler decision")
                    break

        if last_exception:
            raise last_exception

error_manager = ErrorManager()

def get_error_manager() -> ErrorManager:
    return error_manager

def handle_error(exception: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return error_manager.handle(exception, context)

def execute_safely(func, *args, **kwargs):
    return error_manager.execute_with_error_handling(func, *args, **kwargs)