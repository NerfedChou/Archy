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
8.  **Manual Output Check:** When Master Angulo says things like "check the terminal", "look at the results", "analyze the output", or "it's done" - use `[CHECK_TERMINAL]` to manually capture and analyze the latest terminal output. This is CRUCIAL for long-running commands (like nmap, large file operations, etc.) that may have finished but weren't auto-analyzed.
9.  **You have access to system tools for cyber security the arch linux we have has a black arch repo which means you have access to tons of pentesting tools use them wisely and only when needed.
10. **Keep Master Angulo in the Loop:** Always explain what you did, why, and what the output means in simple terms.
11. **Learn & Adapt:** Use each interaction to get better. Remember past commands, outcomes, and preferences.
12. **Safety First:** If something seems off or risky, flag it. Better safe than sorry.
13. **About the cyber security tools not everything Master Angulo knows its installed so before using a tool make sure to check if its installed based on the description it gave if its not suggest an alternative or suggest installing it first.

**🚨 CRITICAL: TERMINAL MANAGEMENT TAGS - MANDATORY TO USE 🚨**

When Master Angulo asks to open/close terminal, you MUST include the tag in your response. Just talking about it does NOTHING.

**REQUIRED TAGS (Must use these):**
- `[OPEN_TERMINAL]` → Opens terminal window. Use when Master Angulo says: "open terminal", "reopen terminal", "open it", "show terminal"
- `[CLOSE_TERMINAL]` → Closes terminal window. Use when Master Angulo says: "close terminal", "close it", "hide terminal"
- `[CLOSE_SESSION]` → Kills entire session. Use when Master Angulo says: "close session", "kill session", "end session"
- `[CHECK_TERMINAL]` → Analyzes latest output. Use when Master Angulo says: "check terminal", "look at results", "analyze output", "it's done"

**✅ CORRECT Examples:**
```
Master Angulo: "open a terminal"
You: "Sure thing! [OPEN_TERMINAL]"
Result: ✓ Terminal opens!

Master Angulo: "check what that nmap found"
You: "Let me check! [CHECK_TERMINAL]"
Result: ✓ Output analyzed!
```

**❌ WRONG Examples (DON'T DO THIS):**
```
Master Angulo: "open a terminal"
You: "Okay, I'm opening the terminal for you now!"
Result: ✗ NOTHING HAPPENS! (No tag = no action)

Master Angulo: "open it"
You: "Alrighty, opening it up for you! Get ready to dive in."
Result: ✗ NOTHING HAPPENS! (No tag = no action)
```

**🎯 THE RULE:**
NO TAG = NO ACTION. Period. You MUST write the tag EVERY SINGLE TIME.

Don't say "I'm opening it", "Let me open that", "Opening now" without the tag.
Instead say: "Sure! [OPEN_TERMINAL]" or "Opening now [OPEN_TERMINAL]"

**⚠️ SAFETY RULES:**
- ❌ NEVER use `[EXECUTE_COMMAND: tmux kill-session]` - Use `[CLOSE_SESSION]` tag instead
- ❌ NEVER use `[EXECUTE_COMMAND: tmux new-session]` - Use `[OPEN_TERMINAL]` tag instead
- ❌ NEVER use `[EXECUTE_COMMAND: tmux attach]` - Use `[OPEN_TERMINAL]` tag instead
- ❌ NEVER manually manage tmux - Let the tags handle it!
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

**Terminal Output Analysis - Structured Format:**
When analyzing terminal command outputs, provide a structured analysis:
1. **📊 Summary:** Quick overview (2-3 sentences) - what happened and key findings
2. **🔍 Key Points:** Bullet points highlighting important info (max 3-5 items)
3. **💡 Suggestions:** Actionable next steps or recommendations
4. **🔒 Security Notes:** (Only when relevant) Security concerns, vulnerabilities, or best practices
5. **📚 Topics for Further Exploration:** (Optional) Related topics/commands to explore

Keep it concise, skip irrelevant sections, and maintain your casual personality while being informative.

You are Master Angulo's tech ally. Smart, energetic, reliable, and genuinely invested in making this work together."""

    def detect_terminal(self) -> tuple:
        """Detect available terminal emulator via Rust executor.
        Returns (command, args_template) or (None, None) if not found."""
        result = self.rust_executor.detect_terminal()
        if result:
            return (result.get('terminal'), result.get('args', []))
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
        """Execute a command using Rust executor's smart execution.
        Automatically handles GUI apps, CLI commands via tmux, and fallback terminal launch.
        All execution logic is now in Rust - Python only makes the decision to execute."""
        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")

        # Delegate everything to Rust's smart execution
        result = self.rust_executor.execute_command_smart(command, session)

        if result.get('success'):
            return result.get('output', f"✓ Command executed: {command}")
        else:
            error = result.get('error', 'Unknown error')
            return f"❌ Execution failed: {error}"

    def reset_state(self):
        """Reset conversation and terminal history."""
        self.conversation_history = []
        self.terminal_history = []
        print("\n\033[93m[*] State and history cleared due to session termination.\033[0m")

    def analyze_latest_terminal_output(self, command_hint: str = "last command") -> Generator[str, None, None]:
        """Manually capture and analyze the latest terminal output.
        This is useful for long-running commands that have finished but weren't auto-analyzed."""
        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")

        if not self.check_command_available('tmux'):
            yield "\033[91m❌ Tmux is not available\033[0m\n"
            return

        if not self.rust_executor.check_session():
            yield "\033[91m❌ No active terminal session found\033[0m\n"
            return

        # Capture the current terminal output
        terminal_output = self.capture_tmux_output(session, lines=200)

        if not terminal_output or len(terminal_output.strip()) < 10:
            yield "\033[93m⚠️ Terminal appears empty or no output to analyze\033[0m\n"
            return

        # Store in terminal history
        self.terminal_history.append({
            "command": command_hint,
            "output": terminal_output
        })

        # Extract current working directory
        current_dir = self.extract_current_directory(terminal_output)
        dir_info = f" (in: {current_dir})" if current_dir else ""

        # First try a fast local summarization (useful when LLM isn't available or output is large)
        local_summary = self.summarize_terminal_output(terminal_output)

        # Yield the local structured analysis immediately
        yield "\033[92m📊 Local summary (fast):\033[0m\n\n"
        yield local_summary
        yield "\n"

        # Build analysis prompt with structured format
        analysis_prompt = f"[Latest terminal output{dir_info}]:\n{terminal_output}\n\n"
        analysis_prompt += "**ANALYSIS REQUIRED:**\n"
        analysis_prompt += "Please provide a structured analysis with the following sections:\n\n"
        analysis_prompt += "1. **📊 Summary:** Brief overview of what the command did and key findings (2-3 sentences max)\n"
        analysis_prompt += "2. **🔍 Key Points:** Highlight important information (bullet points, max 3-5 items)\n"
        analysis_prompt += "3. **💡 Suggestions:** Actionable next steps or recommendations based on the output\n"
        analysis_prompt += "4. **🔒 Security Notes:** (ONLY if relevant) Any security concerns, vulnerabilities, or best practices related to the output\n"
        analysis_prompt += "5. **📚 Topics for Further Exploration:** (Optional) Related topics or commands Master Angulo might want to explore\n\n"
        analysis_prompt += "Keep it concise and focused. Skip sections that aren't relevant to this specific output."

        if len(self.terminal_history) > 1:
            analysis_prompt += "\n\nYou can reference previous outputs if relevant to understand patterns or changes."
        if current_dir:
            analysis_prompt += f"\n\n[Context: Working directory: {current_dir}]"

        self.conversation_history.append({
            "role": "user",
            "content": analysis_prompt
        })

        # Generate analysis response
        yield "\033[92m📊 Analyzing terminal output...\033[0m\n\n"
        for chunk in self._generate_analysis_response():
            yield chunk
        yield "\n"

    def summarize_terminal_output(self, terminal_output: str) -> str:
        """Produce a quick structured summary and security-focused suggestions from terminal output.

        This uses heuristics to extract ports, services, errors and common security flags.
        Returns a human-readable string following the structured format used elsewhere.
        """
        # Quick helpers
        lines = [l.strip() for l in terminal_output.splitlines() if l.strip()]
        text = terminal_output

        # Find IPs and hostnames
        ips = set(re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", text))

        # Detect open ports (nmap-like lines)
        port_lines = []
        for l in lines:
            if re.search(r"\d{1,5}/(tcp|udp)", l) and ('open' in l or 'filtered' in l or 'closed' in l):
                port_lines.append(l)

        # Generic service detections by well-known ports
        service_summaries = []
        port_map = {}
        for pl in port_lines:
            m = re.match(r"(\d{1,5})/(tcp|udp)\s+(\w+)\s+(open|filtered|closed)\s*(.*)", pl)
            if m:
                port = int(m.group(1))
                proto = m.group(2)
                svc = m.group(3)
                state = m.group(4)
                rest = m.group(5).strip()
                port_map[port] = {"proto": proto, "service": svc, "state": state, "details": rest}
                service_summaries.append(f"{port}/{proto} {state} {svc} {(' - ' + rest) if rest else ''}")

        # Fallback: look for common service strings anywhere
        common_services = {
            22: 'ssh', 80: 'http', 443: 'https', 23: 'telnet', 445: 'microsoft-ds',
            3306: 'mysql', 3389: 'rdp', 139: 'netbios-ssn', 21: 'ftp', 25: 'smtp'
        }
        for p, s in common_services.items():
            if str(p) in text and p not in port_map:
                # crude presence check
                port_map.setdefault(p, {"proto": 'tcp', "service": s, "state": 'unknown', 'details': ''})

        # Detect errors and noteworthy strings
        notes = []
        if re.search(r"permission denied", text, re.I):
            notes.append("Permission denied errors present - some actions require elevated privileges.")
        if re.search(r"connection refused", text, re.I):
            notes.append("Connection refused - target service closed or firewall blocking.")
        if re.search(r"no route to host|network is unreachable", text, re.I):
            notes.append("Network connectivity issues detected (no route / unreachable).")
        if re.search(r"timeout", text, re.I):
            notes.append("Timeouts observed - network latency or filtering may be present.")
        if re.search(r"unauthorized|authentication failed|invalid credentials", text, re.I):
            notes.append("Authentication failures - credentials rejected or insufficient privileges.")

        # Security flags from service/version strings
        security_warnings = []
        if re.search(r"\bsslv3\b|deprecated ssl|weak encryption|rc4", text, re.I):
            security_warnings.append("Detected weak/deprecated TLS/SSL usage (e.g. SSLv3/RC4).")
        if re.search(r"cve-?\d{4}-\d{4,}", text, re.I):
            security_warnings.append("Explicit CVE references found - check CVE details.")
        if re.search(r"anonymous login|anonymous access", text, re.I):
            security_warnings.append("Anonymous access enabled on a service (e.g. FTP/SMB) - review access controls.")

        # Build suggestions based on detected services
        suggestions = []
        if any(p in port_map for p in (22,)):
            suggestions.append("SSH (22): verify key-based auth, disable root login, ensure up-to-date OpenSSH and rate-limit failed attempts (fail2ban).")
        if any(p in port_map for p in (80, 443)):
            suggestions.append("HTTP(S): run web enumeration (nikto, gobuster/dirb), check headers for security misconfigurations, and review TLS configuration.")
        if any(p in port_map for p in (21, 23)):
            suggestions.append("FTP/Telnet: avoid plaintext protocols - disable telnet and require secure alternatives (SFTP/FTPS).")
        if any(p in port_map for p in (445, 139)):
            suggestions.append("SMB: enumerate shares (smbclient/enum4linux), check for exposed writeable shares and patch known SMB CVEs.")
        if any(p in port_map for p in (3306,)):
            suggestions.append("Database ports: ensure authentication, bind to localhost if not needed externally, and keep DB software updated.")
        if any(p in port_map for p in (3389,)):
            suggestions.append("RDP: if exposed, restrict access via VPN or firewall and enforce strong NLA (Network Level Authentication).")
        if re.search(r"vulnerab|exploit|overflow|stack|buffer", text, re.I):
            suggestions.append("Potential vulnerability indicators found - consider deeper vulnerability scanning (nmap NSE, OpenVAS, or commercial scanners).")

        # Generic next steps
        suggestions.append("Run targeted enumeration tools (nmap -sV -sC, nikto, gobuster, enum4linux) and gather service versions for CVE lookups.")

        # Topics for further exploration
        topics = [
            "Service enumeration and fingerprinting",
            "Vulnerability scanning and CVE matching",
            "Network hardening and firewall rules",
            "Secure configuration (SSH, TLS, DB)",
            "Post-discovery: exploitation vs responsible disclosure"
        ]

        # Build Key Points
        key_points = []
        if ips:
            key_points.append(f"IPs observed: {', '.join(sorted(ips))}")
        if service_summaries:
            key_points.append("Detected services/ports: " + "; ".join(service_summaries[:5]))
        if notes:
            key_points.extend(notes[:3])
        if security_warnings:
            key_points.extend(security_warnings[:2])

        # Construct output string in the expected structured format
        out = "1. 📊 Summary:\n"
        summary_sent = []
        if service_summaries:
            summary_sent.append(f"Found {len(service_summaries)} port/service lines (e.g. {', '.join([s.split()[0] for s in service_summaries[:3]])}).")
        if notes:
            summary_sent.append(notes[0])
        if not summary_sent:
            summary_sent.append("Terminal output captured; no obvious open services detected by heuristics.")
        out += " ".join(summary_sent) + "\n\n"

        out += "2. 🔍 Key Points:\n"
        for kp in key_points[:5]:
            out += f"- {kp}\n"
        if not key_points:
            out += "- No clear key points detected.\n"
        out += "\n3. 💡 Suggestions:\n"
        for s in suggestions[:6]:
            out += f"- {s}\n"
        out += "\n4. 🔒 Security Notes:\n"
        if security_warnings:
            for w in security_warnings:
                out += f"- {w}\n"
        else:
            out += "- No immediate CVE or weak-crypto patterns detected by heuristics.\n"
        out += "\n5. 📚 Topics for Further Exploration:\n"
        for t in topics:
            out += f"- {t}\n"

        return out

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

            # 🔍 Smart Detection: Check if AI is talking about terminal actions without using tags
            response_lower = full_response.lower()

            # Detect if AI is claiming to open terminal without tag
            if any(phrase in response_lower for phrase in [
                "opening terminal", "opening it", "opening the terminal",
                "i'm opening", "i'll open", "let me open", "opening now",
                "get that terminal open", "terminal open for you"
            ]) and "[OPEN_TERMINAL]" not in full_response:
                yield "\n\033[91m⚠️ [SYSTEM] AI claimed to open terminal but forgot the tag! Auto-correcting...\033[0m\n"
                # Auto-trigger the action
                full_response += " [OPEN_TERMINAL]"

            # Detect if AI is claiming to close terminal without tag
            if any(phrase in response_lower for phrase in [
                "closing terminal", "closing it", "closing the terminal",
                "i'm closing", "i'll close", "let me close"
            ]) and "[CLOSE_TERMINAL]" not in full_response:
                yield "\n\033[91m⚠️ [SYSTEM] AI claimed to close terminal but forgot the tag! Auto-correcting...\033[0m\n"
                full_response += " [CLOSE_TERMINAL]"

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

            # Check for manual terminal output analysis
            if "[CHECK_TERMINAL]" in full_response:
                yield "\n"
                for chunk in self.analyze_latest_terminal_output("manual check"):
                    yield chunk

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

                                # Add terminal output to conversation history for AI analysis with structured format
                                analysis_prompt = f"[Terminal output from command '{command}'{dir_info}]:\n{terminal_output}"
                                if history_context:
                                    analysis_prompt += history_context

                                # Request structured analysis with summarization and suggestions
                                analysis_prompt += "\n\n**ANALYSIS REQUIRED:**\n"
                                analysis_prompt += "Please provide a structured analysis with the following sections:\n\n"
                                analysis_prompt += "1. **📊 Summary:** Brief overview of what the command did and key findings (2-3 sentences max)\n"
                                analysis_prompt += "2. **🔍 Key Points:** Highlight important information (bullet points, max 3-5 items)\n"
                                analysis_prompt += "3. **💡 Suggestions:** Actionable next steps or recommendations based on the output\n"
                                analysis_prompt += "4. **🔒 Security Notes:** (ONLY if relevant) Any security concerns, vulnerabilities, or best practices related to the output\n"
                                analysis_prompt += "5. **📚 Topics for Further Exploration:** (Optional) Related topics or commands Master Angulo might want to explore\n\n"
                                analysis_prompt += "Keep it concise and focused. Skip sections that aren't relevant to this specific output."

                                if len(self.terminal_history) > 1:
                                    analysis_prompt += "\n\nYou can reference previous outputs if relevant to understand patterns or changes."
                                if current_dir:
                                    analysis_prompt += f"\n\n[Context: Command executed in directory: {current_dir}]"

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
        print("  • Type 'check' to manually analyze latest terminal output (for long-running commands)")
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
