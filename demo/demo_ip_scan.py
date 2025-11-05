#!/usr/bin/env python3
"""
Quick demo: Get IP and scan network with nmap
Shows the new architecture handling a real security workflow
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from rust_executor import RustExecutor

def main():
    executor = RustExecutor()
    
    print("="*70)
    print("  🔍 IP Discovery & Network Scanning Demo")
    print("="*70)
    print()
    
    # Step 1: Get the IP address
    print("Step 1: Getting your IP address...")
    print("Executing: ip a")
    print()
    
    # Execute ip a
    executor.execute_in_tmux("ip a")
    import time
    time.sleep(1)
    
    # Capture and analyze
    result = executor.capture_analyzed(command="ip a", lines=100)
    
    print(result.get('display', ''))
    
    # Extract the main IP
    structured = result.get('structured', {})
    ipv4_addresses = structured.get('ipv4_addresses', [])
    
    # Find the main network IP (not localhost, not docker)
    main_ip = None
    for ip in ipv4_addresses:
        if not ip.startswith('127.') and not ip.startswith('172.'):
            main_ip = ip.split('/')[0]  # Remove the /24 suffix
            break
    
    if not main_ip:
        print("\n❌ Could not find main network IP")
        return 1
    
    print(f"\n✅ Found your main IP: {main_ip}")
    
    # Calculate network range
    network_base = '.'.join(main_ip.split('.')[:3])  # Get first 3 octets
    network_range = f"{network_base}.0/24"
    
    print(f"🌐 Network range: {network_range}")
    print()
    
    # Step 2: Scan the network
    print(f"Step 2: Scanning network {network_range} for connected devices...")
    print(f"Executing: nmap -sn {network_range}")
    print("(This may take 10-30 seconds...)")
    print()
    
    # Execute nmap
    executor.execute_in_tmux(f"nmap -sn {network_range}")
    time.sleep(15)  # Give nmap time to run
    
    # Capture and analyze
    result = executor.capture_analyzed(command=f"nmap -sn {network_range}", lines=200)
    
    print(result.get('display', ''))
    
    # Show summary
    structured = result.get('structured', {})
    hosts_up = structured.get('hosts_up', 0)
    
    print(f"\n📊 Network Scan Complete!")
    print(f"   • Your IP: {main_ip}")
    print(f"   • Network: {network_range}")
    print(f"   • Devices found: {hosts_up}")
    
    findings = result.get('findings', [])
    if findings:
        print(f"\n🔍 Key Findings:")
        for finding in findings:
            print(f"   • {finding.get('category')}: {finding.get('message')}")
    
    print("\n✨ Demo complete!")
    print("\nThis demonstrates:")
    print("  ✓ Intelligent IP address parsing")
    print("  ✓ Automatic network range calculation")
    print("  ✓ Nmap output analysis with findings")
    print("  ✓ Structured data extraction")
    print("  ✓ Beautiful formatted output")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

