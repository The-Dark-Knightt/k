"""
ADMIN BOT – your private control panel
Commands:
  /pending              - list users waiting for approval
  /approve <user_id>    - approve a user
  /reject <user_id>     - reject a user
  /status <user_id>     - check a user's status
  /list                 - see all users
  /sendreport <user_id> - then send a file to deliver report
  /help                 - show commands
"""

import logging
import os
import sys
import telebot

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.storage import get_user, set_user, all_users, set_admin_status, get_admin_status

# Delay import to avoid circular imports
def _notify_report_sent(chat_id):
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from user_bot.bot import notify_report_sent
        notify_report_sent(chat_id)
    except Exception as e:
        pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]
USER_BOT_TOKEN  = os.environ["USER_BOT_TOKEN"]
ADMIN_CHAT_ID   = int(os.environ["ADMIN_CHAT_ID"])

bot      = telebot.TeleBot(ADMIN_BOT_TOKEN)
user_bot = telebot.TeleBot(USER_BOT_TOKEN)

# Track pending report deliveries: {admin_chat_id: user_id}
pending_reports = {}
# Track files already sent per session: {admin_chat_id: [file_ids]}
pending_files = {}
# Track timers that finalize delivery: {admin_chat_id: Timer}
pending_timers = {}

COLLECT_SECONDS = 30  # seconds to wait for more files after first one

STATUS_EMOJI = {
    "pending_payment":  "💳",
    "pending_approval": "🕐",
    "approved":         "✅",
    "doc_received":     "📄",
    "report_sent":      "📨",
}


def admin_only(func):
    def wrapper(message):
        if message.chat.id != ADMIN_CHAT_ID:
            return
        func(message)
    return wrapper


@bot.message_handler(commands=["pending"])
@admin_only
def cmd_pending(message):
    users = all_users()
    pending = {uid: u for uid, u in users.items() if u.get("status") == "pending_approval"}
    if not pending:
        bot.send_message(message.chat.id, "✅ No users are currently waiting for approval.")
        return
    lines = ["*Users Pending Approval:*\n"]
    for uid, u in pending.items():
        lines.append(f"👤 {u.get('full_name', 'Unknown')}  |  ID: `{uid}`\n   Ref: `{u.get('ref_code', 'N/A')}`\n   Use: `/approve {uid}`\n")
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=["approve"])
@admin_only
def cmd_approve(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: `/approve <user_id>`", parse_mode="Markdown")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID.")
        return

    profile = get_user(user_id)
    if not profile:
        bot.send_message(message.chat.id, "❌ User not found.")
        return

    set_user(user_id, {"status": "approved"})
    user_bot.send_message(
        user_id,
        "🎉 *Your payment has been verified!*\n\n"
        "You are now authorised to submit your document.\n\n"
        "📎 Please send your document as a file (PDF or Word).",
        parse_mode="Markdown",
    )
    bot.send_message(message.chat.id, f"✅ User `{user_id}` ({profile.get('full_name', '')}) approved and notified.", parse_mode="Markdown")


@bot.message_handler(commands=["reject"])
@admin_only
def cmd_reject(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: `/reject <user_id>`", parse_mode="Markdown")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID.")
        return

    profile = get_user(user_id)
    if not profile:
        bot.send_message(message.chat.id, "❌ User not found.")
        return

    set_user(user_id, {"status": "pending_payment"})
    user_bot.send_message(
        user_id,
        "❌ *We could not verify your payment.*\n\n"
        "Please double-check your payment and send the correct reference code.",
        parse_mode="Markdown",
    )
    bot.send_message(message.chat.id, f"🚫 User `{user_id}` rejected and notified.", parse_mode="Markdown")


@bot.message_handler(commands=["status"])
@admin_only
def cmd_status(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: `/status <user_id>`", parse_mode="Markdown")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID.")
        return

    profile = get_user(user_id)
    if not profile:
        bot.send_message(message.chat.id, "❌ User not found.")
        return

    status = profile.get("status", "unknown")
    emoji  = STATUS_EMOJI.get(status, "❓")
    bot.send_message(
        message.chat.id,
        f"*User `{user_id}`*\nName: {profile.get('full_name', 'N/A')}\nRef: `{profile.get('ref_code', 'N/A')}`\nStatus: {emoji} `{status}`\nFile: {profile.get('file_name', 'none')}",
        parse_mode="Markdown",
    )


@bot.message_handler(commands=["list"])
@admin_only
def cmd_list(message):
    users = all_users()
    if not users:
        bot.send_message(message.chat.id, "No users yet.")
        return
    lines = ["*All Users:*\n"]
    for uid, u in users.items():
        status = u.get("status", "unknown")
        emoji  = STATUS_EMOJI.get(status, "❓")
        lines.append(f"{emoji} `{uid}` – {u.get('full_name', 'N/A')} – `{status}`")
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=["sendreport"])
@admin_only
def cmd_sendreport(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: `/sendreport <user_id>` then send the file.", parse_mode="Markdown")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID.")
        return

    profile = get_user(user_id)
    if not profile:
        bot.send_message(message.chat.id, "❌ User not found.")
        return

    pending_reports[message.chat.id] = user_id
    bot.send_message(
        message.chat.id,
        f"📎 Now send the report file for user `{user_id}` ({profile.get('full_name', '')}).",
        parse_mode="Markdown",
    )




@bot.message_handler(commands=["online"])
@admin_only
def cmd_online(message):
    set_admin_status("online")
    bot.send_message(message.chat.id, "🟢 Status set to *Online*. Users will see you as online.", parse_mode="Markdown")


@bot.message_handler(commands=["offline"])
@admin_only
def cmd_offline(message):
    set_admin_status("offline")
    bot.send_message(message.chat.id, "⚫ Status set to *Offline*. Users will no longer see the online indicator.", parse_mode="Markdown")

@bot.message_handler(commands=["help"])
@admin_only
def cmd_help(message):
    bot.send_message(
        message.chat.id,
        "*Admin Commands*\n\n"
        "/pending – users waiting for approval\n"
        "/approve `<id>` – approve & notify user\n"
        "/reject `<id>` – reject & notify user\n"
        "/status `<id>` – check one user's status\n"
        "/list – see all users\n"
        "/sendreport `<id>` – then send file to deliver report\n",
        parse_mode="Markdown",
    )


def _finalize_report(admin_chat_id):
    """Called after COLLECT_SECONDS — delivers all collected files to user."""
    import threading
    user_id = pending_reports.pop(admin_chat_id, None)
    files   = pending_files.pop(admin_chat_id, [])
    pending_timers.pop(admin_chat_id, None)

    if not user_id or not files:
        return

    profile = get_user(user_id)
    total   = len(files)

    for i, (file_id, file_name) in enumerate(files):
        file_info  = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        caption = (
            f"📋 *Your AI & Plagiarism Check Report is ready!*\n\nPlease review the attached document carefully. ✅"
            if i == 0 else f"📎 File {i+1} of {total}"
        )
        user_bot.send_document(
            user_id,
            downloaded,
            visible_file_name=file_name,
            caption=caption,
            parse_mode="Markdown",
        )

    set_user(user_id, {"status": "report_sent"})
    _notify_report_sent(user_id)
    bot.send_message(
        admin_chat_id,
        f"✅ {total} file(s) delivered to user `{user_id}` ({profile.get('full_name', '')}).",
        parse_mode="Markdown",
    )


@bot.message_handler(content_types=["document"])
@admin_only
def handle_admin_document(message):
    import threading
    if message.chat.id not in pending_reports:
        bot.send_message(message.chat.id, "ℹ️ Use `/sendreport <user_id>` before sending a file.", parse_mode="Markdown")
        return

    admin_chat_id = message.chat.id

    # Collect the file
    if admin_chat_id not in pending_files:
        pending_files[admin_chat_id] = []
    pending_files[admin_chat_id].append((message.document.file_id, message.document.file_name))

    # Cancel existing timer and restart it
    if admin_chat_id in pending_timers:
        pending_timers[admin_chat_id].cancel()

    count = len(pending_files[admin_chat_id])
    bot.send_message(
        admin_chat_id,
        f"📎 File {count} received. Send more files or wait {COLLECT_SECONDS}s to deliver all to user.",
    )

    timer = threading.Timer(COLLECT_SECONDS, _finalize_report, args=[admin_chat_id])
    timer.daemon = True
    timer.start()
    pending_timers[admin_chat_id] = timer


def main():
    logger.info("Admin bot running...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()

# Patch: add /done command to finalize early
@bot.message_handler(commands=["done"])
@admin_only
def cmd_done(message):
    if message.chat.id not in pending_reports:
        bot.send_message(message.chat.id, "ℹ️ No active report session. Use `/sendreport <user_id>` first.", parse_mode="Markdown")
        return
    if message.chat.id in pending_timers:
        pending_timers[message.chat.id].cancel()
    _finalize_report(message.chat.id)
