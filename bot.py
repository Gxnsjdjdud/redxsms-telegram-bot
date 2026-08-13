import os
import re
import json
import time
import threading
import requests

from datetime import timezone, timedelta


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

API_KEY = os.environ["API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

CHAT_ID = "-1004469160922"


# =========================================================
# REDX SMS API
# =========================================================

REDX_URL = "https://redxsms.com/api/v1/iprn/messages"

REDX_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
}


# =========================================================
# SETTINGS
# =========================================================

PROCESSED_IDS_FILE = "processed_ids.txt"

CHECK_INTERVAL = 4
DELETE_AFTER = 180

BD_TZ = timezone(timedelta(hours=6))


# =========================================================
# PROCESSED MESSAGE IDS
# =========================================================

def load_processed_ids():
    try:
        if not os.path.exists(PROCESSED_IDS_FILE):
            return set()

        with open(PROCESSED_IDS_FILE, "r", encoding="utf-8") as f:
            return {
                line.strip()
                for line in f
                if line.strip()
            }

    except Exception as e:
        print("❌ Failed loading processed IDs:", repr(e))
        return set()


def save_processed_id(message_id):
    try:
        with open(
            PROCESSED_IDS_FILE,
            "a",
            encoding="utf-8"
        ) as f:
            f.write(str(message_id) + "\n")

    except Exception as e:
        print("❌ Failed saving processed ID:", repr(e))


# =========================================================
# COUNTRY FLAG
# =========================================================

def get_country_flag(number):

    flags = {
        "880": "🇧🇩",
        "91": "🇮🇳",
        "92": "🇵🇰",
        "1": "🇺🇸",
        "44": "🇬🇧",
        "971": "🇦🇪",
        "966": "🇸🇦",
        "60": "🇲🇾",
        "65": "🇸🇬",
        "62": "🇮🇩",
        "63": "🇵🇭",
        "66": "🇹🇭",
        "81": "🇯🇵",
        "82": "🇰🇷",
        "86": "🇨🇳",
        "90": "🇹🇷",
        "49": "🇩🇪",
        "33": "🇫🇷",
        "39": "🇮🇹",
        "34": "🇪🇸",
        "31": "🇳🇱",
        "61": "🇦🇺",
        "55": "🇧🇷",
        "7": "🇷🇺",
        "98": "🇮🇷",
        "964": "🇮🇶",
        "20": "🇪🇬",
        "27": "🇿🇦",
        "234": "🇳🇬",
        "254": "🇰🇪",
        "977": "🇳🇵",
        "94": "🇱🇰",
        "84": "🇻🇳",
        "93": "🇦🇫",
        "212": "🇲🇦",
        "216": "🇹🇳",
        "972": "🇮🇱",
        "974": "🇶🇦",
        "973": "🇧🇭",
        "968": "🇴🇲",
        "965": "🇰🇼",
        "962": "🇯🇴",
        "32": "🇧🇪",
        "41": "🇨🇭",
        "43": "🇦🇹",
        "45": "🇩🇰",
        "46": "🇸🇪",
        "47": "🇳🇴",
        "48": "🇵🇱",
        "351": "🇵🇹",
        "358": "🇫🇮",
        "30": "🇬🇷",
        "36": "🇭🇺",
        "40": "🇷🇴",
        "420": "🇨🇿",
        "421": "🇸🇰",
        "380": "🇺🇦",
    }

    number = re.sub(r"\D", "", number)

    for code in sorted(flags, key=len, reverse=True):
        if number.startswith(code):
            return flags[code]

    return "🌐"


# =========================================================
# SERVICE DETECTION
# =========================================================

def get_service(item, message):

    possible_fields = [
        "service",
        "app",
        "service_name",
        "name",
        "title",
        "gateway",
    ]

    service = ""

    for key in possible_fields:

        value = item.get(key)

        if value:
            value = str(value).strip().lower()

            if value and value != "none":
                service = value
                break

    if not service:

        text = message.upper()

        services = {
            "TELEGRAM": "telegram",
            "WHATSAPP": "whatsapp",
            "GOOGLE": "google",
            "FACEBOOK": "facebook",
            "IMO": "imo",
            "VIBER": "viber",
        }

        for keyword, name in services.items():

            if keyword in text:
                service = name
                break

    service_map = {
        "telegram": ("#TG", "✈️"),
        "whatsapp": ("#WA", "💬"),
        "google": ("#GG", "🌐"),
        "facebook": ("#FB", "📘"),
        "imo": ("#IMO", "💜"),
        "viber": ("#VB", "📳"),
    }

    return service_map.get(
        service,
        ("#SMS", "💬")
    )


# =========================================================
# MASK SENSITIVE NUMERIC CODES
# =========================================================

def mask_sensitive_codes(text):

    if not text:
        return ""

    # Mask 4-8 digit verification-like sequences.
    # Example: 123456 -> ******

    def replace_code(match):
        value = match.group(0)
        return "*" * len(value)

    text = re.sub(
        r"\b\d{4,8}\b",
        replace_code,
        text
    )

    # Mask 3-3 patterns such as 123-456

    text = re.sub(
        r"\b\d{3}[-\s]\d{3}\b",
        lambda m: "******",
        text
    )

    return text


# =========================================================
# DELETE TELEGRAM MESSAGE
# =========================================================

def delete_message_later(chat_id, message_id):

    time.sleep(DELETE_AFTER)

    try:

        url = (
            f"https://api.telegram.org/"
            f"bot{BOT_TOKEN}/deleteMessage"
        )

        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "message_id": message_id,
            },
            timeout=10,
        )

        print(
            "🗑 Delete status:",
            response.status_code,
            response.text
        )

    except Exception as e:

        print(
            "❌ Delete error:",
            repr(e)
        )


# =========================================================
# SEND TELEGRAM NOTIFICATION
# =========================================================

def send_telegram_message(
    text,
    emoji
):

    telegram_url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📞 Get Number",
                    "url": "https://t.me/Heueururuhhd_bot",
                },
                {
                    "text": "📢 Main Channel",
                    "url": "https://t.me/Global_Method_Channel",
                },
            ]
        ]
    }

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "reply_markup": keyboard,
    }

    try:

        response = requests.post(
            telegram_url,
            json=payload,
            timeout=15,
        )

        print(
            "📨 Telegram Status:",
            response.status_code
        )

        print(
            "📨 Telegram Response:",
            response.text
        )

        data = response.json()

        if not data.get("ok"):

            print(
                "❌ Telegram rejected message:",
                data
            )

            return False

        message_id = (
            data["result"]["message_id"]
        )

        print(
            "✅ Telegram message sent:",
            message_id
        )

        threading.Thread(
            target=delete_message_later,
            args=(
                CHAT_ID,
                message_id,
            ),
            daemon=True,
        ).start()

        return True

    except Exception as e:

        print(
            "❌ Telegram Error:",
            repr(e)
        )

        return False


# =========================================================
# PROCESS REDX MESSAGE
# =========================================================

def process_message(
    item,
    processed_ids
):

    message_id = str(
        item.get(
            "id",
            item.get(
                "received_at",
                ""
            )
        )
    ).strip()

    if not message_id:
        print("⚠️ Message has no ID")
        return False

    if message_id in processed_ids:

        print(
            "⏭ Already processed:",
            message_id
        )

        return False

    number = str(
        item.get(
            "number",
            ""
        )
    ).strip()

    message = str(
        item.get(
            "message",
            ""
        ) or ""
    )

    flag = get_country_flag(number)

    service_code, emoji = get_service(
        item,
        message
    )

    safe_message = mask_sensitive_codes(
        message
    )

    # Mask phone number except last 4 digits

    if len(number) > 4:

        masked_number = (
            "*" * (len(number) - 4)
            + number[-4:]
        )

    else:

        masked_number = "****"

    text = (
        f"{flag} {service_code} 📱 "
        f"{masked_number}\n\n"
        f"{safe_message}\n\n"
        f"🔐 Verification code hidden\n"
        f"⏳ Auto delete after 3 minutes"
    )

    if send_telegram_message(
        text,
        emoji
    ):

        save_processed_id(
            message_id
        )

        processed_ids.add(
            message_id
        )

        print(
            "✅ Processed:",
            message_id
        )

        return True

    print(
        "❌ Failed to send:",
        message_id
    )

    return False


# =========================================================
# CHECK REDX MESSAGES
# =========================================================

def check_messages():

    try:

        params = {
            "per_page": 30
        }

        response = requests.get(
            REDX_URL,
            headers=REDX_HEADERS,
            params=params,
            timeout=15,
        )

        print(
            "📡 RedX Status:",
            response.status_code
        )

        print(
            "📡 RedX Response:",
            response.text[:1000]
        )

        if response.status_code != 200:

            print(
                "❌ RedX API returned:",
                response.status_code
            )

            return

        result = response.json()

        messages = result.get(
            "data",
            []
        )

        print(
            f"📥 RedX messages received: "
            f"{len(messages)}"
        )

        if not messages:
            return

        processed_ids = (
            load_processed_ids()
        )

        sent = 0

        for item in messages:

            try:

                if process_message(
                    item,
                    processed_ids
                ):
                    sent += 1

            except Exception as e:

                print(
                    "❌ Message processing error:",
                    repr(e)
                )

        print(
            f"📤 This cycle sent: {sent}"
        )

    except requests.RequestException as e:

        print(
            "❌ RedX connection error:",
            repr(e)
        )

    except ValueError as e:

        print(
            "❌ RedX JSON error:",
            repr(e)
        )

    except Exception as e:

        print(
            "❌ Unexpected API error:",
            repr(e)
        )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print("=" * 50)
    print("🚀 RedX Telegram Notification Bot")
    print("=" * 50)

    print(
        "→ Checking pending messages..."
    )

    check_messages()

    print(
        f"→ Watching RedX every "
        f"{CHECK_INTERVAL} seconds..."
    )

    while True:

        try:

            check_messages()

        except Exception as e:

            print(
                "❌ Main loop error:",
                repr(e)
            )

        time.sleep(
            CHECK_INTERVAL
                   )
