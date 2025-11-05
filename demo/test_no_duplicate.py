#!/usr/bin/env python3
"""
Quick test to verify no duplicate execution
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from rust_executor import RustExecutor
import time

def test_no_duplicates():
    print("="*70)
    print("  Testing: No Duplicate Execution")
    print("="*70)
    print()

    executor = RustExecutor()

    # Create a counter file
    counter_file = "/tmp/archy_test_counter.txt"

    # Reset counter
    print("Resetting test counter...")
    executor.execute_in_tmux(f"echo 0 > {counter_file}")
    time.sleep(1)

    # Command that increments counter
    test_cmd = f"echo $(($(cat {counter_file}) + 1)) > {counter_file}"

    print(f"Executing test command: {test_cmd}")
    print("This command increments a counter in a file")
    print()

    # Execute via execute_command_smart (the same path Archy uses)
    result = executor.execute_command_smart(test_cmd)
    print(f"Smart execution result: {result.get('success')}")
    print(f"Output: {result.get('output', '')[:100]}")

    # Wait for completion
    time.sleep(3)

    # Read the counter value
    print("\nReading counter value...")
    executor.execute_in_tmux(f"cat {counter_file}")
    time.sleep(1)

    output = executor.capture_output(lines=5)
    print(f"Terminal output:\n{output}")

    # Check if counter is 1 (executed once) or 2 (executed twice)
    if "1" in output and "2" not in output:
        print("\n✅ SUCCESS! Command executed ONCE (counter = 1)")
    elif "2" in output:
        print("\n❌ FAILED! Command executed TWICE (counter = 2)")
    else:
        print(f"\n⚠️  Unexpected output: {output}")

    # Cleanup
    executor.execute_in_tmux(f"rm -f {counter_file}")

    print()
    print("="*70)

if __name__ == "__main__":
    try:
        test_no_duplicates()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

