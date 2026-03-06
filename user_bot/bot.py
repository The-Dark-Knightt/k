"""
USER BOT  –  student-facing side
"""

import logging
import os
import sys
import threading
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.storage import get_user, set_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_BOT_TOKEN  = os.environ["USER_BOT_TOKEN"]
ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]
ADMIN_CHAT_ID   = int(os.environ["ADMIN_CHAT_ID"])

bot       = telebot.TeleBot(USER_BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

PAYMENT_INSTRUCTIONS = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 *HOW IT WORKS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ Make your payment
2️⃣ Send your payment reference here
3️⃣ Wait for confirmation ✅
4️⃣ Upload your document 📄
5️⃣ Receive your report 📊
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *PRICING*
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 *$1 per document check*
Accepted as: *1 USDT* or *1 USDC*
━━━━━━━━━━━━━━━━━━━━━━━━━━━
💳 *PAYMENT OPTIONS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 *M-Pesa:*
`0799023325`
🔶 *Binance Pay ID:*
`2938399390`
━━━━━━━━━━━━━━━━━━━━━━━━━━━
➡️ *Once paid, send your payment reference number here to proceed!*
━━━━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()

FOLLOWUP_DELAY = 3 * 60  # 3 minutes in seconds


def send_followup(chat_id):
    """Wait 3 minutes then send a follow-up message with a Start New Check button."""
    time.sleep(FOLLOWUP_DELAY)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📄 Start New Check", callback_data="new_check"))
    bot.send_message(
        chat_id,
        "🔄 *Need another check?*\n\n"
        "Tap the button below to submit a new document!",
        parse_mode="Markdown",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data == "new_check")
def handle_new_check(call):
    """Handle the Start New Check button tap."""
    user = call.from_user
    full_name = user.first_name + (" " + user.last_name if user.last_name else "")
    set_user(user.id, {
        "username":  user.username or "",
        "full_name": full_name,
        "status":    "pending_payment",
    })
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"👋 Welcome back, {user.first_name}!\n\n"
        "Let's get your next document checked.\n\n"
        + PAYMENT_INSTRUCTIONS,
        parse_mode="Markdown",
    )


@bot.message_handler(commands=["start"])
def cmd_start(message):
    user = message.from_user
    full_name = user.first_name + (" " + user.last_name if user.last_name else "")
    set_user(user.id, {
        "username":  user.username or "",
        "full_name": full_name,
        "status":    "pending_payment",
    })
    bot.send_message(
        message.chat.id,
        f"👋 Welcome, {user.first_name}!\n\n"
        "This bot lets you submit documents for *AI & plagiarism checking*.\n\n"
        "To get started, please complete a payment first.\n\n"
        + PAYMENT_INSTRUCTIONS,
        parse_mode="Markdown",
    )


@bot.message_handler(content_types=["document"])
def handle_document(message):
    user    = message.from_user
    profile = get_user(user.id)
    status  = profile.get("status", "pending_payment")

    if status != "approved":
        msgs = {
            "pending_payment":  "❌ Please send your reference code first.",
            "pending_approval": "⏳ Still waiting for payment verification. Please wait.",
            "doc_received":     "⏳ We already have your document. Please wait for your report.",
            "report_sent":      "✅ Your report was already sent. Use /start to submit a new document.",
        }
        bot.send_message(message.chat.id, msgs.get(status, "❌ Not authorised yet."))
        return

    doc = message.document
    set_user(user.id, {"status": "doc_received", "file_id": doc.file_id, "file_name": doc.file_name})

    admin_bot.send_message(
        ADMIN_CHAT_ID,
        f"📄 *Document Received*\n\n"
        f"👤 {profile.get('full_name', user.first_name)}  |  ID: `{user.id}`\n"
        f"📎 File: {doc.file_name}\n\n"
        f"When done, use:\n`/sendreport {user.id}` and attach the report.",
        parse_mode="Markdown",
    )
    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    admin_bot.send_document(
        ADMIN_CHAT_ID,
        downloaded,
        visible_file_name=doc.file_name,
        caption=f"📎 From {profile.get('full_name', user.first_name)} (ID: {user.id})",
    )

    bot.send_message(
        message.chat.id,
        "📨 Your document has been received! We'll send your report within 5 - 15 min. ✅"
    )


def notify_report_sent(chat_id):
    """Called by admin bot after sending report — triggers the follow-up message."""
    t = threading.Thread(target=send_followup, args=(chat_id,), daemon=True)
    t.start()


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    user    = message.from_user
    text    = message.text.strip()
    profile = get_user(user.id)
    status  = profile.get("status", "pending_payment")

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
        bot.send_message(message.chat.id, "📎 You're approved! Please *send your document as a file* (PDF or Word).", parse_mode="Markdown")
    elif status == "doc_received":
        bot.send_message(message.chat.id, "⏳ Your document is being reviewed. We'll send your report soon!")
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


if __name__ == "__main__":
    main()
