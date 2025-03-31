"""
Data Module Package

This package contains modules for data management, including file operations,
encryption, and session management.

The file management modules provide functionality for handling different types of files:
- Basic file operations (read, write, copy, delete)
- JSON file operations (read, write, validate)
- Encrypted file operations (secure storage of sensitive data)
"""

# Import and re-export classes and functions to maintain
# the same API as before to avoid breaking changes

# Import File Managers
from .base_file_manager import FileManager, FileReadError, FileWriteError
from .json_file_manager import JsonFileManager
from .encrypted_file_manager import EncryptedFileManager
from .file_factory import FileManagerFactory

# Import other data modules if they are available
try:
    from .encryption import Encryptor, get_password
except ImportError:
    # These may not be implemented yet
    pass

try:
    from .session_manager import (
        Session,
        SessionManager,
        SessionStatus,
        get_session_manager
    )
except ImportError:
    # These may not be implemented yet
    pass

# Define what's available when importing * from this package
__all__ = [
    # File Managers
    'FileManager',
    'JsonFileManager',
    'EncryptedFileManager',
    'SafeFileWriter',
    'get_file_manager',

    # Conditional exports based on what's imported
    *([] if 'Encryptor' not in globals() else ['Encryptor', 'get_password']),
    *([] if 'SessionManager' not in globals() else [
        'Session',
        'SessionManager',
        'SessionStatus',
        'get_session_manager'
    ]),
]
