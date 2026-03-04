#!/bin/bash
# Send a question to Slack and wait for a reply from Eli Maxfield only
# Usage: ask-and-wait.sh "Your question here" [timeout_seconds]
#
# Returns the reply text on success, exits with error if timeout

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config"

QUESTION="$1"
TIMEOUT="${2:-300}"  # Default 5 minute timeout
CHANNEL_ID="$SLACK_DEFAULT_CHANNEL_ID"
POLL_INTERVAL=5

if [ -z "$QUESTION" ]; then
    echo "Usage: $0 \"question\" [timeout_seconds]"
    exit 1
fi

# Build JSON payload with proper escaping
PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'channel': '$CHANNEL_ID',
    'text': '''$QUESTION''',
    'unfurl_links': False
}))
")

# Send the question
response=$(curl -s -X POST "https://slack.com/api/chat.postMessage" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "$PAYLOAD")

msg_ts=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ts',''))")

if [ -z "$msg_ts" ]; then
    echo "Failed to send message" >&2
    exit 1
fi

echo "Waiting for reply from Eli (timeout: ${TIMEOUT}s)..." >&2

# Poll for replies
elapsed=0
while [ $elapsed -lt $TIMEOUT ]; do
    sleep $POLL_INTERVAL
    elapsed=$((elapsed + POLL_INTERVAL))

    # Get recent messages
    history=$(curl -s "https://slack.com/api/conversations.history?channel=$CHANNEL_ID&oldest=$msg_ts&limit=10" \
        -H "Authorization: Bearer $SLACK_BOT_TOKEN")

    # Look for a reply from ALLOWED_USER_ID only
    reply=$(echo "$history" | python3 -c "
import sys, json

ALLOWED_USER = '$ALLOWED_USER_ID'

data = json.load(sys.stdin)
for msg in data.get('messages', []):
    # Skip bot messages and the original question
    if msg.get('bot_id') or msg.get('ts') == '$msg_ts':
        continue
    # SECURITY: Only accept from allowed user
    if msg.get('user') != ALLOWED_USER:
        continue
    # Found an authorized reply
    print(msg.get('text', ''))
    sys.exit(0)
" 2>/dev/null)

    if [ -n "$reply" ]; then
        echo "$reply"
        exit 0
    fi
done

echo "Timeout waiting for reply" >&2
exit 1
