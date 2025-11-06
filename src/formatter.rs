// formatter.rs - Complete Text Output Migration to Rust
// Handles ALL formatting, coloring, and pretty display generation

use serde_json::Value;
use crate::parser::{Finding, Importance, Metadata};

/// ANSI color utilities
pub fn color_red(s: &str) -> String {
    format!("\x1b[31m{}\x1b[0m", s)
}

pub fn color_green(s: &str) -> String {
    format!("\x1b[32m{}\x1b[0m", s)
}

pub fn color_yellow(s: &str) -> String {
    format!("\x1b[33m{}\x1b[0m", s)
}

pub fn color_blue(s: &str) -> String {
    format!("\x1b[34m{}\x1b[0m", s)
}

pub fn color_magenta(s: &str) -> String {
    format!("\x1b[35m{}\x1b[0m", s)
}

pub fn color_cyan(s: &str) -> String {
    format!("\x1b[36m{}\x1b[0m", s)
}

pub fn color_bold(s: &str) -> String {
    format!("\x1b[1m{}\x1b[0m", s)
}

pub fn color_dim(s: &str) -> String {
    format!("\x1b[2m{}\x1b[0m", s)
}

/// Strip ANSI color codes from string
pub fn strip_colors(s: &str) -> String {
    let re = regex::Regex::new(r"\x1b\[[0-9;]*m").unwrap();
    re.replace_all(s, "").to_string()
}

/// Pad string to specific width
pub fn pad_string(s: &str, width: usize) -> String {
    if s.len() >= width {
        s.to_string()
    } else {
        format!("{}{}", s, " ".repeat(width - s.len()))
    }
}

/// Truncate string to max length with ellipsis
pub fn truncate_string(s: &str, max_len: usize) -> String {
    if s.len() <= max_len {
        s.to_string()
    } else if max_len <= 3 {
        "...".to_string()
    } else {
        format!("{}...", &s[..max_len - 3])
    }
}

/// Format a finding with icon and color based on importance
pub fn format_finding(finding: &Finding) -> String {
    let icon = match finding.importance {
        Importance::Critical => "🔴",
        Importance::High => "🟠",
        Importance::Medium => "🟡",
        Importance::Low => "🟢",
        Importance::Info => "ℹ️ ",
    };

    format!(
        "  {} {} - {}\n",
        icon,
        color_bold(&finding.category),
        finding.message
    )
}

/// Generate summary from findings
pub fn generate_summary(findings: &[Finding]) -> String {
    if findings.is_empty() {
        return "Command completed successfully".to_string();
    }

    let critical = findings.iter().filter(|f| matches!(f.importance, Importance::Critical)).count();
    let high = findings.iter().filter(|f| matches!(f.importance, Importance::High)).count();

    if critical > 0 {
        format!("{} critical issue(s) found", critical)
    } else if high > 0 {
        format!("{} important finding(s) detected", high)
    } else {
        findings.first().map(|f| f.message.clone()).unwrap_or_else(|| "Analysis complete".to_string())
    }
}

/// Check if a JSON object looks like table data
pub fn is_table_like(obj: &serde_json::Map<String, Value>) -> bool {
    // Simple heuristic: if all values are primitives, it's table-like
    obj.values().all(|v| matches!(v, Value::String(_) | Value::Number(_) | Value::Bool(_) | Value::Null))
}

/// Format JSON object as a simple key-value table
pub fn format_as_table(data: &serde_json::Map<String, Value>) -> String {
    let mut output = String::new();
    output.push_str(&color_cyan("\n┌─ Data\n"));

    for (key, value) in data {
        let formatted_value = match value {
            Value::String(s) => s.clone(),
            Value::Number(n) => n.to_string(),
            Value::Bool(b) => b.to_string(),
            Value::Null => "null".to_string(),
            _ => value.to_string(),
        };

        output.push_str(&format!(
            "│ {}: {}\n",
            color_bold(key),
            formatted_value
        ));
    }

    output.push_str("└─\n");
    output
}

/// Format array of objects as a pretty table with borders
pub fn format_as_table_from_array(arr: &[Value]) -> String {
    if arr.is_empty() {
        return color_dim("  (No data)\n");
    }

    let mut output = String::new();

    // Get headers from first object
    if let Some(Value::Object(first)) = arr.first() {
        let headers: Vec<String> = first.keys().cloned().collect();

        // Calculate column widths
        let mut widths: Vec<usize> = headers.iter().map(|h| h.len()).collect();

        for item in arr {
            if let Value::Object(obj) = item {
                for (i, header) in headers.iter().enumerate() {
                    if let Some(val) = obj.get(header) {
                        let val_str = match val {
                            Value::String(s) => s.clone(),
                            Value::Number(n) => n.to_string(),
                            Value::Bool(b) => b.to_string(),
                            Value::Null => "null".to_string(),
                            _ => val.to_string(),
                        };
                        widths[i] = widths[i].max(val_str.len()).min(50); // Cap at 50 chars
                    }
                }
            }
        }

        // Draw table top border
        output.push_str("\n┌");
        for (i, width) in widths.iter().enumerate() {
            output.push_str(&"─".repeat(width + 2));
            if i < widths.len() - 1 {
                output.push('┬');
            }
        }
        output.push_str("┐\n");

        // Headers
        output.push('│');
        for (header, width) in headers.iter().zip(&widths) {
            output.push_str(&format!(
                " {} │",
                color_bold(&pad_string(&truncate_string(header, *width), *width))
            ));
        }
        output.push('\n');

        // Separator
        output.push('├');
        for (i, width) in widths.iter().enumerate() {
            output.push_str(&"─".repeat(width + 2));
            if i < widths.len() - 1 {
                output.push('┼');
            }
        }
        output.push_str("┤\n");

        // Data rows (limit to 20 rows for display)
        let display_limit = 20;
        let rows_to_show = arr.len().min(display_limit);

        for item in arr.iter().take(rows_to_show) {
            if let Value::Object(obj) = item {
                output.push('│');
                for (header, width) in headers.iter().zip(&widths) {
                    let val_str = if let Some(val) = obj.get(header) {
                        match val {
                            Value::String(s) => s.clone(),
                            Value::Number(n) => n.to_string(),
                            Value::Bool(b) => b.to_string(),
                            Value::Null => "null".to_string(),
                            _ => val.to_string(),
                        }
                    } else {
                        "".to_string()
                    };
                    output.push_str(&format!(
                        " {} │",
                        pad_string(&truncate_string(&val_str, *width), *width)
                    ));
                }
                output.push('\n');
            }
        }

        // Bottom border
        output.push('└');
        for (i, width) in widths.iter().enumerate() {
            output.push_str(&"─".repeat(width + 2));
            if i < widths.len() - 1 {
                output.push('┴');
            }
        }
        output.push_str("┘\n");

        // Show truncation notice if needed
        if arr.len() > display_limit {
            output.push_str(&color_dim(&format!("  ... and {} more rows\n", arr.len() - display_limit)));
        }
    } else {
        // Not an array of objects, just show as JSON
        let arr_value = Value::Array(arr.to_vec());
        output.push_str(&format_as_json(&arr_value));
    }

    output
}

/// Format data section based on type
pub fn format_data_section(data: &Value) -> String {
    match data {
        Value::Object(obj) if is_table_like(obj) => {
            format_as_table(obj)
        }
        Value::Array(arr) if !arr.is_empty() => {
            format_as_table_from_array(arr)
        }
        Value::Null => {
            String::new()
        }
        _ => {
            // Don't show raw JSON to users - structured data is for AI internal use only
            // If it's not table-like, just skip displaying it
            String::new()
        }
    }
}

/// Format value as pretty JSON with indentation
pub fn format_as_json(value: &Value) -> String {
    match serde_json::to_string_pretty(value) {
        Ok(json) => format!("\n{}\n", color_dim(&json)),
        Err(_) => format!("\n{}\n", color_dim(&value.to_string())),
    }
}

/// Main formatter: create pretty output with command header, findings, data, and summary
pub fn format_pretty(
    data: &Value,
    findings: &[Finding],
    command: &str,
) -> String {
    let mut output = String::new();

    // Command header with styling
    output.push_str(&format!(
        "{}\n",
        color_cyan(&format!("➜ Command: {}", command))
    ));

    // Findings section (most important)
    if !findings.is_empty() {
        output.push_str(&color_yellow("\n📊 Key Findings:\n"));
        for finding in findings {
            output.push_str(&format_finding(finding));
        }
    }

    // Data section (structured)
    let data_section = format_data_section(data);
    if !data_section.trim().is_empty() {
        output.push_str(&data_section);
    }

    // Summary
    let summary = generate_summary(findings);
    output.push_str(&format!(
        "\n{}\n",
        color_green(&format!("✓ Summary: {}", summary))
    ));

    output
}

/// Format error message
pub fn format_error(command: &str, error: &str) -> String {
    format!(
        "{}\n{}\n",
        color_red(&format!("✗ Command failed: {}", command)),
        color_red(&format!("  Error: {}", error))
    )
}

/// Format metadata display
pub fn format_metadata(metadata: &Metadata) -> String {
    let mut output = String::new();

    output.push_str(&color_dim("\n─── Metadata ───\n"));
    output.push_str(&color_dim(&format!("Lines: {}\n", metadata.line_count)));
    output.push_str(&color_dim(&format!("Size: {} bytes\n", metadata.byte_count)));

    if let Some(duration) = metadata.duration_ms {
        output.push_str(&color_dim(&format!("Duration: {}ms\n", duration)));
    }

    output
}

/// Format batch execution result with AI-friendly summary
pub fn format_batch_result(batch: &crate::batch::BatchExecutionResult) -> String {
    let mut output = String::new();

    // Header
    output.push_str("\n");
    output.push_str(&format!("{}\n", color_cyan("⚡ Executing commands in sequence...")));
    output.push_str(&format!("{}\n\n", color_dim(&"─".repeat(60))));

    // Command list
    for cmd in &batch.commands {
        output.push_str(&format!(
            "{}\n",
            color_cyan(&format!("[{}/{}] {}", cmd.index, batch.total_commands, cmd.command))
        ));

        if cmd.success {
            output.push_str(&format!("  {}\n", color_green("✓ Completed")));
        } else {
            output.push_str(&format!(
                "  {}\n",
                color_red(&format!("✗ Failed: {}", cmd.error.as_ref().unwrap_or(&"Unknown error".to_string())))
            ));
        }
    }

    output.push_str(&format!("{}\n", color_dim(&"─".repeat(60))));

    // AI Explanations section
    output.push_str(&format!("\n{}\n", color_magenta("🤖 AI COMMAND EXPLANATIONS")));
    output.push_str(&format!("{}\n\n", "=".repeat(60)));

    for cmd in &batch.commands {
        output.push_str(&format!("[{}] {}\n", cmd.index, color_bold(&cmd.command)));
        if !cmd.explanation.is_empty() {
            output.push_str(&format!("  📝 Explanation: {}\n", cmd.explanation));
        } else {
            output.push_str("  📝 Explanation: (AI explanation pending)\n");
        }
        output.push_str("\n");
    }

    // Summary
    output.push_str(&format!("{}\n", "=".repeat(60)));
    output.push_str(&format!("{}\n", color_yellow("💡 COMMAND SUMMARY")));
    output.push_str(&format!("{}\n\n", "=".repeat(60)));

    output.push_str(&format!(
        "✓ {} completed successfully\n",
        color_green(&format!("{}/{}", batch.successful, batch.total_commands))
    ));

    if batch.failed > 0 {
        output.push_str(&format!(
            "✗ {} failed\n",
            color_red(&batch.failed.to_string())
        ));
    }

    output
}
