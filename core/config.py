"""
Configuration Module

This module provides a central configuration system for the Telegram Account Manager.
It handles loading and saving configuration settings to/from files and provides defaults
for first-time setup. The class follows the Singleton pattern to ensure only one
configuration instance exists across the application.

Features:
- Configuration loading and saving in JSON format
- Default configuration values for first-time setup
- Validation of configuration values
- Verification of encryption files
- Detailed logging of configuration changes
- Dynamic configuration updates
- Extended proxy configuration support

Usage:
    from core.config import Config

    # Get the configuration instance
    config = Config()

    # Access a configuration value
    api_id = config.get('api_id')

    # Set a configuration value
    config.set('api_id', 12345)

    # Validate configuration
    is_valid, issues = config.validate()

    # Save configuration to file
    config.save()

    # Load configuration from file
    config.load()
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime
import threading

# Assuming constants.py is already implemented
from core.constants import CONFIG_FILE, SALT_FILE, ENCRYPTION_KEY_FILE

# Logger will be set up properly when logging module is implemented
logger = logging.getLogger(__name__)


class Config:
    """
    Singleton configuration class for managing application settings.

    This class handles loading configuration from files, saving to files,
    and providing access to configuration values throughout the application.
    """
    _instance = None
    _lock = threading.RLock()
    _initialized = False

    def __new__(cls):
        """
        Create a new Config instance if one doesn't exist (Singleton pattern).

        Returns:
            Config: The singleton Config instance
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the Config object if not already initialized."""
        with Config._lock:
            if Config._initialized:
                return

            self._config_data = {}
            self._config_file = CONFIG_FILE
            self._salt_file = SALT_FILE
            self._encryption_key_file = ENCRYPTION_KEY_FILE
            self._set_defaults()

            Config._initialized = True

            # Try to load existing config
            try:
                self.load()
            except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
                logger.warning(
                    "Could not load configuration: %s. Using defaults.", e)

    def _set_defaults(self):
        """Set default configuration values for first-time setup."""
        self._config_data = {
            # Application settings
            'app_name': 'Telegram Account Manager',
            'app_version': '1.0.0',
            'debug_mode': False,
            'last_config_update': datetime.now().isoformat(),

            # Delay settings
            'default_delay': 20,  # Default delay between requests in seconds
            'max_delay': 300,     # Maximum delay between requests in seconds

            # Limits
            'max_retry_count': 5,             # Maximum number of retry attempts
            'max_memory_records': 1000,       # Maximum number of records to keep in memory
            # Delay between switching accounts (seconds)
            'account_change_delay': 60,
            # Number of consecutive failures before considering account blocked
            'max_failures_before_block': 3,
            # Maximum number of members to extract or add per account per day
            'max_members_per_day': 20,

            # File paths
            'log_file': 'telegram_adder.log',
            'request_log_file': 'request_log.json',
            'ai_data_file': 'ai_training_data.json',
            'accounts_file': 'telegram_accounts.json',

            # Proxy settings (extended)
            'use_proxy': False,
            'default_proxy_type': 'socks5',
            'proxy_settings': {
                'default': {
                    'proxy_type': 'socks5',
                    'addr': '',
                    'port': 1080,
                    'username': '',
                    'password': '',
                    'rdns': True
                }
            },
            'proxy_rotation_enabled': False,
            'proxy_rotation_interval': 3600,  # 1 hour in seconds

            # Session settings
            'session_prefix': 'tg_session',

            # Security settings
            'encryption_enabled': True,
            'encryption_algorithm': 'fernet',
            'encryption_required_for_sensitive_data': True,
        }

    def _set_defaults(self):
        """Set default configuration values for first-time setup."""
        self._config_data = {
            # Application settings
            'app_name': 'Telegram Account Manager',
            'app_version': '1.0.0',
            'debug_mode': False,
            'last_config_update': datetime.now().isoformat(),

            # Delay settings
            'default_delay': 20,  # Default delay between requests in seconds
            'max_delay': 300,     # Maximum delay between requests in seconds

            # Limits
            'max_retry_count': 5,             # Maximum number of retry attempts
            'max_memory_records': 1000,       # Maximum number of records to keep in memory
            # Delay between switching accounts (seconds)
            'account_change_delay': 60,
            # Number of consecutive failures before considering account blocked
            'max_failures_before_block': 3,
            # Maximum number of members to extract or add per account per day
            'max_members_per_day': 20,

            # File paths
            'log_file': 'telegram_adder.log',
            'request_log_file': 'request_log.json',
            'ai_data_file': 'ai_training_data.json',
            'accounts_file': 'telegram_accounts.json',

            # Proxy settings (extended)
            'use_proxy': False,
            'default_proxy_type': 'socks5',
            'proxy_settings': {
                'default': {
                    'proxy_type': 'socks5',
                    'addr': '',
                    'port': 1080,
                    'username': '',
                    'password': '',
                    'rdns': True
                }
            },
            'proxy_rotation_enabled': False,
            'proxy_rotation_interval': 3600,  # 1 hour in seconds

            # Session settings
            'session_prefix': 'tg_session',

            # Security settings
            'encryption_enabled': True,
            'encryption_algorithm': 'fernet',
            'encryption_required_for_sensitive_data': True,
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Args:
            key: The configuration key to retrieve
            default: Default value to return if key doesn't exist

        Returns:
            The configuration value or default if key doesn't exist
        """
        return self._config_data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: The configuration key to set
            value: The value to set for the key
        """
        previous_value = self._config_data.get(key, None)
        self._config_data[key] = value
        self._config_data['last_config_update'] = datetime.now().isoformat()

        # Log the configuration change with previous and new values
        logger.debug(
            "Configuration updated: %s = %s (previous: %s), timestamp: %s",
            key, value, previous_value, self._config_data['last_config_update']
        )

    def update(self, config_dict: Dict[str, Any]) -> None:
        """
        Update multiple configuration values at once.

        Args:
            config_dict: Dictionary containing configuration key-value pairs
        """
        # Create a log of changed values
        changes = {}
        for key, new_value in config_dict.items():
            if key in self._config_data:
                old_value = self._config_data[key]
                changes[key] = {"old": old_value, "new": new_value}

        # Update the configuration
        self._config_data.update(config_dict)
        self._config_data['last_config_update'] = datetime.now().isoformat()

        # Log detailed changes
        logger.debug(
            "Configuration updated with multiple values: %s, timestamp: %s",
            list(config_dict.keys()), self._config_data['last_config_update']
        )

        # Log individual changes at trace level (if logger supports it)
        for key, change in changes.items():
            logger.debug(
                "Configuration change: %s from %s to %s",
                key, change['old'], change['new']
            )

    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            Dict containing all configuration key-value pairs
        """
        return self._config_data.copy()

    def reset_defaults(self) -> None:
        """Reset all configuration values to their defaults."""
        self._set_defaults()
        logger.info("Configuration reset to defaults")

    def load(self, config_file: Optional[str] = None) -> bool:
        """
        Load configuration from a file.

        Args:
            config_file: Path to the configuration file. If None, uses the default path.

        Returns:
            True if configuration was loaded successfully, False otherwise
        """
        file_path = config_file or self._config_file

        if not os.path.exists(file_path):
            logger.info(
                "Configuration file %s not found. Using defaults.",
                file_path
            )
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                loaded_config = json.load(file)
                self.update(loaded_config)
                logger.info("Configuration loaded from %s", file_path)
                return True
        except json.JSONDecodeError:
            logger.error("Error decoding JSON from %s", file_path)
            return False
        except IOError as e:
            logger.error("Error loading configuration from %s: %s",
                         file_path, str(e))
            return False

    def save(self, config_file: Optional[str] = None) -> bool:
        """
        Save configuration to a file.

        Args:
            config_file: Path to save the configuration to. If None, uses the default path.

        Returns:
            True if configuration was saved successfully, False otherwise
        """
        file_path = config_file or self._config_file

        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(
                os.path.abspath(file_path)), exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(self._config_data, file, indent=4)
            logger.info("Configuration saved to %s", file_path)
            return True
        except IOError as e:
            logger.error("Error saving configuration to %s: %s",
                         file_path, str(e))
            return False

    def get_file_path(self, key: str) -> Optional[str]:
        """
        Get an absolute file path for a file path configuration value.

        Args:
            key: The configuration key for a file path

        Returns:
            Absolute path to the file, or None if the key doesn't exist or isn't a string
        """
        value = self.get(key)
        if not value or not isinstance(value, str):
            return None

        # If path is already absolute, return it
        if os.path.isabs(value):
            return value

        # Otherwise, make it relative to the application directory
        # This assumes the application is run from the project root
        return os.path.abspath(value)

    def set_config_file(self, config_file: str) -> None:
        """
        Set the path to the configuration file.

        Args:
            config_file: Path to the configuration file
        """
        self._config_file = config_file

    def set_encryption_key_file(self, encryption_key_file: str) -> None:
        """
        Set the path to the encryption key file.

        Args:
            encryption_key_file: Path to the encryption key file
        """
        self._encryption_key_file = encryption_key_file

    def set_salt_file(self, salt_file: str) -> None:
        """
        Set the path to the salt file.

        Args:
            salt_file: Path to the salt file
        """
        self._salt_file = salt_file

    def get_config_file(self) -> str:
        """
        Get the path to the configuration file.

        Returns:
            Path to the configuration file
        """
        return self._config_file

    def get_encryption_key_file(self) -> str:
        """
        Get the path to the encryption key file.

        Returns:
            Path to the encryption key file
        """
        return self._encryption_key_file

    def get_salt_file(self) -> str:
        """
        Get the path to the salt file.

        Returns:
            Path to the salt file
        """
        return self._salt_file

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the current configuration.

        Checks for required settings, valid data types, and valid value ranges.

        Returns:
            Tuple containing:
                - Boolean indicating if configuration is valid
                - List of validation issues (empty if valid)
        """
        issues = []

        # Check required settings
        required_settings = [
            'app_name', 'app_version', 'default_delay', 'max_delay',
            'max_retry_count', 'max_members_per_day', 'accounts_file'
        ]

        for setting in required_settings:
            if setting not in self._config_data:
                issues.append(f"Missing required setting: {setting}")

        # Check data types
        type_checks = {
            'app_name': str,
            'app_version': str,
            'debug_mode': bool,
            'default_delay': (int, float),
            'max_delay': (int, float),
            'max_retry_count': int,
            'max_members_per_day': int,
            'use_proxy': bool,
        }

        for setting, expected_type in type_checks.items():
            if setting in self._config_data:
                value = self._config_data[setting]
                # Handle case for multiple allowed types (tuple of types)
                if isinstance(expected_type, tuple):
                    if not any(isinstance(value, t) for t in expected_type):
                        issues.append(
                            (
                                f"Invalid type for {setting}: "
                                f"expected one of {expected_type}, "
                                f"got {type(value)}"
                            )
                        )
                elif not isinstance(value, expected_type):
                    issues.append(
                        (
                            f"Invalid type for {setting}: "
                            f"expected {expected_type.__name__}, "
                            f"got {type(value).__name__}"
                        )
                    )

        # Check value ranges
        if 'default_delay' in self._config_data and (
           self._config_data['default_delay'] < 0 or self._config_data['default_delay'] > 3600):
            issues.append("default_delay must be between 0 and 3600 seconds")

        if 'max_delay' in self._config_data and (
           self._config_data['max_delay'] < 0 or self._config_data['max_delay'] > 86400):
            issues.append(
                "max_delay must be between 0 and 86400 seconds (24 hours)")

        if 'max_members_per_day' in self._config_data and (
            self._config_data['max_members_per_day'] < 1 or
            self._config_data['max_members_per_day'] > 100
        ):
            issues.append("max_members_per_day must be between 1 and 100")

        # Verify encryption files if encryption is enabled
        if self.get('encryption_enabled', True):
            if not self._verify_encryption_files():
                issues.append(
                    "Encryption is enabled but required files are missing or invalid")

        # Check proxy configuration if enabled
        if self.get('use_proxy', False):
            proxy_settings = self.get('proxy_settings', {}).get('default', {})
            if not proxy_settings.get('addr'):
                issues.append(
                    "Proxy is enabled but no proxy address is configured")
            if not isinstance(proxy_settings.get('port'), int):
                issues.append("Proxy port must be an integer")

        # Return validation result
        is_valid = len(issues) == 0
        return is_valid, issues

    def _verify_encryption_files(self) -> bool:
        """
        Verify that encryption-related files exist and are valid.

        Returns:
            True if all required encryption files exist and are valid, False otherwise
        """
        # Check if encryption key file exists
        if self.get('encryption_required_for_sensitive_data', True):
            if not os.path.exists(self._encryption_key_file):
                logger.warning(
                    "Encryption key file %s not found",
                    self._encryption_key_file
                )
                return False

            # Read the file to check if it's a valid encryption key
            try:
                with open(self._encryption_key_file, 'rb') as f:
                    key_data = f.read()
                    # Common lengths for Fernet keys
                    if len(key_data) != 32 and len(key_data) != 44:
                        logger.warning(
                            "Encryption key in %s has invalid length", self._encryption_key_file)
                        return False
            except IOError as e:
                logger.error("Failed to read encryption key file: %s", str(e))
                return False

            # Check if salt file exists (if used)
            if os.path.exists(self._salt_file):
                try:
                    with open(self._salt_file, 'rb') as f:
                        salt_data = f.read()
                        if len(salt_data) < 8:  # Salt should be at least 8 bytes
                            logger.warning(
                                "Salt in %s is too short", self._salt_file)
                            return False
                except IOError as e:
                    logger.error("Failed to read salt file: %s", str(e))
                    return False

        return True

    def set_proxy_config(self, proxy_name: str, proxy_config: Dict[str, Any]) -> None:
        """
        Configure a proxy for the application.

        Args:
            proxy_name: Name/identifier for this proxy configuration
            proxy_config: Dictionary with proxy configuration:
                - proxy_type: Type of proxy (socks5, http, etc.)
                - addr: Proxy server address
                - port: Proxy server port
                - username: Username for authentication (optional)
                - password: Password for authentication (optional)
                - rdns: Whether to use remote DNS resolution (optional)
        """
        # Create proxy_settings dict if it doesn't exist
        if 'proxy_settings' not in self._config_data:
            self._config_data['proxy_settings'] = {}

        # Add or update this proxy configuration
        self._config_data['proxy_settings'][proxy_name] = proxy_config

        # Enable proxies when a proxy is configured
        self._config_data['use_proxy'] = True

        # Update last config change timestamp
        self._config_data['last_config_update'] = datetime.now().isoformat()

        logger.info("Proxy '%s' configured: %s:%d", proxy_name,
                    proxy_config['addr'], proxy_config['port'])

    def remove_proxy_config(self, proxy_name: str) -> bool:
        """
        Remove a proxy configuration.

        Args:
            proxy_name: Name/identifier of the proxy to remove

        Returns:
            True if the proxy was removed, False if it wasn't found
        """
        if 'proxy_settings' not in self._config_data:
            return False

        if proxy_name not in self._config_data['proxy_settings']:
            return False

        # Remove the proxy
        removed_proxy = self._config_data['proxy_settings'].pop(proxy_name)

        # If no proxies remain, disable proxy usage
        # NOTE: We always disable proxy usage when a proxy is removed
        # The user will need to explicitly enable use_proxy again
        self._config_data['use_proxy'] = False

        # Update last config change timestamp
        self._config_data['last_config_update'] = datetime.now().isoformat()

        logger.info("Proxy '%s' removed: %s:%d", proxy_name,
                    removed_proxy['addr'], removed_proxy['port'])
        return True

    def get_proxy_config(self, proxy_name: str = 'default') -> Optional[Dict[str, Any]]:
        """
        Get a proxy configuration.

        Args:
            proxy_name: Name/identifier of the proxy to get (default: 'default')

        Returns:
            Proxy configuration dictionary or None if not found
        """
        if 'proxy_settings' not in self._config_data:
            return None

        return self._config_data['proxy_settings'].get(proxy_name)

    def list_proxies(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all configured proxies.

        Returns:
            Dictionary of proxy configurations
        """
        return self._config_data.get('proxy_settings', {})
