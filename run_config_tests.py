#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test runner for Config module.

This script runs the tests for the Config class and related functionality.
"""

import os
import sys
import unittest

# Add the project root to the Python path
current_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def run_tests():
    """Run the config module tests."""
    # Create a test loader
    loader = unittest.TestLoader()

    # Load tests from the test module
    try:
        from tests.test_core.test_config import TestConfig

        # Create a test suite with the test class
        suite = unittest.TestSuite()
        suite.addTest(loader.loadTestsFromTestCase(TestConfig))

        # Run the tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        # Print summary
        print("\n" + "="*70)
        print(f"Total tests: {result.testsRun}")
        print(
            f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print("="*70)

        # Return result for exit code
        return result.wasSuccessful()
    except ImportError as e:
        print(f"Error importing test modules: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
