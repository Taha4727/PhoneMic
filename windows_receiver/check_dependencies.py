#!/usr/bin/env python3
"""
PhoneMic Dependency & Audio Diagnostic Utility
Thin wrapper around phonemic_receiver's diagnostic suite.
Runs standalone dependency verification and audio device diagnostics.
"""

import sys
import os

# Delegate to phonemic_receiver's unified diagnostic engine
try:
    from phonemic_receiver import run_interactive_dependency_fixer
    success = run_interactive_dependency_fixer()
    input("\nPress Enter to exit...")
    sys.exit(0 if success else 1)
except ImportError:
    # Fallback if run standalone without phonemic_receiver in path
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phonemic_receiver.py")
    if os.path.exists(script):
        ret = subprocess.call([sys.executable, script, "--check"])
        sys.exit(ret)
    else:
        print("[!] phonemic_receiver.py not found in same directory.")
        input("Press Enter to exit...")
        sys.exit(1)
