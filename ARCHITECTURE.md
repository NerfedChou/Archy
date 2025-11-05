# Archy Architecture

## Overview

Archy uses a **hybrid Python + Rust architecture** for optimal performance and maintainability.

```
┌─────────────────────────────────────────────────────┐
│                   Gemini API                        │
│          (AI Model / Language Processing)           │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│              Python (Brain)                         │
│  ┌─────────────────────────────────────────────┐   │
│  │ archy_chat.py                               │   │
│  │ - Conversation history management           │   │
│  │ - System prompt logic                       │   │
│  │ - Command parsing & decision making         │   │
│  │ - Natural language analysis                 │   │
│  │ - API request handling                      │   │
│  └─────────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ Unix Socket (/tmp/archy.sock)
                   │ JSON over IPC
                   ▼
┌─────────────────────────────────────────────────────┐
│              Rust (Hands)                           │
│  ┌─────────────────────────────────────────────┐   │
│  │ archy-executor                              │   │
│  │ - Fast command execution                    │   │
│  │ - Process monitoring                        │   │
│  │ - tmux session management                   │   │
│  │ - Terminal output capture                   │   │
│  │ - System-level operations                   │   │
│  │ - Error handling & recovery                 │   │
│  └─────────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│         System Integration Layer                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │   tmux   │  │   foot   │  │  shell   │          │
│  │ (session)│  │(terminal)│  │  (bash)  │          │
│  └──────────┘  └──────────┘  └──────────┘          │
└─────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Python Brain (`scripts/archy_chat.py`)

**Purpose**: High-level intelligence and reasoning

**Responsibilities**:
- Communicate with Gemini API
- Maintain conversation context
- Parse user intents
- Generate system prompts
- Make decisions about what actions to take
- Format responses to user

**Why Python?**:
- Excellent for API integration
- Rich ecosystem for AI/ML work
- Easy to modify prompts and logic
- Good for string processing and JSON handling

### Rust Hands (`src/main.rs`)

**Purpose**: Fast, reliable system operations

**Responsibilities**:
- Execute shell commands in tmux
- Monitor process states
- Manage tmux sessions (create/destroy/check)
- Open/close terminal windows
- Capture terminal output efficiently
- Handle system-level errors

**Why Rust?**:
- Fast subprocess execution
- Better process monitoring
- Memory safety guarantees
- Excellent error handling
- Lower resource usage
- More reliable for long-running daemon

### Communication Layer (`rust_executor.py`)

**Purpose**: Bridge between Python and Rust

**Mechanism**: Unix domain socket at `/tmp/archy.sock`

**Protocol**: JSON messages over socket

```python
# Request format
{
    "action": "execute" | "capture" | "check_session" | "open_terminal" | "close_terminal" | "close_session",
    "data": {
        "command": "...",      # for execute
        "lines": 100,          # for capture
        "session": "archy_session"
    }
}

# Response format
{
    "success": bool,
    "output": str | null,
    "error": str | null,
    "exists": bool | null
}
```

## Data Flow Examples

### Example 1: Execute a Command

```
User: "list my files"
    ↓
Python:
    - Analyzes intent
    - Decides to run 'ls -la'
    - Calls rust_executor.execute_in_tmux("ls -la")
    ↓
Unix Socket:
    {"action": "execute", "data": {"command": "ls -la"}}
    ↓
Rust:
    - Receives request
    - Validates session exists
    - Runs: tmux send-keys -t archy_session "ls -la" C-m
    - Returns success
    ↓
Python:
    - Gets success confirmation
    - Waits briefly
    - Calls rust_executor.capture_output()
    ↓
Unix Socket:
    {"action": "capture", "data": {"lines": 100}}
    ↓
Rust:
    - Captures tmux pane output
    - Returns terminal text
    ↓
Python:
    - Parses output
    - Sends to Gemini for analysis
    - Presents summary to user
```

### Example 2: Open Terminal

```
User: "open a terminal"
    ↓
Python:
    - Recognizes terminal action
    - Calls rust_executor.open_terminal()
    ↓
Unix Socket:
    {"action": "open_terminal", "data": {}}
    ↓
Rust:
    - Checks if tmux session exists
    - Creates session if needed (tmux new-session -d -s archy_session)
    - Spawns foot terminal: foot -e tmux attach -t archy_session
    - Returns success
    ↓
Python:
    - Confirms to user
    - Terminal window visible to user
```

## Benefits of This Architecture

### Separation of Concerns
- Python handles AI logic (its strength)
- Rust handles system calls (its strength)
- Each component focused on what it does best

### Performance
- Rust executor is compiled → faster than Python subprocesses
- Unix socket communication is very fast (no network overhead)
- Daemon stays running → no startup cost per command

### Reliability
- Rust's error handling prevents crashes
- Process monitoring is more robust
- Memory safety guarantees

### Maintainability
- Python code easier to modify for prompt engineering
- Rust code can be optimized independently
- Clear API boundary makes testing easier

### Extensibility
- Easy to add new actions to Rust executor
- Python logic can evolve without touching system layer
- Can add multiple language frontends (Python, CLI, etc.)

## File Structure

```
Archy/
├── src/
│   └── main.rs                 # Rust executor daemon
├── scripts/
│   ├── archy                   # Main CLI entry point (bash)
│   ├── archy_chat.py          # Python brain
│   └── rust_executor.py       # Python-Rust bridge
├── target/
│   └── release/
│       └── archy-executor     # Compiled Rust binary
├── Cargo.toml                 # Rust dependencies
├── start_daemon.sh            # Start the Rust daemon
├── stop_daemon.sh             # Stop the Rust daemon
└── test_executor.py           # Test suite for executor
```

## Running the System

### Automatic Mode (Recommended)
```bash
archy                          # Daemon starts automatically if needed
```

### Manual Mode
```bash
# Start daemon manually
./start_daemon.sh

# Use Archy
archy "what's my uptime?"

# Stop daemon when done
./stop_daemon.sh
```

## Debugging

### Check if daemon is running
```bash
ls -la /tmp/archy.sock         # Socket should exist
pgrep -f archy-executor        # Should show PID
```

### Test executor directly
```bash
python3 test_executor.py       # Runs test suite
```

### View daemon output
```bash
# Run daemon in foreground
./target/release/archy-executor
```

## Future Enhancements

### Potential Improvements
- [ ] Add WebSocket support for real-time streaming
- [ ] Implement command queuing in Rust
- [ ] Add metrics and logging to executor
- [ ] Support multiple concurrent sessions
- [ ] Add configuration file for executor settings
- [ ] Implement plugin system for custom actions
- [ ] Add security layer (authentication, sandboxing)
- [ ] Support remote execution over network

### Performance Optimizations
- [ ] Connection pooling for socket
- [ ] Batch command execution
- [ ] Async I/O in Rust executor
- [ ] Output streaming instead of buffering
- [ ] Smart caching of terminal state

