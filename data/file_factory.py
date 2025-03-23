"""
File Manager Factory Module

This module provides a factory function for creating different types of file managers.
It simplifies the process of getting the right file manager based on the needs of the application.

Features:
- Factory function to create file managers
- Support for basic, JSON, and encrypted file managers
- Easy switching between file manager types
"""

import logging
from typing import Union, Optional, Any

# Import file managers
from .base_file_manager import FileManager
from .json_file_manager import JsonFileManager
from .encrypted_file_manager import EncryptedFileManager

# Setup logger
logger = logging.getLogger(__name__)


def get_file_manager(
    manager_type: str = "basic", *args, **kwargs
) -> Union[FileManager, JsonFileManager, EncryptedFileManager]:
    """
    Factory function to get an appropriate file manager.

    Args:
        manager_type (str): Type of manager to create ('basic', 'json', or 'encrypted').
        *args: Arguments to pass to the manager constructor.
        **kwargs: Keyword arguments to pass to the manager constructor.

    Returns:
        Union[FileManager, JsonFileManager, EncryptedFileManager]: The file manager instance.

    Raises:
        ValueError: If the manager type is not supported.
    """
    if manager_type.lower() == "basic":
        return FileManager(*args, **kwargs)
    elif manager_type.lower() == "json":
        return JsonFileManager(*args, **kwargs)
    elif manager_type.lower() == "encrypted":
        return EncryptedFileManager(*args, **kwargs)
    else:
        logger.error("Unsupported file manager type: %s", manager_type)
        raise ValueError(f"Unsupported file manager type: {manager_type}")
