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

LAST_ID_FILE = "last_id.txt"
PROCESSED_IDS_FILE = "processed_ids.txt"

# Bangladesh time (UTC+6)
BD_TZ = timezone(timedelta(hours=6))

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

def get_country_info(number):
    country_data = {
        "93": ("🇦🇫", "Afghanistan"), "355": ("🇦🇱", "Albania"), "213": ("🇩🇿", "Algeria"),
        "376": ("🇦🇩", "Andorra"), "244": ("🇦🇴", "Angola"), "54": ("🇦🇷", "Argentina"),
        "374": ("🇦🇲", "Armenia"), "61": ("🇦🇺", "Australia"), "43": ("🇦🇹", "Austria"),
        "994": ("🇦🇿", "Azerbaijan"), "973": ("🇧🇭", "Bahrain"), "880": ("🇧🇩", "Bangladesh"),
        "375": ("🇧🇾", "Belarus"), "32": ("🇧🇪", "Belgium"), "501": ("🇧🇿", "Belize"),
        "229": ("🇧🇯", "Benin"), "975": ("🇧🇹", "Bhutan"), "591": ("🇧🇴", "Bolivia"),
        "387": ("🇧🇦", "Bosnia"), "267": ("🇧🇼", "Botswana"), "55": ("🇧🇷", "Brazil"),
        "673": ("🇧🇳", "Brunei"), "359": ("🇧🇬", "Bulgaria"), "226": ("🇧🇫", "Burkina Faso"),
        "257": ("🇧🇮", "Burundi"), "855": ("🇰🇭", "Cambodia"), "237": ("🇨🇲", "Cameroon"),
        "1": ("🇺🇸", "United States"), "238": ("🇨🇻", "Cape Verde"), "236": ("🇨🇫", "Central African Republic"),
        "235": ("🇹🇩", "Chad"), "56": ("🇨🇱", "Chile"), "86": ("🇨🇳", "China"),
        "57": ("🇨🇴", "Colombia"), "269": ("🇰🇲", "Comoros"), "242": ("🇨🇬", "Congo"),
        "243": ("🇨🇩", "DR Congo"), "506": ("🇨🇷", "Costa Rica"), "385": ("🇭🇷", "Croatia"),
        "53": ("🇨🇺", "Cuba"), "357": ("🇨🇾", "Cyprus"), "420": ("🇨🇿", "Czech Republic"),
        "45": ("🇩🇰", "Denmark"), "253": ("🇩🇯", "Djibouti"), "1767": ("🇩🇲", "Dominica"),
        "1809": ("🇩🇴", "Dominican Republic"), "593": ("🇪🇨", "Ecuador"), "20": ("🇪🇬", "Egypt"),
        "503": ("🇸🇻", "El Salvador"), "240": ("🇬🇶", "Equatorial Guinea"), "291": ("🇪🇷", "Eritrea"),
        "372": ("🇪🇪", "Estonia"), "251": ("🇪🇹", "Ethiopia"), "679": ("🇫🇯", "Fiji"),
        "358": ("🇫🇮", "Finland"), "33": ("🇫🇷", "France"), "241": ("🇬🇦", "Gabon"),
        "220": ("🇬🇲", "Gambia"), "995": ("🇬🇪", "Georgia"), "49": ("🇩🇪", "Germany"),
        "233": ("🇬🇭", "Ghana"), "30": ("🇬🇷", "Greece"), "502": ("🇬🇹", "Guatemala"),
        "224": ("🇬🇳", "Guinea"), "245": ("🇬🇼", "Guinea-Bissau"), "592": ("🇬🇾", "Guyana"),
        "509": ("🇭🇹", "Haiti"), "504": ("🇭🇳", "Honduras"), "36": ("🇭🇺", "Hungary"),
        "354": ("🇮🇸", "Iceland"), "91": ("🇮🇳", "India"), "62": ("🇮🇩", "Indonesia"),
        "98": ("🇮🇷", "Iran"), "964": ("🇮🇶", "Iraq"), "353": ("🇮🇪", "Ireland"),
        "972": ("🇮🇱", "Israel"), "39": ("🇮🇹", "Italy"), "1876": ("🇯🇲", "Jamaica"),
        "81": ("🇯🇵", "Japan"), "962": ("🇯🇴", "Jordan"), "7": ("🇷🇺", "Russia"),
        "254": ("🇰🇪", "Kenya"), "965": ("🇰🇼", "Kuwait"), "996": ("🇰🇬", "Kyrgyzstan"),
        "856": ("🇱🇦", "Laos"), "371": ("🇱🇻", "Latvia"), "961": ("🇱🇧", "Lebanon"),
        "266": ("🇱🇸", "Lesotho"), "231": ("🇱🇷", "Liberia"), "218": ("🇱🇾", "Libya"),
        "423": ("🇱🇮", "Liechtenstein"), "370": ("🇱🇹", "Lithuania"), "352": ("🇱🇺", "Luxembourg"),
        "261": ("🇲🇬", "Madagascar"), "265": ("🇲🇼", "Malawi"), "60": ("🇲🇾", "Malaysia"),
        "960": ("🇲🇻", "Maldives"), "223": ("🇲🇱", "Mali"), "356": ("🇲🇹", "Malta"),
        "52": ("🇲🇽", "Mexico"), "373": ("🇲🇩", "Moldova"), "377": ("🇲🇨", "Monaco"),
        "976": ("🇲🇳", "Mongolia"), "382": ("🇲🇪", "Montenegro"), "212": ("🇲🇦", "Morocco"),
        "258": ("🇲🇿", "Mozambique"), "95": ("🇲🇲", "Myanmar"), "264": ("🇳🇦", "Namibia"),
        "977": ("🇳🇵", "Nepal"), "31": ("🇳🇱", "Netherlands"), "64": ("🇳🇿", "New Zealand"),
        "505": ("🇳🇮", "Nicaragua"), "227": ("🇳🇪", "Niger"), "234": ("🇳🇬", "Nigeria"),
        "47": ("🇳🇴", "Norway"), "968": ("🇴🇲", "Oman"), "92": ("🇵🇰", "Pakistan"),
        "970": ("🇵🇸", "Palestine"), "507": ("🇵🇦", "Panama"), "675": ("🇵🇬", "Papua New Guinea"),
        "595": ("🇵🇾", "Paraguay"), "51": ("🇵🇪", "Peru"), "63": ("🇵🇭", "Philippines"),
        "48": ("🇵🇱", "Poland"), "351": ("🇵🇹", "Portugal"), "974": ("🇶🇦", "Qatar"),
        "40": ("🇷🇴", "Romania"), "250": ("🇷🇼", "Rwanda"), "966": ("🇸🇦", "Saudi Arabia"),
        "221": ("🇸🇳", "Senegal"), "381": ("🇷🇸", "Serbia"), "248": ("🇸🇨", "Seychelles"),
        "232": ("🇸🇱", "Sierra Leone"), "65": ("🇸🇬", "Singapore"), "421": ("🇸🇰", "Slovakia"),
        "386": ("🇸🇮", "Slovenia"), "252": ("🇸🇴", "Somalia"), "27": ("🇿🇦", "South Africa"),
        "82": ("🇰🇷", "South Korea"), "34": ("🇪🇸", "Spain"), "94": ("🇱🇰", "Sri Lanka"),
        "249": ("🇸🇩", "Sudan"), "597": ("🇸🇷", "Suriname"), "46": ("🇸🇪", "Sweden"),
        "41": ("🇨🇭", "Switzerland"), "963": ("🇸🇾", "Syria"), "886": ("🇹🇼", "Taiwan"),
        "992": ("🇹🇯", "Tajikistan"), "255": ("🇹🇿", "Tanzania"), "66": ("🇹🇭", "Thailand"),
        "228": ("🇹🇬", "Togo"), "676": ("🇹🇴", "Tonga"), "216": ("🇹🇳", "Tunisia"),
        "90": ("🇹🇷", "Turkey"), "993": ("🇹🇲", "Turkmenistan"), "256": ("🇺🇬", "Uganda"),
        "380": ("🇺🇦", "Ukraine"), "971": ("🇦🇪", "United Arab Emirates"), "44": ("🇬🇧", "United Kingdom"),
        "598": ("🇺🇾", "Uruguay"), "998": ("🇺🇿", "Uzbekistan"), "58": ("🇻🇪", "Venezuela"),
        "84": ("🇻🇳", "Vietnam"), "967": ("🇾🇪", "Yemen"), "260": ("🇿🇲", "Zambia"),
        "263": ("🇿🇼", "Zimbabwe")
    }

    for prefix_code in sorted(country_data.keys(), key=len, reverse=True):
        if number.startswith(prefix_code):
            return country_data[prefix_code]
    return ("🌐", "Unknown")

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

def delete_message_later(chat_id, message_id):
    """3 মিনিট পর মেসেজ ডিলিট করবে"""
    time.sleep(180)
    try:
        delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        requests.post(delete_url, json={
            "chat_id": chat_id,
            "message_id": message_id
        }, timeout=10)
        print(f"Message {message_id} auto-deleted after 3 minutes")
    except Exception as e:
        print(f"Delete error: {e}")

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
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(inline_keyboard)
    }

    try:
        resp = requests.post(tg_url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            message_id = data["result"]["message_id"]
            # ৩ মিনিট পর অটো ডিলিট
            t = threading.Thread(target=delete_message_later, args=(CHAT_ID, message_id), daemon=True)
            t.start()
            return message_id
        else:
            print(f"Telegram Error: {data}")
            return None
    except Exception as e:
        print(f"Telegram Error: {e}")
        return None

def is_today(item):
    for key in ["received_at", "created_at", "date", "timestamp", "time"]:
        if key in item and item[key]:
            try:
                raw = str(item[key])
                if raw.isdigit():
                    dt = datetime.fromtimestamp(int(raw), tz=timezone.utc)
                else:
                    raw = raw.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(BD_TZ).date() == datetime.now(BD_TZ).date()
            except Exception:
                continue
    return True

def process_message(item, processed_ids):
    msg_id = str(item.get("id", item.get("received_at", "")))
    if not msg_id or msg_id in processed_ids:
        return False

    raw_number = str(item.get("number", ""))
    msg_body = item.get("message", "") or ""

    service_name, service_emoji = get_service_info(item, msg_body)
    flag, country_name = get_country_info(raw_number)
    masked_num = mask_number(raw_number)
    prefix = raw_number[:5] if len(raw_number) >= 5 else raw_number

    otp_match = re.search(r'\b\d{3}[-\s]?\d{3}\b|\b\d{4,8}\b', msg_body)
    otp_code = otp_match.group(0) if otp_match else "N/A"

    # Live time (Bangladesh time)
    now = datetime.now(BD_TZ)
    live_time = now.strftime("%d %b %Y • %H:%M")

    formatted_msg = (
        f"{service_emoji} **{service_name}**\n"
        f"{flag} **{country_name}**\n"
        f"🕒 `{live_time}`\n\n"
        f"```{msg_body}```\n\n"
        f"🔍 Prefix : `+{prefix}`\n"
        f"🔑 OTP : `{otp_code}`\n\n"
        f"⏳ OTP auto delete after 3 minutes"
    )

    sent = send_telegram_message(formatted_msg, service_emoji, otp_code)
    if sent:
        save_processed_id(msg_id)
        save_last_processed_id(msg_id)
        print(f"Sent → ID: {msg_id} | OTP: {otp_code} | Country: {country_name}")
        return True
    return False

def check_messages(send_all_today=False):
    try:
        params = {'per_page': 50}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        result = response.json()

        messages = result.get("data", [])
        if not messages:
            print("No messages available.")
            return

        processed_ids = load_processed_ids()
        sent_count = 0

        for item in reversed(messages):
            if send_all_today:
                if is_today(item):
                    if process_message(item, processed_ids):
                        sent_count += 1
            else:
                msg_id = str(item.get("id", item.get("received_at", "")))
                last_saved = get_last_processed_id()
                if msg_id != last_saved and msg_id not in processed_ids:
                    if process_message(item, processed_ids):
                        sent_count += 1
                        break

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
    while True:
        check_messages(send_all_today=False)
        time.sleep(8)
