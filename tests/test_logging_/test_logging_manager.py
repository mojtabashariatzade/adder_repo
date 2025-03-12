"""
تست ماژول logging_manager
"""

import unittest
import os
import sys
import tempfile
import logging

# اضافه کردن مسیر اصلی پروژه به سیستم
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# وارد کردن ماژول تحت تست
from logging_.logging_manager import LoggingManager


class TestLoggingManager(unittest.TestCase):
    """
    کلاس تست برای ماژول logging_manager
    """

    def setUp(self):
        """تنظیمات اولیه قبل از هر تست"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test_log.log")
        self.json_log_file = os.path.join(self.temp_dir, "test_log.json")
        self.logging_manager = LoggingManager(
            log_dir=self.temp_dir,
            log_file="test_log.log",
            max_file_size=1024,  # 1KB for testing rotation
            backup_count=2,
            default_level=logging.DEBUG,
            console_level=logging.INFO,
            file_level=logging.DEBUG,
            json_log_enabled=True
        )

    def tearDown(self):
        """پاکسازی بعد از هر تست"""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """تست ایجاد دایرکتوری لاگ و فایل لاگ"""
        self.assertTrue(os.path.exists(self.temp_dir), "دایرکتوری لاگ ایجاد نشده است")
        self.assertTrue(os.path.exists(self.log_file), "فایل لاگ ایجاد نشده است")

    def test_get_logger(self):
        """تست متد get_logger"""
        # ایجاد یک logger
        logger_name = "test_logger"
        logger = self.logging_manager.get_logger(logger_name)

        # بررسی نام logger
        self.assertEqual(logger.name, logger_name, "نام logger مطابقت ندارد")

        # بررسی اینکه logger در دیکشنری loggers ذخیره شده باشد
        self.assertIn(logger_name, self.logging_manager.loggers, "logger در دیکشنری loggers ذخیره نشده است")

    def test_health_check(self):
        """تست متد health_check"""
        healthy, issues = self.logging_manager.health_check()
        self.assertTrue(healthy, "سیستم لاگینگ باید در حالت سالم باشد")
        self.assertEqual(len(issues), 0, "نباید هیچ مشکلی وجود داشته باشد")


if __name__ == "__main__":
    unittest.main()