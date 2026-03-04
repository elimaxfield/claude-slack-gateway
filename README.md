# Claude Slack Gateway

A lightweight gateway that connects Claude Code to Slack, allowing you to control Claude remotely from your phone or any device with Slack access.

## Quick Install (Copy & Paste)

```bash
git clone git@github.com:elimaxfield/claude-slack-gateway.git ~/.claude/slack && cd ~/.claude/slack && ./install.sh
```

Then edit your config:
```bash
nano ~/.claude/slack/config
```

Add your Slack credentials:
```
SLACK_BOT_TOKEN="xoxb-your-token"
SLACK_DEFAULT_CHANNEL="claude-bot"
SLACK_DEFAULT_CHANNEL_ID="C0XXXXXXX"
ALLOWED_USER_ID="U0XXXXXXX"
```

Start the gateway:
```bash
~/.claude/slack/gateway-ctl.sh start
```

---

## Features

- **Remote Control**: Send tasks to Claude via Slack messages
- **Interactive Approvals**: Approve/deny file writes, commands, and other actions from Slack
- **Dashboard**: Web UI for monitoring, analytics, and user management
- **Multi-User Support**: Allowlist specific Slack users who can send commands
- **Zero Idle Cost**: Only uses Claude tokens when processing messages

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Slack     │────▶│   Gateway   │────▶│ Claude CLI  │
│  (Phone)    │◀────│  (Python)   │◀────│             │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  Dashboard  │
                    │  (Web UI)   │
                    └─────────────┘
```

## Prerequisites

- Python 3.8+
- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- A Slack workspace with admin access

## Quick Start

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name it "Claude Code Bot" and select your workspace
4. Go to **OAuth & Permissions** and add these Bot Token Scopes:
   - `chat:write`
   - `chat:write.public`
   - `channels:read`
   - `channels:history`
5. Click "Install to Workspace" and authorize
6. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 2. Configure the Gateway

```bash
# Copy the example config
cp config.example config

# Edit with your values
nano config
```

Add your Slack bot token and channel info:
```
SLACK_BOT_TOKEN="xoxb-your-token-here"
SLACK_DEFAULT_CHANNEL="claude-bot"
SLACK_DEFAULT_CHANNEL_ID="C0XXXXXXX"
ALLOWED_USER_ID="U0XXXXXXX"
```

To find your Channel ID:
```bash
./send-message.sh "test"
# The response will include the channel ID
```

To find your User ID:
- In Slack, click on your profile → "..." → "Copy member ID"

### 3. Set Up the Approval Hook

Copy the hook configuration to your Claude settings:
```bash
cp hooks.json ~/.claude/settings.json
```

### 4. Start the Gateway

```bash
./gateway-ctl.sh start
```

### 5. Start the Dashboard (optional)

```bash
cd dashboard
python3 server.py &
# Open http://localhost:8420
```

## Usage

### From Slack

Just send a message in your configured channel:
```
Create a Python script that prints hello world
```

Claude will process it and respond. If it needs to write files or run commands, you'll get an approval request:
```
⚠️ Approval Required

Write file: `/Users/you/hello.py`
```python
print("Hello, World!")
```

Reply Y to approve or N to deny
```

Reply `Y` or `N` to approve/deny.

### Control Commands

```bash
./gateway-ctl.sh start   # Start the gateway
./gateway-ctl.sh stop    # Stop the gateway
./gateway-ctl.sh status  # Check if running
./gateway-ctl.sh logs    # Watch live logs
```

### Helper Scripts

```bash
./send-message.sh "Hello"           # Send a message to Slack
./read-messages.sh                  # Read recent messages
./ask-and-wait.sh "Question?"       # Ask and wait for reply
./check-inbox.sh                    # Check pending messages
```

## Dashboard

The web dashboard provides:
- **Status**: Gateway running/stopped, start/stop controls
- **Messages**: View Slack message history
- **Users**: Manage allowed users who can send commands
- **Analytics**: Message counts and activity
- **Logs**: Real-time gateway logs
- **Settings**: Configure Slack tokens and channels

Access at: http://localhost:8420

## Files

| File | Purpose |
|------|---------|
| `gateway.py` | Main gateway service |
| `gateway-ctl.sh` | Start/stop/status control script |
| `approval-hook.py` | Claude hook for Slack approvals |
| `config` | Configuration (tokens, channels) |
| `dashboard/` | Web UI for monitoring |
| `send-message.sh` | Send messages to Slack |
| `read-messages.sh` | Read messages from Slack |
| `ask-and-wait.sh` | Ask question and wait for reply |

## Security

- Only users in the allowlist can send commands
- All file writes and commands require explicit approval
- Bot token is stored locally and never transmitted except to Slack

## Troubleshooting

**Gateway not processing messages?**
- Check `./gateway-ctl.sh status`
- View logs: `./gateway-ctl.sh logs`
- Ensure the bot is invited to the channel: `/invite @Claude Code Bot`

**Approval requests not working?**
- Check `~/.claude/settings.json` has the hook configured
- Ensure `CLAUDE_SLACK_GATEWAY=1` is set (gateway does this automatically)

## License

MIT
