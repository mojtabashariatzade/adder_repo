"""
Data Management Package

This package provides classes and utilities for file operations and data management.
"""

# First import the base classes to avoid circular imports
from .base_file_manager import FileManager, FileReadError, FileWriteError

# Then import specific file managers
from .json_file_manager import JsonFileManager

# Import other modules
# Uncomment as needed
# from .encrypted_file_manager import EncryptedFileManager
# from .file_factory import FileManagerFactory
