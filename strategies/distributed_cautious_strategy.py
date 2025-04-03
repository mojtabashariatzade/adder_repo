"""
Distributed Cautious Strategy Module with Multi-Group Support

This module implements a distributed cautious strategy for adding members to Telegram groups.
It's designed to work 24/7 and distribute the load across multiple accounts while maintaining
a cautious approach to avoid account restrictions. The strategy supports multiple source and
target groups for more efficient member transfers.

Features:
- Distributes operations evenly across the available time period
- Uses multiple accounts simultaneously but with controlled parallelism
- Implements variable delays between operations
- Automatically switches to other accounts if one encounters issues
- Adapts operation speed based on success/failure rates
- Supports 24/7 operation with intelligent scheduling
- Handles multiple source and target groups for optimal distribution
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple, Union, Set
import threading
import itertools

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
logger = get_logger("MultiGroupStrategy")


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


class GroupPair:
    """
    Represents a source-target group pair for member transfer operations.

    This class tracks the status and progress of member transfers between a specific
    source group and target group.
    """

    def __init__(self, source_group: Any, target_group: Any, priority: int = 0):
        """
        Initialize a group pair.

        Args:
            source_group: The source group (for member extraction)
            target_group: The target group (for member addition)
            priority: Priority level for this pair (higher numbers = higher priority)
        """
        self.source_group = source_group
        self.target_group = target_group
        self.priority = priority
        self.processed_members = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.members_cache = []
        self.last_operation_time = None
        self.is_active = True
        self.source_exhausted = False
        self.target_full = False
        self.error_count = 0
        self.consecutive_failures = 0
        self.extracted_member_count = 0

    def record_operation(self, success: bool) -> None:
        """
        Record an operation result for this group pair.

        Args:
            success: Whether the operation was successful
        """
        self.processed_members += 1
        self.last_operation_time = datetime.now()

        if success:
            self.successful_operations += 1
            self.consecutive_failures = 0
        else:
            self.failed_operations += 1
            self.consecutive_failures += 1

            # If too many consecutive failures, mark as inactive temporarily
            if self.consecutive_failures >= 5:
                self.is_active = False
                logger.warning(
                    f"Group pair {self.get_pair_id()} temporarily deactivated due to consecutive failures")

    def get_pair_id(self) -> str:
        """
        Get a unique identifier for this group pair.

        Returns:
            String identifier for the group pair
        """
        source_id = getattr(self.source_group, 'id', str(self.source_group))
        target_id = getattr(self.target_group, 'id', str(self.target_group))
        return f"{source_id}->{target_id}"

    def get_success_rate(self) -> float:
        """
        Get the success rate for operations in this group pair.

        Returns:
            Success rate as a percentage or 100 if no operations
        """
        if self.processed_members == 0:
            return 100.0

        return (self.successful_operations / self.processed_members) * 100

    def needs_members_extraction(self) -> bool:
        """
        Check if this pair needs to extract more members from the source group.

        Returns:
            True if members cache is empty and source is not exhausted
        """
        return len(self.members_cache) == 0 and not self.source_exhausted

    def add_members_to_cache(self, members: List[Any]) -> int:
        """
        Add extracted members to the cache.

        Args:
            members: List of members to add to cache

        Returns:
            Number of members added to cache
        """
        # Add only members that aren't already in the cache
        new_count = 0
        for member in members:
            if member not in self.members_cache:
                self.members_cache.append(member)
                new_count += 1

        self.extracted_member_count += new_count

        # If no new members were found, source might be exhausted
        if new_count == 0 and len(members) > 0:
            self.source_exhausted = True
            logger.info(
                f"Source group in pair {self.get_pair_id()} appears to be exhausted")

        return new_count

    def get_next_member(self) -> Optional[Any]:
        """
        Get the next member from the cache for processing.

        Returns:
            Next member or None if cache is empty
        """
        if self.members_cache:
            return self.members_cache.pop(0)
        return None

    def reactivate(self) -> None:
        """Reactivate this group pair after it was deactivated due to errors."""
        self.is_active = True
        self.consecutive_failures = 0
        logger.info(f"Group pair {self.get_pair_id()} has been reactivated")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the group pair to a dictionary for serialization.

        Returns:
            Dictionary representation of the group pair
        """
        return {
            "source_group": self._group_to_dict(self.source_group),
            "target_group": self._group_to_dict(self.target_group),
            "priority": self.priority,
            "processed_members": self.processed_members,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "last_operation_time": self.last_operation_time.isoformat() if self.last_operation_time else None,
            "is_active": self.is_active,
            "source_exhausted": self.source_exhausted,
            "target_full": self.target_full,
            "error_count": self.error_count,
            "extracted_member_count": self.extracted_member_count
        }

    @staticmethod
    def _group_to_dict(group: Any) -> Dict[str, Any]:
        """Convert a group object to a dictionary."""
        if hasattr(group, 'to_dict') and callable(getattr(group, 'to_dict')):
            return group.to_dict()

        # Try to extract common properties
        result = {}
        for attr in ['id', 'title', 'username', 'is_group', 'is_channel']:
            if hasattr(group, attr):
                result[attr] = getattr(group, attr)

        # If we couldn't extract any properties, just use string representation
        if not result:
            result = {"id": str(group)}

        return result


class MultiGroupDistributedStrategy(BaseStrategy):
    """
    A distributed cautious strategy that supports multiple source and target groups.

    This strategy distributes the member addition operations over time using multiple
    account groups and multiple source/target group pairs, with careful management
    of operation timing and account rotation to minimize the risk of account restrictions.
    """

    def __init__(self, **kwargs):
        """
        Initialize the multi-group distributed cautious strategy.

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
        self.max_extraction_batch = kwargs.get("max_extraction_batch", 100)
        self.group_rotation_interval = kwargs.get(
            "group_rotation_interval", 10)  # minutes
        self.max_consecutive_failures = kwargs.get(
            "max_consecutive_failures", 5)
        self.reactivation_timeout = kwargs.get(
            "reactivation_timeout", 30)  # minutes

        # Runtime state
        self.account_groups = []
        self.active_groups = []
        self.current_accounts = []
        self.group_pairs = []
        self.processed_members = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.operation_active = False
        self._stop_event = threading.Event()
        self._activity_thread = None

        # Group rotation state
        self.current_group_pair_index = 0
        self.last_group_rotation = datetime.now()
        self.extracted_members_count = 0
        self.member_cache = {}  # Maps user_id to user object
        self.processed_user_ids = set()  # Track users already processed

        # For backward compatibility, store single source/target as well
        self.source_group = None
        self.target_group = None

        # Get account manager from kwargs or create a new one
        self.account_manager = kwargs.get("account_manager", AccountManager())

        # Set up schedule for 24/7 operation
        self.time_slots = self._create_time_slots()

    async def execute(self, source_groups=None, target_groups=None, member_limit=None, progress_callback=None, **kwargs):
        """
        Execute the member transfer operation using the distributed cautious strategy.

        Args:
            source_groups: Group(s) to extract members from (single group or list)
            target_groups: Group(s) to add members to (single group or list)
            member_limit: Maximum number of members to transfer
            progress_callback: Function to call with progress updates
            **kwargs: Additional parameters

        Returns:
            Dict with operation results
        """
        # For backward compatibility, support both single group and multiple group parameters
        # Handle the case when execute is called with source_group and target_group (old style)
        if source_groups is None and kwargs.get("source_group") is not None:
            source_groups = kwargs.get("source_group")

        if target_groups is None and kwargs.get("target_group") is not None:
            target_groups = kwargs.get("target_group")

        if member_limit is None:
            # Default to 100 if not specified
            member_limit = kwargs.get("member_limit", 100)

        # Handle single group or list
        if not isinstance(source_groups, (list, tuple)):
            source_groups = [source_groups]

        if not isinstance(target_groups, (list, tuple)):
            target_groups = [target_groups]

        # Store the groups for backward compatibility
        if source_groups and len(source_groups) > 0:
            self.source_group = source_groups[0]

        if target_groups and len(target_groups) > 0:
            self.target_group = target_groups[0]

        # Reset any existing group pairs
        self.group_pairs = []

        # Create group pairs from all combinations of source and target groups
        for source in source_groups:
            for target in target_groups:
                # Skip if source and target are the same group
                if self._groups_are_same(source, target):
                    logger.warning(
                        f"Skipping group pair with identical source and target: {source}")
                    continue

                self.group_pairs.append(GroupPair(source, target))

        if not self.group_pairs:
            raise OperationError(
                "No valid group pairs created. Please provide different source and target groups.")

        logger.info(
            f"Created {len(self.group_pairs)} group pairs for member transfer")

        self.member_limit = member_limit
        self.progress_callback = progress_callback

        # Initialize account groups
        self._initialize_account_groups()

        # Set up the operation state
        self.operation_active = True
        self.processed_members = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.processed_user_ids = set()

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
            "status": "running",
            "group_pair_stats": []
        }

        try:
            # Start processing members
            start_time = time.time()

            # Process until limit is reached or all groups are exhausted
            while (self.processed_members < self.member_limit and
                   self.operation_active and
                   self._has_active_group_pairs()):

                # Select the next group pair to work with using round-robin with priority weighting
                group_pair = self._get_next_group_pair()

                if group_pair is None:
                    # If no active group pairs available, wait a bit and try again
                    await asyncio.sleep(10)
                    continue

                # Check if we need to extract members for this group pair
                if group_pair.needs_members_extraction():
                    await self._extract_members_for_pair(group_pair)

                # Process a member from this group pair
                if group_pair.members_cache:
                    member = group_pair.get_next_member()
                    if member:
                        success = await self._process_member(member, group_pair)

                        # Record the result
                        if success:
                            self.successful_operations += 1
                        else:
                            self.failed_operations += 1

                        self.processed_members += 1

                        # Add to processed set to avoid duplicates
                        user_id = self._get_user_id(member)
                        if user_id:
                            self.processed_user_ids.add(user_id)

                # Update progress
                if progress_callback:
                    progress_callback({
                        "processed": self.processed_members,
                        "success_count": self.successful_operations,
                        "failure_count": self.failed_operations,
                        "group_pairs": len(self.group_pairs),
                        "active_pairs": sum(1 for p in self.group_pairs if p.is_active),
                        "current_pair": group_pair.get_pair_id()
                    })

                # Update result dict
                result["processed"] = self.processed_members
                result["success_count"] = self.successful_operations
                result["failure_count"] = self.failed_operations

                # Check if we need to rotate group pairs
                self._check_group_rotation()

                # Check if we should stop
                if self._stop_event.is_set():
                    logger.info("Operation stopped by request")
                    break

            # Finalize the result
            end_time = time.time()
            result["completion_time"] = end_time - start_time
            result["status"] = "completed"

            # Add stats for each group pair
            for pair in self.group_pairs:
                result["group_pair_stats"].append({
                    "pair_id": pair.get_pair_id(),
                    "processed": pair.processed_members,
                    "successful": pair.successful_operations,
                    "failed": pair.failed_operations,
                    "success_rate": pair.get_success_rate(),
                    "is_active": pair.is_active,
                    "source_exhausted": pair.source_exhausted,
                    "extracted_members": pair.extracted_member_count
                })

            # Clean up
            self.operation_active = False
            if self._activity_thread and self._activity_thread.is_alive():
                self._stop_event.set()
                self._activity_thread.join(timeout=2.0)

            logger.info(f"Operation completed: processed {self.processed_members} members, "
                        f"success: {self.successful_operations}, failures: {self.failed_operations}")

            return result

        except Exception as e:
            logger.error(f"Error in multi-group distributed strategy: {e}")
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
        source_groups_data = session.get_custom_data("source_groups", [])
        target_groups_data = session.get_custom_data("target_groups", [])

        # For backward compatibility, also check for single source/target
        if not source_groups_data:
            source_group_data = session.get_custom_data("source_group", {})
            if source_group_data:
                source_groups_data = [source_group_data]

        if not target_groups_data:
            target_group_data = session.get_custom_data("target_group", {})
            if target_group_data:
                target_groups_data = [target_group_data]

        # Check if we have the necessary data
        if not source_groups_data or not target_groups_data:
            raise OperationError(
                "Missing source or target group data in session")

        # Get member limit from session
        member_limit = state.get("total", 1000)

        # Get processed user IDs to avoid duplicates
        processed_ids = session.get_custom_data("processed_user_ids", [])
        self.processed_user_ids = set(processed_ids)

        # Execute the operation
        return await self.execute(
            source_groups=source_groups_data,
            target_groups=target_groups_data,
            member_limit=member_limit,
            progress_callback=progress_callback,
            resumed=True,
            session=session
        )

    async def _extract_members_for_pair(self, group_pair: GroupPair) -> int:
        """
        Extract members from the source group of a group pair.

        Args:
            group_pair: The group pair to extract members for

        Returns:
            Number of members extracted
        """
        logger.info(
            f"Extracting members for group pair {group_pair.get_pair_id()}")

        # Get active accounts for extraction
        active_accounts = self._get_active_accounts(2)
        if not active_accounts:
            logger.warning(
                "No active accounts available for member extraction")
            return 0

        # Use the first available account to extract members
        account = active_accounts[0]

        try:
            # Initialize the client and connect
            client = await self._get_client(account)

            # Get members with batch size limit
            participants = await client.get_participants(
                group_pair.source_group,
                limit=self.max_extraction_batch
            )

            # Filter out bots, empty users, etc.
            valid_members = [
                member for member in participants
                if not member.bot and not member.deleted and not member.fake
                and self._get_user_id(member) not in self.processed_user_ids
            ]

            # Add to the group pair's cache
            added_count = group_pair.add_members_to_cache(valid_members)

            logger.info(
                f"Extracted {len(valid_members)} valid members from source group, "
                f"added {added_count} new members to cache"
            )

            # Disconnect client
            await client.disconnect()

            return added_count

        except Exception as e:
            logger.error(
                f"Error extracting members for group pair {group_pair.get_pair_id()}: {e}")
            group_pair.error_count += 1

            # If too many errors, mark the source as exhausted
            if group_pair.error_count >= 3:
                group_pair.source_exhausted = True
                logger.warning(
                    f"Marking source group in pair {group_pair.get_pair_id()} as exhausted due to errors")

            return 0

    async def _process_member(self, member, group_pair: GroupPair) -> bool:
        """
        Process a single member (add to target group).

        Args:
            member: Member to add to target group
            group_pair: The group pair to process the member for

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
            result = await client.add_contact(member, group_pair.target_group)

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

            # Record successful operation for this group pair
            group_pair.record_operation(True)

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

            # Record failed operation for this group pair
            group_pair.record_operation(False)

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

            # Record failed operation for this group pair
            group_pair.record_operation(False)

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

    def _get_next_group_pair(self):
        """
        Get the next active group pair to process using round-robin with prioritization.

        Returns:
            GroupPair or None if no active pairs
        """
        if not self.group_pairs:
            return None

        # Filter active group pairs
        active_pairs = [pair for pair in self.group_pairs if pair.is_active]
        if not active_pairs:
            # Check if we should reactivate any pairs
            self._reactivate_group_pairs()
            active_pairs = [
                pair for pair in self.group_pairs if pair.is_active]
            if not active_pairs:
                return None

        # Sort by priority (higher priority first)
        active_pairs.sort(key=lambda p: (-p.priority, p.processed_members))

        # Start from the current index
        index = self.current_group_pair_index % len(active_pairs)
        pair = active_pairs[index]

        # Update index for next time
        self.current_group_pair_index = (
            self.current_group_pair_index + 1) % len(active_pairs)

        return pair

    def _check_group_rotation(self):
        """Check if it's time to rotate to the next group pair."""
        now = datetime.now()
        time_since_rotation = (
            now - self.last_group_rotation).total_seconds() / 60  # minutes

        if time_since_rotation >= self.group_rotation_interval:
            self.last_group_rotation = now
            # No need to do anything else since _get_next_group_pair handles rotation
            logger.debug("Group rotation time checkpoint reached")

    def _reactivate_group_pairs(self):
        """Reactivate group pairs that were deactivated due to errors."""
        now = datetime.now()
        reactivated = 0

        for pair in self.group_pairs:
            if not pair.is_active and not pair.source_exhausted and not pair.target_full:
                # Check if it's been long enough since deactivation
                if pair.last_operation_time:
                    minutes_since_operation = (
                        now - pair.last_operation_time).total_seconds() / 60
                    if minutes_since_operation >= self.reactivation_timeout:
                        pair.reactivate()
                        reactivated += 1
                else:
                    # If no last operation time, just reactivate
                    pair.reactivate()
                    reactivated += 1

        if reactivated > 0:
            logger.info(f"Reactivated {reactivated} group pairs")

    def _has_active_group_pairs(self):
        """Check if there are any active group pairs."""
        # First check if any pairs are currently active
        if any(pair.is_active for pair in self.group_pairs):
            return True

        # If not, check if any can be reactivated
        self._reactivate_group_pairs()
        return any(pair.is_active for pair in self.group_pairs)

    def _get_user_id(self, user):
        """Get a unique identifier for a user."""
        if hasattr(user, 'id'):
            return user.id
        if isinstance(user, dict) and 'id' in user:
            return user['id']
        return str(user)

    def _groups_are_same(self, group1, group2):
        """Check if two groups are the same."""
        if group1 is group2:
            return True

        # Try to get IDs
        id1 = getattr(group1, 'id', str(group1))
        id2 = getattr(group2, 'id', str(group2))

        return id1 == id2

    def _save_operation_state(self, session):
        """Save the current operation state to a session."""
        if not session:
            return

        # Basic operation state
        session.update_state({
            "processed": self.processed_members,
            "success_count": self.successful_operations,
            "failure_count": self.failed_operations,
            "total": self.member_limit,
            "status": "running" if self.operation_active else "paused",
            "last_updated": datetime.now().isoformat()
        })

        # Save group pairs state
        group_pairs_state = [pair.to_dict() for pair in self.group_pairs]
        session.set_custom_data("group_pairs", group_pairs_state)

        # Save source and target groups
        source_groups = list(
            set(pair.source_group for pair in self.group_pairs))
        target_groups = list(
            set(pair.target_group for pair in self.group_pairs))

        session.set_custom_data("source_groups", source_groups)
        session.set_custom_data("target_groups", target_groups)

        # Save processed user IDs to avoid duplicates on resume
        session.set_custom_data("processed_user_ids",
                                list(self.processed_user_ids))

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
                active_pairs = sum(1 for p in self.group_pairs if p.is_active)

                logger.debug(
                    f"Activity monitor: {active_group_count} active account groups, "
                    f"{account_count} available accounts, "
                    f"{active_pairs}/{len(self.group_pairs)} active group pairs, "
                    f"processed {self.processed_members}/{self.member_limit} members"
                )

                # Check if any inactive group pairs can be reactivated
                self._reactivate_group_pairs()

            except Exception as e:
                logger.error(f"Error in activity monitor: {e}")

            # Sleep before next check
            time.sleep(60)  # Check every minute
