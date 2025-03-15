"""
Colors Module

This module provides utilities for managing console colors and styles in the Telegram
Account Manager application. It offers a simple interface for applying colors to text,
creating styled messages, and managing color themes.

Features:
- ANSI color support for terminal output
- Color themes for different UI elements
- Helper functions for creating colored and styled text
- Cross-platform compatibility with colorama
- Support for terminal capability detection

Usage:
    from ui.colors import Colors, Styles, colorize, styled_text

    # Simple color application
    colored_text = Colors.GREEN + "Success!" + Colors.RESET

    # Using helper functions
    error_message = colorize("Error occurred!", Colors.RED)

    # Using styles
    highlighted_text = styled_text("Important", fg=Colors.YELLOW, style=Styles.BOLD)

    # Print with colors directly
    print_colored("Status:", "Running", color=Colors.GREEN)
"""

import os
import sys
import platform
from typing import Optional, Dict, List, Tuple, Union

# Try to import colorama for cross-platform color support
try:
    from colorama import init as colorama_init, Fore, Back, Style
    COLORAMA_AVAILABLE = True
    colorama_init(autoreset=False)  # Don't auto-reset, we'll handle it manually
except ImportError:
    COLORAMA_AVAILABLE = False

# Check if we're in a terminal that supports colors
def _supports_color() -> bool:
    """
    Check if the current terminal supports colors.

    Returns:
        bool: True if the terminal supports colors, False otherwise
    """
    # If colorama is available, we can use colors on Windows
    if COLORAMA_AVAILABLE:
        return True

    # Check if we're on a platform that supports colors
    plat = platform.system().lower()
    supported_platform = plat != 'windows' or 'ANSICON' in os.environ

    # isatty is not always implemented, so we need to handle the exception
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    # Check if NO_COLOR environment variable is set (respecting the no-color.org standard)
    no_color = 'NO_COLOR' in os.environ

    # ANSI colors are supported if we're on a supported platform, outputting to a TTY,
    # and the NO_COLOR environment variable is not set
    return supported_platform and is_a_tty and not no_color

# Flag for color support
COLOR_SUPPORTED = _supports_color()


class Colors:
    """
    ANSI color codes for terminal output.

    This class provides constants for ANSI color codes, making it easy to apply
    colors to text output. If color is not supported, empty strings are used.
    """
    # Only define colors if they're supported
    if COLOR_SUPPORTED:
        # Foreground colors
        BLACK = '\033[30m' if not COLORAMA_AVAILABLE else Fore.BLACK
        RED = '\033[31m' if not COLORAMA_AVAILABLE else Fore.RED
        GREEN = '\033[32m' if not COLORAMA_AVAILABLE else Fore.GREEN
        YELLOW = '\033[33m' if not COLORAMA_AVAILABLE else Fore.YELLOW
        BLUE = '\033[34m' if not COLORAMA_AVAILABLE else Fore.BLUE
        MAGENTA = '\033[35m' if not COLORAMA_AVAILABLE else Fore.MAGENTA
        CYAN = '\033[36m' if not COLORAMA_AVAILABLE else Fore.CYAN
        WHITE = '\033[37m' if not COLORAMA_AVAILABLE else Fore.WHITE

        # Background colors
        BG_BLACK = '\033[40m' if not COLORAMA_AVAILABLE else Back.BLACK
        BG_RED = '\033[41m' if not COLORAMA_AVAILABLE else Back.RED
        BG_GREEN = '\033[42m' if not COLORAMA_AVAILABLE else Back.GREEN
        BG_YELLOW = '\033[43m' if not COLORAMA_AVAILABLE else Back.YELLOW
        BG_BLUE = '\033[44m' if not COLORAMA_AVAILABLE else Back.BLUE
        BG_MAGENTA = '\033[45m' if not COLORAMA_AVAILABLE else Back.MAGENTA
        BG_CYAN = '\033[46m' if not COLORAMA_AVAILABLE else Back.CYAN
        BG_WHITE = '\033[47m' if not COLORAMA_AVAILABLE else Back.WHITE

        # Reset code
        RESET = '\033[0m' if not COLORAMA_AVAILABLE else Style.RESET_ALL
    else:
        # Define empty strings if colors are not supported
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ''
        BG_BLACK = BG_RED = BG_GREEN = BG_YELLOW = BG_BLUE = BG_MAGENTA = BG_CYAN = BG_WHITE = ''
        RESET = ''


class Styles:
    """
    ANSI style codes for terminal output.

    This class provides constants for ANSI style codes, making it easy to apply
    styles to text output. If styling is not supported, empty strings are used.
    """
    # Only define styles if they're supported
    if COLOR_SUPPORTED:
        BOLD = '\033[1m' if not COLORAMA_AVAILABLE else Style.BRIGHT
        DIM = '\033[2m' if not COLORAMA_AVAILABLE else Style.DIM
        ITALIC = '\033[3m'  # Not supported by colorama
        UNDERLINE = '\033[4m'  # Not supported by colorama directly
        BLINK = '\033[5m'  # Not supported by colorama directly
        REVERSE = '\033[7m'  # Not supported by colorama directly
        NORMAL = '\033[22m' if not COLORAMA_AVAILABLE else Style.NORMAL
    else:
        # Define empty strings if styles are not supported
        BOLD = DIM = ITALIC = UNDERLINE = BLINK = REVERSE = NORMAL = ''


class ColorTheme:
    """
    Color theme for the application.

    This class defines color schemes for different UI elements, making it easy
    to maintain a consistent look and feel across the application.
    """
    # Default color theme
    DEFAULT = {
        'header': Colors.CYAN,
        'title': Colors.MAGENTA + Styles.BOLD,
        'success': Colors.GREEN,
        'error': Colors.RED,
        'warning': Colors.YELLOW,
        'info': Colors.BLUE,
        'prompt': Colors.CYAN + Styles.BOLD,
        'input': Colors.WHITE,
        'menu_item': Colors.WHITE,
        'menu_selected': Colors.BLACK + Colors.BG_CYAN,
        'menu_header': Colors.YELLOW + Styles.BOLD,
        'menu_footer': Colors.CYAN,
        'status_active': Colors.GREEN,
        'status_inactive': Colors.RED,
        'progress_bar': Colors.CYAN,
        'progress_text': Colors.WHITE,
        'highlight': Colors.YELLOW,
        'normal': Colors.RESET
    }

    # Dark mode theme
    DARK = {
        'header': Colors.BLUE,
        'title': Colors.CYAN + Styles.BOLD,
        'success': Colors.GREEN,
        'error': Colors.RED,
        'warning': Colors.YELLOW,
        'info': Colors.BLUE,
        'prompt': Colors.GREEN + Styles.BOLD,
        'input': Colors.WHITE,
        'menu_item': Colors.WHITE,
        'menu_selected': Colors.BLACK + Colors.BG_GREEN,
        'menu_header': Colors.CYAN + Styles.BOLD,
        'menu_footer': Colors.BLUE,
        'status_active': Colors.GREEN,
        'status_inactive': Colors.RED,
        'progress_bar': Colors.GREEN,
        'progress_text': Colors.WHITE,
        'highlight': Colors.YELLOW,
        'normal': Colors.RESET
    }

    # Current theme (defaults to DEFAULT)
    CURRENT = DEFAULT.copy()

    @classmethod
    def get(cls, element: str) -> str:
        """
        Get the color for a UI element from the current theme.

        Args:
            element (str): The name of the UI element

        Returns:
            str: The color code for the element, or empty string if not found
        """
        return cls.CURRENT.get(element, Colors.RESET)

    @classmethod
    def set_theme(cls, theme: Dict[str, str]) -> None:
        """
        Set the current theme.

        Args:
            theme (Dict[str, str]): The theme dictionary
        """
        cls.CURRENT = theme.copy()

    @classmethod
    def use_dark_mode(cls) -> None:
        """Set the current theme to dark mode."""
        cls.set_theme(cls.DARK)

    @classmethod
    def use_default_mode(cls) -> None:
        """Set the current theme to the default theme."""
        cls.set_theme(cls.DEFAULT)

    @classmethod
    def is_dark_mode(cls) -> bool:
        """
        Check if dark mode is currently active.

        Returns:
            bool: True if dark mode is active, False otherwise
        """
        return cls.CURRENT == cls.DARK


def colorize(text: str, color: str, reset: bool = True) -> str:
    """
    Apply a color to text.

    Args:
        text (str): The text to colorize
        color (str): The color code to apply
        reset (bool): Whether to reset the color after the text

    Returns:
        str: The colorized text
    """
    if not COLOR_SUPPORTED:
        return text

    if reset:
        return f"{color}{text}{Colors.RESET}"
    else:
        return f"{color}{text}"


def styled_text(text: str, fg: Optional[str] = None, bg: Optional[str] = None,
               style: Optional[str] = None) -> str:
    """
    Apply a combination of foreground color, background color, and style to text.

    Args:
        text (str): The text to style
        fg (str, optional): The foreground color
        bg (str, optional): The background color
        style (str, optional): The style

    Returns:
        str: The styled text
    """
    if not COLOR_SUPPORTED:
        return text

    result = ""
    if style:
        result += style
    if fg:
        result += fg
    if bg:
        result += bg

    result += text

    if style or fg or bg:
        result += Colors.RESET

    return result


def theme_styled(text: str, element: str) -> str:
    """
    Apply theme colors to text based on a UI element.

    Args:
        text (str): The text to style
        element (str): The name of the UI element

    Returns:
        str: The themed text
    """
    color = ColorTheme.get(element)
    return colorize(text, color)


def print_colored(label: str, value: str, color: Optional[str] = None,
                 label_color: Optional[str] = None) -> None:
    """
    Print a label and value with colors.

    Args:
        label (str): The label to print
        value (str): The value to print
        color (str, optional): The color for the value (defaults to normal text)
        label_color (str, optional): The color for the label (defaults to theme 'info')
    """
    label_color = label_color or ColorTheme.get('info')
    color = color or Colors.RESET

    colored_label = colorize(f"{label}: ", label_color)
    colored_value = colorize(value, color)

    print(f"{colored_label}{colored_value}")


def print_status(message: str, status: bool) -> None:
    """
    Print a status message with color indicating success or failure.

    Args:
        message (str): The message to print
        status (bool): True for success (green), False for failure (red)
    """
    status_color = ColorTheme.get('success') if status else ColorTheme.get('error')
    status_text = "✓ Success" if status else "✗ Failed"

    print(f"{colorize(message, Colors.RESET)} {colorize(status_text, status_color)}")


def get_color_support_info() -> Dict[str, bool]:
    """
    Get information about color support.

    Returns:
        Dict[str, bool]: Dictionary with color support information
    """
    return {
        'color_supported': COLOR_SUPPORTED,
        'colorama_available': COLORAMA_AVAILABLE,
        'is_a_tty': hasattr(sys.stdout, 'isatty') and sys.stdout.isatty(),
        'no_color_env': 'NO_COLOR' in os.environ,
        'platform': platform.system().lower()
    }


def disable_colors() -> None:
    """
    Disable color output globally.

    This function sets the COLOR_SUPPORTED flag to False, which will make
    all color functions return uncolored text.
    """
    global COLOR_SUPPORTED
    COLOR_SUPPORTED = False


def enable_colors() -> None:
    """
    Try to enable color output globally.

    This function checks if color is actually supported, and if so, sets
    the COLOR_SUPPORTED flag to True.
    """
    global COLOR_SUPPORTED
    COLOR_SUPPORTED = _supports_color()


def create_progress_bar(current: int, total: int, width: int = 40,
                       filled_char: str = '█', empty_char: str = '░') -> str:
    """
    Create a colored progress bar.

    Args:
        current (int): Current progress value
        total (int): Total progress value
        width (int): Width of the progress bar in characters
        filled_char (str): Character for filled portion
        empty_char (str): Character for empty portion

    Returns:
        str: Formatted progress bar
    """
    if total <= 0:
        total = 1  # Avoid division by zero

    progress = min(current / total, 1.0)
    filled_length = int(width * progress)

    bar = filled_char * filled_length + empty_char * (width - filled_length)
    percentage = progress * 100

    bar_colored = colorize(bar, ColorTheme.get('progress_bar'))
    percentage_text = colorize(f" {percentage:6.2f}%", ColorTheme.get('progress_text'))

    return f"[{bar_colored}]{percentage_text}"


def print_progress(current: int, total: int, prefix: str = "Progress:",
                  suffix: str = "", width: int = 40) -> None:
    """
    Print a progress bar with prefix and suffix.

    Args:
        current (int): Current progress value
        total (int): Total progress value
        prefix (str): Text to display before the progress bar
        suffix (str): Text to display after the progress bar
        width (int): Width of the progress bar in characters
    """
    bar = create_progress_bar(current, total, width)
    prefix_colored = colorize(prefix, ColorTheme.get('info'))
    suffix_colored = colorize(suffix, ColorTheme.get('normal')) if suffix else ""

    # Use \r to return to the beginning of the line and overwrite
    print(f"\r{prefix_colored} {bar} {suffix_colored}", end='', flush=True)


# If this module is run directly, perform a color test
if __name__ == "__main__":
    print("Color Support Test")
    print("-----------------")
    print(f"Color supported: {COLOR_SUPPORTED}")
    print(f"Colorama available: {COLORAMA_AVAILABLE}")

    print("\nColor Samples:")
    for name, value in vars(Colors).items():
        if not name.startswith('_') and isinstance(value, str):
            print(f"{name:10}: {colorize('This text is colored', value)}")

    print("\nStyle Samples:")
    for name, value in vars(Styles).items():
        if not name.startswith('_') and isinstance(value, str):
            print(f"{name:10}: {colorize('This text is styled', value)}")

    print("\nTheme Samples:")
    for name in ColorTheme.DEFAULT.keys():
        print(f"{name:15}: {theme_styled('This text uses theme styling', name)}")

    print("\nProgress Bar Test:")
    for i in range(11):
        print_progress(i, 10, "Progress:", f"Step {i}/10")
        # Add a small delay for effect (only for demonstration)
        import time
        time.sleep(0.2)
    print()  # Add a newline after the progress bar