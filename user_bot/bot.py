"""
USER BOT  –  student-facing side
─────────────────────────────────
Flow:
  1. /start → payment instructions + ask for ref code
  2. User sends ref code → stored, admin notified
  3. Admin approves → user unlocked to send document
  4. User sends document → forwarded to admin
  5. Admin sends report back → user receives it here
"""

import logging
import os
import sys

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.storage import get_user, set_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Load from environment ──────────────────────────────────────────────────────
USER_BOT_TOKEN = os.environ["USER_BOT_TOKEN"]
ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]   # used to forward notifications
ADMIN_CHAT_ID   = int(os.environ["ADMIN_CHAT_ID"]) # your personal Telegram chat id

# Payment details shown to every new user – edit to match your payment method
PAYMENT_INSTRUCTIONS = """
💳 *Payment Instructions*

Please send your payment via one of the methods below, then return here with your reference code.

• *M-Pesa / Bank Transfer:*  [your details here]
• *PayPal:*  [your email here]
• *Amount:*  $XX USD (or your local equivalent)

Once payment is confirmed, you will receive a *Reference Code* from us.

➡️ Send that Reference Code here to proceed.
""".strip()


# ── Handlers ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    set_user(user.id, {
        "username": user.username or "",
        "full_name": user.full_name,
        "status": "pending_payment",
    })

    await update.message.reply_text(
        f"👋 Welcome, {user.first_name}!\n\n"
        "This bot lets you submit documents for *AI & plagiarism checking*.\n\n"
        "To get started, you first need to complete a payment.\n\n"
        + PAYMENT_INSTRUCTIONS,
        parse_mode="Markdown",
    )


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    text    = update.message.text.strip()
    profile = get_user(user.id)
    status  = profile.get("status", "pending_payment")

    # ── Waiting for ref code ───────────────────────────────────────────────────
    if status in ("pending_payment", "pending_approval"):
        ref = text.upper()
        set_user(user.id, {"status": "pending_approval", "ref_code": ref})

        # Notify admin bot
        from telegram import Bot
        admin_bot = Bot(token=ADMIN_BOT_TOKEN)
        await admin_bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"🔔 *New Ref Code Submitted*\n\n"
                f"👤 Name: {user.full_name}\n"
                f"🆔 User ID: `{user.id}`\n"
                f"🔑 Ref Code: `{ref}`\n\n"
                f"Use `/approve {user.id}` in the admin bot to unlock their upload."
            ),
            parse_mode="Markdown",
        )

        await update.message.reply_text(
            f"✅ Reference code *{ref}* received!\n\n"
            "Our team will verify your payment shortly. "
            "You will be notified here as soon as you're approved to upload your document. 📄",
            parse_mode="Markdown",
        )
        return

    # ── Approved: remind them to send a file ──────────────────────────────────
    if status == "approved":
        await update.message.reply_text(
            "📎 You're approved! Please *send your document as a file* (PDF, Word, or text).",
            parse_mode="Markdown",
        )
        return

    # ── Already submitted ──────────────────────────────────────────────────────
    if status == "doc_received":
        await update.message.reply_text(
            "⏳ Your document is currently being reviewed. We'll send your report here soon!"
        )
        return

    if status == "report_sent":
        await update.message.reply_text(
            "✅ Your report has already been sent. "
            "Use /start if you'd like to submit a new document."
        )
        return

    # Fallback
    await update.message.reply_text(
        "Please complete payment and send your reference code to proceed."
    )


async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    profile = get_user(user.id)
    status  = profile.get("status", "pending_payment")

    if status != "approved":
        status_msgs = {
            "pending_payment":  "❌ Please send your reference code first.",
            "pending_approval": "⏳ Your payment is still being verified. Please wait for approval.",
            "doc_received":     "⏳ We already have your document. Please wait for your report.",
            "report_sent":      "✅ Your report was already sent. Use /start to submit a new document.",
        }
        await update.message.reply_text(
            status_msgs.get(status, "❌ You are not yet authorised to upload documents.")
        )
        return

    doc = update.message.document
    set_user(user.id, {"status": "doc_received", "file_id": doc.file_id, "file_name": doc.file_name})

    # Forward document to admin
    from telegram import Bot
    admin_bot = Bot(token=ADMIN_BOT_TOKEN)
    await admin_bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=(
            f"📄 *Document Received*\n\n"
            f"👤 {user.full_name}  |  ID: `{user.id}`\n"
            f"📎 File: {doc.file_name}\n\n"
            f"When your review is done, use:\n"
            f"`/sendreport {user.id}` and attach your report file."
        ),
        parse_mode="Markdown",
    )
    await admin_bot.send_document(
        chat_id=ADMIN_CHAT_ID,
        document=doc.file_id,
        caption=f"Document from user {user.id} ({user.full_name})",
    )

    await update.message.reply_text(
        "📨 Your document has been received! We'll get back to you with the full report soon. "
        "This typically takes 24–48 hours. ✅"
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(USER_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("User bot running…")
    app.run_polling()


if __name__ == "__main__":
    main()
