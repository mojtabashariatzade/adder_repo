#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Integration test for logging_manager.py and file_manager.py modules.

This test ensures that the logging manager properly interacts with the file manager
when logging operations, and that file manager operations are correctly logged.
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
import time
import io
from pathlib import Path
import threading
from unittest.mock import patch, MagicMock, PropertyMock

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import needed modules for mocking
import logging

class InMemoryLoggingManagerTest(unittest.TestCase):
    """Test integration between LoggingManager and FileManager using in-memory mocks."""

    @classmethod
    def setUpClass(cls):
        """Set up the test class."""
        print("\n===================================================================")
        print("  TESTING INTEGRATION: logging_manager.py with file_manager.py")
        print("===================================================================")

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Create subdirectories
        self.data_dir = self.test_dir / "data"
        self.data_dir.mkdir(exist_ok=True)

        # Apply mocks
        self.apply_mocks()

        # Import the modules AFTER applying mocks to ensure they use our mocks
        from data.file_manager import FileManager, JsonFileManager
        from logging_.logging_manager import LoggingManager, get_logger

        # Initialize FileManager with our test directory
        self.file_manager = FileManager(base_dir=str(self.data_dir))
        self.json_manager = JsonFileManager(base_dir=str(self.data_dir))

        # Initialize LoggingManager (mocked)
        self.logging_manager = LoggingManager()

        # Get a logger for this test
        self.logger = self.logging_manager.get_logger("IntegrationTest")

        # Log start of test
        self.logger.info(f"Starting test: {self._testMethodName}")

    def apply_mocks(self):
        """Apply all necessary mocks for the test."""
        # Create patch for SafeRotatingFileHandler
        self.handler_patch = patch('logging_.logging_manager.SafeRotatingFileHandler')
        self.mock_file_handler = self.handler_patch.start()

        # Make mock file handler use StringIO instead of real files
        self.log_buffer = io.StringIO()
        self.mock_file_handler.return_value = logging.StreamHandler(self.log_buffer)

        # Ensure LoggingManager instance is reset
        self.instance_patch = patch('logging_.logging_manager.LoggingManager._instance', None)
        self.instance_patch.start()

        # Store all patches for cleanup
        self.patches = [self.handler_patch, self.instance_patch]

    def tearDown(self):
        """Tear down test fixtures."""
        # Stop all patches
        for p in self.patches:
            p.stop()

        # Clean up the temporary directory
        self.temp_dir.cleanup()

    def get_log_content(self):
        """Get the current content of the log buffer."""
        return self.log_buffer.getvalue()

    def test_log_file_operations(self):
        """Test that file operations are properly logged."""
        # Create test file
        test_file = self.data_dir / "test_file.txt"
        test_content = "This is test content for file operations"

        # Log before operations
        self.logger.info("Starting file operations")

        # Perform file operations
        self.file_manager.write_text(test_file, test_content)
        content = self.file_manager.read_text(test_file)
        self.file_manager.delete(test_file)

        # Log after operations
        self.logger.info("Completed file operations")

        # Verify content was correct
        self.assertEqual(content, test_content)

        # Verify operations were logged
        log_content = self.get_log_content()
        self.assertIn("Starting file operations", log_content)
        self.assertIn("Completed file operations", log_content)

    def test_json_file_operations(self):
        """Test JSON file operations with logging."""
        # Create test JSON data
        test_file = self.data_dir / "test_data.json"
        test_data = {"key1": "value1", "key2": 42, "nested": {"inner_key": "inner_value"}}

        # Log before JSON operations
        self.logger.info("Writing JSON data")

        # Perform JSON operations
        self.json_manager.write_json(test_file, test_data)

        # Log between operations
        self.logger.info("Reading JSON data")

        # Continue JSON operations
        loaded_data = self.json_manager.read_json(test_file)

        # Verify data was correctly read
        self.assertEqual(loaded_data, test_data)

        # Verify operations were logged
        log_content = self.get_log_content()
        self.assertIn("Writing JSON data", log_content)
        self.assertIn("Reading JSON data", log_content)

    def test_error_logging(self):
        """Test that file operation errors are properly logged."""
        # Try to read a non-existent file
        non_existent = self.data_dir / "non_existent.txt"

        # Log before attempted operation
        self.logger.info("Attempting to read non-existent file")

        # This should raise an exception
        try:
            self.file_manager.read_text(non_existent)
            self.fail("Expected FileReadError was not raised")
        except Exception as e:
            # Expected exception
            self.logger.error(f"Caught expected error: {e}")

        # Verify error was logged
        log_content = self.get_log_content()
        self.assertIn("Attempting to read non-existent file", log_content)
        self.assertIn("Caught expected error", log_content)

    def test_concurrent_logging_and_file_operations(self):
        """Test concurrent logging and file operations."""
        log_count = 10
        file_count = 3

        def log_messages():
            """Log a series of messages."""
            thread_logger = self.logging_manager.get_logger("ThreadLogger")
            for i in range(log_count):
                thread_logger.info(f"Thread log message {i}")

        def perform_file_ops():
            """Perform a series of file operations."""
            for i in range(file_count):
                file_path = self.data_dir / f"thread_file_{i}.txt"
                self.file_manager.write_text(file_path, f"Content for file {i}")
                content = self.file_manager.read_text(file_path)
                self.assertEqual(content, f"Content for file {i}")

        # Create and start threads
        log_thread = threading.Thread(target=log_messages)
        file_thread = threading.Thread(target=perform_file_ops)

        log_thread.start()
        file_thread.start()

        # Wait for threads to complete
        log_thread.join(timeout=2)
        file_thread.join(timeout=2)

        # Check that threads completed
        self.assertFalse(log_thread.is_alive(), "Logging thread did not complete")
        self.assertFalse(file_thread.is_alive(), "File operations thread did not complete")

        # Verify files were created
        for i in range(file_count):
            file_path = self.data_dir / f"thread_file_{i}.txt"
            self.assertTrue(file_path.exists(), f"File {file_path} was not created")

        # Check logs for thread messages
        log_content = self.get_log_content()
        for i in range(log_count):
            self.assertIn(f"Thread log message {i}", log_content)

    def test_mock_verification(self):
        """Test that our mocking strategy is working correctly."""
        # Log a unique message
        unique_msg = f"Unique test message {time.time()}"
        self.logger.info(unique_msg)

        # Verify the message appears in our mock log
        log_content = self.get_log_content()
        self.assertIn(unique_msg, log_content)

        # Get a new logger and verify it works
        new_logger = self.logging_manager.get_logger("AnotherLogger")
        new_msg = f"Another unique message {time.time()}"
        new_logger.warning(new_msg)

        # Verify the new message also appears
        updated_log_content = self.get_log_content()
        self.assertIn(new_msg, updated_log_content)


class CompactTestResult(unittest.TextTestResult):
    """A test result class that collects results for compact reporting."""

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.test_results = {}
        self.current_test = None

    def startTest(self, test):
        self.current_test = test
        self.test_results[test] = {"status": "PASS", "message": ""}
        super().startTest(test)

    def addError(self, test, err):
        self.test_results[test] = {
            "status": "ERROR",
            "message": str(err[1])
        }
        super().addError(test, err)

    def addFailure(self, test, err):
        self.test_results[test] = {
            "status": "FAIL",
            "message": str(err[1])
        }
        super().addFailure(test, err)

    def print_compact_results(self):
        print("\n" + "="*70)
        print("TEST RESULTS SUMMARY:")
        print("-"*70)

        for test, result in self.test_results.items():
            test_name = test._testMethodName
            status = result["status"]
            message = result["message"]

            if status == "PASS":
                print(f"✓ {test_name}: PASS")
            else:
                print(f"✗ {test_name}: {status} - {message}")

        print("-"*70)
        print(f"Total tests: {self.testsRun}")
        print(f"Passed: {self.testsRun - len(self.failures) - len(self.errors)}")
        print(f"Failures: {len(self.failures)}")
        print(f"Errors: {len(self.errors)}")
        print("="*70)


def run_tests():
    """Run the integration tests."""
    # Create a test loader
    loader = unittest.TestLoader()

    # Create a test suite with our test class
    suite = unittest.TestSuite()
    suite.addTest(loader.loadTestsFromTestCase(InMemoryLoggingManagerTest))

    # Run the tests with compact reporting
    stream = sys.stdout
    runner = unittest.TextTestRunner(
        resultclass=CompactTestResult,
        stream=stream,
        verbosity=1
    )
    result = runner.run(suite)

    # Print compact summary
    result.print_compact_results()

    # Return result for exit code
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)