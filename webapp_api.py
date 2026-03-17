"""
Simple HTTP API server for the Telegram Mini App.
Serves user data so the Mini App can display status and submissions.
Runs alongside the bots on Railway.
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))
from shared.storage import get_user

PORT = int(os.environ.get("API_PORT", 8080))


class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logging

    def do_GET(self):
        parsed = urlparse(self.path)

        # CORS headers for Mini App
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        if parsed.path == "/api/user":
            params = parse_qs(parsed.query)
            user_id = params.get("id", [None])[0]
            if not user_id:
                self.wfile.write(json.dumps({"error": "missing id"}).encode())
                return
            try:
                profile = get_user(int(user_id))
                self.wfile.write(json.dumps(profile).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.wfile.write(json.dumps({"ok": True}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()


def main():
    server = HTTPServer(("0.0.0.0", PORT), APIHandler)
    print(f"API server running on port {PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
