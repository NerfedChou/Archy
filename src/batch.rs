// batch.rs - Batch command execution module
// Executes multiple commands in sequence with structured result aggregation

use serde::{Deserialize, Serialize};
use serde_json::Value;
use crate::tmux;
use crate::parser::parse_intelligently;
use crate::config::Config;

/// Single command result in a batch
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchCommandResult {
    pub index: usize,
    pub command: String,
    pub explanation: String,
    pub success: bool,
    pub status: String, // "success", "error", "timeout"
    pub output_preview: Option<String>,
    pub error: Option<String>,
}

/// Overall batch execution result
#[derive(Debug, Serialize, Deserialize)]
pub struct BatchExecutionResult {
    pub total_commands: usize,
    pub successful: usize,
    pub failed: usize,
    pub commands: Vec<BatchCommandResult>,
    pub summary: String,
}

impl BatchExecutionResult {
    pub fn new() -> Self {
        Self {
            total_commands: 0,
            successful: 0,
            failed: 0,
            commands: Vec::new(),
            summary: String::new(),
        }
    }
}

/// Execute a batch of commands and return structured result
pub fn execute_batch(
    data: &Value,
    config: &Config,
) -> Result<BatchExecutionResult, String> {
    // Extract commands array
    let commands_arr = data
        .get("commands")
        .and_then(|v| v.as_array())
        .ok_or_else(|| "Missing or invalid 'commands' array".to_string())?;

    // Extract session name
    let session = data
        .get("session")
        .and_then(|v| v.as_str())
        .unwrap_or(&config.default_session);

    let mut result = BatchExecutionResult::new();
    result.total_commands = commands_arr.len();

    // Ensure session exists
    if !tmux::has_session(session) {
        tmux::new_session(session)
            .map_err(|e| format!("Failed to create session: {}", e))?;
        std::thread::sleep(std::time::Duration::from_millis(100));
    }

    // Execute each command
    for (idx, cmd_val) in commands_arr.iter().enumerate() {
        let command = match cmd_val.as_str() {
            Some(cmd) => cmd.trim().to_string(),
            None => continue,
        };

        if command.is_empty() {
            continue;
        }

        let explanation = data
            .get("explanations")
            .and_then(|v| v.as_array())
            .and_then(|arr| arr.get(idx))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        // Execute command
        match tmux::send_keys(session, &command) {
            Ok(_) => {
                // Wait briefly for output
                std::thread::sleep(std::time::Duration::from_millis(500));

                // Capture output
                let output = tmux::capture_pane(session, 100).unwrap_or_default();

                // Parse intelligently to get summary
                let _parsed = parse_intelligently(&output, &command);

                // Keep preview (first 6 lines)
                let preview = output
                    .lines()
                    .take(6)
                    .collect::<Vec<_>>()
                    .join("\n");

                result.commands.push(BatchCommandResult {
                    index: idx + 1,
                    command: command.clone(),
                    explanation,
                    success: true,
                    status: "success".to_string(),
                    output_preview: if preview.is_empty() {
                        None
                    } else {
                        Some(preview)
                    },
                    error: None,
                });

                result.successful += 1;
            }
            Err(e) => {
                result.commands.push(BatchCommandResult {
                    index: idx + 1,
                    command: command.clone(),
                    explanation,
                    success: false,
                    status: "error".to_string(),
                    output_preview: None,
                    error: Some(e.clone()),
                });

                result.failed += 1;
            }
        }
    }

    // Build summary
    result.summary = format!(
        "Batch executed {} commands: {} succeeded, {} failed",
        result.total_commands, result.successful, result.failed
    );

    Ok(result)
}

