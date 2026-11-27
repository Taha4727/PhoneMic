"""Windows / OS integration helpers: paths, firewall, network discovery, startup, audio devices.

Everything here is written to be locale-independent (German/French/... Windows) and to never
block the GUI thread for long: slow things (netsh, ipconfig) are cached and refreshed in the
background.
"""
import os
import re
import sys
import time
import shutil
import socket
import tempfile
import threading
import subprocess
from dataclasses import dataclass

from .const import CABLE_HINT, MUTEX_NAME, INSTANCE_PORT

IS_WIN = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")
FROZEN = bool(getattr(sys, "frozen", False))


# ==============================================================================
# PATHS
# ==============================================================================
def app_dir():
    """Folder of the .exe (frozen) or of phonemic_receiver.py (source)."""
    if FROZEN:
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_data_dir_cache = None


def _is_dir_writable(path):
    try:
        probe = os.path.join(path, f".pm_write_test_{os.getpid()}")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("")
        os.remove(probe)
        return True
    except OSError:
        return False


def _xdg_config_dir():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def _xdg_user_documents():
    env_doc = os.environ.get("XDG_DOCUMENTS_DIR")
    if env_doc:
        return os.path.expandvars(os.path.expanduser(env_doc))
    cfg = os.path.join(_xdg_config_dir(), "user-dirs.dirs")
    try:
        with open(cfg, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if s.startswith("XDG_DOCUMENTS_DIR="):
                    val = s.split("=", 1)[1].strip().strip('"').strip("'")
                    val = val.replace("$HOME", os.path.expanduser("~"))
                    val = os.path.expandvars(os.path.expanduser(val))
                    if os.path.isdir(val):
                        return val
    except OSError:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def data_dir():
    """Where settings live: portable next to app on Windows (or if config exists there), else %LOCALAPPDATA%\\PhoneMic or XDG config."""
    global _data_dir_cache
    if _data_dir_cache:
        return _data_dir_cache
    override = os.environ.get("PHONEMIC_CONFIG_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        _data_dir_cache = override
        return override
    base = app_dir()
    if IS_WIN:
        if not os.path.isdir(base) or not _is_dir_writable(base):
            root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            base = os.path.join(root, "PhoneMic")
            os.makedirs(base, exist_ok=True)
    else:
        portable_cfg = os.path.join(base, "phonemic_config.json")
        if os.path.isfile(portable_cfg) and _is_dir_writable(base):
            _data_dir_cache = base
            return base
        base = os.path.join(_xdg_config_dir(), "phonemic")
        os.makedirs(base, exist_ok=True)
    _data_dir_cache = base
    return base


def config_path():
    return os.path.join(data_dir(), "phonemic_config.json")


def crash_log_path():
    return os.path.join(data_dir(), "phonemic_crash.log")


def default_recordings_dir():
    docs = os.path.join(os.path.expanduser("~"), "Documents") if IS_WIN else _xdg_user_documents()
    if os.path.isdir(docs):
        return os.path.join(docs, "PhoneMic Recordings")
    return os.path.join(data_dir(), "Recordings")


def open_in_explorer(path):
    try:
        if IS_WIN:
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


# ==============================================================================
# SILENT SUBPROCESSES (no console flashes, correct OEM code page)
# ==============================================================================
def _oem_encoding():
    if IS_WIN:
        try:
            import ctypes
            return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
        except Exception:
            pass
    return "utf-8"


def run_silent(args, timeout=4.0):
    kw = {}
    if IS_WIN:
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        kw["startupinfo"] = si
    try:
        return subprocess.run(args, capture_output=True, text=True, encoding=_oem_encoding(),
                              errors="replace", timeout=timeout, **kw)
    except Exception:
        return None


# ==============================================================================
# PROCESS / THREAD TUNING
# ==============================================================================
def enable_dpi_awareness():
    if not IS_WIN:
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def apply_dark_titlebar(window, dark=True):
    """Enable dark window title bar on Windows 10 (build 18985+) and Windows 11."""
    if not IS_WIN or window is None:
        return
    try:
        import ctypes
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        val = ctypes.c_int(1 if dark else 0)
        dwm = ctypes.windll.dwmapi
        # Attribute 20 works on Windows 10 20H1 (19041+) & Win 11; attribute 19 works on older Win 10 builds
        for attr in (20, 19):
            try:
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val))
            except Exception:
                pass
    except Exception:
        pass



def set_timer_resolution(ms=1, enable=True):
    """Windows' default 15.6 ms timer tick makes sleeps/waits coarse; 1 ms keeps audio threads punctual."""
    if not IS_WIN:
        return
    try:
        import ctypes
        (ctypes.windll.winmm.timeBeginPeriod if enable else ctypes.windll.winmm.timeEndPeriod)(ms)
    except Exception:
        pass


def boost_current_thread(level=1):
    """level 1 = ABOVE_NORMAL, 2 = HIGHEST. No-op off Windows."""
    if not IS_WIN:
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetThreadPriority(k32.GetCurrentThread(), level)
    except Exception:
        pass


def acquire_single_instance():
    """Returns True if we are the only instance (keeps Win32 mutex or POSIX flock alive for process life)."""
    if IS_WIN:
        try:
            import ctypes
            handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
            already = ctypes.windll.kernel32.GetLastError() == 183   # ERROR_ALREADY_EXISTS
            acquire_single_instance._handle = handle                  # keep reference
            return not already
        except Exception:
            return True
    try:
        import fcntl
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        if runtime_dir and os.path.isdir(runtime_dir):
            lock_path = os.path.join(runtime_dir, "phonemic-receiver.lock")
        else:
            uid = os.getuid() if hasattr(os, "getuid") else 0
            lock_path = os.path.join(tempfile.gettempdir(), f"phonemic-receiver-{uid}.lock")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("ascii"))
        acquire_single_instance._fd = fd
        return True
    except Exception:
        return True


def start_instance_listener(on_show, port=INSTANCE_PORT):
    """Listen on loopback for a second launch asking us to show our window. Returns a stop() function, or None if the port is busy."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        return None
    sock.settimeout(0.5)
    stopped = threading.Event()

    def loop():
        while not stopped.is_set():
            try:
                data, addr = sock.recvfrom(64)
            except socket.timeout:
                continue
            except OSError:
                break
            if data == b"PM_SHOW":
                try:
                    sock.sendto(b"PM_OK", addr)
                except OSError:
                    pass
                try:
                    on_show()
                except Exception:
                    pass
        sock.close()

    threading.Thread(target=loop, name="PM-Instance", daemon=True).start()
    return stopped.set


def signal_running_instance(port=INSTANCE_PORT, timeout=0.8):
    """Ask the copy that is already running to show its window. True only if it answered."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(b"PM_SHOW", ("127.0.0.1", port))
        return s.recvfrom(16)[0] == b"PM_OK"
    except OSError:
        return False
    finally:
        s.close()


def is_admin():
    if not IS_WIN:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ==============================================================================
# FIREWALL (Windows Defender & Linux ufw/firewalld)
# ==============================================================================
def firewall_rule_names(port):
    return [f"PhoneMic Receiver (UDP {port})", f"PhoneMic Receiver (TCP {port})"]


def firewall_summary(port):
    """Return `(ok_or_none, short_label, detail_text)` for the current OS."""
    if IS_WIN:
        ok = firewall_rules_ok(port)
        if ok:
            return True, "Rules present", f"Windows Firewall allows UDP/TCP port {port}."
        return False, "Rules missing", "Rules for USB/LAN streaming are missing."
    if not IS_LINUX:
        return True, "Open", "Host firewall check not required."

    # Check firewalld (common on Fedora/Arch optional)
    if shutil.which("firewall-cmd"):
        st = run_silent(["systemctl", "is-active", "--quiet", "firewalld"], timeout=2.0)
        if st is not None and st.returncode == 0:
            u = run_silent(["firewall-cmd", f"--query-port={port}/udp"], timeout=2.0)
            t = run_silent(["firewall-cmd", f"--query-port={port}/tcp"], timeout=2.0)
            if u and t and u.returncode == 0 and t.returncode == 0:
                return True, "firewalld allowed", f"Ports {port}/udp and {port}/tcp are open in firewalld."
            return (
                False,
                "firewalld missing rule",
                f"Run: sudo firewall-cmd --add-port={port}/udp --add-port={port}/tcp --permanent && sudo firewall-cmd --reload",
            )

    # Check ufw (common on Arch)
    if shutil.which("ufw"):
        st = run_silent(["systemctl", "is-active", "--quiet", "ufw"], timeout=2.0)
        if st is not None and st.returncode == 0:
            p = run_silent(["ufw", "status"], timeout=2.0)
            out = (p.stdout or "") if p else ""
            if p and p.returncode == 0 and "inactive" not in out.lower():
                has_udp = f"{port}/udp" in out or (f"{port} " in out and "ALLOW" in out)
                has_tcp = f"{port}/tcp" in out or (f"{port} " in out and "ALLOW" in out)
                if has_udp and has_tcp:
                    return True, "UFW allowed", f"Ports {port}/udp and {port}/tcp are allowed in UFW."
                return (
                    False,
                    "UFW missing rule",
                    f"Run: sudo ufw allow {port}/udp && sudo ufw allow {port}/tcp",
                )
            return (
                None,
                "UFW active (check rules)",
                f"If phone cannot connect, run: sudo ufw allow {port}/udp && sudo ufw allow {port}/tcp",
            )

    return True, "No blocking firewall", f"No active ufw/firewalld blocking port {port}."


def firewall_rules_ok(port):
    """True when inbound rules exist or no host firewall is blocking the port."""
    if not IS_WIN:
        ok, _, _ = firewall_summary(port)
        return ok is not False
    for name in firewall_rule_names(port):
        p = run_silent(["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"], timeout=4.0)
        if not p or p.returncode != 0 or "PhoneMic" not in (p.stdout or ""):
            return False
    return True


def _firewall_commands(port):
    cmds = []
    for proto in ("UDP", "TCP"):
        name = f"PhoneMic Receiver ({proto} {port})"
        cmds.append(f'netsh advfirewall firewall delete rule name="{name}" >nul 2>&1')
        cmds.append(f'netsh advfirewall firewall add rule name="{name}" dir=in action=allow '
                    f'protocol={proto} localport={port} profile=any enable=yes')
    if FROZEN:
        cmds.append('netsh advfirewall firewall delete rule name="PhoneMic Receiver App" >nul 2>&1')
        cmds.append(f'netsh advfirewall firewall add rule name="PhoneMic Receiver App" dir=in action=allow '
                    f'program="{sys.executable}" profile=any enable=yes')
    return cmds


def configure_firewall(port):
    """Create the inbound rules. Asks for UAC/pkexec elevation when needed.
    Returns (launched: bool, message). Caller should re-check with firewall_rules_ok() afterwards."""
    if IS_LINUX:
        ok, _short, detail = firewall_summary(port)
        if ok is True:
            return True, detail
        pkexec = shutil.which("pkexec")
        cmd = None
        if shutil.which("firewall-cmd"):
            st = run_silent(["systemctl", "is-active", "--quiet", "firewalld"], timeout=2.0)
            if st is not None and st.returncode == 0:
                cmd = f"firewall-cmd --add-port={int(port)}/udp --add-port={int(port)}/tcp --permanent && firewall-cmd --reload"
        if cmd is None and shutil.which("ufw"):
            st = run_silent(["systemctl", "is-active", "--quiet", "ufw"], timeout=2.0)
            if st is not None and st.returncode == 0:
                cmd = f"ufw allow {int(port)}/udp && ufw allow {int(port)}/tcp"
        if cmd is None:
            return True, "No active Linux firewall needed configuration."
        if pkexec:
            p = subprocess.run([pkexec, "sh", "-c", cmd], capture_output=True, text=True)
            if p.returncode == 0:
                return True, f"Firewall rules applied for port {port}."
            return False, (p.stderr or "Authorization cancelled.").strip()
        return False, detail
    if not IS_WIN:
        return True, "Not on Windows - nothing to do."
    bat = os.path.join(tempfile.gettempdir(), "phonemic_firewall.bat")
    try:
        with open(bat, "w", encoding=_oem_encoding(), errors="replace") as f:
            f.write("@echo off\r\n" + "\r\n".join(_firewall_commands(port)) + "\r\n")
    except Exception as e:
        return False, f"Could not write helper script: {e}"
    try:
        import ctypes
        if is_admin():
            for line in _firewall_commands(port):
                subprocess.run(line, shell=True, capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
            return True, "Firewall rules applied."
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", bat, None, None, 0)
        if rc > 32:
            return True, "Approve the Windows prompt to finish configuring the firewall."
        return False, "Administrator approval was declined."
    except Exception as e:
        return False, f"Firewall configuration failed: {e}"


# ==============================================================================
# NETWORK DISCOVERY
# ==============================================================================
@dataclass
class NetIface:
    category: str
    ip: str
    name: str = ""

    def label(self):
        return f"{self.ip} ({self.category})"


_VIRTUAL_KEYS = ("virtual", "vbox", "virtualbox", "vmware", "vethernet", "wsl", "hyper-v", "loopback",
                 "docker", "tap-", "tailscale", "zerotier", "bluetooth", "npcap", "pseudo",
                 "virbr", "veth", "waydroid", "incusbr", "lxdbr", "tun", "tap", "wg")
_USB_KEYS = ("rndis", "remote ndis", "tether", "android", "samsung", "pixel", "poco", "xiaomi", "oneplus",
             "usb ethernet", "usb network", "usb to ethernet", "cdc ethernet", "ncm", "mobile broadband")
_WIFI_KEYS = ("wi-fi", "wifi", "wlan", "wireless", "drahtlos", "802.11", "wi\u2011fi", "sans fil", "inal\u00e1mbrica", "wlp", "wlx")
_CATEGORY_ORDER = {"Wi-Fi": 0, "Ethernet": 1, "Network": 2, "USB Tether": 3, "PC Hotspot": 4, "Virtual": 5}
_LINUX_USB_NAME_RE = re.compile(r"^(?:usb\d+|rndis\d+|enp\d+s\d+.*u\d+|enx[0-9a-f]+)$")
_LINUX_ETH_NAME_RE = re.compile(r"^(?:eth\d+|en[ops]\w+)$")
_LINUX_VIRT_NAME_RE = re.compile(r"^(?:br-[0-9a-f]+|virbr\d*|docker\d*|veth\w+|vboxnet\d*|vmnet\d+|tun\d*|tap\d*|wg\d*|tailscale\d*|zt\w+|waydroid\d*|incusbr\d*|lxdbr\d*|lo)$")


def classify_interface(adapter_name, description, ip):
    """Pure function (unit-tested). Names are matched case-insensitively across locales."""
    adapter_low = (adapter_name or "").strip().lower()
    text = f"{adapter_name} {description}".lower()
    if ip.startswith("192.168.137."):
        return "PC Hotspot"
    if _LINUX_VIRT_NAME_RE.match(adapter_low) or any(k in text for k in _VIRTUAL_KEYS) or ip.startswith(("192.168.56.", "172.17.")):
        return "Virtual"
    if _LINUX_USB_NAME_RE.match(adapter_low) or any(k in text for k in _USB_KEYS) or ip.startswith("192.168.42."):
        return "USB Tether"
    if adapter_low.startswith(("wlan", "wlp", "wlx")) or any(k in text for k in _WIFI_KEYS):
        return "Wi-Fi"
    if _LINUX_ETH_NAME_RE.match(adapter_low) or "ethernet" in text or "lan" in text or "gbe" in text or "realtek" in text or "intel" in text:
        return "Ethernet"
    return "Network"


_IPV4_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")
_DESC_RE = re.compile(r"^\s*(description|beschreibung|descripci[o\u00f3]n|descrizione|beschrijving|opis)\b", re.I)
_IP_ADDR_LINE_RE = re.compile(r"^\d+:\s+([^\s:@]+)(?:@[^\s:]+)?\s+inet\s+(\d{1,3}(?:\.\d{1,3}){3})(?:/\d+|\s)")


def parse_ipconfig(text):
    """Parse `ipconfig /all` output of any language into NetIface entries."""
    result, seen = [], set()
    name, desc = "", ""
    for raw in (text or "").splitlines():
        if not raw.strip():
            continue
        if not raw[0].isspace() and raw.rstrip().endswith(":"):      # adapter header line
            name, desc = raw.strip().rstrip(":"), ""
            continue
        if _DESC_RE.match(raw) and ":" in raw and not desc:
            desc = raw.split(":", 1)[1].strip()
            continue
        low = raw.lower()
        is_v4_line = "ipv4" in low or re.match(r"\s*ip[- ]?(address|adresse)\b", low)
        if is_v4_line and "ipv6" not in low:
            m = _IPV4_RE.search(raw)
            if not m:
                continue
            ip = m.group(1)
            if ip.startswith(("127.", "169.254.", "0.")) or ip in seen:
                continue
            seen.add(ip)
            result.append(NetIface(classify_interface(name, desc, ip), ip, name))
    return result


def parse_ip_addr(text):
    """Parse Linux `ip -o -4 addr show` output into NetIface entries."""
    result, seen = [], set()
    for raw in (text or "").splitlines():
        m = _IP_ADDR_LINE_RE.match(raw.strip())
        if not m:
            continue
        iface, ip = m.group(1), m.group(2)
        if iface == "lo" or ip.startswith(("127.", "169.254.", "0.")) or ip in seen:
            continue
        seen.add(ip)
        result.append(NetIface(classify_interface(iface, "", ip), ip, iface))
    return result


def _socket_interfaces():
    """No-subprocess fallback: hostname addresses + the outbound interface."""
    found, seen = [], set()

    def add(ip):
        if ip and ip not in seen and not ip.startswith(("127.", "169.254.", "0.")):
            seen.add(ip)
            found.append(NetIface(classify_interface("", "", ip), ip, ""))

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))          # no packet is sent for UDP connect
        add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            add(ip)
    except Exception:
        pass
    return found


class NetworkInfo:
    """Cached, thread-safe view of this PC's IPv4 interfaces (ipconfig/ip are run off the GUI thread)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._cache = _socket_interfaces()
        self._ts = 0.0
        self._busy = False

    def _scan(self):
        found = []
        if IS_WIN:
            p = run_silent(["ipconfig", "/all"], timeout=5.0)
            if p and p.returncode == 0:
                found = parse_ipconfig(p.stdout)
        elif IS_LINUX:
            ip_bin = shutil.which("ip") or next((c for c in ("/usr/bin/ip", "/usr/sbin/ip", "/sbin/ip") if os.path.exists(c)), "ip")
            p = run_silent([ip_bin, "-o", "-4", "addr", "show"], timeout=3.0)
            if p and p.returncode == 0:
                found = parse_ip_addr(p.stdout)
        known = {i.ip for i in found}
        for i in _socket_interfaces():          # always merge, covers parse failures
            if i.ip not in known:
                found.append(i)
        found.sort(key=lambda i: _CATEGORY_ORDER.get(i.category, 9))
        with self._lock:
            self._cache, self._ts = found, time.time()
        return found

    def refresh(self):
        """Blocking refresh."""
        return self._scan()

    def refresh_async(self, callback=None):
        with self._lock:
            if self._busy:
                return
            self._busy = True

        def work():
            try:
                res = self._scan()
                if callback:
                    callback(res)
            finally:
                with self._lock:
                    self._busy = False

        threading.Thread(target=work, name="PM-NetScan", daemon=True).start()

    def get(self, max_age=10.0):
        if time.time() - self._ts > max_age:
            self.refresh_async()
        with self._lock:
            return list(self._cache)

    # -- convenience --------------------------------------------------------------
    def first(self, *cats):
        for i in self.get():
            if i.category in cats:
                return i.ip
        return ""

    def best_ip(self):
        for i in self.get():
            if i.category in ("Wi-Fi", "Ethernet", "Network"):
                return i.ip
        for i in self.get():
            if i.category != "Virtual":
                return i.ip
        return "127.0.0.1"

    def matching_ip(self, client_ip):
        """Our address on the same subnet as the phone - so replies route over USB when the phone is on USB."""
        parts = str(client_ip).split(".")
        ifaces = self.get()
        if len(parts) == 4:
            for prefix in (".".join(parts[:3]) + ".", ".".join(parts[:2]) + "."):
                for i in ifaces:
                    if i.ip.startswith(prefix):
                        return i.ip
        return self.best_ip()

    def broadcast_targets(self):
        out = []
        for i in self.get():
            if i.category == "Virtual":
                continue
            p = i.ip.split(".")
            if len(p) == 4:
                out.append((i.ip, ".".join(p[:3]) + ".255"))
        return out


# ==============================================================================
# AUTOSTART (Windows Registry / Linux XDG Autostart)
# ==============================================================================
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "PhoneMicReceiver"


def _linux_autostart_path():
    return os.path.join(_xdg_config_dir(), "autostart", "phonemic-receiver.desktop")


def startup_command():
    if FROZEN:
        return f'"{sys.executable}" --minimized'
    if IS_WIN:
        exe = sys.executable
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pyw):
            exe = pyw
        script = os.path.join(app_dir(), "phonemic_receiver.py")
        return f'"{exe}" "{script}" --minimized'
    if IS_LINUX and os.path.isfile("/usr/bin/phonemic-receiver") and app_dir().startswith("/usr/"):
        return "/usr/bin/phonemic-receiver --minimized"
    script = os.path.join(app_dir(), "phonemic_receiver.py")
    return f'"{sys.executable}" "{script}" --minimized'


def get_startup_enabled():
    if IS_LINUX:
        path = _linux_autostart_path()
        if not os.path.isfile(path):
            return False
        try:
            txt = open(path, "r", encoding="utf-8", errors="replace").read()
            return "Hidden=true" not in txt
        except OSError:
            return False
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, _RUN_VALUE)
            return True
    except Exception:
        return False


def set_startup_enabled(enabled):
    if IS_LINUX:
        path = _linux_autostart_path()
        try:
            if enabled:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                content = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=PhoneMic Receiver\n"
                    "Comment=Use your phone as a low-latency studio microphone\n"
                    f"Exec={startup_command()}\n"
                    "Icon=phonemic-receiver\n"
                    "Terminal=false\n"
                    "Categories=AudioVideo;Audio;\n"
                    "X-GNOME-Autostart-enabled=true\n"
                )
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
            return True
        except Exception:
            return False
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, _RUN_VALUE, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(k, _RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


# ==============================================================================
# AUDIO DEVICES
# ==============================================================================
@dataclass
class AudioDevice:
    index: int
    name: str
    api: str
    channels: int
    default_sr: float
    is_default: bool = False
    sink_name: str = ""

    @property
    def is_cable(self):
        n = (self.name or "").lower()
        s = (self.sink_name or "").lower()
        return (
            CABLE_HINT.lower() in n
            or "phonemic_sink" in s
            or "phonemic virtual mic" in n
            or "phonemic_virtual_mic" in n
        )


def _api_rank(api):
    a = (api or "").lower()
    if IS_WIN:
        if "wasapi" in a:
            return 0
        if "directsound" in a:
            return 1
        if "mme" in a:
            return 2
        if "wdm" in a:
            return 3
        return 4
    if "pipewire" in a:
        return 0
    if "pulse" in a:
        return 1
    if "jack" in a:
        return 2
    if "alsa" in a:
        return 3
    if "wasapi" in a:
        return 4
    if "directsound" in a:
        return 5
    if "mme" in a:
        return 6
    if "wdm" in a:
        return 7
    return 8


def _linux_virtual_and_pulse_devices(raw_devs):
    """Expose PipeWire / PulseAudio sinks via the PortAudio ALSA bridge on Linux."""
    if not IS_LINUX:
        return []
    bridge = None
    for preferred in ("pipewire", "pulse", "default"):
        bridge = next(
            (d for d in raw_devs if d.name.strip().lower() == preferred and ("alsa" in d.api.lower() or "pipewire" in d.api.lower() or "pulse" in d.api.lower())),
            None,
        )
        if bridge is not None:
            break
    if bridge is None:
        return []
    from . import virtual_mic
    if not virtual_mic.pactl_available():
        return []
    backend, _ = virtual_mic.server_info()
    if not backend:
        return []
    sinks = virtual_mic.list_sinks()
    if not sinks:
        return []
    out = []
    # Put PhoneMic_Sink first when present so pick_default_output & UI highlight it cleanly
    ordered = sorted(sinks, key=lambda s: (0 if s.name == virtual_mic.SINK_NAME else (1 if s.is_default else 2), s.description.lower()))
    for s in ordered:
        if s.name == virtual_mic.SINK_NAME:
            label = f"{virtual_mic.FRIENDLY_DEVICE_LABEL}"
            is_def = False
        else:
            label = f"{s.description} [{backend}]"
            is_def = s.is_default
        out.append(
            AudioDevice(
                index=bridge.index,
                name=label,
                api=backend,
                channels=max(2, bridge.channels),
                default_sr=bridge.default_sr,
                is_default=is_def,
                sink_name=s.name,
            )
        )
    return out


def list_output_devices(sd):
    """All output-capable devices across host APIs (WDM-KS is skipped: it is flaky for shared use)."""
    if sd is None:
        return []
    try:
        devices = sd.query_devices()
        apis = sd.query_hostapis()
    except Exception:
        return []
    out = []
    for idx, d in enumerate(devices):
        if d.get("max_output_channels", 0) <= 0:
            continue
        try:
            api = apis[d["hostapi"]]
        except Exception:
            api = {"name": "?", "default_output_device": -1}
        if "wdm" in api.get("name", "").lower():
            continue
        out.append(AudioDevice(idx, d.get("name", f"Device {idx}"), api.get("name", "?"),
                               int(d.get("max_output_channels", 2)), float(d.get("default_samplerate", 48000)),
                               api.get("default_output_device", -1) == idx))
    if IS_LINUX:
        pulse_devs = _linux_virtual_and_pulse_devices(out)
        if pulse_devs:
            return pulse_devs + out
    return out


def available_apis(devs):
    return sorted({d.api for d in devs}, key=_api_rank)


def resolve_api(devs, pref):
    """pref: 'auto' or a substring such as 'WASAPI' / 'PipeWire'. Returns the concrete host API name to use."""
    apis = available_apis(devs)
    if not apis:
        return ""
    if pref and pref.lower() != "auto":
        for a in apis:
            if pref.lower() in a.lower():
                return a
    return apis[0]


def devices_for_api(devs, api):
    return [d for d in devs if d.api == api]


def name_matches(a, b):
    """MME truncates names to 31 chars, so compare by prefix."""
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    return bool(a and b and (a.startswith(b) or b.startswith(a)))


def find_device(devs, name, api=None):
    pool = [d for d in devs if (not api or d.api == api)] or devs
    for d in pool:
        if name_matches(d.name, name):
            return d
    return None


def pick_default_output(devs, api):
    pool = devices_for_api(devs, api) or devs
    for d in pool:
        if d.is_cable:
            return d
    for d in pool:
        if d.is_default:
            return d
    return pool[0] if pool else None


def pick_default_monitor(devs, api):
    pool = devices_for_api(devs, api) or devs
    for d in pool:
        if d.is_default and not d.is_cable:
            return d
    for d in pool:
        if not d.is_cable:
            return d
    return pool[0] if pool else None
