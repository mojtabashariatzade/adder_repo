# run_tests.py

import sys
import os
from tests.test_framework import ModuleTestLoader  # Import the test loader

def main():
    """
    Main function to run tests
    """
    # Add project and tests directories to the system path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'tests')))

    # Parse command-line arguments
    module_name = None
    verbosity = 2  # Default verbosity level

    if len(sys.argv) > 1:
        # Get the module name from the first argument
        module_name = sys.argv[1]

    if len(sys.argv) > 2:
        # Get the verbosity level from the second argument
        try:
            verbosity = int(sys.argv[2])
        except ValueError:
            print("Error: Verbosity level must be a number.")
            sys.exit(1)

    # Run the tests
    print("\n===== Starting test execution =====\n")
    success = ModuleTestLoader.run_tests(module_name=module_name, verbosity=verbosity)
    print("\n===== Test execution completed =====\n")

    # Check the overall result
    if success:
        print("Overall result: ✅ Success")
        sys.exit(0)  # Exit with success code
    else:
        print("Overall result: ❌ Failure")
        sys.exit(1)  # Exit with failure code

if __name__ == "__main__":
    main()