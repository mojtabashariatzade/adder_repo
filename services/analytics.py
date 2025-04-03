"""
Analytics Service Module

This module provides functionalities for collecting, analyzing, and reporting
performance data and statistics for the Telegram Account Manager. It tracks metrics
such as success rates, error frequencies, operation durations, and generates
insightful reports to help optimize account usage and operation strategies.
"""

import os
import json
import datetime
from typing import Dict, Any, Optional, Union
import statistics
import time
import uuid
import threading
from enum import Enum, auto

# Try to import JsonFileManager
try:
    from data.json_file_manager import JsonFileManager
except ImportError:
    print("Warning: JsonFileManager could not be imported. Analytics functionality may be limited.")

    # Define a mock class as fallback
    class JsonFileManager:
        """Mock JsonFileManager class for when the actual module is not available."""

        def __init__(self, base_dir=None):
            self.base_dir = base_dir or os.getcwd()

        def read_json(self, path, default=None):
            return default or {}

        def write_json(self, path, data, make_backup=False):
            pass

try:
    from data.base_file_manager import JsonFileManager, get_file_manager
    from data.session_manager import get_session_manager
    from logging_.logging_manager import get_logger
    from core.config import Config
    from core.exceptions import FileReadError, FileWriteError
except ImportError:
    print("Warning: Some dependencies could not be imported. Analytics functionality may be limited.")


class MetricType(Enum):
    ACCOUNT = auto()
    OPERATION = auto()
    ERROR = auto()
    PERFORMANCE = auto()
    USER = auto()
    GROUP = auto()


class AnalyticsManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AnalyticsManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, data_dir: Optional[str] = None,
                 file_manager: Optional[JsonFileManager] = None,
                 metrics_file: Optional[str] = None,
                 retention_days: int = 30):
        with self._lock:
            if self._initialized:
                return

            self.logger = get_logger("AnalyticsManager")
            self.config = Config()

            self.data_dir = data_dir or os.path.join(
                os.getcwd(), "analytics_data")
            self.file_manager = file_manager or get_file_manager(
                'json', base_dir=self.data_dir)
            self.metrics_file = metrics_file or "metrics.json"
            self.retention_days = retention_days

            self.session_manager = get_session_manager()

            self.metrics = {
                "accounts": {},
                "operations": {},
                "errors": {},
                "performance": {},
                "users": {},
                "groups": {}
            }

            self._active_timers = {}

            os.makedirs(self.data_dir, exist_ok=True)
            self._load_metrics()

            self._initialized = True
            self.logger.info("AnalyticsManager initialized")

    def _load_metrics(self) -> None:
        metrics_path = os.path.join(self.data_dir, self.metrics_file)
        try:
            loaded_metrics = self.file_manager.read_json(
                metrics_path, default={})
            if loaded_metrics:
                self.metrics.update(loaded_metrics)
                self.logger.debug(f"Loaded metrics from {metrics_path}")
        except (FileReadError, json.JSONDecodeError) as e:
            self.logger.warning(
                f"Could not load metrics from {metrics_path}: {e}")

    def _save_metrics(self) -> bool:
        metrics_path = os.path.join(self.data_dir, self.metrics_file)
        try:
            self.file_manager.write_json(
                metrics_path, self.metrics, make_backup=True)
            self.logger.debug(f"Saved metrics to {metrics_path}")
            return True
        except (FileWriteError, json.JSONDecodeError) as e:
            self.logger.error(f"Could not save metrics to {metrics_path}: {e}")
            return False

    def record_account_metric(self, account_id: str, metric_name: str,
                              value: Any, category: Optional[str] = None) -> None:
        if account_id not in self.metrics["accounts"]:
            self.metrics["accounts"][account_id] = {
                "first_seen": datetime.datetime.now().isoformat(),
                "metrics": {}
            }

        account_metrics = self.metrics["accounts"][account_id]["metrics"]

        category = category or "general"
        if category not in account_metrics:
            account_metrics[category] = {}

        if metric_name not in account_metrics[category]:
            account_metrics[category][metric_name] = []

        metric_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "value": value
        }

        account_metrics[category][metric_name].append(metric_entry)
        self._save_metrics()

    def record_operation_metric(self, operation_id: str, metric_name: str,
                                value: Any, operation_type: Optional[str] = None) -> None:
        if operation_id not in self.metrics["operations"]:
            self.metrics["operations"][operation_id] = {
                "start_time": datetime.datetime.now().isoformat(),
                "type": operation_type or "unknown",
                "metrics": {}
            }

        operation_metrics = self.metrics["operations"][operation_id]["metrics"]

        if metric_name not in operation_metrics:
            operation_metrics[metric_name] = []

        metric_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "value": value
        }

        operation_metrics[metric_name].append(metric_entry)
        self._save_metrics()

    def record_error(self, error_type: str, error_message: str,
                     context: Optional[Dict[str, Any]] = None) -> None:
        if error_type not in self.metrics["errors"]:
            self.metrics["errors"][error_type] = []

        error_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "message": error_message,
            "context": context or {}
        }

        self.metrics["errors"][error_type].append(error_entry)
        self._save_metrics()

    def record_performance_metric(self, metric_name: str, value: Any,
                                  component: Optional[str] = None) -> None:
        component = component or "general"

        if component not in self.metrics["performance"]:
            self.metrics["performance"][component] = {}

        if metric_name not in self.metrics["performance"][component]:
            self.metrics["performance"][component][metric_name] = []

        metric_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "value": value
        }

        self.metrics["performance"][component][metric_name].append(
            metric_entry)
        self._save_metrics()

    def start_timer(self, operation_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        timer_id = str(uuid.uuid4())
        self._active_timers[timer_id] = {
            "start_time": time.time(),
            "operation_name": operation_name,
            "context": context or {}
        }
        return timer_id

    def stop_timer(self, timer_id: str) -> Optional[float]:
        if timer_id not in self._active_timers:
            self.logger.warning(f"Timer {timer_id} not found")
            return None

        timer_data = self._active_timers.pop(timer_id)
        duration = time.time() - timer_data["start_time"]

        self.record_performance_metric(
            timer_data["operation_name"],
            duration,
            "timers"
        )

        return duration

    def get_account_stats(self, account_id: str) -> Dict[str, Any]:
        if account_id not in self.metrics["accounts"]:
            return {"error": "Account not found"}

        account_data = self.metrics["accounts"][account_id]

        stats = {
            "account_id": account_id,
            "first_seen": account_data["first_seen"],
            "metrics_summary": {}
        }

        for category, metrics in account_data["metrics"].items():
            stats["metrics_summary"][category] = {}

            for metric_name, values in metrics.items():
                if not values:
                    continue

                numeric_values = [entry["value"] for entry in values
                                  if isinstance(entry["value"], (int, float))]

                if numeric_values:
                    stats["metrics_summary"][category][metric_name] = {
                        "min": min(numeric_values),
                        "max": max(numeric_values),
                        "avg": sum(numeric_values) / len(numeric_values),
                        "count": len(numeric_values),
                        "latest": values[-1]["value"]
                    }
                else:
                    stats["metrics_summary"][category][metric_name] = {
                        "count": len(values),
                        "latest": values[-1]["value"]
                    }

        return stats

    def get_operation_stats(self, operation_id: str) -> Dict[str, Any]:
        if operation_id not in self.metrics["operations"]:
            return {"error": "Operation not found"}

        operation_data = self.metrics["operations"][operation_id]

        stats = {
            "operation_id": operation_id,
            "type": operation_data["type"],
            "start_time": operation_data["start_time"],
            "metrics_summary": {}
        }

        for metric_name, values in operation_data["metrics"].items():
            if not values:
                continue

            numeric_values = [entry["value"] for entry in values
                              if isinstance(entry["value"], (int, float))]

            if numeric_values:
                stats["metrics_summary"][metric_name] = {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "avg": sum(numeric_values) / len(numeric_values),
                    "count": len(numeric_values),
                    "latest": values[-1]["value"]
                }
            else:
                stats["metrics_summary"][metric_name] = {
                    "count": len(values),
                    "latest": values[-1]["value"]
                }

        return stats

    def get_error_stats(self) -> Dict[str, Any]:
        error_stats = {
            "total_errors": 0,
            "error_types": {},
            "recent_errors": []
        }

        for error_type, errors in self.metrics["errors"].items():
            error_stats["total_errors"] += len(errors)
            error_stats["error_types"][error_type] = len(errors)

            # Add most recent errors (up to 10)
            for error in errors[-10:]:
                error_stats["recent_errors"].append({
                    "type": error_type,
                    "timestamp": error["timestamp"],
                    "message": error["message"]
                })

        # Sort recent errors by timestamp (newest first)
        error_stats["recent_errors"].sort(
            key=lambda e: e["timestamp"],
            reverse=True
        )

        # Limit to 10 most recent
        error_stats["recent_errors"] = error_stats["recent_errors"][:10]

        return error_stats

    def get_performance_stats(self) -> Dict[str, Any]:
        performance_stats = {}

        for component, metrics in self.metrics["performance"].items():
            performance_stats[component] = {}

            for metric_name, values in metrics.items():
                if not values:
                    continue

                numeric_values = [entry["value"] for entry in values
                                  if isinstance(entry["value"], (int, float))]

                if numeric_values:
                    performance_stats[component][metric_name] = {
                        "min": min(numeric_values),
                        "max": max(numeric_values),
                        "avg": sum(numeric_values) / len(numeric_values),
                        "count": len(numeric_values),
                        "latest": values[-1]["value"]
                    }

                    # Calculate standard deviation if more than one value
                    if len(numeric_values) > 1:
                        performance_stats[component][metric_name]["std_dev"] = statistics.stdev(
                            numeric_values)

                    # Calculate linear regression (simple trend)
                    if len(numeric_values) > 2:
                        x = list(range(len(numeric_values)))
                        sum_x = sum(x)
                        sum_y = sum(numeric_values)
                        sum_xy = sum(x_i * y_i for x_i,
                                     y_i in zip(x, numeric_values))
                        sum_xx = sum(x_i ** 2 for x_i in x)
                        n = len(numeric_values)

                        slope = (n * sum_xy - sum_x * sum_y) / \
                            (n * sum_xx - sum_x ** 2)
                        performance_stats[component][metric_name]["trend"] = "increasing" if slope > 0 else "decreasing"
                        performance_stats[component][metric_name]["trend_value"] = slope

        return performance_stats

    def generate_report(self, report_type: str = "general") -> Dict[str, Any]:
        if report_type == "general":
            return self._generate_general_report()
        elif report_type == "accounts":
            return self._generate_accounts_report()
        elif report_type == "operations":
            return self._generate_operations_report()
        elif report_type == "errors":
            return self._generate_errors_report()
        elif report_type == "performance":
            return self._generate_performance_report()
        else:
            return {"error": f"Unknown report type: {report_type}"}

    def _generate_general_report(self) -> Dict[str, Any]:
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "account_summary": {
                "total_accounts": len(self.metrics["accounts"]),
                "active_accounts": 0,
                "blocked_accounts": 0,
                "daily_limit_reached_accounts": 0
            },
            "operation_summary": {
                "total_operations": len(self.metrics["operations"]),
                "success_rate": 0,
                "average_duration": 0
            },
            "error_summary": self.get_error_stats(),
            "performance_summary": {}
        }

        # Account activity status
        for account_id, account_data in self.metrics["accounts"].items():
            if "status" in account_data:
                status = account_data["status"]
                if status == "active":
                    report["account_summary"]["active_accounts"] += 1
                elif status == "blocked":
                    report["account_summary"]["blocked_accounts"] += 1
                elif status == "daily_limit_reached":
                    report["account_summary"]["daily_limit_reached_accounts"] += 1

        # Operation success rate and duration
        successful_operations = 0
        total_duration = 0
        duration_count = 0

        for operation_id, operation_data in self.metrics["operations"].items():
            metrics = operation_data.get("metrics", {})

            # Check for success metrics
            if "success" in metrics and metrics["success"]:
                last_success = metrics["success"][-1]["value"]
                if last_success:
                    successful_operations += 1

            # Check for duration metrics
            if "duration" in metrics and metrics["duration"]:
                for entry in metrics["duration"]:
                    if isinstance(entry["value"], (int, float)):
                        total_duration += entry["value"]
                        duration_count += 1

        if len(self.metrics["operations"]) > 0:
            report["operation_summary"]["success_rate"] = (
                successful_operations / len(self.metrics["operations"])) * 100

        if duration_count > 0:
            report["operation_summary"]["average_duration"] = total_duration / \
                duration_count

        # Performance summary
        performance_stats = self.get_performance_stats()
        for component, metrics in performance_stats.items():
            component_summary = {}
            for metric_name, stats in metrics.items():
                if "avg" in stats:
                    component_summary[metric_name] = stats["avg"]

            if component_summary:
                report["performance_summary"][component] = component_summary

        return report

    def _generate_accounts_report(self) -> Dict[str, Any]:
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "accounts": {}
        }

        for account_id in self.metrics["accounts"]:
            report["accounts"][account_id] = self.get_account_stats(account_id)

        return report

    def _generate_operations_report(self) -> Dict[str, Any]:
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "operations": {},
            "operation_types": {},
            "success_by_hour": {str(h): 0 for h in range(24)},
            "success_count_by_hour": {str(h): 0 for h in range(24)}
        }

        for operation_id, operation_data in self.metrics["operations"].items():
            # Collect operation-specific stats
            operation_stats = self.get_operation_stats(operation_id)
            report["operations"][operation_id] = operation_stats

            # Aggregate by operation type
            op_type = operation_data.get("type", "unknown")
            if op_type not in report["operation_types"]:
                report["operation_types"][op_type] = {
                    "count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "total_duration": 0,
                    "duration_count": 0
                }

            report["operation_types"][op_type]["count"] += 1

            # Check success
            success = False
            if "metrics" in operation_data and "success" in operation_data["metrics"]:
                success_entries = operation_data["metrics"]["success"]
                if success_entries and success_entries[-1]["value"]:
                    success = True
                    report["operation_types"][op_type]["success_count"] += 1
                else:
                    report["operation_types"][op_type]["failure_count"] += 1

            # Check duration
            if "metrics" in operation_data and "duration" in operation_data["metrics"]:
                for entry in operation_data["metrics"]["duration"]:
                    if isinstance(entry["value"], (int, float)):
                        report["operation_types"][op_type]["total_duration"] += entry["value"]
                        report["operation_types"][op_type]["duration_count"] += 1

            # Analyze success by hour
            if "metrics" in operation_data and "success" in operation_data["metrics"]:
                for entry in operation_data["metrics"]["success"]:
                    try:
                        timestamp = datetime.datetime.fromisoformat(
                            entry["timestamp"])
                        hour = str(timestamp.hour)
                        if entry["value"]:
                            report["success_by_hour"][hour] += 1
                        report["success_count_by_hour"][hour] += 1
                    except (ValueError, KeyError):
                        pass

        # Calculate average duration and success rate for each operation type
        for op_type in report["operation_types"]:
            type_stats = report["operation_types"][op_type]

            if type_stats["duration_count"] > 0:
                type_stats["average_duration"] = type_stats["total_duration"] / \
                    type_stats["duration_count"]
            else:
                type_stats["average_duration"] = 0

            if type_stats["count"] > 0:
                type_stats["success_rate"] = (
                    type_stats["success_count"] / type_stats["count"]) * 100
            else:
                type_stats["success_rate"] = 0

        # Calculate success rate by hour
        report["success_rate_by_hour"] = {}
        for hour in report["success_by_hour"]:
            if report["success_count_by_hour"][hour] > 0:
                report["success_rate_by_hour"][hour] = (
                    report["success_by_hour"][hour] /
                    report["success_count_by_hour"][hour]
                ) * 100
            else:
                report["success_rate_by_hour"][hour] = 0

        return report

    def _generate_errors_report(self) -> Dict[str, Any]:
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "error_summary": self.get_error_stats(),
            "error_timeline": {
                "daily": {},
                "hourly": {}
            },
            "error_correlations": {}
        }

        # Generate error timeline data
        for error_type, errors in self.metrics["errors"].items():
            for error in errors:
                try:
                    timestamp = datetime.datetime.fromisoformat(
                        error["timestamp"])
                    date_str = timestamp.strftime("%Y-%m-%d")
                    hour_str = timestamp.strftime("%Y-%m-%d %H")

                    # Daily counts
                    if date_str not in report["error_timeline"]["daily"]:
                        report["error_timeline"]["daily"][date_str] = {}

                    if error_type not in report["error_timeline"]["daily"][date_str]:
                        report["error_timeline"]["daily"][date_str][error_type] = 0

                    report["error_timeline"]["daily"][date_str][error_type] += 1

                    # Hourly counts
                    if hour_str not in report["error_timeline"]["hourly"]:
                        report["error_timeline"]["hourly"][hour_str] = {}

                    if error_type not in report["error_timeline"]["hourly"][hour_str]:
                        report["error_timeline"]["hourly"][hour_str][error_type] = 0

                    report["error_timeline"]["hourly"][hour_str][error_type] += 1

                    # Look for correlations with context data
                    if "context" in error and error["context"]:
                        for key, value in error["context"].items():
                            correlation_key = f"{key}:{value}"

                            if correlation_key not in report["error_correlations"]:
                                report["error_correlations"][correlation_key] = {}

                            if error_type not in report["error_correlations"][correlation_key]:
                                report["error_correlations"][correlation_key][error_type] = 0

                            report["error_correlations"][correlation_key][error_type] += 1
                except (ValueError, KeyError):
                    pass

        # Sort timelines by date/hour
        report["error_timeline"]["daily"] = dict(
            sorted(report["error_timeline"]["daily"].items()))
        report["error_timeline"]["hourly"] = dict(
            sorted(report["error_timeline"]["hourly"].items()))

        return report

    def _generate_performance_report(self) -> Dict[str, Any]:
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "performance_summary": self.get_performance_stats(),
            "performance_timeline": {},
            "bottlenecks": [],
            "recommendations": []
        }

        # Generate performance timeline data
        timeline_metrics = ["response_time",
                            "duration", "cpu_usage", "memory_usage"]

        for component, metrics in self.metrics["performance"].items():
            for metric_name, values in metrics.items():
                if metric_name in timeline_metrics:
                    metric_key = f"{component}:{metric_name}"
                    report["performance_timeline"][metric_key] = []

                    for entry in values:
                        if isinstance(entry["value"], (int, float)):
                            try:
                                timestamp = datetime.datetime.fromisoformat(
                                    entry["timestamp"])
                                report["performance_timeline"][metric_key].append({
                                    "timestamp": entry["timestamp"],
                                    "value": entry["value"]
                                })
                            except (ValueError, KeyError):
                                pass

        # Find bottlenecks (metrics with high values or negative trends)
        for component, metrics in report["performance_summary"].items():
            for metric_name, stats in metrics.items():
                if "trend" in stats and stats["trend"] == "increasing":
                    if metric_name in ["response_time", "duration", "cpu_usage", "memory_usage"]:
                        report["bottlenecks"].append({
                            "component": component,
                            "metric": metric_name,
                            "stats": stats,
                            "severity": "high" if stats["trend_value"] > 0.1 else "medium"
                        })

                # Check for high average values
                if "avg" in stats:
                    if metric_name == "response_time" and stats["avg"] > 2.0:
                        report["bottlenecks"].append({
                            "component": component,
                            "metric": metric_name,
                            "stats": stats,
                            "severity": "high" if stats["avg"] > 5.0 else "medium"
                        })
                    elif metric_name == "duration" and stats["avg"] > 10.0:
                        report["bottlenecks"].append({
                            "component": component,
                            "metric": metric_name,
                            "stats": stats,
                            "severity": "high" if stats["avg"] > 30.0 else "medium"
                        })

        # Generate recommendations based on data
        if report["bottlenecks"]:
            for bottleneck in report["bottlenecks"]:
                if bottleneck["metric"] == "response_time":
                    report["recommendations"].append({
                        "component": bottleneck["component"],
                        "issue": f"High response time ({bottleneck['stats']['avg']:.2f}s average)",
                        "recommendation": "Consider adding delays between requests or using proxies to avoid rate limits"
                    })
                elif bottleneck["metric"] == "duration":
                    report["recommendations"].append({
                        "component": bottleneck["component"],
                        "issue": f"High operation duration ({bottleneck['stats']['avg']:.2f}s average)",
                        "recommendation": "Optimize operation logic or consider using parallel strategies"
                    })
                elif bottleneck["metric"] == "cpu_usage" and bottleneck["stats"]["avg"] > 70:
                    report["recommendations"].append({
                        "component": bottleneck["component"],
                        "issue": f"High CPU usage ({bottleneck['stats']['avg']:.2f}% average)",
                        "recommendation": "Optimize code or reduce parallel operations"
                    })
                elif bottleneck["metric"] == "memory_usage" and bottleneck["stats"]["avg"] > 80:
                    report["recommendations"].append({
                        "component": bottleneck["component"],
                        "issue": f"High memory usage ({bottleneck['stats']['avg']:.2f}% average)",
                        "recommendation": "Check for memory leaks or reduce batch sizes"
                    })

        # Add time-based recommendations
        if "timers" in report["performance_summary"]:
            for timer_name, stats in report["performance_summary"]["timers"].items():
                if "avg" in stats and stats["avg"] > 5.0:
                    report["recommendations"].append({
                        "component": timer_name,
                        "issue": f"Slow operation ({stats['avg']:.2f}s average)",
                        "recommendation": "Consider optimizing or splitting into smaller operations"
                    })

        # Add success rate recommendations from operation stats
        if hasattr(self, "_generate_operations_report"):
            operations_report = self._generate_operations_report()
            success_rate_by_hour = operations_report.get(
                "success_rate_by_hour", {})

            # Find best and worst hours
            if success_rate_by_hour:
                best_hours = sorted(success_rate_by_hour.items(
                ), key=lambda x: x[1], reverse=True)[:3]
                worst_hours = sorted(
                    success_rate_by_hour.items(), key=lambda x: x[1])[:3]

                if best_hours and best_hours[0][1] > 0:
                    best_hours_list = [
                        f"{h}:00-{int(h)+1}:00" for h, _ in best_hours if float(_) > 0]
                    if best_hours_list:
                        report["recommendations"].append({
                            "component": "scheduling",
                            "issue": "Optimal operation times identified",
                            "recommendation": f"Schedule operations during these hours for best results: {', '.join(best_hours_list)}"
                        })

                if worst_hours and worst_hours[0][1] < 50:
                    worst_hours_list = [
                        f"{h}:00-{int(h)+1}:00" for h, _ in worst_hours if float(_) < 50]
                    if worst_hours_list:
                        report["recommendations"].append({
                            "component": "scheduling",
                            "issue": "Suboptimal operation times identified",
                            "recommendation": f"Avoid scheduling operations during these hours: {', '.join(worst_hours_list)}"
                        })

        return report

    def export_report(self, report_type: str = "general", format: str = "json",
                      file_path: Optional[str] = None) -> Union[str, Dict[str, Any]]:
        report = self.generate_report(report_type)

        if format.lower() == "json":
            if file_path:
                try:
                    self.file_manager.write_json(file_path, report)
                    return f"Report saved to {file_path}"
                except Exception as e:
                    self.logger.error(
                        f"Error saving report to {file_path}: {e}")
                    return {"error": f"Failed to save report: {str(e)}"}
            return report

        elif format.lower() == "text":
            text_report = self._convert_report_to_text(report, report_type)

            if file_path:
                try:
                    with open(file_path, 'w') as f:
                        f.write(text_report)
                    return f"Report saved to {file_path}"
                except Exception as e:
                    self.logger.error(
                        f"Error saving report to {file_path}: {e}")
                    return {"error": f"Failed to save report: {str(e)}"}
            return text_report

        else:
            return {"error": f"Unsupported format: {format}"}

    def _convert_report_to_text(self, report: Dict[str, Any], report_type: str) -> str:
        if report_type == "general":
            return self._convert_general_report_to_text(report)
        elif report_type == "accounts":
            return self._convert_accounts_report_to_text(report)
        elif report_type == "operations":
            return self._convert_operations_report_to_text(report)
        elif report_type == "errors":
            return self._convert_errors_report_to_text(report)
        elif report_type == "performance":
            return self._convert_performance_report_to_text(report)
        else:
            return f"Unknown report type: {report_type}"

    def _convert_general_report_to_text(self, report: Dict[str, Any]) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("TELEGRAM ACCOUNT MANAGER - GENERAL REPORT")
        lines.append("=" * 60)
        lines.append(f"Generated: {report['timestamp']}")
        lines.append("")

        lines.append("ACCOUNT SUMMARY")
        lines.append("-" * 30)
        account_summary = report.get("account_summary", {})
        lines.append(
            f"Total Accounts: {account_summary.get('total_accounts', 0)}")
        lines.append(
            f"Active Accounts: {account_summary.get('active_accounts', 0)}")
        lines.append(
            f"Blocked Accounts: {account_summary.get('blocked_accounts', 0)}")
        lines.append(
            f"Daily Limit Reached: {account_summary.get('daily_limit_reached_accounts', 0)}")
        lines.append("")

        lines.append("OPERATION SUMMARY")
        lines.append("-" * 30)
        operation_summary = report.get("operation_summary", {})
        lines.append(
            f"Total Operations: {operation_summary.get('total_operations', 0)}")
        lines.append(
            f"Success Rate: {operation_summary.get('success_rate', 0):.2f}%")
        lines.append(
            f"Average Duration: {operation_summary.get('average_duration', 0):.2f} seconds")
        lines.append("")

        lines.append("ERROR SUMMARY")
        lines.append("-" * 30)
        error_summary = report.get("error_summary", {})
        lines.append(f"Total Errors: {error_summary.get('total_errors', 0)}")

        error_types = error_summary.get("error_types", {})
        if error_types:
            lines.append("Error Types:")
            for error_type, count in error_types.items():
                lines.append(f"  {error_type}: {count}")

        lines.append("")
        lines.append("RECENT ERRORS")
        lines.append("-" * 30)
        recent_errors = error_summary.get("recent_errors", [])
        if recent_errors:
            for error in recent_errors[:5]:  # Show only 5 most recent
                lines.append(
                    f"[{error.get('timestamp', '')}] {error.get('type', '')}: {error.get('message', '')}")
        else:
            lines.append("No recent errors")

        lines.append("")
        lines.append("PERFORMANCE SUMMARY")
        lines.append("-" * 30)
        performance_summary = report.get("performance_summary", {})
        for component, metrics in performance_summary.items():
            lines.append(f"{component.upper()}:")
            for metric_name, value in metrics.items():
                if isinstance(value, dict) and "avg" in value:
                    lines.append(f"  {metric_name}: {value['avg']:.2f} (avg)")
                else:
                    lines.append(f"  {metric_name}: {value}")

        return "\n".join(lines)

    def _convert_accounts_report_to_text(self, report: Dict[str, Any]) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("TELEGRAM ACCOUNT MANAGER - ACCOUNTS REPORT")
        lines.append("=" * 60)
        lines.append(f"Generated: {report['timestamp']}")
        lines.append("")

        accounts = report.get("accounts", {})
        for account_id, account_data in accounts.items():
            lines.append(f"ACCOUNT: {account_id}")
            lines.append("-" * 30)
            lines.append(
                f"First Seen: {account_data.get('first_seen', 'Unknown')}")

            metrics_summary = account_data.get("metrics_summary", {})
            for category, metrics in metrics_summary.items():
                lines.append(f"\n{category.upper()}:")
                for metric_name, stats in metrics.items():
                    if isinstance(stats, dict) and "avg" in stats:
                        lines.append(f"  {metric_name}:")
                        lines.append(f"    Min: {stats.get('min', 'N/A')}")
                        lines.append(f"    Max: {stats.get('max', 'N/A')}")
                        lines.append(f"    Avg: {stats.get('avg', 'N/A')}")
                        lines.append(f"    Count: {stats.get('count', 'N/A')}")
                        lines.append(
                            f"    Latest: {stats.get('latest', 'N/A')}")
                    else:
                        lines.append(f"  {metric_name}: {stats}")

            lines.append("\n" + "=" * 30)

        return "\n".join(lines)

    def _convert_operations_report_to_text(self, report: Dict[str, Any]) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("TELEGRAM ACCOUNT MANAGER - OPERATIONS REPORT")
        lines.append("=" * 60)
        lines.append(f"Generated: {report['timestamp']}")
        lines.append("")

        lines.append("OPERATION TYPES SUMMARY")
        lines.append("-" * 30)
        operation_types = report.get("operation_types", {})
        for op_type, stats in operation_types.items():
            lines.append(f"{op_type.upper()}:")
            lines.append(f"  Count: {stats.get('count', 0)}")
            lines.append(f"  Success Count: {stats.get('success_count', 0)}")
            lines.append(f"  Failure Count: {stats.get('failure_count', 0)}")
            lines.append(
                f"  Success Rate: {stats.get('success_rate', 0):.2f}%")
            lines.append(
                f"  Average Duration: {stats.get('average_duration', 0):.2f} seconds")
            lines.append("")

        lines.append("SUCCESS RATE BY HOUR")
        lines.append("-" * 30)
        success_rate_by_hour = report.get("success_rate_by_hour", {})
        for hour in sorted(success_rate_by_hour.keys()):
            lines.append(
                f"  {hour}:00 - {int(hour)+1}:00: {success_rate_by_hour[hour]:.2f}%")

        lines.append("\nOPERATION DETAILS")
        lines.append("-" * 30)
        operations = report.get("operations", {})
        # Limit to 5 operations for readability
        for i, (operation_id, operation_data) in enumerate(list(operations.items())[:5]):
            lines.append(f"Operation ID: {operation_id}")
            lines.append(f"Type: {operation_data.get('type', 'Unknown')}")
            lines.append(
                f"Start Time: {operation_data.get('start_time', 'Unknown')}")

            metrics_summary = operation_data.get("metrics_summary", {})
            if metrics_summary:
                lines.append("Metrics:")
                for metric_name, stats in metrics_summary.items():
                    if isinstance(stats, dict) and "avg" in stats:
                        lines.append(
                            f"  {metric_name}: {stats.get('avg', 'N/A')} (avg)")
                    else:
                        lines.append(f"  {metric_name}: {stats}")

            if i < len(list(operations.items())[:5]) - 1:
                lines.append("")

        if len(operations) > 5:
            lines.append(f"\n... and {len(operations) - 5} more operations")

        return "\n".join(lines)

    def _convert_errors_report_to_text(self, report: Dict[str, Any]) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("TELEGRAM ACCOUNT MANAGER - ERRORS REPORT")
        lines.append("=" * 60)
        lines.append(f"Generated: {report['timestamp']}")
        lines.append("")

        error_summary = report.get("error_summary", {})
        lines.append("ERROR SUMMARY")
        lines.append("-" * 30)
        lines.append(f"Total Errors: {error_summary.get('total_errors', 0)}")

        error_types = error_summary.get("error_types", {})
        if error_types:
            lines.append("\nError Types:")
            for error_type, count in error_types.items():
                lines.append(f"  {error_type}: {count}")

        lines.append("\nRECENT ERRORS")
        lines.append("-" * 30)
        recent_errors = error_summary.get("recent_errors", [])
        if recent_errors:
            for error in recent_errors:
                lines.append(
                    f"[{error.get('timestamp', '')}] {error.get('type', '')}: {error.get('message', '')}")
        else:
            lines.append("No recent errors")

        lines.append("\nERROR TIMELINE (DAILY)")
        lines.append("-" * 30)
        daily_timeline = report.get("error_timeline", {}).get("daily", {})
        # Last 10 days
        for date, errors in sorted(daily_timeline.items())[:10]:
            total = sum(errors.values())
            lines.append(f"{date}: {total} errors")
            for error_type, count in errors.items():
                lines.append(f"  {error_type}: {count}")

        lines.append("\nERROR CORRELATIONS")
        lines.append("-" * 30)
        correlations = report.get("error_correlations", {})
        # Show top 10 correlations
        top_correlations = sorted(correlations.items(),
                                  key=lambda x: sum(x[1].values()),
                                  reverse=True)[:10]
        for context, error_counts in top_correlations:
            total = sum(error_counts.values())
            lines.append(f"{context}: {total} errors")
            for error_type, count in error_counts.items():
                lines.append(f"  {error_type}: {count}")

        return "\n".join(lines)

    def _convert_performance_report_to_text(self, report: Dict[str, Any]) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("TELEGRAM ACCOUNT MANAGER - PERFORMANCE REPORT")
        lines.append("=" * 60)
        lines.append(f"Generated: {report['timestamp']}")
        lines.append("")

        lines.append("PERFORMANCE SUMMARY")
        lines.append("-" * 30)
        performance_summary = report.get("performance_summary", {})
        for component, metrics in performance_summary.items():
            lines.append(f"{component.upper()}:")
            for metric_name, stats in metrics.items():
                if isinstance(stats, dict):
                    lines.append(f"  {metric_name}:")
                    for stat_name, value in stats.items():
                        if isinstance(value, (int, float)):
                            lines.append(f"    {stat_name}: {value:.2f}")
                        else:
                            lines.append(f"    {stat_name}: {value}")
                else:
                    lines.append(f"  {metric_name}: {stats}")
            lines.append("")

        lines.append("BOTTLENECKS")
        lines.append("-" * 30)
        bottlenecks = report.get("bottlenecks", [])
        if bottlenecks:
            for bottleneck in bottlenecks:
                lines.append(
                    f"Component: {bottleneck.get('component', 'Unknown')}")
                lines.append(f"Metric: {bottleneck.get('metric', 'Unknown')}")
                lines.append(
                    f"Severity: {bottleneck.get('severity', 'Unknown')}")

                stats = bottleneck.get("stats", {})
                if stats:
                    lines.append("Statistics:")
                    for stat_name, value in stats.items():
                        if isinstance(value, (int, float)):
                            lines.append(f"  {stat_name}: {value:.2f}")
                        else:
                            lines.append(f"  {stat_name}: {value}")
                lines.append("")
        else:
            lines.append("No bottlenecks identified")
            lines.append("")

        lines.append("RECOMMENDATIONS")
        lines.append("-" * 30)
        recommendations = report.get("recommendations", [])
        if recommendations:
            for i, recommendation in enumerate(recommendations):
                lines.append(
                    f"{i+1}. Component: {recommendation.get('component', 'Unknown')}")
                lines.append(
                    f"   Issue: {recommendation.get('issue', 'Unknown')}")
                lines.append(
                    f"   Recommendation: {recommendation.get('recommendation', 'Unknown')}")
                lines.append("")
        else:
            lines.append("No recommendations available")

        return "\n".join(lines)

    def cleanup_old_data(self, days: Optional[int] = None) -> int:
        """
        Remove data older than specified days.

        Args:
            days (int, optional): Number of days to keep data for.
                If None, uses self.retention_days.

        Returns:
            int: Number of records removed
        """
        days = days or self.retention_days
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_str = cutoff_date.isoformat()

        removed_count = 0

        # Clean up metrics
        for category in ["accounts", "operations", "errors", "performance", "users", "groups"]:
            if category == "accounts":
                # For accounts, we need to clean up metrics within each account
                for account_id in list(self.metrics["accounts"].keys()):
                    if "metrics" in self.metrics["accounts"][account_id]:
                        for metric_category in list(self.metrics["accounts"][account_id]["metrics"].keys()):
                            for metric_name in list(self.metrics["accounts"][account_id]["metrics"][metric_category].keys()):
                                values = self.metrics["accounts"][account_id]["metrics"][metric_category][metric_name]
                                new_values = [v for v in values if v.get(
                                    "timestamp", "") >= cutoff_str]
                                removed_count += len(values) - len(new_values)
                                self.metrics["accounts"][account_id]["metrics"][metric_category][metric_name] = new_values

            elif category == "operations":
                # For operations, check start_time and clean up metrics
                for operation_id in list(self.metrics["operations"].keys()):
                    start_time = self.metrics["operations"][operation_id].get(
                        "start_time", "")
                    if start_time < cutoff_str:
                        removed_count += 1
                        del self.metrics["operations"][operation_id]

            elif category == "errors":
                # For errors, filter each error type by timestamp
                for error_type in list(self.metrics["errors"].keys()):
                    errors = self.metrics["errors"][error_type]
                    new_errors = [e for e in errors if e.get(
                        "timestamp", "") >= cutoff_str]
                    removed_count += len(errors) - len(new_errors)
                    self.metrics["errors"][error_type] = new_errors

            elif category == "performance":
                # For performance, clean up metrics within each component
                for component in list(self.metrics["performance"].keys()):
                    for metric_name in list(self.metrics["performance"][component].keys()):
                        values = self.metrics["performance"][component][metric_name]
                        new_values = [v for v in values if v.get(
                            "timestamp", "") >= cutoff_str]
                        removed_count += len(values) - len(new_values)
                        self.metrics["performance"][component][metric_name] = new_values

        # Save the cleaned up metrics
        self._save_metrics()

        return removed_count

    def analyze_patterns(self) -> Dict[str, Any]:
        """
        Analyze patterns and correlations in the data.

        Returns:
            Dict[str, Any]: Analysis results
        """
        analysis = {
            "timestamp": datetime.datetime.now().isoformat(),
            "success_factors": {},
            "error_factors": {},
            "time_patterns": {},
            "account_patterns": {},
            "correlations": {}
        }

        # Analyze success factors
        successful_operations = []
        failed_operations = []

        for operation_id, operation_data in self.metrics["operations"].items():
            operation_success = False

            if "metrics" in operation_data and "success" in operation_data["metrics"]:
                success_entries = operation_data["metrics"]["success"]
                if success_entries and success_entries[-1]["value"]:
                    operation_success = True

            operation_info = {
                "id": operation_id,
                "type": operation_data.get("type", "unknown"),
                "start_time": operation_data.get("start_time"),
                "metrics": operation_data.get("metrics", {})
            }

            if operation_success:
                successful_operations.append(operation_info)
            else:
                failed_operations.append(operation_info)

        # Time-based patterns
        time_patterns = {}

        for operation in successful_operations + failed_operations:
            try:
                timestamp = datetime.datetime.fromisoformat(
                    operation["start_time"])
                hour = timestamp.hour
                day_of_week = timestamp.weekday()

                # Hour analysis
                if hour not in time_patterns:
                    time_patterns[hour] = {"success": 0, "failure": 0}

                if operation in successful_operations:
                    time_patterns[hour]["success"] += 1
                else:
                    time_patterns[hour]["failure"] += 1

                # Day of week analysis
                day_key = f"day_{day_of_week}"
                if day_key not in time_patterns:
                    time_patterns[day_key] = {"success": 0, "failure": 0}

                if operation in successful_operations:
                    time_patterns[day_key]["success"] += 1
                else:
                    time_patterns[day_key]["failure"] += 1
            except (ValueError, KeyError):
                pass

        # Calculate success rates for each hour and day
        for key, data in time_patterns.items():
            total = data["success"] + data["failure"]
            if total > 0:
                data["success_rate"] = (data["success"] / total) * 100
            else:
                data["success_rate"] = 0

        analysis["time_patterns"] = time_patterns

        # Find best and worst hours
        hour_success_rates = {hour: data["success_rate"]
                              for hour, data in time_patterns.items()
                              if isinstance(hour, int)}

        if hour_success_rates:
            best_hours = sorted(hour_success_rates.items(),
                                key=lambda x: x[1], reverse=True)[:3]
            worst_hours = sorted(hour_success_rates.items(),
                                 key=lambda x: x[1])[:3]

            analysis["success_factors"]["best_hours"] = [
                {"hour": hour, "success_rate": rate} for hour, rate in best_hours
            ]

            analysis["error_factors"]["worst_hours"] = [
                {"hour": hour, "success_rate": rate} for hour, rate in worst_hours
            ]

        # Account patterns
        for account_id, account_data in self.metrics["accounts"].items():
            if "metrics" in account_data:
                account_metrics = account_data["metrics"]

                # Look for success metrics
                success_count = 0
                failure_count = 0

                for category, metrics in account_metrics.items():
                    for metric_name, values in metrics.items():
                        if metric_name == "success" and values:
                            for entry in values:
                                if entry["value"]:
                                    success_count += 1
                                else:
                                    failure_count += 1

                if success_count + failure_count > 0:
                    success_rate = (
                        success_count / (success_count + failure_count)) * 100

                    if account_id not in analysis["account_patterns"]:
                        analysis["account_patterns"][account_id] = {}

                    analysis["account_patterns"][account_id]["success_rate"] = success_rate
                    analysis["account_patterns"][account_id]["success_count"] = success_count
                    analysis["account_patterns"][account_id]["failure_count"] = failure_count

        # Find accounts with highest and lowest success rates
        if analysis["account_patterns"]:
            account_success_rates = {
                account_id: data["success_rate"]
                for account_id, data in analysis["account_patterns"].items()
                # Minimum sample size
                if "success_rate" in data and data["success_count"] + data["failure_count"] >= 5
            }

            if account_success_rates:
                best_accounts = sorted(
                    account_success_rates.items(), key=lambda x: x[1], reverse=True)[:3]
                worst_accounts = sorted(
                    account_success_rates.items(), key=lambda x: x[1])[:3]

                analysis["success_factors"]["best_accounts"] = [
                    {"account_id": account_id, "success_rate": rate} for account_id, rate in best_accounts
                ]

                analysis["error_factors"]["worst_accounts"] = [
                    {"account_id": account_id, "success_rate": rate} for account_id, rate in worst_accounts
                ]

        # Correlations between errors and other factors
        error_contexts = {}

        for error_type, errors in self.metrics["errors"].items():
            for error in errors:
                if "context" in error and error["context"]:
                    for key, value in error["context"].items():
                        context_key = f"{key}:{value}"

                        if context_key not in error_contexts:
                            error_contexts[context_key] = {
                                "count": 0, "types": {}}

                        error_contexts[context_key]["count"] += 1

                        if error_type not in error_contexts[context_key]["types"]:
                            error_contexts[context_key]["types"][error_type] = 0

                        error_contexts[context_key]["types"][error_type] += 1

        # Find strongest correlations
        top_contexts = sorted(error_contexts.items(),
                              key=lambda x: x[1]["count"], reverse=True)[:10]
        analysis["correlations"]["error_contexts"] = [
            {
                "context": context_key,
                "count": data["count"],
                "error_types": data["types"]
            }
            for context_key, data in top_contexts
        ]

        return analysis


def get_analytics_manager(data_dir: Optional[str] = None) -> AnalyticsManager:
    """
    Get an AnalyticsManager instance (singleton).

    Args:
        data_dir (str, optional): Directory for analytics data.

    Returns:
        AnalyticsManager: An AnalyticsManager instance.
    """
    return AnalyticsManager(data_dir=data_dir)
