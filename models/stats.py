"""
Stats Module

This module provides models and utilities for tracking and analyzing performance metrics,
operation statistics, and error tracking within the Telegram Account Manager application.

Features:
- OperationStats: Tracks success/failure rates for operations
- PerformanceMetrics: Monitors execution times and resource usage
- ErrorStats: Aggregates error frequency and patterns
- AccountStats: Collects account-specific performance data
- MetricsExporter: Exports statistics in various formats (JSON, CSV)
- MetricsCollector: Centralized collection of metrics from different sources
- TimeSeriesData: Stores time-based metrics for trend analysis
"""

import os
import json
import csv
import time
import logging
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Union, Tuple
import threading
from collections import defaultdict, deque, Counter

try:
    from data.base_file_manager import FileManager, FileReadError, FileWriteError
    from data.json_file_manager import JsonFileManager
except ImportError:
    # For development, define placeholder classes if not available
    class FileReadError(Exception):
        """Raised when a file cannot be read."""
        pass

    class FileWriteError(Exception):
        """Raised when a file cannot be written."""
        pass

    class FileManager:
        """Placeholder for FileManager."""

        def __init__(self, base_dir=None):
            self.base_dir = base_dir or os.getcwd()

    class JsonFileManager(FileManager):
        """Placeholder for JsonFileManager."""

        def read_json(self, path, default=None):
            return default or {}

        def write_json(self, path, data, make_backup=False):
            pass

    def get_logger(name):
        return logging.getLogger(name)

# Setup logger
logger = get_logger("Stats")

# pylint: disable=missing-class-docstring


class MetricType(Enum):
    COUNTER = auto()
    GAUGE = auto()
    TIMER = auto()
    HISTOGRAM = auto()
    DISTRIBUTION = auto()

# pylint: disable=missing-class-docstring


class OperationType(Enum):
    MEMBER_ADD = auto()
    MEMBER_EXTRACT = auto()
    ACCOUNT_VERIFY = auto()
    GROUP_JOIN = auto()
    SESSION_START = auto()
    API_REQUEST = auto()
    FILE_OPERATION = auto()
    OTHER = auto()

    @classmethod
    # pylint: disable=missing-function-docstring
    def to_str(cls, op_type):
        type_map = {
            cls.MEMBER_ADD: "member_add",
            cls.MEMBER_EXTRACT: "member_extract",
            cls.ACCOUNT_VERIFY: "account_verify",
            cls.GROUP_JOIN: "group_join",
            cls.SESSION_START: "session_start",
            cls.API_REQUEST: "api_request",
            cls.FILE_OPERATION: "file_operation",
            cls.OTHER: "other"
        }
        return type_map.get(op_type, "unknown")

    @classmethod
    # pylint: disable=missing-function-docstring
    def from_str(cls, op_type_str):
        type_map = {
            "member_add": cls.MEMBER_ADD,
            "member_extract": cls.MEMBER_EXTRACT,
            "account_verify": cls.ACCOUNT_VERIFY,
            "group_join": cls.GROUP_JOIN,
            "session_start": cls.SESSION_START,
            "api_request": cls.API_REQUEST,
            "file_operation": cls.FILE_OPERATION,
            "other": cls.OTHER
        }
        return type_map.get(op_type_str.lower(), cls.OTHER)

# pylint: disable=missing-class-docstring


class OperationStats:
    def __init__(self, operation_type: OperationType):
        self.operation_type = operation_type
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.last_operation_time = None
        self.last_success_time = None
        self.last_failure_time = None
        self.last_error = None
        self.error_counts = Counter()
        self.time_distribution = []
        self.recent_operations = deque(maxlen=100)
        self.hourly_stats = defaultdict(
            lambda: {"total": 0, "success": 0, "failure": 0})
        self.daily_stats = defaultdict(
            lambda: {"total": 0, "success": 0, "failure": 0})

# pylint: disable=missing-function-docstring
    def record_operation(self, success: bool, duration_ms: float, error_type: str = None,
                         details: Dict[str, Any] = None):
        self.total_operations += 1
        self.last_operation_time = datetime.now()

        if success:
            self.successful_operations += 1
            self.last_success_time = self.last_operation_time
        else:
            self.failed_operations += 1
            self.last_failure_time = self.last_operation_time
            if error_type:
                self.last_error = error_type
                self.error_counts[error_type] += 1

        self.time_distribution.append(duration_ms)

        # Record for time-based stats
        hour_key = self.last_operation_time.strftime("%Y-%m-%d %H:00")
        day_key = self.last_operation_time.strftime("%Y-%m-%d")

        self.hourly_stats[hour_key]["total"] += 1
        self.daily_stats[day_key]["total"] += 1

        if success:
            self.hourly_stats[hour_key]["success"] += 1
            self.daily_stats[day_key]["success"] += 1
        else:
            self.hourly_stats[hour_key]["failure"] += 1
            self.daily_stats[day_key]["failure"] += 1

        # Record operation details
        operation_record = {
            "timestamp": self.last_operation_time.isoformat(),
            "success": success,
            "duration_ms": duration_ms,
            "error_type": error_type if not success else None
        }

        if details:
            operation_record["details"] = details

# pylint: disable=missing-function-docstring
        self.recent_operations.append(operation_record)

# pylint: disable=missing-function-docstring
    def get_success_rate(self) -> float:
        if self.total_operations == 0:
            return 0.0
        return (self.successful_operations / self.total_operations) * 100

# pylint: disable=missing-function-docstring
    def get_failure_rate(self) -> float:
        if self.total_operations == 0:
            return 0.0
        return (self.failed_operations / self.total_operations) * 100

# pylint: disable=missing-function-docstring
    def get_average_duration(self) -> float:
        if not self.time_distribution:
            return 0.0
        return sum(self.time_distribution) / len(self.time_distribution)

# pylint: disable=missing-function-docstring
    def get_median_duration(self) -> float:
        if not self.time_distribution:
            return 0.0
        sorted_times = sorted(self.time_distribution)
        n = len(sorted_times)
        if n % 2 == 0:
            return (sorted_times[n//2 - 1] + sorted_times[n//2]) / 2
        else:
            return sorted_times[n//2]

    def get_common_errors(self, limit: int = 5) -> List[Tuple[str, int]]:
        return self.error_counts.most_common(limit)

    def get_time_series_data(self, by: str = 'hour', last_n: int = 24) -> Dict[str, Dict]:
        if by.lower() == 'hour':
            data_source = self.hourly_stats
        else:
            data_source = self.daily_stats

        # Sort keys by time (latest first)
        sorted_keys = sorted(data_source.keys(), reverse=True)

        # Take the last N periods
        selected_keys = sorted_keys[:last_n]

        # Create time series data
        time_series = {}
        for key in sorted(selected_keys):
            time_series[key] = data_source[key]

        return time_series

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_type": OperationType.to_str(self.operation_type),
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "success_rate": self.get_success_rate(),
            "last_operation_time": (
                self.last_operation_time.isoformat() if self.last_operation_time else None
            ),
            "last_success_time": (
                self.last_success_time.isoformat()
                if self.last_success_time
                else None
            ),
            "last_failure_time": (
                self.last_failure_time.isoformat()
                if self.last_failure_time
                else None
            ),
            "average_duration_ms": self.get_average_duration(),
            "median_duration_ms": self.get_median_duration(),
            "common_errors": dict(self.get_common_errors()),
            "recent_operations": list(self.recent_operations)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OperationStats':
        operation_type = OperationType.from_str(
            data.get("operation_type", "other"))
        stats = cls(operation_type)

        stats.total_operations = data.get("total_operations", 0)
        stats.successful_operations = data.get("successful_operations", 0)
        stats.failed_operations = data.get("failed_operations", 0)

        if data.get("last_operation_time"):
            stats.last_operation_time = datetime.fromisoformat(
                data["last_operation_time"])

        if data.get("last_success_time"):
            stats.last_success_time = datetime.fromisoformat(
                data["last_success_time"])

        if data.get("last_failure_time"):
            stats.last_failure_time = datetime.fromisoformat(
                data["last_failure_time"])

        stats.last_error = data.get("last_error")
        stats.error_counts = Counter(data.get("common_errors", {}))

        # Reconstruct time distribution (if available)
        if "time_distribution" in data:
            stats.time_distribution = data["time_distribution"]

        # Reconstruct recent operations
        if "recent_operations" in data:
            stats.recent_operations = deque(
                data["recent_operations"], maxlen=100)

        # Reconstruct hourly and daily stats
        if "hourly_stats" in data:
            for hour, hour_data in data["hourly_stats"].items():
                stats.hourly_stats[hour] = hour_data

        if "daily_stats" in data:
            for day, day_data in data["daily_stats"].items():
                stats.daily_stats[day] = day_data

        return stats


class PerformanceMetrics:
    def __init__(self, name: str):
        self.name = name
        self.start_time = datetime.now()
        self.metrics = defaultdict(list)
        self.counters = defaultdict(int)
        self.gauges = {}
        self.timers = {}
        self.histograms = defaultdict(list)
        self.dimensions = {}
        self.active_timers = {}

# pylint: disable=missing-function-docstring
    def set_dimension(self, key: str, value: Any) -> None:
        self.dimensions[key] = value

# pylint: disable=missing-function-docstring
    def increment_counter(self, name: str, value: int = 1,
                          dimensions: Dict[str, Any] = None) -> None:
        self.counters[name] += value

        if dimensions:
            # Create a unique key for this counter with these dimensions
            dim_key = f"{name}:{self._format_dimensions(dimensions)}"
            self.counters[dim_key] += value

    def set_gauge(self, name: str, value: float,
                  dimensions: Dict[str, Any] = None) -> None:
        self.gauges[name] = value

        if dimensions:
            # Create a unique key for this gauge with these dimensions
            dim_key = f"{name}:{self._format_dimensions(dimensions)}"
            self.gauges[dim_key] = value

    def start_timer(self, name: str, dimensions: Dict[str, Any] = None) -> str:
        timer_id = f"{name}:{time.time()}:{id(threading.current_thread())}"
        timer_data = {
            "start_time": time.time(),
            "name": name,
            "dimensions": dimensions or {}
        }
        self.active_timers[timer_id] = timer_data
        return timer_id

    def stop_timer(self, timer_id: str) -> float:
        if timer_id not in self.active_timers:
            logger.warning("Timer %s not found", timer_id)
            return 0.0

        stop_time = time.time()
        timer_data = self.active_timers.pop(timer_id)
        duration_ms = (stop_time - timer_data["start_time"]) * 1000

        name = timer_data["name"]
        dimensions = timer_data["dimensions"]

        # Record the timer
        self.timers.setdefault(name, []).append(duration_ms)

        if dimensions:
            # Create a unique key for this timer with these dimensions
            dim_key = f"{name}:{self._format_dimensions(dimensions)}"
            self.timers.setdefault(dim_key, []).append(duration_ms)

        return duration_ms

    def record_histogram(self, name: str, value: float,
                         dimensions: Dict[str, Any] = None) -> None:
        self.histograms[name].append(value)

        if dimensions:
            # Create a unique key for this histogram with these dimensions
            dim_key = f"{name}:{self._format_dimensions(dimensions)}"
            self.histograms[dim_key].append(value)

    def _format_dimensions(self, dimensions: Dict[str, Any]) -> str:
        return ",".join(f"{k}={v}" for k, v in sorted(dimensions.items()))

    def get_counter(self, name: str) -> int:
        return self.counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        return self.gauges.get(name, 0.0)

    def get_timer_stats(self, name: str) -> Dict[str, float]:
        timer_values = self.timers.get(name, [])
        if not timer_values:
            return {
                "count": 0,
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p50": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0
            }

        sorted_values = sorted(timer_values)
        count = len(sorted_values)

        return {
            "count": count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(sorted_values) / count,
            "p50": self._percentile(sorted_values, 50),
            "p90": self._percentile(sorted_values, 90),
            "p95": self._percentile(sorted_values, 95),
            "p99": self._percentile(sorted_values, 99)
        }

    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        histogram_values = self.histograms.get(name, [])
        if not histogram_values:
            return {
                "count": 0,
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p50": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0
            }

        sorted_values = sorted(histogram_values)
        count = len(sorted_values)

        return {
            "count": count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(sorted_values) / count,
            "p50": self._percentile(sorted_values, 50),
            "p90": self._percentile(sorted_values, 90),
            "p95": self._percentile(sorted_values, 95),
            "p99": self._percentile(sorted_values, 99)
        }

    def _percentile(self, sorted_values: List[float], percentile: int) -> float:
        n = len(sorted_values)
        if n == 0:
            return 0.0

        k = (n - 1) * percentile / 100
        f = int(k)
        c = int(k) + 1 if k < n - 1 else int(k)

        if f == c:
            return sorted_values[f]
        d0 = sorted_values[f] * (c - k)
        d1 = sorted_values[c] * (k - f)
        return d0 + d1

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "dimensions": self.dimensions,
            "counters": dict(self.counters),
            "gauges": self.gauges,
        }

        # Calculate timer statistics
        timer_stats = {}
        for timer_name in self.timers:
            timer_stats[timer_name] = self.get_timer_stats(timer_name)
        result["timers"] = timer_stats

        # Calculate histogram statistics
        histogram_stats = {}
        for hist_name in self.histograms:
            histogram_stats[hist_name] = self.get_histogram_stats(hist_name)
        result["histograms"] = histogram_stats

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PerformanceMetrics':
        name = data.get("name", "unknown")
        metrics = cls(name)

        # Reconstruct basic properties
        if data.get("start_time"):
            metrics.start_time = datetime.fromisoformat(data["start_time"])

        metrics.dimensions = data.get("dimensions", {})
        metrics.counters = defaultdict(int, data.get("counters", {}))
        metrics.gauges = data.get("gauges", {})

        # Reconstruct timers (only the raw values, not the statistics)
        if "timers_raw" in data:
            for timer_name, timer_values in data["timers_raw"].items():
                metrics.timers[timer_name] = timer_values

        # Reconstruct histograms (only the raw values, not the statistics)
        if "histograms_raw" in data:
            for hist_name, hist_values in data["histograms_raw"].items():
                metrics.histograms[hist_name] = hist_values

        return metrics


class ErrorStats:
    def __init__(self):
        self.total_errors = 0
        self.error_counts = Counter()
        self.error_by_module = defaultdict(Counter)
        self.error_by_operation = defaultdict(Counter)
        self.error_timestamps = defaultdict(list)
        self.recent_errors = deque(maxlen=100)
        self.hourly_errors = defaultdict(Counter)
        self.daily_errors = defaultdict(Counter)

# pylint: disable=missing-function-docstring
    def record_error(self, error_type: str, module: str = None,
                     operation: str = None, details: Dict[str, Any] = None) -> None:
        self.total_errors += 1
        timestamp = datetime.now()

        # Update general error count
        self.error_counts[error_type] += 1

        # Update module-specific counts
        if module:
            self.error_by_module[module][error_type] += 1

        # Update operation-specific counts
        if operation:
            self.error_by_operation[operation][error_type] += 1

        # Track timestamps for this error type
        self.error_timestamps[error_type].append(timestamp)

        # Update hourly and daily stats
        hour_key = timestamp.strftime("%Y-%m-%d %H:00")
        day_key = timestamp.strftime("%Y-%m-%d")

        self.hourly_errors[hour_key][error_type] += 1
        self.daily_errors[day_key][error_type] += 1

        # Record error details
        error_record = {
            "timestamp": timestamp.isoformat(),
            "error_type": error_type,
            "module": module,
            "operation": operation
        }

        if details:
            error_record["details"] = details

        self.recent_errors.append(error_record)

    def get_most_common_errors(self, limit: int = 10) -> List[Tuple[str, int]]:
        return self.error_counts.most_common(limit)

    def get_errors_by_module(self, module: str, limit: int = 10) -> List[Tuple[str, int]]:
        if module not in self.error_by_module:
            return []
        return self.error_by_module[module].most_common(limit)

    def get_errors_by_operation(self, operation: str, limit: int = 10) -> List[Tuple[str, int]]:
        if operation not in self.error_by_operation:
            return []
        return self.error_by_operation[operation].most_common(limit)

    def get_error_time_series(self, error_type: Optional[str] = None,
                              by: str = 'hour', last_n: int = 24) -> Dict[str, Dict]:
        if by.lower() == 'hour':
            data_source = self.hourly_errors
        else:
            data_source = self.daily_errors

        # Sort keys by time (latest first)
        sorted_keys = sorted(data_source.keys(), reverse=True)

        # Take the last N periods
        selected_keys = sorted_keys[:last_n]

        # Create time series data
        time_series = {}
        for key in sorted(selected_keys):
            if error_type:
                time_series[key] = {error_type: data_source[key][error_type]}
            else:
                time_series[key] = dict(data_source[key])

        return time_series

    def get_error_rate(self, total_operations: int) -> float:
        if total_operations == 0:
            return 0.0
        return (self.total_errors / total_operations) * 100

    def get_error_frequency(self, error_type: str, time_window: int = 3600) -> float:
        if error_type not in self.error_timestamps:
            return 0.0

        now = datetime.now()
        cutoff = now - timedelta(seconds=time_window)

        # Count errors within the time window
        recent_errors = [
            ts for ts in self.error_timestamps[error_type] if ts >= cutoff]

        # Calculate frequency (errors per hour)
        return len(recent_errors) * 3600 / time_window

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_errors": self.total_errors,
            "error_counts": dict(self.error_counts),
            "error_by_module": {
                module: dict(counts)
                for module, counts in self.error_by_module.items()
            },
            "error_by_operation": {
                op: dict(counts)
                for op, counts in self.error_by_operation.items()
            },
            "recent_errors": list(self.recent_errors),
            "hourly_errors": {hour: dict(counts) for hour, counts in self.hourly_errors.items()},
            "daily_errors": {day: dict(counts) for day, counts in self.daily_errors.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorStats':
        stats = cls()

        stats.total_errors = data.get("total_errors", 0)
        stats.error_counts = Counter(data.get("error_counts", {}))

        # Reconstruct error_by_module
        for module, counts in data.get("error_by_module", {}).items():
            stats.error_by_module[module] = Counter(counts)

        # Reconstruct error_by_operation
        for operation, counts in data.get("error_by_operation", {}).items():
            stats.error_by_operation[operation] = Counter(counts)

        # Reconstruct error timestamps (if available)
        if "error_timestamps" in data:
            for error_type, timestamps in data["error_timestamps"].items():
                stats.error_timestamps[error_type] = [
                    datetime.fromisoformat(ts) for ts in timestamps
                ]

        # Reconstruct recent errors
        if "recent_errors" in data:
            stats.recent_errors = deque(data["recent_errors"], maxlen=100)

        # Reconstruct hourly and daily errors
        for hour, counts in data.get("hourly_errors", {}).items():
            stats.hourly_errors[hour] = Counter(counts)

        for day, counts in data.get("daily_errors", {}).items():
            stats.daily_errors[day] = Counter(counts)

        return stats


class AccountStats:
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.phone = None
        self.created_at = datetime.now()
        self.last_active = None
        self.operations = defaultdict(int)
        self.successful_operations = defaultdict(int)
        self.failed_operations = defaultdict(int)
        self.members_added = 0
        self.members_extracted = 0
        self.daily_stats = defaultdict(lambda: defaultdict(int))
        self.error_counts = Counter()
        self.cooldown_periods = []
        self.performance_metrics = {}
        self.success_rate_history = []
        self.total_uptime_seconds = 0
        self.total_cooldown_seconds = 0

# pylint: disable=missing-function-docstring
    def set_phone(self, phone: str) -> None:
        self.phone = phone

    def record_activity(self, operation_type: OperationType,
                        success: bool, duration_ms: float = 0,
                        error_type: str = None, details: Dict[str, Any] = None) -> None:
        timestamp = datetime.now()
        self.last_active = timestamp

        operation_str = OperationType.to_str(operation_type)
        self.operations[operation_str] += 1

        if success:
            self.successful_operations[operation_str] += 1
        else:
            self.failed_operations[operation_str] += 1
            if error_type:
                self.error_counts[error_type] += 1

        # Update daily stats
        day_key = timestamp.strftime("%Y-%m-%d")
        self.daily_stats[day_key]["operations"] += 1
        self.daily_stats[day_key][f"{operation_str}_operations"] += 1

        if success:
            self.daily_stats[day_key]["successful_operations"] += 1
            self.daily_stats[day_key][f"{operation_str}_successful"] += 1
        else:
            self.daily_stats[day_key]["failed_operations"] += 1
            self.daily_stats[day_key][f"{operation_str}_failed"] += 1

        # Update members added/extracted counters
        if operation_type == OperationType.MEMBER_ADD and success:
            self.members_added += 1
            self.daily_stats[day_key]["members_added"] += 1
        elif operation_type == OperationType.MEMBER_EXTRACT and success:
            self.members_extracted += 1
            self.daily_stats[day_key]["members_extracted"] += 1

        # Store performance metric
        if duration_ms > 0:
            metric_key = f"{operation_str}_duration"
            if metric_key not in self.performance_metrics:
                self.performance_metrics[metric_key] = []
            self.performance_metrics[metric_key].append(duration_ms)

        # Update success rate history (weekly calculation)
        week_number = timestamp.isocalendar()[1]
        year = timestamp.year
        week_key = f"{year}-W{week_number:02d}"

        # Find or create entry for this week
        week_entry = None
        for entry in self.success_rate_history:
            if entry["period"] == week_key:
                week_entry = entry
                break

        if not week_entry:
            week_entry = {
                "period": week_key,
                "operations": 0,
                "successful": 0,
                "rate": 0.0
            }
            self.success_rate_history.append(week_entry)

        # Update the entry
        week_entry["operations"] += 1
        if success:
            week_entry["successful"] += 1

        # Recalculate rate
        if week_entry["operations"] > 0:
            week_entry["rate"] = (
                week_entry["successful"] / week_entry["operations"]) * 100

    def record_cooldown(self, start_time: datetime, end_time: datetime = None,
                        reason: str = None) -> None:
        if end_time is None:
            # Ongoing cooldown (to be updated later)
            end_time = datetime.max

        cooldown_record = {
            "start": start_time.isoformat(),
            "end": end_time.isoformat() if end_time != datetime.max else None,
            "reason": reason,
            "duration_seconds": (
                (end_time - start_time).total_seconds()
                if end_time != datetime.max
                else None
            )
        }

        self.cooldown_periods.append(cooldown_record)

        if end_time != datetime.max:
            self.total_cooldown_seconds += (end_time -
                                            start_time).total_seconds()

    def update_cooldown(self, index: int, end_time: datetime) -> None:
        if index < 0 or index >= len(self.cooldown_periods):
            logger.warning(
                "Invalid cooldown index for account %s: %s", self.account_id, index)
            return

        cooldown_record = self.cooldown_periods[index]

        if cooldown_record["end"] is not None:
            logger.warning(
                "Cooldown for account %s already has an end time", self.account_id)
            return

        start_time = datetime.fromisoformat(cooldown_record["start"])
        duration_seconds = (end_time - start_time).total_seconds()

        cooldown_record["end"] = end_time.isoformat()
        cooldown_record["duration_seconds"] = duration_seconds

        self.total_cooldown_seconds += duration_seconds

    def get_success_rate(self, operation_type: Optional[OperationType] = None) -> float:
        if operation_type:
            operation_str = OperationType.to_str(operation_type)
            total = self.operations.get(operation_str, 0)
            successful = self.successful_operations.get(operation_str, 0)
        else:
            total = sum(self.operations.values())
            successful = sum(self.successful_operations.values())

        if total == 0:
            return 0.0

        return (successful / total) * 100

    def get_daily_stats(self, day: Optional[str] = None) -> Dict[str, int]:
        if day:
            return dict(self.daily_stats.get(day, {}))

        # If no specific day, get stats for today
        today = datetime.now().strftime("%Y-%m-%d")
        return dict(self.daily_stats.get(today, {}))

    def get_weekly_stats(self) -> Dict[str, Dict[str, int]]:
        today = datetime.now()
        result = {}

        # Get data for the last 7 days
        for i in range(7):
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            result[day] = dict(self.daily_stats.get(day, {}))

        return result

    def get_common_errors(self, limit: int = 5) -> List[Tuple[str, int]]:
        return self.error_counts.most_common(limit)

    def get_average_performance(self, operation_type: OperationType) -> Dict[str, float]:
        operation_str = OperationType.to_str(operation_type)
        metric_key = f"{operation_str}_duration"

        if metric_key not in self.performance_metrics or not self.performance_metrics[metric_key]:
            return {
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p90": 0.0
            }

        values = self.performance_metrics[metric_key]
        sorted_values = sorted(values)

        return {
            "avg": sum(values) / len(values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p50": sorted_values[len(sorted_values) // 2],
            "p90": sorted_values[int(len(sorted_values) * 0.9)]
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "phone": self.phone,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "operations": dict(self.operations),
            "successful_operations": dict(self.successful_operations),
            "failed_operations": dict(self.failed_operations),
            "members_added": self.members_added,
            "members_extracted": self.members_extracted,
            "daily_stats": {day: dict(stats) for day, stats in self.daily_stats.items()},
            "error_counts": dict(self.error_counts),
            "cooldown_periods": self.cooldown_periods,
            "success_rate_history": self.success_rate_history,
            "total_uptime_seconds": self.total_uptime_seconds,
            "total_cooldown_seconds": self.total_cooldown_seconds
            # Note: performance_metrics can be large, so they're not included by default
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccountStats':
        account_id = data.get("account_id", "unknown")
        stats = cls(account_id)

        stats.phone = data.get("phone")

        if data.get("created_at"):
            stats.created_at = datetime.fromisoformat(data["created_at"])

        if data.get("last_active"):
            stats.last_active = datetime.fromisoformat(data["last_active"])

        stats.operations = defaultdict(int, data.get("operations", {}))
        stats.successful_operations = defaultdict(
            int, data.get("successful_operations", {}))
        stats.failed_operations = defaultdict(
            int, data.get("failed_operations", {}))

        stats.members_added = data.get("members_added", 0)
        stats.members_extracted = data.get("members_extracted", 0)

        # Reconstruct daily stats
        for day, day_stats in data.get("daily_stats", {}).items():
            stats.daily_stats[day] = defaultdict(int, day_stats)

        stats.error_counts = Counter(data.get("error_counts", {}))
        stats.cooldown_periods = data.get("cooldown_periods", [])
        stats.success_rate_history = data.get("success_rate_history", [])
        stats.total_uptime_seconds = data.get("total_uptime_seconds", 0)
        stats.total_cooldown_seconds = data.get("total_cooldown_seconds", 0)

        return stats


class MetricsCollector:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MetricsCollector, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, stats_dir: Optional[str] = None,
                 auto_save: bool = True, save_interval: int = 300):
        with self._lock:
            if self._initialized:
                return

            self.stats_dir = stats_dir or os.path.join(os.getcwd(), "stats")
            self.auto_save = auto_save
            self.save_interval = save_interval

            # Create stats directory if it doesn't exist
            os.makedirs(self.stats_dir, exist_ok=True)

            # File manager for saving/loading stats
            self.file_manager = JsonFileManager(base_dir=self.stats_dir)

            # Stats collections
            self.operation_stats = {}
            self.performance_metrics = PerformanceMetrics("application")
            self.error_stats = ErrorStats()
            self.account_stats = {}
            self.time_series = {}

            # For aggregating operations across different parts of the app
            self.operations_by_type = {}

            # Last save time
            self.last_save_time = time.time()

            # Auto-save thread
            self._stop_auto_save = threading.Event()
            self._auto_save_thread = None

            if self.auto_save:
                self._start_auto_save()

            # Try to load existing stats
            self._load_stats()

            self._initialized = True

    def _start_auto_save(self):
        """Start the auto-save background thread."""
        self._stop_auto_save.clear()
        self._auto_save_thread = threading.Thread(
            target=self._auto_save_worker,
            daemon=True,
            name="MetricsCollector-AutoSave"
        )
        self._auto_save_thread.start()

    def _stop_auto_save_thread(self):
        """Stop the auto-save background thread."""
        if self._auto_save_thread is None or not self._auto_save_thread.is_alive():
            return

        self._stop_auto_save.set()
        self._auto_save_thread.join(timeout=2.0)
        self._auto_save_thread = None

    def _auto_save_worker(self):
        """Worker function for auto-save thread."""
        while not self._stop_auto_save.is_set():
            try:
                # Sleep for a while, checking for stop flag periodically
                for _ in range(self.save_interval * 2):  # Check twice per second
                    if self._stop_auto_save.is_set():
                        return
                    time.sleep(0.5)

                # Time to save
                with self._lock:
                    self._save_stats()
                    self.last_save_time = time.time()
            except (IOError, FileNotFoundError) as e:
                logger.error("Error in metrics auto-save worker: %s", e)
                # Don't crash the thread, just continue

    def _load_stats(self):
        """Load stats from disk."""
        try:
            # Load operation stats
            op_stats_file = os.path.join(
                self.stats_dir, "operation_stats.json")
            if os.path.exists(op_stats_file):
                op_stats_data = self.file_manager.read_json(
                    op_stats_file, default={})
                for op_type, stats_data in op_stats_data.items():
                    self.operation_stats[op_type] = OperationStats.from_dict(
                        stats_data)

            # Load performance metrics
            perf_file = os.path.join(
                self.stats_dir, "performance_metrics.json")
            if os.path.exists(perf_file):
                perf_data = self.file_manager.read_json(perf_file, default={})
                self.performance_metrics = PerformanceMetrics.from_dict(
                    perf_data)

            # Load error stats
            error_file = os.path.join(self.stats_dir, "error_stats.json")
            if os.path.exists(error_file):
                error_data = self.file_manager.read_json(
                    error_file, default={})
                self.error_stats = ErrorStats.from_dict(error_data)

            # Load account stats
            account_dir = os.path.join(self.stats_dir, "accounts")
            if os.path.exists(account_dir):
                for account_file in os.listdir(account_dir):
                    if account_file.endswith(".json"):
                        # Remove .json extension
                        account_id = account_file[:-5]
                        account_data = self.file_manager.read_json(
                            os.path.join(account_dir, account_file), default={}
                        )
                        self.account_stats[account_id] = AccountStats.from_dict(
                            account_data)

            # Load time series data
            ts_dir = os.path.join(self.stats_dir, "time_series")
            if os.path.exists(ts_dir):
                for ts_file in os.listdir(ts_dir):
                    if ts_file.endswith(".json"):
                        ts_name = ts_file[:-5]  # Remove .json extension
                        ts_data = self.file_manager.read_json(
                            os.path.join(ts_dir, ts_file), default={}
                        )
                        self.time_series[ts_name] = TimeSeriesData.from_dict(
                            ts_data)

            logger.info("Metrics loaded from disk")
        except (IOError, FileNotFoundError) as e:
            logger.error("Error loading metrics: %s", e)

    def _save_stats(self):
        """Save stats to disk."""
        try:
            # Save operation stats
            op_stats_data = {}
            for op_type, stats in self.operation_stats.items():
                op_stats_data[op_type] = stats.to_dict()

            self.file_manager.write_json(
                os.path.join(self.stats_dir, "operation_stats.json"),
                op_stats_data
            )

            # Save performance metrics
            self.file_manager.write_json(
                os.path.join(self.stats_dir, "performance_metrics.json"),
                self.performance_metrics.to_dict()
            )

            # Save error stats
            self.file_manager.write_json(
                os.path.join(self.stats_dir, "error_stats.json"),
                self.error_stats.to_dict()
            )

            # Save account stats
            account_dir = os.path.join(self.stats_dir, "accounts")
            os.makedirs(account_dir, exist_ok=True)

            for account_id, stats in self.account_stats.items():
                self.file_manager.write_json(
                    os.path.join(account_dir, f"{account_id}.json"),
                    stats.to_dict()
                )

            # Save time series data
            ts_dir = os.path.join(self.stats_dir, "time_series")
            os.makedirs(ts_dir, exist_ok=True)

            for ts_name, ts in self.time_series.items():
                self.file_manager.write_json(
                    os.path.join(ts_dir, f"{ts_name}.json"),
                    ts.to_dict()
                )

            logger.debug("Metrics saved to disk")
        except (IOError, FileNotFoundError) as e:
            logger.error("Error saving metrics: %s", e)

    def get_operation_stats(self, operation_type: OperationType) -> OperationStats:
        """Get or create operation stats for a specific operation type."""
        op_type_str = OperationType.to_str(operation_type)

        with self._lock:
            if op_type_str not in self.operation_stats:
                self.operation_stats[op_type_str] = OperationStats(
                    operation_type)

            return self.operation_stats[op_type_str]

    def record_operation(self, operation_type: OperationType, success: bool,
                         duration_ms: float, error_type: str = None,
                         details: Optional[Dict[str, Any]] = None) -> None:
        """Record an operation result."""
        with self._lock:
            # Get or create stats for this operation type
            stats = self.get_operation_stats(operation_type)

            # Record the operation
            stats.record_operation(success, duration_ms, error_type, details)

            # If there was an error, record it in error stats
            if not success and error_type:
                operation_str = OperationType.to_str(operation_type)
                self.error_stats.record_error(
                    error_type=error_type,
                    operation=operation_str,
                    details=details
                )

    def record_error(self, error_type: str, module: str = None,
                     operation: str = None, details: Optional[Dict[str, Any]] = None) -> None:
        """Record an error."""
        with self._lock:
            self.error_stats.record_error(
                error_type, module, operation, details)

    def get_account_stats(self, account_id: str) -> AccountStats:
        """Get or create account stats for a specific account."""
        with self._lock:
            if account_id not in self.account_stats:
                self.account_stats[account_id] = AccountStats(account_id)

            return self.account_stats[account_id]

    def record_account_activity(self, account_id: str, operation_type: OperationType,
                                success: bool, duration_ms: float = 0,
                                error_type: str = None,
                                details: Optional[Dict[str, Any]] = None) -> None:
        """Record account activity."""
        with self._lock:
            # Get or create account stats
            account_stats = self.get_account_stats(account_id)

            # Record the activity
            account_stats.record_activity(
                operation_type, success, duration_ms, error_type, details)

            # Also record in operation stats
            self.record_operation(operation_type, success,
                                  duration_ms, error_type, details)

    def get_time_series(self, name: str, resolution: str = 'hour') -> TimeSeriesData:
        """Get or create a time series."""
        with self._lock:
            key = f"{name}_{resolution}"

            if key not in self.time_series:
                self.time_series[key] = TimeSeriesData(name, resolution)

            return self.time_series[key]

    def record_time_series_point(self, name: str, value: Union[int, float],
                                 resolution: str = 'hour',
                                 timestamp: Optional[datetime] = None,
                                 dimensions: Optional[Dict[str, Any]] = None) -> None:
        """Record a time series data point."""
        with self._lock:
            time_series = self.get_time_series(name, resolution)
            time_series.add_point(value, timestamp, dimensions)

    def get_error_summary(self) -> Dict[str, Any]:
        """Get a summary of recent errors."""
        with self._lock:
            most_common = self.error_stats.get_most_common_errors(10)

            return {
                "total_errors": self.error_stats.total_errors,
                "most_common_errors": dict(most_common),
                "recent_errors": list(self.error_stats.recent_errors)[-10:]
            }

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of performance metrics."""
        with self._lock:
            timer_stats = {}

            for timer_name, timer_values in self.performance_metrics.timers.items():
                if len(timer_values) > 0:
                    timer_stats[timer_name] = self.performance_metrics.get_timer_stats(
                        timer_name)

            return {
                "counters": dict(self.performance_metrics.counters),
                "gauges": self.performance_metrics.gauges,
                "timers": timer_stats
            }

    def get_operation_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get a summary of operation statistics."""
        with self._lock:
            result = {}

            for op_type, stats in self.operation_stats.items():
                result[op_type] = {
                    "total": stats.total_operations,
                    "success": stats.successful_operations,
                    "failed": stats.failed_operations,
                    "success_rate": stats.get_success_rate(),
                    "avg_duration": stats.get_average_duration()
                }

            return result

    def get_account_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get a summary of account statistics."""
        with self._lock:
            result = {}

            for account_id, stats in self.account_stats.items():
                result[account_id] = {
                    "phone": stats.phone,
                    "members_added": stats.members_added,
                    "members_extracted": stats.members_extracted,
                    "success_rate": stats.get_success_rate(),
                    "last_active": stats.last_active.isoformat() if stats.last_active else None
                }

            return result

    def generate_report(self, report_format: str = 'json') -> str:
        """Generate a comprehensive report of all metrics."""
        with self._lock:
            report_data = {
                "generated_at": datetime.now().isoformat(),
                "operation_summary": self.get_operation_summary(),
                "error_summary": self.get_error_summary(),
                "performance_summary": self.get_performance_summary(),
                "account_summary": self.get_account_summary()
            }

            if report_format == 'json':
                return json.dumps(report_data, indent=2)
            elif report_format == 'csv':
                # This is a simplified CSV format focusing on operation stats
                lines = [
                    "operation_type,total,success,failed,success_rate,avg_duration"]

                for op_type, stats in report_data["operation_summary"].items():
                    line = (
                        f"{op_type},{stats['total']},{stats['success']},"
                        f"{stats['failed']},{stats['success_rate']:.2f},"
                        f"{stats['avg_duration']:.2f}"
                    )
                    lines.append(line)

                return "\n".join(lines)
            else:
                raise ValueError(f"Unsupported report format: {report_format}")

    def reset_error_stats(self) -> None:
        """Reset error statistics."""
        with self._lock:
            self.error_stats = ErrorStats()

    def save(self) -> None:
        """Manually save metrics to disk."""
        with self._lock:
            self._save_stats()
            self.last_save_time = time.time()

    def cleanup(self) -> None:
        """Clean up resources."""
        self._stop_auto_save_thread()


class MetricsExporter:
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.file_manager = JsonFileManager()

    def export_operation_stats(self, file_path: str, operation_type: Optional[OperationType] = None,
                               format: str = 'json') -> bool:
        """Export operation statistics to a file."""
        try:
            data = {}

            if operation_type:
                # Export stats for a specific operation type
                op_type_str = OperationType.to_str(operation_type)
                stats = self.metrics_collector.operation_stats.get(op_type_str)

                if stats:
                    data[op_type_str] = stats.to_dict()
            else:
                # Export all operation stats
                for op_type, stats in self.metrics_collector.operation_stats.items():
                    data[op_type] = stats.to_dict()

            if format == 'json':
                self.file_manager.write_json(file_path, data)
            elif format == 'csv':
                self._write_csv(file_path, self._flatten_operation_stats(data))
            else:
                raise ValueError(f"Unsupported format: {format}")

            return True
        except (IOError, FileNotFoundError) as e:
            logger.error("Error exporting operation stats: %s", e)
            return False

    def export_error_stats(self, file_path: str, format: str = 'json') -> bool:
        """Export error statistics to a file."""
        try:
            data = self.metrics_collector.error_stats.to_dict()

            if format == 'json':
                self.file_manager.write_json(file_path, data)
            elif format == 'csv':
                # Convert to a format suitable for CSV
                csv_data = []

                # Add most common errors
                for error_type, count in (
                    self.metrics_collector.error_stats.get_most_common_errors()
                ):
                    csv_data.append({
                        "error_type": error_type,
                        "count": count,
                        "category": "common_error"
                    })

                # Add errors by module
                for module, errors in data.get("error_by_module", {}).items():
                    for error_type, count in errors.items():
                        csv_data.append({
                            "module": module,
                            "error_type": error_type,
                            "count": count,
                            "category": "module_error"
                        })

                self._write_csv(file_path, csv_data)
            else:
                raise ValueError(f"Unsupported format: {format}")

            return True
        except (IOError, FileNotFoundError) as e:
            logger.error("Error exporting error stats: %s", e)
            return False

    def export_account_stats(self, file_path: str, account_id: Optional[str] = None,
                             format: str = 'json') -> bool:
        """Export account statistics to a file."""
        try:
            data = {}

            if account_id:
                # Export stats for a specific account
                stats = self.metrics_collector.account_stats.get(account_id)

                if stats:
                    data[account_id] = stats.to_dict()
            else:
                # Export all account stats
                for acc_id, stats in self.metrics_collector.account_stats.items():
                    data[acc_id] = stats.to_dict()

            if format == 'json':
                self.file_manager.write_json(file_path, data)
            elif format == 'csv':
                # Convert to a format suitable for CSV
                csv_data = []

                for acc_id, acc_data in data.items():
                    base_row = {
                        "account_id": acc_id,
                        "phone": acc_data.get("phone", ""),
                        "created_at": acc_data.get("created_at", ""),
                        "last_active": acc_data.get("last_active", ""),
                        "members_added": acc_data.get("members_added", 0),
                        "members_extracted": acc_data.get("members_extracted", 0),
                        "total_uptime_seconds": acc_data.get("total_uptime_seconds", 0),
                        "total_cooldown_seconds": acc_data.get("total_cooldown_seconds", 0)
                    }

                    # Add operation stats
                    for op_type, count in acc_data.get("operations", {}).items():
                        row = base_row.copy()
                        row["operation_type"] = op_type
                        row["total"] = count
                        row["successful"] = acc_data.get(
                            "successful_operations", {}).get(op_type, 0)
                        row["failed"] = acc_data.get(
                            "failed_operations", {}).get(op_type, 0)
                        csv_data.append(row)

                self._write_csv(file_path, csv_data)
            else:
                raise ValueError(f"Unsupported format: {format}")

            return True
        except (IOError, FileNotFoundError) as e:
            logger.error("Error exporting account stats: %s", e)
            return False

    def export_time_series(self, file_path: str, name: str, resolution: str = 'hour',
                           format: str = 'json') -> bool:
        """Export time series data to a file."""
        try:
            key = f"{name}_{resolution}"
            time_series = self.metrics_collector.time_series.get(key)

            if not time_series:
                logger.warning("Time series %s not found", key)
                return False

            data = time_series.to_dict()

            if format == 'json':
                self.file_manager.write_json(file_path, data)
            elif format == 'csv':
                # Convert to a format suitable for CSV
                csv_data = []

                for time_key, dim_data in data.get("data_points", {}).items():
                    for dim_key, point_data in dim_data.items():
                        dimensions = data.get(
                            "dimensions", {}).get(dim_key, {})

                        row = {
                            "timestamp": time_key,
                            "dimension": dim_key,
                            "count": point_data.get("count", 0),
                            "sum": point_data.get("sum", 0),
                            "min": point_data.get("min", 0),
                            "max": point_data.get("max", 0),
                            "avg": point_data.get("sum", 0) / point_data.get("count", 1)
                        }

                        # Add dimension values if available
                        for dim_name, dim_value in dimensions.items():
                            row[f"dim_{dim_name}"] = dim_value

                        csv_data.append(row)

                self._write_csv(file_path, csv_data)
            else:
                raise ValueError(f"Unsupported format: {format}")

            return True
        except (IOError, FileNotFoundError) as e:
            logger.error("Error exporting time series: %s", e)
            return False

    def export_full_report(self, directory: str, formats: List[str] = ['json']) -> bool:
        """Export a full report of all metrics to the specified directory."""
        try:
            os.makedirs(directory, exist_ok=True)

            success = True

            # Export operation stats
            for format in formats:
                file_path = os.path.join(
                    directory, f"operation_stats.{format}")
                if not self.export_operation_stats(file_path, format=format):
                    success = False

            # Export error stats
            for format in formats:
                file_path = os.path.join(directory, f"error_stats.{format}")
                if not self.export_error_stats(file_path, format=format):
                    success = False

            # Export account stats
            for format in formats:
                file_path = os.path.join(directory, f"account_stats.{format}")
                if not self.export_account_stats(file_path, format=format):
                    success = False

            # Export time series
            for key, time_series in self.metrics_collector.time_series.items():
                name, resolution = key.rsplit('_', 1)
                for format in formats:
                    file_path = os.path.join(
                        directory, f"time_series_{name}_{resolution}.{format}")
                    if not self.export_time_series(file_path, name, resolution, format=format):
                        success = False

            # Export summary report
            summary_report = self.metrics_collector.generate_report(
                report_format='json')
            summary_path = os.path.join(directory, "summary_report.json")
            with open(summary_path, 'w') as f:
                f.write(summary_report)

            return success
        except (IOError, FileNotFoundError) as e:
            logger.error("Error exporting full report: %s", e)
            return False

    def _write_csv(self, file_path: str, data: List[Dict[str, Any]]) -> None:
        """Write data to a CSV file."""
        if not data:
            # Create an empty CSV file
            with open(file_path, 'w') as f:
                f.write("")
            return

        # Get all keys from all dictionaries to create headers
        headers = set()
        for item in data:
            headers.update(item.keys())

        # Sort headers for consistency
        headers = sorted(headers)

        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)

    def _flatten_operation_stats(self, data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert nested operation stats data to a flat list for CSV export."""
        flattened = []

        for op_type, stats in data.items():
            row = {
                "operation_type": op_type,
                "total_operations": stats.get("total_operations", 0),
                "successful_operations": stats.get("successful_operations", 0),
                "failed_operations": stats.get("failed_operations", 0),
                "success_rate": stats.get("success_rate", 0),
                "average_duration_ms": stats.get("average_duration_ms", 0),
                "median_duration_ms": stats.get("median_duration_ms", 0),
                "last_operation_time": stats.get("last_operation_time", "")
            }

            flattened.append(row)

            # Add error counts as separate rows
            for error_type, count in stats.get("common_errors", {}).items():
                error_row = {
                    "operation_type": op_type,
                    "error_type": error_type,
                    "count": count,
                    "category": "error"
                }
                flattened.append(error_row)

        return flattened


# Helper function to get a MetricsCollector instance
def get_metrics_collector(stats_dir: Optional[str] = None) -> MetricsCollector:
    """
    Get a MetricsCollector instance (singleton).

    Args:
        stats_dir (str, optional): Directory for stats files.

    Returns:
        MetricsCollector: A MetricsCollector instance.
    """
    return MetricsCollector(stats_dir=stats_dir)


class TimeSeriesData:
    """
    Stores time-based metrics with flexible resolution for trend analysis.

    Allows recording and aggregating values over time with various resolutions
    (minute, hour, day, week, month) and supports multi-dimensional data.
    """

    def __init__(self, name: str, resolution: str = 'hour', max_points: int = 1000):
        """
        Initialize time series data collection.

        Args:
            name (str): Name of this time series
            resolution (str): Time bucket resolution ('minute', 'hour', 'day', 'week', 'month')
            max_points (int): Maximum number of time points to store
        """
        self.name = name
        self.resolution = resolution
        self.max_points = max_points
        self.data_points = {}  # Maps time bucket to dimension data
        self.dimensions = {}   # Maps dimension keys to dimension dictionaries
        self.metadata = {}     # Additional metadata about this time series

    def add_point(self, value: Union[int, float], timestamp: Optional[datetime] = None,
                  dimensions: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a data point to the time series.

        Args:
            value (Union[int, float]): The value to record
            timestamp (datetime, optional): When this value occurred. Defaults to now.
            dimensions (Dict[str, Any], optional): Dimension values for this point
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Create a time bucket based on resolution
        if self.resolution == 'minute':
            time_key = timestamp.strftime("%Y-%m-%d %H:%M:00")
        elif self.resolution == 'hour':
            time_key = timestamp.strftime("%Y-%m-%d %H:00:00")
        elif self.resolution == 'day':
            time_key = timestamp.strftime("%Y-%m-%d 00:00:00")
        elif self.resolution == 'week':
            # Start of the week (Monday)
            start_of_week = timestamp - timedelta(days=timestamp.weekday())
            time_key = start_of_week.strftime("%Y-%m-%d 00:00:00")
        elif self.resolution == 'month':
            time_key = timestamp.strftime("%Y-%m-01 00:00:00")
        else:  # Default to hour
            time_key = timestamp.strftime("%Y-%m-%d %H:00:00")

        # Create dimension key if dimensions provided
        dim_key = "_default"
        if dimensions:
            dim_key = ":".join(
                f"{k}={v}" for k, v in sorted(dimensions.items()))
            # Store the dimension definition
            self.dimensions[dim_key] = dimensions

        # Get or create the data structure for this time and dimension
        if time_key not in self.data_points:
            self.data_points[time_key] = {}

        if dim_key not in self.data_points[time_key]:
            self.data_points[time_key][dim_key] = {
                "count": 0,
                "sum": 0,
                "min": float('inf'),
                "max": float('-inf'),
                "values": []
            }

        # Update the data point
        point = self.data_points[time_key][dim_key]
        point["count"] += 1
        point["sum"] += value
        point["min"] = min(point["min"], value)
        point["max"] = max(point["max"], value)
        point["values"].append(value)

        # Prune old points if we exceed max_points
        self._prune_if_needed()

    def _prune_if_needed(self) -> None:
        """Remove oldest data points if we exceed the maximum number of points."""
        if len(self.data_points) <= self.max_points:
            return

        # Sort time keys and remove oldest ones
        time_keys = sorted(self.data_points.keys())
        to_remove = time_keys[:(len(time_keys) - self.max_points)]

        for key in to_remove:
            del self.data_points[key]

    def get_points(self, start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   dimensions: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get time series data points within a time range.

        Args:
            start_time (datetime, optional): Start of time range
            end_time (datetime, optional): End of time range
            dimensions (Dict[str, Any], optional): Filter by these dimensions

        Returns:
            Dict[str, Dict[str, Any]]: Time points with their statistics
        """
        result = {}

        # Calculate dimension key
        dim_key = "_default"
        if dimensions:
            dim_key = ":".join(
                f"{k}={v}" for k, v in sorted(dimensions.items()))

        # Filter by time range
        for time_key, dim_data in sorted(self.data_points.items()):
            # Skip if this time key doesn't have our dimension
            if dim_key not in dim_data:
                continue

            # Convert time key to datetime for comparison
            time_point = datetime.fromisoformat(time_key)

            # Skip if outside time range
            if start_time and time_point < start_time:
                continue
            if end_time and time_point > end_time:
                continue

            # Add to result
            result[time_key] = {
                "count": dim_data[dim_key]["count"],
                "sum": dim_data[dim_key]["sum"],
                "min": dim_data[dim_key]["min"],
                "max": dim_data[dim_key]["max"],
                "avg": (
                    dim_data[dim_key]["sum"] / dim_data[dim_key]["count"]
                    if dim_data[dim_key]["count"] > 0
                    else 0
                )
            }

        return result

    def get_aggregates(self, start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None,
                       dimensions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get aggregated statistics for the time series.

        Args:
            start_time (datetime, optional): Start of time range
            end_time (datetime, optional): End of time range
            dimensions (Dict[str, Any], optional): Filter by these dimensions

        Returns:
            Dict[str, Any]: Aggregated statistics
        """
        points = self.get_points(start_time, end_time, dimensions)

        if not points:
            return {
                "count": 0,
                "sum": 0,
                "min": 0,
                "max": 0,
                "avg": 0
            }

        # Aggregate across all points
        count = sum(p["count"] for p in points.values())
        total_sum = sum(p["sum"] for p in points.values())
        min_val = min(p["min"] for p in points.values())
        max_val = max(p["max"] for p in points.values())

        return {
            "count": count,
            "sum": total_sum,
            "min": min_val,
            "max": max_val,
            "avg": total_sum / count if count > 0 else 0
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert time series data to a dictionary for serialization.

        Returns:
            Dict[str, Any]: Dictionary representation of time series data
        """
        return {
            "name": self.name,
            "resolution": self.resolution,
            "max_points": self.max_points,
            "data_points": self.data_points,
            "dimensions": self.dimensions,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeSeriesData':
        """
        Create a TimeSeriesData instance from a dictionary.

        Args:
            data (Dict[str, Any]): Dictionary data

        Returns:
            TimeSeriesData: New instance with loaded data
        """
        name = data.get("name", "unknown")
        resolution = data.get("resolution", "hour")
        max_points = data.get("max_points", 1000)

        time_series = cls(name, resolution, max_points)
        time_series.data_points = data.get("data_points", {})
        time_series.dimensions = data.get("dimensions", {})
        time_series.metadata = data.get("metadata", {})

        return time_series
