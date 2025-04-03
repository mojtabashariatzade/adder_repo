"""
Logging package for Telegram Adder application.
"""

# Direct imports to make modules available
try:
    from .logging_manager import LoggingManager, get_logger, get_json_logger
except ImportError:
    # For development use - these may not be available yet
    pass