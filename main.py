"""
main.py - starts both bots in parallel
"""
import threading
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

def run_user_bot():
    from user_bot.bot import main
    main()

def run_admin_bot():
    from admin_bot.bot import main
    main()

if __name__ == "__main__":
    t1 = threading.Thread(target=run_user_bot)
    t2 = threading.Thread(target=run_admin_bot)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
