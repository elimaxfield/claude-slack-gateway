#!/bin/bash
# Claude Slack Gateway - Installation Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==================================="
echo "Claude Slack Gateway - Installer"
echo "==================================="
echo

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Check for Claude CLI
if ! command -v claude &> /dev/null; then
    echo "Error: Claude CLI is required but not installed."
    echo "Install it from: https://claude.ai/code"
    exit 1
fi

# Make scripts executable
echo "Making scripts executable..."
chmod +x "$SCRIPT_DIR"/*.sh
chmod +x "$SCRIPT_DIR"/*.py

# Create config from example if not exists
if [ ! -f "$SCRIPT_DIR/config" ]; then
    echo "Creating config file..."
    cp "$SCRIPT_DIR/config.example" "$SCRIPT_DIR/config"
    chmod 600 "$SCRIPT_DIR/config"
    echo ""
    echo "IMPORTANT: Edit $SCRIPT_DIR/config with your Slack credentials"
    echo ""
fi

# Create dashboard directories
mkdir -p "$SCRIPT_DIR/dashboard"

# Set up Claude hooks
echo "Setting up Claude hooks..."
HOOKS_FILE="$HOME/.claude/settings.json"
HOOK_PATH="$SCRIPT_DIR/approval-hook.py"

if [ -f "$HOOKS_FILE" ]; then
    echo "Warning: $HOOKS_FILE already exists."
    echo "You may need to manually add the hook configuration."
else
    cat > "$HOOKS_FILE" << EOF
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "command": "$HOOK_PATH"
      }
    ]
  }
}
EOF
    echo "Hook configuration created at $HOOKS_FILE"
fi

# Create LaunchAgent for macOS (optional)
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$PLIST_DIR/com.claude.slack-gateway.plist"

    if [ ! -f "$PLIST_FILE" ]; then
        echo "Creating macOS LaunchAgent..."
        mkdir -p "$PLIST_DIR"
        cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude.slack-gateway</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPT_DIR/gateway.py</string>
    </array>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/gateway.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/gateway.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF
        echo "LaunchAgent created. Use './gateway-ctl.sh start' to start."
    fi
fi

echo ""
echo "==================================="
echo "Installation complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit $SCRIPT_DIR/config with your Slack credentials"
echo "2. Invite the bot to your Slack channel: /invite @YourBotName"
echo "3. Start the gateway: ./gateway-ctl.sh start"
echo "4. (Optional) Start the dashboard: cd dashboard && python3 server.py"
echo ""
