#!/usr/bin/env python3
"""
ULTIMATE DEBUG: Complete Real-Time Data Inspector
Shows EVERYTHING with ACTUAL data flowing through Archy
"""

import sys
import json
import time
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from rust_executor import RustExecutor

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def show_real_time_execution(command, description):
    """Execute a command and show ALL the real data"""
    print(f"\n{'='*80}")
    print(f"{Colors.BOLD}{Colors.CYAN} LIVE EXECUTION: {description} {Colors.END}")
    print(f"{'='*80}")
    print(f"{Colors.YELLOW}Command:{Colors.END} {command}")
    print(f"{'─'*80}\n")

    executor = RustExecutor()

    # Stage 1: Show what we're sending
    print(f"{Colors.GREEN}[1] 🐍 Python → Rust{Colors.END}")
    request = {
        "action": "execute_and_wait",
        "data": {
            "command": command,
            "session": "archy_session",
            "max_wait": 30
        }
    }
    request_json = json.dumps(request, indent=2)
    print(f"    Sending: {len(request_json)} bytes")
    print(f"{Colors.BLUE}    {request_json[:200]}...{Colors.END}" if len(request_json) > 200 else f"{Colors.BLUE}    {request_json}{Colors.END}")

    # Stage 2: Execute and time it
    print(f"\n{Colors.RED}[2] 🦀 Rust Executing...{Colors.END}")
    start_time = time.time()
    result = executor.execute_and_wait(command, max_wait=30)
    elapsed = time.time() - start_time
    print(f"    ⏱️  Execution time: {Colors.BOLD}{elapsed:.3f}s{Colors.END}")

    # Stage 3: Show what we got back
    print(f"\n{Colors.GREEN}[3] 🦀 Rust → Python{Colors.END}")
    response_json = json.dumps(result)
    print(f"    Received: {Colors.BOLD}{len(response_json)} bytes{Colors.END}")

    # Stage 4: Dissect the REAL response
    print(f"\n{Colors.CYAN}[4] 📊 REAL DATA BREAKDOWN:{Colors.END}")
    print(f"{'─'*80}")

    # Basic info
    print(f"\n  {Colors.YELLOW}Status:{Colors.END}")
    print(f"    ✓ Success: {result.get('success')}")
    print(f"    ✓ Exit Code: {result.get('exit_code')}")
    print(f"    ✓ Status: {result.get('status')}")

    # Metadata
    if result.get('metadata'):
        meta = result['metadata']
        print(f"\n  {Colors.YELLOW}Metadata (REAL):{Colors.END}")
        print(f"    • Format detected: {meta.get('format_detected')}")
        print(f"    • Lines processed: {meta.get('line_count')}")
        print(f"    • Bytes processed: {meta.get('byte_count')}")
        if meta.get('duration_ms'):
            print(f"    • Duration: {meta.get('duration_ms')}ms")

    # Structured data
    if result.get('structured'):
        structured = result['structured']
        print(f"\n  {Colors.YELLOW}Structured Data (Parsed by Rust):{Colors.END}")
        print(f"    Fields: {list(structured.keys())}")

        # Show actual values
        for key, value in list(structured.items())[:5]:
            if isinstance(value, list):
                if len(value) > 0:
                    print(f"    • {key}: [{len(value)} items]")
                    # Show first few items
                    for item in value[:3]:
                        if isinstance(item, dict):
                            print(f"        → {json.dumps(item)[:60]}...")
                        else:
                            print(f"        → {str(item)[:60]}")
                else:
                    print(f"    • {key}: []")
            elif isinstance(value, dict):
                print(f"    • {key}: {json.dumps(value)[:80]}")
            else:
                print(f"    • {key}: {value}")

    # Findings
    if result.get('findings'):
        findings = result['findings']
        print(f"\n  {Colors.YELLOW}Findings (Detected by Rust):{Colors.END}")
        print(f"    Total: {len(findings)} insights")
        for i, finding in enumerate(findings, 1):
            importance = finding.get('importance', 'Medium')
            category = finding.get('category', 'Unknown')
            message = finding.get('message', '')
            emoji = '🔴' if importance == 'High' else '🟡' if importance == 'Medium' else '⚪'
            print(f"    {i}. {emoji} [{importance}] {category}")
            print(f"       {message[:75]}")

    # Summary
    if result.get('summary'):
        print(f"\n  {Colors.YELLOW}Summary:{Colors.END}")
        print(f"    {result['summary']}")

    # Display output (formatted)
    if result.get('display'):
        print(f"\n  {Colors.YELLOW}Formatted Display (What user sees):{Colors.END}")
        print(f"    {'─'*76}")
        lines = result['display'].split('\n')
        for line in lines[:15]:
            print(f"    {line}")
        if len(lines) > 15:
            print(f"    ... ({len(lines) - 15} more lines)")
        print(f"    {'─'*76}")

    print(f"\n{Colors.GREEN}{'='*80}{Colors.END}")
    print(f"{Colors.GREEN} ✅ ALL DATA ABOVE IS 100% REAL - CAPTURED LIVE! {Colors.END}")
    print(f"{Colors.GREEN}{'='*80}{Colors.END}\n")

    return result


def main():
    """Run comprehensive real-time debugging"""
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     ULTIMATE REAL-TIME DATA INSPECTOR                        ║
║                 Watch ACTUAL data flow through Archy LIVE                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

{Colors.CYAN}This script will:{Colors.END}
  • Execute REAL commands on your system
  • Capture ACTUAL data from Rust
  • Show REAL parsing results
  • Display TRUE performance metrics
  • Reveal COMPLETE data structures

{Colors.YELLOW}Every byte, every field, every timing - 100% REAL!{Colors.END}
""")

    input("Press Enter to start live data inspection...")

    tests = [
        {
            "command": "hostname && date && whoami",
            "description": "Basic System Info (REAL)"
        },
        {
            "command": "ip addr show | head -30",
            "description": "Network Configuration (REAL - watch Rust parse IPs!)"
        },
        {
            "command": "ls -la /tmp | head -20",
            "description": "Directory Listing (REAL - watch Rust parse files!)"
        },
        {
            "command": "ps aux | head -10",
            "description": "Process List (REAL - watch Rust count processes!)"
        }
    ]

    results = []
    for i, test in enumerate(tests, 1):
        print(f"\n{Colors.BOLD}{Colors.HEADER}═══ TEST {i}/{len(tests)} ═══{Colors.END}")

        if i > 1:
            response = input(f"\nRun next test? (Enter/skip): ").strip().lower()
            if response == 'skip':
                print(f"{Colors.YELLOW}  ⊘ Skipped{Colors.END}")
                continue

        result = show_real_time_execution(test['command'], test['description'])
        results.append(result)

        time.sleep(0.5)

    # Final summary
    print(f"\n{'='*80}")
    print(f"{Colors.BOLD}{Colors.CYAN} FINAL SUMMARY - ALL REAL DATA {Colors.END}")
    print(f"{'='*80}\n")

    total_bytes = sum(len(json.dumps(r)) for r in results)
    total_findings = sum(len(r.get('findings', [])) for r in results)
    total_structured_fields = sum(len(r.get('structured', {})) for r in results)

    print(f"{Colors.GREEN}Tests executed: {len(results)}{Colors.END}")
    print(f"{Colors.GREEN}Total data transferred: {total_bytes:,} bytes{Colors.END}")
    print(f"{Colors.GREEN}Total findings detected: {total_findings}{Colors.END}")
    print(f"{Colors.GREEN}Total structured fields: {total_structured_fields}{Colors.END}")

    print(f"\n{Colors.YELLOW}Format detection breakdown:{Colors.END}")
    formats = {}
    for r in results:
        fmt = r.get('metadata', {}).get('format_detected', 'unknown')
        formats[fmt] = formats.get(fmt, 0) + 1
    for fmt, count in formats.items():
        print(f"  • {fmt}: {count}")

    print(f"\n{Colors.BOLD}{Colors.GREEN}🎉 ALL DATA WAS 100% REAL!{Colors.END}")
    print(f"{Colors.GREEN}   ✓ No mock data{Colors.END}")
    print(f"{Colors.GREEN}   ✓ No examples{Colors.END}")
    print(f"{Colors.GREEN}   ✓ No simulations{Colors.END}")
    print(f"{Colors.GREEN}   ✓ Pure Archy internals revealed!{Colors.END}")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️  Inspection interrupted{Colors.END}")
    except Exception as e:
        print(f"\n\n{Colors.RED}❌ Error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()

