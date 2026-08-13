import requests
import re
import os
import json
import time

api_key = 'sk_live_1x7jN6OUqTIzUNEv7MIM9Er2h5GphCXer9ef4BUx'
BOT_TOKEN = "8627306223:AAETFF7cWWJiUALC22fGtLy4m_8F04L1o3M"
CHAT_ID = "-1004469160922"

url = 'https://redxsms.com/api/v1/iprn/messages'

headers = {
    'Authorization': f'Bearer {api_key}',
    'Accept': 'application/json'
}

LAST_ID_FILE = "last_id.txt"

def get_last_processed_id():
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, "r") as f:
            return f.read().strip()
    return None

def save_last_processed_id(msg_id):
    with open(LAST_ID_FILE, "w") as f:
        f.write(str(msg_id))

def get_country_code_and_flag(number):
    country_data = {
        "93": ("AF", "🇦🇫"), "355": ("AL", "🇦🇱"), "213": ("DZ", "🇩🇿"), "376": ("AD", "🇦🇩"), "244": ("AO", "🇦🇴"),
        "54": ("AR", "🇦🇷"), "374": ("AM", "🇦🇲"), "61": ("AU", "🇦🇺"), "43": ("AT", "🇦🇹"), "994": ("AZ", "🇦🇿"),
        "973": ("BH", "🇧🇭"), "880": ("BD", "🇧🇩"), "375": ("BY", "🇧🇾"), "32": ("BE", "🇧🇪"), "501": ("BZ", "🇧🇿"),
        "229": ("BJ", "🇧🇯"), "975": ("BT", "🇧🇹"), "591": ("BO", "🇧🇴"), "387": ("BA", "🇧🇦"), "267": ("BW", "🇧🇼"),
        "55": ("BR", "🇧🇷"), "673": ("BN", "🇧🇳"), "359": ("BG", "🇧🇬"), "226": ("BF", "🇧🇫"), "257": ("BI", "🇧🇮"),
        "855": ("KH", "🇰🇭"), "237": ("CM", "🇨🇲"), "1": ("US", "🇺🇸"), "238": ("CV", "🇨🇻"), "236": ("CF", "🇨🇫"),
        "235": ("TD", "🇹🇩"), "56": ("CL", "🇨🇱"), "86": ("CN", "🇨🇳"), "57": ("CO", "🇨🇴"), "269": ("KM", "🇰🇲"),
        "242": ("CG", "🇨🇬"), "243": ("CD", "🇨🇩"), "506": ("CR", "🇨🇷"), "385": ("HR", "🇭🇷"), "53": ("CU", "🇨🇺"),
        "357": ("CY", "🇨🇾"), "420": ("CZ", "🇨🇿"), "45": ("DK", "🇩🇰"), "253": ("DJ", "🇩🇯"), "1767": ("DM", "🇩🇲"),
        "1809": ("DO", "🇩🇴"), "593": ("EC", "🇪🇨"), "20": ("EG", "🇪🇬"), "503": ("SV", "🇸🇻"), "240": ("GQ", "🇬🇶"),
        "291": ("ER", "🇪🇷"), "372": ("EE", "🇪🇪"), "251": ("ET", "🇪🇹"), "679": ("FJ", "🇫🇯"), "358": ("FI", "🇫🇮"),
        "33": ("FR", "🇫🇷"), "241": ("GA", "🇬🇦"), "220": ("GM", "🇬🇲"), "995": ("GE", "🇬🇪"), "49": ("DE", "🇩🇪"),
        "233": ("GH", "🇬🇭"), "30": ("GR", "🇬🇷"), "502": ("GT", "🇬🇹"), "224": ("GN", "🇬🇳"), "245": ("GW", "🇬🇼"),
        "592": ("GY", "🇬🇾"), "509": ("HT", "🇭🇹"), "504": ("HN", "🇭🇳"), "36": ("HU", "🇭🇺"), "354": ("IS", "🇮🇸"),
        "91": ("IN", "🇮🇳"), "62": ("ID", "🇮🇩"), "98": ("IR", "🇮🇷"), "964": ("IQ", "🇮🇶"), "353": ("IE", "🇮🇪"),
        "972": ("IL", "🇮🇱"), "39": ("IT", "🇮🇹"), "1876": ("JM", "🇯🇲"), "81": ("JP", "🇯🇵"), "962": ("JO", "🇯🇴"),
        "7": ("KZ", "🇰🇿"), "254": ("KE", "🇰🇪"), "965": ("KW", "🇰🇼"), "996": ("KG", "🇰🇬"), "856": ("LA", "🇱🇦"),
        "371": ("LV", "🇱🇻"), "961": ("LB", "🇱🇧"), "266": ("LS", "🇱🇸"), "231": ("LR", "🇱🇷"), "218": ("LY", "🇱🇾"),
        "423": ("LI", "🇱🇮"), "370": ("LT", "🇱🇹"), "352": ("LU", "🇱🇺"), "261": ("MG", "🇲🇬"), "265": ("MW", "🇲🇼"),
        "60": ("MY", "🇲🇾"), "960": ("MV", "🇲🇻"), "223": ("ML", "🇲🇱"), "356": ("MT", "🇲🇹"), "52": ("MX", "🇲🇽"),
        "373": ("MD", "🇲🇩"), "377": ("MC", "🇲🇨"), "976": ("MN", "🇲🇳"), "382": ("ME", "🇲🇪"), "212": ("MA", "🇲🇦"),
        "258": ("MZ", "🇲🇿"), "95": ("MM", "🇲🇲"), "264": ("NA", "🇳🇦"), "977": ("NP", "🇳🇵"), "31": ("NL", "🇳🇱"),
        "64": ("NZ", "🇳🇿"), "505": ("NI", "🇳🇮"), "227": ("NE", "🇳🇪"), "234": ("NG", "🇳🇬"), "47": ("NO", "🇳🇴"),
        "968": ("OM", "🇴🇲"), "92": ("PK", "🇵🇰"), "970": ("PS", "🇵🇸"), "507": ("PA", "🇵🇦"), "675": ("PG", "🇵🇬"),
        "595": ("PY", "🇵🇾"), "51": ("PE", "🇵🇪"), "63": ("PH", "🇵🇭"), "48": ("PL", "🇵🇱"), "351": ("PT", "🇵🇹"),
        "974": ("QA", "🇶🇦"), "40": ("RO", "🇷🇴"), "7": ("RU", "🇷🇺"), "250": ("RW", "🇷🇼"), "966": ("SA", "🇸🇦"),
        "221": ("SN", "🇸🇳"), "381": ("RS", "🇷🇸"), "248": ("SC", "🇸🇨"), "232": ("SL", "🇸🇱"), "65": ("SG", "🇸🇬"),
        "421": ("SK", "🇸🇰"), "386": ("SI", "🇸🇮"), "252": ("SO", "🇸🇴"), "27": ("ZA", "🇿🇦"), "82": ("KR", "🇰🇷"),
        "34": ("ES", "🇪🇸"), "94": ("LK", "🇱🇰"), "249": ("SD", "🇸🇩"), "597": ("SR", "🇸🇷"), "46": ("SE", "🇸🇪"),
        "41": ("CH", "🇨🇭"), "963": ("SY", "🇸🇾"), "886": ("TW", "🇹🇼"), "992": ("TJ", "🇹🇯"), "255": ("TZ", "🇹🇿"),
        "66": ("TH", "🇹🇭"), "228": ("TG", "🇹🇬"), "676": ("TO", "🇹🇴"), "216": ("TN", "🇹🇳"), "90": ("TR", "🇹🇷"),
        "993": ("TM", "🇹🇲"), "256": ("UG", "🇺🇬"), "380": ("UA", "🇺🇦"), "971": ("AE", "🇦🇪"), "44": ("GB", "🇬🇧"),
        "598": ("UY", "🇺🇾"), "998": ("UZ", "🇺🇿"), "58": ("VE", "🇻🇪"), "84": ("VN", "🇻🇳"), "967": ("YE", "🇾🇪"),
        "260": ("ZM", "🇿🇲"), "263": ("ZW", "🇿🇼")
    }
    
    for prefix_code in sorted(country_data.keys(), key=len, reverse=True):
        if number.startswith(prefix_code):
            return country_data[prefix_code]
    return "GEN", "🌐"

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
        short_name = "TG"
        emoji = "✈️"
    elif "WHATSAPP" in s_upper:
        short_name = "Ws"
        emoji = "🟢"
    elif "1XBET" in s_upper:
        short_name = "1xBet"
        emoji = "🎰"
    elif "GOOGLE" in s_upper:
        short_name = "Google"
        emoji = "🌐"
    else:
        short_name = detected_name
        emoji = "💬"
        
    return short_name, emoji

def send_telegram_message(text, emoji, otp_code):
    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    inline_keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": f"{emoji} 📋 {otp_code}",
                    "copy_text": {"text": otp_code}
                },
                {
                    "text": "🌐 Number Bot",
                    "url": "https://t.me/YourBotUsername"  # এখানে তোমার বটের লিংক বসিয়ে নেবে
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
        requests.post(tg_url, json=payload, timeout=2)
    except Exception as e:
        print(f"Telegram Error: {e}")

def check_messages():
    try:
        # প্যানেল থেকে একাধিক (যেমন একসাথে ১০টি) মেসেজ ফেচ করার ব্যবস্থা যাতে পুরোনো ও আজকের সব কোড একসাথে ধরতে পারে
        params = {'per_page': 10}
        response = requests.get(url, headers=headers, params=params, timeout=2)
        
        try:
            result = response.json()
        except:
            return
        
        messages = result.get("data", [])
        
        if messages:
            # পুরোনো মেসেজগুলো আগে প্রসেস করার জন্য রিভার্স করা হলো, যাতে সিরিয়াল ঠিক থাকে
            messages.reverse()
            
            last_saved_id = get_last_processed_id()
            new_last_id = last_saved_id
            
            for latest_item in messages:
                msg_id = str(latest_item.get("id", latest_item.get("received_at", "")))
                
                # যদি আইডি সেভ করা না থাকে অথবা নতুন আইডি হয়, তবে সেন্ড করবে
                if last_saved_id is None or msg_id > last_saved_id:
                    raw_number = str(latest_item.get("number", ""))
                    msg_body = latest_item.get("message", "")
                    
                    service_name, service_emoji = get_service_info(latest_item, msg_body)
                    country_code, flag = get_country_code_and_flag(raw_number)
                    prefix = raw_number[:9] if len(raw_number) >= 9 else raw_number
                    
                    otp_match = re.search(r'\b\d{3}[-\s]?\d{3}\b|\b\d{4,6}\b', msg_body)
                    otp_code = otp_match.group(0) if otp_match else "N/A"
                    
                    formatted_msg = (
                        f"{flag} **{country_code}** {service_emoji} `{raw_number}`\n\n"
                        f"```{msg_body}```\n\n"
                        f"🛡️ **Prefix:** `{prefix}`"
                    )
                    
                    send_telegram_message(formatted_msg, service_emoji, otp_code)
                    new_last_id = msg_id
                    time.sleep(0.3) # মেসেজগুলোর মাঝে ছোট বিরতি যাতে টেলিগ্রাম ফ্লাড এরর না দেয়
            
            if new_last_id != last_saved_id:
                save_last_processed_id(new_last_id)
            
    except Exception as e:
        pass

if __name__ == "__main__":
    print("Bot is running and syncing old & new messages...")
    while True:
        check_messages()
        time.sleep(0.5)
