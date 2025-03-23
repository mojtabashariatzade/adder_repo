"""
Tests for the logging_/formatters.py module.

This module contains unit tests for the various log formatters in the formatters.py module:
- ColorFormatter
- JSONFormatter
- DetailedFormatter
- CompactFormatter
- HTMLFormatter
- ConfigurableFormatter
"""

import unittest
import logging
import json
import os
import sys
import io
import re
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the formatters module
from logging_.formatters import (
    ColorFormatter,
    JSONFormatter,
    DetailedFormatter,
    CompactFormatter,
    HTMLFormatter,
    ConfigurableFormatter,
    LogColors
)


class TestLogColors(unittest.TestCase):
    """Test the LogColors helper class."""

    def test_get_level_colors(self):
        """Test that the level colors dictionary contains expected keys."""
        colors = LogColors.get_level_colors()

        # Check that we have colors for all standard log levels
        expected_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        for level in expected_levels:
            self.assertIn(level, colors)
            self.assertIsNotNone(colors[level])

    def test_get_reset(self):
        """Test that the reset code is not empty."""
        reset_code = LogColors.get_reset()
        self.assertIsNotNone(reset_code)
        self.assertNotEqual(reset_code, '')


class TestColorFormatter(unittest.TestCase):
    """Test the ColorFormatter class."""

    def setUp(self):
        """Set up a logger and handler for testing."""
        self.log_capture = io.StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        self.logger = logging.getLogger("test_color_formatter")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)

        # Remove all other handlers to avoid interference
        for handler in self.logger.handlers[:]:
            if handler is not self.handler:
                self.logger.removeHandler(handler)

    def test_format_with_colors(self):
        """Test that log messages are formatted with colors."""
        formatter = ColorFormatter()
        self.handler.setFormatter(formatter)

        # Log messages at different levels
        self.logger.debug("Debug message")
        self.logger.info("Info message")
        self.logger.warning("Warning message")
        self.logger.error("Error message")
        self.logger.critical("Critical message")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that colors are present
        colors = LogColors.get_level_colors()
        reset = LogColors.get_reset()

        for level, color in colors.items():
            # For each log level, there should be a message with its color code
            if level == 'DEBUG':
                self.assertIn(f"{color}", log_output)
                self.assertIn("Debug message", log_output)
            if level == 'INFO':
                self.assertIn(f"{color}", log_output)
                self.assertIn("Info message", log_output)
            if level == 'WARNING':
                self.assertIn(f"{color}", log_output)
                self.assertIn("Warning message", log_output)
            if level == 'ERROR':
                self.assertIn(f"{color}", log_output)
                self.assertIn("Error message", log_output)
            if level == 'CRITICAL':
                self.assertIn(f"{color}", log_output)
                self.assertIn("Critical message", log_output)

        # Check that reset code is present
        self.assertIn(reset, log_output)

    def test_format_with_hostname(self):
        """Test that hostname is included when requested."""
        formatter = ColorFormatter(include_hostname=True)
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test with hostname")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check for hostname
        import socket
        hostname = socket.gethostname()
        self.assertIn(hostname, log_output)


class TestJSONFormatter(unittest.TestCase):
    """Test the JSONFormatter class."""

    def setUp(self):
        """Set up a logger and handler for testing."""
        self.log_capture = io.StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        self.logger = logging.getLogger("test_json_formatter")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)

        # Remove all other handlers to avoid interference
        for handler in self.logger.handlers[:]:
            if handler is not self.handler:
                self.logger.removeHandler(handler)

    def test_format_as_json(self):
        """Test that log records are formatted as valid JSON."""
        formatter = JSONFormatter()
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test JSON formatting")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that it's valid JSON
        try:
            log_data = json.loads(log_output)
            self.assertIsInstance(log_data, dict)
        except json.JSONDecodeError:
            self.fail("Log output is not valid JSON")

        # Check required fields
        self.assertIn('timestamp', log_data)
        self.assertIn('level', log_data)
        self.assertEqual(log_data['level'], 'INFO')
        self.assertIn('name', log_data)
        self.assertEqual(log_data['name'], 'test_json_formatter')
        self.assertIn('message', log_data)
        self.assertEqual(log_data['message'], 'Test JSON formatting')

    def test_format_with_exception(self):
        """Test that exceptions are correctly included in JSON format."""
        formatter = JSONFormatter()
        self.handler.setFormatter(formatter)

        # Log an exception
        try:
            raise ValueError("Test exception")
        except ValueError:
            self.logger.exception("Exception occurred")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Parse as JSON
        log_data = json.loads(log_output)

        # Check exception fields
        self.assertIn('exception', log_data)
        self.assertEqual(log_data['exception']['type'], 'ValueError')
        self.assertEqual(log_data['exception']['message'], 'Test exception')
        self.assertIsInstance(log_data['exception']['traceback'], list)

    def test_custom_data(self):
        """Test that custom data is included in the JSON output."""
        formatter = JSONFormatter()
        self.handler.setFormatter(formatter)

        # Create a log record with custom data
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=42,
            msg="Test with custom data",
            args=(),
            exc_info=None
        )

        # Add custom data
        record.data = {"user_id": 12345, "action": "login"}

        # Format the record
        output = formatter.format(record)

        # Parse as JSON
        log_data = json.loads(output)

        # Check custom data
        self.assertIn('data', log_data)
        self.assertEqual(log_data['data']['user_id'], 12345)
        self.assertEqual(log_data['data']['action'], 'login')


class TestDetailedFormatter(unittest.TestCase):
    """Test the DetailedFormatter class."""

    def setUp(self):
        """Set up a logger and handler for testing."""
        self.log_capture = io.StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        self.logger = logging.getLogger("test_detailed_formatter")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)

        # Remove all other handlers to avoid interference
        for handler in self.logger.handlers[:]:
            if handler is not self.handler:
                self.logger.removeHandler(handler)

    def test_format_with_path_and_function(self):
        """Test that log messages include path and function info."""
        formatter = DetailedFormatter(show_path=True, show_function=True)
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test detailed formatting")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check for path and function info
        self.assertIn(__file__, log_output)  # Should contain file path
        self.assertIn("test_format_with_path_and_function", log_output)  # Should contain function name

    def test_format_without_path(self):
        """Test that log messages don't include path when not requested."""
        formatter = DetailedFormatter(show_path=False, show_function=True)
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test without path")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Should not contain file path
        self.assertNotIn(__file__, log_output)

        # Should still contain function name
        self.assertIn("test_format_without_path", log_output)

    def test_format_exception(self):
        """Test that exceptions are formatted with additional info."""
        formatter = DetailedFormatter()
        self.handler.setFormatter(formatter)

        # Log an exception
        try:
            raise ValueError("Test exception")
        except ValueError:
            self.logger.exception("Exception occurred")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check for exception info
        self.assertIn("Traceback", log_output)
        self.assertIn("ValueError: Test exception", log_output)

        # Check for system information
        self.assertIn("System Information:", log_output)
        self.assertIn("Platform:", log_output)
        self.assertIn("Python Version:", log_output)


class TestCompactFormatter(unittest.TestCase):
    """Test the CompactFormatter class."""

    def setUp(self):
        """Set up a logger and handler for testing."""
        self.log_capture = io.StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        self.logger = logging.getLogger("test_compact_formatter")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)

        # Remove all other handlers to avoid interference
        for handler in self.logger.handlers[:]:
            if handler is not self.handler:
                self.logger.removeHandler(handler)

    def test_format_compact(self):
        """Test that log messages are formatted compactly."""
        formatter = CompactFormatter()
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test compact formatting")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that it's a single line
        line_count = len(log_output.splitlines())
        self.assertEqual(line_count, 1)

        # Check format: should be "HH:MM:SS I:logger:message"
        # The first character of the level name is used
        self.assertRegex(log_output, r'\d{2}:\d{2}:\d{2} I:test_compact_formatter:Test compact formatting')

    def test_abbreviation(self):
        """Test that long logger names are abbreviated."""
        # Create a logger with a long name
        long_logger = logging.getLogger("very.long.logger.name.test")
        long_logger.setLevel(logging.DEBUG)
        long_logger.addHandler(self.handler)

        formatter = CompactFormatter()
        self.handler.setFormatter(formatter)

        # Log a message
        long_logger.info("Test abbreviation")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Instead of "very.long.logger.name.test", it should be abbreviated
        # The abbreviated name would be "v.l.l.n.test"
        self.assertNotIn("very.long.logger.name.test", log_output)

        # CompactFormatter actually does abbreviate the name in its format method
        self.assertIn("I:v.l.l.n.test:Test abbreviation", log_output)

    def test_without_timestamp(self):
        """Test formatting without timestamp."""
        formatter = CompactFormatter(include_timestamp=False)
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test without timestamp")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that there is no timestamp (HH:MM:SS)
        time_pattern = r'\d{2}:\d{2}:\d{2}'
        self.assertNotRegex(log_output, time_pattern)

        # Should just be "I:logger:message"
        self.assertEqual(log_output.strip(), "I:test_compact_formatter:Test without timestamp")


class TestHTMLFormatter(unittest.TestCase):
    """Test the HTMLFormatter class."""

    def setUp(self):
        """Set up a logger and handler for testing."""
        self.log_capture = io.StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        self.logger = logging.getLogger("test_html_formatter")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)

        # Remove all other handlers to avoid interference
        for handler in self.logger.handlers[:]:
            if handler is not self.handler:
                self.logger.removeHandler(handler)

    def test_format_as_html(self):
        """Test that log messages are formatted as HTML."""
        formatter = HTMLFormatter()
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test HTML formatting")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that it contains HTML elements
        self.assertIn('<div class="log-entry">', log_output)
        self.assertIn('<span class="timestamp">', log_output)
        self.assertIn('<span class="logger">test_html_formatter</span>', log_output)
        self.assertIn('<span class="message">Test HTML formatting</span>', log_output)

    def test_format_with_exception(self):
        """Test that exceptions are included in HTML format."""
        formatter = HTMLFormatter()
        self.handler.setFormatter(formatter)

        # Log an exception
        try:
            raise ValueError("HTML test exception")
        except ValueError:
            self.logger.exception("Exception in HTML")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check for exception information
        self.assertIn('<pre>', log_output)
        self.assertIn('Traceback', log_output)
        self.assertIn('ValueError: HTML test exception', log_output)
        self.assertIn('</pre>', log_output)

    def test_html_escaping(self):
        """Test that HTML characters are properly escaped."""
        formatter = HTMLFormatter()
        self.handler.setFormatter(formatter)

        # Log a message with HTML characters
        self.logger.info("Test with <script>alert('xss')</script> & other < > chars")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that HTML is escaped
        self.assertIn('&lt;script&gt;', log_output)
        self.assertIn('&amp; other &lt; &gt; chars', log_output)

    def test_format_header_footer(self):
        """Test the HTML header and footer generation."""
        formatter = HTMLFormatter(title="Test Logs")

        # Check header
        header = formatter.format_header()
        self.assertIn('<title>Test Logs</title>', header)
        self.assertIn('<h1>Test Logs</h1>', header)
        self.assertIn('<style>', header)

        # Check footer
        footer = formatter.format_footer()
        self.assertIn('</div>', footer)
        self.assertIn('</body>', footer)
        self.assertIn('</html>', footer)


class TestConfigurableFormatter(unittest.TestCase):
    """Test the ConfigurableFormatter class."""

    def setUp(self):
        """Set up a logger and handler for testing."""
        self.log_capture = io.StringIO()
        self.handler = logging.StreamHandler(self.log_capture)
        self.logger = logging.getLogger("test_configurable_formatter")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)

        # Remove all other handlers to avoid interference
        for handler in self.logger.handlers[:]:
            if handler is not self.handler:
                self.logger.removeHandler(handler)

    def test_simple_template(self):
        """Test formatting with a simple template."""
        template = "{asctime} - {name} - {levelname} - {message}"
        formatter = ConfigurableFormatter(template)
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test configurable formatting")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that template was used correctly
        # The format should match: "timestamp - loggername - LEVEL - message"
        pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - test_configurable_formatter - INFO - Test configurable formatting'
        self.assertRegex(log_output, pattern)

    def test_processor(self):
        """Test using a field processor."""
        # Create a template that uses the upper processor
        template = "{levelname:upper} - {message}"
        formatter = ConfigurableFormatter(template)
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test with processor")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that the processor was applied
        # levelname "INFO" should be transformed to "INFO" (upper)
        self.assertEqual(log_output.strip(), "INFO - Test with processor")

    def test_custom_processor(self):
        """Test with a custom processor."""
        # Define a custom processor
        def reverse_text(text):
            return text[::-1]

        # Create a formatter with the custom processor
        template = "{message:reverse}"
        processors = {"reverse": reverse_text}
        formatter = ConfigurableFormatter(template, processors=processors)
        self.handler.setFormatter(formatter)

        # Log a message
        self.logger.info("Test custom processor")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that the custom processor was applied
        self.assertEqual(log_output.strip(), "rossecorp motsuc tseT")

    def test_default_processors(self):
        """Test the default processors."""
        # Create a template that uses multiple processors
        template = "{name:abbreviated} {levelname:first_char} - {message}"
        formatter = ConfigurableFormatter(template)
        self.handler.setFormatter(formatter)

        # Set up a logger with a multi-part name
        nested_logger = logging.getLogger("parent.child.test_logger")
        nested_logger.setLevel(logging.DEBUG)
        nested_logger.addHandler(self.handler)

        # Log a message
        nested_logger.info("Test default processors")

        # Get captured log output
        log_output = self.log_capture.getvalue()

        # Check that the processors were applied:
        # - abbreviated: "parent.child.test_logger" -> "p.c.test_logger"
        # - first_char: "INFO" -> "I"
        self.assertIn("p.c.test_logger I - Test default processors", log_output)


if __name__ == '__main__':
    unittest.main()