# LINE Messaging API — MCP Connector

透過 MCP（Model Context Protocol）協議，讓 Claude 直接呼叫 LINE Messaging API，
實現傳送訊息、推播通知等功能。

---

## 提供的 Tools

| Tool | 說明 |
|------|------|
| `send_push_message` | 傳送文字訊息給指定聯絡人名稱或 userId / groupId |
| `send_broadcast_message` | 廣播訊息給所有關注者 |
| `get_user_profile` | 查詢 LINE 使用者個人資料 |
| `send_flex_message` | 傳送自訂排版的 Flex Message |
| `list_contacts` | 列出 `line_user_id_map.json` 中所有已命名的聯絡人 |

---

## 安裝步驟

### 1. 安裝 Python 相依套件

```bash
pip install -r requirements.txt
```

### 2. 取得 LINE Channel Access Token

1. 前往 [LINE Developers Console](https://developers.line.biz/console/)
2. 選擇或建立一個 Provider
3. 建立 **Messaging API** Channel
4. 進入 Channel → **Messaging API** 頁籤
5. 在 **Channel access token** 區塊點選 **Issue**，複製 Token

### 3. 設定聯絡人對照表（選用）

複製範例檔並填入你的聯絡人資訊，讓你可以用名字而非原始 userId 傳送訊息：

```bash
cp line_user_id_map.example.json line_user_id_map.json
```

`line_user_id_map.json` 格式：

```json
[
  {
    "userId": "U4af4980629xxxxxxxxxxxxxxxxxxxxxxx",
    "name": "Alice"
  },
  {
    "userId": "Uabcdef1234xxxxxxxxxxxxxxxxxxxxxxx",
    "name": "Bob"
  }
]
```

> **注意**: `line_user_id_map.json` 含有私人資料，已列入 `.gitignore`，不會被提交至版本控制。

### 4. 設定客戶端

#### Claude Desktop

開啟 Claude Desktop 的設定檔：

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

加入以下設定（請修改路徑和 Token）：

```json
{
  "mcpServers": {
    "line-messaging": {
      "command": "python",
      "args": ["/absolute/path/to/line-mcp/line_mcp_server.py"],
      "env": {
        "LINE_CHANNEL_ACCESS_TOKEN": "你的_Channel_Access_Token"
      }
    }
  }
}
```

#### Claude Code（CLI）

可透過指令自動註冊（推薦）：

```bash
claude mcp add line-messaging -- python /absolute/path/to/line-mcp/line_mcp_server.py
```

然後設定環境變數（可加入 `.env` 或 shell profile）：

```bash
export LINE_CHANNEL_ACCESS_TOKEN=你的_Channel_Access_Token
```

或直接編輯全域設定檔手動加入：

- **macOS / Linux**: `~/.claude.json`
- **Windows**: `%USERPROFILE%\.claude.json`

```json
{
  "mcpServers": {
    "line-messaging": {
      "command": "python",
      "args": ["/absolute/path/to/line-mcp/line_mcp_server.py"],
      "env": {
        "LINE_CHANNEL_ACCESS_TOKEN": "你的_Channel_Access_Token"
      }
    }
  }
}
```

> **重要**: `args` 中的路徑必須是**絕對路徑**。

### 5. 重新啟動客戶端

儲存設定後重新啟動 Claude Desktop 或重新載入 Claude Code，即可在對話中使用 LINE 相關工具。

---

## 使用範例

在 Claude 中直接輸入：

```
傳送 LINE 訊息給「Alice」，內容是「你好！」
```

```
傳送 LINE 訊息給 userId "U1234567890abcdef"，內容是「你好！」
```

```
廣播一則訊息給所有關注者：「系統維護通知：今晚 22:00-23:00 暫停服務」
```

```
查詢 LINE 使用者 U1234567890abcdef 的個人資料
```

```
列出所有可用的聯絡人
```

---

## 如何取得 userId

使用者的 userId 無法直接查詢，需透過 **Webhook** 取得：

1. 在 LINE Developers Console 設定 Webhook URL
2. 當使用者傳訊息給你的 Bot，Webhook 會收到含有 `userId` 的事件
3. 記錄該 `userId` 並填入 `line_user_id_map.json`，即可用名字直接傳送訊息

> 詳細的 Webhook 伺服器架設與 userId 查詢方式，請參閱 [LINE Webhook Server — 操作說明](#line-webhook-server--操作說明)。

---

## 注意事項

- Push Message 需要使用者**已關注**你的 LINE Official Account（或曾互動過）
- 廣播訊息會發送給**所有關注者**，請謹慎使用
- 免費方案每月有**訊息數量限制**，詳見 [LINE 官方定價](https://www.linebiz.com/tw/service/line-official-account/plan/)
- Channel Access Token 請**妥善保管**，勿提交至版本控制系統
- `line_user_id_map.json` 含有使用者私人資料，同樣勿提交至版本控制系統

---

# LINE Webhook Server — 操作說明

`line_webhook_server.py` 是一個輕量的本地伺服器，用來接收 LINE Bot 事件並記錄傳過訊息的使用者 `userId`。

## 安裝與啟動

```bash
# 安裝相依套件
pip install fastapi uvicorn httpx --break-system-packages

# 設定環境變數
export LINE_CHANNEL_SECRET=你的_Channel_Secret

# 啟動伺服器
python line_webhook_server.py
```

## 取得 userId 的步驟

1. 用 [ngrok](https://ngrok.com/) 建立公開 HTTPS URL：
   ```bash
   ngrok http 8000
   ```

2. 前往 [LINE Developers Console](https://developers.line.biz/console/)，進入你的 Messaging API Channel → **Messaging API** 頁籤，將 Webhook URL 設為：
   ```
   https://xxxx.ngrok-free.app/webhook
   ```
   點選 **Verify** 確認連線，並開啟 **Use webhook**。

3. 請對方傳訊息給你的 Bot，伺服器會自動記錄其 `userId`。

4. 查詢已記錄的 userId：
   ```bash
   curl http://localhost:8000/senders/ids
   ```
   回傳範例：
   ```json
   {
     "total": 3,
     "userIds": ["U4af4980629...", "Uabcdef1234..."]
   }
   ```
   所有記錄同時會儲存在伺服器同目錄的 `line_recent_senders.json`，最多保留 200 筆。

5. 將取得的 `userId` 填入 `line_user_id_map.json`，並設定對應的名稱，即可在 `send_push_message` 等 MCP 工具中用名字傳送訊息。
