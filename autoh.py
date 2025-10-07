import time
import csv
from itertools import zip_longest
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

_status = {"running": False, "processed": 0, "last": None}
_stop_flag = False  # manual stop flag

URL = "https://pack.chromaawards.com/sign-in"
LOG_PATH = Path("logs.csv")


def _now_str():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def read_lines(path):
    try:
        with open(path, "r", encoding="utf8") as f:
            return [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        return []


def append_log_row(timestamp, email, phone, status, message):
    header = ["timestamp", "email", "phone", "status", "message"]
    exists = LOG_PATH.exists()
    try:
        with open(LOG_PATH, "a", newline="", encoding="utf8") as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(header)
            writer.writerow([timestamp, email, phone, status, message])
    except Exception as e:
        print("Failed to write log:", e)


def _safe_fill(page, selector, value, timeout=3000):
    tries = 0
    while tries < 3:
        tries += 1
        try:
            page.fill(selector, value, timeout=timeout)
            return True, "filled"
        except PlaywrightTimeoutError:
            time.sleep(0.5)
        except Exception:
            try:
                el = page.locator(selector)
                el.first.fill(value, timeout=timeout)
                return True, "filled-fallback"
            except Exception:
                time.sleep(0.5)
    return False, f"could not fill selector {selector}"


def _safe_click(page, button_text, timeout=3000):
    tries = 0
    while tries < 3:
        tries += 1
        try:
            page.locator(f"button:has-text('{button_text}')").first.click(timeout=timeout)
            return True, "clicked"
        except PlaywrightTimeoutError:
            time.sleep(0.5)
        except Exception:
            try:
                btns = page.locator("button").all()
                for b in btns:
                    try:
                        b.click(timeout=1000)
                        return True, "clicked-generic"
                    except:
                        continue
            except:
                pass
            time.sleep(0.5)
    return False, f"could not click button '{button_text}'"


def _process_one(page, email, phone):
    print("Open Website...")
    try:
        page.goto(URL, wait_until="domcontentloaded", timeout=15000)
    except Exception as e:
        return False, f"goto_error:{e}"

    print(f"Enter email: {email}")
    ok, msg = _safe_fill(page, "#email", email)
    if not ok:
        return False, f"email_fill_failed:{msg}"

    ok, msg_click = _safe_click(page, "Continue")
    if not ok:
        return False, f"continue_click_failed:{msg_click}"

    time.sleep(1.2)

    print(f"Enter phone: {phone}")
    ok, msg = _safe_fill(page, "#phone", phone)
    if not ok:
        return False, f"phone_fill_failed:{msg}"

    ok, msg_click = _safe_click(page, "Send verification code")
    if not ok:
        return False, f"send_click_failed:{msg_click}"

    return True, "send_clicked"


def start_processing(emails_path, phones_path):
    global _status, _stop_flag
    _stop_flag = False
    _status = {"running": True, "processed": 0, "last": None}
    print("✅ Worker started.")

    emails = read_lines(emails_path)
    phones = read_lines(phones_path)

    if not phones:
        print("❌ phones.txt not found or empty. Stopping.")
        _status["running"] = False
        return

    pairs = list(zip_longest(emails or [], phones, fillvalue=None))
    if not emails:
        pairs = [(f"demo{idx+1}@example.com", p) for idx, (_, p) in enumerate(pairs)]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for idx, (email, phone) in enumerate(pairs, start=1):
            if _stop_flag:
                print("⛔ Stop requested. Worker stopping.")
                break

            if not phone:
                continue

            timestamp = _now_str()
            ok, msg = _process_one(page, email, phone)
            status_text = "Success" if ok else "Fail"
            _status["processed"] += 1
            _status["last"] = {"email": email, "phone": phone, "ok": ok, "msg": msg}

            append_log_row(timestamp, email, phone, status_text, msg)
            print(f"{'✅' if ok else '❌'} {status_text} | Phone: {phone} | Email: {email} | Info: {msg}")

            print("Waiting 15 sec....")
            for _ in range(15):
                if _stop_flag:
                    break
                time.sleep(1)

            try:
                page.reload(timeout=8000)
            except:
                pass

        try:
            context.close()
            browser.close()
        except:
            pass

    print("🏁 Worker finished.")
    _status["running"] = False


def get_status():
    return dict(_status)


def stop_processing():
    global _stop_flag
    _stop_flag = True


if __name__ == "__main__":
    start_processing("emails.txt", "phones.txt")
