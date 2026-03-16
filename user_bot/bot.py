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
from shared.storage import get_user, set_user, get_admin_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_BOT_TOKEN  = os.environ["USER_BOT_TOKEN"]
ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]
ADMIN_CHAT_ID   = int(os.environ["ADMIN_CHAT_ID"])

bot       = telebot.TeleBot(USER_BOT_TOKEN)
admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)

PAYMENT_INSTRUCTIONS = """
💰 *Price:* $1 per check — 1 USDT or 130 Kshs

📋 *How it works*
1️⃣ Pay for your check
2️⃣ Send payment proof or reference
3️⃣ Upload your document 📄
4️⃣ Receive your AI & Plag reports 📊

💳 *Payment Options*
📱 M-Pesa: `0799023325`
🔶 USDC (Solana): `BNoFmzZxuR1DWPsG8yUfQppEJ95guwGCCzZBKfeMiUP1`
💎 USDT (TRC20): `TYf8HUV4tXtvhSviLKzKyeZQqGHoMg889E`

⭐ *Reviews & Announcements*
https://t.me/reviewstransactions

🎁 *Bonus:* Bring 2 clients and get 1 free check from support.
🛠 *Support:* @daemonizerr
""".strip()

FOLLOWUP_DELAY = 3 * 60  # 3 minutes before follow-up message


def get_status_line():
    if get_admin_status() == "online":
        return "\n\n🟢 Online"
    return "\n\n🔴 Offline"


def send_followup(chat_id):
    """Wait 3 minutes then send a follow-up message."""
    time.sleep(FOLLOWUP_DELAY)
    profile = get_user(chat_id)
    submissions = profile.get("submissions", 0)

    if submissions > 0:
        bot.send_message(
            chat_id,
            f"📄 *Ready for your next document?*\n"
            f"You have *{submissions} submission(s)* remaining — go ahead and upload your file!",
            parse_mode="Markdown",
        )
    else:
        bot.send_message(
            chat_id,
            "✅ *All submissions used.*\n"
            "Use /start to submit a new document.",
            parse_mode="Markdown",
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
        "username":  user.username or "",
        "full_name": full_name,
        "status":    "pending_payment",
        "submissions": 0,
    })
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"👋 Welcome back, {user.first_name}!\n\n"
        "Let's get your next document checked.\n\n"
        + PAYMENT_INSTRUCTIONS + get_status_line(),
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
        "submissions": 0,
    })
    bot.send_message(
        message.chat.id,
        f"👋 Welcome, {user.first_name}!\n\n"
        + PAYMENT_INSTRUCTIONS + get_status_line(),
        parse_mode="Markdown",
    )


@bot.message_handler(content_types=["document"])
def handle_document(message):
    user    = message.from_user
    profile = get_user(user.id)
    status  = profile.get("status", "pending_payment")

    if status != "approved":
        msgs = {
            "pending_payment":  "❌ Please send your payment reference or screenshot first.",
            "pending_approval": "⏳ Still waiting for payment verification. Please hold on.",
            "doc_received":     "⏳ We already have your document. Your report will be ready in 5–15 minutes!",
            "report_sent":      "✅ Your report was already sent. Use /start to submit a new document.",
        }
        bot.send_message(message.chat.id, msgs.get(status, "❌ Not authorised yet."))
        return

    full_name   = profile.get("full_name", user.first_name)
    submissions = profile.get("submissions", 1)
    doc         = message.document

    # Deduct one submission
    new_count = max(0, submissions - 1)
    set_user(user.id, {
        "status":      "doc_received",
        "file_id":     doc.file_id,
        "file_name":   doc.file_name,
        "submissions": new_count,
    })

    file_info  = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    admin_bot.send_message(
        ADMIN_CHAT_ID,
        f"📄 *Document Received*\n\n"
        f"👤 {full_name}  |  ID: `{user.id}`\n"
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
        f"📨 *Document received!*\n"
        f"⏱ Your report will be ready in approximately *5–15 minutes.*\n"
        f"📂 Submissions remaining: *{new_count}*",
        parse_mode="Markdown",
    )


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    user    = message.from_user
    profile = get_user(user.id)
    status  = profile.get("status", "pending_payment")

    if status in ("pending_payment", "pending_approval"):
        photo_id   = message.photo[-1].file_id
        file_info  = bot.get_file(photo_id)
        downloaded = bot.download_file(file_info.file_path)
        admin_bot.send_photo(
            ADMIN_CHAT_ID,
            downloaded,
            caption=(
                f"🖼 *Payment Screenshot*\n\n"
                f"👤 {profile.get('full_name', user.first_name)}  |  ID: `{user.id}`\n"
                f"Ref Code: `{profile.get('ref_code', 'not sent yet')}`\n\n"
                f"Use `/approve {user.id} <submissions>` or `/reject {user.id}`."
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
            f"Use `/approve {user.id} <submissions>` to unlock their upload.",
            parse_mode="Markdown",
        )
        bot.send_message(
            message.chat.id,
            f"✅ Reference code *{ref}* received!\n\n"
            "Our team will verify your payment shortly and notify you here. 📄",
            parse_mode="Markdown",
        )
    elif status == "approved":
        submissions = profile.get("submissions", 0)
        bot.send_message(
            message.chat.id,
            f"📎 You're approved! Please *send your document as a file* (PDF or Word).\n"
            f"📂 Submissions remaining: *{submissions}*",
            parse_mode="Markdown",
        )
    elif status == "doc_received":
        bot.send_message(message.chat.id, "⏳ Your document is being reviewed. Your report will be ready in 5–15 minutes!")
    elif status == "report_sent":
        submissions = profile.get("submissions", 0)
        if submissions > 0:
            bot.send_message(
                message.chat.id,
                f"📄 *Ready for your next document?*\n"
                f"You have *{submissions} submission(s)* remaining — go ahead and upload your file!",
                parse_mode="Markdown",
            )
        else:
            bot.send_message(
                message.chat.id,
                "✅ *All submissions used.*\n"
                "Use /start to submit a new document.",
                parse_mode="Markdown",
            )
    else:
        bot.send_message(message.chat.id, "Please complete payment and send your reference code to proceed.")


def main():
    logger.info("User bot running...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
