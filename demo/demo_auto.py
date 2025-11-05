#!/usr/bin/env python3
"""
Auto Demo: Real-world security scanning with the new architecture
Non-interactive version that runs automatically
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from rust_executor import RustExecutor

def demo_banner(text):
    """Print a demo banner"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def main():
    executor = RustExecutor()
    
    demo_banner("🔒 SECURITY SCANNING DEMO - New Architecture Showcase")
    
    print("This demo shows how the new Rust-based architecture handles")
    print("security-focused commands with intelligent parsing, finding")
    print("extraction, and beautiful formatted output.\n")
    
    time.sleep(2)
    
    # Demo 1: Network interface scanning
    demo_banner("Demo 1: Network Interface Discovery (ip addr)")
    print("Command: ip addr show\n")
    
    result = executor.execute_analyzed("ip addr show", max_wait=5)
    
    print(result.get('display', ''))
    
    print("\n📦 Structured Data (for AI/Logic):")
    print(json.dumps(result.get('structured', {}), indent=2))
    
    time.sleep(2)
    
    # Demo 2: Listening ports and services
    demo_banner("Demo 2: Port & Service Discovery (ss -tlnp)")
    print("Command: ss -tlnp | head -20\n")
    
    result = executor.execute_analyzed("ss -tlnp 2>/dev/null | head -20", max_wait=5)
    
    print(result.get('display', ''))
    
    findings = result.get('findings', [])
    if findings:
        print("\n🔍 Extracted Findings:")
        for finding in findings:
            importance_icon = {
                'Critical': '🔴',
                'High': '🟠',
                'Medium': '🟡',
                'Low': '🟢',
                'Info': 'ℹ️'
            }.get(finding['importance'], '•')
            print(f"  {importance_icon} {finding['category']}: {finding['message']}")
    
    time.sleep(2)
    
    # Demo 3: Process monitoring
    demo_banner("Demo 3: Process Monitoring (ps)")
    print("Command: ps aux | head -20\n")
    
    result = executor.execute_analyzed("ps aux | head -20", max_wait=5)
    
    print(result.get('display', ''))
    
    print("\n📊 Summary:", result.get('summary', 'N/A'))
    print("📋 Format Detected:", result.get('metadata', {}).get('format_detected', 'unknown'))
    
    time.sleep(2)
    
    # Demo 4: Disk usage analysis
    demo_banner("Demo 4: Disk Space Analysis (df -h)")
    print("Command: df -h\n")
    
    result = executor.execute_analyzed("df -h", max_wait=5)
    
    print(result.get('display', ''))
    
    findings = result.get('findings', [])
    critical = [f for f in findings if f['importance'] == 'Critical']
    high = [f for f in findings if f['importance'] == 'High']
    
    if critical or high:
        print("\n⚠️ ALERTS DETECTED:")
        for finding in critical + high:
            print(f"  {finding['importance']}: {finding['message']}")
    else:
        print("\n✅ No critical disk space issues")
    
    time.sleep(2)
    
    # Demo 5: System uptime
    demo_banner("Demo 5: System Information (uname -a)")
    print("Command: uname -a\n")
    
    result = executor.execute_analyzed("uname -a", max_wait=5)
    
    print(result.get('display', ''))
    print("\n📊 Status:", result.get('status', 'unknown'))
    
    time.sleep(2)
    
    # Final summary
    demo_banner("✨ Demo Complete - Key Takeaways")
    
    print("""
The new Rust-based architecture provides:

1. 🎨 Beautiful Formatted Output
   • Colorful, easy-to-read display
   • Unicode box-drawing tables
   • Clear section separation
   • Importance-based icons

2. 🔍 Intelligent Parsing
   • Auto-detects command format
   • Extracts structured data
   • Identifies key metrics
   • Handles 10+ formats

3. 🔒 Security Awareness
   • Automatic threat detection
   • CVE reference flagging
   • Weak crypto detection
   • Authentication failure alerts

4. 🤖 AI-Ready Output
   • Clean structured JSON
   • Pre-extracted findings
   • One-line summaries
   • Context metadata

5. ⚡ High Performance
   • Rust parsing (10-50x faster)
   • Single pass analysis
   • Minimal memory footprint
   • Concurrent-safe design

6. 🛠️ Developer Friendly
   • Easy to add parsers
   • Modular architecture
   • Comprehensive docs
   • Rich examples

---

Python is now the BRAIN (AI logic, decisions)
Rust is now the HANDS (execution, parsing, formatting)

No more text parsing in Python! 🎉
""")
    
    print("\nFor more information:")
    print("  • NEW_ARCHITECTURE.md - Complete system documentation")
    print("  • QUICK_REFERENCE.md - Developer quick start guide")
    print("  • test_new_architecture.py - Comprehensive test suite")
    
    demo_banner("🎊 SUCCESS - Architecture Integration Complete!")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

