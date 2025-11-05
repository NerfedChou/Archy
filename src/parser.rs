// parser.rs - Universal Command Output Parser
// Detects formats, extracts findings, generates summaries

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use regex::Regex;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Importance {
    Critical,
    High,
    Medium,
    Low,
    Info,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Finding {
    pub category: String,
    pub message: String,
    pub importance: Importance,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Metadata {
    pub line_count: usize,
    pub byte_count: usize,
    pub duration_ms: Option<u64>,
    pub format_detected: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ParsedOutput {
    pub raw: String,
    pub structured: Value,
    pub findings: Vec<Finding>,
    pub summary: String,
    pub metadata: Metadata,
}

/// Detect the format of command output
pub fn detect_format(output: &str, command: &str) -> String {
    let lower_cmd = command.to_lowercase();
    let lower_output = output.to_lowercase();

    // Check by command name first
    if lower_cmd.contains("nmap") {
        return "nmap".to_string();
    } else if lower_cmd.contains("netstat") || lower_cmd.contains("ss") {
        return "network_table".to_string();
    } else if lower_cmd.contains("ps") || lower_cmd.contains("top") {
        return "process_table".to_string();
    } else if lower_cmd.contains("ls") && (lower_cmd.contains("-l") || lower_cmd.contains("--long")) {
        return "ls_long".to_string();
    } else if lower_cmd.contains("ip") && (lower_cmd.contains("addr") || lower_cmd.contains("ip a") || lower_cmd == "ip a") {
        return "ip_addr".to_string();
    } else if lower_cmd.contains("systemctl") {
        return "systemctl".to_string();
    } else if lower_cmd.contains("df") {
        return "disk_usage".to_string();
    } else if lower_cmd.contains("lsblk") {
        return "block_devices".to_string();
    } else if lower_cmd.contains("journalctl") {
        return "journalctl".to_string();
    }

    // Check by content patterns
    if lower_output.contains("starting nmap") || lower_output.contains("host is up") {
        return "nmap".to_string();
    } else if lower_output.contains("tcp") && lower_output.contains("established") {
        return "network_table".to_string();
    } else if output.lines().filter(|l| l.contains("|") || l.contains("│")).count() > 3 {
        return "table".to_string();
    } else if output.starts_with('{') || output.starts_with('[') {
        return "json".to_string();
    }

    "plain_text".to_string()
}

/// Parse intelligently based on format
pub fn parse_intelligently(raw: &str, command: &str) -> ParsedOutput {
    let format = detect_format(raw, command);
    let line_count = raw.lines().count();
    let byte_count = raw.len();

    let metadata = Metadata {
        line_count,
        byte_count,
        duration_ms: None,
        format_detected: format.clone(),
    };

    match format.as_str() {
        "nmap" => parse_nmap(raw, metadata),
        "network_table" => parse_network_table(raw, metadata),
        "process_table" => parse_process_table(raw, metadata),
        "ls_long" => parse_ls_long(raw, metadata),
        "ip_addr" => parse_ip_addr(raw, metadata),
        "systemctl" => parse_systemctl(raw, metadata),
        "disk_usage" => parse_disk_usage(raw, metadata),
        "journalctl" => parse_journalctl(raw, metadata),
        "json" => parse_json(raw, metadata),
        _ => parse_generic(raw, metadata),
    }
}

/// Parse nmap output
fn parse_nmap(raw: &str, metadata: Metadata) -> ParsedOutput {
    let mut findings = Vec::new();
    let mut hosts_up = 0;
    let mut open_ports = Vec::new();
    let mut services = Vec::new();

    for line in raw.lines() {
        let lower = line.to_lowercase();

        if lower.contains("host is up") {
            hosts_up += 1;
        }

        if line.contains("/tcp") && lower.contains("open") {
            // Extract port and service
            let parts: Vec<&str> = line.split_whitespace().collect();
            if let Some(port_part) = parts.first() {
                open_ports.push(port_part.to_string());
                if parts.len() > 2 {
                    services.push(parts[2].to_string());
                }
            }
        }
    }

    if hosts_up > 0 {
        findings.push(Finding {
            category: "Host Count".to_string(),
            message: format!("Found {} active host(s) on network", hosts_up),
            importance: if hosts_up > 10 { Importance::High } else { Importance::Medium },
        });
    }

    if !open_ports.is_empty() {
        findings.push(Finding {
            category: "Open Ports".to_string(),
            message: format!("Detected {} open port(s): {}", open_ports.len(), open_ports.join(", ")),
            importance: Importance::High,
        });
    }

    if !services.is_empty() {
        findings.push(Finding {
            category: "Services".to_string(),
            message: format!("Services detected: {}", services.join(", ")),
            importance: Importance::Info,
        });
    }

    let structured = json!({
        "hosts_up": hosts_up,
        "open_ports": open_ports,
        "services": services,
        "scan_type": "nmap"
    });

    let summary = if hosts_up > 0 {
        format!("Network scan complete - {} hosts active, {} open ports", hosts_up, open_ports.len())
    } else {
        "Network scan complete - no hosts detected".to_string()
    };

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary,
        metadata,
    }
}

/// Parse network table (netstat/ss output)
fn parse_network_table(raw: &str, metadata: Metadata) -> ParsedOutput {
    let mut findings = Vec::new();
    let mut connections = Vec::new();
    let mut established = 0;
    let mut listening = 0;

    for line in raw.lines() {
        let lower = line.to_lowercase();

        if lower.contains("established") {
            established += 1;
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 5 {
                connections.push(json!({
                    "protocol": parts.get(0).unwrap_or(&""),
                    "local": parts.get(3).unwrap_or(&""),
                    "remote": parts.get(4).unwrap_or(&""),
                    "state": "ESTABLISHED"
                }));
            }
        } else if lower.contains("listen") {
            listening += 1;
        }
    }

    if established > 0 {
        findings.push(Finding {
            category: "Active Connections".to_string(),
            message: format!("{} established connection(s)", established),
            importance: if established > 50 { Importance::High } else { Importance::Info },
        });
    }

    if listening > 0 {
        findings.push(Finding {
            category: "Listening Ports".to_string(),
            message: format!("{} listening port(s)", listening),
            importance: Importance::Info,
        });
    }

    let structured = json!({
        "connections": connections,
        "established_count": established,
        "listening_count": listening
    });

    let summary = format!("{} established, {} listening", established, listening);

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary,
        metadata,
    }
}

/// Parse process table output
fn parse_process_table(raw: &str, metadata: Metadata) -> ParsedOutput {
    let mut findings = Vec::new();
    let process_count = raw.lines().filter(|l| !l.trim().is_empty() && !l.to_lowercase().contains("pid")).count();

    if process_count > 0 {
        findings.push(Finding {
            category: "Process Count".to_string(),
            message: format!("{} process(es) listed", process_count),
            importance: Importance::Info,
        });
    }

    let structured = json!({
        "process_count": process_count,
        "type": "process_list"
    });

    let summary = format!("{} processes", process_count);

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary,
        metadata,
    }
}

/// Parse ls -l output
fn parse_ls_long(raw: &str, metadata: Metadata) -> ParsedOutput {
    let mut findings = Vec::new();
    let mut files = 0;
    let mut directories = 0;
    let mut total_size: u64 = 0;

    for line in raw.lines() {
        if line.starts_with('d') {
            directories += 1;
        } else if line.starts_with('-') {
            files += 1;
            // Try to extract size (5th column typically)
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() > 4 {
                if let Ok(size) = parts[4].parse::<u64>() {
                    total_size += size;
                }
            }
        }
    }

    if files > 0 || directories > 0 {
        findings.push(Finding {
            category: "Directory Contents".to_string(),
            message: format!("{} file(s), {} director(ies)", files, directories),
            importance: Importance::Info,
        });
    }

    let structured = json!({
        "files": files,
        "directories": directories,
        "total_size_bytes": total_size
    });

    let summary = format!("{} files, {} directories", files, directories);

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary,
        metadata,
    }
}

/// Parse ip addr output
fn parse_ip_addr(raw: &str, metadata: Metadata) -> ParsedOutput {
    let mut findings = Vec::new();
    let mut interfaces = Vec::new();
    let mut ipv4_addresses = Vec::new();

    let re_interface = Regex::new(r"^\d+:\s+(\S+):").unwrap();
    let re_ipv4 = Regex::new(r"inet\s+(\d+\.\d+\.\d+\.\d+/\d+)").unwrap();

    for line in raw.lines() {
        if let Some(cap) = re_interface.captures(line) {
            if let Some(iface) = cap.get(1) {
                interfaces.push(iface.as_str().to_string());
            }
        }

        if let Some(cap) = re_ipv4.captures(line) {
            if let Some(ip) = cap.get(1) {
                ipv4_addresses.push(ip.as_str().to_string());
            }
        }
    }

    if !interfaces.is_empty() {
        findings.push(Finding {
            category: "Network Interfaces".to_string(),
            message: format!("{} interface(s) detected: {}", interfaces.len(), interfaces.join(", ")),
            importance: Importance::Info,
        });
    }

    if !ipv4_addresses.is_empty() {
        findings.push(Finding {
            category: "IP Addresses".to_string(),
            message: format!("{} IPv4 address(es): {}", ipv4_addresses.len(), ipv4_addresses.join(", ")),
            importance: Importance::Info,
        });
    }

    let structured = json!({
        "interfaces": interfaces,
        "ipv4_addresses": ipv4_addresses
    });

    let summary = format!("{} interfaces, {} IPs", interfaces.len(), ipv4_addresses.len());

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary,
        metadata,
    }
}

/// Parse systemctl output
fn parse_systemctl(raw: &str, metadata: Metadata) -> ParsedOutput {
    let mut findings = Vec::new();
    let mut active_services = Vec::new();
    let mut failed_services = Vec::new();

    for line in raw.lines() {
        let lower = line.to_lowercase();
        let parts: Vec<&str> = line.split_whitespace().collect();

        // Extract service name (usually first column before .service)
        if let Some(first) = parts.first() {
            if first.ends_with(".service") || first.contains(".service") {
                let service_name = first.replace(".service", "");

                if lower.contains("active") && lower.contains("running") {
                    active_services.push(service_name.clone());
                } else if lower.contains("failed") {
                    failed_services.push(service_name.clone());
                }
            }
        }
    }

    if !failed_services.is_empty() {
        let service_list = failed_services.join(", ");
        findings.push(Finding {
            category: "Failed Services".to_string(),
            message: format!("{} service(s) in failed state: {}", failed_services.len(), service_list),
            importance: Importance::High,
        });
    }

    if !active_services.is_empty() {
        findings.push(Finding {
            category: "Active Services".to_string(),
            message: format!("{} service(s) active and running", active_services.len()),
            importance: Importance::Info,
        });
    }

    let structured = json!({
        "active_count": active_services.len(),
        "failed_count": failed_services.len(),
        "active_services": active_services,
        "failed_services": failed_services
    });

    let summary = if !failed_services.is_empty() {
        format!("{} failed services: {}", failed_services.len(), failed_services.join(", "))
    } else {
        format!("{} active, {} failed", active_services.len(), failed_services.len())
    };

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary,
        metadata,
    }
}

/// Parse disk usage output (df)
fn parse_disk_usage(raw: &str, metadata: Metadata) -> ParsedOutput {
    let mut findings = Vec::new();
    let mut filesystems = Vec::new();

    for line in raw.lines() {
        if line.contains('%') {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 5 {
                if let Some(usage_str) = parts.iter().find(|p| p.ends_with('%')) {
                    if let Ok(usage) = usage_str.trim_end_matches('%').parse::<u8>() {
                        filesystems.push(json!({
                            "filesystem": parts[0],
                            "size": parts.get(1).unwrap_or(&""),
                            "used": parts.get(2).unwrap_or(&""),
                            "available": parts.get(3).unwrap_or(&""),
                            "usage_percent": usage,
                            "mount": parts.get(5).unwrap_or(&"")
                        }));

                        if usage > 90 {
                            findings.push(Finding {
                                category: "Disk Space Critical".to_string(),
                                message: format!("{} is {}% full", parts[0], usage),
                                importance: Importance::Critical,
                            });
                        } else if usage > 80 {
                            findings.push(Finding {
                                category: "Disk Space Warning".to_string(),
                                message: format!("{} is {}% full", parts[0], usage),
                                importance: Importance::High,
                            });
                        }
                    }
                }
            }
        }
    }

    let structured = json!({
        "filesystems": filesystems
    });

    let summary = format!("{} filesystem(s) checked", filesystems.len());

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary,
        metadata,
    }
}

/// Parse JSON output
fn parse_json(raw: &str, metadata: Metadata) -> ParsedOutput {
    let structured = match serde_json::from_str::<Value>(raw) {
        Ok(json) => json,
        Err(_) => json!({ "raw": raw }),
    };

    let findings = vec![Finding {
        category: "Format".to_string(),
        message: "JSON data detected and parsed".to_string(),
        importance: Importance::Info,
    }];

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary: "JSON data parsed successfully".to_string(),
        metadata,
    }
}

/// Parse journalctl output - extract errors, warnings, and service issues
fn parse_journalctl(raw: &str, metadata: Metadata) -> ParsedOutput {
    let mut findings = Vec::new();
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    let mut failed_services = std::collections::HashSet::new();

    for line in raw.lines() {
        let lower = line.to_lowercase();

        // Detect error levels
        if lower.contains("error") || lower.contains("failed") || lower.contains("fail") {
            errors.push(line.to_string());

            // Extract service names
            if lower.contains(".service") {
                if let Some(start) = line.find(char::is_alphabetic) {
                    if let Some(end) = line[start..].find(".service") {
                        let service = &line[start..start+end];
                        failed_services.insert(service.to_string());
                    }
                }
            }
        } else if lower.contains("warning") || lower.contains("warn") {
            warnings.push(line.to_string());
        }
    }

    // Generate findings
    if !errors.is_empty() {
        findings.push(Finding {
            category: "Errors".to_string(),
            message: format!("{} error(s) found in logs", errors.len()),
            importance: Importance::High,
        });
    }

    if !warnings.is_empty() {
        findings.push(Finding {
            category: "Warnings".to_string(),
            message: format!("{} warning(s) found in logs", warnings.len()),
            importance: Importance::Medium,
        });
    }

    if !failed_services.is_empty() {
        let service_list: Vec<String> = failed_services.iter().cloned().collect();
        findings.push(Finding {
            category: "Failed Services".to_string(),
            message: format!("Services with issues: {}", service_list.join(", ")),
            importance: Importance::High,
        });
    }

    let structured = json!({
        "error_count": errors.len(),
        "warning_count": warnings.len(),
        "failed_services": failed_services.iter().cloned().collect::<Vec<_>>(),
        "errors": errors.iter().take(10).cloned().collect::<Vec<_>>(),
        "warnings": warnings.iter().take(10).cloned().collect::<Vec<_>>(),
    });

    let summary = if !errors.is_empty() || !warnings.is_empty() {
        format!("{} error(s), {} warning(s) in logs", errors.len(), warnings.len())
    } else {
        "No errors or warnings found".to_string()
    };

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary,
        metadata,
    }
}

/// Generic parser for unknown formats
fn parse_generic(raw: &str, metadata: Metadata) -> ParsedOutput {
    let findings = Vec::new();

    let structured = json!({
        "type": "plain_text",
        "line_count": metadata.line_count
    });

    let summary = format!("Output captured ({} lines)", metadata.line_count);

    ParsedOutput {
        raw: raw.to_string(),
        structured,
        findings,
        summary,
        metadata,
    }
}

