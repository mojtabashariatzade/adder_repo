#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telegram Account Manager

Main entry point for the Telegram Account Manager application.
"""

import os
import sys
import logging
import signal
import traceback  # اضافه شده برای دیباگ بهتر
from error_handling.error_manager import get_error_manager
from utils.app_context import AppContext

# Add the project path to system path if needed
project_path = os.path.abspath(os.path.dirname(__file__))
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# Import required modules
try:
    from services.account_manager import AccountManager
except ImportError as e:
    print(f"Error importing AccountManager: {e}")
    sys.exit(1)

# Import UI modules with individual try-except blocks to handle potential errors in any module
try:
    from ui.display import clear_screen, print_banner, print_header
except ImportError as e:
    print(f"Error importing display module: {e}")
    # Define fallback functions for display
    def clear_screen(): pass
    def print_banner(text): print(f"\n{'='*50}\n{text}\n{'='*50}")
    def print_header(text): print(f"\n{text}\n{'-'*len(text)}")

# Try to import menu modules - will handle missing modules in initialize_menus function
try:
    from ui.menu_system import MenuSystem, Menu, create_submenu_item, create_action_item
    HAS_MENU_SYSTEM = True
except ImportError as e:
    print(f"Warning: Menu system not available: {e}")
    HAS_MENU_SYSTEM = False

# Additional UI modules - will be checked at runtime
UI_MODULES_AVAILABLE = {
    'menu_system': HAS_MENU_SYSTEM,
    'account_menu': False,
    'operation_menu': False,
    'settings_menu': False
}

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
    app_context.register_service('config', config)
    logger.info("Loaded configuration: app_version=%s",
                config.get('app_version', 'unknown'))

    # Register core services
    error_manager = get_error_manager()
    app_context.register_service('error_manager', error_manager)

    # Initialize account manager
    try:
        account_manager = AccountManager(app_context)
        app_context.register_service('account_manager', account_manager)
        logger.info("Account Manager service registered")
    except (ValueError, TypeError, AttributeError, ImportError, FileNotFoundError) as e:
        logger.error(f"Failed to initialize Account Manager: {e}")

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
    clear_screen()
    print_banner("TELEGRAM ACCOUNT MANAGER")
    print("\nWelcome to the Telegram Account Manager!")
    print("This application helps you manage Telegram accounts")
    print("and transfer members between groups.")
    print("\nInitialization complete. The application is ready to use.")
    print("\nPress Enter to continue...")
    input()


def setup_signal_handlers(app_context, logger):
    """
    Set up signal handlers for graceful shutdown.

    Args:
        app_context: The application context
        logger: The logger to use for logging
    """
    def signal_handler(sig, frame):
        """Handle termination signals."""
        logger.info("Received termination signal")
        cleanup_application(app_context, logger)
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination request

    # On Windows, this will only be registered if it's available
    try:
        signal.signal(signal.SIGHUP, signal_handler)  # Terminal closed
    except (AttributeError, ValueError):
        pass


def initialize_menus(app_context):
    """
    Initialize the menu system.

    Args:
        app_context: The application context

    Returns:
        MenuSystem or None: The menu system if available, None otherwise
    """
    # Check if menu system is available
    if not HAS_MENU_SYSTEM:
        LOGGER.warning("Menu system not available - using fallback interface")
        return None

    try:
        # Create main menu
        main_menu = Menu("Main Menu")
        print("DEBUG: Created main menu")

        # Try to import and create account menu
        try:
            from ui.account_menu import create_account_menu
            account_menu = create_account_menu(main_menu)
            UI_MODULES_AVAILABLE['account_menu'] = True
            main_menu.add_item(create_submenu_item(
                "1", "Account Management", account_menu))
            print("DEBUG: Successfully added account menu")
        except (ImportError, SyntaxError, TypeError, AttributeError) as e:
            LOGGER.warning(f"Account menu not available: {e}")
            print(f"DEBUG: Detailed error in account menu: {e}")
            print(traceback.format_exc())

        # Try to import and create operation menu
        try:
            from ui.operation_menu import create_operation_menu
            operation_menu = create_operation_menu(main_menu)
            UI_MODULES_AVAILABLE['operation_menu'] = True
            main_menu.add_item(create_submenu_item(
                "2", "Member Operations", operation_menu))
            print("DEBUG: Successfully added operation menu")
        except (ImportError, SyntaxError, TypeError, AttributeError) as e:
            LOGGER.warning(f"Operation menu not available: {e}")
            print(f"DEBUG: Detailed error in operation menu: {e}")
            print(traceback.format_exc())

        # Try to import and create settings menu
        try:
            from ui.settings_menu import create_settings_menu
            settings_menu = create_settings_menu(main_menu)
            UI_MODULES_AVAILABLE['settings_menu'] = True
            main_menu.add_item(create_submenu_item(
                "3", "Settings", settings_menu))
            print("DEBUG: Successfully added settings menu")
        except (ImportError, SyntaxError, TypeError, AttributeError) as e:
            LOGGER.warning(f"Settings menu not available: {e}")
            print(f"DEBUG: Detailed error in settings menu: {e}")
            print(traceback.format_exc())

        # Add exit option
        main_menu.add_item(create_action_item(
            "q", "Exit", lambda: sys.exit(0)))
        print("DEBUG: Added exit option")

        # Create menu system with main menu
        menu_system = MenuSystem(main_menu)
        print("DEBUG: Created menu system instance")

        # Pass app_context to the menu system if it has a property for it
        if hasattr(menu_system, 'app_context'):
            menu_system.app_context = app_context

        return menu_system
    except Exception as e:
        LOGGER.error(f"Failed to initialize menu system: {e}")
        print(f"DEBUG: Detailed error in menu system initialization: {e}")
        print(traceback.format_exc())
        return None


def create_main_menu(menu_system):
    """
    Create the main menu.

    Args:
        menu_system: The menu system

    Returns:
        Dict: Menu configuration
    """
    # Define main menu options based on available modules
    options = []

    # Only add menu options for available modules
    if UI_MODULES_AVAILABLE.get('account_menu', False):
        options.append({
            'title': 'Manage Accounts',
            'action': lambda: menu_system.show_menu('account')
        })

    if UI_MODULES_AVAILABLE.get('operation_menu', False):
        options.append({
            'title': 'Manage Members',
            'action': lambda: menu_system.show_menu('operation')
        })

    if UI_MODULES_AVAILABLE.get('settings_menu', False):
        options.append({
            'title': 'Settings',
            'action': lambda: menu_system.show_menu('settings')
        })

    # Always add exit option
    options.append({
        'title': 'Exit',
        'action': lambda: sys.exit(0)
    })

    # If no menu modules are available, add a placeholder option
    if len(options) == 1:  # Only exit option is available
        options.insert(0, {
            'title': 'Show Account Summary',
            'action': lambda: display_account_summary(menu_system.app_context)
        })

    # Define menu header
    menu_header = {
        'title': 'Main Menu',
        'banner': 'TELEGRAM ACCOUNT MANAGER',
        'description': 'Please select an option:'
    }

    # Create menu configuration
    main_menu = {
        'options': options,
        'header': menu_header,
        'on_display': lambda: display_account_summary(menu_system.app_context)
    }

    return main_menu


def display_account_summary(app_context):
    """
    Display account summary.

    Args:
        app_context: The application context
    """
    # Access account manager
    account_manager = app_context.get_service('account_manager')
    if account_manager:
        account_count = account_manager.get_account_count()
        print_header("Account Summary")
        print(f"Total accounts: {account_count['total']}")
        print(f"- Active: {account_count['active']}")
        print(f"- Blocked: {account_count['blocked']}")
        print(f"- In cooldown: {account_count['cooldown']}")
        print(f"- Daily limit reached: {account_count['daily_limit_reached']}")
        print(f"- Unverified: {account_count['unverified']}")
        print("\n")


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

        # Set up signal handlers
        setup_signal_handlers(app_context, logger)

        # Display welcome message
        display_welcome_message()

        # Initialize menu system
        print("DEBUG: Starting menu initialization...")
        menu_system = initialize_menus(app_context)

        if menu_system:
            # Show main menu if menu system is available
            print("DEBUG: Menu system initialized, running menu...")
            menu_system.run()
        else:
            # Fallback to basic interface if menu system is not available
            clear_screen()
            print_banner("TELEGRAM ACCOUNT MANAGER")
            print_header("Account Summary")

            # Display account summary
            account_manager = app_context.get_service('account_manager')
            if account_manager:
                account_count = account_manager.get_account_count()
                print(f"Total accounts: {account_count['total']}")
                print(f"- Active: {account_count['active']}")
                print(f"- Blocked: {account_count['blocked']}")
                print(f"- In cooldown: {account_count['cooldown']}")
                print(
                    f"- Daily limit reached: {account_count['daily_limit_reached']}")
                print(f"- Unverified: {account_count['unverified']}")

            print("\nMenu system is not available due to errors.")
            print("Please fix the errors in UI modules to use the full interface.")
            print("\nPress Enter to exit...")
            input()

        return 0  # Success exit code

    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
        return 0  # Success exit code

    except Exception as exc:
        # Log the error
        error_msg = f"Unhandled exception: {str(exc)}"
        logger.critical(error_msg, exc_info=True)
        print(f"ERROR: {error_msg}")
        print("Detailed traceback:")
        traceback.print_exc()
        return 1  # Error exit code

    finally:
        # Clean up application resources
        if app_context is not None:
            cleanup_application(app_context, logger)


if __name__ == "__main__":
    sys.exit(main())
