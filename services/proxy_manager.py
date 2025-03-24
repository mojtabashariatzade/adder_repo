"""
Proxy Manager Module

This module provides a centralized system for managing and using proxy servers for
Telegram API connections. It handles adding, testing, removing, and rotating proxies to
ensure stable and reliable connections, especially in environments with restrictions.

Features:
- Add, test, remove, and list proxies
- Automatic proxy rotation based on performance or time intervals
- Integration with Telegram clients for seamless proxy usage
- Proxy health checks and reliability metrics
- Proxy categorization by speed, reliability, and region
- Fallback mechanism for handling proxy failures
- Import/export proxy lists from various formats

Usage:
    from services.proxy_manager import ProxyManager, ProxyType, ProxyStatus

    # Using the singleton instance
    proxy_manager = ProxyManager.get_instance()

    # Add a proxy
    proxy_id = proxy_manager.add_proxy(
        proxy_type=ProxyType.SOCKS5,
        host="127.0.0.1",
        port=1080,
        username="user",  # Optional
        password="pass"   # Optional
    )

    # Test a proxy
    success, latency = proxy_manager.test_proxy(proxy_id)

    # Get the best available proxy for a client
    proxy_settings = proxy_manager.get_best_proxy()

    # Apply proxy to a Telegram client
    proxy_manager.apply_proxy_to_client(client, proxy_id)

    # Enable automatic proxy rotation
    proxy_manager.enable_auto_rotation(interval_minutes=60)
"""

import os
import json
import time
import random
import logging
import socket
import threading
import asyncio
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime

# Try to import from project modules
try:
    from core.config import Config
    from core.exceptions import (
        ProxyError, ValidationError
    )
    from data.file_manager import JsonFileManager, FileReadError, FileWriteError
    from logging_.logging_manager import get_logger
except ImportError:
    # For standalone testing, define minimal versions of dependencies
    # pylint: disable=C0115  # Missing class docstring
    class Config:
        _instance = None

        def __new__(cls):
            if cls._instance is None:
                cls._instance = super(Config, cls).__new__(cls)
                cls._instance._config_data = {}
            return cls._instance

# pylint: disable=C0116  # Missing function or method docstring
        def get(self, key, default=None):
            return self._config_data.get(key, default)

        def set(self, key, value):
            self._config_data[key] = value

    class Constants:
        class ProxyDefaults:
            TYPE = "socks5"
            PORT = 1080
            TIMEOUT = 30

    # Define minimal exception classes
    class ProxyError(Exception):
        pass

    class ConnectionErrors(Exception):
        pass

    class TimeoutErrors(Exception):
        pass

    class ValidationError(Exception):
        pass

    class FileReadError(Exception):
        pass

    class FileWriteError(Exception):
        pass

    # Define minimal JsonFileManager
    class JsonFileManager:
        def __init__(self, base_dir=None):
            self.base_dir = base_dir or os.getcwd()

# pylint: disable=C0116  # Missing function or method docstring
        def read_json(self, path, default=None):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except:
                return default

        def write_json(self, path, data, make_backup=False):
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)

    # Define minimal logger
    # pylint: disable=C0116  # Missing function or method docstring
    def get_logger(name):
        return logging.getLogger(name)


# Set up logger
logger = get_logger("ProxyManager")


class ProxyType(Enum):
    """
    Enumeration of supported proxy types.
    """
    SOCKS4 = auto()
    SOCKS5 = auto()
    HTTP = auto()
    HTTPS = auto()

    @classmethod
    def to_str(cls, proxy_type):
        """
        Convert enum value to string representation.

        Args:
            proxy_type: The proxy type enum value.

        Returns:
            str: String representation of the proxy type.
        """
        if isinstance(proxy_type, str):
            return proxy_type.lower()

        type_map = {
            cls.SOCKS4: "socks4",
            cls.SOCKS5: "socks5",
            cls.HTTP: "http",
            cls.HTTPS: "https"
        }
        return type_map.get(proxy_type, "unknown")

    @classmethod
    def from_str(cls, type_str):
        """
        Convert string to enum value.

        Args:
            type_str (str): String representation of proxy type.

        Returns:
            ProxyType: The corresponding enum value.
        """
        type_map = {
            "socks4": cls.SOCKS4,
            "socks5": cls.SOCKS5,
            "http": cls.HTTP,
            "https": cls.HTTPS
        }
        return type_map.get(type_str.lower(), cls.SOCKS5)


class ProxyStatus(Enum):
    """
    Enumeration of possible proxy statuses.
    """
    ACTIVE = auto()      # Proxy is active and usable
    INACTIVE = auto()    # Proxy is temporarily disabled (manually)
    FAILED = auto()      # Proxy has failed recent tests
    SLOW = auto()        # Proxy is active but slow
    BLOCKED = auto()     # Proxy is blocked by Telegram
    UNTESTED = auto()    # Proxy has not been tested yet

    @classmethod
    def to_str(cls, status):
        """
        Convert enum value to string representation.

        Args:
            status: The status enum value.

        Returns:
            str: String representation of the status.
        """
        if isinstance(status, str):
            return status.lower()

        status_map = {
            cls.ACTIVE: "active",
            cls.INACTIVE: "inactive",
            cls.FAILED: "failed",
            cls.SLOW: "slow",
            cls.BLOCKED: "blocked",
            cls.UNTESTED: "untested"
        }
        return status_map.get(status, "unknown")

    @classmethod
    def from_str(cls, status_str):
        """
        Convert string to enum value.

        Args:
            status_str (str): String representation of status.

        Returns:
            ProxyStatus: The corresponding enum value.
        """
        status_map = {
            "active": cls.ACTIVE,
            "inactive": cls.INACTIVE,
            "failed": cls.FAILED,
            "slow": cls.SLOW,
            "blocked": cls.BLOCKED,
            "untested": cls.UNTESTED
        }
        return status_map.get(status_str.lower(), cls.UNTESTED)


class ProxyManager:
    """
    Centralized proxy management system for Telegram Account Manager.

    This class handles the management of proxy servers, including adding, testing,
    removing, and rotating proxies. It follows the Singleton pattern to ensure
    consistent proxy management across the application.
    """
    _instance = None
    _lock = threading.RLock()

    DEFAULT_PROXIES_FILE = "proxies.json"
    DEFAULT_TEST_TIMEOUT = 10  # seconds
    DEFAULT_MAX_LATENCY = 1000  # milliseconds
    DEFAULT_TEST_URL = "api.telegram.org"
    DEFAULT_TEST_PORT = 443

    def __new__(cls, proxies_file=None, config=None, file_manager=None):
        """
        Create a new ProxyManager instance if one doesn't exist (Singleton pattern).

        Args:
            proxies_file (str, optional): Path to the proxies file.
            config (Config, optional): Configuration instance to use.
            file_manager (JsonFileManager, optional): File manager to use.

        Returns:
            ProxyManager: The singleton ProxyManager instance.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ProxyManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, proxies_file=None, config=None, file_manager=None):
        """
        Initialize the ProxyManager.

        Args:
            proxies_file (str, optional): Path to the proxies file.
            config (Config, optional): Configuration instance to use.
            file_manager (JsonFileManager, optional): File manager to use.
        """
        with self._lock:
            if self._initialized:
                return

            # Initialize dependencies
            self.config = config or Config()
            self.file_manager = file_manager or JsonFileManager()

            # Proxy file location
            self.proxies_file = proxies_file or self.config.get(
                "proxies_file",
                self.DEFAULT_PROXIES_FILE
            )

            # Proxies dictionary: ID -> proxy data
            self.proxies = {}

            # Proxy rotation settings
            self.auto_rotation_enabled = False
            self.rotation_interval = self.config.get(
                "proxy_rotation_interval", 3600)  # 1 hour
            self.rotation_thread = None
            self.stop_rotation = threading.Event()

            # Test settings
            self.test_timeout = self.config.get(
                "proxy_test_timeout", self.DEFAULT_TEST_TIMEOUT)
            self.max_latency = self.config.get(
                "proxy_max_latency", self.DEFAULT_MAX_LATENCY)
            self.test_url = self.config.get(
                "proxy_test_url", self.DEFAULT_TEST_URL)
            self.test_port = self.config.get(
                "proxy_test_port", self.DEFAULT_TEST_PORT)

            # Current active proxy
            self.current_proxy_id = None

            # Cache for proxy performance metrics
            self.proxy_metrics = {}

            # Load proxies from file
            self._load_proxies()

            # Start auto-rotation if enabled in config
            if self.config.get("proxy_rotation_enabled", False):
                self.enable_auto_rotation(
                    self.config.get("proxy_rotation_interval", 3600) // 60
                )

            self._initialized = True
            logger.debug("ProxyManager initialized")

    @classmethod
    def get_instance(cls):
        """
        Get the singleton instance of ProxyManager.

        Returns:
            ProxyManager: The singleton instance.
        """
        return cls()

    def _load_proxies(self):
        """
        Load proxies from the proxies file.

        Returns:
            bool: True if proxies were loaded successfully, False otherwise.
        """
        try:
            proxies_data = self.file_manager.read_json(
                self.proxies_file, default={})

            if not proxies_data:
                logger.info("No proxies found in %s", self.proxies_file)
                return False

            # Convert loaded data to internal format
            self.proxies = {}
            for proxy_id, proxy_data in proxies_data.items():
                # Convert string status and type to enum
                proxy_data["status"] = ProxyStatus.from_str(
                    proxy_data.get("status", "untested"))
                proxy_data["type"] = ProxyType.from_str(
                    proxy_data.get("type", "socks5"))

                # Add to proxies dictionary
                self.proxies[proxy_id] = proxy_data

            # Select current proxy if any are active
            active_proxies = {p_id: p for p_id, p in self.proxies.items()
                              if p.get("status") == ProxyStatus.ACTIVE}

            if active_proxies:
                # Select proxy with lowest latency or most recent test
                sorted_proxies = sorted(
                    active_proxies.items(),
                    key=lambda x: (x[1].get("latency", float('inf')),
                                   -x[1].get("last_tested", 0))
                )
                self.current_proxy_id = sorted_proxies[0][0]

            logger.info(
                "Loaded %d proxies from %s",
                len(self.proxies),
                self.proxies_file
            )
            return True

        except FileReadError as e:
            logger.warning("Could not load proxies file: %s", e)
            return False
        except Exception as e:
            logger.error("Error loading proxies: %s", e)
            return False

    def _save_proxies(self):
        """
        Save proxies to the proxies file.

        Returns:
            bool: True if proxies were saved successfully, False otherwise.
        """
        try:
            # Convert internal format to serializable format
            proxies_data = {}
            for proxy_id, proxy_data in self.proxies.items():
                # Create a copy to avoid modifying the original
                serialized_proxy = proxy_data.copy()

                # Convert enum values to strings
                if "status" in serialized_proxy:
                    if isinstance(serialized_proxy["status"], ProxyStatus):
                        serialized_proxy["status"] = ProxyStatus.to_str(
                            serialized_proxy["status"])

                if "type" in serialized_proxy:
                    if isinstance(serialized_proxy["type"], ProxyType):
                        serialized_proxy["type"] = ProxyType.to_str(
                            serialized_proxy["type"])

                proxies_data[proxy_id] = serialized_proxy

            # Save to file
            self.file_manager.write_json(
                self.proxies_file, proxies_data, make_backup=True)
            logger.debug(
                "Saved %d proxies to %s",
                len(self.proxies),
                self.proxies_file
            )
            return True

        except FileWriteError as e:
            logger.error("Could not save proxies file: %s", e)
            return False
        except Exception as e:
            logger.error("Error saving proxies: %s", e)
            return False

    def add_proxy(self, proxy_type: Union[ProxyType, str], host: str, port: int,
                  username: Optional[str] = None, password: Optional[str] = None,
                  label: Optional[str] = None, region: Optional[str] = None,
                  test: bool = True) -> str:
        """
        Add a new proxy to the manager.

        Args:
            proxy_type (Union[ProxyType, str]): Type of proxy (SOCKS5, HTTP, etc.).
            host (str): Proxy server hostname or IP address.
            port (int): Proxy server port.
            username (str, optional): Username for authentication.
            password (str, optional): Password for authentication.
            label (str, optional): Custom label for the proxy.
            region (str, optional): Geographic region of the proxy.
            test (bool): Whether to test the proxy immediately after adding.

        Returns:
            str: ID of the added proxy.

        Raises:
            ValidationError: If proxy details are invalid.
        """
        # Validate inputs
        if not host:
            raise ValidationError("host", "Proxy host cannot be empty")

        if not isinstance(port, int) or port <= 0 or port > 65535:
            raise ValidationError("port", f"Invalid proxy port: {port}")

        # Convert string type to enum if needed
        if isinstance(proxy_type, str):
            proxy_type = ProxyType.from_str(proxy_type)

        # Generate a unique ID for the proxy
        proxy_id = f"proxy_{int(time.time())}_{random.randint(1000, 9999)}"

        # Create proxy object
        proxy_data = {
            "type": proxy_type,
            "host": host,
            "port": port,
            "status": ProxyStatus.UNTESTED,
            "added_at": datetime.now().isoformat(),
            "last_tested": None,
            "latency": None,
            "success_count": 0,
            "failure_count": 0
        }

        # Add optional fields if provided
        if username:
            proxy_data["username"] = username

        if password:
            proxy_data["password"] = password

        if label:
            proxy_data["label"] = label

        if region:
            proxy_data["region"] = region

        # Add to proxies dictionary
        with self._lock:
            self.proxies[proxy_id] = proxy_data
            self._save_proxies()

        logger.info(
            "Added new proxy %s: %s:%s (%s)",
            proxy_id,
            host,
            port,
            ProxyType.to_str(proxy_type)
        )

        # Test the proxy if requested
        if test:
            is_working, latency = self.test_proxy(proxy_id)
            logger.info(
                "Tested proxy %s: %s" +
                (", latency: %sms" if is_working else ""),
                proxy_id,
                "Success" if is_working else "Failed",
                latency if is_working else None
            )

        return proxy_id

    def remove_proxy(self, proxy_id: str) -> bool:
        """
        Remove a proxy from the manager.

        Args:
            proxy_id (str): ID of the proxy to remove.

        Returns:
            bool: True if the proxy was removed, False otherwise.
        """
        with self._lock:
            if proxy_id not in self.proxies:
                logger.warning("Proxy %s not found for removal", proxy_id)
                return False

            # If this is the current proxy, clear it
            if proxy_id == self.current_proxy_id:
                self.current_proxy_id = None

            # Remove from dictionaries
            host = self.proxies[proxy_id].get("host", "unknown")
            port = self.proxies[proxy_id].get("port", 0)
            del self.proxies[proxy_id]

            if proxy_id in self.proxy_metrics:
                del self.proxy_metrics[proxy_id]

            # Save changes
            self._save_proxies()

            logger.info("Removed proxy %s: %s:%s", proxy_id, host, port)
            return True

    def get_proxy(self, proxy_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a proxy by its ID.

        Args:
            proxy_id (str): ID of the proxy to get.

        Returns:
            Optional[Dict[str, Any]]: The proxy data or None if not found.
        """
        return self.proxies.get(proxy_id)

    def list_proxies(self, status: Optional[Union[ProxyStatus, str]] = None,
                     region: Optional[str] = None,
                     max_latency: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List proxies, optionally filtered by criteria.

        Args:
            status (Optional[Union[ProxyStatus, str]]): Filter by proxy status.
            region (Optional[str]): Filter by region.
            max_latency (Optional[int]): Maximum acceptable latency in ms.

        Returns:
            List[Dict[str, Any]]: List of proxies matching the criteria.
        """
        # Convert string status to enum if needed
        if isinstance(status, str):
            status = ProxyStatus.from_str(status)

        result = []
        for proxy_id, proxy_data in self.proxies.items():
            # Apply filters
            if status is not None and proxy_data.get("status") != status:
                continue

            if region is not None and proxy_data.get("region") != region:
                continue

            if max_latency is not None:
                latency = proxy_data.get("latency")
                if latency is None or latency > max_latency:
                    continue

            # Add proxy ID to data
            proxy_info = proxy_data.copy()
            proxy_info["id"] = proxy_id

            result.append(proxy_info)

        # Sort by latency and success rate
        result.sort(key=lambda p: (
            # Sort active first, then untested, then others
            0 if p.get("status") == ProxyStatus.ACTIVE else
            1 if p.get("status") == ProxyStatus.UNTESTED else 2,
            # Then by latency (None is considered worst)
            float('inf') if p.get("latency") is None else p.get("latency"),
            # Then by success rate
            -(p.get("success_count", 0) /
              max(p.get("success_count", 0) + p.get("failure_count", 0), 1))
        ))

        return result

    async def _test_proxy_async(self, proxy_data: Dict[str, Any]) -> Tuple[bool, Optional[float]]:
        """
        Test a proxy asynchronously.

        Args:
            proxy_data (Dict[str, Any]): The proxy data to test.

        Returns:
            Tuple[bool, Optional[float]]: Success status and latency (if successful).
        """
        proxy_type = proxy_data.get("type", ProxyType.SOCKS5)
        host = proxy_data.get("host")
        port = proxy_data.get("port")
        username = proxy_data.get("username")
        password = proxy_data.get("password")

        if not host or not port:
            return False, None

        # Convert enum to string if needed
        if isinstance(proxy_type, ProxyType):
            proxy_type = ProxyType.to_str(proxy_type)

        try:
            # Use asyncio for non-blocking socket operations
            start_time = time.time()

            # Create socket based on proxy type
            reader, writer = None, None

            try:
                # Connect to the proxy
                reader, writer = await asyncio.open_connection(host, port)

                # If we get here, the connection to the proxy was successful
                # In a real implementation, we would make a request through the proxy
                # to ensure it can connect to Telegram's servers

                latency = (time.time() - start_time) * 1000  # Convert to ms
                return True, latency

            finally:
                # Clean up resources
                if writer:
                    writer.close()
                    await writer.wait_closed()

        except (asyncio.TimeoutError, ConnectionRefusedError, ConnectionError, socket.error) as e:
            logger.debug("Proxy test failed for %s:%s: %s", host, port, e)
            return False, None

        except Exception as e:
            logger.error("Error testing proxy %s:%s: %s", host, port, e)
            return False, None

    def test_proxy(self, proxy_id: str) -> Tuple[bool, Optional[float]]:
        """
        Test a proxy's connectivity and performance.

        Args:
            proxy_id (str): ID of the proxy to test.

        Returns:
            Tuple[bool, Optional[float]]: Success status and latency (if successful).

        Raises:
            ProxyError: If the proxy doesn't exist or can't be tested.
        """
        with self._lock:
            proxy_data = self.proxies.get(proxy_id)
            if not proxy_data:
                raise ProxyError(f"Proxy {proxy_id} not found")

            host = proxy_data.get("host", "unknown")
            port = proxy_data.get("port", 0)

            # Create an event loop or use the existing one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # If there's no event loop in this thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run the async test
            try:
                is_working, latency = loop.run_until_complete(
                    self._test_proxy_async(proxy_data)
                )
            except Exception as e:
                logger.error(
                    "Error during proxy test for %s:%s: %s", host, port, e)
                is_working, latency = False, None

            # Update proxy status based on test results
            now = datetime.now().isoformat()
            proxy_data["last_tested"] = now

            if is_working:
                proxy_data["latency"] = latency
                proxy_data["last_success"] = now
                proxy_data["success_count"] = proxy_data.get(
                    "success_count", 0) + 1

                # Set status based on latency
                if latency <= self.max_latency:
                    proxy_data["status"] = ProxyStatus.ACTIVE
                else:
                    proxy_data["status"] = ProxyStatus.SLOW
            else:
                proxy_data["last_failure"] = now
                proxy_data["failure_count"] = proxy_data.get(
                    "failure_count", 0) + 1

                # If too many failures, mark as failed
                failure_count = proxy_data.get("failure_count", 0)
                success_count = proxy_data.get("success_count", 0)

                if failure_count > 3 and failure_count > success_count:
                    proxy_data["status"] = ProxyStatus.FAILED

            # Save the updated proxy data
            self._save_proxies()

            # Log test result
            log_msg = f"Proxy {proxy_id} ({host}:{port}) test: " + \
                ("Successful" if is_working else "Failed")
            if is_working and latency is not None:
                log_msg += f", latency: {latency:.2f}ms"
            logger.debug(log_msg)

            return is_working, latency

    def test_all_proxies(self) -> Dict[str, Tuple[bool, Optional[float]]]:
        """
        Test all proxies and return their status.

        Returns:
            Dict[str, Tuple[bool, Optional[float]]]: Dictionary mapping proxy IDs to
                their test results (success status, latency).
        """
        results = {}

        for proxy_id in list(self.proxies.keys()):
            try:
                success, latency = self.test_proxy(proxy_id)
                results[proxy_id] = (success, latency)
            except Exception as e:
                logger.error("Error testing proxy %s: %s", proxy_id, e)
                results[proxy_id] = (False, None)

        return results

    def get_best_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Get the best available proxy based on performance metrics.

        Returns:
            Optional[Dict[str, Any]]: The best proxy data with ID, or None if no proxy is available.
        """
        with self._lock:
            # Get active proxies
            active_proxies = self.list_proxies(status=ProxyStatus.ACTIVE)

            if not active_proxies:
                # If no active proxies, try to test untested ones
                untested_proxies = self.list_proxies(
                    status=ProxyStatus.UNTESTED)
                for proxy in untested_proxies:
                    proxy_id = proxy.get("id")
                    try:
                        success, _ = self.test_proxy(proxy_id)
                        if success:
                            # Found a working proxy, update active proxies list
                            active_proxies = self.list_proxies(
                                status=ProxyStatus.ACTIVE)
                            break
                    except Exception:
                        continue

            if not active_proxies:
                # Still no active proxies, try slow ones
                active_proxies = self.list_proxies(status=ProxyStatus.SLOW)

            if not active_proxies:
                logger.warning("No active or slow proxies available")
                return None

            # First proxy is the best according to the sorting in list_proxies
            best_proxy = active_proxies[0]
            self.current_proxy_id = best_proxy.get("id")

            return best_proxy

    def apply_proxy_to_client(self, client, proxy_id: Optional[str] = None) -> bool:
        """
        Apply a proxy to a Telegram client.

        Args:
            client: The Telegram client to apply the proxy to.
            proxy_id (Optional[str]): ID of the proxy to apply. If None, uses the best available.

        Returns:
            bool: True if the proxy was applied, False otherwise.
        """
        try:
            # Get the proxy to use
            if proxy_id:
                proxy_data = self.proxies.get(proxy_id)
                if not proxy_data:
                    logger.warning(
                        "Proxy %s not found, using best available", proxy_id)
                    proxy_data = self.get_best_proxy()
            else:
                proxy_data = self.get_best_proxy()

            if not proxy_data:
                logger.warning("No proxy available to apply to client")
                return False

            # Extract proxy details
            proxy_id = proxy_data.get("id")
            proxy_type = proxy_data.get("type")
            host = proxy_data.get("host")
            port = proxy_data.get("port")
            username = proxy_data.get("username")
            password = proxy_data.get("password")

            # Convert enum to string if needed
            if isinstance(proxy_type, ProxyType):
                proxy_type_str = ProxyType.to_str(proxy_type)
            else:
                proxy_type_str = str(proxy_type).lower()

            # Set proxy on the client
            if hasattr(client, 'proxy'):
                # For Telethon clients
                proxy_args = {
                    'proxy_type': proxy_type_str,
                    'addr': host,
                    'port': port,
                    'rdns': True
                }

                if username:
                    proxy_args['username'] = username
                if password:
                    proxy_args['password'] = password

                client.proxy = proxy_args
                logger.info("Applied proxy %s (%s:%s) to client",
                            proxy_id, host, port)
                return True

            elif hasattr(client, 'session') and hasattr(client.session, 'proxy'):
                # For some other types of clients
                client.session.proxy = {
                    'scheme': proxy_type_str,
                    'hostname': host,
                    'port': port,
                    'username': username,
                    'password': password
                }
                logger.info(
                    "Applied proxy %s (%s:%s) to client session", proxy_id, host, port)
                return True

            else:
                logger.warning("Client does not support proxy configuration")
                return False

        except Exception as e:
            logger.error("Error applying proxy to client: %s", e)
            return False

    def enable_auto_rotation(self, interval_minutes: int = 60) -> bool:
        """
        Enable automatic proxy rotation at specified intervals.

        Args:
            interval_minutes (int): Interval in minutes between rotations.

        Returns:
            bool: True if auto-rotation was enabled, False otherwise.
        """
        with self._lock:
            # Stop existing rotation if any
            if self.rotation_thread and self.rotation_thread.is_alive():
                self.stop_rotation.set()
                self.rotation_thread.join(timeout=2.0)

            # Reset stop event
            self.stop_rotation.clear()

            # Set rotation settings
            self.auto_rotation_enabled = True
            self.rotation_interval = interval_minutes * 60  # Convert to seconds

            # Start rotation thread
            self.rotation_thread = threading.Thread(
                target=self._rotation_worker,
                daemon=True,
                name="ProxyRotationThread"
            )
            self.rotation_thread.start()

            logger.info(
                "Enabled automatic proxy rotation every %s minutes", interval_minutes)

            # Update config
            self.config.set("proxy_rotation_enabled", True)
            self.config.set("proxy_rotation_interval", self.rotation_interval)

            return True

    def disable_auto_rotation(self) -> bool:
        """
        Disable automatic proxy rotation.

        Returns:
            bool: True if auto-rotation was disabled, False otherwise.
        """
        with self._lock:
            if not self.auto_rotation_enabled:
                return True

            # Stop rotation thread
            self.auto_rotation_enabled = False
            self.stop_rotation.set()

            if self.rotation_thread and self.rotation_thread.is_alive():
                self.rotation_thread.join(timeout=2.0)

            self.rotation_thread = None

            logger.info("Disabled automatic proxy rotation")

            # Update config
            self.config.set("proxy_rotation_enabled", False)

            return True

    def _rotation_worker(self):
        """
        Worker function for proxy rotation thread.
        """
        logger.debug("Proxy rotation thread started")

        while not self.stop_rotation.is_set():
            try:
                # Sleep for a short interval at a time to check stop flag frequently
                for _ in range(self.rotation_interval * 2):  # Check twice per second
                    if self.stop_rotation.is_set():
                        return
                    time.sleep(0.5)

                # Time to rotate proxy
                logger.debug("Rotating proxy...")
                self.rotate_proxy()

            except Exception as e:
                logger.error("Error in proxy rotation worker: %s", e)
                # Don't crash the thread on error, just continue

    def rotate_proxy(self) -> Optional[str]:
        """
        Rotate to the next best available proxy.

        Returns:
            Optional[str]: ID of the new proxy, or None if no suitable proxy was found.
        """
        with self._lock:
            # Get current proxy info
            current_id = self.current_proxy_id
            current_proxy = self.proxies.get(
                current_id) if current_id else None

            # Get list of active proxies excluding current one
            active_proxies = [p for p in self.list_proxies(status=ProxyStatus.ACTIVE)
                              if p.get("id") != current_id]

            # If no active proxies other than current, try to find some
            if not active_proxies:
                # Test some untested proxies
                untested_proxies = self.list_proxies(
                    status=ProxyStatus.UNTESTED)
                # Test up to 3 untested proxies
                for proxy in untested_proxies[:3]:
                    proxy_id = proxy.get("id")
                    try:
                        success, _ = self.test_proxy(proxy_id)
                        if success:
                            # Found a working proxy, update active proxies list
                            active_proxies = [p for p in self.list_proxies(status=ProxyStatus.ACTIVE)
                                              if p.get("id") != current_id]
                            break
                    except Exception:
                        continue

            # If still no other active proxies, try slow ones
            if not active_proxies:
                active_proxies = [p for p in self.list_proxies(status=ProxyStatus.SLOW)
                                  if p.get("id") != current_id]

            # If no alternative proxies available, keep using current one
            if not active_proxies:
                if current_proxy:
                    logger.warning(
                        "No alternative proxies available for rotation, keeping current proxy")
                    return current_id
                else:
                    logger.warning("No proxies available for rotation")
                    return None

            # Select best alternative proxy (already sorted by list_proxies)
            new_proxy = active_proxies[0]
            new_proxy_id = new_proxy.get("id")

            # Update current proxy
            self.current_proxy_id = new_proxy_id

            logger.info("Rotated proxy from %s to %s",
                        current_id or 'None', new_proxy_id)
            return new_proxy_id

    def import_proxies_from_file(self, file_path: str, format_type: str = "json") -> Tuple[int, int]:
        """
        Import proxies from a file.

        Args:
            file_path (str): Path to the file to import.
            format_type (str): Format of the file ('json', 'txt', 'csv').

        Returns:
            Tuple[int, int]: Number of total and successfully imported proxies.

        Raises:
            FileReadError: If the file cannot be read.
            ValidationError: If the file format is invalid.
        """
        if not os.path.exists(file_path):
            raise FileReadError(file_path, "File not found")

        format_type = format_type.lower()
        imported_count = 0
        total_count = 0

        try:
            if format_type == "json":
                # Import from JSON format
                proxies_data = self.file_manager.read_json(file_path)
                if not isinstance(proxies_data, dict) and not isinstance(proxies_data, list):
                    raise ValidationError(
                        "file", "Invalid JSON format for proxies file")

                if isinstance(proxies_data, dict):
                    # Handle dictionary format {id -> proxy_data}
                    for proxy_id, proxy_data in proxies_data.items():
                        total_count += 1
                        try:
                            # Extract proxy details
                            proxy_type = proxy_data.get("type", "socks5")
                            host = proxy_data.get("host")
                            port = proxy_data.get("port")
                            username = proxy_data.get("username")
                            password = proxy_data.get("password")
                            label = proxy_data.get("label")
                            region = proxy_data.get("region")

                            if not host or not port:
                                logger.warning(
                                    "Skipping proxy with missing host or port: %s", proxy_id)
                                continue

                            # Add proxy
                            self.add_proxy(
                                proxy_type=proxy_type,
                                host=host,
                                port=port,
                                username=username,
                                password=password,
                                label=label,
                                region=region,
                                test=False  # Don't test immediately to speed up import
                            )
                            imported_count += 1

                        except Exception as e:
                            logger.error(
                                "Error importing proxy %s: %s", proxy_id, e)

                elif isinstance(proxies_data, list):
                    # Handle list format [proxy_data, proxy_data, ...]
                    for proxy_data in proxies_data:
                        total_count += 1
                        try:
                            # Extract proxy details
                            proxy_type = proxy_data.get("type", "socks5")
                            host = proxy_data.get("host")
                            port = proxy_data.get("port")
                            username = proxy_data.get("username")
                            password = proxy_data.get("password")
                            label = proxy_data.get("label")
                            region = proxy_data.get("region")

                            if not host or not port:
                                logger.warning(
                                    "Skipping proxy with missing host or port")
                                continue

                            # Add proxy
                            self.add_proxy(
                                proxy_type=proxy_type,
                                host=host,
                                port=port,
                                username=username,
                                password=password,
                                label=label,
                                region=region,
                                test=False  # Don't test immediately to speed up import
                            )
                            imported_count += 1

                        except Exception as e:
                            logger.error(f"Error importing proxy: {e}")

            elif format_type == "txt":
                # Import from plain text format (one proxy per line)
                with open(file_path, 'r') as f:
                    lines = f.readlines()

                for line in lines:
                    total_count += 1
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    try:
                        # Parse line format: [type://][username:password@]host:port
                        proxy_type = "socks5"  # Default type
                        username = None
                        password = None

                        # Extract proxy type if present
                        if "://" in line:
                            parts = line.split("://", 1)
                            proxy_type = parts[0].strip().lower()
                            line = parts[1]

                        # Extract credentials if present
                        if "@" in line:
                            creds, line = line.split("@", 1)
                            if ":" in creds:
                                username, password = creds.split(":", 1)

                        # Extract host:port
                        if ":" in line:
                            host, port = line.split(":", 1)
                            try:
                                port = int(port)

                                # Add proxy
                                self.add_proxy(
                                    proxy_type=proxy_type,
                                    host=host,
                                    port=port,
                                    username=username,
                                    password=password,
                                    test=False  # Don't test immediately to speed up import
                                )
                                imported_count += 1

                            except ValueError:
                                logger.warning(
                                    f"Invalid port number in proxy entry: {line}")
                        else:
                            logger.warning(
                                f"Invalid proxy format (missing port): {line}")

                    except Exception as e:
                        logger.error(
                            f"Error importing proxy from line '{line}': {e}")

            elif format_type == "csv":
                # Import from CSV format
                import csv

                with open(file_path, 'r', newline='') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)

                    # Try to identify columns
                    if header:
                        header = [h.lower() for h in header]
                        type_col = next(
                            (i for i, h in enumerate(header) if 'type' in h), None)
                        host_col = next((i for i, h in enumerate(
                            header) if 'host' in h or 'ip' in h), None)
                        port_col = next(
                            (i for i, h in enumerate(header) if 'port' in h), None)
                        user_col = next(
                            (i for i, h in enumerate(header) if 'user' in h), None)
                        pass_col = next(
                            (i for i, h in enumerate(header) if 'pass' in h), None)
                        label_col = next((i for i, h in enumerate(
                            header) if 'label' in h or 'name' in h), None)
                        region_col = next((i for i, h in enumerate(
                            header) if 'region' in h or 'country' in h), None)
                    else:
                        # No header, assume fixed order: type,host,port,username,password,label,region
                        type_col, host_col, port_col, user_col, pass_col, label_col, region_col = 0, 1, 2, 3, 4, 5, 6

                    for row in reader:
                        total_count += 1
                        try:
                            # Extract values, with fallbacks for missing columns
                            proxy_type = row[type_col] if type_col is not None and type_col < len(
                                row) else "socks5"
                            host = row[host_col] if host_col is not None and host_col < len(
                                row) else None

                            if port_col is not None and port_col < len(row):
                                try:
                                    port = int(row[port_col])
                                except ValueError:
                                    logger.warning(
                                        "Invalid port value in row: %s", row)
                                    continue
                            else:
                                continue  # Port is required

                            username = row[user_col] if user_col is not None and user_col < len(
                                row) else None
                            password = row[pass_col] if pass_col is not None and pass_col < len(
                                row) else None
                            label = row[label_col] if label_col is not None and label_col < len(
                                row) else None
                            region = row[region_col] if region_col is not None and region_col < len(
                                row) else None

                            if not host:
                                logger.warning("Missing host in row: %s", row)
                                continue

                            # Add proxy
                            self.add_proxy(
                                proxy_type=proxy_type,
                                host=host,
                                port=port,
                                username=username,
                                password=password,
                                label=label,
                                region=region,
                                test=False  # Don't test immediately to speed up import
                            )
                            imported_count += 1

                        except Exception as e:
                            logger.error(
                                "Error importing proxy from row '%s': %s", row, e)

            else:
                raise ValidationError(
                    "format_type", f"Unsupported import format: {format_type}")

            # Save changes
            self._save_proxies()

            logger.info(
                "Imported %d/%d proxies from %s",
                imported_count,
                total_count,
                file_path
            )
            return total_count, imported_count

        except Exception as e:
            logger.error("Error importing proxies from %s: %s", file_path, e)
            raise

    def export_proxies_to_file(self, file_path: str, format_type: str = "json",
                               include_credentials: bool = False,
                               filter_status: Optional[ProxyStatus] = None) -> int:
        """
        Export proxies to a file.

        Args:
            file_path (str): Path to the file to export to.
            format_type (str): Format of the file ('json', 'txt', 'csv').
            include_credentials (bool): Whether to include usernames and passwords.
            filter_status (Optional[ProxyStatus]): Only export proxies with this status.

        Returns:
            int: Number of exported proxies.

        Raises:
            FileWriteError: If the file cannot be written.
            ValidationError: If the format type is invalid.
        """
        # Get proxies to export
        proxies_to_export = self.list_proxies(status=filter_status)

        if not proxies_to_export:
            logger.warning("No proxies to export")
            return 0

        try:
            format_type = format_type.lower()

            if format_type == "json":
                # Export to JSON format
                export_data = {}

                for proxy in proxies_to_export:
                    # Remove ID from data to avoid duplicates
                    proxy_id = proxy.pop("id")

                    # Remove credentials if not including them
                    if not include_credentials:
                        if "username" in proxy:
                            del proxy["username"]
                        if "password" in proxy:
                            del proxy["password"]

                    export_data[proxy_id] = proxy

                # Write to file
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=4)

            elif format_type == "txt":
                # Export to plain text format (one proxy per line)
                with open(file_path, 'w') as f:
                    for proxy in proxies_to_export:
                        proxy_type = ProxyType.to_str(
                            proxy.get("type", "socks5"))
                        host = proxy.get("host")
                        port = proxy.get("port")

                        if not host or not port:
                            continue

                        # Build the proxy string
                        proxy_str = f"{proxy_type}://"

                        if include_credentials:
                            username = proxy.get("username")
                            password = proxy.get("password")
                            if username and password:
                                proxy_str += f"{username}:{password}@"

                        proxy_str += f"{host}:{port}"

                        # Add comments for status and label
                        status = ProxyStatus.to_str(
                            proxy.get("status", "unknown"))
                        label = proxy.get("label", "")

                        if label:
                            proxy_str += f"  # {status}, {label}"
                        else:
                            proxy_str += f"  # {status}"

                        f.write(proxy_str + "\n")

            elif format_type == "csv":
                # Export to CSV format
                import csv

                with open(file_path, 'w', newline='') as f:
                    # Define CSV columns
                    fieldnames = ["type", "host", "port"]

                    if include_credentials:
                        fieldnames.extend(["username", "password"])

                    fieldnames.extend(
                        ["label", "region", "status", "latency", "success_count", "failure_count"])

                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                    for proxy in proxies_to_export:
                        # Build row data
                        row_data = {
                            "type": ProxyType.to_str(proxy.get("type", "socks5")),
                            "host": proxy.get("host", ""),
                            "port": proxy.get("port", ""),
                            "label": proxy.get("label", ""),
                            "region": proxy.get("region", ""),
                            "status": ProxyStatus.to_str(proxy.get("status", "unknown")),
                            "latency": proxy.get("latency", ""),
                            "success_count": proxy.get("success_count", 0),
                            "failure_count": proxy.get("failure_count", 0)
                        }

                        if include_credentials:
                            row_data["username"] = proxy.get("username", "")
                            row_data["password"] = proxy.get("password", "")

                        writer.writerow(row_data)

            else:
                raise ValidationError(
                    "format_type", f"Unsupported export format: {format_type}")

            logger.info(
                f"Exported {len(proxies_to_export)} proxies to {file_path}")
            return len(proxies_to_export)

        except Exception as e:
            logger.error(f"Error exporting proxies to {file_path}: {e}")
            raise

    def set_proxy_status(self, proxy_id: str, status: Union[ProxyStatus, str]) -> bool:
        """
        Set the status of a proxy.

        Args:
            proxy_id (str): ID of the proxy to update.
            status (Union[ProxyStatus, str]): New status to set.

        Returns:
            bool: True if the status was updated, False otherwise.
        """
        with self._lock:
            if proxy_id not in self.proxies:
                logger.warning(f"Proxy {proxy_id} not found for status update")
                return False

            # Convert string status to enum if needed
            if isinstance(status, str):
                status = ProxyStatus.from_str(status)

            # Update status
            self.proxies[proxy_id]["status"] = status
            self._save_proxies()

            logger.info(
                f"Updated proxy {proxy_id} status to {ProxyStatus.to_str(status)}")
            return True

    def cleanup(self):
        """
        Clean up resources used by the ProxyManager.
        """
        # Stop auto-rotation thread if running
        if self.auto_rotation_enabled:
            self.disable_auto_rotation()

        # Save proxies
        self._save_proxies()

        logger.debug("ProxyManager cleaned up")

    def __del__(self):
        """Destructor to ensure resources are cleaned up."""
        try:
            self.cleanup()
        except:
            pass
