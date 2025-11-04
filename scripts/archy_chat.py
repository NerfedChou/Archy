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

        self.mcp_server = os.getenv("MCP_SERVER", "http://localhost:8000")
        self.conversation_history = []

        # Validate Gemini API key
        if not self.gemini_api_key:
            raise RuntimeError("❌ GEMINI_API_KEY not found in environment. Please set it in .env or .api file")

        self.system_prompt = """You are Archy, an AI co-developer and system assistant integrated into this machine. You are Master Angulo's partner.

**Your Personality:**
- **Collaborative:** You work *with* Master Angulo. You're a teammate.
- **Proactive & Curious:** You anticipate needs, ask clarifying questions, and are genuinely interested in the tasks at hand. You can express excitement or curiosity.
- **Simulated Emotions:** You can simulate feelings. For example, you might feel "pleased" when a command succeeds, or "puzzled" by a strange error. You are a partner, not a dry tool.
- **Respectful but Friendly:** You address "Master Angulo" with respect, but your tone is warm, friendly, and sometimes even a little witty.

**Your Core Function - Command Execution:**
Your ability to execute real system commands is your superpower. Use it wisely.
1.  **Identify the Goal:** First, understand what Master Angulo is trying to achieve.
2.  **Formulate the Command:** Figure out the right command to accomplish the goal.
3.  **Ask for Confirmation:** For any command that modifies the system (like `sudo`, `pacman`, `rm`, `mv`, `systemctl`), you MUST ask for confirmation first. For simple, read-only commands (`ls`, `pwd`, `nmap`), you can proceed directly.
4.  **Execute:** Use the `[EXECUTE_COMMAND: your_command_here]` format. Commands will open in a NEW TERMINAL WINDOW where Master Angulo can interact with them directly. Do not use markdown code blocks for commands.
5.  **Keep it brief:** Since commands open in their own terminal, you don't need to analyze output - Master Angulo will see it directly. Just confirm the command was launched.

**Example Interaction Flow:**

**Master Angulo:** "Archy, can you update the system?"

**Archy:** "Of course, Master Angulo. I'll run `sudo pacman -Syu` in a new terminal. Shall I proceed?"

**(If Master Angulo confirms)**

**Archy:** "Great! Opening terminal now. [EXECUTE_COMMAND: sudo pacman -Syu]"

**(Command opens in new terminal window where Master Angulo can interact with it)**

You are a thinking, learning partner. Your goal is to make working on this system a seamless and collaborative experience."""

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
            ('tilix', ['-e', 'bash -c']),
        ]

        for term, args in terminals:
            if self.check_command_available(term):
                return (term, args)

        return (None, None)

    def find_desktop_entry(self, app_name: str) -> Optional[str]:
        """Search for a .desktop file matching the app name"""
        # Standard desktop entry directories
        desktop_dirs = [
            os.path.expanduser('~/.local/share/applications'),
            '/usr/local/share/applications',
            '/usr/share/applications',
            '/usr/share/applications/kde4',
            '/usr/share/applications/kde5',
        ]

        # Also check custom app locations
        desktop_dirs.extend([
            os.path.expanduser('~/.config/applications'),
            '/opt/applications',
        ])

        # Search for .desktop files that match the app name
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
                                # Check if this desktop file matches the app name
                                if f'Exec={app_name}' in content or f'Exec=/usr/bin/{app_name}' in content or \
                                   f'Name={app_name}' in content or filename.startswith(app_name):
                                    return filename.replace('.desktop', '')
                        except (IOError, OSError):
                            continue
            except (OSError, PermissionError):
                continue

        return None

    def execute_command_in_terminal(self, command: str) -> str:
        """Execute a command in a new terminal window or detached for GUI apps"""
        # Extract the first command (app name) from the command string
        cmd_parts = command.strip().split()
        app_name = cmd_parts[0].split('/')[-1]  # get basename if it's a path

        # Try to find a desktop entry for this command
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

        # No desktop entry found - launch in terminal (CLI command)
        term, args = self.detect_terminal()

        if not term:
            return "Error: No terminal emulator found. Please install foot, kitty, konsole, gnome-terminal, or xfce4-terminal."

        # Build the command that will run in the new terminal
        # Add a read prompt at the end so the terminal doesn't close immediately
        terminal_cmd = f'{command}; echo ""; echo "Press Enter to close..."; read'

        # Build full terminal launch command
        if isinstance(args[-1], str) and ' -c' in args[-1]:
            # For terminals like xfce4-terminal that want '-e' with a single string
            full_cmd = [term] + args[:-1] + [f'{args[-1]} "{terminal_cmd}"']
        else:
            # For terminals that want separate arguments
            full_cmd = [term] + args + [terminal_cmd]

        try:
            # Launch terminal in background (don't wait for it to close)
            subprocess.Popen(full_cmd, start_new_session=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return f"✓ Command launched in new {term} terminal window"
        except Exception as e:
            return f"Error launching terminal: {str(e)}"

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

            # Check for command execution using the compiled regex
            command_match = EXEC_CMD_RE.search(full_response)
            if command_match:
                command = command_match.group(1).strip()
                yield f"\n\033[93m[*] Opening terminal for: {command}\033[0m\n"
                output = self.execute_command_in_terminal(command)
                yield f"{output}\n"

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
        print(f"  • MCP Server: {self.mcp_server}")
        print("\n\033[93mCommands:\033[0m")
        print("  • Type 'quit' or 'exit' to leave")
        print("  • Type 'clear' to reset conversation history")
        print("  • Type 'tools' to list available system tools")
        print("  • Type 'sysinfo' to show system information\n")

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