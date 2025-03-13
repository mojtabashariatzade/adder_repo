#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

current_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def run_tests():
    loader = unittest.TestLoader()

    try:
        from tests.test_integration.test_config_file_manager import TestConfigFileManagerIntegration

        suite = unittest.TestSuite()
        suite.addTest(loader.loadTestsFromTestCase(TestConfigFileManagerIntegration))

        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        print("\n" + "="*70)
        print(f"Total tests: {result.testsRun}")
        print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print("="*70)

        return result.wasSuccessful()
    except ImportError as e:
        print(f"Error importing test modules: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)