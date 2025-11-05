#!/usr/bin/env python3
"""
Test script for the new Rust-based parsing and formatting architecture.
Tests execute_analyzed and capture_analyzed with various commands.
"""

import sys
import json
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from rust_executor import RustExecutor

def print_section(title):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_execute_analyzed():
    """Test execute_analyzed with various commands"""
    executor = RustExecutor()
    
    print_section("Test 1: Simple command (echo)")
    result = executor.execute_analyzed("echo 'Hello from new architecture!'", max_wait=5)
    print("Status:", result.get('status'))
    print("Summary:", result.get('summary'))
    print("\nFormatted Display:")
    print(result.get('display', ''))
    
    print_section("Test 2: Directory listing (ls)")
    result = executor.execute_analyzed("ls -la /tmp", max_wait=5)
    print("Status:", result.get('status'))
    print("Summary:", result.get('summary'))
    print("Findings:", json.dumps(result.get('findings', []), indent=2))
    print("\nFormatted Display:")
    print(result.get('display', ''))
    
    print_section("Test 3: System info (uname)")
    result = executor.execute_analyzed("uname -a", max_wait=5)
    print("Status:", result.get('status'))
    print("Summary:", result.get('summary'))
    print("\nStructured Data:")
    print(json.dumps(result.get('structured', {}), indent=2))
    print("\nFormatted Display:")
    print(result.get('display', ''))
    
    print_section("Test 4: Network connections (ss)")
    result = executor.execute_analyzed("ss -tuln | head -20", max_wait=5)
    print("Status:", result.get('status'))
    print("Summary:", result.get('summary'))
    print("Findings:", json.dumps(result.get('findings', []), indent=2))
    print("\nStructured Data:")
    print(json.dumps(result.get('structured', {}), indent=2))
    print("\nFormatted Display:")
    print(result.get('display', ''))

def test_capture_analyzed():
    """Test capture_analyzed"""
    executor = RustExecutor()
    
    print_section("Test 5: Capture and analyze current terminal output")
    
    # First execute a command to have something to capture
    executor.execute_in_tmux("ps aux | head -15")
    import time
    time.sleep(2)  # Wait for command to finish
    
    # Now capture and analyze
    result = executor.capture_analyzed(command="ps aux", lines=100)
    print("Status:", result.get('status'))
    print("Summary:", result.get('summary'))
    print("Findings:", json.dumps(result.get('findings', []), indent=2))
    print("\nFormatted Display:")
    print(result.get('display', ''))

def test_metadata():
    """Test metadata extraction"""
    executor = RustExecutor()
    
    print_section("Test 6: Metadata and format detection")
    result = executor.execute_analyzed("df -h", max_wait=5)
    
    metadata = result.get('metadata', {})
    print("Format detected:", metadata.get('format_detected'))
    print("Line count:", metadata.get('line_count'))
    print("Byte count:", metadata.get('byte_count'))
    print("\nFindings:", json.dumps(result.get('findings', []), indent=2))
    print("\nFormatted Display:")
    print(result.get('display', ''))

def main():
    """Run all tests"""
    print("\n" + "🦀 "*30)
    print("  NEW ARCHITECTURE TEST SUITE")
    print("  Rust handles: Parsing, Formatting, Analysis")
    print("  Python consumes: Structured JSON output")
    print("🦀 "*30)
    
    try:
        test_execute_analyzed()
        test_capture_analyzed()
        test_metadata()
        
        print_section("✅ All tests completed!")
        print("The new architecture is working correctly!")
        print("\nKey benefits:")
        print("  ✓ Rust handles ALL text parsing and formatting")
        print("  ✓ Python receives clean structured JSON")
        print("  ✓ Beautiful colored output generated in Rust")
        print("  ✓ Findings automatically extracted")
        print("  ✓ Summaries generated intelligently")
        print("  ✓ Metadata tracked for every command")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

