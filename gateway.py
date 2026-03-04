#!/usr/bin/env python3
"""
Claude-Slack Gateway

A lightweight service that bridges Slack messages to Claude CLI.
Zero tokens used while waiting - only runs Claude when messages arrive.

Usage:
    python3 gateway.py              # Run in foreground
    python3 gateway.py --daemon     # Run as background daemon
"""

import json
import os
import subprocess
import sys
import time
import signal
import argparse
from datetime import datetime
from urllib import request
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config"
USERS_FILE = SCRIPT_DIR / "dashboard" / "allowed_users.json"
LAST_TS_FILE = SCRIPT_DIR / ".gateway_last_ts"
LOG_FILE = SCRIPT_DIR / "gateway.log"
PID_FILE = SCRIPT_DIR / "gateway.pid"

POLL_INTERVAL = 5  # seconds between Slack checks

class Gateway:
    def __init__(self):
        self.config = self.load_config()
        self.allowed_users = self.load_allowed_users()
        self.last_ts = self.load_last_ts()
        self.running = True

        # Handle shutdown gracefully
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def log(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

    def load_config(self):
        config = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        key, val = line.strip().split("=", 1)
                        config[key] = val.strip().strip('"')
        return config

    def load_allowed_users(self):
        users = set()
        # From config
        if self.config.get("ALLOWED_USER_ID"):
            users.add(self.config["ALLOWED_USER_ID"])
        # From users file
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE) as f:
                    for u in json.load(f):
                        users.add(u.get("id", ""))
            except:
                pass
        return users

    def load_last_ts(self):
        if LAST_TS_FILE.exists():
            return LAST_TS_FILE.read_text().strip()
        # Start from now
        ts = str(time.time())
        LAST_TS_FILE.write_text(ts)
        return ts

    def save_last_ts(self, ts):
        self.last_ts = ts
        LAST_TS_FILE.write_text(ts)

    def slack_api(self, endpoint, method="GET", data=None):
        """Make Slack API call"""
        token = self.config.get("SLACK_BOT_TOKEN", "")
        url = f"https://slack.com/api/{endpoint}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }

        req_data = json.dumps(data).encode() if data else None
        req = request.Request(url, data=req_data, headers=headers, method=method)

        try:
            with request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            self.log(f"Slack API error: {e}")
            return {"ok": False, "error": str(e)}

    def send_slack(self, text):
        """Send message to Slack"""
        channel_id = self.config.get("SLACK_DEFAULT_CHANNEL_ID", "")
        result = self.slack_api("chat.postMessage", "POST", {
            "channel": channel_id,
            "text": text,
            "unfurl_links": False
        })
        return result.get("ok", False)

    def get_new_messages(self):
        """Get new messages from Slack"""
        channel_id = self.config.get("SLACK_DEFAULT_CHANNEL_ID", "")
        result = self.slack_api(
            f"conversations.history?channel={channel_id}&oldest={self.last_ts}&limit=20"
        )

        if not result.get("ok"):
            return []

        messages = []
        new_ts = self.last_ts

        for msg in reversed(result.get("messages", [])):
            ts = msg.get("ts", "")

            # Skip bot messages
            if msg.get("bot_id"):
                if float(ts) > float(new_ts):
                    new_ts = ts
                continue

            # Skip if already processed
            if float(ts) <= float(self.last_ts):
                continue

            # Check if user is allowed
            user = msg.get("user", "")
            if user not in self.allowed_users:
                self.log(f"Ignoring message from unauthorized user: {user}")
                if float(ts) > float(new_ts):
                    new_ts = ts
                continue

            text = msg.get("text", "").strip()
            if text:
                messages.append({"text": text, "user": user, "ts": ts})

            if float(ts) > float(new_ts):
                new_ts = ts

        self.save_last_ts(new_ts)
        return messages

    def run_claude(self, prompt):
        """Run Claude CLI with the given prompt and return response"""
        self.log(f"Running Claude with prompt: {prompt[:50]}...")

        try:
            # Run claude CLI with tool use enabled
            # The approval hook will handle permission requests via Slack
            claude_path = os.path.expanduser("~/.local/bin/claude")

            # Set environment variable so hook knows this is from gateway
            env = os.environ.copy()
            env["CLAUDE_SLACK_GATEWAY"] = "1"

            # Run with --print for output and --dangerously-skip-permissions
            # because our hook handles approvals via Slack
            result = subprocess.run(
                [claude_path, "-p", prompt, "--dangerously-skip-permissions"],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout (approvals take time)
                cwd=os.path.expanduser("~"),
                env=env
            )

            response = result.stdout.strip()
            if result.returncode != 0 and result.stderr:
                self.log(f"Claude stderr: {result.stderr}")

            return response if response else "No response from Claude"

        except subprocess.TimeoutExpired:
            return "Request timed out after 10 minutes"
        except FileNotFoundError:
            return "Error: Claude CLI not found. Is it installed?"
        except Exception as e:
            return f"Error running Claude: {e}"

    def process_message(self, msg):
        """Process a single message"""
        text = msg["text"]

        # Send "thinking" indicator
        self.send_slack(":hourglass: Processing your request...")

        # Run Claude
        response = self.run_claude(text)

        # Send response back to Slack
        # Split long messages if needed (Slack limit is ~4000 chars)
        if len(response) > 3900:
            chunks = [response[i:i+3900] for i in range(0, len(response), 3900)]
            for i, chunk in enumerate(chunks):
                prefix = f"[Part {i+1}/{len(chunks)}]\n" if len(chunks) > 1 else ""
                self.send_slack(prefix + chunk)
        else:
            self.send_slack(response)

        self.log(f"Processed message, response length: {len(response)}")

    def shutdown(self, signum=None, frame=None):
        self.log("Shutting down gateway...")
        self.running = False
        if PID_FILE.exists():
            PID_FILE.unlink()

    def run(self):
        """Main loop"""
        self.log("=" * 50)
        self.log("Claude-Slack Gateway started")
        self.log(f"Monitoring channel: {self.config.get('SLACK_DEFAULT_CHANNEL', 'unknown')}")
        self.log(f"Allowed users: {len(self.allowed_users)}")
        self.log(f"Poll interval: {POLL_INTERVAL}s")
        self.log("=" * 50)

        # Write PID file
        PID_FILE.write_text(str(os.getpid()))

        # Notify Slack
        self.send_slack(":robot_face: Gateway is online. Send me a task!")

        while self.running:
            try:
                # Reload allowed users periodically (in case dashboard updates them)
                self.allowed_users = self.load_allowed_users()

                # Check for new messages
                messages = self.get_new_messages()

                for msg in messages:
                    self.log(f"New message: {msg['text'][:50]}...")
                    self.process_message(msg)

            except Exception as e:
                self.log(f"Error in main loop: {e}")

            time.sleep(POLL_INTERVAL)

        self.log("Gateway stopped")


def main():
    parser = argparse.ArgumentParser(description="Claude-Slack Gateway")
    parser.add_argument("--daemon", "-d", action="store_true", help="Run as daemon")
    args = parser.parse_args()

    if args.daemon:
        # Fork to background
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)

        # Redirect stdio
        sys.stdin = open(os.devnull)
        sys.stdout = open(LOG_FILE, "a")
        sys.stderr = sys.stdout

    gateway = Gateway()
    gateway.run()


if __name__ == "__main__":
    main()
