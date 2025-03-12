"""
Test module for logging_/handlers.py

This module contains unit tests for the custom logging handlers in the application.
"""

import os
import sys
import unittest
import logging
import tempfile
import shutil
import threading
import time
from io import StringIO

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the module being tested
try:
    from logging_.handlers import (
        SafeRotatingFileHandler,
        ConcurrentRotatingFileHandler,
        MultiprocessSafeHandler
    )
except ImportError:
    # Placeholder classes for development
    class SafeRotatingFileHandler:
        pass
    class ConcurrentRotatingFileHandler:
        pass
    class MultiprocessSafeHandler:
        pass


class TestSafeRotatingFileHandler(unittest.TestCase):
    """Test suite for SafeRotatingFileHandler."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for log files
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'test.log')

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)

    def test_log_rotation(self):
        """Test log file rotation functionality."""
        # Create handler with small max bytes to force rotation
        handler = SafeRotatingFileHandler(
            self.log_file,
            maxBytes=100,  # Very small to force quick rotation
            backupCount=3
        )

        # Create a logger
        logger = logging.getLogger('rotation_test')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        # Log multiple messages to trigger rotation
        for i in range(20):
            logger.info(f"Test log message {i}")

        # Close the handler
        handler.close()

        # Check that backup files were created
        backup_files = [f for f in os.listdir(self.temp_dir) if f.startswith('test.log.')]
        self.assertTrue(len(backup_files) > 0)
        self.assertTrue(len(backup_files) <= 3)  # Should not exceed backup count

    def test_error_handling(self):
        """Test error handling during log writing."""
        # Create handler
        handler = SafeRotatingFileHandler(
            self.log_file,
            maxBytes=100,
            backupCount=3
        )

        # Simulate an error by making log file non-writable
        os.chmod(self.log_file, 0o400)  # Read-only

        # Create a logger
        logger = logging.getLogger('error_test')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        # Attempt to log
        try:
            logger.info("Test error handling message")
        except Exception as e:
            self.fail(f"Logging raised an unexpected exception: {e}")
        finally:
            # Restore write permissions
            os.chmod(self.log_file, 0o644)
            handler.close()


class TestConcurrentRotatingFileHandler(unittest.TestCase):
    """Test suite for ConcurrentRotatingFileHandler."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'concurrent_test.log')

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_concurrent_logging(self):
        """Test logging from multiple threads."""
        handler = ConcurrentRotatingFileHandler(
            self.log_file,
            maxBytes=1000,
            backupCount=3
        )

        logger = logging.getLogger('concurrent_test')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        # Function to log messages
        def worker(thread_id):
            for i in range(50):
                logger.info(f"Thread {thread_id} message {i}")

        # Create multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Close handler
        handler.close()

        # Check log file was created and contains messages
        with open(self.log_file, 'r') as f:
            log_content = f.read()

        self.assertTrue(len(log_content) > 0)
        self.assertTrue(all(f"Thread {i} message" in log_content for i in range(5)))


class TestMultiprocessSafeHandler(unittest.TestCase):
    """Test suite for MultiprocessSafeHandler."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'multiprocess_test.log')

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_multiprocess_logging(self):
        """Test logging from multiple processes."""
        # This is a placeholder test as full multiprocess testing
        # requires more complex setup
        handler = MultiprocessSafeHandler(self.log_file)

        logger = logging.getLogger('multiprocess_test')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        logger.info("Multiprocess logging test")
        handler.close()

        # Verify log file was created
        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file, 'r') as f:
            log_content = f.read()
        self.assertIn("Multiprocess logging test", log_content)


class TestHandlerErrorRecovery(unittest.TestCase):
    """Test suite for handler error recovery mechanisms."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'error_recovery_test.log')

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_handler_fallback(self):
        """Test handler's ability to recover from logging errors."""
        # Capture stderr for error reporting
        import sys
        stderr_capture = StringIO()
        sys.stderr = stderr_capture

        # Attempt to log to a directory that doesn't exist
        non_existent_dir = os.path.join(self.temp_dir, 'non_existent_dir')
        log_path = os.path.join(non_existent_dir, 'test.log')

        handler = SafeRotatingFileHandler(
            log_path,
            maxBytes=100,
            backupCount=3
        )

        logger = logging.getLogger('fallback_test')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        # Log a message
        try:
            logger.info("Test fallback logging")
        except Exception as e:
            self.fail(f"Logging raised an unexpected exception: {e}")
        finally:
            # Restore stderr
            sys.stderr = sys.__stderr__
            handler.close()

        # Check error messages
        error_output = stderr_capture.getvalue()
        self.assertTrue(len(error_output) > 0)


def run_tests():
    """Run the logging handlers tests."""
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTest(unittest.makeSuite(TestSafeRotatingFileHandler))
    suite.addTest(unittest.makeSuite(TestConcurrentRotatingFileHandler))
    suite.addTest(unittest.makeSuite(TestMultiprocessSafeHandler))
    suite.addTest(unittest.makeSuite(TestHandlerErrorRecovery))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print(f"Total tests: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)