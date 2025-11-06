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
    let mut buffer = vec![0; config.max_buffer_size];

    let size = stream.read(&mut buffer)?;
    let request: Request = match serde_json::from_slice(&buffer[..size]) {
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
        "open_terminal" => open_terminal(),
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
        "execute_smart" => execute_command_smart(&request.data),
        _ => response::error("Unknown action".to_string()),
    };

    let json = serde_json::to_string(&response).unwrap();
    stream.write_all(json.as_bytes())?;

    Ok(())
}

fn execute_command(data: &Value, config: &Config) -> Response {
    // Extract parameters using helpers
    let command = match params::extract_string(data, "command") {
        Ok(cmd) => cmd,
        Err(e) => return response::error(e),
    };

    let session = config.get_session(data);

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



fn open_terminal() -> Response {
    let session = "archy_session";

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

    // Check if a foot terminal is already running for this session
    let check_foot = Command::new("pgrep")
        .args(&["-f", &format!("foot.*tmux.*attach.*{}", session)])
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

    // First close any foot terminals
    let _ = Command::new("pkill")
        .args(&["-f", &format!("foot.*{}", session)])
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
                let info = String::from_utf8_lossy(&result.stdout).trim().to_string();
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

    let desktop_dirs = vec![
        format!("{}/.local/share/applications", std::env::var("HOME").unwrap_or_default()),
        "/usr/local/share/applications".to_string(),
        "/usr/share/applications".to_string(),
        "/usr/share/applications/kde4".to_string(),
        "/usr/share/applications/kde5".to_string(),
        format!("{}/.config/applications", std::env::var("HOME").unwrap_or_default()),
        "/opt/applications".to_string(),
    ];

    for dir in desktop_dirs {
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
                            // Check if Exec line contains the exact app name with proper word boundaries
                            for line in content.lines() {
                                if line.starts_with("Exec=") {
                                    let exec_value = &line[5..]; // Skip "Exec="

                                    // Split by space to get the actual command
                                    let parts: Vec<&str> = exec_value.split_whitespace().collect();
                                    if parts.is_empty() {
                                        continue;
                                    }

                                    // Get the command part (may include path)
                                    let command = parts[0];

                                    // Extract just the binary name from the path
                                    let binary_name = if command.contains('/') {
                                        command.rsplit('/').next().unwrap_or(command)
                                    } else {
                                        command
                                    };

                                    // Exact match only (case-insensitive)
                                    if binary_name.eq_ignore_ascii_case(app_name) {
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

                            // Check if desktop filename matches exactly
                            if let Some(stem) = filepath.file_stem() {
                                if stem.to_string_lossy().eq_ignore_ascii_case(app_name) {
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

    Response {
        success: true,
        output: None,
        error: None,
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

    let check_interval_ms = data.get("interval_ms")
        .and_then(|v| v.as_u64())
        .unwrap_or(500) as u64; // Default 500ms

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
                let current_output = String::from_utf8_lossy(&out.stdout).to_string();

                // Check if output has stabilized
                if current_output == last_output {
                    stable_count += 1;
                } else {
                    stable_count = 0;
                    last_output = current_output.clone();
                }

                // Look for prompt in last line
                let lines: Vec<&str> = current_output.trim().split('\n').collect();
                if let Some(last_line) = lines.last() {
                    // Check for common prompt indicators
                    let has_prompt = last_line.contains('$') ||
                                   last_line.contains('#') ||
                                   last_line.contains('❯');

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
    let json = serde_json::to_string(&response).unwrap();
    stream.write_all(json.as_bytes())
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

    // Try gtk-launch first
    let gtk_result = Command::new("gtk-launch")
        .arg(desktop_entry)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();

    if gtk_result.is_ok() {
        return Response {
            success: true,
            output: Some(format!("✓ GUI app '{}' launched via gtk-launch", desktop_entry)),
            error: None,
            exists: None,
        };
    }

    // Fallback: Try to find and execute the desktop entry directly
    let desktop_dirs = vec![
        format!("{}/.local/share/applications", std::env::var("HOME").unwrap_or_default()),
        "/usr/local/share/applications".to_string(),
        "/usr/share/applications".to_string(),
    ];

    for dir in desktop_dirs {
        let desktop_file = format!("{}/{}.desktop", dir, desktop_entry);
        if let Ok(content) = fs::read_to_string(&desktop_file) {
            for line in content.lines() {
                if line.starts_with("Exec=") {
                    let exec_line = &line[5..];
                    let parts: Vec<&str> = exec_line.split_whitespace().collect();
                    if !parts.is_empty() {
                        let result = Command::new(parts[0])
                            .args(&parts[1..])
                            .stdout(std::process::Stdio::null())
                            .stderr(std::process::Stdio::null())
                            .spawn();

                        if result.is_ok() {
                            return Response {
                                success: true,
                                output: Some(format!("✓ GUI app '{}' launched", desktop_entry)),
                                error: None,
                                exists: None,
                            };
                        }
                    }
                }
            }
        }
    }

    Response {
        success: false,
        output: None,
        error: Some("Failed to launch GUI app".to_string()),
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

    let terminal = data.get("terminal")
        .and_then(|v| v.as_str())
        .unwrap_or("foot");

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

fn execute_command_smart(data: &serde_json::Value) -> Response {
    let command = match data.get("command").and_then(|v| v.as_str()) {
        Some(cmd) => cmd,
        None => return Response {
            success: false,
            output: None,
            error: Some("Missing command parameter".to_string()),
            exists: None,
        },
    };

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
                        let _ = open_terminal();
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
            let json = serde_json::to_string(&output).unwrap();
            stream.write_all(json.as_bytes())?;
            return Ok(());
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
        let json = serde_json::to_string(&output).unwrap();
        stream.write_all(json.as_bytes())?;
        return Ok(());
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

    let json = serde_json::to_string(&display_output).unwrap();
    stream.write_all(json.as_bytes())?;
    Ok(())
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

    let json = serde_json::to_string(&display_output).unwrap();
    stream.write_all(json.as_bytes())?;
    Ok(())
}

/// Handle execute_and_wait - executes command, waits for completion, then analyzes
/// This is the SMART way - no hardcoded timeouts!
fn handle_execute_and_wait(stream: &mut UnixStream, data: &serde_json::Value) -> std::io::Result<()> {
    let command = match data.get("command").and_then(|v| v.as_str()) {
        Some(cmd) => cmd,
        None => {
            let output = DisplayOutput::from_error("", "Missing command parameter");
            let json = serde_json::to_string(&output).unwrap();
            stream.write_all(json.as_bytes())?;
            return Ok(());
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
        let json = serde_json::to_string(&output).unwrap();
        stream.write_all(json.as_bytes())?;
        return Ok(());
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

    let json = serde_json::to_string(&display_output).unwrap();
    stream.write_all(json.as_bytes())?;
    Ok(())
}

