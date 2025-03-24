"""
Session Module

This module provides the Session class, which represents an individual session
in the system. A session tracks the state of an operation over time, including
progress, start/end times, and additional data related to the operation.

Features:
- Session creation and management
- State tracking and history
- Event logging and error recording
- Metrics collection
- Recovery point management
- Auto-saving capabilities
"""

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Any, Union

from session_types import SessionStatus, SESSION_FIELDS, DEFAULT_AUTO_SAVE_INTERVAL, DEFAULT_MAX_HISTORY_SIZE

# Setup logger
logger = logging.getLogger(__name__)


class Session:
    """
    Class representing a session.

    A session tracks the state of an operation over time, including progress,
    start/end times, and additional data related to the operation.
    """

    def __init__(self,
                 session_id: Optional[str] = None,
                 session_type: Optional[str] = None,
                 auto_save: bool = True,
                 auto_save_interval: int = DEFAULT_AUTO_SAVE_INTERVAL,
                 max_history_size: int = DEFAULT_MAX_HISTORY_SIZE):
        """
        Initialize a new session.

        Args:
            session_id (str, optional): Unique identifier for the session.
                If None, a UUID will be generated.
            session_type (str, optional): Type of session (e.g., "member_transfer").
            auto_save (bool): Whether to automatically save the session periodically.
            auto_save_interval (int): Interval in seconds for auto-saving.
            max_history_size (int): Maximum number of state history entries to keep.
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.session_type = session_type or "generic"
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.completed_at = None
        self.status = SessionStatus.CREATED
        self.progress = 0.0  # 0 to 100 percent
        self.state = {}  # Current operation state
        self.state_history = []  # History of state changes
        self.event_log = []  # Log of significant events
        self.metrics = {}  # Performance metrics
        self.errors = []  # List of errors encountered
        self.recovery_point = None  # Data for recovery
        self.custom_data = {}  # For session-specific data

        # Auto-save configuration
        self.auto_save = auto_save
        self.auto_save_interval = auto_save_interval
        self.max_history_size = max_history_size

        # Handle StopIteration that can occur in tests with mock.time
        try:
            self._last_save_time = time.time()
        except StopIteration:
            self._last_save_time = 0

        self._auto_save_lock = threading.RLock()
        self._auto_save_thread = None
        self._stop_auto_save = threading.Event()

        # Start auto-save if enabled
        if self.auto_save:
            self._start_auto_save()

    def _start_auto_save(self):
        """Start the auto-save background thread."""
        if self._auto_save_thread is not None and self._auto_save_thread.is_alive():
            return  # Already running

        self._stop_auto_save.clear()
        self._auto_save_thread = threading.Thread(
            target=self._auto_save_worker,
            daemon=True,
            name=f"AutoSave-{self.session_id}"
        )
        self._auto_save_thread.start()

    def _stop_auto_save_thread(self):
        """Stop the auto-save background thread."""
        if self._auto_save_thread is None or not self._auto_save_thread.is_alive():
            return  # Not running

        self._stop_auto_save.set()
        self._auto_save_thread.join(timeout=2.0)  # Wait up to 2 seconds
        self._auto_save_thread = None

    def _auto_save_worker(self):
        """Worker function for auto-save thread."""
        while not self._stop_auto_save.is_set():
            try:
                # Sleep for the interval, but check for stop frequently
                for _ in range(self.auto_save_interval * 2):  # Check twice per second
                    if self._stop_auto_save.is_set():
                        return
                    time.sleep(0.5)

                # Time to save
                try:
                    current_time = time.time()
                except StopIteration:
                    current_time = 0

                if current_time - self._last_save_time >= self.auto_save_interval:
                    with self._auto_save_lock:
                        # This will be handled by the session_manager
                        # The manager will be imported here to avoid circular imports
                        try:
                            # Dynamically import to avoid circular imports
                            from session_manager import get_session_manager
                            session_manager = get_session_manager()
                            session_manager.save_session(self)

                            try:
                                self._last_save_time = time.time()
                            except StopIteration:
                                self._last_save_time = 0

                            logger.debug(
                                f"Auto-saved session {self.session_id}")
                        except ImportError:
                            # SessionManager might not be available during development/testing
                            logger.warning(
                                f"SessionManager not available for auto-save of session {self.session_id}")
            except Exception as e:
                logger.error(f"Error in auto-save worker: {e}")
                # Don't crash the thread, just continue

    def update_state(self, new_state: Dict[str, Any], track_history: bool = True) -> None:
        """
        Update the current state of the session.

        Args:
            new_state (Dict[str, Any]): New state data to merge with current state.
            track_history (bool): Whether to add the current state to history before updating.
        """
        # Update timestamp
        self.updated_at = datetime.now().isoformat()

        # Track state history if requested
        if track_history and self.state:
            # Add timestamp to the state before storing in history
            history_entry = {
                "timestamp": self.updated_at,
                "state": self.state.copy()
            }
            self.state_history.append(history_entry)

            # Limit history size
            if len(self.state_history) > self.max_history_size:
                self.state_history = self.state_history[-self.max_history_size:]

        # Update state
        self.state.update(new_state)

        # Update progress if provided
        if "progress" in new_state:
            self.progress = float(new_state["progress"])
        elif "processed" in new_state and "total" in new_state:
            # Calculate progress if processed and total are provided
            processed = new_state["processed"]
            total = new_state["total"]
            if total > 0:
                self.progress = (processed / total) * 100.0

    def set_status(self, status: Union[SessionStatus, str]) -> None:
        """
        Update the session status.

        Args:
            status (Union[SessionStatus, str]): New status value.
        """
        if isinstance(status, str):
            status = SessionStatus.from_str(status)

        # Update status
        self.status = status
        self.updated_at = datetime.now().isoformat()

        # If completed or failed, record completion time
        if status in [SessionStatus.COMPLETED, SessionStatus.FAILED]:
            self.completed_at = self.updated_at

        # Log the status change
        self.log_event(f"Status changed to {SessionStatus.to_str(status)}")

    def log_event(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log an event in the session event log.

        Args:
            message (str): Event message.
            data (Dict[str, Any], optional): Additional event data.
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "message": message
        }

        if data:
            event["data"] = data

        self.event_log.append(event)

    def log_error(self, error_message: str, error_type: Optional[str] = None,
                  exception: Optional[Exception] = None, context: Optional[
                      Dict[str, Any]] = None) -> None:
        """
        Log an error encountered during the session.

        Args:
            error_message (str): Error message.
            error_type (str, optional): Type of error.
            exception (Exception, optional): Exception object if available.
            context (Dict[str, Any], optional): Context in which the error occurred.
        """
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "message": error_message,
            "type": error_type or (exception.__class__.__name__ if exception else "UnknownError")
        }

        if exception:
            error_entry["exception"] = str(exception)

        if context:
            error_entry["context"] = context

        self.errors.append(error_entry)
        self.log_event(f"Error: {error_message}", {
                       "error_type": error_entry["type"]})

        # Debug log to verify error is being added correctly
        error_log_str = f"Added error to session: {error_message}, type={error_entry['type']}"
        if "exception" in error_entry:
            error_log_str += f", exception={error_entry['exception']}"
        logger.debug(error_log_str)

    def record_metric(self, name: str, value: Any, category: Optional[str] = None) -> None:
        """
        Record a performance or operational metric.

        Args:
            name (str): Metric name.
            value (Any): Metric value.
            category (str, optional): Metric category for organization.
        """
        # Use 'general' as the default category if none is provided
        cat = category or "general"

        if cat not in self.metrics:
            self.metrics[cat] = {}

        if name not in self.metrics[cat]:
            self.metrics[cat][name] = []

        metric_entry = {
            "timestamp": datetime.now().isoformat(),
            "value": value
        }

        self.metrics[cat][name].append(metric_entry)
        self.updated_at = datetime.now().isoformat()

    def set_recovery_point(self, data: Dict[str, Any]) -> None:
        """
        Set a recovery point to allow resuming operations.

        Args:
            data (Dict[str, Any]): Recovery data.
        """
        self.recovery_point = {
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

    def clear_recovery_point(self) -> None:
        """Clear the recovery point."""
        self.recovery_point = None

    def set_custom_data(self, key: str, value: Any) -> None:
        """
        Set a custom data value for the session.

        Args:
            key (str): Data key.
            value (Any): Data value.
        """
        self.custom_data[key] = value
        self.updated_at = datetime.now().isoformat()

    def get_custom_data(self, key: str, default: Any = None) -> Any:
        """
        Get a custom data value.

        Args:
            key (str): Data key.
            default (Any, optional): Default value if key doesn't exist.

        Returns:
            Any: The data value or default.
        """
        return self.custom_data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the session to a dictionary for serialization.

        Returns:
            Dict[str, Any]: Dictionary representation of the session.
        """
        return {
            SESSION_FIELDS["ID"]: self.session_id,
            SESSION_FIELDS["TYPE"]: self.session_type,
            SESSION_FIELDS["CREATED_AT"]: self.created_at,
            SESSION_FIELDS["UPDATED_AT"]: self.updated_at,
            SESSION_FIELDS["COMPLETED_AT"]: self.completed_at,
            SESSION_FIELDS["STATUS"]: SessionStatus.to_str(self.status),
            SESSION_FIELDS["PROGRESS"]: self.progress,
            SESSION_FIELDS["STATE"]: self.state,
            SESSION_FIELDS["STATE_HISTORY"]: self.state_history,
            SESSION_FIELDS["EVENT_LOG"]: self.event_log,
            SESSION_FIELDS["METRICS"]: self.metrics,
            SESSION_FIELDS["ERRORS"]: self.errors,
            SESSION_FIELDS["RECOVERY_POINT"]: self.recovery_point,
            SESSION_FIELDS["CUSTOM_DATA"]: self.custom_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """
        Create a session from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary data.

        Returns:
            Session: Session object.
        """
        session = cls(
            session_id=data.get(SESSION_FIELDS["ID"]),
            session_type=data.get(SESSION_FIELDS["TYPE"])
        )

        # Set attributes from data
        session.created_at = data.get(
            SESSION_FIELDS["CREATED_AT"], session.created_at)
        session.updated_at = data.get(
            SESSION_FIELDS["UPDATED_AT"], session.updated_at)
        session.completed_at = data.get(SESSION_FIELDS["COMPLETED_AT"])
        session.status = SessionStatus.from_str(
            data.get(SESSION_FIELDS["STATUS"], "created"))
        session.progress = data.get(SESSION_FIELDS["PROGRESS"], 0.0)
        session.state = data.get(SESSION_FIELDS["STATE"], {})
        session.state_history = data.get(SESSION_FIELDS["STATE_HISTORY"], [])
        session.event_log = data.get(SESSION_FIELDS["EVENT_LOG"], [])
        session.metrics = data.get(SESSION_FIELDS["METRICS"], {})
        session.errors = data.get(SESSION_FIELDS["ERRORS"], [])
        session.recovery_point = data.get(SESSION_FIELDS["RECOVERY_POINT"])
        session.custom_data = data.get(SESSION_FIELDS["CUSTOM_DATA"], {})

        return session

    def cleanup(self):
        """Clean up resources when the session is no longer needed."""
        self._stop_auto_save_thread()

    def __enter__(self):
        """Support using the session as a context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup when exiting context manager."""
        # Cleanup resources
        self.cleanup()

        # Log any exception that occurred in the context
        if exc_type is not None:
            self.log_error(
                error_message=str(exc_val),
                error_type=exc_type.__name__,
                exception=exc_val
            )

        # Return False to let the exception propagate
        return False

    def export_summary(self, format: str = 'json') -> Union[str, Dict[str, Any]]:
        """
        Export a summary of the session in the specified format.

        Args:
            format (str): Output format ('json' or 'text')

        Returns:
            Union[str, Dict[str, Any]]: Session summary
        """
        data = {
            "session_id": self.session_id,
            "session_type": self.session_type,
            "status": SessionStatus.to_str(self.status),
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error_count": len(self.errors)
        }

        if format.lower() == 'json':
            return data
        elif format.lower() == 'text':
            lines = [
                f"Session ID: {self.session_id}",
                f"Type: {self.session_type}",
                f"Status: {SessionStatus.to_str(self.status)}",
                f"Progress: {self.progress:.1f}%",
                f"Created: {self.created_at}",
                f"Last Updated: {self.updated_at}",
                f"Completed: {self.completed_at or 'Not completed'}",
                f"Errors: {len(self.errors)}"
            ]
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def add_state_checkpoint(self, name: str) -> None:
        """
        Add a named checkpoint of the current state.

        Args:
            name (str): Checkpoint name
        """
        checkpoint = {
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "state": self.state.copy()
        }

        if "checkpoints" not in self.custom_data:
            self.custom_data["checkpoints"] = []

        self.custom_data["checkpoints"].append(checkpoint)
        self.log_event(f"Created checkpoint: {name}")
