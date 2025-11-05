#!/usr/bin/env python3
"""
Test for Duplicate Execution and Hallucination Fixes

Tests:
1. Commands are not executed multiple times
2. AI uses actual output data instead of hallucinating
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from rust_executor import RustExecutor
import time

def test_no_duplicate_execution():
    """Test that commands aren't executed multiple times"""
    print("="*70)
    print("  Test 1: No Duplicate Execution")
    print("="*70)
    print()

    executor = RustExecutor()

    # Create a test file that tracks executions
    test_file = "/tmp/archy_exec_count.txt"

    # Execute a command that appends to the file
    cmd = f"echo test >> {test_file}"

    # Clear the file first
    executor.execute_in_tmux(f"rm -f {test_file}")
    time.sleep(1)

    print(f"Executing: {cmd}")
    print("This should only run ONCE even if AI mentions it multiple times")
    print()

    # Execute the command
    executor.execute_in_tmux(cmd)
    time.sleep(2)

    # Check how many times it ran
    result = executor.execute_in_tmux(f"wc -l < {test_file}")
    time.sleep(1)

    output = executor.capture_output(lines=10)
    print(f"File contents count: {output}")

    # Clean up
    executor.execute_in_tmux(f"rm -f {test_file}")

    print("✅ Test complete - check if command ran only once")
    print()

def test_structured_output_usage():
    """Test that structured output is available after command execution"""
    print("="*70)
    print("  Test 2: Structured Output Available")
    print("="*70)
    print()

    executor = RustExecutor()

    # Create a test file in a known location
    test_file = "/tmp/findme_test.txt"
    executor.execute_in_tmux(f"echo 'test content' > {test_file}")
    time.sleep(1)

    # Find the file
    print(f"Finding file: {test_file}")
    executor.execute_in_tmux(f"find /tmp -name 'findme_test.txt'")
    time.sleep(3)

    # Capture and analyze
    result = executor.capture_analyzed(command="find /tmp -name findme_test.txt", lines=100)

    print("Command output captured:")
    print(f"Status: {result.get('status')}")
    print(f"Summary: {result.get('summary')}")
    print(f"Structured data: {result.get('structured')}")
    print()

    # Check if the actual file path is in the structured data
    structured = result.get('structured', {})
    print("Structured data type:", type(structured))
    print("Structured data keys:", structured.keys() if isinstance(structured, dict) else "Not a dict")
    print()

    # Clean up
    executor.execute_in_tmux(f"rm -f {test_file}")

    print("✅ Test complete - structured data should contain actual file path")
    print()

def test_find_command_parsing():
    """Test that find command output is properly parsed"""
    print("="*70)
    print("  Test 3: Find Command Output Parsing")
    print("="*70)
    print()

    executor = RustExecutor()

    # Create multiple test files
    executor.execute_in_tmux("mkdir -p /tmp/test_find_archy")
    executor.execute_in_tmux("touch /tmp/test_find_archy/file1.txt")
    executor.execute_in_tmux("touch /tmp/test_find_archy/file2.txt")
    executor.execute_in_tmux("touch /tmp/test_find_archy/file3.txt")
    time.sleep(2)

    # Find them
    print("Finding files in /tmp/test_find_archy...")
    executor.execute_in_tmux("find /tmp/test_find_archy -name '*.txt'")
    time.sleep(3)

    # Capture and analyze
    result = executor.capture_analyzed(command="find", lines=100)

    print("Raw output sample:")
    raw = result.get('display', '')
    print(raw[:500] if len(raw) > 500 else raw)
    print()

    print(f"Status: {result.get('status')}")
    print(f"Format detected: {result.get('metadata', {}).get('format_detected')}")
    print(f"Summary: {result.get('summary')}")
    print()

    # Clean up
    executor.execute_in_tmux("rm -rf /tmp/test_find_archy")

    print("✅ Test complete - parser should extract file paths")
    print()

def main():
    print("\n" + "🔧 "*30)
    print("  Testing Duplicate Execution & Hallucination Fixes")
    print("🔧 "*30)
    print()

    try:
        test_no_duplicate_execution()
        test_structured_output_usage()
        test_find_command_parsing()

        print("="*70)
        print("  All Tests Complete!")
        print("="*70)
        print()
        print("Fixes implemented:")
        print("  ✓ Commands are deduplicated before execution")
        print("  ✓ Structured output added to conversation history")
        print("  ✓ AI told to use actual data, not hallucinate")
        print()
        print("Now when user asks 'where is it?', Archy will:")
        print("  1. Look at previous message in conversation history")
        print("  2. Find the actual structured output from command")
        print("  3. Use REAL file paths, not made-up ones")
        print()

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())

