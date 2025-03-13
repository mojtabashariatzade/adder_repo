import logging
import traceback
import time
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, Type
from core.exceptions import (
    TelegramAdderError, AccountError, AccountNotFoundError, AccountLimitReachedError,
    AccountBlockedError, AccountInCooldownError, AccountVerificationError,
    APIError, FloodWaitError, PeerFloodError, UserPrivacyRestrictedError,
    PhoneNumberBannedError, ApiIdInvalidError, ApiHashInvalidError,
    GroupNotFoundError, NotGroupAdminError, MemberExtractionError, MemberAdditionError,
    NetworkError, ConnectionError, ProxyError, TimeoutError,
    SessionExpiredError, OperationError
)

logger = logging.getLogger(__name__)

class BaseErrorHandler:
    def __init__(self, retry_count: int = 3, retry_delay: int = 5, fallback_handler: Optional['BaseErrorHandler'] = None):
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.fallback_handler = fallback_handler

    def handle_error(self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if context is None:
            context = {}

        error_type = type(exception).__name__
        error_message = str(exception)

        logger.error(f"Error: {error_type} - {error_message}")

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
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            logger.debug(traceback.format_exc())

        if not response["handled"] and self.fallback_handler:
            try:
                fallback_response = self.fallback_handler.handle_error(exception, context)
                response.update(fallback_response)
            except Exception as e:
                logger.error(f"Error in fallback handler: {e}")
                logger.debug(traceback.format_exc())

        if not response["handled"]:
            response.update(self.handle_unknown_error(exception, context))
            response["handled"] = True

        self.log_error_response(exception, context, response)
        return response

    def handle_unknown_error(self, exception: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Unknown error occurred",
            "should_abort": True
        }

    def log_error_response(self, exception: Exception, context: Dict[str, Any], response: Dict[str, Any]) -> None:
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

        logger.info(f"Error {status}: {type(exception).__name__} - Action: {action_str}")

    def execute_with_retry(self, func: Callable, *args, retry_count: Optional[int] = None,
                         retry_delay: Optional[int] = None, context: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        retries = retry_count if retry_count is not None else self.retry_count
        delay = retry_delay if retry_delay is not None else self.retry_delay
        current_try = 0
        last_exception = None

        while current_try <= retries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                current_try += 1

                if current_try > retries:
                    break

                error_response = self.handle_error(e, context)

                if error_response.get("should_abort", False):
                    logger.warning(f"Aborting retry due to error: {e}")
                    break

                if error_response.get("retry", True):
                    cooldown_time = error_response.get("cooldown_time", delay)
                    logger.info(f"Retrying in {cooldown_time} seconds (attempt {current_try}/{retries})")
                    time.sleep(cooldown_time)
                else:
                    logger.info(f"Not retrying due to error handler decision")
                    break

        if last_exception:
            raise last_exception

class AccountErrorHandler(BaseErrorHandler):
    def handle_AccountNotFoundError(self, exception: AccountNotFoundError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account not found",
            "switch_account": True,
            "should_abort": False
        }

    def handle_AccountLimitReachedError(self, exception: AccountLimitReachedError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account has reached its daily limit",
            "switch_account": True,
            "should_abort": False
        }

    def handle_AccountBlockedError(self, exception: AccountBlockedError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account is blocked by Telegram",
            "switch_account": True,
            "should_abort": False
        }

    def handle_AccountInCooldownError(self, exception: AccountInCooldownError, context: Dict[str, Any]) -> Dict[str, Any]:
        cooldown_time = getattr(exception, 'cooldown_time', 3600)
        return {
            "message": f"Account is in cooldown period for {cooldown_time} seconds",
            "switch_account": True,
            "cooldown": True,
            "cooldown_time": cooldown_time,
            "should_abort": False
        }

    def handle_AccountVerificationError(self, exception: AccountVerificationError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account verification failed",
            "switch_account": True,
            "should_abort": False
        }

    def handle_PhoneNumberBannedError(self, exception: PhoneNumberBannedError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Phone number is banned by Telegram",
            "switch_account": True,
            "should_abort": False
        }

class TelegramErrorHandler(BaseErrorHandler):
    def handle_FloodWaitError(self, exception: FloodWaitError, context: Dict[str, Any]) -> Dict[str, Any]:
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

    def handle_PeerFloodError(self, exception: PeerFloodError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Too many requests. Telegram enforced peer flood protection",
            "retry": False,
            "switch_account": True,
            "cooldown": True,
            "cooldown_time": 1800,
            "should_abort": False
        }

    def handle_UserPrivacyRestrictedError(self, exception: UserPrivacyRestrictedError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "User's privacy settings prevent this action",
            "retry": False,
            "switch_account": False,
            "should_abort": False
        }

    def handle_ApiIdInvalidError(self, exception: ApiIdInvalidError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "API ID is invalid",
            "retry": False,
            "switch_account": True,
            "should_abort": True
        }

    def handle_ApiHashInvalidError(self, exception: ApiHashInvalidError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "API hash is invalid",
            "retry": False,
            "switch_account": True,
            "should_abort": True
        }

    def handle_ConnectionError(self, exception: ConnectionError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Connection error. Check your internet connection",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 30,
            "should_abort": False
        }

    def handle_TimeoutError(self, exception: TimeoutError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Connection timed out",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 30,
            "should_abort": False
        }

    def handle_ProxyError(self, exception: ProxyError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Error with proxy connection",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 30,
            "should_abort": False
        }

class GroupErrorHandler(BaseErrorHandler):
    def handle_GroupNotFoundError(self, exception: GroupNotFoundError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Group not found",
            "retry": False,
            "should_abort": True
        }

    def handle_NotGroupAdminError(self, exception: NotGroupAdminError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Account is not an admin of the group",
            "retry": False,
            "switch_account": True,
            "should_abort": False
        }

    def handle_MemberExtractionError(self, exception: MemberExtractionError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Failed to extract members from group",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 60,
            "should_abort": False
        }

    def handle_MemberAdditionError(self, exception: MemberAdditionError, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message": "Failed to add members to group",
            "retry": True,
            "cooldown": True,
            "cooldown_time": 60,
            "should_abort": False
        }

class SessionErrorHandler(BaseErrorHandler):
    def handle_SessionExpiredError(self, exception: SessionExpiredError, context: Dict[str, Any]) -> Dict[str, Any]:
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

    def add_handler(self, handler: BaseErrorHandler) -> None:
        self.handlers.append(handler)

    def handle_error(self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
            except Exception as e:
                logger.error(f"Error in handler {type(handler).__name__}: {e}")
                logger.debug(traceback.format_exc())

        if not response["handled"]:
            response.update(self.handle_unknown_error(exception, context))
            response["handled"] = True

        self.log_error_response(exception, context, response)
        return response

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

def handle_error(exception: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return default_error_handler.handle_error(exception, context)

def execute_with_error_handling(func: Callable, *args, retry_count: int = 3,
                              retry_delay: int = 5, context: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
    handler = default_error_handler
    return handler.execute_with_retry(func, *args, retry_count=retry_count,
                                    retry_delay=retry_delay, context=context, **kwargs)