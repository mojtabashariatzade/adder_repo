#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test runner for Account Model module.

This script runs the tests for the Account, AccountMetrics, and AccountFactory classes.
"""

import os
import sys
import unittest

# Add the project root to the Python path
current_dir = os.path.abspath(os.path.dirname(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def run_tests():
    """Run the Account model tests."""
    # Create a test loader
    loader = unittest.TestLoader()

    # Load tests from the test module
    try:
        from tests.test_models.test_account import TestAccountMetrics, TestAccount, TestAccountFactory

        # Create a test suite with all test classes
        suite = unittest.TestSuite()
        suite.addTest(loader.loadTestsFromTestCase(TestAccountMetrics))
        suite.addTest(loader.loadTestsFromTestCase(TestAccount))
        suite.addTest(loader.loadTestsFromTestCase(TestAccountFactory))

        # Run the tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        # Print summary
        print("\n" + "="*70)
        print(f"Total tests: {result.testsRun}")
        print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
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