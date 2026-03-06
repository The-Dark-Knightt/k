# 📄 AI & Plagiarism Checker — Telegram Bot System

A two-bot system for managing student document submissions, manual review, and report delivery — all over Telegram.

---

## System Overview

```
Student (User Bot)                      You (Admin Bot)
──────────────────                      ───────────────
/start                                  
  → See payment instructions            
  → Send ref code          ──────────► Notified of ref code
                                        /approve <user_id>
  ← "You're approved!"    ◄──────────
  → Send document          ──────────► Receive document
                                        (manually check it)
                                        /sendreport <user_id>
                                        + attach report file
  ← Receive report         ◄──────────
```

---

## Setup Instructions

### Step 1 — Create two Telegram bots
1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` → follow prompts → copy the **token**
3. Repeat to create a **second bot** (admin bot)

### Step 2 — Get your Telegram Chat ID
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your numeric user ID (e.g. `123456789`)

### Step 3 — Configure environment variables
```bash
cp .env.example .env
# Edit .env with your tokens and chat ID
```

### Step 4 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 5 — Run both bots (two separate terminals)

**Terminal 1 — User Bot:**
```bash
export $(cat .env | xargs)
python user_bot/bot.py
```

**Terminal 2 — Admin Bot:**
```bash
export $(cat .env | xargs)
python admin_bot/bot.py
```

> 💡 For production, use a server (e.g. a $5/mo VPS) and run with `systemd` or `screen`/`tmux`.

---

## Admin Commands Reference

| Command | What it does |
|---|---|
| `/pending` | List all users waiting for approval |
| `/approve <id>` | Approve user → they're notified and can upload |
| `/reject <id>` | Reject user → they're notified to re-check payment |
| `/status <id>` | Check one user's current status |
| `/list` | See all users and their statuses |
| `/sendreport <id>` | Then attach a file → sends report to student |
| `/help` | Show command list |

---

## User Status Flow

| Status | Meaning |
|---|---|
| `pending_payment` | User started bot, hasn't sent ref code yet |
| `pending_approval` | Ref code submitted, awaiting your approval |
| `approved` | You approved them, they can now upload |
| `doc_received` | Document uploaded, you're working on it |
| `report_sent` | You sent the report back |

---

## Customisation

- **Payment instructions** — edit `PAYMENT_INSTRUCTIONS` in `user_bot/bot.py`
- **Pricing / amount** — same section
- **Welcome message** — edit `cmd_start` in `user_bot/bot.py`

---

## File Structure

```
telegram-checker/
├── .env.example          ← copy to .env and fill in
├── requirements.txt
├── shared/
│   └── storage.py        ← shared JSON database
├── user_bot/
│   └── bot.py            ← student-facing bot
└── admin_bot/
    └── bot.py            ← your private admin bot
```
