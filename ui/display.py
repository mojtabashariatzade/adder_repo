"""
Display Module

This module provides utilities for displaying information and rendering UI elements
in the Telegram Account Manager application. It includes functions for creating
formatted text boxes, tables, menus, and other UI components.

Features:
- Text box rendering with borders and titles
- Table generation with customizable headers and alignment
- Banner and header display for application sections
- Loading and progress indicators
- Error and warning message formatting
- Multi-column layouts
- Console screen clearing and cursor manipulation

Usage:
    from ui.display import (
        clear_screen, print_banner, print_header,
        print_text_box, print_table, print_menu,
        print_error, print_warning, print_success
    )

    # Display a banner
    print_banner("Telegram Account Manager")

    # Display a header for a section
    print_header("Account Management")

    # Display information in a text box
    print_text_box("Operation completed successfully", title="Result")

    # Display tabular data
    headers = ["ID", "Phone", "Status"]
    rows = [
        ["1", "+1234567890", "Active"],
        ["2", "+0987654321", "Blocked"]
    ]
    print_table(headers, rows)
"""

import os
import shutil
import time
from typing import List, Any, Optional, Tuple, Callable

# Import colors module
try:
    from ui.colors import (
        theme_styled,
        print_progress
    )
except ImportError:
    # Fallback if colors module is not available
    class Colors:
        """Fallback Colors class."""
        RESET = BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ""
        BG_BLACK = BG_RED = BG_GREEN = BG_YELLOW = BG_BLUE = BG_MAGENTA = BG_CYAN = BG_WHITE = ""

    class Styles:
        """Fallback Styles class."""
        BOLD = DIM = ITALIC = UNDERLINE = BLINK = REVERSE = NORMAL = ""

    class ColorTheme:
        """Fallback ColorTheme class."""
        @staticmethod
        def get(element: str) -> str:
            return ""

    def colorize(text: str, color: str, reset: bool = True) -> str:
        return text

    def styled_text(text: str, fg: Optional[str] = None,
                    bg: Optional[str] = None, style: Optional[str] = None) -> str:
        return text

    def theme_styled(text: str, element: str) -> str:
        return text

    def print_colored(label: str, value: str, color: Optional[str] = None,
                      label_color: Optional[str] = None) -> None:
        print(f"{label}: {value}")

    def print_status(message: str, status: bool) -> None:
        status_text = "Success" if status else "Failed"
        print(f"{message} {status_text}")

    def print_progress(current: int, total: int, prefix: str = "Progress:",
                       suffix: str = "", width: int = 40) -> None:
        print(f"{prefix} {current}/{total} {suffix}")

    def enable_colors() -> None:
        pass

    def disable_colors() -> None:
        pass


# Get terminal size
def get_terminal_size() -> Tuple[int, int]:
    """
    Get the current terminal width and height.

    Returns:
        Tuple[int, int]: Terminal width and height in characters
    """
    try:
        columns, lines = shutil.get_terminal_size()
        return columns, lines
    except:
        # Fallback to a reasonable default if terminal size can't be determined
        return 80, 24


def clear_screen() -> None:
    """
    Clear the terminal screen.

    This function attempts to clear the screen in a cross-platform way.
    """
    # Clear screen command based on OS
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:  # For Unix/Linux/MacOS
        os.system('clear')


def move_cursor(x: int, y: int) -> None:
    """
    Move the cursor to a specific position in the terminal.

    Args:
        x (int): Column position (0-based)
        y (int): Row position (0-based)
    """
    print(f"\033[{y};{x}H", end='')


def save_cursor_position() -> None:
    """Save the current cursor position."""
    print("\033[s", end='')


def restore_cursor_position() -> None:
    """Restore the cursor to the saved position."""
    print("\033[u", end='')


def print_banner(text: str, width: Optional[int] = None, style: str = 'double') -> None:
    """
    Print a banner with the given text.

    Args:
        text (str): The text to display in the banner
        width (int, optional): The width of the banner. If None, uses terminal width
        style (str): The style of the banner ('single', 'double', 'heavy', 'ascii')
    """
    if width is None:
        term_width, _ = get_terminal_size()
        # Limit width to 80 chars or terminal width
        width = min(term_width, 80)

    # Choose border characters based on style
    if style == 'double':
        top_left = '╔'
        top_right = '╗'
        bottom_left = '╚'
        bottom_right = '╝'
        horizontal = '═'
        vertical = '║'
    elif style == 'heavy':
        top_left = '┏'
        top_right = '┓'
        bottom_left = '┗'
        bottom_right = '┛'
        horizontal = '━'
        vertical = '┃'
    elif style == 'single':
        top_left = '┌'
        top_right = '┐'
        bottom_left = '└'
        bottom_right = '┘'
        horizontal = '─'
        vertical = '│'
    else:  # ASCII style
        top_left = top_right = bottom_left = bottom_right = '+'
        horizontal = '-'
        vertical = '|'

    # Create top and bottom borders
    top_border = top_left + horizontal * (width - 2) + top_right
    bottom_border = bottom_left + horizontal * (width - 2) + bottom_right

    # Calculate padding for centering the text
    padding = (width - 2 - len(text)) // 2
    left_padding = padding
    right_padding = width - 2 - len(text) - left_padding

    # Create the centered text row
    text_row = vertical + ' ' * left_padding + text + ' ' * right_padding + vertical

    # Apply theme colors
    top_border = theme_styled(top_border, 'header')
    text_row = theme_styled(text_row, 'header')
    bottom_border = theme_styled(bottom_border, 'header')

    # Print the banner
    print(top_border)
    print(text_row)
    print(bottom_border)


def print_header(text: str, width: Optional[int] = None,
                 char: str = '=', centered: bool = True) -> None:
    """
    Print a section header.

    Args:
        text (str): The header text
        width (int, optional): The width of the header. If None, uses terminal width
        char (str): The character to use for the separator line
        centered (bool): Whether to center the text
    """
    if width is None:
        term_width, _ = get_terminal_size()
        # Limit width to 80 chars or terminal width
        width = min(term_width, 80)

    # Create the separator line
    separator = char * width

    # Create the text line
    if centered:
        padding = (width - len(text)) // 2
        text_line = ' ' * padding + text + ' ' * (width - len(text) - padding)
    else:
        text_line = text

    # Apply theme colors
    separator = theme_styled(separator, 'title')
    text_line = theme_styled(text_line, 'title')

    # Print the header
    print()
    print(separator)
    print(text_line)
    print(separator)
    print()


def print_text_box(text: str, title: Optional[str] = None,
                   width: Optional[int] = None, style: str = 'single',
                   padding: int = 1) -> None:
    """
    Print text in a bordered box.

    Args:
        text (str): The text to display in the box
        title (str, optional): The title of the box
        width (int, optional): The width of the box. If None, uses terminal width - 4
        style (str): The style of the box ('single', 'double', 'heavy', 'ascii')
        padding (int): Padding inside the box (number of spaces)
    """
    if width is None:
        term_width, _ = get_terminal_size()
        width = min(term_width - 4, 76)  # Leave some margin

    # Choose border characters based on style
    if style == 'double':
        top_left = '╔'
        top_right = '╗'
        bottom_left = '╚'
        bottom_right = '╝'
        horizontal = '═'
        vertical = '║'
        t_right = '╠'
        t_left = '╣'
        t_down = '╦'
        t_up = '╩'
        cross = '╬'
    elif style == 'heavy':
        top_left = '┏'
        top_right = '┓'
        bottom_left = '┗'
        bottom_right = '┛'
        horizontal = '━'
        vertical = '┃'
        t_right = '┣'
        t_left = '┫'
        t_down = '┳'
        t_up = '┻'
        cross = '╋'
    elif style == 'single':
        top_left = '┌'
        top_right = '┐'
        bottom_left = '└'
        bottom_right = '┘'
        horizontal = '─'
        vertical = '│'
        t_right = '├'
        t_left = '┤'
        t_down = '┬'
        t_up = '┴'
        cross = '┼'
    else:  # ASCII style
        top_left = top_right = bottom_left = bottom_right = '+'
        horizontal = '-'
        vertical = '|'
        t_right = t_left = t_down = t_up = cross = '+'

    # Split text into lines that fit within the box
    # Account for borders and padding
    content_width = width - 2 * (padding + 1)
    lines = []

    # If text is a list or tuple, handle each item
    if isinstance(text, (list, tuple)):
        for item in text:
            item_str = str(item)
            # Split long lines
            for i in range(0, len(item_str), content_width):
                lines.append(item_str[i:i + content_width])
    else:
        # Split the text into words
        text_str = str(text)
        words = text_str.split()

        current_line = ""
        for word in words:
            # If adding the word exceeds the content width, start a new line
            if len(current_line + " " + word) > content_width and current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Add word to current line with space if not the first word
                current_line = word if not current_line else current_line + " " + word

        # Add the last line if it's not empty
        if current_line:
            lines.append(current_line)

    # If no lines (empty text), add an empty line
    if not lines:
        lines = [""]

    # Create top border
    if title and title.strip():
        title_len = min(len(title), content_width)
        left_border = (width - title_len - 4) // 2
        right_border = width - left_border - title_len - 4

        top_border = (
            top_left +
            horizontal * left_border +
            t_down +
            ' ' + title[:content_width] + ' ' +
            t_down +
            horizontal * right_border +
            top_right
        )
    else:
        top_border = top_left + horizontal * (width - 2) + top_right

    # Create bottom border
    bottom_border = bottom_left + horizontal * (width - 2) + bottom_right

    # Create empty line for padding
    empty_line = vertical + ' ' * (width - 2) + vertical

    # Apply theme colors
    top_border = theme_styled(top_border, 'info')
    bottom_border = theme_styled(bottom_border, 'info')
    empty_line = theme_styled(empty_line, 'info')

    # Print the box
    print(top_border)

    # Add top padding
    for _ in range(padding):
        print(empty_line)

    # Print each line
    for line in lines:
        # Create the line with padding
        line_text = vertical + ' ' * padding + \
            line.ljust(content_width) + ' ' * padding + vertical
        print(theme_styled(line_text, 'info'))

    # Add bottom padding
    for _ in range(padding):
        print(empty_line)

    print(bottom_border)


def print_table(headers: List[str], rows: List[List[str]],
                title: Optional[str] = None, width: Optional[int] = None,
                alignments: Optional[List[str]] = None) -> None:
    """
    Print data in a formatted table.

    Args:
        headers (List[str]): List of column headers
        rows (List[List[str]]): List of rows, each a list of column values
        title (str, optional): Table title
        width (int, optional): Table width. If None, uses terminal width
        alignments (List[str], optional): List of alignments for each column
                                        ('left', 'center', 'right')
    """
    if not rows:
        print_text_box("No data to display", title=title, style='single')
        return

    # Make sure all rows have the same number of columns as headers
    for i, row in enumerate(rows):
        if len(row) < len(headers):
            rows[i] = row + [''] * (len(headers) - len(row))
        elif len(row) > len(headers):
            rows[i] = row[:len(headers)]

    # If alignments not provided, default to left alignment for all columns
    if not alignments:
        alignments = ['left'] * len(headers)
    elif len(alignments) < len(headers):
        alignments = alignments + ['left'] * (len(headers) - len(alignments))

    # Calculate column widths based on content
    col_widths = []
    for i in range(len(headers)):
        header_width = len(headers[i])
        content_width = max([len(str(row[i])) for row in rows]) if rows else 0
        col_widths.append(max(header_width, content_width))

    # Adjust column widths if total exceeds available width
    if width is None:
        term_width, _ = get_terminal_size()
        width = min(term_width - 4, 76)  # Leave some margin

    # Account for borders and padding
    available_width = width - (len(headers) + 1) - (2 * len(headers))
    total_col_width = sum(col_widths)

    if total_col_width > available_width:
        # Scale down column widths proportionally
        scale_factor = available_width / total_col_width
        col_widths = [max(3, int(w * scale_factor)) for w in col_widths]

    # Choose border characters
    top_left = '┌'
    top_right = '┐'
    bottom_left = '└'
    bottom_right = '┘'
    horizontal = '─'
    vertical = '│'
    t_right = '├'
    t_left = '┤'
    t_down = '┬'
    t_up = '┴'
    cross = '┼'

    # Create separator lines
    top_border = (
        top_left +
        t_down.join([horizontal * (width + 2) for width in col_widths]) +
        top_right
    )

    header_separator = (
        t_right +
        cross.join([horizontal * (width + 2) for width in col_widths]) +
        t_left
    )

    bottom_border = (
        bottom_left +
        t_up.join([horizontal * (width + 2) for width in col_widths]) +
        bottom_right
    )

    # Apply theme colors
    top_border = theme_styled(top_border, 'menu_header')
    header_separator = theme_styled(header_separator, 'menu_header')
    bottom_border = theme_styled(bottom_border, 'menu_header')

    # Print title if provided
    if title:
        print()
        print(theme_styled(title, 'menu_header'))

    # Print the table
    print(top_border)

    # Print headers
    header_row = vertical
    for i, header in enumerate(headers):
        # Align and pad the header
        aligned_header = align_text(header, col_widths[i], alignments[i])
        header_row += f" {aligned_header} {vertical}"

    print(theme_styled(header_row, 'menu_header'))
    print(header_separator)

    # Print rows
    for row in rows:
        row_text = vertical
        for i, cell in enumerate(row):
            cell_str = str(cell) if cell is not None else ""
            aligned_cell = align_text(cell_str, col_widths[i], alignments[i])
            row_text += f" {aligned_cell} {vertical}"

        print(theme_styled(row_text, 'menu_item'))

    print(bottom_border)


def align_text(text: str, width: int, alignment: str = 'left') -> str:
    """
    Align text within a specified width.

    Args:
        text (str): The text to align
        width (int): The width to align within
        alignment (str): The alignment type ('left', 'center', 'right')

    Returns:
        str: The aligned text
    """
    if len(text) > width:
        return text[:width-3] + '...'

    if alignment.lower() == 'center':
        return text.center(width)
    elif alignment.lower() == 'right':
        return text.rjust(width)
    else:  # default to left alignment
        return text.ljust(width)


def print_menu(title: str, options: List[str],
               current_selection: int = 0, description: Optional[str] = None,
               show_numbers: bool = True, show_cursor: bool = True) -> None:
    """
    Print a selectable menu with options.

    Args:
        title (str): The menu title
        options (List[str]): List of menu options
        current_selection (int): Index of the currently selected option
        description (str, optional): Description text for the menu
        show_numbers (bool): Whether to show numbers beside options
        show_cursor (bool): Whether to show a cursor beside the selected option
    """
    if not options:
        print_text_box("No options available", title=title, style='single')
        return

    # Print title
    print()
    print(theme_styled(title, 'menu_header'))

    # Print description if provided
    if description:
        print(theme_styled(description, 'menu_item'))

    print()

    # Print options
    for i, option in enumerate(options):
        # Determine if this option is selected
        is_selected = i == current_selection

        # Create number prefix if needed
        number_prefix = f"{i+1}. " if show_numbers else ""

        # Create cursor if needed
        cursor = "→ " if is_selected and show_cursor else "  "

        # Format the option text
        option_text = f"{cursor}{number_prefix}{option}"

        # Style based on selection
        if is_selected:
            print(theme_styled(option_text, 'menu_selected'))
        else:
            print(theme_styled(option_text, 'menu_item'))

    print()


def print_error(message: str, details: Optional[str] = None) -> None:
    """
    Print an error message.

    Args:
        message (str): The error message
        details (str, optional): Additional error details
    """
    error_prefix = theme_styled("ERROR:", 'error')
    error_message = theme_styled(message, 'error')

    print(f"{error_prefix} {error_message}")

    if details:
        print(theme_styled(f"  Details: {details}", 'normal'))


def print_warning(message: str, details: Optional[str] = None) -> None:
    """
    Print a warning message.

    Args:
        message (str): The warning message
        details (str, optional): Additional warning details
    """
    warning_prefix = theme_styled("WARNING:", 'warning')
    warning_message = theme_styled(message, 'warning')

    print(f"{warning_prefix} {warning_message}")

    if details:
        print(theme_styled(f"  Details: {details}", 'normal'))


def print_success(message: str, details: Optional[str] = None) -> None:
    """
    Print a success message.

    Args:
        message (str): The success message
        details (str, optional): Additional success details
    """
    success_prefix = theme_styled("SUCCESS:", 'success')
    success_message = theme_styled(message, 'success')

    print(f"{success_prefix} {success_message}")

    if details:
        print(theme_styled(f"  Details: {details}", 'normal'))


def print_spinning_indicator(state: int, prefix: str = "", suffix: str = "") -> None:
    """
    Print a spinning indicator showing an ongoing process.

    Args:
        state (int): Current state of the spinner (0-3)
        prefix (str): Text to display before the spinner
        suffix (str): Text to display after the spinner
    """
    # Spinner characters
    spinner_chars = ['|', '/', '-', '\\']
    char = spinner_chars[state % len(spinner_chars)]

    # Create the spinner text
    spinner_text = f"\r{prefix} {char} {suffix}"

    # Print the spinner (overwrite the current line)
    print(spinner_text, end='', flush=True)


def create_spinner(prefix: str = "Loading", suffix: str = "",
                   delay: float = 0.1) -> Callable:
    """
    Create and return a function that displays a spinning indicator.

    Args:
        prefix (str): Text to display before the spinner
        suffix (str): Text to display after the spinner
        delay (float): Delay between spinner updates in seconds

    Returns:
        Callable: Function to call to show the spinner
    """
    state = [0]  # Use a list to allow modification in the closure

    def spin() -> None:
        """Display the spinner and update its state."""
        print_spinning_indicator(state[0], prefix, suffix)
        state[0] = (state[0] + 1) % 4
        time.sleep(delay)

    return spin


def wait_with_spinner(seconds: float, prefix: str = "Loading",
                      suffix: str = "", step: float = 0.1) -> None:
    """
    Wait for a specified time while displaying a spinner.

    Args:
        seconds (float): Time to wait in seconds
        prefix (str): Text to display before the spinner
        suffix (str): Text to display after the spinner
        step (float): How often to update the spinner in seconds
    """
    spinner = create_spinner(prefix, suffix, step)

    steps = int(seconds / step)
    for _ in range(steps):
        spinner()

    # Clear the spinner line
    print("\r" + " " * (len(prefix) + len(suffix) + 10), end="\r", flush=True)


def confirm_prompt(prompt: str, default: bool = True) -> bool:
    """
    Display a yes/no confirmation prompt and return the user's response.

    Args:
        prompt (str): The prompt to display
        default (bool): Default response if user just presses Enter

    Returns:
        bool: True for yes, False for no
    """
    yes_text = "YES" if default else "yes"
    no_text = "no" if default else "NO"

    while True:
        response = input(f"{prompt} [{yes_text}/{no_text}]: ").strip().lower()

        if not response:
            return default

        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False

        print_error("Please answer 'yes' or 'no'.")


def input_with_placeholder(prompt: str, placeholder: str = "") -> str:
    """
    Display an input prompt with a placeholder text.

    Works only on terminals that support ANSI escape sequences.

    Args:
        prompt (str): The prompt to display
        placeholder (str): Placeholder text to display

    Returns:
        str: User input
    """
    # Print prompt and placeholder
    placeholder_text = theme_styled(placeholder, 'normal')
    print(f"{prompt} {placeholder_text}", end="", flush=True)

    # Move cursor back to erase the placeholder
    print("\b" * len(placeholder), end="", flush=True)

    # Get user input
    user_input = input()

    # Return input or placeholder if empty
    return user_input if user_input else placeholder


def display_loading_animation(iterations: int, prefix: str = "Loading",
                              suffix: str = "", delay: float = 0.1) -> None:
    """
    Display a loading animation for a specified number of iterations.

    Args:
        iterations (int): Number of iterations to display the animation
        prefix (str): Text to display before the animation
        suffix (str): Text to display after the animation
        delay (float): Delay between animation frames in seconds
    """
    animation = "|/-\\"
    for i in range(iterations):
        print(
            f"\r{prefix} {animation[i % len(animation)]} {suffix}", end='', flush=True)
        time.sleep(delay)

    # Clear the animation line
    print("\r" + " " * (len(prefix) + len(suffix) + 10), end="\r", flush=True)


def display_data_page(data: List[Any], page: int, page_size: int,
                      formatter: Callable[[Any], str],
                      title: str = "Data", show_page_info: bool = True) -> int:
    """
    Display a page of data with navigation info.

    Args:
        data (List[Any]): The data to display
        page (int): Current page number (0-indexed)
        page_size (int): Number of items per page
        formatter (Callable[[Any], str]): Function to format each data item
        title (str): Title for the data display
        show_page_info (bool): Whether to show page navigation info

    Returns:
        int: Total number of pages
    """
    # Calculate total pages
    total_items = len(data)
    total_pages = (total_items + page_size -
                   1) // page_size if total_items > 0 else 1

    # Ensure page is within bounds
    page = max(0, min(page, total_pages - 1))

    # Calculate start and end indices for this page
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, total_items)

    # Display title and page info
    if show_page_info:
        page_info = f"Page {page + 1}/{total_pages} ({start_idx + 1}-{end_idx} of {total_items})"
        print_header(f"{title} - {page_info}", centered=True)
    else:
        print_header(title, centered=True)

    # Display items for this page
    if start_idx < total_items:
        for i in range(start_idx, end_idx):
            print(formatter(data[i]))
    else:
        print_text_box("No data to display", style='single')

    # Display navigation instructions if more than one page
    if total_pages > 1 and show_page_info:
        nav_text = "Navigation: [←/→] Previous/Next Page, [Enter] Select"
        print(theme_styled(nav_text, 'menu_footer'))

    print()
    return total_pages


def create_loading_bar(text: str = "Processing", delay: float = 0.05,
                       width: int = 20, char: str = "█") -> Callable:
    """
    Create a decorative loading bar function that can be called repeatedly.

    Args:
        text (str): Text to display before the loading bar
        delay (float): Delay between updates in seconds
        width (int): Width of the loading bar in characters
        char (str): Character to use for the loading bar

    Returns:
        Callable: Function that displays an animated loading bar
    """
    position = [0]  # Use a list to allow modification in the closure

    def update_bar() -> None:
        """Update and display the loading bar."""
        pos = position[0] % (width * 2)

        if pos < width:
            # Moving right
            bar = char * pos + " " * (width - pos)
        else:
            # Moving left
            pos = width * 2 - pos - 1
            bar = " " * (width - pos - 1) + char * (pos + 1)

        print(f"\r{text} [{bar}]", end='', flush=True)
        position[0] = (position[0] + 1) % (width * 2)
        time.sleep(delay)

    return update_bar


# If this module is run directly, demonstrate some of the display functions
if __name__ == "__main__":
    print("Display Module Demonstration")
    print("==========================")

    # Banner display
    print_banner("Telegram Account Manager")

    # Header display
    print_header("Display Functions")

    # Text box
    print_text_box(
        "This is a sample text box with a medium length text that should wrap if it's too long for the box width.", title="Sample Text Box")

    # Table display
    headers = ["ID", "Phone Number", "Status", "Last Used"]
    rows = [
        ["1", "+1234567890", "Active", "2023-10-15 14:30"],
        ["2", "+9876543210", "Cooldown", "2023-10-15 16:45"],
        ["3", "+5551234567", "Blocked", "2023-10-14 09:12"]
    ]
    print_table(headers, rows, title="Accounts Status",
                alignments=["center", "left", "center", "right"])

    # Menu display
    options = [
        "Manage Accounts",
        "Start Member Transfer",
        "Settings",
        "View Statistics",
        "Exit"
    ]
    print_menu("Main Menu", options, current_selection=1,
               description="Please select an option:")

    # Status messages
    print_success("Operation completed successfully",
                  "Added 15 members to the group")
    print_warning("Rate limit approaching",
                  "Slow down operations to avoid hitting limits")
    print_error("Connection failed", "Could not connect to Telegram servers")

    # Progress demonstration
    print("\nProgress bar demo:")
    for i in range(21):
        print_progress(i, 20, "Transferring members:",
                       f"{i}/20 members processed")
        time.sleep(0.1)
    print()  # Add a newline after the progress bar

    # Spinner demonstration
    print("\nSpinner demo:")
    wait_with_spinner(3, "Processing", "please wait...")
    print("Done!")
