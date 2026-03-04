#!/usr/bin/env python3
"""
Claude Code Slack Integration Dashboard - Backend API
"""

import json
import os
import re
import time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import subprocess

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SLACK_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_FILE = os.path.join(SLACK_DIR, "config")
INBOX_FILE = os.path.join(SLACK_DIR, "inbox")
ANALYTICS_FILE = os.path.join(SCRIPT_DIR, "analytics.json")
USERS_FILE = os.path.join(SCRIPT_DIR, "allowed_users.json")
GATEWAY_LOG_FILE = os.path.join(SLACK_DIR, "gateway.log")

def load_config():
    """Load Slack config"""
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.strip().split("=", 1)
                    config[key] = val.strip().strip('"')
    return config

def save_config(config):
    """Save Slack config"""
    lines = []
    for key, val in config.items():
        if "#" in val:
            lines.append(f'{key}="{val}"  {val.split("#")[1] if "#" in val else ""}')
        else:
            lines.append(f'{key}="{val}"')
    with open(CONFIG_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")

def load_analytics():
    """Load analytics data"""
    if os.path.exists(ANALYTICS_FILE):
        with open(ANALYTICS_FILE) as f:
            return json.load(f)
    return {
        "messages_sent": 0,
        "messages_received": 0,
        "approvals_requested": 0,
        "approvals_granted": 0,
        "history": []
    }

def save_analytics(data):
    """Save analytics data"""
    with open(ANALYTICS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_allowed_users():
    """Load allowed users list"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    # Initialize with current allowed user from config
    config = load_config()
    users = []
    if config.get("ALLOWED_USER_ID"):
        users.append({
            "id": config["ALLOWED_USER_ID"],
            "name": "Eli Maxfield",
            "added": datetime.now().isoformat()
        })
        save_allowed_users(users)
    return users

def save_allowed_users(users):
    """Save allowed users list"""
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def load_inbox():
    """Load inbox messages"""
    messages = []
    if os.path.exists(INBOX_FILE):
        with open(INBOX_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    # Parse [timestamp] message format
                    match = re.match(r'\[(.+?)\] (.+)', line)
                    if match:
                        messages.append({
                            "timestamp": match.group(1),
                            "text": match.group(2)
                        })
    return messages

def load_gateway_logs(limit=200):
    """Load gateway logs"""
    if os.path.exists(GATEWAY_LOG_FILE):
        with open(GATEWAY_LOG_FILE) as f:
            lines = f.readlines()
            return [line.strip() for line in lines[-limit:] if line.strip()]
    return []

def get_gateway_status():
    """Check if gateway is running"""
    pid_file = os.path.join(SLACK_DIR, "gateway.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
            # Check if process is running
            os.kill(pid, 0)
            return {"running": True, "pid": pid}
        except (ProcessLookupError, ValueError):
            return {"running": False, "pid": None}
    return {"running": False, "pid": None}

def slack_api_call(endpoint, method="GET", data=None):
    """Make Slack API call"""
    config = load_config()
    token = config.get("SLACK_BOT_TOKEN", "")

    import urllib.request
    url = f"https://slack.com/api/{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    req_data = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/config":
            self.send_json(load_config())
        elif parsed.path == "/api/analytics":
            self.send_json(load_analytics())
        elif parsed.path == "/api/users":
            self.send_json(load_allowed_users())
        elif parsed.path == "/api/inbox":
            self.send_json(load_inbox())
        elif parsed.path == "/api/status":
            gateway = get_gateway_status()
            self.send_json({
                "gateway_running": gateway["running"],
                "gateway_pid": gateway["pid"],
                "timestamp": datetime.now().isoformat()
            })
        elif parsed.path == "/api/messages":
            # Get recent Slack messages
            config = load_config()
            channel_id = config.get("SLACK_DEFAULT_CHANNEL_ID", "")
            result = slack_api_call(f"conversations.history?channel={channel_id}&limit=50")
            self.send_json(result)
        elif parsed.path == "/api/logs":
            # Get gateway logs
            logs = load_gateway_logs()
            self.send_json({"logs": logs})
        else:
            super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length else "{}"
        data = json.loads(body) if body else {}
        parsed = urlparse(self.path)

        if parsed.path == "/api/users":
            # Add new user
            users = load_allowed_users()
            users.append({
                "id": data.get("id"),
                "name": data.get("name", "Unknown"),
                "added": datetime.now().isoformat()
            })
            save_allowed_users(users)
            # Update config with all user IDs
            self.send_json({"ok": True, "users": users})

        elif parsed.path == "/api/send":
            # Send a message to Slack
            result = slack_api_call("chat.postMessage", "POST", {
                "channel": load_config().get("SLACK_DEFAULT_CHANNEL_ID"),
                "text": data.get("text", "")
            })
            # Update analytics
            analytics = load_analytics()
            analytics["messages_sent"] += 1
            analytics["history"].append({
                "type": "sent",
                "text": data.get("text", "")[:100],
                "timestamp": datetime.now().isoformat()
            })
            save_analytics(analytics)
            self.send_json(result)

        elif parsed.path == "/api/config":
            # Update config
            config = load_config()
            config.update(data)
            save_config(config)
            self.send_json({"ok": True})

        elif parsed.path == "/api/gateway/start":
            subprocess.run([os.path.join(SLACK_DIR, "gateway-ctl.sh"), "start"])
            self.send_json({"ok": True})

        elif parsed.path == "/api/gateway/stop":
            subprocess.run([os.path.join(SLACK_DIR, "gateway-ctl.sh"), "stop"])
            self.send_json({"ok": True})

        elif parsed.path == "/api/inbox/clear":
            open(INBOX_FILE, "w").close()
            self.send_json({"ok": True})

        elif parsed.path == "/api/logs/clear":
            open(GATEWAY_LOG_FILE, "w").close()
            self.send_json({"ok": True})

        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)

        if parsed.path.startswith("/api/users/"):
            user_id = parsed.path.split("/")[-1]
            users = load_allowed_users()
            users = [u for u in users if u["id"] != user_id]
            save_allowed_users(users)
            self.send_json({"ok": True, "users": users})
        else:
            self.send_error(404)

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

def main():
    port = 8420
    server = HTTPServer(("localhost", port), DashboardHandler)
    print(f"Dashboard running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()
