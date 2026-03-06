# 📄 AI & Plagiarism Checker — Telegram Bot System

A two-bot system for managing student document submissions, manual review, and report delivery — all over Telegram.

---

## System Overview

```
Student (User Bot)                      You (Admin Bot)
──────────────────                      ───────────────
/start
  → See payment instructions
  → Send ref code OR screenshot ──────► Notified of ref code / screenshot
                                         /approve <user_id>
  ← "You're approved!"         ◄──────
  → Send document              ──────► Receive document
                                         (manually check it)
                                         /sendreport <user_id>
                                         + attach report file(s)
  ← Receive report             ◄──────
  ← Follow-up button after 3min
```

---

## Setup Instructions

### Step 1 — Create two Telegram bots
1. Open Telegram and message **@BotFather**
2. Send `/newbot` → follow prompts → copy the **token**
3. Repeat to create a **second bot** (admin bot)

### Step 2 — Get your Telegram Chat ID
1. Message **@userinfobot** on Telegram
2. It replies with your numeric ID e.g. `123456789`

### Step 3 — Set environment variables on Railway
Add these three variables in the Railway Variables tab:
```
USER_BOT_TOKEN   = your first bot token
ADMIN_BOT_TOKEN  = your second bot token
ADMIN_CHAT_ID    = your numeric chat ID from @userinfobot
```

### Step 4 — Deploy on Railway
- Connect your GitHub repo to Railway
- Set Start Command to: `python main.py`
- Railway auto-deploys on every GitHub push

---

## Admin Commands Reference

| Command | What it does |
|---|---|
| `/pending` | List all users waiting for approval |
| `/approve <id>` | Approve user → they're notified and can upload |
| `/reject <id>` | Reject user → they're notified to re-check payment |
| `/status <id>` | Check one user's current status |
| `/list` | See all users and their statuses |
| `/sendreport <id>` | Start a report session for a user |
| `/done` | Finalize and deliver all files immediately |
| `/online` | Set your status to 🟢 Online |
| `/offline` | Set your status to offline (hides indicator) |
| `/help` | Show command list |

---

## Sending Reports (Step by Step)

1. Type `/sendreport <user_id>` in the admin bot
2. Send your report file(s) one by one
3. After 30 seconds of no new files, all files are delivered automatically
4. Or type `/done` to deliver immediately without waiting

---

## User Status Flow

| Status | Meaning |
|---|---|
| `pending_payment` | User started bot, hasn't sent ref code yet |
| `pending_approval` | Ref code or screenshot submitted, awaiting your approval |
| `approved` | You approved them, they can now upload |
| `doc_received` | Document uploaded, you're working on it |
| `report_sent` | You sent the report back |

---

## Online / Offline Status

- Type `/online` in your admin bot when you start working
- Type `/offline` when you're done for the day
- Users who send `/start` will see `🟢 Online` at the bottom of the instructions when you're online
- When offline the indicator disappears — clean and simple

---

## Payment Verification

Users can verify payment in two ways:
1. **Text** — type their M-Pesa or Binance reference code
2. **Screenshot** — send a photo of their payment confirmation

Both are forwarded to your admin bot for manual verification. Use `/approve` or `/reject` accordingly.

---

## What Users Experience

1. Send `/start` → see payment instructions with pricing and payment details
2. Make payment via M-Pesa (`0799023325`) or Binance Pay (`2938399390`)
3. Send reference code or payment screenshot
4. Wait for your approval notification
5. Once approved, upload their document (PDF or Word)
6. Receive their report in 5–15 minutes
7. After report is delivered, bot sends a follow-up after 3 minutes with a **"Start New Check"** button

---

## File Structure

```
telegram-checker/
├── main.py                 ← starts both bots together
├── requirements.txt        ← pyTelegramBotAPI==4.20.0
├── .env.example            ← copy to .env for local testing
├── shared/
│   └── storage.py          ← shared JSON database
├── user_bot/
│   └── bot.py              ← student-facing bot
└── admin_bot/
    └── bot.py              ← your private admin bot
```

---

## Running Locally (Windows)

1. Fill in `start_bots.bat` with your tokens
2. Double-click it — two terminal windows open
3. ⚠️ Never run locally while Railway is also running — causes 409 conflict
