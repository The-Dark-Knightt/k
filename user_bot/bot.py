"""
USER BOT  –  student-facing side
Role: notifications only. All input goes through the Mini App.
"""

import logging
import os
import sys
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

WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://the-dark-knightt.github.io/k/webapp/index.html")


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


def notify_report_sent(chat_id):
    pass  # follow-up removed — admin_bot handles post-delivery message


# ── /start ────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(message):
    user      = message.from_user
    full_name = user.first_name + (" " + user.last_name if user.last_name else "")
    existing  = get_user(user.id)
    existing_subs   = existing.get("submissions", 0)
    existing_status = existing.get("status", "pending_payment")

    set_user(user.id, {
        "username":    user.username or "",
        "full_name":   full_name,
        "status":      existing_status,
        "submissions": existing_subs,
    })

    status = get_admin_status()
    online = "🟢 Online" if status == "online" else "🔴 Offline"

    bot.send_message(
        message.chat.id,
        f"👋 Hi {user.first_name}! Open the app below — $1 per check, results in 5–15 min. {online}",
        reply_markup=open_app_markup(),
    )


# ── All text / file messages → redirect to app ────────────────────────────────

@bot.message_handler(func=lambda m: True, content_types=["text", "photo", "document"])
def handle_any(message):
    msg = "Use the app to upload or reach support: @daemonizerr"
    bot.send_message(message.chat.id, msg, reply_markup=open_app_markup())


def main():
    logger.info("User bot running...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
