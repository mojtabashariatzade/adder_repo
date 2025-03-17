"""
Encryption Module

This module provides utilities for encrypting and decrypting sensitive data.
It supports multiple encryption algorithms with a primary focus on Fernet encryption.

Features:
- Generate and manage encryption keys and salts
- Encrypt and decrypt data with password-based protection
- Support for different encryption algorithms
- Secure handling of sensitive information

Usage:
    from data.encryption import Encryptor, EncryptionKeyManager

    # Simple encryption/decryption with a password
    encryptor = Encryptor(password="your_secure_password")
    encrypted_data = encryptor.encrypt("sensitive data")
    decrypted_data = encryptor.decrypt(encrypted_data)

    # Working with files
    encryptor.encrypt_file("config.json", "config.encrypted")
    encryptor.decrypt_file("config.encrypted", "config_decrypted.json")

    # Using with a specific key file
    key_manager = EncryptionKeyManager()
    key_path = key_manager.generate_key_file("encryption.key")
    encryptor = Encryptor(key_file=key_path)
"""

import os
import base64
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import getpass

# Cryptography imports
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Import custom exceptions
from core.exceptions import EncryptionError, DecryptionError, FileReadError, FileWriteError

# Import constants
from core.constants import ENCRYPTION_KEY_FILE, SALT_FILE

# Setup logger
logger = logging.getLogger(__name__)


class EncryptionAlgorithm(ABC):
    """
    Abstract base class for encryption algorithms.

    This class defines the interface that all encryption algorithm implementations must follow.
    It ensures consistent behavior across different encryption methods.
    """

    @abstractmethod
    def encrypt(self, data: str) -> str:
        """
        Encrypt the provided data.

        Args:
            data (str): The data to encrypt

        Returns:
            str: The encrypted data
        """
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt the provided encrypted data.

        Args:
            encrypted_data (str): The encrypted data to decrypt

        Returns:
            str: The decrypted data
        """
        raise NotImplementedError("Subclasses must implement this method")


class FernetEncryption(EncryptionAlgorithm):
    """
    Implementation of Fernet encryption algorithm.

    Fernet is a symmetric encryption method that ensures that a message encrypted
    using it cannot be manipulated or read without the key.
    """

    def __init__(self, key: bytes):
        """
        Initialize the Fernet encryption with a key.

        Args:
            key (bytes): The encryption key
        """
        self.cipher = Fernet(key)

    def encrypt(self, data: str) -> str:
        """
        Encrypt the provided data using Fernet.

        Args:
            data (str): The data to encrypt

        Returns:
            str: The encrypted data as a base64-encoded string
        """
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error("Fernet encryption failed: %s", e)
            raise EncryptionError(f"Fernet encryption failed: {e}") from e

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt the provided Fernet-encrypted data.

        Args:
            encrypted_data (str): The encrypted data to decrypt

        Returns:
            str: The decrypted data

        Raises:
            DecryptionError: If decryption fails (e.g., incorrect key, corrupted data)
        """
        try:
            decrypted = self.cipher.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except InvalidToken as exc:
            logger.error(
                "Decryption failed: Invalid token. The key may be incorrect.")
            raise DecryptionError(
                "Invalid token. The key may be incorrect.") from exc
        except Exception as e:
            logger.error("Fernet decryption failed: %s", e)
            raise DecryptionError(f"Decryption failed: {e}") from e


class EncryptionKeyManager:
    """
    Manages encryption keys and salts.

    This class handles the generation, storage, and loading of encryption keys
    and salts used for password-based encryption.
    """

    def __init__(self, salt_file: str = SALT_FILE, key_size: int = 32):
        """
        Initialize the key manager.

        Args:
            salt_file (str): Path to the salt file
            key_size (int): Size of the key in bytes
        """
        self.salt_file = salt_file
        self.key_size = key_size

    def generate_salt(self) -> bytes:
        """
        Generate a random salt for encryption.

        Returns:
            bytes: A random salt
        """
        return os.urandom(16)

    def save_salt(self, salt: bytes, salt_file: Optional[str] = None) -> str:
        """
        Save the salt to a file.

        Args:
            salt (bytes): The salt to save
            salt_file (str, optional): The file to save the salt to.
                If None, uses the default salt file

        Returns:
            str: The path to the saved salt file

        Raises:
            FileWriteError: If writing to the file fails
        """
        salt_path = salt_file or self.salt_file
        try:
            os.makedirs(os.path.dirname(
                os.path.abspath(salt_path)), exist_ok=True)
            with open(salt_path, "wb") as file:
                file.write(salt)
            logger.debug("Salt saved to %s", salt_path)
            return salt_path
        except Exception as e:
            logger.error("Failed to save salt to %s: %s", salt_path, e)
            raise FileWriteError(salt_path, str(e)) from e

    def load_salt(self, salt_file: Optional[str] = None) -> bytes:
        """
        Load the salt from a file.

        Args:
            salt_file (str, optional): The file to load the salt from.
                If None, uses the default salt file

        Returns:
            bytes: The loaded salt

        Raises:
            FileReadError: If reading from the file fails
            EncryptionError: If the salt is invalid (e.g., too short)
        """
        salt_path = salt_file or self.salt_file
        try:
            with open(salt_path, "rb") as file:
                salt = file.read()
            if len(salt) < 8:
                logger.error(
                    "Salt in %s is too short (minimum 8 bytes required)", salt_path)
                raise EncryptionError(
                    f"Salt in {salt_path} is too short (minimum 8 bytes required)")
            logger.debug("Salt loaded from %s", salt_path)
            return salt
        except FileNotFoundError as exc:
            logger.error("Salt file not found: %s", salt_path)
            raise FileReadError(salt_path, "Salt file not found") from exc
        except EncryptionError:
            # Re-raise EncryptionError without converting it
            raise
        except Exception as e:
            logger.error("Failed to load salt from %s: %s", salt_path, e)
            raise FileReadError(salt_path, str(e)) from e

    def generate_key_from_password(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """
        Generate an encryption key from a password and salt.

        Args:
            password (str): The password to use
            salt (bytes, optional): The salt to use. If None, generates a new salt

        Returns:
            bytes: The generated key
        """
        if salt is None:
            salt = self.generate_salt()

        # Generate key from password using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.key_size,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def generate_key_file(self,
                          key_file: str = ENCRYPTION_KEY_FILE,
                          password: Optional[str] = None,
                          salt: Optional[bytes] = None) -> str:
        """
        Generate and save an encryption key to a file.

        Args:
            key_file (str): The file to save the key to
            password (str, optional): Password to use for key generation.
                If None, generates a random key
            salt (bytes, optional): Salt to use for key generation.
                If None and password is provided, generates a new salt

        Returns:
            str: The path to the saved key file

        Raises:
            FileWriteError: If writing to the file fails
        """
        try:
            os.makedirs(os.path.dirname(
                os.path.abspath(key_file)), exist_ok=True)

            # Generate key - either random or from password
            if password:
                if salt is None:
                    salt = self.generate_salt()
                    self.save_salt(salt)
                key = self.generate_key_from_password(password, salt)
            else:
                key = Fernet.generate_key()

            # Save key to file
            with open(key_file, "wb") as file:
                file.write(key)

            logger.info("Encryption key saved to %s", key_file)
            return key_file
        except Exception as e:
            logger.error(
                "Failed to generate and save key to %s: %s", key_file, e)
            raise FileWriteError(key_file, str(e)) from e

    def load_key(self, key_file: str = ENCRYPTION_KEY_FILE) -> bytes:
        """
        Load an encryption key from a file.

        Args:
            key_file (str): The file to load the key from

        Returns:
            bytes: The loaded key

        Raises:
            FileReadError: If reading from the file fails
            EncryptionError: If the key is invalid
        """
        try:
            with open(key_file, "rb") as file:
                key = file.read()

            # Validate key
            if len(key) != 32 and len(key) != 44:  # Common lengths for Fernet keys
                logger.error("Invalid key length: %d bytes", len(key))
                raise EncryptionError(
                    f"Invalid encryption key in {key_file} (incorrect length)")

            logger.debug("Encryption key loaded from %s", key_file)
            return key
        except FileNotFoundError as exc:
            logger.error("Encryption key file not found: %s", key_file)
            raise FileReadError(
                key_file, "Encryption key file not found") from exc
        except EncryptionError:
            # Re-raise EncryptionError without converting it
            raise
        except Exception as e:
            logger.error(
                "Failed to load encryption key from %s: %s", key_file, e)
            raise FileReadError(key_file, str(e)) from e


class Encryptor:
    """
    Main encryption utility class.

    This class provides high-level methods for encrypting and decrypting data
    using various encryption algorithms. It supports both key-based and
    password-based encryption.
    """

    def __init__(self,
                 password: Optional[str] = None,
                 key_file: Optional[str] = None,
                 salt: Optional[bytes] = None,
                 salt_file: Optional[str] = None,
                 algorithm: str = "fernet"):
        """
        Initialize the encryptor.

        Args:
            password (str, optional): Password to use for encryption.
                If provided, uses password-based encryption
            key_file (str, optional): Path to the encryption key file.
                If provided, loads the key from this file
            salt (bytes, optional): Salt to use for password-based encryption.
                If None and password is provided, loads or generates a new salt
            salt_file (str, optional): Path to the salt file.
                If None, uses the default salt file
            algorithm (str): The encryption algorithm to use (default: "fernet")

        Raises:
            EncryptionError: If both password and key_file are None, or if
                the algorithm is not supported
        """
        self.key_manager = EncryptionKeyManager(
            salt_file=salt_file or SALT_FILE)
        self.algorithm = algorithm.lower()

        # Determine key source and initialize encryption algorithm
        if password is not None:
            # Password-based encryption
            if salt is None:
                try:
                    # Try to load existing salt
                    salt = self.key_manager.load_salt(salt_file)
                except FileReadError:
                    # Generate new salt if not found
                    salt = self.key_manager.generate_salt()
                    self.key_manager.save_salt(salt, salt_file)

            # Generate key from password
            key = self.key_manager.generate_key_from_password(password, salt)
        elif key_file is not None:
            # Key file-based encryption
            try:
                key = self.key_manager.load_key(key_file)
            except FileReadError as e:
                logger.error("Failed to load encryption key: %s", e)
                raise EncryptionError(
                    f"Failed to load encryption key: {e}") from e
        else:
            # No encryption source provided
            logger.error(
                "Encryption initialization failed: No password or key file provided")
            raise EncryptionError(
                "Encryption initialization requires either a password or a key file")

        # Initialize the encryption algorithm
        if self.algorithm == "fernet":
            self.cipher = FernetEncryption(key)
        else:
            logger.error("Unsupported encryption algorithm: %s", algorithm)
            raise EncryptionError(
                f"Unsupported encryption algorithm: {algorithm}")

        logger.debug("Encryptor initialized with %s algorithm", algorithm)

    def encrypt(self, data: str) -> str:
        """
        Encrypt data.

        Args:
            data (str): The data to encrypt

        Returns:
            str: The encrypted data

        Raises:
            EncryptionError: If encryption fails
        """
        return self.cipher.encrypt(data)

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data.

        Args:
            encrypted_data (str): The encrypted data to decrypt

        Returns:
            str: The decrypted data

        Raises:
            DecryptionError: If decryption fails
        """
        return self.cipher.decrypt(encrypted_data)

    def encrypt_file(self,
                     input_file: str,
                     output_file: Optional[str] = None,
                     delete_original: bool = False) -> str:
        """
        Encrypt a file.

        Args:
            input_file (str): Path to the file to encrypt
            output_file (str, optional): Path to save the encrypted file.
                If None, appends '.encrypted' to the input file name
            delete_original (bool): Whether to delete the original file
                after encryption

        Returns:
            str: Path to the encrypted file

        Raises:
            FileReadError: If reading from the input file fails
            FileWriteError: If writing to the output file fails
            EncryptionError: If encryption fails
        """
        if output_file is None:
            output_file = f"{input_file}.encrypted"

        try:
            # Read input file
            with open(input_file, 'r', encoding='utf-8') as file:
                content = file.read()

            # Encrypt content
            encrypted_content = self.encrypt(content)

            # Write encrypted content to output file
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write(encrypted_content)

            logger.info("File encrypted: %s -> %s", input_file, output_file)

            # Delete original if requested
            if delete_original:
                os.remove(input_file)
                logger.info("Original file deleted: %s", input_file)

            return output_file
        except FileNotFoundError as exc:
            logger.error("Input file not found: %s", input_file)
            raise FileReadError(input_file, "File not found") from exc
        except PermissionError as e:
            logger.error("Permission error: %s", e)
            raise FileWriteError(output_file, f"Permission error: {e}") from e
        except EncryptionError:
            # Re-raise encryption errors
            raise
        except Exception as e:
            logger.error("File encryption failed: %s", e)
            raise EncryptionError(f"File encryption failed: {e}") from e

    def decrypt_file(self,
                     input_file: str,
                     output_file: Optional[str] = None,
                     delete_encrypted: bool = False) -> str:
        """
        Decrypt a file.

        Args:
            input_file (str): Path to the file to decrypt
            output_file (str, optional): Path to save the decrypted file.
                If None, removes '.encrypted' from the input file name if present
            delete_encrypted (bool): Whether to delete the encrypted file
                after decryption

        Returns:
            str: Path to the decrypted file

        Raises:
            FileReadError: If reading from the input file fails
            FileWriteError: If writing to the output file fails
            DecryptionError: If decryption fails
        """
        if output_file is None:
            # Remove .encrypted extension if present
            if input_file.endswith('.encrypted'):
                output_file = input_file[:-10]
            else:
                output_file = f"{input_file}.decrypted"

        try:
            # Read encrypted file
            with open(input_file, 'r', encoding='utf-8') as file:
                encrypted_content = file.read()

            # Decrypt content
            decrypted_content = self.decrypt(encrypted_content)

            # Write decrypted content to output file
            with open(output_file, 'w', encoding='utf-8') as file:
                file.write(decrypted_content)

            logger.info("File decrypted: %s -> %s", input_file, output_file)

            # Delete encrypted file if requested
            if delete_encrypted:
                os.remove(input_file)
                logger.info("Encrypted file deleted: %s", input_file)

            return output_file
        except FileNotFoundError as exc:
            logger.error("Encrypted file not found: %s", input_file)
            raise FileReadError(input_file, "File not found") from exc
        except PermissionError as e:
            logger.error("Permission error: %s", e)
            raise FileWriteError(f"Permission error: {e}") from e
        except DecryptionError:
            # Re-raise decryption errors
            raise
        except Exception as e:
            logger.error("File decryption failed: %s", e)
            raise DecryptionError(f"File decryption failed: {e}") from e

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """
        Encrypt a dictionary.

        Args:
            data (Dict[str, Any]): The dictionary to encrypt

        Returns:
            str: The encrypted JSON string

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            json_data = json.dumps(data)
            return self.encrypt(json_data)
        except (TypeError, ValueError) as e:
            logger.error("JSON serialization failed: %s", e)
            raise EncryptionError(
                f"Failed to serialize data to JSON: {e}") from e
        except EncryptionError:
            # Re-raise encryption errors
            raise
        except Exception as e:
            logger.error("Dictionary encryption failed: %s", e)
            raise EncryptionError(f"Dictionary encryption failed: {e}") from e

    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt a dictionary.

        Args:
            encrypted_data (str): The encrypted JSON string

        Returns:
            Dict[str, Any]: The decrypted dictionary

        Raises:
            DecryptionError: If decryption or JSON parsing fails
        """
        try:
            json_data = self.decrypt(encrypted_data)
            return json.loads(json_data)
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error("JSON deserialization failed: %s", e)
            raise DecryptionError(
                f"Failed to parse decrypted data as JSON: {e}") from e
        except DecryptionError:
            # Re-raise decryption errors
            raise
        except Exception as e:
            logger.error("Dictionary decryption failed: %s", e)
            raise DecryptionError(f"Dictionary decryption failed: {e}") from e


# Helper function to securely get a password from user input
def get_password(prompt: str) -> str:
    """
    Get a password from user input without echoing.

    Args:
        prompt (str): The prompt to display

    Returns:
        str: The entered password
    """
    return getpass.getpass(prompt)
