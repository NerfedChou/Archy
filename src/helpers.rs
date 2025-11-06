// helpers.rs - Reusable Helper Functions
// Eliminates code duplication throughout the codebase

use serde::{Serialize};
use serde_json::Value;

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

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

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

