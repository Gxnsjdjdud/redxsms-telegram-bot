import os
import re
import json
import time
import asyncio
import logging
import requests
from typing import Dict, List, Set

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config from Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_KEY = os.environ.get("API_KEY", "sk_live_1x7jN6OUqTIzUNEv7MIM9Er2h5GphCXer9ef4BUx")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8136997138"))

BASE_URL = "https://redxsms.com/api/v1/iprn"
MUST_JOIN_CHANNEL = "@Global_Method_Channel"
MUST_JOIN_CHANNEL_URL = "https://t.me/Global_Method_Channel"
OTP_GROUP_LINK = "https://t.me/+ZFN7DCwaLmsxMGQx"
ADMIN_USERNAME = "Smart_Method_Owner"

REFERRAL_BONUS = 0.00189
OTP_BONUS = 0.00180
MIN_WITHDRAW = 2.0

# In-Memory Database (For production, connecting MongoDB/SQLite is recommended)
users_db: Dict[int, dict] = {}
numbers_db: Dict[str, dict] = {}  # {service: {country: [numbers]}}
user_sessions: Dict[int, dict] = {}  # {user_id: {"service": str, "country": str, "numbers": list, "timestamp": float}}
withdrawal_requests: Dict[str, dict] = {}

# Allowed default services
DEFAULT_SERVICES = ["Whatsapp", "Telegram", "Facebook", "Tiktok", "1xbet"]

# ----------------- Helper Functions ----------------- #

def get_user(user_id: int, username: str = "", ref_by: int = None) -> dict:
    if user_id not in users_db:
        users_db[user_id] = {
            "user_id": user_id,
            "username": username,
            "balance": 0.0,
            "ref_by": ref_by,
            "total_ref": 0,
            "total_otp": 0,
            "state": None
        }
        if ref_by and ref_by in users_db and ref_by != user_id:
            users_db[ref_by]["balance"] += REFERRAL_BONUS
            users_db[ref_by]["total_ref"] += 1
    return users_db[user_id]

async def is_subscribed(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=MUST_JOIN_CHANNEL, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        logger.error(f"Channel Check Error: {e}")
        return True  # Fallback if channel access fails

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📱 Get Number")],
        [KeyboardButton("👤 Account"), KeyboardButton("🎁 Refer")],
        [KeyboardButton("💳 Withdraw"), KeyboardButton("❓ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ----------------- Command Handlers ----------------- #

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_by = int(args[0]) if args and args[0].isdigit() else None

    get_user(user.id, user.username, ref_by)

    # Check Channel Subscription
    subscribed = await is_subscribed(context.bot, user.id)
    if not subscribed:
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=MUST_JOIN_CHANNEL_URL)],
            [InlineKeyboardButton("✅ Joined / Check", callback_data="check_join")]
        ]
        await update.message.reply_text(
            f"👋 Welcome {user.first_name}!\n\n"
            f"⚠️ বটে কাজ শুরু করার জন্য আপনাকে অবশ্যই আমাদের চ্যানেলে জয়েন হতে হবে:\n{MUST_JOIN_CHANNEL_URL}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await update.message.reply_text(
        f"👋 Welcome {user.first_name} to OTP Bot!\nনিচের মেনু থেকে আপনার অপশন সিলেক্ট করুন:",
        reply_markup=get_main_keyboard()
    )

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    subscribed = await is_subscribed(context.bot, user.id)
    if subscribed:
        await query.message.delete()
        await context.bot.send_message(
            chat_id=user.id,
            text="✅ ধন্যবাদ! আপনি সঠিকভাবে জয়েন করেছেন।",
            reply_markup=get_main_keyboard()
        )
    else:
        await query.answer("❌ আপনি এখনো চ্যানেলে জয়েন হননি! দয়া করে জয়েন করুন।", show_alert=True)

# ----------------- User Keyboards & Features ----------------- #

async def handle_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    user_data = get_user(user.id, user.username)

    # Admin State Checking
    if user.id == ADMIN_ID and user_data.get("state"):
        state = user_data["state"]
        if state == "WAITING_BROADCAST":
            user_data["state"] = None
            await update.message.reply_text("📢 Broadcast শুরু হয়েছে...")
            count = 0
            for uid in list(users_db.keys()):
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                    count += 1
                except:
                    pass
            await update.message.reply_text(f"✅ মোট {count} জন ইউজারকে বার্তা পাঠানো হয়েছে।")
            return

        elif state.startswith("REJECT_WITHDRAW_"):
            req_id = state.replace("REJECT_WITHDRAW_", "")
            user_data["state"] = None
            if req_id in withdrawal_requests:
                req = withdrawal_requests.pop(req_id)
                target_user = req["user_id"]
                amount = req["amount"]
                users_db[target_user]["balance"] += amount  # Refund

                await context.bot.send_message(
                    chat_id=target_user,
                    text=f"❌ আপনার ${amount} Withdraw রিকোয়েস্টটি বাতিল করা হয়েছে।\n\n📌 কারণ: {text}"
                )
                await update.message.reply_text("✅ রিজেক্ট মেসেজ ইউজারের কাছে পাঠানো হয়েছে।")
            return

        elif state == "ADD_NUMBERS_INPUT":
            user_data["state"] = None
            # Extract numbers from text
            raw_numbers = re.findall(r'\+?\d{8,15}', text)
            if not raw_numbers:
                await update.message.reply_text("❌ কোনো সঠিক নম্বর পাওয়া যায়নি।")
                return

            srv = user_data.get("temp_srv")
            cnt = user_data.get("temp_cnt")

            if srv not in numbers_db:
                numbers_db[srv] = {}
            if cnt not in numbers_db[srv]:
                numbers_db[srv][cnt] = []

            added_count = 0
            for num in raw_numbers:
                clean_num = num.strip().replace("+", "")
                if clean_num not in numbers_db[srv][cnt]:
                    numbers_db[srv][cnt].append(clean_num)
                    added_count += 1

            await update.message.reply_text(f"✅ {added_count} টি নম্বর সফলভাবে যোগ করা হয়েছে!")

            # Notify All Users
            notify_text = (
                f"🔔 **নতুন নম্বর যুক্ত করা হয়েছে!**\n\n"
                f"🌐 Service: {srv}\n"
                f"🏳️ Country: {cnt}\n"
                f"🔢 Total Added: {added_count} টি"
            )
            for uid in list(users_db.keys()):
                try:
                    await context.bot.send_message(chat_id=uid, text=notify_text, parse_mode="Markdown")
                except:
                    pass
            return

    # User Button Handlers
    if text == "📱 Get Number":
        keyboard = []
        row = []
        for srv in DEFAULT_SERVICES:
            row.append(InlineKeyboardButton(srv, callback_data=f"select_srv_{srv}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        await update.message.reply_text("📌 আপনার কাঙ্ক্ষিত Service টি নির্বাচন করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "👤 Account":
        msg = (
            f"👤 **User Info**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 User ID: `{user.id}`\n"
            f"👤 Username: @{user.username or 'N/A'}\n"
            f"💰 Balance: `${user_data['balance']:.5f}`\n"
            f"👥 Total Refer: `{user_data['total_ref']}`\n"
            f"📩 Total OTP Received: `{user_data['total_otp']}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "🎁 Refer":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user.id}"
        msg = (
            f"🎁 **Referral System**\n\n"
            f"আপনার বন্ধুকে ইনভাইট করুন এবং প্রতিটি রেফারেলের জন্য পাবেন `${REFERRAL_BONUS}`!\n\n"
            f"🔗 Ref Link:\n`{ref_link}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "💳 Withdraw":
        if user_data['balance'] < MIN_WITHDRAW:
            await update.message.reply_text(f"⚠️ মিনিমাম উইথড্র `${MIN_WITHDRAW}`। আপনার বর্তমান ব্যালেন্স: `${user_data['balance']:.5f}`")
            return

        keyboard = [
            [InlineKeyboardButton("Binance", callback_data="w_method_Binance")],
            [InlineKeyboardButton("bKash", callback_data="w_method_bKash"), InlineKeyboardButton("Nagad", callback_data="w_method_Nagad")]
        ]
        await update.message.reply_text("💳 Withdraw Method সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "❓ Help":
        keyboard = [[InlineKeyboardButton("👨‍💻 Admin", url=f"https://t.me/{ADMIN_USERNAME}")]]
        await update.message.reply_text("🆘 যেকোনো সহায়তার জন্য অ্যাডমিনের সাথে যোগাযোগ করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

# ----------------- Service & Number Callbacks ----------------- #

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data.startswith("select_srv_"):
        srv = data.replace("select_srv_", "")
        # Get countries for this service
        countries = list(numbers_db.get(srv, {}).keys())
        if not countries:
            countries = ["Bangladesh", "India", "USA"]  # Fallback options

        keyboard = []
        for c in countries:
            keyboard.append([InlineKeyboardButton(f"🏳️ {c}", callback_data=f"select_cnt_{srv}_{c}")])

        await query.message.edit_text(f"🌐 Service: **{srv}**\n📌 এখন Country নির্বাচন করুন:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("select_cnt_"):
        _, _, srv, cnt = data.split("_", 3)

        # Allocate 5 numbers
        available_nums = numbers_db.get(srv, {}).get(cnt, [])
        allocated = available_nums[:5]

        # Update Session
        user_sessions[user.id] = {
            "service": srv,
            "country": cnt,
            "numbers": allocated,
            "timestamp": time.time()
        }

        # Format number display
        text_msg = f"🌐 Service: **{srv}** | 🏳️ Country: **{cnt}**\n"
        text_msg += "⏰ **এই নম্বরগুলো ২ মিনিটের জন্য আপনার নিকট রিজার্ভ থাকবে:**\n\n"

        keyboard = []
        for num in allocated:
            keyboard.append([InlineKeyboardButton(f"📋 +{num}", callback_data=f"copy_{num}")])

        keyboard.append([InlineKeyboardButton("🔄 Change Numbers", callback_data=f"change_num_{srv}_{cnt}")])
        keyboard.append([InlineKeyboardButton("🌐 Change Country", callback_data=f"select_srv_{srv}")])
        keyboard.append([InlineKeyboardButton("📢 OTP Group", url=OTP_GROUP_LINK)])

        await query.message.edit_text(text_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

        # Schedule auto release in 2 minutes (120 sec)
        asyncio.create_task(auto_release_numbers(user.id, 120))

    elif data.startswith("copy_"):
        num = data.replace("copy_", "")
        await query.answer(f"Copied: +{num}", show_alert=True)

    elif data.startswith("change_num_"):
        _, _, srv, cnt = data.split("_", 3)
        # Release existing and fetch new
        if user.id in user_sessions:
            del user_sessions[user.id]
        
        # Trigger same selection
        query.data = f"select_cnt_{srv}_{cnt}"
        await callback_handler(update, context)

    elif data.startswith("w_method_"):
        method = data.replace("w_method_", "")
        user_data = get_user(user.id)
        amount = user_data["balance"]

        if amount < MIN_WITHDRAW:
            await query.answer("⚠️ অপর্যাপ্ত ব্যালেন্স!", show_alert=True)
            return

        user_data["balance"] = 0.0  # Deduct
        req_id = str(int(time.time()))
        withdrawal_requests[req_id] = {
            "user_id": user.id,
            "amount": amount,
            "method": method
        }

        # Notify Admin
        admin_keyboard = [
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"admin_accept_{req_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{req_id}")
            ]
        ]
        admin_text = (
            f"📥 **নতুন উইথড্র রিকোয়েস্ট!**\n\n"
            f"👤 User: {user.first_name} (`{user.id}`)\n"
            f"💳 Method: {method}\n"
            f"💰 Amount: `${amount:.5f}`"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(admin_keyboard))
        await query.message.edit_text("✅ আপনার উইথড্র রিকোয়েস্ট অ্যাডমিনের কাছে পাঠানো হয়েছে।")

    # Admin Actions
    elif data.startswith("admin_accept_"):
        if user.id != ADMIN_ID: return
        req_id = data.replace("admin_accept_", "")
        if req_id in withdrawal_requests:
            req = withdrawal_requests.pop(req_id)
            await context.bot.send_message(
                chat_id=req["user_id"],
                text=f"✅ আপনার `${req['amount']}` উইথড্র রিকোয়েস্টটি সফলভাবে প্রসেস করা হয়েছে!"
            )
            await query.message.edit_text("✅ Accept করা হয়েছে।")

    elif data.startswith("admin_reject_"):
        if user.id != ADMIN_ID: return
        req_id = data.replace("admin_reject_", "")
        users_db[ADMIN_ID]["state"] = f"REJECT_WITHDRAW_{req_id}"
        await query.message.reply_text("📝 রিজেক্ট করার কারণ লিখে পাঠান:")

async def auto_release_numbers(user_id: int, delay: int):
    await asyncio.sleep(delay)
    if user_id in user_sessions:
        del user_sessions[user_id]
        try:
            await Application.get_default().bot.send_message(
                chat_id=user_id,
                text="⏰ আপনার রিজার্ভকৃত নম্বরের সময়সীমা শেষ হয়েছে। নতুন নম্বর নিতে `Get Number` বাটন প্রেস করুন।"
            )
        except:
            pass

# ----------------- Admin Panel Commands ----------------- #

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ এটি কেবল অ্যাডমিনের জন্য সংরক্ষিত কমান্ড!")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Numbers", callback_data="admin_add_num_srv")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")]
    ]
    await update.message.reply_text("⚙️ **Admin Control Panel**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user

    if user.id != ADMIN_ID:
        await query.answer("Unauthorized", show_alert=True)
        return

    if data == "admin_broadcast":
        users_db[ADMIN_ID]["state"] = "WAITING_BROADCAST"
        await query.message.reply_text("📢 ব্রডকাস্ট মেসেজটি লিখে পাঠান:")

    elif data == "admin_add_num_srv":
        keyboard = []
        for srv in DEFAULT_SERVICES:
            keyboard.append([InlineKeyboardButton(srv, callback_data=f"adm_select_srv_{srv}")])
        await query.message.edit_text("📌 কোন সার্ভিস এ নম্বর যুক্ত করবেন?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("adm_select_srv_"):
        srv = data.replace("adm_select_srv_", "")
        users_db[ADMIN_ID]["temp_srv"] = srv

        keyboard = [
            [InlineKeyboardButton("Bangladesh", callback_data=f"adm_select_cnt_{srv}_Bangladesh")],
            [InlineKeyboardButton("India", callback_data=f"adm_select_cnt_{srv}_India")],
            [InlineKeyboardButton("USA", callback_data=f"adm_select_cnt_{srv}_USA")]
        ]
        await query.message.edit_text(f"🌐 Service: **{srv}**\n📌 Country সিলেক্ট করুন:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("adm_select_cnt_"):
        _, _, srv, cnt = data.split("_", 3)
        users_db[ADMIN_ID]["temp_srv"] = srv
        users_db[ADMIN_ID]["temp_cnt"] = cnt
        users_db[ADMIN_ID]["state"] = "ADD_NUMBERS_INPUT"

        await query.message.edit_text(
            f"📝 **{srv} ({cnt})** এর জন্য নম্বরগুলো লিখে পাঠান।\n"
            f"টেক্সট আকারে অথবা একাধিক নম্বর একসাথে পাঠাতে পারেন।"
        )

# ----------------- RedXSMS Polling Task ----------------- #

async def poll_redxsms_messages(app: Application):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }
    processed_ids: Set[str] = set()

    while True:
        try:
            response = requests.get(f"{BASE_URL}/messages", headers=headers, params={'per_page': 15}, timeout=10)
            if response.status_code == 200:
                messages = response.json().get("data", [])
                for item in reversed(messages):
                    msg_id = str(item.get("id", item.get("received_at", "")))
                    if not msg_id or msg_id in processed_ids:
                        continue

                    raw_number = str(item.get("number", "")).strip()
                    msg_body = item.get("message", "") or ""

                    otp_match = re.search(r'\b\d{3}[-\s]?\d{3}\b|\b\d{4,8}\b', msg_body)
                    otp_code = otp_match.group(0) if otp_match else "N/A"

                    # Check who owns this number
                    assigned_user = None
                    for uid, sess in user_sessions.items():
                        if any(raw_number.endswith(num) for num in sess["numbers"]):
                            assigned_user = uid
                            break

                    out_text = f"📩 **New OTP Received!**\n\n📱 Number: `+{raw_number}`\n🔑 Code: `{otp_code}`\n💬 Message: {msg_body}"

                    # Send to OTP Group
                    try:
                        await app.bot.send_message(chat_id=OTP_GROUP_LINK, text=out_text, parse_mode="Markdown")
                    except Exception as e:
                        logger.error(f"Group OTP Send Error: {e}")

                    # Send to specific user if assigned
                    if assigned_user:
                        try:
                            await app.bot.send_message(chat_id=assigned_user, text=out_text, parse_mode="Markdown")
                            users_db[assigned_user]["balance"] += OTP_BONUS
                            users_db[assigned_user]["total_otp"] += 1
                        except Exception as e:
                            logger.error(f"User OTP Send Error: {e}")

                    processed_ids.add(msg_id)

        except Exception as e:
            logger.error(f"RedXSMS API Error: {e}")

        await asyncio.sleep(3)

# ----------------- Main App Setup ----------------- #

def main():
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN is missing!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^adm_"))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_input))

    # Background task for OTP polling
    loop = asyncio.get_event_loop()
    loop.create_task(poll_redxsms_messages(app))

    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
