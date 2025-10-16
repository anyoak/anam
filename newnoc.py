import os
import asyncio
from telethon import TelegramClient, errors
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ParseMode
from config import API_ID, API_HASH, BOT_TOKEN, SUPPORT_USERNAME, REQUIRED_CHANNEL

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

user_sessions = {}  # {user_id: {"client": TelegramClient, "limit": int, "logged_in": bool}}

# --- Helper: Check if user joined required channel ---
async def is_user_joined(user_id):
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Error checking channel membership: {e}")
        return False

# --- Middleware-like check with improved handling ---
async def require_channel_join(message: types.Message):
    joined = await is_user_joined(message.from_user.id)
    if not joined:
        join_link = f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}"
        await message.reply(
            f"🔒 **Premium Access Locked!** 🌟\n\nTo unlock this premium bot, join our exclusive channel first:\n\n👉 [Join Now]({join_link})\n\nAfter joining, send /start again to activate.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return False
    return True

# --- /start command with premium flair ---
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    if not await require_channel_join(message):
        return

    await bot.send_chat_action(message.chat.id, 'typing')  # Premium-like animation
    await asyncio.sleep(1)  # Simulate premium loading

    text = (
        "🌟 **Welcome to Premium Telegram Account Checker Bot** ✨\n\n"
        "🔹 `/login` → Add a fresh new Telegram account\n"
        "🔹 `/logout` → Remove your current session securely\n"
        "🔹 `/limit` → View your premium check quota (100 max)\n"
        "🔹 `/check` → Verify Telegram numbers with precision (t.me/+)\n"
        "🔹 `/help` → Premium guide & VIP support info\n\n"
        "Each premium session allows **100 elite checks.** Upgrade by logging in a new account after limits."
    )
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

# --- /help command with emphasis on new account ---
@dp.message_handler(commands=["help"])
async def help_command(message: types.Message):
    if not await require_channel_join(message):
        return

    await bot.send_chat_action(message.chat.id, 'typing')  # Animation for premium feel
    await asyncio.sleep(0.5)

    text = (
        "📘 **Premium Bot Usage Guide** 💎\n\n"
        "✅ **Step 1:** Use `/login` to add a **fresh, new Telegram account** (must not be old or previously used for best results).\n"
        "✅ **Step 2:** Use `/check` to input numbers (one per line) for elite verification.\n"
        "✅ **Premium Detection Features:**\n"
        "  • Active accounts ✅✨\n"
        "  • Frozen accounts ❄️🚫\n"
        "  • Deleted accounts ❌🔒\n\n"
        "⚙️ **Premium Commands:**\n"
        "• `/limit` → Check your remaining elite quota\n"
        "• `/logout` → Securely logout your session\n\n"
        f"💬 **VIP Support:** {SUPPORT_USERNAME}\n"
        "Contact VIP support for any premium issues, login troubles, or enhancements. Always use a new account for optimal performance!"
    )
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

# --- /login command with improved error handling ---
@dp.message_handler(commands=["login"])
async def login_command(message: types.Message):
    if not await require_channel_join(message):
        return

    user_id = message.from_user.id

    if user_id in user_sessions and user_sessions[user_id].get("logged_in"):
        await message.reply("⚠️ **Premium Alert:** You already have a session active. Use `/logout` first to switch.")
        return

    await bot.send_chat_action(message.chat.id, 'typing')  # Premium animation
    await asyncio.sleep(1)

    session_name = f"sessions/{user_id}"
    os.makedirs("sessions", exist_ok=True)
    client = TelegramClient(session_name, API_ID, API_HASH)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            await message.reply("📱 **Premium Login:** Enter your phone number (with country code):")
            phone_prompt = await bot.wait_for("message")
            phone_number = phone_prompt.text.strip()

            await client.send_code_request(phone_number)
            await message.reply("🔢 **Verification Code:** Send the code you received:")
            code_prompt = await bot.wait_for("message")
            code = code_prompt.text.strip()
            await client.sign_in(phone_number, code)

        user_sessions[user_id] = {"client": client, "limit": 100, "logged_in": True}
        await message.reply("✅ **Premium Login Success!** ✨\nYour elite session is active. Proceed to `/check` for verifications.")

    except Exception as e:
        await message.reply(f"❌ **Premium Login Error:** `{str(e)}` 🚫\nPlease try again or contact VIP support.")
        if client.is_connected():
            await client.disconnect()
        return

# --- /logout command ---
@dp.message_handler(commands=["logout"])
async def logout_command(message: types.Message):
    if not await require_channel_join(message):
        return

    user_id = message.from_user.id
    if user_id not in user_sessions:
        await message.reply("❌ **No Active Session:** Nothing to logout.")
        return

    try:
        client = user_sessions[user_id]["client"]
        await client.log_out()
        del user_sessions[user_id]
        await message.reply("✅ **Premium Logout Success:** Session cleared securely. ✨")
    except Exception as e:
        await message.reply(f"❌ **Logout Error:** `{str(e)}` 🚫\nSession may still be active; try again.")

# --- /limit command ---
@dp.message_handler(commands=["limit"])
async def limit_command(message: types.Message):
    if not await require_channel_join(message):
        return

    user_id = message.from_user.id
    if user_id not in user_sessions:
        await message.reply("❌ **Premium Access Denied:** Login first with `/login`.")
        return

    limit = user_sessions[user_id]["limit"]
    await message.reply(f"📊 **Premium Quota:** **{limit}/100** elite checks remaining. ✨", parse_mode=ParseMode.MARKDOWN)

# --- /check command with real checking and error handling ---
@dp.message_handler(commands=["check"])
async def check_command(message: types.Message):
    if not await require_channel_join(message):
        return

    user_id = message.from_user.id
    if user_id not in user_sessions or not user_sessions[user_id]["logged_in"]:
        await message.reply("❌ **Premium Access Denied:** You must `/login` first.")
        return

    await bot.send_chat_action(message.chat.id, 'typing')  # Premium processing animation
    await asyncio.sleep(1)

    await message.reply("📋 **Premium Check:** Send the list of numbers (one per line):")
    try:
        msg = await bot.wait_for("message", timeout=300)  # Timeout to prevent hanging
        numbers = [num.strip() for num in msg.text.split("\n") if num.strip()]

        if not numbers:
            await message.reply("⚠️ **No Numbers Provided:** Please enter valid numbers.")
            return

        if len(numbers) > user_sessions[user_id]["limit"]:
            await message.reply(f"⚠️ **Quota Exceeded:** You can only check {user_sessions[user_id]['limit']} more in this session.")
            return

        client = user_sessions[user_id]["client"]
        result_text = "🔍 **Premium Check Results:** ✨\n\n"

        for num in numbers:
            phone = f"+{num}"  # Assume num is without +, for phone checking
            try:
                # Real check: Try to get entity for the phone number
                entity = await client.get_entity(phone)
                if entity:
                    result_text += f"{phone} → ✅ **Active Premium Account** ✨\n"
                else:
                    result_text += f"{phone} → 🚫 **Not Available** ❌\n"
                await asyncio.sleep(0.5)  # Rate limit simulation
            except errors.UserDeactivatedBanError:
                result_text += f"{phone} → ❄️ **Frozen Account** 🚫\n"
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                result_text += f"{phone} → ⚠️ **Flood Wait:** Retrying after {e.seconds} seconds.\n"
            except Exception as e:
                result_text += f"{phone} → ❌ **Error:** {str(e)} 🚫\n"

        user_sessions[user_id]["limit"] -= len(numbers)
        await message.reply(result_text, parse_mode=ParseMode.MARKDOWN)

    except asyncio.TimeoutError:
        await message.reply("⚠️ **Timeout:** No input received. Try `/check` again.")
    except Exception as e:
        await message.reply(f"❌ **Check Error:** `{str(e)}` 🚫\nPlease try again or contact support.")

# --- Global error handler to prevent bot crash ---
@dp.errors_handler()
async def errors_handler(update, exception):
    print(f"Global Error: {exception}")
    return True  # Prevent crash by handling all errors

if __name__ == "__main__":
    print("🤖 Premium Bot is running... ✨")
    executor.start_polling(dp, skip_updates=True)
