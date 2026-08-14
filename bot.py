import os
import requests
import re
import json
import time
import threading

api_key = os.environ["API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = "-1004469160922"

url = "https://redxsms.com/api/v1/iprn/messages"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json"
}

PROCESSED_IDS_FILE = "processed_ids.txt"

# HTTP Connection Pooling এর জন্য Session ব্যবহার
session = requests.Session()
session.headers.update(headers)

def clear_processed_ids():
    if os.path.exists(PROCESSED_IDS_FILE):
        os.remove(PROCESSED_IDS_FILE)
        print("→ processed_ids.txt cleared")

def load_processed_ids():
    if os.path.exists(PROCESSED_IDS_FILE):
        with open(PROCESSED_IDS_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_id(msg_id):
    with open(PROCESSED_IDS_FILE, "a") as f:
        f.write(str(msg_id) + "\n")

def get_country_info(number):
    data = {
        "93": ("🇦🇫", "AF"), "355": ("🇦🇱", "AL"), "213": ("🇩🇿", "DZ"), "376": ("🇦🇩", "AD"),
        "244": ("🇦🇴", "AO"), "54": ("🇦🇷", "AR"), "374": ("🇦🇲", "AM"), "61": ("🇦🇺", "AU"),
        "43": ("🇦🇹", "AT"), "994": ("🇦🇿", "AZ"), "973": ("🇧🇭", "BH"), "880": ("🇧🇩", "BD"),
        "375": ("🇧🇾", "BY"), "32": ("🇧🇪", "BE"), "501": ("🇧🇿", "BZ"), "229": ("🇧🇯", "BJ"),
        "975": ("🇧🇹", "BT"), "591": ("🇧🇴", "BO"), "387": ("🇧🇦", "BA"), "267": ("🇧🇼", "BW"),
        "55": ("🇧🇷", "BR"), "673": ("🇧🇳", "BN"), "359": ("🇧🇬", "BG"), "226": ("🇧🇫", "BF"),
        "257": ("🇧🇮", "BI"), "855": ("🇰🇭", "KH"), "237": ("🇨🇲", "CM"), "1": ("🇺🇸", "US"),
        "238": ("🇨🇻", "CV"), "236": ("🇨🇫", "CF"), "235": ("🇹🇩", "TD"), "56": ("🇨🇱", "CL"),
        "86": ("🇨🇳", "CN"), "57": ("🇨🇴", "CO"), "269": ("🇰🇲", "KM"), "242": ("🇨🇬", "CG"),
        "243": ("🇨🇩", "CD"), "506": ("🇨🇷", "CR"), "385": ("🇭🇷", "HR"), "53": ("🇨🇺", "CU"),
        "357": ("🇨🇾", "CY"), "420": ("🇨🇿", "CZ"), "45": ("🇩🇰", "DK"), "253": ("🇩🇯", "DJ"),
        "1767": ("🇩🇲", "DM"), "1809": ("🇩🇴", "DO"), "593": ("🇪🇨", "EC"), "20": ("🇪🇬", "EG"),
        "503": ("🇸🇻", "SV"), "240": ("🇬🇶", "GQ"), "291": ("🇪🇷", "ER"), "372": ("🇪🇪", "EE"),
        "251": ("🇪🇹", "ET"), "679": ("🇫🇯", "FJ"), "358": ("🇫🇮", "FI"), "33": ("🇫🇷", "FR"),
        "241": ("🇬🇦", "GA"), "220": ("🇬🇲", "GM"), "995": ("🇬🇪", "GE"), "49": ("🇩🇪", "DE"),
        "233": ("🇬🇭", "GH"), "30": ("🇬🇷", "GR"), "502": ("🇬🇹", "GT"), "224": ("🇬🇳", "GN"),
        "245": ("🇬🇼", "GW"), "592": ("🇬🇾", "GY"), "509": ("🇭🇹", "HT"), "504": ("🇭🇳", "HN"),
        "36": ("🇭🇺", "HU"), "354": ("🇮🇸", "IS"), "91": ("🇮🇳", "IN"), "62": ("🇮🇩", "ID"),
        "98": ("🇮🇷", "IR"), "964": ("🇮🇶", "IQ"), "353": ("🇮🇪", "IE"), "972": ("🇮🇱", "IL"),
        "39": ("🇮🇹", "IT"), "1876": ("🇯🇲", "JM"), "81": ("🇯🇵", "JP"), "962": ("🇯🇴", "JO"),
        "7": ("🇷🇺", "RU"), "254": ("🇰🇪", "KE"), "965": ("🇰🇼", "KW"), "996": ("🇰🇬", "KG"),
        "856": ("🇱🇦", "LA"), "371": ("🇱🇻", "LV"), "961": ("🇱🇧", "LB"), "266": ("🇱🇸", "LS"),
        "231": ("🇱🇷", "LR"), "218": ("🇱🇾", "LY"), "423": ("🇱🇮", "LI"), "370": ("🇱🇹", "LT"),
        "352": ("🇱🇺", "LU"), "261": ("🇲🇬", "MG"), "265": ("🇲🇼", "MW"), "60": ("🇲🇾", "MY"),
        "960": ("🇲🇻", "MV"), "223": ("🇲🇱", "ML"), "356": ("🇲🇹", "MT"), "52": ("🇲🇽", "MX"),
        "373": ("🇲🇩", "MD"), "377": ("🇲🇨", "MC"), "976": ("🇲🇳", "MN"), "382": ("🇲🇪", "ME"),
        "212": ("🇲🇦", "MA"), "258": ("🇲🇿", "MZ"), "95": ("🇲🇲", "MM"), "264": ("🇳🇦", "NA"),
        "977": ("🇳🇵", "NP"), "31": ("🇳🇱", "NL"), "64": ("🇳🇿", "NZ"), "505": ("🇳🇮", "NI"),
        "227": ("🇳🇪", "NE"), "234": ("🇳🇬", "NG"), "47": ("🇳🇴", "NO"), "968": ("🇴🇲", "OM"),
        "92": ("🇵🇰", "PK"), "970": ("🇵🇸", "PS"), "507": ("🇵🇦", "PA"), "675": ("🇵🇬", "PG"),
        "595": ("🇵🇾", "PY"), "51": ("🇵🇪", "PE"), "63": ("🇵🇭", "PH"), "48": ("🇵🇱", "PL"),
        "351": ("🇵🇹", "PT"), "974": ("🇶🇦", "QA"), "40": ("🇷🇴", "RO"), "250": ("🇷🇼", "RW"),
        "966": ("🇸🇦", "SA"), "221": ("🇸🇳", "SN"), "381": ("🇷🇸", "RS"), "248": ("🇸🇨", "SC"),
        "232": ("🇸🇱", "SL"), "65": ("🇸🇬", "SG"), "421": ("🇸🇰", "SK"), "386": ("🇸🇮", "SI"),
        "252": ("🇸🇴", "SO"), "27": ("🇿🇦", "ZA"), "82": ("🇰🇷", "KR"), "34": ("🇪🇸", "ES"),
        "94": ("🇱🇰", "LK"), "249": ("🇸🇩", "SD"), "597": ("🇸🇷", "SR"), "46": ("🇸🇪", "SE"),
        "41": ("🇨🇭", "CH"), "963": ("🇸🇾", "SY"), "886": ("🇹🇼", "TW"), "992": ("🇹🇯", "TJ"),
        "255": ("🇹🇿", "TZ"), "66": ("🇹🇭", "TH"), "228": ("🇹🇬", "TG"), "676": ("🇹🇴", "TO"),
        "216": ("🇹🇳", "TN"), "90": ("🇹🇷", "TR"), "993": ("🇹🇲", "TM"), "256": ("🇺🇬", "UG"),
        "380": ("🇺🇦", "UA"), "971": ("🇦🇪", "AE"), "44": ("🇬🇧", "GB"), "598": ("🇺🇾", "UY"),
        "998": ("🇺🇿", "UZ"), "58": ("🇻🇪", "VE"), "84": ("🇻🇳", "VN"), "967": ("🇾🇪", "YE"),
        "260": ("🇿🇲", "ZM"), "263": ("🇿🇼", "ZW")
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
        elif "1XBET" in text: name = "1xbet"
        elif "GOOGLE" in text: name = "google"
        elif "FACEBOOK" in text: name = "facebook"
        elif "IMO" in text: name = "imo"
        elif "VIBER" in text: name = "viber"
        elif "INSTAGRAM" in text: name = "instagram"

    if "telegram" in name: return "✈️", "TG"
    if "whatsapp" in name: return "💬", "WA"
    if "tiktok" in name: return "🎵", "TT"
    if "1xbet" in name: return "🎰", "1X"
    if "google" in name: return "🌐", "GG"
    if "facebook" in name: return "📘", "FB"
    if "instagram" in name: return "📸", "IG"
    if "imo" in name: return "💜", "IMO"
    if "viber" in name: return "📳", "VB"
    return "💬", "SV"

def delete_message_later(chat_id, message_id):
    time.sleep(180)
    try:
        session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                     json={"chat_id": chat_id, "message_id": message_id}, timeout=5)
    except:
        pass

def send_telegram_message(text, otp_code):
    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    inline_keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": f"🔑 📋 {otp_code}",
                    "copy_text": {"text": otp_code}
                }
            ],
            [
                {
                    "text": "📢 Main Channel",
                    "url": "https://t.me/Global_Method_Channel"
                },
                {
                    "text": "📞 Number Channel",
                    "url": "https://t.me/Heueururuhhd_bot"
                }
            ]
        ]
    }

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(inline_keyboard)
    }

    try:
        resp = session.post(tg_url, json=payload, timeout=5)
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

    flag, country_code = get_country_info(raw_number)
    service_emoji, service_short = get_service_info(item, msg_body)
    masked = mask_number(raw_number)

    otp_match = re.search(r'\b\d{3}[-\s]?\d{3}\b|\b\d{4,8}\b', msg_body)
    otp_code = otp_match.group(0).replace("-", "").replace(" ", "") if otp_match else "N/A"

    header = f"{flag} <b>{country_code}</b> | {service_emoji} <code>+{masked}</code>"

    if send_telegram_message(header, otp_code):
        save_processed_id(msg_id)
        processed_ids.add(msg_id)
        print(f"✅ NEW → {flag} {country_code} | {service_short} +{masked} → {otp_code}")
        return True
    return False

def check_messages(processed_ids):
    try:
        params = {'per_page': 20}
        response = session.get(url, params=params, timeout=5)
        result = response.json()
        messages = result.get("data", [])

        if not messages:
            return

        sent = 0
        # নতুন মেসেজ যেন সাথে সাথে প্রসেস হয়, তাই লিস্ট রিভার্স করা হয়েছে
        for item in reversed(messages):
            if process_message(item, processed_ids):
                sent += 1

        if sent:
            print(f"→ {sent} new OTP sent to group")

    except Exception as e:
        print("API Error:", e)

if __name__ == "__main__":
    print("🚀 Fast Bot Starting...")
    clear_processed_ids()
    
    processed_ids = load_processed_ids()

    print("→ Processing existing panel messages...")
    check_messages(processed_ids)
    print("→ All existing messages processed! Bot is now running live...")

    while True:
        check_messages(processed_ids)
        time.sleep(1.5)
