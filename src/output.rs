// output.rs - DisplayOutput structure and integration
// Combines parser and formatter into final output structure

use serde::Serialize;
use serde_json::Value;
use crate::parser::{Finding, Metadata, parse_intelligently};
use crate::formatter::{format_pretty, format_error, strip_colors};

/// Complete output structure returned to Python
#[derive(Debug, Serialize)]
pub struct DisplayOutput {
    pub success: bool,               // Quick boolean check for Python
    pub command: String,
    pub status: String,              // "success", "error", "timeout"
    pub exit_code: i32,

    // For Python logic
    pub structured: Value,           // JSON data
    pub findings: Vec<Finding>,      // Key insights
    pub summary: String,             // Text summary

    // For display
    pub display: String,             // Formatted text with colors
    pub display_plain: String,       // No colors (for logging)

    pub metadata: Metadata,
}

impl DisplayOutput {
    /// Create a successful output from command execution
    pub fn from_command_output(command: &str, raw_output: &str, exit_code: i32) -> Self {
        let parsed = parse_intelligently(raw_output, command);

        let display = format_pretty(
            &parsed.structured,
            &parsed.findings,
            command,
        );

        let display_plain = strip_colors(&display);

        let is_success = exit_code == 0;

        DisplayOutput {
            success: is_success,
            command: command.to_string(),
            status: if is_success { "success".to_string() } else { "error".to_string() },
            exit_code,
            structured: parsed.structured,
            findings: parsed.findings,
            summary: parsed.summary,
            display,
            display_plain,
            metadata: parsed.metadata,
        }
    }

    /// Create an error output
    pub fn from_error(command: &str, error: &str) -> Self {
        use serde_json::json;

        let display = format_error(command, error);
        let display_plain = strip_colors(&display);

        DisplayOutput {
            success: false,
            command: command.to_string(),
            status: "error".to_string(),
            exit_code: -1,
            structured: json!({"error": error}),
            findings: vec![],
            summary: format!("Error: {}", error),
            display,
            display_plain,
            metadata: Metadata {
                line_count: 0,
                byte_count: 0,
                duration_ms: None,
                format_detected: "error".to_string(),
            },
        }
    }

    /// Create a timeout output
    pub fn from_timeout(command: &str, partial_output: &str) -> Self {
        use serde_json::json;

        let display = format_error(command, "Command timeout - may still be running");
        let display_plain = strip_colors(&display);

        DisplayOutput {
            success: false,
            command: command.to_string(),
            status: "timeout".to_string(),
            exit_code: -1,
            structured: json!({"timeout": true, "partial_output": partial_output}),
            findings: vec![],
            summary: "Command timeout".to_string(),
            display,
            display_plain,
            metadata: Metadata {
                line_count: partial_output.lines().count(),
                byte_count: partial_output.len(),
                duration_ms: None,
                format_detected: "timeout".to_string(),
            },
        }
    }

    /// Create a simple success response (for non-command actions)
    pub fn simple_success(message: &str) -> Self {
        use serde_json::json;
        use crate::formatter::color_green;

        let display = format!("{}\n", color_green(&format!("✓ {}", message)));
        let display_plain = strip_colors(&display);

        DisplayOutput {
            success: true,
            command: "".to_string(),
            status: "success".to_string(),
            exit_code: 0,
            structured: json!({"message": message}),
            findings: vec![],
            summary: message.to_string(),
            display,
            display_plain,
            metadata: Metadata {
                line_count: 1,
                byte_count: message.len(),
                duration_ms: None,
                format_detected: "simple".to_string(),
            },
        }
    }
}

