"""
JSON File Manager Module

This module provides utilities for reading, writing, and managing JSON files within the application.
It builds on the base FileManager class to provide specific functionality for JSON operations.

Features:
- Read and write JSON files with validation
- Merge multiple JSON files
- JSON schema validation (with optional jsonschema package)
- Error handling specific to JSON operations
"""

import os
import json
from typing import Dict, Any, Optional, Union
from pathlib import Path

from .base_file_manager import FileManager, FileReadError, FileWriteError


class JsonFileManager(FileManager):
    """
    A file manager for handling JSON files.

    This class extends the base FileManager with specialized methods for
    reading from and writing to JSON files.
    """

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
            raise FileReadError(path, f"Invalid JSON format: {str(e)}") from e
        except (IOError, OSError) as e:
            raise FileReadError(path, f"IO error: {str(e)}") from e

    def write_json(self, path: Union[str, Path], data: Dict[str, Any], make_backup: bool = False) -> None:
        """
        Write JSON data to a file.

        Args:
            path: Path to write the JSON file
            data: Data to write to the file
            make_backup: Whether to create a backup of existing file

        Raises:
            FileWriteError: If the file cannot be written
        """
        full_path = self.get_full_path(path)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(full_path)), exist_ok=True)

        # Create backup if requested
        if make_backup and os.path.exists(full_path):
            backup_path = f"{full_path}.bak"
            try:
                os.replace(full_path, backup_path)
            except (IOError, OSError) as e:
                raise FileWriteError(
                    path, f"Failed to create backup: {str(e)}") from e

        try:
            with open(full_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4)
        except (IOError, OSError) as e:
            raise FileWriteError(
                path, f"Failed to write file: {str(e)}") from e

    def validate_json(
        self, path: Union[str, Path], schema: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate a JSON file against a schema.

        Args:
            path (Union[str, Path]): Path to the JSON file.
            schema (Dict[str, Any]): Schema to validate against.

        Returns:
            Tuple[bool, List[str]]: Validation result and list of issues.

        Raises:
            FileReadError: If the file cannot be read.
            FileFormatError: If the file is not valid JSON.
            ImportError: If jsonschema package is not available.
        """
        # Check if jsonschema is available
        if not _HAS_JSONSCHEMA:
            logger.error("jsonschema package is required for validation")
            raise ImportError("jsonschema package is required for validation")

        # Read the JSON file
        data = self.read_json(path)

        # Validate against schema
        issues = []
        try:
            jsonschema.validate(instance=data, schema=schema)
            return True, issues
        except jsonschema.exceptions.ValidationError as e:
            issues.append(f"Validation error: {e.message}")
            logger.warning("JSON validation failed for %s: %s",
                           path, e.message)
        except jsonschema.exceptions.SchemaError as e:
            issues.append(f"Schema error: {e.message}")
            logger.error("Invalid schema: %s", e.message)

        return False, issues

    def merge_json(
        self,
        target_path: Union[str, Path],
        source_path: Union[str, Path],
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        """
        Merge a source JSON file into a target JSON file.

        Args:
            target_path (Union[str, Path]): Path to the target JSON file.
            source_path (Union[str, Path]): Path to the source JSON file.
            overwrite (bool): Whether to overwrite existing keys.

        Returns:
            Dict[str, Any]: The merged data.

        Raises:
            FileReadError: If either file cannot be read.
            FileFormatError: If either file is not valid JSON.
        """
        # Read both files
        target_data = self.read_json(target_path, default={})
        source_data = self.read_json(source_path)

        # Merge the data
        if overwrite:
            target_data.update(source_data)
        else:
            # Only add keys that don't exist in the target
            for key, value in source_data.items():
                if key not in target_data:
                    target_data[key] = value

        # Write the merged data back to the target file
        self.write_json(target_path, target_data, make_backup=True)

        logger.debug("Merged %s into %s", source_path, target_path)
        return target_data
