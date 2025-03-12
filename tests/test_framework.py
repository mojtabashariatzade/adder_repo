"""
Test framework for the Telegram Account Management project.
This module contains base classes and functions for testing various modules of the project.
"""

import unittest
import sys
import os
import logging
import tempfile
from importlib import import_module
from unittest.mock import MagicMock, patch

# Adding the main project path to the system
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Helper function to create a temporary instance of LoggingManager
def get_temp_logging_manager():
    """
    Creates a temporary instance of LoggingManager for testing.

    Returns:
        LoggingManager: An instance of LoggingManager with temporary settings.
    """
    from logging_manager import LoggingManager
    # Create a temporary directory for log files
    temp_dir = tempfile.mkdtemp()
    # Create an instance using the temporary directory
    manager = LoggingManager(
        log_dir=temp_dir,
        log_file="test.log",
        default_level=logging.DEBUG
    )
    return manager


class BaseTestCase(unittest.TestCase):
    """
    Base class for all tests in the project.
    """

    def setUp(self):
        """Initial setup before each test."""
        self.temp_dir = tempfile.mkdtemp()
        # Store paths for cleanup later
        self.cleanup_paths = [self.temp_dir]

    def tearDown(self):
        """Cleanup after each test."""
        # Clean up temporary files
        for path in self.cleanup_paths:
            if os.path.exists(path):
                if os.path.isdir(path):
                    import shutil
                    try:
                        shutil.rmtree(path)
                    except:
                        pass
                else:
                    try:
                        os.remove(path)
                    except:
                        pass


class ModuleTestLoader:
    """
    Class for loading and running module tests.
    """

    @staticmethod
    def load_tests(module_name):
        """
        Loads tests for a specific module.

        Args:
            module_name (str): The name of the module to test.

        Returns:
            unittest.TestSuite: A suite of tests for the module.
        """
        # Build the test path for the module
        test_module_name = f"tests.test_{module_name}"

        try:
            # Attempt to load the test module
            test_module = import_module(test_module_name)

            # Create a test suite
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(test_module)

            return suite
        except ImportError:
            print(f"Error: Test module '{test_module_name}' not found!")
            return unittest.TestSuite()
        except Exception as e:
            print(f"Error loading tests for module '{module_name}': {str(e)}")
            return unittest.TestSuite()

    @staticmethod
    def run_tests(module_name=None, verbosity=2):
        """
        Runs tests.

        Args:
            module_name (str, optional): The name of the module to test. If None, all tests are run.
            verbosity (int): Level of detail in output (2 = normal, 1 = minimal, 3 = verbose).

        Returns:
            bool: Test results (True for success).
        """
        if module_name:
            # Run tests for a specific module
            suite = ModuleTestLoader.load_tests(module_name)
            print(f"\n===== Running tests for module '{module_name}' =====\n")
        else:
            # Run all tests
            suite = unittest.defaultTestLoader.discover(start_dir='tests', pattern='test_*.py')
            print("\n===== Running all tests =====\n")

        # Run the tests
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(suite)

        # Check the results
        success = result.wasSuccessful()

        # Display summary of results
        print(f"\n===== Test Results =====")
        print(f"Total tests: {result.testsRun}")
        print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Overall result: {'Success' if success else 'Failure'}")

        return success