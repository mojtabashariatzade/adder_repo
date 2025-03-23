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

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

# Import custom exceptions
from core.exceptions import (
    FileReadError,
    FileFormatError,
)

# Import base file manager
from .base_file_manager import FileManager


# Setup logger
logger = logging.getLogger(__name__)


class JsonFileManager(FileManager):
    """
    Manager for JSON file operations.

    Provides methods to read, write, and validate JSON files.
    """

    def __init__(self, base_dir: Optional[str] = None, indent: int = 4):
        """
        Initialize the JsonFileManager.

        Args:
            base_dir (str, optional): Base directory for relative paths.
            indent (int): Indentation level for JSON output.
        """
        super().__init__(base_dir)
        self.indent = indent

    def read_json(
        self, path: Union[str, Path], default: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Read and parse a JSON file.

        Args:
            path (Union[str, Path]): Path to the JSON file.
            default (Dict[str, Any], optional): Default value to return if the file doesn't exist.

        Returns:
            Dict[str, Any]: Parsed JSON data.

        Raises:
            FileReadError: If the file cannot be read.
            FileFormatError: If the file is not valid JSON.
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            if default is not None:
                logger.debug(
                    "JSON file not found, returning default: %s", file_path)
                return default
            logger.error("JSON file not found: %s", file_path)
            raise FileReadError(str(file_path), "File not found")

        try:
            content = self.read_text(file_path)
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s", file_path, e)
            raise FileFormatError(str(file_path), f"Invalid JSON: {e}") from e

    def write_json(
        self, path: Union[str, Path], data: Dict[str, Any], make_backup: bool = False
    ) -> None:
        """
        Write data to a JSON file.

        Args:
            path (Union[str, Path]): Path to the JSON file.
            data (Dict[str, Any]): Data to write.
            make_backup (bool): Whether to make a backup of the existing file.

        Raises:
            FileWriteError: If the file cannot be written.
            TypeError: If the data is not JSON-serializable.
        """
        file_path = self._resolve_path(path)

        try:
            # Convert to JSON string
            json_content = json.dumps(
                data, indent=self.indent, ensure_ascii=False)
            # Write to file
            self.write_text(file_path, json_content, make_backup=make_backup)
            logger.debug("JSON written to %s", file_path)
        except TypeError as e:
            logger.error("Data is not JSON-serializable: %s", e)
            raise TypeError(f"Data is not JSON-serializable: {e}") from e

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
        # Try to import jsonschema - will trigger IDE warnings but works at runtime
        jsonschema = None
        try:
            import jsonschema
        except ImportError as exc:
            logger.error("jsonschema package is required for validation")
            raise ImportError(
                "jsonschema package is required for validation") from exc

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
