#!/bin/bash
# Stop the Archy Rust Executor Daemon

echo "🛑 Stopping Archy Executor Daemon..."

# Find and kill the archy-executor process
pkill -f archy-executor

# Remove the socket file
rm -f /tmp/archy.sock

if [ $? -eq 0 ]; then
    echo "✅ Archy executor daemon stopped"
else
    echo "⚠️  No daemon was running"
fi

