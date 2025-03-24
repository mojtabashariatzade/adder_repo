"""
Sequential Strategy Module

This module implements a sequential execution strategy for Telegram account operations.
It processes tasks one account at a time, handling errors and retries, and managing
the state of the operation. This strategy is less aggressive than parallel strategies
and minimizes the risk of rate limits or account blocks.

Features:
- Use one account at a time for adding members
- Switch to next account when limits are reached or errors occur
- Handle different types of errors with appropriate retries or timeouts
- Track operation progress and statistics
- Support for pausing and resuming operations
- Backup state for recovery in case of interruptions
"""

import time
import asyncio
import random
from typing import Optional, Callable
import unittest.mock  # برای MagicMock
from datetime import datetime, timedelta

# Import from base strategy module
# Since this module is not implemented yet, we'll define a mock class
# This should be replaced with actual import once base_strategy.py is implemented
try:
    from strategies.base_strategy import BaseStrategy
except ImportError:
    # Mock BaseStrategy class for development
    class BaseStrategy:
        """Mock BaseStrategy class for development purposes."""

        def __init__(self, **kwargs):
            self.name = "BaseStrategy"
            self.description = "Base class for all strategies"
            self.progress = 0.0
            self.status = "initialized"
            self.config = kwargs

# Import from other modules
from core.constants import (
    DEFAULT_DELAY, MAX_DELAY, MAX_RETRY_COUNT, ACCOUNT_CHANGE_DELAY
)
from core.exceptions import (
    AccountError, APIError, NetworkError,
    StrategyExecutionError
)
from logging_.logging_manager import get_logger
from data.session_manager import SessionManager, SessionStatus

# Get logger
logger = get_logger("SequentialStrategy")


class SequentialStrategy(BaseStrategy):
    """
    Sequential execution strategy for Telegram operations.

    This strategy processes members one by one, using a single account at a time.
    When an account reaches its limits or encounters errors, the strategy switches
    to the next available account. This approach minimizes the risk of triggering
    rate limits or account blocks.
    """

    def __init__(
        self,
        account_manager,
        session_id: Optional[str] = None,
        initial_delay: int = DEFAULT_DELAY,
        max_delay: int = MAX_DELAY,
        account_change_delay: int = ACCOUNT_CHANGE_DELAY,
        max_retry_count: int = MAX_RETRY_COUNT,
        on_progress_callback: Optional[Callable] = None,
        **kwargs
    ):
        """
        Initialize the sequential strategy.

        Args:
            account_manager: Service for managing Telegram accounts
            session_id (str, optional): ID of an existing session to resume
            initial_delay (int): Initial delay between operations in seconds
            max_delay (int): Maximum delay between operations in seconds
            account_change_delay (int): Delay when switching accounts in seconds
            max_retry_count (int): Maximum number of retries for failed operations
            on_progress_callback (callable, optional): Function to call for progress updates
            **kwargs: Additional configuration parameters
        """
        super().__init__(
            name="sequential",
            description="Sequential execution strategy using one account at a time",
            **kwargs
        )

        self.account_manager = account_manager
        self.initial_delay = initial_delay
        self.current_delay = initial_delay
        self.max_delay = max_delay
        self.account_change_delay = account_change_delay
        self.max_retry_count = max_retry_count
        self.on_progress_callback = on_progress_callback

        # Operation state
        self.current_account = None
        self.current_account_index = -1
        self.current_client = None
        self.operation_active = False
        self.session = None
        self.queue = []
        self.processed_items = []
        self.failed_items = []
        self.success_count = 0
        self.retry_count = 0
        self.total_count = 0
        self.error_counts = {}
        self.start_time = None
        self.end_time = None

        # Initialize or retrieve session
        self._init_session(session_id)

    def _init_session(self, session_id: Optional[str] = None):
        """
        Initialize or retrieve a session.

        Args:
            session_id (str, optional): ID of an existing session to resume
        """
        session_manager = SessionManager()

        if session_id:
            # Try to retrieve existing session
            self.session = session_manager.get_session(session_id)
            if self.session:
                logger.info("Resumed session with ID: %s", session_id)

                # Restore state from session
                self._restore_state_from_session()
            else:
                logger.warning(
                    "Session ID %s not found, creating new session", session_id)
                self._create_new_session()
        else:
            # Create new session
            self._create_new_session()

    def _create_new_session(self):
        """Create a new session for this operation."""
        session_manager = SessionManager()
        self.session = session_manager.create_session(
            session_type="sequential_strategy")

        # Initialize session state
        self.session.update_state({
            "strategy": "sequential",
            "initial_delay": self.initial_delay,
            "current_delay": self.current_delay,
            "max_delay": self.max_delay,
            "account_change_delay": self.account_change_delay,
            "max_retry_count": self.max_retry_count,
            "start_time": datetime.now().isoformat(),
            "processed": 0,
            "success_count": 0,
            "total": 0,
            "progress": 0.0,
            "current_account_index": -1,
            "error_counts": {}
        })

        # Set status to created
        self.session.set_status(SessionStatus.CREATED)

        logger.info("Created new session with ID: %s", self.session.session_id)

    def _restore_state_from_session(self):
        """Restore operation state from the session."""
        if self.session:
            state = self.session.state

            # Restore basic settings
            self.current_delay = state.get("current_delay", self.initial_delay)

            # Restore progress information
            self.success_count = state.get("success_count", 0)
            self.total_count = state.get("total", 0)
            self.progress = state.get("progress", 0.0)
            self.current_account_index = state.get("current_account_index", -1)

            # Restore processed and failed items
            self.processed_items = state.get("processed_items", [])
            self.failed_items = state.get("failed_items", [])

            # برای سازگاری با نام‌های متفاوت کلیدها در جلسات قدیمی
            if not self.processed_items and "processed" in state:
                processed_count = state.get("processed", 0)
                logger.info(
                    "Found %d processed items in session but no details. Using count only.",
                    processed_count
                )

            # Restore error counts
            self.error_counts = state.get("error_counts", {})

            # Restore remaining queue if available
            if "queue" in state:
                self.queue = state["queue"]

            # تلاش برای بازیابی تایم استمپ شروع اگر موجود باشد
            start_time_str = state.get("start_time")
            if start_time_str:
                try:
                    self.start_time = datetime.fromisoformat(start_time_str)
                    logger.debug("Restored start time: %s", self.start_time)
                except (ValueError, TypeError):
                    self.start_time = None

            # Set appropriate status for resumed session
            self.session.set_status(SessionStatus.RECOVERED)

            logger.info("Restored state from session %s",
                        self.session.session_id)
            logger.debug(
                "Restored progress: %.1f%%, Success: %d/%d",
                self.progress, self.success_count, self.total_count
            )

    def _save_state_to_session(self):
        """Save current operation state to the session."""
        if self.session:
            # Create state update
            state_update = {
                "current_delay": self.current_delay,
                "success_count": self.success_count,
                "progress": self.progress,
                "current_account_index": self.current_account_index,
                "processed_items": self.processed_items,
                "failed_items": self.failed_items,
                "error_counts": self.error_counts,
                "queue": self.queue,
                "last_updated": datetime.now().isoformat()
            }

            # Update session state
            self.session.update_state(state_update)

            # Set recovery point in case operation is interrupted
            recovery_data = {
                "position": len(self.processed_items),
                "remaining_items": len(self.queue),
                "current_account_index": self.current_account_index,
                "current_delay": self.current_delay
            }
            self.session.set_recovery_point(recovery_data)

            # If using SessionManager directly instead of auto-save:
            # session_manager = SessionManager()
            # session_manager.save_session(self.session)

            logger.debug("Saved operation state to session %s",
                         self.session.session_id)

    async def execute(self, target_group, members, **kwargs):
        """
        Execute the strategy to add members to the target group.

        Args:
            target_group: Target Telegram group entity
            members (list): List of members to add
            **kwargs: Additional execution parameters

        Returns:
            dict: Execution results and statistics
        """
        if self.operation_active:
            logger.warning(
                "Operation already active, cannot start another execution")
            raise StrategyExecutionError("Operation already active")

        try:
            self.operation_active = True
            self.start_time = datetime.now()

            # Initialize the queue if it's empty (new execution)
            if not self.queue:
                self.queue = list(members)
                self.total_count = len(members)

                # Update session with total count
                if self.session:
                    self.session.update_state({
                        "total": self.total_count,
                        "queue_initialized": True
                    })

            # Set status to running
            if self.session:
                self.session.set_status(SessionStatus.RUNNING)

            # Log start of operation
            logger.info(
                "Starting sequential execution with %d members to process", len(self.queue))

            # Process the queue
            result = await self._process_queue(target_group, **kwargs)

            # Finalize operation
            self.end_time = datetime.now()
            self._finalize_operation(result)

            return result

        except Exception as e:
            logger.error("Error during sequential execution: %s", e)

            # Log error to session
            if self.session:
                self.session.log_error(
                    error_message=f"Execution error: {str(e)}",
                    exception=e
                )
                self.session.set_status(SessionStatus.INTERRUPTED)

            # Save current state for potential recovery
            self._save_state_to_session()

            # Raise as StrategyExecutionError
            raise StrategyExecutionError(f"Execution failed: {str(e)}") from e

        finally:
            # Clean up resources
            if self.current_client and hasattr(self.current_client, 'disconnect'):
                try:
                    await self.current_client.disconnect()
                except (ValueError, TypeError, StopIteration):
                    pass

            self.operation_active = False

    async def _process_queue(self, target_group, **kwargs):
        """
        Process the queue of members to add.

        Args:
            target_group: Target Telegram group entity
            **kwargs: Additional processing parameters
                - jitter_factor (float): Factor to control randomness in delays (0-1)
                - max_consecutive_errors (int): Maximum consecutive errors before pausing
                - max_consecutive_account_switches (int): Maximum consecutive account switches
                - batch_size (int): Number of members to process before saving state

        Returns:
            dict: Processing results and statistics
        """
        # Initialize results
        results = {
            "success_count": 0,
            "failure_count": 0,
            "total_count": self.total_count,
            "elapsed_time": 0,
            "errors": {},
            "account_stats": {}
        }

        last_progress_update = time.time()
        progress_update_interval = 2.0  # seconds between progress updates

        # Additional control parameters
        max_consecutive_errors = kwargs.get('max_consecutive_errors', 5)
        max_consecutive_account_switches = kwargs.get(
            'max_consecutive_account_switches', 3)
        batch_size = kwargs.get('batch_size', 10)

        # Tracking variables
        consecutive_errors = 0
        consecutive_account_switches = 0
        last_state_save = time.time()
        state_save_interval = 60.0  # seconds between forced state saves

        # Process until queue is empty
        while self.queue:
            # Get next member from queue
            item = self.queue[0]
            member_id, member_info = item if isinstance(
                item, tuple) else (item, "No info")

            # Log progress
            processed = len(self.processed_items)
            remaining = len(self.queue)
            self.progress = (processed / self.total_count) * \
                100 if self.total_count > 0 else 0

            # Send progress updates at intervals
            current_time = time.time()
            if current_time - last_progress_update >= progress_update_interval:
                self._update_progress()
                last_progress_update = current_time

            # Get an active account if we don't have one
            if self.current_client is None:
                client, account_index = await self._get_next_account()

                if client is None:
                    # If no accounts are available, log the error and pause
                    logger.error("No available accounts. Operation paused.")

                    if self.session:
                        self.session.log_event(
                            "No available accounts, operation paused")
                        self.session.set_status(SessionStatus.PAUSED)

                    # Save state for future resume
                    self._save_state_to_session()

                    return {
                        **results,
                        "status": "paused",
                        "reason": "no_accounts_available",
                        "elapsed_time": (datetime.now() - self.start_time).total_seconds()
                    }

                self.current_client = client
                self.current_account_index = account_index

                # Log account switch
                logger.info("Switched to account %s",
                            self.current_account_index)

                # Update session state
                if self.session:
                    self.session.update_state({
                        "current_account_index": self.current_account_index
                    })
                    self.session.log_event(
                        f"Switched to account {self.current_account_index}")

            # Try to add the member
            try:
                logger.info("Adding member %s (%s) to group",
                            member_id, member_info)

                # Call account manager to add the member
                # This would be something like:
                # success = await self.account_manager.add_to_group(
                #     self.current_client,
                #     member_id,
                #     target_group,
                #     delay=self.current_delay
                # )

                # For development, simulate the add operation
                success, new_delay = await self._simulate_add_member(
                    self.current_client,
                    member_id,
                    target_group,
                    self.current_account_index,
                    retry_count=self.retry_count
                )

                # Update delay if needed
                if new_delay != self.current_delay:
                    logger.info("Adjusting delay from %ds to %ds",
                                self.current_delay, new_delay)
                    self.current_delay = new_delay

                # Process result
                if success:
                    # Member added successfully
                    logger.info("Successfully added member %s", member_id)

                    # Pop the member from the queue and add to processed items
                    self.queue.pop(0)
                    self.processed_items.append(item)
                    self.success_count += 1
                    results["success_count"] += 1

                    # Update account stats
                    account_id = str(self.current_account_index)
                    if account_id not in results["account_stats"]:
                        results["account_stats"][account_id] = {
                            "success": 0, "failure": 0}
                    results["account_stats"][account_id]["success"] += 1

                    # Reset retry count
                    self.retry_count = 0

                    # Save state periodically (every batch_size successful operations)
                    if self.success_count % batch_size == 0:
                        self._save_state_to_session()

                    # Reset consecutive errors counter on success
                    consecutive_errors = 0
                else:
                    # Failed to add member
                    self.retry_count += 1

                    # If max retries exceeded, mark as permanent failure
                    if self.retry_count >= self.max_retry_count:
                        logger.warning(
                            "Max retries (%d) exceeded for member %s, skipping to next member",
                            self.max_retry_count, member_id
                        )

                        # Pop the member from the queue and add to failed items
                        self.queue.pop(0)
                        self.failed_items.append(item)
                        results["failure_count"] += 1

                        # Log to session
                        if self.session:
                            self.session.log_event(
                                f"Permanently failed to add member {
                                    member_id} after {self.max_retry_count} retries"
                            )

                        # Update account stats
                        account_id = str(self.current_account_index)
                        if account_id not in results["account_stats"]:
                            results["account_stats"][account_id] = {
                                "success": 0, "failure": 0}
                        results["account_stats"][account_id]["failure"] += 1

                        # Reset retry count for next member
                        self.retry_count = 0
                    else:
                        # Will retry with current member
                        logger.info(
                            "Failed to add member %s, will retry (attempt %d of %d)",
                            member_id, self.retry_count, self.max_retry_count
                        )

                        # Take a short break before retry
                        await asyncio.sleep(self.current_delay)

                # Check account status - may need to switch accounts
                account_status = await self._check_account_status(self.current_account_index)

                if account_status != "active":
                    logger.info(
                        "Account %s status changed to %s, switching accounts",
                        self.current_account_index, account_status
                    )

                    # Disconnect current client
                    if self.current_client:
                        try:
                            await self.current_client.disconnect()
                        except:
                            pass

                    self.current_client = None

                    # Increment account switch counter
                    consecutive_account_switches += 1

                    # Check if we've switched accounts too many times in a row
                    if consecutive_account_switches >= max_consecutive_account_switches:
                        logger.warning(
                            "Too many consecutive account switches (%d)."
                            "Pausing operation for extended period.",
                            consecutive_account_switches
                        )
                        # Log to session
                        if self.session:
                            self.session.log_event(
                                f"Pausing due to {
                                    consecutive_account_switches} consecutive account switches"
                            )

                        # Take an extended break
                        await asyncio.sleep(self.account_change_delay * 3)
                        consecutive_account_switches = 0
                    else:
                        # Take a break before switching accounts
                        await asyncio.sleep(self.account_change_delay)

                # Take a short break between operations
                # 10% jitter up to 5 seconds max
                jitter = min(5, self.current_delay * 0.1)
                wait_time = self.current_delay + \
                    (jitter * (2 * (0.5 - kwargs.get("jitter_factor", 0.5))))
                await asyncio.sleep(wait_time)

                # Reset consecutive account switches counter after successful operation
                consecutive_account_switches = 0

                # Forced state save if it's been a while
                current_time = time.time()
                if current_time - last_state_save >= state_save_interval:
                    self._save_state_to_session()
                    last_state_save = current_time

            except Exception as e:
                # Handle unexpected errors
                logger.error("Error processing member %s: %s", member_id, e)

                # Track error counts
                error_type = type(e).__name__
                self.error_counts[error_type] = self.error_counts.get(
                    error_type, 0) + 1
                results["errors"][error_type] = results["errors"].get(
                    error_type, 0) + 1

                # Log to session
                if self.session:
                    self.session.log_error(
                        error_message=f"Error processing member {member_id}",
                        error_type=error_type,
                        exception=e
                    )

                # Handle different error types
                if self._is_account_error(e):
                    # If it's an account-related issue, switch accounts
                    logger.warning(
                        "Account error detected: %s, switching accounts", e)

                    # Disconnect current client
                    if self.current_client:
                        try:
                            await self.current_client.disconnect()
                        except:
                            pass

                    self.current_client = None

                    # Take a break before switching accounts
                    await asyncio.sleep(self.account_change_delay)

                elif self._is_network_error(e):
                    # For network errors, wait a bit and retry
                    logger.warning(
                        "Network error detected: %s, waiting before retry", e)
                    await asyncio.sleep(30)  # Longer wait for network issues

                elif self._is_api_error(e):
                    # For API errors, increase delay and continue
                    new_delay = min(self.current_delay * 2, self.max_delay)
                    logger.warning(
                        "API error detected: %s, increasing delay to %d", e, new_delay)
                    self.current_delay = new_delay
                    await asyncio.sleep(new_delay)
                else:
                    # For other errors, add short delay and continue
                    logger.warning(
                        "Unexpected error: %s, continuing with short delay", e)
                    await asyncio.sleep(10)

                # Increment consecutive error counter
                consecutive_errors += 1

                # Check if we've had too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(
                        "Too many consecutive errors (%d). Pausing operation.", consecutive_errors)

                    # Log to session
                    if self.session:
                        self.session.log_event(
                            f"Pausing due to {consecutive_errors} consecutive errors")
                        self.session.set_status(SessionStatus.PAUSED)

                    # Save state for future resume
                    self._save_state_to_session()

                    return {
                        **results,
                        "status": "paused",
                        "reason": "too_many_consecutive_errors",
                        "elapsed_time": (datetime.now() - self.start_time).total_seconds()
                    }

        # Queue is empty, operation completed
        logger.info("Queue processing completed")

        # Calculate final statistics
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        results["elapsed_time"] = elapsed_time
        results["speed"] = self.success_count / \
            elapsed_time if elapsed_time > 0 else 0
        results["status"] = "completed"

        return results

    async def _get_next_account(self):
        """
        Get the next available account.

        Returns:
            tuple: (client, account_index) or (None, -1) if no accounts available
        """
        # This is a mock implementation
        # In the actual implementation, this would call account_manager to get the next account
        account, account_index = await self._simulate_get_account()

        if account is None:
            return None, -1

        # Connect to the account
        client = await self._simulate_connect_account(account_index)

        # If connection failed
        if client is None:
            # Log the failure
            logger.error("Failed to connect to account %s", account_index)

            # Try next account recursively
            return await self._get_next_account()

        return client, account_index

    async def _check_account_status(self, account_index):
        """
        Check the status of an account.

        Args:
            account_index (int): Index of the account to check

        Returns:
            str: Account status (active, cooldown, blocked, etc.)
        """
        # This is a mock implementation
        # In the actual implementation, this would call account_manager
        return "active"

    def _is_account_error(self, error):
        """
        Check if an error is account-related.

        Args:
            error (Exception): Error to check

        Returns:
            bool: True if the error is account-related, False otherwise
        """
        return isinstance(error, AccountError)

    def _is_network_error(self, error):
        """
        Check if an error is network-related.

        Args:
            error (Exception): Error to check

        Returns:
            bool: True if the error is network-related, False otherwise
        """
        return isinstance(error, NetworkError)

    def _is_api_error(self, error):
        """
        Check if an error is API-related.

        Args:
            error (Exception): Error to check

        Returns:
            bool: True if the error is API-related, False otherwise
        """
        return isinstance(error, APIError)

    def _update_progress(self):
        """Update and report progress."""
        # Calculate progress
        processed = len(self.processed_items)
        remaining = len(self.queue)
        total = processed + remaining

        self.progress = (processed / total) * 100 if total > 0 else 0

        # Calculate time statistics
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()

            # Estimate remaining time
            if processed > 0 and remaining > 0:
                time_per_item = elapsed / processed
                estimated_remaining = time_per_item * remaining
                eta = datetime.now() + timedelta(seconds=estimated_remaining)
            else:
                estimated_remaining = 0
                eta = None
        else:
            elapsed = 0
            estimated_remaining = 0
            eta = None

        # Create progress data
        progress_data = {
            "processed": processed,
            "remaining": remaining,
            "total": total,
            "success_count": self.success_count,
            "failure_count": len(self.failed_items),
            "progress": self.progress,
            "elapsed_time": elapsed,
            "estimated_remaining": estimated_remaining,
            "eta": eta.isoformat() if eta else None,
            "current_account": self.current_account_index,
            "current_delay": self.current_delay,
            "retry_count": self.retry_count,
            "speed": self.success_count / elapsed if elapsed > 0 else 0
        }

        # Log progress
        logger.info(
            "Progress: %.1f%% (%d/%d) - Success: %d - Account: %s - Delay: %ds",
            self.progress, processed, total, self.success_count,
            self.current_account_index, self.current_delay
        )

        # Update session state
        if self.session:
            self.session.update_state({
                "processed": processed,
                "success_count": self.success_count,
                "progress": self.progress,
                "current_delay": self.current_delay
            })

        # Call progress callback if provided
        if self.on_progress_callback:
            try:
                self.on_progress_callback(progress_data)
            except Exception as e:
                logger.error("Error in progress callback: %s", e)

    def _finalize_operation(self, result):
        """
        Finalize the operation and save final state.

        Args:
            result (dict): Operation results
        """
        # Update session with final results
        if self.session:
            # Update state with final statistics
            self.session.update_state({
                "completed_at": datetime.now().isoformat(),
                "elapsed_time": result["elapsed_time"],
                "final_success_count": result["success_count"],
                "final_failure_count": result["failure_count"],
                "speed": result["speed"] if "speed" in result else 0,
                "status": result["status"] if "status" in result else "unknown"
            })

            # Set final status
            if result.get("status") == "completed":
                self.session.set_status(SessionStatus.COMPLETED)
            elif result.get("status") == "paused":
                self.session.set_status(SessionStatus.PAUSED)
            else:
                self.session.set_status(SessionStatus.FAILED)

            # Log completion event
            self.session.log_event(
                f"Operation {result.get('status', 'completed')} with "
                f"{result['success_count']} successes and {result['failure_count']} failures"
            )

            # Clear recovery point
            self.session.clear_recovery_point()

        # Log completion
        logger.info(
            "Operation finalized with status '%s'. Added %d out of %d members.",
            result.get('status', 'completed'),
            result['success_count'],
            result['total_count']
        )

    async def pause(self):
        """
        Pause the current operation.

        Returns:
            bool: True if paused successfully, False otherwise
        """
        if not self.operation_active:
            logger.warning("Cannot pause: no active operation")
            return False

        logger.info("Pausing operation...")

        # Set status in session
        if self.session:
            self.session.set_status(SessionStatus.PAUSED)
            self.session.log_event("Operation paused by user")

        # Save current state
        self._save_state_to_session()

        # Note: The actual pausing is handled externally by stopping the execute() call
        # and later resuming using the saved session state

        return True

    async def resume(self, target_group):
        """
        Resume a previously paused operation.

        Args:
            target_group: Target Telegram group entity

        Returns:
            dict: Execution results and statistics
        """
        if self.operation_active:
            logger.warning("Cannot resume: operation already active")
            return {"status": "failed", "reason": "operation_already_active"}

        if not self.session:
            logger.error("Cannot resume: no session available")
            return {"status": "failed", "reason": "no_session"}

        logger.info(
            "Resuming operation from session %s",
            self.session.session_id
        )

        # Set status to running
        self.session.set_status(SessionStatus.RUNNING)
        self.session.log_event("Operation resumed")

        # Execute the operation with current queue
        # Empty list since queue is already loaded
        return await self.execute(target_group, [])

    async def stop(self):
        """
        Stop the current operation completely.

        Unlike pause, this indicates the operation is complete and won't be resumed.

        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.operation_active:
            logger.warning("Cannot stop: no active operation")
            return False

        logger.info("Stopping operation...")

        # Update session status to completed (or failed depending on context)
        if self.session:
            self.session.set_status(SessionStatus.COMPLETED)
            self.session.log_event("Operation stopped by user")

            # Calculate and update final statistics
            processed = len(self.processed_items)
            total = processed + len(self.queue)
            self.session.update_state({
                "completed_at": datetime.now().isoformat(),
                "final_success_count": self.success_count,
                "final_failure_count": len(self.failed_items),
                "early_termination": True,
                "remaining_queue_size": len(self.queue),
                "completion_percentage": (processed / total) * 100 if total > 0 else 0
            })

            # Clear recovery point since this is a complete stop
            self.session.clear_recovery_point()

        # Cleanup resources
        if self.current_client and hasattr(self.current_client, 'disconnect'):
            try:
                await self.current_client.disconnect()
            except:
                pass

        self.current_client = None
        self.operation_active = False

        logger.info(
            "Operation stopped. Processed %d items with %d successes.",
            len(self.processed_items),
            self.success_count
        )
        return True

    # The following methods are for development and testing
    # They simulate interactions with the account_manager and Telegram API
    # Should be replaced with actual implementations in production

    async def _simulate_get_account(self):
        """Simulate getting the next available account."""
        # In production, this would call account_manager.get_next_available_account()
        # For development, return a mock account
        account = {"phone": "+1234567890", "status": "active"}
        return account, 0  # Mock account index 0

    async def _simulate_connect_account(self, account_index):
        """Simulate connecting to an account."""
        # In production, this would call account_manager.connect_account(account_index)
        # For development, return a mock client
        return MagicMock()  # Mock Telegram client

    async def _simulate_add_member(
            self, client, member_id, target_group, account_index, retry_count=0):
        """Simulate adding a member to a group."""
        # In production, this would call the Telegram API to add a member
        # For development, simulate success/failure based on probability

        # Higher success rate on later retries
        success_probability = 0.8 + (retry_count * 0.05)

        # Simulate random delays
        new_delay = min(self.current_delay *
                        random.uniform(0.8, 1.2), self.max_delay)

        # Simulate API call
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # Determine result
        success = random.random() < success_probability

        return success, new_delay


# Mock class for testing
class MagicMock(unittest.mock.MagicMock):
    """Mock class for simulating Telegram client in tests.

    Extends unittest.mock.MagicMock to support async methods.
    """

    async def disconnect(self):
        """Simulate disconnecting from Telegram."""
        pass

    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
