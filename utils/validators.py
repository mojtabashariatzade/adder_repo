"""
Input Validation Module

This module provides validation functions for checking the integrity and correctness
of user inputs and data throughout the Telegram Account Manager application.

Features:
- Telegram-specific validations (API IDs, phone numbers, usernames)
- Configuration validation
- File and path validation
- Network and connectivity validation
- Generic data type validation

Usage:
    from utils.validators import validate_phone, validate_api_credentials

    # Validate a phone number
    result, error = validate_phone("+1234567890")

    # Validate API credentials
    result, error = validate_api_credentials(api_id, api_hash)
"""

import os
import re
import json
import ipaddress
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Set, Callable, TypeVar, Generic

# Import helper utilities
try:
    from utils.helpers import (
        normalize_phone, is_valid_api_id, is_valid_api_hash,
        is_valid_phone_number, is_valid_hostname, is_valid_ip
    )
except ImportError:
    # Define minimal versions for development/testing
    def normalize_phone(phone):
        digits = re.sub(r'[^\d+]', '', phone)
        if not digits.startswith('+'): digits = '+' + digits
        return digits

    def is_valid_api_id(api_id):
        try: return int(api_id) > 0 and len(str(int(api_id))) <= 10
        except (ValueError, TypeError): return False

    def is_valid_api_hash(api_hash):
        return isinstance(api_hash, str) and bool(re.match(r'^[0-9a-fA-F]{32}$', api_hash))

    def is_valid_phone_number(phone):
        try: return bool(re.match(r'^\+\d{7,15}$', normalize_phone(phone)))
        except ValueError: return False

    def is_valid_hostname(hostname):
        if not hostname or len(hostname) > 255: return False
        allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in hostname.split("."))

    def is_valid_ip(ip):
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

# Import core exceptions
try:
    from core.exceptions import ValidationError
except ImportError:
    # Define a minimal version for development/testing
    class ValidationError(Exception):
        def __init__(self, field=None, message=None):
            self.field = field
            self.message = message
            error_message = f"Validation failed for field '{field}': {message}" if field else message or "Validation failed"
            super().__init__(error_message)


# Type for validation results
ValidationResult = Tuple[bool, Optional[str]]

# Generic validation function
def validate(value: Any, validators: List[Callable[[Any], ValidationResult]]) -> ValidationResult:
    """
    Run a series of validators on a value.

    Args:
        value (Any): Value to validate
        validators (List[Callable[[Any], ValidationResult]]): List of validator functions

    Returns:
        ValidationResult: Result of the first failed validation, or (True, None) if all pass
    """
    for validator in validators:
        success, error = validator(value)
        if not success:
            return False, error

    return True, None

# Telegram-specific validations
def validate_phone(phone: str) -> ValidationResult:
    """
    Validate a phone number for Telegram.

    Args:
        phone (str): Phone number to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    if not phone:
        return False, "Phone number cannot be empty"

    try:
        if not is_valid_phone_number(phone):
            return False, "Invalid phone number format"

        # Phone number is valid
        return True, None
    except Exception as e:
        return False, f"Error validating phone number: {e}"

def validate_api_id(api_id: Any) -> ValidationResult:
    """
    Validate a Telegram API ID.

    Args:
        api_id (Any): API ID to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    if not api_id:
        return False, "API ID cannot be empty"

    try:
        # Try to convert to int if it's a string
        if isinstance(api_id, str):
            try:
                api_id = int(api_id)
            except ValueError:
                return False, "API ID must be a number"

        if not is_valid_api_id(api_id):
            return False, "Invalid API ID format"

        # API ID is valid
        return True, None
    except Exception as e:
        return False, f"Error validating API ID: {e}"

def validate_api_hash(api_hash: str) -> ValidationResult:
    """
    Validate a Telegram API hash.

    Args:
        api_hash (str): API hash to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    if not api_hash:
        return False, "API hash cannot be empty"

    try:
        if not is_valid_api_hash(api_hash):
            return False, "Invalid API hash format (must be a 32-character hexadecimal string)"

        # API hash is valid
        return True, None
    except Exception as e:
        return False, f"Error validating API hash: {e}"

def validate_api_credentials(api_id: Any, api_hash: str) -> ValidationResult:
    """
    Validate Telegram API credentials.

    Args:
        api_id (Any): API ID to validate
        api_hash (str): API hash to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    # Validate API ID
    valid_id, id_error = validate_api_id(api_id)
    if not valid_id:
        return False, id_error

    # Validate API hash
    valid_hash, hash_error = validate_api_hash(api_hash)
    if not valid_hash:
        return False, hash_error

    # Both are valid
    return True, None

def validate_username(username: str) -> ValidationResult:
    """
    Validate a Telegram username.

    Args:
        username (str): Username to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    if not username:
        return False, "Username cannot be empty"

    # Remove @ prefix if present
    username = username[1:] if username.startswith('@') else username

    # Telegram username requirements:
    # 5-32 characters, alphanumeric with underscores, must start with a letter
    if len(username) < 5:
        return False, "Username must be at least 5 characters"

    if len(username) > 32:
        return False, "Username cannot exceed 32 characters"

    if not re.match(r'^[a-zA-Z][\w]*$', username):
        return False, "Username must start with a letter and contain only letters, numbers, and underscores"

    # Username is valid
    return True, None

def validate_group_username(group_username: str) -> ValidationResult:
    """
    Validate a Telegram group username.

    Args:
        group_username (str): Group username to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    return validate_username(group_username)  # Same rules apply

def validate_session_string(session_string: str) -> ValidationResult:
    """
    Validate a Telethon session string.

    Args:
        session_string (str): Session string to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    if not session_string:
        return False, "Session string cannot be empty"

    # Basic format check for session strings
    if len(session_string) < 10:
        return False, "Session string is too short"

    # Check if it's a valid base64 string
    try:
        # Session strings in Telethon are base64-encoded
        import base64
        base64.b64decode(session_string)
        return True, None
    except Exception:
        return False, "Invalid session string format"

# Configuration validations
def validate_delay(delay: Any, min_delay: int = 0, max_delay: int = 3600) -> ValidationResult:
    """
    Validate a delay value.

    Args:
        delay (Any): Delay value to validate
        min_delay (int): Minimum allowed delay
        max_delay (int): Maximum allowed delay

    Returns:
        ValidationResult: (success, error_message)
    """
    try:
        # Convert to int/float if it's a string
        if isinstance(delay, str):
            try:
                delay = float(delay)
            except ValueError:
                return False, "Delay must be a number"

        # Check if it's a number
        if not isinstance(delay, (int, float)):
            return False, "Delay must be a number"

        # Check range
        if delay < min_delay:
            return False, f"Delay cannot be less than {min_delay} seconds"

        if delay > max_delay:
            return False, f"Delay cannot exceed {max_delay} seconds"

        # Delay is valid
        return True, None
    except Exception as e:
        return False, f"Error validating delay: {e}"

def validate_limit(limit: Any, min_limit: int = 1, max_limit: int = 1000) -> ValidationResult:
    """
    Validate a limit value.

    Args:
        limit (Any): Limit value to validate
        min_limit (int): Minimum allowed limit
        max_limit (int): Maximum allowed limit

    Returns:
        ValidationResult: (success, error_message)
    """
    try:
        # Convert to int if it's a string
        if isinstance(limit, str):
            try:
                limit = int(limit)
            except ValueError:
                return False, "Limit must be an integer"

        # Check if it's an integer
        if not isinstance(limit, int):
            return False, "Limit must be an integer"

        # Check range
        if limit < min_limit:
            return False, f"Limit cannot be less than {min_limit}"

        if limit > max_limit:
            return False, f"Limit cannot exceed {max_limit}"

        # Limit is valid
        return True, None
    except Exception as e:
        return False, f"Error validating limit: {e}"

def validate_config_value(key: str, value: Any, config_schema: Dict[str, Dict[str, Any]]) -> ValidationResult:
    """
    Validate a configuration value against a schema with type and constraint information.

    Args:
        key (str): Configuration key
        value (Any): Configuration value
        config_schema (Dict[str, Dict[str, Any]]): Configuration schema with type and constraint information

    Returns:
        ValidationResult: (success, error_message)
    """
    if key not in config_schema:
        return True, None  # No schema for this key, assume valid

    schema = config_schema[key]

    # Check type
    expected_type = schema.get('type')
    if expected_type:
        if expected_type == 'integer':
            if not isinstance(value, int):
                return False, f"{key} must be an integer"
        elif expected_type == 'number':
            if not isinstance(value, (int, float)):
                return False, f"{key} must be a number"
        elif expected_type == 'string':
            if not isinstance(value, str):
                return False, f"{key} must be a string"
        elif expected_type == 'boolean':
            if not isinstance(value, bool):
                return False, f"{key} must be a boolean"
        elif expected_type == 'array':
            if not isinstance(value, list):
                return False, f"{key} must be an array"
        elif expected_type == 'object':
            if not isinstance(value, dict):
                return False, f"{key} must be an object"

    # Check minimum/maximum for numbers
    if isinstance(value, (int, float)):
        if 'minimum' in schema and value < schema['minimum']:
            return False, f"{key} cannot be less than {schema['minimum']}"
        if 'maximum' in schema and value > schema['maximum']:
            return False, f"{key} cannot exceed {schema['maximum']}"

    # Check minLength/maxLength for strings
    if isinstance(value, str):
        if 'minLength' in schema and len(value) < schema['minLength']:
            return False, f"{key} must be at least {schema['minLength']} characters"
        if 'maxLength' in schema and len(value) > schema['maxLength']:
            return False, f"{key} cannot exceed {schema['maxLength']} characters"

    # Check enum values
    if 'enum' in schema and value not in schema['enum']:
        enum_values = ', '.join(str(v) for v in schema['enum'])
        return False, f"{key} must be one of: {enum_values}"

    # Check pattern for strings
    if isinstance(value, str) and 'pattern' in schema:
        if not re.match(schema['pattern'], value):
            return False, f"{key} does not match the required pattern"

    # Value is valid
    return True, None

# File and path validations
def validate_file_exists(file_path: Union[str, Path]) -> ValidationResult:
    """
    Validate that a file exists.

    Args:
        file_path (Union[str, Path]): Path to the file

    Returns:
        ValidationResult: (success, error_message)
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return False, f"File not found: {file_path}"

        if not path.is_file():
            return False, f"Path is not a file: {file_path}"

        # File exists
        return True, None
    except Exception as e:
        return False, f"Error validating file: {e}"

def validate_directory_exists(dir_path: Union[str, Path]) -> ValidationResult:
    """
    Validate that a directory exists.

    Args:
        dir_path (Union[str, Path]): Path to the directory

    Returns:
        ValidationResult: (success, error_message)
    """
    try:
        path = Path(dir_path)
        if not path.exists():
            return False, f"Directory not found: {dir_path}"

        if not path.is_dir():
            return False, f"Path is not a directory: {dir_path}"

        # Directory exists
        return True, None
    except Exception as e:
        return False, f"Error validating directory: {e}"

def validate_writable_path(path: Union[str, Path]) -> ValidationResult:
    """
    Validate that a path is writable.

    Args:
        path (Union[str, Path]): Path to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    try:
        path_obj = Path(path)

        # Check if the path itself exists and is writable
        if path_obj.exists():
            if not os.access(path_obj, os.W_OK):
                return False, f"Path is not writable: {path}"

            # Path is writable
            return True, None

        # If the path doesn't exist, check if its parent directory is writable
        parent = path_obj.parent
        if not parent.exists():
            return False, f"Parent directory does not exist: {parent}"

        if not os.access(parent, os.W_OK):
            return False, f"Parent directory is not writable: {parent}"

        # Parent directory is writable
        return True, None
    except Exception as e:
        return False, f"Error validating writable path: {e}"

def validate_file_extension(file_path: Union[str, Path], allowed_extensions: List[str]) -> ValidationResult:
    """
    Validate that a file has an allowed extension.

    Args:
        file_path (Union[str, Path]): Path to the file
        allowed_extensions (List[str]): List of allowed extensions (e.g., ['.txt', '.json'])

    Returns:
        ValidationResult: (success, error_message)
    """
    try:
        path = Path(file_path)
        extension = path.suffix.lower()

        if not extension:
            return False, "File has no extension"

        normalized_extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in allowed_extensions]

        if extension not in normalized_extensions:
            ext_list = ', '.join(normalized_extensions)
            return False, f"File must have one of these extensions: {ext_list}"

        # Extension is valid
        return True, None
    except Exception as e:
        return False, f"Error validating file extension: {e}"

# Network validations
def validate_proxy_settings(proxy_settings: Dict[str, Any]) -> ValidationResult:
    """
    Validate proxy settings.

    Args:
        proxy_settings (Dict[str, Any]): Proxy settings to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    if not isinstance(proxy_settings, dict):
        return False, "Proxy settings must be a dictionary"

    # Check required fields
    required_fields = ['addr', 'port', 'proxy_type']
    for field in required_fields:
        if field not in proxy_settings:
            return False, f"Missing required proxy field: {field}"

    # Validate address
    addr = proxy_settings['addr']
    if not addr:
        return False, "Proxy address cannot be empty"

    if not (is_valid_ip(addr) or is_valid_hostname(addr)):
        return False, "Proxy address must be a valid IP or hostname"

    # Validate port
    port = proxy_settings['port']
    try:
        port_int = int(port)
        if port_int < 1 or port_int > 65535:
            return False, "Proxy port must be between 1 and 65535"
    except (ValueError, TypeError):
        return False, "Proxy port must be an integer"

    # Validate proxy type
    proxy_type = proxy_settings['proxy_type']
    valid_types = ['socks4', 'socks5', 'http', 'https']
    if proxy_type not in valid_types:
        return False, f"Proxy type must be one of: {', '.join(valid_types)}"

    # Proxy settings are valid
    return True, None

def validate_url(url: str) -> ValidationResult:
    """
    Validate a URL.

    Args:
        url (str): URL to validate

    Returns:
        ValidationResult: (success, error_message)
    """
    if not url:
        return False, "URL cannot be empty"

    # Basic URL pattern
    pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
    if not re.match(pattern, url):
        return False, "Invalid URL format"

    # URL is valid
    return True, None

# Input sanitation and validation
def sanitize_input(input_str: str, allow_html: bool = False) -> str:
    """
    Sanitize input to prevent injection attacks.

    Args:
        input_str (str): Input string to sanitize
        allow_html (bool): Whether to allow HTML tags

    Returns:
        str: Sanitized input
    """
    if not input_str:
        return ''

    if not allow_html:
        # Replace < and > to prevent HTML injection
        input_str = input_str.replace('<', '&lt;').replace('>', '&gt;')

    # Remove or escape other potentially dangerous characters
    # This is a basic implementation - for production, consider using a library like bleach
    return input_str

def validate_and_sanitize_input(input_str: str, validators: List[Callable[[str], ValidationResult]],
                               allow_html: bool = False) -> Tuple[bool, Optional[str], str]:
    """
    Validate and sanitize input.

    Args:
        input_str (str): Input string to validate and sanitize
        validators (List[Callable[[str], ValidationResult]]): List of validator functions
        allow_html (bool): Whether to allow HTML tags

    Returns:
        Tuple[bool, Optional[str], str]: (success, error_message, sanitized_input)
    """
    # Validate input
    for validator in validators:
        success, error = validator(input_str)
        if not success:
            return False, error, input_str

    # Sanitize input
    sanitized = sanitize_input(input_str, allow_html)

    return True, None, sanitized

# Utility functions for validation
def raise_if_invalid(value: Any, validator: Callable[[Any], ValidationResult], field: str = None) -> None:
    """
    Validate a value and raise ValidationError if invalid.

    Args:
        value (Any): Value to validate
        validator (Callable[[Any], ValidationResult]): Validator function
        field (str, optional): Field name for the error message

    Raises:
        ValidationError: If validation fails
    """
    success, error = validator(value)
    if not success:
        raise ValidationError(field, error)

def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> ValidationResult:
    """
    Validate that all required fields are present in the data.

    Args:
        data (Dict[str, Any]): Data to validate
        required_fields (List[str]): List of required field names

    Returns:
        ValidationResult: (success, error_message)
    """
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]

    if missing_fields:
        missing_list = ', '.join(missing_fields)
        return False, f"Missing required fields: {missing_list}"

    return True, None

# System and environment validations
def validate_environment() -> ValidationResult:
    """
    Validate that the environment has all necessary dependencies and permissions.

    Checks for required Python modules, system permissions, and other
    environment requirements.

    Returns:
        ValidationResult: (success, error_message)
    """
    # Check Python version
    import sys
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
        return False, f"Python 3.7 or higher is required. Current version: {python_version.major}.{python_version.minor}"

    # Check for required modules
    required_modules = [
        ('telethon', 'Telethon'),
        ('cryptography', 'cryptography'),
        ('colorama', 'Colorama')
    ]

    missing_modules = []
    for module_name, display_name in required_modules:
        try:
            __import__(module_name)
        except ImportError:
            missing_modules.append(display_name)

    if missing_modules:
        modules_list = ', '.join(missing_modules)
        return False, f"Missing required Python modules: {modules_list}. Please install them using pip."

    # Check for write permissions in current directory
    try:
        test_file = "write_permission_test.tmp"
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except (IOError, OSError, PermissionError):
        return False, "Application does not have write permission in the current directory"

    # All checks passed
    return True, None