"""
main.py - starts both bots and the Mini App API in parallel.

On startup we drop any pending Telegram updates so that a Railway redeploy
never triggers Error 409 (two getUpdates sessions fighting each other).
"""
import threading
import time
import os
import sys
import telebot

sys.path.insert(0, os.path.dirname(__file__))

USER_BOT_TOKEN  = os.environ["USER_BOT_TOKEN"]
ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]


def clear_webhook_and_updates(token: str, label: str):
    """Delete any active webhook and flush pending updates before polling starts."""
    bot = telebot.TeleBot(token)
    try:
        bot.delete_webhook(drop_pending_updates=True)
        print(f"[{label}] Webhook cleared, pending updates dropped.")
    except Exception as e:
        print(f"[{label}] Warning during pre-start cleanup: {e}")
    time.sleep(1)  # small grace period so Telegram registers the drop


def run_user_bot():
    from user_bot.bot import main
    main()


def run_admin_bot():
    from admin_bot.bot import main
    main()


def run_api():
    from webapp_api import main
    main()


if __name__ == "__main__":
    # Clear any stale polling sessions before starting — prevents 409 on redeploy
    clear_webhook_and_updates(USER_BOT_TOKEN,  "user_bot")
    clear_webhook_and_updates(ADMIN_BOT_TOKEN, "admin_bot")

    t1 = threading.Thread(target=run_user_bot,  daemon=True, name="run_user_bot")
    t2 = threading.Thread(target=run_admin_bot, daemon=True, name="run_admin_bot")
    t3 = threading.Thread(target=run_api,       daemon=True, name="run_api")

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()
