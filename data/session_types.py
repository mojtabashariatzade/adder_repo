"""
Session Types Module

This module defines the fundamental types, enumerations, and constants used in the session
management system. It provides the basic building blocks for tracking session state
throughout the application.

Key components:
- SessionStatus: Enumeration of possible session statuses
- Session-related constants and default values
"""

from enum import Enum, auto


class SessionStatus(Enum):
    """Enumeration of possible session statuses."""

    # Initial status when a session is created
    CREATED = auto()

    # Session is actively running
    RUNNING = auto()

    # Session has been temporarily paused
    PAUSED = auto()

    # Session has been successfully completed
    COMPLETED = auto()

    # Session has failed due to an error
    FAILED = auto()

    # Session was interrupted unexpectedly
    INTERRUPTED = auto()

    # Session was recovered after an interruption
    RECOVERED = auto()

    @classmethod
    def to_str(cls, status) -> str:
        """
        Convert enum value to string representation.

        Args:
            status: The SessionStatus enum value

        Returns:
            str: String representation of the status
        """
        status_map = {
            cls.CREATED: "created",
            cls.RUNNING: "running",
            cls.PAUSED: "paused",
            cls.COMPLETED: "completed",
            cls.FAILED: "failed",
            cls.INTERRUPTED: "interrupted",
            cls.RECOVERED: "recovered"
        }
        return status_map.get(status, "unknown")

    @classmethod
    def from_str(cls, status_str: str) -> 'SessionStatus':
        """
        Convert string to enum value.

        Args:
            status_str (str): String representation of the status

        Returns:
            SessionStatus: The corresponding enum value or CREATED if not found
        """
        status_map = {
            "created": cls.CREATED,
            "running": cls.RUNNING,
            "paused": cls.PAUSED,
            "completed": cls.COMPLETED,
            "failed": cls.FAILED,
            "interrupted": cls.INTERRUPTED,
            "recovered": cls.RECOVERED
        }
        return status_map.get(status_str.lower(), cls.CREATED)


# Default values for session configuration
DEFAULT_AUTO_SAVE_INTERVAL = 60  # seconds
DEFAULT_MAX_HISTORY_SIZE = 100
DEFAULT_MAX_ACTIVE_SESSIONS = 50
DEFAULT_SESSIONS_DIR = "sessions"
DEFAULT_ARCHIVE_AGE_DAYS = 30

# Session serialization field names (to maintain consistency across modules)
SESSION_FIELDS = {
    "ID": "session_id",
    "TYPE": "session_type",
    "CREATED_AT": "created_at",
    "UPDATED_AT": "updated_at",
    "COMPLETED_AT": "completed_at",
    "STATUS": "status",
    "PROGRESS": "progress",
    "STATE": "state",
    "STATE_HISTORY": "state_history",
    "EVENT_LOG": "event_log",
    "METRICS": "metrics",
    "ERRORS": "errors",
    "RECOVERY_POINT": "recovery_point",
    "CUSTOM_DATA": "custom_data"
}
