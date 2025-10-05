from telethon import TelegramClient, events
import asyncio, re

# === CONFIG ===
API_ID = 29680263                # তোমার API ID
API_HASH = "a251c8203284c9fe7812f418ec8aa3a9" # তোমার API HASH
SOURCE_CHANNEL = -1002042542257 # ALPHA PREMIUM
TARGET_CHANNEL = -1002110340097 # তোমার চ্যানেল

# === CLIENT ===
client = TelegramClient("user_session", API_ID, API_HASH)

# === AUTO-REPLY MESSAGE ===
AUTO_REPLY = "Hi! I’m currently busy. Please leave your important messages here, and I’ll get back to you when I’m free."

# === TEXT CLEANER ===
def clean_text(text: str) -> str:
    if not text:
        return text
    # সব mention কে @professor_cry বানাও
    text = re.sub(r"@\w+", "@professor_cry", text)
    # ALPHA → WHALE
    text = re.sub(r"ALPHA", "WHALE", text, flags=re.IGNORECASE)
    return text.strip()

# === COPY FUNCTION ===
async def copy_post(msg):
    try:
        # শুধু ভয়েস/ভয়েস নোট skip
        if msg.voice:
            print(f"⚠️ Skipped voice message {msg.id}")
            return

        caption = clean_text(msg.text or msg.caption or "")

        if msg.photo:
            file = await msg.download_media(file=bytes)
            await client.send_file(TARGET_CHANNEL, file=file, caption=caption)
        elif msg.video:
            file = await msg.download_media(file=bytes)
            await client.send_file(TARGET_CHANNEL, file=file, caption=caption)
        elif msg.document:
            file = await msg.download_media(file=bytes)
            await client.send_file(TARGET_CHANNEL, file=file, caption=caption)
        elif msg.text:
            await client.send_message(TARGET_CHANNEL, caption)
        else:
            print(f"⚠️ Unsupported message type, skipped {msg.id}")
            return

        print(f"✅ Sent message {msg.id}")

    except Exception as e:
        print(f"❌ Error sending {msg.id}: {e}")

# === OLD MESSAGES ===
async def send_old():
    print("📥 Sending last 10 messages...")
    async for msg in client.iter_messages(SOURCE_CHANNEL, limit=10, reverse=True):
        await copy_post(msg)
    print("✅ Old messages sent.\n🚀 Listening for new ones...")

# === LISTENER FOR NEW MESSAGES IN CHANNEL ===
@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def new_signal(event):
    await copy_post(event.message)

# === AUTO-REPLY FOR INCOMING PRIVATE MESSAGES ===
@client.on(events.NewMessage(incoming=True))
async def auto_reply(event):
    if event.is_private:
        await event.respond(AUTO_REPLY)
        print(f"✅ Auto-replied to {event.sender_id}")

# === MAIN ===
async def main():
    await client.start()
    me = await client.get_me()
    print(f"👤 Logged in as: {me.first_name}")
    await send_old()
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
