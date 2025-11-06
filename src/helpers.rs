// helpers.rs - Reusable Helper Functions
// Eliminates code duplication throughout the codebase

use serde::{Serialize};
use serde_json::Value;
use std::os::unix::net::UnixStream;
use std::io::Write;

// ...existing code...

/// Security helpers - Input validation and output sanitization
pub mod security {
    use super::*;

    /// Safely serialize and send JSON response, prevents unwrap() panics (FIX #1)
    pub fn safe_json_response(response: &Response, stream: &mut UnixStream) -> std::io::Result<()> {
        match serde_json::to_string(response) {
            Ok(json) => {
                stream.write_all(json.as_bytes())?;
                stream.flush()?;
            }
            Err(e) => {
                eprintln!("❌ JSON serialization failed: {}", e);
                let fallback = r#"{"success":false,"error":"Internal serialization error"}"#;
                let _ = stream.write_all(fallback.as_bytes());
                let _ = stream.flush();
            }
        }
        let _ = stream.shutdown(std::net::Shutdown::Both);
        Ok(())
    }

    /// Escape special characters in pgrep patterns to prevent regex injection (FIX #3)
    pub fn escape_pgrep_pattern(s: &str) -> String {
        s.replace('\\', "\\\\")
         .replace('.', "\\.")
         .replace('*', "\\*")
         .replace('+', "\\+")
         .replace('?', "\\?")
         .replace('[', "\\[")
         .replace(']', "\\]")
         .replace('(', "\\(")
         .replace(')', "\\)")
         .replace('{', "\\{")
         .replace('}', "\\}")
         .replace('|', "\\|")
         .replace('^', "\\^")
         .replace('$', "\\$")
    }

    /// Validate that a path is safe to execute (prevents command injection) (FIX #6)
    pub fn is_safe_executable_path(path: &str) -> bool {
        // Allowed prefixes for executables
        let allowed_prefixes = ["/usr/", "/bin/", "/usr/local/bin/", "/opt/", "/snap/bin/"];
        let is_allowed_prefix = allowed_prefixes.iter().any(|prefix| path.starts_with(prefix));

        if !is_allowed_prefix {
            return false;
        }

        // Verify file exists and is executable
        if let Ok(metadata) = std::fs::metadata(path) {
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                return metadata.permissions().mode() & 0o111 != 0;
            }
            #[cfg(not(unix))]
            return true;
        }

        false
    }

    /// Validate command for dangerous patterns
    pub fn validate_command(command: &str) -> Result<(), String> {
        // Check for null bytes (common injection vector)
        if command.contains('\0') {
            return Err("Invalid command: contains null byte".to_string());
        }

        // Limit command length to prevent buffer overflow
        if command.len() > 8192 {
            return Err("Command too long (max 8192 characters)".to_string());
        }

        // Blacklist extremely dangerous patterns
        let dangerous_patterns = [
            "rm -rf /",
            "rm -rf /*",
            "> /dev/sda",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.",
            ":(){ :|:& };:",  // Fork bomb
        ];

        let command_lower = command.to_lowercase();
        for pattern in &dangerous_patterns {
            if command_lower.contains(pattern) {
                return Err(format!("Blocked dangerous command pattern: {}", pattern));
            }
        }

        Ok(())
    }

    /// Validate desktop entry name to prevent directory traversal
    pub fn validate_desktop_entry(entry: &str) -> Result<(), String> {
        if entry.contains('/') || entry.contains("..") || entry.contains('\0') {
            return Err("Invalid desktop_entry: contains illegal characters".to_string());
        }

        if entry.len() > 255 {
            return Err("Invalid desktop_entry: too long".to_string());
        }

        Ok(())
    }
}

/// Standard Response structure
#[derive(Serialize)]
pub struct Response {
    pub success: bool,
    pub output: Option<String>,
    pub error: Option<String>,
    pub exists: Option<bool>,
}

/// Response builders - DRY principle
pub mod response {
    use super::*;

    /// Create a successful response with output
    pub fn success(output: String) -> Response {
        Response {
            success: true,
            output: Some(output),
            error: None,
            exists: None,
        }
    }

    /// Create a successful response without output
    pub fn success_empty() -> Response {
        Response {
            success: true,
            output: None,
            error: None,
            exists: None,
        }
    }

    /// Create an error response
    pub fn error(message: String) -> Response {
        Response {
            success: false,
            output: None,
            error: Some(message),
            exists: None,
        }
    }

    /// Create an exists response (for boolean checks)
    pub fn exists(exists: bool) -> Response {
        Response {
            success: exists,
            output: None,
            error: None,
            exists: Some(exists),
        }
    }

    /// Create response from Result
    pub fn from_result(result: Result<String, String>) -> Response {
        match result {
            Ok(output) => success(output),
            Err(err_msg) => error(err_msg),
        }
    }
}

/// Parameter extraction helpers
pub mod params {
    use super::*;

    /// Extract required string parameter
    pub fn extract_string(data: &Value, key: &str) -> Result<String, String> {
        data.get(key)
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .ok_or_else(|| format!("Missing required parameter: {}", key))
    }

    /// Extract optional string parameter
    pub fn extract_string_opt(data: &Value, key: &str) -> Option<String> {
        data.get(key)
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
    }

    /// Extract integer parameter with default
    pub fn extract_i64(data: &Value, key: &str, default: i64) -> i64 {
        data.get(key)
            .and_then(|v| v.as_i64())
            .unwrap_or(default)
    }

    /// Extract u64 parameter with default
    pub fn extract_u64(data: &Value, key: &str, default: u64) -> u64 {
        data.get(key)
            .and_then(|v| v.as_u64())
            .unwrap_or(default)
    }

    /// Extract boolean parameter with default
    pub fn extract_bool(data: &Value, key: &str, default: bool) -> bool {
        data.get(key)
            .and_then(|v| v.as_bool())
            .unwrap_or(default)
    }
}

/// String manipulation helpers
pub mod strings {
    /// Check if string is empty or whitespace
    pub fn is_blank(s: &str) -> bool {
        s.trim().is_empty()
    }

    /// Sanitize command string (remove dangerous characters)
    pub fn sanitize_command(cmd: &str) -> String {
        cmd.replace('\0', "")
           .replace('\r', "")
           .trim()
           .to_string()
    }

    /// Truncate string to max length
    pub fn truncate(s: &str, max_len: usize) -> String {
        if s.len() <= max_len {
            s.to_string()
        } else {
            format!("{}...", &s[..max_len.saturating_sub(3)])
        }
    }
}

/// Environment detection helpers
pub mod environment {
    use std::process::Command;

    /// Detect the correct DISPLAY for the current session
    /// First checks env var, then searches for active X displays
    pub fn get_display() -> String {
        // First, check if DISPLAY is already set in environment
        if let Ok(display) = std::env::var("DISPLAY") {
            if !display.is_empty() {
                return display;
            }
        }

        // Try to detect active X server display
        // Check common X socket locations
        for display_num in &["0", "1", "2", "10", "99"] {
            let socket_path = format!("/tmp/.X11-unix/X{}", display_num);
            if std::path::Path::new(&socket_path).exists() {
                return format!(":{}", display_num);
            }
        }

        // Try Wayland
        if std::env::var("WAYLAND_DISPLAY").is_ok() {
            eprintln!("⚠️  Using Wayland instead of X11");
        }

        // Fallback
        eprintln!("⚠️  Could not detect active display, using default :0");
        ":0".to_string()
    }

    /// Get XAUTHORITY file location
    pub fn get_xauthority() -> String {
        std::env::var("XAUTHORITY").unwrap_or_else(|_| {
            format!("{}/.Xauthority", std::env::var("HOME").unwrap_or_default())
        })
    }

    /// Get proper DBUS address for the current session
    pub fn get_dbus_address() -> String {
        // Try to get from environment
        if let Ok(addr) = std::env::var("DBUS_SESSION_BUS_ADDRESS") {
            if !addr.is_empty() {
                return addr;
            }
        }

        // Try to detect using dbus-launch
        if let Ok(output) = Command::new("dbus-launch")
            .arg("--sh-syntax")
            .output()
        {
            if let Ok(output_str) = String::from_utf8(output.stdout) {
                for line in output_str.lines() {
                    if line.starts_with("DBUS_SESSION_BUS_ADDRESS=") {
                        if let Some(addr) = line.split('=').nth(1) {
                            let addr = addr.trim_matches(';').trim_matches('\'').to_string();
                            if !addr.is_empty() {
                                return addr;
                            }
                        }
                    }
                }
            }
        }

        // Fallback - try to get UID from environment
        let uid = std::env::var("UID")
            .or_else(|_| std::env::var("EUID"))
            .unwrap_or_else(|_| "1000".to_string()); // Common default UID
        format!("unix:path=/run/user/{}/bus", uid)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_environment_detection() {
        let display = environment::get_display();
        assert!(!display.is_empty());
        eprintln!("Detected DISPLAY: {}", display);
    }

    #[test]
    fn test_response_builders() {
        let success = response::success("test output".to_string());
        assert!(success.success);
        assert_eq!(success.output, Some("test output".to_string()));
        assert_eq!(success.error, None);

        let error = response::error("test error".to_string());
        assert!(!error.success);
        assert_eq!(error.error, Some("test error".to_string()));
        assert_eq!(error.output, None);

        let exists = response::exists(true);
        assert_eq!(exists.exists, Some(true));
    }

    #[test]
    fn test_param_extraction() {
        let data = json!({
            "command": "ls -la",
            "lines": 200,
            "verbose": true
        });

        assert_eq!(
            params::extract_string(&data, "command").unwrap(),
            "ls -la"
        );
        assert_eq!(params::extract_i64(&data, "lines", 100), 200);
        assert_eq!(params::extract_bool(&data, "verbose", false), true);
        assert_eq!(params::extract_bool(&data, "missing", false), false);
    }

    #[test]
    fn test_sanitize_command() {
        let dirty = "ls\0-la\r\n";
        let clean = strings::sanitize_command(dirty);
        assert_eq!(clean, "ls-la");
    }
}

