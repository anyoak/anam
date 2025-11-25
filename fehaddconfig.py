import time
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import phonenumbers
from phonenumbers import geocoder, carrier, timezone
import pycountry
import html
import json

# Configuration
BOT_TOKEN = "8371638048:AAEHGvy-vYHmUFPXslg-2toZgOA_14osM9k"
CHAT_IDS = ["-1002287664519", "-1003294791664", "-1002776098360"]  # List of chat IDs
SMS_URL = "http://139.99.63.204/ints/agent/SMSCDRStats"
LOGIN_URL = "http://139.99.63.204/ints/login"
TIMEZONE_OFFSET = 8

# Cache for sent messages
last_messages = set()

def mask_number(number: str) -> str:
    """Mask phone number middle 3 digits"""
    digits = re.sub(r"\D", "", number)
    if len(digits) > 6:
        return digits[:5] + "***" + digits[-3:]
    return number

def country_to_flag(country_code: str) -> str:
    """Convert ISO country code to emoji flag"""
    if not country_code or len(country_code) != 2:
        return "🏳️"
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())

def detect_country(number: str):
    """Detect country name + flag from number using phonenumbers library"""
    try:
        # Parse the phone number
        parsed_number = phonenumbers.parse(number, None)
        country_code = phonenumbers.region_code_for_number(parsed_number)
        
        if country_code:
            # Get country name using pycountry
            country = pycountry.countries.get(alpha_2=country_code)
            country_name = country.name if country else "Unknown"
            country_flag = country_to_flag(country_code)
            
            return {
                'name': country_name,
                'flag': country_flag,
                'code': country_code
            }
    except Exception as e:
        print(f"Error detecting country for {number}: {e}")
    
    return {'name': 'Unknown', 'flag': '🏳️', 'code': ''}

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

def send_to_telegram(text: str, otp_code: str):
    """Send message with inline copy button to multiple groups"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # Create inline keyboard with only copy button using ⧉ icon
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": f"⧉ {otp_code}", 
                    "callback_data": f"copy_otp_{otp_code}"
                }
            ]
        ]
    }

    # Send to all chat IDs
    for chat_id in CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": json.dumps(keyboard),
        }

        try:
            res = requests.post(url, data=payload, timeout=10)
            if res.status_code == 200:
                print(f"[✅] Telegram message sent to {chat_id}.")
            else:
                print(f"[❌] Failed to send to {chat_id}: {res.status_code} - {res.text}")
        except requests.exceptions.RequestException as e:
            print(f"[❌] Telegram request error for {chat_id}: {e}")

def login_to_site(driver):
    """Login to the SMS site if required"""
    try:
        driver.get(LOGIN_URL)
        time.sleep(2)
        
        # Check if login is required by looking for login form elements
        if "login" in driver.title.lower() or driver.find_elements(By.NAME, "username"):
            print("[🔐] Login required. Please implement login logic.")
            # You'll need to add your login credentials and form submission here
            # Example:
            # username_field = driver.find_element(By.NAME, "username")
            # password_field = driver.find_element(By.NAME, "password")
            # username_field.send_keys("your_username")
            # password_field.send_keys("your_password")
            # driver.find_element(By.XPATH, "//button[@type='submit']").click()
            # time.sleep(2)
            
    except Exception as e:
        print(f"[❌] Login check failed: {e}")

def extract_sms(driver):
    global last_messages
    try:
        driver.get(SMS_URL)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Find table headers to identify columns
        headers = soup.find_all("th")
        print(f"[ℹ️] Found {len(headers)} headers")

        number_idx = service_idx = sms_idx = None
        for idx, th in enumerate(headers):
            text = th.get_text(strip=True).lower()
            aria_label = th.get("aria-label", "").lower()
            
            if "number" in text or "number" in aria_label:
                number_idx = idx
                print(f"[🔍] Number column found at index {idx}")
            elif "service" in text or "cli" in text or "service" in aria_label or "cli" in aria_label:
                service_idx = idx
                print(f"[🔍] Service column found at index {idx}")
            elif "sms" in text or "message" in text or "sms" in aria_label or "message" in aria_label:
                sms_idx = idx
                print(f"[🔍] SMS column found at index {idx}")

        if None in (number_idx, service_idx, sms_idx):
            print("[⚠️] Could not detect all required columns. Trying alternative method...")
            # Alternative: try to find by position if standard structure
            if len(headers) >= 3:
                number_idx, service_idx, sms_idx = 0, 1, 2
                print(f"[🔍] Using default indices: number={number_idx}, service={service_idx}, sms={sms_idx}")
            else:
                return

        rows = soup.find_all("tr")[1:]  # skip header row
        print(f"[ℹ️] Found {len(rows)} rows to process")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) <= max(number_idx, service_idx, sms_idx):
                continue

            number = cols[number_idx].get_text(strip=True) or "Unknown"
            service = cols[service_idx].get_text(strip=True) or "Unknown"
            message = cols[sms_idx].get_text(strip=True)

            # Skip if no message or already processed
            if not message or message in last_messages:
                continue
            if message.strip() in ("0", "Unknown") or (
                number in ("0", "Unknown") and service in ("0", "Unknown")
            ):
                continue

            # Add to cache and process
            last_messages.add(message)
            
            # Limit cache size
            if len(last_messages) > 100:
                last_messages.pop()

            otp_code = extract_otp(message)
            country_info = detect_country(number)
            masked_number = mask_number(number)

            # Format message as per requirement
            formatted = (
                f"{country_info['flag']} {country_info['name']} {service} Of {masked_number} Captured!\n"
                f"```{message.strip()}```"
            )

            if otp_code != "N/A":
                send_to_telegram(formatted, otp_code)
                print(f"[📱] New SMS captured: {country_info['name']} - {service} - OTP: {otp_code}")
            else:
                print(f"[ℹ️] SMS captured but no OTP found: {country_info['name']} - {service}")

    except Exception as e:
        print(f"[❌] Failed to extract SMS: {e}")

def setup_driver():
    """Setup Chrome driver with options"""
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--headless=new")  # Remove this line if you want to see browser
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

if __name__ == "__main__":
    driver = setup_driver()
    
    try:
        print("[🚀] SMS Extractor running. Press Ctrl+C to stop.")
        print(f"[📢] Broadcasting to {len(CHAT_IDS)} groups")
        
        # Check login first
        login_to_site(driver)
        
        while True:
            extract_sms(driver)
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n[🛑] Stopped by user.")
    finally:
        driver.quit()
        print("[✅] Browser closed.")
