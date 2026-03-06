"""
Simple JSON-based persistent storage shared between both bots.
Stores user states, ref codes, and document tracking.
"""

import json
import os
import threading
from datetime import datetime

STORAGE_FILE = os.path.join(os.path.dirname(__file__), "data.json")
_lock = threading.Lock()


def _load():
    if not os.path.exists(STORAGE_FILE):
        return {"users": {}, "ref_codes": {}}
    with open(STORAGE_FILE, "r") as f:
        return json.load(f)


def _save(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── User status helpers ────────────────────────────────────────────────────────
# Status flow:
#   "pending_payment"  → user started, awaiting payment + ref code
#   "pending_approval" → ref code submitted, waiting for admin to approve
#   "approved"         → admin approved, user may upload document
#   "doc_received"     → document uploaded, admin working on it
#   "report_sent"      → admin sent back the report

def get_user(user_id: int) -> dict:
    with _lock:
        data = _load()
        return data["users"].get(str(user_id), {})


def set_user(user_id: int, fields: dict):
    with _lock:
        data = _load()
        uid = str(user_id)
        if uid not in data["users"]:
            data["users"][uid] = {"created_at": datetime.utcnow().isoformat()}
        data["users"][uid].update(fields)
        _save(data)


def get_user_by_ref(ref_code: str):
    """Return (user_id, user_dict) for a given ref code, or (None, None)."""
    with _lock:
        data = _load()
        for uid, info in data["users"].items():
            if info.get("ref_code") == ref_code.strip().upper():
                return int(uid), info
    return None, None


def all_users() -> dict:
    with _lock:
        return _load()["users"]
