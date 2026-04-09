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

# 初始化 MCP Server
mcp = FastMCP("LINE Messaging API")

LINE_API_BASE = "https://api.line.me/v2/bot"


def get_headers() -> dict:
    """取得 LINE API 驗證 headers"""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise ValueError(
            "請設定環境變數 LINE_CHANNEL_ACCESS_TOKEN\n"
            "可至 LINE Developers Console 取得 Channel Access Token"
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ──────────────────────────────────────────────
# Tool 1: 傳送 Push Message
# ──────────────────────────────────────────────

@mcp.tool()
def send_push_message(to: str, message: str) -> str:
    """
    傳送 Push Message 給指定的 LINE 使用者、群組或聊天室。

    Args:
        to: 收件人的 userId、groupId 或 roomId
            - userId 範例: "U4af4980629..."
            - groupId 範例: "C4af4980629..."
        message: 要傳送的文字訊息內容

    Returns:
        傳送結果（成功或錯誤訊息）
    """
    try:
        headers = get_headers()
        payload = {
            "to": to,
            "messages": [
                {
                    "type": "text",
                    "text": message,
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
            return f"✅ 訊息已成功傳送！\n收件人: {to}\n內容: {message}"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", "未知錯誤")
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
                f"❌ 傳送失敗\n"
                f"狀態碼: {response.status_code}\n"
                f"錯誤: {error_msg}"
                + (f"\n詳情:\n{detail_str}" if detail_str else "")
            )

    except ValueError as e:
        return f"❌ 設定錯誤: {str(e)}"
    except httpx.TimeoutException:
        return "❌ 連線逾時，請確認網路連線後再試"
    except Exception as e:
        return f"❌ 發生未預期的錯誤: {str(e)}"


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
    傳送 Flex Message（支援自訂排版的進階訊息）給指定使用者。

    Args:
        to: 收件人的 userId 或 groupId
        alt_text: 通知欄顯示的替代文字（推播通知用）
        flex_content: Flex Message 的 JSON 字串內容（container 物件）

    Returns:
        傳送結果

    範例 flex_content（泡泡卡片）:
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
    """
    try:
        headers = get_headers()

        # 解析 Flex content JSON
        try:
            flex_obj = json.loads(flex_content)
        except json.JSONDecodeError as e:
            return f"❌ flex_content JSON 格式錯誤: {str(e)}"

        payload = {
            "to": to,
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
            return f"✅ Flex Message 已成功傳送！\n收件人: {to}\n替代文字: {alt_text}"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", "未知錯誤")
            except Exception:
                error_msg = response.text
            return f"❌ 傳送失敗 (狀態碼: {response.status_code}): {error_msg}"

    except ValueError as e:
        return f"❌ 設定錯誤: {str(e)}"
    except httpx.TimeoutException:
        return "❌ 連線逾時，請確認網路連線後再試"
    except Exception as e:
        return f"❌ 發生未預期的錯誤: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
