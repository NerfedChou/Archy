#!/usr/bin/env python3
"""
Complete AI Integration Debug
Shows the FULL flow: User → AI → Commands → Rust → Parsing → AI Analysis
"""

import sys
import os
from pathlib import Path

# Add scripts directory
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

# Load API key
api_file = Path(__file__).parent.parent / '.api'
if api_file.exists():
    with open(api_file, 'r') as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY='):
                os.environ['GEMINI_API_KEY'] = line.strip().split('=', 1)[1]

from archy_chat import ArchyChat
import json
import time


class DebugArchyChat(ArchyChat):
    """
    Extended version of ArchyChat with detailed logging
    """

    def __init__(self):
        print("🔧 Initializing ArchyChat...")
        super().__init__()
        print(f"✓ Connected to Gemini API")
        print(f"✓ Connected to Rust executor")
        print(f"✓ Model: {self.gemini_model}")
        print()

    def send_message_debug(self, user_input: str):
        """
        Debug version that shows every step
        """
        print("╔" + "="*78 + "╗")
        print("║" + " USER INPUT ".center(78) + "║")
        print("╚" + "="*78 + "╝")
        print(f"📝 User: {user_input}")
        print()

        # Step 1: Preprocess
        print("─" * 80)
        print("🔄 STEP 1: Preprocessing user input...")
        processed = self._preprocess_user_input(user_input)
        if processed != user_input:
            print(f"✓ Input preprocessed:")
            print(f"  Before: {user_input}")
            print(f"  After: {processed}")
        else:
            print(f"✓ No preprocessing needed")
        print()

        # Step 2: Send to AI
        print("─" * 80)
        print("🤖 STEP 2: Sending to Gemini API...")
        print(f"  API URL: {self.gemini_api_url}")
        print(f"  Model: {self.gemini_model}")
        print(f"  Conversation history: {len(self.conversation_history)} messages")

        # Add to history
        self.conversation_history.append({"role": "user", "content": processed})

        # Build context
        context = f"\n\n[System Context: {self.rust_executor.get_system_info()}]"
        messages = [{"role": "system", "content": self.system_prompt + context}] + self.conversation_history

        payload = {
            "model": self.gemini_model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 4096
        }

        headers = {
            "Authorization": f"Bearer {self.gemini_api_key[:10]}...",
            "Content-Type": "application/json"
        }

        print(f"  Request size: {len(json.dumps(payload))} bytes")
        print()

        # Make request
        import requests
        headers["Authorization"] = f"Bearer {self.gemini_api_key}"
        response = requests.post(self.gemini_api_url, json=payload, headers=headers, stream=True, timeout=60)

        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            return

        # Step 3: Stream response
        print("─" * 80)
        print("📥 STEP 3: Receiving AI response...")
        print("╔" + "="*78 + "╗")
        print("║" + " AI RESPONSE ".center(78) + "║")
        print("╚" + "="*78 + "╝")
        print("Archy: ", end="", flush=True)

        full_response = ""
        chunk_count = 0
        for chunk in self._stream_and_collect_response(response):
            full_response += chunk
            chunk_count += 1
            print(chunk, end="", flush=True)

        print()
        print()
        print(f"✓ Received {chunk_count} chunks, total {len(full_response)} characters")
        self.conversation_history.append({"role": "assistant", "content": full_response})
        print()

        # Step 4: Extract commands
        print("─" * 80)
        print("🔍 STEP 4: Extracting command tags...")

        import re
        pattern = re.compile(r'\[EXECUTE_COMMAND:\s*(.+?)\]')
        commands = pattern.findall(full_response)

        if commands:
            print(f"✓ Found {len(commands)} command(s):")
            for idx, cmd in enumerate(commands, 1):
                print(f"  {idx}. {cmd}")
        else:
            print("  No commands found in response")
            return
        print()

        # Step 5: Execute commands
        print("─" * 80)
        print("⚡ STEP 5: Executing commands via Rust...")

        session = os.getenv("ARCHY_TMUX_SESSION", "archy_session")

        for idx, command in enumerate(commands, 1):
            print(f"\n┌─ Command {idx}/{len(commands)}: {command}")
            print(f"│")

            # Send to Rust
            print(f"│ 🔵 Python → Rust: execute_and_wait()")
            start_time = time.time()

            result = self.rust_executor.execute_and_wait(
                command=command,
                session=session,
                max_wait=300,
                interval_ms=500
            )

            elapsed = time.time() - start_time
            print(f"│ ⏱️  Execution took: {elapsed:.2f}s")
            print(f"│")

            if not result.get('success'):
                print(f"│ ❌ Failed: {result.get('error')}")
                continue

            # Show what Rust did
            print(f"│ 🦀 Rust performed:")
            print(f"│   1. Sent command to tmux")
            print(f"│   2. Waited for prompt return")
            print(f"│   3. Captured output")
            print(f"│   4. Parsed output (parser.rs)")
            print(f"│   5. Formatted output (formatter.rs)")
            print(f"│   6. Created DisplayOutput (output.rs)")
            print(f"│")

            # Show structured data
            if result.get('structured'):
                print(f"│ 📊 Structured Data (parsed by Rust):")
                structured = result['structured']
                if isinstance(structured, dict):
                    for key, value in list(structured.items())[:3]:  # Show first 3 keys
                        if isinstance(value, list):
                            print(f"│   • {key}: {len(value)} items")
                        else:
                            val_str = str(value)
                            if len(val_str) > 40:
                                val_str = val_str[:40] + "..."
                            print(f"│   • {key}: {val_str}")

            # Show findings
            if result.get('findings'):
                print(f"│ 💡 Key Findings (detected by Rust):")
                for finding in result['findings'][:2]:  # Show first 2
                    print(f"│   • {finding.get('message', '')[:60]}...")

            # Show summary
            if result.get('summary'):
                print(f"│ ✓ Summary: {result['summary']}")

            print(f"│")
            print(f"│ 🎨 Formatted Output:")
            print(f"└─")

            # Display the formatted output
            if result.get('display'):
                for line in result['display'].split('\n')[:20]:  # Show first 20 lines
                    print(f"  {line}")

            print()

        print("─" * 80)
        print("✅ ALL STEPS COMPLETE!")
        print()

        # Summary
        print("╔" + "="*78 + "╗")
        print("║" + " FLOW SUMMARY ".center(78) + "║")
        print("╚" + "="*78 + "╝")
        print()
        print("1. 📝 User Input → Python")
        print("2. 🤖 Python → Gemini API (AI generates response)")
        print("3. 📥 Gemini API → Python (response with [EXECUTE_COMMAND] tags)")
        print("4. 🔍 Python extracts commands from tags")
        print("5. 🔵 Python → Rust (via Unix socket /tmp/archy.sock)")
        print("6. 🦀 Rust executes, parses, and formats")
        print("7. 🔴 Rust → Python (returns DisplayOutput JSON)")
        print("8. 📺 Python displays formatted output to user")
        print("9. 🤖 (Optional) Python sends structured data back to AI for analysis")
        print()


def main():
    """Run comprehensive debug"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    COMPLETE AI → RUST INTEGRATION DEBUG                     ║
║            Traces the entire flow from user input to final output           ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    try:
        # Create debug chat
        chat = DebugArchyChat()

        # Test 1: Simple command
        print("\n" + "="*80)
        print(" TEST 1: Simple Command ".center(80))
        print("="*80 + "\n")
        chat.send_message_debug("get my IP address")

        input("\n\nPress Enter to run Test 2...")

        # Test 2: Multiple commands
        print("\n" + "="*80)
        print(" TEST 2: Multiple Commands ".center(80))
        print("="*80 + "\n")
        chat.send_message_debug("list the files in /tmp and show me the current date")

    except KeyboardInterrupt:
        print("\n\n⚠️  Debug interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

