"""
Test module for data/encryption.py

This module contains unit tests for the encryption module, testing key generation,
encryption/decryption of strings, files, and dictionaries, error handling, and more.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import sys
import logging
import time
from pathlib import Path

# Fix import path - add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, project_root)
print(f"Added path to sys.path: {project_root}")

# Now try to import the modules
try:
    from data.encryption import (
        Encryptor,
        EncryptionKeyManager,
        EncryptionAlgorithm,
        FernetEncryption,
        get_password
    )
    print("Successfully imported encryption module")

    from core.exceptions import (
        EncryptionError,
        DecryptionError,
        FileReadError,
        FileWriteError
    )
    print("Successfully imported exceptions module")
except ImportError as e:
    print(f"Error importing modules: {e}")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)


class TestEncryptionKeyManager(unittest.TestCase):
    """Test case for the EncryptionKeyManager class."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: data/encryption.py - EncryptionKeyManager")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: EncryptionKeyManager")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up before each test method."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_salt_file = os.path.join(self.temp_dir.name, 'test_salt.salt')
        self.temp_key_file = os.path.join(self.temp_dir.name, 'test_key.key')

        # Create key manager
        self.key_manager = EncryptionKeyManager(salt_file=self.temp_salt_file)

    def tearDown(self):
        """Tear down after each test method."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

        # Clean up
        self.temp_dir.cleanup()

    def test_generate_salt(self):
        """Test generating a random salt."""
        print("  Testing salt generation...")
        salt = self.key_manager.generate_salt()

        # Check salt is bytes and has correct length
        self.assertIsInstance(salt, bytes)
        self.assertEqual(len(salt), 16)

        # Generate another and verify they're different
        another_salt = self.key_manager.generate_salt()
        self.assertNotEqual(salt, another_salt)

    def test_save_and_load_salt(self):
        """Test saving and loading a salt from a file."""
        print("  Testing save and load salt...")
        # Generate and save a salt
        salt = self.key_manager.generate_salt()
        salt_path = self.key_manager.save_salt(salt, self.temp_salt_file)

        # Verify file exists
        self.assertTrue(os.path.exists(salt_path))

        # Load the salt and verify it's the same
        loaded_salt = self.key_manager.load_salt(salt_path)
        self.assertEqual(salt, loaded_salt)

    def test_load_salt_file_not_found(self):
        """Test loading a salt from a non-existent file."""
        print("  Testing load salt with non-existent file...")
        nonexistent_file = os.path.join(self.temp_dir.name, 'nonexistent.salt')

        # Verify it raises the correct exception
        with self.assertRaises(FileReadError):
            self.key_manager.load_salt(nonexistent_file)

    def test_load_salt_invalid_length(self):
        """Test loading a salt with invalid length."""
        print("  Testing load salt with invalid length...")
        # Create a salt file with insufficient length
        short_salt_file = os.path.join(self.temp_dir.name, 'short_salt.salt')
        with open(short_salt_file, 'wb') as f:
            f.write(b'1234')  # Too short

        # Verify it raises the correct exception
        with self.assertRaises(EncryptionError):
            self.key_manager.load_salt(short_salt_file)

    def test_generate_key_from_password(self):
        """Test generating an encryption key from a password and salt."""
        print("  Testing key generation from password...")
        # Generate a key with a known password and salt
        password = "test_password"
        salt = self.key_manager.generate_salt()
        key = self.key_manager.generate_key_from_password(password, salt)

        # Check key is bytes and has correct length for Fernet
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 44)  # Base64 encoded 32-byte key

        # Generate another with same password and salt - should be identical
        same_key = self.key_manager.generate_key_from_password(password, salt)
        self.assertEqual(key, same_key)

        # Generate with different password - should be different
        diff_key = self.key_manager.generate_key_from_password("different_password", salt)
        self.assertNotEqual(key, diff_key)

        # Generate with different salt - should be different
        diff_salt_key = self.key_manager.generate_key_from_password(password, self.key_manager.generate_salt())
        self.assertNotEqual(key, diff_salt_key)

    def test_generate_and_load_key_file(self):
        """Test generating and loading a key file."""
        print("  Testing generate and load key file...")
        # Generate a random key and save to file
        key_path = self.key_manager.generate_key_file(self.temp_key_file)

        # Verify file exists
        self.assertTrue(os.path.exists(key_path))

        # Load the key
        key = self.key_manager.load_key(key_path)

        # Verify key is valid
        self.assertIsInstance(key, bytes)
        self.assertIn(len(key), [32, 44])  # Either raw key or base64 encoded

    def test_generate_key_file_with_password(self):
        """Test generating a key file using a password."""
        print("  Testing generate key file with password...")
        password = "test_password"
        salt = self.key_manager.generate_salt()

        # Generate key file with password and salt
        key_path = self.key_manager.generate_key_file(
            self.temp_key_file,
            password=password,
            salt=salt
        )

        # Verify file exists
        self.assertTrue(os.path.exists(key_path))

        # Load the key
        key = self.key_manager.load_key(key_path)

        # Generate the same key directly for comparison
        expected_key = self.key_manager.generate_key_from_password(password, salt)

        # Verify keys match
        self.assertEqual(key, expected_key)

    def test_load_key_file_not_found(self):
        """Test loading a key from a non-existent file."""
        print("  Testing load key with non-existent file...")
        nonexistent_file = os.path.join(self.temp_dir.name, 'nonexistent.key')

        # Verify it raises the correct exception
        with self.assertRaises(FileReadError):
            self.key_manager.load_key(nonexistent_file)

    def test_load_key_invalid_length(self):
        """Test loading a key with invalid length."""
        print("  Testing load key with invalid length...")
        # Create a key file with invalid length
        invalid_key_file = os.path.join(self.temp_dir.name, 'invalid_key.key')
        with open(invalid_key_file, 'wb') as f:
            f.write(b'1234')  # Invalid length for Fernet key

        # Verify it raises the correct exception
        with self.assertRaises(EncryptionError):
            self.key_manager.load_key(invalid_key_file)


class TestFernetEncryption(unittest.TestCase):
    """Test case for the FernetEncryption class."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: data/encryption.py - FernetEncryption")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: FernetEncryption")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up before each test method."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        # Create a valid Fernet key
        from cryptography.fernet import Fernet
        self.key = Fernet.generate_key()
        self.fernet = FernetEncryption(self.key)

    def tearDown(self):
        """Tear down after each test method."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

    def test_encrypt_decrypt(self):
        """Test basic encryption and decryption."""
        print("  Testing basic encryption and decryption...")
        original_data = "This is sensitive data"

        # Encrypt
        encrypted_data = self.fernet.encrypt(original_data)
        self.assertIsInstance(encrypted_data, str)
        self.assertNotEqual(encrypted_data, original_data)

        # Decrypt
        decrypted_data = self.fernet.decrypt(encrypted_data)
        self.assertEqual(decrypted_data, original_data)

    def test_encrypt_decrypt_empty_string(self):
        """Test encryption and decryption of an empty string."""
        print("  Testing encryption/decryption of empty string...")
        original_data = ""

        # Encrypt
        encrypted_data = self.fernet.encrypt(original_data)
        self.assertIsInstance(encrypted_data, str)
        self.assertNotEqual(encrypted_data, original_data)

        # Decrypt
        decrypted_data = self.fernet.decrypt(encrypted_data)
        self.assertEqual(decrypted_data, original_data)

    def test_decrypt_invalid_token(self):
        """Test decryption with an invalid token."""
        print("  Testing decryption with invalid token...")
        # Create an invalid token
        invalid_token = "Invalid token that is not properly formatted"

        # Verify it raises the correct exception
        with self.assertRaises(DecryptionError):
            self.fernet.decrypt(invalid_token)

    def test_decrypt_with_wrong_key(self):
        """Test decryption with a different key than was used for encryption."""
        print("  Testing decryption with wrong key...")
        # Encrypt data with current key
        data = "Secret message"
        encrypted = self.fernet.encrypt(data)

        # Create a new Fernet encryptor with a different key
        from cryptography.fernet import Fernet
        different_key = Fernet.generate_key()
        different_fernet = FernetEncryption(different_key)

        # Try to decrypt with different key
        with self.assertRaises(DecryptionError):
            different_fernet.decrypt(encrypted)


class TestEncryptor(unittest.TestCase):
    """Test case for the Encryptor class."""

    @classmethod
    def setUpClass(cls):
        """Set up for the test class."""
        print("\n===================================================================")
        print("  TESTING: data/encryption.py - Encryptor")
        print("===================================================================")
        cls.start_time = time.time()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in the class have run."""
        elapsed = time.time() - cls.start_time
        print("\n-------------------------------------------------------------------")
        print(f"  COMPLETED ALL TESTS FOR: Encryptor")
        print(f"  Total time: {elapsed:.2f} seconds")
        print("===================================================================")

    def setUp(self):
        """Set up before each test method."""
        self.start_time = time.time()
        self.test_name = self.id().split('.')[-1]
        print(f"\n→ Running: {self.test_name}")

        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_salt_file = os.path.join(self.temp_dir.name, 'test_salt.salt')
        self.temp_key_file = os.path.join(self.temp_dir.name, 'test_key.key')

        # Create salt and key files for testing
        self.key_manager = EncryptionKeyManager(salt_file=self.temp_salt_file)
        salt = self.key_manager.generate_salt()
        self.key_manager.save_salt(salt, self.temp_salt_file)

        # Generate key file with a test password
        self.test_password = "test_password"
        self.key_manager.generate_key_file(
            self.temp_key_file,
            password=self.test_password,
            salt=salt
        )

        # Create test file
        self.test_file = os.path.join(self.temp_dir.name, 'test_file.txt')
        with open(self.test_file, 'w') as f:
            f.write("This is test content for encryption")

        # Create test dictionary
        self.test_dict = {
            "key1": "value1",
            "key2": 123,
            "key3": [1, 2, 3],
            "key4": {"nested": "value"}
        }

    def tearDown(self):
        """Tear down after each test method."""
        elapsed = time.time() - self.start_time
        print(f"  ✓ Passed: {self.test_name} ({elapsed:.4f} sec)")

        # Clean up
        self.temp_dir.cleanup()

    def test_init_with_password(self):
        """Test initializing with a password."""
        print("  Testing initialization with password...")
        encryptor = Encryptor(
            password=self.test_password,
            salt_file=self.temp_salt_file
        )
        self.assertIsNotNone(encryptor.cipher)

    def test_init_with_key_file(self):
        """Test initializing with a key file."""
        print("  Testing initialization with key file...")
        encryptor = Encryptor(key_file=self.temp_key_file)
        self.assertIsNotNone(encryptor.cipher)

    def test_init_no_password_or_key(self):
        """Test initializing without password or key file."""
        print("  Testing initialization without password or key file...")
        with self.assertRaises(EncryptionError):
            Encryptor()

    def test_init_unsupported_algorithm(self):
        """Test initializing with an unsupported algorithm."""
        print("  Testing initialization with unsupported algorithm...")
        with self.assertRaises(EncryptionError):
            Encryptor(
                password=self.test_password,
                salt_file=self.temp_salt_file,
                algorithm="unsupported"
            )

    def test_encrypt_decrypt(self):
        """Test basic string encryption and decryption."""
        print("  Testing basic string encryption and decryption...")
        encryptor = Encryptor(password=self.test_password, salt_file=self.temp_salt_file)
        original = "This is a test string"

        # Encrypt
        encrypted = encryptor.encrypt(original)
        self.assertIsInstance(encrypted, str)
        self.assertNotEqual(encrypted, original)

        # Decrypt
        decrypted = encryptor.decrypt(encrypted)
        self.assertEqual(decrypted, original)

    def test_encrypt_decrypt_file(self):
        """Test file encryption and decryption."""
        print("  Testing file encryption and decryption...")
        encryptor = Encryptor(password=self.test_password, salt_file=self.temp_salt_file)
        encrypted_file = os.path.join(self.temp_dir.name, 'encrypted_file.txt')
        decrypted_file = os.path.join(self.temp_dir.name, 'decrypted_file.txt')

        # Read original content
        with open(self.test_file, 'r') as f:
            original_content = f.read()

        # Encrypt file
        encryptor.encrypt_file(self.test_file, encrypted_file)
        self.assertTrue(os.path.exists(encrypted_file))

        # Verify content is encrypted
        with open(encrypted_file, 'r') as f:
            encrypted_content = f.read()
            self.assertNotEqual(encrypted_content, original_content)

        # Decrypt file
        encryptor.decrypt_file(encrypted_file, decrypted_file)
        self.assertTrue(os.path.exists(decrypted_file))

        # Verify content is restored
        with open(decrypted_file, 'r') as f:
            decrypted_content = f.read()
            self.assertEqual(decrypted_content, original_content)

    def test_encrypt_decrypt_file_delete_original(self):
        """Test file encryption with deletion of original."""
        print("  Testing file encryption with deletion of original...")
        encryptor = Encryptor(password=self.test_password, salt_file=self.temp_salt_file)

        # Encrypt file and delete original
        encrypted_file = encryptor.encrypt_file(self.test_file, delete_original=True)

        # Verify original is deleted and encrypted exists
        self.assertFalse(os.path.exists(self.test_file))
        self.assertTrue(os.path.exists(encrypted_file))

    def test_encrypt_decrypt_dict(self):
        """Test dictionary encryption and decryption."""
        print("  Testing dictionary encryption and decryption...")
        encryptor = Encryptor(password=self.test_password, salt_file=self.temp_salt_file)

        # Encrypt dictionary
        encrypted = encryptor.encrypt_dict(self.test_dict)
        self.assertIsInstance(encrypted, str)

        # Decrypt dictionary
        decrypted = encryptor.decrypt_dict(encrypted)
        self.assertEqual(decrypted, self.test_dict)

    def test_decrypt_dict_invalid_json(self):
        """Test decrypting a string that doesn't contain valid JSON."""
        print("  Testing dictionary decryption with invalid JSON...")
        encryptor = Encryptor(password=self.test_password, salt_file=self.temp_salt_file)

        # Encrypt a non-JSON string
        encrypted = encryptor.encrypt("This is not JSON")

        # Try to decrypt as a dictionary
        with self.assertRaises(DecryptionError):
            encryptor.decrypt_dict(encrypted)

    def test_encrypt_file_not_found(self):
        """Test encrypting a non-existent file."""
        print("  Testing encryption of non-existent file...")
        encryptor = Encryptor(password=self.test_password, salt_file=self.temp_salt_file)
        nonexistent_file = os.path.join(self.temp_dir.name, 'nonexistent.txt')

        # Try to encrypt a non-existent file
        with self.assertRaises(FileReadError):
            encryptor.encrypt_file(nonexistent_file)

    def test_decrypt_file_not_found(self):
        """Test decrypting a non-existent file."""
        print("  Testing decryption of non-existent file...")
        encryptor = Encryptor(password=self.test_password, salt_file=self.temp_salt_file)
        nonexistent_file = os.path.join(self.temp_dir.name, 'nonexistent.txt')

        # Try to decrypt a non-existent file
        with self.assertRaises(FileReadError):
            encryptor.decrypt_file(nonexistent_file)


class TestPasswordHelperFunction(unittest.TestCase):
    """Test case for the get_password helper function."""

    def test_get_password(self):
        """Test the get_password function."""
        # Mock getpass.getpass to return a fixed password
        with patch('getpass.getpass', return_value='mocked_password'):
            password = get_password("Enter password: ")
            self.assertEqual(password, 'mocked_password')


if __name__ == '__main__':
    unittest.main(verbosity=2)