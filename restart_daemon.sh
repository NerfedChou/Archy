#!/bin/bash
# Quick restart script for Archy daemon

echo "🛑 Stopping any running daemon..."
# Try regular kill first
pkill -9 archy-executor 2>/dev/null
# If socket is owned by root, use sudo to clean it
if [ -S /tmp/archy.sock ]; then
    SOCKET_OWNER=$(stat -c '%U' /tmp/archy.sock 2>/dev/null)
    if [ "$SOCKET_OWNER" = "root" ]; then
        echo "   Socket owned by root, using sudo to clean..."
        sudo pkill -9 archy-executor 2>/dev/null
        sudo rm -f /tmp/archy.sock
    else
        rm -f /tmp/archy.sock
    fi
fi
sleep 1

echo "🚀 Starting daemon with fixed code..."
cd /home/chef/Archy
./target/release/archy-executor &

sleep 2

if [ -S /tmp/archy.sock ]; then
    echo "✅ Daemon restarted successfully!"
    echo "   Socket: /tmp/archy.sock"
    echo "   PID: $(pgrep archy-executor)"
else
    echo "❌ Failed to start daemon"
    exit 1
fi

