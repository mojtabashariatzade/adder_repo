"""Basic tests to ensure the environment is correctly set up."""

def test_import():
    """Test importing the package."""
    import adder_repo
    assert adder_repo.__version__ == "0.1.0"

def test_python_version():
    """Test Python version."""
    import sys
    assert sys.version_info >= (3, 10)
