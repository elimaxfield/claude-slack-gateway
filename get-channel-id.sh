#!/bin/bash
# Get the channel ID for a channel name
# Usage: get-channel-id.sh channel-name

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config"

CHANNEL_NAME="${1:-$SLACK_DEFAULT_CHANNEL}"

response=$(curl -s "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=200" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN")

channel_id=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for ch in data.get('channels', []):
    if ch['name'] == '$CHANNEL_NAME':
        print(ch['id'])
        break
" 2>/dev/null)

if [ -n "$channel_id" ]; then
    echo "$channel_id"
else
    echo "Channel #$CHANNEL_NAME not found" >&2
    exit 1
fi
