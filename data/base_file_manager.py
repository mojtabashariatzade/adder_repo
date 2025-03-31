"""
Base File Manager Module

This module provides base utilities for reading, writing, and managing files within the application.
It supports operations for text and binary files with built-in error handling and validation.

Features:
- Read and write text/binary files safely
- Directory management (create, check existence, list contents)
- File backup mechanisms
- Atomic file operations for safe writes
- Comprehensive error handling
"""

import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar
from datetime import datetime
import time
import threading
import hashlib
from data.base_file_manager import JsonFileManager

# Import custom exceptions
from core.exceptions import (
    FileReadError,
    FileWriteError,
)

# Setup logger
logger = logging.getLogger(__name__)

# Type variable for generic functions
T = TypeVar("T")


class FileManager:
    """
    Base class for file management operations.

    Provides fundamental file operations like reading, writing, copying,
    and deleting files with proper error handling and logging.
    """

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize the FileManager.

        Args:
            base_dir (str, optional): Base directory for relative paths.
                If None, uses the current working directory.
        """
        self.base_dir = base_dir or os.getcwd()
        logger.debug(
            "FileManager initialized with base directory: %s", self.base_dir)

        def get_full_path(self, path):
            """Get the absolute path by joining with base_dir if needed."""
            if os.path.isabs(path):
                return path
            return os.path.join(self.base_dir, path)

    def _resolve_path(self, path: Union[str, Path]) -> Path:
        """
        Resolve a path to an absolute path.

        Args:
            path (Union[str, Path]): The path to resolve.

        Returns:
            Path: The resolved absolute path.
        """
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return Path(self.base_dir) / path_obj

    def exists(self, path: Union[str, Path]) -> bool:
        """
        Check if a file exists.

        Args:
            path (Union[str, Path]): Path to the file.

        Returns:
            bool: True if the file exists, False otherwise.
        """
        file_path = self._resolve_path(path)
        return file_path.exists()

    def is_file(self, path: Union[str, Path]) -> bool:
        """
        Check if a path is a file.

        Args:
            path (Union[str, Path]): Path to check.

        Returns:
            bool: True if the path is a file, False otherwise.
        """
        file_path = self._resolve_path(path)
        return file_path.is_file()

    def is_dir(self, path: Union[str, Path]) -> bool:
        """
        Check if a path is a directory.

        Args:
            path (Union[str, Path]): Path to check.

        Returns:
            bool: True if the path is a directory, False otherwise.
        """
        file_path = self._resolve_path(path)
        return file_path.is_dir()

    def ensure_dir(self, path: Union[str, Path]) -> Path:
        """
        Ensure a directory exists. Creates it if it doesn't.

        Args:
            path (Union[str, Path]): Path to the directory.

        Returns:
            Path: The path to the directory.

        Raises:
            FileWriteError: If the directory cannot be created.
        """
        dir_path = self._resolve_path(path)
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            return dir_path
        except Exception as e:
            logger.error("Failed to create directory %s: %s", dir_path, e)
            raise FileWriteError(f"Failed to create directory: {e}") from e

    def ensure_parent_dir(self, path: Union[str, Path]) -> Path:
        """
        Ensure the parent directory of a file exists. Creates it if it doesn't.

        Args:
            path (Union[str, Path]): Path to the file.

        Returns:
            Path: The path to the parent directory.

        Raises:
            FileWriteError: If the parent directory cannot be created.
        """
        file_path = self._resolve_path(path)
        return self.ensure_dir(file_path.parent)

    def read_text(self, path: Union[str, Path], encoding: str = "utf-8") -> str:
        """
        Read text from a file.

        Args:
            path (Union[str, Path]): Path to the file.
            encoding (str): Character encoding to use.

        Returns:
            str: The file content as text.

        Raises:
            FileReadError: If the file cannot be read.
        """
        file_path = self._resolve_path(path)
        try:
            with open(file_path, "r", encoding=encoding) as file:
                return file.read()
        except FileNotFoundError:
            logger.error("File not found: %s", file_path)
            raise FileReadError(str(file_path), "File not found") from None
        except UnicodeDecodeError as e:
            logger.error("Unicode decode error for %s: %s", file_path, e)
            raise FileReadError(f"Unicode decode error: {e}") from e
        except Exception as e:
            logger.error("Error reading file %s: %s", file_path, e)
            raise FileReadError(str(file_path), str(e)) from e

    def read_binary(self, path: Union[str, Path]) -> bytes:
        """
        Read binary data from a file.

        Args:
            path (Union[str, Path]): Path to the file.

        Returns:
            bytes: The file content as binary data.

        Raises:
            FileReadError: If the file cannot be read.
        """
        file_path = self._resolve_path(path)
        try:
            with open(file_path, "rb") as file:
                return file.read()
        except FileNotFoundError:
            logger.error("File not found: %s", file_path)
            raise FileReadError(str(file_path), "File not found") from None
        except Exception as e:
            logger.error("Error reading binary file %s: %s", file_path, str(e))
            raise FileReadError(str(file_path), str(e)) from None

    def write_text(
        self,
        path: Union[str, Path],
        content: str,
        encoding: str = "utf-8",
        make_backup: bool = False,
    ) -> None:
        """
        Write text to a file.

        Args:
            path (Union[str, Path]): Path to the file.
            content (str): Text content to write.
            encoding (str): Character encoding to use.
            make_backup (bool): Whether to make a backup of the existing file.

        Raises:
            FileWriteError: If the file cannot be written.
        """
        file_path = self._resolve_path(path)

        # Create parent directory if it doesn't exist
        self.ensure_parent_dir(file_path)

        # Make backup if requested
        if make_backup and file_path.exists():
            self.make_backup(file_path)

        try:
            # Use atomic write for safety
            self._atomic_write(file_path, content, mode="w", encoding=encoding)
            logger.debug("Text file written: %s", file_path)
        except Exception as e:
            logger.error("Error writing text file %s: %s", file_path, str(e))
            raise FileWriteError(str(file_path), str(e)) from e

    def write_binary(
        self, path: Union[str, Path], content: bytes, make_backup: bool = False
    ) -> None:
        """
        Write binary data to a file.

        Args:
            path (Union[str, Path]): Path to the file.
            content (bytes): Binary content to write.
            make_backup (bool): Whether to make a backup of the existing file.

        Raises:
            FileWriteError: If the file cannot be written.
        """
        file_path = self._resolve_path(path)

        # Create parent directory if it doesn't exist
        self.ensure_parent_dir(file_path)

        # Make backup if requested
        if make_backup and file_path.exists():
            self.make_backup(file_path)

        try:
            # Use atomic write for safety
            self._atomic_write(file_path, content, mode="wb")
            logger.debug("Text file written: %s", file_path)
        except Exception as e:
            logger.error("Error writing text file %s: %s", file_path, str(e))
            raise FileWriteError(str(file_path), str(e)) from e

    def _atomic_write(
        self,
        path: Path,
        content: Union[str, bytes],
        mode: str,
        encoding: Optional[str] = None,
    ) -> None:
        """
        Write to a file atomically using a temporary file.

        Args:
            path (Path): Path to the file.
            content (Union[str, bytes]): Content to write.
            mode (str): File mode ('w' or 'wb').
            encoding (str, optional): Character encoding to use.
        """
        # Create a temporary file in the same directory
        temp_file = Path(f"{path}.temp.{int(time.time())}")

        try:
            # Write content to the temporary file
            kwargs = {}
            if "b" not in mode:  # Text mode
                # Use utf-8 as default if encoding is None
                kwargs["encoding"] = encoding or "utf-8"
            with open(
                    temp_file, mode, encoding="utf-8" if "b" not in mode else None, **kwargs) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Ensure data is written to disk

            # Replace the original file with the temporary file
            # This is atomic on POSIX systems
            os.replace(temp_file, path)
        except (IOError, OSError) as e:
            # Clean up the temporary file if an error occurred
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except (IOError, OSError) as cleanup_error:
                    logger.error(
                        "Error cleaning up temporary file %s: %s",
                        temp_file,
                        str(cleanup_error),
                    )
            raise FileWriteError(str(path), str(e)) from e

    def make_backup(
        self, path: Union[str, Path], backup_suffix: Optional[str] = None
    ) -> Path:
        """
        Create a backup of a file.

        Args:
            path (Union[str, Path]): Path to the file to backup.
            backup_suffix (str, optional): Suffix to append to the backup file name.
                If None, uses timestamp.

        Returns:
            Path: Path to the backup file.

        Raises:
            FileReadError: If the source file cannot be read.
            FileWriteError: If the backup cannot be created.
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            logger.error("Cannot backup non-existent file: %s", file_path)
            raise FileReadError(str(file_path), "File not found")

        # Default suffix is a timestamp
        suffix = backup_suffix or f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = Path(f"{file_path}{suffix}")

        try:
            shutil.copy2(file_path, backup_path)
            logger.debug("Backup created: %s", backup_path)
            return backup_path
        except Exception as e:
            logger.error("Error creating backup of %s: %s", file_path, e)
            raise FileWriteError(f"Error creating backup: {e}") from e

    def delete(self, path: Union[str, Path], missing_ok: bool = False) -> bool:
        """
        Delete a file.

        Args:
            path (Union[str, Path]): Path to the file to delete.
            missing_ok (bool): If True, don't raise an error if the file doesn't exist.

        Returns:
            bool: True if the file was deleted, False if it didn't exist and missing_ok is True.

        Raises:
            FileWriteError: If the file cannot be deleted.
            FileReadError: If the file doesn't exist and missing_ok is False.
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            if missing_ok:
                return False
            logger.error("Cannot delete non-existent file: %s", file_path)
            raise FileReadError(str(file_path), "File not found")

        try:
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                os.unlink(file_path)
            logger.debug("Deleted: %s", file_path)
            return True
        except Exception as e:
            logger.error("Error deleting %s: %s", file_path, e)
            raise FileWriteError(f"Error deleting file: {e}") from e

    def copy(
        self, src: Union[str, Path], dst: Union[str, Path], overwrite: bool = False
    ) -> Path:
        """
        Copy a file or directory.

        Args:
            src (Union[str, Path]): Source path.
            dst (Union[str, Path]): Destination path.
            overwrite (bool): Whether to overwrite the destination if it exists.

        Returns:
            Path: Path to the destination.

        Raises:
            FileReadError: If the source cannot be read.
            FileWriteError: If the destination cannot be written.
        """
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)

        if not src_path.exists():
            logger.error("Source does not exist: %s", str(src_path))
            raise FileReadError(str(src_path), "Source not found")

        if dst_path.exists() and not overwrite:
            logger.error("Destination already exists: %s", str(dst_path))
            raise FileWriteError(str(dst_path), "Destination already exists")

        try:
            if src_path.is_dir():
                # If destination exists and is a file, remove it
                if dst_path.exists() and dst_path.is_file():
                    os.unlink(dst_path)
                # Copy directory and its contents
                if overwrite and dst_path.exists():
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)
            else:
                # Create parent directory if it doesn't exist
                self.ensure_parent_dir(dst_path)
                # Copy file with metadata
                shutil.copy2(src_path, dst_path)

            logger.debug("Copied %s to %s", src_path, dst_path)
            return dst_path
        except Exception as e:
            logger.error("Error copying %s to %s: %s", src_path, dst_path, e)
            raise FileWriteError(str(dst_path), f"Error copying: {e}") from e

    def move(
        self, src: Union[str, Path], dst: Union[str, Path], overwrite: bool = False
    ) -> Path:
        """
        Move a file or directory.

        Args:
            src (Union[str, Path]): Source path.
            dst (Union[str, Path]): Destination path.
            overwrite (bool): Whether to overwrite the destination if it exists.

        Returns:
            Path: Path to the destination.

        Raises:
            FileReadError: If the source cannot be read.
            FileWriteError: If the destination cannot be written.
        """
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)

        if not src_path.exists():
            logger.error("Source does not exist: %s", str(src_path))
            raise FileReadError(str(src_path), "Source not found")

        if dst_path.exists() and not overwrite:
            logger.error("Destination already exists: %s", str(dst_path))
            raise FileWriteError(str(dst_path), "Destination already exists")

        try:
            # Create parent directory if it doesn't exist
            self.ensure_parent_dir(dst_path)

            # Remove destination if it exists and overwrite is True
            if dst_path.exists() and overwrite:
                if dst_path.is_dir():
                    shutil.rmtree(dst_path)
                else:
                    os.unlink(dst_path)

            # Move file or directory
            shutil.move(src_path, dst_path)

            logger.debug("Moved %s to %s", src_path, dst_path)
            return dst_path
        except Exception as e:
            logger.error("Error moving %s to %s: %s", src_path, dst_path, e)
            raise FileWriteError(f"Error moving: {e}") from e

    def list_dir(
        self, path: Union[str, Path], pattern: Optional[str] = None
    ) -> List[Path]:
        """
        List files and directories in a directory.

        Args:
            path (Union[str, Path]): Path to the directory.
            pattern (str, optional): Glob pattern to filter results.

        Returns:
            List[Path]: List of paths in the directory.

        Raises:
            FileReadError: If the directory cannot be read.
        """
        dir_path = self._resolve_path(path)

        if not dir_path.exists():
            logger.error("Directory does not exist: %s", dir_path)
            raise FileReadError(str(dir_path), "Directory not found")

        if not dir_path.is_dir():
            logger.error("Path is not a directory: %s", dir_path)
            raise FileReadError(str(dir_path), "Not a directory")

        try:
            if pattern:
                return list(dir_path.glob(pattern))
            return list(dir_path.iterdir())
        except Exception as e:
            logger.error("Error listing directory %s: %s", dir_path, e)
            raise FileReadError(f"Error listing directory: {e}") from e

    def get_file_info(self, path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get information about a file or directory.

        Args:
            path (Union[str, Path]): Path to the file or directory.

        Returns:
            Dict[str, Any]: Dictionary containing file information.

        Raises:
            FileReadError: If the file information cannot be read.
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            logger.error("Path does not exist: %s", file_path)
            raise FileReadError(str(file_path), "Path not found")

        try:
            stat_result = file_path.stat()

            # Calculate file hash for regular files
            file_hash = None
            if file_path.is_file() and file_path.suffix.lower() != ".enc":
                try:
                    file_hash = self.calculate_file_hash(file_path)
                except (IOError, FileNotFoundError) as e:
                    logger.error(
                        "Error calculating file hash for %s: %s", file_path, e)
                    # Don't fail if hash calculation fails

            return {
                "path": str(file_path),
                "name": file_path.name,
                "size": stat_result.st_size,
                "is_file": file_path.is_file(),
                "is_dir": file_path.is_dir(),
                "created": datetime.fromtimestamp(stat_result.st_ctime),
                "modified": datetime.fromtimestamp(stat_result.st_mtime),
                "accessed": datetime.fromtimestamp(stat_result.st_atime),
                "extension": file_path.suffix.lower() if file_path.is_file() else None,
                "hash": file_hash,
            }
        except Exception as e:
            logger.error(
                "Error getting file info for %s: %s", file_path, e)
            raise FileReadError(f"Error getting file info: {e}") from e

    def calculate_file_hash(
        self, path: Union[str, Path], algorithm: str = "sha256"
    ) -> str:
        """
        Calculate a hash of the file content.

        Args:
            path (Union[str, Path]): Path to the file.
            algorithm (str): Hash algorithm to use.

        Returns:
            str: Hexadecimal hash of the file content.

        Raises:
            FileReadError: If the file cannot be read.
            ValueError: If the algorithm is not supported.
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            logger.error("File does not exist: %s", file_path)
            raise FileReadError(str(file_path), "File not found")

        if not file_path.is_file():
            logger.error("Path is not a file: %s", file_path)
            raise FileReadError(str(file_path), "Not a file")

        # Check if the algorithm is supported
        try:
            hasher = getattr(hashlib, algorithm)()
        except AttributeError:
            logger.error("Unsupported hash algorithm: %s", algorithm)
            raise ValueError(
                f"Unsupported hash algorithm: {algorithm}") from AttributeError

        try:
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error("Error calculating hash for %s: %s", file_path, e)
            raise FileReadError(
                str(file_path), f"Error calculating hash: {e}") from e

    def get_temp_file(
        self,
        suffix: Optional[str] = None,
        prefix: Optional[str] = None,
        dir: Optional[Union[str, Path]] = None,
    ) -> tuple[Path, Callable[[], None]]:
        """
        Create a temporary file.

        Args:
            suffix (str, optional): File suffix.
            prefix (str, optional): File prefix.
            dir (Union[str, Path], optional): Directory for the temporary file.

        Returns:
            tuple[Path, Callable[[], None]]: Path to the temporary file and a cleanup function.
        """
        if dir:
            dir_path = self._resolve_path(dir)
            self.ensure_dir(dir_path)
            dir_str = str(dir_path)
        else:
            dir_str = None

        try:
            fd, temp_path = tempfile.mkstemp(
                suffix=suffix, prefix=prefix, dir=dir_str)
            os.close(fd)  # Close the file descriptor

            # Create a cleanup function
            def cleanup():
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass

            logger.debug("Temporary file created: %s", temp_path)
            return Path(temp_path), cleanup
        except Exception as e:
            logger.error("Error creating temporary file: %s", e)
            raise FileWriteError(
                "temp file", f"Error creating temporary file: {e}")

    def get_temp_dir(
        self,
        suffix: Optional[str] = None,
        prefix: Optional[str] = None,
        dir: Optional[Union[str, Path]] = None,
    ) -> tuple[Path, Callable[[], None]]:
        """
        Create a temporary directory.

        Args:
            suffix (str, optional): Directory suffix.
            prefix (str, optional): Directory prefix.
            dir (Union[str, Path], optional): Parent directory.

        Returns:
            tuple[Path, Callable[[], None]]: Path to the temporary directory and a cleanup function.
        """
        if dir:
            dir_path = self._resolve_path(dir)
            self.ensure_dir(dir_path)
            dir_str = str(dir_path)
        else:
            dir_str = None

        try:
            temp_dir = tempfile.mkdtemp(
                suffix=suffix, prefix=prefix, dir=dir_str)

            # Create a cleanup function
            def cleanup():
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                except:
                    pass

            logger.debug("Temporary directory created: %s", temp_dir)
            return Path(temp_dir), cleanup
        except Exception as e:
            logger.error("Error creating temporary directory: %s", e)
            raise FileWriteError(
                "temp directory", f"Error creating temporary directory: {e}"
            )


class SafeFileWriter:
    """
    Utility class for safe file operations with locking.

    Prevents race conditions when multiple processes or threads
    try to write to the same file.
    """

    # Class variable for file locks
    _file_locks = {}
    _lock = threading.RLock()

    @classmethod
    def get_lock(cls, file_path: str) -> threading.RLock:
        """
        Get a lock for a specific file path.

        Args:
            file_path (str): Path to the file.

        Returns:
            threading.RLock: Lock for the file.
        """
        with cls._lock:
            if file_path not in cls._file_locks:
                cls._file_locks[file_path] = threading.RLock()
            return cls._file_locks[file_path]

    @classmethod
    def safe_write(
        cls,
        path: Union[str, Path],
        content: Union[str, bytes],
        mode: str = "w",
        encoding: Optional[str] = "utf-8",
        make_backup: bool = False,
    ) -> None:
        """
        Write to a file safely with locking.

        Args:
            path (Union[str, Path]): Path to the file.
            content (Union[str, bytes]): Content to write.
            mode (str): File mode ('w' or 'wb').
            encoding (str, optional): Character encoding to use.
            make_backup (bool): Whether to make a backup of the existing file.

        Raises:
            FileWriteError: If the file cannot be written.
        """
        path_str = str(path)
        lock = cls.get_lock(path_str)

        with lock:
            try:
                # Create parent directory if it doesn't exist
                os.makedirs(os.path.dirname(
                    os.path.abspath(path_str)), exist_ok=True)

                # Make backup if requested
                if make_backup and os.path.exists(path_str):
                    backup_path = (
                        f"{path_str}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    )
                    shutil.copy2(path_str, backup_path)

                # Write to a temporary file
                temp_path = f"{path_str}.tmp.{int(time.time())}"
                kwargs = {
                    "encoding": encoding} if "b" not in mode and encoding else {}

                with open(temp_path, mode, **kwargs) as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data is written to disk

                # Replace the original file with the temporary file
                os.replace(temp_path, path_str)

                logger.debug("File written safely: %s", path_str)
            except Exception as e:
                logger.error("Error writing file %s: %s", path_str, e)
                # Clean up temporary file if it exists
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                raise FileWriteError(path_str, str(e))
