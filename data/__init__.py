"""
Data Module

This module contains utilities for data management, including encryption, file operations,
and session management.
"""

# During development, these imports may not work until modules are implemented
# We'll use a try/except to handle this gracefully
try:
    # Use relative imports instead of absolute
    from .encryption import Encryptor, get_password
except (ImportError, ModuleNotFoundError):
    # Just pass if modules aren't implemented yet
    pass