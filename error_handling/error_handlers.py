"""
Error handling utilities for the application.

This module contains base classes and functions to handle various types
of errors in the application.
"""

import logging
import traceback
import time
from typing import Any, Dict, List, Optional, Callable
from core.exceptions import (
    AccountNotFoundError, AccountLimitReachedError,
    AccountBlockedError, AccountInCooldownError, AccountVerificationError,
    FloodWaitError, PeerFloodError, UserPrivacyRestrictedError,
    PhoneNumberBannedError, ApiIdInvalidError, ApiHashInvalidError,
    GroupNotFoundError, NotGroupAdminError, MemberExtractionError, MemberAdditionError,
    ProxyError, SessionExpiredError
)

logger = logging.getLogger(__name__)

# pylint: disable=missing-class-docstring


class BaseErrorHandler:
    def __init__(self, retry_count: int = 3, retry_delay: int = 5,
                 fallback_handler: Optional['BaseErrorHandler'] = None):
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.fallback_handler = fallback_handler

# pylint: disable=missing-function-docstring

    def handle_error(self, exception: Exception,
                     context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if context is None:
            context = {}

        error_type = type(exception).__name__
        error_message = str(exception)

        logger.error("Error: %s - %s", error_type, error_message)

        response = {
            "success": False,
            "error_type": error_type,
            "error_message": error_message,
            "handled": False,
            "retry": False,
            "switch_account": False,
            "cooldown": False,
            "cooldown_time": 0,
            "should_abort": False
        }

        try:
            error_method_name = f"handle_{error_type}"
            if hasattr(self, error_method_name):
                error_handler = getattr(self, error_method_name)
                handler_response = error_handler(exception, context)
                if handler_response:
                    response.update(handler_response)
                    response["handled"] = True
        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Error in error handler: %s", e)
            logger.debug(traceback.format_exc())

        if not response["handled"] and self.fallback_handler:
            try:
                fallback_response = self.fallback_handler.handle_error(
                    exception, context)
                response.update(fallback_response)
            except (ValueError, TypeError, AttributeError) as e:
                logger.error("Error in fallback handler: %s", e)
                logger.debug(traceback.format_exc())

        if not response["handled"]:
            response.update(self.handle_unknown_error(exception, context))
            response["handled"] = True

        self.log_error_response(exception, context, response)
        return response

    def handle_unknown_error(self, _exception: Exception,
                             _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Unknown error occurred",
            "should_abort": True
        }

    def log_error_response(self, exception: Exception,
                           _context: Dict[str, Any], response: Dict[str, Any]) -> None:
        status = "handled" if response["handled"] else "unhandled"
        action = []

        if response.get("retry"):
            action.append("retry")
        if response.get("switch_account"):
            action.append("switch account")
        if response.get("cooldown"):
            action.append(f"cooldown for {response.get('cooldown_time')}s")
        if response.get("should_abort"):
            action.append("abort operation")

        action_str = ", ".join(action) if action else "no action"

        logger.info("Error %s: %s - Action: %s", status,
                    type(exception).__name__, action_str)

    def execute_with_retry(
        self,
        func: Callable,
        *args,
        retry_count: Optional[int] = None,
        retry_delay: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        retries = retry_count if retry_count is not None else self.retry_count
        delay = retry_delay if retry_delay is not None else self.retry_delay
        current_try = 0
        last_exception = None

        while current_try <= retries:
            try:
                return func(*args, **kwargs)
            except (ValueError, TypeError, AttributeError) as e:
                last_exception = e
                current_try += 1

                if current_try > retries:
                    break

                error_response = self.handle_error(e, context)

                if error_response.get("should_abort", False):
                    logger.warning("Aborting retry due to error: %s", e)
                    break

                if error_response.get("retry", True):
                    cooldown_time = error_response.get("cooldown_time", delay)
                    logger.info("Retrying in %s seconds (attempt %s/%s)",
                                cooldown_time, current_try, retries)
                    time.sleep(cooldown_time)
                else:
                    logger.info("Not retrying due to error handler decision")
                    break

        if last_exception:
            raise last_exception


class AccountErrorHandler(BaseErrorHandler):
    # pylint: disable=missing-function-docstring
    def handle_account_not_found_error(self, _exception: AccountNotFoundError,
                                       _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account not found",
            "switch_account": True,
            "should_abort": False
        }

    def handle_account_limit_reached_error(self, _exception: AccountLimitReachedError,
                                           _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account has reached its daily limit",
            "switch_account": True,
            "should_abort": False
        }

    def handle_account_blocked_error(self, _exception: AccountBlockedError,
                                     _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account is blocked by Telegram",
            "switch_account": True,
            "should_abort": False
        }

    def handle_account_in_cooldown_error(self, exception: AccountInCooldownError,
                                         _context: Dict[str, Any]) -> Dict[str, Any]:
        cooldown_time = getattr(exception, 'cooldown_time', 3600)
        return {
            "message": f"Account is in cooldown period for {cooldown_time} seconds",
            "switch_account": True,
            "cooldown": True,
            "cooldown_time": cooldown_time,
            "should_abort": False
        }

    def handle_account_verification_error(self, _exception: AccountVerificationError,
                                          _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account verification failed",
            "switch_account": True,
            "should_abort": False
        }

    def handle_phone_number_banned_error(self, _exception: PhoneNumberBannedError,
                                         _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Phone number is banned by Telegram",
            "switch_account": True,
            "should_abort": False
        }


class TelegramErrorHandler(BaseErrorHandler):
    # pylint: disable=missing-function-docstring
    def handle_flood_wait_error(self, exception: FloodWaitError,
                                _context: Dict[str, Any]) -> Dict[str, Any]:
        seconds = getattr(exception, 'seconds', 60)
        cooldown_time = min(seconds, 3600)

        return {
            "message": f"Telegram rate limit hit. Wait for {seconds} seconds",
            "retry": True,
            "switch_account": seconds > 300,
            "cooldown": True,
            "cooldown_time": cooldown_time,
            "should_abort": False
        }

    def handle_peer_flood_error(self, _exception: PeerFloodError,
                                _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Too many requests. Telegram enforced peer flood protection",
            "retry": False,
            "switch_account": True,
            "cooldown": True,
            "cooldown_time": 1800,
            "should_abort": False
        }

    def handle_user_privacy_restricted_error(self, _exception: UserPrivacyRestrictedError,
                                             _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "User's privacy settings prevent this action",
            "retry": False,
            "switch_account": False,
            "should_abort": False
        }

    def handle_api_id_invalid_error(self, _exception: ApiIdInvalidError,
                                    _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "API ID is invalid",
            "retry": False,
            "switch_account": True,
            "should_abort": True
        }

    def handle_api_hash_invalid_error(self, _exception: ApiHashInvalidError,
                                      _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "API hash is invalid",
            "retry": False,
            "switch_account": True,
            "should_abort": True
        }

    def handle_connection_error(self, _exception: ConnectionError,
                                _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Connection error. Check your internet connection",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 30,
            "should_abort": False
        }

    def handle_timeout_error(self, _exception: TimeoutError,
                             _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Connection timed out",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 30,
            "should_abort": False
        }

    def handle_proxy_error(self, _exception: ProxyError,
                           _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Error with proxy connection",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 30,
            "should_abort": False
        }


class GroupErrorHandler(BaseErrorHandler):
    # pylint: disable=missing-function-docstring
    def handle_group_not_found_error(self, _exception: GroupNotFoundError,
                                     _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Group not found",
            "retry": False,
            "should_abort": True
        }

    def handle_not_group_admin_error(self, _exception: NotGroupAdminError,
                                     _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account is not an admin of the group",
            "retry": False,
            "switch_account": True,
            "should_abort": False
        }

    def handle_member_extraction_error(self, _exception: MemberExtractionError,
                                       _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Failed to extract members from group",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 60,
            "should_abort": False
        }

# pylint: disable=missing-function-docstring
    def handle_member_addition_error(self, _exception: MemberAdditionError,
                                     _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Failed to add members to group",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 60,
            "should_abort": False
        }


class SessionErrorHandler(BaseErrorHandler):
    # pylint: disable=missing-function-docstring
    def handle_session_expired_error(self, _exception: SessionExpiredError,
                                     _context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Session has expired",
            "retry": False,
            "switch_account": True,
            "should_abort": False
        }


class CompositeErrorHandler(BaseErrorHandler):
    def __init__(self, handlers: Optional[List[BaseErrorHandler]] = None):
        super().__init__()
        self.handlers = handlers or []

# pylint: disable=missing-function-docstring
    def add_handler(self, handler: BaseErrorHandler) -> None:
        self.handlers.append(handler)

    def handle_error(self, exception: Exception,
                     context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if context is None:
            context = {}

        response = {
            "success": False,
            "error_type": type(exception).__name__,
            "error_message": str(exception),
            "handled": False,
            "retry": False,
            "switch_account": False,
            "cooldown": False,
            "cooldown_time": 0,
            "should_abort": False
        }

        for handler in self.handlers:
            try:
                handler_response = handler.handle_error(exception, context)
                if handler_response.get("handled", False):
                    response.update(handler_response)
                    response["handled"] = True
                    break
            except (ValueError, TypeError, AttributeError) as e:
                logger.error("Error in handler %s: %s",
                             type(handler).__name__, e)
                logger.debug(traceback.format_exc())

        if not response["handled"]:
            response.update(self.handle_unknown_error(exception, context))
            response["handled"] = True

        self.log_error_response(exception, context, response)
        return response

# pylint: disable=missing-function-docstring


def create_default_error_handler() -> CompositeErrorHandler:
    account_handler = AccountErrorHandler()
    telegram_handler = TelegramErrorHandler()
    group_handler = GroupErrorHandler()
    session_handler = SessionErrorHandler()

    composite_handler = CompositeErrorHandler([
        account_handler,
        telegram_handler,
        group_handler,
        session_handler
    ])

    return composite_handler


default_error_handler = create_default_error_handler()

# pylint: disable=missing-function-docstring


def handle_error(exception: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return default_error_handler.handle_error(exception, context)

# pylint: disable=missing-function-docstring


def execute_with_error_handling(
    func: Callable,
    *args,
    retry_count: int = 3,
    retry_delay: int = 5,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Any:
    handler = default_error_handler
    return handler.execute_with_retry(func, *args, retry_count=retry_count,
                                      retry_delay=retry_delay, context=context, **kwargs)
