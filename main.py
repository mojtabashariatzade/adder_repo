import sys
from utils.app_context import AppContext
from ui.menu_system import MenuSystem
from logging_.logging_manager import LoggingManager
from error_handling.error_manager import ErrorManager


def setup_logging(app_context):
    logging_manager = LoggingManager(app_context=app_context)
    app_context.register_service('logging_manager', logging_manager)


def setup_error_handling(app_context):
    error_manager = ErrorManager()
    app_context.register_service('error_manager', error_manager)


def main():
    # Initialize the application context
    with AppContext() as app_context:
        try:
            # Set up logging
            setup_logging(app_context)

            # Set up error handling
            setup_error_handling(app_context)

            # Register services
            from services.account_manager import AccountManager
            account_manager = AccountManager(app_context=app_context)
            app_context.register_service('account_manager', account_manager)

            from services.group_manager import GroupManager
            group_manager = GroupManager(app_context=app_context)
            app_context.register_service('group_manager', group_manager)

            from services.proxy_manager import ProxyManager
            proxy_manager = ProxyManager(app_context=app_context)
            app_context.register_service('proxy_manager', proxy_manager)

            from strategies.strategy_selector import StrategySelector
            strategy_selector = StrategySelector()
            app_context.register_service(
                'strategy_selector', strategy_selector)

            from models.stats import MetricsCollector
            metrics_collector = MetricsCollector(app_context=app_context)
            app_context.register_service(
                'metrics_collector', metrics_collector)

            # Initialize services
            app_context.initialize()

            # Display the main menu
            menu_system = MenuSystem(app_context)
            menu_system.run()

        except Exception as e:
            error_manager = app_context.get_service('error_manager')
            error_manager.handle(e)
            sys.exit(1)
        finally:
            # Clean up resources
            app_context.shutdown()


if __name__ == "__main__":
    main()
