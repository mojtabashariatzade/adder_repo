"""
Tests for the FileManager module (data/file_manager.py).

This module contains unit tests for the FileManager class and its subclasses
(JsonFileManager, EncryptedFileManager) which manage file operations.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import sys
import logging
import time
import shutil
from pathlib import Path
import threading

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the module and exceptions
from data.file_manager import (
    FileManager, JsonFileManager, EncryptedFileManager,
    SafeFileWriter, get_file_manager
)
from core.exceptions import (
    FileReadError, FileWriteError, FileFormatError,
    EncryptionError, DecryptionError
)


class TestFileManager(unittest.TestCase):
    """Test suite for the FileManager class."""

    def setUp(self):
        """Set up test fixtures, if any."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Create a file manager instance
        self.file_manager = FileManager(base_dir=self.test_dir)

        # Create test files and directories
        self.test_file = self.test_dir / "test_file.txt"
        self.test_file.write_text("Test content")

        self.test_binary_file = self.test_dir / "test_binary.bin"
        self.test_binary_file.write_bytes(b'\x00\x01\x02\x03')

        self.test_dir_path = self.test_dir / "test_dir"
        self.test_dir_path.mkdir()

        self.non_existent_file = self.test_dir / "non_existent.txt"

    def tearDown(self):
        """Tear down test fixtures, if any."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_init(self):
        """Test initialization of FileManager."""
        # Test with default base directory
        fm = FileManager()
        self.assertEqual(fm.base_dir, os.getcwd())

        # Test with custom base directory
        custom_dir = "/tmp/custom_dir"
        fm = FileManager(base_dir=custom_dir)
        self.assertEqual(fm.base_dir, custom_dir)

    def test_resolve_path(self):
        """Test path resolution."""
        # Test with relative path
        rel_path = "relative/path.txt"
        abs_path = self.file_manager._resolve_path(rel_path)
        expected_path = Path(self.test_dir) / rel_path
        self.assertEqual(abs_path, expected_path)

        # Test with absolute path
        abs_path_str = "/absolute/path.txt"
        result_path = self.file_manager._resolve_path(abs_path_str)
        self.assertEqual(result_path, Path(abs_path_str))

        # Test with Path object
        path_obj = Path("path/object.txt")
        result_path = self.file_manager._resolve_path(path_obj)
        expected_path = Path(self.test_dir) / path_obj
        self.assertEqual(result_path, expected_path)

    def test_exists(self):
        """Test file existence check."""
        # Test with existing file
        self.assertTrue(self.file_manager.exists(self.test_file))

        # Test with non-existent file
        self.assertFalse(self.file_manager.exists(self.non_existent_file))

        # Test with directory
        self.assertTrue(self.file_manager.exists(self.test_dir_path))

    def test_is_file(self):
        """Test file type check."""
        # Test with file
        self.assertTrue(self.file_manager.is_file(self.test_file))

        # Test with directory
        self.assertFalse(self.file_manager.is_file(self.test_dir_path))

        # Test with non-existent file
        self.assertFalse(self.file_manager.is_file(self.non_existent_file))

    def test_is_dir(self):
        """Test directory type check."""
        # Test with directory
        self.assertTrue(self.file_manager.is_dir(self.test_dir_path))

        # Test with file
        self.assertFalse(self.file_manager.is_dir(self.test_file))

        # Test with non-existent directory
        non_existent_dir = self.test_dir / "non_existent_dir"
        self.assertFalse(self.file_manager.is_dir(non_existent_dir))

    def test_ensure_dir(self):
        """Test directory creation."""
        # Test creating a new directory
        new_dir = self.test_dir / "new_dir"
        result_dir = self.file_manager.ensure_dir(new_dir)
        self.assertTrue(new_dir.exists())
        self.assertTrue(new_dir.is_dir())
        self.assertEqual(result_dir, new_dir)

        # Test with existing directory
        result_dir = self.file_manager.ensure_dir(self.test_dir_path)
        self.assertEqual(result_dir, self.test_dir_path)

        # Test with nested directory
        nested_dir = self.test_dir / "parent/child/grandchild"
        result_dir = self.file_manager.ensure_dir(nested_dir)
        self.assertTrue(nested_dir.exists())
        self.assertTrue(nested_dir.is_dir())
        self.assertEqual(result_dir, nested_dir)

    def test_ensure_parent_dir(self):
        """Test parent directory creation."""
        # Test with file in new directory
        new_file = self.test_dir / "new_dir/test.txt"
        parent_dir = self.file_manager.ensure_parent_dir(new_file)
        self.assertTrue(parent_dir.exists())
        self.assertTrue(parent_dir.is_dir())
        self.assertEqual(parent_dir, new_file.parent)

        # Test with file in existing directory
        file_in_existing = self.test_dir_path / "test.txt"
        parent_dir = self.file_manager.ensure_parent_dir(file_in_existing)
        self.assertEqual(parent_dir, self.test_dir_path)

    def test_read_text(self):
        """Test reading text from a file."""
        # Test with existing file
        content = self.file_manager.read_text(self.test_file)
        self.assertEqual(content, "Test content")

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.file_manager.read_text(self.non_existent_file)

        # Test with directory
        with self.assertRaises(FileReadError):
            self.file_manager.read_text(self.test_dir_path)

        # Test with binary file (should work with proper encoding)
        binary_as_text = self.file_manager.read_text(self.test_binary_file, encoding='latin1')
        self.assertEqual(len(binary_as_text), 4)

    def test_read_binary(self):
        """Test reading binary data from a file."""
        # Test with existing binary file
        content = self.file_manager.read_binary(self.test_binary_file)
        self.assertEqual(content, b'\x00\x01\x02\x03')

        # Test with text file (should work)
        content = self.file_manager.read_binary(self.test_file)
        self.assertEqual(content, b'Test content')

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.file_manager.read_binary(self.non_existent_file)

        # Test with directory
        with self.assertRaises(FileReadError):
            self.file_manager.read_binary(self.test_dir_path)

    def test_write_text(self):
        """Test writing text to a file."""
        # Test writing to a new file
        new_file = self.test_dir / "new_text.txt"
        self.file_manager.write_text(new_file, "New content")
        self.assertTrue(new_file.exists())
        self.assertEqual(new_file.read_text(), "New content")

        # Test writing to an existing file
        self.file_manager.write_text(self.test_file, "Updated content")
        self.assertEqual(self.test_file.read_text(), "Updated content")

        # Test with different encoding
        unicode_file = self.test_dir / "unicode.txt"
        unicode_content = "⻢⸎ 鸜 好熊猫"
        self.file_manager.write_text(unicode_file, unicode_content, encoding='utf-8')
        self.assertEqual(unicode_file.read_text(encoding='utf-8'), unicode_content)

        # Test with make_backup=True
        backup_file = self.test_dir / "backup_test.txt"
        backup_file.write_text("Original content")
        self.file_manager.write_text(backup_file, "New content", make_backup=True)

        # Check that a backup was created
        backup_files = list(self.test_dir.glob("backup_test.txt.bak.*"))
        self.assertTrue(len(backup_files) > 0)
        self.assertEqual(backup_files[0].read_text(), "Original content")
        self.assertEqual(backup_file.read_text(), "New content")

    def test_write_binary(self):
        """Test writing binary data to a file."""
        # Test writing to a new file
        new_file = self.test_dir / "new_binary.bin"
        binary_data = b'\x04\x05\x06\x07'
        self.file_manager.write_binary(new_file, binary_data)
        self.assertTrue(new_file.exists())
        self.assertEqual(new_file.read_bytes(), binary_data)

        # Test writing to an existing file
        updated_data = b'\x08\x09\x0A\x0B'
        self.file_manager.write_binary(self.test_binary_file, updated_data)
        self.assertEqual(self.test_binary_file.read_bytes(), updated_data)

        # Test with make_backup=True
        backup_file = self.test_dir / "backup_binary.bin"
        original_data = b'\x0C\x0D\x0E\x0F'
        backup_file.write_bytes(original_data)
        self.file_manager.write_binary(backup_file, binary_data, make_backup=True)

        # Check that a backup was created
        backup_files = list(self.test_dir.glob("backup_binary.bin.bak.*"))
        self.assertTrue(len(backup_files) > 0)
        self.assertEqual(backup_files[0].read_bytes(), original_data)
        self.assertEqual(backup_file.read_bytes(), binary_data)

    def test_make_backup(self):
        """Test making a backup of a file."""
        # Test backing up a text file
        backup_path = self.file_manager.make_backup(self.test_file)
        self.assertTrue(backup_path.exists())
        self.assertEqual(backup_path.read_text(), "Test content")

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.file_manager.make_backup(self.non_existent_file)

        # Test with custom suffix
        custom_suffix = ".custom_backup"
        backup_path = self.file_manager.make_backup(self.test_file, backup_suffix=custom_suffix)
        self.assertTrue(str(backup_path).endswith(custom_suffix))
        self.assertEqual(backup_path.read_text(), "Test content")

    def test_delete(self):
        """Test deleting a file."""
        # Test deleting a file
        file_to_delete = self.test_dir / "delete_me.txt"
        file_to_delete.write_text("Delete me")
        self.assertTrue(self.file_manager.delete(file_to_delete))
        self.assertFalse(file_to_delete.exists())

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.file_manager.delete(self.non_existent_file)

        # Test with missing_ok=True
        self.assertFalse(self.file_manager.delete(self.non_existent_file, missing_ok=True))

        # Test deleting a directory
        dir_to_delete = self.test_dir / "delete_dir"
        dir_to_delete.mkdir()
        (dir_to_delete / "file.txt").write_text("Test")
        self.assertTrue(self.file_manager.delete(dir_to_delete))
        self.assertFalse(dir_to_delete.exists())

    def test_copy(self):
        """Test copying a file."""
        # Test copying a file
        dest_file = self.test_dir / "copied_file.txt"
        result_path = self.file_manager.copy(self.test_file, dest_file)
        self.assertTrue(dest_file.exists())
        self.assertEqual(dest_file.read_text(), "Test content")
        self.assertEqual(result_path, dest_file)

        # Test with non-existent source
        with self.assertRaises(FileReadError):
            self.file_manager.copy(self.non_existent_file, dest_file)

        # Test with existing destination (should fail without overwrite)
        with self.assertRaises(FileWriteError):
            self.file_manager.copy(self.test_file, dest_file)

        # Test with overwrite=True
        self.test_file.write_text("Updated content")
        result_path = self.file_manager.copy(self.test_file, dest_file, overwrite=True)
        self.assertEqual(dest_file.read_text(), "Updated content")

        # Test copying a directory
        dest_dir = self.test_dir / "copied_dir"
        (self.test_dir_path / "dir_file.txt").write_text("Dir file content")
        result_path = self.file_manager.copy(self.test_dir_path, dest_dir)
        self.assertTrue(dest_dir.exists())
        self.assertTrue((dest_dir / "dir_file.txt").exists())
        self.assertEqual((dest_dir / "dir_file.txt").read_text(), "Dir file content")

    def test_move(self):
        """Test moving a file."""
        # Test moving a file
        file_to_move = self.test_dir / "move_me.txt"
        file_to_move.write_text("Move me")
        dest_file = self.test_dir / "moved_file.txt"
        result_path = self.file_manager.move(file_to_move, dest_file)
        self.assertFalse(file_to_move.exists())
        self.assertTrue(dest_file.exists())
        self.assertEqual(dest_file.read_text(), "Move me")
        self.assertEqual(result_path, dest_file)

        # Test with non-existent source
        with self.assertRaises(FileReadError):
            self.file_manager.move(self.non_existent_file, dest_file)

        # Test with existing destination (should fail without overwrite)
        file_to_move = self.test_dir / "move_me2.txt"
        file_to_move.write_text("Move me again")
        with self.assertRaises(FileWriteError):
            self.file_manager.move(file_to_move, dest_file)

        # Test with overwrite=True
        result_path = self.file_manager.move(file_to_move, dest_file, overwrite=True)
        self.assertFalse(file_to_move.exists())
        self.assertTrue(dest_file.exists())
        self.assertEqual(dest_file.read_text(), "Move me again")

        # Test moving a directory
        dir_to_move = self.test_dir / "move_dir"
        dir_to_move.mkdir()
        (dir_to_move / "dir_file.txt").write_text("Dir file content")
        dest_dir = self.test_dir / "moved_dir"
        result_path = self.file_manager.move(dir_to_move, dest_dir)
        self.assertFalse(dir_to_move.exists())
        self.assertTrue(dest_dir.exists())
        self.assertTrue((dest_dir / "dir_file.txt").exists())
        self.assertEqual((dest_dir / "dir_file.txt").read_text(), "Dir file content")

    def test_list_dir(self):
        """Test listing directory contents."""
        # Create test files in a new directory
        test_dir = self.test_dir / "list_dir_test"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("File 1")
        (test_dir / "file2.txt").write_text("File 2")
        (test_dir / "file3.bin").write_bytes(b'\x01\x02')
        (test_dir / "subdir").mkdir()

        # Test listing all files and directories
        items = self.file_manager.list_dir(test_dir)
        self.assertEqual(len(items), 4)

        # Test with pattern
        txt_files = self.file_manager.list_dir(test_dir, pattern="*.txt")
        self.assertEqual(len(txt_files), 2)

        # Test with non-existent directory
        with self.assertRaises(FileReadError):
            self.file_manager.list_dir(self.test_dir / "non_existent_dir")

        # Test with file instead of directory
        with self.assertRaises(FileReadError):
            self.file_manager.list_dir(self.test_file)

    def test_get_file_info(self):
        """Test getting file information."""
        # Test with a file
        info = self.file_manager.get_file_info(self.test_file)
        self.assertEqual(info['name'], self.test_file.name)
        self.assertEqual(info['size'], len("Test content"))
        self.assertTrue(info['is_file'])
        self.assertFalse(info['is_dir'])
        self.assertEqual(info['extension'], '.txt')
        self.assertIsNotNone(info['hash'])

        # Test with a directory
        info = self.file_manager.get_file_info(self.test_dir_path)
        self.assertEqual(info['name'], self.test_dir_path.name)
        self.assertFalse(info['is_file'])
        self.assertTrue(info['is_dir'])
        self.assertIsNone(info['extension'])
        self.assertIsNone(info['hash'])

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.file_manager.get_file_info(self.non_existent_file)

    def test_calculate_file_hash(self):
        """Test calculating file hash."""
        # Create a file with known content
        hash_test_file = self.test_dir / "hash_test.txt"
        hash_test_file.write_text("fixed content for hash test")

        # Calculate hash with default algorithm (SHA-256)
        hash_value = self.file_manager.calculate_file_hash(hash_test_file)
        self.assertIsInstance(hash_value, str)
        self.assertTrue(len(hash_value) > 0)

        # Calculate hash with MD5
        md5_hash = self.file_manager.calculate_file_hash(hash_test_file, algorithm='md5')
        self.assertIsInstance(md5_hash, str)
        self.assertNotEqual(hash_value, md5_hash)

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.file_manager.calculate_file_hash(self.non_existent_file)

        # Test with unsupported algorithm
        with self.assertRaises(ValueError):
            self.file_manager.calculate_file_hash(hash_test_file, algorithm='unsupported')

        # Test with directory
        with self.assertRaises(FileReadError):
            self.file_manager.calculate_file_hash(self.test_dir_path)

    def test_get_temp_file(self):
        """Test creating a temporary file."""
        # Test basic temp file creation
        temp_path, cleanup = self.file_manager.get_temp_file()
        self.assertTrue(os.path.exists(temp_path))

        # Write to the temp file
        with open(temp_path, 'w') as f:
            f.write("Test")

        # Clean up and verify
        cleanup()
        self.assertFalse(os.path.exists(temp_path))

        # Test with suffix and prefix
        temp_path, cleanup = self.file_manager.get_temp_file(suffix='.txt', prefix='test_')
        try:
            self.assertTrue(str(temp_path).endswith('.txt'))
            self.assertTrue(os.path.basename(str(temp_path)).startswith('test_'))
        finally:
            cleanup()

        # Test with custom directory
        custom_dir = self.test_dir / "temp_files"
        temp_path, cleanup = self.file_manager.get_temp_file(dir=custom_dir)
        try:
            self.assertTrue(custom_dir.exists())
            self.assertTrue(str(temp_path).startswith(str(custom_dir)))
        finally:
            cleanup()

    def test_get_temp_dir(self):
        """Test creating a temporary directory."""
        # Test basic temp directory creation
        temp_dir, cleanup = self.file_manager.get_temp_dir()
        self.assertTrue(os.path.exists(temp_dir))
        self.assertTrue(os.path.isdir(temp_dir))

        # Create a file in the temp directory
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("Test")

        # Clean up and verify
        cleanup()
        self.assertFalse(os.path.exists(temp_dir))

        # Test with suffix and prefix
        temp_dir, cleanup = self.file_manager.get_temp_dir(suffix='_dir', prefix='test_')
        try:
            self.assertTrue(str(temp_dir).endswith('_dir'))
            self.assertTrue(os.path.basename(str(temp_dir)).startswith('test_'))
        finally:
            cleanup()

        # Test with custom parent directory
        custom_parent = self.test_dir / "temp_dirs"
        temp_dir, cleanup = self.file_manager.get_temp_dir(dir=custom_parent)
        try:
            self.assertTrue(custom_parent.exists())
            self.assertTrue(str(temp_dir).startswith(str(custom_parent)))
        finally:
            cleanup()


class TestJsonFileManager(unittest.TestCase):
    """Test suite for the JsonFileManager class."""

    def setUp(self):
        """Set up test fixtures, if any."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Create a JSON file manager instance
        self.json_manager = JsonFileManager(base_dir=self.test_dir)

        # Create test JSON files
        self.test_json_file = self.test_dir / "test.json"
        self.test_json_data = {"key1": "value1", "key2": 42, "key3": [1, 2, 3]}
        with open(self.test_json_file, 'w') as f:
            json.dump(self.test_json_data, f)

        self.invalid_json_file = self.test_dir / "invalid.json"
        with open(self.invalid_json_file, 'w') as f:
            f.write("This is not valid JSON")

        self.non_existent_json = self.test_dir / "non_existent.json"

    def tearDown(self):
        """Tear down test fixtures, if any."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_init(self):
        """Test initialization of JsonFileManager."""
        # Test with default parameters
        jfm = JsonFileManager()
        self.assertEqual(jfm.base_dir, os.getcwd())
        self.assertEqual(jfm.indent, 4)

        # Test with custom parameters
        custom_dir = "/tmp/custom_dir"
        custom_indent = 2
        jfm = JsonFileManager(base_dir=custom_dir, indent=custom_indent)
        self.assertEqual(jfm.base_dir, custom_dir)
        self.assertEqual(jfm.indent, custom_indent)

    def test_read_json(self):
        """Test reading a JSON file."""
        # Test with valid JSON file
        data = self.json_manager.read_json(self.test_json_file)
        self.assertEqual(data, self.test_json_data)

        # Test with invalid JSON file
        with self.assertRaises(FileFormatError):
            self.json_manager.read_json(self.invalid_json_file)

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.json_manager.read_json(self.non_existent_json)

        # Test with default value for non-existent file
        default_data = {"default": "value"}
        data = self.json_manager.read_json(self.non_existent_json, default=default_data)
        self.assertEqual(data, default_data)

    def test_write_json(self):
        """Test writing a JSON file."""
        # Test writing to a new file
        new_file = self.test_dir / "new.json"
        new_data = {"new": "data"}
        self.json_manager.write_json(new_file, new_data)

        # Verify the file was written correctly
        with open(new_file, 'r') as f:
            loaded_data = json.load(f)
        self.assertEqual(loaded_data, new_data)

        # Test writing to an existing file
        updated_data = {"updated": "data"}
        self.json_manager.write_json(self.test_json_file, updated_data)

        # Verify the file was updated correctly
        with open(self.test_json_file, 'r') as f:
            loaded_data = json.load(f)
        self.assertEqual(loaded_data, updated_data)

        # Test with non-serializable data
        with self.assertRaises(TypeError):
            self.json_manager.write_json(new_file, {"key": set([1, 2, 3])})

        # Test with make_backup=True
        backup_file = self.test_dir / "backup.json"
        original_data = {"original": "data"}
        with open(backup_file, 'w') as f:
            json.dump(original_data, f)

        self.json_manager.write_json(backup_file, {"new": "data"}, make_backup=True)

        # Check that a backup was created
        backup_files = list(self.test_dir.glob("backup.json.bak.*"))
        self.assertTrue(len(backup_files) > 0)
        with open(backup_files[0], 'r') as f:
            backup_data = json.load(f)
        self.assertEqual(backup_data, original_data)

    def test_merge_json(self):
        """Test merging JSON files."""
        # Create source and target files
        target_file = self.test_dir / "target.json"
        target_data = {"key1": "target1", "key2": "target2"}
        with open(target_file, 'w') as f:
            json.dump(target_data, f)

        source_file = self.test_dir / "source.json"
        source_data = {"key2": "source2", "key3": "source3"}
        with open(source_file, 'w') as f:
            json.dump(source_data, f)

        # Test merging with overwrite=True (default)
        merged_data = self.json_manager.merge_json(target_file, source_file)
        expected_data = {"key1": "target1", "key2": "source2", "key3": "source3"}
        self.assertEqual(merged_data, expected_data)

        # Verify the file was updated correctly
        with open(target_file, 'r') as f:
            loaded_data = json.load(f)
        self.assertEqual(loaded_data, expected_data)

        # Test with overwrite=False
        # Reset target file
        with open(target_file, 'w') as f:
            json.dump(target_data, f)

        merged_data = self.json_manager.merge_json(target_file, source_file, overwrite=False)
        expected_data = {"key1": "target1", "key2": "target2", "key3": "source3"}
        self.assertEqual(merged_data, expected_data)

        # Verify the file was updated correctly
        with open(target_file, 'r') as f:
            loaded_data = json.load(f)
        self.assertEqual(loaded_data, expected_data)

        # Test with non-existent target (should create it)
        non_existent_target = self.test_dir / "non_existent_target.json"
        merged_data = self.json_manager.merge_json(non_existent_target, source_file)
        self.assertEqual(merged_data, source_data)

        # Test with non-existent source
        with self.assertRaises(FileReadError):
            self.json_manager.merge_json(target_file, self.non_existent_json)

    @unittest.skipIf(True, "jsonschema package required for this test")
    def test_validate_json(self):
        """Test validating a JSON file against a schema."""
        # This test is skipped by default because it requires the jsonschema package
        # If you have jsonschema installed, change the skipIf condition to False

        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema package is required for this test")

        # Create a test file
        valid_file = self.test_dir / "valid.json"
        valid_data = {
            "name": "Test Name",
            "age": 30,
            "email": "test@example.com"
        }
        with open(valid_file, 'w') as f:
            json.dump(valid_data, f)

        # Create an invalid file
        invalid_file = self.test_dir / "invalid_schema.json"
        invalid_data = {
            "name": "Test Name",
            "age": "thirty",  # Should be an integer
            "email": "not_an_email"  # Should be an email format
        }
        with open(invalid_file, 'w') as f:
            json.dump(invalid_data, f)

        # Define a schema
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string", "format": "email"}
            },
            "required": ["name", "age", "email"]
        }

        # Test with valid file
        is_valid, issues = self.json_manager.validate_json(valid_file, schema)
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)

        # Test with invalid file
        is_valid, issues = self.json_manager.validate_json(invalid_file, schema)
        self.assertFalse(is_valid)
        self.assertTrue(len(issues) > 0)

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.json_manager.validate_json(self.non_existent_json, schema)

        # Test with invalid schema
        invalid_schema = {"type": "not_a_valid_type"}
        with self.assertRaises(Exception):  # Could be SchemaError or other exception
            self.json_manager.validate_json(valid_file, invalid_schema)


class TestEncryptedFileManager(unittest.TestCase):
    """Test suite for the EncryptedFileManager class."""

    def setUp(self):
        """Set up test fixtures, if any."""
        # Skip tests if Encryptor is not available
        try:
            from data.encryption import Encryptor
        except ImportError:
            self.skipTest("data.encryption.Encryptor is not available")

        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Create a mock Encryptor
        self.mock_encryptor = MagicMock()
        self.mock_encryptor.encrypt.side_effect = lambda text: f"ENCRYPTED:{text}"
        self.mock_encryptor.decrypt.side_effect = lambda text: text.replace("ENCRYPTED:", "")

        # Create an EncryptedFileManager instance
        self.enc_manager = EncryptedFileManager(self.mock_encryptor, base_dir=self.test_dir)

        # Create test files
        self.test_file = self.test_dir / "test.txt"
        with open(self.test_file, 'w') as f:
            f.write("ENCRYPTED:Original content")

        self.test_json_file = self.test_dir / "test.json"
        with open(self.test_json_file, 'w') as f:
            f.write('ENCRYPTED:{"key1": "value1", "key2": 42}')

        self.non_existent_file = self.test_dir / "non_existent.txt"

    def tearDown(self):
        """Tear down test fixtures, if any."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_init(self):
        """Test initialization of EncryptedFileManager."""
        # Test with valid encryptor
        self.assertIsInstance(self.enc_manager, EncryptedFileManager)

        # Test with invalid encryptor
        with self.assertRaises(TypeError):
            EncryptedFileManager("not an encryptor")

    def test_read_encrypted(self):
        """Test reading an encrypted file."""
        # Test with valid encrypted file
        content = self.enc_manager.read_encrypted(self.test_file)
        self.assertEqual(content, "Original content")
        self.mock_encryptor.decrypt.assert_called_with("ENCRYPTED:Original content")

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.enc_manager.read_encrypted(self.non_existent_file)

        # Test with decryption error
        self.mock_encryptor.decrypt.side_effect = Exception("Decryption error")
        with self.assertRaises(DecryptionError):
            self.enc_manager.read_encrypted(self.test_file)

        # Reset side effect
        self.mock_encryptor.decrypt.side_effect = lambda text: text.replace("ENCRYPTED:", "")

    def test_write_encrypted(self):
        """Test writing an encrypted file."""
        # Test writing to a new file
        new_file = self.test_dir / "new_encrypted.txt"
        self.enc_manager.write_encrypted(new_file, "New content")
        self.mock_encryptor.encrypt.assert_called_with("New content")

        # Check file content
        self.assertTrue(new_file.exists())
        with open(new_file, 'r') as f:
            content = f.read()
        self.assertEqual(content, "ENCRYPTED:New content")

        # Test with encryption error
        self.mock_encryptor.encrypt.side_effect = Exception("Encryption error")
        with self.assertRaises(EncryptionError):
            self.enc_manager.write_encrypted(new_file, "Updated content")

        # Reset side effect
        self.mock_encryptor.encrypt.side_effect = lambda text: f"ENCRYPTED:{text}"

        # Test with make_backup=True
        self.enc_manager.write_encrypted(self.test_file, "Updated content", make_backup=True)

        # Check that a backup was created
        backup_files = list(self.test_dir.glob("test.txt.bak.*"))
        self.assertTrue(len(backup_files) > 0)
        with open(backup_files[0], 'r') as f:
            backup_content = f.read()
        self.assertEqual(backup_content, "ENCRYPTED:Original content")

    def test_read_encrypted_json(self):
        """Test reading an encrypted JSON file."""
        # Test with valid encrypted JSON
        data = self.enc_manager.read_encrypted_json(self.test_json_file)
        self.assertEqual(data, {"key1": "value1", "key2": 42})

        # Test with non-existent file
        with self.assertRaises(FileReadError):
            self.enc_manager.read_encrypted_json(self.non_existent_file)

        # Test with default value for non-existent file
        default_data = {"default": "value"}
        data = self.enc_manager.read_encrypted_json(self.non_existent_file, default=default_data)
        self.assertEqual(data, default_data)

        # Test with invalid JSON
        invalid_json = self.test_dir / "invalid.json"
        with open(invalid_json, 'w') as f:
            f.write("ENCRYPTED:This is not valid JSON")

        with self.assertRaises(FileFormatError):
            self.enc_manager.read_encrypted_json(invalid_json)

    def test_write_encrypted_json(self):
        """Test writing an encrypted JSON file."""
        # Test writing to a new file
        new_file = self.test_dir / "new_encrypted.json"
        json_data = {"key1": "value1", "key2": 42, "key3": [1, 2, 3]}
        self.enc_manager.write_encrypted_json(new_file, json_data)

        # The encrypt method should be called with a JSON string
        call_args = self.mock_encryptor.encrypt.call_args[0][0]
        self.assertIn('"key1": "value1"', call_args)
        self.assertIn('"key2": 42', call_args)

        # Test with non-serializable data
        with self.assertRaises(TypeError):
            self.enc_manager.write_encrypted_json(new_file, {"key": set([1, 2, 3])})

        # Test with custom indent
        self.enc_manager.write_encrypted_json(new_file, json_data, indent=2)

        # Test with make_backup=True
        self.enc_manager.write_encrypted_json(self.test_json_file, json_data, make_backup=True)

        # Check that a backup was created
        backup_files = list(self.test_dir.glob("test.json.bak.*"))
        self.assertTrue(len(backup_files) > 0)


class TestSafeFileWriter(unittest.TestCase):
    """Test suite for the SafeFileWriter class."""

    def setUp(self):
        """Set up test fixtures, if any."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Create test file
        self.test_file = self.test_dir / "test_safe.txt"
        with open(self.test_file, 'w') as f:
            f.write("Original content")

    def tearDown(self):
        """Tear down test fixtures, if any."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_get_lock(self):
        """Test getting a lock for a file path."""
        # Get locks for different paths
        path1 = str(self.test_dir / "file1.txt")
        path2 = str(self.test_dir / "file2.txt")

        lock1 = SafeFileWriter.get_lock(path1)
        lock2 = SafeFileWriter.get_lock(path2)

        # Different paths should have different locks
        self.assertIsNot(lock1, lock2)

        # Same path should get same lock
        lock1_again = SafeFileWriter.get_lock(path1)
        self.assertIs(lock1, lock1_again)

    def test_safe_write(self):
        """Test safe file writing."""
        # Test writing to a file
        content = "Safe content"
        SafeFileWriter.safe_write(self.test_file, content)

        # Check file content
        with open(self.test_file, 'r') as f:
            file_content = f.read()
        self.assertEqual(file_content, content)

        # Test with binary mode
        binary_content = b'\x01\x02\x03\x04'
        binary_file = self.test_dir / "binary_safe.bin"
        SafeFileWriter.safe_write(binary_file, binary_content, mode='wb')

        # Check file content
        with open(binary_file, 'rb') as f:
            file_content = f.read()
        self.assertEqual(file_content, binary_content)

        # Test with make_backup=True
        SafeFileWriter.safe_write(self.test_file, "Updated content", make_backup=True)

        # Check that a backup was created
        backup_files = list(self.test_dir.glob("test_safe.txt.bak.*"))
        self.assertTrue(len(backup_files) > 0)
        with open(backup_files[0], 'r') as f:
            backup_content = f.read()
        self.assertEqual(backup_content, "Safe content")

        # Check that file was updated
        with open(self.test_file, 'r') as f:
            file_content = f.read()
        self.assertEqual(file_content, "Updated content")

        # Test write to new directory
        new_dir_file = self.test_dir / "new_dir" / "new_file.txt"
        SafeFileWriter.safe_write(new_dir_file, "New dir content")

        # Check that directory and file were created
        self.assertTrue(new_dir_file.exists())
        with open(new_dir_file, 'r') as f:
            file_content = f.read()
        self.assertEqual(file_content, "New dir content")

    def test_safe_write_concurrent(self):
        """Test safe file writing with concurrent access."""
        # This test requires multiprocessing
        import concurrent.futures

        # Function to write to file with a delay
        def write_with_delay(content, delay):
            time.sleep(delay)
            SafeFileWriter.safe_write(self.test_file, content)
            return content

        # Run multiple writes concurrently
        contents = ["Content 1", "Content 2", "Content 3", "Content 4"]
        delays = [0.2, 0.1, 0.3, 0.05]  # Different delays to simulate race conditions

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(write_with_delay, content, delay)
                      for content, delay in zip(contents, delays)]

            # Wait for all to complete
            concurrent.futures.wait(futures)

        # Check that file content matches one of the contents (last writer wins)
        with open(self.test_file, 'r') as f:
            file_content = f.read()

        self.assertIn(file_content, contents)


class TestGetFileManager(unittest.TestCase):
    """Test suite for the get_file_manager function."""

    def test_get_basic_manager(self):
        """Test getting a basic file manager."""
        manager = get_file_manager('basic')
        self.assertIsInstance(manager, FileManager)

    def test_get_json_manager(self):
        """Test getting a JSON file manager."""
        manager = get_file_manager('json')
        self.assertIsInstance(manager, JsonFileManager)

    def test_get_encrypted_manager(self):
        """Test getting an encrypted file manager."""
        # Create a mock Encryptor
        mock_encryptor = MagicMock()

        # Get encrypted manager
        manager = get_file_manager('encrypted', mock_encryptor)
        self.assertIsInstance(manager, EncryptedFileManager)

    def test_get_unknown_manager(self):
        """Test getting an unknown manager type."""
        with self.assertRaises(ValueError):
            get_file_manager('unknown')

    def test_with_arguments(self):
        """Test passing arguments to managers."""
        base_dir = '/tmp/test_dir'

        # Test basic manager with base_dir
        manager = get_file_manager('basic', base_dir=base_dir)
        self.assertEqual(manager.base_dir, base_dir)

        # Test JSON manager with base_dir and indent
        manager = get_file_manager('json', base_dir=base_dir, indent=2)
        self.assertEqual(manager.base_dir, base_dir)
        self.assertEqual(manager.indent, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)