#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telegram Account Manager

Main entry point for the Telegram Account Manager application.
"""

import os
import sys
import logging
from error_handling.error_manager import get_error_manager
from utils.app_context import AppContext


# Add the project path to system path if needed
project_path = os.path.abspath(os.path.dirname(__file__))
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# Import required modules

# Try to import custom logging module
try:
    from logging_.logging_manager import get_logger
    HAS_CUSTOM_LOGGER = True
except ImportError:
    HAS_CUSTOM_LOGGER = False

# Set up basic logging until we can initialize the proper logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger("Main")


def initialize_logging():
    """Initialize the logging system with proper configuration."""
    if HAS_CUSTOM_LOGGER:
        return get_logger("Main")
    else:
        # If custom logging module is not available, use the basic logger
        LOGGER.warning(
            "Custom logging module not available, using basic logging")
        return LOGGER


def initialize_application(logger):
    """
    Initialize the application and its core components.

    Creates the application context, loads configuration,
    sets up error handling, and initializes all services.

    Args:
        logger: The logger to use for logging

    Returns:
        The initialized application context
    """
    # Create and initialize the application context
    app_context = AppContext()

    # Log application startup
    logger.info("Initializing Telegram Account Manager application")

    # Load configuration
    config = app_context.config
    logger.info("Loaded configuration: app_version=%s",
                config.get('app_version', 'unknown'))

    # Register core services
    error_manager = get_error_manager()
    app_context.register_service('error_manager', error_manager)

    # Initialize all services
    app_context.initialize()

    logger.info("Application initialization completed")
    return app_context


def cleanup_application(app_context, logger):
    """
    Perform cleanup operations before exiting.

    This function ensures all resources are properly released
    and the application shuts down gracefully.

    Args:
        app_context: The application context to shut down
        logger: The logger to use for logging
    """
    logger.info("Shutting down application")
    app_context.shutdown()
    logger.info("Application shutdown completed")


def display_welcome_message():
    """
    Display welcome message to the user.

    Shows the application name and a brief description of its purpose.
    """
    print("\n" + "=" * 60)
    print("     TELEGRAM ACCOUNT MANAGER     ".center(60))
    print("=" * 60)
    print("\nWelcome to the Telegram Account Manager!")
    print("This application helps you manage Telegram accounts")
    print("and transfer members between groups.")
    print("\nInitialization complete. The application is ready to use.")
    print("=" * 60 + "\n")


def main():
    """
    Main entry point for the application.

    Initializes the application, displays the welcome message,
    and handles the main application flow.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    # Initialize logging first
    logger = initialize_logging()

    app_context = None
    try:
        # Initialize application
        app_context = initialize_application(logger)

        # Display welcome message
        display_welcome_message()

        # In the basic version, we'll just wait for user input to exit
        input("Press Enter to exit...")

        return 0  # Success exit code

    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
        return 0  # Success exit code

    except (IOError, ValueError, FileNotFoundError) as exc:
        # Log the error
        error_msg = f"Unhandled exception: {str(exc)}"
        logger.critical(error_msg, exc_info=True)
        print(f"ERROR: {error_msg}")
        return 1  # Error exit code

    finally:
        # Clean up application resources
        if app_context is not None:
            cleanup_application(app_context, logger)


if __name__ == "__main__":
    sys.exit(main())
