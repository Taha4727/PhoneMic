#!/usr/bin/env python3
"""
PhoneMic Windows Receiver - launcher.

    python phonemic_receiver.py            GUI (default)
    python phonemic_receiver.py --cli      console mode
    python phonemic_receiver.py --check    environment / dependency check
    python phonemic_receiver.py --list-devices

The implementation lives in the `phonemic` package next to this file.
"""
import os
import sys
import argparse
import traceback

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phonemic.const import VERSION, APP_NAME            # noqa: E402
from phonemic import system                             # noqa: E402
from phonemic.cli import run_interactive_dependency_fixer, list_devices, run_cli   # noqa: E402,F401  (re-exported for check_dependencies.py)


def message_box(text, title=APP_NAME, error=False):
    if system.IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, title, 0x10 if error else 0x40)
            return
        except Exception:
            pass
    print(f"{title}: {text}", file=sys.stderr)


def install_crash_handlers(rx_getter=lambda: None):
    def write(exc_type, exc, tb, where):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(system.crash_log_path(), "a", encoding="utf-8") as f:
                f.write(f"--- {where} v{VERSION} ---\n{text}\n")
        except Exception:
            pass
        rx = rx_getter()
        if rx is not None:
            rx.log.error(f"{where}: {exc!r}")
        return text

    def hook(exc_type, exc, tb):
        text = write(exc_type, exc, tb, "unhandled exception")
        message_box(f"An unexpected error occurred:\n\n{exc!r}\n\nDetails were saved to:\n{system.crash_log_path()}", error=True)

    sys.excepthook = hook
    try:
        import threading
        threading.excepthook = lambda a: write(a.exc_type, a.exc_value, a.exc_traceback, f"thread {a.thread.name if a.thread else '?'}")
    except Exception:
        pass
    return write


def parse_args(argv):
    p = argparse.ArgumentParser(prog="PhoneMicReceiver", description="Use your phone as a PC microphone.")
    p.add_argument("--cli", "--no-gui", action="store_true", help="run in the console without the GUI")
    p.add_argument("--check", action="store_true", help="check dependencies, audio devices, port and firewall")
    p.add_argument("--list-devices", action="store_true", help="list audio output devices and exit")
    p.add_argument("--selftest", action="store_true", help="check tray, shortcuts, firewall and other Windows features, then exit")
    def valid_port(val):
        try:
            p = int(val)
            if 1 <= p <= 65535:
                return p
        except Exception:
            pass
        raise argparse.ArgumentTypeError(f"Invalid port: '{val}'. Must be between 1 and 65535.")

    p.add_argument("--port", type=valid_port, help="listen on this port (1-65535, saved to settings)")
    p.add_argument("--minimized", action="store_true", help="start minimized")
    p.add_argument("--reset-config", action="store_true", help="reset settings to defaults (keeps your presets)")
    p.add_argument("--version", action="store_true", help="print version and exit")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        print(f"{APP_NAME} {VERSION}")
        return 0
    if args.check:
        return 0 if run_interactive_dependency_fixer() else 1
    if args.list_devices:
        return list_devices()
    if args.selftest:
        from phonemic import selftest
        results = selftest.run_selftest()
        print(selftest.format_results(results))
        return 1 if any(r.status == "fail" for r in results) else 0

    system.enable_dpi_awareness()
    use_gui = not args.cli
    if use_gui:
        try:
            import tkinter  # noqa: F401
        except Exception:
            print("tkinter is not available - falling back to console mode.")
            use_gui = False

    if not system.acquire_single_instance():
        if not system.signal_running_instance():        # the running copy brings its window to the front
            message_box("PhoneMic Receiver is already running.\n\nCheck your taskbar or the tray - a second copy cannot listen on the same port.")
        return 0

    from phonemic.config import ConfigManager
    from phonemic.engine import Receiver

    holder = {}
    write_crash = install_crash_handlers(lambda: holder.get("rx"))
    cfg = ConfigManager()
    if args.reset_config:
        cfg.reset(keep_presets=True)
    if args.port:
        cfg.data["network"]["port"] = args.port
        cfg.save_soon()

    system.set_timer_resolution(1, True)
    rx = Receiver(cfg)
    holder["rx"] = rx
    rx.start()
    try:
        if use_gui:
            from phonemic.gui import App
            app = App(rx, start_minimized=args.minimized or cfg.data["app"]["start_minimized"])
            app.root.report_callback_exception = lambda t, v, tb: write_crash(t, v, tb, "UI callback")
            app.run()
        else:
            run_cli(rx)
    finally:
        try:
            rx.stop()
        finally:
            cfg.close()
            system.set_timer_resolution(1, False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
