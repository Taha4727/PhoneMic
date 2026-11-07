"""Run every test script: python tests/run_all.py"""
import os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
failed = []
for name in ("test_dsp.py", "test_dsp_controls.py", "test_registry.py", "test_presets_io.py", "test_bindings.py", "test_hotkeys.py", "test_desktop.py", "test_packaging.py", "test_engine_gate.py", "test_config_net.py", "test_theme.py", "test_tk_shadowing.py", "test_engine.py", "test_gui_smoke.py", "test_gui_desktop.py"):
    print(f"\n=== {name} ===", flush=True)
    if subprocess.call([sys.executable, os.path.join(here, name)], cwd=here) != 0:
        failed.append(name)
print("\nALL PASSED" if not failed else f"\nFAILED: {failed}")
sys.exit(1 if failed else 0)
