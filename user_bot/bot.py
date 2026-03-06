"""
USER BOT – student-facing side
"""

import logging
import os
import sys
import threading
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.insert(0, os.path.join(os.path.dirname(**file**), ".."))
from shared.storage import get_user, set_user, get_admin_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(**name**)

USER_BOT_TOKEN = os.environ["USER_BOT_TOKEN"]
ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])

bot = telebot.TeleBot(USER_BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

PAYMENT_INSTRUCTIONS = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 _HOW IT WORKS_
━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ Make your payment
2️⃣ Send your payment reference here
3️⃣ Wait for confirmation ✅
4️⃣ Upload your document(s) 📄
5️⃣ Receive your report 📊
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 _PRICING_
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 _$1 per document check_
Accepted as: _1 USDT_ 0R _130 Kshs_
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💳 _PAYMENT OPTIONS_
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 _M-Pesa:_ `0799023325`
🔶 _Binance Pay ID:_ `2938399390`
USDT (Tron(trc20): TYf8HUV4tXtvhSviLKzKyeZQqGHoMg889E
━━━━━━━━━━━━━━━━━━━━━━━━━━━
➡️ _Once paid, send your payment reference number OR a screenshot of your payment here to proceed!_
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Support _@daemonizerr_
""".strip()

def get_status_line():
if get_admin_status() == "online":
return "\n🟢 Online"
return ""

FOLLOWUP_DELAY = 3 \* 60 # 3 minutes before follow-up message
COLLECT_SECONDS = 30 # seconds to wait for more files after first upload

# Multi-file upload tracking per user

user_files = {} # {user_id: [(file_id, file_name), ...]}
user_timers = {} # {user_id: Timer}

# ── Follow-up after report ─────────────────────────────────────────────────────

def send_followup(chat_id):
time.sleep(FOLLOWUP_DELAY)
markup = InlineKeyboardMarkup()
markup.add(InlineKeyboardButton("📄 Start New Check", callback_data="new_check"))
bot.send_message(
chat_id,
"🔄 _Need another check?_\n\n"
"Tap the button below to submit a new document!",
parse_mode="Markdown",
reply_markup=markup,
)

def notify_report_sent(chat_id):
"""Called by admin bot after sending report — triggers the follow-up message."""
t = threading.Thread(target=send_followup, args=(chat_id,), daemon=True)
t.start()

@bot.callback_query_handler(func=lambda call: call.data == "new_check")
def handle_new_check(call):
user = call.from_user
full_name = user.first_name + (" " + user.last_name if user.last_name else "")
set_user(user.id, {
"username": user.username or "",
"full_name": full_name,
"status": "pending_payment",
})
bot.answer_callback_query(call.id)
bot.send_message(
call.message.chat.id,
f"👋 Welcome back, {user.first_name}!\n\n"
"Let's get your next document checked.\n\n" + PAYMENT_INSTRUCTIONS + get_status_line(),
parse_mode="Markdown",
)

# ── Multi-file upload finalizer ────────────────────────────────────────────────

def \_finalize_upload(user_id, chat_id, full_name):
"""Called after COLLECT_SECONDS — forwards all collected files to admin."""
files = user_files.pop(user_id, [])
user_timers.pop(user_id, None)

    if not files:
        return

    total = len(files)

    # Notify admin
    admin_bot.send_message(
        ADMIN_CHAT_ID,
        f"📄 *{total} Document(s) Received*\n\n"
        f"👤 {full_name}  |  ID: `{user_id}`\n"
        f"📎 Files: {', '.join(n for _, n in files)}\n\n"
        f"When done, use:\n`/sendreport {user_id}` and attach the report(s).",
        parse_mode="Markdown",
    )

    for file_id, file_name in files:
        file_info  = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        admin_bot.send_document(
            ADMIN_CHAT_ID,
            downloaded,
            visible_file_name=file_name,
            caption=f"📎 From {full_name} (ID: {user_id})",
        )

    set_user(user_id, {"status": "doc_received"})

    bot.send_message(
        chat_id,
        f"📨 *{total} document(s) received!*\n\n"
        f"⏱ Your report will be ready in approximately *5-15 minutes*. "
        f"We'll send it here as soon as it's done! ✅",
        parse_mode="Markdown",
    )

# ── Handlers ───────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message):
user = message.from_user
full_name = user.first_name + (" " + user.last_name if user.last_name else "")
set_user(user.id, {
"username": user.username or "",
"full_name": full_name,
"status": "pending_payment",
})
bot.send_message(
message.chat.id,
f"👋 Welcome, {user.first_name}!\n\n"
"This bot lets you submit documents for _AI & plagiarism checking_.\n\n"
"To get started, please complete a payment first.\n\n" + PAYMENT_INSTRUCTIONS + get_status_line(),
parse_mode="Markdown",
)

@bot.message_handler(content_types=["document"])
def handle_document(message):
user = message.from_user
profile = get_user(user.id)
status = profile.get("status", "pending_payment")

    if status != "approved":
        msgs = {
            "pending_payment":  "❌ Please send your reference code first.",
            "pending_approval": "⏳ Still waiting for payment verification. Please wait.",
            "doc_received":     "⏳ We already have your document(s). Please wait for your report.",
            "report_sent":      "✅ Your report was already sent. Use /start to submit a new document.",
        }
        bot.send_message(message.chat.id, msgs.get(status, "❌ Not authorised yet."))
        return

    full_name = profile.get("full_name", user.first_name)
    doc = message.document

    # Only allow one file

doc = message.document
set_user(user.id, {"status": "doc_received", "file_id": doc.file_id, "file_name": doc.file_name})

file_info = bot.get_file(doc.file_id)
downloaded = bot.download_file(file_info.file_path)
admin_bot.send_message(
ADMIN_CHAT_ID,
f"📄 _Document Received_\n\n"
f"👤 {full_name} | ID: `{user.id}`\n"
f"📎 File: {doc.file_name}\n\n"
f"When done, use:\n`/sendreport {user.id}` and attach the report.",
parse_mode="Markdown",
)
admin_bot.send_document(
ADMIN_CHAT_ID,
downloaded,
visible_file_name=doc.file_name,
caption=f"📎 From {full_name} (ID: {user.id})",
)
bot.send_message(
message.chat.id,
"📨 _Document received!_\n\n"
"⏱ Your report will be ready in approximately _5–15 minutes_. "
"We'll send it here as soon as it's done! ✅",
parse_mode="Markdown",
)

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
user = message.from_user
profile = get_user(user.id)
status = profile.get("status", "pending_payment")

    if status in ("pending_payment", "pending_approval"):
        # Forward screenshot to admin
        photo_id = message.photo[-1].file_id
        file_info = bot.get_file(photo_id)
        downloaded = bot.download_file(file_info.file_path)
        admin_bot.send_photo(
            ADMIN_CHAT_ID,
            downloaded,
            caption=(
                f"🖼 *Payment Screenshot*\n\n"
                f"👤 {profile.get('full_name', user.first_name)}  |  ID: `{user.id}`\n"
                f"Ref Code: `{profile.get('ref_code', 'not sent yet')}`\n\n"
                f"Use `/approve {user.id}` or `/reject {user.id}`."
            ),
            parse_mode="Markdown",
        )
        set_user(user.id, {"status": "pending_approval"})
        bot.send_message(
            message.chat.id,
            "🖼 *Payment screenshot received!*\n\n"
            "Our team will verify your payment shortly and notify you here. ✅",
            parse_mode="Markdown",
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ Please send your document as a *file* (PDF or Word), not as a photo.",
            parse_mode="Markdown",
        )

@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
user = message.from_user
text = message.text.strip()
profile = get_user(user.id)
status = profile.get("status", "pending_payment")

    if status in ("pending_payment", "pending_approval"):
        ref = text.upper()
        set_user(user.id, {"status": "pending_approval", "ref_code": ref})
        admin_bot.send_message(
            ADMIN_CHAT_ID,
            f"🔔 *New Ref Code Submitted*\n\n"
            f"👤 Name: {profile.get('full_name', user.first_name)}\n"
            f"🆔 User ID: `{user.id}`\n"
            f"🔑 Ref Code: `{ref}`\n\n"
            f"Use `/approve {user.id}` to unlock their upload.",
            parse_mode="Markdown",
        )
        bot.send_message(
            message.chat.id,
            f"✅ Reference code *{ref}* received!\n\n"
            "Our team will verify your payment shortly and notify you here. 📄",
            parse_mode="Markdown",
        )
    elif status == "approved":
        bot.send_message(
            message.chat.id,
            "📎 You're approved! Please *send your document(s) as files* (PDF or Word).\n\n"
            "You can send multiple files — just send them one after another!",
            parse_mode="Markdown",
        )
    elif status == "doc_received":
        bot.send_message(message.chat.id, "⏳ Your document(s) are being reviewed. We'll send your report in ~15 minutes!")
    elif status == "report_sent":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📄 Start New Check", callback_data="new_check"))
        bot.send_message(
            message.chat.id,
            "✅ Your report has already been sent!\n\nWant to check another document?",
            reply_markup=markup,
        )
    else:
        bot.send_message(message.chat.id, "Please complete payment and send your reference code to proceed.")

def main():
logger.info("User bot running...")
bot.infinity_polling()

if **name** == "**main**":
main()
