#!/usr/bin/env python3
"""
Test script for collaborative terminal monitoring
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import time
from archy_chat import ArchyChat

def test_monitoring():
    """Test the terminal monitoring feature"""
    print("\n" + "="*70)
    print("🧪 Testing Collaborative Terminal Monitoring")
    print("="*70 + "\n")
    
    # Initialize Archy
    chat = ArchyChat()
    
    # Open terminal to trigger monitoring
    print("1️⃣  Opening terminal session...")
    if chat.rust_executor.open_terminal():
        print("✅ Terminal opened successfully")
        chat.start_terminal_monitoring()
        print("✅ Monitoring started")
    else:
        print("❌ Failed to open terminal")
        return False
    
    # Wait for monitoring to initialize
    print("\n2️⃣  Monitoring is active, waiting for commands...")
    print("   (The monitoring thread is checking terminal every 2 seconds)")
    
    # Simulate waiting (in real usage, user would type commands in terminal)
    for i in range(5):
        time.sleep(2)
        with chat._monitor_lock:
            if chat._detected_commands:
                print(f"\n✅ Detected commands: {chat._detected_commands}")
            else:
                print(f"   ⏳ Waiting... ({i+1}/5)")
    
    # Check terminal history
    print("\n3️⃣  Terminal history:")
    if chat.terminal_history:
        for idx, entry in enumerate(chat.terminal_history, 1):
            cmd = entry.get('command', 'unknown')
            summary = entry.get('summary', 'no summary')
            is_auto = " [AUTO-DETECTED]" if entry.get('auto_detected') else ""
            print(f"   {idx}. {cmd}{is_auto}")
            print(f"      → {summary}")
    else:
        print("   (No commands detected yet)")
    
    # Stop monitoring
    print("\n4️⃣  Stopping monitoring...")
    chat.stop_terminal_monitoring()
    print("✅ Monitoring stopped")
    
    # Cleanup
    chat.cleanup()
    
    print("\n" + "="*70)
    print("✅ Test completed!")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        test_monitoring()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

