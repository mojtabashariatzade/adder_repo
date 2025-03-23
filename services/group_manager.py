"""
Group Manager Service
"""

import os
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Tuple, Any
from pathlib import Path
import uuid

try:
    from core.constants import Constants, AccountStatus
    from core.exceptions import (
        GroupNotFoundError, NotGroupAdminError, GroupError,
        MemberExtractionError, MemberAdditionError, APIError,
        FileReadError, FileWriteError
    )
    from core.config import Config
    from services.account_manager import AccountManager, get_account_manager
    from logging_.logging_manager import get_logger
except ImportError:
    # For development
    class GroupNotFoundError(Exception):
        pass

    class NotGroupAdminError(Exception):
        pass

    class GroupError(Exception):
        pass

    class MemberExtractionError(Exception):
        pass

    class MemberAdditionError(Exception):
        pass

    class APIError(Exception):
        pass

    class FileReadError(Exception):
        pass

    class FileWriteError(Exception):
        pass

    class AccountStatus:
        ACTIVE = 1

    class Config:
        _instance = None

        def __new__(cls):
            if cls._instance is None:
                cls._instance = super(Config, cls).__new__(cls)
                cls._instance._config_data = {
                    "groups_file": "telegram_groups.json",
                    "max_members_per_request": 100,
                    "member_add_delay": 20,
                    "max_extraction_members": 1000
                }
            return cls._instance

        def get(self, key, default=None):
            return self._config_data.get(key, default)

    class AccountManager:
        def get_available_accounts(self, count=1, for_adding=True):
            return []

        def increment_member_count(self, account_id, count_type="added"):
            return True

        def update_account_status(self, account_id, status, cooldown_hours=None):
            return True

        def increment_failure_count(self, account_id):
            return 1

        def reset_failure_count(self, account_id):
            return True

    def get_account_manager():
        return AccountManager()

    get_logger = lambda name: logging.getLogger(name)

# Constants
GROUPS_FILE = "telegram_groups.json"
MAX_MEMBERS_PER_REQUEST = 100
MEMBER_ADD_DELAY = 20
MAX_EXTRACTION_MEMBERS = 1000

# Logger setup
logger = get_logger("GroupManager")

class TelegramGroup:
    def __init__(self, group_id, title=None, username=None, access_hash=None):
        self.group_id = group_id
        self.title = title
        self.username = username
        self.access_hash = access_hash
        self.member_count = 0
        self.is_admin = False
        self.join_date = datetime.now().isoformat()
        self.last_used = datetime.now().isoformat()
        self.description = ""
        self.custom_data = {}

    def to_dict(self):
        return {
            "group_id": self.group_id,
            "title": self.title,
            "username": self.username,
            "access_hash": self.access_hash,
            "member_count": self.member_count,
            "is_admin": self.is_admin,
            "join_date": self.join_date,
            "last_used": self.last_used,
            "description": self.description,
            "custom_data": self.custom_data
        }

    @classmethod
    def from_dict(cls, data):
        group = cls(
            group_id=data.get("group_id"),
            title=data.get("title"),
            username=data.get("username"),
            access_hash=data.get("access_hash")
        )
        group.member_count = data.get("member_count", 0)
        group.is_admin = data.get("is_admin", False)
        group.join_date = data.get("join_date", datetime.now().isoformat())
        group.last_used = data.get("last_used", datetime.now().isoformat())
        group.description = data.get("description", "")
        group.custom_data = data.get("custom_data", {})
        return group

class GroupManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GroupManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, groups_file=None):
        with self._lock:
            if self._initialized:
                return

            self.config = Config()
            self.groups_file = groups_file or self.config.get('groups_file', GROUPS_FILE)
            self.max_members_per_request = self.config.get('max_members_per_request', MAX_MEMBERS_PER_REQUEST)
            self.member_add_delay = self.config.get('member_add_delay', MEMBER_ADD_DELAY)
            self.max_extraction_members = self.config.get('max_extraction_members', MAX_EXTRACTION_MEMBERS)

            self.groups = {}
            self.cached_members = {}
            self.account_manager = get_account_manager()

            self._load_groups()
            self._initialized = True
            logger.info("GroupManager initialized")

    def _load_groups(self):
        try:
            if not os.path.exists(self.groups_file):
                logger.info(f"Groups file not found: {self.groups_file}. Creating new file.")
                self.groups = {}
                self._save_groups()
                return

            with open(self.groups_file, 'r') as file:
                groups_data = json.load(file)

            self.groups = {}
            for group_data in groups_data.get('groups', []):
                group = TelegramGroup.from_dict(group_data)
                self.groups[group.group_id] = group

            logger.info(f"Loaded {len(self.groups)} groups from {self.groups_file}")
        except Exception as e:
            logger.error(f"Error loading groups: {e}")
            self.groups = {}

    def _save_groups(self):
        try:
            groups_data = {
                'last_updated': datetime.now().isoformat(),
                'groups': [group.to_dict() for group in self.groups.values()]
            }

            with open(self.groups_file, 'w') as file:
                json.dump(groups_data, file, indent=4)

            logger.debug(f"Saved {len(self.groups)} groups to {self.groups_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving groups: {e}")
            return False

    def add_group(self, group_id, title=None, username=None, access_hash=None, is_admin=False, description=""):
        # Check if group already exists
        if group_id in self.groups:
            logger.info(f"Group {title or group_id} already exists, updating information")
            group = self.groups[group_id]

            # Update group information
            if title:
                group.title = title
            if username:
                group.username = username
            if access_hash:
                group.access_hash = access_hash

            group.is_admin = is_admin
            if description:
                group.description = description

            group.last_used = datetime.now().isoformat()
        else:
            # Create new group
            group = TelegramGroup(
                group_id=group_id,
                title=title,
                username=username,
                access_hash=access_hash
            )
            group.is_admin = is_admin
            group.description = description

            self.groups[group_id] = group
            logger.info(f"Added new group: {title or group_id} (ID: {group_id})")

        self._save_groups()
        return group_id

    def get_group(self, group_id):
        if group_id not in self.groups:
            raise GroupNotFoundError(f"Group with ID {group_id} not found")
        return self.groups[group_id]

    def get_group_by_title(self, title):
        for group in self.groups.values():
            if group.title == title:
                return group
        raise GroupNotFoundError(f"Group with title '{title}' not found")

    def get_group_by_username(self, username):
        # Remove @ if present
        if username.startswith('@'):
            username = username[1:]

        for group in self.groups.values():
            if group.username == username:
                return group
        raise GroupNotFoundError(f"Group with username '@{username}' not found")

    def update_group(self, group_id, **kwargs):
        if group_id not in self.groups:
            raise GroupNotFoundError(f"Group with ID {group_id} not found")

        group = self.groups[group_id]

        # Update group properties
        for key, value in kwargs.items():
            if hasattr(group, key):
                setattr(group, key, value)

        group.last_used = datetime.now().isoformat()
        self._save_groups()

        logger.info(f"Updated group {group.title or group_id} (ID: {group_id})")
        return True

    def remove_group(self, group_id):
        if group_id not in self.groups:
            raise GroupNotFoundError(f"Group with ID {group_id} not found")

        group = self.groups.pop(group_id)
        self._save_groups()

        # Remove from cached members if present
        if group_id in self.cached_members:
            del self.cached_members[group_id]

        logger.info(f"Removed group {group.title or group_id} (ID: {group_id})")
        return True

    def get_all_groups(self):
        return list(self.groups.values())

    def get_admin_groups(self):
        return [group for group in self.groups.values() if group.is_admin]

    async def extract_members(self, group_id, limit=None, filter_criteria=None, client=None, callback=None):
        """
        Extract members from a group.

        Args:
            group_id: ID of the group
            limit: Maximum number of members to extract (None for no limit)
            filter_criteria: Dictionary of filter conditions
            client: Optional Telegram client to use
            callback: Optional callback function for progress updates

        Returns:
            List of extracted members
        """
        if group_id not in self.groups:
            raise GroupNotFoundError(f"Group with ID {group_id} not found")

        group = self.groups[group_id]

        # If no client provided, get one from account manager
        if not client:
            available_accounts = self.account_manager.get_available_accounts(count=1, for_adding=False)
            if not available_accounts:
                raise GroupError("No available accounts for member extraction")

            # Note: In actual implementation, get the client from the account
            # For now, we'll just simulate it
            account_id = "simulated_account_id"
            client = "simulated_client"
        else:
            account_id = "provided_account_id"

        try:
            if callback:
                callback({"status": "starting", "group": group.title, "count": 0})

            # Simulated member extraction
            # In actual implementation, use client to get participants
            members = []
            max_members = limit if limit else self.max_extraction_members

            # For development, return simulated members
            for i in range(min(max_members, 100)):  # Simulate 100 members max for testing
                member = {
                    "id": i + 1000,
                    "first_name": f"User{i}",
                    "last_name": f"Test{i}",
                    "username": f"user{i}",
                    "phone": f"+123456{i:04}",
                    "status": "online" if i % 5 == 0 else "recently" if i % 5 == 1 else "last_week",
                    "bot": i % 20 == 0,  # Every 20th user is a bot
                }

                # Apply filters if provided
                if filter_criteria:
                    # Skip bots if specified
                    if filter_criteria.get("no_bots", False) and member["bot"]:
                        continue

                    # Filter by status if specified
                    if "status" in filter_criteria and member["status"] not in filter_criteria["status"]:
                        continue

                members.append(member)

                # Update progress callback
                if callback and i % 10 == 0:
                    callback({"status": "extracting", "group": group.title, "count": len(members)})

            # Cache the extracted members
            self.cached_members[group_id] = members

            # Update account extraction count
            self.account_manager.increment_member_count(account_id, count_type="extracted")

            # Update group information
            group.member_count = len(members)
            group.last_used = datetime.now().isoformat()
            self._save_groups()

            if callback:
                callback({"status": "completed", "group": group.title, "count": len(members)})

            logger.info(f"Extracted {len(members)} members from group {group.title}")
            return members

        except Exception as e:
            logger.error(f"Error extracting members from group {group.title}: {e}")
            self.account_manager.increment_failure_count(account_id)

            if callback:
                callback({"status": "failed", "group": group.title, "error": str(e)})

            raise MemberExtractionError(f"Failed to extract members: {e}")

    async def add_members_to_group(self, target_group_id, members, client=None, delay=None, callback=None):
        """
        Add members to a group.

        Args:
            target_group_id: ID of the target group
            members: List of members to add
            client: Optional Telegram client to use
            delay: Delay between requests (None for default)
            callback: Optional callback function for progress updates

        Returns:
            Dictionary with results of the operation
        """
        if target_group_id not in self.groups:
            raise GroupNotFoundError(f"Group with ID {target_group_id} not found")

        target_group = self.groups[target_group_id]

        if not target_group.is_admin:
            raise NotGroupAdminError(f"Not an admin in the group {target_group.title}")

        # If no delay specified, use default
        if delay is None:
            delay = self.member_add_delay

        # If no client provided, get one from account manager
        if not client:
            available_accounts = self.account_manager.get_available_accounts(count=1, for_adding=True)
            if not available_accounts:
                raise GroupError("No available accounts for adding members")

            # Note: In actual implementation, get the client from the account
            # For now, we'll just simulate it
            account_id = "simulated_account_id"
            client = "simulated_client"
        else:
            account_id = "provided_account_id"

        try:
            if callback:
                callback({
                    "status": "starting",
                    "group": target_group.title,
                    "total": len(members),
                    "added": 0,
                    "failed": 0
                })

            results = {
                "total": len(members),
                "added": 0,
                "failed": 0,
                "failed_members": [],
                "success_members": []
            }

            # Process members in batches to avoid flooding
            for i, member in enumerate(members):
                try:
                    # Simulate adding member
                    # In actual implementation, use client to add member
                    member_id = member.get("id", 0)
                    success = member_id % 10 != 0  # Simulate failure for every 10th member

                    if success:
                        results["added"] += 1
                        results["success_members"].append(member)

                        # Increment the account's member addition count
                        self.account_manager.increment_member_count(account_id, count_type="added")
                    else:
                        results["failed"] += 1
                        results["failed_members"].append({
                            "member": member,
                            "error": "Simulated failure"
                        })

                    # Update progress
                    if callback:
                        callback({
                            "status": "adding",
                            "group": target_group.title,
                            "total": len(members),
                            "added": results["added"],
                            "failed": results["failed"],
                            "current": i + 1
                        })

                    # Reset failure count if successful
                    if success and i > 0 and i % 5 == 0:
                        self.account_manager.reset_failure_count(account_id)

                    # Enforce delay between requests
                    if i < len(members) - 1:
                        await asyncio.sleep(delay)

                except Exception as e:
                    logger.error(f"Error adding member {member.get('id', 0)} to group: {e}")
                    results["failed"] += 1
                    results["failed_members"].append({
                        "member": member,
                        "error": str(e)
                    })

                    # Increment failure count
                    failure_count = self.account_manager.increment_failure_count(account_id)

                    # If too many failures, switch account
                    if failure_count >= 3:  # MAX_FAILURES_BEFORE_BLOCK
                        self.account_manager.update_account_status(account_id, "COOLDOWN", cooldown_hours=1)

                        # In actual implementation, get a new client here
                        logger.warning("Too many failures, would switch accounts in actual implementation")

            # Update group information
            target_group.last_used = datetime.now().isoformat()
            self._save_groups()

            if callback:
                callback({
                    "status": "completed",
                    "group": target_group.title,
                    "total": len(members),
                    "added": results["added"],
                    "failed": results["failed"]
                })

            logger.info(f"Added {results['added']} members to group {target_group.title} (failed: {results['failed']})")
            return results

        except Exception as e:
            logger.error(f"Error adding members to group {target_group.title}: {e}")
            self.account_manager.increment_failure_count(account_id)

            if callback:
                callback({
                    "status": "failed",
                    "group": target_group.title,
                    "error": str(e)
                })

            raise MemberAdditionError(f"Failed to add members: {e}")

    def search_groups(self, query, field=None):
        """
        Search for groups matching the query.

        Args:
            query: Search query
            field: Specific field to search in (title, username, etc.)

        Returns:
            List of matching groups
        """
        results = []
        query = query.lower()

        for group in self.groups.values():
            if field is None or field == "title":
                if query in group.title.lower():
                    results.append(group)
                    continue

            if field is None or field == "username":
                if group.username and query in group.username.lower():
                    results.append(group)
                    continue

            if field is None or field == "description":
                if query in group.description.lower():
                    results.append(group)
                    continue

        return results

    def get_cached_members(self, group_id):
        """
        Get cached members for a group.

        Args:
            group_id: ID of the group

        Returns:
            List of cached members or None if not cached
        """
        return self.cached_members.get(group_id)

    def clear_cached_members(self, group_id=None):
        """
        Clear cached members.

        Args:
            group_id: ID of the group to clear (None for all)

        Returns:
            True if successful
        """
        if group_id:
            if group_id in self.cached_members:
                del self.cached_members[group_id]
                logger.debug(f"Cleared cached members for group {group_id}")
        else:
            self.cached_members.clear()
            logger.debug("Cleared all cached members")

        return True

    def backup_groups(self, backup_file=None):
        """
        Backup groups to a file.

        Args:
            backup_file: Path to backup file (None for auto-generated)

        Returns:
            Path to backup file or None if failed
        """
        if not backup_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"groups_backup_{timestamp}.json"

        try:
            groups_data = {
                'timestamp': datetime.now().isoformat(),
                'groups': [group.to_dict() for group in self.groups.values()]
            }

            with open(backup_file, 'w') as file:
                json.dump(groups_data, file, indent=4)

            logger.info(f"Groups backed up to {backup_file}")
            return backup_file
        except Exception as e:
            logger.error(f"Error backing up groups: {e}")
            return None

    def restore_groups(self, backup_file):
        """
        Restore groups from a backup file.

        Args:
            backup_file: Path to backup file

        Returns:
            True if successful
        """
        try:
            with open(backup_file, 'r') as file:
                groups_data = json.load(file)

            new_groups = {}
            for group_data in groups_data.get('groups', []):
                group = TelegramGroup.from_dict(group_data)
                new_groups[group.group_id] = group

            # Replace current groups with restored ones
            self.groups = new_groups
            self._save_groups()

            logger.info(f"Restored {len(self.groups)} groups from {backup_file}")
            return True
        except Exception as e:
            logger.error(f"Error restoring groups from backup: {e}")
            return False

def get_group_manager():
    return GroupManager()