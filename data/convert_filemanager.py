#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
اسکریپت پیشرفته اصلاح کد - بر اساس convert_filemanager.py
این اسکریپت می‌تواند خطاهای مختلف را در کدهای پایتون شناسایی و اصلاح کند.
قابلیت پردازش مستقیم خروجی linter و ذخیره پایگاه داده الگوهای خطا را دارد.

استفاده:
    # اصلاح مستقیم فایل
    python advanced_code_fixer.py file_manager.py --fix

    # استفاده با خروجی لینتر
    pylint file_manager.py | python advanced_code_fixer.py --from-lint

    # اصلاح براساس شماره خط‌ها
    python advanced_code_fixer.py file_manager.py --lines 330,639,649,655 --fix

    # اصلاح چندین فایل به صورت دسته‌ای
    python advanced_code_fixer.py file1.py file2.py --fix
"""

import re
import os
import sys
import json
import argparse
from pathlib import Path
import tempfile
from datetime import datetime
import traceback


# مسیر فایل پایگاه داده الگوهای خطا
ERROR_PATTERNS_DB = "error_patterns.json"

# الگوهای پیش‌فرض خطاها
DEFAULT_ERROR_PATTERNS = {
    "f-string": {
        "pattern": r'f["\'].*\{.*\}.*["\']',
        "fix_function": "convert_fstring"
    },
    "mixed-format": {
        "pattern": r'"[^"]*%[^"]*\{[^{}]+\}[^"]*"[^,]*%\s*\(',
        "fix_function": "fix_mixed_format"
    },
    "missing-from-e": {
        "pattern": r'raise\s+[A-Za-z]+Error\s*\([^)]+\)(?!\s*from)',
        "fix_function": "fix_missing_from_e"
    },
    "logger-fstring": {
        "pattern": r'logger\.\w+\(["\'][^"\']*\{[^{}]+\}[^"\']*["\']\)',
        "fix_function": "fix_logger_fstring"
    },
    "unspecified-encoding": {
        "pattern": r'open\([^,)]*\)',
        "fix_function": "fix_unspecified_encoding"
    },
    "redefined-builtin": {
        "pattern": r'\b(dir|id|max|min|sum|len|type|str|int|float|bool|list|dict|set|tuple|object)\s*=',
        "fix_function": "fix_redefined_builtin"
    },
    "bare-except": {
        "pattern": r'except:',
        "fix_function": "fix_bare_except"
    }
}


def load_error_patterns():
    """بارگیری الگوهای خطا از فایل یا استفاده از الگوهای پیش‌فرض"""
    try:
        if os.path.exists(ERROR_PATTERNS_DB):
            with open(ERROR_PATTERNS_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"خطا در بارگیری الگوهای خطا: {e}")

    return DEFAULT_ERROR_PATTERNS


def save_error_patterns(patterns):
    """ذخیره الگوهای خطا در فایل"""
    try:
        with open(ERROR_PATTERNS_DB, 'w', encoding='utf-8') as f:
            json.dump(patterns, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"خطا در ذخیره الگوهای خطا: {e}")


def read_file(file_path):
    """خواندن محتوای فایل"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.readlines()
    except UnicodeDecodeError:
        # تلاش دوباره با encoding دیگر
        try:
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.readlines()
        except Exception as e:
            print(f"خطا در خواندن فایل: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"خطا در خواندن فایل: {e}")
        sys.exit(1)


def write_file(file_path, lines):
    """نوشتن محتوا در فایل"""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)
        print(f"فایل با موفقیت به‌روزرسانی شد: {file_path}")
    except Exception as e:
        print(f"خطا در نوشتن فایل: {e}")
        sys.exit(1)


def create_backup(file_path):
    """ایجاد نسخه پشتیبان از فایل"""
    backup_path = f"{file_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        with open(file_path, 'r', encoding='utf-8') as src, open(backup_path, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
        print(f"نسخه پشتیبان ایجاد شد: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"خطا در ایجاد نسخه پشتیبان: {e}")
        return None


def parse_lint_output(lint_output):
    """تجزیه خروجی لینتر و استخراج شماره خط و نوع خطا"""
    line_errors = []

    # الگوهای مختلف خروجی لینتر را پشتیبانی می‌کنیم
    # pylint
    pylint_pattern = r'.*\[Ln (\d+), Col \d+\]'

    for line in lint_output.splitlines():
        # بررسی الگوی pylint
        match = re.search(pylint_pattern, line)
        if match:
            line_number = int(match.group(1))
            # تعیین نوع خطا براساس متن خطا
            error_type = "unknown"
            if "unspecified-encoding" in line:
                error_type = "unspecified-encoding"
            elif "raise-missing-from" in line:
                error_type = "missing-from-e"
            elif "redefined-builtin" in line:
                error_type = "redefined-builtin"
            elif "bare-except" in line:
                error_type = "bare-except"
            elif "f-string" in line.lower():
                error_type = "f-string"
            elif "{" in line and "%" in line:
                error_type = "mixed-format"

            line_errors.append((line_number, error_type, line))

    return line_errors


def identify_errors_in_line(line, patterns):
    """شناسایی انواع خطاها در یک خط"""
    found_errors = []

    for error_type, error_info in patterns.items():
        if re.search(error_info["pattern"], line):
            found_errors.append(error_type)

    return found_errors


def convert_fstring(line):
    """تبدیل f-string به فرمت %"""

    # الگوی 1: logger.xxx(f"... {var} ...")
    logger_match = re.match(
        r'(\s*)(logger\.\w+)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)(.*)', line)
    if logger_match:
        indent, logger_func, before, var, after, rest = logger_match.groups()
        return f'{indent}{logger_func}("{before}%s{after}", {var}){rest}'

    # الگوی 2: print|raise|return(f"... {var} ...")
    func_match = re.match(
        r'(\s*)(print|raise|return)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)(.*)', line)
    if func_match:
        indent, func, before, var, after, rest = func_match.groups()
        return f'{indent}{func}("{before}%s{after}" % ({var})){rest}'

    # الگوی 3: var = f"... {x} ..."
    assign_match = re.match(
        r'(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*f"([^"]*)\{([^{}]+)\}([^"]*)"\s*(.*)', line)
    if assign_match:
        indent, var_name, before, exp, after, rest = assign_match.groups()
        return f'{indent}{var_name} = "{before}%s{after}" % ({exp}){rest}'

    # پشتیبانی از f-string با تک کوتیشن
    logger_match = re.match(
        r"(\s*)(logger\.\w+)\(f'([^']*)\{([^{}]+)\}([^']*)'\)(.*)", line)
    if logger_match:
        indent, logger_func, before, var, after, rest = logger_match.groups()
        return f'{indent}{logger_func}("{before}%s{after}", {var}){rest}'

    # در صورتی که هیچ الگویی مطابقت نداشت
    return None


def fix_mixed_format(line):
    """اصلاح خطوط با فرمت‌های ترکیبی % و {} که ناسازگار هستند"""

    # مثال: "Error decrypting %s: {e}" % (path)
    mixed_match = re.match(
        r'(\s*)(.*)"([^"]*%[^"]*)\{([^{}]+)\}([^"]*)"(\s*%\s*\(([^)]+)\))(.*)', line)

    if mixed_match:
        indent, prefix, before, var, after, fmt_part, fmt_var, suffix = mixed_match.groups()
        # جایگزینی {} با %s و اضافه کردن متغیر به لیست فرمت
        return f'{indent}{prefix}"{before}%s{after}"{fmt_part[:-1]}, {var}){suffix}'

    return None


def fix_missing_from_e(line):
    """اضافه کردن from e به خطوط raise که آن را ندارند"""

    # پیدا کردن الگوی raise ExceptionType(...)
    raise_match = re.match(
        r'(\s*)(raise\s+[A-Za-z]+Error\s*\([^)]+\))(\s*)(.*)', line)

    if raise_match:
        indent, raise_part, whitespace, rest = raise_match.groups()
        # اضافه کردن from e
        return f'{indent}{raise_part} from e{whitespace}{rest}'

    return None


def fix_logger_fstring(line):
    """تبدیل logger.error با f-string پنهان به فرمت صحیح"""

    # الگوی logger.error("message with {var}")
    logger_match = re.match(
        r'(\s*)(logger\.\w+)\((["\'])([^"\']*)\{([^{}]+)\}([^"\']*)\3(.*)', line)

    if logger_match:
        indent, logger_func, quote, before, var, after, rest = logger_match.groups()
        if ',' not in rest or rest.strip() == ')':  # اگر پارامتر مجزایی وجود ندارد
            return f'{indent}{logger_func}({quote}{before}%s{after}{quote}, {var}{rest}'

    return None


def fix_unspecified_encoding(line):
    """اضافه کردن encoding به توابع open"""

    # الگوی open(... بدون encoding
    open_match = re.match(
        r'(\s*)(.*open\()([^,)]*)((\)|, [^)]*))', line)

    if open_match:
        indent, prefix, file_path, suffix, _ = open_match.groups()
        if 'encoding' not in suffix:
            # اضافه کردن encoding='utf-8' قبل از پرانتز بسته
            if ')' in suffix:
                new_suffix = ', encoding=\'utf-8\'' + suffix
            else:
                new_suffix = suffix.replace(', ', ', encoding=\'utf-8\', ', 1)
            return f'{indent}{prefix}{file_path}{new_suffix}'

    return None


def fix_redefined_builtin(line):
    """اصلاح متغیرهایی که نام‌های تعبیه‌شده را بازتعریف می‌کنند"""

    # الگوی تعریف متغیر با نام تعبیه‌شده
    builtin_match = re.match(
        r'(\s*)(\b(?:dir|id|max|min|sum|len|type|str|int|float|bool|list|dict|set|tuple|object)\b)(\s*=\s*)(.*)', line)

    if builtin_match:
        indent, builtin_name, assign_op, value = builtin_match.groups()
        # اضافه کردن پسوند '_var' به نام متغیر
        return f'{indent}{builtin_name}_var{assign_op}{value}'

    return None


def fix_bare_except(line):
    """اصلاح except: به except Exception:"""

    # الگوی except:
    except_match = re.match(
        r'(\s*)(except)(\s*:)(.*)', line)

    if except_match:
        indent, except_keyword, colon, rest = except_match.groups()
        # تبدیل به except Exception:
        return f'{indent}{except_keyword} Exception{colon}{rest}'

    return None


def get_fix_function(error_type, patterns):
    """دریافت تابع اصلاح کننده براساس نوع خطا"""
    if error_type not in patterns:
        return None

    func_name = patterns[error_type]["fix_function"]

    # نگاشت نام تابع به تابع واقعی
    function_map = {
        "convert_fstring": convert_fstring,
        "fix_mixed_format": fix_mixed_format,
        "fix_missing_from_e": fix_missing_from_e,
        "fix_logger_fstring": fix_logger_fstring,
        "fix_unspecified_encoding": fix_unspecified_encoding,
        "fix_redefined_builtin": fix_redefined_builtin,
        "fix_bare_except": fix_bare_except
    }

    return function_map.get(func_name)


def fix_line(line, error_type, patterns):
    """اصلاح خط براساس نوع خطا"""
    fix_func = get_fix_function(error_type, patterns)
    if fix_func:
        return fix_func(line.rstrip('\n'))
    return None


def fix_file_by_lines(file_path, line_errors, auto_fix=False):
    """اصلاح خطوط مشخصی از فایل"""
    # بارگیری الگوهای خطا
    patterns = load_error_patterns()

    # خواندن فایل
    lines = read_file(file_path)

    # آماده‌سازی ردیابی تغییرات
    changes = []
    fixed_count = 0

    # اصلاح خط‌های مشخص شده
    for line_number, error_type, _ in line_errors:
        # تنظیم شماره خط (لینترها از 1 شروع می‌کنند، ولی لیست‌های پایتون از 0)
        index = line_number - 1

        if index < 0 or index >= len(lines):
            print(f"شماره خط نامعتبر: {line_number}")
            continue

        original_line = lines[index].rstrip('\n')

        # اگر نوع خطا مشخص نشده، تلاش کنیم آن را تشخیص دهیم
        if error_type == "unknown":
            detected_errors = identify_errors_in_line(original_line, patterns)
            if detected_errors:
                error_type = detected_errors[0]
            else:
                print(
                    f"هیچ خطایی در خط {line_number} تشخیص داده نشد: {original_line}")
                continue

        # اصلاح خط
        fixed_line = fix_line(original_line, error_type, patterns)

        if fixed_line:
            # ثبت تغییر
            changes.append({
                "line_number": line_number,
                "error_type": error_type,
                "original": original_line,
                "fixed": fixed_line
            })

            # اعمال تغییر اگر auto_fix فعال است
            if auto_fix:
                lines[index] = fixed_line + '\n'
                fixed_count += 1
                print(f"خط {line_number} اصلاح شد ({error_type}):")
                print(f"  اصلی: {original_line}")
                print(f"  اصلاح شده: {fixed_line}\n")
            else:
                print(f"خط {line_number} ({error_type}): {original_line}")
                print(f"پیشنهاد اصلاح: {fixed_line}\n")
        else:
            print(
                f"امکان اصلاح خودکار خط {line_number} نیست ({error_type}): {original_line}\n")

    # اعمال تغییرات اگر auto_fix فعال است و تغییراتی وجود داشته باشد
    if auto_fix and fixed_count > 0:
        # ایجاد نسخه پشتیبان
        create_backup(file_path)

        # اعمال تغییرات
        write_file(file_path, lines)
        print(f"{fixed_count} خط از {len(line_errors)} خط با خطا اصلاح شد.")
    elif not auto_fix:
        print(f"{len(changes)} خط از {len(line_errors)} خط با خطا قابل اصلاح است.")
        print("برای اعمال این تغییرات، از گزینه --fix استفاده کنید.")

    # ذخیره گزارش تغییرات
    if changes:
        report_path = f"fix_report_{os.path.basename(file_path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "file": file_path,
                    "timestamp": datetime.now().isoformat(),
                    "changes": changes
                }, f, ensure_ascii=False, indent=2)
            print(f"گزارش تغییرات در {report_path} ذخیره شد.")
        except Exception as e:
            print(f"خطا در ذخیره گزارش: {e}")

    return fixed_count


def find_errors_in_file(file_path):
    """یافتن خطاها در کل فایل"""
    # بارگیری الگوهای خطا
    patterns = load_error_patterns()

    # خواندن فایل
    lines = read_file(file_path)

    # جستجوی خطاها در تمام خط‌ها
    line_errors = []

    for i, line in enumerate(lines):
        errors = identify_errors_in_line(line, patterns)
        if errors:
            # خط+1 چون شماره خط‌ها از 1 شروع می‌شوند
            line_errors.append((i+1, errors[0], line))

    return line_errors


def process_files(files, args):
    """پردازش یک یا چند فایل"""
    total_fixed = 0

    for file_path in files:
        print(f"\nپردازش فایل: {file_path}")

        if not os.path.isfile(file_path):
            print(f"خطا: فایل {file_path} یافت نشد")
            continue

        # تعیین خط‌های با خطا
        if args.from_lint or args.lint_file:
            # استفاده از خروجی لینتر
            lint_output = ""
            if args.from_lint:
                # خواندن از stdin
                if not sys.stdin.isatty():
                    lint_output = sys.stdin.read()
            elif args.lint_file:
                # خواندن از فایل
                try:
                    with open(args.lint_file, 'r', encoding='utf-8') as f:
                        lint_output = f.read()
                except Exception as e:
                    print(f"خطا در خواندن فایل لینتر: {e}")
                    continue

            # تجزیه خروجی لینتر
            line_errors = parse_lint_output(lint_output)
        elif args.lines:
            # استفاده از شماره خط‌های مشخص شده
            line_errors = [(int(line.strip()), "unknown", "")
                           for line in args.lines.split(',')]
        else:
            # بررسی کل فایل
            line_errors = find_errors_in_file(file_path)

        if not line_errors:
            print(f"هیچ خطایی در فایل {file_path} یافت نشد.")
            continue

        # اصلاح خطوط
        fixed = fix_file_by_lines(file_path, line_errors, args.fix)
        total_fixed += fixed

    return total_fixed


def main():
    """تابع اصلی برنامه"""
    parser = argparse.ArgumentParser(description='اسکریپت پیشرفته اصلاح کد')
    parser.add_argument('files', nargs='*', help='فایل‌های مورد پردازش')
    parser.add_argument('--fix', action='store_true', help='اعمال اصلاحات')
    parser.add_argument(
        '--lines', help='شماره خط‌های با خطا (با کاما جدا شده)')
    parser.add_argument('--from-lint', action='store_true',
                        help='استفاده از خروجی لینتر از ورودی استاندارد')
    parser.add_argument('--lint-file', help='فایل حاوی خروجی لینتر')

    args = parser.parse_args()

    # بررسی ورودی‌ها
    if not args.files and not args.from_lint and not args.lint_file:
        parser.print_help()
        sys.exit(1)

    # پردازش فایل‌ها
    try:
        total_fixed = process_files(args.files, args)
        if total_fixed > 0:
            print(f"\nدر مجموع {total_fixed} خط اصلاح شد.")
        else:
            print("\nهیچ خطی اصلاح نشد.")
    except KeyboardInterrupt:
        print("\nعملیات توسط کاربر متوقف شد.")
    except Exception as e:
        print(f"\nخطای غیرمنتظره: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
