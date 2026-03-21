"""
webapp_api.py  —  HTTP API for the Telegram Mini App
Endpoints:
  GET  /api/user?id=...        → fetch user profile
  POST /api/submit_ref         → submit payment reference code
  POST /api/submit_screenshot  → submit payment screenshot image
  POST /api/upload_doc         → upload document for checking
  GET  /api/download/<user_id> → download report file
"""

import json
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))
from shared.storage import get_user, set_user

import telebot

PORT            = int(os.environ.get("API_PORT", 8080))
ADMIN_BOT_TOKEN = os.environ["ADMIN_BOT_TOKEN"]
USER_BOT_TOKEN  = os.environ["USER_BOT_TOKEN"]
ADMIN_CHAT_ID   = int(os.environ["ADMIN_CHAT_ID"])

admin_bot = telebot.TeleBot(ADMIN_BOT_TOKEN)
user_bot  = telebot.TeleBot(USER_BOT_TOKEN)

# In-memory report store: { user_id: [(file_bytes, filename), ...] }
report_store      = {}
report_store_lock = threading.Lock()

WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://the-dark-knightt.github.io/k/webapp/index.html")


def _open_app_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        "📱 Open App", web_app=telebot.types.WebAppInfo(url=WEBAPP_URL)
    ))
    return markup


def _cors(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def _json(handler, code, obj):
    body = json.dumps(obj).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    _cors(handler)
    handler.end_headers()
    handler.wfile.write(body)


def _parse_multipart(body: bytes, boundary: bytes) -> dict:
    result    = {}
    delimiter = b"--" + boundary
    for part in body.split(delimiter)[1:]:
        if part in (b"", b"--", b"--\r\n"):
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if b"\r\n\r\n" not in part:
            continue
        header_block, _, content = part.partition(b"\r\n\r\n")
        headers = header_block.decode(errors="replace").lower()
        if 'name="' not in headers:
            continue
        name = headers.split('name="')[1].split('"')[0]
        if 'filename="' in headers:
            fname = headers.split('filename="')[1].split('"')[0]
            result[name + "_filename"] = fname.encode()
            result[name] = content
        else:
            result[name] = content
    return result


class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        _cors(self)
        self.end_headers()

    # ── GET ───────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/user":
            params  = parse_qs(parsed.query)
            user_id = params.get("id", [None])[0]
            if not user_id:
                return _json(self, 400, {"error": "missing id"})
            try:
                profile = get_user(int(user_id))
                return _json(self, 200, profile)
            except Exception as e:
                return _json(self, 500, {"error": str(e)})

        if parsed.path.startswith("/api/download/"):
            uid_str = parsed.path.split("/api/download/")[-1]
            try:
                uid = int(uid_str)
            except ValueError:
                return _json(self, 400, {"error": "bad user id"})
            with report_store_lock:
                files = report_store.get(uid, [])
            if not files:
                return _json(self, 404, {"error": "no report available yet"})
            file_bytes, filename = files[0]
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(file_bytes)))
            _cors(self)
            self.end_headers()
            self.wfile.write(file_bytes)
            return

        _json(self, 200, {"ok": True})

    # ── POST ──────────────────────────────────────────────────────────────────

    def do_POST(self):
        parsed   = urlparse(self.path)
        length   = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b""

        # ── POST /api/submit_ref ──────────────────────────────────────────────
        if parsed.path == "/api/submit_ref":
            try:
                payload = json.loads(raw_body)
            except Exception:
                return _json(self, 400, {"error": "invalid JSON"})

            user_id    = payload.get("user_id")
            ref        = (payload.get("ref") or "").strip().upper()
            first_name = payload.get("first_name", "User")
            full_name  = payload.get("full_name", first_name)
            username   = payload.get("username", "")

            if not user_id or not ref:
                return _json(self, 400, {"error": "missing user_id or ref"})

            set_user(int(user_id), {
                "username":  username,
                "full_name": full_name,
                "status":    "pending_approval",
                "ref_code":  ref,
            })

            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                telebot.types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
                telebot.types.InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{user_id}"),
            )
            try:
                admin_bot.send_message(
                    ADMIN_CHAT_ID,
                    f"🔔 *New Ref Code (via App)*\n\n"
                    f"👤 Name: {full_name}\n"
                    f"🆔 User ID: `{user_id}`\n"
                    f"🔑 Ref Code: `{ref}`",
                    parse_mode="Markdown",
                    reply_markup=markup,
                )
            except Exception as e:
                return _json(self, 500, {"error": f"admin notify failed: {e}"})

            return _json(self, 200, {"ok": True})

        # ── POST /api/submit_screenshot ───────────────────────────────────────
        if parsed.path == "/api/submit_screenshot":
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                return _json(self, 400, {"error": "expected multipart/form-data"})

            try:
                boundary = content_type.split("boundary=")[-1].encode()
                parts    = _parse_multipart(raw_body, boundary)
            except Exception as e:
                return _json(self, 400, {"error": f"parse error: {e}"})

            user_id    = (parts.get("user_id")    or b"").decode().strip()
            first_name = (parts.get("first_name") or b"User").decode().strip()
            full_name  = (parts.get("full_name")  or first_name.encode()).decode().strip()
            username   = (parts.get("username")   or b"").decode().strip()
            img_data   = parts.get("screenshot")

            if not user_id or not img_data:
                return _json(self, 400, {"error": "missing user_id or screenshot"})

            uid = int(user_id)
            set_user(uid, {
                "username":  username,
                "full_name": full_name,
                "status":    "pending_approval",
            })

            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                telebot.types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}"),
                telebot.types.InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{uid}"),
            )
            try:
                admin_bot.send_photo(
                    ADMIN_CHAT_ID,
                    img_data,
                    caption=(
                        f"🖼 *Payment Screenshot (via App)*\n\n"
                        f"👤 {full_name}  |  ID: `{uid}`\n"
                        f"Ref Code: `{get_user(uid).get('ref_code', 'not sent')}`"
                    ),
                    parse_mode="Markdown",
                    reply_markup=markup,
                )
            except Exception as e:
                return _json(self, 500, {"error": f"admin notify failed: {e}"})

            # Confirm to user
            try:
                user_bot.send_message(
                    uid,
                    "🖼 *Payment screenshot received!*\n\n"
                    "Our team will verify shortly and notify you here. ✅",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

            return _json(self, 200, {"ok": True})

        # ── POST /api/upload_doc ──────────────────────────────────────────────
        if parsed.path == "/api/upload_doc":
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                return _json(self, 400, {"error": "expected multipart/form-data"})

            try:
                boundary = content_type.split("boundary=")[-1].encode()
                parts    = _parse_multipart(raw_body, boundary)
            except Exception as e:
                return _json(self, 400, {"error": f"parse error: {e}"})

            user_id    = (parts.get("user_id")    or b"").decode().strip()
            first_name = (parts.get("first_name") or b"User").decode().strip()
            full_name  = (parts.get("full_name")  or first_name.encode()).decode().strip()
            username   = (parts.get("username")   or b"").decode().strip()
            file_data  = parts.get("file")
            filename   = (parts.get("file_filename") or b"document").decode()

            if not user_id or not file_data:
                return _json(self, 400, {"error": "missing user_id or file"})

            uid     = int(user_id)
            profile = get_user(uid)

            if profile.get("status") != "approved":
                return _json(self, 403, {"error": "not approved yet"})

            subs = profile.get("submissions", 0)
            if subs < 1:
                return _json(self, 403, {"error": "no submissions remaining"})

            set_user(uid, {"status": "doc_received"})

            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton(
                "📤 Send Report", callback_data=f"sendreport_{uid}"
            ))
            try:
                admin_bot.send_document(
                    ADMIN_CHAT_ID,
                    file_data,
                    visible_file_name=filename,
                    caption=(
                        f"📄 *Document Received (via App)*\n\n"
                        f"👤 {full_name}  |  ID: `{uid}`\n"
                        f"📎 File: `{filename}`\n"
                        f"📂 Submissions remaining: {subs}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=markup,
                )
            except Exception as e:
                return _json(self, 500, {"error": f"admin notify failed: {e}"})

            try:
                user_bot.send_message(
                    uid,
                    "📄 Document received — report ready in 5–15 min.",
                )
            except Exception:
                pass

            return _json(self, 200, {"ok": True})

        _json(self, 404, {"error": "not found"})


# ── Called by admin_bot after report is delivered ─────────────────────────────

def store_report(user_id: int, files: list):
    """files = list of (file_bytes, filename)"""
    with report_store_lock:
        report_store[user_id] = files


def main():
    server = HTTPServer(("0.0.0.0", PORT), APIHandler)
    print(f"API server running on port {PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
