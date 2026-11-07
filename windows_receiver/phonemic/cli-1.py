"""Console mode, dependency check and device listing (no Tk required)."""
import os
import sys
import time
import socket
import subprocess

from . import system
from .const import VERSION, DEFAULT_PORT, VB_CABLE_URL



def enable_ansi():
    """Turn on ANSI colour escapes in the Windows 10+ console (no subprocess => no console flash in the GUI exe)."""
    if not system.IS_WIN:
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, mode.value | 0x0004)       # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


C = {"reset": "\033[0m", "dim": "\033[2m", "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
     "cyan": "\033[36m", "bold": "\033[1m"}


def _c(color, text):
    return f"{C[color]}{text}{C['reset']}"


# ==============================================================================
# DEVICES
# ==============================================================================
def list_devices():
    from . import engine
    if engine._sd is None:
        print(_c("red", f"sounddevice is not available: {engine.SD_ERROR}"))
        return 1
    devs = system.list_output_devices(engine._sd)
    if not devs:
        print("No output devices found.")
        return 1
    print(f"{'#':>3}  {'Backend':<18} {'Ch':>2}  Name")
    for d in sorted(devs, key=lambda d: (system._api_rank(d.api), d.name)):
        flag = " (default)" if d.is_default else ""
        cable = _c("green", "  <- virtual cable") if d.is_cable else ""
        print(f"{d.index:>3}  {d.api:<18} {d.channels:>2}  {d.name}{flag}{cable}")
    return 0


# ==============================================================================
# DEPENDENCY / ENVIRONMENT CHECK
# ==============================================================================
def _module_status(name):
    """-> (ok, detail). ImportError = package missing (pip can fix it); OSError = package present but a DLL is not."""
    try:
        __import__(name)
        return True, ""
    except ImportError as e:
        return False, f"not installed ({e})"
    except OSError as e:
        return False, f"installed, but a native library failed to load: {e}"
    except Exception as e:      # noqa: BLE001
        return False, str(e)


def _module_ok(name):
    return _module_status(name)[0]


def run_interactive_dependency_fixer(interactive=True):
    """Checks Python packages, audio devices, port and firewall. Returns True if everything needed works."""
    enable_ansi()
    print(_c("cyan", f"PhoneMic Receiver v{VERSION} - environment check"))
    print("-" * 64)
    ok_all = True
    frozen = system.FROZEN

    def line(ok, text, extra=""):
        mark = _c("green", "[ OK ]") if ok else _c("red", "[FAIL]")
        print(f"{mark} {text}" + (f"  {_c('dim', extra)}" if extra else ""))

    py_ok = sys.version_info >= (3, 8)
    line(py_ok, f"Python {sys.version.split()[0]}")
    ok_all &= py_ok

    missing = []
    for pkg, mod in (("numpy", "numpy"), ("sounddevice", "sounddevice")):
        good, detail = _module_status(mod)
        line(good, f"{pkg} package", detail)
        if not good and detail.startswith("not installed"):
            missing.append(pkg)
        elif not good:
            ok_all = False
    line(_module_ok("tkinter"), "tkinter (GUI)", "" if _module_ok("tkinter") else "- console mode still works (--cli)")
    tray_ok = _module_ok("pystray") and _module_ok("PIL")
    line(tray_ok, "pystray and Pillow (tray icon, optional)", "" if tray_ok else "- install with: pip install pystray pillow")

    if missing and not frozen:
        ok_all = False
        print()
        print(f"Missing: {', '.join(missing)}")
        if interactive:
            try:
                ans = input("Install them now with pip? (Y/N): ").strip().lower()
            except EOFError:
                ans = "n"
            if ans == "y":
                rc = subprocess.call([sys.executable, "-m", "pip", "install", *missing])
                if rc == 0:
                    print(_c("green", "Installed. Re-run the check to confirm."))
                else:
                    print(_c("red", "pip failed - check your internet connection."))
    elif missing:
        ok_all = False

    from . import engine
    if engine._sd is not None:
        devs = system.list_output_devices(engine._sd)
        api = system.resolve_api(devs, "auto")
        line(bool(devs), f"Audio output devices: {len(devs)}", f"(preferred backend: {api or 'none'})")
        cable = any(d.is_cable for d in devs)
        line(cable, "VB-CABLE virtual microphone", "" if cable else f"- optional, needed for Discord/OBS/Zoom: {VB_CABLE_URL}")
        ok_all &= bool(devs)
    else:
        line(False, "PortAudio / sounddevice", engine.SD_ERROR)
        ok_all = False

    # can we bind the port?
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if system.IS_WIN and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("0.0.0.0", DEFAULT_PORT))
        line(True, f"UDP port {DEFAULT_PORT} is free")
    except OSError as e:
        line(False, f"UDP port {DEFAULT_PORT}", f"{e} - is another receiver already running?")
        ok_all = False
    finally:
        s.close()

    if system.IS_WIN:
        fw = system.firewall_rules_ok(DEFAULT_PORT)
        line(fw, "Windows Firewall rules", "" if fw else "- run fix_firewall.bat as Administrator")
    ip = system.NetworkInfo()
    ip.refresh()
    for i in ip.get():
        print(f"       {i.category:<11} {i.ip}")
    print("-" * 64)
    print(_c("green", "Everything needed is available.") if ok_all else _c("yellow", "Some checks failed - see above."))
    return ok_all


# ==============================================================================
# CONSOLE MODE
# ==============================================================================
class _Keys:
    """Non-blocking single-key reader for both Windows and POSIX terminals."""

    def __enter__(self):
        self.win = system.IS_WIN
        if not self.win:
            import termios
            import tty
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, *a):
        if not self.win:
            import termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    def get(self):
        if self.win:
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getwch().lower()
            return ""
        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1).lower()
        return ""


def run_cli(rx):
    from .dsp import VoiceChanger
    p = rx.processor
    enable_ansi()
    print(_c("cyan", f"PhoneMic Receiver v{VERSION} - console mode"))
    last = 0.0
    try:
        keys = _Keys().__enter__() if sys.stdin.isatty() else None
    except Exception:
        keys = None
    try:
        while True:
            k = keys.get() if keys else ""
            if k == "q":
                break
            elif k == "m":
                rx.toggle_pause()
            elif k == "n":
                p.set_param("smart_noise_cancel", not p.smart_noise_cancel)
            elif k == "v":
                p.voice_changer.enabled = not p.voice_changer.enabled
            elif k == "r":
                rx.toggle_recording()
            elif k == "t":
                rx.play_test_tone()
            now = time.time()
            if now - last >= 0.4:
                last = now
                _draw(rx, keys is not None)
            time.sleep(0.03)
    except KeyboardInterrupt:
        pass
    finally:
        if keys:
            keys.__exit__()
    print("\nStopping...")


def _draw(rx, interactive):
    st, p, jb = rx.stats, rx.processor, rx.jb
    state = rx.state()
    col = {"streaming": "green", "waiting": "cyan", "muted": "yellow", "lost": "yellow", "error": "red"}[state]
    db = p.level_db if state == "streaming" else -80.0
    n = max(0, min(30, int((db + 60) / 60 * 30)))
    bar = "#" * n + "." * (30 - n)
    dev = rx.main_dev.name if rx.main_dev else "none"
    out = ["\033[H\033[J" if interactive else ""]
    out.append(_c("bold", f"PhoneMic Receiver v{VERSION}") + "  (console mode)\n")
    out.append(f"Status  : {_c(col, state.upper())}  {rx.client_ip} {rx.transport if rx.client_ip else ''}\n")
    out.append(f"Listen  : {rx.netinfo.best_ip()}:{rx.config.data['network']['port']}  "
               f"{_c('red', rx.net.udp_error) if rx.net.udp_error else ''}\n")
    out.append(f"Output  : {dev} [{rx.api}]  latency ~ {rx.latency_estimate_ms():.0f} ms\n")
    out.append(f"Level   : [{bar}] {db:6.1f} dBFS\n")
    out.append(f"Network : jitter {st.jitter_ms:4.1f} ms | loss {st.loss_pct:4.2f}% | {st.bitrate_kbps:4.0f} kbps | "
               f"buffer {jb.depth_ms:.0f}/{jb.target_ms:.0f} ms | concealed {st.plc_frames}\n")
    out.append(f"Effects : noise suppression {'ON ' if p.smart_noise_cancel else 'off'} {int(p.noise_cancel_amount * 100)}% | "
               f"gate {'ON' if p.gate_enabled else 'off'} | voice {p.voice_changer.active_preset if p.voice_changer.enabled else 'off'}\n")
    if rx.recorder.active:
        out.append(_c("red", f"Recording: {rx.recorder.seconds:.0f} s -> {rx.recorder.path}\n"))
    if interactive:
        out.append(_c("dim", "\n[M]ute  [N]oise suppression  [V]oice changer  [R]ecord  [T]est tone  [Q]uit\n"))
    sys.stdout.write("".join(out))
    sys.stdout.flush()
