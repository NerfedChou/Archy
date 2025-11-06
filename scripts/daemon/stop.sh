#!/bin/bash
# Stop the Archy Rust Executor Daemon via systemd user service

echo "🛑 Stopping Archy Executor Daemon..."

# Stop the systemd user service
systemctl --user stop archy-executor.service

sleep 1

# Verify it's stopped
if systemctl --user is-active --quiet archy-executor.service; then
    echo "⚠️  Service is still running, forcing kill..."
    pkill -9 archy-executor
    rm -f /tmp/archy.sock
else
    echo "✅ Archy executor daemon stopped"
fi

