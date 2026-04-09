#!/usr/bin/env python3
"""
LINE Webhook Server
Receives incoming events from LINE Bot and records the most recent sender User IDs.

Environment variables required:
  LINE_CHANNEL_SECRET=your_channel_secret
  LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token  (optional, for auto-reply)

Startup:
  pip install fastapi uvicorn httpx --break-system-packages
  python line_webhook_server.py

Listens on http://0.0.0.0:8000 by default.
For external testing, use ngrok: ngrok http 8000
"""

import os
import json
import hmac
import hashlib
import base64
import httpx
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
import uvicorn

app = FastAPI(title="LINE Webhook Server")

# Store records of message senders (keep the most recent 200 entries)
RECORDS_FILE = Path(__file__).parent / "line_recent_senders.json"
MAX_RECORDS = 200


# ──────────────────────────────────────────────
# Utility functions
# ──────────────────────────────────────────────

def load_records() -> list[dict]:
    """Load records from file."""
    if RECORDS_FILE.exists():
        try:
            return json.loads(RECORDS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_records(records: list[dict]) -> None:
    """Save records to file."""
    RECORDS_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def verify_signature(body: bytes, signature: str) -> bool:
    """Verify LINE Webhook signature to prevent forged requests."""
    secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    if not secret:
        # Skip verification if secret is not set (development only)
        print("WARNING: LINE_CHANNEL_SECRET is not set, skipping signature verification")
        return True
    digest = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def add_sender(user_id: str, event_type: str, message_text: str = "") -> None:
    """Add or update sender record."""
    records = load_records()

    # If this user_id already exists, update timestamp and message
    for r in records:
        if r["userId"] == user_id:
            r["lastSeen"] = datetime.now().isoformat()
            r["lastEventType"] = event_type
            if message_text:
                r["lastMessage"] = message_text
            r["messageCount"] = r.get("messageCount", 1) + 1
            save_records(records)
            return

    # New user, insert at the front
    records.insert(0, {
        "userId": user_id,
        "firstSeen": datetime.now().isoformat(),
        "lastSeen": datetime.now().isoformat(),
        "lastEventType": event_type,
        "lastMessage": message_text,
        "messageCount": 1,
    })

    # Keep only the most recent MAX_RECORDS entries
    save_records(records[:MAX_RECORDS])


# ──────────────────────────────────────────────
# Webhook endpoint
# ──────────────────────────────────────────────

@app.post("/webhook")
async def webhook(request: Request):
    """Receive events sent from the LINE platform."""
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    for event in data.get("events", []):
        source = event.get("source", {})
        user_id = source.get("userId")
        event_type = event.get("type", "unknown")

        if not user_id:
            continue

        # Extract text message content if present
        message_text = ""
        if event_type == "message":
            msg = event.get("message", {})
            if msg.get("type") == "text":
                message_text = msg.get("text", "")

        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"event: {event_type} | userId: {user_id}"
              + (f" | message: {message_text}" if message_text else ""))

        add_sender(user_id, event_type, message_text)

    return {"status": "ok"}


# ──────────────────────────────────────────────
# Query endpoints
# ──────────────────────────────────────────────

@app.get("/senders")
def get_senders(limit: int = 20):
    """
    Get the list of users who recently sent messages.

    Query params:
      limit: Number of results to return (default 20, max 200)

    Example response:
    [
      {
        "userId": "U4af4980629...",
        "lastSeen": "2026-04-02T10:30:00",
        "lastMessage": "Hello",
        "messageCount": 5
      },
      ...
    ]
    """
    limit = min(limit, MAX_RECORDS)
    records = load_records()
    return {
        "total": len(records),
        "senders": records[:limit],
    }


@app.get("/senders/ids")
def get_sender_ids(limit: int = 20):
    """
    Return only a list of User IDs of recent message senders.
    """
    limit = min(limit, MAX_RECORDS)
    records = load_records()
    return {
        "total": len(records),
        "userIds": [r["userId"] for r in records[:limit]],
    }


@app.get("/")
def health_check():
    records = load_records()
    return {
        "status": "running",
        "recordedSenders": len(records),
        "endpoints": {
            "POST /webhook": "LINE Webhook endpoint",
            "GET  /senders": "Get recent message senders (with details)",
            "GET  /senders/ids": "Get User ID list only",
        },
    }


# ──────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"""
╔══════════════════════════════════════════════╗
║         LINE Webhook Server started          ║
╠══════════════════════════════════════════════╣
║  Local URL : http://localhost:{port:<15}║
║                                              ║
║  Set LINE Webhook URL:                       ║
║    https://<your-domain>/webhook             ║
║                                              ║
║  Query recent sender User IDs:               ║
║    GET http://localhost:{port}/senders/ids{"":>{9 - len(str(port))}}║
╚══════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=port)
