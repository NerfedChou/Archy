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
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(self.socket_path)
            
            message = json.dumps({"action": action, "data": data})
            client.sendall(message.encode())
            
            response = client.recv(4096).decode()
            client.close()
            
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
        """Get system information (uname -a)."""
        result = self.send_command("get_system_info", {})
        return result.get("output", "System info unavailable")

    def find_desktop_entry(self, app_name: str) -> Optional[str]:
        """Find a desktop entry file for an application."""
        result = self.send_command("find_desktop_entry", {"app_name": app_name})
        if result.get("exists", False):
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
        """
        Smart command execution - automatically handles:
        - GUI apps (via desktop entries)
        - CLI commands (via tmux)
        - Fallback to new terminal window

        This is the recommended way to execute commands as it handles all cases.
        """
        return self.send_command("execute_smart", {
            "command": command,
            "session": session
        })

    def launch_gui_app(self, desktop_entry: str) -> Dict[str, Any]:
        """Launch a GUI application using its desktop entry."""
        return self.send_command("launch_gui_app", {"desktop_entry": desktop_entry})

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

    def get_last_error(self) -> Optional[str]:
        """Get the last error message if any."""
        # This would need to be tracked in the class state
        return None

