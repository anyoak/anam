import time
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import phonenumbers
from phonenumbers import geocoder, region_code_for_number
import pycountry
import html

import config  # BOT_TOKEN, CHAT_ID, SMS_URL

# Cache for sent messages
last_messages = set()


def mask_number(number: str) -> str:
    """Mask phone number middle 3 digits"""
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:4] + "***" + digits[-3:]
    return number


def country_to_flag(country_code: str) -> str:
    """Convert ISO country code to emoji flag"""
    if not country_code or len(country_code) != 2:
        return "🏳️"
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())


def detect_country(number: str):
    """Detect country name + flag from number"""
    try:
        parsed_number = phonenumbers.parse("+" + number, None)
        region = region_code_for_number(parsed_number)
        country = pycountry.countries.get(alpha_2=region)
        if country:
            return country.name, country_to_flag(region)
    except:
        pass
    return "Unknown", "🏳️"


def extract_otp(message: str) -> str:
    """Extract OTP code from message with improved pattern matching"""
    # First try to find WhatsApp-style codes (3 digits - 3 digits)
    whatsapp_patterns = [
        r'\b\d{3}-\d{3}\b',  # 111-111 format
        r'\b\d{3} \d{3}\b',  # 111 111 format
        r'\b\d{6}\b',        # 111111 format
    ]
    
    for pattern in whatsapp_patterns:
        match = re.search(pattern, message)
        if match:
            # Remove any non-digit characters for consistent formatting
            return re.sub(r'\D', '', match.group(0))
    
    # Then try to find other common OTP patterns
    common_patterns = [
        r'\b\d{4}\b',  # 4-digit codes
        r'\b\d{5}\b',  # 5-digit codes
        r'\b\d{6}\b',  # 6-digit codes
        r'\b\d{7}\b',  # 7-digit codes
        r'\b\d{8}\b',  # 8-digit codes
    ]
    
    for pattern in common_patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(0)
    
    return "N/A"


def send_to_telegram(text: str):
    """Send message with inline buttons"""
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🤖 Developer", "url": "https://t.me/professor_cry"}
            ],
            [
                {"text": "🔗 Main Channel", "url": "https://t.me/mailtwist"}
            ]
        ]
    }

    payload = {
        "chat_id": config.CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": keyboard,
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print("[✅] Telegram message sent.")
        else:
            print(f"[❌] Failed: {res.status_code} - {res.text}")
    except requests.exceptions.RequestException as e:
        print(f"[❌] Telegram request error: {e}")


def extract_sms(driver):
    global last_messages
    try:
        driver.get(config.SMS_URL)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        headers = soup.find_all("th")

        number_idx = service_idx = sms_idx = None
        for idx, th in enumerate(headers):
            label = th.get("aria-label", "").lower()
            if "number" in label:
                number_idx = idx
            elif "cli" in label or "service" in label:
                service_idx = idx
            elif "sms" in label:
                sms_idx = idx

        if None in (number_idx, service_idx, sms_idx):
            print("[⚠️] Could not detect all required columns.")
            return

        rows = soup.find_all("tr")[1:]  # skip header row
        for row in rows:
            cols = row.find_all("td")
            if len(cols) <= max(number_idx, service_idx, sms_idx):
                continue

            number = cols[number_idx].get_text(strip=True) or "Unknown"
            service = cols[service_idx].get_text(strip=True) or "Unknown"
            message = cols[sms_idx].get_text(strip=True)

            if not message or message in last_messages:
                continue
            if message.strip() in ("0", "Unknown") or (
                number in ("0", "Unknown") and service in ("0", "Unknown")
            ):
                continue

            last_messages.add(message)
            timestamp = datetime.utcnow() + timedelta(hours=6)  # Dhaka time

            otp_code = extract_otp(message)
            country_name, country_flag = detect_country(number)
            masked_number = mask_number(number)

            # HTML formatted message with monospace for OTP and all text bold
            formatted = (
                f"<b>{country_flag} {country_name} {service} OTP Code Received! 🎉</b>\n"
                f"<b>━━━━━━━━━━━━━━</b>\n"
                f"<b>📞 Number: {masked_number}</b>\n"
                f"<b>⚙️ Service: {service}</b>\n"
                f"<b>🌍 Country: {country_flag} {country_name}</b>\n"
                f"<b>⏳ Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
                f"<b>🔐 OTP: <code>{otp_code}</code></b>\n"
                f"<b>━━━━━━━━━━━━━━</b>\n"
                f"<b>💬 Full Message:</b>\n"
                f"<code>{html.escape(message.strip())}</code>"
            )

            send_to_telegram(formatted)

    except Exception as e:
        print(f"[ERR] Failed to extract SMS: {e}")


if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    # chrome_options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        print("[*] SMS Extractor running. Press Ctrl+C to stop.")
        while True:
            extract_sms(driver)
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n[🛑] Stopped by user.")
    finally:
        driver.quit()
        print("[*] Browser closed.")