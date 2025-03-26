"""
Application Context Module

This module provides a central application context for the Telegram Account Manager.
It implements the Singleton pattern to ensure only one instance exists across the
application, providing easy access to services, configurations, and other components.

Features:
- Centralized access to application components and services
- Dependency injection for better testability
- Runtime registration and resolution of services
- Lazy loading of resources
- Support for configuration management
- Lifecycle management for application startup and shutdown

Usage:
    from utils.app_context import AppContext

    # Get the AppContext instance
    context = AppContext()

    # Access a configuration value
    api_id = context.config.get('api_id')

    # Access a service
    account_manager = context.get_service('account_manager')

    # Register a service
    context.register_service('analytics', analytics_service)

    # Initialize all services
    context.initialize()

    # Clean up resources on shutdown
    context.shutdown()
"""

import logging
import threading
from typing import Any, Optional, Type, Callable, TypeVar

# Import core modules
try:
    from core.config import Config
except ImportError:
    # Mock Config for development/testing
    # pylint: disable=C0115  # Missing class docstring
    class Config:
        def __init__(self):
            self._config_data = {}

# pylint: disable=C0116  # Missing function or method docstring
        def get(self, key, default=None):
            return self._config_data.get(key, default)

        def set(self, key, value):
            self._config_data[key] = value

# Import logging
try:
    from logging_.logging_manager import LoggingManager
except ImportError:
    # Mock LoggingManager for development/testing
    # pylint: disable=C0115  # Missing class docstring
    class LoggingManager:
        # pylint: disable=C0116  # Missing function or method docstring
        def get_logger(self, name):
            return logging.getLogger(name)

# Setup logger
logger = logging.getLogger("AppContext")

# Type variable for service resolution
T = TypeVar('T')


class AppContext:
    """
    Application context for centralized access to services and configuration.

    This class follows the Singleton pattern to ensure only one instance exists
    across the application. It provides centralized access to services, configurations,
    and other components, as well as lifecycle management for the application.
    """

    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        """
        Create a new AppContext instance if one doesn't exist (Singleton pattern).

        Returns:
            AppContext: The singleton AppContext instance
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AppContext, cls).__new__(cls)
            return cls._instance

    def __init__(self):
        """
        Initialize the AppContext if not already initialized.
        """
        # Skip initialization if already initialized (Singleton pattern)
        with self._lock:
            if self._initialized:
                return

            # Initialize properties
            self._services = {}
            self._factories = {}
            self._initialized_services = set()
            self._app_state = "created"

            # Set up configuration
            self._config = Config()

            # Set up logging manager
            try:
                self._logging_manager = LoggingManager()
            except (IOError, FileNotFoundError, ValueError) as e:
                # Fallback to basic logging if LoggingManager is not available
                self._logging_manager = None
                logging.basicConfig(
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                logger.warning(
                    "Failed to initialize LoggingManager: %s. Using basic logging.", e)

            # Mark as initialized
            self._initialized = True
            logger.debug("AppContext initialized")

    @property
    def config(self) -> Config:
        """
        Get the application configuration.

        Returns:
            Config: The application configuration instance
        """
        return self._config

    @property
    def app_state(self) -> str:
        """
        Get the current application state.

        Returns:
            str: The current application state
        """
        return self._app_state

    def get_service(self, name: str, default: Any = None) -> Any:
        """
        Get a service by name.

        Args:
            name (str): Name of the service to retrieve
            default (Any, optional): Default value to return if service is not found

        Returns:
            Any: The service instance or default if not found
        """
        with self._lock:
            # Return the instance if already created
            if name in self._services:
                return self._services[name]

            # Create the instance using factory if available
            if name in self._factories:
                factory = self._factories[name]
                instance = factory()
                self._services[name] = instance
                logger.debug("Service '%s' created using factory", name)
                return instance

            # Service not found
            logger.debug("Service '%s' not found", name)
            return default

    def get_service_of_type(self, service_type: Type[T]) -> Optional[T]:
        """
        Get a service by its type.

        Args:
            service_type (Type[T]): Type of the service to retrieve

        Returns:
            Optional[T]: The service instance or None if not found
        """
        with self._lock:
            # Find a service of the specified type
            for service in self._services.values():
                if isinstance(service, service_type):
                    return service

            # Service not found
            logger.debug("Service of type '%s' not found",
                         service_type.__name__)
            return None

    def register_service(self, name: str, instance: Any) -> None:
        """
        Register a service with the AppContext.

        Args:
            name (str): Name of the service
            instance (Any): Service instance to register
        """
        with self._lock:
            self._services[name] = instance
            logger.debug("Service '%s' registered", name)

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """
        Register a factory function for lazy-loading a service.

        Args:
            name (str): Name of the service
            factory (Callable[[], Any]): Factory function to create the service
        """
        with self._lock:
            self._factories[name] = factory
            # Remove any existing instance to force recreation
            if name in self._services:
                del self._services[name]
            logger.debug("Factory for service '%s' registered", name)

    def has_service(self, name: str) -> bool:
        """
        Check if a service exists.

        Args:
            name (str): Name of the service to check

        Returns:
            bool: True if the service exists, False otherwise
        """
        with self._lock:
            return name in self._services or name in self._factories

    def initialize(self) -> None:
        """
        Initialize all services that have an 'initialize' method.

        This method is called to bootstrap the application.
        """
        with self._lock:
            if self._app_state != "created":
                logger.warning(
                    "Cannot initialize AppContext in state: %s", self._app_state)
                return

            # Initialize services
            initialized_count = 0
            for name, service in self._services.items():
                if hasattr(service, 'initialize') and callable(
                        service.initialize) and name not in self._initialized_services:
                    try:
                        service.initialize()
                        self._initialized_services.add(name)
                        initialized_count += 1
                        logger.debug("Service '%s' initialized", name)
                    except (IOError, FileNotFoundError, ValueError) as e:
                        logger.error(
                            "Failed to initialize service '%s': %s", name, e)

            # Update app state
            self._app_state = "initialized"
            logger.info("AppContext initialized with %s services",
                        initialized_count)

    def shutdown(self) -> None:
        """
        Shutdown all services that have a 'shutdown' method.

        This method is called when the application is shutting down.
        """
        with self._lock:
            if self._app_state not in ["initialized", "running"]:
                logger.warning(
                    "Cannot shutdown AppContext in state: %s", self._app_state)
                return

            # Update app state
            self._app_state = "shutting_down"

            # Shutdown services in reverse order of initialization
            shutdown_count = 0
            for name in reversed(list(self._initialized_services)):
                service = self._services.get(name)
                if service and hasattr(service, 'shutdown') and callable(service.shutdown):
                    try:
                        service.shutdown()
                        shutdown_count += 1
                        logger.debug("Service '%s' shutdown", name)
                    except (IOError, FileNotFoundError, ValueError) as e:
                        logger.error(
                            "Failed to shutdown service '%s': %s", name, e)

            # Clear services
            self._services.clear()
            self._factories.clear()
            self._initialized_services.clear()

            # Update app state
            self._app_state = "shutdown"
            logger.info("AppContext shutdown with %s services", shutdown_count)

    def start(self) -> None:
        """
        Start the application.

        This method is called after initialization to mark the application as running.
        """
        with self._lock:
            if self._app_state != "initialized":
                logger.warning(
                    "Cannot start AppContext in state: %s", self._app_state)
                return

            # Update app state
            self._app_state = "running"
            logger.info("AppContext started")

    def reset(self) -> None:
        """
        Reset the AppContext to its initial state.

        This is primarily used for testing.
        """
        with self._lock:
            # Shutdown services
            if self._app_state in ["initialized", "running"]:
                self.shutdown()

            # Clear data and reinitialize
            self._services = {}
            self._factories = {}
            self._initialized_services = set()
            self._app_state = "created"

            # Reset configuration
            self._config = Config()

            logger.debug("AppContext reset")

    # Context manager support
    def __enter__(self):
        """
        Enter context manager.

        Returns:
            AppContext: The AppContext instance
        """
        self.initialize()
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context manager.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        self.shutdown()
        return False  # Do not suppress exceptions


# Module-level function to get the AppContext instance
def get_app_context() -> AppContext:
    """
    Get the AppContext instance.

    Returns:
        AppContext: The singleton AppContext instance
    """
    return AppContext()
