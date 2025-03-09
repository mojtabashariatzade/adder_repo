#!/bin/bash

# Activate the virtual environment
source venv/bin/activate

# Run tests
python -m pytest -v

# Check code quality
python -m pylint adder-repo/
python -m black --check adder-repo/
python -m mypy adder-repo/

echo "All tests and checks completed."
