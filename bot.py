import os
import requests
import re
import json
import time
import threading
from datetime import datetime, timedelta

# ================== CONFIG ==================
api_key = os.environ["API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = "-1004469160922"
ADMIN_ID = 8136997138          # ← এখানে তোমার টেলিগ্রাম ইউজার আইডি দাও

OTP_GROUP_LINK = "https://t.me/+your_otp_group_link"
CHANNEL_LINK = "https://t.me/Global_Method_Channel"

url = "https://redxsms.com/api/v1/iprn/messages"
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

NUMBERS_FILE = "numbers.json"
ASSIGNED_FILE = "assigned.json"
PROCESSED_IDS_FILE = "processed_ids.txt"

# ================== STORAGE ==================
def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def load_numbers():
    return load_json(NUMBERS_FILE, {"telegram": [], "whatsapp": [], "tiktok": [], "facebook": []})

def save_numbers(data):
    save_json(NUMBERS_FILE, data)

def load_assigned():
    return load_json(ASSIGNED_FILE, {})

def save_assigned(data):
    save_json(ASSIGNED_FILE, data)

def load_processed():
    if os.path.exists(PROCESSED_IDS_FILE):
        with open(PROCESSED_IDS_FILE) as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed(msg_id):
    with open(PROCESSED_IDS_FILE, "a") as f:
        f.write(str(msg_id) + "\n")

# ================== HELPERS ==================
def get_country_info(number):
    data = {
        "93": ("🇦🇫", "AF"), "355": ("🇦🇱", "AL"), "213": ("🇩🇿", "DZ"), "880": ("🇧🇩", "BD"),
        "1": ("🇺🇸", "US"), "44": ("🇬🇧", "GB"), "91": ("🇮🇳", "IN"), "62": ("🇮🇩", "ID"),
        "86": ("🇨🇳", "CN"), "81": ("🇯🇵", "JP"), "82": ("🇰🇷", "KR"), "66": ("🇹🇭", "TH"),
        "84": ("🇻🇳", "VN"), "63": ("🇵🇭", "PH"), "60": ("🇲🇾", "MY"), "65": ("🇸🇬", "SG"),
        "971": ("🇦🇪", "AE"), "966": ("🇸🇦", "SA"), "92": ("🇵🇰", "PK"), "977": ("🇳🇵", "NP"),
        "94": ("🇱🇰", "LK"), "95": ("🇲🇲", "MM"), "855": ("🇰🇭", "KH"), "856": ("🇱🇦", "LA"),
        "47": ("🇳🇴", "NO"), "46": ("🇸🇪", "SE"), "45": ("🇩🇰", "DK"), "49": ("🇩🇪", "DE"),
        "33": ("🇫🇷", "FR"), "39": ("🇮🇹", "IT"), "34": ("🇪🇸", "ES"), "7": ("🇷🇺", "RU"),
        "380": ("🇺🇦", "UA"), "48": ("🇵🇱", "PL"), "90": ("🇹🇷", "TR"), "20": ("🇪🇬", "EG"),
        "27": ("🇿🇦", "ZA"), "234": ("🇳🇬", "NG"), "254": ("🇰🇪", "KE"), "233": ("🇬🇭", "GH"),
        "55": ("🇧🇷", "BR"), "54": ("🇦🇷", "AR"), "52": ("🇲🇽", "MX"), "57": ("🇨🇴", "CO"),
        "51": ("🇵🇪", "PE"), "56": ("🇨🇱", "CL"), "58": ("🇻🇪", "VE")
    }
    for code in sorted(data.keys(), key=len, reverse=True):
        if number.startswith(code):
            return data[code]
    return ("🌐", "UN")

def mask_number(number):
    if len(number) <= 8:
        return number
    return number[:2] + "••••" + number[-4:]

def get_service_info(item, message_text):
    name = ""
    for key in ['service', 'app', 'service_name', 'name', 'title', 'gateway']:
        if key in item and item[key]:
            val = str(item[key]).strip().lower()
            if val and val != "none":
                name = val
                break
    text = (message_text or "").upper()
    if not name:
        if "TELEGRAM" in text: name = "telegram"
        elif "WHATSAPP" in text: name = "whatsapp"
        elif "TIKTOK" in text: name = "tiktok"
        elif "FACEBOOK" in text: name = "facebook"
        elif "GOOGLE" in text: name = "google"
        elif "IMO" in text: name = "imo"

    if "telegram" in name: return "✈️", "TG"
    if "whatsapp" in name: return "💬", "WA"
    if "tiktok" in name: return "🎵", "TT"
    if "facebook" in name: return "📘", "FB"
    if "google" in name: return "🌐", "GG"
    if "imo" in name: return "💜", "IMO"
    return "💬", "SV"

# ================== TELEGRAM SEND ==================
def tg_api(method, payload):
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload, timeout=15)
        return r.json()
    except Exception as e:
        print("TG Error:", e)
        return {}

def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    return tg_api("sendMessage", payload)

def answer_callback(callback_id, text=None):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    tg_api("answerCallbackQuery", payload)

# ================== NUMBER SYSTEM ==================
def get_available_numbers(platform, count=5):
    numbers = load_numbers()
    assigned = load_assigned()
    now = time.time()

    # expire old assignments
    for uid, info in list(assigned.items()):
        if info.get("expire", 0) < now:
            del assigned[uid]
    save_assigned(assigned)

    used = set()
    for info in assigned.values():
        used.update(info.get("numbers", []))

    available = [n for n in numbers.get(platform, []) if n not in used]
    return available[:count]

def assign_numbers(user_id, platform, nums):
    assigned = load_assigned()
    assigned[str(user_id)] = {
        "platform": platform,
        "numbers": nums,
        "expire": time.time() + 300   # 5 minutes
    }
    save_assigned(assigned)

def release_user_numbers(user_id):
    assigned = load_assigned()
    if str(user_id) in assigned:
        del assigned[str(user_id)]
        save_assigned(assigned)

# ================== OTP FORWARDER ==================
def process_otp(item, processed):
    msg_id = str(item.get("id", item.get("received_at", "")))
    if not msg_id or msg_id in processed:
        return False

    raw_number = str(item.get("number", "")).strip()
    msg_body = item.get("message", "") or ""

    flag, country_code = get_country_info(raw_number)
    service_emoji, service_short = get_service_info(item, msg_body)
    masked = mask_number(raw_number)

    otp_match = re.search(r'\b\d{3}[-\s]?\d{3}\b|\b\d{4,8}\b', msg_body)
    otp_code = otp_match.group(0).replace("-", "").replace(" ", "") if otp_match else "N/A"

    header = f"{flag} <b>{country_code}</b> | {service_emoji} <code>+{masked}</code>"

    # Group message
    keyboard = {
        "inline_keyboard": [
            [{"text": f"🔑 📋 {otp_code}", "copy_text": {"text": otp_code}}],
            [
                {"text": "📢 Main Channel", "url": CHANNEL_LINK},
                {"text": "📞 Number Channel", "url": "https://t.me/Heueururuhhd_bot"}
            ]
        ]
    }
    send_message(CHAT_ID, header, keyboard)
    save_processed(msg_id)

    # Private to user if assigned
    assigned = load_assigned()
    for uid, info in assigned.items():
        if raw_number in info.get("numbers", []):
            private_text = f"🔔 <b>Your OTP Received!</b>\n\n{header}\n\n🔑 OTP: <code>{otp_code}</code>"
            send_message(int(uid), private_text)
            print(f"→ Also sent privately to user {uid}")

    print(f"✅ OTP sent → {otp_code}")
    return True

def check_otps():
    try:
        r = requests.get(url, headers=headers, params={"per_page": 20}, timeout=12)
        data = r.json().get("data", [])
        processed = load_processed()
        for item in data:
            process_otp(item, processed)
    except Exception as e:
        print("OTP check error:", e)

# ================== BOT HANDLERS ==================
def handle_message(msg):
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text = (msg.get("text") or "").strip().lower()

    # Admin upload
    if user_id == ADMIN_ID and msg.get("document"):
        # simple txt support
        file_id = msg["document"]["file_id"]
        file_info = tg_api("getFile", {"file_id": file_id})
        if file_info.get("ok"):
            file_path = file_info["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            content = requests.get(file_url).text
            nums = [line.strip() for line in content.splitlines() if line.strip().isdigit()]
            # for now put in telegram (you can improve)
            numbers = load_numbers()
            numbers["telegram"].extend(nums)
            numbers["telegram"] = list(set(numbers["telegram"]))
            save_numbers(numbers)
            send_message(chat_id, f"✅ {len(nums)} numbers added to Telegram pool")
        return

    if text in ["get number", "getnumber", "/start", "number"]:
        keyboard = {
            "inline_keyboard": [
                [{"text": "✈️ Telegram", "callback_data": "plat_telegram"},
                 {"text": "💬 WhatsApp", "callback_data": "plat_whatsapp"}],
                [{"text": "🎵 TikTok", "callback_data": "plat_tiktok"},
                 {"text": "📘 Facebook", "callback_data": "plat_facebook"}]
            ]
        }
        send_message(chat_id, "📱 <b>Select your Platform</b>", keyboard)
        return

    if text == "/admin" and user_id == ADMIN_ID:
        keyboard = {
            "inline_keyboard": [
                [{"text": "✈️ Telegram", "callback_data": "admin_telegram"},
                 {"text": "💬 WhatsApp", "callback_data": "admin_whatsapp"}],
                [{"text": "🎵 TikTok", "callback_data": "admin_tiktok"},
                 {"text": "📘 Facebook", "callback_data": "admin_facebook"}]
            ]
        }
        send_message(chat_id, "🔧 Admin Panel\nSelect platform to upload numbers:", keyboard)
        return

def handle_callback(cq):
    data = cq["data"]
    chat_id = cq["message"]["chat"]["id"]
    user_id = cq["from"]["id"]
    callback_id = cq["id"]

    answer_callback(callback_id)

    if data.startswith("plat_"):
        platform = data.replace("plat_", "")
        nums = get_available_numbers(platform, 5)
        if not nums:
            send_message(chat_id, "❌ No numbers available for this platform right now.")
            return

        assign_numbers(user_id, platform, nums)

        text = f"✅ <b>Your 5 Numbers ({platform.upper()})</b>\n\n"
        for i, n in enumerate(nums, 1):
            text += f"{i}. <code>+{n}</code>\n"
        text += "\n⏳ Numbers locked for 5 minutes"

        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 OTP Group", "url": OTP_GROUP_LINK},
                 {"text": "📣 Channels", "url": CHANNEL_LINK}],
                [{"text": "🔄 Change Number", "callback_data": f"change_{platform}"},
                 {"text": "🌍 Change Country", "callback_data": "change_country"}]
            ]
        }
        send_message(chat_id, text, keyboard)
        return

    if data.startswith("change_"):
        platform = data.replace("change_", "")
        release_user_numbers(user_id)
        nums = get_available_numbers(platform, 5)
        if not nums:
            send_message(chat_id, "❌ No more numbers available.")
            return
        assign_numbers(user_id, platform, nums)
        text = f"🔄 <b>New 5 Numbers</b>\n\n"
        for i, n in enumerate(nums, 1):
            text += f"{i}. <code>+{n}</code>\n"
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 OTP Group", "url": OTP_GROUP_LINK},
                 {"text": "📣 Channels", "url": CHANNEL_LINK}],
                [{"text": "🔄 Change Number", "callback_data": f"change_{platform}"},
                 {"text": "🌍 Change Country", "callback_data": "change_country"}]
            ]
        }
        send_message(chat_id, text, keyboard)
        return

    if data.startswith("admin_") and user_id == ADMIN_ID:
        platform = data.replace("admin_", "")
        send_message(chat_id, f"📤 Now send a <b>.txt</b> file with numbers (one number per line) for <b>{platform}</b>")
        # You can store pending platform in a temp dict if needed
        return

# ================== MAIN LOOP ==================
def telegram_polling():
    offset = 0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                             params={"offset": offset, "timeout": 30}, timeout=35)
            data = r.json()
            if data.get("ok"):
                for update in data["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update:
                        handle_message(update["message"])
                    elif "callback_query" in update:
                        handle_callback(update["callback_query"])
        except Exception as e:
            print("Polling error:", e)
            time.sleep(3)

def otp_loop():
    while True:
        check_otps()
        time.sleep(4)

if __name__ == "__main__":
    print("🚀 Full Featured Bot Starting...")
    # clear processed on start if you want
    # if os.path.exists(PROCESSED_IDS_FILE): os.remove(PROCESSED_IDS_FILE)

    t1 = threading.Thread(target=telegram_polling, daemon=True)
    t2 = threading.Thread(target=otp_loop, daemon=True)
    t1.start()
    t2.start()

    print("✅ Bot is running...")
    while True:
        time.sleep(60)
