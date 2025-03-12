import os
import sys
import unittest

# اضافه کردن مسیر پروژه به sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# وارد کردن کلاس تست
from tests.test_logging_.test_logging_manager import TestLoggingManager

if __name__ == "__main__":
    # اجرای تست
    unittest.main(defaultTest="TestLoggingManager")