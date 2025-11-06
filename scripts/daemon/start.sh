#!/bin/bash
# Start the Archy Rust Executor Daemon via systemd user service

# Ensure we have the correct DISPLAY
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi

echo "🚀 Starting Archy Executor Daemon (systemd user service)..."

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVICE_FILE="$PROJECT_ROOT/archy-executor-user.service"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

# Ensure user service directory exists
mkdir -p "$USER_SERVICE_DIR"

# Copy/update the service file
if [ -f "$SERVICE_FILE" ]; then
    echo "📝 Installing user service file..."
    cp "$SERVICE_FILE" "$USER_SERVICE_DIR/archy-executor.service"

    # Update DISPLAY in the service file if needed
    if [ -n "$DISPLAY" ]; then
        sed -i "s|Environment=\"DISPLAY=.*\"|Environment=\"DISPLAY=$DISPLAY\"|g" "$USER_SERVICE_DIR/archy-executor.service"
    fi

    # Reload systemd to recognize the new/updated service
    systemctl --user daemon-reload
    echo "✅ Service file installed"
else
    echo "⚠️  Service file not found: $SERVICE_FILE"
    echo "   Using existing service configuration..."
fi

# Enable the service to start on login
systemctl --user enable archy-executor.service 2>/dev/null || true

# Start the systemd user service
systemctl --user start archy-executor.service

# Wait for socket to be created
sleep 1

# Check if it started successfully
if systemctl --user is-active --quiet archy-executor.service; then
    echo "✅ Archy executor daemon is running!"
    PID=$(pgrep -f 'archy-executor' | head -1)
    if [ -n "$PID" ]; then
        echo "   Process: $PID (running as $(whoami))"
    fi
    echo "   Socket: /tmp/archy.sock"
    echo "   DISPLAY: $DISPLAY"
    echo ""
    echo "Service commands:"
    echo "  systemctl --user status archy-executor.service"
    echo "  systemctl --user stop archy-executor.service"
    echo "  systemctl --user restart archy-executor.service"
    echo "  systemctl --user disable archy-executor.service  # disable auto-start"
else
    echo "❌ Failed to start daemon"
    systemctl --user status archy-executor.service
    exit 1
fi

