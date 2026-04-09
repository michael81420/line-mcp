#!/usr/bin/env python3
"""
LINE Messaging API - MCP Server
Communicates with the LINE Messaging API via MCP protocol, supporting Push Message delivery.

Environment variables required:
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
# Tool 1: Send Push Message
# ──────────────────────────────────────────────

@mcp.tool()
def send_push_message(to: str, message: str) -> str:
    """
    Send a push message to a LINE user, group, or room.

    Args:
        to: Recipient name (from line_user_id_map.json, e.g. "John")
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
# Tool 2: Broadcast message to all followers
# ──────────────────────────────────────────────

@mcp.tool()
def send_broadcast_message(message: str) -> str:
    """
    Broadcast a message to all users following this LINE Official Account.

    Args:
        message: Text message content to broadcast.

    Returns:
        Result of the broadcast operation (success or error message).
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
            return f"Broadcast sent successfully to all followers.\nContent: {message}"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", "Unknown error")
            except Exception:
                error_msg = response.text

            return (
                f"Broadcast failed\n"
                f"Status: {response.status_code}\n"
                f"Error: {error_msg}"
            )

    except ValueError as e:
        return f"Configuration error: {str(e)}"
    except httpx.TimeoutException:
        return "Connection timed out. Please check your network connection."
    except Exception as e:
        return f"Unexpected error: {str(e)}"


# ──────────────────────────────────────────────
# Tool 3: Get user profile
# ──────────────────────────────────────────────

@mcp.tool()
def get_user_profile(user_id: str) -> str:
    """
    Retrieve a LINE user's profile information.

    Args:
        user_id: LINE user ID (format: "U" + 32 alphanumeric characters)

    Returns:
        User profile (display name, picture URL, status message) or error message.
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
                f"User Profile\n"
                f"Display name: {data.get('displayName', 'N/A')}\n"
                f"userId: {data.get('userId', 'N/A')}\n"
                f"Language: {data.get('language', 'N/A')}\n"
                f"Status message: {data.get('statusMessage', '(none)')}\n"
                f"Picture URL: {data.get('pictureUrl', '(none)')}"
            )
            return result
        elif response.status_code == 404:
            return f"User {user_id} not found. Please verify the userId is correct."
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", "Unknown error")
            except Exception:
                error_msg = response.text
            return f"Query failed (status {response.status_code}): {error_msg}"

    except ValueError as e:
        return f"Configuration error: {str(e)}"
    except httpx.TimeoutException:
        return "Connection timed out. Please check your network connection."
    except Exception as e:
        return f"Unexpected error: {str(e)}"


# ──────────────────────────────────────────────
# Tool 4: Send Flex Message (rich layout message)
# ──────────────────────────────────────────────

@mcp.tool()
def send_flex_message(to: str, alt_text: str, flex_content: str) -> str:
    """
    Send a Flex Message (rich layout message) to a LINE user or group.

    Args:
        to: Recipient name (from line_user_id_map.json, e.g. "John")
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
