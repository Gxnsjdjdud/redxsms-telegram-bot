import os
import requests
import re
import json
from datetime import datetime, timezone

api_key = os.environ["API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = "-1004469160922"

url = "https://redxsms.com/api/v1/iprn/messages"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json"
}

LAST_ID_FILE = "last_id.txt"
PROCESSED_IDS_FILE = "processed_ids.txt"   # keeps track of already sent messages

def get_last_processed_id():
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, "r") as f:
            return f.read().strip()
    return None

def save_last_processed_id(msg_id):
    with open(LAST_ID_FILE, "w") as f:
        f.write(str(msg_id))

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
        "7": "🇰🇿", "254": "🇰🇪", "965": "🇰🇼", "996": "🇰🇬", "856": "🇱🇦",
        "371": "🇱🇻", "961": "🇱🇧", "266": "🇱🇸", "231": "🇱🇷", "218": "🇱🇾",
        "423": "🇱🇮", "370": "🇱🇹", "352": "🇱🇺", "261": "🇲🇬", "265": "🇲🇼",
        "60": "🇲🇾", "960": "🇲🇻", "223": "🇲🇱", "356": "🇲🇹", "52": "🇲🇽",
        "373": "🇲🇩", "377": "🇲🇨", "976": "🇲🇳", "382": "🇲🇪", "212": "🇲🇦",
        "258": "🇲🇿", "95": "🇲🇲", "264": "🇳🇦", "977": "🇳🇵", "31": "🇳🇱",
        "64": "🇳🇿", "505": "🇳🇮", "227": "🇳🇪", "234": "🇳🇬", "47": "🇳🇴",
        "968": "🇴🇲", "92": "🇵🇰", "970": "🇵🇸", "507": "🇵🇦", "675": "🇵🇬",
        "595": "🇵🇾", "51": "🇵🇪", "63": "🇵🇭", "48": "🇵🇱", "351": "🇵🇹",
        "974": "🇶🇦", "40": "🇷🇴", "7": "🇷🇺", "250": "🇷🇼", "966": "🇸🇦",
        "221": "🇸🇳", "381": "🇷🇸", "248": "🇸🇨", "232": "🇸🇱", "65": "🇸🇬",
        "421": "🇸🇰", "386": "🇸🇮", "252": "🇸🇴", "27": "🇿🇦", "82": "🇰🇷",
        "34": "🇪🇸", "94": "🇱🇰", "249": "🇸🇩", "597": "🇸🇷", "46": "🇸🇪",
        "41": "🇨🇭", "963": "🇸🇾", "886": "🇹🇼", "992": "🇹🇯", "255": "🇹🇿",
        "66": "🇹🇭", "228": "🇹🇬", "676": "🇹🇴", "216": "🇹🇳", "90": "🇹🇷",
        "993": "🇹🇲", "256": "🇺🇬", "380": "🇺🇦", "971": "🇦🇪", "44": "🇬🇧",
        "598": "🇺🇾", "998": "🇺🇿", "58": "🇻🇪", "84": "🇻🇳", "967": "🇾🇪",
        "260": "🇿🇲", "263": "🇿🇼"
    }

    for prefix_code in sorted(country_flags.keys(), key=len, reverse=True):
        if number.startswith(prefix_code):
            return country_flags[prefix_code]
    return "🌐"

def mask_number(number):
    if len(number) > 8:
        return number[:5] + "****" + number[-3:]
    return number

def get_service_info(item, message_text):
    detected_name = ""
    for key in ['service', 'app', 'service_name', 'name', 'title', 'gateway']:
        if key in item and item[key]:
            val = str(item[key]).strip()
            if val and val.lower() != "none":
                val = val.replace("A2P", "").replace("a2p", "").strip()
                if val:
                    detected_name = val
                    break

    if not detected_name:
        for key, value in item.items():
            if value and isinstance(value, str):
                val_lower = value.lower()
                for app in ["telegram", "whatsapp", "1xbet", "google", "facebook", "imo", "viber"]:
                    if app in val_lower:
                        detected_name = app.capitalize()
                        if app == "1xbet":
                            detected_name = "1xBet"
                        break
                if detected_name:
                    break

    if not detected_name or detected_name.lower() == "none":
        text_upper = message_text.upper()
        if "TELEGRAM" in text_upper:
            detected_name = "Telegram"
        elif "WHATSAPP" in text_upper:
            detected_name = "WhatsApp"
        elif "1XBET" in text_upper:
            detected_name = "1xBet"
        elif "GOOGLE" in text_upper:
            detected_name = "Google"
        else:
            detected_name = "Service"

    s_upper = detected_name.upper()
    if "TELEGRAM" in s_upper:
        emoji = "✈️"
    elif "WHATSAPP" in s_upper:
        emoji = "💬"
    elif "1XBET" in s_upper:
        emoji = "🎰"
    elif "GOOGLE" in s_upper:
        emoji = "🌐"
    else:
        emoji = "💬"

    return detected_name, emoji

def send_telegram_message(text, emoji, otp_code):
    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    inline_keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": f"{emoji} 📋 {otp_code}",
                    "copy_text": {"text": otp_code}
                }
            ]
        ]
    }

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(inline_keyboard)
    }
    try:
        requests.post(tg_url, json=payload)
    except Exception as e:
        print(f"Telegram Error: {e}")

def is_today(item):
    """Check if the message belongs to today (UTC)."""
    # Try common date fields
    for key in ["received_at", "created_at", "date", "timestamp", "time"]:
        if key in item and item[key]:
            try:
                raw = str(item[key])
                # Handle both ISO and unix timestamp style
                if raw.isdigit():
                    dt = datetime.fromtimestamp(int(raw), tz=timezone.utc)
                else:
                    # remove Z or timezone part if present
                    raw = raw.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                return dt.date() == datetime.now(timezone.utc).date()
            except Exception:
                continue
    # If no date field found, assume it is recent (include it)
    return True

def process_message(item, processed_ids):
    msg_id = str(item.get("id", item.get("received_at", "")))
    if not msg_id or msg_id in processed_ids:
        return False

    raw_number = str(item.get("number", ""))
    msg_body = item.get("message", "") or ""

    service_name, service_emoji = get_service_info(item, msg_body)
    flag = get_country_flag(raw_number)
    masked_num = mask_number(raw_number)
    prefix = raw_number[:5] if len(raw_number) >= 5 else raw_number

    otp_match = re.search(r'\b\d{3}[-\s]?\d{3}\b|\b\d{4,8}\b', msg_body)
    otp_code = otp_match.group(0) if otp_match else "N/A"

    formatted_msg = (
        f"{service_emoji} {service_name} {flag} `{masked_num}`\n\n"
        f"```{msg_body}```\n\n"
        f"🔍 Prefix : `+{prefix}`\n"
        f"🔑 OTP : `{otp_code}`\n\n"
        f"⚠️ Just demo otp"
    )

    send_telegram_message(formatted_msg, service_emoji, otp_code)
    save_processed_id(msg_id)
    save_last_processed_id(msg_id)
    print(f"Sent → ID: {msg_id} | OTP: {otp_code}")
    return True

def check_messages(send_all_today=False):
    try:
        # Fetch more messages so we can catch all of today's
        params = {'per_page': 50}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        result = response.json()

        messages = result.get("data", [])
        if not messages:
            print("No messages available.")
            return

        processed_ids = load_processed_ids()
        sent_count = 0

        # Reverse so older messages go first when sending all of today
        for item in reversed(messages):
            if send_all_today:
                if is_today(item):
                    if process_message(item, processed_ids):
                        sent_count += 1
            else:
                # Normal mode – only new messages
                msg_id = str(item.get("id", item.get("received_at", "")))
                last_saved = get_last_processed_id()
                if msg_id != last_saved and msg_id not in processed_ids:
                    if process_message(item, processed_ids):
                        sent_count += 1
                        break   # only the newest one in continuous mode

        if sent_count == 0:
            print("No new messages.")
        else:
            print(f"Total sent this run: {sent_count}")

    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    print("🚀 Bot started...")
    print("→ Sending all messages of TODAY first...")
    check_messages(send_all_today=True)

    print("→ Now watching for new messages (Ctrl+C to stop)...")
    import time
    while True:
        check_messages(send_all_today=False)
        time.sleep(8)   # check every 8 seconds
