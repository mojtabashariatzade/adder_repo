"""
Menu System Module

This module provides a flexible menu system for the Telegram Account Manager application.
It allows for creating hierarchical menus, handling user input, and executing actions based on menu selections.

Features:
- Create multi-level menus with parent-child relationships
- Support for different menu item types (actions, sub-menus, toggles)
- Input validation and error handling for user interactions
- Context-aware menu rendering
- Support for breadcrumbs to show navigation path
- Dynamic menu generation based on application state
- Customizable rendering styles (plain text, colored text)

Usage:
    from ui.menu_system import Menu, MenuItem, MenuSystem

    # Create a main menu
    main_menu = Menu("Main Menu")

    # Add menu items
    main_menu.add_item(MenuItem("1", "Account Management", lambda: account_menu.display()))
    main_menu.add_item(MenuItem("2", "Start Transfer", lambda: start_transfer()))
    main_menu.add_item(MenuItem("q", "Quit", lambda: sys.exit(0)))

    # Create the menu system
    menu_system = MenuSystem(main_menu)

    # Run the menu system
    menu_system.run()
"""

import os
import sys
import time
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Union, Tuple

# Try to import colorama for colored output
try:
    from colorama import Fore, Back, Style, init as colorama_init
    colorama_init()
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

# Try to import the display module for rendering
try:
    from ui.display import clear_screen, print_colored, print_heading, print_error
except ImportError:
    # Fallback implementations if display module is not available
    def clear_screen():
        """Clear the console screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_colored(text, color=None, style=None, end='\n'):
        """Print text with color."""
        if COLORAMA_AVAILABLE and color:
            print(f"{color}{style or ''}{text}{Style.RESET_ALL}", end=end)
        else:
            print(text, end=end)

    def print_heading(text, width=60):
        """Print a formatted heading."""
        print("\n" + "=" * width)
        print(text.center(width))
        print("=" * width)

    def print_error(text):
        """Print an error message."""
        if COLORAMA_AVAILABLE:
            print(f"{Fore.RED}Error: {text}{Style.RESET_ALL}")
        else:
            print(f"Error: {text}")

# Try to import the logging manager
try:
    from logging_.logging_manager import get_logger
    logger = get_logger("MenuSystem")
except ImportError:
    # Fallback logger if logging module is not available
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("MenuSystem")


class MenuItemType(Enum):
    """Enumeration of possible menu item types."""
    ACTION = auto()    # Executes a function
    SUBMENU = auto()   # Opens another menu
    TOGGLE = auto()    # Toggles a boolean value
    BACK = auto()      # Returns to previous menu
    EXIT = auto()      # Exits the application
    SEPARATOR = auto() # Visual separator, not selectable


class MenuItem:
    """
    Represents a single item in a menu.

    Menu items can be actions that execute a function, sub-menus that open another menu,
    toggles that change a boolean value, back items that return to the previous menu,
    exit items that exit the application, or separators for visual organization.
    """

    def __init__(self, key: str, title: str,
                 action: Optional[Callable] = None,
                 item_type: MenuItemType = MenuItemType.ACTION,
                 submenu: Optional['Menu'] = None,
                 enabled: bool = True,
                 visible: bool = True,
                 toggle_value: Optional[bool] = None,
                 toggle_callback: Optional[Callable[[bool], None]] = None,
                 description: Optional[str] = None,
                 confirm: bool = False,
                 confirm_message: Optional[str] = None):
        """
        Initialize a menu item.

        Args:
            key (str): Key to select this item (e.g., "1", "q").
            title (str): Title of the menu item to display.
            action (Optional[Callable]): Function to execute when item is selected.
            item_type (MenuItemType): Type of menu item.
            submenu (Optional[Menu]): Sub-menu to open (for SUBMENU type).
            enabled (bool): Whether the item is currently enabled.
            visible (bool): Whether the item is currently visible.
            toggle_value (Optional[bool]): Current value for TOGGLE type items.
            toggle_callback (Optional[Callable[[bool], None]]): Function to call when toggle changes.
            description (Optional[str]): Additional description to display.
            confirm (bool): Whether to ask for confirmation before executing.
            confirm_message (Optional[str]): Custom confirmation message.
        """
        self.key = key
        self.title = title
        self.action = action
        self.item_type = item_type
        self.submenu = submenu
        self.enabled = enabled
        self.visible = visible
        self.toggle_value = toggle_value
        self.toggle_callback = toggle_callback
        self.description = description
        self.confirm = confirm
        self.confirm_message = confirm_message or f"Are you sure you want to {title.lower()}? (y/n): "

        # Validate the item configuration based on its type
        self._validate()

    def _validate(self):
        """Validate the menu item configuration based on its type."""
        if self.item_type == MenuItemType.ACTION and not callable(self.action):
            raise ValueError(f"ACTION menu item '{self.title}' must have a callable action")

        if self.item_type == MenuItemType.SUBMENU and self.submenu is None:
            raise ValueError(f"SUBMENU menu item '{self.title}' must have a submenu")

        if self.item_type == MenuItemType.TOGGLE:
            if self.toggle_value is None:
                raise ValueError(f"TOGGLE menu item '{self.title}' must have a toggle_value")
            if not callable(self.toggle_callback):
                raise ValueError(f"TOGGLE menu item '{self.title}' must have a callable toggle_callback")

    def execute(self) -> Any:
        """
        Execute the menu item based on its type.

        Returns:
            Any: Result of the action or submenu.
        """
        # If the item is disabled, do nothing
        if not self.enabled:
            print_error(f"The option '{self.title}' is currently disabled.")
            time.sleep(1)  # Small delay to show the message
            return None

        # For items requiring confirmation
        if self.confirm:
            confirmation = input(self.confirm_message).strip().lower()
            if confirmation != 'y':
                print("Operation cancelled.")
                time.sleep(1)  # Small delay to show the message
                return None

        # Execute based on item type
        if self.item_type == MenuItemType.ACTION:
            try:
                return self.action()
            except Exception as e:
                logger.error(f"Error executing menu action '{self.title}': {e}")
                print_error(f"Error executing '{self.title}': {e}")
                time.sleep(2)  # Longer delay for errors
                return None

        elif self.item_type == MenuItemType.TOGGLE:
            # Toggle the value
            self.toggle_value = not self.toggle_value
            # Call the callback function
            try:
                self.toggle_callback(self.toggle_value)
                return self.toggle_value
            except Exception as e:
                logger.error(f"Error executing toggle callback '{self.title}': {e}")
                print_error(f"Error toggling '{self.title}': {e}")
                # Revert the toggle
                self.toggle_value = not self.toggle_value
                time.sleep(2)
                return None

        elif self.item_type == MenuItemType.SUBMENU:
            return self.submenu

        elif self.item_type == MenuItemType.BACK:
            return "BACK"

        elif self.item_type == MenuItemType.EXIT:
            return "EXIT"

        # SEPARATOR items don't do anything
        return None

    def render(self, width: int = 80) -> str:
        """
        Render the menu item as text.

        Args:
            width (int): Width of the rendering area.

        Returns:
            str: Rendered menu item text.
        """
        # Don't render invisible items
        if not self.visible:
            return ""

        # Handle separator items
        if self.item_type == MenuItemType.SEPARATOR:
            return "-" * width

        # Create the base item text with key and title
        item_text = f"{self.key}) {self.title}"

        # Add toggle state indicator for toggle items
        if self.item_type == MenuItemType.TOGGLE:
            toggle_indicator = "[ON]" if self.toggle_value else "[OFF]"
            item_text = f"{item_text} {toggle_indicator}"

        # Add description if available
        if self.description:
            # Calculate available space for description
            key_title_length = len(f"{self.key}) {self.title}")
            desc_space = width - key_title_length - 5  # Leave some margin

            if desc_space > 10:  # Only add description if there's enough space
                # Truncate description if needed
                truncated_desc = (self.description[:desc_space-3] + '...') if len(self.description) > desc_space else self.description
                item_text = f"{item_text} - {truncated_desc}"

        # Format based on enabled state
        if not self.enabled:
            if COLORAMA_AVAILABLE:
                item_text = f"{Fore.LIGHTBLACK_EX}{item_text} (Disabled){Style.RESET_ALL}"
            else:
                item_text = f"{item_text} (Disabled)"

        return item_text


class Menu:
    """
    Represents a menu containing multiple menu items.

    A menu can contain various types of menu items, including actions, sub-menus, toggles,
    and navigation items. Menus can be nested to create a hierarchical menu structure.
    """

    def __init__(self, title: str, parent: Optional['Menu'] = None,
                 items: Optional[List[MenuItem]] = None,
                 footer_text: Optional[str] = None,
                 show_back_item: bool = True,
                 back_item_key: str = "b",
                 back_item_title: str = "Back",
                 width: int = 80):
        """
        Initialize a menu.

        Args:
            title (str): Title of the menu.
            parent (Optional[Menu]): Parent menu, if this is a submenu.
            items (Optional[List[MenuItem]]): Initial list of menu items.
            footer_text (Optional[str]): Text to display at the bottom of the menu.
            show_back_item (bool): Whether to automatically add a back item.
            back_item_key (str): Key for the automatically added back item.
            back_item_title (str): Title for the automatically added back item.
            width (int): Width of the menu display.
        """
        self.title = title
        self.parent = parent
        self.items: List[MenuItem] = items or []
        self.footer_text = footer_text
        self.show_back_item = show_back_item
        self.back_item_key = back_item_key
        self.back_item_title = back_item_title
        self.width = width

        # Add back item if needed and this is a submenu
        if parent is not None and show_back_item:
            self.add_item(MenuItem(
                back_item_key,
                back_item_title,
                item_type=MenuItemType.BACK
            ))

    def add_item(self, item: MenuItem) -> None:
        """
        Add an item to the menu.

        Args:
            item (MenuItem): Menu item to add.
        """
        # Check for duplicate keys
        for existing_item in self.items:
            if existing_item.key == item.key:
                logger.warning(f"Duplicate menu item key '{item.key}' in menu '{self.title}'")
                # Don't raise an exception, just log a warning

        self.items.append(item)

    def add_separator(self) -> None:
        """Add a separator line to the menu."""
        self.items.append(MenuItem("", "", item_type=MenuItemType.SEPARATOR))

    def add_items(self, items: List[MenuItem]) -> None:
        """
        Add multiple items to the menu.

        Args:
            items (List[MenuItem]): List of menu items to add.
        """
        for item in items:
            self.add_item(item)

    def remove_item(self, key: str) -> bool:
        """
        Remove an item from the menu by its key.

        Args:
            key (str): Key of the item to remove.

        Returns:
            bool: True if item was removed, False if not found.
        """
        for i, item in enumerate(self.items):
            if item.key == key:
                del self.items[i]
                return True
        return False

    def get_item(self, key: str) -> Optional[MenuItem]:
        """
        Get an item by its key.

        Args:
            key (str): Key of the item to get.

        Returns:
            Optional[MenuItem]: The menu item, or None if not found.
        """
        for item in self.items:
            if item.key == key:
                return item
        return None

    def set_visible(self, key: str, visible: bool) -> bool:
        """
        Set the visibility of a menu item.

        Args:
            key (str): Key of the item to modify.
            visible (bool): Whether the item should be visible.

        Returns:
            bool: True if item was modified, False if not found.
        """
        item = self.get_item(key)
        if item:
            item.visible = visible
            return True
        return False

    def set_enabled(self, key: str, enabled: bool) -> bool:
        """
        Set whether a menu item is enabled.

        Args:
            key (str): Key of the item to modify.
            enabled (bool): Whether the item should be enabled.

        Returns:
            bool: True if item was modified, False if not found.
        """
        item = self.get_item(key)
        if item:
            item.enabled = enabled
            return True
        return False

    def clear_items(self) -> None:
        """Clear all items from the menu."""
        self.items.clear()

        # Re-add back item if needed
        if self.parent is not None and self.show_back_item:
            self.add_item(MenuItem(
                self.back_item_key,
                self.back_item_title,
                item_type=MenuItemType.BACK
            ))

    def render(self) -> str:
        """
        Render the entire menu as text.

        Returns:
            str: Rendered menu text.
        """
        result = []

        # Add title
        result.append("=" * self.width)
        result.append(self.title.center(self.width))
        result.append("=" * self.width)
        result.append("")

        # Add items
        for item in self.items:
            if item.visible:
                result.append(item.render(self.width))

        # Add footer if available
        if self.footer_text:
            result.append("")
            result.append("-" * self.width)
            result.append(self.footer_text)

        return "\n".join(result)

    def display(self) -> None:
        """Display the menu to the console."""
        clear_screen()
        print(self.render())

    def get_breadcrumb_path(self) -> List[str]:
        """
        Get the breadcrumb path to this menu.

        Returns:
            List[str]: List of menu titles from root to this menu.
        """
        path = [self.title]
        current = self.parent

        while current:
            path.insert(0, current.title)
            current = current.parent

        return path

    def display_with_breadcrumbs(self) -> None:
        """Display the menu with breadcrumb navigation path."""
        clear_screen()

        # Show breadcrumb path
        path = self.get_breadcrumb_path()
        breadcrumb = " > ".join(path)

        if COLORAMA_AVAILABLE:
            print_colored(breadcrumb, Fore.CYAN)
        else:
            print(breadcrumb)

        print("\n" + self.render())


class MenuSystem:
    """
    Manages menu navigation and user interaction.

    The MenuSystem class provides the main loop for displaying menus, processing
    user input, and executing menu actions. It supports navigation between parent
    and child menus and maintains the menu stack for tracking the current position.
    """

    def __init__(self, main_menu: Menu):
        """
        Initialize the menu system.

        Args:
            main_menu (Menu): The main (root) menu to start with.
        """
        self.main_menu = main_menu
        self.current_menu = main_menu
        self.menu_stack: List[Menu] = []
        self.running = False
        self.show_breadcrumbs = True

    def navigate_to(self, menu: Menu) -> None:
        """
        Navigate to a specific menu.

        Args:
            menu (Menu): The menu to navigate to.
        """
        self.menu_stack.append(self.current_menu)
        self.current_menu = menu

    def navigate_back(self) -> bool:
        """
        Navigate back to the previous menu.

        Returns:
            bool: True if successfully navigated back, False if at main menu.
        """
        if self.menu_stack:
            self.current_menu = self.menu_stack.pop()
            return True
        return False

    def navigate_to_main(self) -> None:
        """Navigate back to the main menu."""
        self.menu_stack.clear()
        self.current_menu = self.main_menu

    def display_current_menu(self) -> None:
        """Display the current menu."""
        if self.show_breadcrumbs:
            self.current_menu.display_with_breadcrumbs()
        else:
            self.current_menu.display()

    def process_input(self, user_input: str) -> bool:
        """
        Process user input.

        Args:
            user_input (str): The user's input.

        Returns:
            bool: True to continue running, False to exit.
        """
        # Clean up input
        user_input = user_input.strip().lower()

        # Get the selected item
        selected_item = self.current_menu.get_item(user_input)

        if selected_item:
            # Execute the item
            result = selected_item.execute()

            # Handle the result
            if result == "BACK":
                # Navigate back to the previous menu
                if not self.navigate_back():
                    # If at main menu, ask if user wants to exit
                    if self.current_menu == self.main_menu:
                        confirm = input("Do you really want to exit? (y/n): ").strip().lower()
                        if confirm == 'y':
                            return False  # Exit the menu system
            elif result == "EXIT":
                # Exit the menu system
                return False
            elif isinstance(result, Menu):
                # Navigate to the submenu
                self.navigate_to(result)
        else:
            # Invalid input
            if COLORAMA_AVAILABLE:
                print_colored(f"Invalid selection: '{user_input}'. Please try again.", Fore.YELLOW)
            else:
                print(f"Invalid selection: '{user_input}'. Please try again.")
            time.sleep(1)

        return True

    def run(self) -> None:
        """Run the menu system main loop."""
        self.running = True

        while self.running:
            # Display the current menu
            self.display_current_menu()

            # Get user input
            user_input = input("\nEnter your choice: ")

            # Process the input
            self.running = self.process_input(user_input)

        # Final cleanup
        clear_screen()
        print("Thank you for using the application. Goodbye!")


# Helper functions to create common menu items

def create_action_item(key: str, title: str, action: Callable,
                       description: Optional[str] = None,
                       enabled: bool = True,
                       confirm: bool = False,
                       confirm_message: Optional[str] = None) -> MenuItem:
    """
    Create an action menu item.

    Args:
        key (str): Selection key.
        title (str): Item title.
        action (Callable): Function to execute.
        description (Optional[str]): Item description.
        enabled (bool): Whether item is enabled.
        confirm (bool): Whether to confirm before executing.
        confirm_message (Optional[str]): Custom confirmation message.

    Returns:
        MenuItem: A new action menu item.
    """
    return MenuItem(
        key=key,
        title=title,
        action=action,
        item_type=MenuItemType.ACTION,
        enabled=enabled,
        description=description,
        confirm=confirm,
        confirm_message=confirm_message
    )

def create_submenu_item(key: str, title: str, submenu: Menu,
                       description: Optional[str] = None,
                       enabled: bool = True) -> MenuItem:
    """
    Create a submenu menu item.

    Args:
        key (str): Selection key.
        title (str): Item title.
        submenu (Menu): Submenu to open.
        description (Optional[str]): Item description.
        enabled (bool): Whether item is enabled.

    Returns:
        MenuItem: A new submenu menu item.
    """
    return MenuItem(
        key=key,
        title=title,
        item_type=MenuItemType.SUBMENU,
        submenu=submenu,
        enabled=enabled,
        description=description
    )

def create_toggle_item(key: str, title: str,
                      initial_value: bool,
                      toggle_callback: Callable[[bool], None],
                      description: Optional[str] = None,
                      enabled: bool = True) -> MenuItem:
    """
    Create a toggle menu item.

    Args:
        key (str): Selection key.
        title (str): Item title.
        initial_value (bool): Initial toggle state.
        toggle_callback (Callable[[bool], None]): Function to call when toggled.
        description (Optional[str]): Item description.
        enabled (bool): Whether item is enabled.

    Returns:
        MenuItem: A new toggle menu item.
    """
    return MenuItem(
        key=key,
        title=title,
        item_type=MenuItemType.TOGGLE,
        toggle_value=initial_value,
        toggle_callback=toggle_callback,
        enabled=enabled,
        description=description
    )

def create_back_item(key: str = "b", title: str = "Back") -> MenuItem:
    """
    Create a back navigation menu item.

    Args:
        key (str): Selection key.
        title (str): Item title.

    Returns:
        MenuItem: A new back menu item.
    """
    return MenuItem(
        key=key,
        title=title,
        item_type=MenuItemType.BACK
    )

def create_exit_item(key: str = "q", title: str = "Exit",
                    confirm: bool = True,
                    confirm_message: Optional[str] = None) -> MenuItem:
    """
    Create an exit menu item.

    Args:
        key (str): Selection key.
        title (str): Item title.
        confirm (bool): Whether to confirm before exiting.
        confirm_message (Optional[str]): Custom confirmation message.

    Returns:
        MenuItem: A new exit menu item.
    """
    return MenuItem(
        key=key,
        title=title,
        item_type=MenuItemType.EXIT,
        confirm=confirm,
        confirm_message=confirm_message or "Are you sure you want to exit? (y/n): "
    )


# Example usage
if __name__ == "__main__":
    # Create main menu
    main_menu = Menu("Telegram Account Manager - Main Menu", width=80)

    # Create some submenus
    account_menu = Menu("Account Management", parent=main_menu)
    operation_menu = Menu("Transfer Operations", parent=main_menu)
    settings_menu = Menu("Settings", parent=main_menu)

    # Add items to account menu
    account_menu.add_item(create_action_item("1", "List Accounts", lambda: print("Listing accounts...")))
    account_menu.add_item(create_action_item("2", "Add Account", lambda: print("Adding account...")))
    account_menu.add_item(create_action_item("3", "Remove Account", lambda: print("Removing account...")))
    account_menu.add_item(create_action_item("4", "Reset Daily Limits", lambda: print("Resetting limits...")))

    # Add items to operation menu
    operation_menu.add_item(create_action_item("1", "Start Member Transfer", lambda: print("Starting transfer...")))
    operation_menu.add_item(create_action_item("2", "Check Transfer Status", lambda: print("Checking status...")))

    # Add items to settings menu
    def toggle_debug(value):
        print(f"Debug mode {'enabled' if value else 'disabled'}")

    settings_menu.add_item(create_toggle_item("1", "Debug Mode", False, toggle_debug))
    settings_menu.add_item(create_action_item("2", "Configure Delays", lambda: print("Configuring delays...")))

    # Add items to main menu
    main_menu.add_item(create_submenu_item("1", "Account Management", account_menu))
    main_menu.add_item(create_submenu_item("2", "Transfer Operations", operation_menu))
    main_menu.add_item(create_submenu_item("3", "Settings", settings_menu))
    main_menu.add_separator()
    main_menu.add_item(create_exit_item("q", "Quit"))

    # Create and run the menu system
    menu_system = MenuSystem(main_menu)
    try:
        menu_system.run()
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
        sys.exit(0)