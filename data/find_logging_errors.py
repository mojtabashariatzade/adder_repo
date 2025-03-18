#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to find logging-related errors in JSON lint output files.
"""

import os
import json
import sys
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
        import re
        result = re.search(pattern, code_line)
        if result:
            fixed_line = re.sub(pattern, replacement, code_line)
            pattern_used = f"Pattern {i+1}"
            break

    if not fixed_line:
        # Try to handle more complex cases
        # Check if line contains logger call with f-string inside
        if "logger." in code_line and "{" in code_line and "}" in code_line:
            # This needs more sophisticated handling, maybe manual intervention
            return None, "Complex logging pattern - manual fix needed"

    return fixed_line, pattern_used


def apply_fixes_to_file(file_path, errors):
    """Apply fixes to file based on identified errors."""
    try:
        # Try multiple path formats to find the file
        possible_paths = []

        # Original path
        possible_paths.append(file_path)

        # Try with backslashes
        if '/' in file_path:
            possible_paths.append(file_path.replace('/', '\\'))

        # Try with forward slashes
        if '\\' in file_path:
            possible_paths.append(file_path.replace('\\', '/'))

        # Try without drive letter
        if ':' in file_path:
            drive, rest = file_path.split(':', 1)
            possible_paths.append(rest)

            # Also try with different slash style
            if '/' in rest:
                possible_paths.append(rest.replace('/', '\\'))
            if '\\' in rest:
                possible_paths.append(rest.replace('\\', '/'))

        # Try with leading slash removed
        if file_path.startswith('/'):
            possible_paths.append(file_path[1:])

        # Try with modified separators
        if '/adder_repo/' in file_path:
            _, rel_path = file_path.split('/adder_repo/', 1)
            possible_paths.append(os.path.join('F:\\adder_repo', rel_path))
            possible_paths.append(os.path.join('F:/adder_repo', rel_path))

        # Try all possible paths
        actual_path = None
        for path in possible_paths:
            if os.path.exists(path):
                actual_path = path
                break

        if not actual_path:
            print(f"File not found. Tried paths: {possible_paths}")
            return False

        # Read file
        with open(actual_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Track lines that were fixed
        fixed_lines = []
        failed_fixes = []

        # Fix each error
        for error in errors:
            line_num = error.get('startLineNumber', 0)

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


def format_error(error):
    """Format an error for printing."""
    file_path = error.get('resource', 'Unknown file')
    message = error.get('message', 'No message')
    severity = error.get('severity', 0)
    line = error.get('startLineNumber', 0)
    column = error.get('startColumn', 0)

    severity_str = "Error" if severity >= 8 else "Warning" if severity >= 4 else "Info"

    # Try to read the actual line from the source file
    code_line = ""
    try:
        # Try multiple path formats to find the file
        possible_paths = []

        # Original path
        possible_paths.append(file_path)

        # Try with backslashes
        if '/' in file_path:
            possible_paths.append(file_path.replace('/', '\\'))

        # Try with forward slashes
        if '\\' in file_path:
            possible_paths.append(file_path.replace('\\', '/'))

        # Try without drive letter
        if ':' in file_path:
            drive, rest = file_path.split(':', 1)
            possible_paths.append(rest)

            # Also try with different slash style
            if '/' in rest:
                possible_paths.append(rest.replace('/', '\\'))
            if '\\' in rest:
                possible_paths.append(rest.replace('\\', '/'))

        # Try with leading slash removed
        if file_path.startswith('/'):
            possible_paths.append(file_path[1:])

        # Try with modified separators
        if '/adder_repo/' in file_path:
            _, rel_path = file_path.split('/adder_repo/', 1)
            possible_paths.append(os.path.join('F:\\adder_repo', rel_path))
            possible_paths.append(os.path.join('F:/adder_repo', rel_path))

        # Try all possible paths
        file_found = False
        for path in possible_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if 0 < line <= len(lines):
                        code_line = lines[line-1].strip()
                        file_found = True
                        break

        if not file_found:
            print(f"File not found. Tried paths: {possible_paths}")
    except Exception as e:
        print(f"Error reading source file: {e}")

    return {
        "file": os.path.basename(file_path),
        "path": file_path,
        "line": line,
        "column": column,
        "severity": severity_str,
        "message": message,
        "code": code_line
    }


def process_json_directory(directory_path):
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
                formatted_error = format_error(error)
                all_errors.append(formatted_error)

                # Also organize by source file
                source_file = formatted_error["file"]
                errors_by_file[source_file].append(formatted_error)

    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Total logging errors found: {len(all_errors)}")
    print("\nErrors by file:")
    for file, errors in errors_by_file.items():
        print(f"  {file}: {len(errors)} errors")

    # Print detailed errors
    if all_errors:
        print("\n=== DETAILED ERRORS ===")
        for idx, error in enumerate(all_errors, 1):
            print(
                f"\n{idx}. {error['file']} (Line {error['line']}, Col {error['column']})")
            print(f"   {error['severity']}: {error['message']}")


def main():
    """Main function."""
    if len(sys.argv) > 1:
        json_dir = sys.argv[1]
    else:
        json_dir = input("Enter the path to the JSON directory: ")

    # Allow user to specify project root for resolving file paths
    project_root = input(
        "Enter the project root path (e.g., F:\\adder_repo): ")

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
            process_json_directory(json_dir)
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
                        errors_by_file = {}
                        for error in logging_errors:
                            if 'resource' in error:
                                file_resource = error['resource']
                                # Extract the relative path after the repo name
                                if project_root:
                                    # Make sure project_root has correct format
                                    if '\\' in project_root and '/' in file_resource:
                                        # If resource uses / but project_root uses \
                                        project_root_slash = project_root.replace(
                                            '\\', '/')
                                        if '/adder_repo/' in file_resource:
                                            _, rel_path = file_resource.split(
                                                '/adder_repo/', 1)
                                            file_resource = os.path.join(
                                                project_root, rel_path)
                                    elif '/' in project_root and '\\' in file_resource:
                                        # If resource uses \ but project_root uses /
                                        project_root_backslash = project_root.replace(
                                            '/', '\\')
                                        if '\\adder_repo\\' in file_resource:
                                            _, rel_path = file_resource.split(
                                                '\\adder_repo\\', 1)
                                            file_resource = os.path.join(
                                                project_root, rel_path)

                                if file_resource not in errors_by_file:
                                    errors_by_file[file_resource] = []
                                errors_by_file[file_resource].append(error)

                        # Print summary
                        print("\n=== SUMMARY ===")
                        print(f"Found errors in {len(errors_by_file)} files")
                        for file, errors in errors_by_file.items():
                            print(
                                f"  {os.path.basename(file)}: {len(errors)} errors")

                        # Ask if user wants to apply fixes
                        if errors_by_file:
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
                                    formatted_error = format_error(error)
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
                                            f"    Source file: {file_path} (not found or couldn't be read)")
                else:
                    print("Invalid selection")
            except ValueError:
                print("Please enter a number or 'all'")

    except Exception as e:
        print(f"Error listing directory {json_dir}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
