import time
import re
import requests
import json
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import phonenumbers
from phonenumbers import geocoder, carrier, timezone
import pycountry

# Configuration
BOT_TOKEN = "8371638048:AAEHGvy-vYHmUFPXslg-2toZgOA_14osM9k"
CHAT_IDS = ["-1002287664519", "-1003294791664", "-1002776098360"]
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

def extract_sms(driver):
    """Extract SMS messages from the website with automatic refresh"""
    global last_messages
    
    try:
        # Refresh the page to get latest messages
        driver.refresh()
        print("[🔄] Page refreshed")
        
        # Wait for page to load
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

        new_messages_found = False
        
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
            new_messages_found = True
            
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

        if not new_messages_found:
            print("[⏳] No new messages found")

    except Exception as e:
        print(f"[❌] Failed to extract SMS: {e}")

def wait_for_login(driver, timeout=180):
    """Wait for manual login with improved detection"""
    print("[*] Waiting for manual login...")
    print("[ℹ️] Please login manually in the browser window")
    
    start = time.time()
    last_url = driver.current_url
    
    while time.time() - start < timeout:
        try:
            current_url = driver.current_url
            
            # Check if URL changed (indicating successful login redirect)
            if current_url != last_url and "login" not in current_url.lower():
                print("[✅] Login detected via URL change!")
                return True
            
            # Check for logout button or successful login indicators
            page_text = driver.page_source.lower()
            if any(indicator in page_text for indicator in ["logout", "log out", "dashboard", "welcome", "main"]):
                print("[✅] Login successful!")
                return True
                
            # Check if we're still on login page
            if "login" in current_url.lower():
                print(f"[⏳] Still on login page... {int(timeout - (time.time() - start))}s remaining")
            else:
                print(f"[✅] Redirected from login page!")
                return True
                
            last_url = current_url
            time.sleep(3)
            
        except Exception as e:
            print(f"[⚠️] Page check failed: {e}")
            time.sleep(3)
    
    print("[❌] Login timeout!")
    return False

def launch_browser():
    """Setup Chrome driver with options"""
    print("[*] Launching Chrome browser...")

    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Uncomment below line to run in headless mode
    # chrome_options.add_argument("--headless=new")

    service = Service()  # You can specify executable_path if needed
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def main():
    driver = launch_browser()
    
    try:
        print(f"[🚀] Starting SMS Monitor for {SMS_URL}")
        driver.get(LOGIN_URL)
        
        if not wait_for_login(driver):
            print("[❌] Login failed. Exiting...")
            driver.quit()
            return

        print("[✅] Login successful! Starting OTP monitoring...")
        print(f"[📢] Broadcasting to {len(CHAT_IDS)} groups")
        
        # Navigate to SMS page after login
        driver.get(SMS_URL)
        time.sleep(3)
        
        monitor_count = 0
        try:
            while True:
                monitor_count += 1
                print(f"\n[🔄] Monitoring cycle #{monitor_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                extract_sms(driver)
                time.sleep(5)  # Wait 5 seconds between checks
                
        except KeyboardInterrupt:
            print("\n[🛑] Monitoring stopped by user")
            
    except Exception as e:
        print(f"[❌] Critical error: {e}")
    finally:
        print("[*] Closing browser...")
        driver.quit()
        print("[✅] Browser closed successfully")

if __name__ == "__main__":
    main()
