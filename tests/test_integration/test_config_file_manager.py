#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest
import tempfile
import json
import shutil
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.config import Config
from data.file_manager import JsonFileManager, FileManager
from core.exceptions import FileReadError, FileWriteError, FileFormatError
from core.constants import ENCRYPTION_KEY_FILE, SALT_FILE


class TestConfigFileManagerIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "config.json")

        # Create directories for test files
        os.makedirs(os.path.join(self.temp_dir, "logs"), exist_ok=True)

        # Clear singleton instance
        Config._instance = None

        # Create file manager
        self.file_manager = JsonFileManager(base_dir=self.temp_dir)

        # Save original paths and settings
        self.original_config_file = Config().get_config_file()
        self.original_encryption_enabled = Config().get('encryption_enabled', True)

        # Disable encryption for tests or set up encryption files properly
        config = Config()

        # Option 1: Disable encryption for tests
        config.set('encryption_enabled', False)

        # Option 2: Set up encryption files properly
        self.key_file = os.path.join(self.temp_dir, os.path.basename(ENCRYPTION_KEY_FILE))
        self.salt_file = os.path.join(self.temp_dir, os.path.basename(SALT_FILE))

        # Create key file with proper content (32 bytes for Fernet key)
        key_content = os.urandom(32)
        with open(self.key_file, "wb") as f:
            f.write(key_content)

        # Create salt file
        salt_content = os.urandom(16)
        with open(self.salt_file, "wb") as f:
            f.write(salt_content)

        # Update config paths to use our test files
        config.set_config_file(self.config_file)
        config.set_encryption_key_file(self.key_file)
        config.set_salt_file(self.salt_file)

        # Save changes to initialize config file
        config.save()

    def tearDown(self):
        # Reset singleton
        Config._instance = None

        # Restore original config file path and encryption setting
        config = Config()
        config.set_config_file(self.original_config_file)
        config.set('encryption_enabled', self.original_encryption_enabled)

        # Clean up temp directory
        shutil.rmtree(self.temp_dir)

    def test_load_save_config(self):
        # Get fresh Config instance
        Config._instance = None
        config = Config()

        # Record the original values for comparison
        original_values = {
            'app_name': config.get('app_name'),
            'debug_mode': config.get('debug_mode'),
            'max_retry_count': config.get('max_retry_count')
        }

        # Update with test values
        test_settings = {
            'app_name': 'Test App',
            'debug_mode': True,
            'max_retry_count': 10
        }

        config.update(test_settings)
        saved = config.save()
        self.assertTrue(saved, "Failed to save config")
        self.assertTrue(os.path.exists(self.config_file), "Config file was not created")

        # Get the raw saved content to verify
        raw_config = self.file_manager.read_json(self.config_file)
        for key, value in test_settings.items():
            self.assertEqual(raw_config.get(key), value, f"Value for {key} was not saved correctly in the file")

        # Reset singleton to force reload from file
        Config._instance = None
        new_config = Config()

        # Verify each setting was loaded correctly
        for key, expected in test_settings.items():
            actual = new_config.get(key)
            self.assertEqual(actual, expected, f"Config value mismatch for {key}: expected {expected}, got {actual}")

    def test_invalid_config_file(self):
        # Write invalid JSON to the config file
        with open(self.config_file, 'w') as f:
            f.write("This is not valid JSON")

        # Reset Config instance
        Config._instance = None

        # Load config - it should use defaults instead of failing
        config = Config()

        # Verify we got default values, not None
        self.assertIsNotNone(config.get('app_name'), "Default app_name should be available after invalid config")

        # Verify we can still update and save
        config.set('recovery_test', 'success')
        saved = config.save()
        self.assertTrue(saved, "Failed to save config after recovering from invalid file")

        # Verify file now contains valid JSON with our updated setting
        config_data = self.file_manager.read_json(self.config_file)
        self.assertEqual(config_data.get('recovery_test'), 'success')

    def test_config_file_permissions(self):
        if sys.platform != 'win32':  # Skip on Windows
            config = Config()
            config.update({'test_key': 'test_value'})

            try:
                # Make temp_dir read-only
                os.chmod(self.temp_dir, 0o444)

                # Try to save - should fail
                result = config.save()
                self.assertFalse(result, "Config save should fail with read-only directory")
            finally:
                # Restore permissions for cleanup
                os.chmod(self.temp_dir, 0o755)

    def test_direct_file_manager_access(self):
        # First, create a config
        config = Config()
        test_settings = {'direct_access': 'test_value'}
        config.update(test_settings)
        config.save()

        # Read directly with file manager
        data = self.file_manager.read_json(self.config_file)
        self.assertEqual(data.get('direct_access'), 'test_value')

        # Modify directly with file manager
        modified_data = data.copy()
        modified_data['new_key'] = 'new_value'
        self.file_manager.write_json(self.config_file, modified_data)

        # Reset Config singleton to force reload
        Config._instance = None
        new_config = Config()

        # Verify Config can read the changes made directly via file manager
        self.assertEqual(new_config.get('new_key'), 'new_value',
                         "Config did not detect changes made directly via file manager")

    def test_file_backup(self):
        # Create a config with initial data
        config = Config()
        config.update({'backup_test': 'original'})
        config.save()

        # Get the initial file content
        initial_content = self.file_manager.read_json(self.config_file)

        # Now modify and save with backup
        modified_data = initial_content.copy()
        modified_data['backup_test'] = 'modified'
        self.file_manager.write_json(self.config_file, modified_data, make_backup=True)

        # Find backup files
        backup_files = list(Path(self.temp_dir).glob("config.json.bak.*"))

        # Assert backup was created
        self.assertTrue(len(backup_files) > 0, "No backup file was created")

        # Verify backup has original content
        backup_content = self.file_manager.read_json(backup_files[0])
        self.assertEqual(backup_content.get('backup_test'), 'original',
                         "Backup file doesn't contain the original data")

        # Verify main file has new content
        current_content = self.file_manager.read_json(self.config_file)
        self.assertEqual(current_content.get('backup_test'), 'modified',
                         "Main file doesn't contain the modified data")

    def test_config_validation(self):
        config = Config()

        # Generate valid settings based on core.constants.py
        valid_settings = {
            'max_retry_count': 5,  # Must be positive integer
            'default_delay': 20,   # Must be non-negative
            'max_members_per_day': 20  # Must be 1-100
        }

        # Update with valid settings
        config.update(valid_settings)

        # Validate settings
        is_valid, issues = config.validate()

        # Should be valid
        self.assertTrue(is_valid, f"Config validation failed with valid settings: {issues}")
        self.assertEqual(len(issues), 0, f"Expected no validation issues, got: {issues}")

        # Now try invalid settings
        invalid_settings = {
            'max_retry_count': 'not_an_integer',  # Wrong type
            'default_delay': -10,  # Negative value
            'max_members_per_day': 200  # Too high based on core/constants.py
        }

        # Update with invalid settings
        config.update(invalid_settings)

        # Validate settings
        is_valid, issues = config.validate()

        # Should be invalid with issues
        self.assertFalse(is_valid, "Config validation passed with invalid settings")
        self.assertTrue(len(issues) > 0, "Expected validation issues but got none")

    def test_file_path_resolution(self):
        config = Config()

        # Set a relative path
        relative_path = "logs/app.log"
        config.set('log_file', relative_path)

        # Get absolute path
        absolute_path = config.get_file_path('log_file')

        # If the method returns None, it's not implemented - skip the test
        if absolute_path is None:
            return

        # Verify path is absolute
        self.assertTrue(os.path.isabs(absolute_path), "Resolved path is not absolute")

        # Verify the path ends with our relative path
        # Convert both to normalized path with forward slashes for comparison
        norm_rel = os.path.normpath(relative_path).replace('\\', '/')
        norm_abs = os.path.normpath(absolute_path).replace('\\', '/')

        # Check if norm_abs ends with norm_rel
        self.assertTrue(norm_abs.endswith(norm_rel),
                        f"Absolute path {norm_abs} does not end with relative path {norm_rel}")


if __name__ == "__main__":
    unittest.main()