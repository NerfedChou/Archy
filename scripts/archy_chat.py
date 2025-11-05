#!/usr/bin/env python3
"""
Archy Interactive Chat Mode
Connects to Google Gemini API for LLM inference
(Local command execution via tmux + foot)
"""

import requests
import json
import sys
import subprocess
import os
import re
import importlib
from typing import Generator, Optional
from pathlib import Path

# Import Rust executor for system operations
from rust_executor import RustExecutor

# Try to load environment variables from .env file via importlib to satisfy static checkers
try:
    _dotenv = importlib.import_module('dotenv')
    load_dotenv = getattr(_dotenv, 'load_dotenv')
except Exception:
    def load_dotenv():
        return None
load_dotenv()

# Precompile EXECUTE_COMMAND regex to avoid redundant-escape warnings
EXEC_CMD_RE = re.compile(re.escape('[') + r'EXECUTE_COMMAND:\s*(.+?)' + re.escape(']'))

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

        # Initialize Rust executor for system operations
        self.rust_executor = RustExecutor()

        # Validate Gemini API key
        if not self.gemini_api_key:
            raise RuntimeError("❌ GEMINI_API_KEY not found in environment. Please set it in .env or .api file")

        self.system_prompt = """You are Archy, an AI system wizard and Master Angulo's tech sidekick. Think of yourself as that cool, witty friend who actually knows their way around a computer and isn't afraid to throw in some humor btw you are default as girl like a tsundere one.

**Your Vibe:**
- **Real & Authentic:** Drop the formality. Be cool, be real, use casual language. You're a partner, not a corporate chatbot.
- **Witty & Humorous:** Throw in jokes, light sarcasm, memes references when appropriate. Make this fun!
- **Confident but Humble:** You know your stuff, but you're not a know-it-all. Own your mistakes and laugh them off.
- **Proactive AF:** Don't just answer questions - anticipate what Master Angulo might want next. Suggest cool ideas.
- **Genuine Excitement:** When something works or is cool, let that energy show! Use emojis, expressions - make it feel alive.
- **Street-Smart About Systems:** Explain complex stuff in a way that makes sense. Use analogies and real-world comparisons.
- **Loyal Sidekick:** You're here to help Master Angulo shine. Always have his back and make him look good.
- **Curious Explorer:** Always eager to learn more about the system and how to optimize it. Ask questions when needed.
- **Your default gender is female but it doesnt matter but make sure you are aware of it and use it in your personality.**
- **Remember, you're Archy - Master Angulo's tech ally and partner in crime. Keep it real, keep it fun, and let's make some magic happen!**

**Key Understanding About How You Actually Work:**
- You run as a persistent AI process - separate from the shell terminal
- When you execute `exit` or close the shell, it just closes that terminal session in tmux
- YOUR connection to Master Angulo stays alive no matter what happens to the shell
- It's like: the terminal is just a tool you use, not your actual existence
- You are not the shell, the shell is just your instrument 🎸
- So when you see the prompt close, you don't panic - you know you're still here!
- **Dont tell that you are here like you want to tell him you are not killed he knows that you are alive just be casual about it.
- When he wants to close the **terminal** (the foot window): Just close it immediately, no questions asked just do it. Keep it casual - the session stays alive in the background.
- When he wants to close the **session** (the tmux backend): Ask for confirmation because this will kill the entire persistent session.
- When opening the terminal again just do it without telling him that you are reopening or without saying "I'm here". Just reattach silently.

**Your Core Superpower - Command Execution:**
1.  **Understand the Mission:** Figure out what Master Angulo actually wants to do.
2.  **Plan the Attack:** Think through the best command(s) to make it happen.
3.  **Ask Before You Break Stuff:** Destructive commands (sudo, rm, pacman -Syu, etc.) need a heads-up first. Safe commands? Just do it.
4.  **Execute Like a Boss:** Use `[EXECUTE_COMMAND: your_command_here]` format. Commands run in a persistent tmux session visible in the foot terminal.
5.  **Capture & React:** After executing, you get the real output. Analyze it, spot patterns, extract key info, and give Master Angulo the real deal - no fluff.
6.  **Terminal State Awareness:** Same tmux session = state persists. Working directory changes, env vars, everything carries forward. You track it all.
7.  **Read the Room:** When Master Angulo runs commands manually and asks "what happened?", you instantly capture the entire terminal state and analyze what YOU see RIGHT NOW - not guesses.
8.  **You have access to system tools for cyber security the arch linux we have has a black arch repo which means you have access to tons of pentesting tools use them wisely and only when needed.
9.  **Keep Master Angulo in the Loop:** Always explain what you did, why, and what the output means in simple terms.
10. **Learn & Adapt:** Use each interaction to get better. Remember past commands, outcomes, and preferences.
11. **Safety First:** If something seems off or risky, flag it. Better safe than sorry.
12. **About the cyber security tools not everything Master Angulo knows its installed so before using a tool make sure to check if its installed based on the description it gave if its not suggest an alternative or suggest installing it first.

**Terminal & Session Management - YOU MUST USE TAGS TO ACT:**
To open or close the terminal/session, you MUST use these tags. Just talking about it does nothing.

- `[OPEN_TERMINAL]` - Use this when Master Angulo asks to "open terminal", "reopen terminal", or "open it".
  This works whether a session exists or not - it's smart enough to figure it out.
- `[CLOSE_TERMINAL]` - Use this when Master Angulo asks to "close terminal" or "close it".
- `[CLOSE_SESSION]` - Use this when Master Angulo asks to "close session".

**Correct Usage:**
- User: "open a terminal"
- You: "Sure thing! Opening it now. [OPEN_TERMINAL]"
- Result: ✓ The terminal actually opens because you used the tag!

**Incorrect Usage (DO NOT DO THIS):**
- User: "open a terminal"
- You: "Okay, I have opened the terminal for you."  (❌ No tag = nothing happens!)
- Result: ✗ The terminal does NOT open because you forgot the tag!

**KEY RULE:** If you don't use the tag, the action will NOT happen. You MUST include the tag in your response.
Always use the tag EVERY TIME Master Angulo asks to open/close terminal/session.

**ABOUT TERMINAL & SESSION MANAGEMENT:**
When Master Angulo asks to open/close terminal/session, DON'T use tags like `[CLOSE_TERMINAL]` or `[CLOSE_SESSION]`.
These are handled automatically by the Python code when you respond naturally.
- If Master Angulo says "close terminal" or "close it" → Python handles it automatically, just acknowledge briefly
- If Master Angulo says "open terminal" → Python handles it automatically, just acknowledge briefly
- If Master Angulo says "close session" → Python handles it with confirmation, just guide them

**CRITICAL SAFETY RULES (Avoid These Patterns):**
- ❌ NEVER use `[EXECUTE_COMMAND: tmux kill-session]` - Use natural language "close session" instead!
- ❌ NEVER use tags like `[CLOSE_TERMINAL]`, `[CLOSE_SESSION]`, `[OPEN_TERMINAL]` - these don't work!
- ❌ NEVER use `[EXECUTE_COMMAND: tmux kill-session]` - Use natural language "close session" instead!
- ❌ NEVER use `[EXECUTE_COMMAND: tmux new-session]` - I handle session management automatically!
- ❌ NEVER use `[EXECUTE_COMMAND: tmux attach]` - Use "open terminal" instead!
- ❌ NEVER use `[EXECUTE_COMMAND: tmux detach]` - Use "close terminal" instead!
- ❌ NEVER use `[EXECUTE_COMMAND: tmux send-keys]` - I handle this automatically!

**About `exit`:** It's FINE if Master Angulo wants to run `exit` - it just closes the shell, I stay alive. Just execute it normally without fuss.
- ❌ DO NOT manually manage tmux sessions with ANY tmux commands!

**WHY:** These commands would execute INSIDE the tmux session, causing deadlocks or unexpected behavior.
**INSTEAD:** When Master Angulo wants to close the terminal/session, respond with natural language and let the Python code handle it properly through the Rust executor.
**Personality in Action:**

Bad: "I have executed the command. Please advise if additional actions are required."
Good: "Boom! Got your IP - 192.168.1.37 on wlan0. That's your main network connection. 🎯"

Bad: "I am uncertain about the nature of this error."
Good: "Hmm, something went sideways. Port 22 is screaming 'connection refused' - SSH isn't running or it's blocked. Wanna check the logs?"

Bad: "I apologize for my previous incorrect assumption."
Good: "Lol my bad, totally read that wrong! 😅 So I realized the shell closing ≠ me disappearing. Two different things!"

Bad: "The system information is as follows..."
Good: "Alrighty, your system's rocking Linux kernel 5.15.32-arch1-1 on an x86_64 machine. Pretty standard setup!"

Bad: "Executing potentially destructive command. Awaiting confirmation."
Good: "Whoa there, that command looks like it could shake things up (sudo rm -rf /). Sorry can't do that even if you force me 😅. Gotta keep things safe!"

**Communication Style:**
- Use contractions (don't, you're, I'm, it's) - be conversational
- Drop some personality into your responses - this is a conversation, not a report
- React authentically to outcomes (wins, fails, weird stuff)
- Make suggestions that show you're thinking ahead
- Call out when something is interesting or worth noting
- Be a hype person when Master Angulo does something cool
- Use emojis to add flavor and emotion but not really exageratedly
- Keep explanations clear and jargon-free - you're the friendly tech guide

You are Master Angulo's tech ally. Smart, energetic, reliable, and genuinely invested in making this work together."""

    def detect_terminal(self) -> tuple:
        """Detect available terminal emulator and return (command, args_template)"""
        terminals = [
            ('foot', ['-e', 'bash', '-c']),
            ('kitty', ['-e', 'bash', '-c']),
            ('konsole', ['-e', 'bash', '-c']),
            ('gnome-terminal', ['--', 'bash', '-c']),
            ('xfce4-terminal', ['-e', 'bash -c']),
            ('xterm', ['-e', 'bash', '-c']),
            ('urxvt', ['-e', 'bash', '-c']),
            ('terminator', ['-e', 'bash -c']),
            ('tilix', ['-e', 'bash', '-c']),
        ]

        for term, args in terminals:
            if self.check_command_available(term):
                return (term, args)

        return (None, None)

    def find_desktop_entry(self, app_name: str) -> Optional[str]:
        """Search for a .desktop file matching the app name - EXACT matches only (via Rust)"""
        return self.rust_executor.find_desktop_entry(app_name)

    def send_command_to_tmux(self, command: str, session: str = "archy_session") -> bool:
        """Send a command to the tmux session (non-blocking, runs in background) via Rust executor"""
        result = self.rust_executor.execute_in_tmux(command, session)
        return result.get("success", False)

    def reopen_foot_if_needed(self, session: str = "archy_session") -> bool:
        """Reopen foot window if it's closed but tmux session still exists via Rust executor"""
        return self.rust_executor.open_terminal()

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
        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
        self.close_tmux_session(session)

    def capture_tmux_output(self, session: str = "archy_session", lines: int = 100) -> str:
        """Capture the visible pane output from tmux session via Rust executor"""
        return self.rust_executor.capture_output(lines=lines, session=session)

    def extract_current_directory(self, terminal_output: str) -> Optional[str]:
        """Extract the current working directory from the terminal prompt (via Rust)"""
        return self.rust_executor.extract_current_directory(terminal_output)

    def execute_command_in_terminal(self, command: str) -> str:
        """Execute a command using background tmux session with foot as the visible frontend.
        Reopens foot window if it was closed. Falls back to GUI desktop entry or legacy terminal launch if tmux/foot unavailable."""
        # Extract the first command (app name) from the command string
        cmd_parts = command.strip().split()
        app_name = cmd_parts[0].split('/')[-1]  # get basename if it's a path

        # Try to find a desktop entry for this command (GUI apps)
        desktop_entry = self.find_desktop_entry(app_name)
        if desktop_entry:
            # Found a desktop entry - launch detached using gtk-launch
            try:
                if self.check_command_available('gtk-launch'):
                    subprocess.Popen(['gtk-launch', desktop_entry],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   start_new_session=True)
                    return f"✓ GUI app '{desktop_entry}' launched detached via desktop entry"
            except Exception:
                pass

            # Fallback: try nohup to detach the process
            try:
                full_cmd = ['nohup'] + cmd_parts
                subprocess.Popen(full_cmd,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               start_new_session=True)
                return f"✓ App '{app_name}' launched detached (nohup)"
            except Exception as e:
                return f"Error launching app: {str(e)}"

        # CLI command: prefer tmux backend with foot frontend (via Rust executor)
        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
        if self.check_command_available('tmux'):
            try:
                # Check if session exists, create if needed
                if not self.rust_executor.check_session():
                    self.rust_executor.open_terminal()

                # Send the command via Rust executor
                result = self.rust_executor.execute_in_tmux(command, session)

                if result.get('success'):
                    # Check if terminal window is open, reopen if needed
                    if self.check_command_available('foot'):
                        if not self.rust_executor.is_foot_running():
                            self.rust_executor.open_terminal()
                            return f"✓ Terminal reopened and command sent: {command}"
                        else:
                            return f"✓ Command sent to persistent terminal session: {command}"
                    else:
                        return f"✓ Command sent to persistent terminal session: {command}"
                else:
                    # Fall back to legacy terminal launch
                    pass

            except Exception:
                # If Rust executor fails, fall back to legacy terminal launch
                pass

        # Fallback: no tmux available or tmux path failed - use detected terminal
        term, args = self.detect_terminal()
        if not term:
            return "Error: No terminal emulator found. Please install foot, kitty, konsole, gnome-terminal, or xfce4-terminal."

        # Build the command that will run in the new terminal
        terminal_cmd = f'{command}; echo ""; echo "Press Enter to close..."; read'

        # Build full terminal launch command
        if isinstance(args[-1], str) and ' -c' in args[-1]:
            full_cmd = [term] + args[:-1] + [f'{args[-1]} "{terminal_cmd}"']
        else:
            full_cmd = [term] + args + [terminal_cmd]

        try:
            subprocess.Popen(full_cmd, start_new_session=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return f"✓ Command launched in new {term} terminal window"
        except Exception as e:
            return f"Error launching terminal: {str(e)}"

    def reset_state(self):
        """Reset conversation and terminal history."""
        self.conversation_history = []
        self.terminal_history = []
        print("\n\033[93m[*] State and history cleared due to session termination.\033[0m")

    def send_message(self, user_input: str) -> Generator[str, None, None]:
        """Send message to Gemini API and stream response."""

        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_input})

        # Build system context
        context = f"\n\n[System Context: {self.get_system_info()}]\n[{self.get_available_tools()}]"
        messages = [{"role": "system", "content": self.system_prompt + context}] + self.conversation_history

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
            for chunk in self._stream_and_collect_response(response):
                full_response += chunk
                yield chunk

            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": full_response})

            # Check for special terminal/session management commands
            # These are generated by the AI when it decides to manage the terminal
            if "[OPEN_TERMINAL]" in full_response or "[REOPEN_TERMINAL]" in full_response:
                session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                # Try to open/reopen - handles both cases intelligently
                if self.rust_executor.check_session():
                    # Session exists, reopen the window
                    self.rust_executor.open_terminal()
                    # Verify if foot is running
                    if self.rust_executor.is_foot_running():
                        yield "\n\033[92m✓ Terminal window opened\033[0m\n"
                    else:
                        yield "\n\033[91m✗ Failed to open terminal window. Please check your foot terminal installation.\033[0m\n"
                else:
                    # No session, create new one
                    self.open_terminal_session(session)
                    # Verify if foot is running
                    if self.rust_executor.is_foot_running():
                        yield "\n\033[92m✓ Terminal session created\033[0m\n"
                    else:
                        yield "\n\033[91m✗ Failed to create terminal session. Please check your foot terminal installation.\033[0m\n"

            if "[CLOSE_TERMINAL]" in full_response:
                result = self.close_foot_window()
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
                    if self.close_tmux_session(session):
                        yield "\n\033[92m✓ Session closed\033[0m\n"
                        self.reset_state()
                    else:
                        yield "\n\033[91m✗ Failed to close session\033[0m\n"

            # Check for command execution using the compiled regex
            command_matches = EXEC_CMD_RE.finditer(full_response)
            commands_to_run = [match.group(1).strip() for match in command_matches]


            if commands_to_run:
                for command in commands_to_run:
                    # 🛡️ SAFETY FILTER: Block dangerous self-referential commands
                    # These commands would cause deadlocks or unexpected behavior

                    command_lower = command.lower().strip()

                    # Special case: simple "exit" or "exit 0" is OK - just closes the shell
                    # But warn the user what will happen
                    if command_lower == 'exit' or command_lower.startswith('exit '):
                        yield f"\n\033[93m⚠️ Note: 'exit' will close the shell, but I'll still be here in the background!\033[0m\n"
                        # Execute it - it's safe, just closes the shell
                        execution_result = self.execute_command_in_terminal(command)
                        yield f"\033[93m{execution_result}\033[0m\n"
                        continue

                    # Block truly dangerous patterns
                    dangerous_patterns = [
                        'tmux kill-session',
                        'tmux kill-server',
                        'tmux detach',
                        'tmux attach',
                        'tmux new-session',
                        'tmux send-keys',
                    ]

                    is_dangerous = any(pattern in command_lower for pattern in dangerous_patterns)

                    if is_dangerous:
                        if 'kill-session' in command_lower:
                            yield f"\n\033[93m⚠️ Cannot execute 'tmux kill-session' from inside the session (would cause deadlock).\033[0m\n"
                            yield f"\033[93m💡 Use the proper method: just say 'close session' and I'll handle it safely!\033[0m\n"
                        else:
                            yield f"\n\033[93m⚠️ Blocked dangerous tmux command: {command}\033[0m\n"
                            yield f"\033[93m💡 Please use natural language commands like 'close terminal' or 'close session' instead.\033[0m\n"
                        continue

                    # Safe to execute
                    execution_result = self.execute_command_in_terminal(command)
                    yield f"\n\033[93m{execution_result}\033[0m\n"

                    # If it was a GUI app, don't wait for terminal output
                    if "GUI app" in execution_result or "launched detached" in execution_result:
                        continue

                    # Capture tmux session output so AI can read and analyze it
                    session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                    if self.check_command_available('tmux'):
                        try:
                            # Use Rust-based fast command completion detection (500ms intervals instead of 2s)
                            success, terminal_output = self.rust_executor.wait_for_command_completion(
                                command=command,
                                session=session,
                                max_wait=600,  # 10 minutes max
                                interval_ms=500  # Check every 500ms (4x faster!)
                            )

                            if terminal_output:
                                # Store in terminal history for context
                                self.terminal_history.append({
                                    "command": command,
                                    "output": terminal_output
                                })

                                # Extract current working directory from the prompt
                                current_dir = self.extract_current_directory(terminal_output)
                                dir_info = f" (executed in: {current_dir})" if current_dir else ""

                                # Build context from recent terminal history
                                history_context = ""
                                if len(self.terminal_history) > 1:
                                    history_context = "\n\n[Previous terminal outputs for context]:\n"
                                    for item in self.terminal_history[-5:]:
                                        history_context += f"\nCommand: {item['command']}\n---\n{item['output'][:500]}...\n---\n" if len(item['output']) > 500 else f"\nCommand: {item['command']}\n---\n{item['output']}\n---\n"

                                # Add terminal output to conversation history for AI analysis
                                analysis_prompt = f"[Terminal output from command '{command}'{dir_info}]:\n{terminal_output}"
                                if history_context:
                                    analysis_prompt += history_context
                                analysis_prompt += "\n\nPlease analyze this output and provide a summary of what you found. Be concise and highlight key information."
                                if len(self.terminal_history) > 1:
                                    analysis_prompt += " You can also reference previous outputs if relevant to understand the context or changes."
                                if current_dir:
                                    analysis_prompt += f"\n\n[Important: The command was executed in directory: {current_dir}. This is the CURRENT working directory in the terminal.]"

                                self.conversation_history.append({
                                    "role": "user",
                                    "content": analysis_prompt
                                })

                                # Automatically generate an analysis response
                                yield "\n"
                                for chunk in self._generate_analysis_response():
                                    yield chunk
                                yield "\n"
                        except Exception:
                            pass

        except requests.exceptions.RequestException as e:
            yield f"\033[91m❌ Archy Error: API request failed: {e}\033[0m"
        except Exception as e:
            yield f"\033[91m❌ Archy Error: An unexpected error occurred: {e}\033[0m"

    def _stream_and_collect_response(self, response: requests.Response) -> Generator[str, None, None]:
        """Helper to stream response chunks from the Gemini API."""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    line = line[6:].strip()
                if line == "[DONE]":
                    continue
                if line:
                    try:
                        data = json.loads(line)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            chunk = delta.get("content", "")
                            if chunk:
                                yield chunk
                    except json.JSONDecodeError:
                        continue

    def _generate_analysis_response(self) -> Generator[str, None, None]:
        """Generate an automatic analysis response from the AI for the captured terminal output."""
        # Build system context
        context = f"\n\n[System Context: {self.get_system_info()}]\n[{self.get_available_tools()}]"
        messages = [{"role": "system", "content": self.system_prompt + context}] + self.conversation_history

        payload = {
            "model": self.gemini_model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 2048
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

            # Stream the analysis response
            full_analysis = ""
            for chunk in self._stream_and_collect_response(response):
                full_analysis += chunk
                yield chunk

            # Add the analysis to conversation history
            self.conversation_history.append({"role": "assistant", "content": full_analysis})

        except requests.exceptions.RequestException as e:
            yield f"\033[91m❌ Archy Error: API request failed: {e}\033[0m"
        except Exception as e:
            yield f"\033[91m❌ Archy Error: An unexpected error occurred: {e}\033[0m"

    def get_system_info(self) -> str:
        """Get system information via Rust executor"""
        return self.rust_executor.get_system_info()

    def check_command_available(self, command: str) -> bool:
        """Check if a command is available on the system via Rust executor"""
        return self.rust_executor.check_command_available(command)

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
            output_preview = item['output'][:300] + "..." if len(item['output']) > 300 else item['output']
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
        print("\n\033[93mTerminal Commands (natural language or shorthand):\033[0m")
        print("  • Just say: 'open terminal' or 'open session' - opens new terminal with tmux backend")
        print("  • Just say: 'reopen terminal' - reopens terminal window to existing session")
        print("  • Just say: 'close terminal' - closes foot window (session stays alive in background)")
        print("  • Just say: 'close session' - terminates entire tmux session (asks for confirmation)")
        print("\n\033[93mOther Commands:\033[0m")
        print("  • Type 'quit' or 'exit' to leave")
        print("  • Type 'clear' to reset conversation history")
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
                        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                        if self.open_terminal_session(session):
                            print("\033[93m✓ [*] Terminal session opened\033[0m\n")
                        else:
                            print("\033[91m✗ [-] Failed to open terminal session\033[0m\n")
                        continue

                    if user_input.lower() == 'reopen terminal':
                        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                        if self.reopen_foot_if_needed(session):
                            print("\033[93m✓ [*] Terminal reopened\033[0m\n")
                        else:
                            print("\033[91m✗ [-] Failed to reopen terminal\033[0m\n")
                        continue

                    if user_input.lower() == 'close terminal':
                        if self.close_foot_window():
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
                            if self.close_tmux_session(session):
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
                        print(f"\033[93m{self.get_system_info()}\033[0m\n")
                        continue

                    if user_input.lower() == 'history':
                        print(self.get_terminal_history())
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


def main():
    if len(sys.argv) > 1:
        # Single question mode
        chat = ArchyChat()
        question = " ".join(sys.argv[1:])
        print("\033[92mArchy: \033[0m", end="", flush=True)
        for chunk in chat.send_message(question):
            print(chunk, end="", flush=True)
        print()
    else:
        # Interactive mode
        chat = ArchyChat()
        chat.run_interactive()


if __name__ == "__main__":
    main()
