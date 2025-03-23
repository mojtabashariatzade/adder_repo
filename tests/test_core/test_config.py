"""
Tests for the Config module (core/config.py).

This module contains unit tests for the Config class which manages
application configuration.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import sys
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.config import Config


class TestConfig(unittest.TestCase):
    """Test suite for the Config class."""

    def setUp(self):
        """Set up test fixtures, if any."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()

        # Create temporary files for testing
        self.temp_config_file = os.path.join(self.temp_dir.name, 'test_config.json')
        self.temp_key_file = os.path.join(self.temp_dir.name, 'test_key.key')
        self.temp_salt_file = os.path.join(self.temp_dir.name, 'test_salt.salt')

        # Mock the constants
        self.config_file_patcher = patch('core.config.CONFIG_FILE', self.temp_config_file)
        self.encryption_key_file_patcher = patch('core.config.ENCRYPTION_KEY_FILE', self.temp_key_file)
        self.salt_file_patcher = patch('core.config.SALT_FILE', self.temp_salt_file)

        # Start the patchers
        self.config_file_patcher.start()
        self.encryption_key_file_patcher.start()
        self.salt_file_patcher.start()

        # Reset the Config singleton between tests
        Config._instance = None

        # Create a dummy encryption key file
        with open(self.temp_key_file, 'wb') as f:
            f.write(b'A' * 32)  # 32 bytes of dummy key data

        # Create a dummy salt file
        with open(self.temp_salt_file, 'wb') as f:
            f.write(b'B' * 16)  # 16 bytes of dummy salt data

    def tearDown(self):
        """Tear down test fixtures, if any."""
        # Stop the patchers
        self.config_file_patcher.stop()
        self.encryption_key_file_patcher.stop()
        self.salt_file_patcher.stop()

        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_singleton_pattern(self):
        """Test that Config follows the singleton pattern."""
        config1 = Config()
        config2 = Config()
        self.assertIs(config1, config2)

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = Config()

        # Check some default values
        self.assertEqual(config.get('app_name'), 'Telegram Account Manager')
        self.assertEqual(config.get('default_delay'), 20)
        self.assertEqual(config.get('max_members_per_day'), 20)

    def test_get_nonexistent_key(self):
        """Test getting a non-existent key returns the default value."""
        config = Config()
        self.assertIsNone(config.get('nonexistent_key'))
        self.assertEqual(config.get('nonexistent_key', 'default'), 'default')

    def test_set_and_get(self):
        """Test setting and getting values."""
        config = Config()

        # Set a value
        config.set('test_key', 'test_value')

        # Get the value
        self.assertEqual(config.get('test_key'), 'test_value')

    def test_update(self):
        """Test updating multiple values."""
        config = Config()

        # Update multiple values
        update_dict = {
            'app_name': 'New App Name',
            'debug_mode': True,
            'new_key': 'new_value'
        }
        config.update(update_dict)

        # Check values
        self.assertEqual(config.get('app_name'), 'New App Name')
        self.assertTrue(config.get('debug_mode'))
        self.assertEqual(config.get('new_key'), 'new_value')

    def test_save_and_load(self):
        """Test saving and loading configuration to/from file."""
        config = Config()

        # Set some test values
        config.set('app_name', 'Test App')
        config.set('test_key', 'test_value')

        # Save to file
        success = config.save(self.temp_config_file)
        self.assertTrue(success)

        # Verify file exists
        self.assertTrue(os.path.exists(self.temp_config_file))

        # Create a new Config instance (should load defaults)
        Config._instance = None
        config2 = Config()

        # Load from file
        success = config2.load(self.temp_config_file)
        self.assertTrue(success)

        # Verify loaded values
        self.assertEqual(config2.get('app_name'), 'Test App')
        self.assertEqual(config2.get('test_key'), 'test_value')

    def test_reset_defaults(self):
        """Test resetting to default values."""
        config = Config()

        # Change some values
        config.set('app_name', 'Changed App')
        config.set('default_delay', 100)

        # Reset to defaults
        config.reset_defaults()

        # Verify defaults are restored
        self.assertEqual(config.get('app_name'), 'Telegram Account Manager')
        self.assertEqual(config.get('default_delay'), 20)

    def test_validate_valid_config(self):
        """Test validation with valid configuration."""
        config = Config()

        # Validate default configuration
        is_valid, issues = config.validate()

        # Should be valid
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)

    def test_validate_invalid_config(self):
        """Test validation with invalid configuration."""
        config = Config()

        # Set some invalid values
        config.set('default_delay', -10)  # Negative delay
        config.set('max_members_per_day', 200)  # Too high

        # Remove a required setting
        config_data = config.get_all()
        config_data.pop('app_name')
        config._config_data = config_data

        # Validate configuration
        is_valid, issues = config.validate()

        # Should be invalid
        self.assertFalse(is_valid)
        self.assertGreater(len(issues), 0)

        # Check for specific issues
        self.assertTrue(any('default_delay' in issue for issue in issues))
        self.assertTrue(any('max_members_per_day' in issue for issue in issues))
        self.assertTrue(any('app_name' in issue for issue in issues))

    def test_proxy_configuration(self):
        """Test proxy configuration functionality."""
        config = Config()

        # Add a proxy configuration
        proxy_config = {
            'proxy_type': 'socks5',
            'addr': '127.0.0.1',
            'port': 9050,
            'username': 'user',
            'password': 'pass',
            'rdns': True
        }
        config.set_proxy_config('test_proxy', proxy_config)

        # Check if proxy was added
        self.assertTrue(config.get('use_proxy'))
        self.assertEqual(config.get_proxy_config('test_proxy'), proxy_config)

        # List proxies
        proxies = config.list_proxies()
        self.assertIn('test_proxy', proxies)
        self.assertEqual(proxies['test_proxy'], proxy_config)

        # Remove proxy
        success = config.remove_proxy_config('test_proxy')
        self.assertTrue(success)

        # Check if proxy was removed
        self.assertFalse(config.get('use_proxy'))
        self.assertIsNone(config.get_proxy_config('test_proxy'))

    def test_file_path_handling(self):
        """Test handling of file paths."""
        config = Config()

        # Set a relative file path
        config.set('test_file', 'test/path/file.txt')

        # Get absolute path
        abs_path = config.get_file_path('test_file')

        # Should be an absolute path
        self.assertTrue(os.path.isabs(abs_path))

        # Set an absolute file path
        abs_path = os.path.abspath('/tmp/test.txt')
        config.set('test_abs_file', abs_path)

        # Get absolute path
        returned_path = config.get_file_path('test_abs_file')

        # Should be the same absolute path
        self.assertEqual(returned_path, abs_path)

    def test_verify_encryption_files(self):
        """Test verification of encryption files."""
        config = Config()

        # With valid files, should return True
        self.assertTrue(config._verify_encryption_files())

        # Simulate missing encryption key file
        with patch('os.path.exists', return_value=False):
            self.assertFalse(config._verify_encryption_files())

if __name__ == '__main__':
    unittest.main()