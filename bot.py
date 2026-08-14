import os
import re
import json
import time
import asyncio
import logging
import requests
from typing import Dict, List, Set, Optional
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode

# ================== CONFIG ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_KEY = os.environ.get("API_KEY", "sk_live_1x7jN6OUqTIzUNEv7MIM9Er2h5GphCXer9ef4BUx")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8136997138"))

BASE_URL = "https://redxsms.com/api/v1/iprn"
MUST_JOIN_CHANNEL = "@Global_Method_Channel"
MUST_JOIN_CHANNEL_URL = "https://t.me/Global_Method_Channel"
OTP_GROUP = "-1004469160922"          # তোমার OTP গ্রুপ আইডি (লিংক না, আইডি দাও)
OTP_GROUP_LINK = "https://t.me/+ZFN7DCwaLmsxMGQx"
ADMIN_USERNAME = "Smart_Method_Owner"

REFERRAL_BONUS = 0.00189
OTP_BONUS = 0.00180
MIN_WITHDRAW = 2.0
NUMBER_RESERVE_TIME = 120  # 2 minutes

# ================== DATABASE (In-Memory) ==================
users_db: Dict[int, dict] = {}
numbers_db: Dict[str, Dict[str, List[str]]] = {}  # service -> country -> [numbers]
user_sessions: Dict[int, dict] = {}               # user_id -> session
withdrawal_requests: Dict[str, dict] = {}
processed_otps: Set[str] = set()

DEFAULT_SERVICES = ["WhatsApp", "Telegram", "Facebook", "TikTok", "1xBet"]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== HELPERS ==================
def get_user(user_id: int, username: str = "", first_name: str = "", ref_by: int = None) -> dict:
    if user_id not in users_db:
        users_db[user_id] = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "balance": 0.0,
            "ref_by": ref_by,
            "total_ref": 0,
            "total_otp": 0,
            "state": None,
            "temp_srv": None,
            "temp_cnt": None
        }
        if ref_by and ref_by in users_db and ref_by != user_id:
            users_db[ref_by]["balance"] += REFERRAL_BONUS
            users_db[ref_by]["total_ref"] += 1
    return users_db[user_id]

def clean_number(num: str) -> str:
    """Remove + and spaces"""
    return re.sub(r"[^\d]", "", num)

def format_number(num: str) -> str:
    """Always show with +"""
    num = clean_number(num)
    return f"+{num}"

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📱 Get Number")],
        [KeyboardButton("👤 Account"), KeyboardButton("🎁 Refer")],
        [KeyboardButton("💳 Withdraw"), KeyboardButton("❓ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def is_joined(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(MUST_JOIN_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return True  # fallback

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_by = int(args[0]) if args and args[0].isdigit() else None

    get_user(user.id, user.username or "", user.first_name or "", ref_by)

    if not await is_joined(context.bot, user.id):
        kb = [
            [InlineKeyboardButton("📢 Join Channel", url=MUST_JOIN_CHANNEL_URL)],
            [InlineKeyboardButton("✅ I Joined", callback_data="check_join")]
        ]
        await update.message.reply_text(
            f"👋 Welcome <b>{user.first_name}</b>!\n\n"
            f"বট ব্যবহার করতে অবশ্যই আমাদের চ্যানেলে জয়েন হতে হবে:\n"
            f"{MUST_JOIN_CHANNEL_URL}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    await update.message.reply_text(
        f"👋 Welcome <b>{user.first_name}</b>!\n\nনিচের মেনু থেকে অপশন সিলেক্ট করুন:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await is_joined(context.bot, query.from_user.id):
        await query.message.delete()
        await context.bot.send_message(
            query.from_user.id,
            "✅ জয়েন সম্পন্ন! এখন বট ব্যবহার করতে পারবেন।",
            reply_markup=get_main_keyboard()
        )
    else:
        await query.answer("❌ এখনো চ্যানেলে জয়েন হননি!", show_alert=True)

# ================== USER FEATURES ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    ud = get_user(user.id, user.username or "", user.first_name or "")

    # ----- Admin States -----
    if user.id == ADMIN_ID and ud.get("state"):
        state = ud["state"]

        if state == "WAITING_BROADCAST":
            ud["state"] = None
            count = 0
            for uid in list(users_db.keys()):
                try:
                    await context.bot.send_message(uid, text)
                    count += 1
                except:
                    pass
            await update.message.reply_text(f"✅ Broadcast পাঠানো হয়েছে → {count} জন")
            return

        if state.startswith("REJECT_"):
            req_id = state.replace("REJECT_", "")
            ud["state"] = None
            if req_id in withdrawal_requests:
                req = withdrawal_requests.pop(req_id)
                users_db[req["user_id"]]["balance"] += req["amount"]
                await context.bot.send_message(
                    req["user_id"],
                    f"❌ Withdraw রিকোয়েস্ট বাতিল করা হয়েছে।\n\nকারণ: {text}"
                )
                await update.message.reply_text("✅ রিজেক্ট মেসেজ পাঠানো হয়েছে")
            return

        if state == "ADD_NUMBERS":
            ud["state"] = None
            srv = ud.get("temp_srv")
            cnt = ud.get("temp_cnt")
            nums = re.findall(r"\+?\d{8,15}", text)
            if not nums:
                await update.message.reply_text("❌ কোনো নাম্বার পাওয়া যায়নি")
                return

            if srv not in numbers_db:
                numbers_db[srv] = {}
            if cnt not in numbers_db[srv]:
                numbers_db[srv][cnt] = []

            added = 0
            for n in nums:
                clean = clean_number(n)
                if clean not in numbers_db[srv][cnt]:
                    numbers_db[srv][cnt].append(clean)
                    added += 1

            await update.message.reply_text(f"✅ {added} টি নাম্বার যোগ করা হয়েছে!")

            # Notify all users
            notify = (
                f"🔔 <b>নতুন নাম্বার যোগ করা হয়েছে!</b>\n\n"
                f"Service: <b>{srv}</b>\n"
                f"Country: <b>{cnt}</b>\n"
                f"Added: <b>{added}</b> টি"
            )
            for uid in list(users_db.keys()):
                try:
                    await context.bot.send_message(uid, notify, parse_mode=ParseMode.HTML)
                except:
                    pass
            return

    # ----- Normal User Buttons -----
    if text == "📱 Get Number":
        kb = []
        row = []
        for s in DEFAULT_SERVICES:
            row.append(InlineKeyboardButton(s, callback_data=f"srv_{s}"))
            if len(row) == 2:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        await update.message.reply_text("📌 Service সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "👤 Account":
        msg = (
            f"👤 <b>Account Info</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"👤 Name: {user.first_name}\n"
            f"💰 Balance: <b>${ud['balance']:.5f}</b>\n"
            f"👥 Total Refer: {ud['total_ref']}\n"
            f"📩 Total OTP: {ud['total_otp']}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    elif text == "🎁 Refer":
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start={user.id}"
        await update.message.reply_text(
            f"🎁 <b>Referral System</b>\n\n"
            f"প্রতি রেফারে পাবেন: <b>${REFERRAL_BONUS}</b>\n\n"
            f"🔗 আপনার লিংক:\n<code>{link}</code>",
            parse_mode=ParseMode.HTML
        )

    elif text == "💳 Withdraw":
        if ud["balance"] < MIN_WITHDRAW:
            await update.message.reply_text(
                f"⚠️ মিনিমাম উইথড্র ${MIN_WITHDRAW}\n"
                f"আপনার ব্যালেন্স: ${ud['balance']:.5f}"
            )
            return
        kb = [
            [InlineKeyboardButton("Binance", callback_data="wd_Binance")],
            [InlineKeyboardButton("bKash", callback_data="wd_bKash"),
             InlineKeyboardButton("Nagad", callback_data="wd_Nagad")]
        ]
        await update.message.reply_text("💳 Method সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "❓ Help":
        kb = [[InlineKeyboardButton("👨‍💻 Admin", url=f"https://t.me/{ADMIN_USERNAME}")]]
        await update.message.reply_text("🆘 সাহায্যের জন্য অ্যাডমিনের সাথে যোগাযোগ করুন:", reply_markup=InlineKeyboardMarkup(kb))

# ================== CALLBACKS ==================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    ud = get_user(user.id)

    if data.startswith("srv_"):
        srv = data[4:]
        countries = list(numbers_db.get(srv, {}).keys()) or ["Bangladesh", "India", "USA", "Egypt", "Russia"]
        kb = [[InlineKeyboardButton(f"🏳️ {c}", callback_data=f"cnt_{srv}_{c}")] for c in countries]
        kb.append([InlineKeyboardButton("⬅️ Back", callback_data="back_services")])
        await query.edit_message_text(
            f"🌐 Service: <b>{srv}</b>\n\nCountry সিলেক্ট করুন:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data.startswith("cnt_"):
        parts = data.split("_", 2)
        srv = parts[1]
        cnt = parts[2]

        available = numbers_db.get(srv, {}).get(cnt, [])[:]
        # Remove numbers already reserved by others
        reserved = set()
        for sess in user_sessions.values():
            reserved.update(sess.get("numbers", []))
        available = [n for n in available if n not in reserved][:5]

        if not available:
            await query.edit_message_text("❌ এই কান্ট্রিতে এখন কোনো ফ্রি নাম্বার নেই।")
            return

        user_sessions[user.id] = {
            "service": srv,
            "country": cnt,
            "numbers": available,
            "time": time.time()
        }

        text = (
            f"🌐 <b>{srv}</b> | 🏳️ <b>{cnt}</b>\n"
            f"⏰ ২ মিনিটের জন্য রিজার্ভ করা হয়েছে\n\n"
            f"নিচের নাম্বারে ক্লিক করে কপি করুন:"
        )
        kb = [[InlineKeyboardButton(f"📋 {format_number(n)}", callback_data=f"copy_{n}")] for n in available]
        kb.append([InlineKeyboardButton("🔄 Change Number", callback_data=f"change_{srv}_{cnt}")])
        kb.append([InlineKeyboardButton("🌐 Change Country", callback_data=f"srv_{srv}")])
        kb.append([InlineKeyboardButton("📢 OTP Group", url=OTP_GROUP_LINK)])

        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        asyncio.create_task(release_after(user.id, NUMBER_RESERVE_TIME, context.bot))

    elif data.startswith("copy_"):
        num = data[5:]
        await query.answer(f"Copied: {format_number(num)}", show_alert=True)

    elif data.startswith("change_"):
        _, srv, cnt = data.split("_", 2)
        if user.id in user_sessions:
            del user_sessions[user.id]
        # Re-trigger
        query.data = f"cnt_{srv}_{cnt}"
        await callback_handler(update, context)

    elif data.startswith("wd_"):
        method = data[3:]
        amount = ud["balance"]
        if amount < MIN_WITHDRAW:
            await query.answer("অপর্যাপ্ত ব্যালেন্স", show_alert=True)
            return
        ud["balance"] = 0.0
        req_id = str(int(time.time()))
        withdrawal_requests[req_id] = {"user_id": user.id, "amount": amount, "method": method}

        kb = [[
            InlineKeyboardButton("✅ Accept", callback_data=f"acc_{req_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rej_{req_id}")
        ]]
        await context.bot.send_message(
            ADMIN_ID,
            f"📥 <b>Withdraw Request</b>\n\n"
            f"User: {user.first_name} (<code>{user.id}</code>)\n"
            f"Method: {method}\n"
            f"Amount: <b>${amount:.5f}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await query.edit_message_text("✅ রিকোয়েস্ট অ্যাডমিনের কাছে পাঠানো হয়েছে।")

    elif data.startswith("acc_"):
        if user.id != ADMIN_ID:
            return
        req_id = data[4:]
        if req_id in withdrawal_requests:
            req = withdrawal_requests.pop(req_id)
            await context.bot.send_message(
                req["user_id"],
                f"✅ আপনার <b>${req['amount']:.5f}</b> উইথড্র সফলভাবে প্রসেস করা হয়েছে!",
                parse_mode=ParseMode.HTML
            )
            await query.edit_message_text("✅ Accepted")

    elif data.startswith("rej_"):
        if user.id != ADMIN_ID:
            return
        req_id = data[4:]
        users_db[ADMIN_ID]["state"] = f"REJECT_{req_id}"
        await query.message.reply_text("📝 রিজেক্টের কারণ লিখে পাঠান:")

# ================== AUTO RELEASE ==================
async def release_after(user_id: int, delay: int, bot):
    await asyncio.sleep(delay)
    if user_id in user_sessions:
        del user_sessions[user_id]
        try:
            await bot.send_message(
                user_id,
                "⏰ আপনার নাম্বার রিজার্ভের সময় শেষ। নতুন নাম্বার নিতে <b>Get Number</b> চাপুন।",
                parse_mode=ParseMode.HTML
            )
        except:
            pass

# ================== ADMIN ==================
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ শুধু অ্যাডমিন!")
        return
    kb = [
        [InlineKeyboardButton("➕ Add Numbers", callback_data="adm_add")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="adm_bc")]
    ]
    await update.message.reply_text("⚙️ <b>Admin Panel</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    data = query.data

    if data == "adm_bc":
        users_db[ADMIN_ID]["state"] = "WAITING_BROADCAST"
        await query.message.reply_text("📢 Broadcast মেসেজ লিখে পাঠান:")

    elif data == "adm_add":
        kb = [[InlineKeyboardButton(s, callback_data=f"adm_srv_{s}")] for s in DEFAULT_SERVICES]
        await query.edit_message_text("Service সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("adm_srv_"):
        srv = data[8:]
        users_db[ADMIN_ID]["temp_srv"] = srv
        kb = [
            [InlineKeyboardButton("Bangladesh", callback_data=f"adm_cnt_{srv}_Bangladesh")],
            [InlineKeyboardButton("India", callback_data=f"adm_cnt_{srv}_India")],
            [InlineKeyboardButton("USA", callback_data=f"adm_cnt_{srv}_USA")],
            [InlineKeyboardButton("Egypt", callback_data=f"adm_cnt_{srv}_Egypt")],
            [InlineKeyboardButton("Russia", callback_data=f"adm_cnt_{srv}_Russia")],
        ]
        await query.edit_message_text(f"Service: <b>{srv}</b>\nCountry সিলেক্ট করুন:", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("adm_cnt_"):
        parts = data.split("_", 3)
        srv, cnt = parts[2], parts[3]
        users_db[ADMIN_ID]["temp_srv"] = srv
        users_db[ADMIN_ID]["temp_cnt"] = cnt
        users_db[ADMIN_ID]["state"] = "ADD_NUMBERS"
        await query.edit_message_text(
            f"📝 <b>{srv} → {cnt}</b>\n\nনাম্বারগুলো লিখে পাঠান (এক লাইনে বা একাধিক):",
            parse_mode=ParseMode.HTML
        )

# ================== OTP POLLING ==================
async def otp_polling(app: Application):
    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    while True:
        try:
            r = requests.get(f"{BASE_URL}/messages", headers=headers, params={"per_page": 20}, timeout=10)
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    mid = str(item.get("id") or item.get("received_at") or "")
                    if not mid or mid in processed_otps:
                        continue

                    raw = str(item.get("number", "")).strip()
                    body = item.get("message", "") or ""
                    otp_match = re.search(r"\b\d{3,8}\b", body)
                    otp = otp_match.group(0) if otp_match else "N/A"

                    text = (
                        f"📩 <b>New OTP</b>\n\n"
                        f"📱 Number: <code>{format_number(raw)}</code>\n"
                        f"🔑 OTP: <code>{otp}</code>\n"
                        f"💬 {body}"
                    )

                    # Send to group
                    try:
                        await app.bot.send_message(OTP_GROUP, text, parse_mode=ParseMode.HTML)
                    except Exception as e:
                        logger.error(f"Group send error: {e}")

                    # Send to reserved user
                    for uid, sess in list(user_sessions.items()):
                        if any(raw.endswith(n) or n in raw for n in sess.get("numbers", [])):
                            try:
                                await app.bot.send_message(uid, text, parse_mode=ParseMode.HTML)
                                users_db[uid]["balance"] += OTP_BONUS
                                users_db[uid]["total_otp"] += 1
                            except:
                                pass
                            break

                    processed_otps.add(mid)
        except Exception as e:
            logger.error(f"Polling error: {e}")

        await asyncio.sleep(3)
# ================== MAIN ==================
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN missing")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(check_join, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(admin_cb, pattern="^adm_"))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Start OTP polling
    async def post_init(application: Application):
        asyncio.create_task(otp_polling(application))

    app.post_init = post_init

    print("🚀 Bot is running...")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
