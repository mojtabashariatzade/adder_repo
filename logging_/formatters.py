"""
Log Formatters Module

This module provides custom log formatters for the Telegram Adder application.
It defines formatters for different output formats, including colorized console output,
JSON output, and detailed formats for various log destinations.

Features:
- ColorFormatter: Colorizes log output based on log level for console display
- JSONFormatter: Formats log records as JSON for machine readability
- DetailedFormatter: Provides detailed formatting with optional source information
- CompactFormatter: Simple, concise format for space-constrained environments
- HTMLFormatter: Formats logs as HTML for web interfaces
- ConfigurableFormatter: Customizable formatter with template-based formatting

Usage:
    from logging_.formatters import ColorFormatter, JSONFormatter

    # Set up console handler with color formatting
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter())

    # Set up file handler with JSON formatting
    json_handler = logging.FileHandler("app.json.log")
    json_handler.setFormatter(JSONFormatter())
"""

import logging
import json
import traceback
from datetime import datetime
import socket
import os
import sys
import platform
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union, Tuple

try:
    from colorama import Fore, Back, Style, init as colorama_init
    COLORAMA_AVAILABLE = True
    colorama_init()
except ImportError:
    COLORAMA_AVAILABLE = False


class LogColors:
    """
    Defines color mappings for log levels.

    This class provides color codes for different log levels, with fallbacks
    for environments where colorama is not available.
    """

    class ANSI(Enum):
        """ANSI color codes for terminal output."""
        RESET = '\033[0m'
        BOLD = '\033[1m'

        # Foreground colors
        BLACK = '\033[30m'
        RED = '\033[31m'
        GREEN = '\033[32m'
        YELLOW = '\033[33m'
        BLUE = '\033[34m'
        MAGENTA = '\033[35m'
        CYAN = '\033[36m'
        WHITE = '\033[37m'

        # Background colors
        BG_BLACK = '\033[40m'
        BG_RED = '\033[41m'
        BG_GREEN = '\033[42m'
        BG_YELLOW = '\033[43m'
        BG_BLUE = '\033[44m'
        BG_MAGENTA = '\033[45m'
        BG_CYAN = '\033[46m'
        BG_WHITE = '\033[47m'

    @staticmethod
    def get_level_colors() -> Dict[str, str]:
        """
        Get colors for different log levels.

        Returns:
            Dict[str, str]: Map of log level names to color codes
        """
        if COLORAMA_AVAILABLE:
            return {
                'DEBUG': Fore.BLUE,
                'INFO': Fore.GREEN,
                'WARNING': Fore.YELLOW,
                'ERROR': Fore.RED,
                'CRITICAL': Fore.MAGENTA
            }
        else:
            return {
                'DEBUG': LogColors.ANSI.BLUE.value,
                'INFO': LogColors.ANSI.GREEN.value,
                'WARNING': LogColors.ANSI.YELLOW.value,
                'ERROR': LogColors.ANSI.RED.value,
                'CRITICAL': LogColors.ANSI.MAGENTA.value
            }

    @staticmethod
    def get_reset() -> str:
        """
        Get the reset code to return to normal text formatting.

        Returns:
            str: Reset code
        """
        if COLORAMA_AVAILABLE:
            return Style.RESET_ALL
        else:
            return LogColors.ANSI.RESET.value


class ColorFormatter(logging.Formatter):
    """
    Formats log records with colorized output based on the log level.

    This formatter colorizes the log output in the console to make it easier
    to distinguish between different log levels at a glance.
    """

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, style: str = '%',
                include_hostname: bool = False):
        """
        Initialize the ColorFormatter.

        Args:
            fmt (Optional[str]): Format string for log messages.
                If None, uses a default format.
            datefmt (Optional[str]): Format string for dates.
                If None, uses ISO format.
            style (str): Style of format string (%, {, or $).
            include_hostname (bool): Whether to include the hostname in the log.
        """
        if fmt is None:
            if include_hostname:
                hostname = socket.gethostname()
                fmt = f'%(asctime)s - {hostname} - %(name)s - %(levelname)s - %(message)s'
            else:
                fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
        self.level_colors = LogColors.get_level_colors()
        self.reset_code = LogColors.get_reset()

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with appropriate colors.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: Colorized log message.
        """
        # Format the message using the parent class
        formatted_message = super().format(record)

        # Apply color based on log level
        level_name = record.levelname
        color = self.level_colors.get(level_name, '')

        # Return colorized message
        return f"{color}{formatted_message}{self.reset_code}"


class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON objects.

    This formatter outputs logs in a structured JSON format, making it easier
    to parse and analyze logs programmatically or with log management tools.
    """

    def __init__(self, include_extra_fields: bool = True, indent: Optional[int] = None):
        """
        Initialize the JSONFormatter.

        Args:
            include_extra_fields (bool): Whether to include additional fields like
                process ID, thread ID, etc.
            indent (Optional[int]): Indentation level for pretty-printing.
                None for compact JSON (no pretty-printing).
        """
        super().__init__()
        self.include_extra_fields = include_extra_fields
        self.indent = indent

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON string.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: JSON-formatted log message.
        """
        # Create base dictionary with log information
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'name': record.name,
            'message': record.getMessage(),
        }

        # Add source information
        log_data.update({
            'module': record.module,
            'funcName': record.funcName,
            'lineNo': record.lineno,
        })

        # Add extra fields if requested
        if self.include_extra_fields:
            log_data.update({
                'process': record.process,
                'processName': record.processName,
                'thread': record.thread,
                'threadName': record.threadName,
                'msecs': record.msecs,
                'relativeCreated': record.relativeCreated,
            })

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
        return json.dumps(log_data, ensure_ascii=False, indent=self.indent)


class DetailedFormatter(logging.Formatter):
    """
    Provides detailed log formatting with source code information.

    This formatter includes detailed information about the source of the log,
    including file paths, function names, and line numbers.
    """

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, style: str = '%',
                show_path: bool = True, show_function: bool = True):
        """
        Initialize the DetailedFormatter.

        Args:
            fmt (Optional[str]): Format string for log messages.
                If None, uses a detailed default format.
            datefmt (Optional[str]): Format string for dates.
                If None, uses ISO format.
            style (str): Style of format string (%, {, or $).
            show_path (bool): Whether to include the file path in the log.
            show_function (bool): Whether to include the function name in the log.
        """
        if fmt is None:
            fmt = '%(asctime)s [%(process)d:%(thread)d] %(levelname)s'

            if show_path:
                fmt += ' [%(pathname)s:%(lineno)d]'

            if show_function:
                fmt += ' [%(funcName)s]'

            fmt += ' - %(message)s'

        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def formatException(self, ei) -> str:
        """
        Format an exception with detailed traceback.

        Args:
            ei: Exception information tuple from sys.exc_info().

        Returns:
            str: Formatted exception information.
        """
        # Get the standard traceback
        result = super().formatException(ei)

        # Add additional system information
        result += f"\n\nSystem Information:\n"
        result += f"  Platform: {platform.platform()}\n"
        result += f"  Python Version: {platform.python_version()}\n"
        result += f"  Time: {datetime.now().isoformat()}\n"

        return result


class CompactFormatter(logging.Formatter):
    """
    Formats log records in a compact single-line format.

    This formatter is designed for space-constrained environments where logs
    need to be kept as concise as possible.
    """

    def __init__(self, include_timestamp: bool = True):
        """
        Initialize the CompactFormatter.

        Args:
            include_timestamp (bool): Whether to include a timestamp.
        """
        fmt = ''
        if include_timestamp:
            fmt = '%(asctime)s '

        fmt += '%(levelname).1s:%(name)s:%(message)s'
        super().__init__(fmt=fmt, datefmt='%H:%M:%S')

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record compactly.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: Compactly formatted log message.
        """
        # Abbreviate the logger name to save space
        original_name = record.name
        name_parts = original_name.split('.')

        if len(name_parts) > 2:
            abbreviated_parts = [part[0] for part in name_parts[:-1]]
            abbreviated_parts.append(name_parts[-1])
            record.name = '.'.join(abbreviated_parts)

        # Format the message
        formatted_message = super().format(record)

        # Restore the original name
        record.name = original_name

        return formatted_message


class HTMLFormatter(logging.Formatter):
    """
    Formats log records as HTML for web display.

    This formatter outputs logs in an HTML format, making it suitable for
    web interfaces or HTML reports.
    """

    def __init__(self, title: str = "Application Logs"):
        """
        Initialize the HTMLFormatter.

        Args:
            title (str): Title for the HTML document.
        """
        super().__init__()
        self.title = title

        # Define CSS styles for different log levels
        self.level_styles = {
            'DEBUG': 'color: #6c757d;',  # Gray
            'INFO': 'color: #28a745;',   # Green
            'WARNING': 'color: #ffc107;', # Yellow
            'ERROR': 'color: #dc3545;',   # Red
            'CRITICAL': 'color: #dc3545; font-weight: bold;', # Bold red
        }

    def format_header(self) -> str:
        """
        Generate the HTML header with styles.

        Returns:
            str: HTML header.
        """
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .log-entry {{ margin-bottom: 4px; }}
        .timestamp {{ color: #6c757d; }}
        .logger {{ color: #007bff; font-weight: bold; }}
        pre {{ margin: 10px 0; padding: 10px; background-color: #f8f9fa; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>{self.title}</h1>
    <div class="log-container">
"""

    def format_footer(self) -> str:
        """
        Generate the HTML footer.

        Returns:
            str: HTML footer.
        """
        return """    </div>
</body>
</html>"""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as an HTML entry.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: HTML-formatted log entry.
        """
        # Get the log message
        message = record.getMessage()

        # Escape HTML special characters
        message = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Format the timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')

        # Get the style for this log level
        level_style = self.level_styles.get(record.levelname, '')

        # Format exception information if available
        exception_html = ""
        if record.exc_info:
            exception_text = self.formatException(record.exc_info)
            exception_text = exception_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            exception_html = f'<pre>{exception_text}</pre>'

        # Construct the HTML entry
        return f"""        <div class="log-entry">
            <span class="timestamp">[{timestamp}]</span>
            <span class="logger">{record.name}</span>:
            <span style="{level_style}">{record.levelname}</span> -
            <span class="message">{message}</span>
            {exception_html}
        </div>
"""


class ConfigurableFormatter(logging.Formatter):
    """
    Highly configurable formatter with template-based formatting.

    This formatter allows users to define custom templates for formatting log
    records, as well as custom processing functions for fields.
    """

    def __init__(self, template: str, processors: Optional[Dict[str, callable]] = None,
                 datefmt: Optional[str] = None):
        """
        Initialize the ConfigurableFormatter.

        Args:
            template (str): Template string for formatting logs. Use {field_name}
                for standard fields and {field_name:processor_name} for processed fields.
            processors (Optional[Dict[str, callable]]): Dictionary mapping processor names
                to functions that process field values.
            datefmt (Optional[str]): Date format string.
        """
        super().__init__(datefmt=datefmt)
        self.template = template
        self.processors = processors or {}

        # Add some default processors
        self._add_default_processors()

    def _add_default_processors(self):
        """Add default processors to the processor dictionary."""
        default_processors = {
            'upper': str.upper,
            'lower': str.lower,
            'title': str.title,
            'first_char': lambda s: s[0] if s else '',
            'abbreviated': lambda s: '.'.join(part[0] for part in s.split('.')[:-1]) + '.' + s.split('.')[-1]
                           if '.' in s else s,
        }

        # Only add defaults if they don't already exist
        for name, processor in default_processors.items():
            if name not in self.processors:
                self.processors[name] = processor

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record using the template.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: Formatted log message according to the template.
        """
        # Create a dictionary of all available record attributes
        record_dict = {
            'name': record.name,
            'levelname': record.levelname,
            'levelno': record.levelno,
            'pathname': record.pathname,
            'filename': record.filename,
            'module': record.module,
            'lineno': record.lineno,
            'funcName': record.funcName,
            'created': record.created,
            'asctime': self.formatTime(record, self.datefmt),
            'msecs': record.msecs,
            'relativeCreated': record.relativeCreated,
            'thread': record.thread,
            'threadName': record.threadName,
            'process': record.process,
            'processName': record.processName,
            'message': record.getMessage(),
        }

        # Add exception info if available
        if record.exc_info:
            record_dict['exc_text'] = self.formatException(record.exc_info)
        else:
            record_dict['exc_text'] = ""

        # Add stack info if available
        if record.stack_info:
            record_dict['stack_info'] = self.formatStack(record.stack_info)
        else:
            record_dict['stack_info'] = ""

        # Format the template using the record dictionary and processors
        # This is a simplified implementation - a real one would use a proper template engine
        result = self.template

        # First replace simple fields without processors
        for field, value in record_dict.items():
            result = result.replace(f"{{{field}}}", str(value))

        # Then handle fields with processors
        import re
        processor_pattern = r'\{(\w+):(\w+)\}'
        matches = re.findall(processor_pattern, result)

        for field, processor_name in matches:
            if field in record_dict and processor_name in self.processors:
                value = record_dict[field]
                processed_value = self.processors[processor_name](value)
                result = result.replace(f"{{{field}:{processor_name}}}", str(processed_value))

        return result