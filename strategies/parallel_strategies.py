"""
User Model Module

This module defines models for representing Telegram users and their details.
It provides structures for storing, validating, and managing user information
collected during member extraction and addition operations.

The module is a core component of the Telegram Adder system, enabling the
tracking and analysis of users from source groups before they are added
to target groups. It helps identify active and legitimate users, avoiding
bots and fake accounts.

Features:
- Storage of user identifiers, metadata, and statuses
- User activity and legitimacy analysis
- Classification of users based on activity patterns
- Serialization and deserialization for storage and transfer
- Analysis utilities for user data
- Integration with other system components
- Tag-based user categorization
- Analytics for user demographics and collection comparison

Classes:
- UserStatus: Enum defining possible user activity statuses
- User: Representation of a single Telegram user with analysis capabilities
- UserCollection: Container for managing multiple User objects with filtering and search
- UserAnalytics: Utility class for analyzing user collections

Helper Functions:
- get_users_from_file: Load users from a file into a UserCollection
- save_users_to_file: Save a UserCollection to a file
- filter_active_legitimate_users: Filter for users that are both active and legitimate
- add_tag_to_users: Add tags to users matching specific criteria

Usage:
    from models.user import User, UserStatus, UserCollection, UserAnalytics
    from models.user import get_users_from_file, filter_active_legitimate_users

    # Create a user from Telegram data
    user = User.from_telegram_user(telegram_user)

    # Check user status
    if user.is_active and not user.is_fake:
        # Use user in operations
        print(f"Valid user: {user.full_name}")

    # Create a collection and add users
    collection = UserCollection()
    collection.add(user)

    # Filter and analyze collections
    active_users = collection.filter(lambda u: u.is_active)
    stats = UserAnalytics.compute_activity_stats(active_users)

    # Load users from file, filter, and save results
    all_users = get_users_from_file("extracted_users.json")
    valid_users = filter_active_legitimate_users(all_users)
    save_users_to_file(valid_users, "valid_users.json")
"""

import json
import logging
import uuid
import time
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Union, Callable, Tuple
from pathlib import Path
import re

# Try to import from local modules, with fallbacks for development
try:
    from data.file_manager import JsonFileManager, FileReadError, FileWriteError
except ImportError:
    # For development use before the modules are fully implemented
    class JsonFileManager:
        def __init__(self, base_dir=None):
            pass

        def read_json(self, path, default=None):
            return default

        def write_json(self, path, data, make_backup=False):
            pass

    class FileReadError(Exception):
        pass

    class FileWriteError(Exception):
        pass

try:
    from logging_.logging_manager import get_logger
except ImportError:
    # Fallback logging setup
    def get_logger(name):
        return logging.getLogger(name)

# Setup logger
logger = get_logger("UserModel")


class UserStatus(Enum):
    """Enumeration of possible user statuses based on activity."""
    ACTIVE = auto()       # User is active and recently seen
    INACTIVE = auto()     # User has not been active recently
    ONLINE = auto()       # User is currently online
    RECENTLY = auto()     # User was seen recently (within a day)
    LAST_WEEK = auto()    # User was seen within the last week
    LAST_MONTH = auto()   # User was seen within the last month
    OFFLINE = auto()      # User is offline with last seen timestamp
    UNKNOWN = auto()      # User status is unknown or hidden

    @classmethod
    def to_str(cls, status):
        """Convert enum value to string representation."""
        status_map = {
            cls.ACTIVE: "active",
            cls.INACTIVE: "inactive",
            cls.ONLINE: "online",
            cls.RECENTLY: "recently",
            cls.LAST_WEEK: "last_week",
            cls.LAST_MONTH: "last_month",
            cls.OFFLINE: "offline",
            cls.UNKNOWN: "unknown"
        }
        return status_map.get(status, "unknown")

    @classmethod
    def from_str(cls, status_str):
        """Convert string to enum value."""
        status_map = {
            "active": cls.ACTIVE,
            "inactive": cls.INACTIVE,
            "online": cls.ONLINE,
            "recently": cls.RECENTLY,
            "last_week": cls.LAST_WEEK,
            "last_month": cls.LAST_MONTH,
            "offline": cls.OFFLINE,
            "unknown": cls.UNKNOWN
        }
        return status_map.get(status_str.lower(), cls.UNKNOWN)


class User:
    """
    Represents a Telegram user with relevant attributes and analytics.

    This class stores user information collected from Telegram and provides
    methods for analyzing user activity, legitimacy, and status. It includes
    functionality for determining if users are active, if they might be fake
    accounts, and for updating user data from Telegram API objects.

    Key features:
    - Storage of basic user attributes (ID, name, username, etc.)
    - Methods to analyze user legitimacy based on various heuristics
    - Activity status tracking and classification
    - Serialization and deserialization for persistence
    - Customizable metadata for application-specific uses
    - Tagging and note system for user categorization
    """

    def __init__(self,
                user_id: int,
                username: Optional[str] = None,
                first_name: Optional[str] = None,
                last_name: Optional[str] = None,
                phone: Optional[str] = None,
                status: UserStatus = UserStatus.UNKNOWN,
                last_seen: Optional[datetime] = None,
                is_bot: bool = False,
                is_verified: bool = False,
                has_photo: bool = False):
        """
        Initialize a User object with provided data.

        Args:
            user_id (int): Telegram user ID.
            username (Optional[str]): Telegram username if available.
            first_name (Optional[str]): User's first name.
            last_name (Optional[str]): User's last name.
            phone (Optional[str]): User's phone number if available.
            status (UserStatus): Current status of the user.
            last_seen (Optional[datetime]): Timestamp when user was last seen.
            is_bot (bool): Whether the user is a bot.
            is_verified (bool): Whether the user is verified by Telegram.
            has_photo (bool): Whether the user has a profile photo.
        """
        # Basic user attributes from Telegram
        self.user_id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.status = status
        self.last_seen = last_seen
        self.is_bot = is_bot
        self.is_verified = is_verified
        self.has_photo = has_photo

        # Additional attributes for analysis and tracking
        self.collected_at = datetime.now()
        self.analysis_results = {}
        self.metadata = {}
        self.fake_score = 0
        self.fake_reasons = []

        # Store the user's joining date if we know it
        self.joined_at = None

        # Custom application-specific flags and data
        self.tags = set()
        self.notes = []
        self.contact_attempts = 0
        self.last_contact = None
        self.response_rate = 0.0

        # Perform initial analysis if we have enough data
        if self.username or self.first_name or self.last_name:
            self._analyze_legitimacy()

    @property
    def full_name(self) -> str:
        """
        Get the full name of the user.

        Returns:
            str: Full name combining first and last name, or username if name is not available.
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        elif self.username:
            return self.username
        else:
            return f"User {self.user_id}"

    @property
    def display_name(self) -> str:
        """
        Get a display name for the user suitable for user interfaces.

        Returns:
            str: Display name with username if available.
        """
        base_name = self.full_name
        if self.username:
            return f"{base_name} (@{self.username})"
        return base_name

    @property
    def is_active(self) -> bool:
        """
        Determine if the user is considered active based on status.

        Returns:
            bool: True if user is active, False otherwise.
        """
        active_statuses = [
            UserStatus.ACTIVE,
            UserStatus.ONLINE,
            UserStatus.RECENTLY
        ]

        # Additionally check last_seen if available and status is OFFLINE
        if self.status == UserStatus.OFFLINE and self.last_seen:
            # Consider active if seen within the last 3 days
            return datetime.now() - self.last_seen < timedelta(days=3)

        return self.status in active_statuses

    @property
    def is_fake(self) -> bool:
        """
        Determine if the user is likely a fake account based on analysis.

        Returns:
            bool: True if user is likely fake, False otherwise.
        """
        # If we haven't analyzed yet, do it now
        if not self.fake_reasons and (self.username or self.first_name or self.last_name):
            self._analyze_legitimacy()

        # Consider fake if fake_score is 2 or higher or is a bot
        return self.fake_score >= 2 or self.is_bot

    def _analyze_legitimacy(self) -> None:
        """
        Analyze user attributes to determine if they are likely a legitimate user.

        This method calculates a fake_score and populates fake_reasons based on various
        heuristics like username patterns, name presence, and profile completeness.
        """
        self.fake_score = 0
        self.fake_reasons = []

        # Rule 1: Bot accounts are always considered fake
        if self.is_bot:
            self.fake_score += 3
            self.fake_reasons.append("Is a bot account")

        # Rule 2: Verified accounts are likely legitimate
        if self.is_verified:
            self.fake_score -= 3  # Significant negative score

        # Rule 3: Check username patterns if available
        if self.username:
            # Check for many digits (common in auto-generated usernames)
            if re.search(r'\d{4,}', self.username):
                self.fake_score += 1
                self.fake_reasons.append("Username contains many digits")

            # Check for random-looking username with no recognizable words
            if (re.match(r'[a-zA-Z0-9]{10,}$', self.username) and
                not re.match(r'[a-z]+', self.username.lower())):
                self.fake_score += 1
                self.fake_reasons.append("Username appears randomly generated")

        # Rule 4: Missing names
        if not self.first_name and not self.last_name:
            self.fake_score += 2
            self.fake_reasons.append("No name provided")

        # Rule 5: No profile photo
        if not self.has_photo:
            self.fake_score += 1
            self.fake_reasons.append("No profile photo")

        # Store analysis timestamp
        self.analysis_results["analyzed_at"] = datetime.now().isoformat()
        self.analysis_results["fake_score"] = self.fake_score
        self.analysis_results["fake_reasons"] = self.fake_reasons

    def update_status(self, status: Union[UserStatus, str], last_seen: Optional[datetime] = None) -> None:
        """
        Update the user's status and last seen timestamp.

        Args:
            status (Union[UserStatus, str]): New status to set.
            last_seen (Optional[datetime]): New last seen timestamp.
        """
        # Convert string status to enum if needed
        if isinstance(status, str):
            status = UserStatus.from_str(status)

        self.status = status

        # Only update last_seen if provided
        if last_seen is not None:
            self.last_seen = last_seen

        logger.debug(f"Updated user {self.user_id} status to {UserStatus.to_str(status)}")

        # Re-analyze legitimacy as status can affect it
        self._analyze_legitimacy()

    def update_from_telegram_user(self, telegram_user: Any) -> None:
        """
        Update user data from a Telegram user object.

        Args:
            telegram_user (Any): Telegram user object (from Telethon or another API wrapper).
        """
        # Update basic properties if available in the telegram_user object
        for attr in ["username", "first_name", "last_name", "phone"]:
            if hasattr(telegram_user, attr):
                setattr(self, attr, getattr(telegram_user, attr))

        # Update is_bot if available
        if hasattr(telegram_user, "bot"):
            self.is_bot = bool(telegram_user.bot)

        # Update is_verified if available
        if hasattr(telegram_user, "verified"):
            self.is_verified = bool(telegram_user.verified)

        # Update has_photo if available
        if hasattr(telegram_user, "photo"):
            self.has_photo = bool(telegram_user.photo)

        # Update status and last_seen based on telegram_user.status
        if hasattr(telegram_user, "status"):
            status = telegram_user.status

            if status is None:
                self.status = UserStatus.UNKNOWN
            elif hasattr(status, "__class__") and "UserStatusOnline" in status.__class__.__name__:
                self.status = UserStatus.ONLINE
            elif hasattr(status, "__class__") and "UserStatusRecently" in status.__class__.__name__:
                self.status = UserStatus.RECENTLY
            elif hasattr(status, "__class__") and "UserStatusLastWeek" in status.__class__.__name__:
                self.status = UserStatus.LAST_WEEK
            elif hasattr(status, "__class__") and "UserStatusLastMonth" in status.__class__.__name__:
                self.status = UserStatus.LAST_MONTH
            elif hasattr(status, "__class__") and "UserStatusOffline" in status.__class__.__name__:
                self.status = UserStatus.OFFLINE
                # Extract last_seen timestamp if available
                if hasattr(status, "was_online"):
                    self.last_seen = status.was_online
            else:
                self.status = UserStatus.UNKNOWN

        # Re-analyze legitimacy with updated data
        self._analyze_legitimacy()

        logger.debug(f"Updated user {self.user_id} from Telegram user data")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the user object to a dictionary for serialization.

        Returns:
            Dict[str, Any]: Dictionary representation of the user.
        """
        user_dict = {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "status": UserStatus.to_str(self.status),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_bot": self.is_bot,
            "is_verified": self.is_verified,
            "has_photo": self.has_photo,
            "collected_at": self.collected_at.isoformat(),
            "analysis_results": self.analysis_results,
            "metadata": self.metadata,
            "fake_score": self.fake_score,
            "fake_reasons": self.fake_reasons,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "tags": list(self.tags),
            "notes": self.notes,
            "contact_attempts": self.contact_attempts,
            "last_contact": self.last_contact.isoformat() if self.last_contact else None,
            "response_rate": self.response_rate
        }
        return user_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """
        Create a User object from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary containing user data.

        Returns:
            User: Instantiated User object.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        # Extract required fields with defaults for optional ones
        user_id = data.get("user_id")
        if not user_id:
            raise ValueError("User ID is required")

        # Create User instance with basic data
        user = cls(
            user_id=user_id,
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            phone=data.get("phone"),
            status=UserStatus.from_str(data.get("status", "unknown")),
            is_bot=data.get("is_bot", False),
            is_verified=data.get("is_verified", False),
            has_photo=data.get("has_photo", False)
        )

        # Set last_seen if available
        if data.get("last_seen"):
            try:
                user.last_seen = datetime.fromisoformat(data["last_seen"])
            except (ValueError, TypeError):
                logger.warning(f"Invalid last_seen format in user data: {data['last_seen']}")

        # Set collected_at if available
        if data.get("collected_at"):
            try:
                user.collected_at = datetime.fromisoformat(data["collected_at"])
            except (ValueError, TypeError):
                logger.warning(f"Invalid collected_at format in user data: {data['collected_at']}")

        # Set analysis data
        user.analysis_results = data.get("analysis_results", {})
        user.metadata = data.get("metadata", {})
        user.fake_score = data.get("fake_score", 0)
        user.fake_reasons = data.get("fake_reasons", [])

        # Set extended attributes
        if data.get("joined_at"):
            try:
                user.joined_at = datetime.fromisoformat(data["joined_at"])
            except (ValueError, TypeError):
                logger.warning(f"Invalid joined_at format in user data: {data['joined_at']}")

        user.tags = set(data.get("tags", []))
        user.notes = data.get("notes", [])
        user.contact_attempts = data.get("contact_attempts", 0)

        if data.get("last_contact"):
            try:
                user.last_contact = datetime.fromisoformat(data["last_contact"])
            except (ValueError, TypeError):
                logger.warning(f"Invalid last_contact format in user data: {data['last_contact']}")

        user.response_rate = data.get("response_rate", 0.0)

        return user

    @classmethod
    def from_telegram_user(cls, telegram_user: Any) -> 'User':
        """
        Create a User object from a Telegram user object.

        Args:
            telegram_user (Any): Telegram user object from Telethon or another API wrapper.

        Returns:
            User: Instantiated User object with data from the Telegram user.
        """
        # Extract user_id, which is required
        if not hasattr(telegram_user, "id"):
            raise ValueError("Telegram user object must have an 'id' attribute")

        user_id = telegram_user.id

        # Create basic user
        user = cls(user_id=user_id)

        # Update with Telegram data
        user.update_from_telegram_user(telegram_user)

        return user

    def __eq__(self, other: Any) -> bool:
        """
        Compare two User objects for equality.

        Args:
            other (Any): Another object to compare with.

        Returns:
            bool: True if both are User objects with the same user_id.
        """
        if not isinstance(other, User):
            return False
        return self.user_id == other.user_id

    def __hash__(self) -> int:
        """
        Generate a hash for the User object based on user_id.

        Returns:
            int: Hash value.
        """
        return hash(self.user_id)

    def __str__(self) -> str:
        """
        Get a string representation of the User.

        Returns:
            str: String representation including name and username.
        """
        return self.display_name

    def __repr__(self) -> str:
        """
        Get a detailed string representation of the User.

        Returns:
            str: Detailed representation including ID and status.
        """
        return f"User(id={self.user_id}, name='{self.full_name}', status={UserStatus.to_str(self.status)})"


class UserCollection:
    """
    Manages a collection of User objects with search, filtering, and persistence capabilities.

    This class provides a container for User objects with utilities for adding, removing,
    searching, and filtering users. It also supports loading and saving collections to files.

    The collection maintains internal indexes for efficient lookup by user ID and username,
    while avoiding duplicates through the use of a set-based storage mechanism.
    """

    def __init__(self, users: Optional[List[User]] = None):
        """
        Initialize a UserCollection with optional initial users.

        Args:
            users (Optional[List[User]]): Initial list of users to add to the collection.
        """
        # Main storage is a set for fast membership testing and avoiding duplicates
        self._users = set()

        # Indexes for fast lookups
        self._users_by_id = {}          # Lookup by user_id
        self._users_by_username = {}    # Lookup by username (lowercase)

        # Add initial users if provided
        if users:
            for user in users:
                self.add(user)

        # Initialize file manager for persistence operations
        self.file_manager = JsonFileManager()

    def add(self, user: User) -> bool:
        """
        Add a user to the collection.

        Adds a user to the internal set and updates the ID and username indexes
        for fast lookups. Ensures no duplicates are added.

        Args:
            user (User): User object to add.

        Returns:
            bool: True if user was added, False if already exists.
        """
        if user in self._users:
            return False

        self._users.add(user)
        self._users_by_id[user.user_id] = user

        if user.username:
            self._users_by_username[user.username.lower()] = user

        return True

    def remove(self, user: Union[User, int, str]) -> bool:
        """
        Remove a user from the collection.

        Args:
            user (Union[User, int, str]): User object, user ID, or username to remove.

        Returns:
            bool: True if user was removed, False if not found.
        """
        found_user = self.get(user)

        if not found_user:
            return False

        self._users.remove(found_user)

        if found_user.user_id in self._users_by_id:
            del self._users_by_id[found_user.user_id]

        if found_user.username and found_user.username.lower() in self._users_by_username:
            del self._users_by_username[found_user.username.lower()]

        return True

    def get(self, user_identifier: Union[User, int, str]) -> Optional[User]:
        """
        Get a user from the collection.

        Args:
            user_identifier (Union[User, int, str]): User object, user ID, or username to get.

        Returns:
            Optional[User]: User object if found, None otherwise.
        """
        # If already a User object, check if it's in the collection
        if isinstance(user_identifier, User):
            return user_identifier if user_identifier in self._users else None

        # If integer, look up by ID
        if isinstance(user_identifier, int):
            return self._users_by_id.get(user_identifier)

        # If string, look up by username
        if isinstance(user_identifier, str):
            return self._users_by_username.get(user_identifier.lower())

        return None

    def filter(self, predicate: Callable[[User], bool]) -> 'UserCollection':
        """
        Filter users based on a predicate function.

        Args:
            predicate (Callable[[User], bool]): Function that takes a User and returns True to include.

        Returns:
            UserCollection: New collection with filtered users.

        Example:
            # Get all users with usernames containing 'test'
            test_users = collection.filter(lambda user: user.username and 'test' in user.username)

            # Get all non-bot users who were active in the last week
            recent_real_users = collection.filter(
                lambda user: not user.is_bot and user.status in [UserStatus.ONLINE, UserStatus.RECENTLY]
            )
        """
        filtered_users = [user for user in self._users if predicate(user)]
        return UserCollection(filtered_users)

    def search(self, query: str) -> 'UserCollection':
        """
        Search for users by name or username.

        Args:
            query (str): Search string to match against user names and usernames.

        Returns:
            UserCollection: New collection with matching users.
        """
        query = query.lower().strip()

        if not query:
            return UserCollection()

        matches = []

        for user in self._users:
            if (user.username and query in user.username.lower() or
                user.first_name and query in user.first_name.lower() or
                user.last_name and query in user.last_name.lower()):
                matches.append(user)

        return UserCollection(matches)

    def active_users(self) -> 'UserCollection':
        """
        Get all active users in the collection.

        Returns:
            UserCollection: New collection with active users.
        """
        return self.filter(lambda user: user.is_active)

    def legitimate_users(self) -> 'UserCollection':
        """
        Get all users that are considered legitimate (not fake or bots).

        Returns:
            UserCollection: New collection with legitimate users.
        """
        return self.filter(lambda user: not user.is_fake)

    def save(self, file_path: Union[str, Path]) -> bool:
        """
        Save the user collection to a JSON file.

        Args:
            file_path (Union[str, Path]): Path to save the collection to.

        Returns:
            bool: True if saved successfully, False otherwise.
        """
        try:
            # Convert users to dictionaries
            users_data = [user.to_dict() for user in self._users]

            # Add metadata
            data = {
                "metadata": {
                    "count": len(users_data),
                    "active_count": len(self.active_users()),
                    "legitimate_count": len(self.legitimate_users()),
                    "exported_at": datetime.now().isoformat()
                },
                "users": users_data
            }

            # Save to file
            self.file_manager.write_json(file_path, data)
            logger.info(f"Saved {len(users_data)} users to {file_path}")
            return True

        except (FileWriteError, Exception) as e:
            logger.error(f"Failed to save user collection to {file_path}: {e}")
            return False

    @classmethod
    def load(cls, file_path: Union[str, Path]) -> 'UserCollection':
        """
        Load a user collection from a JSON file.

        Args:
            file_path (Union[str, Path]): Path to load the collection from.

        Returns:
            UserCollection: Loaded user collection.

        Raises:
            FileReadError: If the file cannot be read.
            ValueError: If the file contains invalid data.
        """
        try:
            file_manager = JsonFileManager()
            data = file_manager.read_json(file_path)

            if not data or "users" not in data:
                raise ValueError(f"Invalid user collection data in {file_path}")

            # Create users from data
            users = []
            for user_data in data["users"]:
                try:
                    user = User.from_dict(user_data)
                    users.append(user)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping invalid user data: {e}")

            collection = cls(users)
            logger.info(f"Loaded {len(users)} users from {file_path}")
            return collection

        except FileReadError as e:
            logger.error(f"Failed to read user collection from {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading user collection: {e}")
            raise ValueError(f"Invalid user collection data: {e}")

    def merge(self, other: 'UserCollection', overwrite: bool = True) -> int:
        """
        Merge another user collection into this one.

        Args:
            other (UserCollection): Collection to merge into this one.
            overwrite (bool): Whether to overwrite existing users with new data.

        Returns:
            int: Number of users added or updated.
        """
        count = 0

        for user in other:
            existing = self.get(user.user_id)

            if not existing:
                # New user, add it
                self.add(user)
                count += 1
            elif overwrite:
                # Existing user, update it
                self.remove(existing)
                self.add(user)
                count += 1

        return count

    def to_list(self) -> List[User]:
        """
        Convert the collection to a list of users.

        Returns:
            List[User]: List containing all users in the collection.
        """
        return list(self._users)

    def __len__(self) -> int:
        """
        Get the number of users in the collection.

        Returns:
            int: Number of users.
        """
        return len(self._users)

    def __iter__(self):
        """
        Get an iterator over the users in the collection.

        Returns:
            Iterator: Iterator over User objects.
        """
        return iter(self._users)

    def __contains__(self, user: Union[User, int, str]) -> bool:
        """
        Check if a user is in the collection.

        Args:
            user (Union[User, int, str]): User object, user ID, or username to check.

        Returns:
            bool: True if the user is in the collection, False otherwise.
        """
        return self.get(user) is not None


class UserAnalytics:
    """
    Provides analytical functions for user data.

    This class offers utilities for analyzing collections of users, extracting
    statistics, and identifying patterns in user data. It can be used to
    generate reports on user activity, legitimacy, and demographic information.
    """

    @staticmethod
    def compute_activity_stats(collection: UserCollection) -> Dict[str, Any]:
        """
        Compute statistics about user activity in a collection.

        Analyzes the activity levels of users in the collection, including
        the distribution of different status types and the proportion of
        active vs. inactive users.

        Args:
            collection (UserCollection): Collection to analyze.

        Returns:
            Dict[str, Any]: Dictionary with activity statistics including:
                - total_users: Total number of users in the collection
                - active_count: Number of active users
                - active_percentage: Percentage of active users
                - inactive_count: Number of inactive users
                - inactive_percentage: Percentage of inactive users
                - status_distribution: Distribution of different status types
        """
        total = len(collection)
        if total == 0:
            return {
                "total_users": 0,
                "active_count": 0,
                "active_percentage": 0,
                "inactive_count": 0,
                "inactive_percentage": 0,
                "status_distribution": {}
            }

        active_users = collection.active_users()
        active_count = len(active_users)

        # Calculate status distribution
        status_counts = {}
        for user in collection:
            status = UserStatus.to_str(user.status)
            status_counts[status] = status_counts.get(status, 0) + 1

        # Convert counts to percentages
        status_distribution = {
            status: {
                "count": count,
                "percentage": (count / total) * 100
            }
            for status, count in status_counts.items()
        }

def get_users_from_file(file_path: Union[str, Path]) -> UserCollection:
    """
    Load users from a file and create a UserCollection.

    This is a convenience function that wraps UserCollection.load().

    Args:
        file_path (Union[str, Path]): Path to the file containing user data.

    Returns:
        UserCollection: Collection containing the loaded users.

    Raises:
        FileReadError: If the file cannot be read.
        ValueError: If the file contains invalid data.
    """
    return UserCollection.load(file_path)


def save_users_to_file(collection: UserCollection, file_path: Union[str, Path]) -> bool:
    """
    Save a UserCollection to a file.

    This is a convenience function that wraps collection.save().

    Args:
        collection (UserCollection): Collection to save.
        file_path (Union[str, Path]): Path where to save the collection.

    Returns:
        bool: True if the collection was saved successfully, False otherwise.
    """
    return collection.save(file_path)


def filter_active_legitimate_users(collection: UserCollection) -> UserCollection:
    """
    Filter out inactive or fake users from a collection.

    This is a convenience function that combines filtering for active and legitimate users.

    Args:
        collection (UserCollection): Collection to filter.

    Returns:
        UserCollection: Filtered collection containing only active, legitimate users.
    """
    return collection.filter(lambda user: user.is_active and not user.is_fake)


def add_tag_to_users(collection: UserCollection, tag: str,
                   predicate: Optional[Callable[[User], bool]] = None) -> int:
    """
    Add a tag to users in a collection, optionally filtering with a predicate.

    Args:
        collection (UserCollection): Collection containing users to tag.
        tag (str): Tag to add to the users.
        predicate (Optional[Callable[[User], bool]]): Function that takes a User and
            returns True for users that should receive the tag. If None, tag all users.

    Returns:
        int: Number of users that were tagged.
    """
    count = 0

    for user in collection:
        if predicate is None or predicate(user):
            user.tags.add(tag)
            count += 1

    return count

    @staticmethod
    def compute_legitimacy_stats(collection: UserCollection) -> Dict[str, Any]:
        """
        Compute statistics about user legitimacy in a collection.

        Analyzes the proportion of legitimate users vs. fake accounts and bots,
        and summarizes common indicators of fake accounts.

        Args:
            collection (UserCollection): Collection to analyze.

        Returns:
            Dict[str, Any]: Dictionary with legitimacy statistics including:
                - total_users: Total number of users in the collection
                - legitimate_count: Number of legitimate users
                - legitimate_percentage: Percentage of legitimate users
                - fake_count: Number of fake users
                - fake_percentage: Percentage of fake users
                - bot_count: Number of bot accounts
                - bot_percentage: Percentage of bot accounts
                - common_fake_reasons: List of common reasons for marking as fake
                - analyzed_at: Timestamp of analysis
        """
        total = len(collection)
        if total == 0:
            return {
                "total_users": 0,
                "legitimate_count": 0,
                "legitimate_percentage": 0,
                "fake_count": 0,
                "fake_percentage": 0,
                "bot_count": 0,
                "bot_percentage": 0,
                "common_fake_reasons": []
            }

        legitimate_users = collection.legitimate_users()
        legitimate_count = len(legitimate_users)

        # Count bots and fake accounts
        bot_count = sum(1 for user in collection if user.is_bot)
        fake_count = sum(1 for user in collection if user.is_fake)

        # Analyze fake reasons
        all_reasons = []
        for user in collection:
            all_reasons.extend(user.fake_reasons)

        # Count occurrences of each reason
        reason_counts = {}
        for reason in all_reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        # Sort by frequency
        common_reasons = sorted(
            [{"reason": reason, "count": count} for reason, count in reason_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )

    @staticmethod
    def generate_profile_report(user: User) -> Dict[str, Any]:
        """
        Generate a detailed profile report for a single user.

        Creates a comprehensive report of a user's attributes, activity, and legitimacy analysis.

        Args:
            user (User): User to generate report for.

        Returns:
            Dict[str, Any]: Detailed user profile report including:
                - basic_info: Basic user information (name, ID, username)
                - activity_info: Activity status and history
                - legitimacy_analysis: Detailed assessment of user legitimacy
                - metadata: Additional metadata about the user
        """
        now = datetime.now()

        # Calculate time since collection
        time_since_collection = None
        if user.collected_at:
            collection_diff = now - user.collected_at
            days = collection_diff.days
            hours = collection_diff.seconds // 3600
            minutes = (collection_diff.seconds % 3600) // 60
            time_since_collection = f"{days}d {hours}h {minutes}m"

        # Calculate time since last seen
        time_since_last_seen = None
        if user.last_seen:
            last_seen_diff = now - user.last_seen
            days = last_seen_diff.days
            hours = last_seen_diff.seconds // 3600
            minutes = (last_seen_diff.seconds % 3600) // 60
            time_since_last_seen = f"{days}d {hours}h {minutes}m"

        # Create profile report
        report = {
            "basic_info": {
                "user_id": user.user_id,
                "username": user.username,
                "full_name": user.full_name,
                "display_name": user.display_name,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone
            },
            "activity_info": {
                "status": UserStatus.to_str(user.status),
                "is_active": user.is_active,
                "last_seen": user.last_seen.isoformat() if user.last_seen else None,
                "time_since_last_seen": time_since_last_seen,
                "collected_at": user.collected_at.isoformat() if user.collected_at else None,
                "time_since_collection": time_since_collection
            },
            "legitimacy_analysis": {
                "is_bot": user.is_bot,
                "is_verified": user.is_verified,
                "has_photo": user.has_photo,
                "fake_score": user.fake_score,
                "is_fake": user.is_fake,
                "fake_reasons": user.fake_reasons,
                "assessment": "Legitimate" if not user.is_fake else "Suspicious",
                "confidence": "High" if user.fake_score > 3 or user.fake_score < -2 else "Medium" if user.fake_score >= 2 or user.fake_score <= -1 else "Low"
            },
            "metadata": user.metadata,
            "generated_at": now.isoformat()
        }

        return report

    @staticmethod
    def extract_demographics(collection: UserCollection) -> Dict[str, Any]:
        """
        Extract demographic information from a user collection.

        Analyzes patterns in usernames, name formats, and other characteristics
        to determine demographic distribution.

        Args:
            collection (UserCollection): Collection to analyze.

        Returns:
            Dict[str, Any]: Demographic statistics.
        """
        # Not a complete implementation - would require more advanced NLP methods
        # for accurate demographic analysis. This is just a placeholder.

        # Count users with names vs. unnamed users
        named_users = 0
        unnamed_users = 0

        for user in collection:
            if user.first_name or user.last_name:
                named_users += 1
            else:
                unnamed_users += 1

        # Count various username patterns
        usernames_with_year = 0
        usernames_with_name = 0

        year_pattern = re.compile(r'(19|20)\d{2}')

        for user in collection:
            if not user.username:
                continue

            if year_pattern.search(user.username):
                usernames_with_year += 1

            # Very basic name detection - would need NLP for better results
            if user.first_name and user.first_name.lower() in user.username.lower():
                usernames_with_name += 1

        return {
            "total_users": len(collection),
            "named_users": named_users,
            "unnamed_users": unnamed_users,
            "named_percentage": (named_users / len(collection) * 100) if len(collection) > 0 else 0,
            "username_patterns": {
                "with_year": usernames_with_year,
                "with_name": usernames_with_name
            },
            "analyzed_at": datetime.now().isoformat()
        }

    @staticmethod
    def compare_collections(collection1: UserCollection, collection2: UserCollection,
                          name1: str = "Collection 1", name2: str = "Collection 2") -> Dict[str, Any]:
        """
        Compare two user collections and generate comparative statistics.

        Args:
            collection1 (UserCollection): First collection to compare.
            collection2 (UserCollection): Second collection to compare.
            name1 (str): Name for the first collection in the report.
            name2 (str): Name for the second collection in the report.

        Returns:
            Dict[str, Any]: Comparison statistics.
        """
        # Get sets of user IDs for comparison
        ids1 = set(user.user_id for user in collection1)
        ids2 = set(user.user_id for user in collection2)

        # Calculate overlap and exclusive sets
        common_ids = ids1.intersection(ids2)
        only_in_1 = ids1 - ids2
        only_in_2 = ids2 - ids1

        # Compute activity and legitimacy stats for each collection
        stats1 = UserAnalytics.compute_activity_stats(collection1)
        stats2 = UserAnalytics.compute_activity_stats(collection2)

        legit_stats1 = UserAnalytics.compute_legitimacy_stats(collection1)
        legit_stats2 = UserAnalytics.compute_legitimacy_stats(collection2)

        return {
            "collection_sizes": {
                name1: len(collection1),
                name2: len(collection2),
                "difference": len(collection1) - len(collection2),
                "ratio": len(collection1) / len(collection2) if len(collection2) > 0 else float('inf')
            },
            "overlap": {
                "common_users": len(common_ids),
                "overlap_percentage": (len(common_ids) / len(ids1.union(ids2)) * 100) if ids1.union(ids2) else 0,
                "only_in_first": len(only_in_1),
                "only_in_second": len(only_in_2)
            },
            "activity_comparison": {
                name1: {
                    "active_percentage": stats1["active_percentage"],
                    "status_distribution": stats1["status_distribution"]
                },
                name2: {
                    "active_percentage": stats2["active_percentage"],
                    "status_distribution": stats2["status_distribution"]
                },
                "active_difference": stats1["active_percentage"] - stats2["active_percentage"]
            },
            "legitimacy_comparison": {
                name1: {
                    "legitimate_percentage": legit_stats1["legitimate_percentage"],
                    "fake_percentage": legit_stats1["fake_percentage"],
                    "bot_percentage": legit_stats1["bot_percentage"]
                },
                name2: {
                    "legitimate_percentage": legit_stats2["legitimate_percentage"],
                    "fake_percentage": legit_stats2["fake_percentage"],
                    "bot_percentage": legit_stats2["bot_percentage"]
                },
                "legitimacy_difference": legit_stats1["legitimate_percentage"] - legit_stats2["legitimate_percentage"]
            },
            "compared_at": datetime.now().isoformat()
        }