"""
Base Strategy Module

This module defines the base class for all operation strategies in the Telegram Account Manager.
It provides a common interface and shared functionality for different execution strategies,
such as sequential or parallel member transfer operations.

Features:
- Abstract base class for all strategy implementations
- State management for operations (created, running, paused, completed, failed)
- Progress tracking and reporting
- Session integration for persistence and recovery
- Event hooks for extensibility
- Comprehensive error handling and logging

Usage:
    from strategies.base_strategy import BaseStrategy, StrategyState

    class MyCustomStrategy(BaseStrategy):
        def _execute_implementation(self):
            # Custom implementation here
            pass

        def _validate_requirements(self):
            # Custom validation logic
            return True, []

    # Using the strategy
    strategy = MyCustomStrategy(
        source_group="source_group_id",
        target_group="target_group_id",
        member_limit=50
    )

    # Execute with progress callback
    strategy.execute(progress_callback=my_progress_callback)
"""

import abc
import logging
import time
import threading
import uuid
from enum import Enum, auto
from typing import Optional, Callable, Dict, Any, List, Tuple, Union
from datetime import datetime

# Import custom modules
try:
    # Core modules
    from core.exceptions import (
        StrategyError, StrategyExecutionError,
        StrategyNotFoundError, OperationError
    )

    # Data management
    from data.session_manager import SessionManager, Session, SessionStatus

    # Services (these will be used in concrete strategy implementations)
    from services.account_manager import AccountManager
    from services.analytics import AnalyticsService

except ImportError:
    # For standalone testing or development before other modules are available
    # Define mock classes for testing
    class StrategyError(Exception):
        """Base exception for all strategy-related errors."""
        pass

    class StrategyExecutionError(StrategyError):
        """Raised when a strategy execution fails."""
        pass

    class StrategyNotFoundError(StrategyError):
        """Raised when a requested strategy is not found."""
        pass

    class OperationError(Exception):
        """Base exception for all operation-related errors."""
        pass

    class SessionManager:
        """Mock SessionManager class."""
        @staticmethod
        def get_session_manager():
            return SessionManager()

        def create_session(self, *args, **kwargs):
            return Session()

    class Session:
        """Mock Session class."""
        def update_state(self, *args, **kwargs):
            pass

        def log_event(self, *args, **kwargs):
            pass

    class SessionStatus(Enum):
        """Mock session status enum."""
        RUNNING = auto()
        PAUSED = auto()
        COMPLETED = auto()
        FAILED = auto()

    class AccountManager:
        """Mock AccountManager class."""
        pass

    class AnalyticsService:
        """Mock AnalyticsService class."""
        pass


# Get logger for this module
logger = logging.getLogger(__name__)


class StrategyState(Enum):
    """
    Enumeration of possible strategy states.

    These states represent the lifecycle of a strategy from creation to completion.
    """
    CREATED = auto()      # Strategy has been created but not started
    VALIDATING = auto()   # Strategy is validating requirements
    INITIALIZING = auto() # Strategy is initializing resources
    RUNNING = auto()      # Strategy is actively running
    PAUSING = auto()      # Strategy is in the process of pausing
    PAUSED = auto()       # Strategy execution is paused
    RESUMING = auto()     # Strategy is resuming from a paused state
    COMPLETING = auto()   # Strategy is in the final stages of completion
    COMPLETED = auto()    # Strategy has completed successfully
    FAILING = auto()      # Strategy is in the process of failing
    FAILED = auto()       # Strategy has failed
    CANCELLING = auto()   # Strategy is in the process of being cancelled
    CANCELLED = auto()    # Strategy was cancelled by the user
    RECOVERING = auto()   # Strategy is recovering from a previous state

    @classmethod
    def to_str(cls, state):
        """Convert enum value to string representation."""
        state_map = {
            cls.CREATED: "created",
            cls.VALIDATING: "validating",
            cls.INITIALIZING: "initializing",
            cls.RUNNING: "running",
            cls.PAUSING: "pausing",
            cls.PAUSED: "paused",
            cls.RESUMING: "resuming",
            cls.COMPLETING: "completing",
            cls.COMPLETED: "completed",
            cls.FAILING: "failing",
            cls.FAILED: "failed",
            cls.CANCELLING: "cancelling",
            cls.CANCELLED: "cancelled",
            cls.RECOVERING: "recovering"
        }
        return state_map.get(state, "unknown")

    @classmethod
    def from_str(cls, state_str):
        """Convert string to enum value."""
        state_map = {
            "created": cls.CREATED,
            "validating": cls.VALIDATING,
            "initializing": cls.INITIALIZING,
            "running": cls.RUNNING,
            "pausing": cls.PAUSING,
            "paused": cls.PAUSED,
            "resuming": cls.RESUMING,
            "completing": cls.COMPLETING,
            "completed": cls.COMPLETED,
            "failing": cls.FAILING,
            "failed": cls.FAILED,
            "cancelling": cls.CANCELLING,
            "cancelled": cls.CANCELLED,
            "recovering": cls.RECOVERING
        }
        return state_map.get(state_str.lower(), cls.CREATED)

    @classmethod
    def is_terminal_state(cls, state):
        """Check if a state is terminal (no further execution possible)."""
        return state in [cls.COMPLETED, cls.FAILED, cls.CANCELLED]

    @classmethod
    def is_active_state(cls, state):
        """Check if a state indicates active execution."""
        return state in [cls.RUNNING, cls.VALIDATING, cls.INITIALIZING,
                        cls.PAUSING, cls.RESUMING, cls.COMPLETING,
                        cls.FAILING, cls.CANCELLING, cls.RECOVERING]


class BaseStrategy(abc.ABC):
    """
    Abstract base class for all operation strategies.

    This class defines the common interface and shared functionality for different
    execution strategies, such as sequential or parallel member transfer operations.

    Subclasses must implement the abstract methods to provide specific functionality.
    """

    def __init__(self,
                 strategy_id: Optional[str] = None,
                 strategy_type: Optional[str] = None,
                 source_group: Optional[str] = None,
                 target_group: Optional[str] = None,
                 member_limit: int = 20,
                 max_retries: int = 3,
                 delay_between_operations: float = 20.0,
                 auto_retry: bool = True,
                 session: Optional[Session] = None):
        """
        Initialize the strategy.

        Args:
            strategy_id (str, optional): Unique identifier for this strategy.
                If None, a UUID will be generated.
            strategy_type (str, optional): Type of strategy (e.g., "sequential", "parallel").
                If None, will use the class name.
            source_group (str, optional): Identifier for the source group.
            target_group (str, optional): Identifier for the target group.
            member_limit (int): Maximum number of members to process.
            max_retries (int): Maximum number of retry attempts.
            delay_between_operations (float): Delay between operations in seconds.
            auto_retry (bool): Whether to automatically retry failed operations.
            session (Session, optional): Session object for persistence.
                If None, a new session will be created.
        """
        # Basic strategy information
        self.strategy_id = strategy_id or str(uuid.uuid4())
        self.strategy_type = strategy_type or self.__class__.__name__

        # Operation parameters
        self.source_group = source_group
        self.target_group = target_group
        self.member_limit = member_limit
        self.max_retries = max_retries
        self.delay_between_operations = delay_between_operations
        self.auto_retry = auto_retry

        # Execution state
        self.state = StrategyState.CREATED
        self.start_time = None
        self.end_time = None
        self.pause_time = None
        self.total_pause_duration = 0.0

        # Progress tracking
        self.total_items = 0
        self.processed_items = 0
        self.successful_items = 0
        self.failed_items = 0
        self.retried_items = 0
        self.current_item = None

        # Error tracking
        self.errors = []
        self.last_error = None

        # Execution control
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._execution_thread = None
        self._lock = threading.RLock()

        # Session management
        self.session = session
        self._initialize_session()

        # Callback for progress updates
        self.progress_callback = None

        # Hooks dictionary for extensibility
        self.hooks = {
            'pre_execute': [],
            'post_execute': [],
            'pre_item_process': [],
            'post_item_process': [],
            'on_error': [],
            'on_retry': [],
            'on_pause': [],
            'on_resume': [],
            'on_cancel': [],
            'on_complete': [],
            'on_fail': []
        }

        # Log initialization
        logger.info(f"Strategy {self.strategy_type} initialized with ID: {self.strategy_id}")

    def _initialize_session(self):
        """Initialize or connect to a session for persistence."""
        if not self.session:
            # Get session manager
            try:
                session_manager = SessionManager.get_session_manager()
                self.session = session_manager.create_session(
                    session_type=f"strategy_{self.strategy_type}",
                    session_id=f"strategy_{self.strategy_id}"
                )
                logger.debug(f"Created new session for strategy {self.strategy_id}")
            except Exception as e:
                logger.warning(f"Failed to create session for strategy {self.strategy_id}: {e}")
                self.session = None

        # Update session with initial state
        self._update_session()

    def _update_session(self):
        """Update the session with current strategy state and progress."""
        if self.session:
            try:
                self.session.update_state({
                    "strategy_id": self.strategy_id,
                    "strategy_type": self.strategy_type,
                    "state": StrategyState.to_str(self.state),
                    "source_group": self.source_group,
                    "target_group": self.target_group,
                    "member_limit": self.member_limit,
                    "max_retries": self.max_retries,
                    "delay_between_operations": self.delay_between_operations,
                    "auto_retry": self.auto_retry,
                    "start_time": self.start_time,
                    "end_time": self.end_time,
                    "pause_time": self.pause_time,
                    "total_pause_duration": self.total_pause_duration,
                    "processed": self.processed_items,
                    "total": self.total_items,
                    "successful": self.successful_items,
                    "failed": self.failed_items,
                    "retried": self.retried_items,
                    "current_item": self.current_item,
                    "progress": self.get_progress(),
                    "last_error": str(self.last_error) if self.last_error else None,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.warning(f"Failed to update session for strategy {self.strategy_id}: {e}")

    def _update_progress(self):
        """Update progress information and notify via callback."""
        # Calculate progress
        progress = self.get_progress()

        # Update session
        self._update_session()

        # Call progress callback if available
        if self.progress_callback:
            try:
                progress_data = {
                    "strategy_id": self.strategy_id,
                    "strategy_type": self.strategy_type,
                    "state": StrategyState.to_str(self.state),
                    "progress": progress,
                    "processed": self.processed_items,
                    "total": self.total_items,
                    "successful": self.successful_items,
                    "failed": self.failed_items,
                    "retried": self.retried_items,
                    "current_item": self.current_item,
                    "elapsed_time": self.get_elapsed_time(),
            "estimated_remaining_time": self.estimate_remaining_time()
        }

        # Add custom properties from subclasses
        strategy_dict.update(self._get_additional_properties())

        return strategy_dict

    def _get_additional_properties(self) -> Dict[str, Any]:
        """
        Get additional properties specific to subclasses.

        This method can be overridden by subclasses to add additional properties
        to the dictionary representation.

        Returns:
            Dict[str, Any]: Dictionary with additional properties.
        """
        return {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseStrategy':
        """
        Create a strategy instance from a dictionary.

        This is a factory method that creates a strategy instance
        based on the strategy_type in the dictionary.

        Args:
            data (Dict[str, Any]): Dictionary with strategy data.

        Returns:
            BaseStrategy: A strategy instance.

        Raises:
            StrategyNotFoundError: If the strategy type is not recognized.
        """
        # This should be implemented by a strategy factory
        # Here we'll just provide a base implementation that will be
        # usually overridden by a more sophisticated factory

        strategy_type = data.get("strategy_type")
        if not strategy_type:
            raise StrategyNotFoundError("Strategy type not specified in data")

        # Try to find the strategy class by name (this is a simple implementation)
        # In a real application, you'd have a registry of strategies
        from importlib import import_module
        try:
            # Try to import the module and get the class
            module_name = "strategies"
            module = import_module(module_name)

            # Try different naming conventions
            class_names = [
                strategy_type,
                strategy_type + "Strategy",
                ''.join(word.capitalize() for word in strategy_type.split('_')) + "Strategy"
            ]

            for class_name in class_names:
                if hasattr(module, class_name):
                    strategy_class = getattr(module, class_name)
                    break
            else:
                raise StrategyNotFoundError(f"Strategy class for type '{strategy_type}' not found")

            # Create an instance with basic parameters
            strategy = strategy_class(
                strategy_id=data.get("strategy_id"),
                source_group=data.get("source_group"),
                target_group=data.get("target_group"),
                member_limit=data.get("member_limit", 20)
            )

            # Set additional parameters
            strategy.max_retries = data.get("max_retries", strategy.max_retries)
            strategy.delay_between_operations = data.get("delay_between_operations", strategy.delay_between_operations)
            strategy.auto_retry = data.get("auto_retry", strategy.auto_retry)

            # Set state if it's a valid state string
            state_str = data.get("state")
            if state_str:
                strategy.state = StrategyState.from_str(state_str)

            # Set timestamps
            strategy.start_time = data.get("start_time")
            strategy.end_time = data.get("end_time")
            strategy.pause_time = data.get("pause_time")
            strategy.total_pause_duration = data.get("total_pause_duration", 0.0)

            # Set progress tracking
            strategy.total_items = data.get("total_items", 0)
            strategy.processed_items = data.get("processed_items", 0)
            strategy.successful_items = data.get("successful_items", 0)
            strategy.failed_items = data.get("failed_items", 0)
            strategy.retried_items = data.get("retried_items", 0)
            strategy.current_item = data.get("current_item")

            # Set errors
            strategy.errors = data.get("errors", [])
            strategy.last_error = data.get("last_error")

            return strategy

        except (ImportError, AttributeError) as e:
            raise StrategyNotFoundError(f"Strategy type '{strategy_type}' not found: {e}")

    def __del__(self):
        """Clean up resources when the strategy is deleted."""
        # Make sure we stop any running execution
        if self._execution_thread and self._execution_thread.is_alive():
            self._stop_event.set()
            self._pause_event.clear()

            # Don't join the thread here as it might deadlock


class StrategyFactory:
    """
    Factory class for creating strategy instances.

    This class provides methods for creating and retrieving strategy instances
    based on their type.
    """

    @staticmethod
    def create_strategy(strategy_type: str, **kwargs) -> BaseStrategy:
        """
        Create a strategy instance of the specified type.

        Args:
            strategy_type (str): Type of strategy to create.
            **kwargs: Additional arguments to pass to the strategy constructor.

        Returns:
            BaseStrategy: A strategy instance.

        Raises:
            StrategyNotFoundError: If the strategy type is not recognized.
        """
        # Normalize strategy type
        strategy_type = strategy_type.lower()

        # Define mapping of strategy types to classes
        # This should be dynamically built in a real application
        strategy_classes = {
            # These will be provided by other modules
            'sequential': None,
            'parallel_low': None,
            'parallel_medium': None,
            'parallel_high': None
        }

        # Try to import the specified strategy class
        from importlib import import_module

        try:
            # Build class name
            if '_' in strategy_type:
                # Convert snake_case to CamelCase
                class_name = ''.join(word.capitalize() for word in strategy_type.split('_'))
            else:
                # Capitalize first letter
                class_name = strategy_type.capitalize()

            # Add "Strategy" suffix if not present
            if not class_name.endswith('Strategy'):
                class_name += 'Strategy'

            # Try to import the module and get the class
            module_name = f"strategies.{strategy_type}_strategy"
            module = import_module(module_name)

            if hasattr(module, class_name):
                strategy_class = getattr(module, class_name)
            else:
                # Fallback to other naming conventions
                for attr_name in dir(module):
                    if attr_name.lower().endswith('strategy'):
                        strategy_class = getattr(module, attr_name)
                        break
                else:
                    raise StrategyNotFoundError(f"Strategy class for type '{strategy_type}' not found in module {module_name}")

            # Create and return the strategy instance
            return strategy_class(**kwargs)

        except (ImportError, AttributeError) as e:
            # If direct import fails, try the built-in mapping
            if strategy_type in strategy_classes and strategy_classes[strategy_type] is not None:
                return strategy_classes[strategy_type](**kwargs)

            raise StrategyNotFoundError(f"Strategy type '{strategy_type}' not found: {e}")

    @staticmethod
    def get_available_strategies() -> List[str]:
        """
        Get a list of available strategy types.

        Returns:
            List[str]: List of available strategy types.
        """
        # In a real application, this would dynamically discover available strategies
        return ['sequential', 'parallel_low', 'parallel_medium', 'parallel_high']": self.get_elapsed_time(),
                    "estimated_time": self.estimate_remaining_time(),
                    "last_error": str(self.last_error) if self.last_error else None
                }
                self.progress_callback(progress_data)
            except Exception as e:
                logger.warning(f"Error in progress callback for strategy {self.strategy_id}: {e}")

    def _set_state(self, new_state: StrategyState):
        """
        Set the strategy state and update related timestamps.

        Args:
            new_state (StrategyState): The new state to set.
        """
        with self._lock:
            old_state = self.state
            self.state = new_state

            # Update timestamps based on state transitions
            now = datetime.now().isoformat()

            if new_state == StrategyState.RUNNING and old_state in [StrategyState.CREATED, StrategyState.INITIALIZING]:
                self.start_time = now

            elif new_state == StrategyState.PAUSED:
                self.pause_time = now

            elif new_state == StrategyState.RUNNING and old_state == StrategyState.PAUSED:
                # Calculate pause duration when resuming
                if self.pause_time:
                    try:
                        pause_start = datetime.fromisoformat(self.pause_time)
                        pause_end = datetime.fromisoformat(now)
                        pause_duration = (pause_end - pause_start).total_seconds()
                        self.total_pause_duration += pause_duration
                    except (ValueError, TypeError):
                        # Handle invalid timestamp formats
                        pass
                self.pause_time = None

            elif StrategyState.is_terminal_state(new_state):
                self.end_time = now

            # Log state change
            logger.info(f"Strategy {self.strategy_id} state changed: {StrategyState.to_str(old_state)} -> {StrategyState.to_str(new_state)}")

            # Update session
            self._update_session()

            # If the session has a log_event method, use it
            if self.session and hasattr(self.session, 'log_event'):
                self.session.log_event(
                    f"Strategy state changed to {StrategyState.to_str(new_state)}",
                    {"old_state": StrategyState.to_str(old_state)}
                )

    def _log_error(self, error_message: str, exception: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        """
        Log an error encountered during strategy execution.

        Args:
            error_message (str): Error description message.
            exception (Exception, optional): The exception object if available.
            context (dict, optional): Additional context information.
        """
        # Create error entry
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "message": error_message,
            "exception_type": exception.__class__.__name__ if exception else "Unknown",
            "exception_details": str(exception) if exception else None,
            "context": context or {}
        }

        # Store error
        self.errors.append(error_entry)
        self.last_error = exception or error_message

        # Log to logger
        logger.error(f"Strategy {self.strategy_id} error: {error_message}", exc_info=exception is not None)

        # Log to session if available
        if self.session and hasattr(self.session, 'log_error'):
            self.session.log_error(
                error_message=error_message,
                error_type=error_entry["exception_type"],
                exception=exception,
                context=context
            )

        # Call error hooks
        self._run_hook('on_error', error_entry)

    def add_hook(self, hook_name: str, callback: Callable):
        """
        Add a hook callback for a specific event.

        Args:
            hook_name (str): Name of the hook (e.g., 'pre_execute', 'post_execute').
            callback (callable): Function to call when the hook is triggered.

        Raises:
            ValueError: If the hook name is invalid.
        """
        if hook_name not in self.hooks:
            raise ValueError(f"Invalid hook name: {hook_name}. Available hooks: {list(self.hooks.keys())}")

        self.hooks[hook_name].append(callback)
        logger.debug(f"Added hook '{hook_name}' to strategy {self.strategy_id}")

    def _run_hook(self, hook_name: str, *args, **kwargs):
        """
        Run all callbacks registered for a specific hook.

        Args:
            hook_name (str): Name of the hook to run.
            *args, **kwargs: Arguments to pass to the hook callbacks.
        """
        if hook_name not in self.hooks:
            return

        for callback in self.hooks[hook_name]:
            try:
                callback(self, *args, **kwargs)
            except Exception as e:
                logger.warning(f"Error in hook '{hook_name}' for strategy {self.strategy_id}: {e}")

    def get_progress(self) -> float:
        """
        Get the current progress as a percentage.

        Returns:
            float: Progress percentage (0-100).
        """
        if self.total_items <= 0:
            return 0.0

        return (self.processed_items / self.total_items) * 100.0

    def get_elapsed_time(self) -> float:
        """
        Get the elapsed execution time in seconds.

        Returns:
            float: Elapsed time in seconds, or 0 if not started.
        """
        if not self.start_time:
            return 0.0

        try:
            start = datetime.fromisoformat(self.start_time)

            if self.end_time:
                end = datetime.fromisoformat(self.end_time)
            elif self.pause_time:
                end = datetime.fromisoformat(self.pause_time)
            else:
                end = datetime.now()

            elapsed = (end - start).total_seconds() - self.total_pause_duration
            return max(0.0, elapsed)  # Ensure non-negative value
        except (ValueError, TypeError):
            return 0.0

    def estimate_remaining_time(self) -> float:
        """
        Estimate the remaining execution time in seconds.

        Returns:
            float: Estimated remaining time in seconds, or None if not calculable.
        """
        if self.processed_items <= 0 or self.total_items <= 0:
            return 0.0

        elapsed_time = self.get_elapsed_time()
        if elapsed_time <= 0:
            return 0.0

        # Calculate processing rate (items per second)
        rate = self.processed_items / elapsed_time

        # If rate is too low, avoid division by near-zero
        if rate < 0.0001:
            return float('inf')

        # Estimate time for remaining items
        remaining_items = self.total_items - self.processed_items
        estimated_time = remaining_items / rate

        return max(0.0, estimated_time)

    def execute(self, progress_callback: Optional[Callable] = None,
                blocking: bool = False) -> bool:
        """
        Execute the strategy.

        Args:
            progress_callback (callable, optional): Function to call with progress updates.
            blocking (bool): Whether to block until completion.

        Returns:
            bool: True if execution started successfully, False otherwise.
        """
        with self._lock:
            # Check if already running
            if StrategyState.is_active_state(self.state):
                logger.warning(f"Strategy {self.strategy_id} is already running: {StrategyState.to_str(self.state)}")
                return False

            # Check if in terminal state
            if StrategyState.is_terminal_state(self.state):
                logger.warning(f"Strategy {self.strategy_id} cannot be executed from terminal state: {StrategyState.to_str(self.state)}")
                return False

            # Reset stop and pause events
            self._stop_event.clear()
            self._pause_event.clear()

            # Set progress callback
            self.progress_callback = progress_callback

            # Set state to validating
            self._set_state(StrategyState.VALIDATING)

            # Validate requirements
            valid, issues = self._validate_requirements()
            if not valid:
                error_msg = f"Strategy requirements validation failed: {', '.join(issues)}"
                self._log_error(error_msg)
                self._set_state(StrategyState.FAILED)
                return False

            # Run pre-execute hooks
            self._run_hook('pre_execute')

            # Set state to initializing
            self._set_state(StrategyState.INITIALIZING)

            try:
                # Initialize execution
                result = self._initialize_execution()
                if not result:
                    logger.error(f"Strategy {self.strategy_id} initialization failed")
                    self._set_state(StrategyState.FAILED)
                    return False

                # Start execution thread
                if blocking:
                    # Run directly in current thread
                    self._set_state(StrategyState.RUNNING)
                    try:
                        self._execute_implementation()
                        if not self._stop_event.is_set():
                            self._set_state(StrategyState.COMPLETED)
                            self._run_hook('on_complete')
                        return True
                    except Exception as e:
                        self._log_error("Execution failed", e)
                        self._set_state(StrategyState.FAILED)
                        self._run_hook('on_fail')
                        return False
                else:
                    # Run in separate thread
                    self._execution_thread = threading.Thread(
                        target=self._execution_wrapper,
                        name=f"Strategy-{self.strategy_id}",
                        daemon=True
                    )
                    self._execution_thread.start()

                    # Set state to running (thread will handle state changes after that)
                    self._set_state(StrategyState.RUNNING)

                    return True

            except Exception as e:
                error_msg = f"Failed to start strategy execution: {e}"
                self._log_error(error_msg, e)
                self._set_state(StrategyState.FAILED)
                self._run_hook('on_fail')
                return False

    def _execution_wrapper(self):
        """Wrapper for threaded execution to handle exceptions and state changes."""
        try:
            # Run the actual implementation
            self._execute_implementation()

            # Check if stopped
            if self._stop_event.is_set():
                return

            # Set state to completed
            self._set_state(StrategyState.COMPLETED)
            self._run_hook('on_complete')

            # Run post-execute hooks
            self._run_hook('post_execute')

        except Exception as e:
            # Log the error
            self._log_error("Execution failed", e)

            # Set state to failed
            self._set_state(StrategyState.FAILED)
            self._run_hook('on_fail')

    def pause(self) -> bool:
        """
        Pause strategy execution.

        Returns:
            bool: True if paused successfully, False otherwise.
        """
        if self.state != StrategyState.RUNNING:
            logger.warning(f"Cannot pause strategy {self.strategy_id}: not running (current state: {StrategyState.to_str(self.state)})")
            return False

        logger.info(f"Pausing strategy {self.strategy_id}")
        self._set_state(StrategyState.PAUSING)
        self._pause_event.set()
        self._run_hook('on_pause')
        return True

    def resume(self) -> bool:
        """
        Resume a paused strategy.

        Returns:
            bool: True if resumed successfully, False otherwise.
        """
        if self.state != StrategyState.PAUSED:
            logger.warning(f"Cannot resume strategy {self.strategy_id}: not paused (current state: {StrategyState.to_str(self.state)})")
            return False

        logger.info(f"Resuming strategy {self.strategy_id}")
        self._set_state(StrategyState.RESUMING)
        self._pause_event.clear()
        self._set_state(StrategyState.RUNNING)
        self._run_hook('on_resume')
        return True

    def cancel(self) -> bool:
        """
        Cancel strategy execution.

        Returns:
            bool: True if cancelled successfully, False otherwise.
        """
        if StrategyState.is_terminal_state(self.state):
            logger.warning(f"Cannot cancel strategy {self.strategy_id}: already in terminal state (current state: {StrategyState.to_str(self.state)})")
            return False

        logger.info(f"Cancelling strategy {self.strategy_id}")
        self._set_state(StrategyState.CANCELLING)
        self._stop_event.set()
        self._pause_event.clear()  # In case it was paused
        self._run_hook('on_cancel')

        # Wait for execution thread to finish if it exists
        if self._execution_thread and self._execution_thread.is_alive():
            self._execution_thread.join(timeout=5.0)

        self._set_state(StrategyState.CANCELLED)
        return True

    def _check_pause(self):
        """
        Check if execution should be paused and handle pausing.
        """
        if self._pause_event.is_set():
            self._set_state(StrategyState.PAUSED)

            # Wait until resumed or stopped
            while self._pause_event.is_set() and not self._stop_event.is_set():
                time.sleep(0.1)

            # If stopped, raise exception to break execution
            if self._stop_event.is_set():
                raise StrategyExecutionError("Strategy execution was cancelled")

    def _check_stop(self):
        """
        Check if execution should be stopped and raise exception if needed.

        Raises:
            StrategyExecutionError: If the stop flag is set.
        """
        if self._stop_event.is_set():
            raise StrategyExecutionError("Strategy execution was cancelled")

    def _validate_requirements(self) -> Tuple[bool, List[str]]:
        """
        Validate that all requirements for execution are met.

        Returns:
            Tuple[bool, List[str]]: A tuple containing:
                - Boolean indicating if requirements are met
                - List of validation issues (empty if valid)
        """
        issues = []

        # Basic requirements
        if not self.source_group:
            issues.append("Source group is not specified")

        if not self.target_group:
            issues.append("Target group is not specified")

        if self.member_limit <= 0:
            issues.append(f"Invalid member limit: {self.member_limit}")

        return len(issues) == 0, issues

    def _initialize_execution(self) -> bool:
        """
        Initialize resources needed for execution.

        This method should be overridden by subclasses to provide
        implementation-specific initialization.

        Returns:
            bool: True if initialization is successful, False otherwise.
        """
        # Base implementation just sets the total items to member_limit if not set
        if self.total_items <= 0:
            self.total_items = self.member_limit

        return True

    @abc.abstractmethod
    def _execute_implementation(self):
        """
        Implement the actual execution logic.

        This abstract method must be implemented by subclasses to provide
        the actual execution logic.

        Raises:
            StrategyExecutionError: If execution fails.
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the strategy execution.

        Returns:
            Dict[str, Any]: Dictionary with execution statistics.
        """
        return {
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type,
            "state": StrategyState.to_str(self.state),
            "elapsed_time": self.get_elapsed_time(),
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "retried_items": self.retried_items,
            "progress": self.get_progress(),
            "error_count": len(self.errors)
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the strategy to a dictionary for serialization.

        Returns:
            Dict[str, Any]: Dictionary representation of the strategy.
        """
        # Basic properties
        strategy_dict = {
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type,
            "state": StrategyState.to_str(self.state),

            # Operation parameters
            "source_group": self.source_group,
            "target_group": self.target_group,
            "member_limit": self.member_limit,
            "max_retries": self.max_retries,
            "delay_between_operations": self.delay_between_operations,
            "auto_retry": self.auto_retry,

            # Execution state
            "start_time": self.start_time,
            "end_time": self.end_time,
            "pause_time": self.pause_time,
            "total_pause_duration": self.total_pause_duration,

            # Progress tracking
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "retried_items": self.retried_items,
            "current_item": self.current_item,

            # Error tracking
            "errors": self.errors,
            "last_error": str(self.last_error) if self.last_error else None,

            # Additional stats
            "progress": self.get_progress(),
            "elapsed_time