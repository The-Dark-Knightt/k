"""
ADMIN BOT  –  your private control panel
─────────────────────────────────────────
Commands:
  /pending              – list all users awaiting approval
  /approve <user_id>    – approve a user to upload their document
  /reject  <user_id>    – reject a user (notifies them)
  /status  <user_id>    – show a user's current status
  /list                 – show all users and their statuses
  /sendreport <user_id> – reply with this command + attach a file to send the report to the user
"""

import logging
import os
import sys

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.storage import get_user, set_user, all_users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]
USER_BOT_TOKEN  = os.environ["USER_BOT_TOKEN"]
ADMIN_CHAT_ID   = int(os.environ["ADMIN_CHAT_ID"])

STATUS_EMOJI = {
    "pending_payment":  "💳",
    "pending_approval": "🕐",
    "approved":         "✅",
    "doc_received":     "📄",
    "report_sent":      "📨",
}


def admin_only(handler):
    """Decorator – silently ignore anyone who is not the admin."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_CHAT_ID:
            return
        return await handler(update, ctx)
    return wrapper


# ── Commands ───────────────────────────────────────────────────────────────────

@admin_only
async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    users = all_users()
    pending = {uid: u for uid, u in users.items() if u.get("status") == "pending_approval"}

    if not pending:
        await update.message.reply_text("✅ No users are currently waiting for approval.")
        return

    lines = ["*Users Pending Approval:*\n"]
    for uid, u in pending.items():
        lines.append(
            f"👤 {u.get('full_name', 'Unknown')}  |  ID: `{uid}`\n"
            f"   Ref: `{u.get('ref_code', 'N/A')}`\n"
            f"   Use: `/approve {uid}`\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/approve <user_id>`", parse_mode="Markdown")
        return

    try:
        user_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    profile = get_user(user_id)
    if not profile:
        await update.message.reply_text("❌ User not found.")
        return

    set_user(user_id, {"status": "approved"})

    # Notify the user via user bot
    from telegram import Bot
    user_bot = Bot(token=USER_BOT_TOKEN)
    await user_bot.send_message(
        chat_id=user_id,
        text=(
            "🎉 *Your payment has been verified!*\n\n"
            "You are now authorised to submit your document.\n\n"
            "📎 Please send your document as a file (PDF, Word, or plain text) and we'll get started!"
        ),
        parse_mode="Markdown",
    )

    await update.message.reply_text(
        f"✅ User `{user_id}` ({profile.get('full_name', '')}) has been approved and notified.",
        parse_mode="Markdown",
    )


@admin_only
async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/reject <user_id>`", parse_mode="Markdown")
        return

    try:
        user_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    profile = get_user(user_id)
    if not profile:
        await update.message.reply_text("❌ User not found.")
        return

    set_user(user_id, {"status": "pending_payment"})

    from telegram import Bot
    user_bot = Bot(token=USER_BOT_TOKEN)
    await user_bot.send_message(
        chat_id=user_id,
        text=(
            "❌ *We could not verify your payment.*\n\n"
            "Please double-check your payment and send the correct reference code.\n"
            "If you need help, contact support."
        ),
        parse_mode="Markdown",
    )

    await update.message.reply_text(
        f"🚫 User `{user_id}` rejected and notified.",
        parse_mode="Markdown",
    )


@admin_only
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/status <user_id>`", parse_mode="Markdown")
        return

    try:
        user_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    profile = get_user(user_id)
    if not profile:
        await update.message.reply_text("❌ User not found.")
        return

    status = profile.get("status", "unknown")
    emoji  = STATUS_EMOJI.get(status, "❓")
    await update.message.reply_text(
        f"*User `{user_id}`*\n"
        f"Name: {profile.get('full_name', 'N/A')}\n"
        f"Ref:  `{profile.get('ref_code', 'N/A')}`\n"
        f"Status: {emoji} `{status}`\n"
        f"File: {profile.get('file_name', 'none')}",
        parse_mode="Markdown",
    )


@admin_only
async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    users = all_users()
    if not users:
        await update.message.reply_text("No users yet.")
        return

    lines = ["*All Users:*\n"]
    for uid, u in users.items():
        status = u.get("status", "unknown")
        emoji  = STATUS_EMOJI.get(status, "❓")
        lines.append(f"{emoji} `{uid}` – {u.get('full_name', 'N/A')} – `{status}`")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_sendreport(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Usage: reply to a document with /sendreport <user_id>
    Or: send /sendreport <user_id> and immediately follow with the file.
    This handler sets ctx.user_data so the next document from admin is routed.
    """
    if not ctx.args:
        await update.message.reply_text("Usage: `/sendreport <user_id>` then send the file.", parse_mode="Markdown")
        return

    try:
        user_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    profile = get_user(user_id)
    if not profile:
        await update.message.reply_text("❌ User not found.")
        return

    # If a document is already attached in the same message
    if update.message.document:
        await _deliver_report(update, ctx, user_id, profile, update.message.document)
        return

    # Otherwise wait for next document
    ctx.user_data["pending_report_for"] = user_id
    await update.message.reply_text(
        f"📎 Now send the report file for user `{user_id}` ({profile.get('full_name', '')}).",
        parse_mode="Markdown",
    )


async def _deliver_report(update, ctx, user_id, profile, document):
    from telegram import Bot
    user_bot = Bot(token=USER_BOT_TOKEN)
    await user_bot.send_document(
        chat_id=user_id,
        document=document.file_id,
        caption=(
            "📋 *Your AI & Plagiarism Check Report is ready!*\n\n"
            "Please review the attached document carefully.\n"
            "If you have any questions, feel free to reach out. ✅"
        ),
        parse_mode="Markdown",
    )
    set_user(user_id, {"status": "report_sent"})
    ctx.user_data.pop("pending_report_for", None)

    await update.message.reply_text(
        f"✅ Report delivered to user `{user_id}` ({profile.get('full_name', '')}).",
        parse_mode="Markdown",
    )


@admin_only
async def handle_admin_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Catches a document sent by admin after /sendreport <id>."""
    pending = ctx.user_data.get("pending_report_for")
    if not pending:
        await update.message.reply_text(
            "ℹ️ Use `/sendreport <user_id>` before sending a file.",
            parse_mode="Markdown",
        )
        return

    profile = get_user(pending)
    await _deliver_report(update, ctx, pending, profile, update.message.document)


@admin_only
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Admin Commands*\n\n"
        "/pending – users waiting for approval\n"
        "/approve `<id>` – approve & notify user\n"
        "/reject `<id>` – reject & notify user\n"
        "/status `<id>` – check one user's status\n"
        "/list – see all users\n"
        "/sendreport `<id>` – then send file → delivers report to user\n",
        parse_mode="Markdown",
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(ADMIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler("pending",    cmd_pending))
    app.add_handler(CommandHandler("approve",    cmd_approve))
    app.add_handler(CommandHandler("reject",     cmd_reject))
    app.add_handler(CommandHandler("status",     cmd_status))
    app.add_handler(CommandHandler("list",       cmd_list))
    app.add_handler(CommandHandler("sendreport", cmd_sendreport))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_admin_document))
    logger.info("Admin bot running…")
    app.run_polling()


if __name__ == "__main__":
    main()
