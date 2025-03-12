"""
Account models module for Telegram Adder application.
Contains models related to Telegram accounts and their status.
"""

# Account status enum
class AccountStatus:
    """Enumeration of possible account statuses."""
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    BLOCKED = "blocked"
    UNVERIFIED = "unverified"
    DAILY_LIMIT_REACHED = "daily_limit_reached"