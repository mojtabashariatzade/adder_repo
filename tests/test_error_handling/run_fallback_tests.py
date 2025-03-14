#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test runner for Error Handling Fallback module.

This script runs the tests for the fallback error recovery mechanisms.
"""

import os
import sys
import unittest

# Add the project root to the Python path
current_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def run_tests():
    """Run the fallback mechanism tests."""
    # Create a test loader
    loader = unittest.TestLoader()

    # Create a test suite for fallback tests only
    suite = unittest.TestSuite()

    # Specifically load only the fallback test module
    test_module = 'tests.test_error_handling.test_fallback'
    try:
        loaded_tests = loader.loadTestsFromName(test_module)
        suite.addTest(loaded_tests)

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
        print(f"Error importing test module {test_module}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)