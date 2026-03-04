#!/bin/bash
# Check inbox for new messages and return them
# Usage: ./check-inbox.sh [--clear]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INBOX="$SCRIPT_DIR/inbox"

if [ ! -f "$INBOX" ] || [ ! -s "$INBOX" ]; then
    echo "No new messages"
    exit 0
fi

# Show messages
cat "$INBOX"

# Clear if requested
if [ "$1" = "--clear" ]; then
    > "$INBOX"
fi
