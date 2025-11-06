// config.rs - Configuration Management
// Centralizes all configuration, eliminates hardcoding

use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub socket_path: String,
    pub default_session: String,
    pub max_buffer_size: usize,
    pub default_capture_lines: i64,
    pub terminal_emulator: Option<String>,
    pub max_wait_seconds: u64,
    pub poll_interval_ms: u64,
}

impl Config {
    /// Load configuration from environment variables with sensible defaults
    pub fn from_env() -> Self {
        Config {
            socket_path: env::var("ARCHY_SOCKET")
                .unwrap_or_else(|_| "/tmp/archy.sock".to_string()),

            default_session: env::var("ARCHY_TMUX_SESSION")
                .unwrap_or_else(|_| "archy_session".to_string()),

            max_buffer_size: env::var("ARCHY_BUFFER_SIZE")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(8192),

            default_capture_lines: env::var("ARCHY_CAPTURE_LINES")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(100),

            terminal_emulator: env::var("ARCHY_TERMINAL").ok(),

            max_wait_seconds: env::var("ARCHY_MAX_WAIT")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(600),

            poll_interval_ms: env::var("ARCHY_POLL_INTERVAL")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(500),
        }
    }

    /// Get session name from data or use default
    pub fn get_session<'a>(&'a self, data: &'a serde_json::Value) -> &'a str {
        data.get("session")
            .and_then(|v| v.as_str())
            .unwrap_or(&self.default_session)
    }

    /// Get capture lines from data or use default
    pub fn get_lines(&self, data: &serde_json::Value) -> i64 {
        data.get("lines")
            .and_then(|v| v.as_i64())
            .unwrap_or(self.default_capture_lines)
    }
}

impl Default for Config {
    fn default() -> Self {
        Config {
            socket_path: "/tmp/archy.sock".to_string(),
            default_session: "archy_session".to_string(),
            max_buffer_size: 8192,
            default_capture_lines: 100,
            terminal_emulator: None,
            max_wait_seconds: 600,
            poll_interval_ms: 500,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = Config::default();
        assert_eq!(config.socket_path, "/tmp/archy.sock");
        assert_eq!(config.default_session, "archy_session");
        assert_eq!(config.max_buffer_size, 8192);
    }

    #[test]
    fn test_get_session_from_data() {
        let config = Config::default();
        let data = serde_json::json!({
            "session": "custom_session"
        });
        assert_eq!(config.get_session(&data), "custom_session");
    }

    #[test]
    fn test_get_session_default() {
        let config = Config::default();
        let data = serde_json::json!({});
        assert_eq!(config.get_session(&data), "archy_session");
    }
}

