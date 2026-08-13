import os
import requests
import re
import json
import time
import threading
from datetime import datetime, timezone, timedelta

api_key = os.environ["API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = "-1004469160922"

url = "https://redxsms.com/api/v1/iprn/messages"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json"
}

PROCESSED_IDS_FILE = "processed_ids.txt"
BD_TZ = timezone(timedelta(hours=6))

# ========== Custom Premium Emoji IDs ==========
# তুমি যে ID দিছো (পিক থেকে)
CUSTOM_PHONE_EMOJI_ID = "5972209358606440253"   # 📱 এর কাস্টম প্রিমিয়াম ইমোজি

# চাইলে পরে Telegram / WhatsApp এর জন্য আলাদা ID দিয়ে এখানে বসাবে
CUSTOM_TG_EMOJI_ID = None      # উদাহরণ: "1234567890123456789"
CUSTOM_WA_EMOJI_ID = None      # উদাহরণ: "9876543210987654321"

def load_processed_ids():
    if os.path.exists(PROCESSED_IDS_FILE):
        with open(PROCESSED_IDS_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_id(msg_id):
    with open(PROCESSED_IDS_FILE, "a") as f:
        f.write(str(msg_id) + "\n")

def get_country_flag(number):
    country_flags = {
        "93": "🇦🇫", "355": "🇦🇱", "213": "🇩🇿", "376": "🇦🇩", "244": "🇦🇴",
        "54": "🇦🇷", "374": "🇦🇲", "61": "🇦🇺", "43": "🇦🇹", "994": "🇦🇿",
        "973": "🇧🇭", "880": "🇧🇩", "375": "🇧🇾", "32": "🇧🇪", "501": "🇧🇿",
        "229": "🇧🇯", "975": "🇧🇹", "591": "🇧🇴", "387": "🇧🇦", "267": "🇧🇼",
        "55": "🇧🇷", "673": "🇧🇳", "359": "🇧🇬", "226": "🇧🇫", "257": "🇧🇮",
        "855": "🇰🇭", "237": "🇨🇲", "1": "🇺🇸", "238": "🇨🇻", "236": "🇨🇫",
        "235": "🇹🇩", "56": "🇨🇱", "86": "🇨🇳", "57": "🇨🇴", "269": "🇰🇲",
        "242": "🇨🇬", "243": "🇨🇩", "506": "🇨🇷", "385": "🇭🇷", "53": "🇨🇺",
        "357": "🇨🇾", "420": "🇨🇿", "45": "🇩🇰", "253": "🇩🇯", "1767": "🇩🇲",
        "1809": "🇩🇴", "593": "🇪🇨", "20": "🇪🇬", "503": "🇸🇻", "240": "🇬🇶",
        "291": "🇪🇷", "372": "🇪🇪", "251": "🇪🇹", "679": "🇫🇯", "358": "🇫🇮",
        "33": "🇫🇷", "241": "🇬🇦", "220": "🇬🇲", "995": "🇬🇪", "49": "🇩🇪",
        "233": "🇬🇭", "30": "🇬🇷", "502": "🇬🇹", "224": "🇬🇳", "245": "🇬🇼",
        "592": "🇬🇾", "509": "🇭🇹", "504": "🇭🇳", "36": "🇭🇺", "354": "🇮🇸",
        "91": "🇮🇳", "62": "🇮🇩", "98": "🇮🇷", "964": "🇮🇶", "353": "🇮🇪",
        "972": "🇮🇱", "39": "🇮🇹", "1876": "🇯🇲", "81": "🇯🇵", "962": "🇯🇴",
        "7": "🇷🇺", "254": "🇰🇪", "965": "🇰🇼", "996": "🇰🇬", "856": "🇱🇦",
        "371": "🇱🇻", "961": "🇱🇧", "266": "🇱🇸", "231": "🇱🇷", "218": "🇱🇾",
        "423": "🇱🇮", "370": "🇱🇹", "352": "🇱🇺", "261": "🇲🇬", "265": "🇲🇼",
        "60": "🇲🇾", "960": "🇲🇻", "223": "🇲🇱", "356": "🇲🇹", "52": "🇲🇽",
        "373": "🇲🇩", "377": "🇲🇨", "976": "🇲🇳", "382": "🇲🇪", "212": "🇲🇦",
        "258": "🇲🇿", "95": "🇲🇲", "264": "🇳🇦", "977": "🇳🇵", "31": "🇳🇱",
        "64": "🇳🇿", "505": "🇳🇮", "227": "🇳🇪", "234": "🇳🇬", "47": "🇳🇴",
        "968": "🇴🇲", "92": "🇵🇰", "970": "🇵🇸", "507": "🇵🇦", "675": "🇵🇬",
        "595": "🇵🇾", "51": "🇵🇪", "63": "🇵🇭", "48": "🇵🇱", "351": "🇵🇹",
        "974": "🇶🇦", "40": "🇷🇴", "250": "🇷🇼", "966": "🇸🇦", "221": "🇸🇳",
        "381": "🇷🇸", "248": "🇸🇨", "232": "🇸🇱", "65": "🇸🇬", "421": "🇸🇰",
        "386": "🇸🇮", "252": "🇸🇴", "27": "🇿🇦", "82": "🇰🇷", "34": "🇪🇸",
        "94": "🇱🇰", "249": "🇸🇩", "597": "🇸🇷", "46": "🇸🇪", "41": "🇨🇭",
        "963": "🇸🇾", "886": "🇹🇼", "992": "🇹🇯", "255": "🇹🇿", "66": "🇹🇭",
        "228": "🇹🇬", "676": "🇹🇴", "216": "🇹🇳", "90": "🇹🇷", "993": "🇹🇲",
        "256": "🇺🇬", "380": "🇺🇦", "971": "🇦🇪", "44": "🇬🇧", "598": "🇺🇾",
        "998": "🇺🇿", "58": "🇻🇪", "84": "🇻🇳", "967": "🇾🇪", "260": "🇿🇲",
        "263": "🇿🇼"
    }
    for code in sorted(country_flags.keys(), key=len, reverse=True):
        if number.startswith(code):
            return country_flags[code]
    return "🌐"

def get_service_short(item, message_text):
    name = ""
    for key in ['service', 'app', 'service_name', 'name', 'title', 'gateway']:
        if key in item and item[key]:
            val = str(item[key]).strip().lower()
            if val and val != "none":
                name = val
                break

    if not name:
        text = message_text.upper()
        if "TELEGRAM" in text: name = "telegram"
        elif "WHATSAPP" in text: name = "whatsapp"
        elif "1XBET" in text: name = "1xbet"
        elif "GOOGLE" in text: name = "google"
        elif "FACEBOOK" in text: name = "facebook"
        elif "IMO" in text: name = "imo"
        elif "VIBER" in text: name = "viber"

    if "telegram" in name:
        return "#TG", "✈️", CUSTOM_TG_EMOJI_ID
    if "whatsapp" in name:
        return "#WA", "💬", CUSTOM_WA_EMOJI_ID
    if "1xbet" in name:
        return "#1X", "🎰", None
    if "google" in name:
        return "#GG", "🌐", None
    if "facebook" in name:
        return "#FB", "📘", None
    if "imo" in name:
        return "#IMO", "💜", None
    if "viber" in name:
        return "#VB", "📳", None
    return "#SV", "💬", None

def detect_language(text):
    if re.search(r'[\u0600-\u06FF]', text): return "Arabic"
    if re.search(r'[\u4e00-\u9fff]', text): return "Chinese"
    if re.search(r'[\u0400-\u04FF]', text): return "Russian"
    if re.search(r'[\u0980-\u09FF]', text): return "Bengali"
    if re.search(r'[\u0e00-\u0e7f]', text): return "Thai"
    if re.search(r'[\u0900-\u097f]', text): return "Hindi"
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text): return "Japanese"
    if re.search(r'[\uac00-\ud7af]', text): return "Korean"
    return "English"

def delete_message_later(chat_id, message_id):
    time.sleep(180)
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                      json={"chat_id": chat_id, "message_id": message_id}, timeout=10)
    except:
        pass

def send_telegram_message(text, emoji, otp_code):
    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    inline_keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": f"{emoji} 📋 Copy OTP",
                    "copy_text": {"text": otp_code}
                }
            ],
            [
                {
                    "text": "📞 Get Number",
                    "url": "https://t.me/Heueururuhhd_bot"
                },
                {
                    "text": "📢 Main Channel",
                    "url": "https://t.me/Global_Method_Channel"
                }
            ]
        ]
    }

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",          # Custom emoji এর জন্য HTML লাগবে
        "reply_markup": json.dumps(inline_keyboard)
    }

    try:
        resp = requests.post(tg_url, json=payload, timeout=12)
        data = resp.json()
        if data.get("ok"):
            msg_id = data["result"]["message_id"]
            threading.Thread(target=delete_message_later, args=(CHAT_ID, msg_id), daemon=True).start()
            return True
        else:
            print("Telegram Error:", data)
            return False
    except Exception as e:
        print("Telegram Error:", e)
        return False

def process_message(item, processed_ids):
    msg_id = str(item.get("id", item.get("received_at", "")))
    if not msg_id or msg_id in processed_ids:
        return False

    raw_number = str(item.get("number", "")).strip()
    msg_body = item.get("message", "") or ""

    flag = get_country_flag(raw_number)
    short_code, normal_emoji, custom_service_id = get_service_short(item, msg_body)
    lang = detect_language(msg_body)

    otp_match = re.search(r'\b\d{3}[-\s]?\d{3}\b|\b\d{4,8}\b', msg_body)
    otp_code = otp_match.group(0) if otp_match else "N/A"

    # ===== Custom Premium Phone Emoji =====
    phone_emoji = f'<tg-emoji emoji-id="{CUSTOM_PHONE_EMOJI_ID}">📱</tg-emoji>'

    # যদি service এর জন্য আলাদা custom emoji থাকে তাহলে সেটা ব্যবহার করবে
    if custom_service_id:
        service_part = f'<tg-emoji emoji-id="{custom_service_id}">{normal_emoji}</tg-emoji> {short_code}'
    else:
        service_part = f"{normal_emoji} {short_code}"

    # Final header format (তোমার চাওয়া স্টাইল)
    header = f"{flag} {service_part} {phone_emoji} {raw_number}  native{lang}"

    formatted_msg = (
        f"{header}\n\n"
        f"<pre>{msg_body}</pre>\n\n"
        f"🔑 OTP : <code>{otp_code}</code>\n"
        f"⏳ Auto delete after 3 minutes"
    )

    if send_telegram_message(formatted_msg, normal_emoji, otp_code):
        save_processed_id(msg_id)
        print(f"✅ {flag} {short_code} {raw_number} | OTP: {otp_code}")
        return True
    return False

def check_messages():
    try:
        params = {'per_page': 30}
        response = requests.get(url, headers=headers, params=params, timeout=12)
        result = response.json()
        messages = result.get("data", [])

        if not messages:
            return

        processed_ids = load_processed_ids()
        sent = 0

        for item in messages:
            if process_message(item, processed_ids):
                sent += 1

        if sent:
            print(f"→ {sent} message(s) sent")

    except Exception as e:
        print("API Error:", e)

if __name__ == "__main__":
    print("🚀 Final Bot with Custom Premium Emoji Starting...")
    print("→ Sending ALL old messages first...")
    check_messages()

    print("→ Watching new OTPs (4-10 sec max delay)...")
    while True:
        check_messages()
        time.sleep(4)
