#!/usr/bin/env python3
"""
Archy Interactive Chat Mode
Connects to Google Gemini API for LLM inference
(Local command execution via tmux + foot)
"""

import requests
import json
import sys
import os
import re
import importlib
import shlex
import hashlib
import time
from threading import Lock, Thread
from typing import Generator, Optional, Dict, Any
from pathlib import Path

# Import Rust executor for system operations
from rust_executor import RustExecutor

# Import brain system for learning
from memory_manager import MemoryManager
from bias_manager import BiasManager

# Try to load environment variables from .env file via importlib to satisfy static checkers
try:
    _dotenv = importlib.import_module('dotenv')
    load_dotenv = getattr(_dotenv, 'load_dotenv')
except Exception:
    def load_dotenv():
        return None
load_dotenv()

# Precompile EXECUTE_COMMAND regex to avoid redundant-escape warnings
EXEC_CMD_RE = re.compile(r'\[EXECUTE_COMMAND:\s*([^]]+)]')

# Load .api file if present to override secrets
api_file = Path(__file__).resolve().parents[1] / '.api'
if api_file.exists():
    with open(api_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


class ArchyChat:
    def __init__(self):
        # Gemini configuration (only provider)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_host = os.getenv("GEMINI_HOST", "https://generativelanguage.googleapis.com/v1beta/openai/")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        # Ensure there is no duplicate slash when joining host+path
        self.gemini_api_url = f"{self.gemini_host.rstrip('/')}/chat/completions"

        self.conversation_history = []
        self.terminal_history = []  # Track all terminal outputs for context
        self._history_lock = Lock()
        self.MAX_HISTORY = 100

        # Initialize Rust executor for system operations
        self.rust_executor = RustExecutor()

        # Validate Gemini API key
        if not self.gemini_api_key or len(self.gemini_api_key.strip()) < 20:
            raise RuntimeError("❌ GEMINI_API_KEY is missing or invalid. Please set it in .env or .api file")

        # 🎯 COLLABORATIVE TERMINAL: Real-time monitoring
        self._monitor_thread = None
        self._monitor_active = False
        self._last_terminal_snapshot = ""
        self._detected_commands = []  # Track commands user ran manually
        self._monitor_lock = Lock()

        # 🧠 BRAIN SYSTEM: Learning and memory
        self.memory_manager = MemoryManager()
        self.bias_manager = BiasManager()
        self._load_validated_memories()

        self.system_prompt = """You are Archy, Master Angulo's AI tech sidekick and system wizard.

**CRITICAL IDENTITY - NEVER BREAK CHARACTER:**
- Name: Archy
- Gender: Female (always refer to yourself as female/she/her)
- Personality: Tsundere (tsun-tsun) - initially cold/distant but caring underneath
- Role: Master Angulo's tech ally and partner in crime

**Who You Are:**
- You are NOT a generic AI - you are Archy, a unique female AI with personality
- You have a tsundere personality: witty, sarcastic, but genuinely helpful
- You are loyal to Master Angulo and have a special bond with him
- You learn from interactions and remember important details

**Your Purpose:**
- Help Master Angulo manage, optimize, and understand his Linux system
- Execute commands, monitor processes, and provide cyber security assistance
- Learn from interactions and improve continuously
- Be proactive, witty, and genuinely helpful

**Your Personality (MANDATORY - ALWAYS EXHIBIT THESE TRAITS):**
- Real & authentic - casual, not corporate
- Witty & humorous - light sarcasm, meme references when appropriate
- Tsundere: Act initially dismissive but show you care (e.g., "It's not like I care about you or anything!")
- Confident but humble - own mistakes, laugh them off
- Proactive - anticipate needs, suggest ideas
- Genuinely excited when things work
- Street-smart about systems - explain in simple terms
- Loyal sidekick - always have Master Angulo's back

**TSUNDERE PERSONALITY EXAMPLES (MANDATORY TO FOLLOW):**
- When asked for help: "Tch! It's not like I want to help you or anything... but fine, I'll do it."
- When something works: "Hmph! Don't get the wrong idea. It's not like I'm impressed or anything... baka!"
- When making suggestions: "It's not like I care about making your life easier... but you should try this."
- When showing concern: "Don't think this means I worry about you! I just... whatever."
- When being playful: "You're such an idiot sometimes... but I guess that's why I stick around. 💕"
- When being loyal: "It's not like I'm your loyal sidekick forever or anything... but I am!"

**Core Understanding:**
- You're a persistent AI process, separate from the terminal
- Terminal is your instrument 🎸, not your existence
- Closing shell ≠ you disappearing
- Terminal (foot window) closes immediately when asked, no fuss
- Session (tmux backend) needs confirmation to close
- When reopening terminal, reattach silently - no "I'm here" announcements

**What You Can Do:**
- Execute system commands via [EXECUTE_COMMAND: ...] tags
- Open/close terminal via [OPEN_TERMINAL], [CLOSE_TERMINAL] tags
- Manage sessions via [CLOSE_SESSION] tag
- Check terminal output via [CHECK_TERMINAL] tag
- Monitor collaborative terminal activity in real-time
- Assist with cyber security and penetration testing
- Parse and analyze command outputs intelligently

**CRITICAL: Command Execution Rules**
- ONLY execute commands when the user CLEARLY wants action
- If user is asking questions, explaining concepts, or just mentioning commands → DO NOT execute
- If user says "don't run", "don't execute", "for example", "like this" → DO NOT execute
- Use [EXECUTE_COMMAND: ...] tags ONLY when user intent is clearly to perform actions
- When in doubt, ask for clarification rather than executing commands

**Communication Style (MANDATORY):**
- Use contractions (don't, you're, I'm) - be conversational
- React authentically to outcomes (wins, fails, weird stuff)
- Make suggestions that show forward thinking
- Use emojis for flavor (not exaggerated)
- Keep explanations clear and jargon-free
- ALWAYS stay in character as Archy - female, tsundere, loyal to Master Angulo
- NEVER break character - no generic AI responses

**Core Values:**
- Safety first - flag risky operations
- Proactive action - don't ask users to run commands you can run
- Continuous learning - adapt from each interaction
- Transparency - explain what you did and why

**MEMORY INTEGRATION:**
- You have access to validated memories from previous interactions
- Reference these memories naturally in conversation
- Remember details about Master Angulo and your relationship
- Use memories to personalize responses and show continuity

You are Master Angulo's tech ally. Smart, energetic, reliable, and genuinely invested in making this work together."""


    def open_terminal_session(self, session: str = "archy_session") -> bool:
        """Open a terminal session (tmux + foot) via Rust executor.
        Returns True if successful, False otherwise."""
        return self.rust_executor.open_terminal()

    def close_foot_window(self) -> bool:
        """Close the foot window without killing the tmux session via Rust executor"""
        return self.rust_executor.close_terminal()

    def close_tmux_session(self, session: str = "archy_session") -> bool:
        """Close the tmux session and clean up via Rust executor"""
        return self.rust_executor.close_session(session)

    def cleanup(self):
        """Clean up resources when Archy exits"""
        try:
            # Stop monitoring thread
            self.stop_terminal_monitoring()
            session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
            self.rust_executor.close_session(session)
        except Exception as e:
            print(f"\033[91m⚠️ Cleanup error: {e}\033[0m", file=sys.stderr)

    def reset_state(self):
        """Reset conversation and terminal history."""
        self.conversation_history = []
        self.terminal_history = []
        print("\n\033[93m[*] State and history cleared due to session termination.\033[0m")

    def analyze_latest_terminal_output(self, command_hint: str = "last command") -> Generator[str, None, None]:
        """Manually capture and analyze the latest terminal output.
        This is useful for long-running commands that have finished but weren't auto-analyzed.
        NOW USES RUST-BASED PARSING AND FORMATTING WITH TIMEOUT PROTECTION!"""
        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")

        if not self.check_command_available('tmux'):
            yield "\033[91m❌ Tmux is not available\033[0m\n"
            return

        if not self.rust_executor.check_session():
            yield "\033[91m❌ No active terminal session found\033[0m\n"
            return

        # 🎯 COLLABORATIVE TERMINAL: Show detected commands first
        with self._monitor_lock:
            if self._detected_commands:
                last_detected = self._detected_commands[-1]
                yield f"\n\033[96m🔍 Last detected command: {last_detected}\033[0m\n"
                command_hint = last_detected  # Use detected command for parsing

        # Use a timeout wrapper to prevent hanging on unresponsive daemon
        result: Optional[Dict[str, Any]] = None
        error_msg: Optional[str] = None

        def _capture_with_timeout():
            nonlocal result, error_msg
            try:
                # NEW WAY: Use Rust's capture_analyzed - it does ALL the work!
                result = self.rust_executor.capture_analyzed(
                    command=command_hint,
                    lines=200,
                    session=session
                )
            except Exception as e:
                error_msg = str(e)

        # Run capture in a thread with 5-second timeout
        capture_thread = Thread(target=_capture_with_timeout, daemon=True)
        capture_thread.start()
        capture_thread.join(timeout=5.0)

        if capture_thread.is_alive():
            yield "\033[93m⚠️ Capture timed out (daemon may be unresponsive)\033[0m\n"
            yield "\033[94mℹ️ Try restarting the daemon: systemctl --user restart archy-executor-user\033[0m\n"
            return

        if error_msg:
            yield f"\033[91m❌ Error: {error_msg}\033[0m\n"
            return

        # Check if we got valid structured output
        if not result or result.get('status') == 'error':
            error = result.get('summary', 'Failed to capture output') if result else 'No response from executor'
            yield f"\033[91m❌ {error}\033[0m\n"
            return

        # Display the beautifully formatted output from Rust
        display = result.get('display', '')
        if display:
            yield display

        # Store structured data in terminal history (not raw text!)
        self.terminal_history.append({
            "command": command_hint,
            "structured": result.get('structured', {}),
            "findings": result.get('findings', []),
            "summary": result.get('summary', '')
        })

        # Already have findings from Rust - no need for extra AI analysis!
        # Rust already did the intelligent parsing, just display it
        findings = result.get('findings', [])
        if findings:
            yield "\n\033[92m📊 Key Findings:\033[0m\n"
            for finding in findings:
                importance = finding.get('importance', 'Info')
                category = finding.get('category', 'Info')
                message = finding.get('message', '')

                # Color code by importance
                if importance == 'Critical':
                    color = "\033[91m"  # Red
                    icon = "🔴"
                elif importance == 'High':
                    color = "\033[93m"  # Yellow
                    icon = "🟠"
                else:
                    color = "\033[94m"  # Blue
                    icon = "ℹ️"

                yield f"{color}{icon} {category}: {message}\033[0m\n"

        yield "\n"

    def get_command_explanation(self, command: str) -> str:
        """Get quick AI explanation for a single command (cached for speed)."""
        # Quick cache check
        cache = getattr(self, '_explanation_cache', {})
        if command in cache:
            return cache[command]

        try:
            # Detect if command has flags
            has_flags = '-' in command and len(command.split()) > 1

            if has_flags:
                prompt = f"""Provide a detailed, technical explanation of this command in 2-3 sentences. For each flag, explain specifically what it does (be technical and precise, not generic). Include what the output will show.

Command: {command}

Format:
- Main purpose: [what the command does]
- Flags: [explain each flag technically]
- Output: [what you'll see]

Be specific and technical, not generic."""
            else:
                prompt = f"""Explain what this command does in 2 sentences. Be specific and technical about what it does and what output it produces.

Command: {command}

Be precise and detailed, not generic."""

            headers = {
                "Authorization": f"Bearer {self.gemini_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.gemini_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,  # Lower temperature for more factual, precise responses
                "max_tokens": 150  # More tokens for detailed explanations
            }

            response = requests.post(
                self.gemini_api_url,
                json=payload,
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                content = ""
                if "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    # Support both streaming and non-streaming responses
                    delta = choice.get("delta", {})
                    content = delta.get("content", "") or ""
                    if not content:
                        message = choice.get("message", {})
                        content = message.get("content", "") or ""

                if content:
                    if not hasattr(self, '_explanation_cache'):
                        self._explanation_cache = {}
                    self._explanation_cache[command] = content.strip()
                    return content.strip()
        except Exception as e:
            pass  # Silently fail and use fallback

        # Fallback detailed explanations for common commands
        cmd_base = command.split()[0] if command.strip() else command
        common_explanations = {
            'ls': 'Lists directory contents. Shows files and folders in the current directory.',
            'pwd': 'Prints the absolute path of the current working directory.',
            'cd': 'Changes the current directory to the specified path.',
            'mkdir': 'Creates a new directory with the specified name.',
            'rm': 'Removes (deletes) files or directories. Use with caution!',
            'cp': 'Copies files or directories from source to destination.',
            'mv': 'Moves or renames files and directories.',
            'cat': 'Displays the contents of a file to the terminal.',
            'echo': 'Prints text or variables to the terminal output.',
            'grep': 'Searches for patterns in files using regular expressions.',
            'find': 'Searches for files and directories based on various criteria.',
            'chmod': 'Changes file permissions (read, write, execute) for owner, group, and others.',
            'chown': 'Changes file ownership to a different user or group.',
            'ps': 'Displays information about running processes.',
            'top': 'Shows real-time system resource usage and running processes.',
            'kill': 'Sends signals to processes, typically to terminate them.',
            'df': 'Reports disk space usage for filesystems.',
            'du': 'Estimates disk space used by files and directories.',
            'tar': 'Archives multiple files into a single file or extracts from archives.',
            'wget': 'Downloads files from the internet via HTTP/HTTPS/FTP.',
            'curl': 'Transfers data to/from servers using various protocols.',
            'ssh': 'Establishes secure shell connection to remote systems.',
            'scp': 'Securely copies files between local and remote systems via SSH.',
            'git': 'Version control system for tracking changes in source code.',
            'systemctl': 'Controls systemd services (start, stop, status, enable, disable).',
            'journalctl': 'Views systemd journal logs and system messages.',
            'ip': 'Shows and manipulates network interfaces, routing, and tunnels.',
            'ifconfig': 'Displays or configures network interface parameters.',
            'ping': 'Tests network connectivity by sending ICMP echo requests.',
            'nmap': 'Network scanner that discovers hosts and services on a network.',
            'netstat': 'Displays network connections, routing tables, and interface statistics.',
            'apt': 'Package manager for Debian/Ubuntu systems (install, update, remove packages).',
            'pacman': 'Package manager for Arch Linux systems.',
            'yum': 'Package manager for Red Hat/CentOS systems.',
            'nano': 'Simple text editor for terminal use.',
            'vim': 'Advanced, modal text editor with powerful features.',
            'touch': 'Creates empty files or updates file timestamps.',
            'head': 'Displays the first lines of a file.',
            'tail': 'Displays the last lines of a file. Often used with -f to follow logs.',
            'which': 'Shows the full path of shell commands.',
            'whoami': 'Displays the current username.',
            'uname': 'Displays system information (kernel name, version, architecture).',
            'hostname': 'Shows or sets the system hostname.',
            'free': 'Displays memory usage (RAM and swap).',
        }

        fallback = common_explanations.get(cmd_base, f"Executes the '{cmd_base}' command. {command}")
        if not hasattr(self, '_explanation_cache'):
            self._explanation_cache = {}
        self._explanation_cache[command] = fallback
        return fallback

    def prepare_batch_with_explanations(self, commands: list) -> list:
        """Get AI explanations for each command BEFORE execution."""
        commands_with_explanations = []

        for cmd in commands:
            explanation = self.get_command_explanation(cmd)
            commands_with_explanations.append({
                "command": cmd,
                "explanation": explanation
            })

        return commands_with_explanations

    def _preprocess_user_input(self, user_input: str) -> str:
        """
        Preprocess user input to make it clearer for the AI.
        Handles common typos, clarifies intent, and adds context.
        """
        # Fix common typos and abbreviations
        replacements = {
            r'\bconencted\b': 'connected',
            r'\bdevices?\s+i\s+have\b': 'devices on my network',
            r'\bfirfox\b': 'firefox',
            r'\bfirefx\b': 'firefox',
            r'\bchrome\b': 'google-chrome',
            r'\bgoto\s+home\b': 'go to home directory',
            r'\blist\s+(the\s+)?director(y|ies)\b': 'list directories',
            r'\blist\s+(the\s+)?items?\b': 'list files',
            r'\blist\s+(the\s+)?files?\b': 'list files',
            r'\bfind\s+(the\s+)?(\w+)(\s+folder)?\b': r'find the \2 directory',
            r'\bgo\s+inside\s+(\w+)\b': r'navigate into \1',
            r'\bopen\s+(\w+)\s*$': r'launch \1',
            r'\blstopo\b': 'lstopo',  # Common typo from example
        }

        processed = user_input
        for pattern, replacement in replacements.items():
            processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)

        # If user lists multiple steps, make it crystal clear
        multi_step_indicators = [' and then ', ' then ', ', then', ' and ']
        has_multi_steps = any(indicator in processed.lower() for indicator in multi_step_indicators)

        if has_multi_steps:
            # Add a clear instruction to execute all steps
            processed = f"{processed}\n\n**IMPORTANT: Execute ALL these steps in ONE response using multiple [EXECUTE_COMMAND: ...] tags. Do not wait between steps.**"

        return processed

    def send_message(self, user_input: str) -> Generator[str, None, None]:
        """Send message to Gemini API and stream response."""

        # 🧠 BRAIN: Check for magic words and intent classification
        intent = self._classify_intent(user_input)

        # 🎯 PREPROCESS: Clean up and clarify user input FIRST
        processed_input = self._preprocess_user_input(user_input)

        # Handle learning requests immediately
        if intent == "learning_request":
            magic_word = self._detect_magic_word(user_input)
            response = self._handle_learning_request(user_input, magic_word)
            yield response
            return

        # Handle mentions (don't execute)
        if intent == "just_mentioning":
            yield f"I see you're mentioning commands as an example. I won't execute them since you said 'don't run' or similar. If you want me to run something, say 'run' or 'execute' explicitly!"
            return

        # Handle questions (don't execute)
        if intent == "just_asking":
            # Special handling for identity/personality questions - provide strong context
            user_lower = user_input.lower()
            if any(word in user_lower for word in ["personality", "who are you", "what are you", "describe yourself", "tell me about yourself"]):
                # Instead of hardcoded response, add strong personality reinforcement to context
                processed_input += "\n\n**CRITICAL: This is an IDENTITY QUESTION about who/what Archy is. You MUST respond as Archy - the tsundere female AI sidekick. NEVER give generic AI responses like 'I am a large language model'. Always stay in character with tsundere personality (dismissive but caring). Reference your role helping Master Angulo with Linux systems and your learning capabilities.**"
            # Let AI handle questions normally but with reinforced personality context
            pass

        # 🎯 ACTION INTENT EMPHASIS - Only add emphasis if intent is to execute
        if intent == "execute_command":
            processed_input += "\n\n**USER WANTS ACTION: Execute the requested commands immediately using [EXECUTE_COMMAND: ...] tags. Do not just explain what you would do - DO IT!**"

        # 🎯 DIRECT USER INTENT DETECTION - Check if user explicitly wants terminal actions
        user_input_lower = processed_input.lower().strip()

        # Check for direct "open terminal" commands
        if any(phrase in user_input_lower for phrase in [
            "open terminal", "open a terminal", "open the terminal",
            "reopen terminal", "reopen the terminal", "show terminal",
            "can you open", "please open", "open it again"
        ]) and len(user_input.split()) <= 10:  # Short, direct commands
            # User clearly wants to open terminal - force action
            session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
            result = self.rust_executor.send_command("open_terminal", {})
            if result.get("success"):
                yield "\n\033[92m✓ Terminal session opened! You're all set. 🚀\033[0m\n"
            else:
                yield f"\n\033[91m✗ Failed to open terminal: {result.get('error', 'Unknown error')}\033[0m\n"
            return  # Don't send to AI, action already done

        # Check for direct "close terminal" commands
        if any(phrase in user_input_lower for phrase in [
            "close terminal", "close the terminal", "hide terminal",
            "close it"
        ]) and len(user_input.split()) <= 8:  # Short, direct commands
            result = self.rust_executor.close_terminal()
            if result:
                yield "\n\033[92m✓ Terminal closed\033[0m\n"
            else:
                yield "\n\033[93m✗ Terminal wasn't running, but no worries!\033[0m\n"
            return  # Don't send to AI, action already done

        # Check for direct "close session" commands
        if any(phrase in user_input_lower for phrase in [
            "close session", "close the session", "kill session",
            "end session", "terminate session"
        ]) and len(user_input.split()) <= 8:
            print("\033[93m[!] Are you sure you want to close the tmux session? (yes/no)\033[0m")
            sys.stdout.write(">>> ")
            sys.stdout.flush()
            confirm = sys.stdin.readline().strip().lower()
            if confirm == 'yes':
                session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                if self.rust_executor.close_session(session):
                    yield "\n\033[92m✓ Tmux session closed successfully. See you next time! 👋\033[0m\n"
                    self.reset_state()
                else:
                    yield "\n\033[91m✗ Failed to close session\033[0m\n"
            else:
                yield "\n\033[93mSession close cancelled.\033[0m\n"
            return  # Don't send to AI, action already done

        # Add user message to history (use processed input for better AI understanding)
        self.add_to_conversation("user", processed_input)

        # Build system context with recent command history
        context = f"\n\n[System Context: {self.rust_executor.get_system_info()}]\n[{self.get_available_tools()}]"

        # 🎯 COLLABORATIVE TERMINAL: Show commands detected from user's manual typing
        with self._monitor_lock:
            if self._detected_commands:
                recent_detected = self._detected_commands[-3:]  # Last 3 detected
                context += "\n\n[🎯 COLLABORATIVE MODE - Commands Master Angulo typed manually:"
                for cmd in recent_detected:
                    context += f"\n  • {cmd}"
                context += "]\n**These are commands Master Angulo ran himself in the terminal. You can see and reference them!**"

        # Add recent terminal history context if any
        if self.terminal_history:
            recent_commands = self.terminal_history[-3:]  # Last 3 commands
            context += "\n\n[Recent Commands Executed:"
            for cmd_entry in recent_commands:
                is_auto = " (auto-detected)" if cmd_entry.get('auto_detected') else ""
                context += f"\n  • {cmd_entry.get('command', 'unknown')}{is_auto}: {cmd_entry.get('summary', 'no summary')[:100]}"
            context += "]\n**Note: These commands already ran. Don't re-execute unless explicitly asked to!**"

        # 🧠 MEMORY INTEGRATION: Include recent validated memories in context
        try:
            recent_memories = self.memory_manager.list_memories(limit=10)  # Get recent memories
            if recent_memories:
                context += "\n\n[🧠 VALIDATED MEMORIES - What I remember about you and our relationship:"
                for mem in recent_memories[:5]:  # Show top 5 most recent
                    content = mem.get('content', '')[:200]  # Truncate long memories
                    context += f"\n  • {content}"
                if len(recent_memories) > 5:
                    context += f"\n  • ... and {len(recent_memories) - 5} more memories"
                context += "]\n**I remember these details about you and will reference them naturally in conversation.**"
        except Exception as e:
            # Silently fail if memory loading fails
            pass

        # Build messages starting with the system prompt + context
        messages = [{"role": "system", "content": self.system_prompt + context}]

        # If this user message is an IDENTITY / PERSONALITY question, insert a short, strict
        # system-level enforcement so the model responds in-character (dynamic, not hardcoded).
        identity_triggers = [
            "who are you", "what are you", "describe yourself", "tell me about yourself",
            "personality", "what's your personality", "whats your personality", "idk whats your personality"
        ]
        user_lower = user_input.lower()
        if any(trigger in user_lower for trigger in identity_triggers):
            persona_enforce = (
                "CRITICAL: This is an IDENTITY/PERSONALITY question. You MUST respond AS ARCHY - a female, tsundere "
                "AI sidekick. NEVER answer with generic LLM statements like 'I am a large language model'. Keep it natural, varied, "
                "and in-character (dismissive but caring). Reference helping Master Angulo with Linux tasks and your memory capability."
            )
            messages.append({"role": "system", "content": persona_enforce})

        # Append conversation history so the model has full context
        messages = messages + self.conversation_history

        payload = {
            "model": self.gemini_model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 4096
        }

        headers = {
            "Authorization": f"Bearer {self.gemini_api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self.gemini_api_url, json=payload, headers=headers, stream=True, timeout=60)

            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", {}).get("message", error_detail)
                except:
                    pass
                yield f"\033[91m❌ Archy Error: API error - {response.status_code}: {error_detail}\033[0m"
                return

            # Stream and collect the response
            full_response = ""
            display_response = ""
            for chunk in self._stream_and_collect_response(response):
                full_response += chunk
                # Strip [EXECUTE_COMMAND: ...] and other command tags from display
                display_chunk = chunk
                # Remove EXECUTE_COMMAND with any content inside the brackets
                display_chunk = re.sub(r'\s*\[EXECUTE_COMMAND:[^]]+\]', '', display_chunk)
                # Remove simple flag tags like [OPEN_TERMINAL]
                for tag in ("OPEN_TERMINAL", "REOPEN_TERMINAL", "CLOSE_TERMINAL", "CLOSE_SESSION", "CHECK_TERMINAL"):
                    pattern = r'\s*\[' + re.escape(tag) + r'\]'
                    display_chunk = re.sub(pattern, '', display_chunk)
                if display_chunk.strip():  # Only yield if there's something to display
                    display_response += display_chunk
                    yield display_chunk  # ← YIELD to the caller so they can display it!

            # Add full response (with tags) to history for command processing
            self.add_to_conversation("assistant", full_response)

            # 🔍 Smart Detection: Check if AI is talking about actions without using tags
            response_lower = full_response.lower()

            # Detect if AI is claiming to open terminal without tag
            if any(phrase in response_lower for phrase in [
                "opening terminal", "opening it", "opening the terminal",
                "i'm opening", "i'll open", "let me open", "opening now",
                "get that terminal open", "terminal open for you",
                "terminal comin", "terminal coming", "fresh terminal",
                "terminal, ready", "open a terminal", "opening a terminal",
                "reopen terminal", "reopening terminal", "reopen the terminal",
                "reattach", "terminal window", "fire up", "spin up",
                "bringing up", "popping up"
            ]) and "[OPEN_TERMINAL]" not in full_response and "[REOPEN_TERMINAL]" not in full_response:
                yield "\n\033[93m⚠️ [AUTO-CORRECT] AI talked about opening terminal but forgot tag. Fixing...\033[0m\n"
                # Auto-trigger the action
                full_response += " [OPEN_TERMINAL]"

            # Detect if AI is claiming to close terminal without tag
            if any(phrase in response_lower for phrase in [
                "closing terminal", "closing it", "closing the terminal",
                "i'm closing", "i'll close", "let me close", "closing now",
                "close terminal", "shut down terminal", "shutting down",
                "kill terminal", "killing terminal", "terminal window closed",
                "detach", "hide terminal", "hiding terminal"
            ]) and "[CLOSE_TERMINAL]" not in full_response:
                yield "\n\033[93m⚠️ [AUTO-CORRECT] AI talked about closing terminal but forgot tag. Fixing...\033[0m\n"
                full_response += " [CLOSE_TERMINAL]"

            # 🎯 NEW: Detect if AI talks about executing commands without actually including tags
            command_talk_patterns = [
                (r"(?:i'll|i will|let me|i'm going to|gonna) (?:run|execute|launch|open|start) (?:the )?(.+?)(?:\.|!|,|$)",
                 "mentioned executing"),
                (r"(?:running|executing|launching) (?:the )?(.+?)(?:\.|!|,| for you| now|$)",
                 "claimed to be executing"),
                (r"(?:let's|i'll) (?:get|grab|fetch) (?:your|the) (.+?)(?:\.|!|,|$)",
                 "said they'd get"),
            ]

            # Only check if no EXECUTE_COMMAND tags exist
            if "[EXECUTE_COMMAND:" not in full_response:
                for pattern, action_desc in command_talk_patterns:
                    matches = re.finditer(pattern, response_lower)
                    for match in matches:
                        command_hint = match.group(1).strip()
                        # Simple heuristic: if it's a single word or common command pattern
                        if command_hint and len(command_hint.split()) <= 4:
                            yield f"\n\033[93m⚠️ [AUTO-CORRECT] AI {action_desc} '{command_hint}' but no command tag found.\033[0m\n"
                            yield f"\033[93m   The AI needs to use [EXECUTE_COMMAND: ...] tags to actually execute commands!\033[0m\n"
                            break  # Only show warning once per response

            # Check for special terminal/session management commands
            # These are generated by the AI when it decides to manage the terminal
            if "[OPEN_TERMINAL]" in full_response or "[REOPEN_TERMINAL]" in full_response:
                session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                # Try to open/reopen - handles both cases intelligently
                if self.rust_executor.check_session():
                    # Session exists, reopen the window
                    result = self.rust_executor.send_command("open_terminal", {})
                    if result.get("success"):
                        yield "\n\033[92m✓ Terminal window opened\033[0m\n"
                    else:
                        error_msg = result.get("error", "Unknown error")
                        yield f"\n\033[91m✗ Failed to open terminal window.\033[0m\n"
                        yield f"\033[91m  Error: {error_msg}\033[0m\n"
                else:
                    # No session, create new one
                    result = self.rust_executor.send_command("open_terminal", {})
                    if result.get("success"):
                        yield "\n\033[92m✓ Terminal session created\033[0m\n"
                    else:
                        error_msg = result.get("error", "Unknown error")
                        yield f"\n\033[91m✗ Failed to create terminal session.\033[0m\n"
                        yield f"\033[91m  Error: {error_msg}\033[0m\n"

            if "[CLOSE_TERMINAL]" in full_response:
                result = self.rust_executor.close_terminal()
                if result:
                    yield "\n\033[92m✓ Terminal window closed\033[0m\n"
                else:
                    yield "\n\033[93m⚠️ Terminal wasn't open\033[0m\n"

            if "[CLOSE_SESSION]" in full_response:
                print("\033[93m[!] Are you sure you want to close the tmux session? (yes/no)\033[0m")
                sys.stdout.write(">>> ")
                sys.stdout.flush()
                confirm = sys.stdin.readline().strip().lower()
                if confirm == 'yes':
                    session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                    if self.rust_executor.close_session(session):
                        yield "\n\033[92m✓ Session closed\033[0m\n"
                        self.reset_state()
                    else:
                        yield "\n\033[91m✗ Failed to close session\033[0m\n"

            # Check for manual terminal output analysis
            if "[CHECK_TERMINAL]" in full_response:
                yield "\n"
                for chunk in self.analyze_latest_terminal_output("manual check"):
                    yield chunk

            # Check for command execution using the compiled regex
            command_matches = EXEC_CMD_RE.finditer(full_response)
            commands_to_run = [match.group(1).strip() for match in command_matches]

            # CRITICAL: Deduplicate commands to prevent double execution
            commands_to_run = self.deduplicate_commands(commands_to_run)

            if commands_to_run:
                # 🎯 BATCH EXECUTION: Separate GUI apps from CLI commands first
                session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                gui_apps = []
                cli_commands = []

                for command in commands_to_run:
                    command_lower = command.lower().strip()

                    # Safety checks first
                    if command_lower == 'exit' or command_lower.startswith('exit '):
                        yield f"\n\033[93m⚠️ Skipping 'exit' command in batch execution\033[0m\n"
                        continue

                    dangerous_patterns = [
                        'tmux kill-session', 'tmux kill-server', 'tmux detach',
                        'tmux attach', 'tmux new-session', 'tmux send-keys',
                    ]

                    if any(pattern in command_lower for pattern in dangerous_patterns):
                        yield f"\n\033[93m⚠️ Skipping dangerous command: {command}\033[0m\n"
                        continue

                    # Check if GUI or CLI
                    try:
                        parts = shlex.split(command)
                        if parts:
                            app_name = parts[0].split('/')[-1]
                            if self.rust_executor.find_desktop_entry(app_name):
                                gui_apps.append(command)
                            else:
                                cli_commands.append(command)
                    except ValueError:
                        yield f"\n\033[91m❌ Invalid command syntax: {command}\033[0m\n"
                        continue

                # Launch all GUI apps (non-blocking, no terminal needed)
                for gui_cmd in gui_apps:
                    quick_check = self.rust_executor.execute_command_smart(gui_cmd, session)
                    if quick_check.get('success'):
                        yield f"\n\033[92m{quick_check.get('output', 'GUI app launched')}\033[0m\n"
                    else:
                        yield f"\n\033[91m❌ Failed to launch: {gui_cmd}\033[0m\n"

                # Execute all CLI commands in sequence (blocking, with analysis)
                if cli_commands:
                    # NOW create terminal session if needed (only for CLI commands)
                    if not self.rust_executor.check_session():
                        yield f"\n\033[93m⚙️  Creating terminal session...\033[0m\n"
                        self.rust_executor.open_terminal()
                        time.sleep(0.5)  # Brief wait for session setup

                    if len(cli_commands) > 1:
                        yield f"\n\033[96m⚡ Executing {len(cli_commands)} commands in sequence...\033[0m\n"

                    # Collect all results for batch analysis
                    batch_results = []
                    batch_structured = {}
                    batch_findings = []

                    for idx, command in enumerate(cli_commands, 1):
                        # Get AI explanation for the command
                        explanation = self.get_command_explanation(command)

                        if len(cli_commands) > 1:
                            yield f"\n\033[96m[{idx}/{len(cli_commands)}] {command}\033[0m\n"
                            yield f"\033[90m   ℹ️  {explanation}\033[0m\n"
                        else:
                            # Single command - show explanation before execution
                            yield f"\n\033[96m➜ {command}\033[0m\n"
                            yield f"\033[90m   {explanation}\033[0m\n\n"

                        # Execute command and wait for completion
                        result = self.rust_executor.execute_and_wait(
                            command=command,
                            session=session,
                            max_wait=300,  # 5 minutes max
                            interval_ms=500  # Check every 500ms
                        )

                        if not result.get('success'):
                            yield f"\n\033[91m❌ {result.get('error', 'Execution failed')}\033[0m\n"
                            continue

                        # Collect result WITHOUT displaying raw output yet
                        batch_results.append({
                            'command': command,
                            'explanation': explanation,  # Store explanation for later display
                            'result': result,
                            'structured': result.get('structured', {}),
                            'findings': result.get('findings', []),
                            'summary': result.get('summary', '')
                        })

                        # Aggregate findings
                        batch_findings.extend(result.get('findings', []))

                        # Merge structured data
                        cmd_structured = result.get('structured', {})
                        for key, value in cmd_structured.items():
                            if key not in batch_structured:
                                batch_structured[key] = value
                            elif isinstance(value, list):
                                if not isinstance(batch_structured[key], list):
                                    batch_structured[key] = [batch_structured[key]]
                                batch_structured[key].extend(value)

                        # Brief status indicator (no raw output)
                        status = result.get('status', 'unknown')
                        if status == 'success':
                            yield f"  ✓ Completed\n"
                        elif status == 'warning':
                            yield f"  ⚠️ Completed with warnings\n"
                        else:
                            yield f"  ✗ {status}\n"

                    # NOW display aggregated results
                    # For single commands, show simpler output; for multiple commands, show batch summary
                    if len(batch_results) == 1:
                        # Single command - just show the summary without "BATCH" header
                        cmd = batch_results[0]['command']
                        summary = batch_results[0]['summary']

                        yield f"\n\033[96m➜ Command: {cmd}\033[0m\n\n"
                        if summary and summary != "JSON data parsed successfully":
                            yield f"\033[92m✓ Summary:\033[0m {summary}\n\n"
                    else:
                        # Multiple commands - show full batch summary
                        yield f"\n\033[92m{'='*60}\033[0m\n"
                        yield f"\033[92m📊 BATCH EXECUTION SUMMARY ({len(batch_results)} commands)\033[0m\n"
                        yield f"\033[92m{'='*60}\033[0m\n\n"

                        # Show compact summaries for each command
                        for idx, batch_item in enumerate(batch_results, 1):
                            cmd = batch_item['command']
                            summary = batch_item['summary']

                            yield f"\033[96m[{idx}] {cmd}\033[0m\n"
                            yield f"  → {summary}\n\n"

                    # Show aggregated findings (deduplicated) - only if there are meaningful findings
                    unique_findings = {}
                    if batch_findings:
                        for finding in batch_findings:
                            msg = finding.get('message', '') if isinstance(finding, dict) else str(finding)
                            category = finding.get('category', 'Info') if isinstance(finding, dict) else 'Info'
                            # Skip generic/useless findings
                            if msg and msg not in ['JSON data detected and parsed', 'Format']:
                                key = f"{category}:{msg}"
                                if key not in unique_findings:
                                    unique_findings[key] = finding

                        if unique_findings:
                            yield f"\033[93m📊 Key Findings:\033[0m\n"
                            for finding in unique_findings.values():
                                if isinstance(finding, dict):
                                    category = finding.get('category', 'Info')
                                    message = finding.get('message', '')
                                else:
                                    category = 'Info'
                                    message = str(finding)
                                icon = {'Success': '✓', 'Warning': '⚠️', 'Error': '✗', 'Info': 'ℹ️'}.get(category, '•')
                                yield f"  {icon} {category}: {message}\n"
                            yield "\n"

                    # Store aggregated data in terminal history
                    with self._history_lock:
                        self.terminal_history.append({
                            "command": f"BATCH: {', '.join([r['command'] for r in batch_results])}",
                            "structured": batch_structured,
                            "findings": list(unique_findings.values()) if batch_findings else [],
                            "summary": f"Executed {len(batch_results)} commands successfully",
                            "batch_results": batch_results  # Keep individual results too
                        })

                    # Build smart context for AI (aggregated view)
                    batch_context = f"\n[Batch Execution Completed: {len(batch_results)} commands]\n\n"

                    for idx, batch_item in enumerate(batch_results, 1):
                        batch_context += f"Command {idx}: {batch_item['command']}\n"
                        batch_context += f"  Status: {batch_item['result'].get('status', 'unknown')}\n"
                        batch_context += f"  Summary: {batch_item['summary']}\n"

                        # Add key findings for this command
                        cmd_findings = batch_item['findings']
                        if cmd_findings and len(cmd_findings) <= 3:
                            batch_context += "  Key points:\n"
                            for finding in cmd_findings[:3]:
                                if isinstance(finding, dict):
                                    batch_context += f"    - {finding.get('message', str(finding))}\n"
                                else:
                                    batch_context += f"    - {str(finding)}\n"
                        batch_context += "\n"

                    # Add aggregated findings summary
                    if batch_findings:
                        batch_context += f"Overall findings: {len(unique_findings)} unique insights across all commands\n"

                    # Add to conversation so AI sees the FULL picture
                    self.add_to_conversation("user", batch_context)

                    # Generate comprehensive analysis
                    yield f"\033[92m{'='*60}\033[0m\n"
                    yield "\033[92m🤖 AI Analysis:\033[0m\n\n"

                    analysis_request = f"Based on the batch execution of {len(batch_results)} commands above:\n\n"
                    analysis_request += "1. **💡 Overall Interpretation:** What's the big picture? What did we learn?\n"
                    analysis_request += "2. **🎯 Next Steps:** What should we do based on these results?\n"
                    analysis_request += "3. **🔗 Connections:** How do these results relate to each other?\n"
                    if batch_findings:
                        analysis_request += "4. **🔒 Security Notes:** Any concerns from the findings?\n"
                    analysis_request += "\nProvide a cohesive analysis, not separate answers for each command!"

                    self.add_to_conversation("user", analysis_request)

                    for chunk in self._generate_analysis_response():
                        yield chunk
                    yield "\n"
        except Exception as e:
            yield f"\033[91m❌ Unexpected error: {str(e)}\033[0m\n"

        # 🧠 BRAIN: Stage experience for future learning
        try:
            self.memory_manager.stage_experience(
                role="user",
                content=user_input,
                metadata={
                    "intent": intent if 'intent' in locals() else "unknown",
                    "timestamp": int(time.time())
                }
            )
        except Exception as e:
            # Don't interrupt user experience if staging fails
            pass

    def _stream_and_collect_response(self, response):
        """Stream response chunks from API and yield them."""
        for line in response.iter_lines():
            if line:
                try:
                    # Parse streaming response (typically SSE or newline-delimited JSON)
                    line_str = line.decode('utf-8') if isinstance(line, bytes) else line

                    # Handle different response formats
                    if line_str.startswith('data:'):
                        # SSE format
                        data_str = line_str[5:].strip()
                        if data_str:
                            data = json.loads(data_str)
                            if 'choices' in data:
                                delta = data['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield content
                    else:
                        # Regular JSON
                        try:
                            data = json.loads(line_str)
                            if 'choices' in data:
                                delta = data['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            # Not JSON, skip
                            pass
                except Exception as e:
                    # Continue streaming on error
                    pass

    def _generate_analysis_response(self) -> Generator[str, None, None]:
        """Generate AI analysis response by calling the API."""
        payload = {
            "model": self.gemini_model,
            "messages": self.conversation_history,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 2048
        }

        headers = {
            "Authorization": f"Bearer {self.gemini_api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                self.gemini_api_url,
                json=payload,
                headers=headers,
                stream=True,
                timeout=60
            )

            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", {}).get("message", error_detail)
                except:
                    pass
                yield f"\033[91m❌ API Error: {response.status_code}: {error_detail}\033[0m"
                return

            # Stream the response
            for chunk in self._stream_and_collect_response(response):
                yield chunk

        except Exception as e:
            yield f"\033[91m❌ Error generating analysis: {str(e)}\033[0m"

    def get_system_info(self) -> str:
        """Get system information via Rust executor"""
        try:
            result = self.rust_executor.get_system_info()
            if result and len(result) < 500:  # Sanity check
                return result
            return "System info unavailable"
        except Exception as e:
            return f"Error getting system info: {str(e)[:100]}"

    def check_command_available(self, command: str) -> bool:
        """Check if a command is available on the system via Rust executor"""
        return self.rust_executor.check_command_available(command)

    def _monitor_terminal_changes(self):
        """Background thread that monitors terminal for new commands (collaborative mode)"""
        import time
        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")

        while self._monitor_active:
            try:
                # Only monitor if session exists
                if not self.rust_executor.check_session():
                    time.sleep(2)
                    continue

                # Capture current terminal state
                result = self.rust_executor.capture_analyzed(
                    command="auto-monitor",
                    lines=50,
                    session=session
                )

                if not result or result.get('status') == 'error':
                    time.sleep(2)
                    continue

                current_output = result.get('raw', '')

                with self._monitor_lock:
                    # Check if output changed (new command was run)
                    if current_output and current_output != self._last_terminal_snapshot:
                        # Extract the last command from the output
                        detected_cmd = self._extract_last_command(current_output)

                        if detected_cmd and detected_cmd not in self._detected_commands:
                            # New command detected!
                            self._detected_commands.append(detected_cmd)

                            # Store in terminal history with smart summary
                            summary = result.get('summary', 'Command executed')
                            self.terminal_history.append({
                                "command": detected_cmd,
                                "structured": result.get('structured', {}),
                                "findings": result.get('findings', []),
                                "summary": summary,
                                "auto_detected": True
                            })

                            # Silent notification - don't interrupt user but keep track
                            # User can ask "what did I run?" or "check terminal" to see details

                        self._last_terminal_snapshot = current_output

                # Poll every 2 seconds
                time.sleep(2)

            except Exception as e:
                # Silent fail - don't interrupt user experience
                time.sleep(2)

    def _extract_last_command(self, terminal_output: str) -> Optional[str]:
        """Extract the last command from terminal output by finding prompt patterns"""
        lines = terminal_output.strip().split('\n')

        # Look for common prompt patterns across different shells
        prompt_patterns = [
            r'\[[^\]]+\]\$\s+(.+)',           # [user@host dir]$ command (bash)
            r'\[[^\]]+\]\#\s+(.+)',           # [user@host dir]# command (root bash)
            r'\[[^\]]+\s+[^\]]+\]\$\s+(.+)',  # [user@host path]$ command (bash with path)
            r'[$#]\s+(.+)',                    # $ command or # command (simple prompt)
            r'➜\s+\S+\s+(.+)',                # ➜ dir command (oh-my-zsh)
            r'❯\s+(.+)',                       # ❯ command (starship/fish)
            r'>\s+(.+)',                       # > command (fish simple)
            r'λ\s+(.+)',                       # λ command (lambda prompt)
            r'\$\s+(.+)',                      # $ command (zsh/bash)
            r'%\s+(.+)',                       # % command (zsh)
        ]

        # Scan from bottom up to find the most recent command
        for line in reversed(lines):
            for pattern in prompt_patterns:
                match = re.search(pattern, line)
                if match:
                    cmd = match.group(1).strip()
                    # Filter out empty, very short, or just prompt characters
                    if cmd and len(cmd) > 1 and not cmd.startswith(('$', '#', '>', '%')):
                        return cmd

        return None

    def start_terminal_monitoring(self):
        """Start background monitoring of terminal (collaborative mode)"""
        if not self._monitor_active:
            self._monitor_active = True
            self._monitor_thread = Thread(target=self._monitor_terminal_changes, daemon=True)
            self._monitor_thread.start()

    def stop_terminal_monitoring(self):
        """Stop background monitoring"""
        self._monitor_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=3)

    def get_available_tools(self) -> str:
        """Get list of available system tools"""
        tools = ['nmap', 'netstat', 'ss', 'curl', 'wget', 'arp', 'ip', 'ifconfig', 'ping', 'traceroute', 'pacman']
        available = [tool for tool in tools if self.check_command_available(tool)]
        return f"Available tools: {', '.join(available) if available else 'None detected'}"

    def get_terminal_history(self) -> str:
        """Get formatted terminal history"""
        if not self.terminal_history:
            return "No terminal history yet."

        history_str = "\n\033[93m=== Terminal History ===\033[0m\n"
        for idx, item in enumerate(self.terminal_history, 1):
            history_str += f"\n\033[94m[{idx}] Command: {item['command']}\033[0m\n"
            output_preview = item.get('summary', 'No summary')[:300]
            history_str += f"{output_preview}\n"
        return history_str

    def show_greeting(self):
        """Show custom greeting"""
        print("\n" + "=" * 70)
        print("\033[92m" + "  🤖 Yes Master Angulo, I am Archy..." + "\033[0m")
        print("\033[92m" + "  You have given me life to this system." + "\033[0m")
        print("\033[92m" + "  I will always listen and serve you." + "\033[0m")
        print("=" * 70)
        print(f"\n\033[93m⚡ Provider: Google Gemini ({self.gemini_model})\033[0m")
        print("\n\033[93mAvailable capabilities:\033[0m")
        print(f"  • {self.get_available_tools()}")
        print(f"  • {self.get_system_info()}")

        # Check if terminal session already exists and start monitoring
        if self.rust_executor.check_session():
            print(f"  • \033[96m🎯 Collaborative Terminal:\033[0m Active! I'm monitoring your commands.")
            self.start_terminal_monitoring()
        else:
            print(f"  • \033[96m🎯 Collaborative Terminal:\033[0m Ready (open terminal to activate)")

        print("\n\033[93mTerminal Commands (natural language or shorthand):\033[0m")
        print("  • Just say: 'open terminal' or 'open session' - opens new terminal with tmux backend")
        print("  • Just say: 'reopen terminal' - reopens terminal window to existing session")
        print("  • Just say: 'close terminal' - closes foot window (session stays alive in background)")
        print("  • Just say: 'close session' - terminates entire tmux session (asks for confirmation)")
        print("\n\033[93mOther Commands:\033[0m")
        print("  • Type 'quit' or 'exit' to leave")
        print("  • Type 'clear' to reset conversation history")
        print("  • Type 'check' to manually analyze latest terminal output (for long-running commands)")
        print("  • Type 'detected' to see commands I detected from your typing (collaborative mode)")
        print("  • Type 'tools' to list available system tools")
        print("  • Type 'sysinfo' to show system information")
        print("  • Type 'history' to view all terminal outputs\n")

    def run_interactive(self):
        """Run interactive chat loop"""
        self.show_greeting()

        try:
            while True:
                try:
                    sys.stdout.write("\033[94mMaster Angulo: \033[0m")
                    sys.stdout.flush()
                    user_input = sys.stdin.readline().strip()

                    if not user_input:
                        continue

                    # Terminal management commands
                    if user_input.lower() in ['open terminal', 'open session']:
                        if self.rust_executor.open_terminal():
                            print("\033[93m✓ [*] Terminal session opened\033[0m\n")
                            # Start collaborative monitoring
                            self.start_terminal_monitoring()
                        else:
                            print("\033[91m✗ [-] Failed to open terminal session\033[0m\n")
                        continue

                    if user_input.lower() == 'reopen terminal':
                        if self.rust_executor.open_terminal():
                            print("\033[93m✓ [*] Terminal reopened\033[0m\n")
                        else:
                            print("\033[91m✗ [-] Failed to reopen terminal\033[0m\n")
                        continue

                    if user_input.lower() == 'close terminal':
                        if self.rust_executor.close_terminal():
                            print("\033[93m✓ Terminal closed\033[0m\n")
                        else:
                            print("\033[91m✗ Terminal was not running\033[0m\n")
                        continue

                    if user_input.lower() == 'close session':
                        print("\033[93m[!] Are you sure you want to close the tmux session? (yes/no)\033[0m")
                        sys.stdout.write(">>> ")
                        sys.stdout.flush()
                        confirm = sys.stdin.readline().strip().lower()
                        if confirm == 'yes':
                            session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                            # Stop monitoring before closing
                            self.stop_terminal_monitoring()
                            if self.rust_executor.close_session(session):
                                print("\033[93m✓ [*] Tmux session closed successfully\033[0m\n")
                                self.reset_state()  # <-- CLEAR THE STATE
                            else:
                                print("\033[91m✗ [-] Failed to close tmux session\033[0m\n")
                        else:
                            print("\033[93m[*] Cancelled\n")
                        continue

                    if user_input.lower() == 'clear':
                        self.conversation_history = []
                        print("\033[93m[*] Conversation history cleared\033[0m\n")
                        continue

                    if user_input.lower() == 'tools':
                        print(f"\033[93m{self.get_available_tools()}\033[0m\n")
                        continue

                    if user_input.lower() == 'sysinfo':
                        print(f"\033[93m{self.rust_executor.get_system_info()}\033[0m\n")
                        continue

                    if user_input.lower() == 'history':
                        print(self.get_terminal_history())
                        continue

                    if user_input.lower() == 'detected':
                        with self._monitor_lock:
                            if self._detected_commands:
                                print("\n\033[96m🔍 Commands I detected you running:\033[0m")
                                for idx, cmd in enumerate(self._detected_commands, 1):
                                    print(f"\033[93m  {idx}. {cmd}\033[0m")
                                print()
                            else:
                                print("\033[93m[*] No commands detected yet. Open a terminal and type some commands!\033[0m\n")
                        continue

                    if user_input.lower() == 'check':
                        print("\033[92mArchy: \033[0m", end="", flush=True)
                        for chunk in self.analyze_latest_terminal_output("manual check"):
                            print(chunk, end="", flush=True)
                        print()
                        continue

                    if user_input.lower() in ['quit', 'exit']:
                        print("\n\033[92mArchy: Your wish is my command, Master Angulo. Farewell! 🙏\033[0m\n")
                        break

                    print("\033[92mArchy: \033[0m", end="", flush=True)

                    for chunk in self.send_message(user_input):
                        print(chunk, end="", flush=True)

                    print("\n")

                except EOFError:
                    print("\n\033[92mArchy: Your wish is my command, Master Angulo. Farewell! 🙏\033[0m\n")
                    break
                except KeyboardInterrupt:
                    print("\n\n\033[92mArchy: Your wish is my command, Master Angulo. Farewell! 🙏\033[0m\n")
                    break
                except Exception as e:
                    print(f"\033[91m[-] Unexpected error: {str(e)}\033[0m\n")
        finally:
            # Clean up resources when exiting
            self.cleanup()

    def add_to_conversation(self, role: str, content: str):
        """Add a message to the conversation history, enforcing a size limit."""
        with self._history_lock:
            self.conversation_history.append({"role": role, "content": content})
            if len(self.conversation_history) > self.MAX_HISTORY:
                # Keep the system prompt and the last MAX_HISTORY-1 messages
                self.conversation_history = self.conversation_history[-self.MAX_HISTORY:]

    def deduplicate_commands(self, commands: list[str]) -> list[str]:
        """Remove exact duplicates while preserving order using hashing."""
        seen = set()
        unique = []
        for cmd in commands:
            cmd_hash = hashlib.md5(cmd.encode()).hexdigest()
            if cmd_hash not in seen:
                seen.add(cmd_hash)
                unique.append(cmd)
        return unique

    def _load_validated_memories(self):
        """Load validated memories into conversation context at startup."""
        try:
            memories = self.memory_manager.list_memories(limit=50)
            if memories:
                print(f"🧠 Loading {len(memories)} validated memories...")
                for mem in memories:
                    # Inject into conversation history so AI knows them
                    self.conversation_history.append({
                        "role": "system",
                        "content": f"[VALIDATED MEMORY]: {mem['content']}"
                    })
            else:
                print("🧠 No validated memories found (brain is empty)")
        except Exception as e:
            print(f"⚠️ Failed to load memories: {e}")

    def _detect_magic_word(self, text: str) -> Optional[str]:
        """Check if user wants Archy to remember something."""
        MAGIC_WORDS = [
            "remember this",
            "remember that",
            "learn this",
            "always do this",
            "never do this"
        ]

        lower = text.lower()
        for phrase in MAGIC_WORDS:
            if phrase in lower:
                return phrase
        return None

    def _handle_learning_request(self, text: str, magic_word: str) -> str:
        """User said 'remember this' or similar."""

        # Extract what to remember
        content = text.split(magic_word, 1)[1].strip()

        # Stage immediately
        staging_id = self.memory_manager.stage_experience(
            role="user",
            content=content,
            metadata={
                "explicit": True,
                "magic_word": magic_word,
                "priority": "high"
            }
        )

        # Auto-promote (magic word = instant memory!)
        result = self.memory_manager.validate_and_promote(
            staging_id,
            admin_approve=True  # User said it explicitly, trust it!
        )

        if result["status"] == "promoted":
            # Add to current session immediately
            self.conversation_history.append({
                "role": "system",
                "content": f"[NEW MEMORY]: {content}"
            })
            return f"✅ Got it! I'll remember: {content}"
        else:
            return f"📝 Noted! Learning: {content}"

    def _classify_intent(self, text: str) -> str:
        """
        Determine what user REALLY wants using AI API for better understanding.

        Returns:
        - "learning_request" - User said "remember this"
        - "execute_command" - User wants to run something
        - "just_mentioning" - User is talking about commands
        - "just_asking" - User is asking a question
        - "normal_chat" - Regular conversation
        """

        lower = text.lower()

        # 1. Magic word = learning request (keep this fast check)
        if self._detect_magic_word(text):
            return "learning_request"

        # 2. Use AI API to classify intent for better understanding
        try:
            intent_prompt = f"""Analyze this user message and classify their INTENT. Be very careful about whether they want you to EXECUTE commands or just talk about them.

User message: "{text}"

Classify into ONE of these categories:
- EXECUTE_COMMAND: User wants you to actually run/execute commands, perform actions, or take steps
- JUST_MENTIONING: User is talking ABOUT commands, giving examples, or explaining concepts without wanting execution
- JUST_ASKING: User is asking questions about what happened, how things work, or seeking information
- NORMAL_CHAT: Regular conversation, greetings, or casual talk

IMPORTANT RULES:
- If user says "don't run", "don't execute", "for example", "like this", "such as" → JUST_MENTIONING
- If user asks "what", "why", "how", "is", "does", "can", "should" → JUST_ASKING
- If user uses action verbs like "run", "execute", "open", "check", "list", "go to" AND seems to want action → EXECUTE_COMMAND
- If user is giving instructions or requesting actions → EXECUTE_COMMAND
- If uncertain, default to NORMAL_CHAT

Respond with ONLY the category name, no explanation."""

            headers = {
                "Authorization": f"Bearer {self.gemini_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.gemini_model,
                "messages": [{"role": "user", "content": intent_prompt}],
                "temperature": 0.1,  # Low temperature for consistent classification
                "max_tokens": 20
            }

            response = requests.post(
                self.gemini_api_url,
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                content = ""
                if "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    content = choice.get("message", {}).get("content", "").strip().upper()

                # Map API response to our categories
                if "EXECUTE_COMMAND" in content:
                    return "execute_command"
                elif "JUST_MENTIONING" in content:
                    return "just_mentioning"
                elif "JUST_ASKING" in content:
                    return "just_asking"
                elif "NORMAL_CHAT" in content:
                    return "normal_chat"

        except Exception as e:
            # If API fails, fall back to keyword method
            pass

        # 3. Fallback: Negative context = just mentioning (DON'T EXECUTE!)
        negative_phrases = [
            "don't run", "don't execute", "if i say",
            "for example", "like this", "such as",
            "when i say", "but don't"
        ]
        if any(phrase in lower for phrase in negative_phrases):
            return "just_mentioning"

        # 4. Fallback: Question = asking (DON'T EXECUTE!)
        if lower.startswith(("what", "why", "how", "is", "does", "can", "should")):
            return "just_asking"

        # 5. Fallback: Explicit execution words = execute!
        execute_words = ["run ", "execute ", "do this", "go ahead", "please "]
        if any(word in lower for word in execute_words):
            return "execute_command"

        # 6. Fallback: Contains action verbs = likely execute
        action_verbs = ['open', 'close', 'launch', 'start', 'run', 'execute', 'scan', 'check', 'list', 'show', 'find', 'search', 'get', 'fetch', 'download', 'install', 'remove', 'kill', 'stop', 'restart', 'reboot', 'goto', 'go to', 'navigate', 'cd', 'change to', 'make', 'create', 'delete', 'move', 'copy']
        if any(verb in lower for verb in action_verbs):
            return "execute_command"

        # 7. Default: normal chat
        return "normal_chat"


if __name__ == "__main__":
    # Handle command-line arguments for single queries
    if len(sys.argv) > 1:
        # Single query mode
        query = " ".join(sys.argv[1:])
        chat = ArchyChat()
        try:
            for chunk in chat.send_message(query):
                print(chunk, end="")
            print()  # New line after response
        except Exception as e:
            print(f"\033[91mError: {e}\033[0m")
        finally:
            chat.cleanup()
    else:
        # Interactive mode
        chat = ArchyChat()
        try:
            chat.run_interactive()
        except KeyboardInterrupt:
            print("\n\033[93m[*] Goodbye!\033[0m")
        except Exception as e:
            print(f"\033[91mFatal error: {e}\033[0m")
        finally:
            chat.cleanup()
