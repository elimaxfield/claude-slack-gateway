#!/bin/bash
# Read recent messages from a Slack channel
# Usage: read-messages.sh [limit]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config"

LIMIT="${1:-10}"
CHANNEL_ID="$SLACK_DEFAULT_CHANNEL_ID"

response=$(curl -s "https://slack.com/api/conversations.history?channel=$CHANNEL_ID&limit=$LIMIT" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN")

echo "$response" | python3 -c "
import sys, json
from datetime import datetime

data = json.load(sys.stdin)
if not data.get('ok'):
    print('Error:', data.get('error', 'Unknown error'))
    sys.exit(1)

messages = data.get('messages', [])
for msg in reversed(messages):
    ts = datetime.fromtimestamp(float(msg['ts'])).strftime('%H:%M:%S')
    user = msg.get('user', 'unknown')[:8]
    text = msg.get('text', '')
    # Check if it's from a bot
    if msg.get('bot_id'):
        user = 'claude'
    print(f'[{ts}] {user}: {text}')
"
