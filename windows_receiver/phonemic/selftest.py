"""Self-test for the parts that only a real Windows PC can verify. Run:  PhoneMicReceiver.exe --selftest
or press 'Run self-test' on the Diagnostics page, and send the result when something does not work."""
import sys
import time
import socket
from collections import namedtuple

from . import system, hotkeys, tray, cues
from .const import VERSION, INSTANCE_PORT

Result = namedtuple("Result", "name status detail")      # status: pass | fail | skip


def run_selftest():
    out = []

    def add(name, status, detail=""):
        out.append(Result(name, status, detail))

    add("Version and platform", "pass", f"PhoneMic Receiver {VERSION}, Python {sys.version.split()[0]}, {sys.platform}")

    # keyboard polling
    if not system.IS_WIN:
        add("Global shortcuts", "skip", "Windows only")
    else:
        try:
            be = hotkeys.WinKeyBackend()
            ctrl = be.down(0x11)
            t0 = time.perf_counter()
            for _ in range(1000):
                be.down(0x41)
            add("Global shortcuts: keyboard polling", "pass", f"GetAsyncKeyState works (1000 reads in {(time.perf_counter() - t0) * 1000:.1f} ms; Ctrl held: {ctrl})")
        except Exception as e:      # noqa: BLE001
            add("Global shortcuts: keyboard polling", "fail", repr(e))

    # tray
    mods = tray.load_modules()
    if mods is None:
        add("Tray icon", "skip", "pystray and Pillow are not installed (pip install pystray pillow). The app works without a tray.")
    else:
        try:
            img = tray.make_image("#4cd48a", mods[1], mods[2])
            ti = tray.TrayIcon({k: (lambda: None) for k in ("show", "mute", "monitor", "record", "bypass", "quit")},
                               lambda: {"muted": False, "monitoring": False, "recording": False, "bypassed": False})
            ok = ti.start("streaming")
            time.sleep(0.6)
            ti.set_state("muted", "PhoneMic self-test")
            time.sleep(0.4)
            ti.stop()
            add("Tray icon", "pass" if ok else "fail", f"icon image {img.size[0]}x{img.size[1]}; the icon appeared and disappeared" if ok else "pystray could not create the icon")
        except Exception as e:      # noqa: BLE001
            add("Tray icon", "fail", repr(e))

    # single-instance channel
    got = []
    stop = system.start_instance_listener(lambda: got.append(1), port=INSTANCE_PORT + 1)
    if stop is None:
        add("Second-launch channel", "fail", f"could not listen on 127.0.0.1:{INSTANCE_PORT + 1}")
    else:
        ok = system.signal_running_instance(port=INSTANCE_PORT + 1)
        for _ in range(40):                                  # the callback runs just after the acknowledgement is sent
            if got:
                break
            time.sleep(0.025)
        stop()
        add("Second-launch channel", "pass" if ok and got else "fail", "a second launch can reach the running copy" if ok and got else "no answer on loopback")

    # sound cues
    if system.IS_WIN:
        try:
            import winsound  # noqa: F401
            add("Sound cues", "pass", f"winsound is available ({len(cues.make_cue_wav('mute'))} bytes per cue)")
        except Exception as e:      # noqa: BLE001
            add("Sound cues", "fail", repr(e))
    else:
        add("Sound cues", "skip", "Windows only")

    # firewall / startup / network
    if system.IS_WIN:
        try:
            ok = system.firewall_rules_ok(5001)
            add("Windows Firewall rules", "pass" if ok else "fail",
                "inbound rules for port 5001 exist" if ok else "rules for port 5001 are missing: use Network, Fix firewall")
        except Exception as e:      # noqa: BLE001
            add("Windows Firewall rules", "fail", repr(e))
        add("Start with Windows", "pass", "currently " + ("on" if system.get_startup_enabled() else "off"))
    else:
        add("Windows Firewall rules", "skip", "Windows only")
    ni = system.NetworkInfo()
    found = ni.refresh()
    add("Network adapters", "pass" if found else "fail", ", ".join(i.label() for i in found) or "none found")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if system.IS_WIN and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("0.0.0.0", 5001))
        s.close()
        add("Port 5001", "pass", "free")
    except OSError as e:
        add("Port 5001", "pass", f"in use (normal while the receiver is running): {e}")
    return out


def format_results(results):
    mark = {"pass": "PASS", "fail": "FAIL", "skip": "skip"}
    lines = [f"{mark[r.status]:4s}  {r.name}: {r.detail}" for r in results]
    fails = sum(r.status == "fail" for r in results)
    lines.append("")
    lines.append("Everything that could be checked works." if not fails else f"{fails} check(s) failed. Please send this text when asking for help.")
    return "\n".join(lines)
