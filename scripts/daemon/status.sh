#!/bin/bash
# Check the status of the Archy Executor Daemon

if pgrep -f "archy-executor" > /dev/null; then
    echo "✅ Archy executor daemon is RUNNING"
    if [ -S /tmp/archy.sock ]; then
        echo "✅ Socket is available at /tmp/archy.sock"
    else
        echo "⚠️  Socket not found (may be unhealthy)"
    fi
    exit 0
else
    echo "❌ Archy executor daemon is NOT RUNNING"
    exit 1
fi
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
cd "$(dirname "$SCRIPT_DIR")"  # Go up to scripts, then to root
cd ..

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
else
    echo "❌ Failed to start daemon"
    exit 1
fi

