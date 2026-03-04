#!/bin/bash
# Send a message to Slack from Claude Code
# Usage: send-message.sh "Your message here" [channel]

set -e

# Load config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config"

MESSAGE="$1"
CHANNEL="${2:-$SLACK_DEFAULT_CHANNEL}"

if [ -z "$MESSAGE" ]; then
    echo "Usage: $0 \"message\" [channel]"
    exit 1
fi

# Build JSON payload with proper escaping
PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'channel': '$CHANNEL',
    'text': '''$MESSAGE''',
    'unfurl_links': False
}))
")

# Send to Slack
response=$(curl -s -X POST "https://slack.com/api/chat.postMessage" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "$PAYLOAD")

# Check if successful
if echo "$response" | grep -q '"ok":true'; then
    echo "Message sent to #$CHANNEL"
else
    echo "Failed to send message:"
    echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    exit 1
fi
