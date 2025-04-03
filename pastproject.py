import asyncio
from queue import Queue
from telethon import TelegramClient, functions, types, errors
from telethon.sessions import StringSession
import os
import uuid
import glob
import platform
import json
import base64
import getpass
import time
import sys
import re
import random
import traceback
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging
from colorama import Fore, Style, init

# Initialize colorama for console color support
init()

# Log settings
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler("telegram_adder.log")
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logger = logging.getLogger("TelegramAdder")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Constants
CONFIG_FILE = ".env.encrypted"
SALT_FILE = ".env.salt"
REQUEST_LOG_FILE = "request_log.json"
AI_DATA_FILE = "ai_training_data.json"
ACCOUNTS_FILE = "telegram_accounts.json"
ENCRYPTION_KEY_FILE = "encryption.key"
DEFAULT_DELAY = 20  # Default delay between requests in seconds
MAX_DELAY = 300  # Maximum delay between requests in seconds
MAX_RETRY_COUNT = 5  # Maximum number of retry attempts
MAX_MEMORY_RECORDS = 1000  # Maximum number of records to keep in memory
ACCOUNT_CHANGE_DELAY = 60  # Delay between switching accounts (seconds)
MAX_FAILURES_BEFORE_BLOCK = 3  # Number of consecutive failures before considering account blocked
MAX_MEMBERS_PER_DAY = 20  # Maximum number of members to extract or add per account per day

# Global variables
request_count = 0
last_request_time = None
ai_training_data = []
current_session = None

# Create unique session identifier
session_id = str(uuid.uuid4())

# Account status enum
class AccountStatus:
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    BLOCKED = "blocked"
    UNVERIFIED = "unverified"
    DAILY_LIMIT_REACHED = "daily_limit_reached"

# Account manager class
class AccountManager:
    def __init__(self):
        self.accounts = []
        self.current_account_index = 0
        self.active_clients = {}  # Dictionary to store active TelegramClient instances
        self._load_encryption_key()
        self._load_accounts()

    def _load_encryption_key(self):
        """Load or generate encryption key for sensitive data"""
        if os.path.exists(ENCRYPTION_KEY_FILE):
            with open(ENCRYPTION_KEY_FILE, "rb") as key_file:
                self.key = key_file.read()
        else:
            self.key = Fernet.generate_key()
            with open(ENCRYPTION_KEY_FILE, "wb") as key_file:
                key_file.write(self.key)

        self.cipher = Fernet(self.key)

    def _load_accounts(self):
        """Load accounts from file"""
        if not os.path.exists(ACCOUNTS_FILE):
            self.accounts = []
            return

        try:
            with open(ACCOUNTS_FILE, "r") as file:
                encrypted_data = file.read()
                if not encrypted_data:
                    self.accounts = []
                    return

                decrypted_data = self.cipher.decrypt(encrypted_data.encode()).decode()
                self.accounts = json.loads(decrypted_data)

                # Set default values for any missing fields
                now = datetime.now()
                for account in self.accounts:
                    if "status" not in account:
                        account["status"] = AccountStatus.ACTIVE
                    if "cooldown_until" not in account:
                        account["cooldown_until"] = None
                    if "last_used" not in account:
                        account["last_used"] = None
                    if "failure_count" not in account:
                        account["failure_count"] = 0
                    # New fields for daily limit tracking
                    if "members_added_today" not in account:
                        account["members_added_today"] = 0
                    if "members_extracted_today" not in account:
                        account["members_extracted_today"] = 0
                    if "daily_reset_time" not in account:
                        account["daily_reset_time"] = now.isoformat()

                    # Check if we need to reset daily counters
                    if "daily_reset_time" in account:
                        try:
                            last_reset = datetime.fromisoformat(account["daily_reset_time"])
                            if (now - last_reset).total_seconds() > 86400:  # 24 hours in seconds
                                account["members_added_today"] = 0
                                account["members_extracted_today"] = 0
                                account["daily_reset_time"] = now.isoformat()

                                # If account was daily limit reached, set it back to active
                                if account["status"] == AccountStatus.DAILY_LIMIT_REACHED:
                                    account["status"] = AccountStatus.ACTIVE
                        except:
                            account["daily_reset_time"] = now.isoformat()

                self._save_accounts()
        except Exception as e:
            logger.error(f"Error loading accounts: {e}")
            self.accounts = []

    def _save_accounts(self):
        """Save accounts to file"""
        try:
            encrypted_data = self.cipher.encrypt(json.dumps(self.accounts).encode()).decode()
            with open(ACCOUNTS_FILE, "w") as file:
                file.write(encrypted_data)
        except Exception as e:
            logger.error(f"Error saving accounts: {e}")

    def add_account(self, api_id, api_hash, phone, session_string=None):
        """Add a new account to the manager"""
        # Check if account already exists
        for i, account in enumerate(self.accounts):
            if account["phone"] == phone:
                # Update existing account if found
                if session_string and not account["session_string"]:
                    account["session_string"] = session_string
                    account["status"] = AccountStatus.ACTIVE
                    self._save_accounts()
                return i

        # Add new account
        account = {
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "session_string": session_string,
            "status": AccountStatus.ACTIVE if session_string else AccountStatus.UNVERIFIED,
            "cooldown_until": None,
            "last_used": None,
            "failure_count": 0,
            "members_added_today": 0,
            "members_extracted_today": 0,
            "daily_reset_time": datetime.now().isoformat(),
            "added_date": datetime.now().isoformat()
        }

        self.accounts.append(account)
        self._save_accounts()
        return len(self.accounts) - 1  # Return the index of the new account

    def remove_account(self, index):
        """Remove an account by index"""
        if 0 <= index < len(self.accounts):
            phone = self.accounts[index]["phone"]
            del self.accounts[index]
            self._save_accounts()
            return True, phone
        return False, None

    def get_account_by_phone(self, phone):
        """Find account index by phone number"""
        for i, account in enumerate(self.accounts):
            if account["phone"] == phone:
                return i
        return -1

    def reset_daily_limits(self, index=None):
        """Reset daily limits for account at index or all accounts if index is None"""
        now = datetime.now()

        if index is not None:
            if 0 <= index < len(self.accounts):
                self.accounts[index]["members_added_today"] = 0
                self.accounts[index]["members_extracted_today"] = 0
                self.accounts[index]["daily_reset_time"] = now.isoformat()
                if self.accounts[index]["status"] == AccountStatus.DAILY_LIMIT_REACHED:
                    self.accounts[index]["status"] = AccountStatus.ACTIVE
                self._save_accounts()
                return True
            return False
        else:
            # Reset all accounts
            for account in self.accounts:
                account["members_added_today"] = 0
                account["members_extracted_today"] = 0
                account["daily_reset_time"] = now.isoformat()
                if account["status"] == AccountStatus.DAILY_LIMIT_REACHED:
                    account["status"] = AccountStatus.ACTIVE
            self._save_accounts()
            return True

    def get_next_available_account(self):
        """Get the next available account"""
        if not self.accounts:
            return None, -1

        now = datetime.now()

        # First, check and update cooldown accounts
        for i, account in enumerate(self.accounts):
            # Reset daily counters if needed
            try:
                last_reset = datetime.fromisoformat(account["daily_reset_time"])
                if (now - last_reset).total_seconds() > 86400:  # 24 hours in seconds
                    account["members_added_today"] = 0
                    account["members_extracted_today"] = 0
                    account["daily_reset_time"] = now.isoformat()

                    # If account was daily limit reached, set it back to active
                    if account["status"] == AccountStatus.DAILY_LIMIT_REACHED:
                        account["status"] = AccountStatus.ACTIVE
                        self._save_accounts()
            except:
                account["daily_reset_time"] = now.isoformat()

            # Update cooldown status
            if account["status"] == AccountStatus.COOLDOWN and account["cooldown_until"]:
                cooldown_until = datetime.fromisoformat(account["cooldown_until"])
                if now > cooldown_until:
                    account["status"] = AccountStatus.ACTIVE
                    account["cooldown_until"] = None
                    self._save_accounts()

        # Try to find an active account
        start_index = self.current_account_index
        for _ in range(len(self.accounts)):
            self.current_account_index = (self.current_account_index + 1) % len(self.accounts)
            account = self.accounts[self.current_account_index]

            if account["status"] == AccountStatus.ACTIVE:
                return account, self.current_account_index

        # If no active account found, try to use a cooldown account that's closest to being ready
        closest_cooldown = None
        closest_index = -1
        closest_time = timedelta(days=365)  # Large initial value

        for i, account in enumerate(self.accounts):
            if account["status"] == AccountStatus.COOLDOWN and account["cooldown_until"]:
                cooldown_until = datetime.fromisoformat(account["cooldown_until"])
                time_left = cooldown_until - now
                if time_left < closest_time:
                    closest_time = time_left
                    closest_cooldown = account
                    closest_index = i

        if closest_cooldown:
            wait_minutes = closest_time.total_seconds() / 60
            logger.info(f"No active accounts. Closest account will be ready in {wait_minutes:.1f} minutes.")

        return closest_cooldown, closest_index

    def increment_member_count(self, index, count_type="added"):
        """Increment the member count for an account. Count type can be 'added' or 'extracted'."""
        if 0 <= index < len(self.accounts):
            if count_type == "added":
                self.accounts[index]["members_added_today"] += 1
            elif count_type == "extracted":
                self.accounts[index]["members_extracted_today"] += 1

            # Check if daily limit reached
            if (self.accounts[index]["members_added_today"] >= MAX_MEMBERS_PER_DAY or
                self.accounts[index]["members_extracted_today"] >= MAX_MEMBERS_PER_DAY):
                self.accounts[index]["status"] = AccountStatus.DAILY_LIMIT_REACHED
                logger.warning(f"Daily limit reached for account {self.accounts[index]['phone']}.")

            self._save_accounts()
            return True
        return False

    def get_member_counts(self, index):
        """Get the current member counts for an account"""
        if 0 <= index < len(self.accounts):
            return (
                self.accounts[index]["members_added_today"],
                self.accounts[index]["members_extracted_today"]
            )
        return 0, 0

    def set_account_status(self, index, status, cooldown_hours=None):
        """Update account status"""
        if 0 <= index < len(self.accounts):
            self.accounts[index]["status"] = status
            self.accounts[index]["last_used"] = datetime.now().isoformat()

            if status == AccountStatus.COOLDOWN and cooldown_hours:
                cooldown_until = datetime.now() + timedelta(hours=cooldown_hours)
                self.accounts[index]["cooldown_until"] = cooldown_until.isoformat()
            elif status == AccountStatus.ACTIVE:
                self.accounts[index]["cooldown_until"] = None
                self.accounts[index]["failure_count"] = 0

            self._save_accounts()
            return True
        return False

    def increment_failure_count(self, index):
        """Increment failure count for an account"""
        if 0 <= index < len(self.accounts):
            self.accounts[index]["failure_count"] += 1

            # If too many failures, put account in cooldown
            if self.accounts[index]["failure_count"] >= MAX_FAILURES_BEFORE_BLOCK:
                self.set_account_status(index, AccountStatus.COOLDOWN, cooldown_hours=6)

            self._save_accounts()
            return self.accounts[index]["failure_count"]
        return 0

    def reset_failure_count(self, index):
        """Reset failure count for an account"""
        if 0 <= index < len(self.accounts):
            self.accounts[index]["failure_count"] = 0
            self._save_accounts()

    def get_account_stats(self):
        """Get statistics about accounts"""
        total = len(self.accounts)
        active = sum(1 for acc in self.accounts if acc["status"] == AccountStatus.ACTIVE)
        cooldown = sum(1 for acc in self.accounts if acc["status"] == AccountStatus.COOLDOWN)
        blocked = sum(1 for acc in self.accounts if acc["status"] == AccountStatus.BLOCKED)
        unverified = sum(1 for acc in self.accounts if acc["status"] == AccountStatus.UNVERIFIED)
        daily_limit = sum(1 for acc in self.accounts if acc["status"] == AccountStatus.DAILY_LIMIT_REACHED)

        return {
            "total": total,
            "active": active,
            "cooldown": cooldown,
            "blocked": blocked,
            "unverified": unverified,
            "daily_limit_reached": daily_limit
        }

    async def connect_account(self, index):
        """Connect to a Telegram account and return the client"""
        if index < 0 or index >= len(self.accounts):
            return None

        account = self.accounts[index]

        # If already have an active client for this account, return it
        if index in self.active_clients:
            client = self.active_clients[index]
            try:
                if not client.is_connected():
                    await client.connect()
                return client
            except:
                # If reconnect failed, create a new client
                pass

        try:
            if account["session_string"]:
                client = TelegramClient(
                    StringSession(account["session_string"]),
                    account["api_id"],
                    account["api_hash"]
                )
            else:
                client = TelegramClient(
                    StringSession(),
                    account["api_id"],
                    account["api_hash"]
                )

            await client.connect()

            # If account is not verified yet
            if account["status"] == AccountStatus.UNVERIFIED:
                await client.start(phone=account["phone"])
                # Save session string
                session_string = client.session.save()
                account["session_string"] = session_string
                account["status"] = AccountStatus.ACTIVE
                self._save_accounts()

            self.active_clients[index] = client
            return client

        except errors.PhoneNumberInvalidError:
            logger.error(f"Phone number invalid for account {account['phone']}")
            account["status"] = AccountStatus.BLOCKED
            self._save_accounts()
            return None
        except Exception as e:
            logger.error(f"Error connecting to account {account['phone']}: {e}")
            return None

    async def disconnect_all(self):
        """Disconnect all active clients"""
        for client in self.active_clients.values():
            try:
                await client.disconnect()
            except:
                pass
        self.active_clients = {}

# Create account manager instance
account_manager = AccountManager()

# Original functions from the base code

def setup_session():
    """Set up a new session for data collection"""
    global current_session

    current_session = {
        "session_id": session_id,
        "start_time": datetime.now().isoformat(),
        "device_info": f"{platform.system()} {platform.release()}",
        "completed": False,
        "attempts": [],
        "user_data": []
    }

    # Initial session save
    save_session()

def save_session():
    """Save current session state"""
    global current_session

    if current_session:
        try:
            filename = f"session_{current_session['session_id']}.json"
            with open(filename, "w") as file:
                json.dump(current_session, file, indent=2)
            logger.debug(f"Session saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving session: {e}")

def check_incomplete_sessions():
    """Check for previous incomplete sessions"""
    try:
        session_files = glob.glob("session_*.json")
        for session_file in session_files:
            with open(session_file, 'r') as f:
                session = json.load(f)
                if not session.get("completed", False):
                    return session_file, session
    except Exception as e:
        logger.error(f"Error checking incomplete sessions: {e}")
    return None, None

def generate_salt():
    """Generate random salt for encryption"""
    return os.urandom(16)

class Encryptor:
    def __init__(self, password, salt=None):
        """Create an encryption object using password and salt"""
        if salt is None:
            # Try to read salt from file
            if os.path.exists(SALT_FILE):
                with open(SALT_FILE, "rb") as salt_file:
                    salt = salt_file.read()
            else:
                # Create new salt
                salt = generate_salt()
                with open(SALT_FILE, "wb") as salt_file:
                    salt_file.write(salt)

        # Generate key from password and salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)

    def encrypt(self, data):
        """Encrypt data"""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data):
        """Decrypt data"""
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Error decrypting data: {e}")
            return None

def get_password(prompt):
    """Get password from user"""
    return getpass.getpass(prompt)

def load_config(password=None):
    """Read information from encrypted configuration file"""
    if not os.path.exists(CONFIG_FILE):
        return None, None, None, None

    try:
        if password is None:
            password = get_password("Enter password to decrypt configuration:")

        encryptor = Encryptor(password)
        with open(CONFIG_FILE, 'r') as file:
            encrypted_data = file.read()
            decrypted_json = encryptor.decrypt(encrypted_data)
            if decrypted_json:
                config = json.loads(decrypted_json)
                return (
                    config.get('api_id'),
                    config.get('api_hash'),
                    config.get('phone'),
                    config.get('session_string')
                )
            else:
                logger.error("Failed to decrypt configuration file. Wrong password?")
                return None, None, None, None
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return None, None, None, None

def save_config(api_id, api_hash, phone, session_string, password=None):
    """Save information to encrypted configuration file"""
    try:
        if password is None:
            password = get_password("Create a password to encrypt your configuration:")

        # Create new salt
        salt = generate_salt()
        with open(SALT_FILE, "wb") as salt_file:
            salt_file.write(salt)

        config = {
            'api_id': api_id,
            'api_hash': api_hash,
            'phone': phone,
            'session_string': session_string
        }

        encryptor = Encryptor(password, salt)
        encrypted_data = encryptor.encrypt(json.dumps(config))

        with open(CONFIG_FILE, 'w') as file:
            file.write(encrypted_data)

        logger.info("Configuration saved and encrypted successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        return False

def get_user_inputs():
    """Get user inputs in console mode"""
    api_id, api_hash, phone, session_string = load_config()
    if not all([api_id, api_hash, phone]):
        logger.info("No configuration found or it's incomplete. Please enter your Telegram credentials:")
        api_id = int(input("API ID: "))
        api_hash = input("API Hash: ")
        phone = input("Phone Number (with country code): ")
        password = get_password("Create a password to encrypt your configuration:")
        save_config(api_id, api_hash, phone, "", password)
    return api_id, api_hash, phone, session_string

def is_bot(user):
    """Check if user is a bot"""
    return getattr(user, 'bot', False)

def is_user_active(user, threshold=timedelta(hours=72)):
    """Check user activity based on last seen status"""
    status_type = "Unknown"
    status_details = {}

    if user.status is None:
        status_type = "NoStatus"
        return False, status_type, status_details

    if isinstance(user.status, types.UserStatusOnline):
        status_type = "Online"
        return True, status_type, status_details
    elif isinstance(user.status, types.UserStatusRecently):
        status_type = "Recently"
        return True, status_type, status_details
    elif isinstance(user.status, types.UserStatusLastWeek):
        status_type = "LastWeek"
        return False, status_type, status_details
    elif isinstance(user.status, types.UserStatusLastMonth):
        status_type = "LastMonth"
        return False, status_type, status_details
    elif isinstance(user.status, types.UserStatusOffline):
        last_seen = user.status.was_online
        status_type = "Offline"
        hours_ago = (datetime.now(tz=last_seen.tzinfo) - last_seen).total_seconds() / 3600
        status_details = {"hours_ago": hours_ago}

        if datetime.now(tz=last_seen.tzinfo) - last_seen < threshold:
            return True, status_type, status_details

    return False, status_type, status_details

def is_fake_account(user):
    """Check if user is likely a fake or bot account"""
    # Fake user indicators
    fake_indicators = 0
    reasons = []
    fake_features = {}

    # Check username
    if user.username:
        fake_features["has_username"] = True
        fake_features["username_length"] = len(user.username)

        # Suspicious patterns in username (many numbers or random characters)
        if re.match(r'.*\d{4,}.*', user.username):
            fake_indicators += 1
            reasons.append("Username has many numbers")
            fake_features["has_many_numbers"] = True
        else:
            fake_features["has_many_numbers"] = False

        if re.match(r'[a-zA-Z0-9]{10,}$', user.username) and not re.match(r'[a-z]+', user.username.lower()):
            fake_indicators += 1
            reasons.append("Username looks random")
            fake_features["random_username"] = True
        else:
            fake_features["random_username"] = False
    else:
        fake_features["has_username"] = False

    # Check first and last name
    fake_features["has_first_name"] = bool(user.first_name)
    fake_features["has_last_name"] = bool(user.last_name)

    if not user.first_name and not user.last_name:
        fake_indicators += 2
        reasons.append("No name")

    # Check profile photo
    fake_features["has_photo"] = bool(user.photo)
    if not user.photo:
        fake_indicators += 1
        reasons.append("No profile photo")

    # Check account status
    fake_features["is_verified"] = getattr(user, 'verified', False)
    if fake_features["is_verified"]:
        fake_indicators -= 3  # Verified accounts are likely real

    # Final score for fake detection
    fake_features["fake_score"] = fake_indicators
    is_fake = fake_indicators >= 2

    return is_fake, reasons, fake_features

def collect_user_data(user, is_active, status_type, status_details, is_fake, fake_reasons, fake_features):
    """Collect user information for AI training"""
    user_data = {
        "user_id": user.id,
        "timestamp": datetime.now().isoformat(),
        "features": {
            "has_username": bool(user.username),
            "username_length": len(user.username) if user.username else 0,
            "has_first_name": bool(user.first_name),
            "has_last_name": bool(user.last_name),
            "has_photo": bool(user.photo),
            "is_verified": getattr(user, 'verified', False),
            "is_bot": is_bot(user),
            "status_type": status_type,
            **status_details,
            **fake_features
        },
        "labels": {
            "is_active": is_active,
            "is_fake": is_fake,
            "fake_reasons": fake_reasons
        }
    }
    return user_data

def load_ai_training_data():
    """Load AI training data"""
    global ai_training_data

    if not os.path.exists(AI_DATA_FILE):
        ai_training_data = []
        return

    try:
        with open(AI_DATA_FILE, "r") as file:
            ai_training_data = json.load(file)

        # Limit number of records in memory
        if len(ai_training_data) > MAX_MEMORY_RECORDS:
            ai_training_data = ai_training_data[-MAX_MEMORY_RECORDS:]

    except Exception as e:
        logger.error(f"Error loading AI training data: {e}")
        ai_training_data = []

def save_ai_training_data(force=False):
    """Save AI training data"""
    global ai_training_data, current_session

    # Save data in current session
    if current_session:
        current_session["attempts"] = ai_training_data[-100:]  # Only last 100 attempts
        save_session()

    if not force and len(ai_training_data) % 10 != 0:
        # Save every 10 records or when force=True
        return

    try:
        # Save to main file
        existing_data = []
        if os.path.exists(AI_DATA_FILE):
            with open(AI_DATA_FILE, "r") as file:
                try:
                    existing_data = json.load(file)
                except:
                    existing_data = []

        # Combine existing data with new data
        combined_data = existing_data + ai_training_data

        # Save all data
        with open(AI_DATA_FILE, "w") as file:
            json.dump(combined_data, file, indent=2)

        # Clear in-memory data list after saving
        ai_training_data = []

        logger.debug(f"AI training data saved to {AI_DATA_FILE}")
    except Exception as e:
        logger.error(f"Error saving AI training data: {e}")

def load_request_stats():
    """Load request statistics from file"""
    global request_count, last_request_time

    if not os.path.exists(REQUEST_LOG_FILE):
        request_count = 0
        last_request_time = None
        return

    try:
        with open(REQUEST_LOG_FILE, "r") as file:
            data = json.load(file)
            request_count = data.get("count", 0)
            timestamp = data.get("timestamp")
            if timestamp:
                last_request_time = datetime.fromisoformat(timestamp)
            else:
                last_request_time = None

            # Check if 24 hours have passed
            if last_request_time and datetime.now() - last_request_time > timedelta(hours=24):
                logger.info("Resetting request count due to 24 hours passed.")
                request_count = 0
                save_request_stats()
    except Exception as e:
        logger.error(f"Error loading request stats: {e}")
        request_count = 0
        last_request_time = None

def save_request_stats():
    """Save request statistics to file"""
    global request_count, last_request_time

    data = {
        "count": request_count,
        "timestamp": datetime.now().isoformat() if last_request_time else None
    }

    try:
        with open(REQUEST_LOG_FILE, "w") as file:
            json.dump(data, file)
    except Exception as e:
        logger.error(f"Error saving request stats: {e}")

# Modified functions for multi-account support

async def add_user_to_group_with_account(client, user_id, group_entity, account_index, user_info="", current_delay=DEFAULT_DELAY, retry_count=0):
    """Add user to group using a specific account"""
    global request_count, last_request_time, ai_training_data

    # Collect data about current attempt
    attempt_data = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "user_info": user_info,
        "account_phone": account_manager.accounts[account_index]["phone"] if account_index >= 0 else "unknown",
        "features": {
            "hour_of_day": datetime.now().hour,
            "day_of_week": datetime.now().weekday(),
            "current_delay": current_delay,
            "retry_count": retry_count,
            "request_count": request_count,
            "time_since_last_request": (datetime.now() - last_request_time).total_seconds() if last_request_time else None
        }
    }

    # Check time since last request
    if last_request_time:
        elapsed = (datetime.now() - last_request_time).total_seconds()
        if elapsed < current_delay:
            wait_time = current_delay - elapsed
            logger.debug(f"Waiting {wait_time:.2f} seconds before next request")
            await asyncio.sleep(wait_time)

    start_time = datetime.now()
    success = False
    error_type = None
    error_details = {}

    try:
        # Check if we've reached the daily limit for this account
        if account_index >= 0:
            added_today, _ = account_manager.get_member_counts(account_index)
            if added_today >= MAX_MEMBERS_PER_DAY:
                logger.warning(f"Daily limit reached for account {account_manager.accounts[account_index]['phone']}. Using another account.")
                account_manager.set_account_status(account_index, AccountStatus.DAILY_LIMIT_REACHED)
                error_type = "DailyLimitReached"
                success = False
                return False, current_delay

        logger.info(f"Attempting to add user {user_id} ({user_info}) to the group...")
        result = await client(functions.channels.InviteToChannelRequest(
            channel=group_entity,
            users=[user_id]
        ))

        # Update request counter and time
        request_count += 1
        last_request_time = datetime.now()
        save_request_stats()

        # If successful, increment the member count for this account
        if account_index >= 0:
            account_manager.increment_member_count(account_index, "added")

        logger.info(f"{Fore.GREEN}User {user_id} ({user_info}) added to the group successfully.{Style.RESET_ALL}")
        success = True
        return True, current_delay
    except errors.FloodWaitError as e:
        wait_time = e.seconds
        error_type = "FloodWaitError"
        error_details = {"wait_seconds": wait_time}
        logger.warning(f"{Fore.RED}FloodWaitError: Must wait {wait_time} seconds before next request.{Style.RESET_ALL}")

        # Update account status
        if account_index >= 0:
            cooldown_hours = max(1, wait_time / 3600)  # Convert seconds to hours, min 1 hour
            account_manager.set_account_status(account_index, AccountStatus.COOLDOWN, cooldown_hours=cooldown_hours)

        # Update request counter and time
        request_count += 1
        last_request_time = datetime.now()
        save_request_stats()

        # Update attempt data
        attempt_data["result"] = {
            "success": False,
            "error_type": error_type,
            "error_details": error_details,
            "response_time": (datetime.now() - start_time).total_seconds()
        }
        ai_training_data.append(attempt_data)
        save_ai_training_data()

        return False, current_delay
    except errors.UserPrivacyRestrictedError:
        error_type = "UserPrivacyRestrictedError"
        logger.warning(f"{Fore.YELLOW}User {user_id} has privacy restrictions and cannot be added.{Style.RESET_ALL}")
        # Update request counter and time
        request_count += 1
        last_request_time = datetime.now()
        save_request_stats()
        success = False
        return False, current_delay
    except errors.PeerFloodError:
        error_type = "PeerFloodError"
        new_delay = min(current_delay * 2, MAX_DELAY)
        logger.warning(f"{Fore.RED}PEER_FLOOD: Too many requests. Increasing delay to {new_delay} seconds.{Style.RESET_ALL}")

        # Update account status
        if account_index >= 0:
            account_manager.increment_failure_count(account_index)
            # If too many failures, put account in cooldown
            if account_manager.accounts[account_index]["failure_count"] >= MAX_FAILURES_BEFORE_BLOCK:
                account_manager.set_account_status(account_index, AccountStatus.COOLDOWN, cooldown_hours=6)

        # Update request counter and time
        request_count += 1
        last_request_time = datetime.now()
        save_request_stats()
        success = False

        # Update attempt data
        attempt_data["result"] = {
            "success": False,
            "error_type": error_type,
            "new_delay": new_delay,
            "response_time": (datetime.now() - start_time).total_seconds()
        }
        ai_training_data.append(attempt_data)
        save_ai_training_data()

        return False, new_delay
    except errors.PhoneNumberBannedError:
        error_type = "PhoneNumberBannedError"
        logger.error(f"{Fore.RED}Account {account_manager.accounts[account_index]['phone']} has been banned by Telegram.{Style.RESET_ALL}")

        # Mark account as blocked
        if account_index >= 0:
            account_manager.set_account_status(account_index, AccountStatus.BLOCKED)

        success = False
        return False, current_delay
    except Exception as e:
        error_type = type(e).__name__
        error_details = {"message": str(e)}
        logger.error(f"{Fore.RED}Failed to add user {user_id} to the group: {e}{Style.RESET_ALL}")
        logger.debug(traceback.format_exc())

        # Increment failure count for account
        if account_index >= 0:
            account_manager.increment_failure_count(account_index)

        # Update request counter and time
        request_count += 1
        last_request_time = datetime.now()
        save_request_stats()
        success = False
        return False, current_delay
    finally:
        # In any case, save this attempt data (if not already saved)
        if "result" not in attempt_data:
            attempt_data["result"] = {
                "success": success,
                "error_type": error_type,
                "error_details": error_details,
                "response_time": (datetime.now() - start_time).total_seconds()
            }
            ai_training_data.append(attempt_data)
            save_ai_training_data()

async def process_queue_with_accounts(queue, target_group, progress_callback=None):
    """Process queue of users to add to group using multiple accounts"""
    current_delay = DEFAULT_DELAY
    total_users = queue.qsize()
    processed = 0
    success_count = 0

    start_time = time.time()
    current_account = None
    current_account_index = -1

    while not queue.empty():
        # If we don't have a current account or need to switch
        if current_account is None:
            # Get the next available account
            account, account_index = account_manager.get_next_available_account()

            if not account:
                # No accounts available, wait and try again
                logger.warning(f"{Fore.YELLOW}No accounts available currently. Waiting 5 minutes...{Style.RESET_ALL}")
                await asyncio.sleep(300)  # Wait 5 minutes
                continue

            current_account_index = account_index
            logger.info(f"Using account: {account['phone']}")

            # Connect to this account
            current_account = await account_manager.connect_account(account_index)

            if not current_account:
                logger.error(f"{Fore.RED}Failed to connect to account {account['phone']}. Trying another account.{Style.RESET_ALL}")
                account_manager.set_account_status(account_index, AccountStatus.COOLDOWN, cooldown_hours=1)
                current_account = None
                await asyncio.sleep(5)
                continue

            # Check if this account already hit daily limit
            added_today, _ = account_manager.get_member_counts(account_index)
            if added_today >= MAX_MEMBERS_PER_DAY:
                logger.warning(f"{Fore.YELLOW}Account {account['phone']} has reached daily limit. Trying another account.{Style.RESET_ALL}")
                account_manager.set_account_status(account_index, AccountStatus.DAILY_LIMIT_REACHED)
                # Disconnect and try another account
                await current_account.disconnect()
                current_account = None
                await asyncio.sleep(5)
                continue

        # Process a batch with the current account
        batch_size = min(5, queue.qsize(), MAX_MEMBERS_PER_DAY - added_today)  # Process in small batches
        batch_success = 0

        for _ in range(batch_size):
            if queue.empty():
                break

            user_id, user_info = queue.get()

            try:
                success, new_delay = await add_user_to_group_with_account(
                    current_account,
                    user_id,
                    target_group,
                    current_account_index,
                    user_info,
                    current_delay
                )

                if success:
                    batch_success += 1
                    success_count += 1

                processed += 1
                current_delay = new_delay

                # Update progress
                elapsed = time.time() - start_time
                estimated_time = (elapsed / processed) * (total_users - processed) if processed > 0 else 0
                progress_data = {
                    "processed": processed,
                    "total": total_users,
                    "success_count": success_count,
                    "current_delay": current_delay,
                    "elapsed_time": elapsed,
                    "estimated_time": estimated_time,
                    "current_account": account_manager.accounts[current_account_index]["phone"] if current_account_index >= 0 else "unknown"
                }

                if progress_callback:
                    progress_callback(progress_data)
                else:
                    progress_percent = (processed / total_users) * 100 if total_users > 0 else 0
                    logger.info(f"Progress: {processed}/{total_users} ({progress_percent:.1f}%) - Success: {success_count}")

                # Check if we've hit errors that require changing accounts
                if current_account_index >= 0:
                    account_status = account_manager.accounts[current_account_index]["status"]
                    if account_status in [AccountStatus.COOLDOWN, AccountStatus.BLOCKED, AccountStatus.DAILY_LIMIT_REACHED]:
                        logger.info(f"Account {account_manager.accounts[current_account_index]['phone']} status changed to {account_status}. Switching accounts.")
                        break

                # Take a short break between requests (randomized to avoid patterns)
                await asyncio.sleep(current_delay + random.uniform(-5, 5))

            except Exception as e:
                logger.error(f"Error processing user {user_id}: {e}")
                # Put the user back in the queue to retry with another account
                queue.put((user_id, user_info))
                processed -= 1  # Adjust counter since we're retrying
                break

        # After a batch, take a break and switch accounts
        logger.info(f"Completed batch with account {account_manager.accounts[current_account_index]['phone']}. Added {batch_success} members.")

        # Reset failure count if some successes
        if batch_success > 0 and current_account_index >= 0:
            account_manager.reset_failure_count(current_account_index)

        # Disconnect current account
        if current_account:
            try:
                await current_account.disconnect()
            except:
                pass

        current_account = None

        # Take a break between account switches
        await asyncio.sleep(ACCOUNT_CHANGE_DELAY)

    return success_count, processed

async def fetch_active_members_with_accounts(source_group, member_limit=20, progress_callback=None):
    """Extract active members using multiple accounts"""
    global current_session

    logger.info(f"Fetching members from the source group (limit: {member_limit})...")

    all_participants = []  # List to hold all fetched users
    all_user_data = []     # List to hold user data for AI training

    remaining_limit = member_limit
    current_account = None
    current_account_index = -1

    while remaining_limit > 0:
        # Get the next available account
        account, account_index = account_manager.get_next_available_account()

        if not account:
            # No accounts available, check if we have enough members already
            if all_participants:
                logger.warning(f"{Fore.YELLOW}No more accounts available. Proceeding with {len(all_participants)} members.{Style.RESET_ALL}")
                break
            else:
                # No accounts and no members yet, wait and try again
                logger.warning(f"{Fore.YELLOW}No accounts available currently. Waiting 5 minutes...{Style.RESET_ALL}")
                await asyncio.sleep(300)  # Wait 5 minutes
                continue

        current_account_index = account_index
        logger.info(f"Using account {account['phone']} for fetching members.")

        # Check if this account already hit daily limit
        _, extracted_today = account_manager.get_member_counts(account_index)
        if extracted_today >= MAX_MEMBERS_PER_DAY:
            logger.warning(f"{Fore.YELLOW}Account {account['phone']} has reached daily extraction limit. Trying another account.{Style.RESET_ALL}")
            account_manager.set_account_status(account_index, AccountStatus.DAILY_LIMIT_REACHED)
            await asyncio.sleep(5)
            continue

        # Connect to this account
        current_account = await account_manager.connect_account(account_index)

        if not current_account:
            logger.error(f"{Fore.RED}Failed to connect to account {account['phone']}. Trying another account.{Style.RESET_ALL}")
            account_manager.set_account_status(account_index, AccountStatus.COOLDOWN, cooldown_hours=1)
            await asyncio.sleep(5)
            continue

        # Calculate batch size for this account
        batch_limit = min(20, remaining_limit, MAX_MEMBERS_PER_DAY - extracted_today)

        try:
            # Get total member count first
            members_info = await current_account.get_participants(source_group, limit=0)
            total_members = members_info.total
            logger.info(f"Total members in the source group: {total_members}")

            # Set batch size based on total members
            batch_size = min(100, total_members // 10)  # Maximum 100 or one tenth of total
            if batch_size < 10:
                batch_size = 10  # Minimum 10 users per batch

            # Fetch a batch of members
            offset = 0
            required_sample = min(total_members, batch_limit * 3)  # 3x for more selection
            current_batch = []

            while len(current_batch) < required_sample:
                try:
                    # Use offset to get different batches
                    users_batch = await current_account.get_participants(source_group, limit=batch_size, offset=offset)
                    if not users_batch:
                        break

                    current_batch.extend(users_batch)
                    offset += len(users_batch)

                    # Increment extraction count
                    account_manager.increment_member_count(current_account_index, "extracted")

                    # Update progress
                    if progress_callback:
                        progress_callback({
                            "phase": "fetching",
                            "fetched": len(current_batch),
                            "required": required_sample,
                            "progress": (len(current_batch) / required_sample) * 100 if required_sample > 0 else 0,
                            "account": account["phone"]
                        })

                    logger.info(f"Fetched {len(current_batch)}/{required_sample} members with account {account['phone']}.")

                    # Check if we hit the daily limit
                    _, extracted_today = account_manager.get_member_counts(current_account_index)
                    if extracted_today >= MAX_MEMBERS_PER_DAY:
                        logger.warning(f"{Fore.YELLOW}Account {account['phone']} reached daily extraction limit during fetch.{Style.RESET_ALL}")
                        account_manager.set_account_status(current_account_index, AccountStatus.DAILY_LIMIT_REACHED)
                        break

                    # Add delay to avoid limits
                    await asyncio.sleep(2)
                except errors.FloodWaitError as e:
                    wait_time = e.seconds
                    logger.warning(f"{Fore.RED}FloodWaitError: Must wait {wait_time} seconds.{Style.RESET_ALL}")

                    # Put account in cooldown
                    cooldown_hours = max(1, wait_time / 3600)
                    account_manager.set_account_status(current_account_index, AccountStatus.COOLDOWN, cooldown_hours=cooldown_hours)
                    break
                except Exception as e:
                    logger.error(f"Error fetching batch of members: {e}")
                    logger.debug(traceback.format_exc())
                    account_manager.increment_failure_count(current_account_index)
                    break

            # Filter and process the current batch
            filtered_from_batch = []

            for user in current_batch:
                # Check user status
                is_active, status_type, status_details = is_user_active(user)
                is_fake, fake_reasons, fake_features = is_fake_account(user)

                # Collect data for AI training
                user_data = collect_user_data(user, is_active, status_type, status_details, is_fake, fake_reasons, fake_features)
                all_user_data.append(user_data)

                # Add to current session
                if current_session:
                    current_session["user_data"].append(user_data)
                    if len(current_session["user_data"]) % 20 == 0:
                        save_session()

                # Filter out bots, inactive and fake users
                if is_bot(user):
                    continue

                if not is_active:
                    continue

                if is_fake:
                    continue

                user_info = f"{user.first_name or ''} {user.last_name or ''} (@{user.username or 'No username'}) - {status_type}"
                filtered_from_batch.append((user, user_info))

                # If we reached the batch limit, exit
                if len(filtered_from_batch) >= batch_limit:
                    break

            # Add filtered members from this batch to our total
            all_participants.extend(filtered_from_batch)
            logger.info(f"Added {len(filtered_from_batch)} filtered members from account {account['phone']}.")

            # Update remaining limit
            remaining_limit -= len(filtered_from_batch)

            # Disconnect account
            await current_account.disconnect()
            current_account = None

            # Take a break between accounts
            await asyncio.sleep(ACCOUNT_CHANGE_DELAY)

            # If we've reached our total limit, we're done
            if remaining_limit <= 0:
                break

        except Exception as e:
            logger.error(f"Error using account {account['phone']} to fetch members: {e}")
            logger.debug(traceback.format_exc())

            # Mark account as having an issue
            account_manager.increment_failure_count(current_account_index)

            # Disconnect account
            if current_account:
                try:
                    await current_account.disconnect()
                except:
                    pass
                current_account = None

    # Save user data to separate file
    user_data_file = f"user_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(user_data_file, "w") as file:
            json.dump(all_user_data, file, indent=2)
        logger.info(f"User data saved to {user_data_file}")
    except Exception as e:
        logger.error(f"Error saving user data: {e}")

    logger.info(f"Filtered {len(all_participants)} active, non-bot, legitimate users from all accounts.")
    return all_participants

# New functions for account management

def add_new_account():
    """Add a new account with user input"""
    print(f"\n{Fore.CYAN}=== Adding New Account ==={Style.RESET_ALL}")

    try:
        api_id = int(input("API ID: ").strip())
        api_hash = input("API Hash: ").strip()
        phone = input("Phone Number (with country code): ").strip()

        # Check if account already exists
        existing_index = account_manager.get_account_by_phone(phone)
        if existing_index >= 0:
            print(f"{Fore.YELLOW}This account already exists at index {existing_index}.{Style.RESET_ALL}")
            return existing_index

        # Add new account
        index = account_manager.add_account(api_id, api_hash, phone)
        print(f"{Fore.GREEN}Account added successfully with index {index}.{Style.RESET_ALL}")
        return index

    except ValueError:
        print(f"{Fore.RED}Invalid API ID. Must be a number.{Style.RESET_ALL}")
        return -1
    except Exception as e:
        print(f"{Fore.RED}Error adding account: {e}{Style.RESET_ALL}")
        return -1

def list_accounts():
    """Display list of all accounts"""
    accounts = account_manager.accounts

    if not accounts:
        print(f"{Fore.YELLOW}No accounts found.{Style.RESET_ALL}")
        return

    print(f"\n{Fore.CYAN}=== Account List ({len(accounts)} accounts) ==={Style.RESET_ALL}")
    print(f"{'Index':<6} {'Phone':<15} {'Status':<20} {'Added Today':<12} {'Extracted Today':<15} {'Last Used':<20}")
    print("-" * 80)

    for i, account in enumerate(accounts):
        status_color = Fore.GREEN if account["status"] == AccountStatus.ACTIVE else \
                      Fore.YELLOW if account["status"] == AccountStatus.COOLDOWN else \
                      Fore.RED if account["status"] == AccountStatus.BLOCKED else \
                      Fore.BLUE if account["status"] == AccountStatus.UNVERIFIED else \
                      Fore.MAGENTA  # For DAILY_LIMIT_REACHED

        status_text = account["status"]
        if account["status"] == AccountStatus.COOLDOWN and account["cooldown_until"]:
            try:
                cooldown_until = datetime.fromisoformat(account["cooldown_until"])
                if cooldown_until > datetime.now():
                    minutes_left = (cooldown_until - datetime.now()).total_seconds() / 60
                    status_text = f"{account['status']} ({minutes_left:.0f}m left)"
            except:
                pass

        last_used = "Never"
        if account["last_used"]:
            try:
                last_used_time = datetime.fromisoformat(account["last_used"])
                last_used = last_used_time.strftime("%Y-%m-%d %H:%M")
            except:
                last_used = "Invalid date"

        print(f"{i:<6} {account['phone']:<15} {status_color}{status_text:<20}{Style.RESET_ALL} "
              f"{account['members_added_today']:<12} {account['members_extracted_today']:<15} {last_used:<20}")

    # Display account stats
    stats = account_manager.get_account_stats()
    print(f"\n{Fore.CYAN}Account Statistics:{Style.RESET_ALL}")
    print(f"Total: {stats['total']}, Active: {stats['active']}, Cooldown: {stats['cooldown']}, "
          f"Blocked: {stats['blocked']}, Unverified: {stats['unverified']}, Daily Limit Reached: {stats['daily_limit_reached']}")

def remove_account_interactive():
    """Remove an account interactively"""
    list_accounts()

    if not account_manager.accounts:
        return

    try:
        index = int(input(f"\n{Fore.YELLOW}Enter the index of the account to remove (-1 to cancel): {Style.RESET_ALL}"))

        if index == -1:
            print("Canceled.")
            return

        success, phone = account_manager.remove_account(index)
        if success:
            print(f"{Fore.GREEN}Account {phone} removed successfully.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Invalid account index.{Style.RESET_ALL}")

    except ValueError:
        print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error removing account: {e}{Style.RESET_ALL}")

def reset_account_limits_interactive():
    """Reset daily limits for accounts interactively"""
    list_accounts()

    if not account_manager.accounts:
        return

    try:
        index = input(f"\n{Fore.YELLOW}Enter the index of the account to reset limits, or 'all' to reset all accounts (-1 to cancel): {Style.RESET_ALL}")

        if index == "-1":
            print("Canceled.")
            return

        if index.lower() == "all":
            account_manager.reset_daily_limits()
            print(f"{Fore.GREEN}Daily limits reset for all accounts.{Style.RESET_ALL}")
        else:
            index = int(index)
            if account_manager.reset_daily_limits(index):
                print(f"{Fore.GREEN}Daily limits reset for account {account_manager.accounts[index]['phone']}.{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Invalid account index.{Style.RESET_ALL}")

    except ValueError:
        print(f"{Fore.RED}Invalid input. Please enter a number or 'all'.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error resetting limits: {e}{Style.RESET_ALL}")

def manage_accounts():
    """Menu for managing accounts"""
    while True:
        print(f"\n{Fore.CYAN}=== Account Management Menu ==={Style.RESET_ALL}")
        print("1. List All Accounts")
        print("2. Add New Account")
        print("3. Remove Account")
        print("4. Reset Daily Limits")
        print("5. Return to Main Menu")

        choice = input(f"\n{Fore.YELLOW}Enter your choice (1-5): {Style.RESET_ALL}")

        if choice == "1":
            list_accounts()
        elif choice == "2":
            add_new_account()
        elif choice == "3":
            remove_account_interactive()
        elif choice == "4":
            reset_account_limits_interactive()
        elif choice == "5":
            break
        else:
            print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and 5.{Style.RESET_ALL}")

def print_welcome_message():
    """Display welcome message and instructions"""
    welcome = f"""
{Fore.CYAN}================================================================{Style.RESET_ALL}
    {Fore.GREEN}Multi-Account Telegram Member Adder with 20 Member/Day Limit{Style.RESET_ALL}
{Fore.CYAN}================================================================{Style.RESET_ALL}

This program helps you transfer active members from one group to another
using multiple Telegram accounts with a daily limit of 20 members per account.

{Fore.YELLOW}Important Notes:{Style.RESET_ALL}
• Add multiple accounts to increase your daily member transfer capacity
• Each account is limited to 20 members per day (adding or extracting)
• Accounts with issues are automatically put in cooldown
• The system automatically rotates between accounts

{Fore.CYAN}================================================================{Style.RESET_ALL}
"""
    print(welcome)

def progress_display(data):
    """Display progress information"""
    if "phase" in data and data["phase"] == "fetching":
        progress = data["progress"]
        fetched = data["fetched"]
        required = data["required"]
        account = data.get("account", "unknown")
        bar_length = 30
        filled_length = int(bar_length * fetched / required) if required > 0 else 0
        bar = '█' * filled_length + '░' * (bar_length - filled_length)

        sys.stdout.write(f"\r{Fore.CYAN}Fetching members: [{bar}] {progress:.1f}% ({fetched}/{required}) - Account: {account}{Style.RESET_ALL}")
        sys.stdout.flush()
    else:
        processed = data.get("processed", 0)
        total = data.get("total", 1)
        success_count = data.get("success_count", 0)
        current_delay = data.get("current_delay", DEFAULT_DELAY)
        elapsed_time = data.get("elapsed_time", 0)
        estimated_time = data.get("estimated_time", 0)
        current_account = data.get("current_account", "unknown")

        progress = (processed / total) * 100 if total > 0 else 0
        bar_length = 30
        filled_length = int(bar_length * processed / total) if total > 0 else 0
        bar = '█' * filled_length + '░' * (bar_length - filled_length)

        elapsed_min = int(elapsed_time // 60)
        elapsed_sec = int(elapsed_time % 60)

        est_min = int(estimated_time // 60)
        est_sec = int(estimated_time % 60)

        sys.stdout.write(f"\r{Fore.GREEN}Progress: [{bar}] {progress:.1f}% ({processed}/{total}) - Success: {success_count} - "
                         f"Account: {current_account} - Time: {elapsed_min:02d}:{elapsed_sec:02d} - Remaining: {est_min:02d}:{est_sec:02d}{Style.RESET_ALL}")
        sys.stdout.flush()

async def main():
    """Main function"""
    global request_count, last_request_time, ai_training_data, current_session

    try:
        # Display welcome message
        print_welcome_message()

        # Main menu
        while True:
            print(f"\n{Fore.CYAN}=== Main Menu ==={Style.RESET_ALL}")
            print("1. Manage Accounts")
            print("2. Start Member Transfer")
            print("3. Exit")

            choice = input(f"\n{Fore.YELLOW}Enter your choice (1-3): {Style.RESET_ALL}")

            if choice == "1":
                manage_accounts()
            elif choice == "2":
                await start_member_transfer()
            elif choice == "3":
                break
            else:
                print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and 3.{Style.RESET_ALL}")

    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Operation stopped by user.{Style.RESET_ALL}")

        if current_session:
            current_session["interrupted"] = True
            current_session["end_time"] = datetime.now().isoformat()
            save_session()

        save_ai_training_data(force=True)
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
        logger.error(f"Unexpected error: {e}")
        logger.debug(traceback.format_exc())

        if current_session:
            current_session["error"] = str(e)
            current_session["error_traceback"] = traceback.format_exc()
            current_session["end_time"] = datetime.now().isoformat()
            save_session()

        save_ai_training_data(force=True)
    finally:
        # Disconnect all clients
        await account_manager.disconnect_all()

async def start_member_transfer():
    """Start the member transfer process"""
    global current_session

    try:
        # Check if we have any accounts
        if not account_manager.accounts:
            print(f"{Fore.RED}No accounts available. Please add at least one account first.{Style.RESET_ALL}")
            return

        # Check if we have any active or soon-to-be-active accounts
        stats = account_manager.get_account_stats()
        if stats["active"] == 0 and stats["cooldown"] == 0 and stats["unverified"] == 0:
            print(f"{Fore.RED}No active or cooldown accounts available.{Style.RESET_ALL}")
            return

        # Check for incomplete sessions
        continue_incomplete, session_file, incomplete_session = ask_continue_incomplete_session()

        if continue_incomplete and incomplete_session:
            # Continue incomplete session
            current_session = incomplete_session
            logger.info(f"Continuing incomplete session from {session_file}")
        else:
            # Create new session
            setup_session()

        # Load previous AI training data
        load_ai_training_data()

        # Load request count and last request time
        load_request_stats()

        # Select groups - we'll use the first available account just for group selection
        account, account_index = account_manager.get_next_available_account()

        if not account:
            print(f"{Fore.RED}No available accounts at the moment. Try again later.{Style.RESET_ALL}")
            return

        print(f"{Fore.GREEN}Using account {account['phone']} for initial selection.{Style.RESET_ALL}")

        client = await account_manager.connect_account(account_index)

        if not client:
            print(f"{Fore.RED}Failed to connect to account {account['phone']}.{Style.RESET_ALL}")
            return

        # Select groups
        source_group, target_group = await interactive_group_selection(client)

        # Disconnect this client as we'll use multiple accounts later
        await client.disconnect()

        if not source_group or not target_group:
            logger.error("Group selection failed.")
            return

        # Get number of members to transfer
        while True:
            try:
                member_limit = int(input(f"\n{Fore.YELLOW}Enter the number of members to transfer: {Style.RESET_ALL}"))
                if member_limit > 0:
                    break
                print(f"{Fore.RED}Number must be greater than zero.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")

        # Calculate how many accounts we need
        stats = account_manager.get_account_stats()
        accounts_needed = (member_limit + MAX_MEMBERS_PER_DAY - 1) // MAX_MEMBERS_PER_DAY  # Ceiling division
        accounts_available = stats["active"] + stats["unverified"]

        print(f"\n{Fore.CYAN}Member Transfer Details:{Style.RESET_ALL}")
        print(f"Members to transfer: {member_limit}")
        print(f"Accounts needed: {accounts_needed} (20 members per account per day)")
        print(f"Accounts available: {accounts_available}")

        if accounts_needed > accounts_available:
            print(f"{Fore.YELLOW}Warning: You may need more accounts to complete this transfer in one day.{Style.RESET_ALL}")
            add_more = input(f"Would you like to add more accounts now? (y/n): ").lower()
            if add_more == 'y':
                while accounts_available < accounts_needed:
                    if add_new_account() >= 0:
                        accounts_available += 1
                    else:
                        break

                    print(f"Accounts available: {accounts_available}/{accounts_needed}")
                    if accounts_available < accounts_needed:
                        more = input("Add another account? (y/n): ").lower()
                        if more != 'y':
                            break

        # Extract active members from source group using multiple accounts
        print(f"\n{Fore.CYAN}Extracting active members from source group...{Style.RESET_ALL}")
        active_participants = await fetch_active_members_with_accounts(source_group, member_limit, progress_display)

        if not active_participants:
            print(f"{Fore.RED}No active members found!{Style.RESET_ALL}")
            return

        print(f"\n{Fore.GREEN}{len(active_participants)} active members extracted.{Style.RESET_ALL}")

        # Display extracted member information
        print(f"\n{Fore.CYAN}List of selected members for transfer:{Style.RESET_ALL}")
        for i, (user, user_info) in enumerate(active_participants[:10], 1):
            print(f"{i}. {user_info}")

        if len(active_participants) > 10:
            print(f"... and {len(active_participants) - 10} more members")

        # Final confirmation
        confirm = input(f"\n{Fore.YELLOW}Do you want to add these members to the target group? (y/n): {Style.RESET_ALL}").strip().lower()
        if confirm != 'y':
            print(f"{Fore.RED}Operation cancelled.{Style.RESET_ALL}")
            return

        # Create Queue to manage adding users
        user_queue = Queue()
        for user, user_info in active_participants:
            user_queue.put((user.id, user_info))

        # Start adding members using multiple accounts
        print(f"\n{Fore.GREEN}Adding active members to target group...{Style.RESET_ALL}")
        success_count, processed_count = await process_queue_with_accounts(user_queue, target_group, progress_display)

        print(f"\n\n{Fore.GREEN}Member transfer operation completed.{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Total: {processed_count} - Success: {success_count} - Failed: {processed_count - success_count}{Style.RESET_ALL}")

        # Mark session as completed
        if current_session:
            current_session["completed"] = True
            current_session["end_time"] = datetime.now().isoformat()
            current_session["summary"] = {
                "total_processed": processed_count,
                "success_count": success_count,
                "source_group": source_group.title,
                "target_group": target_group.title
            }
            save_session()

        # Save training data
        save_ai_training_data(force=True)

        # Generate and display report
        report_file = generate_session_report()
        print(f"\n{Fore.YELLOW}Session report saved to {report_file}.{Style.RESET_ALL}")

        # Show account status after operation
        list_accounts()

    except Exception as e:
        print(f"\n{Fore.RED}Error during member transfer: {e}{Style.RESET_ALL}")
        logger.error(f"Error during member transfer: {e}")
        logger.debug(traceback.format_exc())

def analyze_collected_data():
    """Analyze collected data for insights"""
    try:
        # Load data from file
        if not os.path.exists(AI_DATA_FILE):
            logger.warning("No AI training data file found for analysis")
            return {
                "success_rate": 0,
                "avg_delay": DEFAULT_DELAY,
                "best_hours": [12, 18, 20],
                "total_attempts": 0
            }

        with open(AI_DATA_FILE, "r") as file:
            data = json.load(file)

        if not data:
            logger.warning("AI training data is empty")
            return {
                "success_rate": 0,
                "avg_delay": DEFAULT_DELAY,
                "best_hours": [12, 18, 20],
                "total_attempts": 0
            }

        # Calculate success rate
        success_count = sum(1 for a in data if a.get("result", {}).get("success", False))
        success_rate = success_count / len(data) if data else 0

        # Calculate average delay
        delays = [a.get("features", {}).get("current_delay", DEFAULT_DELAY) for a in data]
        avg_delay = sum(delays) / len(delays) if delays else DEFAULT_DELAY

        # Analyze best hours
        hours = {}
        for a in data:
            hour = a.get("features", {}).get("hour_of_day")
            success = a.get("result", {}).get("success", False)
            if hour is not None:
                if hour not in hours:
                    hours[hour] = {"total": 0, "success": 0}
                hours[hour]["total"] += 1
                if success:
                    hours[hour]["success"] += 1

        # Calculate success rate for each hour
        hour_success_rates = {}
        for hour, stats in hours.items():
            if stats["total"] >= 5:  # At least 5 attempts for meaningful data
                hour_success_rates[hour] = stats["success"] / stats["total"] if stats["total"] > 0 else 0

        # Sort hours by success rate
        sorted_hours = sorted(hour_success_rates.items(), key=lambda x: x[1], reverse=True)
        best_hours = [hour for hour, _ in sorted_hours[:3]] if sorted_hours else [12, 18, 20]

        # Analyze error types
        error_types = {}
        for a in data:
            error_type = a.get("result", {}).get("error_type")
            if error_type:
                if error_type not in error_types:
                    error_types[error_type] = 0
                error_types[error_type] += 1

        # Analyze per-account performance
        account_stats = {}
        for a in data:
            account = a.get("account_phone", "unknown")
            success = a.get("result", {}).get("success", False)

            if account not in account_stats:
                account_stats[account] = {"total": 0, "success": 0}

            account_stats[account]["total"] += 1
            if success:
                account_stats[account]["success"] += 1

        # Calculate success rate for each account
        for account in account_stats:
            stats = account_stats[account]
            stats["success_rate"] = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0

        return {
            "success_rate": success_rate * 100,
            "avg_delay": avg_delay,
            "best_hours": best_hours,
            "total_attempts": len(data),
            "error_types": error_types,
            "account_stats": account_stats
        }
    except Exception as e:
        logger.error(f"Error analyzing collected data: {e}")
        logger.debug(traceback.format_exc())
        return {
            "success_rate": 0,
            "avg_delay": DEFAULT_DELAY,
            "best_hours": [12, 18, 20],
            "total_attempts": 0
        }

def generate_session_report():
    """Generate session report"""
    analysis = analyze_collected_data()

    report = f"""
=============================================================
               Multi-Account Member Transfer Report
=============================================================
Report Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

General Statistics:
---------
Total Attempts: {analysis['total_attempts']}
Success Rate: {analysis['success_rate']:.2f}%
Average Delay: {analysis['avg_delay']:.2f} seconds

Best Times for Member Transfer:
----------------------------
"""

    for hour in analysis['best_hours']:
        hour_str = f"{hour}:00 - {hour+1}:00"
        report += f"  • {hour_str}\n"

    if 'error_types' in analysis and analysis['error_types']:
        report += "\nEncountered Error Types:\n-------------------------\n"
        for error_type, count in analysis['error_types'].items():
            report += f"  • {error_type}: {count} times\n"

    if 'account_stats' in analysis and analysis['account_stats']:
        report += "\nAccount Performance:\n-------------------------\n"
        for account, stats in analysis['account_stats'].items():
            if stats["total"] > 5:  # Only show accounts with sufficient data
                report += f"  • {account}: {stats['success_rate']:.1f}% success rate ({stats['success']}/{stats['total']})\n"

    report += """
Recommendations:
-----------------------
"""

    if analysis['success_rate'] < 50:
        report += "  • Increase delay between requests\n"
    elif analysis['success_rate'] > 90 and analysis['avg_delay'] > DEFAULT_DELAY * 1.5:
        report += "  • You can slightly reduce delay between requests\n"
    else:
        report += f"  • Maintain current delay ({analysis['avg_delay']:.2f} seconds)\n"

    report += f"  • Try to transfer members during hours {', '.join(str(h) for h in analysis['best_hours'])}\n"

    if 'error_types' in analysis and 'PeerFloodError' in analysis['error_types'] and analysis['error_types']['PeerFloodError'] > 5:
        report += "  • Add more accounts to distribute the workload\n"

    report += """
=============================================================
    """

    logger.info(report)

    # Save report to file
    report_file = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"Report saved to {report_file}")
        return report_file
    except Exception as e:
        logger.error(f"Error saving report: {e}")

    return report

# Run script
if __name__ == "__main__":
    asyncio.run(main())