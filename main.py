#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telegram Account Manager - Main Entry Point

This module serves as the main entry point for the Telegram Account Manager application.
It initializes all necessary components, sets up logging, error handling,
and manages the application lifecycle.

Features:
- Application initialization and configuration
- Main menu presentation and navigation
- Command-line argument processing
- Application context setup and resource management
- Graceful shutdown handling
"""

import os
import sys
import argparse
import logging
import signal
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union

# Add project root to Python path to ensure imports work correctly
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import core modules
from core.config import Config
from core.constants import Constants
from core.exceptions import TelegramAdderError, ConfigError

# Import logging modules
from logging_.logging_manager import LoggingManager, get_logger

# Import utility modules
from utils.app_context import AppContext
from utils.helpers import get_platform_info, setup_signal_handlers, clear_console
from utils.validators import validate_environment

# Import UI modules
from ui.menu_system import MenuSystem
from ui.display import Display
from ui.colors import ColorManager

# Global variables
logger = None  # Will be initialized properly during setup
app_context = None  # Application context singleton
exit_event = threading.Event()  # Event to signal clean exit


def setup_logging(config: Config) -> logging.Logger:
    """
    Set up the logging system.

    Args:
        config (Config): Application configuration.

    Returns:
        logging.Logger: Configured logger for the main module.
    """
    log_level = logging.DEBUG if config.get('debug_mode', False) else logging.INFO
    log_file = config.get_file_path('log_file')

    # Initialize the logging manager
    log_manager = LoggingManager(
        log_dir=os.path.dirname(log_file),
        log_file=os.path.basename(log_file),
        default_level=log_level,
        json_log_enabled=config.get('json_logging_enabled', False)
    )

    # Get the main logger
    main_logger = log_manager.get_logger("Main")
    main_logger.info(f"Logging system initialized. Log file: {log_file}")

    return main_logger


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Telegram Account Manager")

    parser.add_argument(
        "--config",
        type=str,
        help="Path to the configuration file"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    parser.add_argument(
        "--recover",
        action="store_true",
        help="Attempt to recover from previous interrupted session"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )
    parser.add_argument(
        "--sessions-dir",
        type=str,
        help="Directory to store session files"
    )

    return parser.parse_args()


def initialize_application(args: argparse.Namespace) -> Tuple[Config, AppContext]:
    """
    Initialize the application and its components.

    Args:
        args (argparse.Namespace): Command-line arguments.

    Returns:
        Tuple[Config, AppContext]: Configuration and application context.

    Raises:
        ConfigError: If configuration initialization fails.
    """
    # Initialize configuration
    config = Config()

    # Apply command-line arguments to configuration
    if args.config:
        config.load(args.config)

    if args.debug:
        config.set('debug_mode', True)

    # Create application context
    context = AppContext()

    # Initialize context with configuration
    context.register('config', config)

    # Set up sessions directory if specified
    if args.sessions_dir:
        context.register('sessions_dir', args.sessions_dir)

    # Set up color manager
    color_manager = ColorManager(enabled=not args.no_color)
    context.register('color_manager', color_manager)

    return config, context


def setup_environment() -> bool:
    """
    Set up the application environment.

    Checks for required dependencies, file permissions, and environment variables.

    Returns:
        bool: True if environment is valid, False otherwise.
    """
    try:
        # Validate environment
        valid, issues = validate_environment()

        if not valid:
            for issue in issues:
                print(f"Environment issue: {issue}")
            return False

        # Check Python version
        min_python_version = (3, 7)
        current_version = sys.version_info[:2]

        if current_version < min_python_version:
            print(f"Python {min_python_version[0]}.{min_python_version[1]} or higher is required. "
                  f"You're using Python {current_version[0]}.{current_version[1]}.")
            return False

        return True
    except Exception as e:
        print(f"Error during environment setup: {e}")
        return False


def show_welcome_message(color_manager: ColorManager):
    """
    Display the welcome message and application information.

    Args:
        color_manager (ColorManager): Color manager for styled output.
    """
    clear_console()
    print(color_manager.style_text("""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║   ████████╗███████╗██╗     ███████╗ ██████╗ ██████╗  █████╗ ███╗   ███╗ ║
║   ╚══██╔══╝██╔════╝██║     ██╔════╝██╔════╝ ██╔══██╗██╔══██╗████╗ ████║ ║
║      ██║   █████╗  ██║     █████╗  ██║  ███╗██████╔╝███████║██╔████╔██║ ║
║      ██║   ██╔══╝  ██║     ██╔══╝  ██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║ ║
║      ██║   ███████╗███████╗███████╗╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║ ║
║      ╚═╝   ╚══════╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝ ║
║                                                                    ║
║                      ACCOUNT MANAGER                               ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
""", 'CYAN', bright=True))

    # Show version and build info
    config = app_context.get('config')
    app_name = config.get('app_name', 'Telegram Account Manager')
    app_version = config.get('app_version', '1.0.0')

    print(color_manager.style_text(f" {app_name} v{app_version}", 'GREEN'))
    print(color_manager.style_text(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 'GREEN'))
    print(color_manager.style_text(" " + "="*70, 'GREEN'))
    print()


def clean_shutdown():
    """
    Perform a clean shutdown of the application.

    This function handles resource cleanup and proper shutdown procedures.
    """
    global logger, app_context

    print("\nShutting down... Please wait.")

    # Log shutdown
    if logger:
        logger.info("Application shutdown initiated")

    # Clean up resources
    if app_context:
        # Get logging manager and shut it down
        logging_manager = LoggingManager()
        logging_manager.shutdown()

        # Perform other cleanup tasks
        app_context.cleanup()

    print("Shutdown complete. Goodbye!")


def handle_signal(sig, frame):
    """
    Handle system signals like SIGINT (Ctrl+C).

    Args:
        sig: Signal number
        frame: Current stack frame
    """
    global exit_event

    if logger:
        logger.info(f"Received signal {sig}, initiating shutdown")

    # Set the exit event to signal all threads to terminate
    exit_event.set()


def handle_exceptions(exc_type, exc_value, exc_traceback):
    """
    Global exception handler for uncaught exceptions.

    Args:
        exc_type: Exception type
        exc_value: Exception value
        exc_traceback: Exception traceback
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Call the original handler for KeyboardInterrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    if logger:
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    print("\nFatal error occurred. Check the log file for details.")

    # Initiate shutdown
    clean_shutdown()


async def check_for_interrupted_sessions():
    """
    Check for any interrupted sessions and offer to recover them.

    Returns:
        bool: True if recovery was successful or not needed, False if failed
    """
    try:
        # Import session manager
        from data.session_manager import SessionManager

        # Get sessions directory from app context or use default
        sessions_dir = app_context.get('sessions_dir', None)
        session_manager = SessionManager(sessions_dir=sessions_dir)

        # Find incomplete sessions
        incomplete_sessions = session_manager.find_incomplete_sessions()

        if incomplete_sessions:
            color_manager = app_context.get('color_manager')
            display = Display(color_manager=color_manager)

            display.print_warning(f"Found {len(incomplete_sessions)} interrupted operation(s).")

            # Ask user if they want to recover
            recover = display.prompt_yes_no("Do you want to recover interrupted operations?")

            if recover:
                # For now, just log that we would recover
                logger.info(f"User chose to recover {len(incomplete_sessions)} interrupted operations")
                display.print_info("Recovery option selected but implementation pending...")
                return True
            else:
                logger.info("User chose not to recover interrupted operations")
                return True

        return True
    except Exception as e:
        logger.error(f"Error checking for interrupted sessions: {e}")
        return False


async def main_async():
    """
    Main asynchronous function that runs the application.

    This is the main entry point for the application's business logic.
    """
    global logger, app_context, exit_event

    try:
        # Parse command-line arguments
        args = parse_arguments()

        # Check environment
        if not setup_environment():
            print("Environment setup failed. Exiting.")
            return 1

        # Initialize application
        config, app_context = initialize_application(args)

        # Setup logging
        logger = setup_logging(config)
        logger.info(f"Application startup: {config.get('app_name', 'Telegram Account Manager')} "
                   f"v{config.get('app_version', '1.0.0')}")

        # Log platform information
        platform_info = get_platform_info()
        logger.info(f"Platform: {platform_info}")

        # Set up signal handlers
        setup_signal_handlers(handle_signal)

        # Set up global exception handler
        sys.excepthook = handle_exceptions

        # Get color manager from context
        color_manager = app_context.get('color_manager')

        # Display welcome message
        show_welcome_message(color_manager)

        # Check for interrupted sessions if requested
        if args.recover:
            if not await check_for_interrupted_sessions():
                logger.warning("Failed to check for interrupted sessions")

        # Create menu system
        menu_system = MenuSystem(app_context=app_context)
        app_context.register('menu_system', menu_system)

        # Create display
        display = Display(color_manager=color_manager)
        app_context.register('display', display)

        # Initialize services from other modules
        # Import and configure account manager
        from services.account_manager import AccountManager
        account_manager = AccountManager(app_context=app_context)
        app_context.register('account_manager', account_manager)

        # Import and configure group manager
        from services.group_manager import GroupManager
        group_manager = GroupManager(app_context=app_context)
        app_context.register('group_manager', group_manager)

        # Import and configure analytics service
        from services.analytics import AnalyticsService
        analytics_service = AnalyticsService(app_context=app_context)
        app_context.register('analytics_service', analytics_service)

        # Import and configure proxy manager if enabled
        if config.get('use_proxy', False):
            from services.proxy_manager import ProxyManager
            proxy_manager = ProxyManager(app_context=app_context)
            app_context.register('proxy_manager', proxy_manager)

        # Wait for exit signal or completion
        logger.info("Application initialized and ready")

        # Start the menu system - this is the main application loop
        await menu_system.start()

        # If we get here, the menu system has completed
        logger.info("Application completed successfully")
        return 0

    except ConfigError as e:
        print(f"Configuration error: {e}")
        if logger:
            logger.error(f"Configuration error: {e}")
        return 1

    except TelegramAdderError as e:
        print(f"Application error: {e}")
        if logger:
            logger.error(f"Application error: {e}")
        return 1

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        if logger:
            logger.info("Operation cancelled by user (KeyboardInterrupt)")
        return 0

    except Exception as e:
        print(f"Unexpected error: {e}")
        if logger:
            logger.critical(f"Unexpected error", exc_info=True)
        return 1

    finally:
        clean_shutdown()


def main():
    """
    Main function that serves as the entry point for the application.

    This function sets up the asynchronous environment and runs the main_async function.
    """
    try:
        # Run the asynchronous main function
        exit_code = asyncio.run(main_async())
        return exit_code

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 0

    except Exception as e:
        print(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)