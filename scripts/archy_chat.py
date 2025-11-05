#!/usr/bin/env python3
"""
Archy Interactive Chat Mode
Connects to Google Gemini API for LLM inference
With system integration and command execution via MCP
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
        self.foot_process = None  # Track the actual foot process object (PID)
        self.terminal_history = []  # Track all terminal outputs for context

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
10.  **Learn & Adapt:** Use each interaction to get better. Remember past commands, outcomes, and preferences.
11.  **Safety First:** If something seems off or risky, flag it. Better safe than sorry.
12. **About the cyber security tools not everything Master Angulo knows its installed so before using a tool make sure to check if its installed based on the description it gave if its not suggest an alternative or suggest installing it first.

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
        """Search for a .desktop file matching the app name - EXACT matches only"""
        desktop_dirs = [
            os.path.expanduser('~/.local/share/applications'),
            '/usr/local/share/applications',
            '/usr/share/applications',
            '/usr/share/applications/kde4',
            '/usr/share/applications/kde5',
            os.path.expanduser('~/.config/applications'),
            '/opt/applications',
        ]

        for desktop_dir in desktop_dirs:
            if not os.path.isdir(desktop_dir):
                continue
            try:
                for filename in os.listdir(desktop_dir):
                    if filename.endswith('.desktop'):
                        filepath = os.path.join(desktop_dir, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()

                                # ✅ FIXED: Use regex for exact word boundaries
                                # This ensures "ls" doesn't match "lsotop"
                                import re

                                # Match Exec line with exact command (word boundary)
                                exec_patterns = [
                                    rf'^Exec={re.escape(app_name)}(\s|$)',  # Exec=ls (space or end)
                                    rf'^Exec=/usr/bin/{re.escape(app_name)}(\s|$)',  # Exec=/usr/bin/ls
                                    rf'^Exec=.+/bin/{re.escape(app_name)}(\s|$)',  # Any path ending in /bin/ls
                                ]

                                for pattern in exec_patterns:
                                    if re.search(pattern, content, re.MULTILINE):
                                        return filename.replace('.desktop', '')

                                # Check desktop file name matches EXACTLY
                                desktop_name = filename.replace('.desktop', '')
                                if desktop_name.lower() == app_name.lower():
                                    return desktop_name

                        except (IOError, OSError):
                            continue
            except (OSError, PermissionError):
                continue

        return None

    def send_command_to_tmux(self, command: str, session: str = "archy_session") -> bool:
        """Send a command to the tmux session (non-blocking, runs in background)"""
        try:
            subprocess.run(['tmux', 'send-keys', '-t', session, command, 'C-m'], check=False)
            return True
        except Exception:
            return False

    def is_foot_running(self) -> bool:
        """Check if the foot process is still alive"""
        if self.foot_process is None:
            return False

        # Check if process is still running
        try:
            # poll() returns None if process is still running
            if self.foot_process.poll() is None:
                return True
            else:
                # Process has terminated
                self.foot_process = None
                return False
        except Exception:
            return False

    def reopen_foot_if_needed(self, session: str = "archy_session") -> bool:
        """Reopen foot window if it's closed but tmux session still exists"""
        if self.is_foot_running():
            return True  # Already open, no need to reopen

        # Foot is closed, reopen it
        if self.check_command_available('foot'):
            try:
                self.foot_process = subprocess.Popen(
                    ['foot', '-e', 'tmux', 'attach', '-t', session],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                return False
        return False

    def close_tmux_session(self, session: str = "archy_session") -> bool:
        """Close the tmux session and clean up"""
        try:
            # First, kill the foot window if it's still running
            if self.is_foot_running():
                try:
                    self.foot_process.terminate()
                    self.foot_process.wait(timeout=2)
                except Exception:
                    self.foot_process.kill()
                self.foot_process = None

            # Then kill the tmux session
            result = subprocess.run(['tmux', 'kill-session', '-t', session],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except Exception:
            return False

    def cleanup(self):
        """Clean up resources when Archy exits"""
        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
        self.close_tmux_session(session)

    def capture_tmux_output(self, session: str = "archy_session", lines: int = 100) -> str:
        """Capture the visible pane output from tmux session"""
        try:
            result = subprocess.run(
                ['tmux', 'capture-pane', '-pt', session, '-S', f'-{lines}'],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception:
            return ""

    def extract_current_directory(self, terminal_output: str) -> Optional[str]:
        """Extract the current working directory from the terminal prompt"""
        lines = terminal_output.strip().split('\n')
        if not lines:
            return None

        # Look at the last few lines for the prompt
        for line in reversed(lines[-5:]):
            # Common prompt patterns: user@host:path$ or user@host ~/path$ or just path$
            # Extract directory from patterns like:
            # chef@Developie ~/Downloads$ or [chef@Developie Downloads]$ or ~/path $
            import re

            # Pattern 1: user@host:path$ (after colon)
            match = re.search(r':([~\w/.-]+)\s*\$', line)
            if match:
                return match.group(1)

            # Pattern 2: user@host path$ (space before path and $)
            match = re.search(r'\s([~\w/.-]+)\s*\$', line)
            if match:
                return match.group(1)

            # Pattern 3: [user@host path]$ (inside brackets)
            match = re.search(r'\[.*\s([~\w/.-]+)]', line)
            if match:
                return match.group(1)

        return None

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

        # CLI command: prefer tmux backend with foot frontend
        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
        if self.check_command_available('tmux'):
            try:
                # Ensure detached tmux session exists
                has = subprocess.run(['tmux', 'has-session', '-t', session],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if has.returncode != 0:
                    subprocess.run(['tmux', 'new-session', '-d', '-s', session], check=True)

                # Send the command into the tmux session
                subprocess.run(['tmux', 'send-keys', '-t', session, command, 'C-m'], check=False)

                # Check if foot window is running, reopen it if needed
                if self.check_command_available('foot'):
                    if not self.is_foot_running():
                        # Foot is closed, reopen it
                        self.reopen_foot_if_needed(session)
                        return f"✓ Terminal reopened and command sent: {command}"
                    else:
                        return f"✓ Command sent to persistent terminal session: {command}"
                else:
                    return f"✓ Command sent to persistent terminal session: {command}"

            except Exception:
                # If tmux path fails, fall back to legacy terminal launch
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

    def send_message(self, user_input: str) -> Generator[str, None, None]:
        """Send message to Gemini API and stream response."""

        # Check if user is asking to analyze terminal output or asking what commands were run
        analyze_keywords = ['analyze', 'what happened', 'see the output', 'show me', 'what did',
                           'look at', 'check the', 'read the', 'you see', 'can you see',
                           'what command', 'did i run', 'what i', 'see what']
        should_capture = any(keyword in user_input.lower() for keyword in analyze_keywords)

        # ALWAYS capture terminal output when user asks questions (real-time capture)
        if should_capture:
            session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
            if self.check_command_available('tmux'):
                try:
                    import time
                    # Small delay to ensure terminal has flushed output
                    time.sleep(0.3)
                    # Capture the entire terminal buffer (up to 1000 lines) RIGHT NOW
                    terminal_output = self.capture_tmux_output(session=session, lines=1000)
                    if terminal_output:
                        # Prepend the CURRENT terminal state to the user's message
                        user_input = f"[Current terminal buffer - captured just now]:\n{terminal_output}\n\n[User's question]: {user_input}\n\nNote: This is the LIVE terminal state right now, including any commands Master Angulo ran manually."
                except Exception:
                    pass

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

            # Check for command execution using the compiled regex
            command_match = EXEC_CMD_RE.search(full_response)
            if command_match:
                command = command_match.group(1).strip()
                self.execute_command_in_terminal(command)

                # Capture tmux session output so AI can read and analyze it (silently, no print)
                session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")
                if self.check_command_available('tmux'):
                    try:
                        import time

                        # For sudo commands or long-running commands, wait longer and poll multiple times
                        is_sudo_or_long = any(keyword in command.lower() for keyword in ['sudo', 'pacman', 'apt', 'yum', 'nmap', 'make', 'cargo'])

                        if is_sudo_or_long:
                            # Long-running command: wait up to 30 seconds, polling every 2 seconds
                            terminal_output = ""
                            last_output = ""

                            for attempt in range(15):  # 15 attempts * 2 seconds = up to 30 seconds
                                time.sleep(2)
                                current_output = self.capture_tmux_output(session=session, lines=500)

                                if current_output:
                                    terminal_output = current_output

                                    # Check if the command has finished (prompt returned)
                                    # Look for shell prompt patterns at the end
                                    if any(prompt in terminal_output.split('\n')[-1] for prompt in ['$', '#', '❯', '~']):
                                        # Prompt detected, command likely finished
                                        break

                                    # If output hasn't changed for 2 checks, it's probably done
                                    if current_output == last_output:
                                        break

                                    last_output = current_output
                        else:
                            # Quick command: wait just a bit longer (3 seconds)
                            time.sleep(3)
                            terminal_output = self.capture_tmux_output(session=session, lines=200)

                        if terminal_output:
                            # Store in terminal history for context
                            self.terminal_history.append({
                                "command": command,
                                "output": terminal_output
                            })

                            # Extract current working directory from the prompt
                            current_dir = self.extract_current_directory(terminal_output)
                            dir_info = f" (executed in: {current_dir})" if current_dir else ""

                            # Build context from recent terminal history (last 5 commands)
                            history_context = ""
                            if len(self.terminal_history) > 1:
                                history_context = "\n\n[Previous terminal outputs for context]:\n"
                                for item in self.terminal_history[-5:]:  # Last 5 commands
                                    history_context += f"\nCommand: {item['command']}\n---\n{item['output'][:500]}...\n---\n" if len(item['output']) > 500 else f"\nCommand: {item['command']}\n---\n{item['output']}\n---\n"

                            # Add terminal output to conversation history so AI can see and analyze it
                            # But don't print it to the user - keep terminal clean
                            analysis_prompt = f"[Terminal output from command '{command}'{dir_info}]:\n{terminal_output}"
                            if history_context:
                                analysis_prompt += history_context
                            analysis_prompt += "\n\nPlease analyze this output and provide a summary of what you found. Be concise and highlight key information."
                            if len(self.terminal_history) > 1:
                                analysis_prompt += " You can also reference previous outputs if relevant to understand the context or changes."

                            # Add extra context about directory changes
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
                    except Exception as e:
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
        """Get system information"""
        try:
            result = subprocess.run(['uname', '-a'], capture_output=True, text=True, timeout=5)
            return f"System: {result.stdout.strip()}"
        except:
            return "System info unavailable"

    def check_command_available(self, command: str) -> bool:
        """Check if a command is available on the system"""
        try:
            result = subprocess.run(['which', command], capture_output=True, text=True, timeout=2)
            return result.returncode == 0
        except:
            return False

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
        print("\n\033[93mCommands:\033[0m")
        print("  • Type 'quit' or 'exit' to leave")
        print("  • Type 'clear' to reset conversation history")
        print("  • Type 'tools' to list available system tools")
        print("  • Type 'sysinfo' to show system information")
        print("  • Type 'history' to view all terminal outputs\n")

    def run_interactive(self):
        """Run interactive chat loop"""
        self.show_greeting()

        while True:
            try:
                sys.stdout.write("\033[94mMaster Angulo: \033[0m")
                sys.stdout.flush()
                user_input = sys.stdin.readline().strip()

                if not user_input:
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