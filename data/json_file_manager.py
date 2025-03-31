"""
JSON File Manager Module

This module provides a specialized file manager for handling JSON files.
It extends the base FileManager class with JSON-specific operations.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union, List
from pathlib import Path

# Import from base_file_manager - IMPORTANT: only import what you need
from .base_file_manager import FileManager, FileReadError, FileWriteError

# Setup logger
logger = logging.getLogger(__name__)


class JsonFileManager(FileManager):
    """
    A file manager for handling JSON files.

    This class extends the base FileManager with specialized methods for
    reading from and writing to JSON files.
    """

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize the JSON file manager.

        Args:
            base_dir: Base directory for file operations
        """
        super().__init__(base_dir)

    def read_json(self, path: Union[str, Path], default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Read JSON data from a file.

        Args:
            path: Path to the JSON file
            default: Default value to return if file doesn't exist

        Returns:
            Dict containing the parsed JSON data

        Raises:
            FileReadError: If the file cannot be read or parsed
        """
        full_path = self.get_full_path(path)

        if not os.path.exists(full_path):
            return default if default is not None else {}

        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON format in %s: %s", full_path, e)
            raise FileReadError(path, f"Invalid JSON format: {e}") from e
        except (IOError, OSError) as e:
            logger.error("Failed to read JSON file %s: %s", full_path, e)
            raise FileReadError(path, f"IO error: {e}") from e

    def write_json(self, path: Union[str, Path],
                   data: Dict[str, Any],
                   make_backup: bool = False,
                   indent: int = 4,
                   ensure_ascii: bool = False) -> None:
        """
        Write JSON data to a file.

        Args:
            path: Path to write the JSON file
            data: Data to write to the file
            make_backup: Whether to create a backup of existing file
            indent: Number of spaces for indentation (pretty-printing)
            ensure_ascii: Whether to escape non-ASCII characters

        Raises:
            FileWriteError: If the file cannot be written
        """
        full_path = self.get_full_path(path)

        # Create directory if it doesn't exist
        self.ensure_directory_exists(path)

        # Create backup if requested
        if make_backup and os.path.exists(full_path):
            try:
                backup_path = self.create_backup(path)
                logger.debug("Created backup at %s", backup_path)
            except (IOError, OSError) as e:
                logger.error("Failed to create backup of %s: %s", full_path, e)
                raise FileWriteError(
                    path, f"Failed to create backup: {str(e)}") from e

        try:
            with open(full_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=indent, ensure_ascii=ensure_ascii)
                logger.debug("Successfully wrote JSON to %s", full_path)
        except (IOError, OSError) as e:
            logger.error("Failed to write JSON to %s: %s", full_path, e)
            raise FileWriteError(
                path, f"Failed to write file: {str(e)}") from e
        except (TypeError, ValueError) as e:
            logger.error("JSON serialization error for %s: %s", full_path, e)
            raise FileWriteError(
                path, f"JSON serialization error: {str(e)}") from e

    def update_json(self, path: Union[str, Path],
                    updates: Dict[str, Any],
                    create_if_missing: bool = True,
                    make_backup: bool = True) -> Dict[str, Any]:
        """
        Update an existing JSON file with new data.

        Args:
            path: Path to the JSON file
            updates: Dictionary of updates to apply
            create_if_missing: Whether to create the file if it doesn't exist
            make_backup: Whether to create a backup before updating

        Returns:
            Dict containing the updated JSON data

        Raises:
            FileReadError: If the file cannot be read
            FileWriteError: If the file cannot be written
        """
        # Read existing data
        try:
            current_data = self.read_json(path, default={})
        except FileReadError as e:
            if create_if_missing:
                current_data = {}
            else:
                raise

        # Update the data
        current_data.update(updates)

        # Write back to file
        self.write_json(path, current_data, make_backup=make_backup)

        return current_data

    def read_json_list(self, path: Union[str, Path], default: Optional[List[Any]] = None) -> List[Any]:
        """
        Read a JSON file that contains a list.

        Args:
            path: Path to the JSON file
            default: Default value to return if file doesn't exist

        Returns:
            List from the JSON file

        Raises:
            FileReadError: If the file cannot be read or does not contain a list
        """
        full_path = self.get_full_path(path)

        if not os.path.exists(full_path):
            return default if default is not None else []

        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                data = json.load(file)

                if not isinstance(data, list):
                    logger.error(
                        "JSON file %s does not contain a list", full_path)
                    raise FileReadError(
                        path, "JSON file does not contain a list")

                return data

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON format in %s: %s", full_path, e)
            raise FileReadError(path, f"Invalid JSON format: {e}") from e
        except (IOError, OSError) as e:
            logger.error("Failed to read JSON file %s: %s", full_path, e)
            raise FileReadError(path, f"IO error: {e}") from e
