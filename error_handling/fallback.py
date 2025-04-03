"""
Fallback Module

This module provides fallback mechanisms for error recovery in the Telegram Adder application.
It implements strategies for handling various error scenarios, including network issues,
API rate limits, account blocks, and other operational failures.
"""

import time
import random
import logging
import threading
from enum import Enum, auto
from typing import Any, Callable, Dict, Optional, TypeVar

from core.exceptions import (
    TelegramAdderError, AccountError, APIError,
    FloodWaitError, PeerFloodError, NetworkError,
    OperationError, SessionExpiredError
)

from core.constants import MAX_RETRY_COUNT, DEFAULT_DELAY, MAX_DELAY

try:
    from logging_.logging_manager import get_logger
except ImportError:
    # pylint: disable=missing-function-docstring
    def get_logger(name):
        return logging.getLogger(name)

logger = get_logger("Fallback")

T = TypeVar('T')

# pylint: disable=missing-class-docstring


class FallbackStrategy(Enum):
    RETRY = auto()
    SWITCH_ACCOUNT = auto()
    SWITCH_PROXY = auto()
    WAIT_AND_RETRY = auto()
    ABORT = auto()
    CHECKPOINT = auto()


class RecoveryState(Enum):
    NONE = auto()
    RUNNING = auto()
    RECOVERED = auto()
    FAILED = auto()


class FallbackManager:
    def __init__(self,
                 max_retries: int = MAX_RETRY_COUNT,
                 base_delay: float = DEFAULT_DELAY,
                 max_delay: float = MAX_DELAY):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retry_counts = {}
        self.recovery_data = {}
        self._lock = threading.RLock()

# pylint: disable=missing-function-docstring
    def reset_retry_count(self, operation_id: str) -> None:
        with self._lock:
            if operation_id in self.retry_counts:
                del self.retry_counts[operation_id]

    def get_retry_count(self, operation_id: str) -> int:
        with self._lock:
            return self.retry_counts.get(operation_id, 0)

    def increment_retry_count(self, operation_id: str) -> int:
        with self._lock:
            current = self.retry_counts.get(operation_id, 0)
            self.retry_counts[operation_id] = current + 1
            return self.retry_counts[operation_id]

    def can_retry(self, operation_id: str) -> bool:
        with self._lock:
            return self.get_retry_count(operation_id) < self.max_retries

    def calculate_delay(self, operation_id: str, error: Optional[Exception] = None) -> float:
        retry_count = self.get_retry_count(operation_id)

        if isinstance(error, FloodWaitError) and hasattr(error, 'seconds'):
            return max(error.seconds, self.base_delay)

        factor = min(2 ** retry_count, 10)  # Cap the exponential factor at 10
        jitter = random.uniform(0.8, 1.2)  # Add 20% jitter

        delay = min(self.base_delay * factor * jitter, self.max_delay)
        return delay

    def save_recovery_point(self, operation_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self.recovery_data[operation_id] = {
                "timestamp": time.time(),
                "data": data,
                "state": RecoveryState.RUNNING
            }

    def get_recovery_point(self, operation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            recovery_info = self.recovery_data.get(operation_id)
            if recovery_info:
                return recovery_info.get("data")
            return None

    def clear_recovery_point(self, operation_id: str) -> None:
        with self._lock:
            if operation_id in self.recovery_data:
                del self.recovery_data[operation_id]

    def mark_recovery_complete(self, operation_id: str, success: bool = True) -> None:
        with self._lock:
            if operation_id in self.recovery_data:
                self.recovery_data[operation_id]["state"] = (
                    RecoveryState.RECOVERED if success else RecoveryState.FAILED
                )

    def has_recovery_point(self, operation_id: str) -> bool:
        with self._lock:
            return operation_id in self.recovery_data

    @staticmethod
    def get_fallback_strategy(error: Exception) -> FallbackStrategy:
        if isinstance(error, FloodWaitError):
            return FallbackStrategy.WAIT_AND_RETRY
        elif isinstance(error, PeerFloodError):
            return FallbackStrategy.SWITCH_ACCOUNT
        elif isinstance(error, NetworkError):
            return FallbackStrategy.SWITCH_PROXY
        elif isinstance(error, SessionExpiredError):
            return FallbackStrategy.SWITCH_ACCOUNT
        elif isinstance(error, APIError):
            return FallbackStrategy.RETRY
        elif isinstance(error, AccountError):
            return FallbackStrategy.SWITCH_ACCOUNT
        elif isinstance(error, TelegramAdderError):
            return FallbackStrategy.RETRY
        else:
            return FallbackStrategy.ABORT

# pylint: disable=missing-function-docstring


def retry_operation(
    func: Callable[..., T],
    operation_id: str,
    *args,
    fallback_manager: Optional[FallbackManager] = None,
    max_retries: int = MAX_RETRY_COUNT,
    base_delay: float = DEFAULT_DELAY,
    error_callback: Optional[Callable[[Exception, int], None]] = None,
    **kwargs
) -> T:
    if fallback_manager is None:
        fallback_manager = FallbackManager(
            max_retries=max_retries, base_delay=base_delay)

    fallback_manager.reset_retry_count(operation_id)
    last_error = None

    while fallback_manager.can_retry(operation_id):
        try:
            result = func(*args, **kwargs)
            # Success, reset retry count and return result
            fallback_manager.reset_retry_count(operation_id)
            return result
        except (ValueError, TypeError, AttributeError) as e:
            last_error = e
            retry_count = fallback_manager.increment_retry_count(operation_id)

            # Log the error
            logger.warning(
                "Operation %s failed (attempt %s/%s): %s",
                operation_id,
                retry_count,
                max_retries,
                str(e)
            )
            # Call error callback if provided
            if error_callback:
                error_callback(e, retry_count)

            # Get fallback strategy
            strategy = fallback_manager.get_fallback_strategy(e)

            if strategy == FallbackStrategy.ABORT:
                break

            # Calculate delay for retry
            delay = fallback_manager.calculate_delay(operation_id, e)

            if strategy == FallbackStrategy.RETRY or strategy == FallbackStrategy.WAIT_AND_RETRY:
                logger.info(
                    "Retrying operation %s in %.2f seconds...",
                    operation_id,
                    delay
                )
                time.sleep(delay)
            else:
                # For other strategies, we need to let the caller handle it
                break

    # If we get here, we've exhausted retries or need a different fallback
    if last_error:
        raise last_error

    # Should never get here
    raise RuntimeError(
        f"Unexpected error in retry_operation for {operation_id}")


def with_recovery(
    func: Callable[..., T],
    operation_id: str,
    get_state_func: Callable[..., Dict[str, Any]],
    *args,
    fallback_manager: Optional[FallbackManager] = None,
    **kwargs
) -> T:

    if fallback_manager is None:
        fallback_manager = FallbackManager()

    # Check if we have a recovery point for this operation
    if fallback_manager.has_recovery_point(operation_id):
        recovery_data = fallback_manager.get_recovery_point(operation_id)
        if recovery_data:
            logger.info(
                "Resuming operation %s from recovery point",
                operation_id
            )
            # Update kwargs with recovery data
            kwargs.update(recovery_data)

    try:
        # Capture the state periodically during execution
        current_state = get_state_func(*args, **kwargs)
        fallback_manager.save_recovery_point(operation_id, current_state)

        # Execute the operation
        result = func(*args, **kwargs)

        # Mark recovery as complete and clear the recovery point
        fallback_manager.mark_recovery_complete(operation_id, success=True)
        fallback_manager.clear_recovery_point(operation_id)

        return result

    except Exception as e:
        # Handle the exception, save the state for recovery
        logger.error(
            "Operation %s failed with error: %s",
            operation_id,
            str(e)
        )

        try:
            # Try to capture the state even after failure
            current_state = get_state_func(*args, **kwargs)
            fallback_manager.save_recovery_point(operation_id, current_state)
            fallback_manager.mark_recovery_complete(
                operation_id, success=False)
        except (ValueError, TypeError, AttributeError) as state_error:
            logger.error(
                "Failed to capture state for recovery: %s",
                str(state_error)
            )

        # Re-raise the original exception
        raise


class RetryContext:
    def __init__(self,
                 operation_id: str,
                 max_retries: int = MAX_RETRY_COUNT,
                 base_delay: float = DEFAULT_DELAY,
                 max_delay: float = MAX_DELAY):
        self.operation_id = operation_id
        self.fallback_manager = FallbackManager(
            max_retries, base_delay, max_delay)
        self.current_attempt = 0
        self.error = None
        self.strategy = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            self.current_attempt = self.fallback_manager.increment_retry_count(
                self.operation_id)
            self.strategy = self.fallback_manager.get_fallback_strategy(
                exc_val)

            # Determine if we should suppress the exception and retry
            if self.should_retry():
                delay = self.fallback_manager.calculate_delay(
                    self.operation_id, exc_val)
                logger.info(
                    "Retrying operation %s in %.2f seconds...",
                    self.operation_id,
                    delay
                )
                time.sleep(delay)
                return True  # Suppress the exception

        return False  # Don't suppress the exception

    def should_retry(self):
        # Check if we have retries left and the strategy is retry-compatible
        can_retry = self.fallback_manager.can_retry(self.operation_id)
        is_retry_strategy = (self.strategy == FallbackStrategy.RETRY or
                             self.strategy == FallbackStrategy.WAIT_AND_RETRY)
        return can_retry and is_retry_strategy

    def reset(self):
        self.fallback_manager.reset_retry_count(self.operation_id)
        self.current_attempt = 0
        self.error = None
        self.strategy = None

    @property
    def has_error(self):
        return self.error is not None

    @property
    def retry_count(self):
        return self.fallback_manager.get_retry_count(self.operation_id)


class OperationCheckpoint:
    def __init__(self,
                 operation_id: str,
                 checkpoint_interval: int = 10,
                 save_func: Optional[Callable[[Dict[str, Any]], None]] = None,
                 load_func: Optional[Callable[[], Dict[str, Any]]] = None):
        self.operation_id = operation_id
        self.checkpoint_interval = checkpoint_interval
        self.save_func = save_func
        self.load_func = load_func
        self.fallback_manager = FallbackManager()
        self.item_count = 0

    def checkpoint(self, state: Dict[str, Any]):
        self.item_count += 1

        # Save checkpoint if we've hit the interval
        if self.item_count % self.checkpoint_interval == 0:
            self.fallback_manager.save_recovery_point(self.operation_id, state)

            if self.save_func:
                try:
                    self.save_func(state)
                except (ValueError, TypeError, AttributeError) as e:
                    logger.error("Error saving checkpoint: %s", str(e))

# pylint: disable=missing-function-docstring

    def load_last_checkpoint(self) -> Optional[Dict[str, Any]]:
        # Try loading from the fallback manager first
        state = self.fallback_manager.get_recovery_point(self.operation_id)

        # If not found and we have a load function, try that
        if state is None and self.load_func:
            try:
                state = self.load_func()
            except (ValueError, TypeError, AttributeError) as e:
                logger.error("Error loading checkpoint: %s", str(e))

        return state
# pylint: disable=missing-function-docstring

    def clear_checkpoints(self):
        self.fallback_manager.clear_recovery_point(self.operation_id)
        self.item_count = 0


def switch_account_fallback(retry_func, account_provider, error, *args, **kwargs):
    """Use with error handlers to automatically switch accounts on certain errors"""
    logger.info("Switching account due to error: %s", str(error))

    try:
        # Get next available account from provider
        new_account, account_index = account_provider.get_next_available_account()

        if new_account is None:
            logger.error("No alternative accounts available")
            raise OperationError("No alternative accounts available")

        # Update the account in kwargs
        kwargs['account'] = new_account
        kwargs['account_index'] = account_index

        # Retry with new account
        return retry_func(*args, **kwargs)
    except Exception as e:
        logger.error("Account switch fallback failed: %s", str(e))
        raise


def emergency_shutdown(operation_id: str,
                       state: Dict[str, Any],
                       error: Exception,
                       cleanup_func: Optional[Callable[[], None]] = None):
    """Perform emergency shutdown when unrecoverable errors occur"""
    logger.critical(
        "EMERGENCY SHUTDOWN for operation %s: %s",
        operation_id,
        str(error)
    )

    # Create a fallback manager to store the state
    fallback_manager = FallbackManager()

    try:
        # Save the current state for later recovery
        fallback_manager.save_recovery_point(operation_id, state)
        fallback_manager.mark_recovery_complete(operation_id, success=False)

        # Run cleanup function if provided
        if cleanup_func:
            cleanup_func()

        logger.info(
            "Emergency shutdown completed for %s. Recovery data saved.",
            operation_id
        )
    except (ValueError, TypeError, AttributeError) as e:
        logger.critical("Failed to complete emergency shutdown: %s", str(e))


def get_fallback_manager():
    """Get singleton instance of FallbackManager"""
    return FallbackManager()


def retry_with_fallback_strategies(func, operation_id, fallback_strategies, *args, **kwargs):
    """Retry an operation with multiple fallback strategies in sequence"""
    fallback_manager = FallbackManager()
    last_error = None

    # Try each strategy in sequence
    for strategy in fallback_strategies:
        try:
            # Reset retry count for each strategy
            fallback_manager.reset_retry_count(operation_id)

            if strategy == FallbackStrategy.RETRY:
                return retry_operation(func, operation_id, fallback_manager, *args, **kwargs)
            elif strategy == FallbackStrategy.SWITCH_ACCOUNT:
                # This assumes an account_provider is in kwargs
                return switch_account_fallback(
                    func, kwargs.get('account_provider'), last_error, *args, **kwargs)
            elif strategy == FallbackStrategy.SWITCH_PROXY:
                # Similar to switch_account but for proxies
                # Implementation would depend on proxy manager
                logger.info("Switching proxy and retrying...")
                # TODO: Implement custom proxy switching logic here
            elif strategy == FallbackStrategy.CHECKPOINT:
                # Try to restore from checkpoint
                checkpoint = OperationCheckpoint(operation_id)
                state = checkpoint.load_last_checkpoint()
                if state:
                    logger.info(
                        "Restoring from checkpoint for %s", operation_id)
                    # Update kwargs with checkpoint state
                    kwargs.update(state)
                    return func(*args, **kwargs)
            elif strategy == FallbackStrategy.ABORT:
                logger.warning("Aborting operation %s", operation_id)
                break

        except (ValueError, TypeError, AttributeError) as e:
            last_error = e
            logger.warning("Fallback strategy %s failed: %s", strategy, str(e))

    # If we get here, all strategies failed
    if last_error:
        raise last_error

    # Should never get here
    raise OperationError(f"All fallback strategies failed for {operation_id}")
