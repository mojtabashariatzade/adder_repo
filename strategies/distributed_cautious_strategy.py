"""
Distributed Cautious Strategy Module

This module implements a distributed cautious strategy for adding members to Telegram groups.
It's designed to work 24/7 and distribute the load across multiple accounts while maintaining
a cautious approach to avoid account restrictions.

Features:
- Distributes operations evenly across the available time period
- Uses multiple accounts simultaneously but with controlled parallelism
- Implements variable delays between operations
- Automatically switches to other accounts if one encounters issues
- Adapts operation speed based on success/failure rates
- Supports 24/7 operation with intelligent scheduling
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
import threading

from strategies.base_strategy import BaseStrategy
from strategies.parallel_strategies import ParallelLowStrategy
from core.exceptions import (
    AccountNotFoundError,
    AccountLimitReachedError,
    AccountBlockedError,
    AccountInCooldownError,
    FloodWaitError,
    PeerFloodError,
    OperationError,
    TelegramAdderError
)
from core.constants import Constants
from models.account import AccountStatus
from services.account_manager import AccountManager
from logging_.logging_manager import get_logger

# Setup logger
logger = get_logger("DistributedCautiousStrategy")


class AccountGroup:
    """
    Represents a group of accounts that will be used together in a time slot.

    This class manages a group of accounts that are scheduled to work during specific time periods.
    It tracks account usage, rotates accounts, and provides status information for the group.
    """

    def __init__(self, accounts: List[Dict[str, Any]], group_id: str, max_parallel: int = 2):
        """
        Initialize an account group.

        Args:
            accounts: List of account dictionaries to include in this group
            group_id: Unique identifier for this group
            max_parallel: Maximum number of accounts to use in parallel from this group
        """
        self.accounts = accounts
        self.group_id = group_id
        self.max_parallel = max_parallel
        self.active_accounts = []
        self.last_active_time = None
        self.scheduled_periods = []
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0

    def get_available_accounts(self, count: int = None) -> List[Dict[str, Any]]:
        """
        Get available accounts from this group.

        Args:
            count: Number of accounts to return, defaults to max_parallel if None

        Returns:
            List of available account dictionaries
        """
        if count is None:
            count = self.max_parallel

        # Filter for active accounts
        available = [acc for acc in self.accounts
                     if acc.get("status") == AccountStatus.to_str(AccountStatus.ACTIVE)
                     and not self._is_daily_limit_reached(acc)]

        # Sort by least recently used
        available.sort(key=lambda a: a.get(
            "last_used", "1970-01-01T00:00:00") or "1970-01-01T00:00:00")

        return available[:count]

    def _is_daily_limit_reached(self, account: Dict[str, Any]) -> bool:
        """Check if an account has reached its daily limit."""
        # Check daily usage
        daily_usage = account.get("daily_usage", {})
        if not isinstance(daily_usage, dict):
            return False

        # Check if it's a new day
        today = datetime.now().strftime("%Y-%m-%d")
        if daily_usage.get("date") != today:
            return False

        # Check current count against limit
        current_count = daily_usage.get("count", 0)
        max_per_day = Constants.Limits.MAX_MEMBERS_PER_DAY

        return current_count >= max_per_day

    def record_operation(self, success: bool) -> None:
        """
        Record an operation result for this group.

        Args:
            success: Whether the operation was successful
        """
        self.total_operations += 1
        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1

    def get_success_rate(self) -> float:
        """
        Get the success rate for operations in this group.

        Returns:
            Success rate as a percentage or 100 if no operations
        """
        if self.total_operations == 0:
            return 100.0

        return (self.successful_operations / self.total_operations) * 100

    def schedule_period(self, start_time: datetime, end_time: datetime) -> bool:
        """
        Schedule this group for a specific time period.

        Args:
            start_time: When this group should start working
            end_time: When this group should stop working

        Returns:
            True if scheduling was successful, False if there's a conflict
        """
        # Check for conflicts with existing periods
        for period_start, period_end in self.scheduled_periods:
            # Check if the new period overlaps with any existing period
            if (start_time <= period_end and end_time >= period_start):
                return False

        # No conflicts, add the period
        self.scheduled_periods.append((start_time, end_time))
        return True

    def is_active_now(self) -> bool:
        """
        Check if this group is scheduled to be active right now.

        Returns:
            True if the group should be active now
        """
        now = datetime.now()

        for start_time, end_time in self.scheduled_periods:
            if start_time <= now <= end_time:
                return True

        return False

    def __str__(self) -> str:
        """String representation of the account group."""
        active_count = len(self.get_available_accounts())
        return f"AccountGroup(id={self.group_id}, accounts={len(self.accounts)}, active={active_count})"


class DistributedCautiousStrategy(BaseStrategy):
    """
    A distributed cautious strategy for adding members to Telegram groups.

    This strategy distributes the member addition operations over time using multiple
    account groups, with careful management of operation timing and account rotation
    to minimize the risk of account restrictions.
    """

    def __init__(self, **kwargs):
        """
        Initialize the distributed cautious strategy.

        Args:
            **kwargs: Additional parameters for strategy configuration
        """
        super().__init__(**kwargs)

        # Strategy parameters with defaults
        self.max_parallel_accounts = kwargs.get("max_parallel_accounts", 2)
        self.accounts_per_group = kwargs.get("accounts_per_group", 10)
        self.group_activity_hours = kwargs.get("group_activity_hours", 4)
        self.min_delay = kwargs.get("min_delay", 12)
        self.max_delay = kwargs.get("max_delay", 30)
        self.target_hourly_rate = kwargs.get("target_hourly_rate", 80)
        self.operation_hours = kwargs.get(
            "operation_hours", 24)  # 24/7 operation
        self.adaptive_delays = kwargs.get("adaptive_delays", True)

        # Runtime state
        self.account_groups = []
        self.active_groups = []
        self.current_accounts = []
        self.processed_members = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.operation_active = False
        self._stop_event = threading.Event()
        self._activity_thread = None

        # Get account manager from kwargs or create a new one
        self.account_manager = kwargs.get("account_manager", AccountManager())

        # Set up schedule for 24/7 operation
        self.time_slots = self._create_time_slots()

    async def execute(self, source_group, target_group, member_limit, progress_callback=None, **kwargs):
        """
        Execute the member transfer operation using the distributed cautious strategy.

        Args:
            source_group: Group to extract members from
            target_group: Group to add members to
            member_limit: Maximum number of members to transfer
            progress_callback: Function to call with progress updates
            **kwargs: Additional parameters

        Returns:
            Dict with operation results
        """
        self.source_group = source_group
        self.target_group = target_group
        self.member_limit = member_limit
        self.progress_callback = progress_callback

        # Initialize account groups
        self._initialize_account_groups()

        # Set up the operation state
        self.operation_active = True
        self.processed_members = 0
        self.successful_operations = 0
        self.failed_operations = 0

        # Create and start monitoring thread
        self._activity_thread = threading.Thread(
            target=self._activity_monitor_worker,
            daemon=True
        )
        self._activity_thread.start()

        # Create result dict to be updated throughout the operation
        result = {
            "start_time": datetime.now(),
            "processed": 0,
            "success_count": 0,
            "failure_count": 0,
            "completion_time": 0,
            "status": "running"
        }

        try:
            # Extract members from source group
            members = await self._extract_members(self.source_group, self.member_limit)

            if not members:
                logger.error("Failed to extract members from source group")
                raise OperationError(
                    "Failed to extract members from source group")

            total_members = len(members)
            logger.info(f"Extracted {total_members} members from source group")

            # Start processing members
            start_time = time.time()

            # Process members until limit is reached or all are processed
            for i, member in enumerate(members):
                if self.processed_members >= self.member_limit:
                    logger.info(f"Reached member limit of {self.member_limit}")
                    break

                if not self.operation_active:
                    logger.info("Operation stopped")
                    break

                # Update progress
                if progress_callback:
                    progress_callback({
                        "processed": self.processed_members,
                        "success_count": self.successful_operations,
                        "failure_count": self.failed_operations,
                        "current_member": i,
                        "total_members": total_members
                    })

                # Process this member
                success = await self._process_member(member)

                # Record the result
                if success:
                    self.successful_operations += 1
                else:
                    self.failed_operations += 1

                self.processed_members += 1

                # Update result dict
                result["processed"] = self.processed_members
                result["success_count"] = self.successful_operations
                result["failure_count"] = self.failed_operations

                # Check if we should stop
                if self._stop_event.is_set():
                    logger.info("Operation stopped by request")
                    break

            # Finalize the result
            end_time = time.time()
            result["completion_time"] = end_time - start_time
            result["status"] = "completed"

            # Clean up
            self.operation_active = False
            if self._activity_thread and self._activity_thread.is_alive():
                self._stop_event.set()
                self._activity_thread.join(timeout=2.0)

            logger.info(f"Operation completed: processed {self.processed_members} members, "
                        f"success: {self.successful_operations}, failures: {self.failed_operations}")

            return result

        except Exception as e:
            logger.error(f"Error in distribute cautious strategy: {e}")
            self.operation_active = False
            if self._activity_thread and self._activity_thread.is_alive():
                self._stop_event.set()
                self._activity_thread.join(timeout=2.0)

            # Update result with error info
            result["status"] = "failed"
            result["error"] = str(e)

            raise

    async def resume(self, session, progress_callback=None):
        """
        Resume an interrupted operation.

        Args:
            session: Session object containing the interrupted operation state
            progress_callback: Function to call with progress updates

        Returns:
            Dict with operation results
        """
        # Load state from session
        state = session.state
        self.processed_members = state.get("processed", 0)
        self.successful_operations = state.get("success_count", 0)
        self.failed_operations = state.get("failure_count", 0)

        # Get source and target groups from session
        source_group_data = session.get_custom_data("source_group", {})
        target_group_data = session.get_custom_data("target_group", {})

        # Check if we have the necessary data
        if not source_group_data or not target_group_data:
            raise OperationError(
                "Missing source or target group data in session")

        # Get member limit from session
        member_limit = state.get("total", 1000)

        # Execute the operation
        return await self.execute(
            source_group=source_group_data,
            target_group=target_group_data,
            member_limit=member_limit,
            progress_callback=progress_callback,
            resumed=True,
            session=session
        )

    async def _extract_members(self, source_group, limit):
        """
        Extract members from the source group.

        Args:
            source_group: Group to extract members from
            limit: Maximum number of members to extract

        Returns:
            List of members
        """
        logger.info(f"Extracting up to {limit} members from source group")

        # Get active accounts for extraction
        active_accounts = self._get_active_accounts(2)
        if not active_accounts:
            raise OperationError(
                "No active accounts available for member extraction")

        # Use the first available account to extract members
        account = active_accounts[0]

        try:
            # Initialize the client and connect
            client = await self._get_client(account)

            # Get members
            participants = await client.get_participants(source_group, limit=limit)

            # Filter out bots, empty users, etc.
            valid_members = [
                member for member in participants
                if not member.bot and not member.deleted and not member.fake
            ]

            logger.info(
                f"Extracted {len(valid_members)} valid members from source group")

            # Disconnect client
            await client.disconnect()

            return valid_members

        except Exception as e:
            logger.error(f"Error extracting members: {e}")
            raise OperationError(f"Failed to extract members: {e}")

    async def _process_member(self, member):
        """
        Process a single member (add to target group).

        Args:
            member: Member to add to target group

        Returns:
            bool: True if successful, False otherwise
        """
        # Get an active account
        account = self._get_next_account()
        if not account:
            logger.warning("No active accounts available for adding member")
            return False

        # Calculate adaptive delay
        delay = self._calculate_adaptive_delay()

        try:
            # Add the member
            client = await self._get_client(account)

            # Try to add member to target group
            result = await client.add_contact(member)

            # Disconnect client
            await client.disconnect()

            # Apply delay after operation
            await asyncio.sleep(delay)

            # Record successful usage
            self.account_manager.record_usage(account["phone"], 1)

            # Update account groups
            for group in self.account_groups:
                if account in group.accounts:
                    group.record_operation(True)

            return True

        except (FloodWaitError, PeerFloodError) as e:
            logger.warning(f"Account {account['phone']} hit rate limit: {e}")

            # Update account status
            if isinstance(e, PeerFloodError):
                self.account_manager.update_account_status(
                    account["phone"], AccountStatus.COOLDOWN)

            # Apply a longer delay after error
            await asyncio.sleep(delay * 2)

            # Update account groups
            for group in self.account_groups:
                if account in group.accounts:
                    group.record_operation(False)

            return False

        except TelegramAdderError as e:
            logger.error(
                f"Error adding member with account {account['phone']}: {e}")

            # Record failure
            self.account_manager.record_failure(account["phone"])

            # Apply delay after error
            await asyncio.sleep(delay)

            # Update account groups
            for group in self.account_groups:
                if account in group.accounts:
                    group.record_operation(False)

            return False

    def _initialize_account_groups(self):
        """Initialize account groups from available accounts."""
        # Get all accounts
        accounts = self.account_manager.get_all_accounts()

        # Clear existing groups
        self.account_groups = []

        # Group accounts
        for i in range(0, len(accounts), self.accounts_per_group):
            group_accounts = accounts[i:i+self.accounts_per_group]
            group_id = f"group_{i//self.accounts_per_group}"

            group = AccountGroup(
                accounts=group_accounts,
                group_id=group_id,
                max_parallel=self.max_parallel_accounts
            )

            self.account_groups.append(group)

        # Schedule the groups across time slots
        self._schedule_groups()

        logger.info(f"Initialized {len(self.account_groups)} account groups")

    def _schedule_groups(self):
        """Schedule account groups into time slots for 24/7 operation."""
        if not self.account_groups:
            return

        # Get the current time as reference point
        now = datetime.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Assign groups to time slots
        for i, group in enumerate(self.account_groups):
            # Calculate the time slot for this group
            slot_index = i % len(self.time_slots)
            slot_hours = self.time_slots[slot_index]

            # Create start and end times
            start_time = day_start + timedelta(hours=slot_hours[0])
            end_time = day_start + timedelta(hours=slot_hours[1])

            # If end time is earlier than start time, it spans across midnight
            if end_time < start_time:
                end_time += timedelta(days=1)

            # Adjust if the calculated times are in the past
            while end_time < now:
                start_time += timedelta(days=1)
                end_time += timedelta(days=1)

            # Schedule the group for this time slot
            group.schedule_period(start_time, end_time)

        logger.info("Scheduled account groups across time slots")

    def _create_time_slots(self):
        """
        Create time slots for 24/7 operation.

        Returns:
            List of tuples with start and end hours
        """
        # For 24/7 operation with 6 time slots (4 hours each)
        return [
            (0, 4),    # 12am - 4am
            (4, 8),    # 4am - 8am
            (8, 12),   # 8am - 12pm
            (12, 16),  # 12pm - 4pm
            (16, 20),  # 4pm - 8pm
            (20, 24)   # 8pm - 12am
        ]

    def _get_active_accounts(self, count=1):
        """
        Get active accounts from active groups.

        Args:
            count: Number of accounts to return

        Returns:
            List of active account dictionaries
        """
        # Update the list of active groups
        self._update_active_groups()

        # No active groups
        if not self.active_groups:
            return []

        # Collect accounts from all active groups
        available_accounts = []
        for group in self.active_groups:
            available_accounts.extend(group.get_available_accounts())

        # Return requested number of accounts
        return available_accounts[:count]

    def _get_next_account(self):
        """
        Get the next account to use for operations.

        Returns:
            Account dictionary or None if no accounts available
        """
        # Check if we have current accounts
        if not self.current_accounts:
            # Try to get more accounts
            self.current_accounts = self._get_active_accounts(
                self.max_parallel_accounts)

        if not self.current_accounts:
            return None

        # Get next account and rotate the list
        account = self.current_accounts[0]
        self.current_accounts = self.current_accounts[1:] + [account]

        return account

    def _update_active_groups(self):
        """Update the list of groups that are active right now."""
        self.active_groups = [
            group for group in self.account_groups
            if group.is_active_now()
        ]

    def _calculate_adaptive_delay(self):
        """
        Calculate an adaptive delay based on current conditions.

        Returns:
            Delay time in seconds
        """
        if not self.adaptive_delays:
            # Use random delay within range if adaptive delays are disabled
            return random.uniform(self.min_delay, self.max_delay)

        # Base delay from configured range
        base_delay = random.uniform(self.min_delay, self.max_delay)

        # Adjust based on time of day - increase during peak hours
        hour = datetime.now().hour
        time_factor = 1.0

        # Peak hours are typically evenings (higher factor means longer delay)
        if 17 <= hour <= 23:  # 5pm - 11pm
            time_factor = 1.3
        elif 0 <= hour <= 4:  # 12am - 4am
            time_factor = 0.8  # Less delay during night hours

        # Adjust based on recent success rate
        success_factor = 1.0
        if self.processed_members > 0:
            success_rate = (self.successful_operations /
                            self.processed_members) * 100

            # Increase delay if success rate is low
            if success_rate < 70:
                success_factor = 1.5
            elif success_rate < 85:
                success_factor = 1.2
            elif success_rate > 95:
                success_factor = 0.9  # Slightly decrease if things are going well

        # Combine factors
        adjusted_delay = base_delay * time_factor * success_factor

        # Add small random variation (±10%)
        final_delay = adjusted_delay * random.uniform(0.9, 1.1)

        return final_delay

    async def _get_client(self, account):
        """
        Initialize and connect a client for the given account.

        Args:
            account: Account dictionary

        Returns:
            Connected client
        """
        # Import Telethon here to avoid circular imports
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        api_id = account.get("api_id")
        api_hash = account.get("api_hash")
        session_string = account.get("session_string")

        if not all([api_id, api_hash, session_string]):
            raise ValueError("Missing account credentials")

        # Initialize client with session
        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash
        )

        # Connect to Telegram
        await client.connect()

        # Verify authorization
        if not await client.is_user_authorized():
            raise ValueError("User not authorized")

        return client

    def _activity_monitor_worker(self):
        """Background worker that monitors activity and adjusts parameters."""
        while not self._stop_event.is_set() and self.operation_active:
            try:
                # Update active groups
                self._update_active_groups()

                # Check if we need to refresh accounts
                if not self.current_accounts:
                    self.current_accounts = self._get_active_accounts(
                        self.max_parallel_accounts)

                # Log current status
                active_group_count = len(self.active_groups)
                account_count = len(self.current_accounts)

                logger.debug(
                    f"Activity monitor: {active_group_count} active groups, "
                    f"{account_count} available accounts, "
                    f"processed {self.processed_members}/{self.member_limit} members"
                )

                # Adjust parameters dynamically if needed
                # (This could be expanded with more sophisticated logic)

            except Exception as e:
                logger.error(f"Error in activity monitor: {e}")

            # Sleep before next check
            time.sleep(60)  # Check every minute
