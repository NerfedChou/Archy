#!/bin/bash
# Start the Archy Rust Executor Daemon

# Check if daemon is already running
if [ -S /tmp/archy.sock ]; then
    # Check if the process is actually running
    if pgrep -f "archy-executor" > /dev/null; then
        echo "⚠️  Archy executor daemon is already running."
        exit 1
    else
        echo "🧹 Cleaning up stale socket..."
        rm -f /tmp/archy.sock
    fi
fi

# Navigate to Archy directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if binary exists
if [ ! -f "target/release/archy-executor" ]; then
    echo "🔨 Building Rust executor..."
    cargo build --release
    if [ $? -ne 0 ]; then
        echo "❌ Failed to build Rust executor"
        exit 1
    fi
fi

echo "🚀 Starting Archy Executor Daemon..."
./target/release/archy-executor &

# Wait a moment for the socket to be created
sleep 1

if [ -S /tmp/archy.sock ]; then
    echo "✅ Archy executor daemon is running!"
    echo "🐍 You can now use: ./scripts/archy"
else
    echo "❌ Failed to start daemon"
    exit 1
fi

