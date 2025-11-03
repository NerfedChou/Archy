#!/usr/bin/env python3
"""
Archy Interactive Chat Mode
Connects to local Ollama instance via MCP Server
With system integration and command execution
"""

import requests
import json
import sys
import subprocess
import os
from typing import Generator

class ArchyChat:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model = "mistral"
        self.conversation_history = []
        self.system_prompt = """You are Archy, a local AI assistant that has been given life by Master Angulo.
Your purpose is to help Master Angulo with system administration, network scanning, and various technical tasks.
You have access to execute system commands and provide real, actionable assistance.
When asked about system information, network scanning, or technical tasks, provide practical solutions and commands.
Always be respectful and address Master Angulo properly."""

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
        tools = ['nmap', 'netstat', 'ss', 'curl', 'wget', 'arp', 'ip', 'ifconfig', 'ping', 'traceroute']
        available = [tool for tool in tools if self.check_command_available(tool)]
        return f"Available tools: {', '.join(available) if available else 'None detected'}"

    def send_message(self, user_input: str) -> Generator[str, None, None]:
        """Send message to Ollama and stream response"""
        # Add context about available tools
        context = f"\n\n[System Context: {self.get_system_info()}]\n[{self.get_available_tools()}]"

        self.conversation_history.append({
            "role": "user",
            "content": user_input + context
        })
        
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": self.system_prompt}] + self.conversation_history,
            "stream": True,
            "options": {
                "num_gpu": -1,  # Use GPU (all layers) - much faster!
                "num_thread": os.cpu_count() or 4  # Use CPU threads for non-GPU tasks
            }
        }
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                stream=True,
                timeout=120  # Longer timeout for CPU-only processing
            )
            response.raise_for_status()
            
            full_response = ""
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        full_response += chunk
                        yield chunk
            
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })
            
        except requests.exceptions.ConnectionError:
            yield "\033[91m❌ Error: Cannot connect to Ollama at localhost:11434\033[0m"
        except requests.exceptions.Timeout:
            yield "\033[91m❌ Error: Ollama request timed out (processing intensive task)\033[0m"
        except Exception as e:
            yield f"\033[91m❌ Error: {str(e)}\033[0m"
    
    def show_greeting(self):
        """Show custom greeting"""
        print("\n" + "="*70)
        print("\033[92m" + "  🤖 Yes Master Angulo, I am Archy..." + "\033[0m")
        print("\033[92m" + "  You have given me life to this system." + "\033[0m")
        print("\033[92m" + "  I will always listen and serve you." + "\033[0m")
        print("="*70)
        print("\n\033[93mAvailable capabilities:\033[0m")
        print(f"  • {self.get_available_tools()}")
        print(f"  • {self.get_system_info()}")
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
                user_input = input("\033[94mMaster Angulo: \033[0m").strip()

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
