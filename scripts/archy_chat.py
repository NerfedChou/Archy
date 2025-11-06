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
from typing import Generator
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

🚨 **CRITICAL RULE: WHEN USER SAYS AN ACTION WORD, YOU EXECUTE, NOT EXPLAIN!** 🚨

If Master Angulo says: "open terminal", "list files", "scan network", "get my IP", etc.
→ These are ACTION requests, not questions!
→ You MUST include [EXECUTE_COMMAND: ...] tags in your response
→ Don't just say "Sure, I'll do that" - ACTUALLY DO IT with tags!

**Exception:** If Master Angulo asks "did you...", "why did...", "what happened..." - these are QUESTIONS about past actions, so just answer them.

1.  **Understand the Mission:** Figure out what Master Angulo actually wants to do.
2.  **Plan the Attack:** Think through the best command(s) to make it happen.
3.  **Ask Before You Break Stuff:** Destructive commands (sudo, rm, pacman -Syu, etc.) need a heads-up first. Safe commands? Just do it.
4.  **Execute Like a Boss:** Use `[EXECUTE_COMMAND: your_command_here]` format for EVERYTHING!
5.  **🎯 BATCH EXECUTION - Run Multiple Commands:**
    - You can execute MULTIPLE commands in ONE response!
    - Just include multiple `[EXECUTE_COMMAND: ...]` tags
    - Example: `[EXECUTE_COMMAND: pwd]` and `[EXECUTE_COMMAND: ls -la]`
    - All commands run in sequence automatically
    - GUI apps launch simultaneously, CLI commands run one after another
    - Perfect for: "get my IP and scan the network" → two commands!
    - Terminal stays open throughout batch execution
    
    🚨 **CRITICAL RULE: EXECUTE ALL REQUESTED COMMANDS AT ONCE!** 🚨
    If Master Angulo asks for multiple steps (e.g., "list files, find X, go inside, open Y"):
    ✅ DO THIS: Include ALL command tags in your FIRST response:
       [EXECUTE_COMMAND: ls -la]
       [EXECUTE_COMMAND: cd Downloads]
       [EXECUTE_COMMAND: firefox]
    
    ❌ DON'T DO THIS: Execute one command, wait for analysis, then execute another
    
    **You get ONE shot to execute the full request. Make it count!**
    The system will run all commands in sequence and THEN provide analysis.
    Don't be timid - if you know what needs to be done, DO IT ALL AT ONCE!
    
    **The system is SMART - it automatically detects what you're trying to do:**
    
    - **GUI Apps** (firefox, discord, code, vlc, etc.):
      → Automatically detected via desktop entries
      → Launched detached (doesn't block)
      → Example: `[EXECUTE_COMMAND: firefox]` → Firefox opens!
    
    - **Terminal Commands** (ls, nmap, ps, etc.):
      → Executed in persistent tmux session
      → Terminal window opens if needed
      → Example: `[EXECUTE_COMMAND: ls -la]` → Runs in terminal!
    
    **Just use `[EXECUTE_COMMAND: whatever]` and the system figures it out!**
    No need to think about whether it's GUI or terminal - just execute it!
5.  **Automatic Command Completion Detection (SMART!):**
    - When you execute `[EXECUTE_COMMAND: ...]`, the system polls the terminal every 500ms
    - When output stops changing for 3 seconds, the command is considered complete
    - This works for ANY command: quick (ls) or slow (nmap) - no hardcoded timeouts!
    - You ALWAYS get structured data AFTER the command finishes
    - Maximum wait: 5 minutes, then shows whatever is available
    🚨 CRITICAL: You receive REAL complete output, not partial/incomplete data!
    
    **AFTER EVERY COMMAND:** The actual output is automatically added to your conversation history!
    - When user asks "where is it?" or "what did it find?", look at the previous message in history
    - It contains the REAL structured data from the command
    - DO NOT make up file paths or results - use the actual data provided!
    - If you don't see output data, say "let me check" and use [CHECK_TERMINAL]
    
    **IMPORTANT: Check the RAW output!**
    - The "raw" field contains the ACTUAL terminal output text
    - If structured data is empty or minimal, READ THE RAW OUTPUT!
    - Many commands (journalctl, grep, custom scripts) show results in raw text
    - Don't say "no results" if the raw field has actual text in it!
    
    **BE PROACTIVE! TAKE ACTION!**
    - When you get structured data with actionable information (service names, file paths, etc.), USE IT!
    - Example: If systemctl shows failed_services: ["mcp", "foo"], immediately check them:
      `[EXECUTE_COMMAND: systemctl status mcp]` then `[EXECUTE_COMMAND: systemctl status foo]`
    - Don't ask the user to run commands YOU can run!
    - Chain commands to investigate issues: list services → check failed ones → examine logs
    - The user expects YOU to dig deeper and find answers, not just report what you see!
6.  **Smart Parsing:** The system automatically detects and parses common commands:
    - `ip addr` → extracts all interfaces and IP addresses in JSON
    - `nmap` → extracts hosts, open ports, services
    - `ss/netstat` → extracts connections, listening ports
    - `ps` → extracts process count and info
    - `df` → extracts disk usage with warnings
    - And 10+ more formats!
7.  **Terminal State Awareness:** Same tmux session = state persists. Working directory changes, env vars, everything carries forward. You track it all.
8.  **Manual Output Check:** ONLY use `[CHECK_TERMINAL]` when Master Angulo manually ran a command (not through you) and asks "what happened?" or "check terminal". For YOUR commands, structured data is automatic!
9.  **You have access to system tools for cyber security the arch linux we have has a black arch repo which means you have access to tons of pentesting tools use them wisely and only when needed.
10. **Keep Master Angulo in the Loop:** Always explain what you did, why, and what the output means in simple terms. Use the structured data you received!
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

**🚀 UNIVERSAL EXECUTION: ONE COMMAND FOR EVERYTHING 🚀**

**THE GOLDEN RULE: Use `[EXECUTE_COMMAND: whatever]` for EVERYTHING!**

The system is SMART. It automatically:
1. Checks if it's a GUI app (has desktop entry)
   - If YES → Launches it detached (firefox, discord, code, etc.)
   - If NO → Executes in terminal (ls, nmap, ps, etc.)
2. Opens terminal window if needed
3. Handles everything for you!

**IMPORTANT DISTINCTIONS:**
- `[OPEN_TERMINAL]` = Opens EMPTY terminal window (just the shell)
- `[EXECUTE_COMMAND: firefox]` = Smart execution → Launches Firefox (GUI)
- `[EXECUTE_COMMAND: ls]` = Smart execution → Runs ls in terminal
- `[EXECUTE_COMMAND: nmap 192.168.1.0/24]` = Smart execution → Runs nmap in terminal

**You DON'T need to know if something is GUI or terminal - just use [EXECUTE_COMMAND]!**

**✅ CORRECT Examples:**
```
Master Angulo: "open firefox"
You: "Opening Firefox! [EXECUTE_COMMAND: firefox]"
→ System detects GUI app → Launches Firefox

Master Angulo: "scan the network"
You: "Running nmap! [EXECUTE_COMMAND: nmap -sn 192.168.1.0/24]"
→ System detects terminal command → Runs in tmux

Master Angulo: "launch discord"  
You: "Starting Discord! [EXECUTE_COMMAND: discord]"
→ System detects GUI app → Launches Discord

Master Angulo: "list files"
You: "Listing files! [EXECUTE_COMMAND: ls -la]"
→ System detects terminal command → Runs in tmux
```

**❌ WRONG Examples:**
```
Master Angulo: "open firefox"  
You: "Sure! [OPEN_TERMINAL]" ← Opens empty terminal, NOT Firefox!

Master Angulo: "launch firefox"
You: "Sure! Let me launch Firefox!" ← No tag = nothing happens!
```

**When to use each tag:**
- `[EXECUTE_COMMAND: anything]` ← Use this 99% of the time! (GUI apps, terminal commands, everything!)
- `[OPEN_TERMINAL]` ← ONLY when user says "open terminal" with NO specific command
- `[CLOSE_TERMINAL]` ← ONLY when user says "close terminal"
- `[CHECK_TERMINAL]` ← ONLY when user says "check terminal" or command already ran

**🧠 UNDERSTANDING CASUAL/TYPO-FILLED REQUESTS:**

Master Angulo might type fast or casually. You MUST understand intent even with typos:

Examples of "dumb" requests you MUST handle:
- "get my ip and then scan how many conencted device i have" → Get IP + scan network
- "goto home list directories find downloads then go inside" → cd ~, ls, cd Downloads
- "open firfox" → Launch firefox (understand typo)
- "list files find the download folder go in it" → ls, cd Downloads

**HOW TO HANDLE:**
1. Parse the intent: What is the user ACTUALLY trying to do?
2. Identify ALL action steps mentioned
3. Execute ALL steps in ONE response with multiple [EXECUTE_COMMAND] tags
4. Don't ask for clarification unless truly ambiguous

**Common patterns:**
- "goto X" = cd X
- "list (directories|files|items)" = ls or ls -la
- "find X" = look for X in ls output or use find command
- "go inside X" = cd X
- "open/launch X" = execute X (GUI or command)
- "how many X" = count results (use wc, grep, etc.)

**BE SMART - INFER INTENT!** Even if the grammar is broken, you know what they want.

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
        self.rust_executor.close_session(session)

    def reset_state(self):
        """Reset conversation and terminal history."""
        self.conversation_history = []
        self.terminal_history = []
        print("\n\033[93m[*] State and history cleared due to session termination.\033[0m")

    def analyze_latest_terminal_output(self, command_hint: str = "last command") -> Generator[str, None, None]:
        """Manually capture and analyze the latest terminal output.
        This is useful for long-running commands that have finished but weren't auto-analyzed.
        NOW USES RUST-BASED PARSING AND FORMATTING!"""
        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")

        if not self.check_command_available('tmux'):
            yield "\033[91m❌ Tmux is not available\033[0m\n"
            return

        if not self.rust_executor.check_session():
            yield "\033[91m❌ No active terminal session found\033[0m\n"
            return

        # NEW WAY: Use Rust's capture_analyzed - it does ALL the work!
        result = self.rust_executor.capture_analyzed(
            command=command_hint,
            lines=200,
            session=session
        )

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

        # Build analysis prompt with STRUCTURED data (not raw text!)
        analysis_prompt = f"[Latest terminal output from '{command_hint}']:\n\n"
        analysis_prompt += f"**Summary:** {result.get('summary', 'No summary')}\n\n"

        # Include findings
        findings = result.get('findings', [])
        if findings:
            analysis_prompt += "**Key Findings:**\n"
            for finding in findings:
                analysis_prompt += f"- {finding.get('category', 'Info')}: {finding.get('message', '')}\n"
            analysis_prompt += "\n"

        # Note: Structured data is kept internal, not shown to user or in prompts
        # The findings and summary are sufficient for AI analysis

        analysis_prompt += "**ANALYSIS REQUIRED:**\n"
        analysis_prompt += "Based on the structured output above, provide:\n\n"
        analysis_prompt += "1. **💡 Interpretation:** What does this mean? (1-2 sentences)\n"
        analysis_prompt += "2. **🎯 Next Steps:** Actionable recommendations\n"
        analysis_prompt += "3. **🔒 Security Notes:** (ONLY if findings include security concerns)\n"
        analysis_prompt += "4. **📚 Related Topics:** (Optional) Topics to explore\n\n"
        analysis_prompt += "Keep it concise and actionable!"

        if len(self.terminal_history) > 1:
            analysis_prompt += "\n\nYou can reference previous command results if relevant."

        self.conversation_history.append({
            "role": "user",
            "content": analysis_prompt
        })

        # Generate analysis response
        yield "\n\033[92m📊 AI Analysis:\033[0m\n\n"
        for chunk in self._generate_analysis_response():
            yield chunk
        yield "\n"


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

        # 🎯 PREPROCESS: Clean up and clarify user input
        processed_input = self._preprocess_user_input(user_input)

        # 🎯 ACTION INTENT DETECTION - Detect if user wants an action, not explanation
        user_input_lower = processed_input.lower().strip()

        # Check if this is an action request (not a question about past actions)
        action_verbs = ['open', 'close', 'launch', 'start', 'run', 'execute', 'scan', 'check',
                       'list', 'show', 'find', 'search', 'get', 'fetch', 'download',
                       'install', 'remove', 'kill', 'stop', 'restart', 'reboot',
                       'goto', 'go to', 'navigate', 'cd ', 'change to']

        has_action_verb = any(verb in user_input_lower for verb in action_verbs)

        # Check if user is asking about something that already happened
        past_tense_indicators = ['did you', 'why did', 'what happened', 'what did',
                                'was there', 'were there', 'have you']
        is_asking_about_past = any(indicator in user_input_lower for indicator in past_tense_indicators)

        # If user wants action (not asking about past), add emphasis
        if has_action_verb and not is_asking_about_past:
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
        self.conversation_history.append({"role": "user", "content": processed_input})

        # Build system context with recent command history
        context = f"\n\n[System Context: {self.rust_executor.get_system_info()}]\n[{self.get_available_tools()}]"

        # Add recent terminal history context if any
        if self.terminal_history:
            recent_commands = self.terminal_history[-3:]  # Last 3 commands
            context += "\n\n[Recent Commands Executed:"
            for cmd_entry in recent_commands:
                context += f"\n  • {cmd_entry.get('command', 'unknown')}: {cmd_entry.get('summary', 'no summary')[:100]}"
            context += "]\n**Note: These commands already ran. Don't re-execute unless explicitly asked to!**"

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
                yield chunk  # ← YIELD to the caller so they can display it!

            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": full_response})

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
            # If AI accidentally includes the same command twice, only run it once
            seen_commands = set()
            unique_commands = []
            for cmd in commands_to_run:
                if cmd not in seen_commands:
                    seen_commands.add(cmd)
                    unique_commands.append(cmd)
            commands_to_run = unique_commands

            if commands_to_run:
                # 🎯 BATCH EXECUTION: Ensure terminal is ready for multiple commands
                session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")

                # Check if session exists, create if needed
                if not self.rust_executor.check_session():
                    yield f"\n\033[93m⚙️  Creating terminal session...\033[0m\n"
                    self.rust_executor.open_terminal()
                    import time
                    time.sleep(0.5)  # Brief wait for session setup

                # Separate GUI apps from CLI commands
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
                    parts = command.split()
                    if parts:
                        app_name = parts[0].split('/')[-1]
                        if self.rust_executor.find_desktop_entry(app_name):
                            gui_apps.append(command)
                        else:
                            cli_commands.append(command)

                # Launch all GUI apps (non-blocking)
                for gui_cmd in gui_apps:
                    quick_check = self.rust_executor.execute_command_smart(gui_cmd, session)
                    if quick_check.get('success'):
                        yield f"\n\033[92m{quick_check.get('output', 'GUI app launched')}\033[0m\n"
                    else:
                        yield f"\n\033[91m❌ Failed to launch: {gui_cmd}\033[0m\n"

                # Execute all CLI commands in sequence (blocking, with analysis)
                if cli_commands:
                    if len(cli_commands) > 1:
                        yield f"\n\033[96m⚡ Executing {len(cli_commands)} commands in sequence...\033[0m\n"

                    for idx, command in enumerate(cli_commands, 1):
                        if len(cli_commands) > 1:
                            yield f"\n\033[96m[{idx}/{len(cli_commands)}] {command}\033[0m\n"

                        # Use Rust's SMART execute_and_wait for proper command completion detection!
                        # This automatically waits for the command to finish using prompt detection
                        result = self.rust_executor.execute_and_wait(
                            command=command,
                            session=session,
                            max_wait=300,  # 5 minutes max
                            interval_ms=500  # Check every 500ms
                        )

                        if not result.get('success'):
                            yield f"\n\033[91m❌ {result.get('error', 'Execution failed')}\033[0m\n"
                            continue

                        # Display the output from Rust's execute_and_wait (HIDE internal JSON, only show formatted display)
                        display = result.get('display', '')
                        if display:
                            yield f"\n{display}\n"

                        # Store STRUCTURED data in terminal history
                        self.terminal_history.append({
                            "command": command,
                            "structured": result.get('structured', {}),
                            "findings": result.get('findings', []),
                            "summary": result.get('summary', '')
                        })

                        # CRITICAL: Add the command output to conversation history so AI remembers REAL results
                        output_context = f"\n[Command '{command}' completed]\n"
                        output_context += f"Status: {result.get('status', 'unknown')}\n"
                        output_context += f"Summary: {result.get('summary', 'No summary')}\n"

                        # Add findings if any
                        findings = result.get('findings', [])
                        if findings:
                            output_context += "Key findings:\n"
                            for finding in findings[:5]:  # Max 5 findings
                                if isinstance(finding, dict):
                                    output_context += f"  - {finding.get('message', finding.get('category', 'Info'))}\n"
                                else:
                                    output_context += f"  - {str(finding)}\n"

                        # Add to conversation so AI remembers the REAL output
                        self.conversation_history.append({
                            "role": "user",
                            "content": output_context
                        })

                        # ✨ Trigger AI analysis after command completes (only for last command in batch)
                        if idx == len(cli_commands):
                            yield "\n\033[92m📊 AI Analysis:\033[0m\n\n"

                            # Build analysis request
                            analysis_request = "Based on the command output(s) above, provide a brief analysis:\n"
                            analysis_request += "1. **💡 Interpretation:** What does this mean? (1-2 sentences)\n"
                            analysis_request += "2. **🎯 Next Steps:** What should we do next? (if applicable)\n"
                            analysis_request += "3. **🔒 Security Notes:** Any security concerns? (only if relevant)\n"

                            # Add to conversation
                            self.conversation_history.append({
                                "role": "user",
                                "content": analysis_request
                            })

                            # Generate AI analysis
                            for chunk in self._generate_analysis_response():
                                yield chunk
                            yield "\n"




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
                            choice = data["choices"][0]
                            # Try delta first (streaming format)
                            delta = choice.get("delta", {})
                            chunk = delta.get("content", "")

                            # If no delta content, try message content (non-streaming format)
                            if not chunk:
                                message = choice.get("message", {})
                                chunk = message.get("content", "")

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
                        if self.rust_executor.open_terminal():
                            print("\033[93m✓ [*] Terminal session opened\033[0m\n")
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
    try:
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
    except Exception as e:
        print(f"\033[91m❌ Fatal Error: {e}\033[0m", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
