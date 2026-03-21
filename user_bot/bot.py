"""
USER BOT  –  student-facing side
Role: notifications only. All input goes through the Mini App.
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

WEBAPP_URL     = os.environ.get("WEBAPP_URL", "https://the-dark-knightt.github.io/k/webapp/index.html")
FOLLOWUP_DELAY = 3 * 60


def get_status_line():
    if get_admin_status() == "online":
        return "\n\n🟢 Online — we'll respond quickly!"
    return "\n\n🔴 Currently offline — we'll get back to you soon."


def open_app_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "📱 Open App",
        web_app=telebot.types.WebAppInfo(url=WEBAPP_URL)
    ))
    return markup


def send_followup(chat_id):
    time.sleep(FOLLOWUP_DELAY)
    profile     = get_user(chat_id)
    submissions = profile.get("submissions", 0)
    if submissions > 0:
        bot.send_message(
            chat_id,
            f"📄 *Ready for your next document?*\n"
            f"You have *{submissions} submission(s)* remaining.\n"
            f"Tap below to open the app and upload!",
            parse_mode="Markdown",
            reply_markup=open_app_markup(),
        )
    else:
        bot.send_message(
            chat_id,
            "✅ *All submissions used.*\n"
            "Open the app to get more checks.",
            parse_mode="Markdown",
            reply_markup=open_app_markup(),
        )


def notify_report_sent(chat_id):
    t = threading.Thread(target=send_followup, args=(chat_id,), daemon=True)
    t.start()


# ── /start ────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message):
    user      = message.from_user
    full_name = user.first_name + (" " + user.last_name if user.last_name else "")
    existing  = get_user(user.id)
    existing_subs   = existing.get("submissions", 0)
    existing_status = existing.get("status", "pending_payment")

    if existing_subs > 0 and existing_status in ("approved", "report_sent"):
        set_user(user.id, {
            "username":  user.username or "",
            "full_name": full_name,
            "status":    "approved",
        })
        bot.send_message(
            message.chat.id,
            f"👋 Welcome back, *{user.first_name}!*\n\n"
            f"📂 You still have *{existing_subs} submission(s)* remaining.\n"
            f"Tap below to open the app and upload your document!",
            parse_mode="Markdown",
            reply_markup=open_app_markup(),
        )
        return

    set_user(user.id, {
        "username":    user.username or "",
        "full_name":   full_name,
        "status":      existing_status,
        "submissions": existing_subs,
    })

    bot.send_message(
        message.chat.id,
        f"👋 Welcome, *{user.first_name}!*\n\n"
        "I generate *AI & Plagiarism Reports* for your documents.\n\n"
        "📱 Open the app below — pay, submit proof, and upload your document all in one place."
        + get_status_line(),
        parse_mode="Markdown",
        reply_markup=open_app_markup(),
    )


# ── All text / file messages → redirect to app ────────────────────────────────

@bot.message_handler(func=lambda m: True, content_types=["text", "photo", "document"])
def handle_any(message):
    profile = get_user(message.from_user.id)
    status  = profile.get("status", "pending_payment")

    nudge_map = {
        "pending_payment":  "👆 Open the app to pay and submit your reference code.",
        "pending_approval": "⏳ Your payment is being verified. We'll notify you here shortly!",
        "approved":         "📎 Open the app to upload your document.",
        "doc_received":     "⏳ Your document is being reviewed — report ready in 5–15 minutes!",
        "report_sent":      "✅ Your report was sent. Open the app to start a new check.",
    }
    msg = nudge_map.get(status, "Please use the app below to continue.")
    bot.send_message(message.chat.id, msg, reply_markup=open_app_markup())


def main():
    logger.info("User bot running...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
