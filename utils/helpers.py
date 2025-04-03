"""
Helper Utilities Module

This module provides various helper functions used throughout the
Telegram Account Manager application.
It contains utility functions for data conversion, text formatting, time calculations, and other
commonly needed operations.

Functions are organized into categories for easier navigation and usage:
- Time and Date utilities
- String formatting utilities
- Data conversion utilities
- Path and File utilities
- Network utilities
- Telegram-specific utilities

Usage:
    from utils.helpers import format_time, format_bytes, ensure_list

    # Format a duration in seconds
    formatted_time = format_time(3665)  # "1h 1m 5s"

    # Format a byte size
    formatted_size = format_bytes(1536000)  # "1.5 MB"

    # Ensure a value is a list
    items = ensure_list("item")  # ["item"]
"""

import os
import re
import hashlib
import platform
import socket
import datetime
import time
import random
import string
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
from pathlib import Path

# Time and Date Utilities


def get_timestamp() -> float:
    """
    Get current Unix timestamp.

    Returns:
        float: Current timestamp
    """
    return time.time()


def get_iso_timestamp() -> str:
    """
    Get current ISO-8601 formatted timestamp.

    Returns:
        str: ISO-8601 formatted timestamp
    """
    return datetime.datetime.now().isoformat()


def format_time(seconds: Union[int, float]) -> str:
    """
    Format a duration in seconds into a human-readable string.

    Args:
        seconds (Union[int, float]): Duration in seconds

    Returns:
        str: Formatted duration string (e.g., "1h 30m 45s")
    """
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


def parse_time_string(time_str: str) -> int:
    """
    Parse a time string (e.g., "1h 30m 45s", "45s", "1h") into seconds.

    Args:
        time_str (str): Time string to parse

    Returns:
        int: Time in seconds

    Raises:
        ValueError: If the time string is invalid
    """
    if not time_str:
        return 0

    pattern = r'(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?'
    match = re.match(pattern, time_str.strip())

    if not match or not any(match.groups()):
        raise ValueError(f"Invalid time string: {time_str}")

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds


def get_time_difference(start: Union[float, datetime.datetime],
                        end: Optional[Union[float, datetime.datetime]] = None) -> float:
    """
    Get time difference between two timestamps or datetime objects.

    Args:
        start (Union[float, datetime.datetime]): Start time
        end (Optional[Union[float, datetime.datetime]]): End time, uses current time if None

    Returns:
        float: Time difference in seconds
    """
    if end is None:
        if isinstance(start, datetime.datetime):
            end = datetime.datetime.now()
        else:
            end = time.time()

    if isinstance(start, datetime.datetime) and isinstance(end, datetime.datetime):
        return (end - start).total_seconds()
    elif isinstance(start, (int, float)) and isinstance(end, (int, float)):
        return end - start
    else:
        raise TypeError(
            "Start and end must be both timestamp floats or both datetime objects")

# String Formatting Utilities


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length, adding a suffix if truncated.

    Args:
        s (str): String to truncate
        max_length (int): Maximum length of the truncated string
        suffix (str): Suffix to add to truncated strings

    Returns:
        str: Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def format_bytes(size: Union[int, float]) -> str:
    """
    Format a byte size into a human-readable string.

    Args:
        size (Union[int, float]): Size in bytes

    Returns:
        str: Formatted size string (e.g., "1.5 MB")
    """
    if size < 0:
        raise ValueError("Size cannot be negative")

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{size} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def normalize_phone(phone: str) -> str:
    """
    Normalize a phone number to standard format.

    Args:
        phone (str): Phone number to normalize

    Returns:
        str: Normalized phone number

    Raises:
        ValueError: If the phone number is invalid
    """
    # Strip all non-digit characters
    digits = re.sub(r'[^\d+]', '', phone)

    # Check if it starts with a plus, if not add one
    if not digits.startswith('+'):
        digits = '+' + digits

    # Validate phone number format
    if not re.match(r'^\+\d{7,15}$', digits):
        raise ValueError(f"Invalid phone number format: {phone}")

    return digits


def mask_sensitive_data(data: str) -> str:
    """
    Mask sensitive data (like API keys, phone numbers, etc).

    Args:
        data (str): Data to mask

    Returns:
        str: Masked data
    """
    if not data:
        return data

    # Detect type of data to apply appropriate masking
    if re.match(r'^[0-9a-fA-F]{32,}$', data):  # API hash or long hex string
        return data[:4] + '*' * (len(data) - 8) + data[-4:]
    elif re.match(r'^\+?\d{7,15}$', data):  # Phone number
        return data[:3] + '*' * (len(data) - 5) + data[-2:]
    else:  # Generic sensitive data
        visible = min(len(data) // 4, 4)  # Show at most 4 chars
        return data[:visible] + '*' * (len(data) - visible * 2) + data[-visible:]


def generate_random_id(length: int = 12) -> str:
    """
    Generate a random ID string.

    Args:
        length (int): Length of the ID

    Returns:
        str: Random ID string
    """
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """
    Return singular or plural form based on count.

    Args:
        count (int): Count value
        singular (str): Singular form
        plural (Optional[str]): Plural form, defaults to singular + 's' if None

    Returns:
        str: Appropriate form based on count
    """
    if not plural:
        plural = singular + 's'

    return singular if count == 1 else plural

# Data Conversion Utilities


def ensure_list(value: Any) -> List[Any]:
    """
    Ensure a value is a list.

    Args:
        value (Any): Value to convert to a list

    Returns:
        List[Any]: List containing the value, or the value if it's already a list
    """
    if value is None:
        return []
    elif isinstance(value, (list, tuple, set)):
        return list(value)
    else:
        return [value]


def safe_cast(value: Any, target_type: type, default: Any = None) -> Any:
    """
    Safely cast a value to a target type.

    Args:
        value (Any): Value to cast
        target_type (type): Target type
        default (Any): Default value to return if casting fails

    Returns:
        Any: Cast value or default
    """
    try:
        return target_type(value)
    except (ValueError, TypeError):
        return default


def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any],
               overwrite: bool = True) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        dict1 (Dict[str, Any]): First dictionary
        dict2 (Dict[str, Any]): Second dictionary
        overwrite (bool): Whether to overwrite values in dict1 with values from dict2

    Returns:
        Dict[str, Any]: Merged dictionary
    """
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value, overwrite)
        elif key not in result or overwrite:
            result[key] = value

    return result


def flatten_dict(d: Dict[str, Any], separator: str = '.', prefix: str = '') -> Dict[str, Any]:
    """
    Flatten a nested dictionary structure.

    Args:
        d (Dict[str, Any]): Dictionary to flatten
        separator (str): Separator character for nested keys
        prefix (str): Prefix for keys

    Returns:
        Dict[str, Any]: Flattened dictionary
    """
    result = {}

    for key, value in d.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key

        if isinstance(value, dict):
            result.update(flatten_dict(value, separator, new_key))
        else:
            result[new_key] = value

    return result

# Path and File Utilities


def is_valid_path(path: str) -> bool:
    """
    Check if a path is valid.

    Args:
        path (str): Path to check

    Returns:
        bool: True if the path is valid, False otherwise
    """
    try:
        Path(path)
        return True
    except (TypeError, ValueError):
        return False


def get_project_root() -> Path:
    """
    Get the project root directory.

    Returns:
        Path: Path to the project root
    """
    # Start from the current file's directory
    current_dir = Path(__file__).parent

    # Go up until we find .env, .git, or other indicators of project root
    max_depth = 5  # Limit search depth
    for _ in range(max_depth):
        if any(
            (current_dir / indicator).exists()
            for indicator in ['.env', '.git', 'setup.py', 'pyproject.toml']
        ):
            return current_dir

        # Move up one directory
        parent = current_dir.parent
        if parent == current_dir:  # Reached filesystem root
            break
        current_dir = parent

    # If root not found, return parent of utils directory as a fallback
    return Path(__file__).parent.parent


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists.

    Args:
        path (Union[str, Path]): Path to the directory

    Returns:
        Path: Path to the directory

    Raises:
        OSError: If the directory cannot be created
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_file_hash(file_path: Union[str, Path], algorithm: str = 'sha256') -> str:
    """
    Calculate the hash of a file.

    Args:
        file_path (Union[str, Path]): Path to the file
        algorithm (str): Hash algorithm to use

    Returns:
        str: Hexadecimal hash of the file

    Raises:
        FileNotFoundError: If the file is not found
        ValueError: If the algorithm is not supported
    """
    try:
        hash_func = getattr(hashlib, algorithm)()
    except AttributeError as exc:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}") from exc

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, 'rb') as f:
        # Read in chunks to handle large files efficiently
        for chunk in iter(lambda: f.read(4096), b''):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def get_file_size_human_readable(file_path: Union[str, Path]) -> str:
    """
    Get the size of a file in human-readable format.

    Args:
        file_path (Union[str, Path]): Path to the file

    Returns:
        str: Human-readable file size

    Raises:
        FileNotFoundError: If the file is not found
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    size = file_path.stat().st_size
    return format_bytes(size)

# Network Utilities


def is_valid_ip(ip: str) -> bool:
    """
    Check if a string is a valid IP address.

    Args:
        ip (str): IP address to check

    Returns:
        bool: True if the IP is valid, False otherwise
    """
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False


def is_valid_hostname(hostname: str) -> bool:
    """
    Check if a string is a valid hostname.

    Args:
        hostname (str): Hostname to check

    Returns:
        bool: True if the hostname is valid, False otherwise
    """
    if not hostname or len(hostname) > 255:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1]
    allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


def get_system_info() -> Dict[str, str]:
    """
    Get system information.

    Returns:
        Dict[str, str]: System information
    """
    return {
        'os': platform.system(),
        'os_version': platform.version(),
        'os_release': platform.release(),
        'architecture': platform.machine(),
        'processor': platform.processor(),
        'hostname': socket.gethostname(),
        'python_version': platform.python_version(),
        'timezone': datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo.tzname(None)
    }


def get_platform_info() -> Dict[str, str]:
    """
    Get platform information.

    Returns:
        Dict[str, str]: Platform information including OS, Python version, and more
    """
    return {
        'system': platform.system(),  # e.g., 'Windows', 'Linux', 'Darwin'
        'release': platform.release(),  # e.g., '10', '18.04'
        'version': platform.version(),  # Detailed version info
        'architecture': platform.machine(),  # e.g., 'x86_64', 'AMD64'
        'processor': platform.processor(),
        'python_version': platform.python_version(),
        'node': platform.node(),  # Hostname
        'platform': platform.platform(),  # Full platform identifier
        'python_implementation': platform.python_implementation(),  # e.g., 'CPython'
    }


def is_internet_available(test_url: str = "8.8.8.8", timeout: float = 3) -> bool:
    """
    Check if internet is available.

    Args:
        test_url (str): URL or IP to ping
        timeout (float): Timeout in seconds

    Returns:
        bool: True if internet is available, False otherwise
    """
    try:
        # Try to connect to Google DNS to check internet connectivity
        socket.create_connection((test_url, 53), timeout=timeout)
        return True
    except (socket.timeout, socket.error):
        return False

# Signal handling utilities


def setup_signal_handlers(shutdown_handler: Callable[[], None] = None) -> None:
    """
    Set up signal handlers for the application.

    This function configures how the application should respond to system signals
    like SIGINT (Ctrl+C) and SIGTERM.

    Args:
        shutdown_handler (Callable[[], None], optional): Function to call when
        shutdown signal received
    """
    import signal
    import sys

    def signal_handler(sig, frame):
        """Signal handler function for graceful shutdown."""
        print("\nShutdown signal received...")

        if shutdown_handler:
            try:
                shutdown_handler()
            except (IOError, FileNotFoundError, ValueError) as e:
                print(f"Error in shutdown handler: {e}")

        print("Shutdown complete. Exiting...")
        sys.exit(0)

    # Register signal handlers
    try:
        signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
        # Handle termination request
        signal.signal(signal.SIGTERM, signal_handler)

        # On Windows, SIGBREAK is sent when Ctrl+Break is pressed
        if platform.system() == 'Windows':
            signal.signal(signal.SIGBREAK, signal_handler)

        # On Unix systems, add more signal handlers
        if platform.system() != 'Windows':
            # Handle terminal closed
            signal.signal(signal.SIGHUP, signal_handler)

    except (AttributeError, ValueError) as e:
        # Some signals might not be available on all platforms
        print(f"Warning: Could not set all signal handlers: {e}")

# Utility functions for terminal/console


def clear_console() -> None:
    """
    Clear the console/terminal screen in a cross-platform way.

    This function detects the operating system and uses the appropriate
    command to clear the console screen.
    """
    # Check which OS we're on
    if platform.system() == 'Windows':
        # For Windows, use 'cls' command
        os.system('cls')
    else:
        # For Unix/Linux/MacOS, use 'clear' command
        os.system('clear')


def get_terminal_size() -> Tuple[int, int]:
    """
    Get the current terminal/console size.

    Returns:
        Tuple[int, int]: Width and height of the terminal in characters (columns, rows)
    """
    try:
        columns, rows = os.get_terminal_size()
        return columns, rows
    except (AttributeError, OSError):
        # Fallback to default values if os.get_terminal_size() is not available
        # or if called in a non-terminal environment
        return 80, 24


# Telegram-specific Utilities
def is_valid_api_id(api_id: Any) -> bool:
    """
    Check if a value is a valid Telegram API ID.

    Args:
        api_id (Any): API ID to check

    Returns:
        bool: True if the API ID is valid, False otherwise
    """
    if not isinstance(api_id, (int, str)):
        return False

    try:
        api_id_int = int(api_id)
        return api_id_int > 0 and len(str(api_id_int)) <= 10
    except (ValueError, TypeError):
        return False


def is_valid_api_hash(api_hash: Any) -> bool:
    """
    Check if a value is a valid Telegram API hash.

    Args:
        api_hash (Any): API hash to check

    Returns:
        bool: True if the API hash is valid, False otherwise
    """
    if not isinstance(api_hash, str):
        return False

    # API hash should be a 32-character hexadecimal string
    return bool(re.match(r'^[0-9a-fA-F]{32}$', api_hash))


def is_valid_phone_number(phone: Any) -> bool:
    """
    Check if a value is a valid phone number for Telegram.

    Args:
        phone (Any): Phone number to check

    Returns:
        bool: True if the phone number is valid, False otherwise
    """
    if not isinstance(phone, str):
        return False

    try:
        normalized = normalize_phone(phone)
        return bool(re.match(r'^\+\d{7,15}$', normalized))
    except ValueError:
        return False


def format_group_name(name: str, max_length: int = 40) -> str:
    """
    Format a group name for display.

    Args:
        name (str): Group name
        max_length (int): Maximum length for display

    Returns:
        str: Formatted group name
    """
    return truncate_string(name, max_length)


def format_username(username: Optional[str]) -> str:
    """
    Format a username for display.

    Args:
        username (Optional[str]): Username

    Returns:
        str: Formatted username
    """
    if not username:
        return "No username"
    return f"@{username}" if not username.startswith('@') else username


def format_user_info(first_name: Optional[str] = None,
                     last_name: Optional[str] = None,
                     username: Optional[str] = None) -> str:
    """
    Format user information for display.

    Args:
        first_name (Optional[str]): First name
        last_name (Optional[str]): Last name
        username (Optional[str]): Username

    Returns:
        str: Formatted user information
    """
    name_parts = []
    if first_name:
        name_parts.append(first_name)
    if last_name:
        name_parts.append(last_name)

    name = " ".join(name_parts) if name_parts else "Unknown"

    if username:
        formatted_username = format_username(username)
        return f"{name} ({formatted_username})"
    return name
