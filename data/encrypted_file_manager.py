"""
Encrypted File Manager Module

This module provides utilities for reading, writing, and managing encrypted files.
It builds on the base FileManager class and provides integration with the encryption module.

Features:
- Read and write encrypted files
- Support for encrypted JSON files
- Integration with the Encryptor class for secure operations
- Error handling specific to encryption operations
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

# Import custom exceptions first
from core.exceptions import (
    FileReadError,
    FileWriteError,
    FileFormatError,
    EncryptionError,
    DecryptionError,
)

# Import Encryptor class for type checking only
from data.encryption import Encryptor

# Import base file manager
from .base_file_manager import FileManager


# Setup logger
logger = logging.getLogger(__name__)


class EncryptedFileManager(FileManager):
    """
    Manager for encrypted file operations.

    Provides methods to read and write encrypted files using the Encryptor class.
    """

    def __init__(self, encryptor: Encryptor, base_dir: Optional[str] = None):
        """
        Initialize the EncryptedFileManager.

        Args:
            encryptor (Encryptor): An instance of the Encryptor class.
            base_dir (str, optional): Base directory for relative paths.

        Raises:
            TypeError: If the provided encryptor is not an instance of Encryptor.
        """
        super().__init__(base_dir)

        # Check if the provided object is valid
        if not isinstance(encryptor, Encryptor):
            logger.error("Invalid encryptor type: %s", type(encryptor))
            raise TypeError(
                "encryptor must be an instance of data.encryption.Encryptor"
            )

        self.encryptor = encryptor

    def read_encrypted(self, path: Union[str, Path]) -> str:
        """
        Read and decrypt an encrypted file.

        Args:
            path (Union[str, Path]): Path to the encrypted file.

        Returns:
            str: The decrypted content.

        Raises:
            FileReadError: If the file cannot be read.
            DecryptionError: If the file cannot be decrypted.
        """
        # Read the encrypted content
        encrypted_content = self.read_text(path)

        try:
            # Decrypt the content
            return self.encryptor.decrypt(encrypted_content)
        except DecryptionError:
            # Re-raise DecryptionError without converting it
            raise
        except Exception as e:
            logger.error("Error decrypting %s: %s", path, e)
            raise DecryptionError(f"Error decrypting {path}: {e}") from e

    def write_encrypted(
        self, path: Union[str, Path], content: str, make_backup: bool = False
    ) -> None:
        """
        Encrypt and write content to a file.

        Args:
            path (Union[str, Path]): Path to the file.
            content (str): Content to encrypt and write.
            make_backup (bool): Whether to make a backup of the existing file.

        Raises:
            FileWriteError: If the file cannot be written.
            EncryptionError: If the content cannot be encrypted.
        """
        try:
            # Encrypt the content
            encrypted_content = self.encryptor.encrypt(content)

            # Write to file
            self.write_text(path, encrypted_content, make_backup=make_backup)
            logger.debug("Encrypted content written to %s", path)
        except EncryptionError:
            # Re-raise EncryptionError without converting it
            raise
        except Exception as e:
            logger.error("Error encrypting or writing to %s: %s", path, e)
            raise EncryptionError(
                f"Error encrypting or writing to {path}: {e}") from e

    def read_encrypted_json(
        self, path: Union[str, Path], default: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Read and decrypt an encrypted JSON file.

        Args:
            path (Union[str, Path]): Path to the encrypted JSON file.
            default (Dict[str, Any], optional): Default value to return if the file doesn't exist.

        Returns:
            Dict[str, Any]: The decrypted and parsed JSON data.

        Raises:
            FileReadError: If the file cannot be read.
            DecryptionError: If the file cannot be decrypted.
            FileFormatError: If the decrypted content is not valid JSON.
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            if default is not None:
                logger.debug(
                    "Encrypted JSON file not found, returning default: %s", file_path
                )
                return default
            logger.error("Encrypted JSON file not found: %s", file_path)
            raise FileReadError(str(file_path), "File not found")

        try:
            # Read and decrypt
            decrypted_content = self.read_encrypted(file_path)

            # Parse JSON
            try:
                return json.loads(decrypted_content)
            except json.JSONDecodeError as e:
                logger.error(
                    "Invalid JSON in decrypted content of %s: %s", file_path, e)
                raise FileFormatError(
                    str(file_path), f"Invalid JSON in decrypted content: {e}"
                ) from e
        except (FileReadError, DecryptionError):
            # Re-raise these specific exceptions without converting them
            raise

    def write_encrypted_json(
        self,
        path: Union[str, Path],
        data: Dict[str, Any],
        indent: int = 4,
        make_backup: bool = False,
    ) -> None:
        """
        Encrypt and write JSON data to a file.

        Args:
            path (Union[str, Path]): Path to the file.
            data (Dict[str, Any]): JSON data to encrypt and write.
            indent (int): Indentation level for JSON output.
            make_backup (bool): Whether to make a backup of the existing file.

        Raises:
            FileWriteError: If the file cannot be written.
            EncryptionError: If the content cannot be encrypted.
            TypeError: If the data is not JSON-serializable.
        """
        # Convert to JSON string
        try:
            json_content = json.dumps(data, indent=indent, ensure_ascii=False)
        except TypeError as e:
            logger.error("Data is not JSON-serializable: %s", e)
            raise TypeError(f"Data is not JSON-serializable: {e}") from e

        try:
            # Encrypt and write
            self.write_encrypted(path, json_content, make_backup=make_backup)
            logger.debug("Encrypted JSON written to %s", path)
        except (EncryptionError, FileWriteError):
            # Re-raise these specific exceptions without converting them
            raise
        except Exception as e:
            logger.error("Error encrypting or writing to %s: %s", path, e)
            raise EncryptionError(
                f"Error encrypting or writing to {path}: {e}") from e
