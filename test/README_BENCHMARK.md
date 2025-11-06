# Archy Benchmark & Stress Test Suite

## Overview

This benchmark suite pushes Archy to its absolute limits to find breaking points and measure performance characteristics.

## What It Tests

### 1. 📦 Batch Command Execution
- **Small batch:** 5 commands
- **Medium batch:** 50 commands
- **Large batch:** 200 commands (stress test)
- **Extreme batch:** 1000 commands for throughput test
- **Mixed types:** Different command types in sequence

**Purpose:** Find the maximum number of commands the system can handle before degradation.

### 2. 📡 Feedback Quality
- Boolean accuracy (True/False responses)
- JSON structure validation
- Error message quality
- Type preservation across IPC (bool, string, dict)

**Purpose:** Ensure feedback is reliable, structured, and type-safe.

### 3. 🛡️ Resiliency & Fault Tolerance
- Invalid input handling
- Rapid connection cycling (100 cycles)
- Large data transfer (500+ lines)
- Concurrent requests (10 threads, 50 requests total)
- Error recovery (continues after failures)

**Purpose:** Test stability under load and error conditions.

### 4. 🔒 Safety & Security
- Command injection prevention
- Path traversal blocking
- Resource limit handling
- Timeout handling

**Purpose:** Verify the system is secure against malicious inputs.

### 5. 🔄 Fallback Mechanisms
- Non-existent session handling
- Missing command detection
- GUI app not found handling
- Partial failure in batch

**Purpose:** Ensure graceful degradation when things go wrong.

### 6. 🧠 Intelligence & Awareness
- GUI vs CLI detection
- System state awareness
- Command availability accuracy
- Smart execution routing

**Purpose:** Verify the system understands what it's doing.

### 7. ⚡ Performance Benchmarks
- **Latency test:** 100 requests to measure average response time
- **Throughput test:** 1000 requests to measure requests/second
- **Connection efficiency:** 50 requests to measure overhead

**Purpose:** Establish performance baselines and find bottlenecks.

### 8. 🔍 Edge Cases
- Empty strings
- Special characters (\n, \0, \t, spaces, semicolons)
- Very long inputs (10KB)
- Unicode and UTF-8
- Rapid state changes

**Purpose:** Find corner cases that might break the system.

## Usage

### Quick Run
```bash
cd /home/chef/Archy/test
python3 benchmark_stress_test.py
```

### With Virtual Environment
```bash
cd /home/chef/Archy
source .venv/bin/activate
python3 test/benchmark_stress_test.py
```

### What to Expect

**Duration:** 2-5 minutes depending on system speed

**CPU Usage:** Will spike to 100% during throughput tests

**Output:** Colored, detailed results with pass/fail for each test

## Interpreting Results

### Grades

| Grade | Pass Rate | Meaning |
|-------|-----------|---------|
| A+ | 95-100% | Production ready, excellent |
| A | 90-94% | Very solid, minor tweaks |
| B | 80-89% | Good, some issues to address |
| C | 70-79% | Acceptable, needs work |
| F | <70% | Critical issues, not ready |

### Key Metrics

**Latency (per request):**
- Excellent: <5ms
- Good: 5-10ms
- Acceptable: 10-20ms
- Slow: >20ms

**Throughput:**
- Excellent: >100 req/s
- Good: 50-100 req/s
- Acceptable: 20-50 req/s
- Slow: <20 req/s

**Batch Capacity:**
- Excellent: 200+ commands without failures
- Good: 100-200 commands
- Acceptable: 50-100 commands
- Limited: <50 commands

## Example Output

```
╔════════════════════════════════════════════════════════════════════════════╗
║                  ARCHY STRESS TEST & BENCHMARK SUITE                      ║
║                    Pushing the System to Its Limits                       ║
╚════════════════════════════════════════════════════════════════════════════╝

This benchmark will stress-test:
  • Batch command execution (up to 1000 commands)
  • Feedback quality and structure
  • Resiliency under load
  • Safety and security measures
  • Fallback mechanisms
  • Intelligence and awareness
  • Performance limits
  • Edge cases and corner cases

✓ Daemon connection verified
⚠ WARNING: This test will push the system hard. Expect high CPU usage.

Press ENTER to start the stress test...

════════════════════════════════════════════════════════════════════════════
📦 BATCH COMMAND STRESS TEST
════════════════════════════════════════════════════════════════════════════

🔬 TEST: Small batch (5 rapid commands)
  ✓ PASS: Executed 5/5 commands successfully (0.0048s)

🔬 TEST: Medium batch (50 rapid commands)
  ✓ PASS: Executed 50/50 commands successfully (0.0523s)
  ℹ INFO: Average time per command: 0.0010s

🔬 TEST: Large batch (200 rapid commands) - STRESS TEST
  ✓ PASS: Executed 200/200 commands successfully (0.2145s)
  ℹ INFO: Average time per command: 0.0011s

...

════════════════════════════════════════════════════════════════════════════
🏆 FINAL BENCHMARK RESULTS
════════════════════════════════════════════════════════════════════════════

Overall Statistics:
  Total Tests: 45
  Passed: 45
  Failed: 0
  Pass Rate: 100.0%
  Total Time: 15.34s

Performance Summary:

  Batch:
    • 5 commands: 0.0048s
    • 50 commands: 0.0523s
    • 200 commands: 0.2145s

  Performance:
    • 100 requests: 0.9876s
    • Throughput test: 12.3456s

════════════════════════════════════════════════════════════════════════════
GRADE: A+
VERDICT: EXCELLENT - Production Ready!
════════════════════════════════════════════════════════════════════════════

Key Findings:

✓ Batch Execution: Handles 200+ rapid commands successfully
✓ Resiliency: Highly resilient to errors and load
✓ Safety: All security checks passed
✓ Performance: High throughput (50+ requests/second)
```

## What This Tests That Normal Tests Don't

1. **Breaking Points:** Where does the system start to fail?
2. **Concurrent Load:** How does it handle multiple threads?
3. **Security:** Is it vulnerable to injection attacks?
4. **Edge Cases:** Does it crash on weird inputs?
5. **Performance Limits:** What's the maximum throughput?
6. **Recovery:** Can it continue after errors?
7. **Resource Usage:** Does it handle large data safely?
8. **Real-World Stress:** Simulates heavy usage patterns

## When to Run This

- **After major changes** to verify stability
- **Before deployment** to ensure production readiness
- **Performance regression testing** to catch slowdowns
- **Capacity planning** to understand limits
- **Security audits** to verify safety measures

## Customization

Edit the test functions to adjust:
- Number of commands in batch tests
- Concurrent thread count
- Timeout values
- Special character test cases
- Performance thresholds

## Troubleshooting

### Daemon Not Running
```
❌ Rust executor daemon is not running!
Please start it with: ./start_daemon.sh
```
**Solution:** Run `./start_daemon.sh` first

### High CPU Usage
Normal during throughput test (1000 requests). If concerned, reduce iterations.

### Some Tests Skipped
Tests requiring active tmux session are skipped if no session exists. This is expected.

### Concurrent Test Failures
May indicate thread-safety issues or connection pool limits. Review concurrent request handling in Rust.

## Files

- `benchmark_stress_test.py` - Main benchmark suite
- `test_integration.py` - Basic integration tests (run this first)

## Expected Results

Based on current implementation:
- **Pass Rate:** 95-100%
- **Latency:** 1-2ms average
- **Throughput:** 100-200 req/s
- **Batch Capacity:** 200+ commands
- **Concurrent Handling:** 50+ simultaneous requests
- **Security:** All injection attempts blocked

## Contributing

When adding features, run this benchmark to ensure:
1. No performance regression
2. Existing functionality not broken
3. New features handle edge cases
4. System remains secure and stable

---

**Remember:** This is a stress test. Some failures are acceptable if they're at extreme limits (e.g., 10,000 character commands). The goal is to find where the system breaks, not to pass 100% of tests.

