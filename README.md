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
                                         /approve <user_id> <submissions>
  ← "You're approved! X submissions"  ◄──────
  → Send document              ──────► Receive document
                                         (manually check it)
                                         /sendreport <user_id>
                                         + attach report file(s)
  ← Receive report             ◄──────
  ← Follow-up after 3min
     (submissions left → upload prompt)
     (submissions done → /start prompt)
```

---

## Setup Instructions

### Step 1 — Create two Telegram bots
1. Open Telegram and message **@BotFather**
2. Send `/newbot` → follow prompts → copy the **token**
3. Repeat to create a **second bot** (admin bot)

### Step 2 — Set your bot description (shown before /start)
In BotFather, use `/setdescription` and paste:

```
💳 Step 1: Pay for checks and verify your payment.
📄 Step 2: Send your document and we'll process it fast ⚡
⚠️ Note: The bot handles one document at a time. Send multiple docs one by one.
⭐ Reviews & Transactions: https://t.me/reviewstransactions
🎁 Bonus: Bring 2 clients and get 1 free check from support.
🛠 Support: @daemonizerr
```

### Step 3 — Get your Telegram Chat ID
1. Message **@userinfobot** on Telegram
2. It replies with your numeric ID e.g. `123456789`

### Step 4 — Set environment variables on Railway
```
USER_BOT_TOKEN   = your first bot token
ADMIN_BOT_TOKEN  = your second bot token
ADMIN_CHAT_ID    = your numeric chat ID from @userinfobot
```

### Step 5 — Deploy on Railway
- Connect your GitHub repo to Railway
- Set Start Command to: `python main.py`

---

## Admin Commands Reference

| Command | What it does |
|---|---|
| `/pending` | List all users waiting for approval |
| `/approve <id> [n]` | Approve user with n submissions (default 1) |
| `/reject <id>` | Reject user → they're notified to re-check payment |
| `/status <id>` | Check one user's current status + submissions left |
| `/list` | See all users, statuses, and submission counts |
| `/sendreport <id>` | Start a report session for a user |
| `/done` | Finalize and deliver all files immediately |
| `/online` | Set your status to 🟢 Online |
| `/offline` | Set your status to 🔴 Offline |
| `/help` | Show command list |

---

## Approving with Submissions

Use `/approve <user_id> <number>` to set how many submissions a user gets:

```
/approve 123456789 1    → 1 submission (single check)
/approve 123456789 3    → 3 submissions (bulk)
/approve 123456789      → defaults to 1 submission
```

The user is notified with how many submissions they have. Each document upload deducts one. When submissions run out, the bot directs them to /start to pay again.

---

## Online / Offline Status

- `/online` → users see **🟢 Online** at the bottom of the start message
- `/offline` → users see **🔴 Offline** at the bottom of the start message

---

## User Status Flow

| Status | Meaning |
|---|---|
| `pending_payment` | User started bot, hasn't sent ref code yet |
| `pending_approval` | Ref code or screenshot submitted, awaiting approval |
| `approved` | Approved, can now upload |
| `doc_received` | Document uploaded, being worked on |
| `report_sent` | Report delivered |

---

## File Structure

```
k-main/
├── main.py                 ← starts both bots together
├── requirements.txt
├── shared/
│   ├── storage.py          ← shared JSON database
│   └── data.json           ← stored user data
├── user_bot/
│   └── bot.py              ← student-facing bot
└── admin_bot/
    └── bot.py              ← your private admin bot
```
