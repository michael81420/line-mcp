#!/usr/bin/env python3
"""
LINE Webhook Server
接收 LINE Bot 傳入的事件，記錄最近傳訊息的使用者 User ID。

使用前請設定環境變數：
  LINE_CHANNEL_SECRET=your_channel_secret
  LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token  （可選，用於自動回覆）

啟動方式：
  pip install fastapi uvicorn httpx --break-system-packages
  python line_webhook_server.py

預設監聽 http://0.0.0.0:8000
對外測試可使用 ngrok：ngrok http 8000
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

# 儲存收到訊息的使用者記錄（保留最近 200 筆）
RECORDS_FILE = Path("line_recent_senders.json")
MAX_RECORDS = 200


# ──────────────────────────────────────────────
# 工具函式
# ──────────────────────────────────────────────

def load_records() -> list[dict]:
    """從檔案讀取記錄"""
    if RECORDS_FILE.exists():
        try:
            return json.loads(RECORDS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_records(records: list[dict]) -> None:
    """儲存記錄到檔案"""
    RECORDS_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def verify_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE Webhook 簽章，防止偽造請求"""
    secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    if not secret:
        # 若未設定 secret，跳過驗證（僅供開發測試用）
        print("⚠️  警告：未設定 LINE_CHANNEL_SECRET，跳過簽章驗證")
        return True
    digest = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def add_sender(user_id: str, event_type: str, message_text: str = "") -> None:
    """新增或更新傳送者記錄"""
    records = load_records()

    # 若此 user_id 已存在，更新時間與訊息
    for r in records:
        if r["userId"] == user_id:
            r["lastSeen"] = datetime.now().isoformat()
            r["lastEventType"] = event_type
            if message_text:
                r["lastMessage"] = message_text
            r["messageCount"] = r.get("messageCount", 1) + 1
            save_records(records)
            return

    # 新使用者，加到最前面
    records.insert(0, {
        "userId": user_id,
        "firstSeen": datetime.now().isoformat(),
        "lastSeen": datetime.now().isoformat(),
        "lastEventType": event_type,
        "lastMessage": message_text,
        "messageCount": 1,
    })

    # 只保留最近 MAX_RECORDS 筆
    save_records(records[:MAX_RECORDS])


# ──────────────────────────────────────────────
# Webhook 接收端點
# ──────────────────────────────────────────────

@app.post("/webhook")
async def webhook(request: Request):
    """接收 LINE 平台送來的事件"""
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

        # 取出文字訊息內容（如果有的話）
        message_text = ""
        if event_type == "message":
            msg = event.get("message", {})
            if msg.get("type") == "text":
                message_text = msg.get("text", "")

        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"事件: {event_type} | userId: {user_id}"
              + (f" | 訊息: {message_text}" if message_text else ""))

        add_sender(user_id, event_type, message_text)

    return {"status": "ok"}


# ──────────────────────────────────────────────
# 查詢端點
# ──────────────────────────────────────────────

@app.get("/senders")
def get_senders(limit: int = 20):
    """
    取得最近傳訊息的使用者清單。

    Query params:
      limit: 回傳筆數（預設 20，最多 200）

    回傳範例：
    [
      {
        "userId": "U4af4980629...",
        "lastSeen": "2026-04-02T10:30:00",
        "lastMessage": "你好",
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
    只回傳最近傳訊息的 User ID 列表（方便直接複製使用）。
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
            "POST /webhook": "LINE Webhook 接收端點",
            "GET  /senders": "取得最近傳訊息使用者（含詳細資料）",
            "GET  /senders/ids": "只取得 User ID 列表",
        },
    }


# ──────────────────────────────────────────────
# 啟動
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"""
╔══════════════════════════════════════════════╗
║        LINE Webhook Server 已啟動            ║
╠══════════════════════════════════════════════╣
║  本機網址: http://localhost:{port:<18}║
║                                              ║
║  設定 LINE Webhook URL：                     ║
║    https://<你的網域>/webhook               ║
║                                              ║
║  查詢最近傳訊息的 User ID：                  ║
║    GET http://localhost:{port}/senders/ids    ║
╚══════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=port)
