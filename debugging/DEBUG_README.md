# Archy Debug Tools - 100% REAL DATA

This folder contains comprehensive debug scripts that show **ACTUAL LIVE DATA** flowing through Archy. No mock data, no examples - everything you see is real!

## 🔍 Debug Scripts

### 🌟 NEW: `ultimate_real_data_inspector.py` - The Complete Package
**Purpose:** See EVERYTHING with ACTUAL data - the most comprehensive view

**What it shows (ALL REAL):**
- Live command execution with timing
- Complete JSON request/response
- Full structured data breakdown
- All findings from Rust parsing
- Actual formatted display output
- Real performance metrics
- True data sizes and formats

**Run:**
```bash
python3 debugging/ultimate_real_data_inspector.py
```

**Output:** Complete real-time data inspection - 100% authentic!


### 1. `debug_archy_flow.py` - High-Level Flow Tracer
**Purpose:** Understand the overall architecture with REAL data

**What it shows:**
- Python ↔ Rust connection with REAL responses
- Actual command execution flow
- Live smart parsing for different command types
- Terminal management with actual state
- Real data flow examples

**Run:**
```bash
python3 debugging/debug_archy_flow.py
```

**Output:** Interactive walkthrough with REAL executed commands


### 2. `debug_socket_tracer.py` - Socket-Level Communication
**Purpose:** See the raw Unix socket communication between Python and Rust

**What it shows:**
- Exact JSON messages sent to Rust
- Exact JSON responses from Rust
- Byte counts and timing
- Socket connection details
- Response structure breakdown

**Run:**
```bash
python3 debugging/debug_socket_tracer.py
```

**Output:** Detailed socket-level logs with timing information


### 3. `debug_ai_rust_integration.py` - Complete AI Integration
**Purpose:** Trace the entire flow from user input to final output

**What it shows:**
- User input preprocessing
- Gemini API request/response
- Command tag extraction
- Rust execution with timing
- Parsed structured data
- Formatted output display
- Complete flow summary

**Run:**
```bash
python3 debugging/debug_ai_rust_integration.py
```

**Output:** Full trace with AI responses and Rust processing


## 📊 Architecture Overview

```
┌─────────────┐
│    USER     │
└──────┬──────┘
       │ "get my ip"
       ▼
┌─────────────────────┐
│  PYTHON             │
│  (archy_chat.py)    │
│  • Gemini API       │
│  • Conversation     │
│  • Intent detection │
└──────┬──────────────┘
       │ JSON over Unix socket
       │ /tmp/archy.sock
       ▼
┌─────────────────────┐
│  RUST DAEMON        │
│  (archy-executor)   │
│  • Command exec     │
│  • Parser.rs        │
│  • Formatter.rs     │
│  • Output.rs        │
└──────┬──────────────┘
       │ DisplayOutput JSON
       ▼
┌─────────────────────┐
│  PYTHON             │
│  • Display to user  │
│  • AI analysis      │
└─────────────────────┘
```

## 🎯 What Each Component Does

### Python (archy_chat.py)
- ✅ **AI Logic** - Talks to Gemini API
- ✅ **Conversation** - Manages chat history
- ✅ **Command Detection** - Finds `[EXECUTE_COMMAND: ...]` tags
- ✅ **Streaming** - Yields responses to user

### Rust (archy-executor)
- ✅ **Execution** - Runs commands in tmux
- ✅ **Parsing** - Extracts structured data (IPs, ports, files, etc.)
- ✅ **Formatting** - Creates colored output with emojis
- ✅ **Smart Waiting** - Detects command completion automatically

### IPC Layer (rust_executor.py)
- ✅ **Socket Communication** - Bridges Python and Rust
- ✅ **JSON Protocol** - Serializes/deserializes messages
- ✅ **Error Handling** - Manages connection issues

## 🧪 Testing Workflow

1. **First, understand the architecture:**
   ```bash
   python3 debugging/debug_archy_flow.py
   ```

2. **Then, see the raw communication:**
   ```bash
   python3 debugging/debug_socket_tracer.py
   ```

3. **Finally, trace a complete AI interaction:**
   ```bash
   python3 debugging/debug_ai_rust_integration.py
   ```

## 💡 Common Issues and Solutions

### Issue: "Daemon not running"
**Solution:**
```bash
./start_daemon.sh
```

### Issue: "Socket not found"
**Check:**
```bash
ls -la /tmp/archy.sock
ps aux | grep archy-executor
```

### Issue: "No response from Rust"
**Debug:**
```bash
# Check daemon logs
ps aux | grep archy-executor

# Restart daemon
./stop_daemon.sh
./start_daemon.sh
```

## 📝 Adding Your Own Debug

To add custom debug output to Archy:

1. **In Python (archy_chat.py):**
   ```python
   print(f"[DEBUG] My message", file=sys.stderr)
   ```

2. **In Rust (main.rs):**
   ```rust
   eprintln!("[DEBUG] My message");
   ```

3. **Socket communication:**
   Use `debug_socket_tracer.py` as a template

## 🔬 Understanding the Output

### DisplayOutput Structure
```json
{
  "success": true,
  "command": "ip addr",
  "status": "success",
  "exit_code": 0,
  "structured": {
    "interfaces": [...],
    "ipv4_addresses": [...]
  },
  "findings": [
    {
      "category": "Network Interfaces",
      "message": "6 interface(s) detected",
      "importance": "Medium"
    }
  ],
  "summary": "6 interfaces, 5 IPs",
  "display": "➜ Command: ip addr\n\n📊 Key Findings...",
  "display_plain": "➜ Command: ip addr...",
  "metadata": {
    "line_count": 42,
    "byte_count": 2156,
    "format_detected": "ip_addr"
  }
}
```

### Key Fields
- **structured**: JSON data parsed by Rust (for AI analysis)
- **findings**: Key insights detected by Rust
- **summary**: One-line summary
- **display**: Formatted output with colors/emojis (for user)
- **display_plain**: Same but without colors (for logs)

## 🚀 Performance Metrics

Typical timings (from debug_socket_tracer.py):
- Socket connection: ~1ms
- Simple command (echo): ~2s (includes prompt waiting)
- Network scan (nmap): ~10-15s
- System info query: ~1ms

## 📚 Related Files

- `/src/parser.rs` - Command output parsing
- `/src/formatter.rs` - Output formatting
- `/src/output.rs` - DisplayOutput structure
- `/src/main.rs` - Socket handler
- `/scripts/archy_chat.py` - AI logic
- `/scripts/rust_executor.py` - IPC bridge

---

**Happy Debugging! 🐛🔍**

