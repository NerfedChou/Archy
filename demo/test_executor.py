#!/usr/bin/env python3
"""
Test script to verify Rust executor communication
"""

import sys
import os

# Add scripts directory to path
sys.path.insert(0, '/scripts')

from rust_executor import RustExecutor

def test_executor():
    print("🧪 Testing Rust Executor Communication...\n")

    executor = RustExecutor()

    # Test 1: Check session (should not exist yet)
    print("Test 1: Check if tmux session exists")
    exists = executor.check_session()
    print(f"  Result: Session exists = {exists}")
    print()

    # Test 2: Open terminal
    print("Test 2: Open terminal window")
    result = executor.open_terminal()
    print(f"  Result: Success = {result}")
    print()

    # Give it a moment
    import time
    time.sleep(2)

    # Test 3: Check session again (should exist now)
    print("Test 3: Check session again")
    exists = executor.check_session()
    print(f"  Result: Session exists = {exists}")
    print()

    # Test 4: Execute a command
    print("Test 4: Execute 'echo Hello from Rust!' in tmux")
    result = executor.execute_in_tmux("echo 'Hello from Rust!'")
    print(f"  Result: {result}")
    print()

    time.sleep(1)

    # Test 5: Capture output
    print("Test 5: Capture terminal output")
    output = executor.capture_output(lines=20)
    print(f"  Output (last 20 lines):")
    print("  " + "-" * 50)
    for line in output.strip().split('\n')[-5:]:  # Show last 5 lines
        print(f"  {line}")
    print("  " + "-" * 50)
    print()

    # Test 6: Close terminal window (keep session)
    print("Test 6: Close terminal window")
    result = executor.close_terminal()
    print(f"  Result: Success = {result}")
    print()

    time.sleep(1)

    # Test 7: Session should still exist
    print("Test 7: Check if session still exists after closing window")
    exists = executor.check_session()
    print(f"  Result: Session exists = {exists}")
    print()

    # Test 8: Close session entirely
    print("Test 8: Close tmux session entirely")
    result = executor.close_session()
    print(f"  Result: Success = {result}")
    print()

    time.sleep(1)

    # Test 9: Session should not exist now
    print("Test 9: Check if session exists after closing")
    exists = executor.check_session()
    print(f"  Result: Session exists = {exists}")
    print()

    print("✅ All tests completed!")

if __name__ == "__main__":
    test_executor()

