#!/usr/bin/env python3
"""
================================================================================
PhoneMic Windows Receiver v0.7.5 (Studio DSP & Modern GUI Native Engine)
================================================================================
Turn your Android phone into an ultra-low latency, studio-quality PC microphone
over Wi-Fi or USB Tethering.

v0.7.5 Improvements:
1. Studio DSP Noise Canceling:
   - Replaced flawed block FFT with 50% Weighted Overlap-Add (WOLA) Sine-window
     Wiener Filter + 80Hz Butterworth 2nd-order High-Pass rumble cut.
   - Frequency-smoothed and time-smoothed gain masking completely eliminates
     musical chirps, 100Hz modulation buzz, and artifacts.
2. Artifact-Free Voice Pitch Shifter:
   - Dual-Tap Rotating Harmonizer with raised-cosine crossfading.
   - Zero clicks, zero discontinuities, and smooth continuous pitch shifting
     from -12.0 to +12.0 semitones.
3. Real 3-Band Parametric Equalizer:
   - Robert Bristow-Johnson (RBJ) Biquad IIR filters in Direct Form II Transposed.
   - Low Shelf (Warmth @ 120Hz), Mid Peaking (Clarity/Presence @ 2500Hz),
     High Shelf (Air/Sparkle @ 8000Hz).
   - Instant studio presets: Flat, Broadcast Warmth, Crisp Vocal, De-Boom, Telephone.
4. Redesigned Modern Obsidian UI:
   - Modern dark slate / obsidian aesthetic inspired by Material 3 and Windows 11 Fluent 2.
   - Custom segmented pill tab bar (Dashboard, Audio Studio FX, Network & Endpoints).
   - 32-Band neon spectrum visualizer with ballistic peak-hold gravity and oscilloscope mode.
   - Stereo VU meter with calibrated dB markings and peak hold.
   - Telemetry metric cards (Protocol, Medium, Jitter, Bitrate, Loss, Uptime).
   - Silent background threads (CREATE_NO_WINDOW) preventing any cmd window flashes.
"""

import sys
import os
import re
import math
import time
import json
import struct
import socket
import select
import shutil
import platform
import subprocess
import threading
import queue
import wave
import webbrowser

# Tkinter GUI Imports
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

# Third-party audio and DSP libraries
np = None
sd = None
try:
    import numpy as np
except ImportError:
    pass

try:
    import sounddevice as sd
except ImportError:
    pass

# ==============================================================================
# AUDIO & NETWORKING CONSTANTS
# ==============================================================================
VERSION = "0.8.0"
HOST = "0.0.0.0"
DEFAULT_PORT = 5001
AUDIO_RATE = 48000
OUTPUT_CHANNELS = 2             # Stereo output for Windows audio subsystem
TARGET_DEVICE_NAME = "CABLE Input"
TARGET_DISPLAY_NAME = "VB-CABLE"

FRAMES_PER_PACKET = 480         # 10ms frame at 48kHz
PCM_BYTES_PER_PACKET = 960      # 480 samples * 2 bytes (16-bit mono)

PACKET_MAGIC = b'PM01'          # PhoneMic Protocol Header
DISCOVERY_PROBE = b'PM_DISCOVER'
DISCOVERY_REPLY = b'PMA1'
CMD_PAUSE = b'PMP1'             # PhoneMic Remote Pause/Mute Command (matches PhoneMicService.kt)
CMD_RESUME = b'PMR1'            # PhoneMic Remote Resume Command (matches PhoneMicService.kt)

VB_CABLE_PAGE = "https://vb-audio.com/Cable/"

DEFAULT_GAIN = 1.0
NOISE_GATE_THRESHOLD_DB = -55.0
LIMITER_CEILING = 0.98

# Winsock IOCTL for UDP connection reset suppression on Windows
SIO_UDP_CONNRESET = 0x9800000C

# ==============================================================================
# ENVIRONMENT, DIRECTORIES & PERSISTENCE
# ==============================================================================
def get_app_dir():
    """Returns the directory of the script or compiled PyInstaller executable."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_cache_marker_path():
    """Returns path to dependency verification cache marker file."""
    app_dir = get_app_dir()
    marker = os.path.join(app_dir, ".phonemic_deps_ok")
    if not os.access(app_dir, os.W_OK):
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        base = os.path.join(appdata, "PhoneMic")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, ".phonemic_deps_ok")
    return marker

def get_config_path():
    """Returns path to the persistent JSON configuration file."""
    app_dir = get_app_dir()
    cfg = os.path.join(app_dir, "phonemic_config.json")
    if not os.access(app_dir, os.W_OK):
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        base = os.path.join(appdata, "PhoneMic")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "phonemic_config.json")
    return cfg


class ConfigManager:
    """
    Persistent configuration and preset storage manager.
    Auto-saves and restores user settings, active presets, custom presets, and device selections.
    """
    def __init__(self, filepath=None):
        self.filepath = filepath or get_config_path()
        self.data = self._default_config()
        self.load()

    def _default_config(self):
        return {
            "version": VERSION,
            "target_device_name": None,
            "monitor_device_name": None,
            "visualizer_mode": "spectrum",
            "studio_fx": {
                "active_preset": "Default (Studio Clean)",
                "gain": 1.0,
                "smart_noise_cancel": True,
                "noise_cancel_amount": 0.65,
                "gate_threshold_db": -55.0,
                "eq_low_gain_db": 0.0,
                "eq_mid_gain_db": 0.0,
                "eq_high_gain_db": 0.0,
                "monitor_volume": 0.85
            },
            "voice_changer": {
                "enabled": False,
                "active_preset": "Normal (Bypass)",
                "mode": "Natural Pitch",
                "pitch_semitones": 0.0,
                "mix": 1.0
            },
            "user_fx_presets": {},
            "user_voice_presets": {}
        }

    def load(self):
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        if "studio_fx" in saved and isinstance(saved["studio_fx"], dict):
                            self.data["studio_fx"].update(saved["studio_fx"])
                        if "voice_changer" in saved and isinstance(saved["voice_changer"], dict):
                            self.data["voice_changer"].update(saved["voice_changer"])
                        if "user_fx_presets" in saved and isinstance(saved["user_fx_presets"], dict):
                            self.data["user_fx_presets"].update(saved["user_fx_presets"])
                        if "user_voice_presets" in saved and isinstance(saved["user_voice_presets"], dict):
                            self.data["user_voice_presets"].update(saved["user_voice_presets"])
                        for k in ("target_device_name", "monitor_device_name", "visualizer_mode"):
                            if k in saved and saved[k] is not None:
                                self.data[k] = saved[k]
        except Exception as e:
            print(f"[!] Config load notice: {e}")

    def save(self):
        try:
            tmp_path = self.filepath + ".tmp"
            os.makedirs(os.path.dirname(os.path.abspath(self.filepath)), exist_ok=True)
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
            if os.name == 'nt' and os.path.exists(self.filepath):
                try:
                    os.remove(self.filepath)
                except Exception:
                    pass
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            print(f"[!] Config save notice: {e}")

# ==============================================================================
# TERMINAL COLORS & FORMATTING
# ==============================================================================
class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

ANSI_REGEX = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

def visible_length(s):
    return len(ANSI_REGEX.sub('', s))

def fit_line_width(text, max_cols):
    vlen = visible_length(text)
    if vlen < max_cols:
        return text + (' ' * (max_cols - vlen))
    elif vlen > max_cols:
        clean = ANSI_REGEX.sub('', text)
        return clean[:max(0, max_cols - 3)] + '...'
    return text

def safe_input(prompt_text, default=''):
    try:
        return input(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        return default

# Windows Console handle and cursor management
kernel32 = None
stdout_handle = None

def init_windows_console():
    global kernel32, stdout_handle
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            stdout_handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode))
            mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(stdout_handle, mode)
        except Exception:
            pass

def hide_cursor():
    if os.name == 'nt' and kernel32 is not None and stdout_handle is not None:
        try:
            import ctypes
            class CONSOLE_CURSOR_INFO(ctypes.Structure):
                _fields_ = [('dwSize', ctypes.c_ulong), ('bVisible', ctypes.c_bool)]
            info = CONSOLE_CURSOR_INFO(dwSize=25, bVisible=False)
            kernel32.SetConsoleCursorInfo(stdout_handle, ctypes.byref(info))
        except Exception:
            pass
    else:
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()

def show_cursor():
    if os.name == 'nt' and kernel32 is not None and stdout_handle is not None:
        try:
            import ctypes
            class CONSOLE_CURSOR_INFO(ctypes.Structure):
                _fields_ = [('dwSize', ctypes.c_ulong), ('bVisible', ctypes.c_bool)]
            info = CONSOLE_CURSOR_INFO(dwSize=25, bVisible=True)
            kernel32.SetConsoleCursorInfo(stdout_handle, ctypes.byref(info))
        except Exception:
            pass
    else:
        sys.stdout.write('\033[?25h')
        sys.stdout.flush()

def reset_cursor_to_top():
    if os.name == 'nt' and kernel32 is not None and stdout_handle is not None:
        try:
            import ctypes
            kernel32.SetConsoleCursorPosition(stdout_handle, ctypes.c_ulong(0))
            return
        except Exception:
            pass
    sys.stdout.write('\033[H')

# ==============================================================================
# DEPENDENCY VERIFICATION
# ==============================================================================
def is_already_verified():
    global np, sd
    if getattr(sys, 'frozen', False):
        return True

    marker_path = get_cache_marker_path()
    if os.path.exists(marker_path):
        if np is not None and sd is not None:
            return True
        try:
            import numpy as np_mod
            import sounddevice as sd_mod
            np = np_mod
            sd = sd_mod
            return True
        except ImportError:
            try:
                os.remove(marker_path)
            except Exception:
                pass
            return False

    if np is not None and sd is not None:
        mark_dependencies_verified()
        return True

    try:
        import numpy as np_mod
        import sounddevice as sd_mod
        np = np_mod
        sd = sd_mod
        mark_dependencies_verified()
        return True
    except ImportError:
        return False

def mark_dependencies_verified():
    try:
        marker_path = get_cache_marker_path()
        data = {
            "version": VERSION,
            "timestamp": time.time(),
            "python": sys.version,
            "platform": platform.platform()
        }
        with open(marker_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def run_interactive_dependency_fixer():
    global np, sd
    print(f"\n{Colors.CYAN}{'═' * 76}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN} PhoneMic Audio & Dependency Diagnostic Utility (v{VERSION}){Colors.RESET}")
    print(f"{Colors.CYAN}{'═' * 76}{Colors.RESET}\n")

    numpy_ok = False
    if np is None:
        try:
            import numpy as np_mod
            np = np_mod
        except ImportError:
            pass

    if np is not None:
        print(f"[*] NumPy DSP Library: {Colors.GREEN}[✓] Active ({np.__version__}){Colors.RESET}")
        numpy_ok = True
    else:
        print(f"[*] NumPy DSP Library: {Colors.YELLOW}[!] Missing{Colors.RESET}")
        if not getattr(sys, 'frozen', False):
            choice = safe_input("    Install NumPy now via pip? [Y/n]: ").lower()
            if choice in ('', 'y', 'yes', '1'):
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy"])
                    import numpy as np_mod
                    np = np_mod
                    numpy_ok = True
                    print(f"    {Colors.GREEN}[✓] NumPy installed successfully!{Colors.RESET}")
                except Exception as e:
                    print(f"    {Colors.RED}[✗] Installation failed: {e}{Colors.RESET}")

    sd_ok = False
    if sd is None:
        try:
            import sounddevice as sd_mod
            sd = sd_mod
        except ImportError:
            pass

    if sd is not None:
        print(f"[*] SoundDevice Audio Engine: {Colors.GREEN}[✓] Active{Colors.RESET}")
        sd_ok = True
    else:
        print(f"[*] SoundDevice Audio Engine: {Colors.YELLOW}[!] Missing{Colors.RESET}")
        if not getattr(sys, 'frozen', False):
            choice = safe_input("    Install sounddevice now via pip? [Y/n]: ").lower()
            if choice in ('', 'y', 'yes', '1'):
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "sounddevice"])
                    import sounddevice as sd_mod
                    sd = sd_mod
                    sd_ok = True
                    print(f"    {Colors.GREEN}[✓] sounddevice installed successfully!{Colors.RESET}")
                except Exception as e:
                    print(f"    {Colors.RED}[✗] Installation failed: {e}{Colors.RESET}")

    cable_dev, default_out, _ = find_audio_devices()
    if cable_dev:
        print(f"[*] Virtual Cable: {Colors.GREEN}[✓] Found: {cable_dev[1].get('name')}{Colors.RESET}")
    else:
        print(f"[*] Virtual Cable: {Colors.YELLOW}[!] Not installed (Optional, needed for Discord/OBS/Zoom){Colors.RESET}")
        if default_out:
            print(f"    Will output to speakers: {default_out[1].get('name')}")

    fw_ok = check_windows_firewall_rule()
    print(f"[*] Windows Firewall: {Colors.GREEN if fw_ok else Colors.YELLOW}[{'✓' if fw_ok else '!'}] Port {DEFAULT_PORT} rules configured{Colors.RESET}")

    all_core_ok = numpy_ok and sd_ok
    if all_core_ok:
        mark_dependencies_verified()
        print(f"\n{Colors.GREEN}[✓] Core audio and DSP dependencies verified.{Colors.RESET}\n")
        return True
    else:
        print(f"\n{Colors.RED}[✗] Core dependencies missing. Please install numpy and sounddevice.{Colors.RESET}\n")
        return False

# ==============================================================================
# SILENT PROCESS EXECUTION (NO CMD WINDOW FLASHES)
# ==============================================================================
def run_silent_cmd(cmd_list, timeout=3.0, shell=False):
    """
    Executes a command completely silently without flashing or opening any visible
    command prompt or conhost window on Windows, even in PyInstaller windowed mode (console=False).
    Handles both list arguments and string commands seamlessly.
    """
    creationflags = 0
    startupinfo = None
    if os.name == 'nt':
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    exec_cmd = cmd_list
    exec_shell = shell
    if isinstance(cmd_list, str) and not shell:
        import shlex
        try:
            exec_cmd = shlex.split(cmd_list)
        except Exception:
            exec_shell = True

    try:
        return subprocess.run(
            exec_cmd,
            capture_output=True,
            text=True,
            encoding='cp437',
            errors='replace',
            timeout=timeout,
            shell=exec_shell,
            creationflags=creationflags,
            startupinfo=startupinfo
        )
    except Exception:
        return None

# ==============================================================================
# WINDOWS FIREWALL AUTO-CONFIGURATION
# ==============================================================================
def check_windows_firewall_rule():
    if os.name != 'nt':
        return True
    try:
        proc = run_silent_cmd(
            'netsh advfirewall firewall show rule name="PhoneMic Receiver (UDP 5001)"',
            shell=True, timeout=2.0
        )
        if proc and proc.returncode == 0:
            return "PhoneMic Receiver" in (proc.stdout or "")
        return False
    except Exception:
        return False

def configure_windows_firewall():
    if os.name != 'nt':
        return True

    cmds = [
        f'netsh advfirewall firewall add rule name="PhoneMic Receiver (UDP 5001)" dir=in action=allow protocol=UDP localport={DEFAULT_PORT} profile=any enable=yes',
        f'netsh advfirewall firewall add rule name="PhoneMic Receiver (TCP 5001)" dir=in action=allow protocol=TCP localport={DEFAULT_PORT} profile=any enable=yes'
    ]

    for cmd in cmds:
        try:
            run_silent_cmd(cmd, shell=True, timeout=3.0)
        except Exception:
            pass

    return check_windows_firewall_rule()

# ==============================================================================
# NETWORK & IP CLASSIFICATION
# ==============================================================================
def get_classified_ips():
    classified = []
    seen = set()
    wifi_ip = ""
    usb_ip = ""
    lan_ip = ""

    # 1. Parse ipconfig /all on Windows (inspecting both adapter name and hardware Description)
    if os.name == 'nt':
        try:
            proc = run_silent_cmd(["ipconfig", "/all"], timeout=3.0)
            if proc and proc.returncode == 0:
                stdout = proc.stdout or ""
                current_adapter = "Unknown"
                adapter_is_usb = False
                adapter_is_wifi = False
                adapter_is_virtual = False

                for line in stdout.splitlines():
                    trimmed = line.strip()
                    if "adapter" in line.lower() and ":" in line:
                        current_adapter = line.split("adapter")[-1].replace(":", "").strip()
                        low = current_adapter.lower()
                        adapter_is_usb = any(k in low for k in ("rndis", "remote ndis", "tether", "samsung", "pixel", "usb"))
                        adapter_is_wifi = any(k in low for k in ("wi-fi", "wireless", "wlan", "802.11"))
                        adapter_is_virtual = any(k in low for k in ("virtual", "vbox", "vmware", "wsl", "vethernet", "loopback", "hyper-v"))

                    if "description" in trimmed.lower() and ":" in trimmed:
                        desc_val = trimmed.split(":", 1)[1].strip().lower()
                        if any(k in desc_val for k in ("rndis", "remote ndis", "tether", "samsung", "pixel", "usb ethernet", "usb network")):
                            adapter_is_usb = True
                        if any(k in desc_val for k in ("wi-fi", "wireless", "wlan", "802.11", "dual band")):
                            adapter_is_wifi = True
                        if any(k in desc_val for k in ("virtual", "vbox", "vmware", "hyper-v")):
                            adapter_is_virtual = True

                    if "IPv4 Address" in line or "IP Address" in line:
                        m = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if m:
                            ip = m.group(1)
                            if ip.startswith("127.") or ip.startswith("169.254."):
                                continue
                            if ip in seen:
                                continue
                            seen.add(ip)

                            category = "LAN / Ethernet"
                            if adapter_is_virtual or ip.startswith("192.168.56.") or ip.startswith("172.17.") or ip.startswith("172.28."):
                                category = "Virtual / WSL"
                            elif adapter_is_usb or ip.startswith("192.168.42.") or ip.startswith("192.168.137."):
                                category = "USB Tether"
                                if not usb_ip:
                                    usb_ip = ip
                            elif adapter_is_wifi:
                                category = "Wi-Fi"
                                if not wifi_ip:
                                    wifi_ip = ip
                            else:
                                category = "Wi-Fi / LAN"
                                if not lan_ip:
                                    lan_ip = ip

                            classified.append((category, ip))
        except Exception:
            pass

    # 2. Hostname enumeration fallback
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip in seen or ip.startswith("127."):
                continue
            seen.add(ip)
            if ip.startswith("169.254."):
                classified.append(("Link-Local", ip))
            elif ip.startswith("192.168.56.") or ip.startswith("172.17.") or ip.startswith("172.28."):
                classified.append(("Virtual / WSL", ip))
            elif ip.startswith("192.168.42.") or ip.startswith("192.168.137."):
                classified.append(("USB Tether", ip))
                if not usb_ip:
                    usb_ip = ip
            elif ip.startswith("192.168.") or ip.startswith("10.") or (ip.startswith("172.") and int(ip.split('.')[1]) in range(16, 32)):
                classified.append(("Wi-Fi / LAN", ip))
                if not lan_ip:
                    lan_ip = ip
            else:
                classified.append(("Network", ip))
    except Exception:
        pass

    order = {"Wi-Fi": 0, "Wi-Fi / LAN": 1, "LAN / Ethernet": 2, "USB Tether": 3, "Network": 4, "Virtual / WSL": 5, "Link-Local": 6}
    classified.sort(key=lambda x: order.get(x[0], 9))
    return classified

def get_best_display_ip():
    classified = get_classified_ips()
    # 1. Prefer dedicated Wi-Fi or local Wi-Fi/LAN in home range (192.168.1.x, 192.168.0.x, 10.x.x.x)
    for cat, ip in classified:
        if cat in ("Wi-Fi", "Wi-Fi / LAN", "LAN / Ethernet") and not (ip.startswith("192.168.42.") or ip.startswith("192.168.137.")):
            return ip, [f"{i} ({c})" for c, i in classified if i != ip and c not in ("Virtual / WSL", "Link-Local")]
    for cat, ip in classified:
        if cat not in ("Virtual / WSL", "Link-Local"):
            return ip, [f"{i} ({c})" for c, i in classified if i != ip]
    if classified:
        return classified[0][1], []
    return "127.0.0.1", []

def get_matching_ip_for_client(client_ip):
    """
    Finds the receiver's local IP address that shares the same subnet with client_ip.
    Crucial for discovery replies: when a phone connects over USB (192.168.42.x),
    the receiver must reply with its 192.168.42.x IP so the phone routes over USB!
    """
    classified = get_classified_ips()
    client_parts = str(client_ip).split('.')
    if len(client_parts) >= 3:
        client_prefix = f"{client_parts[0]}.{client_parts[1]}.{client_parts[2]}."
        for cat, ip in classified:
            if ip.startswith(client_prefix):
                return ip
    return get_best_display_ip()[0]

# ==============================================================================
# AUDIO DEVICE DETECTION & MANAGEMENT
# ==============================================================================
def find_audio_devices():
    if sd is None:
        return None, None, []

    try:
        devices = sd.query_devices()
    except Exception:
        return None, None, []

    cable_device = None
    default_output = None
    all_outputs = []

    try:
        default_output_index = sd.default.device[1]
    except Exception:
        default_output_index = -1

    for idx, dev in enumerate(devices):
        if dev.get('max_output_channels', 0) > 0:
            all_outputs.append((idx, dev))
            name = dev.get('name', '')
            if TARGET_DEVICE_NAME.lower() in name.lower() and cable_device is None:
                cable_device = (idx, dev)
            if idx == default_output_index:
                default_output = (idx, dev)

    if default_output is None and all_outputs:
        default_output = all_outputs[0]

    return cable_device, default_output, all_outputs

# ==============================================================================
# STUDIO DSP MODULES (ROBUST, CLICK-FREE, ZERO-BUZZ)
# ==============================================================================

class BiquadFilter:
    """
    Direct Form II Transposed Biquad Filter.
    Preserves continuous state (s1, s2) across frame boundaries for 100% click-free filtering.
    """
    def __init__(self):
        self.b0 = 1.0
        self.b1 = 0.0
        self.b2 = 0.0
        self.a1 = 0.0
        self.a2 = 0.0
        self.s1 = 0.0
        self.s2 = 0.0

    def reset_state(self):
        self.s1 = 0.0
        self.s2 = 0.0

    def set_bypass(self):
        self.b0 = 1.0
        self.b1 = 0.0
        self.b2 = 0.0
        self.a1 = 0.0
        self.a2 = 0.0

    def set_highpass(self, f0, fs=48000.0, q=0.7071):
        """2nd-order Butterworth High-Pass Filter (80Hz Subsonic Rumble Cut)"""
        w0 = 2.0 * math.pi * f0 / fs
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = sin_w0 / (2.0 * q)

        b0 = (1.0 + cos_w0) * 0.5
        b1 = -(1.0 + cos_w0)
        b2 = (1.0 + cos_w0) * 0.5
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha

        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0

    def set_low_shelf(self, f0, fs=48000.0, gain_db=0.0, s=1.0):
        """RBJ Low-Shelf Filter (Vocal Warmth / Chest Fullness @ 120Hz)"""
        if abs(gain_db) < 0.05:
            self.set_bypass()
            return
        A = 10.0 ** (gain_db / 40.0)
        w0 = 2.0 * math.pi * f0 / fs
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = (sin_w0 / 2.0) * math.sqrt((A + 1.0 / A) * (1.0 / s - 1.0) + 2.0)
        two_sqrt_a_alpha = 2.0 * math.sqrt(A) * alpha

        b0 = A * ((A + 1.0) - (A - 1.0) * cos_w0 + two_sqrt_a_alpha)
        b1 = 2.0 * A * ((A - 1.0) - (A + 1.0) * cos_w0)
        b2 = A * ((A + 1.0) - (A - 1.0) * cos_w0 - two_sqrt_a_alpha)
        a0 = (A + 1.0) + (A - 1.0) * cos_w0 + two_sqrt_a_alpha
        a1 = -2.0 * ((A - 1.0) + (A + 1.0) * cos_w0)
        a2 = (A + 1.0) + (A - 1.0) * cos_w0 - two_sqrt_a_alpha

        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0

    def set_peaking(self, f0, fs=48000.0, gain_db=0.0, q=1.0):
        """RBJ Peaking Bell Filter (Vocal Presence & Articulation @ 2500Hz)"""
        if abs(gain_db) < 0.05:
            self.set_bypass()
            return
        A = 10.0 ** (gain_db / 40.0)
        w0 = 2.0 * math.pi * f0 / fs
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = sin_w0 / (2.0 * q)

        b0 = 1.0 + alpha * A
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / A

        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0

    def set_high_shelf(self, f0, fs=48000.0, gain_db=0.0, s=1.0):
        """RBJ High-Shelf Filter (Vocal Air & Studio Sparkle @ 8000Hz)"""
        if abs(gain_db) < 0.05:
            self.set_bypass()
            return
        A = 10.0 ** (gain_db / 40.0)
        w0 = 2.0 * math.pi * f0 / fs
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = (sin_w0 / 2.0) * math.sqrt((A + 1.0 / A) * (1.0 / s - 1.0) + 2.0)
        two_sqrt_a_alpha = 2.0 * math.sqrt(A) * alpha

        b0 = A * ((A + 1.0) + (A - 1.0) * cos_w0 + two_sqrt_a_alpha)
        b1 = -2.0 * A * ((A - 1.0) + (A + 1.0) * cos_w0)
        b2 = A * ((A + 1.0) + (A - 1.0) * cos_w0 - two_sqrt_a_alpha)
        a0 = (A + 1.0) - (A - 1.0) * cos_w0 + two_sqrt_a_alpha
        a1 = 2.0 * ((A - 1.0) - (A + 1.0) * cos_w0)
        a2 = (A + 1.0) - (A - 1.0) * cos_w0 - two_sqrt_a_alpha

        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0

    def process(self, x):
        """Processes 1D array/list of samples. Preserves s1/s2 states."""
        if self.b1 == 0.0 and self.b2 == 0.0 and self.a1 == 0.0 and self.a2 == 0.0 and self.b0 == 1.0:
            return x

        b0, b1, b2 = self.b0, self.b1, self.b2
        a1, a2 = self.a1, self.a2
        s1, s2 = self.s1, self.s2

        if np is not None and isinstance(x, np.ndarray):
            y = np.empty_like(x)
            for i in range(len(x)):
                xi = x[i]
                yi = b0 * xi + s1
                s1 = b1 * xi - a1 * yi + s2
                s2 = b2 * xi - a2 * yi
                y[i] = yi
            if math.isnan(s1) or math.isinf(s1): s1 = 0.0
            if math.isnan(s2) or math.isinf(s2): s2 = 0.0
            self.s1 = s1
            self.s2 = s2
            return y
        else:
            y = [0.0] * len(x)
            for i in range(len(x)):
                xi = x[i]
                yi = b0 * xi + s1
                s1 = b1 * xi - a1 * yi + s2
                s2 = b2 * xi - a2 * yi
                y[i] = yi
            if math.isnan(s1) or math.isinf(s1): s1 = 0.0
            if math.isnan(s2) or math.isinf(s2): s2 = 0.0
            self.s1 = s1
            self.s2 = s2
            return y


class WolaNoiseSuppressor:
    """
    Weighted Overlap-Add (WOLA) Adaptive Wiener Filter with 50% Sine-Window Overlap.
    Guarantees mathematically perfect reconstruction (w^2(n) + w^2(n+H) == 1) when gain == 1.
    Frequency-smoothed and time-smoothed gain masks eliminate musical chirp and 100Hz buzz.
    """
    def __init__(self, sample_rate=48000, hop_size=240):
        self.sample_rate = sample_rate
        self.hop_size = hop_size            # 240 samples (5ms)
        self.window_size = hop_size * 2     # 480 samples (10ms)
        self.num_bins = self.window_size // 2 + 1

        if np is not None:
            # Sine window satisfies Princen-Bradley condition: w[n]^2 + w[n+hop]^2 == 1.0
            n = np.arange(self.window_size)
            self.window = np.sin((np.pi * (n + 0.5)) / self.window_size).astype(np.float32)
            self.input_history = np.zeros(self.hop_size, dtype=np.float32)
            self.ola_tail = np.zeros(self.hop_size, dtype=np.float32)
            self.noise_psd = np.ones(self.num_bins, dtype=np.float32) * 1e-4
            self.prev_gain = np.ones(self.num_bins, dtype=np.float32)
        else:
            self.window = None

    def process_hop(self, in_hop, amount):
        """Processes 240 samples (1 hop) using WOLA synthesis."""
        if np is None or self.window is None:
            return in_hop

        # 1. Concatenate previous 240 samples with new 240 samples to form 480-sample window
        frame = np.concatenate((self.input_history, in_hop))
        self.input_history = in_hop.copy()

        # 2. Windowed Analysis
        windowed = frame * self.window
        X = np.fft.rfft(windowed)
        power = np.abs(X) ** 2

        # 3. Noise Floor Adaptation (Minimum Statistics Tracking)
        mean_energy = np.mean(power)
        if mean_energy < 0.05:
            # Silence / ambient pause: adapt quickly
            alpha_n = 0.94
        else:
            # Active speech: adapt very slowly to prevent speech suppression
            alpha_n = 0.998
        self.noise_psd = alpha_n * self.noise_psd + (1.0 - alpha_n) * power

        # 4. Wiener Gain Mask
        # Over-subtraction factor beta based on amount
        beta = 1.0 + (amount * 1.5)
        snr_sub = np.maximum(0.0, power - beta * self.noise_psd)
        gain = snr_sub / (power + 1e-9)

        # Gain floor: higher floor preserves natural room warmth without robotic cutoff
        gain_floor = max(0.05, 1.0 - (0.92 * amount))
        gain = np.maximum(gain_floor, gain)

        # 5. Frequency Smoothing (3-point moving average eliminates musical chirps)
        smoothed_gain = gain.copy()
        smoothed_gain[1:-1] = 0.25 * gain[:-2] + 0.5 * gain[1:-1] + 0.25 * gain[2:]

        # 6. Time Smoothing (prevents abrupt flutter)
        self.prev_gain = 0.65 * self.prev_gain + 0.35 * smoothed_gain
        final_gain = self.prev_gain

        # 7. Synthesis
        Y = X * final_gain
        synth = np.fft.irfft(Y, n=self.window_size).astype(np.float32) * self.window

        # 8. Overlap-Add
        out_hop = synth[:self.hop_size] + self.ola_tail
        self.ola_tail = synth[self.hop_size:].copy()

        return out_hop

    def process(self, samples, amount):
        """Processes samples using WOLA synthesis (480-sample frame or multiple hops)."""
        if np is None or amount <= 0.02 or len(samples) < self.hop_size:
            return samples

        if len(samples) == self.window_size:
            out1 = self.process_hop(samples[:self.hop_size], amount)
            out2 = self.process_hop(samples[self.hop_size:], amount)
            return np.concatenate((out1, out2))

        out_hops = []
        hop = self.hop_size
        n = len(samples)
        for i in range(0, n - hop + 1, hop):
            out_hops.append(self.process_hop(samples[i:i + hop], amount))
        if out_hops:
            processed = np.concatenate(out_hops)
            rem = n - len(processed)
            if rem > 0:
                return np.concatenate((processed, samples[-rem:]))
            return processed
        return samples


class DualTapHarmonizer:
    """
    Continuous Rotating Dual-Tap Variable Delay Line Pitch Shifter.
    Uses raised-cosine crossfade (w1 + w2 == 1.0 everywhere) with zero clicks,
    zero discontinuities, and zero 100Hz buzz.
    """
    def __init__(self, size=4096, window=1024):
        self.size = size
        self.window = window
        self.base_delay = 512
        self.buffer = [0.0] * size
        self.write_idx = 0
        self.phase = 0.0

    def reset(self):
        self.buffer = [0.0] * self.size
        self.write_idx = 0
        self.phase = 0.0

    def process(self, samples, semitones):
        """Processes samples with continuous rotating harmonizer."""
        if abs(semitones) < 0.15:
            return samples

        n = len(samples)
        rate = 2.0 ** (semitones / 12.0)
        delta = 1.0 - rate
        T = float(self.window)
        two_pi_over_T = (2.0 * math.pi) / T
        half_T = T * 0.5
        size = self.size
        buf = self.buffer
        w_idx = self.write_idx
        ph = self.phase
        b_del = self.base_delay

        if np is not None and isinstance(samples, np.ndarray):
            out = np.empty_like(samples)
            for i in range(n):
                buf[w_idx] = float(samples[i])
                p1 = ph % T
                p2 = (ph + half_T) % T
                w1 = 0.5 - 0.5 * math.cos(p1 * two_pi_over_T)
                w2 = 1.0 - w1

                r1 = (w_idx - b_del - p1) % size
                r2 = (w_idx - b_del - p2) % size

                i1 = int(r1)
                f1 = r1 - i1
                s1 = (1.0 - f1) * buf[i1] + f1 * buf[(i1 + 1) % size]

                i2 = int(r2)
                f2 = r2 - i2
                s2 = (1.0 - f2) * buf[i2] + f2 * buf[(i2 + 1) % size]

                out[i] = s1 * w1 + s2 * w2

                w_idx = (w_idx + 1) % size
                ph = (ph + delta) % T

            self.write_idx = w_idx
            self.phase = ph
            return out
        else:
            out = [0.0] * n
            for i in range(n):
                buf[w_idx] = float(samples[i])
                p1 = ph % T
                p2 = (ph + half_T) % T
                w1 = 0.5 - 0.5 * math.cos(p1 * two_pi_over_T)
                w2 = 1.0 - w1

                r1 = (w_idx - b_del - p1) % size
                r2 = (w_idx - b_del - p2) % size

                i1 = int(r1)
                f1 = r1 - i1
                s1 = (1.0 - f1) * buf[i1] + f1 * buf[(i1 + 1) % size]

                i2 = int(r2)
                f2 = r2 - i2
                s2 = (1.0 - f2) * buf[i2] + f2 * buf[(i2 + 1) % size]

                out[i] = s1 * w1 + s2 * w2

                w_idx = (w_idx + 1) % size
                ph = (ph + delta) % T

            self.write_idx = w_idx
            self.phase = ph
            return out


# ==============================================================================
# DEDICATED MODULAR VOICE CHANGER ENGINE (SEPARATE & ISOLATED)
# ==============================================================================
class VoiceChanger:
    """
    Dedicated, Isolated Voice Transformation Engine.
    Kept completely separate from the core receiver and audio network layer.
    When disabled (enabled=False), audio passes through 100% untouched.
    """
    MODES = [
        "Natural Pitch",
        "Deep Titan / Monster",
        "Helium / Chipmunk",
        "Robot / Cybernetic",
        "Walkie-Talkie / Comm Radio",
        "Echo / Stadium Delay",
        "Demon / Dark Lord",
        "Alien / Vibrato",
    ]

    MODE_DESCRIPTIONS = {
        "Natural Pitch": "Clean, natural pitch shifting without voice distortion.",
        "Deep Titan / Monster": "Low, authoritative rumble with deep sub-harmonic warmth.",
        "Helium / Chipmunk": "High-pitched formant voice for cartoon & fun effects.",
        "Robot / Cybernetic": "Sci-Fi metallic ring modulation voice effect.",
        "Walkie-Talkie / Comm Radio": "Authentic military two-way radio comms with soft crunch.",
        "Echo / Stadium Delay": "Large venue slapback echo & stadium announcement effect.",
        "Demon / Dark Lord": "Deep guttural transformation with low-frequency growl.",
        "Alien / Vibrato": "Extraterrestrial undulating pitch vibrato modulation."
    }

    BUILTIN_PRESETS = {
        "Normal (Bypass)": {
            "enabled": False,
            "mode": "Natural Pitch",
            "pitch_semitones": 0.0,
            "mix": 1.0
        },
        "Deep Titan / Monster": {
            "enabled": True,
            "mode": "Deep Titan / Monster",
            "pitch_semitones": -4.5,
            "mix": 1.0
        },
        "Announcer / Radio Host": {
            "enabled": True,
            "mode": "Natural Pitch",
            "pitch_semitones": -1.5,
            "mix": 1.0
        },
        "Helium / Chipmunk": {
            "enabled": True,
            "mode": "Helium / Chipmunk",
            "pitch_semitones": 6.0,
            "mix": 1.0
        },
        "Walkie-Talkie / Comm Radio": {
            "enabled": True,
            "mode": "Walkie-Talkie / Comm Radio",
            "pitch_semitones": 0.0,
            "mix": 1.0
        },
        "Robot / Cybernetic": {
            "enabled": True,
            "mode": "Robot / Cybernetic",
            "pitch_semitones": -1.0,
            "mix": 1.0
        },
        "Demon / Dark Lord": {
            "enabled": True,
            "mode": "Demon / Dark Lord",
            "pitch_semitones": -5.5,
            "mix": 1.0
        },
        "Echo / Stadium Announcer": {
            "enabled": True,
            "mode": "Echo / Stadium Delay",
            "pitch_semitones": 0.0,
            "mix": 0.85
        },
        "Alien / Vibrato": {
            "enabled": True,
            "mode": "Alien / Vibrato",
            "pitch_semitones": 2.0,
            "mix": 1.0
        }
    }

    def __init__(self, sample_rate=AUDIO_RATE, config=None):
        self.sample_rate = sample_rate
        self.enabled = False
        self.mode = "Natural Pitch"
        self.pitch_semitones = 0.0
        self.mix = 1.0
        self.active_preset = "Normal (Bypass)"

        # Independent Pitch Harmonizer
        self.harmonizer = DualTapHarmonizer()

        # DSP Modulators
        self._robot_phase = 0.0
        self._echo_len = int(sample_rate * 0.25)
        self._echo_buffer = [0.0] * self._echo_len
        self._echo_idx = 0
        self._lfo_phase = 0.0

        if config and "voice_changer" in config.data:
            vc_data = config.data["voice_changer"]
            self.enabled = bool(vc_data.get("enabled", False))
            self.mode = str(vc_data.get("mode", "Natural Pitch"))
            if self.mode not in self.MODES:
                self.mode = "Natural Pitch"
            self.pitch_semitones = float(vc_data.get("pitch_semitones", 0.0))
            self.mix = float(vc_data.get("mix", 1.0))
            self.active_preset = str(vc_data.get("active_preset", "Normal (Bypass)"))

    def set_preset_dict(self, d, name="Custom"):
        self.enabled = bool(d.get("enabled", True))
        self.mode = str(d.get("mode", "Natural Pitch"))
        if self.mode not in self.MODES:
            self.mode = "Natural Pitch"
        self.pitch_semitones = float(d.get("pitch_semitones", 0.0))
        self.mix = float(d.get("mix", 1.0))
        self.active_preset = name

    def process(self, samples):
        """
        Transforms voice samples. If disabled (enabled=False),
        returns samples immediately with ZERO modification.
        """
        if not self.enabled:
            return samples

        n = len(samples)
        if n == 0:
            return samples

        effective_pitch = self.pitch_semitones

        # Alien Vibrato LFO pitch modulation
        if self.mode == "Alien / Vibrato":
            lfo = math.sin(self._lfo_phase)
            self._lfo_phase = (self._lfo_phase + (2.0 * math.pi * 5.5 * n) / self.sample_rate) % (2.0 * math.pi)
            effective_pitch += lfo * 1.5

        # 1. Pitch Harmonizer
        if abs(effective_pitch) > 0.15:
            shifted = self.harmonizer.process(samples, effective_pitch)
        else:
            shifted = samples

        # 2. Mode-Specific Transformation
        if self.mode == "Robot / Cybernetic":
            wet = self._apply_robot(shifted)
        elif self.mode == "Walkie-Talkie / Comm Radio":
            wet = self._apply_walkie_talkie(shifted)
        elif self.mode == "Echo / Stadium Delay":
            wet = self._apply_echo(shifted)
        elif self.mode == "Deep Titan / Monster":
            wet = self._apply_deep_titan(shifted)
        elif self.mode == "Demon / Dark Lord":
            wet = self._apply_demon(shifted)
        else:
            wet = shifted

        # 3. Dry / Wet Blend
        if self.mix >= 0.99:
            return wet
        elif self.mix <= 0.01:
            return samples
        else:
            w = self.mix
            d = 1.0 - w
            if np is not None and isinstance(samples, np.ndarray) and isinstance(wet, np.ndarray):
                return d * samples + w * wet
            elif isinstance(samples, list) and isinstance(wet, list):
                return [d * s + w * m for s, m in zip(samples, wet)]
            else:
                return wet

    def _apply_robot(self, samples):
        n = len(samples)
        if np is not None and isinstance(samples, np.ndarray):
            t = np.arange(n, dtype=np.float32) / self.sample_rate
            carrier = 0.30 + 0.70 * np.sin(self._robot_phase + 2.0 * np.pi * 55.0 * t).astype(np.float32)
            self._robot_phase = (self._robot_phase + 2.0 * np.pi * 55.0 * n / self.sample_rate) % (2.0 * np.pi)
            return (samples * carrier).astype(np.float32)
        else:
            out = [0.0] * n
            ph = self._robot_phase
            dph = (2.0 * math.pi * 55.0) / self.sample_rate
            for i in range(n):
                c = math.sin(ph)
                out[i] = samples[i] * (0.30 + 0.70 * c)
                ph = (ph + dph) % (2.0 * math.pi)
            self._robot_phase = ph
            return out

    def _apply_walkie_talkie(self, samples):
        if np is not None and isinstance(samples, np.ndarray):
            return (np.tanh(samples * 2.5) * 0.78).astype(np.float32)
        else:
            return [math.tanh(s * 2.5) * 0.78 for s in samples]

    def _apply_echo(self, samples):
        n = len(samples)
        delay_s = int(self.sample_rate * 0.16)
        fb = 0.38
        blen = self._echo_len
        buf = self._echo_buffer
        idx = self._echo_idx

        if np is not None and isinstance(samples, np.ndarray):
            out = np.empty_like(samples)
            for i in range(n):
                d = buf[(idx - delay_s) % blen]
                w = float(samples[i]) + d * fb
                buf[idx] = w
                idx = (idx + 1) % blen
                out[i] = w
            self._echo_idx = idx
            return out
        else:
            out = [0.0] * n
            for i in range(n):
                d = buf[(idx - delay_s) % blen]
                w = samples[i] + d * fb
                buf[idx] = w
                idx = (idx + 1) % blen
                out[i] = w
            self._echo_idx = idx
            return out

    def _apply_deep_titan(self, samples):
        if np is not None and isinstance(samples, np.ndarray):
            return (np.tanh(samples * 1.3) * 0.90).astype(np.float32)
        else:
            return [math.tanh(s * 1.3) * 0.90 for s in samples]

    def _apply_demon(self, samples):
        n = len(samples)
        if np is not None and isinstance(samples, np.ndarray):
            t = np.arange(n, dtype=np.float32) / self.sample_rate
            mod = 0.45 + 0.55 * np.sin(self._robot_phase + 2.0 * np.pi * 42.0 * t).astype(np.float32)
            self._robot_phase = (self._robot_phase + 2.0 * np.pi * 42.0 * n / self.sample_rate) % (2.0 * np.pi)
            driven = np.tanh(samples * 1.5) * mod
            return driven.astype(np.float32)
        else:
            out = [0.0] * n
            ph = self._robot_phase
            dph = (2.0 * math.pi * 42.0) / self.sample_rate
            for i in range(n):
                m = 0.45 + 0.55 * math.sin(ph)
                out[i] = math.tanh(samples[i] * 1.5) * m
                ph = (ph + dph) % (2.0 * math.pi)
            self._robot_phase = ph
            return out


# ==============================================================================
# MASTER AUDIO DSP ENGINE
# ==============================================================================
class AudioProcessor:
    """
    Comprehensive Studio-Grade Audio DSP Pipeline:
    1. 80Hz Subsonic Rumble Filter (2nd-Order Butterworth High-Pass Biquad).
    2. WOLA Spectral Noise Suppressor (50% Sine-Window Wiener Filter).
    3. Dedicated Voice Changer Transformation (Isolated, Modular & Bypassable).
    4. 3-Band Parametric Studio Equalizer (Low Shelf, Mid Peaking, High Shelf).
    5. Anti-Click Studio Noise Gate (-80dB to -30dB).
    6. Broadcast Soft-Knee Limiter & Headroom Protection.
    7. Multi-Band Spectrum Visualizer (32 Log Bands with Peak Hold & Waveform Cache).
    """
    FX_BUILTIN_PRESETS = {
        "Default (Studio Clean)": {
            "gain": 1.0,
            "smart_noise_cancel": True,
            "noise_cancel_amount": 0.65,
            "gate_threshold_db": -55.0,
            "eq_low_gain_db": 0.0,
            "eq_mid_gain_db": 0.0,
            "eq_high_gain_db": 0.0,
            "monitor_volume": 0.85
        },
        "Podcast & Streamer": {
            "gain": 1.1,
            "smart_noise_cancel": True,
            "noise_cancel_amount": 0.70,
            "gate_threshold_db": -50.0,
            "eq_low_gain_db": 2.5,
            "eq_mid_gain_db": 1.5,
            "eq_high_gain_db": 2.5,
            "monitor_volume": 0.85
        },
        "Broadcast Warmth": {
            "gain": 1.0,
            "smart_noise_cancel": True,
            "noise_cancel_amount": 0.65,
            "gate_threshold_db": -55.0,
            "eq_low_gain_db": 4.0,
            "eq_mid_gain_db": 0.5,
            "eq_high_gain_db": 1.5,
            "monitor_volume": 0.85
        },
        "Crisp & Articulate": {
            "gain": 1.0,
            "smart_noise_cancel": True,
            "noise_cancel_amount": 0.60,
            "gate_threshold_db": -52.0,
            "eq_low_gain_db": -1.5,
            "eq_mid_gain_db": 3.0,
            "eq_high_gain_db": 4.5,
            "monitor_volume": 0.85
        },
        "De-Boom (Bass Cut)": {
            "gain": 1.0,
            "smart_noise_cancel": True,
            "noise_cancel_amount": 0.65,
            "gate_threshold_db": -55.0,
            "eq_low_gain_db": -5.5,
            "eq_mid_gain_db": 1.0,
            "eq_high_gain_db": 2.0,
            "monitor_volume": 0.85
        },
        "Heavy Noise Cut (Keyboard)": {
            "gain": 1.0,
            "smart_noise_cancel": True,
            "noise_cancel_amount": 0.80,
            "gate_threshold_db": -42.0,
            "eq_low_gain_db": 0.0,
            "eq_mid_gain_db": 1.0,
            "eq_high_gain_db": 2.0,
            "monitor_volume": 0.85
        },
        "Pure Raw (Zero FX)": {
            "gain": 1.0,
            "smart_noise_cancel": False,
            "noise_cancel_amount": 0.0,
            "gate_threshold_db": -80.0,
            "eq_low_gain_db": 0.0,
            "eq_mid_gain_db": 0.0,
            "eq_high_gain_db": 0.0,
            "monitor_volume": 0.85
        }
    }

    def __init__(self, sample_rate=AUDIO_RATE, config=None):
        self.sample_rate = sample_rate

        # FX Controls
        self.gain = DEFAULT_GAIN
        self.smart_noise_cancel = True
        self.noise_cancel_amount = 0.65
        self.gate_threshold_db = NOISE_GATE_THRESHOLD_DB
        self.eq_low_gain_db = 0.0
        self.eq_mid_gain_db = 0.0
        self.eq_high_gain_db = 0.0
        self.monitor_volume = 0.85
        self.active_preset = "Default (Studio Clean)"

        # Load from config if available
        if config and "studio_fx" in config.data:
            s = config.data["studio_fx"]
            self.gain = float(s.get("gain", DEFAULT_GAIN))
            self.smart_noise_cancel = bool(s.get("smart_noise_cancel", True))
            self.noise_cancel_amount = float(s.get("noise_cancel_amount", 0.65))
            self.gate_threshold_db = float(s.get("gate_threshold_db", NOISE_GATE_THRESHOLD_DB))
            self.eq_low_gain_db = float(s.get("eq_low_gain_db", 0.0))
            self.eq_mid_gain_db = float(s.get("eq_mid_gain_db", 0.0))
            self.eq_high_gain_db = float(s.get("eq_high_gain_db", 0.0))
            self.monitor_volume = float(s.get("monitor_volume", 0.85))
            self.active_preset = str(s.get("active_preset", "Default (Studio Clean)"))

        # Filters
        self.hp_rumble = BiquadFilter()
        self.hp_rumble.set_highpass(80.0, sample_rate, 0.7071)

        self.eq_low = BiquadFilter()
        self.eq_low.set_low_shelf(120.0, sample_rate, self.eq_low_gain_db)

        self.eq_mid = BiquadFilter()
        self.eq_mid.set_peaking(2500.0, sample_rate, self.eq_mid_gain_db, q=1.0)

        self.eq_high = BiquadFilter()
        self.eq_high.set_high_shelf(8000.0, sample_rate, self.eq_high_gain_db)

        self.noise_suppressor = WolaNoiseSuppressor(sample_rate=sample_rate, hop_size=240)

        # Dedicated Modular Voice Changer Engine
        self.voice_changer = VoiceChanger(sample_rate=sample_rate, config=config)

        # Noise Gate Envelope
        self._gate_envelope = 1.0

        # Visualizer State
        self.spectrum_bins = [0.0] * 32
        self.spectrum_peaks = [0.0] * 32
        self.waveform_cache = [0.0] * 64

    def set_fx_preset_dict(self, d, name="Custom"):
        self.gain = float(d.get("gain", 1.0))
        self.smart_noise_cancel = bool(d.get("smart_noise_cancel", True))
        self.noise_cancel_amount = float(d.get("noise_cancel_amount", 0.65))
        self.gate_threshold_db = float(d.get("gate_threshold_db", -55.0))
        self.update_eq(
            low_db=float(d.get("eq_low_gain_db", 0.0)),
            mid_db=float(d.get("eq_mid_gain_db", 0.0)),
            high_db=float(d.get("eq_high_gain_db", 0.0))
        )
        if "monitor_volume" in d:
            self.monitor_volume = float(d["monitor_volume"])
        self.active_preset = name

    def update_eq(self, low_db=None, mid_db=None, high_db=None):
        """Updates 3-Band EQ Biquad coefficients."""
        if low_db is not None:
            self.eq_low_gain_db = float(low_db)
            self.eq_low.set_low_shelf(120.0, self.sample_rate, self.eq_low_gain_db)
        if mid_db is not None:
            self.eq_mid_gain_db = float(mid_db)
            self.eq_mid.set_peaking(2500.0, self.sample_rate, self.eq_mid_gain_db, q=1.0)
        if high_db is not None:
            self.eq_high_gain_db = float(high_db)
            self.eq_high.set_high_shelf(8000.0, self.sample_rate, self.eq_high_gain_db)

    def process(self, pcm_bytes):
        """Processes a frame of mono PCM audio. Returns (stereo_main, stereo_mon, peak, db)."""
        if np is not None:
            int16_samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            if len(int16_samples) == 0:
                empty = np.zeros((0, 2), dtype=np.float32)
                return empty, empty, 0.0, -80.0

            # Convert to float32 [-1.0, 1.0]
            samples = (int16_samples / 32768.0).astype(np.float32)

            # 1. 80Hz Subsonic Rumble Cut (always active for clean studio floor)
            samples = self.hp_rumble.process(samples)

            # 2. Smart Spectral Noise Suppression (WOLA Wiener Filter)
            if self.smart_noise_cancel and self.noise_cancel_amount > 0.02:
                samples = self.noise_suppressor.process(samples, self.noise_cancel_amount)

            # 3. Dedicated Voice Changer Transformation (Isolated, Modular & Bypassable)
            if self.voice_changer.enabled:
                samples = self.voice_changer.process(samples)

            # 4. 3-Band Studio Parametric Equalizer
            if abs(self.eq_low_gain_db) >= 0.1:
                samples = self.eq_low.process(samples)
            if abs(self.eq_mid_gain_db) >= 0.1:
                samples = self.eq_mid.process(samples)
            if abs(self.eq_high_gain_db) >= 0.1:
                samples = self.eq_high.process(samples)

            # 5. Microphone Gain Boost
            if abs(self.gain - 1.0) > 0.01:
                samples = samples * self.gain

            # 6. Peak & dB Metering
            peak = float(np.max(np.abs(samples))) if len(samples) > 0 else 0.0
            db = 20.0 * math.log10(peak) if peak > 1e-4 else -80.0

            # 7. Smooth Anti-Click Studio Noise Gate
            if self.gate_threshold_db > -78.0:
                target_gate = 1.0 if db >= self.gate_threshold_db else 0.01
                attack_rate = 0.25
                release_rate = 0.04
                coeff = attack_rate if target_gate > self._gate_envelope else release_rate
                self._gate_envelope += (target_gate - self._gate_envelope) * coeff
                samples = samples * self._gate_envelope

            # 8. Broadcast Soft-Knee Limiter (clipping prevention)
            np.clip(samples, -LIMITER_CEILING, LIMITER_CEILING, out=samples)

            # 9. Compute Real-Time Visualizer Spectrum
            self._update_visualizer(samples)

            # 10. Stereo Output Blocks
            stereo_main = np.column_stack((samples, samples))
            mon_samples = samples * self.monitor_volume
            stereo_mon = np.column_stack((mon_samples, mon_samples))

            return stereo_main, stereo_mon, peak, db

        else:
            # Pure Python fallback
            count = len(pcm_bytes) // 2
            if count == 0:
                return bytes(0), bytes(0), 0.0, -80.0
            fmt = f"<{count}h"
            samples = list(struct.unpack(fmt, pcm_bytes))
            norm = [s / 32768.0 for s in samples]

            # 1. Rumble Filter
            norm = self.hp_rumble.process(norm)

            # 2. Dedicated Voice Changer Transformation
            if self.voice_changer.enabled:
                norm = self.voice_changer.process(norm)

            # 3. 3-Band EQ
            if abs(self.eq_low_gain_db) >= 0.1:
                norm = self.eq_low.process(norm)
            if abs(self.eq_mid_gain_db) >= 0.1:
                norm = self.eq_mid.process(norm)
            if abs(self.eq_high_gain_db) >= 0.1:
                norm = self.eq_high.process(norm)

            # Gain & Clamp
            max_abs = 0.0
            stereo_bytes = bytearray(count * 4)
            mon_bytes = bytearray(count * 4)

            for i, val in enumerate(norm):
                amp = val * self.gain
                if abs(amp) > max_abs:
                    max_abs = abs(amp)
                clamped = max(-32767, min(32767, int(amp * 32767.0)))
                struct.pack_into("<hh", stereo_bytes, i * 4, clamped, clamped)
                mon_amp = max(-32767, min(32767, int(clamped * self.monitor_volume)))
                struct.pack_into("<hh", mon_bytes, i * 4, mon_amp, mon_amp)

            peak = min(1.0, max_abs)
            db = 20.0 * math.log10(peak) if peak > 1e-4 else -80.0
            return bytes(stereo_bytes), bytes(mon_bytes), peak, db

    def _update_visualizer(self, samples):
        """Computes 32 logarithmic frequency bands with ballistic peak hold."""
        n = len(samples)
        if n < 64:
            return

        # 32 Frequency Bins from RFFT
        rfft = np.abs(np.fft.rfft(samples * np.hanning(n)))
        num_fft = len(rfft)
        bin_count = 32

        for b in range(bin_count):
            start_idx = int((b / bin_count) ** 1.8 * (num_fft - 1))
            end_idx = max(start_idx + 1, int(((b + 1) / bin_count) ** 1.8 * (num_fft - 1)))
            val = float(np.mean(rfft[start_idx:end_idx])) * 0.22
            val = min(1.0, max(0.0, val))

            # Smooth decay on bar
            prev = self.spectrum_bins[b]
            self.spectrum_bins[b] = val if val > prev else (prev * 0.80)

            # Ballistic Peak Hold
            curr_pk = self.spectrum_peaks[b]
            if self.spectrum_bins[b] >= curr_pk:
                self.spectrum_peaks[b] = self.spectrum_bins[b]
            else:
                self.spectrum_peaks[b] = max(0.0, curr_pk - 0.030)

        # Waveform preview (downsampled to 64 points)
        step = max(1, n // 64)
        self.waveform_cache = [float(samples[i * step]) for i in range(min(64, n // step))]


# ==============================================================================
# MAIN RECEIVER ENGINE
# ==============================================================================
class PhoneMicReceiver:
    def __init__(self, port=DEFAULT_PORT, target_device=None, monitor_device=None):
        self.port = port
        self.target_device_idx = target_device
        self.monitor_device_idx = monitor_device

        self.running = False
        self.paused = False
        self.monitoring = False
        self.recording = False

        self.processor = AudioProcessor()
        self.audio_queue = queue.Queue(maxsize=16)

        # Telemetry & Metrics
        self.transport = "UDP"
        self.packets_received = 0
        self.bytes_received = 0
        self.packets_lost = 0
        self.raw_fallback_packets = 0
        self.last_seq = -1
        self.client_addr = None
        self.stream_start_time = 0
        self.last_packet_time = 0
        self.latest_peak = 0.0
        self.latest_db = -80.0

        # Jitter & Rate
        self.bitrate_kbps = 0.0
        self.packets_per_sec = 0.0
        self.estimated_jitter_ms = 0.8
        self._last_arrival_time = 0
        self._rate_calc_time = time.time()
        self._last_calc_bytes = 0
        self._last_calc_packets = 0

        # WAV Recording
        self.wav_file = None
        self.wav_filename = ""
        self.record_start_time = 0
        self.record_bytes_written = 0

        # Audio Output Streams
        self.audio_stream = None
        self.monitor_stream = None

        # Sockets
        self.udp_socket = None
        self.tcp_server = None
        self.tcp_client = None

    def start(self):
        self.running = True
        self._open_primary_audio_stream()

        self.playback_thread = threading.Thread(target=self._playback_loop, name="AudioPlayback", daemon=True)
        self.playback_thread.start()

        self.udp_thread = threading.Thread(target=self._udp_listener_loop, name="UDPListener", daemon=True)
        self.udp_thread.start()

        self.tcp_thread = threading.Thread(target=self._tcp_listener_loop, name="TCPListener", daemon=True)
        self.tcp_thread.start()

        self.beacon_thread = threading.Thread(target=self._beacon_loop, name="DiscoveryBeacon", daemon=True)
        self.beacon_thread.start()

    def _open_primary_audio_stream(self):
        if sd is None:
            return
        output_dtype = 'float32' if np is not None else 'int16'
        for lat in ('low', None):
            try:
                self.audio_stream = sd.OutputStream(
                    samplerate=AUDIO_RATE,
                    channels=OUTPUT_CHANNELS,
                    dtype=output_dtype,
                    device=self.target_device_idx,
                    latency=lat,
                    blocksize=FRAMES_PER_PACKET if lat == 'low' else None
                )
                self.audio_stream.start()
                return
            except Exception:
                pass

        try:
            self.audio_stream = sd.OutputStream(
                samplerate=AUDIO_RATE,
                channels=OUTPUT_CHANNELS,
                dtype=output_dtype
            )
            self.audio_stream.start()
        except Exception:
            self.audio_stream = None

    def set_output_device(self, device_idx):
        self.target_device_idx = device_idx
        if sd is not None and self.running:
            try:
                if self.audio_stream:
                    self.audio_stream.stop()
                    self.audio_stream.close()
            except Exception:
                pass
            self._open_primary_audio_stream()

    def set_monitor_device(self, device_idx):
        self.monitor_device_idx = device_idx
        if self.monitoring and sd is not None and self.running:
            try:
                if self.monitor_stream:
                    self.monitor_stream.stop()
                    self.monitor_stream.close()
            except Exception:
                pass
            self.toggle_monitor()
            self.toggle_monitor()

    def _beacon_loop(self):
        beacon_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        beacon_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running:
            try:
                for cat, ip in get_classified_ips():
                    parts = ip.split('.')
                    if len(parts) == 4:
                        sub_bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                        beacon_msg = DISCOVERY_REPLY + f" {VERSION} {ip}".encode('ascii')
                        try:
                            beacon_sock.sendto(beacon_msg, (sub_bcast, self.port))
                        except Exception:
                            pass

                top_ip, _ = get_best_display_ip()
                global_msg = DISCOVERY_REPLY + f" {VERSION} {top_ip}".encode('ascii')
                try:
                    beacon_sock.sendto(global_msg, ("255.255.255.255", self.port))
                except Exception:
                    pass
            except Exception:
                pass
            time.sleep(1.2)

        try:
            beacon_sock.close()
        except Exception:
            pass

    def _playback_loop(self):
        silence = np.zeros((FRAMES_PER_PACKET, OUTPUT_CHANNELS), dtype=np.float32) if np is not None else bytes(FRAMES_PER_PACKET * 4)

        while self.running:
            try:
                main_block, mon_block = self.audio_queue.get(timeout=0.04)
                if self.paused and silence is not None:
                    main_block = silence
                    mon_block = silence

                # Write to Primary Device (VB-CABLE or Speakers)
                if self.audio_stream and self.audio_stream.active:
                    self.audio_stream.write(main_block)

                # Write to Headphone Monitor
                if self.monitoring and self.monitor_stream and self.monitor_stream.active:
                    self.monitor_stream.write(mon_block)

                # Write to WAV File
                if self.recording and self.wav_file and not self.paused:
                    try:
                        if np is not None:
                            mono_pcm = (main_block[:, 0] * 32767.0).astype(np.int16).tobytes()
                            self.wav_file.writeframes(mono_pcm)
                            self.record_bytes_written += len(mono_pcm)
                        else:
                            self.wav_file.writeframes(main_block)
                            self.record_bytes_written += len(main_block)
                    except Exception:
                        pass
            except queue.Empty:
                continue
            except Exception:
                if not self.running:
                    break

    def _udp_listener_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if os.name == 'nt':
            try:
                sock.ioctl(SIO_UDP_CONNRESET, False)
            except Exception:
                pass

        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)
        except Exception:
            pass

        try:
            sock.bind((HOST, self.port))
            sock.settimeout(1.0)
            self.udp_socket = sock
        except Exception as e:
            print(f"{Colors.RED}[!] Failed to bind UDP port {self.port}: {e}{Colors.RESET}")
            return

        buffer = bytearray(2048)

        while self.running:
            try:
                length, addr = sock.recvfrom_into(buffer)
                if length < 4:
                    continue

                # 1. Discovery probe reply (supports 'PMD0' from Android and 'PM_DISCOVER')
                is_discovery = (
                    (length >= 4 and buffer[:4] == b'PMD0') or
                    (length >= 3 and buffer[:3] == b'PMD') or
                    (length >= len(DISCOVERY_PROBE) and buffer[:len(DISCOVERY_PROBE)] == DISCOVERY_PROBE) or
                    (b'PMD0' in buffer[:min(length, 32)]) or
                    (b'PM_DISCOVER' in buffer[:min(length, 32)])
                )
                if is_discovery:
                    reply_ip = get_matching_ip_for_client(addr[0])
                    reply_payload = DISCOVERY_REPLY + f" {VERSION} {reply_ip}".encode('ascii')
                    sock.sendto(reply_payload, addr)
                    continue

                # 2. PhoneMic Framed Packet: 8-byte header ('PM01' + 4-byte uint32 seq) + PCM audio
                if length >= 8 and buffer[:4] == PACKET_MAGIC:
                    seq = struct.unpack(">I", buffer[4:8])[0]

                    if self.last_seq != -1:
                        lost = (seq - self.last_seq - 1) & 0xFFFFFFFF
                        if 0 < lost < 1000:
                            self.packets_lost += lost
                    self.last_seq = seq

                    pcm_data = bytes(buffer[8:length])
                    self.client_addr = addr
                    self.transport = "UDP"
                    self._enqueue_pcm(pcm_data)
                    continue

                # 3. Raw PCM Fallback (without framing header)
                if length >= 480 and length % 2 == 0:
                    self.raw_fallback_packets += 1
                    self.client_addr = addr
                    self.transport = "UDP (Raw)"
                    self._enqueue_pcm(bytes(buffer[:length]))
                    continue

            except socket.timeout:
                continue
            except Exception:
                if not self.running:
                    break

        try:
            sock.close()
        except Exception:
            pass

    def _tcp_listener_loop(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((HOST, self.port))
            server.listen(1)
            server.settimeout(1.0)
            self.tcp_server = server
        except Exception:
            return

        while self.running:
            try:
                conn, addr = server.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.client_addr = addr
                self.transport = "TCP"
                self.tcp_client = conn
                conn.settimeout(2.0)
                tcp_buf = bytearray()

                while self.running:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    tcp_buf.extend(chunk)
                    while len(tcp_buf) >= PCM_BYTES_PER_PACKET:
                        frame = bytes(tcp_buf[:PCM_BYTES_PER_PACKET])
                        del tcp_buf[:PCM_BYTES_PER_PACKET]
                        self._enqueue_pcm(frame)
                conn.close()
            except socket.timeout:
                continue
            except Exception:
                if not self.running:
                    break
            finally:
                self.tcp_client = None

        try:
            server.close()
        except Exception:
            pass

    def _enqueue_pcm(self, pcm_bytes):
        if not pcm_bytes:
            return
        if len(pcm_bytes) % 2 != 0:
            pcm_bytes = pcm_bytes[:len(pcm_bytes) - 1]
            if len(pcm_bytes) == 0:
                return
        now = time.time()
        if self.stream_start_time == 0:
            self.stream_start_time = now
        self.last_packet_time = now

        # Inter-packet arrival jitter calculation (target 10ms)
        if self._last_arrival_time > 0:
            delta_ms = (now - self._last_arrival_time) * 1000.0
            jitter_delta = abs(delta_ms - 10.0)
            self.estimated_jitter_ms = 0.9 * self.estimated_jitter_ms + 0.1 * jitter_delta
        self._last_arrival_time = now

        self.packets_received += 1
        self.bytes_received += len(pcm_bytes)

        time_diff = now - self._rate_calc_time
        if time_diff >= 1.0:
            bytes_diff = self.bytes_received - self._last_calc_bytes
            packets_diff = self.packets_received - self._last_calc_packets
            self.bitrate_kbps = (bytes_diff * 8.0) / (time_diff * 1000.0)
            self.packets_per_sec = packets_diff / time_diff
            self._rate_calc_time = now
            self._last_calc_bytes = self.bytes_received
            self._last_calc_packets = self.packets_received

        stereo_main, stereo_mon, peak, db = self.processor.process(pcm_bytes)
        self.latest_peak = peak
        self.latest_db = db

        if stereo_main is not None:
            if self.audio_queue.full():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    pass
            try:
                self.audio_queue.put_nowait((stereo_main, stereo_mon))
            except queue.Full:
                pass

    def send_control_to_client(self, cmd_bytes):
        sent = False
        if self.udp_socket and self.client_addr and "UDP" in self.transport:
            try:
                self.udp_socket.sendto(cmd_bytes, self.client_addr)
                sent = True
            except Exception:
                pass
        if self.tcp_client:
            try:
                self.tcp_client.sendall(cmd_bytes)
                sent = True
            except Exception:
                pass
        return sent

    def toggle_pause(self):
        self.paused = not self.paused
        cmd = CMD_PAUSE if self.paused else CMD_RESUME
        self.send_control_to_client(cmd)
        return self.paused

    def toggle_monitor(self):
        if not self.monitoring:
            if sd is None:
                return False, "sounddevice library missing"
            try:
                output_dtype = 'float32' if np is not None else 'int16'
                self.monitor_stream = sd.OutputStream(
                    samplerate=AUDIO_RATE,
                    channels=OUTPUT_CHANNELS,
                    dtype=output_dtype,
                    device=self.monitor_device_idx
                )
                self.monitor_stream.start()
                self.monitoring = True
                return True, "Headphone monitoring active"
            except Exception as e:
                self.monitoring = False
                return False, f"Monitor error: {e}"
        else:
            try:
                if self.monitor_stream:
                    self.monitor_stream.stop()
                    self.monitor_stream.close()
            except Exception:
                pass
            self.monitor_stream = None
            self.monitoring = False
            return False, "Monitoring stopped"

    def toggle_recording(self):
        if not self.recording:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.wav_filename = os.path.join(get_app_dir(), f"PhoneMic_Record_{timestamp}.wav")
            try:
                self.wav_file = wave.open(self.wav_filename, 'wb')
                self.wav_file.setnchannels(1)
                self.wav_file.setsampwidth(2)
                self.wav_file.setframerate(AUDIO_RATE)
                self.recording = True
                self.record_start_time = time.time()
                self.record_bytes_written = 0
                return True, self.wav_filename
            except Exception:
                self.recording = False
                return False, ""
        else:
            self.recording = False
            try:
                if self.wav_file:
                    self.wav_file.close()
            except Exception:
                pass
            self.wav_file = None
            return False, self.wav_filename

    def stop(self):
        self.running = False
        if self.udp_socket:
            try:
                self.udp_socket.close()
            except Exception:
                pass
        if self.tcp_server:
            try:
                self.tcp_server.close()
            except Exception:
                pass
        if self.tcp_client:
            try:
                self.tcp_client.close()
            except Exception:
                pass
        if self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except Exception:
                pass
        if self.monitor_stream:
            try:
                self.monitor_stream.stop()
                self.monitor_stream.close()
            except Exception:
                pass
        if self.wav_file:
            try:
                self.wav_file.close()
            except Exception:
                pass


# ==============================================================================
# REDESIGNED MODERN OBSIDIAN GUI (V0.7.5 STUDIO EDITION)
# ==============================================================================
class PhoneMicGui:
    """
    Modern, sleek desktop interface inspired by modern audio workstations & Material 3 Dark:
    - 32-Band Neon Spectrum Visualizer with Ballistic Peak Gravity & Oscilloscope
    - Real-Time Protocol & Telemetry Dashboard (UDP/TCP, Jitter, Loss, Bitrate)
    - Studio Audio FX:
        * Smart WOLA Spectral Noise Canceler with 80Hz Rumble High-Pass Cut
        * Real 3-Band Parametric Equalizer (Warmth, Clarity, Air) + 5 Quick Presets
        * Artifact-Free Rotating Dual-Tap Voice Pitch Shifter + 5 Presets
        * Anti-Click Studio Noise Gate
        * Independent Headphone Monitor Volume
    - Network & Device Endpoints (Wi-Fi, USB Tether, Virtual Cable Guide)
    - 0% Background CPU when minimized (<Unmap>)
    """
    def __init__(self, root, receiver):
        self.root = root
        self.receiver = receiver
        self.is_visible = True
        self.anim_timer = None
        self.active_tab = "dashboard"
        self.visualizer_mode = "spectrum"

        self.root.title(f"PhoneMic Studio Receiver v{VERSION}")
        self.root.geometry("680x760")
        self.root.minsize(620, 680)

        # Deep Obsidian & Modern Studio Palette
        self.C_BG = "#0d1117"               # Obsidian Canvas
        self.C_SURFACE = "#161b22"          # Elevated Card
        self.C_SURFACE_ALT = "#21262d"      # Inner Card / Controls
        self.C_BORDER = "#30363d"           # Subtle Card Border
        self.C_PRIMARY = "#38bdf8"          # Electric Sky Blue
        self.C_SUCCESS = "#10b981"          # Radiant Emerald
        self.C_WARNING = "#f59e0b"          # Amber
        self.C_DANGER = "#f43f5e"           # Rose Coral
        self.C_PURPLE = "#a855f7"           # Violet Studio
        self.C_TEXT_PRI = "#f0f6fc"         # High-contrast White
        self.C_TEXT_SEC = "#8b949e"         # Soft Gray
        self.C_TEXT_MUTED = "#6e7681"       # Slate Muted

        self.root.configure(bg=self.C_BG)

        # Pause canvas drawing when minimized (CPU Saver)
        self.root.bind("<Unmap>", self.on_unmap)
        self.root.bind("<Map>", self.on_map)

        self._build_ui()
        self.schedule_next_tick()

    def on_unmap(self, event=None):
        if event and event.widget != self.root:
            return
        self.is_visible = False
        if self.anim_timer:
            try:
                self.root.after_cancel(self.anim_timer)
            except Exception:
                pass
            self.anim_timer = None

    def on_map(self, event=None):
        if event and event.widget != self.root:
            return
        self.is_visible = True
        if not self.anim_timer:
            self.schedule_next_tick()

    def _build_ui(self):
        container = tk.Frame(self.root, bg=self.C_BG)
        container.pack(fill="both", expand=True, padx=16, pady=12)

        # ----------------------------------------------------------------------
        # Top Header Bar: App Identity, Protocol Pill & Live Status Badge
        # ----------------------------------------------------------------------
        header = tk.Frame(container, bg=self.C_BG)
        header.pack(fill="x", pady=(0, 10))

        title_col = tk.Frame(header, bg=self.C_BG)
        title_col.pack(side="left")

        title_lbl = tk.Label(
            title_col, text="🎙️ PhoneMic Studio",
            font=("Segoe UI", 16, "bold"), fg=self.C_PRIMARY, bg=self.C_BG
        )
        title_lbl.pack(side="left")

        ver_badge = tk.Label(
            title_col, text=f"v{VERSION}",
            font=("Consolas", 9, "bold"), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE_ALT,
            padx=6, pady=2
        )
        ver_badge.pack(side="left", padx=8, pady=(2, 0))

        # Status & Transport Pills on Right
        status_box = tk.Frame(header, bg=self.C_BG)
        status_box.pack(side="right")

        self.transport_pill = tk.Label(
            status_box, text="UDP :5001", font=("Consolas", 9, "bold"),
            fg="#60a5fa", bg="#172554", padx=8, pady=3, relief="flat"
        )
        self.transport_pill.pack(side="left", padx=(0, 6))

        self.status_pill = tk.Label(
            status_box, text="○ STANDBY", font=("Segoe UI", 9, "bold"),
            fg=self.C_WARNING, bg="#27272a", padx=10, pady=3, relief="flat"
        )
        self.status_pill.pack(side="left")

        # ----------------------------------------------------------------------
        # Segmented Modern Pill Tab Navigation
        # ----------------------------------------------------------------------
        nav_wrapper = tk.Frame(container, bg=self.C_SURFACE, padx=3, pady=3, highlightthickness=1, highlightbackground=self.C_BORDER)
        nav_wrapper.pack(fill="x", pady=(0, 10))

        self.tab_btns = {}
        tabs = [
            ("dashboard", "📊 Studio Dashboard"),
            ("fx_studio", "🎛️ Audio FX & Equalizer"),
            ("network", "🌐 Network & Routing"),
        ]

        for key, label in tabs:
            btn = tk.Button(
                nav_wrapper, text=label, font=("Segoe UI", 9, "bold"),
                relief="flat", padx=14, pady=5, bd=0, cursor="hand2",
                command=lambda k=key: self.switch_tab(k)
            )
            btn.pack(side="left", expand=True, fill="x", padx=2)
            self.tab_btns[key] = btn

        # Container for Dynamic Tab Pages
        self.page_container = tk.Frame(container, bg=self.C_BG)
        self.page_container.pack(fill="both", expand=True)

        self.pages = {}
        self._build_dashboard_page()
        self._build_fx_studio_page()
        self._build_network_page()

        self.switch_tab("dashboard")

        # ----------------------------------------------------------------------
        # Sticky Bottom Action Dock (Mute, Monitor, Record, Firewall)
        # ----------------------------------------------------------------------
        dock = tk.Frame(container, bg=self.C_SURFACE, padx=12, pady=10, highlightthickness=1, highlightbackground=self.C_BORDER)
        dock.pack(fill="x", pady=(10, 0))

        self.pause_btn = tk.Button(
            dock, text="Mute Audio", font=("Segoe UI", 9, "bold"),
            fg=self.C_TEXT_PRI, bg="#2d3748", activebackground="#4a5568",
            relief="flat", padx=12, pady=6, cursor="hand2", command=self.on_toggle_pause
        )
        self.pause_btn.pack(side="left", fill="x", expand=True, padx=3)

        self.monitor_btn = tk.Button(
            dock, text="🎧 Monitor Mic", font=("Segoe UI", 9, "bold"),
            fg=self.C_TEXT_PRI, bg="#2d3748", activebackground="#4a5568",
            relief="flat", padx=12, pady=6, cursor="hand2", command=self.on_toggle_monitor
        )
        self.monitor_btn.pack(side="left", fill="x", expand=True, padx=3)

        self.record_btn = tk.Button(
            dock, text="⏺ Record WAV", font=("Segoe UI", 9, "bold"),
            fg=self.C_TEXT_PRI, bg="#2d3748", activebackground="#4a5568",
            relief="flat", padx=12, pady=6, cursor="hand2", command=self.on_toggle_record
        )
        self.record_btn.pack(side="left", fill="x", expand=True, padx=3)

        self.fw_btn = tk.Button(
            dock, text="🛡️ Fix Firewall", font=("Segoe UI", 9, "bold"),
            fg="#ffffff", bg="#0284c7", activebackground="#0369a1",
            relief="flat", padx=12, pady=6, cursor="hand2", command=self.on_fix_firewall
        )
        if not check_windows_firewall_rule():
            self.fw_btn.pack(side="left", fill="x", expand=True, padx=3)

        # Status Ticker line
        self.notice_lbl = tk.Label(
            container, text="Ready. Listening on UDP/TCP port 5001. Connect from PhoneMic Android app.",
            font=("Segoe UI", 8), fg=self.C_TEXT_MUTED, bg=self.C_BG
        )
        self.notice_lbl.pack(fill="x", pady=(6, 0))

        # Initial scans
        self._refresh_network_ips_async()
        self._populate_audio_devices()

    def switch_tab(self, tab_key):
        self.active_tab = tab_key
        for k, btn in self.tab_btns.items():
            if k == tab_key:
                btn.config(bg=self.C_PRIMARY, fg="#04111d")
            else:
                btn.config(bg=self.C_SURFACE_ALT, fg=self.C_TEXT_SEC)

        for k, page in self.pages.items():
            if k == tab_key:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()

    # ==========================================================================
    # TAB 1: STUDIO DASHBOARD & VISUALIZER
    # ==========================================================================
    def _build_dashboard_page(self):
        page = tk.Frame(self.page_container, bg=self.C_BG)
        self.pages["dashboard"] = page

        # 1. AUDIO VISUALIZER CARD
        vis_card = tk.Frame(page, bg=self.C_SURFACE, padx=14, pady=12, highlightthickness=1, highlightbackground=self.C_BORDER)
        vis_card.pack(fill="both", expand=True, pady=(0, 8))

        # Visualizer Top Bar
        vis_top = tk.Frame(vis_card, bg=self.C_SURFACE)
        vis_top.pack(fill="x", pady=(0, 6))

        tk.Label(
            vis_top, text="REAL-TIME AUDIO SPECTRUM",
            font=("Segoe UI", 9, "bold"), fg=self.C_TEXT_SEC, bg=self.C_SURFACE
        ).pack(side="left")

        self.vis_mode_btn = tk.Button(
            vis_top, text="32-Band Spectrum ▾", font=("Segoe UI", 8, "bold"),
            fg=self.C_PRIMARY, bg=self.C_SURFACE_ALT, relief="flat", padx=8, pady=2,
            cursor="hand2", command=self.toggle_visualizer_mode
        )
        self.vis_mode_btn.pack(side="left", padx=10)

        self.db_lbl = tk.Label(
            vis_top, text="-80.0 dB", font=("Consolas", 11, "bold"),
            fg=self.C_TEXT_PRI, bg=self.C_SURFACE
        )
        self.db_lbl.pack(side="right")

        tk.Label(
            vis_top, text="Peak: ", font=("Segoe UI", 9),
            fg=self.C_TEXT_MUTED, bg=self.C_SURFACE
        ).pack(side="right")

        # Visualizer Canvas
        self.vis_canvas = tk.Canvas(vis_card, height=135, bg="#070a0f", highlightthickness=1, highlightbackground=self.C_BORDER)
        self.vis_canvas.pack(fill="both", expand=True, pady=4)

        # 32 Bar rectangles & Peak caps
        self.spec_bar_ids = []
        self.spec_peak_ids = []
        for _ in range(32):
            b_id = self.vis_canvas.create_rectangle(0, 0, 0, 0, fill=self.C_PRIMARY, width=0)
            p_id = self.vis_canvas.create_line(0, 0, 0, 0, fill="#ffffff", width=2)
            self.spec_bar_ids.append(b_id)
            self.spec_peak_ids.append(p_id)

        # Oscilloscope Waveform line
        self.osc_line_id = self.vis_canvas.create_line(0, 0, 0, 0, fill=self.C_SUCCESS, width=2)

        # Horizontal Stereo VU Meter with dB scale
        vu_box = tk.Frame(vis_card, bg=self.C_SURFACE)
        vu_box.pack(fill="x", pady=(6, 0))

        self.vu_canvas = tk.Canvas(vu_box, height=14, bg="#070a0f", highlightthickness=1, highlightbackground=self.C_BORDER)
        self.vu_canvas.pack(fill="x")
        self.vu_active_id = self.vu_canvas.create_rectangle(0, 0, 0, 14, fill=self.C_SUCCESS, width=0)
        self.vu_peak_id = self.vu_canvas.create_line(0, 0, 0, 14, fill="#ffffff", width=2)

        # Scale markings
        scale_box = tk.Frame(vis_card, bg=self.C_SURFACE)
        scale_box.pack(fill="x", pady=(2, 0))
        for mark in ("-40 dB", "-24 dB", "-12 dB", "-6 dB", "-3 dB", "0 dB"):
            tk.Label(scale_box, text=mark, font=("Consolas", 7), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE).pack(side="left", expand=True)

        # 2. TELEMETRY METRIC GRID (4 CLEAN TILES)
        grid_frame = tk.Frame(page, bg=self.C_BG)
        grid_frame.pack(fill="x", pady=4)
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        # Tile 1: Protocol & Port
        t1 = tk.Frame(grid_frame, bg=self.C_SURFACE, padx=10, pady=8, highlightthickness=1, highlightbackground=self.C_BORDER)
        t1.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
        tk.Label(t1, text="PROTOCOL & PORT", font=("Segoe UI", 7, "bold"), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE).pack(anchor="w")
        self.t_proto_lbl = tk.Label(t1, text="UDP :5001 (Standby)", font=("Segoe UI", 9, "bold"), fg=self.C_PRIMARY, bg=self.C_SURFACE)
        self.t_proto_lbl.pack(anchor="w")

        # Tile 2: Connection Medium & Client
        t2 = tk.Frame(grid_frame, bg=self.C_SURFACE, padx=10, pady=8, highlightthickness=1, highlightbackground=self.C_BORDER)
        t2.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))
        tk.Label(t2, text="CLIENT & MEDIUM", font=("Segoe UI", 7, "bold"), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE).pack(anchor="w")
        self.t_medium_lbl = tk.Label(t2, text="Waiting for phone...", font=("Segoe UI", 9, "bold"), fg=self.C_TEXT_PRI, bg=self.C_SURFACE)
        self.t_medium_lbl.pack(anchor="w")

        # Tile 3: Jitter & Bitrate
        t3 = tk.Frame(grid_frame, bg=self.C_SURFACE, padx=10, pady=8, highlightthickness=1, highlightbackground=self.C_BORDER)
        t3.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(4, 0))
        tk.Label(t3, text="JITTER & BITRATE", font=("Segoe UI", 7, "bold"), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE).pack(anchor="w")
        self.t_jitter_bitrate_lbl = tk.Label(t3, text="Jitter: -- • Bitrate: 768 kbps", font=("Segoe UI", 9), fg=self.C_TEXT_PRI, bg=self.C_SURFACE)
        self.t_jitter_bitrate_lbl.pack(anchor="w")

        # Tile 4: Packets & Loss & Uptime
        t4 = tk.Frame(grid_frame, bg=self.C_SURFACE, padx=10, pady=8, highlightthickness=1, highlightbackground=self.C_BORDER)
        t4.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))
        tk.Label(t4, text="PACKETS, LOSS & UPTIME", font=("Segoe UI", 7, "bold"), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE).pack(anchor="w")
        self.t_loss_uptime_lbl = tk.Label(t4, text="Loss: 0 pkts (0.0%) • 00:00:00", font=("Segoe UI", 9), fg=self.C_TEXT_PRI, bg=self.C_SURFACE)
        self.t_loss_uptime_lbl.pack(anchor="w")

        # 3. QUICK MASTER GAIN BOOST
        gain_card = tk.Frame(page, bg=self.C_SURFACE, padx=12, pady=8, highlightthickness=1, highlightbackground=self.C_BORDER)
        gain_card.pack(fill="x", pady=4)

        tk.Label(
            gain_card, text="Mic Gain Boost:", font=("Segoe UI", 9, "bold"),
            fg=self.C_TEXT_PRI, bg=self.C_SURFACE, width=14, anchor="w"
        ).pack(side="left")

        self.gain_scale = tk.Scale(
            gain_card, from_=0.0, to=4.0, resolution=0.1, orient="horizontal",
            bg=self.C_SURFACE, fg=self.C_TEXT_PRI, highlightthickness=0, bd=0,
            troughcolor=self.C_SURFACE_ALT, activebackground=self.C_PRIMARY,
            command=self.on_gain_changed
        )
        self.gain_scale.set(1.0)
        self.gain_scale.pack(side="left", fill="x", expand=True, padx=8)

        self.gain_val_lbl = tk.Label(
            gain_card, text="1.0x (0 dB)", font=("Consolas", 9, "bold"),
            fg=self.C_PRIMARY, bg=self.C_SURFACE, width=12
        )
        self.gain_val_lbl.pack(side="right")

    def toggle_visualizer_mode(self):
        if self.visualizer_mode == "spectrum":
            self.visualizer_mode = "oscilloscope"
            self.vis_mode_btn.config(text="Oscilloscope Wave ▾", fg=self.C_SUCCESS)
        else:
            self.visualizer_mode = "spectrum"
            self.vis_mode_btn.config(text="32-Band Spectrum ▾", fg=self.C_PRIMARY)

    # ==========================================================================
    # TAB 2: AUDIO FX & STUDIO EQUALIZER
    # ==========================================================================
    def _build_fx_studio_page(self):
        page = tk.Frame(self.page_container, bg=self.C_BG)
        self.pages["fx_studio"] = page

        # 1. SMART NOISE SUPPRESSION (WOLA SINE-WINDOW WIENER + RUMBLE CUT)
        nc_card = tk.Frame(page, bg=self.C_SURFACE, padx=14, pady=10, highlightthickness=1, highlightbackground=self.C_BORDER)
        nc_card.pack(fill="x", pady=(0, 6))

        nc_top = tk.Frame(nc_card, bg=self.C_SURFACE)
        nc_top.pack(fill="x")

        self.nc_toggle_btn = tk.Button(
            nc_top, text="[✓] Active (Wiener Filter)", font=("Segoe UI", 9, "bold"),
            fg="#ffffff", bg="#059669", activebackground="#047857",
            relief="flat", padx=10, pady=3, cursor="hand2", command=self.on_toggle_nc
        )
        self.nc_toggle_btn.pack(side="left")

        tk.Label(
            nc_top, text="WOLA Spectral Subtraction + 80Hz Butterworth Rumble Cut (Zero Artifacts)",
            font=("Segoe UI", 8), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE
        ).pack(side="left", padx=10)

        # Slider row
        nc_slider_row = tk.Frame(nc_card, bg=self.C_SURFACE)
        nc_slider_row.pack(fill="x", pady=(6, 0))

        tk.Label(
            nc_slider_row, text="Suppression Amount:", font=("Segoe UI", 8),
            fg=self.C_TEXT_SEC, bg=self.C_SURFACE, width=18, anchor="w"
        ).pack(side="left")

        self.nc_scale = tk.Scale(
            nc_slider_row, from_=0, to=100, orient="horizontal",
            bg=self.C_SURFACE, fg=self.C_TEXT_PRI, highlightthickness=0, bd=0,
            troughcolor=self.C_SURFACE_ALT, activebackground=self.C_SUCCESS,
            command=self.on_nc_amount_changed
        )
        self.nc_scale.set(65)
        self.nc_scale.pack(side="left", fill="x", expand=True, padx=6)

        self.nc_val_lbl = tk.Label(
            nc_slider_row, text="65% (Optimal)", font=("Consolas", 8, "bold"),
            fg=self.C_SUCCESS, bg=self.C_SURFACE, width=14
        )
        self.nc_val_lbl.pack(side="right")

        # 2. REAL 3-BAND STUDIO PARAMETRIC EQUALIZER
        eq_card = tk.Frame(page, bg=self.C_SURFACE, padx=14, pady=10, highlightthickness=1, highlightbackground=self.C_BORDER)
        eq_card.pack(fill="x", pady=6)

        eq_top = tk.Frame(eq_card, bg=self.C_SURFACE)
        eq_top.pack(fill="x")

        tk.Label(
            eq_top, text="3-BAND STUDIO PARAMETRIC EQUALIZER",
            font=("Segoe UI", 9, "bold"), fg=self.C_PRIMARY, bg=self.C_SURFACE
        ).pack(side="left")

        # Presets bar
        eq_presets = tk.Frame(eq_top, bg=self.C_SURFACE)
        eq_presets.pack(side="right")

        presets = [
            ("Flat", 0.0, 0.0, 0.0),
            ("Warmth", 4.0, 1.5, 2.5),
            ("Crisp", -2.0, 3.5, 5.0),
            ("De-Boom", -5.0, 1.0, 2.0),
        ]
        for name, l, m, h in presets:
            tk.Button(
                eq_presets, text=name, font=("Segoe UI", 7, "bold"),
                fg=self.C_TEXT_PRI, bg=self.C_SURFACE_ALT, activebackground="#374151",
                relief="flat", padx=6, pady=1, cursor="hand2",
                command=lambda low=l, mid=m, high=h: self.apply_eq_preset(low, mid, high)
            ).pack(side="left", padx=2)

        # Band 1: Low Shelf (Warmth @ 120Hz)
        r_low = tk.Frame(eq_card, bg=self.C_SURFACE)
        r_low.pack(fill="x", pady=(6, 2))
        tk.Label(r_low, text="Low Warmth (120 Hz):", font=("Segoe UI", 8), fg=self.C_TEXT_SEC, bg=self.C_SURFACE, width=20, anchor="w").pack(side="left")
        self.eq_low_scale = tk.Scale(
            r_low, from_=-12.0, to=12.0, resolution=0.5, orient="horizontal",
            bg=self.C_SURFACE, fg=self.C_TEXT_PRI, highlightthickness=0, bd=0,
            troughcolor=self.C_SURFACE_ALT, activebackground=self.C_PRIMARY,
            command=self.on_eq_low_changed
        )
        self.eq_low_scale.set(0.0)
        self.eq_low_scale.pack(side="left", fill="x", expand=True, padx=6)
        self.eq_low_lbl = tk.Label(r_low, text="0.0 dB", font=("Consolas", 8, "bold"), fg=self.C_PRIMARY, bg=self.C_SURFACE, width=10)
        self.eq_low_lbl.pack(side="right")

        # Band 2: Mid Peaking (Clarity @ 2500Hz)
        r_mid = tk.Frame(eq_card, bg=self.C_SURFACE)
        r_mid.pack(fill="x", pady=2)
        tk.Label(r_mid, text="Mid Clarity (2.5 kHz):", font=("Segoe UI", 8), fg=self.C_TEXT_SEC, bg=self.C_SURFACE, width=20, anchor="w").pack(side="left")
        self.eq_mid_scale = tk.Scale(
            r_mid, from_=-12.0, to=12.0, resolution=0.5, orient="horizontal",
            bg=self.C_SURFACE, fg=self.C_TEXT_PRI, highlightthickness=0, bd=0,
            troughcolor=self.C_SURFACE_ALT, activebackground=self.C_PRIMARY,
            command=self.on_eq_mid_changed
        )
        self.eq_mid_scale.set(0.0)
        self.eq_mid_scale.pack(side="left", fill="x", expand=True, padx=6)
        self.eq_mid_lbl = tk.Label(r_mid, text="0.0 dB", font=("Consolas", 8, "bold"), fg=self.C_PRIMARY, bg=self.C_SURFACE, width=10)
        self.eq_mid_lbl.pack(side="right")

        # Band 3: High Shelf (Air @ 8000Hz)
        r_high = tk.Frame(eq_card, bg=self.C_SURFACE)
        r_high.pack(fill="x", pady=2)
        tk.Label(r_high, text="High Air (8.0 kHz):", font=("Segoe UI", 8), fg=self.C_TEXT_SEC, bg=self.C_SURFACE, width=20, anchor="w").pack(side="left")
        self.eq_high_scale = tk.Scale(
            r_high, from_=-12.0, to=12.0, resolution=0.5, orient="horizontal",
            bg=self.C_SURFACE, fg=self.C_TEXT_PRI, highlightthickness=0, bd=0,
            troughcolor=self.C_SURFACE_ALT, activebackground=self.C_PRIMARY,
            command=self.on_eq_high_changed
        )
        self.eq_high_scale.set(0.0)
        self.eq_high_scale.pack(side="left", fill="x", expand=True, padx=6)
        self.eq_high_lbl = tk.Label(r_high, text="0.0 dB", font=("Consolas", 8, "bold"), fg=self.C_PRIMARY, bg=self.C_SURFACE, width=10)
        self.eq_high_lbl.pack(side="right")

        # 3. ARTIFACT-FREE VOICE PITCH SHIFTER
        pitch_card = tk.Frame(page, bg=self.C_SURFACE, padx=14, pady=10, highlightthickness=1, highlightbackground=self.C_BORDER)
        pitch_card.pack(fill="x", pady=6)

        pitch_top = tk.Frame(pitch_card, bg=self.C_SURFACE)
        pitch_top.pack(fill="x")

        tk.Label(
            pitch_top, text="REAL-TIME VOICE HARMONIZER (PITCH SHIFTER)",
            font=("Segoe UI", 9, "bold"), fg=self.C_PURPLE, bg=self.C_SURFACE
        ).pack(side="left")

        tk.Label(
            pitch_top, text="Dual-Tap Rotating Delay (Zero Clicks)",
            font=("Segoe UI", 8), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE
        ).pack(side="right")

        pitch_row = tk.Frame(pitch_card, bg=self.C_SURFACE)
        pitch_row.pack(fill="x", pady=(6, 2))

        tk.Label(pitch_row, text="Pitch Shift:", font=("Segoe UI", 8), fg=self.C_TEXT_SEC, bg=self.C_SURFACE, width=14, anchor="w").pack(side="left")

        self.pitch_scale = tk.Scale(
            pitch_row, from_=-12.0, to=12.0, resolution=0.5, orient="horizontal",
            bg=self.C_SURFACE, fg=self.C_TEXT_PRI, highlightthickness=0, bd=0,
            troughcolor=self.C_SURFACE_ALT, activebackground=self.C_PURPLE,
            command=self.on_pitch_changed
        )
        self.pitch_scale.set(0.0)
        self.pitch_scale.pack(side="left", fill="x", expand=True, padx=6)

        self.pitch_val_lbl = tk.Label(
            pitch_row, text="0.0 st (Natural)", font=("Consolas", 8, "bold"),
            fg=self.C_PURPLE, bg=self.C_SURFACE, width=16
        )
        self.pitch_val_lbl.pack(side="right")

        # Pitch Preset Chips
        pitch_chips = tk.Frame(pitch_card, bg=self.C_SURFACE)
        pitch_chips.pack(fill="x", pady=(4, 0))

        p_presets = [
            ("Natural (0st)", 0.0),
            ("Deep Voice (-3st)", -3.0),
            ("Announcer (-1.5st)", -1.5),
            ("Crisp (+1.5st)", 1.5),
            ("Helium (+5st)", 5.0),
        ]
        for title, val in p_presets:
            tk.Button(
                pitch_chips, text=title, font=("Segoe UI", 7),
                fg=self.C_TEXT_PRI, bg=self.C_SURFACE_ALT, activebackground="#374151",
                relief="flat", padx=6, pady=2, cursor="hand2",
                command=lambda v=val: self.set_pitch_preset(v)
            ).pack(side="left", padx=2, fill="x", expand=True)

        # 4. STUDIO NOISE GATE & HEADPHONE MONITOR VOLUME
        sub_grid = tk.Frame(page, bg=self.C_BG)
        sub_grid.pack(fill="x", pady=6)
        sub_grid.columnconfigure(0, weight=1)
        sub_grid.columnconfigure(1, weight=1)

        # Studio Noise Gate Card
        gate_card = tk.Frame(sub_grid, bg=self.C_SURFACE, padx=12, pady=10, highlightthickness=1, highlightbackground=self.C_BORDER)
        gate_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        tk.Label(gate_card, text="STUDIO NOISE GATE", font=("Segoe UI", 8, "bold"), fg=self.C_WARNING, bg=self.C_SURFACE).pack(anchor="w")
        tk.Label(gate_card, text="Smooth anti-click floor gate", font=("Segoe UI", 7), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE).pack(anchor="w")

        gate_srow = tk.Frame(gate_card, bg=self.C_SURFACE)
        gate_srow.pack(fill="x", pady=(4, 0))
        self.gate_scale = tk.Scale(
            gate_srow, from_=-80, to=-30, orient="horizontal",
            bg=self.C_SURFACE, fg=self.C_TEXT_PRI, highlightthickness=0, bd=0,
            troughcolor=self.C_SURFACE_ALT, activebackground=self.C_WARNING,
            command=self.on_gate_changed
        )
        self.gate_scale.set(int(NOISE_GATE_THRESHOLD_DB))
        self.gate_scale.pack(side="left", fill="x", expand=True)
        self.gate_val_lbl = tk.Label(gate_srow, text=f"{int(NOISE_GATE_THRESHOLD_DB)} dB", font=("Consolas", 8, "bold"), fg=self.C_WARNING, bg=self.C_SURFACE, width=7)
        self.gate_val_lbl.pack(side="right")

        # Headphone Monitor Card
        mon_card = tk.Frame(sub_grid, bg=self.C_SURFACE, padx=12, pady=10, highlightthickness=1, highlightbackground=self.C_BORDER)
        mon_card.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        tk.Label(mon_card, text="HEADPHONE MONITOR LEVEL", font=("Segoe UI", 8, "bold"), fg=self.C_SUCCESS, bg=self.C_SURFACE).pack(anchor="w")
        tk.Label(mon_card, text="Independent monitoring volume", font=("Segoe UI", 7), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE).pack(anchor="w")

        mon_srow = tk.Frame(mon_card, bg=self.C_SURFACE)
        mon_srow.pack(fill="x", pady=(4, 0))
        self.mon_vol_scale = tk.Scale(
            mon_srow, from_=0, to=100, orient="horizontal",
            bg=self.C_SURFACE, fg=self.C_TEXT_PRI, highlightthickness=0, bd=0,
            troughcolor=self.C_SURFACE_ALT, activebackground=self.C_SUCCESS,
            command=self.on_mon_vol_changed
        )
        self.mon_vol_scale.set(85)
        self.mon_vol_scale.pack(side="left", fill="x", expand=True)
        self.mon_vol_lbl = tk.Label(mon_srow, text="85%", font=("Consolas", 8, "bold"), fg=self.C_SUCCESS, bg=self.C_SURFACE, width=6)
        self.mon_vol_lbl.pack(side="right")

    def on_toggle_nc(self):
        p = self.receiver.processor
        p.smart_noise_cancel = not p.smart_noise_cancel
        if p.smart_noise_cancel:
            self.nc_toggle_btn.config(text="[✓] Active (Wiener Filter)", bg="#059669")
            self.notice_lbl.config(text="Smart WOLA noise cancellation ENABLED", fg=self.C_SUCCESS)
        else:
            self.nc_toggle_btn.config(text="[Off] Disabled (Bypass)", bg="#374151")
            self.notice_lbl.config(text="Noise cancellation bypassed (raw microphone stream)", fg=self.C_TEXT_MUTED)

    def on_nc_amount_changed(self, val):
        pct = float(val) / 100.0
        self.receiver.processor.noise_cancel_amount = pct
        self.nc_val_lbl.config(text=f"{int(val)}%")

    def apply_eq_preset(self, low_db, mid_db, high_db):
        self.eq_low_scale.set(low_db)
        self.eq_mid_scale.set(mid_db)
        self.eq_high_scale.set(high_db)
        self.on_eq_low_changed(low_db)
        self.on_eq_mid_changed(mid_db)
        self.on_eq_high_changed(high_db)
        self.notice_lbl.config(text=f"EQ Preset Applied: Low {low_db:+.1f}dB, Mid {mid_db:+.1f}dB, High {high_db:+.1f}dB", fg=self.C_PRIMARY)

    def on_eq_low_changed(self, val):
        db = float(val)
        self.receiver.processor.update_eq(low_db=db)
        self.eq_low_lbl.config(text=f"{db:+.1f} dB")

    def on_eq_mid_changed(self, val):
        db = float(val)
        self.receiver.processor.update_eq(mid_db=db)
        self.eq_mid_lbl.config(text=f"{db:+.1f} dB")

    def on_eq_high_changed(self, val):
        db = float(val)
        self.receiver.processor.update_eq(high_db=db)
        self.eq_high_lbl.config(text=f"{db:+.1f} dB")

    def on_pitch_changed(self, val):
        st = float(val)
        self.receiver.processor.pitch_shift_semitones = st
        if abs(st) < 0.15:
            desc = "0.0 st (Natural)"
        elif st > 0:
            desc = f"+{st:.1f} st (Higher)"
        else:
            desc = f"{st:.1f} st (Deeper)"
        self.pitch_val_lbl.config(text=desc)

    def set_pitch_preset(self, st):
        self.pitch_scale.set(st)
        self.on_pitch_changed(st)

    def on_gate_changed(self, val):
        g = float(val)
        self.receiver.processor.gate_threshold_db = g
        self.gate_val_lbl.config(text=f"{int(g)} dB")

    def on_mon_vol_changed(self, val):
        vol = float(val) / 100.0
        self.receiver.processor.monitor_volume = vol
        self.mon_vol_lbl.config(text=f"{int(val)}%")

    # ==========================================================================
    # TAB 3: NETWORK & DEVICE ROUTING
    # ==========================================================================
    def _build_network_page(self):
        page = tk.Frame(self.page_container, bg=self.C_BG)
        self.pages["network"] = page

        # 1. NETWORK IP ADDRESSES CARD
        net_card = tk.Frame(page, bg=self.C_SURFACE, padx=14, pady=12, highlightthickness=1, highlightbackground=self.C_BORDER)
        net_card.pack(fill="x", pady=(0, 6))

        tk.Label(net_card, text="NETWORK CONNECTION IP ADDRESSES", font=("Segoe UI", 9, "bold"), fg=self.C_PRIMARY, bg=self.C_SURFACE).pack(anchor="w")

        # Wi-Fi Row
        wf = tk.Frame(net_card, bg=self.C_SURFACE)
        wf.pack(fill="x", pady=(6, 3))
        tk.Label(wf, text="Wi-Fi IP:", font=("Segoe UI", 9, "bold"), fg=self.C_PRIMARY, bg=self.C_SURFACE, width=14, anchor="w").pack(side="left")
        self.wifi_ip_lbl = tk.Label(wf, text="Detecting...", font=("Consolas", 10, "bold"), fg=self.C_TEXT_PRI, bg=self.C_SURFACE)
        self.wifi_ip_lbl.pack(side="left", padx=4)
        tk.Button(wf, text="Copy", font=("Segoe UI", 8), fg=self.C_TEXT_PRI, bg=self.C_SURFACE_ALT, relief="flat", padx=8, command=lambda: self._copy_ip(self.wifi_ip)).pack(side="right")

        # USB Tether Row
        uf = tk.Frame(net_card, bg=self.C_SURFACE)
        uf.pack(fill="x", pady=3)
        tk.Label(uf, text="USB Tether IP:", font=("Segoe UI", 9, "bold"), fg=self.C_SUCCESS, bg=self.C_SURFACE, width=14, anchor="w").pack(side="left")
        self.usb_ip_lbl = tk.Label(uf, text="Plug phone in USB tether mode", font=("Consolas", 10), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE)
        self.usb_ip_lbl.pack(side="left", padx=4)
        tk.Button(uf, text="Copy", font=("Segoe UI", 8), fg=self.C_TEXT_PRI, bg=self.C_SURFACE_ALT, relief="flat", padx=8, command=lambda: self._copy_ip(self.usb_ip)).pack(side="right")

        # Refresh
        hint_f = tk.Frame(net_card, bg=self.C_SURFACE)
        hint_f.pack(fill="x", pady=(6, 0))
        tk.Label(
            hint_f, text="Tip: When using USB, enable 'USB Tethering' on phone, then enter USB Tether IP in phone app.",
            font=("Segoe UI", 8), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE
        ).pack(side="left")
        tk.Button(hint_f, text="⟳ Refresh IPs", font=("Segoe UI", 8), fg=self.C_PRIMARY, bg=self.C_SURFACE_ALT, relief="flat", padx=8, command=self._refresh_network_ips_async).pack(side="right")

        # 2. AUDIO OUTPUT ENDPOINT CARD
        audio_card = tk.Frame(page, bg=self.C_SURFACE, padx=14, pady=12, highlightthickness=1, highlightbackground=self.C_BORDER)
        audio_card.pack(fill="x", pady=6)

        tk.Label(audio_card, text="AUDIO OUTPUT ENDPOINT & ROUTING", font=("Segoe UI", 9, "bold"), fg=self.C_TEXT_SEC, bg=self.C_SURFACE).pack(anchor="w")

        # Main Output
        dev_row = tk.Frame(audio_card, bg=self.C_SURFACE)
        dev_row.pack(fill="x", pady=(6, 3))
        tk.Label(dev_row, text="Main Output:", font=("Segoe UI", 9, "bold"), fg=self.C_TEXT_PRI, bg=self.C_SURFACE, width=14, anchor="w").pack(side="left")
        self.device_combo = ttk.Combobox(dev_row, state="readonly", font=("Segoe UI", 9), width=34)
        self.device_combo.pack(side="left", padx=6, fill="x", expand=True)
        self.device_combo.bind("<<ComboboxSelected>>", self.on_device_selected)
        tk.Button(dev_row, text="⟳", font=("Segoe UI", 9, "bold"), fg=self.C_TEXT_PRI, bg=self.C_SURFACE_ALT, relief="flat", padx=8, command=self._populate_audio_devices).pack(side="right")

        # Monitor Output
        mon_row = tk.Frame(audio_card, bg=self.C_SURFACE)
        mon_row.pack(fill="x", pady=(3, 3))
        tk.Label(mon_row, text="Monitor Device:", font=("Segoe UI", 9), fg=self.C_TEXT_SEC, bg=self.C_SURFACE, width=14, anchor="w").pack(side="left")
        self.mon_combo = ttk.Combobox(mon_row, state="readonly", font=("Segoe UI", 9), width=34)
        self.mon_combo.pack(side="left", padx=6, fill="x", expand=True)
        self.mon_combo.bind("<<ComboboxSelected>>", self.on_mon_device_selected)

        self.cable_status_lbl = tk.Label(audio_card, text="Checking VB-CABLE...", font=("Segoe UI", 8), fg=self.C_TEXT_MUTED, bg=self.C_SURFACE, anchor="w")
        self.cable_status_lbl.pack(fill="x", pady=(4, 0))

        # Educational Explainer
        exp = tk.Frame(audio_card, bg="#0f172a", padx=10, pady=8, highlightthickness=1, highlightbackground="#1e293b")
        exp.pack(fill="x", pady=(8, 0))
        tk.Label(exp, text="💡 What is the 'Audio Output Endpoint'?", font=("Segoe UI", 8, "bold"), fg=self.C_PRIMARY, bg="#0f172a").pack(anchor="w")
        tk.Label(
            exp,
            text="PhoneMic receives audio from your phone and outputs it into Windows.\n"
                 "• For Discord / OBS / Zoom: Select 'CABLE Input' here. In Discord/OBS, select 'CABLE Output' as your mic!\n"
                 "• For direct headphone testing: Select PC Speakers or Headphones.",
            font=("Segoe UI", 8), fg=self.C_TEXT_SEC, bg="#0f172a", justify="left"
        ).pack(anchor="w", pady=(2, 0))

        # 3. FIREWALL STATUS
        fw_card = tk.Frame(page, bg=self.C_SURFACE, padx=14, pady=12, highlightthickness=1, highlightbackground=self.C_BORDER)
        fw_card.pack(fill="x", pady=6)

        fw_row = tk.Frame(fw_card, bg=self.C_SURFACE)
        fw_row.pack(fill="x")
        self.fw_status_lbl = tk.Label(fw_row, text="Windows Firewall: Checking...", font=("Segoe UI", 9), fg=self.C_TEXT_PRI, bg=self.C_SURFACE)
        self.fw_status_lbl.pack(side="left")
        self.fw_action_btn = tk.Button(
            fw_row, text="Configure Firewall", font=("Segoe UI", 8, "bold"),
            fg="#ffffff", bg="#0284c7", activebackground="#0369a1",
            relief="flat", padx=8, pady=2, command=self.on_fix_firewall
        )
        self.fw_action_btn.pack(side="right")
        self._update_firewall_status_ui()

    def _update_firewall_status_ui(self):
        rule_ok = check_windows_firewall_rule()
        if hasattr(self, 'fw_status_lbl'):
            if rule_ok:
                self.fw_status_lbl.config(
                    text="[✓] Firewall Port 5001 Allowed across All Profiles (Private & Public)",
                    fg=self.C_SUCCESS
                )
                self.fw_action_btn.pack_forget()
            else:
                self.fw_status_lbl.config(
                    text="[!] Port 5001 rules missing. Packets may be dropped.",
                    fg=self.C_WARNING
                )
                self.fw_action_btn.pack(side="right")

    def _copy_ip(self, ip_str):
        if ip_str:
            self.root.clipboard_clear()
            self.root.clipboard_append(ip_str)
            self.notice_lbl.config(text=f"Copied {ip_str} to clipboard!", fg=self.C_SUCCESS)

    def _refresh_network_ips_async(self):
        if getattr(self, '_ip_refresh_in_progress', False):
            return
        self._ip_refresh_in_progress = True

        def _worker():
            try:
                classified = get_classified_ips()
            except Exception:
                classified = []

            def _apply():
                new_wifi_ip = ""
                new_usb_ip = ""

                for cat, ip in classified:
                    if cat == "Wi-Fi" and not new_wifi_ip:
                        new_wifi_ip = ip
                    elif cat == "USB Tether" and not new_usb_ip:
                        new_usb_ip = ip

                if not new_wifi_ip:
                    for cat, ip in classified:
                        if cat in ("Wi-Fi / LAN", "LAN / Ethernet") and not new_wifi_ip:
                            new_wifi_ip = ip

                if not new_wifi_ip:
                    for cat, ip in classified:
                        if cat not in ("Virtual / WSL", "Link-Local", "USB Tether"):
                            new_wifi_ip = ip
                            break

                self.wifi_ip = new_wifi_ip
                self.usb_ip = new_usb_ip

                if hasattr(self, 'wifi_ip_lbl'):
                    self.wifi_ip_lbl.config(text=self.wifi_ip or "No Wi-Fi detected")
                    if self.usb_ip:
                        self.usb_ip_lbl.config(text=self.usb_ip, fg=self.C_SUCCESS, font=("Consolas", 10, "bold"))
                    else:
                        self.usb_ip_lbl.config(text="Not connected (enable USB tether on phone)", fg=self.C_TEXT_MUTED, font=("Consolas", 9))
                self._ip_refresh_in_progress = False

            try:
                self.root.after(0, _apply)
            except Exception:
                self._ip_refresh_in_progress = False

        threading.Thread(target=_worker, name="PhoneMic-IpScanner", daemon=True).start()

    def _populate_audio_devices(self):
        cable_dev, default_out, all_outputs = find_audio_devices()
        self.devices_list = all_outputs
        names = []
        selected_idx = 0
        default_mon_idx = 0

        for i, (idx, dev) in enumerate(all_outputs):
            name = dev.get('name', f"Device {idx}")
            if cable_dev and idx == cable_dev[0]:
                name = f"★ {name} (VB-CABLE Recommended)"
                selected_idx = i
            elif default_out and idx == default_out[0] and not cable_dev:
                name = f"• {name} (Default Output)"
                selected_idx = i
            if default_out and idx == default_out[0]:
                default_mon_idx = i
            names.append(name)

        if hasattr(self, 'device_combo'):
            self.device_combo['values'] = names
            if names:
                self.device_combo.current(selected_idx)

        if hasattr(self, 'mon_combo'):
            self.mon_combo['values'] = names
            if names:
                self.mon_combo.current(default_mon_idx)

        if hasattr(self, 'cable_status_lbl'):
            if cable_dev:
                self.cable_status_lbl.config(
                    text="[✓] VB-Audio Virtual Cable active! Ready for Discord, OBS, Zoom, and games.", fg=self.C_SUCCESS
                )
            else:
                self.cable_status_lbl.config(
                    text="[!] VB-CABLE not detected. Output routed to speakers. Install free VB-CABLE for virtual mic.", fg=self.C_WARNING
                )

    def on_device_selected(self, event=None):
        sel = self.device_combo.current()
        if 0 <= sel < len(self.devices_list):
            dev_idx = self.devices_list[sel][0]
            self.receiver.set_output_device(dev_idx)
            self.notice_lbl.config(text=f"Main audio routed to: {self.devices_list[sel][1].get('name')}", fg=self.C_PRIMARY)

    def on_mon_device_selected(self, event=None):
        sel = self.mon_combo.current()
        if 0 <= sel < len(self.devices_list):
            dev_idx = self.devices_list[sel][0]
            self.receiver.set_monitor_device(dev_idx)
            self.notice_lbl.config(text=f"Headphone monitor routed to: {self.devices_list[sel][1].get('name')}", fg=self.C_SUCCESS)

    def on_gain_changed(self, val):
        try:
            g = float(val)
            self.receiver.processor.gain = g
            db = 20.0 * math.log10(g) if g > 1e-3 else -80.0
            self.gain_val_lbl.config(text=f"{g:.1f}x ({db:+.1f} dB)")
        except Exception:
            pass

    def on_toggle_pause(self):
        is_paused = self.receiver.toggle_pause()
        if is_paused:
            self.pause_btn.config(text="Unmute Audio", bg=self.C_DANGER)
            self.notice_lbl.config(text="Audio MUTED. Sync signal sent to phone.", fg=self.C_DANGER)
        else:
            self.pause_btn.config(text="Mute Audio", bg="#2d3748")
            self.notice_lbl.config(text="Audio LIVE. Streaming actively.", fg=self.C_SUCCESS)

    def on_toggle_record(self):
        is_rec, name = self.receiver.toggle_recording()
        if is_rec:
            self.record_btn.config(text="■ Stop Rec", bg=self.C_DANGER)
            self.notice_lbl.config(text=f"Recording WAV: {name}", fg=self.C_DANGER)
        else:
            self.record_btn.config(text="⏺ Record WAV", bg="#2d3748")
            self.notice_lbl.config(text=f"WAV saved: {name}", fg=self.C_SUCCESS)

    def on_toggle_monitor(self):
        is_mon, msg = self.receiver.toggle_monitor()
        if is_mon:
            self.monitor_btn.config(text="🎧 Stop Monitor", bg=self.C_SUCCESS)
            self.notice_lbl.config(text="Headphone mic monitoring ACTIVE", fg=self.C_SUCCESS)
        else:
            self.monitor_btn.config(text="🎧 Monitor Mic", bg="#2d3748")
            self.notice_lbl.config(text="Headphone mic monitoring stopped", fg=self.C_TEXT_MUTED)

    def on_fix_firewall(self):
        self.notice_lbl.config(text="Configuring Windows Firewall rules silently...", fg=self.C_PRIMARY)

        def _fw_worker():
            configure_windows_firewall()
            rule_ok = check_windows_firewall_rule()

            def _apply_fw():
                self._update_firewall_status_ui()
                if rule_ok:
                    try:
                        self.fw_btn.pack_forget()
                    except Exception:
                        pass
                    self.notice_lbl.config(text="[✓] Windows Firewall successfully configured for Private & Public networks!", fg=self.C_SUCCESS)
                else:
                    self.notice_lbl.config(text="Firewall rule update initiated. (May require Run as Administrator)", fg=self.C_WARNING)

            try:
                self.root.after(0, _apply_fw)
            except Exception:
                pass

        threading.Thread(target=_fw_worker, name="PhoneMic-FirewallWorker", daemon=True).start()

    def schedule_next_tick(self):
        if self.is_visible:
            self.anim_timer = self.root.after(40, self.update_tick)

    def update_tick(self):
        try:
            if self.root.state() == 'iconic' or not self.root.winfo_viewable():
                self.is_visible = False
                self.anim_timer = None
                return
        except Exception:
            pass

        self._tick_count = getattr(self, '_tick_count', 0) + 1
        if self._tick_count % 250 == 0:
            self._refresh_network_ips_async()

        r = self.receiver
        now = time.time()
        is_streaming = (r.last_packet_time > 0 and (now - r.last_packet_time) < 1.5)

        # 1. Update Status Pill & Transport Badge
        if is_streaming:
            self.status_pill.config(text="● STREAMING", fg=self.C_SUCCESS, bg="#064e3b")
            self.transport_pill.config(text=f"{r.transport} :5001", fg="#60a5fa", bg="#172554")
        elif r.paused:
            self.status_pill.config(text="⏸ MUTED", fg=self.C_DANGER, bg="#450a0a")
            self.transport_pill.config(text=f"{r.transport} :5001", fg="#8b949e", bg="#21262d")
        else:
            self.status_pill.config(text="○ STANDBY", fg=self.C_WARNING, bg="#27272a")
            self.transport_pill.config(text="UDP/TCP :5001", fg="#8b949e", bg="#21262d")

        # 2. Peak Level dB Readout
        peak = r.latest_peak
        db = r.latest_db
        self.db_lbl.config(text=f"{db:.1f} dB" if is_streaming else "-80.0 dB")

        # 3. Render Visualizer Canvas
        w = self.vis_canvas.winfo_width()
        h = self.vis_canvas.winfo_height()

        if w > 20 and h > 20:
            if self.visualizer_mode == "spectrum":
                # Hide waveform line
                self.vis_canvas.coords(self.osc_line_id, 0, 0, 0, 0)

                bins = r.processor.spectrum_bins if is_streaming else [0.0] * 32
                peaks = r.processor.spectrum_peaks if is_streaming else [0.0] * 32
                gap = 2
                bar_w = max(2, (w - (32 * gap)) // 32)

                for b in range(32):
                    bx1 = b * (bar_w + gap) + 4
                    bx2 = bx1 + bar_w
                    val = bins[b]
                    bar_h = int(val * (h - 8))
                    by1 = h - bar_h
                    by2 = h

                    if b < 10:
                        color = self.C_SUCCESS
                    elif b < 21:
                        color = self.C_PRIMARY
                    elif b < 28:
                        color = self.C_PURPLE
                    else:
                        color = self.C_DANGER

                    self.vis_canvas.itemconfig(self.spec_bar_ids[b], fill=color)
                    self.vis_canvas.coords(self.spec_bar_ids[b], bx1, by1, bx2, by2)

                    pk_val = peaks[b]
                    pk_y = max(2, h - int(pk_val * (h - 8)))
                    self.vis_canvas.coords(self.spec_peak_ids[b], bx1, pk_y, bx2, pk_y)

            else:
                # Oscilloscope Mode
                for b in range(32):
                    self.vis_canvas.coords(self.spec_bar_ids[b], 0, 0, 0, 0)
                    self.vis_canvas.coords(self.spec_peak_ids[b], 0, 0, 0, 0)

                wave_samples = r.processor.waveform_cache if is_streaming else [0.0] * 64
                pts = []
                step_x = w / max(1, len(wave_samples) - 1)
                mid_y = h / 2.0
                amp = (h / 2.0) * 0.9

                for i, sample in enumerate(wave_samples):
                    px = i * step_x
                    py = mid_y - (sample * amp)
                    pts.extend([px, py])

                if len(pts) >= 4:
                    self.vis_canvas.coords(self.osc_line_id, *pts)

        # 4. Update VU Meter Bar
        vu_w = self.vu_canvas.winfo_width()
        if vu_w > 10:
            bar_w = int(vu_w * min(1.0, max(0.0, peak))) if is_streaming else 0
            fill_color = self.C_SUCCESS if db < -6 else (self.C_WARNING if db < -1 else self.C_DANGER)
            self.vu_canvas.itemconfig(self.vu_active_id, fill=fill_color)
            self.vu_canvas.coords(self.vu_active_id, 0, 0, bar_w, 14)
            self.vu_canvas.coords(self.vu_peak_id, bar_w, 0, bar_w, 14)

        # 5. Update Telemetry Metric Tiles
        if is_streaming and r.client_addr:
            client_ip = r.client_addr[0]
            is_usb = client_ip.startswith("192.168.42.") or client_ip.startswith("192.168.137.")
            med_text = f"USB Tether (~1ms) • {r.client_addr[0]}" if is_usb else f"Wi-Fi • {r.client_addr[0]}"
            self.t_proto_lbl.config(text=f"{r.transport} Stream (:5001)", fg=self.C_PRIMARY)
            self.t_medium_lbl.config(text=med_text, fg=self.C_SUCCESS if is_usb else self.C_PRIMARY)
        else:
            self.t_proto_lbl.config(text="UDP/TCP :5001 (Standby)", fg=self.C_TEXT_MUTED)
            self.t_medium_lbl.config(text="Waiting for phone...", fg=self.C_TEXT_MUTED)

        # Jitter & Bitrate
        jit_text = f"Jitter: {r.estimated_jitter_ms:.1f} ms" if is_streaming else "Jitter: --"
        bit_text = f"Bitrate: {r.bitrate_kbps:.0f} kbps" if is_streaming else "Bitrate: 768 kbps"
        self.t_jitter_bitrate_lbl.config(text=f"{jit_text} • {bit_text}")

        # Loss & Uptime
        loss_pct = (r.packets_lost / max(1, r.packets_received + r.packets_lost)) * 100.0 if r.packets_received > 0 else 0.0
        uptime_text = "00:00:00"
        if is_streaming and r.stream_start_time > 0:
            elapsed = int(now - r.stream_start_time)
            hrs = elapsed // 3600
            mins = (elapsed % 3600) // 60
            secs = elapsed % 60
            uptime_text = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        self.t_loss_uptime_lbl.config(text=f"Loss: {r.packets_lost} pkts ({loss_pct:.1f}%) • {uptime_text}")

        # Schedule next tick
        self.schedule_next_tick()


# ==============================================================================
# CLI FULL SCREEN DASHBOARD (HEADLESS / CONSOLE FALLBACK)
# ==============================================================================
def render_full_screen(receiver, target_device_name, active_notice=""):
    reset_cursor_to_top()
    r = receiver
    now = time.time()
    cols = shutil.get_terminal_size((80, 24)).columns
    max_w = min(cols, 76)

    def print_line(s=""):
        sys.stdout.write(fit_line_width(s, max_w) + "\n")

    print_line(f"{Colors.CYAN}{'═' * max_w}{Colors.RESET}")
    print_line(f"{Colors.BOLD}{Colors.CYAN} PhoneMic Studio Receiver v{VERSION} (CLI Dashboard){Colors.RESET}")
    print_line(f"{Colors.CYAN}{'═' * max_w}{Colors.RESET}")

    is_streaming = (r.last_packet_time > 0 and (now - r.last_packet_time) < 1.5)
    if is_streaming:
        status_text = f"{Colors.GREEN}{Colors.BOLD}● STREAMING LIVE ({r.transport}){Colors.RESET}"
    elif r.paused:
        status_text = f"{Colors.YELLOW}{Colors.BOLD}⏸ MUTED (Sync active with phone){Colors.RESET}"
    else:
        status_text = f"{Colors.DIM}○ STANDBY (Listening on UDP/TCP port {r.port}){Colors.RESET}"
    print_line(f" Status:        {status_text}")

    classified = get_classified_ips()
    wifi_ip = next((ip for cat, ip in classified if cat == "Wi-Fi / LAN"), "None")
    usb_ip = next((ip for cat, ip in classified if cat == "USB Tether"), "None")
    print_line(f" Wi-Fi IP:      {Colors.BOLD}{Colors.CYAN}{wifi_ip}{Colors.RESET} (Port {r.port})")
    print_line(f" USB Tether IP: {Colors.BOLD}{Colors.GREEN}{usb_ip}{Colors.RESET} (Port {r.port})")
    print_line(f" Main Output:   {Colors.BOLD}{target_device_name}{Colors.RESET}")

    p = r.processor
    nc_str = f"{Colors.GREEN}[ON {int(p.noise_cancel_amount*100)}%]{Colors.RESET}" if p.smart_noise_cancel else f"{Colors.DIM}[OFF]{Colors.RESET}"
    eq_str = f"L:{p.eq_low_gain_db:+.1f}dB M:{p.eq_mid_gain_db:+.1f}dB H:{p.eq_high_gain_db:+.1f}dB"
    ps_str = f"{p.pitch_shift_semitones:+.1f}st" if abs(p.pitch_shift_semitones) > 0.1 else "0.0st (Natural)"
    print_line(f" Studio DSP:    NoiseCanceling: {nc_str} | EQ: {eq_str} | Pitch: {ps_str}")

    peak = r.latest_peak
    db = r.latest_db
    meter_len = 28
    filled = int(meter_len * min(1.0, max(0.0, peak))) if is_streaming else 0
    meter_bar = (
        Colors.GREEN + '█' * min(filled, int(meter_len * 0.7)) +
        Colors.YELLOW + '█' * max(0, min(filled - int(meter_len * 0.7), int(meter_len * 0.2))) +
        Colors.RED + '█' * max(0, filled - int(meter_len * 0.9)) +
        Colors.DIM + '░' * (meter_len - filled) +
        Colors.RESET
    )
    db_text = f"{db:+.1f} dB" if is_streaming else "-80.0 dB"
    print_line(f" Audio Level:   [{meter_bar}] {Colors.BOLD}{db_text}{Colors.RESET}")

    if is_streaming and r.client_addr:
        print_line(f" Client:        {r.client_addr[0]}:{r.client_addr[1]} | Jitter: ~{r.estimated_jitter_ms:.1f}ms")
    else:
        print_line(f" Client:        Waiting for connection...")

    print_line(f"{Colors.CYAN}{'─' * max_w}{Colors.RESET}")
    print_line(f" Commands: [M]ute | [P]itch | [E]Q | [N]oiseCanceler | [Q]uit")
    if active_notice:
        print_line(f" {Colors.MAGENTA}Notice: {active_notice}{Colors.RESET}")
    print_line(f"{Colors.CYAN}{'═' * max_w}{Colors.RESET}")
    sys.stdout.flush()


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    force_cli = "--cli" in sys.argv or "-c" in sys.argv or not TKINTER_AVAILABLE

    # Ensure dependencies verified or prompt
    if not is_already_verified() and not getattr(sys, 'frozen', False):
        if not run_interactive_dependency_fixer():
            print(f"{Colors.YELLOW}[!] Proceeding in basic fallback mode.{Colors.RESET}")

    cable_dev, default_out, all_devices = find_audio_devices()
    target_idx = cable_dev[0] if cable_dev else (default_out[0] if default_out else None)
    monitor_idx = default_out[0] if default_out else None

    receiver = PhoneMicReceiver(
        port=DEFAULT_PORT,
        target_device=target_idx,
        monitor_device=monitor_idx
    )
    receiver.start()

    if not force_cli and TKINTER_AVAILABLE:
        try:
            root = tk.Tk()
            gui = PhoneMicGui(root, receiver)

            def on_closing():
                receiver.stop()
                root.destroy()

            root.protocol("WM_DELETE_WINDOW", on_closing)
            root.mainloop()
            return
        except Exception as e:
            print(f"{Colors.YELLOW}[!] Tkinter GUI initialization failed ({e}). Falling back to CLI.{Colors.RESET}")

    # CLI Terminal Mode
    init_windows_console()
    hide_cursor()
    target_name = cable_dev[1].get('name') if cable_dev else (default_out[1].get('name') if default_out else "Default Output")

    try:
        while receiver.running:
            render_full_screen(receiver, target_name)
            time.sleep(0.08)
    except KeyboardInterrupt:
        pass
    finally:
        show_cursor()
        receiver.stop()
        print(f"\n{Colors.GREEN}[✓] PhoneMic Receiver stopped.{Colors.RESET}")

if __name__ == "__main__":
    main()
