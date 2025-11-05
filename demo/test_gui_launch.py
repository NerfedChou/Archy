#!/usr/bin/env python3
"""
GUI App Launching Test
Tests Archy's ability to detect and launch GUI applications
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from rust_executor import RustExecutor
import time

def test_gui_detection():
    """Test which GUI apps are available on this system"""
    executor = RustExecutor()
    
    print("="*70)
    print("  GUI App Detection Test")
    print("="*70)
    print()
    
    # List of common apps to test
    apps_to_test = [
        'firefox',
        'chromium',
        'google-chrome',
        'brave',
        'code',
        'vlc',
        'gimp',
        'discord',
        'spotify',
        'nautilus',
        'thunar',
        'dolphin',
        'kate',
        'gedit',
        'xterm',
        'kitty',
        'alacritty',
        'foot'
    ]
    
    available_apps = []
    
    print("Checking for available GUI applications...\n")
    
    for app in apps_to_test:
        result = executor.send_command('find_desktop_entry', {'app_name': app})
        if result.get('exists'):
            desktop_entry = result.get('output')
            available_apps.append((app, desktop_entry))
            print(f"✅ {app:20s} → {desktop_entry}")
        else:
            print(f"❌ {app:20s} → Not found")
    
    print()
    print("="*70)
    print(f"Found {len(available_apps)} launchable GUI apps")
    print("="*70)
    
    return available_apps

def test_launch_app(app_name):
    """Test launching a specific GUI app"""
    executor = RustExecutor()
    
    print()
    print(f"Testing: Launching {app_name}...")
    print("-"*70)
    
    # Use smart execution
    result = executor.execute_command_smart(app_name)
    
    print(f"Success: {result.get('success')}")
    print(f"Output: {result.get('output')}")
    if result.get('error'):
        print(f"Error: {result.get('error')}")
    
    # Check if it's running
    time.sleep(2)
    import subprocess
    check = subprocess.run(['pgrep', '-a', app_name], capture_output=True, text=True)
    if check.returncode == 0:
        print(f"\n✅ {app_name} is running!")
        print(f"Process: {check.stdout.strip()[:100]}")
        return True
    else:
        print(f"\n⚠️  {app_name} process not found (might use different process name)")
        return False

def main():
    print("\n🦊 Testing Archy's GUI App Launching Feature\n")
    
    # Step 1: Detect available apps
    available_apps = test_gui_detection()
    
    if not available_apps:
        print("\n⚠️  No GUI apps with desktop entries found!")
        print("This might be a minimal system or the apps aren't installed.")
        return 1
    
    # Step 2: Test launching the first available app
    print("\n" + "="*70)
    print("  Launch Test")
    print("="*70)
    
    app_to_test = available_apps[0][0]
    print(f"\nWill test launching: {app_to_test}")
    
    input(f"\nPress Enter to launch {app_to_test}... ")
    
    success = test_launch_app(app_to_test)
    
    if success:
        print("\n" + "="*70)
        print("  ✅ SUCCESS! GUI app launching works!")
        print("="*70)
        print(f"\n{app_to_test} was launched successfully!")
        print("\nArchy can now launch GUI apps with:")
        print(f"  [EXECUTE_COMMAND: {app_to_test}]")
        
        input(f"\nPress Enter to close {app_to_test}... ")
        import subprocess
        subprocess.run(['pkill', app_to_test])
        print(f"✓ Closed {app_to_test}")
    else:
        print("\n⚠️  Could not verify app launch, but command executed")
        print("The app might be running with a different process name.")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

