#!/usr/bin/env python3
"""
Archy Interactive Chat Mode
Connects to Groq API for LLM inference
With system integration and command execution
"""

import requests
import json
import sys
import subprocess
import os
from typing import Generator

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If dotenv is not available, just continue with environment variables
    pass

class ArchyChat:
    def __init__(self, groq_api_key: str = None):
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY", "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")
        self.groq_host = os.getenv("GROQ_HOST", "https://api.groq.com/openai/v1")
        self.groq_api_url = f"{self.groq_host}/chat/completions"
        self.model = os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")
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
        """Send message to Groq API and stream response"""
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
            "temperature": 0.7,
            "max_tokens": 512
        }

        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                self.groq_api_url,
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
                yield f"\033[91m❌ Error: Groq API error - {response.status_code}: {error_detail}\033[0m"
                return
            
            full_response = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8') if isinstance(line, bytes) else line
                    line = line.strip()
                    
                    if not line or line == "[DONE]":
                        continue
                    
                    if line.startswith('data: '):
                        line = line[6:].strip()
                    
                    if line:
                        try:
                            data = json.loads(line)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                chunk = delta.get("content", "")
                                if chunk:
                                    full_response += chunk
                                    yield chunk
                        except json.JSONDecodeError as e:
                            continue

            if full_response:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": full_response
                })
            
        except requests.exceptions.ConnectionError:
            yield "\033[91m❌ Error: Cannot connect to Groq API\033[0m"
        except requests.exceptions.Timeout:
            yield "\033[91m❌ Error: Groq API request timed out\033[0m"
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
                # Use sys.stdin explicitly to ensure proper input handling
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
                # User pressed Ctrl+D
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
