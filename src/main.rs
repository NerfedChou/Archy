use std::os::unix::net::{UnixListener, UnixStream};
use std::io::{Read, Write};
use std::process::Command;
use serde::Deserialize;
use serde_json;
use std::fs;
use std::path::PathBuf;

// New modular architecture
mod formatter;
mod parser;
mod output;
mod config;
mod helpers;
mod tmux;

use output::DisplayOutput;
use config::Config;
use helpers::{response, params, Response};
use helpers::security::{safe_json_response, escape_pgrep_pattern, is_safe_executable_path, validate_command, validate_desktop_entry};
use serde_json::Value;

#[derive(Deserialize)]
struct Request {
    action: String,
    data: Value,
}

fn main() -> std::io::Result<()> {
    // Load configuration from environment
    let config = Config::from_env();

    // Remove old socket if exists
    let _ = fs::remove_file(&config.socket_path);

    let listener = UnixListener::bind(&config.socket_path)?;
    println!("🦀 Archy Executor (Rust) listening on {}", config.socket_path);
    println!("✅ Configuration loaded:");
    println!("   • Socket: {}", config.socket_path);
    println!("   • Default session: {}", config.default_session);
    println!("   • Buffer size: {}", config.max_buffer_size);
    println!("✅ Ready to handle system operations...\n");

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {

                if let Err(e) = handle_client(stream, &config) {
                    eprintln!("❌ Client handler error: {}", e);
                }
            }
            Err(e) => eprintln!("❌ Connection failed: {}", e),
        }
    }

    Ok(())
}

fn handle_client(mut stream: UnixStream, config: &Config) -> std::io::Result<()> {
    // Set read timeout to prevent hanging connections
    use std::time::Duration;
    stream.set_read_timeout(Some(Duration::from_secs(30)))?;
    stream.set_write_timeout(Some(Duration::from_secs(30)))?;

    // Read the full request (handle partial reads)
    let mut buffer = Vec::new();
    let mut temp_buf = vec![0; 8192];
    let mut total_read = 0;

    loop {
        match stream.read(&mut temp_buf) {
            Ok(0) => break,  // EOF
            Ok(n) => {
                total_read += n;
                buffer.extend_from_slice(&temp_buf[..n]);

                // Try to parse - if successful, we have a complete message
                if let Ok(_) = serde_json::from_slice::<Request>(&buffer) {
                    break;
                }

                // Prevent infinite reads
                if total_read > config.max_buffer_size {
                    send_error(&mut stream, "Request too large")?;
                    return Ok(());
                }
            }
            // FIX #2: Handle TimedOut instead of WouldBlock (socket is blocking with timeout)
            Err(e) if e.kind() == std::io::ErrorKind::TimedOut => {
                // Socket timeout - we have partial data, try to parse it
                if buffer.is_empty() {
                    send_error(&mut stream, "Connection timeout")?;
                }
                break;
            }
            Err(e) => {
                eprintln!("❌ Read error: {}", e);
                return Ok(());
            }
        }
    }

    // FIX #7: Validate buffer is not empty and send error response
    if buffer.is_empty() {
        send_error(&mut stream, "Empty request received")?;
        return Ok(());
    }

    let request: Request = match serde_json::from_slice(&buffer) {
        Ok(req) => req,
        Err(e) => {
            send_error(&mut stream, &format!("Invalid JSON: {}", e))?;
            return Ok(());
        }
    };

    let response = match request.action.as_str() {
        "execute" => execute_command(&request.data, config),
        "execute_analyzed" => return handle_execute_analyzed(&mut stream, &request.data),
        "execute_and_wait" => return handle_execute_and_wait(&mut stream, &request.data),
        "capture" => capture_tmux_output(&request.data, config),
        "capture_analyzed" => return handle_capture_analyzed(&mut stream, &request.data),
        "check_session" => check_tmux_session(config),
        "open_terminal" => open_terminal(config),
        "close_terminal" => close_terminal(),
        "close_session" => close_session(&request.data),
        "is_foot_running" => is_foot_running(),
        "check_command" => check_command_available(&request.data),
        "get_system_info" => get_system_info(),
        "find_desktop_entry" => find_desktop_entry(&request.data),
        "extract_directory" => extract_current_directory(&request.data),
        "wait_for_prompt" => wait_for_command_completion(&request.data),
        "launch_gui_app" => launch_gui_app(&request.data),
        "detect_terminal" => detect_terminal(),
        "launch_fallback_terminal" => launch_fallback_terminal(&request.data),
        "execute_smart" => execute_command_smart(&request.data, config),
        _ => response::error("Unknown action".to_string()),
    };

    // FIX #1: Use safe_json_response instead of unwrap()
    safe_json_response(&response, &mut stream)?;
    Ok(())
}

fn execute_command(data: &Value, config: &Config) -> Response {
    // Extract parameters using helpers
    let command = match params::extract_string(data, "command") {
        Ok(cmd) => cmd,
        Err(e) => return response::error(e),
    };

    // Validate and sanitize command using helper
    if command.trim().is_empty() {
        return response::error("Command cannot be empty".to_string());
    }

    // FIX: Use centralized command validation
    if let Err(e) = validate_command(&command) {
        return response::error(e);
    }

    let session = config.get_session(data);

    // Ensure session exists before sending command
    if !tmux::has_session(session) {
        if let Err(e) = tmux::new_session(session) {
            eprintln!("⚠️ Failed to create session {}: {}", session, e);
            return response::error(format!("Failed to create tmux session: {}", e));
        }
        // Brief wait for session initialization
        std::thread::sleep(std::time::Duration::from_millis(50));
    }

    // Use tmux module for execution
    match tmux::send_keys(session, &command) {
        Ok(_) => response::success(format!("✓ Executed: {}", command)),
        Err(e) => response::error(e),
    }
}

fn capture_tmux_output(data: &Value, config: &Config) -> Response {
    let lines = config.get_lines(data);
    let session = config.get_session(data);

    // Use tmux module for capture
    match tmux::capture_pane(session, lines) {
        Ok(output) => response::success(output),
        Err(e) => response::error(e),
    }
}

fn check_tmux_session(config: &Config) -> Response {
    let session = &config.default_session;

    // Use tmux module for session check
    let exists = tmux::has_session(session);
    response::exists(exists)
}



fn open_terminal(config: &Config) -> Response {
    let session = &config.default_session;

    // Check if session exists, create if not
    let has_session = Command::new("tmux")
        .args(&["has-session", "-t", session])
        .status();

    if let Ok(status) = has_session {
        if !status.success() {
            // Create new session
            let create = Command::new("tmux")
                .args(&["new-session", "-d", "-s", session])
                .status();

            if let Err(e) = create {
                return Response {
                    success: false,
                    output: None,
                    error: Some(format!("Failed to create session: {}", e)),
                    exists: None,
                };
            }
        }
    }

    // FIX #3: Escape session name in pgrep pattern to prevent regex injection
    let escaped_session = escape_pgrep_pattern(session);
    let check_foot = Command::new("pgrep")
        .args(&["-f", &format!("foot.*tmux.*attach.*{}", escaped_session)])
        .output();

    if let Ok(result) = check_foot {
        if result.status.success() {
            // foot is already running, don't open another one
            return Response {
                success: true,
                output: Some("✓ Terminal already open (reattached)".to_string()),
                error: None,
                exists: None,
            };
        }
    }

    // Open foot terminal attached to session (non-blocking, detached)
    let result = Command::new("setsid")
        .args(&["foot", "-e", "tmux", "attach", "-t", session])
        .spawn();

    match result {
        Ok(_) => Response {
            success: true,
            output: Some("✓ Terminal opened".to_string()),
            error: None,
            exists: None,
        },
        Err(e) => Response {
            success: false,
            output: None,
            error: Some(format!("Failed to open terminal: {}", e)),
            exists: None,
        },
    }
}

fn close_terminal() -> Response {
    // Find foot processes by looking for foot running with tmux attach
    // The process line looks like: setsid foot -e tmux attach -t archy_session
    let output = Command::new("pgrep")
        .args(&["-f", "foot.*tmux.*attach"])
        .output();

    match output {
        Ok(result) => {
            if result.status.success() {
                let pids = String::from_utf8_lossy(&result.stdout);
                let mut closed_any = false;

                for pid in pids.lines() {
                    if let Ok(_) = Command::new("kill").arg(pid).status() {
                        closed_any = true;
                    }
                }

                if closed_any {
                    Response {
                        success: true,
                        output: Some("✓ Terminal window closed".to_string()),
                        error: None,
                        exists: None,
                    }
                } else {
                    Response {
                        success: false,
                        output: None,
                        error: Some("No foot terminal found".to_string()),
                        exists: None,
                    }
                }
            } else {
                Response {
                    success: false,
                    output: None,
                    error: Some("No foot terminal found".to_string()),
                    exists: None,
                }
            }
        }
        Err(e) => Response {
            success: false,
            output: None,
            error: Some(e.to_string()),
            exists: None,
        },
    }
}

fn close_session(data: &serde_json::Value) -> Response {
    let session = data.get("session")
        .and_then(|v| v.as_str())
        .unwrap_or("archy_session");

    // FIX #3: Escape session name in pgrep pattern
    let escaped_session = escape_pgrep_pattern(session);

    // First close any foot terminals
    let _ = Command::new("pkill")
        .args(&["-f", &format!("foot.*{}", escaped_session)])
        .status();

    // Then kill the tmux session
    let result = Command::new("tmux")
        .args(&["kill-session", "-t", session])
        .status();

    match result {
        Ok(status) => {
            if status.success() {
                Response {
                    success: true,
                    output: Some("✓ Session closed".to_string()),
                    error: None,
                    exists: None,
                }
            } else {
                Response {
                    success: false,
                    output: None,
                    error: Some("Session not found or already closed".to_string()),
                    exists: None,
                }
            }
        }
        Err(e) => Response {
            success: false,
            output: None,
            error: Some(e.to_string()),
            exists: None,
        },
    }
}

fn is_foot_running() -> Response {
    // Check if foot terminal is running by looking for foot with tmux attach
    // The process line looks like: setsid foot -e tmux attach -t archy_session
    let output = Command::new("pgrep")
        .args(&["-f", "foot.*tmux.*attach"])
        .output();

    match output {
        Ok(result) => {
            if result.status.success() && !result.stdout.is_empty() {
                Response {
                    success: true,
                    output: None,
                    error: None,
                    exists: Some(true),
                }
            } else {
                Response {
                    success: true,
                    output: None,
                    error: None,
                    exists: Some(false),
                }
            }
        }
        Err(e) => Response {
            success: false,
            output: None,
            error: Some(e.to_string()),
            exists: Some(false),
        },
    }
}

fn check_command_available(data: &serde_json::Value) -> Response {
    let command = match data.get("command").and_then(|v| v.as_str()) {
        Some(cmd) => cmd,
        None => return Response {
            success: false,
            output: None,
            error: Some("Missing command parameter".to_string()),
            exists: None,
        },
    };

    let status = Command::new("which")
        .arg(command)
        .output();

    match status {
        Ok(result) => {
            let is_available = result.status.success();
            Response {
                success: true,
                output: None,
                error: None,
                exists: Some(is_available),
            }
        }
        Err(e) => Response {
            success: false,
            output: None,
            error: Some(e.to_string()),
            exists: Some(false),
        },
    }
}

fn get_system_info() -> Response {
    let output = Command::new("uname")
        .arg("-a")
        .output();

    match output {
        Ok(result) => {
            if result.status.success() {
                // FIX #4: Handle invalid UTF-8 properly instead of silently corrupting
                let info = match String::from_utf8(result.stdout) {
                    Ok(s) => s.trim().to_string(),
                    Err(e) => {
                        eprintln!("⚠️ Invalid UTF-8 in system info: {}", e);
                        return Response {
                            success: false,
                            output: None,
                            error: Some("Invalid UTF-8 in system output".to_string()),
                            exists: None,
                        };
                    }
                };
                Response {
                    success: true,
                    output: Some(format!("System: {}", info)),
                    error: None,
                    exists: None,
                }
            } else {
                Response {
                    success: false,
                    output: Some("System info unavailable".to_string()),
                    error: None,
                    exists: None,
                }
            }
        }
        Err(e) => Response {
            success: false,
            output: Some("System info unavailable".to_string()),
            error: Some(e.to_string()),
            exists: None,
        },
    }
}

fn find_desktop_entry(data: &serde_json::Value) -> Response {
    let app_name = match data.get("app_name").and_then(|v| v.as_str()) {
        Some(name) => name,
        None => return Response {
            success: false,
            output: None,
            error: Some("Missing app_name parameter".to_string()),
            exists: None,
        },
    };

    // Validate app_name to prevent directory traversal
    if app_name.contains('/') || app_name.contains("..") || app_name.contains('\0') {
        return Response {
            success: false,
            output: None,
            error: Some("Invalid app_name: contains illegal characters".to_string()),
            exists: None,
        };
    }

    // Limit length
    if app_name.len() > 255 {
        return Response {
            success: false,
            output: None,
            error: Some("Invalid app_name: too long".to_string()),
            exists: None,
        };
    }

    let app_name_lower = app_name.to_lowercase();
    eprintln!("🔍 Searching for desktop entry: {}", app_name);

    let desktop_dirs = vec![
        format!("{}/.local/share/applications", std::env::var("HOME").unwrap_or_default()),
        "/usr/local/share/applications".to_string(),
        "/usr/share/applications".to_string(),
        "/usr/share/applications/kde4".to_string(),
        "/usr/share/applications/kde5".to_string(),
        format!("{}/.config/applications", std::env::var("HOME").unwrap_or_default()),
        "/opt/applications".to_string(),
    ];

    // First pass: try exact filename match
    eprintln!("  [Pass 1] Checking exact filename match...");
    for dir in &desktop_dirs {
        let path = PathBuf::from(&dir);
        if !path.exists() || !path.is_dir() {
            continue;
        }

        let desktop_file = format!("{}/{}.desktop", dir, app_name);
        if fs::metadata(&desktop_file).is_ok() {
            eprintln!("  ✓ Found exact match: {}", desktop_file);
            return Response {
                success: true,
                output: Some(app_name.to_string()),
                error: None,
                exists: Some(true),
            };
        }
    }

    // Second pass: search by Name field or Exec field
    eprintln!("  [Pass 2] Searching by Name and Exec fields...");
    for dir in &desktop_dirs {
        let path = PathBuf::from(&dir);
        if !path.exists() || !path.is_dir() {
            continue;
        }

        if let Ok(entries) = fs::read_dir(&path) {
            for entry in entries.flatten() {
                let filepath = entry.path();
                if let Some(ext) = filepath.extension() {
                    if ext == "desktop" {
                        if let Ok(content) = fs::read_to_string(&filepath) {
                            let mut found = false;

                            for line in content.lines() {
                                // Check Name field
                                if line.starts_with("Name=") && line.len() > 5 {
                                    let name_value = &line[5..];
                                    if name_value.eq_ignore_ascii_case(&app_name_lower) {
                                        eprintln!("  ✓ Found by Name field: {}", filepath.display());
                                        found = true;
                                        break;
                                    }
                                }

                                // Check GenericName field
                                if line.starts_with("GenericName=") && line.len() > 12 {
                                    let generic_value = &line[12..];
                                    if generic_value.eq_ignore_ascii_case(&app_name_lower) {
                                        eprintln!("  ✓ Found by GenericName field: {}", filepath.display());
                                        found = true;
                                        break;
                                    }
                                }

                                // Check Exec field for exact command match
                                if line.starts_with("Exec=") && line.len() > 5 {
                                    let exec_value = &line[5..];
                                    let parts: Vec<&str> = exec_value.split_whitespace().collect();
                                    if !parts.is_empty() {
                                        let command = parts[0];
                                        let binary_name = if command.contains('/') {
                                            command.rsplit('/').next().unwrap_or(command)
                                        } else {
                                            command
                                        };

                                        if binary_name.eq_ignore_ascii_case(&app_name_lower) {
                                            eprintln!("  ✓ Found by Exec field: {}", filepath.display());
                                            found = true;
                                            break;
                                        }
                                    }
                                }
                            }

                            if found {
                                if let Some(stem) = filepath.file_stem() {
                                    let entry_name = stem.to_string_lossy().to_string();
                                    return Response {
                                        success: true,
                                        output: Some(entry_name),
                                        error: None,
                                        exists: Some(true),
                                    };
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Third pass: fuzzy match (partial match) - BUT ONLY for longer app names
    // Don't fuzzy match single-letter or 2-letter commands (ls, cd, ps, rm, etc.)
    if app_name_lower.len() >= 4 {
        eprintln!("  [Pass 3] Attempting fuzzy match...");
        for dir in &desktop_dirs {
            let path = PathBuf::from(&dir);
            if !path.exists() || !path.is_dir() {
                continue;
            }

            if let Ok(entries) = fs::read_dir(&path) {
                for entry in entries.flatten() {
                    let filepath = entry.path();
                    if let Some(ext) = filepath.extension() {
                        if ext == "desktop" {
                            if let Ok(content) = fs::read_to_string(&filepath) {
                                for line in content.lines() {
                                    if line.starts_with("Name=") && line.len() > 5 {
                                        let name_value = &line[5..].to_lowercase();
                                        // Only fuzzy match if it's a substantial match (>80% similar length)
                                        let min_match_len = (app_name_lower.len() as f32 * 0.8) as usize;

                                        if name_value.contains(app_name_lower.as_str()) && name_value.len() >= min_match_len {
                                            eprintln!("  ✓ Found by fuzzy match: {}", filepath.display());
                                            if let Some(stem) = filepath.file_stem() {
                                                return Response {
                                                    success: true,
                                                    output: Some(stem.to_string_lossy().to_string()),
                                                    error: None,
                                                    exists: Some(true),
                                                };
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    } else {
        eprintln!("  [Pass 3] Skipping fuzzy match for short app name: '{}'", app_name_lower);
    }

    eprintln!("❌ Desktop entry not found: {}", app_name);
    Response {
        success: true,
        output: None,
        error: Some(format!("Desktop entry '{}' not found", app_name)),
        exists: Some(false),
    }
}

fn extract_current_directory(data: &serde_json::Value) -> Response {
    let terminal_output = match data.get("terminal_output").and_then(|v| v.as_str()) {
        Some(output) => output,
        None => return Response {
            success: false,
            output: None,
            error: Some("Missing terminal_output parameter".to_string()),
            exists: None,
        },
    };

    let lines: Vec<&str> = terminal_output.trim().split('\n').collect();
    if lines.is_empty() {
        return Response {
            success: false,
            output: None,
            error: Some("Empty terminal output".to_string()),
            exists: None,
        };
    }

    // Look at the last few lines for the prompt
    let start = if lines.len() > 5 { lines.len() - 5 } else { 0 };
    for line in lines[start..].iter().rev() {
        // Pattern 1: user@host:path$ or user@host:path#
        if let Some(pos) = line.rfind(':') {
            let after_colon = &line[pos + 1..];
            if let Some(dollar_pos) = after_colon.find('$').or_else(|| after_colon.find('#')) {
                let path = after_colon[..dollar_pos].trim();
                if !path.is_empty() {
                    return Response {
                        success: true,
                        output: Some(path.to_string()),
                        error: None,
                        exists: None,
                    };
                }
            }
        }

        // Pattern 2: [user@host path]$ or [user@host path]#
        if line.contains('[') && line.contains(']') {
            if let Some(start_bracket) = line.rfind('[') {
                if let Some(end_bracket) = line.rfind(']') {
                    if end_bracket > start_bracket {
                        let inside = &line[start_bracket + 1..end_bracket];
                        if let Some(space_pos) = inside.rfind(' ') {
                            let path = inside[space_pos + 1..].trim();
                            if !path.is_empty() {
                                return Response {
                                    success: true,
                                    output: Some(path.to_string()),
                                    error: None,
                                    exists: None,
                                };
                            }
                        }
                    }
                }
            }
        }

        // Pattern 3: space before path and $
        if let Some(dollar_pos) = line.rfind('$').or_else(|| line.rfind('#')) {
            let before_dollar = &line[..dollar_pos];
            if let Some(space_pos) = before_dollar.rfind(' ') {
                let path = before_dollar[space_pos + 1..].trim();
                if !path.is_empty() && (path.starts_with('/') || path.starts_with('~')) {
                    return Response {
                        success: true,
                        output: Some(path.to_string()),
                        error: None,
                        exists: None,
                    };
                }
            }
        }
    }

    Response {
        success: false,
        output: None,
        error: Some("Could not extract directory from prompt".to_string()),
        exists: None,
    }
}

fn wait_for_command_completion(data: &serde_json::Value) -> Response {
    let session = data.get("session")
        .and_then(|v| v.as_str())
        .unwrap_or("archy_session");

    let max_wait_seconds = data.get("max_wait")
        .and_then(|v| v.as_u64())
        .unwrap_or(600) as u64; // Default 10 minutes

    // Cap max_wait to prevent abuse (max 1 hour)
    let max_wait_seconds = max_wait_seconds.min(3600);

    let check_interval_ms = data.get("interval_ms")
        .and_then(|v| v.as_u64())
        .unwrap_or(500) as u64; // Default 500ms

    // Cap check interval to prevent rapid polling (min 100ms)
    let check_interval_ms = check_interval_ms.max(100);

    let command = data.get("command")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    use std::time::{Duration, Instant};
    use std::thread;

    let start_time = Instant::now();
    let max_duration = Duration::from_secs(max_wait_seconds);
    let check_interval = Duration::from_millis(check_interval_ms);

    let mut last_output = String::new();
    let mut stable_count = 0;
    let required_stable_checks = 3; // Output must be stable for 3 checks

    while start_time.elapsed() < max_duration {
        thread::sleep(check_interval);

        // Capture current output
        let output_result = Command::new("tmux")
            .args(&["capture-pane", "-pt", session, "-S", "-100"])
            .output();

        if let Ok(out) = output_result {
            if out.status.success() {
                // FIX #4: Handle invalid UTF-8 properly
                let current_output = match String::from_utf8(out.stdout) {
                    Ok(s) => s,
                    Err(e) => {
                        eprintln!("⚠️ Invalid UTF-8 in tmux output: {}", e);
                        continue;
                    }
                };

                // Check if output has stabilized (FIX #6: Don't clone full string every loop)
                if current_output == last_output {
                    stable_count += 1;
                } else {
                    stable_count = 0;
                    last_output = current_output.clone();
                }

                // Look for prompt in last line
                let lines: Vec<&str> = current_output.trim().split('\n').collect();
                if let Some(last_line) = lines.last() {
                    // FIX #5: Support more shell prompts
                    let has_prompt = last_line.contains('$') ||
                                   last_line.contains('#') ||
                                   last_line.contains('❯') ||
                                   last_line.contains('>') ||
                                   last_line.contains('❮') ||
                                   last_line.contains('⚡');

                    // Make sure the command itself is not in the last line (it just echoed)
                    let command_not_echoed = !last_line.contains(command) || command.is_empty();

                    // Check if it's waiting for password
                    let waiting_for_password = last_line.to_lowercase().contains("password for") ||
                                              last_line.to_lowercase().contains("[sudo]");

                    if !waiting_for_password && has_prompt && command_not_echoed && stable_count >= required_stable_checks {
                        return Response {
                            success: true,
                            output: Some(current_output),
                            error: None,
                            exists: Some(true),
                        };
                    }
                }
            }
        }
    }

    // Timeout reached
    Response {
        success: false,
        output: Some(last_output),
        error: Some("Command timeout - may still be running".to_string()),
        exists: Some(false),
    }
}

fn send_error(stream: &mut UnixStream, msg: &str) -> std::io::Result<()> {
    let response = Response {
        success: false,
        output: None,
        error: Some(msg.to_string()),
        exists: None,
    };
    safe_json_response(&response, stream)?;
    Ok(())
}

/// Helper to safely send JSON response and gracefully handle serialization errors
fn send_json_response<T: serde::Serialize>(stream: &mut UnixStream, data: &T) -> std::io::Result<()> {
    match serde_json::to_string(data) {
        Ok(json) => {
            stream.write_all(json.as_bytes())?;
            stream.flush()?;
        }
        Err(e) => {
            eprintln!("⚠️ JSON serialization error: {}", e);
            let fallback = r#"{"success":false,"output":null,"error":"Internal serialization error","exists":null}"#;
            let _ = stream.write_all(fallback.as_bytes());
            let _ = stream.flush();
        }
    }
    let _ = stream.shutdown(std::net::Shutdown::Both);
    Ok(())
}

fn launch_gui_app(data: &serde_json::Value) -> Response {
    let desktop_entry = match data.get("desktop_entry").and_then(|v| v.as_str()) {
        Some(entry) => entry,
        None => return Response {
            success: false,
            output: None,
            error: Some("Missing desktop_entry parameter".to_string()),
            exists: None,
        },
    };

    // Use centralized validation helper
    if let Err(e) = validate_desktop_entry(desktop_entry) {
        return Response {
            success: false,
            output: None,
            error: Some(e),
            exists: None,
        };
    }

    eprintln!("🔍 Attempting to launch desktop app: {}", desktop_entry);

    // Try gtk-launch first (most reliable)
    eprintln!("  [1] Trying gtk-launch...");
    let gtk_result = Command::new("gtk-launch")
        .arg(desktop_entry)
        .spawn();

    if let Ok(mut child) = gtk_result {
        // Give it a moment to start
        std::thread::sleep(std::time::Duration::from_millis(100));

        match child.try_wait() {
            Ok(Some(status)) => {
                if !status.success() {
                    eprintln!("  ❌ gtk-launch exited with status: {}", status);
                } else {
                    return Response {
                        success: true,
                        output: Some(format!("✓ GUI app '{}' launched via gtk-launch", desktop_entry)),
                        error: None,
                        exists: None,
                    };
                }
            }
            Ok(None) => {
                // Still running - success! Don't kill it, just detach
                eprintln!("  ✓ gtk-launch process still running - application launched successfully");
                return Response {
                    success: true,
                    output: Some(format!("✓ GUI app '{}' launched via gtk-launch", desktop_entry)),
                    error: None,
                    exists: None,
                };
            }
            Err(e) => {
                eprintln!("  ⚠️ Error checking gtk-launch status: {}", e);
            }
        }
    }

    // Fallback: Try to find and execute the desktop entry directly
    eprintln!("  [2] Trying to find desktop file...");

    let desktop_dirs = vec![
        format!("{}/.local/share/applications", std::env::var("HOME").unwrap_or_default()),
        "/usr/local/share/applications".to_string(),
        "/usr/share/applications".to_string(),
    ];

    for dir in desktop_dirs {
        let desktop_file = format!("{}/{}.desktop", dir, desktop_entry);
        eprintln!("    Checking: {}", desktop_file);

        if let Ok(content) = fs::read_to_string(&desktop_file) {
            eprintln!("    ✓ Found desktop file");

            // Parse the desktop file more carefully
            for line in content.lines() {
                if line.starts_with("Exec=") && line.len() > 5 {
                    let exec_line = &line[5..];

                    // Handle desktop entry codes like %U, %F, %i, %c, %k, etc.
                    let exec_line = exec_line
                        .replace("%U", "")
                        .replace("%F", "")
                        .replace("%u", "")
                        .replace("%f", "")
                        .replace("%i", "")
                        .replace("%c", "")
                        .replace("%k", "")
                        .replace("%v", "");

                    let exec_line = exec_line.trim();
                    if exec_line.is_empty() {
                        continue;
                    }

                    let parts: Vec<&str> = exec_line.split_whitespace().collect();
                    if parts.is_empty() {
                        continue;
                    }

                    let exec_path = parts[0];
                    eprintln!("    Exec path: {}", exec_path);

                    // Try to execute it - be more permissive for direct execution
                    // First check if it exists and is executable
                    if let Ok(metadata) = std::fs::metadata(exec_path) {
                        #[cfg(unix)]
                        {
                            use std::os::unix::fs::PermissionsExt;
                            if metadata.permissions().mode() & 0o111 == 0 {
                                eprintln!("    ⚠️ Not executable: {}", exec_path);
                                continue;
                            }
                        }

                        eprintln!("    Launching: {} {:?}", exec_path, parts[1..].to_vec());

                        let result = Command::new(exec_path)
                            .args(&parts[1..])
                            .spawn();

                        match result {
                            Ok(_child) => {
                                // Detach from parent - don't wait for it, don't kill it!
                                eprintln!("  ✓ Application launched successfully from desktop file");
                                return Response {
                                    success: true,
                                    output: Some(format!("✓ GUI app '{}' launched (from desktop file)", desktop_entry)),
                                    error: None,
                                    exists: None,
                                };
                            }
                            Err(e) => {
                                eprintln!("    ⚠️ Failed to spawn: {}", e);
                            }
                        }
                    } else {
                        eprintln!("    ⚠️ Executable not found or not readable: {}", exec_path);
                    }
                }
            }
        }
    }

    // Last resort: Try to run it directly as a command if it's in PATH
    eprintln!("  [3] Trying direct execution in PATH...");
    let which_result = Command::new("which")
        .arg(desktop_entry)
        .output();

    if let Ok(result) = which_result {
        if result.status.success() {
            let cmd_path = String::from_utf8_lossy(&result.stdout).trim().to_string();
            if !cmd_path.is_empty() {
                eprintln!("    Found in PATH: {}", cmd_path);

                let spawn_result = Command::new(&cmd_path)
                    .spawn();

                if let Ok(_child) = spawn_result {
                    eprintln!("  ✓ Application launched directly from PATH");
                    return Response {
                        success: true,
                        output: Some(format!("✓ GUI app '{}' launched directly", desktop_entry)),
                        error: None,
                        exists: None,
                    };
                }
            }
        }
    }

    eprintln!("❌ All launch methods failed for: {}", desktop_entry);
    Response {
        success: false,
        output: None,
        error: Some(format!("Failed to launch GUI app '{}' - not found or not accessible", desktop_entry)),
        exists: None,
    }
}



fn detect_terminal() -> Response {
    let terminals = vec![
        ("foot", vec!["-e", "bash", "-c"]),
        ("kitty", vec!["-e", "bash", "-c"]),
        ("konsole", vec!["-e", "bash", "-c"]),
        ("gnome-terminal", vec!["--", "bash", "-c"]),
        ("xfce4-terminal", vec!["-e", "bash", "-c"]),
        ("alacritty", vec!["-e", "bash", "-c"]),
        ("terminator", vec!["-e", "bash", "-c"]),
    ];

    for (term, args) in terminals {
        let check = Command::new("which")
            .arg(term)
            .output();

        if let Ok(result) = check {
            if result.status.success() {
                let response_data = serde_json::json!({
                    "terminal": term,
                    "args": args
                });
                return Response {
                    success: true,
                    output: Some(response_data.to_string()),
                    error: None,
                    exists: Some(true),
                };
            }
        }
    }

    Response {
        success: false,
        output: None,
        error: Some("No terminal emulator found".to_string()),
        exists: Some(false),
    }
}

fn launch_fallback_terminal(data: &serde_json::Value) -> Response {
    let command = match data.get("command").and_then(|v| v.as_str()) {
        Some(cmd) => cmd,
        None => return Response {
            success: false,
            output: None,
            error: Some("Missing command parameter".to_string()),
            exists: None,
        },
    };

    // Validate command
    if command.trim().is_empty() {
        return Response {
            success: false,
            output: None,
            error: Some("Command cannot be empty".to_string()),
            exists: None,
        };
    }

    if command.contains('\0') {
        return Response {
            success: false,
            output: None,
            error: Some("Invalid command: contains null byte".to_string()),
            exists: None,
        };
    }

    if command.len() > 8192 {
        return Response {
            success: false,
            output: None,
            error: Some("Command too long".to_string()),
            exists: None,
        };
    }

    let terminal = data.get("terminal")
        .and_then(|v| v.as_str())
        .unwrap_or("foot");

    // Validate terminal name (only allow known terminals)
    let allowed_terminals = ["foot", "kitty", "konsole", "gnome-terminal",
                            "xfce4-terminal", "alacritty", "terminator"];
    if !allowed_terminals.contains(&terminal) {
        return Response {
            success: false,
            output: None,
            error: Some("Invalid terminal specified".to_string()),
            exists: None,
        };
    }

    let terminal_cmd = format!("{}; echo ''; echo 'Press Enter to close...'; read", command);

    let result = Command::new("setsid")
        .arg(terminal)
        .arg("-e")
        .arg("bash")
        .arg("-c")
        .arg(&terminal_cmd)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();

    match result {
        Ok(_) => Response {
            success: true,
            output: Some(format!("✓ Command launched in new {} terminal", terminal)),
            error: None,
            exists: None,
        },
        Err(e) => Response {
            success: false,
            output: None,
            error: Some(format!("Failed to launch terminal: {}", e)),
            exists: None,
        },
    }
}

fn execute_command_smart(data: &serde_json::Value, config: &Config) -> Response {
    let command = match data.get("command").and_then(|v| v.as_str()) {
        Some(cmd) => cmd,
        None => return Response {
            success: false,
            output: None,
            error: Some("Missing command parameter".to_string()),
            exists: None,
        },
    };

    // Validate command
    if command.trim().is_empty() {
        return Response {
            success: false,
            output: None,
            error: Some("Command cannot be empty".to_string()),
            exists: None,
        };
    }

    // Check for null bytes
    if command.contains('\0') {
        return Response {
            success: false,
            output: None,
            error: Some("Invalid command: contains null byte".to_string()),
            exists: None,
        };
    }

    // Limit command length
    if command.len() > 8192 {
        return Response {
            success: false,
            output: None,
            error: Some("Command too long (max 8192 characters)".to_string()),
            exists: None,
        };
    }

    let session = data.get("session")
        .and_then(|v| v.as_str())
        .unwrap_or("archy_session");

    // Extract app name
    let parts: Vec<&str> = command.split_whitespace().collect();
    if parts.is_empty() {
        return Response {
            success: false,
            output: None,
            error: Some("Empty command".to_string()),
            exists: None,
        };
    }

    let app_name = parts[0].split('/').last().unwrap_or(parts[0]);

    // Check if it's a GUI app
    let desktop_entry_data = serde_json::json!({"app_name": app_name});
    let desktop_result = find_desktop_entry(&desktop_entry_data);

    if desktop_result.success && desktop_result.exists == Some(true) {
        // It's a GUI app - launch detached
        if let Some(desktop_entry) = desktop_result.output {
            return launch_gui_app(&serde_json::json!({"desktop_entry": desktop_entry}));
        }
    }

    // Check if tmux is available
    let tmux_check = Command::new("which")
        .arg("tmux")
        .output();

    if let Ok(result) = tmux_check {
        if result.status.success() {
            // Check if session exists, create if needed
            let session_check = Command::new("tmux")
                .args(&["has-session", "-t", session])
                .status();

            if let Ok(status) = session_check {
                if !status.success() {
                    // Create session
                    let _ = Command::new("tmux")
                        .args(&["new-session", "-d", "-s", session])
                        .status();
                }
            }

            // Execute in tmux using tmux module directly
            match tmux::send_keys(session, command) {
                Ok(_) => {
                    // Ensure terminal window is open
                    let foot_check = is_foot_running();
                    if foot_check.exists != Some(true) {
                        let _ = open_terminal(config);
                        return Response {
                            success: true,
                            output: Some(format!("✓ Terminal reopened and command sent: {}", command)),
                            error: None,
                            exists: None,
                        };
                    }

                    return Response {
                        success: true,
                        output: Some(format!("✓ Command sent to persistent terminal session: {}", command)),
                        error: None,
                        exists: None,
                    };
                }
                Err(_) => {
                    // Fall through to terminal launch fallback
                }
            }
        }
    }

    // Fallback to new terminal window
    let terminal_result = detect_terminal();
    if terminal_result.success {
        if let Some(terminal_info) = terminal_result.output {
            if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&terminal_info) {
                if let Some(terminal) = parsed.get("terminal").and_then(|v| v.as_str()) {
                    return launch_fallback_terminal(&serde_json::json!({
                        "command": command,
                        "terminal": terminal
                    }));
                }
            }
        }
    }

    Response {
        success: false,
        output: None,
        error: Some("No execution method available".to_string()),
        exists: None,
    }
}


/// Handle execute_analyzed action - executes command, waits, and returns analyzed output
fn handle_execute_analyzed(stream: &mut UnixStream, data: &serde_json::Value) -> std::io::Result<()> {
    let command = match data.get("command").and_then(|v| v.as_str()) {
        Some(cmd) => cmd,
        None => {
            let output = DisplayOutput::from_error("", "Missing command parameter");
            return send_json_response(stream, &output);
        }
    };

    let session = data.get("session")
        .and_then(|v| v.as_str())
        .unwrap_or("archy_session");

    // Execute command in tmux
    let exec_result = Command::new("tmux")
        .args(&["send-keys", "-t", session, command, "C-m"])
        .output();

    if let Err(e) = exec_result {
        let output = DisplayOutput::from_error(command, &e.to_string());
        return send_json_response(stream, &output);
    }

    // Wait for command completion
    let wait_data = serde_json::json!({
        "session": session,
        "command": command,
        "max_wait": data.get("max_wait").and_then(|v| v.as_u64()).unwrap_or(600),
        "interval_ms": data.get("interval_ms").and_then(|v| v.as_u64()).unwrap_or(500)
    });

    let wait_result = wait_for_command_completion(&wait_data);

    let display_output = if wait_result.success {
        if let Some(raw_output) = wait_result.output {
            DisplayOutput::from_command_output(command, &raw_output, 0)
        } else {
            DisplayOutput::from_error(command, "No output captured")
        }
    } else {
        let partial = wait_result.output.unwrap_or_default();
        DisplayOutput::from_timeout(command, &partial)
    };

    send_json_response(stream, &display_output)
}

/// Handle capture_analyzed action - captures current output and returns analyzed version
fn handle_capture_analyzed(stream: &mut UnixStream, data: &serde_json::Value) -> std::io::Result<()> {
    let lines = data.get("lines")
        .and_then(|v| v.as_i64())
        .unwrap_or(100);

    let session = data.get("session")
        .and_then(|v| v.as_str())
        .unwrap_or("archy_session");

    let command = data.get("command")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    // Capture output from tmux
    let output = Command::new("tmux")
        .args(&["capture-pane", "-pt", session, "-S", &format!("-{}", lines)])
        .output();

    let display_output = match output {
        Ok(out) if out.status.success() => {
            let raw_output = String::from_utf8_lossy(&out.stdout).to_string();
            DisplayOutput::from_command_output(command, &raw_output, 0)
        }
        Ok(_) => {
            DisplayOutput::from_error(command, "Failed to capture output")
        }
        Err(e) => {
            DisplayOutput::from_error(command, &e.to_string())
        }
    };

    send_json_response(stream, &display_output)
}

/// Handle execute_and_wait - executes command, waits for completion, then analyzes
/// This is the SMART way - no hardcoded timeouts!
fn handle_execute_and_wait(stream: &mut UnixStream, data: &serde_json::Value) -> std::io::Result<()> {
    let command = match data.get("command").and_then(|v| v.as_str()) {
        Some(cmd) => cmd,
        None => {
            let output = DisplayOutput::from_error("", "Missing command parameter");
            return send_json_response(stream, &output);
        }
    };

    let session = data.get("session")
        .and_then(|v| v.as_str())
        .unwrap_or("archy_session");

    // CRITICAL: Ensure tmux session exists before sending commands
    // This prevents "no server running" errors that cause broken pipes
    if !tmux::has_session(session) {
        eprintln!("⚠️ Session {} doesn't exist, creating...", session);
        if let Err(e) = tmux::new_session(session) {
            eprintln!("❌ Failed to create session: {}", e);
            let output = DisplayOutput::from_error(command, &format!("Failed to create tmux session: {}", e));
            return send_json_response(stream, &output);
        }
        // Brief wait for session to initialize
        std::thread::sleep(std::time::Duration::from_millis(100));
    }

    // Execute command in tmux
    let exec_result = Command::new("tmux")
        .args(&["send-keys", "-t", session, command, "C-m"])
        .output();

    if let Err(e) = exec_result {
        let output = DisplayOutput::from_error(command, &e.to_string());
        return send_json_response(stream, &output);
    }

    // Wait for command completion using smart prompt detection
    let wait_data = serde_json::json!({
        "session": session,
        "command": command,
        "max_wait": data.get("max_wait").and_then(|v| v.as_u64()).unwrap_or(300),  // Default 5 minutes
        "interval_ms": data.get("interval_ms").and_then(|v| v.as_u64()).unwrap_or(500)  // Check every 500ms
    });

    let wait_result = wait_for_command_completion(&wait_data);

    let display_output = if wait_result.success {
        if let Some(raw_output) = wait_result.output {
            DisplayOutput::from_command_output(command, &raw_output, 0)
        } else {
            DisplayOutput::from_error(command, "No output captured")
        }
    } else {
        let partial = wait_result.output.unwrap_or_default();
        DisplayOutput::from_timeout(command, &partial)
    };

    send_json_response(stream, &display_output)
}

