@echo off

:: ── Fill in your values below ──────────────────────────────────────────────
set USER_BOT_TOKEN=8534429133:AAF9yIhBkuqYTPb0gc6jqM6PMP8LPLm1Vpk
set ADMIN_BOT_TOKEN=8675578413:AAFzLgnNmGBKKzHXl_FlRingZH4_1jZm2U0
set ADMIN_CHAT_ID=8554860680
:: ───────────────────────────────────────────────────────────────────────────

echo Starting User Bot...
start "User Bot" cmd /k python user_bot\bot.py

echo Starting Admin Bot...
start "Admin Bot" cmd /k python admin_bot\bot.py

echo Both bots are running!
