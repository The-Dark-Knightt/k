"""
ADMIN BOT – button-driven control panel
Stores delivered reports in webapp_api so users can download from the app.
"""

import logging
import os
import sys
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.storage import get_user, set_user, all_users, set_admin_status, get_admin_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]
USER_BOT_TOKEN  = os.environ["USER_BOT_TOKEN"]
ADMIN_CHAT_ID   = int(os.environ["ADMIN_CHAT_ID"])

WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://the-dark-knightt.github.io/k/webapp/index.html")

bot      = telebot.TeleBot(ADMIN_BOT_TOKEN)
user_bot = telebot.TeleBot(USER_BOT_TOKEN)

pending_reports  = {}
pending_files    = {}
pending_timers   = {}
pending_approval = {}

COLLECT_SECONDS = 30

STATUS_EMOJI = {
    "pending_payment":  "💳",
    "pending_approval": "🕐",
    "approved":         "✅",
    "doc_received":     "📄",
    "report_sent":      "📨",
}


def _open_app_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "📱 Open App", web_app=telebot.types.WebAppInfo(url=WEBAPP_URL)
    ))
    return markup


def _notify_user_report_sent(chat_id):
    try:
        from user_bot.bot import notify_report_sent
        notify_report_sent(chat_id)
    except Exception:
        pass


def _store_report_in_api(user_id, files):
    try:
        from webapp_api import store_report
        store_report(user_id, files)
    except Exception:
        pass


def admin_only(func):
    def wrapper(message):
        if message.chat.id != ADMIN_CHAT_ID:
            return
        func(message)
    return wrapper


def admin_only_callback(func):
    def wrapper(call):
        if call.message.chat.id != ADMIN_CHAT_ID:
            return
        func(call)
    return wrapper


# ── Main Menu ─────────────────────────────────────────────────────────────────

def main_menu_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📋 Pending",   callback_data="menu_pending"),
        InlineKeyboardButton("👥 All Users", callback_data="menu_list"),
        InlineKeyboardButton("🟢 Online",    callback_data="menu_online"),
        InlineKeyboardButton("🔴 Offline",   callback_data="menu_offline"),
    )
    return markup


@bot.message_handler(commands=["start", "menu"])
@admin_only
def cmd_menu(message):
    status = get_admin_status()
    line   = "🟢 You are currently *Online*" if status == "online" else "🔴 You are currently *Offline*"
    bot.send_message(
        message.chat.id,
        f"👋 *Admin Panel*\n\n{line}\n\nWhat would you like to do?",
        parse_mode="Markdown",
        reply_markup=main_menu_markup(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "menu_main")
@admin_only_callback
def cb_main_menu(call):
    status = get_admin_status()
    line   = "🟢 You are currently *Online*" if status == "online" else "🔴 You are currently *Offline*"
    bot.edit_message_text(
        f"👋 *Admin Panel*\n\n{line}\n\nWhat would you like to do?",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=main_menu_markup(),
    )
    bot.answer_callback_query(call.id)


# ── Online / Offline ──────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data == "menu_online")
@admin_only_callback
def cb_online(call):
    set_admin_status("online")
    bot.answer_callback_query(call.id, "🟢 You are now Online")
    bot.edit_message_text(
        "👋 *Admin Panel*\n\n🟢 You are currently *Online*\n\nWhat would you like to do?",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=main_menu_markup(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "menu_offline")
@admin_only_callback
def cb_offline(call):
    set_admin_status("offline")
    bot.answer_callback_query(call.id, "🔴 You are now Offline")
    bot.edit_message_text(
        "👋 *Admin Panel*\n\n🔴 You are currently *Offline*\n\nWhat would you like to do?",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=main_menu_markup(),
    )


# ── Pending ───────────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data == "menu_pending")
@admin_only_callback
def cb_pending(call):
    users   = all_users()
    pending = {uid: u for uid, u in users.items() if u.get("status") == "pending_approval"}
    bot.answer_callback_query(call.id)

    if not pending:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="menu_main"))
        bot.edit_message_text(
            "✅ No users are currently waiting for approval.",
            call.message.chat.id, call.message.message_id, reply_markup=markup,
        )
        return

    lines = ["*Users Pending Approval:*\n"]
    for uid, u in pending.items():
        lines.append(
            f"👤 {u.get('full_name', 'Unknown')}  |  ID: `{uid}`\n"
            f"   Ref: `{u.get('ref_code', 'N/A')}`\n"
        )
    markup = InlineKeyboardMarkup(row_width=1)
    for uid, u in pending.items():
        markup.add(InlineKeyboardButton(
            f"👤 {u.get('full_name', 'Unknown')} — Approve / Reject",
            callback_data=f"user_action_{uid}"
        ))
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="menu_main"))
    bot.edit_message_text(
        "\n".join(lines), call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=markup,
    )


# ── All Users ─────────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data == "menu_list")
@admin_only_callback
def cb_list(call):
    users = all_users()
    bot.answer_callback_query(call.id)
    if not users:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="menu_main"))
        bot.edit_message_text("No users yet.", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return

    lines = ["*All Users:*\n"]
    for uid, u in users.items():
        status      = u.get("status", "unknown")
        emoji       = STATUS_EMOJI.get(status, "❓")
        submissions = u.get("submissions", 0)
        lines.append(f"{emoji} `{uid}` – {u.get('full_name', 'N/A')} – `{status}` – {submissions} sub(s)")

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="menu_main"))
    bot.edit_message_text(
        "\n".join(lines), call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=markup,
    )


# ── User Action ───────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data.startswith("user_action_"))
@admin_only_callback
def cb_user_action(call):
    user_id = int(call.data.split("_")[2])
    profile = get_user(user_id)
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{user_id}"),
        InlineKeyboardButton("⬅️ Back",   callback_data="menu_pending"),
    )
    bot.edit_message_text(
        f"👤 *{profile.get('full_name', 'Unknown')}*\n"
        f"🆔 ID: `{user_id}`\n"
        f"🔑 Ref: `{profile.get('ref_code', 'N/A')}`\n\n"
        f"What would you like to do?",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
@admin_only_callback
def cb_approve(call):
    user_id = int(call.data.split("_")[1])
    profile = get_user(user_id)
    bot.answer_callback_query(call.id)
    pending_approval[call.message.chat.id] = user_id
    markup = InlineKeyboardMarkup(row_width=4)
    markup.add(
        InlineKeyboardButton("1", callback_data=f"subs_{user_id}_1"),
        InlineKeyboardButton("2", callback_data=f"subs_{user_id}_2"),
        InlineKeyboardButton("3", callback_data=f"subs_{user_id}_3"),
        InlineKeyboardButton("5", callback_data=f"subs_{user_id}_5"),
    )
    markup.add(InlineKeyboardButton("✏️ Custom number", callback_data=f"subs_{user_id}_custom"))
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data=f"user_action_{user_id}"))
    bot.edit_message_text(
        f"✅ Approving *{profile.get('full_name', 'Unknown')}*\n\nHow many submissions to allocate?",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("subs_") and not call.data.endswith("_custom"))
@admin_only_callback
def cb_set_submissions(call):
    parts       = call.data.split("_")
    user_id     = int(parts[1])
    submissions = int(parts[2])
    profile     = get_user(user_id)
    bot.answer_callback_query(call.id)
    set_user(user_id, {"status": "approved", "submissions": submissions})
    user_bot.send_message(
        user_id,
        f"✅ *Payment verified!*\n"
        f"You've been allocated *{submissions} submission(s).*\n\n"
        f"📱 Open the app to upload your document!",
        parse_mode="Markdown",
        reply_markup=_open_app_markup(),
    )
    pending_approval.pop(call.message.chat.id, None)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_main"))
    bot.edit_message_text(
        f"✅ *{profile.get('full_name', 'Unknown')}* approved with *{submissions} submission(s)*.",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("subs_") and call.data.endswith("_custom"))
@admin_only_callback
def cb_custom_submissions(call):
    user_id = int(call.data.split("_")[1])
    bot.answer_callback_query(call.id)
    pending_approval[call.message.chat.id] = user_id
    bot.edit_message_text(
        "✏️ Enter the number of submissions for this user:",
        call.message.chat.id, call.message.message_id,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
@admin_only_callback
def cb_reject(call):
    user_id = int(call.data.split("_")[1])
    profile = get_user(user_id)
    bot.answer_callback_query(call.id)
    set_user(user_id, {"status": "pending_payment"})
    user_bot.send_message(
        user_id,
        "❌ *We could not verify your payment.*\n\n"
        "Please double-check and resubmit via the app.",
        parse_mode="Markdown",
        reply_markup=_open_app_markup(),
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_main"))
    bot.edit_message_text(
        f"🚫 *{profile.get('full_name', 'Unknown')}* rejected and notified.",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=markup,
    )


# ── Send Report ───────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data.startswith("sendreport_"))
@admin_only_callback
def cb_sendreport(call):
    user_id = int(call.data.split("_")[1])
    profile = get_user(user_id)
    bot.answer_callback_query(call.id)
    pending_reports[call.message.chat.id] = user_id
    bot.send_message(
        call.message.chat.id,
        f"📎 Send the report file(s) for *{profile.get('full_name', 'Unknown')}* (`{user_id}`).\n"
        f"Send all files then type /done or wait {COLLECT_SECONDS}s to deliver automatically.",
        parse_mode="Markdown",
    )


@bot.message_handler(content_types=["document"])
@admin_only
def handle_admin_document(message):
    if message.chat.id not in pending_reports:
        bot.send_message(
            message.chat.id,
            "ℹ️ Tap *Send Report* on a document notification first, or use /sendreport `<user_id>`.",
            parse_mode="Markdown",
        )
        return

    admin_chat_id = message.chat.id
    if admin_chat_id not in pending_files:
        pending_files[admin_chat_id] = []

    file_info  = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    pending_files[admin_chat_id].append((downloaded, message.document.file_name or "report"))

    if admin_chat_id in pending_timers:
        pending_timers[admin_chat_id].cancel()

    count = len(pending_files[admin_chat_id])
    bot.send_message(
        admin_chat_id,
        f"📎 File {count} received. Send more or wait {COLLECT_SECONDS}s. Type /done to deliver now.",
    )

    timer = threading.Timer(COLLECT_SECONDS, _finalize_report, args=[admin_chat_id])
    timer.daemon = True
    timer.start()
    pending_timers[admin_chat_id] = timer


def _finalize_report(admin_chat_id):
    user_id = pending_reports.pop(admin_chat_id, None)
    files   = pending_files.pop(admin_chat_id, [])
    pending_timers.pop(admin_chat_id, None)

    if not user_id or not files:
        return

    profile = get_user(user_id)
    total   = len(files)

    # Deliver via Telegram chat
    for i, (file_bytes, filename) in enumerate(files):
        caption = (
            "📋 *Your AI & Plagiarism Check Report is ready!*\n\n"
            "📱 You can also download it directly from the app. ✅"
            if i == 0 else f"📎 File {i+1} of {total}"
        )
        user_bot.send_document(
            user_id,
            file_bytes,
            visible_file_name=filename,
            caption=caption,
            parse_mode="Markdown",
        )

    # Store in webapp_api so user can also download from the app
    _store_report_in_api(user_id, files)

    subs = max(0, profile.get("submissions", 1) - 1)
    set_user(user_id, {"status": "report_sent", "submissions": subs})
    _notify_user_report_sent(user_id)

    bot.send_message(
        admin_chat_id,
        f"✅ {total} file(s) delivered to *{profile.get('full_name', '')}* (`{user_id}`).\n"
        f"Submissions remaining: {subs}",
        parse_mode="Markdown",
        reply_markup=main_menu_markup(),
    )


@bot.message_handler(commands=["done"])
@admin_only
def cmd_done(message):
    if message.chat.id not in pending_reports:
        bot.send_message(message.chat.id, "ℹ️ No active report session.", reply_markup=main_menu_markup())
        return
    if message.chat.id in pending_timers:
        pending_timers[message.chat.id].cancel()
    _finalize_report(message.chat.id)


@bot.message_handler(commands=["sendreport"])
@admin_only
def cmd_sendreport(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: `/sendreport <user_id>`", parse_mode="Markdown")
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
        f"📎 Send the report file(s) for *{profile.get('full_name', '')}* (`{user_id}`).",
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda m: True, content_types=["text"])
@admin_only
def handle_text(message):
    admin_chat_id = message.chat.id

    if admin_chat_id in pending_approval:
        user_id = pending_approval[admin_chat_id]
        try:
            submissions = int(message.text.strip())
            if submissions < 1:
                raise ValueError
        except ValueError:
            bot.send_message(admin_chat_id, "❌ Please enter a valid positive number.")
            return

        profile = get_user(user_id)
        set_user(user_id, {"status": "approved", "submissions": submissions})
        user_bot.send_message(
            user_id,
            f"✅ *Payment verified!*\n"
            f"You've been allocated *{submissions} submission(s).*\n\n"
            f"📱 Open the app to upload your document!",
            parse_mode="Markdown",
            reply_markup=_open_app_markup(),
        )
        pending_approval.pop(admin_chat_id, None)
        bot.send_message(
            admin_chat_id,
            f"✅ *{profile.get('full_name', 'Unknown')}* approved with *{submissions} submission(s)*.",
            parse_mode="Markdown",
            reply_markup=main_menu_markup(),
        )
        return

    bot.send_message(admin_chat_id, "Use the menu below.", reply_markup=main_menu_markup())


@bot.message_handler(commands=["help"])
@admin_only
def cmd_help(message):
    bot.send_message(
        message.chat.id,
        "*Admin Commands*\n\n"
        "/menu — open the main menu\n."
        "/sendreport `<id>` — start a report session\n"
        "/done — deliver files immediately\n",
        parse_mode="Markdown",
        reply_markup=main_menu_markup(),
    )


def main():
    logger.info("Admin bot running...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
