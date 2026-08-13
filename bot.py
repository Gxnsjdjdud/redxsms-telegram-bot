import os
import re
import time
import threading
import requests

from datetime import timezone, timedelta


# =========================================================
# CONFIG
# =========================================================

API_KEY = os.environ["API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

CHAT_ID = "-1004469160922"

REDX_URL = "https://redxsms.com/api/v1/iprn/messages"

REDX_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
}

PROCESSED_IDS_FILE = "processed_ids.txt"

# IMPORTANT:
# Do not poll RedX every 4 seconds.
NORMAL_INTERVAL = 30

# Minimum wait after an API error
ERROR_INTERVAL = 60

# Safety margin added to RedX Retry-After
RETRY_MARGIN = 3

DELETE_AFTER = 180

BD_TZ = timezone(timedelta(hours=6))


# =========================================================
# PROCESSED IDS
# =========================================================

def load_processed_ids():
    try:
        if not os.path.exists(PROCESSED_IDS_FILE):
            return set()

        with open(
            PROCESSED_IDS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return {
                line.strip()
                for line in file
                if line.strip()
            }

    except Exception as e:
        print(
            "❌ Could not load processed IDs:",
            repr(e)
        )

        return set()


def save_processed_id(message_id):

    try:

        with open(
            PROCESSED_IDS_FILE,
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                str(message_id) + "\n"
            )

    except Exception as e:

        print(
            "❌ Could not save processed ID:",
            repr(e)
        )


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
        "358": "🇫🇮",
        "30": "🇬🇷",
        "36": "🇭🇺",
        "40": "🇷🇴",
        "420": "🇨🇿",
        "421": "🇸🇰",
        "380": "🇺🇦",
    }

    number = re.sub(
        r"\D",
        "",
        str(number)
    )

    for code in sorted(
        flags,
        key=len,
        reverse=True
    ):

        if number.startswith(code):
            return flags[code]

    return "🌐"


# =========================================================
# SERVICE
# =========================================================

def get_service(item, message):

    service = ""

    fields = [
        "service",
        "app",
        "service_name",
        "name",
        "title",
        "gateway",
    ]

    for key in fields:

        value = item.get(key)

        if value:

            value = str(
                value
            ).strip().lower()

            if value and value != "none":

                service = value
                break

    if not service:

        text = message.upper()

        detection = {
            "TELEGRAM": "telegram",
            "WHATSAPP": "whatsapp",
            "GOOGLE": "google",
            "FACEBOOK": "facebook",
            "IMO": "imo",
            "VIBER": "viber",
        }

        for keyword, name in detection.items():

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
# MASK SENSITIVE INFORMATION
# =========================================================

def mask_sensitive_codes(text):

    if not text:
        return ""

    # 4-8 digit codes
    text = re.sub(
        r"\b\d{4,8}\b",
        lambda match: "*" * len(
            match.group(0)
        ),
        text
    )

    # 123-456 / 123 456
    text = re.sub(
        r"\b\d{3}[-\s]\d{3}\b",
        "******",
        text
    )

    return text


def mask_phone(number):

    number = str(number).strip()

    if len(number) <= 4:
        return "****"

    return (
        "*" * (len(number) - 4)
        + number[-4:]
    )


# =========================================================
# TELEGRAM DELETE
# =========================================================

def delete_message_later(
    chat_id,
    message_id
):

    time.sleep(
        DELETE_AFTER
    )

    try:

        url = (
            "https://api.telegram.org/"
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
            "🗑 Delete:",
            response.status_code,
            response.text
        )

    except Exception as e:

        print(
            "❌ Delete error:",
            repr(e)
        )


# =========================================================
# TELEGRAM SEND
# =========================================================

def send_telegram_message(
    text
):

    url = (
        "https://api.telegram.org/"
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
            url,
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
                "❌ Telegram rejected message"
            )

            return False

        message_id = (
            data["result"]["message_id"]
        )

        print(
            "✅ Telegram sent:",
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
            "❌ Telegram error:",
            repr(e)
        )

        return False


# =========================================================
# PROCESS MESSAGE
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

        print(
            "⚠️ Message has no ID"
        )

        return False

    if message_id in processed_ids:

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

    flag = get_country_flag(
        number
    )

    service_code, emoji = get_service(
        item,
        message
    )

    safe_message = mask_sensitive_codes(
        message
    )

    masked_number = mask_phone(
        number
    )

    text = (
        f"{flag} {service_code} "
        f"📱 {masked_number}\n\n"
        f"{safe_message}\n\n"
        f"🔐 Verification code hidden\n"
        f"⏳ Auto delete after 3 minutes"
    )

    success = send_telegram_message(
        text
    )

    if success:

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

    return False


# =========================================================
# PARSE RETRY TIME FROM REDX
# =========================================================

def get_retry_after(response):

    retry_seconds = None

    # First try Retry-After HTTP header

    header_value = response.headers.get(
        "Retry-After"
    )

    if header_value:

        try:

            retry_seconds = int(
                float(header_value)
            )

        except Exception:
            pass

    # Then inspect JSON error message

    if retry_seconds is None:

        try:

            data = response.json()

            message = (
                data
                .get("error", {})
                .get("message", "")
            )

            match = re.search(
                r"Retry after\s+(\d+)\s+seconds",
                message,
                re.IGNORECASE
            )

            if match:

                retry_seconds = int(
                    match.group(1)
                )

        except Exception:
            pass

    if retry_seconds is None:
        retry_seconds = ERROR_INTERVAL

    # Safety margin

    retry_seconds += RETRY_MARGIN

    # Never retry immediately

    return max(
        retry_seconds,
        10
    )


# =========================================================
# REDX REQUEST
# =========================================================

def fetch_messages():

    try:

        response = requests.get(
            REDX_URL,
            headers=REDX_HEADERS,
            params={
                "per_page": 30
            },
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

        # Rate limit

        if response.status_code == 429:

            retry_after = get_retry_after(
                response
            )

            print(
                f"⏳ RedX rate limit."
                f" Waiting {retry_after} seconds..."
            )

            return None, retry_after

        # Other errors

        if response.status_code != 200:

            print(
                "❌ RedX API error:",
                response.status_code
            )

            return None, ERROR_INTERVAL

        try:

            result = response.json()

        except ValueError:

            print(
                "❌ RedX returned invalid JSON"
            )

            return None, ERROR_INTERVAL

        messages = result.get(
            "data",
            []
        )

        return messages, NORMAL_INTERVAL

    except requests.RequestException as e:

        print(
            "❌ RedX connection error:",
            repr(e)
        )

        return None, ERROR_INTERVAL

    except Exception as e:

        print(
            "❌ RedX request error:",
            repr(e)
        )

        return None, ERROR_INTERVAL


# =========================================================
# CHECK MESSAGES
# =========================================================

def check_messages():

    messages, next_wait = fetch_messages()

    if messages is None:

        return next_wait

    print(
        f"📥 RedX messages: "
        f"{len(messages)}"
    )

    if not messages:

        return NORMAL_INTERVAL

    processed_ids = load_processed_ids()

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
                "❌ Processing error:",
                repr(e)
            )

    print(
        f"📤 Sent notifications: {sent}"
    )

    return NORMAL_INTERVAL


# =========================================================
# MAIN LOOP
# =========================================================

if __name__ == "__main__":

    print("=" * 55)
    print("🚀 RedX Telegram Notification Bot")
    print("=" * 55)

    print(
        "⚙️ Rate-limit protection enabled"
    )

    print(
        f"⚙️ Normal interval: "
        f"{NORMAL_INTERVAL} seconds"
    )

    print(
        "→ First API check..."
    )

    wait_time = check_messages()

    while True:

        try:

            print(
                f"😴 Sleeping {wait_time} seconds..."
            )

            time.sleep(
                wait_time
            )

            wait_time = check_messages()

        except KeyboardInterrupt:

            print(
                "🛑 Bot stopped"
            )

            break

        except Exception as e:

            print(
                "❌ Main loop error:",
                repr(e)
            )

            wait_time = ERROR_INTERVAL
