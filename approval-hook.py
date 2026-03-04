#!/usr/bin/env python3
"""
Slack Approval Hook for Claude Code

This hook intercepts tool calls and asks for approval via Slack.
Dangerous tools (Write, Edit, Bash, NotebookEdit) require approval.
"""

import json
import os
import sys
import time
from urllib import request

# Load config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config")
USERS_FILE = os.path.join(SCRIPT_DIR, "dashboard", "allowed_users.json")

# Tools that require approval
DANGEROUS_TOOLS = {"Write", "Edit", "Bash", "NotebookEdit", "Task"}

# Tools that are always safe
SAFE_TOOLS = {"Read", "Glob", "Grep", "WebSearch", "WebFetch"}

def load_config():
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.strip().split("=", 1)
                    config[key] = val.strip().strip('"')
    return config

def load_allowed_users():
    users = set()
    config = load_config()
    if config.get("ALLOWED_USER_ID"):
        users.add(config["ALLOWED_USER_ID"])
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE) as f:
                for u in json.load(f):
                    users.add(u.get("id", ""))
        except:
            pass
    return users

def slack_send(text):
    config = load_config()
    token = config.get("SLACK_BOT_TOKEN", "")
    channel_id = config.get("SLACK_DEFAULT_CHANNEL_ID", "")

    data = json.dumps({
        "channel": channel_id,
        "text": text,
        "unfurl_links": False
    }).encode()

    req = request.Request(
        "https://slack.com/api/chat.postMessage",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("ts")
    except Exception as e:
        log(f"Slack send error: {e}")
        return None

def slack_get_reply(after_ts, timeout=300):
    """Wait for a reply from an allowed user after the given timestamp"""
    config = load_config()
    token = config.get("SLACK_BOT_TOKEN", "")
    channel_id = config.get("SLACK_DEFAULT_CHANNEL_ID", "")
    allowed_users = load_allowed_users()

    start = time.time()
    poll_interval = 3

    while time.time() - start < timeout:
        url = f"https://slack.com/api/conversations.history?channel={channel_id}&oldest={after_ts}&limit=10"
        req = request.Request(url, headers={"Authorization": f"Bearer {token}"})

        try:
            with request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())

            for msg in result.get("messages", []):
                # Skip bot messages and messages before our question
                if msg.get("bot_id") or float(msg.get("ts", 0)) <= float(after_ts):
                    continue

                # Check if from allowed user
                if msg.get("user") not in allowed_users:
                    continue

                # Found a reply
                return msg.get("text", "").strip().lower()

        except Exception as e:
            log(f"Slack poll error: {e}")

        time.sleep(poll_interval)

    return None

def log(msg):
    log_file = os.path.join(SCRIPT_DIR, "approval.log")
    with open(log_file, "a") as f:
        f.write(f"{msg}\n")

def format_tool_description(tool_name, tool_input):
    """Create a human-readable description of what the tool will do"""
    if tool_name == "Write":
        path = tool_input.get("file_path", "unknown")
        content = tool_input.get("content", "")
        preview = content[:200] + "..." if len(content) > 200 else content
        return f"*Write file:* `{path}`\n```\n{preview}\n```"

    elif tool_name == "Edit":
        path = tool_input.get("file_path", "unknown")
        old = tool_input.get("old_string", "")[:100]
        new = tool_input.get("new_string", "")[:100]
        return f"*Edit file:* `{path}`\nReplace: `{old}`\nWith: `{new}`"

    elif tool_name == "Bash":
        cmd = tool_input.get("command", "unknown")
        return f"*Run command:*\n```\n{cmd}\n```"

    elif tool_name == "NotebookEdit":
        path = tool_input.get("notebook_path", "unknown")
        return f"*Edit notebook:* `{path}`"

    elif tool_name == "Task":
        desc = tool_input.get("description", "unknown task")
        return f"*Spawn agent:* {desc}"

    return f"*{tool_name}*: {json.dumps(tool_input)[:200]}"

def main():
    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except:
        # No input or invalid JSON - allow
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Check if this is a gateway-triggered session
    if os.environ.get("CLAUDE_SLACK_GATEWAY") != "1":
        # Not from gateway, skip approval
        sys.exit(0)

    # Safe tools don't need approval
    if tool_name in SAFE_TOOLS:
        sys.exit(0)

    # Dangerous tools need approval
    if tool_name in DANGEROUS_TOOLS:
        log(f"Approval requested for: {tool_name}")

        # Format the approval request
        description = format_tool_description(tool_name, tool_input)
        message = f":warning: *Approval Required*\n\n{description}\n\nReply *Y* to approve or *N* to deny"

        # Send to Slack
        msg_ts = slack_send(message)
        if not msg_ts:
            log("Failed to send approval request, denying")
            slack_send(":x: Failed to send approval request. Action denied.")
            sys.exit(1)

        # Wait for reply
        log("Waiting for approval...")
        reply = slack_get_reply(msg_ts, timeout=300)

        if reply is None:
            log("Timeout waiting for approval")
            slack_send(":hourglass: Approval timeout. Action denied.")
            sys.exit(1)

        if reply in ("y", "yes", "approve", "ok", "go"):
            log(f"Approved: {tool_name}")
            slack_send(":white_check_mark: Approved")
            sys.exit(0)
        else:
            log(f"Denied: {tool_name}")
            slack_send(":x: Denied")
            sys.exit(1)

    # Unknown tool - allow by default
    sys.exit(0)

if __name__ == "__main__":
    main()
