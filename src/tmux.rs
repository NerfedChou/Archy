// tmux.rs - Tmux Operations Module
// Centralizes all tmux interactions, eliminates repetition

use std::process::Command;
use crate::config::Config;

/// Execute a tmux command and return output
fn run_tmux(args: &[&str]) -> Result<String, String> {
    let output = Command::new("tmux")
        .args(args)
        .output()
        .map_err(|e| format!("Failed to execute tmux: {}", e))?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

/// Execute a tmux command and return status only
fn run_tmux_status(args: &[&str]) -> bool {
    Command::new("tmux")
        .args(args)
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// Check if a tmux session exists
pub fn has_session(session: &str) -> bool {
    run_tmux_status(&["has-session", "-t", session])
}

/// Send keys to a tmux session (execute command)
pub fn send_keys(session: &str, command: &str) -> Result<(), String> {
    run_tmux(&["send-keys", "-t", session, command, "C-m"])
        .map(|_| ())
}

/// Capture output from tmux pane
pub fn capture_pane(session: &str, lines: i64) -> Result<String, String> {
    run_tmux(&["capture-pane", "-pt", session, "-S", &format!("-{}", lines)])
}

/// Create a new tmux session
pub fn new_session(session: &str) -> Result<(), String> {
    run_tmux(&["new-session", "-d", "-s", session])
        .map(|_| ())
}

/// Kill a tmux session
pub fn kill_session(session: &str) -> Result<(), String> {
    run_tmux(&["kill-session", "-t", session])
        .map(|_| ())
}

/// List all tmux sessions
pub fn list_sessions() -> Result<Vec<String>, String> {
    let output = run_tmux(&["list-sessions", "-F", "#{session_name}"])?;
    Ok(output
        .lines()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect())
}

/// Get current working directory from tmux pane
pub fn get_pane_cwd(session: &str) -> Result<String, String> {
    run_tmux(&["display-message", "-t", session, "-p", "#{pane_current_path}"])
        .map(|s| s.trim().to_string())
}

/// Wait for command completion by monitoring prompt
pub fn wait_for_prompt(
    session: &str,
    max_wait_ms: u64,
    poll_interval_ms: u64,
) -> Result<String, String> {
    use std::thread;
    use std::time::Duration;

    let max_iterations = max_wait_ms / poll_interval_ms;
    let mut previous_output = String::new();
    let mut stable_count = 0;
    const STABILITY_THRESHOLD: u32 = 6; // 3 seconds at 500ms intervals

    for _ in 0..max_iterations {
        thread::sleep(Duration::from_millis(poll_interval_ms));

        let current_output = capture_pane(session, 50)?;

        if current_output == previous_output {
            stable_count += 1;
            if stable_count >= STABILITY_THRESHOLD {
                // Output stable for 3 seconds - command complete
                return Ok(current_output);
            }
        } else {
            stable_count = 0;
            previous_output = current_output;
        }
    }

    // Timeout - return what we have
    Ok(previous_output)
}

/// High-level session management
pub struct Session<'a> {
    pub name: &'a str,
    pub config: &'a Config,
}

impl<'a> Session<'a> {
    pub fn new(name: &'a str, config: &'a Config) -> Self {
        Session { name, config }
    }

    /// Check if this session exists
    pub fn exists(&self) -> bool {
        has_session(self.name)
    }

    /// Ensure session exists (create if needed)
    pub fn ensure_exists(&self) -> Result<(), String> {
        if !self.exists() {
            new_session(self.name)?;
        }
        Ok(())
    }

    /// Execute command in this session
    pub fn execute(&self, command: &str) -> Result<(), String> {
        self.ensure_exists()?;
        send_keys(self.name, command)
    }

    /// Capture output from this session
    pub fn capture(&self, lines: i64) -> Result<String, String> {
        capture_pane(self.name, lines)
    }

    /// Execute command and wait for completion
    pub fn execute_and_wait(&self, command: &str) -> Result<String, String> {
        self.execute(command)?;
        wait_for_prompt(
            self.name,
            self.config.max_wait_seconds * 1000,
            self.config.poll_interval_ms,
        )
    }

    /// Kill this session
    pub fn kill(&self) -> Result<(), String> {
        kill_session(self.name)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_has_session() {
        // This will fail if no tmux sessions exist, which is fine for unit tests
        let result = has_session("nonexistent_session_xyz123");
        assert_eq!(result, false);
    }

    #[test]
    fn test_session_struct() {
        let config = Config::default();
        let session = Session::new("test_session", &config);
        assert_eq!(session.name, "test_session");
    }
}

