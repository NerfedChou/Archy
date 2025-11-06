#!/bin/bash
# Quick restart script for Archy daemon via systemd

echo "🔄 Restarting Archy Executor Daemon (systemd user service)..."

# Restart the systemd user service
systemctl --user restart archy-executor.service

sleep 2

# Check if it started successfully
if systemctl --user is-active --quiet archy-executor.service; then
    echo "✅ Daemon restarted successfully!"
    echo "   Process: $(pgrep -f 'archy-executor')"
    echo "   Socket: /tmp/archy.sock"
    echo ""
    echo "View logs with: journalctl --user -u archy-executor.service -f"
else
    echo "❌ Failed to restart daemon"
    echo "Check logs with: journalctl --user -u archy-executor.service -n 50"
    exit 1
fi

