#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
این اسکریپت به جای تغییر خودکار، f-string ها را شناسایی کرده و تغییرات پیشنهادی را نمایش می‌دهد.
"""

import re
import os
import sys
from pathlib import Path


def read_file(file_path):
    """فایل را برای پردازش می‌خواند"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.readlines()
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)


def identify_fstrings(lines):
    """شناسایی خطوط حاوی f-string"""
    fstring_lines = []

    for i, line in enumerate(lines):
        # الگوهای مختلف f-string
        if 'f"' in line or "f'" in line:
            fstring_lines.append((i+1, line.strip()))

    return fstring_lines


def suggest_conversion(line):
    """پیشنهاد تبدیل f-string به فرمت % برای یک خط"""

    # برخی الگوهای رایج در file_manager.py

    # الگوی 1: logger.xxx(f"... {var} ...")
    logger_match = re.match(
        r'(\s*)(logger\.\w+)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)', line)
    if logger_match:
        indent, logger_func, before, var, after = logger_match.groups()
        return f'{indent}{logger_func}("{before}%s{after}", {var})'

    # الگوی 2: print(f"... {var} ...")
    print_match = re.match(
        r'(\s*)(print|raise|return)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)', line)
    if print_match:
        indent, func, before, var, after = print_match.groups()
        return f'{indent}{func}("{before}%s{after}" % ({var}))'

    # الگوی 3: var = f"... {x} ..."
    assign_match = re.match(
        r'(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*f"([^"]*)\{([^{}]+)\}([^"]*)"\s*', line)
    if assign_match:
        indent, var_name, before, exp, after = assign_match.groups()
        return f'{indent}{var_name} = "{before}%s{after}" % ({exp})'

    # الگوی 4: چندین متغیر در f-string
    # این مورد پیچیده‌تر است و باید با دقت بیشتری بررسی شود

    return None  # نمی‌توان به طور خودکار پیشنهادی ارائه داد


def process_file(file_path):
    """پردازش فایل و نمایش پیشنهادات برای f-string ها"""
    print(f"Analyzing file: {file_path}\n")

    # خواندن محتوای فایل
    lines = read_file(file_path)

    # شناسایی خطوط حاوی f-string
    fstring_lines = identify_fstrings(lines)

    if not fstring_lines:
        print("No f-strings found in the file.")
        return

    print(f"Found {len(fstring_lines)} lines with f-strings:\n")

    # نمایش و پیشنهاد تبدیل
    for line_num, line_content in fstring_lines:
        print(f"Line {line_num}: {line_content}")

        suggestion = suggest_conversion(line_content)
        if suggestion:
            print(f"Suggested: {suggestion}\n")
        else:
            print("No automatic suggestion available for this line.\n")

    print("\nTo make these changes, you'll need to edit the file manually.")
    print("Be careful with complex f-strings that may need special handling.")


def main():
    """تابع اصلی برنامه"""
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = 'file_manager.py'

    # بررسی وجود فایل
    if not os.path.isfile(file_path):
        print(f"Error: File not found at {file_path}")
        print("Usage: python analyze_fstrings.py [path/to/file_manager.py]")
        sys.exit(1)

    # پردازش فایل
    process_file(file_path)


if __name__ == "__main__":
    main()
