"""
This module is the main entry point of the application.
It initializes the application, sets up logging, and runs the main menu.
"""
import sys
import logging

from core.config import Config
from core.exceptions import TelegramAdderError
import logging_.logging_manager
import utils.app_context
import ui.menu_system
from services.account_manager import AccountManager

logger = logging.getLogger(__name__)


def main():
    """
    Main entry point of the application.
    """
    try:
        # 1. Configure the application
        config = Config()
        config.load()  # Load settings from file

        # 2. Set up logging system
        logging_manager = logging_.logging_manager.LoggingManager(config)
        # logging_manager.setup_logging()  # REMOVED: setup_logging call
        logger.info("Logging system initialized.")

        # 3. Create Application Context
        app_context: utils.app_context.AppContext = utils.app_context.AppContext()
        app_context.register_service("config", config)
        app_context.register_service("logging_manager", logging_manager)

        # 4. Create Account Manager (if needed)
        account_manager = AccountManager()  # Changed: No arguments
        app_context.register_service("account_manager", account_manager)

        # 5. Initialize main menu
        menu_system = ui.menu_system.MenuSystem(config, app_context)
        app_context.register_service("menu_system", menu_system)

        # 6. Display main menu and run the application
        menu_system.run()

    except TelegramAdderError as e:
        logger.error("Critical application error: %s", e)
        print(f"Critical error: {e}. Please check the log file.")
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected application error: %s", e)
        print("Unexpected error. Please check the log file.")
        sys.exit(1)
    finally:
        logger.info("Application finished.")


if __name__ == "__main__":
    main()
