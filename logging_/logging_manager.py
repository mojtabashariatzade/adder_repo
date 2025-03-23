# pylint: disable=missing-module-docstring
import logging
import os
import sys
import json
import traceback
from logging.handlers import RotatingFileHandler
from datetime import datetime
from colorama import Fore, Style, init

# Colors used for different log levels in console output
LOG_COLORS = {
    'DEBUG': Fore.BLUE,
    'INFO': Fore.GREEN,
    'WARNING': Fore.YELLOW,
    'ERROR': Fore.RED,
    'CRITICAL': Fore.MAGENTA
}


class ColorFormatter(logging.Formatter):
    """
    Custom formatter class for colorized console output
    """

    def format(self, record):
        # Select color based on log level
        color = LOG_COLORS.get(record.levelname, Fore.WHITE)

        # Format log message with color
        log_message = super().format(record)
        colored_message = f"{color}{log_message}{Style.RESET_ALL}"

        return colored_message


class JSONFormatter(logging.Formatter):
    """
    Custom formatter class for JSON output format
    Suitable for automated log processing
    """

    def format(self, record):
        # Create base dictionary with log information
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'name': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'funcName': record.funcName,
            'lineNo': record.lineno,
            'process': record.process,
            'thread': record.thread,
        }

        # Add exception information if available
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        # Add custom data if available
        if hasattr(record, 'data') and record.data:
            log_data['data'] = record.data

        # Convert to JSON
        return json.dumps(log_data, ensure_ascii=False)


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    Enhanced RotatingFileHandler with better error handling
    """

    def __init__(self, *args, **kwargs):
        self.fallback_stream = kwargs.pop('fallback_stream', sys.stderr)
        super().__init__(*args, **kwargs)

    def emit(self, record):
        try:
            super().emit(record)
        except (IOError, OSError, ValueError, TypeError) as e:
            self._handle_error(record, e)

    def _handle_error(self, record, error):
        """Handle errors when writing to log file"""
        error_msg = f"Error writing log to file {self.baseFilename}: {str(error)}"

        try:
            # Try to write to fallback stream
            self.fallback_stream.write(f"{error_msg}\n")
            self.fallback_stream.write(
                f"Original log message: {record.getMessage()}\n")
            self.fallback_stream.flush()
        except (IOError, ValueError):
            # If even fallback writing fails
            pass


class LoggingManager:
    """
    Centralized logging management for the application

    This class provides file and console logging capabilities and uses
    the Singleton pattern for easy access from all parts of the application.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """
        Singleton pattern implementation
        """
        if cls._instance is None:
            cls._instance = super(LoggingManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self,
                 log_dir="logs",
                 log_file="adder_repo.log",
                 max_file_size=5*1024*1024,  # 5 MB
                 backup_count=3,
                 default_level=logging.INFO,
                 console_level=None,
                 file_level=None,
                 json_log_enabled=False,
                 json_log_file=None):
        """
        Initialize logging management

        Parameters:
            log_dir (str): Directory for log files
            log_file (str): Log file name
            max_file_size (int): Maximum log file size in bytes
            backup_count (int): Number of backup files
            default_level (int): Default logging level
            console_level (int): Console logging level (if None, uses default_level)
            file_level (int): File logging level (if None, uses default_level)
            json_log_enabled (bool): Enable JSON logging
            json_log_file (str): JSON log file name (if None, uses log_file with .json extension)
        """

        # Prevent re-initialization
        if self._initialized:
            return

        # Initialize colorama for console color support
        init()

        self.log_dir = log_dir
        self.log_file = log_file
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.default_level = default_level
        self.console_level = console_level if console_level is not None else default_level
        self.file_level = file_level if file_level is not None else default_level
        self.json_log_enabled = json_log_enabled
        self.json_log_file = (json_log_file if json_log_file
                              else f"{os.path.splitext(log_file)[0]}.json")

        # Ensure log directory exists
        try:
            os.makedirs(self.log_dir, exist_ok=True)
        except (IOError, OSError, ValueError, TypeError) as e:
            sys.stderr.write(
                f"Error creating log directory {self.log_dir}: {str(e)}\n")
            # Use current directory if cannot create log directory
            self.log_dir = "."

        # Full paths to log files
        self.log_file_path = os.path.join(self.log_dir, self.log_file)
        self.json_log_file_path = os.path.join(
            self.log_dir, self.json_log_file)

        # Create formatters
        self.console_formatter = ColorFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.json_formatter = JSONFormatter()

        # Store created loggers
        self.loggers = {}

        # Logging system health status
        self.healthy = True
        self._initialized = True

    def get_logger(self, name):
        """
        Get a logger with the specified name

        Parameters:
            name (str): Logger name

        Returns:
            logging.Logger: Configured logger
        """
        # If logger already exists, return it
        if name in self.loggers:
            return self.loggers[name]

        # Create new logger
        local_logger = logging.getLogger(name)
        local_logger.setLevel(self.default_level)

        # Clear existing handlers to avoid duplicates
        if local_logger.handlers:
            local_logger.handlers.clear()

        try:
            # Add console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.console_level)
            console_handler.setFormatter(self.console_formatter)
            local_logger.addHandler(console_handler)

            # Add file handler with rotation and error handling
            try:
                file_handler = SafeRotatingFileHandler(
                    self.log_file_path,
                    maxBytes=self.max_file_size,
                    backupCount=self.backup_count,
                    encoding='utf-8',
                    fallback_stream=sys.stderr
                )
                file_handler.setLevel(self.file_level)
                file_handler.setFormatter(self.file_formatter)
                local_logger.addHandler(file_handler)
            except (IOError, OSError, ValueError, TypeError) as e:
                self.healthy = False
                error_msg = f"Error creating file handler: {str(e)}"
                local_logger.error(error_msg)
                sys.stderr.write(f"{error_msg}\n")

            # Add JSON handler if enabled
            if self.json_log_enabled:
                try:
                    json_handler = SafeRotatingFileHandler(
                        self.json_log_file_path,
                        maxBytes=self.max_file_size,
                        backupCount=self.backup_count,
                        encoding='utf-8',
                        fallback_stream=sys.stderr
                    )
                    json_handler.setLevel(self.file_level)
                    json_handler.setFormatter(self.json_formatter)
                    local_logger.addHandler(json_handler)
                except (IOError, OSError, ValueError, TypeError) as e:
                    error_msg = f"Error creating JSON handler: {str(e)}"
                    local_logger.error(error_msg)
                    sys.stderr.write(f"{error_msg}\n")

        except (IOError, OSError, ValueError, TypeError) as e:
            # Handle general error in logger setup
            self.healthy = False
            sys.stderr.write(
                f"General error in setting up logger {name}: {str(e)}\n")

            # Create at least a console handler to ensure functionality
            try:
                basic_handler = logging.StreamHandler(sys.stderr)
                basic_handler.setFormatter(
                    logging.Formatter('%(levelname)s - %(message)s'))
                local_logger.addHandler(basic_handler)
            except (ValueError, TypeError, AttributeError):
                pass

        # Store logger in dictionary
        self.loggers[name] = local_logger

        # Log status if logging system is unhealthy
        if not self.healthy:
            local_logger.warning(
                "Logging system initialized with issues. Some outputs may not be recorded.")

        return local_logger

    def set_level(self, level, logger_name=None):
        """
        Set logging level

        Parameters:
            level (int): New logging level
            logger_name (str): Logger name (if None, changes all loggers)
        """
        if logger_name is None:
            # Change level for all loggers
            for log_instance in self.loggers.values():
                log_instance.setLevel(level)
        elif logger_name in self.loggers:
            # Change level for specified logger
            self.loggers[logger_name].setLevel(level)

    def set_console_level(self, level, logger_name=None):
        """
        Set console logging level

        Parameters:
            level (int): New console logging level
            logger_name (str): Logger name (if None, changes all loggers)
        """
        self.console_level = level
        if logger_name is None:
            # Change console level for all loggers
            for log_instance in self.loggers.values():
                for handler in log_instance.handlers:
                    if (isinstance(handler, logging.StreamHandler) and
                            not isinstance(handler, logging.FileHandler)):
                        handler.setLevel(level)
        elif logger_name in self.loggers:
            # Change console level for specified logger
            log_instance = self.loggers[logger_name]
            for handler in log_instance.handlers:
                if (isinstance(handler, logging.StreamHandler) and
                        not isinstance(handler, logging.FileHandler)):
                    handler.setLevel(level)

    def set_file_level(self, level, logger_name=None):
        """
        Set file logging level

        Parameters:
            level (int): New file logging level
            logger_name (str): Logger name (if None, changes all loggers)
        """
        self.file_level = level
        if logger_name is None:
            # Change file level for all loggers
            for log_instance in self.loggers.values():
                for handler in log_instance.handlers:
                    if isinstance(handler, logging.FileHandler):
                        handler.setLevel(level)
        elif logger_name in self.loggers:
            # Change file level for specified logger
            log_instance = self.loggers[logger_name]
            for handler in log_instance.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.setLevel(level)

    def enable_json_logging(self, enable=True, logger_name=None, json_file=None):
        """
        Enable or disable JSON logging

        Parameters:
            enable (bool): Enablement status
            logger_name (str): Logger name (if None, applies to all loggers)
            json_file (str): JSON file name (if None, uses previous settings)
        """
        self.json_log_enabled = enable

        if json_file:
            self.json_log_file = json_file
            self.json_log_file_path = os.path.join(
                self.log_dir, self.json_log_file)

        if enable:
            # Add JSON handlers to loggers
            if logger_name is None:
                for name, log_instance in self.loggers.items():
                    # Check if JSON handler doesn't already exist
                    if not any(isinstance(h, logging.FileHandler) and
                               h.formatter == self.json_formatter
                               for h in log_instance.handlers):
                        self._add_json_handler(log_instance)
            elif logger_name in self.loggers:
                log_instance = self.loggers[logger_name]
                # Check if JSON handler doesn't already exist
                if not any(isinstance(h, logging.FileHandler) and
                           h.formatter == self.json_formatter
                           for h in logger.handlers):
                    self._add_json_handler(logger)
        else:
            # Remove JSON handlers from loggers
            if logger_name is None:
                for name, log_instance in self.loggers.items():
                    for handler in list(log_instance.handlers):
                        if (isinstance(handler, logging.FileHandler) and
                                handler.formatter == self.json_formatter):
                            logger.removeHandler(handler)
                            handler.close()
            elif logger_name in self.loggers:
                log_instance = self.loggers[logger_name]
                for handler in list(log_instance.handlers):
                    if isinstance(handler,
                                  logging.FileHandler) and handler.formatter == self.json_formatter:
                        logger.removeHandler(handler)
                        handler.close()

    def _add_json_handler(self, logger):
        """
        Add JSON handler to a logger

        Parameters:
            logger (logging.Logger): Target logger
        """
        try:
            json_handler = SafeRotatingFileHandler(
                self.json_log_file_path,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8',
                fallback_stream=sys.stderr
            )
            json_handler.setLevel(self.file_level)
            json_handler.setFormatter(self.json_formatter)
            logger.addHandler(json_handler)
        except (IOError, OSError, ValueError, TypeError) as e:
            error_msg = f"Error creating JSON handler: {str(e)}"
            logger.error(error_msg)
            sys.stderr.write(f"{error_msg}\n")

    def log_with_data(self, logger_name, level, message, data=None):
        """
        Log with additional data for JSON format

        Parameters:
            logger_name (str): Logger name
            level (int): Log level
            message (str): Log message
            data (dict): Additional data to log in JSON
        """
        if logger_name not in self.loggers:
            logger = self.get_logger(logger_name)
        else:
            logger = self.loggers[logger_name]

        # Create log record with custom data
        record = logger.makeRecord(
            logger.name, level, "", 0, message, (), None
        )
        record.data = data

        # Send record to all handlers
        logger.handle(record)

    def shutdown(self):
        """
        Close all loggers and release resources
        """
        for logger_name, logger in self.loggers.items():
            for handler in logger.handlers:
                try:
                    handler.close()
                    logger.removeHandler(handler)
                except:
                    pass

        self.loggers.clear()

    def create_timestamped_logger(self, base_name):
        """
        Create a logger with timestamp in name for work sessions

        Parameters:
            base_name (str): Base logger name

        Returns:
            logging.Logger: Logger with timestamped name
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger_name = f"{base_name}_{timestamp}"
        return self.get_logger(logger_name)

    def health_check(self):
        """
        Check logging system health

        Verifies if the logging system is functioning correctly

        Returns:
            tuple: (healthy, issues) health status and list of issues
        """
        issues = []

        # Check log directory
        if not os.path.exists(self.log_dir):
            issues.append(f"Log directory {self.log_dir} does not exist")

        # Check log file access
        if os.path.exists(self.log_file_path):
            if not os.access(self.log_file_path, os.W_OK):
                issues.append(
                    f"No write access to log file {self.log_file_path}")
        else:
            try:
                # Try to create file
                with open(self.log_file_path, 'a'):
                    pass
                os.remove(self.log_file_path)  # Remove test file
            except (IOError, OSError, ValueError, TypeError) as e:
                issues.append(
                    f"Error creating log file {self.log_file_path}: {str(e)}")

        # Check JSON file if enabled
        if self.json_log_enabled:
            if os.path.exists(self.json_log_file_path):
                if not os.access(self.json_log_file_path, os.W_OK):
                    issues.append(
                        f"No write access to JSON file {self.json_log_file_path}")
            else:
                try:
                    # Try to create file
                    with open(self.json_log_file_path, 'a'):
                        pass
                    os.remove(self.json_log_file_path)  # Remove test file
                except (IOError, OSError, ValueError, TypeError) as e:
                    issues.append(
                        f"Error creating JSON file {self.json_log_file_path}: {str(e)}")

        # Check overall status
        healthy = len(issues) == 0 and self.healthy

        return healthy, issues


# Usage examples
def get_logger(name="AdderRepo"):
    """
    Helper function to get a logger

    Parameters:
        name (str): Logger name

    Returns:
        logging.Logger: Configured logger
    """
    # Use default values
    logging_manager = LoggingManager()
    return logging_manager.get_logger(name)


def get_json_logger(name="AdderRepo", json_file=None):
    """
    Helper function to get a logger with JSON capability

    Parameters:
        name (str): Logger name
        json_file (str): JSON file name (optional)

    Returns:
        logging.Logger: Configured logger with JSON capability
    """
    # Use default values with JSON enabled
    logging_manager = LoggingManager(
        json_log_enabled=True, json_log_file=json_file)
    return logging_manager.get_logger(name)


# Simple test example
if __name__ == "__main__":
    # This code only runs when the file is executed directly

    # Regular logger
    logger = get_logger("TestLogger")

    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")

    # Logger with JSON support
    json_logger = get_json_logger("JSONLogger")

    json_logger.info("This is a message with JSON format")

    # Log with additional data
    logging_manager = LoggingManager()
    logging_manager.log_with_data(
        "JSONLogger",
        logging.INFO,
        "Log message with custom data",
        {
            "user_id": 12345,
            "action": "login",
            "ip": "192.168.1.1",
            "browser": "Chrome",
            "success": True
        }
    )

    # Check logging system health
    healthy, issues = logging_manager.health_check()
    print(
        f"Logging system health status: {'Healthy' if healthy else 'Unhealthy'}")
    if issues:
        print("Identified issues:")
        for issue in issues:
            print(f"- {issue}")
    print("Logging test completed. Check log files in the logs directory.")
