#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to find and correct logging-related errors in JSON lint output files.
This script searches for W1203:logging-fstring-interpolation errors in JSON files,
finds the corresponding source files, and can apply fixes to convert f-strings
to proper % formatting in logging functions.
"""

import os
import json
import sys
import re
from collections import defaultdict


def load_json_file(file_path):
    """Load a JSON file and return its contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return []


def find_logging_errors(json_data):
    """Find logging-related errors in the JSON data."""
    logging_errors = []

    for error in json_data:
        # Check for logging-related error codes
        if 'code' in error and 'value' in error['code']:
            error_code = error['code']['value']
            if error_code == "W1203:logging-fstring-interpolation":
                logging_errors.append(error)
            # Add other logging-related error codes if needed

    return logging_errors


def fix_logging_fstring(file_path, line_number, code_line):
    """Fix f-string in logging functions."""
    if not code_line:
        return None, "Empty code line"

    # Different patterns for f-string in logging
    patterns = [
        # Pattern 1: logger.xxx(f"... {var} ...")
        (r'(\s*)(logger\.\w+)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)(.*)',
         r'\1\2("\3%s\5", \4)\6'),
        # Pattern 2: logger.xxx(f'... {var} ...')
        (r"(\s*)(logger\.\w+)\(f'([^']*)\{([^{}]+)\}([^']*)'\)(.*)",
         r'\1\2("\3%s\5", \4)\6'),
        # Pattern 3: xxx.debug(f"... {var} ...")
        (r'(\s*)(\w+\.debug)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)(.*)',
         r'\1\2("\3%s\5", \4)\6'),
        # Pattern 4: xxx.info(f"... {var} ...")
        (r'(\s*)(\w+\.info)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)(.*)',
         r'\1\2("\3%s\5", \4)\6'),
        # Pattern 5: xxx.warning(f"... {var} ...")
        (r'(\s*)(\w+\.warning)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)(.*)',
         r'\1\2("\3%s\5", \4)\6'),
        # Pattern 6: xxx.error(f"... {var} ...")
        (r'(\s*)(\w+\.error)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)(.*)',
         r'\1\2("\3%s\5", \4)\6'),
        # Pattern 7: xxx.critical(f"... {var} ...")
        (r'(\s*)(\w+\.critical)\(f"([^"]*)\{([^{}]+)\}([^"]*)"\)(.*)',
         r'\1\2("\3%s\5", \4)\6'),
    ]

    fixed_line = None
    pattern_used = None

    for i, (pattern, replacement) in enumerate(patterns):
        result = re.search(pattern, code_line)
        if result:
            fixed_line = re.sub(pattern, replacement, code_line)
            pattern_used = f"Pattern {i+1}"
            break

    if not fixed_line:
        # Try to handle more complex cases with multiple variables
        if "logger." in code_line and "{" in code_line and "}" in code_line:
            # This needs more sophisticated handling, maybe manual intervention
            return None, "Complex logging pattern - manual fix needed"

    return fixed_line, pattern_used


def find_source_file_path(file_path_resource, project_root=None):
    """Try multiple approaches to find the actual source file."""
    possible_paths = []

    # Original path
    possible_paths.append(file_path_resource)

    # Try with backslashes
    if '/' in file_path_resource:
        possible_paths.append(file_path_resource.replace('/', '\\'))

    # Try with forward slashes
    if '\\' in file_path_resource:
        possible_paths.append(file_path_resource.replace('\\', '/'))

    # Try without drive letter
    if ':' in file_path_resource:
        drive, rest = file_path_resource.split(':', 1)
        possible_paths.append(rest)

        # Also try with different slash style
        if '/' in rest:
            possible_paths.append(rest.replace('/', '\\'))
        if '\\' in rest:
            possible_paths.append(rest.replace('\\', '/'))

    # Try with leading slash removed
    if file_path_resource.startswith('/'):
        possible_paths.append(file_path_resource[1:])

    # Try with project root
    if project_root and '/adder_repo/' in file_path_resource:
        _, rel_path = file_path_resource.split('/adder_repo/', 1)
        possible_paths.append(os.path.join(project_root, rel_path))
        possible_paths.append(os.path.join(
            project_root, rel_path.replace('/', '\\')))

    if project_root and '\\adder_repo\\' in file_path_resource:
        _, rel_path = file_path_resource.split('\\adder_repo\\', 1)
        possible_paths.append(os.path.join(project_root, rel_path))
        possible_paths.append(os.path.join(
            project_root, rel_path.replace('\\', '/')))

    # Try each path
    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def read_source_line(file_path, line_number):
    """Read a specific line from a source file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if 0 < line_number <= len(lines):
                return lines[line_number - 1].strip()
            else:
                print(
                    f"Warning: Line number {line_number} out of range for file {file_path} with {len(lines)} lines")
    except Exception as e:
        print(f"Error reading line {line_number} from {file_path}: {e}")
    return None


def apply_fixes_to_file(file_path, errors):
    """Apply fixes to file based on identified errors."""
    try:
        # Find the actual file
        actual_path = find_source_file_path(file_path)

        if not actual_path:
            print(f"File not found: {file_path}")
            return False

        # Read file
        with open(actual_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Track lines that were fixed
        fixed_lines = []
        failed_fixes = []

        # Fix each error
        for error in errors:
            # Use the exact line number from the error report
            line_num = error.get('startLineNumber', 0)

            # Check if the line exists and contains a logger call
            if 0 < line_num <= len(lines):
                original_line = lines[line_num - 1]
                has_logger = any(x in original_line for x in [
                                 "logger.", ".error", ".info", ".warning", ".debug", ".critical"])

                # If not, try the line before (sometimes line numbers are off by one)
                if not has_logger and line_num > 1:
                    prev_line_num = line_num - 1
                    prev_line = lines[prev_line_num - 1]
                    if any(x in prev_line for x in ["logger.", ".error", ".info", ".warning", ".debug", ".critical"]):
                        print(
                            f"Note: Using line {prev_line_num} instead of reported line {line_num}")
                        line_num = prev_line_num
                        original_line = prev_line

            if 0 < line_num <= len(lines):
                original_line = lines[line_num - 1]
                fixed_line, pattern_used = fix_logging_fstring(
                    actual_path, line_num, original_line.rstrip('\n'))

                if fixed_line:
                    lines[line_num - 1] = fixed_line + '\n'
                    fixed_lines.append({
                        'line': line_num,
                        'original': original_line.strip(),
                        'fixed': fixed_line,
                        'pattern': pattern_used
                    })
                else:
                    failed_fixes.append({
                        'line': line_num,
                        'original': original_line.strip(),
                        'reason': pattern_used  # In this case, pattern_used contains the error message
                    })

        # If we fixed any lines, write back to file
        if fixed_lines:
            # Create backup
            backup_path = f"{actual_path}.bak"
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)  # Store the current lines as backup

            # Write fixed content
            with open(actual_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            print(f"\nApplied {len(fixed_lines)} fixes to {actual_path}")
            print("Fixed lines:")
            for fix in fixed_lines:
                print(f"  Line {fix['line']} using {fix['pattern']}:")
                print(f"    FROM: {fix['original']}")
                print(f"    TO:   {fix['fixed']}")

            if failed_fixes:
                print("\nFailed to fix:")
                for fail in failed_fixes:
                    print(f"  Line {fail['line']}: {fail['reason']}")
                    print(f"    {fail['original']}")

            return True
        else:
            print(f"No fixes applied to {actual_path} - no valid fixes found")

            if failed_fixes:
                print("\nFailed to fix:")
                for fail in failed_fixes:
                    print(f"  Line {fail['line']}: {fail['reason']}")
                    print(f"    {fail['original']}")

            return False

    except Exception as e:
        print(f"Error fixing file {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return False


def format_error(error, project_root=None):
    """Format an error for printing with the actual source code line."""
    file_path = error.get('resource', 'Unknown file')
    message = error.get('message', 'No message')
    severity = error.get('severity', 0)
    # Use the exact line number from JSON
    line_num = error.get('startLineNumber', 0)
    column = error.get('startColumn', 0)

    severity_str = "Error" if severity >= 8 else "Warning" if severity >= 4 else "Info"

    # Find the actual source file
    source_file_path = find_source_file_path(file_path, project_root)
    code_line = None

    if source_file_path:
        # Try to read the exact line
        code_line = read_source_line(source_file_path, line_num)

        # If line not found or doesn't contain logging f-string, try adjacent lines
        if not code_line or ("logger." not in code_line and ".error" not in code_line
                             and ".info" not in code_line and ".warning" not in code_line
                             and ".debug" not in code_line and ".critical" not in code_line):
            # Try the line before
            alt_line = read_source_line(source_file_path, line_num - 1)
            if alt_line and any(x in alt_line for x in ["logger.", ".error", ".info", ".warning", ".debug", ".critical"]):
                code_line = alt_line
                print(
                    f"Note: Using line {line_num-1} instead of reported line {line_num} for {os.path.basename(file_path)}")
                line_num = line_num - 1  # Update the line number

    return {
        "file": os.path.basename(file_path),
        "path": file_path,
        "actual_path": source_file_path,
        "line": line_num,
        "column": column,
        "severity": severity_str,
        "message": message,
        "code": code_line
    }


def process_json_directory(directory_path, project_root=None, auto_fix=False):
    """Process all JSON files in the directory for logging errors."""
    all_errors = []
    errors_by_file = defaultdict(list)

    # List all JSON files in the directory
    try:
        json_files = [f for f in os.listdir(
            directory_path) if f.endswith('.json')]
    except Exception as e:
        print(f"Error listing directory {directory_path}: {e}")
        return

    print(f"Found {len(json_files)} JSON files in {directory_path}")

    # Process each JSON file
    for json_file in json_files:
        file_path = os.path.join(directory_path, json_file)
        json_data = load_json_file(file_path)

        if not json_data:
            continue

        logging_errors = find_logging_errors(json_data)

        if logging_errors:
            print(
                f"\nFound {len(logging_errors)} logging errors in {json_file}")
            for error in logging_errors:
                formatted_error = format_error(error, project_root)
                all_errors.append(formatted_error)

                # Organize by source file
                source_file = formatted_error["path"]
                errors_by_file[source_file].append(error)

    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Total logging errors found: {len(all_errors)}")
    print("\nErrors by file:")
    for file, errors in errors_by_file.items():
        print(f"  {os.path.basename(file)}: {len(errors)} errors")

    # Apply fixes if requested
    if auto_fix:
        print("\n=== APPLYING FIXES ===")
        for file_path, file_errors in errors_by_file.items():
            print(f"\nProcessing {file_path}...")
            apply_fixes_to_file(file_path, file_errors)

    # Print detailed errors
    print("\n=== DETAILED ERRORS ===")
    for idx, error in enumerate(all_errors, 1):
        print(
            f"\n{idx}. {error['file']} (Line {error['line']}, Col {error['column']})")
        print(f"   {error['severity']}: {error['message']}")
        if error['code']:
            print(f"   Code: {error['code']}")
        else:
            print(
                f"   Source file not found or couldn't be read: {error['path']}")

    return all_errors, errors_by_file


def main():
    """Main function to handle command-line arguments and run the script."""
    # Check command-line arguments
    if len(sys.argv) > 1:
        json_dir = sys.argv[1]
    else:
        json_dir = input("Enter the path to the JSON directory: ")

    # Allow user to specify project root for resolving file paths
    project_root = input(
        "Enter the project root path (e.g., F:\\adder_repo): ")

    # Option to automatically fix errors
    auto_fix = input("Automatically apply fixes? (y/n): ").lower() == 'y'

    if not os.path.isdir(json_dir):
        print(f"Error: {json_dir} is not a valid directory")
        return

    # List JSON files in the directory
    try:
        json_files = [f for f in os.listdir(json_dir) if f.endswith('.json')]

        if not json_files:
            print(f"No JSON files found in {json_dir}")
            return

        print("Available JSON files:")
        for idx, file in enumerate(json_files, 1):
            print(f"{idx}. {file}")

        selection = input(
            "\nEnter file number to analyze (or 'all' for all files): ")

        if selection.lower() == 'all':
            process_json_directory(json_dir, project_root, auto_fix)
        else:
            try:
                file_idx = int(selection) - 1
                if 0 <= file_idx < len(json_files):
                    file_path = os.path.join(json_dir, json_files[file_idx])
                    json_data = load_json_file(file_path)
                    if json_data:
                        logging_errors = find_logging_errors(json_data)
                        print(
                            f"\nFound {len(logging_errors)} logging errors in {json_files[file_idx]}")

                        # Group errors by file
                        errors_by_file = defaultdict(list)
                        for error in logging_errors:
                            formatted_error = format_error(error, project_root)
                            source_file = formatted_error["path"]
                            errors_by_file[source_file].append(error)

                        # Print summary
                        print("\n=== SUMMARY ===")
                        print(f"Found errors in {len(errors_by_file)} files")
                        for file, errors in errors_by_file.items():
                            print(
                                f"  {os.path.basename(file)}: {len(errors)} errors")

                        # Apply fixes if requested
                        if auto_fix:
                            for file_path, file_errors in errors_by_file.items():
                                print(f"\nProcessing {file_path}...")
                                apply_fixes_to_file(file_path, file_errors)
                        else:
                            # Ask if user wants to apply fixes
                            fix_option = input("\nApply fixes? (y/n): ")
                            if fix_option.lower() == 'y':
                                for file_path, file_errors in errors_by_file.items():
                                    print(f"\nProcessing {file_path}...")
                                    apply_fixes_to_file(file_path, file_errors)
                            else:
                                print("No fixes applied.")

                        # Print detailed errors
                        show_details = input("\nShow detailed errors? (y/n): ")
                        if show_details.lower() == 'y':
                            print("\n=== DETAILED ERRORS ===")
                            for file_path, file_errors in errors_by_file.items():
                                print(f"\nFile: {os.path.basename(file_path)}")
                                for error in file_errors:
                                    formatted_error = format_error(
                                        error, project_root)
                                    line = formatted_error['line']
                                    col = formatted_error['column']
                                    message = formatted_error['message']
                                    code = formatted_error['code']

                                    print(
                                        f"  Line {line}, Col {col}: {message}")
                                    if code:
                                        print(f"    Code: {code}")
                                    else:
                                        print(
                                            f"    Source file not found or couldn't be read")
                else:
                    print("Invalid selection")
            except ValueError:
                print("Please enter a number or 'all'")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
