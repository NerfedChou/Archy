"""
RustExecutor: Python interface to communicate with Rust executor daemon
Handles all system-level operations via Unix socket IPC
"""

import socket
import json
from typing import Dict, Any, Optional


class RustExecutor:
    """
    Interface to communicate with the Rust executor daemon.
    Handles command execution, terminal management, and tmux operations.
    """
    
    def __init__(self, socket_path: str = "/tmp/archy.sock"):
        self.socket_path = socket_path
    
    def send_command(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send command to Rust executor daemon via Unix socket.
        
        Args:
            action: The action to perform (execute, capture, check_session, etc.)
            data: Dictionary containing action-specific data
            
        Returns:
            Dictionary with response data (success, output, error, exists)
        """
        max_retries = 2  # Retry up to 2 times on connection reset
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

                # Dynamic timeout based on action type
                # For actions that wait for command completion, use max_wait + buffer
                if action in ['execute_and_wait', 'execute_analyzed', 'wait_for_prompt']:
                    max_wait = data.get('max_wait', 300)  # Default 5 minutes
                    # Socket timeout = command max_wait + 30 second buffer for processing
                    socket_timeout = max_wait + 30.0
                else:
                    # Quick actions get 10 second timeout
                    socket_timeout = 10.0

                client.settimeout(socket_timeout)
                client.connect(self.socket_path)
                
                message = json.dumps({"action": action, "data": data})
                client.sendall(message.encode())
                
                # Receive response in chunks to handle large outputs
                response_data = b''
                max_response_size = 10 * 1024 * 1024  # 10MB limit
                while len(response_data) < max_response_size:
                    try:
                        chunk = client.recv(8192)
                        if not chunk:
                            break
                        response_data += chunk
                    except socket.timeout:
                        break  # Stop receiving if timeout is reached

                client.close()

                if not response_data:
                    return {"success": False, "error": "No response from executor (timeout or empty response)"}

                response = response_data.decode('utf-8', errors='replace')
                return json.loads(response)
            except FileNotFoundError:
                return {
                    "success": False,
                    "error": "Rust executor daemon not running. Please start it with: ./start_daemon.sh"
                }
            except ConnectionRefusedError:
                return {
                    "success": False,
                    "error": "Rust executor daemon not running (stale socket). Please start it with: ./start_daemon.sh"
                }
            except ConnectionResetError as e:
                # Connection reset - try again (might be a race condition)
                retry_count += 1
                if retry_count > max_retries:
                    return {"success": False, "error": f"Connection reset by daemon (tried {max_retries} times): {e}"}
                import time
                time.sleep(0.1 * retry_count)  # Brief backoff before retry
                continue
            except socket.timeout:
                return {"success": False, "error": "Socket connection timeout"}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    def execute_in_tmux(self, command: str, session: str = "archy_session") -> Dict[str, Any]:
        """Execute a command in the tmux session."""
        return self.send_command("execute", {"command": command, "session": session})
    
    def capture_output(self, lines: int = 100, session: str = "archy_session") -> str:
        """Capture output from the tmux session."""
        result = self.send_command("capture", {"lines": lines, "session": session})
        return result.get("output", "")
    
    def check_session(self, session: str = "archy_session") -> bool:
        """Check if tmux session exists."""
        result = self.send_command("check_session", {})
        return result.get("exists", False)
    
    def open_terminal(self) -> bool:
        """Open a new terminal window attached to tmux session."""
        result = self.send_command("open_terminal", {})
        return result.get("success", False)
    
    def close_terminal(self) -> bool:
        """Close the terminal window (keeps tmux session alive)."""
        result = self.send_command("close_terminal", {})
        return result.get("success", False)
    
    def close_session(self, session: str = "archy_session") -> bool:
        """Close the tmux session entirely."""
        result = self.send_command("close_session", {"session": session})
        return result.get("success", False)
    
    def is_foot_running(self) -> bool:
        """Check if foot terminal is currently running."""
        result = self.send_command("is_foot_running", {})
        return result.get("exists", False)

    def check_command_available(self, command: str) -> bool:
        """Check if a command is available on the system."""
        result = self.send_command("check_command", {"command": command})
        return result.get("exists", False)

    def get_system_info(self) -> str:
        """Get system information from the Rust executor."""
        result = self.send_command("get_system_info", {})
        return result.get("output", "System info unavailable")

    def find_desktop_entry(self, app_name: str) -> Optional[str]:
        """Find the desktop entry for a given application name."""
        result = self.send_command("find_desktop_entry", {"app_name": app_name})
        if result.get("success") and result.get("exists"):
            return result.get("output")
        return None

    def extract_current_directory(self, terminal_output: str) -> Optional[str]:
        """Extract the current working directory from terminal output."""
        result = self.send_command("extract_directory", {"terminal_output": terminal_output})
        if result.get("success", False):
            return result.get("output")
        return None

    def wait_for_command_completion(self, command: str = "", session: str = "archy_session",
                                    max_wait: int = 600, interval_ms: int = 500) -> tuple[bool, str]:
        """
        Wait for a command to complete by monitoring terminal output.
        Returns (success: bool, output: str)

        Args:
            command: The command that was executed (for verification)
            session: Tmux session name
            max_wait: Maximum wait time in seconds (default 10 minutes)
            interval_ms: Check interval in milliseconds (default 500ms)
        """
        result = self.send_command("wait_for_prompt", {
            "command": command,
            "session": session,
            "max_wait": max_wait,
            "interval_ms": interval_ms
        })
        success = result.get("success", False)
        output = result.get("output", "")
        return (success, output)

    def execute_command_smart(self, command: str, session: str = "archy_session") -> Dict[str, Any]:
        """Execute a command smartly (GUI or CLI)."""
        return self.send_command("execute_smart", {"command": command, "session": session})

    def launch_gui_app(self, desktop_entry: str) -> Dict[str, Any]:
        """Launch a GUI application using its desktop entry."""
        return self.send_command("launch_gui_app", {"desktop_entry": desktop_entry})

    def execute_analyzed(self, command: str, session: str = "archy_session",
                        max_wait: int = 600, interval_ms: int = 500) -> Dict[str, Any]:
        """
        Execute command and return fully analyzed output with:
        - display: Formatted colored output ready to print
        - display_plain: Same output without colors
        - structured: Parsed JSON data
        - findings: List of key insights
        - summary: One-line summary
        - metadata: Stats about the output

        This is the NEW WAY - Rust handles all parsing, formatting, and analysis!
        Python just consumes the structured data.
        """
        return self.send_command("execute_analyzed", {
            "command": command,
            "session": session,
            "max_wait": max_wait,
            "interval_ms": interval_ms
        })

    def capture_analyzed(self, command: str, lines: int, session: str) -> Dict[str, Any]:
        """Capture and analyze terminal output."""
        return self.send_command("capture_analyzed", {
            "command": command,
            "lines": lines,
            "session": session
        })

    def execute_and_wait(self, command: str, session: str = "archy_session",
                        max_wait: int = 300, interval_ms: int = 500) -> Dict[str, Any]:
        """
        Execute command and AUTOMATICALLY wait for it to finish!

        This is the SMART way - no hardcoded sleep times!
        The Rust daemon monitors the terminal and detects when the prompt returns.

        Perfect for commands that take unknown time:
        - nmap scans (can take 30+ seconds)
        - find operations
        - large file operations

        Args:
            command: The command to execute
            session: Tmux session name
            max_wait: Maximum time to wait in seconds (default 5 minutes)
            interval_ms: How often to check for completion (default 500ms)

        Returns:
            DisplayOutput with parsed results when command actually finishes!
        """
        return self.send_command("execute_and_wait", {
            "command": command,
            "session": session,
            "max_wait": max_wait,
            "interval_ms": interval_ms
        })

    def is_process_running(self, process_name: str) -> bool:
        """
        Check if a process is running.
        Useful for verifying GUI apps launched successfully.

        Args:
            process_name: Name of the process to check (e.g., 'firefox', 'discord')

        Returns:
            True if process is running, False otherwise
        """
        import subprocess
        try:
            result = subprocess.run(['pgrep', '-x', process_name],
                                  capture_output=True,
                                  timeout=2)
            return result.returncode == 0
        except:
            return False

    def detect_terminal(self) -> Optional[Dict[str, Any]]:
        """Detect available terminal emulator. Returns dict with 'terminal' and 'args'."""
        result = self.send_command("detect_terminal", {})
        if result.get("success", False) and result.get("output"):
            import json
            try:
                return json.loads(result["output"])
            except:
                pass
        return None

    def launch_fallback_terminal(self, command: str, terminal: str = "foot") -> Dict[str, Any]:
        """Launch command in a new terminal window (fallback method)."""
        return self.send_command("launch_fallback_terminal", {
            "command": command,
            "terminal": terminal
        })

    def batch_execute(self, commands: list[str], explanations: list[str] = None,
                     session: str = "archy_session") -> Dict[str, Any]:
        """
        Execute multiple commands in sequence with AI explanations.

        Args:
            commands: List of commands to execute
            explanations: Optional list of AI explanations (one per command)
            session: Tmux session name

        Returns:
            Dictionary with batch result including all command outputs and explanations
        """
        data = {
            "commands": commands,
            "session": session
        }
        if explanations:
            data["explanations"] = explanations

        return self.send_command("batch_execute", data)

    def get_last_error(self) -> Optional[str]:
        """Get the last error message if any."""
        # This would need to be tracked in the class state
        return None

