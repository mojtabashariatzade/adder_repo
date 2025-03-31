"""
Group Manager Module

This module provides functionality for managing Telegram groups, including:
- Extracting members from source groups
- Adding members to destination groups
- Managing group information and permissions
- Handling group-related errors
"""

import os
import json
import logging
import time
import asyncio
from data.file_factory import FileManager
from typing import Dict, List, Optional, Any, Tuple

# Import telethon modules
from telethon.tl.functions.channels import GetFullChannelRequest, InviteToChannelRequest
from telethon.tl.types import InputPeerChannel, InputPeerUser
from telethon.errors import (
    UserPrivacyRestrictedError,
    UserNotMutualContactError, FloodWaitError
)

from core.config import Config
from core.exceptions import (
    GroupNotFoundError, NotGroupAdminError,
    MemberExtractionError, MemberAdditionError
)
from error_handling.error_handlers import handle_error

logger = logging.getLogger(__name__)


class GroupManager:
    """
    Class for managing Telegram groups, including extracting and adding members.
    """

    def __init__(self, app_context: Optional[Dict[str, Any]] = None):
        """
        Initialize the GroupManager.

        Args:
            app_context (Optional[Dict[str, Any]]): Application context containing
                shared resources like config.
        """
        self.app_context = app_context or {}
        self.config = self.app_context.get('config', Config())
        # Make sure the config is initialized
        if not hasattr(self.config, '_config_data'):
            self.config._set_defaults()
        self.client = None
        self.groups_cache = {}
        self.members_cache = {}

    async def initialize_client(self, client) -> bool:
        """
        Initialize the Telegram client.

        Args:
            client: Initialized Telegram client.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            self.client = client
            return True
        except Exception as e:
            logger.error(
                "Failed to initialize client in GroupManager: %s", str(e))
            error_context = {"operation": "initialize_client"}
            handle_error(e, error_context)
            return False

    async def get_groups(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get a list of groups the account is a member of.

        Args:
            force_refresh (bool): Whether to refresh the cache.

        Returns:
            List[Dict[str, Any]]: List of group info dictionaries.
        """
        if not self.client:
            logger.error("Client not initialized for get_groups")
            return []

        if not force_refresh and self.groups_cache:
            return list(self.groups_cache.values())

        try:
            # Clear the cache if we're refreshing
            if force_refresh:
                self.groups_cache = {}

            # Get dialogs
            dialogs = await self.client.get_dialogs()
            groups = []

            for dialog in dialogs:
                if dialog.is_group or dialog.is_channel:
                    group_info = {
                        "id": dialog.id,
                        "title": dialog.title,
                        "is_group": dialog.is_group,
                        "is_channel": dialog.is_channel,
                        "members_count": getattr(dialog.entity, 'participants_count', 0),
                        "access_hash": getattr(dialog.entity, 'access_hash', None),
                    }

                    # Add to cache
                    self.groups_cache[dialog.id] = group_info
                    groups.append(group_info)

            logger.info("Retrieved %d groups", len(groups))
            return groups
        except Exception as e:
            logger.error("Failed to get groups: %s", str(e))
            error_context = {"operation": "get_groups"}
            handle_error(e, error_context)
            return []

    async def get_group_by_id(self, group_id: int) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific group.

        Args:
            group_id (int): Group ID.

        Returns:
            Optional[Dict[str, Any]]: Group information or None if not found.
        """
        if not self.client:
            logger.error("Client not initialized for get_group_by_id")
            return None

        # Check cache first
        if group_id in self.groups_cache:
            return self.groups_cache[group_id]

        try:
            # Get the entity information
            entity = await self.client.get_entity(group_id)

            # Check if the entity has a participants_count attribute
            if hasattr(entity, 'participants_count'):
                members_count = entity.participants_count
            else:
                # We need to get the full entity to get the participants count
                # Create input peer channel from entity
                input_channel = InputPeerChannel(entity.id, entity.access_hash)
                full_entity = await self.client(GetFullChannelRequest(channel=input_channel))
                members_count = full_entity.full_chat.participants_count

            group_info = {
                "id": entity.id,
                "title": getattr(entity, 'title', 'Unknown'),
                "is_group": hasattr(entity, 'megagroup') and entity.megagroup,
                "is_channel": hasattr(entity, 'broadcast') and entity.broadcast,
                "members_count": members_count,
                "access_hash": getattr(entity, 'access_hash', None),
            }

            # Add to cache
            self.groups_cache[entity.id] = group_info

            logger.info("Retrieved group info for %d: %s",
                        group_id, group_info["title"])
            return group_info
        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Failed to get group %d: %s", group_id, str(e))
            error_context = {
                "operation": "get_group_by_id", "group_id": group_id}
            handle_error(e, error_context)
            return None

    async def check_group_permissions(self, group_id: int) -> Dict[str, bool]:
        """
        Check what permissions the current account has in a group.

        Args:
            group_id (int): The ID of the group to check permissions for

        Returns:
            Dict[str, bool]: Dictionary of permission flags including:
                - is_admin: Whether the account is an admin
                - can_add_members: Whether the account can add members
        """
        if not self.client:
            logger.error("Client not initialized for check_group_permissions")
            return {"is_admin": False, "can_add_members": False}

        try:
            # Get the entity information
            entity = await self.client.get_entity(group_id)

            # Check if we're an admin
            permissions = {"is_admin": False, "can_add_members": False}

            participant = await self.client.get_permissions(entity)

            # Check admin status
            if participant.is_admin:
                permissions["is_admin"] = True

                # Check if we can add members
                permissions["can_add_members"] = participant.add_admins or participant.invite_users

            logger.info("Permissions for group %d: %s", group_id, permissions)
            return permissions
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(
                "Failed to check permissions for group %d: %s", group_id, str(e))
            error_context = {
                "operation": "check_group_permissions", "group_id": group_id}
            handle_error(e, error_context)
            return {"is_admin": False, "can_add_members": False}

    async def extract_group_members(
            self, group_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Extract members from a group.

        Args:
            group_id (int): Group ID.
            limit (Optional[int]): Maximum number of members to extract.

        Returns:
            List[Dict[str, Any]]: List of member info dictionaries.

        Raises:
            GroupNotFoundError: If the group doesn't exist.
            NotGroupAdminError: If the account is not an admin of the group.
            MemberExtractionError: If extraction fails.
        """
        if not self.client:
            logger.error("Client not initialized for extract_group_members")
            raise MemberExtractionError("Client not initialized")

        try:
            # Get the entity information
            entity = await self.client.get_entity(group_id)

            # Check if we're an admin (optional, some groups may not require admin privileges)
            try:
                permissions = await self.check_group_permissions(group_id)
                if not permissions["is_admin"]:
                    logger.warning(
                        "Not an admin of group %d, but attempting extraction anyway", group_id)
            except Exception as e:
                logger.warning(
                    "Couldn't check permissions for group %d: %s", group_id, str(e))

            # Get participants
            max_limit = limit or self.config.get('max_members_per_day', 20)
            members = []
            members_count = 0

            async for member in self.client.iter_participants(entity, limit=max_limit):
                # Filter out bots, deleted accounts, etc.
                if member.bot or member.deleted:
                    continue

                member_info = {
                    "id": member.id,
                    "access_hash": member.access_hash,
                    "username": member.username,
                    "first_name": member.first_name,
                    "last_name": member.last_name,
                    "phone": member.phone,
                    "is_bot": member.bot,
                    "is_deleted": member.deleted,
                }

                members.append(member_info)
                members_count += 1

                # Apply limit if specified
                if limit and members_count >= limit:
                    break

            # Cache the members for this group
            self.members_cache[group_id] = members

            logger.info("Extracted %d members from group %d",
                        len(members), group_id)
            return members
        except GroupNotFoundError:
            # Re-raise specific errors
            raise
        except NotGroupAdminError:
            # Re-raise specific errors
            raise
        except Exception as e:
            logger.error(
                "Failed to extract members from group %d: %s", group_id, str(e))
            error_context = {
                "operation": "extract_group_members", "group_id": group_id}
            handle_error(e, error_context)
            raise MemberExtractionError(
                f"Failed to extract members: {str(e)}") from e

    async def add_member_to_group(self, user_id: int, access_hash: int, group_id: int) -> bool:
        """
        Add a single member to a group.

        Args:
            user_id (int): User ID.
            access_hash (int): User access hash.
            group_id (int): Group ID.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.client:
            logger.error("Client not initialized for add_member_to_group")
            return False

        try:
            # Get the target group entity
            group_entity = await self.client.get_entity(group_id)

            # Create user entity for the user to add
            user_to_add = InputPeerUser(user_id, access_hash)

            # Check if we can add members
            permissions = await self.check_group_permissions(group_id)
            if not permissions.get("can_add_members", False):
                logger.warning(
                    "Don't have permission to add members to group %d", group_id)
                raise NotGroupAdminError(
                    "Don't have permission to add members")

            # Create input channel for the target group
            input_channel = InputPeerChannel(
                group_entity.id, group_entity.access_hash)

            # Add the user
            await self.client(InviteToChannelRequest(input_channel, [user_to_add]))

            logger.info("Added user %d to group %d", user_id, group_id)
            return True
        except NotGroupAdminError:
            # Re-raise specific errors
            raise
        except (UserPrivacyRestrictedError, UserNotMutualContactError, FloodWaitError) as e:
            logger.error("Failed to add user %d to group %d: %s",
                         user_id, group_id, str(e))
            error_context = {
                "operation": "add_member_to_group",
                "user_id": user_id,
                "group_id": group_id
            }
            handle_error(e, error_context)
            return False

    async def add_members_to_group(
        self,
        members: List[Dict[str, Any]],
        group_id: int,
        delay: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Add multiple members to a group.

        Args:
            members (List[Dict[str, Any]]): List of member info dictionaries.
            group_id (int): Group ID.
            delay (Optional[int]): Delay between adding members (in seconds).

        Returns:
            Tuple[int, int]: (Number of successful additions, Number of failed additions).

        Raises:
            GroupNotFoundError: If the group doesn't exist.
            NotGroupAdminError: If the account is not an admin of the group.
            MemberAdditionError: If addition fails.
        """
        if not self.client:
            logger.error("Client not initialized for add_members_to_group")
            raise MemberAdditionError("Client not initialized")

        # Set default delay
        if delay is None:
            delay = self.config.get('default_delay', 20)

        successful_count = 0
        failed_count = 0

        try:
            # Get the target group entity
            group_entity = await self.client.get_entity(group_id)

            # Check if we can add members
            permissions = await self.check_group_permissions(group_id)
            if not permissions.get("can_add_members", False):
                logger.warning(
                    "Don't have permission to add members to group %d", group_id)
                raise NotGroupAdminError(
                    "Don't have permission to add members")

            # Process members one by one with delay between each
            for member in members:
                try:
                    # Extract necessary member information
                    user_id = member["id"]
                    access_hash = member["access_hash"]

                    # Create user entity for the user to add
                    user_to_add = InputPeerUser(user_id, access_hash)

                    # Create input channel for the target group
                    input_channel = InputPeerChannel(
                        group_entity.id, group_entity.access_hash)

                    # Add the user
                    await self.client(InviteToChannelRequest(input_channel, [user_to_add]))

                    successful_count += 1
                    logger.info("Added user %d to group %d (%d/%d)",
                                user_id, group_id, successful_count, len(members))

                    # Apply delay between additions
                    await asyncio.sleep(delay)
                except (UserPrivacyRestrictedError, UserNotMutualContactError, FloodWaitError) as e:
                    failed_count += 1
                    logger.warning("Failed to add user %d to group %d: %s",
                                   user_id, group_id, str(e))

            logger.info("Added %d members to group %d (%d failed)",
                        successful_count, group_id, failed_count)
            return successful_count, failed_count
        except GroupNotFoundError:
            # Re-raise specific errors
            raise
        except NotGroupAdminError:
            # Re-raise specific errors
            raise
        except Exception as e:
            logger.error("Failed to add members to group %d: %s",
                         group_id, str(e))
            error_context = {
                "operation": "add_members_to_group", "group_id": group_id}
            handle_error(e, error_context)
            raise MemberAdditionError(
                f"Failed to add members: {str(e)}") from e

    async def transfer_members(
        self,
        source_group_id: int,
        destination_group_id: int,
        limit: Optional[int] = None,
        delay: Optional[int] = None,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Transfer members from source group to destination group.

        Args:
            source_group_id: Source group ID
            destination_group_id: Destination group ID
            limit: Maximum number of members to transfer
            delay: Delay between adding members (in seconds)
            skip_existing: Whether to skip existing members

        Returns:
            Result dictionary containing statistics
        """
        """
        Transfer members from source group to destination group.

        Args:
            source_group_id (int): Source group ID.
            destination_group_id (int): Destination group ID.
            limit (Optional[int]): Maximum number of members to transfer.
            delay (Optional[int]): Delay between adding members (in seconds).
            skip_existing (bool): Whether to skip existing members in the destination group.

        Returns:
            Dict[str, Any]: Result dictionary containing statistics.
        """
        if not self.client:
            logger.error("Client not initialized for transfer_members")
            return {
                "success": False,
                "error": "Client not initialized",
                "extracted": 0,
                "added": 0,
                "skipped": 0,
                "failed": 0
            }

        # Set default values from config
        default_delay = 20
        default_limit = 20

        # Get values from config if available
        if hasattr(self.config, 'get'):
            default_delay = self.config.get('default_delay', 20)
            default_limit = self.config.get('max_members_per_day', 20)

        # Use provided values or defaults
        if delay is None:
            delay = default_delay

        if limit is None:
            limit = default_limit

        result = {
            "success": False,
            "extracted": 0,
            "added": 0,
            "skipped": 0,
            "failed": 0,
            "source_group": None,
            "destination_group": None
        }

        try:
            # Get group info
            source_group = await self.get_group_by_id(source_group_id)
            destination_group = await self.get_group_by_id(destination_group_id)

            if not source_group:
                raise GroupNotFoundError(
                    f"Source group {source_group_id} not found")

            if not destination_group:
                raise GroupNotFoundError(
                    f"Destination group {destination_group_id} not found")

            result["source_group"] = source_group
            result["destination_group"] = destination_group

            # Extract members from source group
            members = await self.extract_group_members(source_group_id, limit)
            result["extracted"] = len(members)

            if skip_existing:
                # Extract existing members from destination group to skip them
                try:
                    existing_members = await self.extract_group_members(destination_group_id)
                    existing_ids = {member["id"]
                                    for member in existing_members}

                    # Filter out existing members
                    filtered_members = []
                    for member in members:
                        if member["id"] in existing_ids:
                            result["skipped"] += 1
                        else:
                            filtered_members.append(member)

                    members = filtered_members
                    logger.info("Skipping %d existing members in destination group",
                                result["skipped"])
                except Exception as e:
                    logger.warning("Couldn't get existing members, proceeding without skipping: %s",
                                   str(e))

            # Add members to destination group
            added_count, failed_count = await self.add_members_to_group(
                members, destination_group_id, delay
            )

            result["added"] = added_count
            result["failed"] = failed_count
            result["success"] = True

            logger.info("Transfer completed: %d extracted, %d added, %d skipped, %d failed",
                        result["extracted"], result["added"], result["skipped"], result["failed"])

            return result
        except (GroupNotFoundError, NotGroupAdminError, MemberExtractionError, MemberAdditionError) as e:
            logger.error("Failed to transfer members: %s", str(e))
            error_context = {
                "operation": "transfer_members",
                "source_group_id": source_group_id,
                "destination_group_id": destination_group_id
            }
            handle_error(e, error_context)

            result["error"] = str(e)
            return result

    async def get_group_info(self, group_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a group.

        Args:
            group_id (int): Group ID.

        Returns:
            Dict[str, Any]: Detailed group information.
        """
        if not self.client:
            logger.error("Client not initialized for get_group_info")
            return {"error": "Client not initialized"}

        try:
            # Get basic group information about the specified group
            group = await self.get_group_by_id(group_id)
            if not group:
                raise GroupNotFoundError(f"Group {group_id} not found")

            # Get additional permissions information for the group
            permissions = await self.check_group_permissions(group_id)

            # Combine information
            info = {
                **group,
                "permissions": permissions,
                "can_extract_members": True,  # Assume we can always extract members
                "can_add_members": permissions.get("can_add_members", False),
            }

            return info
        except (GroupNotFoundError, ValueError, TypeError, AttributeError) as e:
            logger.error("Failed to get group info for %d: %s",
                         group_id, str(e))
            error_context = {
                "operation": "get_group_info", "group_id": group_id}
            handle_error(e, error_context)
            return {"error": str(e)}

    def save_extracted_members(
        self,
        group_id: int,
        members: List[Dict[str, Any]],
        file_path: Optional[str] = None
    ) -> str:
        """
        Save extracted members to a file.

        Args:
            group_id (int): Group ID.
            members (List[Dict[str, Any]]): List of member info dictionaries.
            file_path (Optional[str]): Path to save the file. If None, generates a path.

        Returns:
            str: Path to the saved file.
        """
        if file_path is None:
            # Generate a filename based on group ID and timestamp
            timestamp = int(time.time())
            file_path = f"members_group_{group_id}_{timestamp}.json"

        try:
            # Ensure directory exists
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            # Save to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(members, f, indent=4, ensure_ascii=False)

            logger.info("Saved %d members to %s", len(members), file_path)
            return file_path
        except (IOError, ValueError, TypeError) as e:
            logger.error("Failed to save members to file %s: %s",
                         file_path, str(e))
            return ""

    def load_members_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load members from a file.

        Args:
            file_path (str): Path to the file.

        Returns:
            List[Dict[str, Any]]: List of member info dictionaries.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                members = json.load(f)

            logger.info("Loaded %d members from %s", len(members), file_path)
            return members
        except (IOError, json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to load members from file %s: %s",
                         file_path, str(e))
            return []

    async def get_group_stats(self, group_id: int) -> Dict[str, Any]:
        """
        Get statistics about a group.

        Args:
            group_id: ID of the group to analyze

        Returns:
            Dictionary containing various statistics about the group
            including total members, active members, bots, etc.
        """
        if not self.client:
            logger.error("Client not initialized for get_group_stats")
            return {"error": "Client not initialized"}

        try:
            # Get basic group information
            group = await self.get_group_by_id(group_id)
            if not group:
                raise GroupNotFoundError(f"Group {group_id} not found")

            # Extract members to analyze
            members = await self.extract_group_members(group_id)

            # Calculate various statistics about the group members
            total_members = len(members)

            # Count different member types
            bots_count = sum(1 for m in members if m.get("is_bot", False))
            deleted_count = sum(
                1 for m in members if m.get("is_deleted", False))

            # Count members with username or phone
            with_username = sum(1 for m in members if m.get("username"))
            with_phone = sum(1 for m in members if m.get("phone"))

            stats = {
                "group_id": group_id,
                "title": group.get("title", "Unknown"),
                "total_members": total_members,
                "bots_count": bots_count,
                "deleted_accounts": deleted_count,
                "with_username": with_username,
                "with_phone": with_phone,
                "active_members": total_members - deleted_count - bots_count,
            }

            return stats
        except (GroupNotFoundError, MemberExtractionError, ValueError, TypeError) as e:
            logger.error("Failed to get group stats for %d: %s",
                         group_id, str(e))
            error_context = {
                "operation": "get_group_stats", "group_id": group_id}
            handle_error(e, error_context)
            return {"error": str(e)}

    async def cleanup(self):
        """Clean up resources when manager is no longer needed."""
        # Clear caches
        self.groups_cache.clear()
        self.members_cache.clear()

        # Don't close the client here, as it might be shared with other components
        self.client = None
