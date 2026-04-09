#!/usr/bin/env python3
"""
LINE Messaging API - MCP Server
透過 MCP 協議與 LINE Messaging API 溝通，支援 Push Message 推播功能。

使用前請設定環境變數：
  LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
"""

import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize MCP Server
mcp = FastMCP("LINE Messaging API")

LINE_API_BASE = "https://api.line.me/v2/bot"
USER_ID_MAP_PATH = os.path.join(os.path.dirname(__file__), "line_user_id_map.json")


def get_headers() -> dict:
    """Get LINE API authorization headers."""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise ValueError(
            "Please set the LINE_CHANNEL_ACCESS_TOKEN environment variable.\n"
            "You can get the Channel Access Token from the LINE Developers Console."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def load_user_id_map() -> dict:
    """Load name -> userId mapping from line_user_id_map.json."""
    try:
        with open(USER_ID_MAP_PATH, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return {entry["name"]: entry["userId"] for entry in entries if "name" in entry and "userId" in entry}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def resolve_recipient(name_or_id: str) -> tuple[str, str]:
    """Resolve a name or raw ID to a userId.

    Returns:
        (userId, display_label) tuple.
    Raises:
        ValueError if the name is not found in the map.
    """
    user_map = load_user_id_map()
    if name_or_id in user_map:
        return user_map[name_or_id], name_or_id
    # Not a known name — treat as a raw ID
    if name_or_id.startswith(("U", "C", "R")):
        return name_or_id, name_or_id
    known = ", ".join(user_map.keys()) if user_map else "(none)"
    raise ValueError(
        f"Unknown recipient '{name_or_id}'.\n"
        f"Known contacts: {known}\n"
        "Pass a name from line_user_id_map.json or a raw LINE userId/groupId."
    )


# ──────────────────────────────────────────────
# Tool 1: 傳送 Push Message
# ──────────────────────────────────────────────

@mcp.tool()
def send_push_message(to: str, message: str) -> str:
    """
    Send a push message to a LINE user, group, or room.

    Args:
        to: Recipient name (from line_user_id_map.json, e.g. "林涑淨")
            or a raw LINE userId / groupId / roomId.
        message: Text message content to send.

    Returns:
        Result of the send operation (success or error message).
    """
    try:
        user_id, label = resolve_recipient(to)
        headers = get_headers()
        payload = {
            "to": user_id,
            "messages": [{"type": "text", "text": message}],
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{LINE_API_BASE}/message/push",
                headers=headers,
                json=payload,
            )

        if response.status_code == 200:
            return f"Message sent successfully.\nRecipient: {label}\nContent: {message}"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", "Unknown error")
                details = error_data.get("details", [])
                detail_str = (
                    "\n".join(f"  - {d.get('message', '')}" for d in details)
                    if details
                    else ""
                )
            except Exception:
                error_msg = response.text
                detail_str = ""

            return (
                f"Send failed\n"
                f"Status: {response.status_code}\n"
                f"Error: {error_msg}"
                + (f"\nDetails:\n{detail_str}" if detail_str else "")
            )

    except ValueError as e:
        return f"Configuration error: {str(e)}"
    except httpx.TimeoutException:
        return "Connection timed out. Please check your network connection."
    except Exception as e:
        return f"Unexpected error: {str(e)}"


# ──────────────────────────────────────────────
# Tool 2: 廣播訊息給所有關注者
# ──────────────────────────────────────────────

@mcp.tool()
def send_broadcast_message(message: str) -> str:
    """
    廣播訊息給所有關注此 LINE Official Account 的使用者。

    Args:
        message: 要廣播的文字訊息內容

    Returns:
        廣播結果（成功或錯誤訊息）
    """
    try:
        headers = get_headers()
        payload = {
            "messages": [
                {
                    "type": "text",
                    "text": message,
                }
            ]
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{LINE_API_BASE}/message/broadcast",
                headers=headers,
                json=payload,
            )

        if response.status_code == 200:
            return f"✅ 廣播訊息已成功發送給所有關注者！\n內容: {message}"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", "未知錯誤")
            except Exception:
                error_msg = response.text

            return (
                f"❌ 廣播失敗\n"
                f"狀態碼: {response.status_code}\n"
                f"錯誤: {error_msg}"
            )

    except ValueError as e:
        return f"❌ 設定錯誤: {str(e)}"
    except httpx.TimeoutException:
        return "❌ 連線逾時，請確認網路連線後再試"
    except Exception as e:
        return f"❌ 發生未預期的錯誤: {str(e)}"


# ──────────────────────────────────────────────
# Tool 3: 查詢使用者資料
# ──────────────────────────────────────────────

@mcp.tool()
def get_user_profile(user_id: str) -> str:
    """
    查詢 LINE 使用者的個人資料。

    Args:
        user_id: LINE 使用者的 userId（格式: "U" + 32 位英數字）

    Returns:
        使用者資料（顯示名稱、頭像網址、狀態訊息）或錯誤訊息
    """
    try:
        headers = get_headers()

        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{LINE_API_BASE}/profile/{user_id}",
                headers=headers,
            )

        if response.status_code == 200:
            data = response.json()
            result = (
                f"👤 使用者資料\n"
                f"顯示名稱: {data.get('displayName', 'N/A')}\n"
                f"userId: {data.get('userId', 'N/A')}\n"
                f"語言: {data.get('language', 'N/A')}\n"
                f"狀態訊息: {data.get('statusMessage', '（無）')}\n"
                f"頭像網址: {data.get('pictureUrl', '（無）')}"
            )
            return result
        elif response.status_code == 404:
            return f"❌ 找不到使用者 {user_id}，請確認 userId 是否正確"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", "未知錯誤")
            except Exception:
                error_msg = response.text
            return f"❌ 查詢失敗 (狀態碼: {response.status_code}): {error_msg}"

    except ValueError as e:
        return f"❌ 設定錯誤: {str(e)}"
    except httpx.TimeoutException:
        return "❌ 連線逾時，請確認網路連線後再試"
    except Exception as e:
        return f"❌ 發生未預期的錯誤: {str(e)}"


# ──────────────────────────────────────────────
# Tool 4: 傳送 Flex Message（進階排版訊息）
# ──────────────────────────────────────────────

@mcp.tool()
def send_flex_message(to: str, alt_text: str, flex_content: str) -> str:
    """
    Send a Flex Message (rich layout message) to a LINE user or group.

    Args:
        to: Recipient name (from line_user_id_map.json, e.g. "林涑淨")
            or a raw LINE userId / groupId.
        alt_text: Fallback text shown in push notifications.
        flex_content: Flex Message container as a JSON string.

    Example flex_content (bubble card):
    {
      "type": "bubble",
      "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {"type": "text", "text": "Hello!", "weight": "bold", "size": "xl"}
        ]
      }
    }

    Returns:
        Result of the send operation.
    """
    try:
        user_id, label = resolve_recipient(to)
        headers = get_headers()

        try:
            flex_obj = json.loads(flex_content)
        except json.JSONDecodeError as e:
            return f"Invalid flex_content JSON: {str(e)}"

        payload = {
            "to": user_id,
            "messages": [
                {
                    "type": "flex",
                    "altText": alt_text,
                    "contents": flex_obj,
                }
            ],
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{LINE_API_BASE}/message/push",
                headers=headers,
                json=payload,
            )

        if response.status_code == 200:
            return f"Flex Message sent successfully.\nRecipient: {label}\nAlt text: {alt_text}"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", "Unknown error")
            except Exception:
                error_msg = response.text
            return f"Send failed (status {response.status_code}): {error_msg}"

    except ValueError as e:
        return f"Configuration error: {str(e)}"
    except httpx.TimeoutException:
        return "Connection timed out. Please check your network connection."
    except Exception as e:
        return f"Unexpected error: {str(e)}"


# ──────────────────────────────────────────────
# Tool 5: List known contacts
# ──────────────────────────────────────────────

@mcp.tool()
def list_contacts() -> str:
    """
    List all named contacts available in line_user_id_map.json.

    Returns:
        A list of contact names that can be used with send_push_message
        and send_flex_message.
    """
    user_map = load_user_id_map()
    if not user_map:
        return "No contacts found in line_user_id_map.json."
    lines = [f"- {name}" for name in user_map]
    return "Available contacts:\n" + "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
