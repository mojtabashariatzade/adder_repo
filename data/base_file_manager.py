"""
Base File Manager Module

This module provides the base class for file management operations.
It defines common file operations and exception classes used by
specialized file managers.
"""

import os
import logging
from typing import Any, Optional, Union, Dict
from pathlib import Path

# Setup logger
logger = logging.getLogger(__name__)


class FileReadError(Exception):
    """Exception raised when a file cannot be read."""

    def __init__(self, path: Union[str, Path], message: str = "File could not be read"):
        self.path = path
        self.message = message
        super().__init__(f"{message}: {path}")


class FileWriteError(Exception):
    """Exception raised when a file cannot be written."""

    def __init__(self, path: Union[str, Path], message: str = "File could not be written"):
        self.path = path
        self.message = message
        super().__init__(f"{message}: {path}")


class FileManager:
    """Base class for file management operations."""

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize the file manager.

        Args:
            base_dir: Base directory for file operations
        """
        self.base_dir = base_dir or os.getcwd()

    def get_full_path(self, path: Union[str, Path]) -> str:
        """
        Get the absolute path by joining with base_dir if needed.

        Args:
            path: Path to convert

        Returns:
            Absolute path
        """
        if isinstance(path, Path):
            path = str(path)

        if os.path.isabs(path):
            return path
        return os.path.join(self.base_dir, path)

    def ensure_directory_exists(self, path: Union[str, Path]) -> None:
        """
        Make sure the directory for the given file path exists.

        Args:
            path: File path whose directory should exist
        """
        full_path = self.get_full_path(path)
        directory = os.path.dirname(full_path)

        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                logger.debug("Created directory: %s", directory)
            except OSError as e:
                logger.error("Failed to create directory %s: %s", directory, e)
                raise FileWriteError(
                    directory, f"Failed to create directory: {e}")

    def file_exists(self, path: Union[str, Path]) -> bool:
        """
        Check if the specified file exists.

        Args:
            path: File path to check

        Returns:
            bool: True if file exists, False otherwise
        """
        full_path = self.get_full_path(path)
        return os.path.exists(full_path) and os.path.isfile(full_path)

    def create_backup(self, path: Union[str, Path], backup_suffix: str = '.bak') -> Optional[str]:
        """
        Create a backup of the specified file.

        Args:
            path: File path to back up
            backup_suffix: Suffix to add to backup file

        Returns:
            Optional[str]: Backup file path if successful, None if file doesn't exist

        Raises:
            FileWriteError: If backup creation fails
        """
        full_path = self.get_full_path(path)

        if not os.path.exists(full_path):
            return None

        backup_path = f"{full_path}{backup_suffix}"

        try:
            with open(full_path, 'rb') as src_file:
                with open(backup_path, 'wb') as dst_file:
                    dst_file.write(src_file.read())

            logger.debug("Created backup of %s at %s", full_path, backup_path)
            return backup_path
        except (IOError, OSError) as e:
            logger.error("Failed to create backup of %s: %s", full_path, e)
            raise FileWriteError(path, f"Failed to create backup: {e}")
