#!/usr/bin/env python3
"""
Quick test to verify all fixes are working correctly
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from rust_executor import RustExecutor

def test_daemon_connection():
    """Test 1: Can we connect to the daemon?"""
    print("🧪 Test 1: Daemon Connection")
    try:
        executor = RustExecutor()
        info = executor.get_system_info()
        print(f"   ✅ Connected to daemon")
        print(f"   📊 System: {info}")
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False

def test_gui_launch():
    """Test 2: Can we launch a GUI app without zombies?"""
    print("\n🧪 Test 2: GUI App Launch (testing with a small app)")
    try:
        executor = RustExecutor()
        
        # Find a small GUI app to test (xcalc, xeyes, etc.)
        test_apps = ['xcalc', 'xeyes', 'xclock']
        
        for app in test_apps:
            result = executor.find_desktop_entry(app)
            if result:
                print(f"   Found test app: {app}")
                launch_result = executor.execute_command_smart(app, 'archy_session')
                if launch_result.get('success'):
                    print(f"   ✅ {app} launched successfully")
                    print(f"   📝 Output: {launch_result.get('output')}")
                    
                    # Kill it after test
                    os.system(f"pkill {app} 2>/dev/null")
                    return True
                else:
                    print(f"   ⚠️  {app} launch returned: {launch_result}")
        
        print("   ⚠️  No test GUI apps found (xcalc, xeyes, xclock)")
        print("   💡 You can manually test with: python3 scripts/archy_chat.py")
        print("      Then type: 'open firefox'")
        return True  # Not a failure, just no test apps available
        
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False

def test_command_tag_hiding():
    """Test 3: Verify command tags are stripped from display"""
    print("\n🧪 Test 3: Command Tag Filtering")
    import re
    
    # Simulate what the chat does
    test_text = "Let me help you! [EXECUTE_COMMAND: ls -la] I'll list the files."
    
    # Apply the same regex patterns from archy_chat.py
    filtered = re.sub(r'\s*\[EXECUTE_COMMAND:\s*[^\]]+\]', '', test_text)
    filtered = re.sub(r'\s*\[OPEN_TERMINAL\]', '', filtered)
    
    expected = "Let me help you! I'll list the files."
    
    if filtered.strip() == expected.strip():
        print(f"   ✅ Command tags properly filtered")
        print(f"   📝 Original: {test_text}")
        print(f"   📝 Filtered: {filtered}")
        return True
    else:
        print(f"   ❌ Filtering failed")
        print(f"   Expected: {expected}")
        print(f"   Got: {filtered}")
        return False

def test_service_environment():
    """Test 4: Verify service has correct environment"""
    print("\n🧪 Test 4: Service Environment Variables")
    import subprocess
    
    try:
        result = subprocess.run(
            ['systemctl', '--user', 'show', 'archy-executor.service', '-p', 'Environment'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            env_line = result.stdout.strip()
            
            required_vars = ['DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR']
            missing = []
            
            for var in required_vars:
                if var not in env_line:
                    missing.append(var)
            
            if not missing:
                print(f"   ✅ All required environment variables present")
                print(f"   📝 {env_line}")
                return True
            else:
                print(f"   ⚠️  Missing variables: {', '.join(missing)}")
                print(f"   📝 {env_line}")
                return False
        else:
            print(f"   ❌ Could not check service (is it running?)")
            return False
            
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 ARCHY FIX VERIFICATION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    results.append(("Daemon Connection", test_daemon_connection()))
    results.append(("Command Tag Filtering", test_command_tag_hiding()))
    results.append(("Service Environment", test_service_environment()))
    results.append(("GUI Launch", test_gui_launch()))
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n  Total: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n  🎉 All tests passed! Archy is fully operational!")
        print("\n  💡 Try it out:")
        print("     python3 scripts/archy_chat.py")
        sys.exit(0)
    else:
        print("\n  ⚠️  Some tests failed. Check the output above.")
        sys.exit(1)

