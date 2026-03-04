#!/bin/bash
# Slack channel watcher - runs in background, queues messages for Claude Code
# Supports multiple allowed users from dashboard/allowed_users.json
# Usage: ./watcher.sh &
# Stop with: pkill -f "slack/watcher.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config"

INBOX="$SCRIPT_DIR/inbox"
LAST_TS_FILE="$SCRIPT_DIR/.last_ts"
USERS_FILE="$SCRIPT_DIR/dashboard/allowed_users.json"
ANALYTICS_FILE="$SCRIPT_DIR/dashboard/analytics.json"
POLL_INTERVAL=5
CHANNEL_ID="$SLACK_DEFAULT_CHANNEL_ID"

# Initialize
touch "$INBOX"
touch "$LAST_TS_FILE"

# Get initial timestamp (start watching from now)
if [ ! -s "$LAST_TS_FILE" ]; then
    echo "$(date +%s).000000" > "$LAST_TS_FILE"
fi

echo "[watcher] Started monitoring #$SLACK_DEFAULT_CHANNEL"
echo "[watcher] Inbox: $INBOX"
echo "[watcher] Poll interval: ${POLL_INTERVAL}s"

while true; do
    LAST_TS=$(cat "$LAST_TS_FILE")

    # Fetch messages newer than last seen
    response=$(curl -s "https://slack.com/api/conversations.history?channel=$CHANNEL_ID&oldest=$LAST_TS&limit=20" \
        -H "Authorization: Bearer $SLACK_BOT_TOKEN")

    # Process new messages
    echo "$response" | python3 -c "
import sys, json, os
from datetime import datetime

# Load allowed users
ALLOWED_USERS = set()
USERS_FILE = '$USERS_FILE'
CONFIG_USER = '${ALLOWED_USER_ID:-}'

# Add user from config
if CONFIG_USER:
    ALLOWED_USERS.add(CONFIG_USER)

# Add users from JSON file
if os.path.exists(USERS_FILE):
    try:
        with open(USERS_FILE) as f:
            users = json.load(f)
            for u in users:
                ALLOWED_USERS.add(u.get('id', ''))
    except:
        pass

data = json.load(sys.stdin)
if not data.get('ok'):
    sys.exit(0)

messages = data.get('messages', [])
new_ts = '$LAST_TS'
queued_count = 0

for msg in reversed(messages):
    ts = msg.get('ts', '')
    user = msg.get('user', '')

    # Skip bot messages
    if msg.get('bot_id'):
        if float(ts) > float(new_ts):
            new_ts = ts
        continue

    # Skip if we've already seen this
    if float(ts) <= float('$LAST_TS'):
        continue

    # SECURITY: Only accept messages from allowed users
    if user not in ALLOWED_USERS:
        print(f'[watcher] Ignoring message from unauthorized user: {user}')
        if float(ts) > float(new_ts):
            new_ts = ts
        continue

    # Authorized message - queue it
    text = msg.get('text', '').strip()
    time_str = datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S')

    if text:
        # Append to inbox
        with open('$INBOX', 'a') as f:
            f.write(f'[{time_str}] {text}\n')
        queued_count += 1
        print(f'[watcher] Queued: {text[:50]}...' if len(text) > 50 else f'[watcher] Queued: {text}')

        # Update analytics
        analytics_file = '$ANALYTICS_FILE'
        try:
            if os.path.exists(analytics_file):
                with open(analytics_file) as f:
                    analytics = json.load(f)
            else:
                analytics = {'messages_sent': 0, 'messages_received': 0, 'approvals_requested': 0, 'approvals_granted': 0, 'history': []}

            analytics['messages_received'] = analytics.get('messages_received', 0) + 1
            analytics['history'].append({
                'type': 'received',
                'text': text[:100],
                'timestamp': datetime.now().isoformat()
            })
            # Keep only last 100 history items
            analytics['history'] = analytics['history'][-100:]

            with open(analytics_file, 'w') as f:
                json.dump(analytics, f, indent=2)
        except Exception as e:
            print(f'[watcher] Analytics error: {e}')

    if float(ts) > float(new_ts):
        new_ts = ts

# Save newest timestamp
with open('$LAST_TS_FILE', 'w') as f:
    f.write(new_ts)
" 2>/dev/null

    sleep $POLL_INTERVAL
done
