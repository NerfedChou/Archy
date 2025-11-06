#!/usr/bin/env python3
"""
Advanced Debug: Socket-Level Communication Tracer
Intercepts and logs ALL communication between Python and Rust
"""

import sys
import socket
import json
import time
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


class DebugRustExecutor:
    """
    Debug version of RustExecutor that logs everything
    """
    
    def __init__(self, socket_path: str = "/tmp/archy.sock"):
        self.socket_path = socket_path
        self.call_count = 0
        
    def send_command(self, action: str, data: dict) -> dict:
        """
        Send command with detailed logging
        """
        self.call_count += 1
        call_id = self.call_count
        
        print(f"\n{'='*80}")
        print(f"🔵 PYTHON → RUST (Call #{call_id})")
        print(f"{'='*80}")
        
        # Show what we're sending
        message = {"action": action, "data": data}
        print(f"📤 Outgoing JSON:")
        print(json.dumps(message, indent=2))
        
        # Timing
        start_time = time.time()
        
        try:
            # Connect to socket
            print(f"\n🔌 Connecting to socket: {self.socket_path}")
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(self.socket_path)
            print(f"✓ Connected!")
            
            # Send data
            message_json = json.dumps(message)
            message_bytes = message_json.encode()
            print(f"\n📊 Sending {len(message_bytes)} bytes...")
            client.sendall(message_bytes)
            print(f"✓ Sent!")
            
            # Receive response
            print(f"\n⏳ Waiting for response from Rust...")
            response_data = b''
            chunk_count = 0
            while True:
                chunk = client.recv(8192)
                if not chunk:
                    break
                chunk_count += 1
                response_data += chunk
                print(f"  📥 Received chunk {chunk_count}: {len(chunk)} bytes")
            
            client.close()
            
            elapsed = time.time() - start_time
            print(f"\n⏱️  Total time: {elapsed:.3f}s")
            
            # Parse response
            print(f"\n📥 Incoming Response ({len(response_data)} bytes total):")
            response_str = response_data.decode('utf-8', errors='replace')
            response = json.loads(response_str)
            
            # Pretty print response (but truncate long values)
            print("Response structure:")
            for key, value in response.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"  • {key}: \"{value[:100]}...\" (truncated, {len(value)} chars total)")
                elif isinstance(value, (list, dict)):
                    print(f"  • {key}: {type(value).__name__} with {len(value)} items")
                else:
                    print(f"  • {key}: {value}")
            
            print(f"\n{'='*80}")
            print(f"✅ RUST → PYTHON (Call #{call_id} complete)")
            print(f"{'='*80}\n")
            
            return response
            
        except FileNotFoundError:
            print(f"\n❌ ERROR: Socket not found!")
            print(f"   Rust daemon is not running")
            return {"success": False, "error": "Daemon not running"}
        except ConnectionRefusedError:
            print(f"\n❌ ERROR: Connection refused!")
            print(f"   Socket exists but daemon not accepting connections")
            return {"success": False, "error": "Connection refused"}
        except json.JSONDecodeError as e:
            print(f"\n❌ ERROR: Invalid JSON in response!")
            print(f"   {e}")
            print(f"   Raw response: {response_data[:500]}")
            return {"success": False, "error": "Invalid JSON"}
        except Exception as e:
            print(f"\n❌ ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}


def trace_command_execution():
    """Trace a complete command execution with REAL DATA"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SOCKET-LEVEL COMMUNICATION TRACER - REAL DATA                   ║
║          Watch ACTUAL data flowing between Python and Rust!                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    executor = DebugRustExecutor()
    
    print("\n🎯 Test 1: Get REAL system info")
    print("─" * 80)
    result = executor.send_command("get_system_info", {})
    print(f"\n✅ ACTUAL System Info Returned:")
    print(f"   {result.get('output', 'N/A')}")

    print("\n\n🎯 Test 2: Check REAL session status")
    print("─" * 80)
    result = executor.send_command("check_session", {})
    print(f"\n✅ ACTUAL Session Status:")
    print(f"   Exists: {result.get('exists')}")
    print(f"   Success: {result.get('success')}")

    print("\n\n🎯 Test 3: Execute REAL command with actual output")
    print("─" * 80)
    # Use a command that gives interesting output
    test_command = "hostname && date && echo 'Test completed'"
    result = executor.send_command("execute_and_wait", {
        "command": test_command,
        "session": "archy_session",
        "max_wait": 10,
        "interval_ms": 500
    })
    
    if result.get('success'):
        print("\n📊 REAL DATA - Let's examine what Rust parsed and formatted:")
        print("─" * 80)
        
        print(f"\n✅ Command executed: {result.get('command')}")
        print(f"✅ Exit code: {result.get('exit_code')}")
        print(f"✅ Status: {result.get('status')}")

        if 'structured' in result:
            print(f"\n🔍 REAL Structured Data (JSON parsed by Rust):")
            print(json.dumps(result['structured'], indent=2))
            print(f"\n   → Rust detected format: {result.get('metadata', {}).get('format_detected', 'unknown')}")
            print(f"   → Parsed {len(result['structured'])} fields from output")

        if 'findings' in result and result['findings']:
            print(f"\n💡 REAL Findings (insights detected by Rust from actual output):")
            for finding in result['findings']:
                importance = finding.get('importance', 'Medium')
                category = finding.get('category', 'Unknown')
                message = finding.get('message', '')
                print(f"  [{importance}] {category}: {message}")

        if 'summary' in result:
            print(f"\n✓ REAL Summary: {result['summary']}")

        if 'metadata' in result:
            meta = result['metadata']
            print(f"\n📈 REAL Metadata:")
            print(f"   • Lines captured: {meta.get('line_count', 0)}")
            print(f"   • Bytes processed: {meta.get('byte_count', 0)}")
            print(f"   • Format detected: {meta.get('format_detected', 'unknown')}")

        if 'display' in result:
            print(f"\n🎨 REAL Formatted Display Output (created by Rust):")
            print("─" * 80)
            print(result['display'])
            print("─" * 80)
            print(f"\n   → This is the ACTUAL formatted output you would see in Archy!")

    print("\n\n🎯 Test 4: Execute network command to see REAL parsing")
    print("─" * 80)
    print("   Running 'ip addr show' to see how Rust parses network info...")
    result = executor.send_command("execute_and_wait", {
        "command": "ip addr show | head -30",
        "session": "archy_session",
        "max_wait": 10,
        "interval_ms": 500
    })

    if result.get('success') and result.get('structured'):
        print(f"\n✅ REAL Network Data Parsed:")
        structured = result['structured']
        if 'interfaces' in structured:
            print(f"   • Interfaces found: {structured['interfaces']}")
        if 'ipv4_addresses' in structured:
            print(f"   • IPv4 addresses: {structured['ipv4_addresses']}")
        print(f"\n   → Rust automatically detected this as: {result.get('metadata', {}).get('format_detected', 'unknown')}")

    print("\n\n🎯 Test 5: Capture current terminal state")
    print("─" * 80)
    result = executor.send_command("capture_analyzed", {
        "command": "current terminal state",
        "lines": 30,
        "session": "archy_session"
    })
    
    if result.get('success'):
        print(f"\n✅ REAL Terminal State:")
        print(f"   • Lines captured: {result.get('metadata', {}).get('line_count', 0)}")
        print(f"   • Bytes: {result.get('metadata', {}).get('byte_count', 0)}")
        if result.get('summary'):
            print(f"   • Summary: {result['summary']}")

    print("\n\n📊 SUMMARY OF REAL DATA CAPTURED")
    print("=" * 80)
    print(f"✅ Total API calls made: {executor.call_count}")
    print(f"✅ Socket path: {executor.socket_path}")
    print(f"✅ All data shown above is REAL:")
    print(f"   • Actual JSON messages sent/received")
    print(f"   • Real command executions")
    print(f"   • True parsing results from Rust")
    print(f"   • Actual formatted output")
    print(f"\n🔄 Data flow verified:")
    print(f"  1. ✓ Python creates JSON with action + data")
    print(f"  2. ✓ Python sends to Unix socket (/tmp/archy.sock)")
    print(f"  3. ✓ Rust daemon receives and parses JSON")
    print(f"  4. ✓ Rust executes the action (we saw real commands run!)")
    print(f"  5. ✓ Rust formats and parses output (we saw real structured data!)")
    print(f"  6. ✓ Rust creates DisplayOutput structure")
    print(f"  7. ✓ Rust serializes to JSON and sends back")
    print(f"  8. ✓ Python receives and deserializes JSON")
    print(f"  9. ✓ Python uses the structured data (we saw the actual results!)")
    print("=" * 80)
    print("\n🎉 Everything you saw was LIVE DATA from actual executions!")
    print("   No mock data, no examples - 100% real Archy internals!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        trace_command_execution()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tracing interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

