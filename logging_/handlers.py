"""
Logging Handlers Module

This module provides various logging handlers for directing logs to different outputs
such as files, console, and remote destinations. It supports features like log rotation,
compression, and error handling to ensure reliable logging in various scenarios.

Handlers Provided:
- SafeRotatingFileHandler: Enhanced RotatingFileHandler with error handling and fallback
- MultiProcessSafeTimedRotatingFileHandler: TimedRotatingFileHandler for multi-process safety
- CompressedRotatingFileHandler: Rotating handler that compresses old logs
- CustomStreamHandler: Stream handler with custom formatting and colors
- BufferingHandler: Handler that buffers logs and flushes periodically
- HTTPHandler: Handler for sending logs to a HTTP server
- SocketHandler: Handler for sending logs over a socket connection
- SysLogHandler: Handler for sending logs to a remote syslog server
"""

import os
import sys
import logging
import logging.handlers
import gzip
import shutil
import time
import multiprocessing
import socket


class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    Enhanced RotatingFileHandler with error handling and fallback.

    If there's an error writing to the log file, it will fallback to writing to
    a fallback stream (default is sys.stderr).
    """

    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None,
                 delay=False, fallback_stream=sys.stderr):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self.fallback_stream = fallback_stream

    def handleError(self, record):
        """
        Handle errors which occur during an emit() call.

        If there's an error, fallback to writing the log record to the fallback stream.
        """
        try:
            if self.fallback_stream:
                # Fallback to writing to the fallback stream
                msg = self.format(record)
                self.fallback_stream.write(msg + self.terminator)
                self.fallback_stream.flush()
        except (IOError, ValueError):
            pass  # Ignore any errors in the fallback


class MultiProcessSafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    TimedRotatingFileHandler that's safe for use in a multi-processing environment.

    This handler uses a multiprocessing lock to ensure that only one process can
    write to the log file at a time, preventing file corruption.
    """

    def __init__(self, filename, when='h', interval=1, backupCount=0, encoding=None,
                 delay=False, utc=False):
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc)
        self._lock = multiprocessing.Lock()

    def doRollover(self):
        """
        Do a rollover, as described in TimedRotatingFileHandler.

        This method is modified to acquire a multiprocessing lock before doing the rollover.
        """
        with self._lock:
            super().doRollover()

    def emit(self, record):
        """
        Emit a record.

        This method is modified to acquire a multiprocessing lock before emitting the record.
        """
        with self._lock:
            super().emit(record)


class CompressedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    Rotating file handler that compresses old log files using gzip.

    When a rollover occurs, the old log file is compressed with gzip and renamed
    with a .gz extension.
    """

    def doRollover(self):
        """
        Do a rollover, as described in RotatingFileHandler.

        This method is modified to compress the old log file after rolling over.
        """
        super().doRollover()

        # Compress the old log file
        old_log = self.baseFilename + ".1"
        with open(old_log, 'rb') as f_in:
            with gzip.open(old_log + '.gz', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove the old uncompressed log file
        os.remove(old_log)


class CustomStreamHandler(logging.StreamHandler):
    """
    Stream handler with custom formatting and colors.

    This handler allows customizing the log record format and supports adding
    colors to the output based on the log level.
    """

    def __init__(self, stream=None, fmt=None, datefmt=None, style='%',
                 use_colors=True, colors=None):
        super().__init__(stream)

        if fmt is None:
            fmt = "%(asctime)s [%(levelname)s] %(message)s"

        if style not in ('%', '{', '$'):
            raise ValueError(
                f"Invalid style '{style}' - must be '%', '{{' or '$'")

        self.use_colors = use_colors

        default_colors = {
            'DEBUG': '\033[94m',  # Blue
            'INFO': '\033[92m',   # Green
            'WARNING': '\033[93m',  # Yellow
            'ERROR': '\033[91m',  # Red
            'CRITICAL': '\033[95m'  # Magenta
        }
        self.colors = colors or default_colors

        # Create formatter with the specified format, date format and style
        self.formatter = logging.Formatter(fmt, datefmt, style)

    def format(self, record):
        """
        Format the specified record.

        If colors are enabled, adds the corresponding color to the formatted output
        based on the log level.
        """
        formatted = self.formatter.format(record)

        if self.use_colors:
            level_color = self.colors.get(record.levelname, '')
            formatted = level_color + formatted + '\033[0m'

        return formatted


class BufferingHandler(logging.handlers.BufferingHandler):
    """
    Handler that buffers logs and flushes them periodically.

    This handler accumulates log records in a buffer and flushes them to the
    underlying handler periodically based on the specified criteria (e.g., number
    of buffered records or time interval).
    """

    def __init__(self, capacity=1000, interval=1.0, target=None):
        super().__init__(capacity)
        self.target = target
        self.interval = interval
        self.last_flush_time = time.time()

    def shouldFlush(self, record):
        """
        Check if buffer should be flushed.

        Flushes the buffer if the number of buffered records exceeds the capacity
        or if the time since last flush exceeds the specified interval.
        """
        if len(self.buffer) >= self.capacity:
            return True

        current_time = time.time()
        if current_time - self.last_flush_time >= self.interval:
            self.last_flush_time = current_time
            return True

        return False

    def flush(self):
        """
        Flush the buffered records to the underlying handler.
        """
        self.acquire()
        try:
            if self.target:
                for record in self.buffer:
                    self.target.handle(record)
                self.buffer.clear()
        finally:
            self.release()


class HTTPHandler(logging.handlers.HTTPHandler):
    """
    Handler that sends logs to a HTTP server.

    This handler sends log records as HTTP POST requests to a specified URL.
    It supports SSL encryption and basic authentication.
    """

    def __init__(self, host, url, method="POST", secure=False, credentials=None,
                 context=None):
        super().__init__(host, url, method, secure, credentials, context)

    def mapLogRecord(self, record):
        """
        Default implementation of mapping the log record into a dict.

        This method can be overridden to customize the log record format sent to
        the HTTP server.
        """
        return {
            'name': record.name,
            'level': record.levelname,
            'path': record.pathname,
            'lineno': record.lineno,
            'message': record.getMessage(),
            'time': record.created
        }


class SocketHandler(logging.handlers.SocketHandler):
    """
    Handler that sends logs over a socket connection.

    This handler sends pickled LogRecord objects to a network socket. It supports
    sending logs over TCP or UDP to a specified host and port.
    """

    def __init__(self, host, port):
        # pylint: disable=useless-super-delegation
        super().__init__(host, port)

    def makeSocket(self, timeout=1):
        """
        Create a socket that can be used for logging.

        Overridden to specify the socket type based on the port number. If the
        port is None, a UDP socket will be created. Otherwise, a TCP socket will
        be created.
        """
        if self.port is None:
            family = socket.AF_INET
            type_ = socket.SOCK_DGRAM  # UDP
        else:
            family = socket.AF_INET
            type_ = socket.SOCK_STREAM  # TCP

        return socket.socket(family, type_)


class SysLogHandler(logging.handlers.SysLogHandler):
    """
    Handler that sends logs to a remote syslog server.

    This handler sends logs to a remote syslog server over UDP. It supports
    specifying the syslog facility and adding a PID to the log message.
    """

    def __init__(self, address=('localhost', logging.handlers.SYSLOG_UDP_PORT),
                 facility=logging.handlers.SysLogHandler.LOG_USER, socktype=None,
                 include_pid=False):
        super().__init__(address, facility, socktype)
        self.include_pid = include_pid

    def format(self, record):
        """
        Format the log record.

        Overridden to add the PID to the message if include_pid is set to True.
        """
        formatted = super().format(record)

        if self.include_pid:
            formatted = f"[{os.getpid()}] {formatted}"

        return formatted
