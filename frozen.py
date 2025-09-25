import asyncio
import json
import os
import csv
from telethon import TelegramClient, events, errors
from asyncio import Semaphore
import random

# ========== CONFIG ==========
BOT_TOKEN = 'YOUR_BOT_TOKEN'
ADMIN_ID = 6577308099
TEMP_FOLDER = 'temp_sessions'
os.makedirs(TEMP_FOLDER, exist_ok=True)
API_FILE = 'api_list.json'
MAX_CONCURRENT = 5  # Max concurrent account checks to avoid FloodWait

# ========== API HANDLING ==========
def load_apis():
    if not os.path.exists(API_FILE):
        return []
    with open(API_FILE, 'r') as f:
        return json.load(f)

def save_apis(api_list):
    with open(API_FILE, 'w') as f:
        json.dump(api_list, f, indent=4)

def get_next_api():
    api_list = load_apis()
    if not api_list:
        return None
    return random.choice(api_list)

def remove_api(api_id):
    api_list = load_apis()
    api_list = [a for a in api_list if a['api_id'] != api_id]
    save_apis(api_list)

# ========== CHECK ACCOUNT FUNCTION ==========
async def check_account(file_path, sem):
    async with sem:
        api = get_next_api()
        if not api:
            return (file_path, None, "NO_API")
        try:
            client = TelegramClient(file_path, api['api_id'], api['api_hash'])
            await client.start()
            me = await client.get_me()
            await client.disconnect()
            return (file_path, True, f"{me.id} | {me.username or 'No Username'}")
        except (errors.AuthKeyDuplicatedError, errors.PhoneNumberBannedError,
                errors.SessionPasswordNeededError, errors.FloodWaitError):
            # Remove API if blocked/invalid
            remove_api(api['api_id'])
            return (file_path, False, f"API_BLOCKED: {api['api_id']}")
        except Exception:
            return (file_path, False, os.path.basename(file_path))

# ========== BOT ==========
bot = TelegramClient('bot_session', 0, '').start(bot_token=BOT_TOKEN)

# ======= START COMMAND =======
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    if event.sender_id != ADMIN_ID:
        return await event.reply("You are not authorized.")
    await event.reply(
        "Welcome! Upload your season files (multiple allowed). Admin commands:\n"
        "/add_api <api_id> <api_hash>\n"
        "/remove_api <api_id>\n"
        "/list_api\n"
        "/reset_api\n"
        "/help - Show all bot guidelines and commands"
    )

# ======= HELP COMMAND =======
@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    if event.sender_id != ADMIN_ID:
        return await event.reply("You are not authorized.")

    help_text = (
        "🤖 **Bot Usage Guide & Commands**\n\n"
        "**Admin Commands:**\n"
        "/add_api <api_id> <api_hash> - Add a new Telegram API to the rotation system.\n"
        "/remove_api <api_id> - Remove an API from the rotation system.\n"
        "/list_api - List all active APIs in the bot.\n"
        "/reset_api - Reset API rotation manually.\n\n"
        "**Checking Accounts:**\n"
        "1. Upload one or multiple season (.session) files directly to the bot.\n"
        "2. The bot will check each account and determine whether it is active (non-frozen) or frozen.\n"
        "3. Progress will be displayed in real-time.\n"
        "4. At the end, a detailed report will be sent with a CSV attachment.\n\n"
        "**API Rotation:**\n"
        "- The bot automatically rotates through all available APIs.\n"
        "- If an API is blocked or invalid, it will be automatically removed and admin will be notified.\n"
        "- If all APIs are exhausted, admin will receive a notification to add new APIs.\n\n"
        "**Notes:**\n"
        "- Ensure your API_ID and API_HASH are valid.\n"
        "- You can upload multiple accounts at once for batch processing.\n"
        "- Always monitor admin notifications for API issues."
    )
    await event.reply(help_text)

# ======= ADMIN COMMANDS =======
@bot.on(events.NewMessage(pattern='/add_api'))
async def add_api(event):
    if event.sender_id != ADMIN_ID:
        return
    try:
        parts = event.raw_text.split()
        api_id = int(parts[1])
        api_hash = parts[2]
        apis = load_apis()
        apis.append({"api_id": api_id, "api_hash": api_hash})
        save_apis(apis)
        await event.reply(f"API added: {api_id}")
    except:
        await event.reply("Usage: /add_api <api_id> <api_hash>")

@bot.on(events.NewMessage(pattern='/remove_api'))
async def remove_api_cmd(event):
    if event.sender_id != ADMIN_ID:
        return
    try:
        api_id = int(event.raw_text.split()[1])
        remove_api(api_id)
        await event.reply(f"API removed: {api_id}")
    except:
        await event.reply("Usage: /remove_api <api_id>")

@bot.on(events.NewMessage(pattern='/list_api'))
async def list_api(event):
    if event.sender_id != ADMIN_ID:
        return
    apis = load_apis()
    if not apis:
        await event.reply("No APIs added.")
        return
    msg = "Active APIs:\n" + "\n".join([str(a['api_id']) for a in apis])
    await event.reply(msg)

@bot.on(events.NewMessage(pattern='/reset_api'))
async def reset_api(event):
    if event.sender_id != ADMIN_ID:
        return
    await event.reply("API rotation reset manually. (Rotation handled automatically)")

# ======= FILE UPLOAD / CHECKING =======
@bot.on(events.NewMessage)
async def handle_upload(event):
    if event.sender_id != ADMIN_ID:
        return

    if not event.message.file:
        return

    file_path = await event.message.download_media(file=TEMP_FOLDER)
    await event.reply(f"File saved: {os.path.basename(file_path)}")

    session_files = [os.path.join(TEMP_FOLDER, f) for f in os.listdir(TEMP_FOLDER) if f.endswith('.session')]
    if not session_files:
        await event.reply("No season files found.")
        return

    sem = Semaphore(MAX_CONCURRENT)
    non_frozen_accounts = []
    frozen_accounts = []
    progress_msg = await event.reply(f"Processing {len(session_files)} account(s)...")

    tasks = [check_account(f, sem) for f in session_files]
    for idx, future in enumerate(asyncio.as_completed(tasks), start=1):
        result = await future
        file_name, status, info = result

        if status is True:
            non_frozen_accounts.append(info)
        elif status is False:
            frozen_accounts.append(info)
            if "API_BLOCKED" in info:
                await bot.send_message(ADMIN_ID, f"API blocked and removed: {info}")
        elif status is None:
            await bot.send_message(ADMIN_ID, "All APIs exhausted! Please add new API.")

        await progress_msg.edit(f"Progress: {idx}/{len(session_files)} checked")

    # Final report
    report_msg = "**✅ Non-Frozen Accounts:**\n"
    report_msg += "\n".join(non_frozen_accounts) if non_frozen_accounts else "None"
    report_msg += "\n\n**❌ Frozen Accounts:**\n"
    report_msg += "\n".join(frozen_accounts) if frozen_accounts else "None"
    await event.reply(report_msg)

    # Save CSV
    csv_path = os.path.join(TEMP_FOLDER, 'account_status.csv')
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Non-Frozen Accounts'])
        for acc in non_frozen_accounts:
            writer.writerow([acc])
        writer.writerow([])
        writer.writerow(['Frozen Accounts'])
        for acc in frozen_accounts:
            writer.writerow([acc])
    await event.reply("CSV report generated.", file=csv_path)

    # Cleanup temp files
    for f in session_files:
        os.remove(f)

# ======= RUN BOT =======
print("Bot is running...")
bot.run_until_disconnected()
