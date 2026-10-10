#!/usr/bin/env python3
"""
================================================================================
PhoneMic Windows Receiver v0.6.3 (Ultra Low Latency Microphone Engine)
================================================================================
Receives real-time 48kHz 16-bit PCM audio streamed from the PhoneMic Android app
over UDP or TCP, applies low-latency DSP (gain, noise gate, limiter, stereo conversion),
and outputs directly into VB-Audio Virtual Cable or system audio device.

Features:
- Flicker-free, stable console dashboard (zero infinite scrolling or newline overflow)
- Uses native Windows Console API (SetConsoleCursorPosition) for rock-solid in-place refresh
- Handles all keystrokes in-place with dedicated notification display
- Single-socket UDP architecture for 100% reliable discovery + audio packet streaming
- Full audio pipeline with real-time VU meter, Gain, Monitor, Pause, and WAV recording
- Detailed telemetry: Peak dB, Bitrate (kbps), Packet Rate (pps), Dropped Packets, Uptime, Recording stats
================================================================================
"""

import os
import sys
import time
import socket
import struct
import threading
import queue
import math
import wave
import shutil
import re
import webbrowser
import platform
from datetime import datetime

try:
    import numpy as np
except ImportError:
    np = None

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

# ==============================================================================
# CONFIGURATION CONSTANTS
# ==============================================================================
VERSION = "0.6.3"
DEFAULT_PORT = 5001
HOST = "0.0.0.0"

AUDIO_RATE = 48000
AUDIO_CHANNELS = 1              # Mono input from Android PhoneMic
OUTPUT_CHANNELS = 2             # Stereo output for Windows Virtual Cable / Speakers
SAMPLE_WIDTH = 2                # 16-bit PCM (2 bytes)
FRAMES_PER_PACKET = 480         # 10ms of audio per packet at 48kHz
PCM_BYTES_PER_PACKET = FRAMES_PER_PACKET * AUDIO_CHANNELS * SAMPLE_WIDTH # 960 bytes

UDP_MAGIC = b"PM01"
UDP_HEADER_SIZE = 8
DISCOVERY_QUERY = b"PMD0"
DISCOVERY_REPLY = b"PMA1"

# Remote Control Commands (Bidirectional Sync with Android PhoneMic App)
CMD_PAUSE = b"PMP1"   # Receiver requests Android app to pause mic capture
CMD_RESUME = b"PMR1"  # Receiver requests Android app to resume mic capture

TARGET_DEVICE_NAME = "CABLE Input"
VB_CABLE_PAGE = "https://vb-audio.com/Cable/"
VB_CABLE_DIRECT_ZIP = "https://download.vb-audio.com/Download_VIP/VBCABLE_Driver_Pack43.zip"

DEFAULT_GAIN = 1.0

def get_app_dir():
    """Returns the directory of the script or compiled PyInstaller executable."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
NOISE_GATE_THRESHOLD_DB = -55.0
LIMITER_CEILING = 0.98


# ==============================================================================
# CONSOLE FORMATTING & WINDOWS SCREEN MANAGEMENT
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
    """Calculates visible character count ignoring ANSI color escape codes."""
    return len(ANSI_REGEX.sub('', s))

def fit_line_width(text, max_cols):
    """Pads or truncates text to fit exactly within max_cols without triggering terminal line-wrap."""
    vlen = visible_length(text)
    if vlen < max_cols:
        return text + (' ' * (max_cols - vlen))
    elif vlen > max_cols:
        clean = ANSI_REGEX.sub('', text)
        return clean[:max(0, max_cols - 3)] + '...'
    return text


# Windows Console API handle and cursor control
kernel32 = None
stdout_handle = None

def init_windows_console():
    """Initializes Windows Console virtual terminal and cursor management."""
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
    """Hides terminal cursor to eliminate blinking/jitter during dashboard updates."""
    # Native Windows Console API
    if os.name == 'nt' and kernel32 is not None and stdout_handle is not None:
        try:
            import ctypes
            class CONSOLE_CURSOR_INFO(ctypes.Structure):
                _fields_ = [('dwSize', ctypes.c_ulong), ('bVisible', ctypes.c_bool)]
            info = CONSOLE_CURSOR_INFO(dwSize=25, bVisible=False)
            kernel32.SetConsoleCursorInfo(stdout_handle, ctypes.byref(info))
        except Exception:
            pass
    # ANSI escape code to hide cursor
    sys.stdout.write('\033[?25l')
    sys.stdout.flush()


def show_cursor():
    """Restores terminal cursor visibility upon exit."""
    # Native Windows Console API
    if os.name == 'nt' and kernel32 is not None and stdout_handle is not None:
        try:
            import ctypes
            class CONSOLE_CURSOR_INFO(ctypes.Structure):
                _fields_ = [('dwSize', ctypes.c_ulong), ('bVisible', ctypes.c_bool)]
            info = CONSOLE_CURSOR_INFO(dwSize=25, bVisible=True)
            kernel32.SetConsoleCursorInfo(stdout_handle, ctypes.byref(info))
        except Exception:
            pass
    # ANSI escape code to restore cursor
    sys.stdout.write('\033[?25h')
    sys.stdout.flush()


def reset_cursor_to_top():
    """
    Moves cursor to (0, 0) of the console buffer.
    Uses native Windows Console API when available for 100% reliable, flicker-free redraws
    without causing terminal scrolling or infinite newlines.
    """
    if os.name == 'nt' and kernel32 is not None and stdout_handle is not None:
        try:
            import ctypes
            # COORD struct packed as short x, short y (0, 0)
            kernel32.SetConsoleCursorPosition(stdout_handle, ctypes.c_ulong(0))
            return
        except Exception:
            pass
    # Fallback to ANSI cursor home code
    sys.stdout.write('\033[H')


def get_local_ips():
    """Finds all valid local IPv4 addresses (Wi-Fi, USB RNDIS, Ethernet)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


# ==============================================================================
# AUDIO DEVICE DETECTION
# ==============================================================================
def find_audio_devices():
    """Finds VB-Audio Cable Input and default output device."""
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


def run_preflight_check(skip_prompt=False):
    """
    Validates audio output targets, checks for VB-Audio Virtual Cable,
    and prompts user with direct download options if VB-CABLE is missing.
    """
    cable_dev, default_out, all_outputs = find_audio_devices()
    if cable_dev:
        return cable_dev, default_out, True

    if not skip_prompt:
        cols, _ = shutil.get_terminal_size(fallback=(80, 24))
        w = min(max(cols - 1, 60), 78)
        print(f"\n{Colors.CYAN}{'═' * w}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW} [!] Audio Output Notice: VB-Audio Virtual Cable not detected{Colors.RESET}")
        print(f"{Colors.CYAN}{'═' * w}{Colors.RESET}")
        print(f" PhoneMic will route audio to your default playback device:")
        if default_out:
            print(f"  -> {Colors.GREEN}{default_out[1].get('name', 'Default Speakers')}{Colors.RESET}")
        print(f"\n To use PhoneMic as a microphone in {Colors.BOLD}Discord, OBS, Zoom, or games{Colors.RESET},")
        print(f" install the free VB-CABLE driver (no PC reboot required):")
        print(f"  • Setup Website: {Colors.CYAN}{VB_CABLE_PAGE}{Colors.RESET}")
        print(f"  • Direct Zip:    {Colors.CYAN}{VB_CABLE_DIRECT_ZIP}{Colors.RESET}")
        print(f"{Colors.CYAN}{'─' * w}{Colors.RESET}")

        try:
            choice = input(f"{Colors.YELLOW} Open VB-CABLE download page in browser? [y/N] (or press Enter to continue): {Colors.RESET}").strip().lower()
            if choice in ('y', 'yes', '1'):
                webbrowser.open(VB_CABLE_PAGE)
                print(f" {Colors.GREEN}[✓] Opened download page in your default browser.{Colors.RESET}\n")
                time.sleep(1.0)
        except (KeyboardInterrupt, EOFError):
            pass

    return cable_dev, default_out, False


def run_diagnostics_suite():
    """Performs a comprehensive dependency, network, and audio diagnostic check."""
    init_windows_console()
    print(f"{Colors.CYAN}{'=' * 75}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}       PhoneMic Windows Receiver - System & Audio Diagnostics{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 75}{Colors.RESET}\n")

    # 1. Runtime Environment
    print("[*] Runtime Environment:")
    if getattr(sys, 'frozen', False):
        print(f"    {Colors.GREEN}[✓] Running as standalone executable ({sys.executable}){Colors.RESET}")
    else:
        print(f"    {Colors.GREEN}[✓] Python {sys.version.split()[0]} ({platform.architecture()[0]}){Colors.RESET}")

    # 2. Audio Engine Libraries
    print("\n[*] Audio Engine (PortAudio / SoundDevice / NumPy):")
    if sd is not None:
        try:
            ver = sd.__version__
            print(f"    {Colors.GREEN}[✓] SoundDevice {ver} active{Colors.RESET}")
        except Exception:
            print(f"    {Colors.GREEN}[✓] SoundDevice active{Colors.RESET}")
    else:
        print(f"    {Colors.RED}[✗] SoundDevice library missing! Run: pip install sounddevice{Colors.RESET}")

    if np is not None:
        print(f"    {Colors.GREEN}[✓] NumPy {np.__version__} active{Colors.RESET}")
    else:
        print(f"    {Colors.RED}[✗] NumPy library missing! Run: pip install numpy{Colors.RESET}")

    # 3. Audio Devices & VB-CABLE
    print("\n[*] Audio Output Endpoints:")
    cable_dev, default_out, all_outputs = find_audio_devices()
    for idx, dev in all_outputs:
        name = dev.get('name', 'Unknown')
        is_cable = TARGET_DEVICE_NAME.lower() in name.lower()
        is_default = default_out and default_out[0] == idx
        tag = ""
        if is_cable:
            tag += f" {Colors.GREEN}[TARGET: VB-CABLE]{Colors.RESET}"
        if is_default:
            tag += f" {Colors.CYAN}[DEFAULT OUTPUT]{Colors.RESET}"
        print(f"    [{idx:2d}] {name}{tag}")

    if cable_dev:
        print(f"\n    {Colors.GREEN}[✓] VB-Audio Virtual Cable is installed and ready for Discord/OBS!{Colors.RESET}")
    else:
        print(f"\n    {Colors.YELLOW}[!] VB-Audio Virtual Cable not detected.{Colors.RESET}")
        print(f"        Download free from: {VB_CABLE_PAGE}")

    # 4. Network Interfaces
    print("\n[*] Network Interfaces & Local IP Addresses:")
    ips = get_local_ips()
    for ip in ips:
        print(f"    -> {Colors.BOLD}{Colors.GREEN}{ip}{Colors.RESET} (Port {DEFAULT_PORT})")

    print(f"\n{Colors.CYAN}{'=' * 75}{Colors.RESET}\n")


# ==============================================================================
# AUDIO DSP PIPELINE
# ==============================================================================
class AudioProcessor:
    def __init__(self, sample_rate=AUDIO_RATE):
        self.sample_rate = sample_rate
        self.gain = DEFAULT_GAIN
        self.gate_threshold_db = NOISE_GATE_THRESHOLD_DB
        self.gate_floor = 0.02

    def process(self, pcm_bytes):
        """
        Takes raw 16-bit PCM bytes (mono, 48kHz, 960 bytes).
        Returns:
            stereo_block: float32 numpy array shape (N, 2)
            peak: float (0.0 to 1.0)
            db: float in dB (-80 to 0)
        """
        if np is not None:
            # High performance vectorized NumPy path
            int16_samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            if len(int16_samples) == 0:
                return np.zeros((0, 2), dtype=np.float32), 0.0, -80.0

            # Convert to float32 [-1.0 .. 1.0]
            float_samples = (int16_samples / 32768.0).astype(np.float32)

            # 1. Gain boost
            if abs(self.gain - 1.0) > 0.01:
                float_samples = float_samples * self.gain

            # 2. Peak & dB calculation
            peak = float(np.max(np.abs(float_samples)))
            db = 20.0 * math.log10(peak) if peak > 1e-4 else -80.0

            # 3. Noise Gate (only if audio is in extreme background noise level)
            if db < self.gate_threshold_db:
                float_samples = float_samples * self.gate_floor

            # 4. Brickwall limiter
            np.clip(float_samples, -LIMITER_CEILING, LIMITER_CEILING, out=float_samples)

            # 5. Expand mono to stereo for Virtual Cable / Speakers
            stereo_block = np.column_stack((float_samples, float_samples))
            return stereo_block, peak, db
        else:
            # Fallback pure python path if numpy is missing
            count = len(pcm_bytes) // 2
            if count == 0:
                return None, 0.0, -80.0
            fmt = f"<{count}h"
            samples = struct.unpack(fmt, pcm_bytes)
            max_abs = max(abs(s) for s in samples) if samples else 0
            peak = max_abs / 32768.0
            db = 20.0 * math.log10(peak) if peak > 1e-4 else -80.0
            return None, peak, db


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
        self.audio_queue = queue.Queue(maxsize=12)

        # Statistics & Real-time Metrics
        self.transport = "UDP"
        self.packets_received = 0
        self.bytes_received = 0
        self.packets_lost = 0
        self.last_seq = -1
        self.client_addr = None
        self.stream_start_time = 0
        self.last_packet_time = 0
        self.latest_peak = 0.0
        self.latest_db = -80.0

        # Rate calculations (updated every 1s)
        self.bitrate_kbps = 0.0
        self.packets_per_sec = 0.0
        self._rate_calc_time = time.time()
        self._last_calc_bytes = 0
        self._last_calc_packets = 0

        # WAV Recording
        self.wav_file = None
        self.wav_filename = ""
        self.record_start_time = 0
        self.record_bytes_written = 0

        # Streams
        self.audio_stream = None
        self.monitor_stream = None
        self.cable_detected = False

        # Sockets
        self.udp_socket = None
        self.tcp_server = None
        self.tcp_client = None

    def start(self):
        self.running = True

        # Open Primary Audio Output (Virtual Cable / Speaker)
        if sd is not None:
            try:
                self.audio_stream = sd.OutputStream(
                    samplerate=AUDIO_RATE,
                    channels=OUTPUT_CHANNELS,
                    dtype='float32',
                    device=self.target_device_idx,
                    latency='low',
                    blocksize=FRAMES_PER_PACKET
                )
                self.audio_stream.start()
            except Exception as e:
                try:
                    self.audio_stream = sd.OutputStream(
                        samplerate=AUDIO_RATE,
                        channels=OUTPUT_CHANNELS,
                        dtype='float32',
                        latency='low',
                        blocksize=FRAMES_PER_PACKET
                    )
                    self.audio_stream.start()
                except Exception:
                    self.audio_stream = None

            # Start Output Audio playback thread
            self.playback_thread = threading.Thread(target=self._playback_loop, name="AudioPlayback", daemon=True)
            self.playback_thread.start()

        # Start single UDP listener thread (Handles discovery query + audio streaming without port conflicts)
        self.udp_thread = threading.Thread(target=self._udp_listener_loop, name="UDPListener", daemon=True)
        self.udp_thread.start()

        # Start TCP listener thread (fallback)
        self.tcp_thread = threading.Thread(target=self._tcp_listener_loop, name="TCPListener", daemon=True)
        self.tcp_thread.start()

    def _playback_loop(self):
        """Pulls processed audio blocks from queue and outputs to sound card."""
        silence = np.zeros((FRAMES_PER_PACKET, OUTPUT_CHANNELS), dtype=np.float32) if np is not None else None

        while self.running:
            try:
                audio_block = self.audio_queue.get(timeout=0.04)

                # If paused, feed silence to output and do not record
                if self.paused and silence is not None:
                    audio_block = silence

                # Write to primary output device (Virtual Cable / Speakers)
                if self.audio_stream and self.audio_stream.active:
                    self.audio_stream.write(audio_block)

                # Write to monitor headphones if enabled
                if self.monitoring and self.monitor_stream and self.monitor_stream.active:
                    self.monitor_stream.write(audio_block)

                # Write to WAV if recording (only when unmuted)
                if self.recording and self.wav_file and not self.paused:
                    try:
                        pcm_data = (audio_block * 32767.0).astype(np.int16).tobytes()
                        self.wav_file.writeframes(pcm_data)
                        self.record_bytes_written += len(pcm_data)
                    except Exception:
                        pass

            except queue.Empty:
                if self.audio_stream and self.audio_stream.active and silence is not None:
                    try:
                        self.audio_stream.write(silence)
                    except Exception:
                        pass
            except Exception:
                pass

    def _udp_listener_loop(self):
        """
        Single dedicated UDP socket on port 5001.
        Handles both PhoneMic auto-discovery (PMD0 -> PMA1) and audio stream (PM01 packets).
        This guarantees that the phone's auto-detect and direct IP audio stream work seamlessly
        without any port collision or OS-level socket stealing.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        except Exception:
            pass

        try:
            sock.bind((HOST, self.port))
            sock.settimeout(0.5)
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

                # 1. Auto-Discovery Query from Android Phone
                if buffer[:4] == DISCOVERY_QUERY:
                    reply = DISCOVERY_REPLY + f" {VERSION}".encode('ascii')
                    sock.sendto(reply, addr)
                    continue

                # 2. Audio Stream Packet from Android Phone
                # Packet format: 'P','M','0','1' + 4-byte big-endian seq + 16-bit PCM payload
                if buffer[:4] == UDP_MAGIC and length >= UDP_HEADER_SIZE:
                    self.transport = "UDP"
                    self.client_addr = addr
                    seq = struct.unpack(">I", buffer[4:8])[0]

                    # Packet loss tracking
                    if self.last_seq != -1:
                        diff = (seq - self.last_seq) & 0xFFFFFFFF
                        if 1 < diff < 5000:
                            self.packets_lost += (diff - 1)
                    self.last_seq = seq

                    pcm_bytes = bytes(buffer[8:length])
                    self._enqueue_pcm(pcm_bytes)

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
        """Fallback TCP listener."""
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

                while self.running:
                    data = conn.recv(PCM_BYTES_PER_PACKET)
                    if not data:
                        break
                    self._enqueue_pcm(data)
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
        now = time.time()
        if self.stream_start_time == 0:
            self.stream_start_time = now
        self.last_packet_time = now

        self.packets_received += 1
        self.bytes_received += len(pcm_bytes)

        # Update rates once per second
        time_diff = now - self._rate_calc_time
        if time_diff >= 1.0:
            bytes_diff = self.bytes_received - self._last_calc_bytes
            packets_diff = self.packets_received - self._last_calc_packets
            self.bitrate_kbps = (bytes_diff * 8.0) / (time_diff * 1000.0)
            self.packets_per_sec = packets_diff / time_diff
            self._rate_calc_time = now
            self._last_calc_bytes = self.bytes_received
            self._last_calc_packets = self.packets_received

        # Process through DSP
        stereo_block, peak, db = self.processor.process(pcm_bytes)

        self.latest_peak = peak
        self.latest_db = db

        if stereo_block is not None:
            # Drop oldest block if queue gets overloaded to maintain lowest latency
            if self.audio_queue.full():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    pass

            try:
                self.audio_queue.put_nowait(stereo_block)
            except queue.Full:
                pass

    def send_control_to_client(self, cmd_bytes):
        """
        Sends bidirectional control commands (e.g. CMD_PAUSE or CMD_RESUME)
        to the connected Android PhoneMic app over UDP or TCP.
        """
        sent = False
        # 1. Send via active UDP socket to client address
        if self.udp_socket and self.client_addr and self.transport == "UDP":
            try:
                self.udp_socket.sendto(cmd_bytes, self.client_addr)
                sent = True
            except Exception:
                pass
        # 2. Send via active TCP socket
        if self.tcp_client and self.transport == "TCP":
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
        if sd is None:
            return False, "sounddevice library not available"

        self.monitoring = not self.monitoring
        if self.monitoring:
            try:
                self.monitor_stream = sd.OutputStream(
                    samplerate=AUDIO_RATE,
                    channels=OUTPUT_CHANNELS,
                    dtype='float32',
                    device=self.monitor_device_idx,
                    latency='low',
                    blocksize=FRAMES_PER_PACKET
                )
                self.monitor_stream.start()
                return True, "OK"
            except Exception as e:
                self.monitoring = False
                return False, f"Failed: {e}"
        else:
            if self.monitor_stream:
                try:
                    self.monitor_stream.stop()
                    self.monitor_stream.close()
                except Exception:
                    pass
                self.monitor_stream = None
            return False, "OK"

    def toggle_recording(self):
        self.recording = not self.recording
        if self.recording:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"PhoneMic_{timestamp}.wav"
            self.wav_filename = os.path.join(get_app_dir(), filename)
            self.record_start_time = time.time()
            self.record_bytes_written = 0
            try:
                self.wav_file = wave.open(self.wav_filename, 'wb')
                self.wav_file.setnchannels(OUTPUT_CHANNELS)
                self.wav_file.setsampwidth(SAMPLE_WIDTH)
                self.wav_file.setframerate(AUDIO_RATE)
                return True, filename
            except Exception as e:
                self.recording = False
                return False, f"Cannot open WAV: {e}"
        else:
            filename = os.path.basename(self.wav_filename)
            if self.wav_file:
                try:
                    self.wav_file.close()
                except Exception:
                    pass
                self.wav_file = None
            return False, filename

    def adjust_gain(self, delta):
        new_gain = round(self.processor.gain + delta, 1)
        self.processor.gain = max(0.5, min(5.0, new_gain))
        return self.processor.gain

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
# TERMINAL UI & INTERACTIVE DASHBOARD
# ==============================================================================
def build_vu_meter(db, length=16):
    """Creates a clean ASCII VU meter that renders stably across terminals."""
    clamped = max(-60.0, min(0.0, db))
    fraction = (clamped + 60.0) / 60.0
    active_count = int(round(fraction * length))

    chars = []
    for i in range(length):
        ratio = (i + 1) / length
        if i < active_count:
            if ratio < 0.65:
                chars.append(f"{Colors.GREEN}█{Colors.RESET}")
            elif ratio < 0.85:
                chars.append(f"{Colors.YELLOW}█{Colors.RESET}")
            else:
                chars.append(f"{Colors.RED}█{Colors.RESET}")
        else:
            chars.append(f"{Colors.DIM}░{Colors.RESET}")
    return "".join(chars)


def format_duration(seconds):
    """Formats seconds into MM:SS format."""
    secs = int(max(0, seconds))
    m = secs // 60
    s = secs % 60
    return f"{m:02d}:{s:02d}"


def render_full_screen(receiver, target_dev_name, notification=""):
    """
    Renders the entire dashboard in-place using absolute cursor positioning.
    This guarantees zero scrolling and zero printing overflow regardless of terminal width.
    """
    cols, _ = shutil.get_terminal_size(fallback=(80, 24))
    usable_width = max(60, min(cols - 1, 95))

    now = time.time()
    connected = (now - receiver.last_packet_time) < 1.5 and receiver.packets_received > 0

    ips = get_local_ips()
    ip_str = ", ".join(ips) if ips else "127.0.0.1"

    lines = []
    # Header
    lines.append(f"{Colors.CYAN}{Colors.BOLD}╔═ PhoneMic Windows Receiver v{VERSION} ═══════════════════════════════════════╗{Colors.RESET}")
    lines.append(f"{Colors.DIM}║ Listening on 0.0.0.0:{receiver.port} (UDP/TCP) | 48kHz 16-bit Stereo Output      ║{Colors.RESET}")
    lines.append(f"{Colors.CYAN}╚═══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")

    # System Status Block
    lines.append(f"Host IP:     {Colors.GREEN}{ip_str}{Colors.RESET}")
    lines.append(f"Target Mic:  {Colors.YELLOW}{target_dev_name}{Colors.RESET}")

    # Separator
    lines.append(f"{Colors.CYAN}{'─' * min(usable_width, 79)}{Colors.RESET}")

    if connected:
        db = receiver.latest_db
        vu = build_vu_meter(db, length=16)
        client_ip = f"{receiver.client_addr[0]}" if receiver.client_addr else "Connected"
        mb = receiver.bytes_received / (1024.0 * 1024.0)

        # Status badges
        if receiver.paused:
            status_tag = f"{Colors.YELLOW}[⏸ MUTED / PAUSED]{Colors.RESET}"
        else:
            status_tag = f"{Colors.GREEN}[● LIVE STREAMING]{Colors.RESET}"

        mon_tag = f" {Colors.CYAN}[MONITOR ACTIVE]{Colors.RESET}" if receiver.monitoring else ""
        uptime = format_duration(now - receiver.stream_start_time)

        lines.append(f"State:       {status_tag}{mon_tag} from {Colors.BOLD}{client_ip}{Colors.RESET} ({receiver.transport})")
        lines.append(f"Audio Level: [{vu}] {db:5.1f} dB  |  Gain: {Colors.BOLD}{receiver.processor.gain:.1f}x{Colors.RESET}")

        kbps_str = f"{receiver.bitrate_kbps:5.1f} kbps" if receiver.bitrate_kbps > 0 else "768.0 kbps"
        pps_str = f"{receiver.packets_per_sec:4.0f} pps" if receiver.packets_per_sec > 0 else "100 pps"
        loss_color = Colors.RED if receiver.packets_lost > 0 else Colors.GREEN

        lines.append(f"Network:     {kbps_str} ({pps_str})  |  Packets: {receiver.packets_received}  |  Loss: {loss_color}{receiver.packets_lost}{Colors.RESET}")
        lines.append(f"Throughput:  {mb:.2f} MB received  |  Uptime: {uptime}")

        # Recording Section
        if receiver.recording:
            rec_dur = format_duration(now - receiver.record_start_time)
            rec_mb = receiver.record_bytes_written / (1024.0 * 1024.0)
            lines.append(f"Recording:   {Colors.RED}● ACTIVE{Colors.RESET} - {receiver.wav_filename} ({rec_dur}, {rec_mb:.2f} MB)")
        else:
            lines.append(f"Recording:   {Colors.DIM}○ Inactive (Press [R] to record lossless WAV){Colors.RESET}")

    else:
        lines.append(f"State:       {Colors.DIM}○ WAITING FOR AUDIO STREAM...{Colors.RESET}")
        lines.append(f"Instruction: Open PhoneMic on your Android phone and tap 'START STREAM'")
        lines.append(f"Audio Level: [{build_vu_meter(-60.0, length=16)}] -60.0 dB  |  Gain: {receiver.processor.gain:.1f}x")
        lines.append(f"Network:     0.0 kbps (0 pps)  |  Loss: 0")
        lines.append(f"Throughput:  0.00 MB received  |  Uptime: 00:00")
        lines.append(f"Recording:   {Colors.DIM}○ Inactive (Press [R] to record){Colors.RESET}")

    # Separator
    lines.append(f"{Colors.CYAN}{'─' * min(usable_width, 79)}{Colors.RESET}")

    # Hotkey instructions
    if getattr(receiver, 'cable_detected', False):
        lines.append(f"Controls:    [P] Mute/Live   [R] Record WAV   [M] Monitor   [+] / [-] Gain   [Q] Quit")
    else:
        lines.append(f"Controls:    [P] Mute/Live   [R] Record WAV   [M] Monitor   [O] Get VB-CABLE   [Q] Quit")

    # Notification Line (Reserved fixed row so no shifting occurs)
    if notification:
        lines.append(f"Notice:      {notification}")
    else:
        lines.append(f"Notice:      {Colors.DIM}Ready{Colors.RESET}")

    # Reset cursor to top-left and write each line padded to terminal width
    reset_cursor_to_top()
    output_buffer = []
    for line in lines:
        padded = fit_line_width(line, usable_width)
        output_buffer.append(f"\033[K{padded}\n")

    sys.stdout.write("".join(output_buffer))
    sys.stdout.flush()


def main():
    if "--check" in sys.argv or "-c" in sys.argv:
        run_diagnostics_suite()
        return

    init_windows_console()

    # Clear screen once on startup
    os.system('cls' if os.name == 'nt' else 'clear')

    # 1. Pre-flight check & discover audio devices
    skip_prompt = "--quiet" in sys.argv or "--no-prompt" in sys.argv
    cable_dev, default_out, cable_ok = run_preflight_check(skip_prompt=skip_prompt)

    if cable_dev:
        target_idx, target_info = cable_dev
        target_name = f"{target_info.get('name', 'VB-CABLE')} (Virtual Cable)"
    elif default_out:
        target_idx, target_info = default_out
        target_name = f"{target_info.get('name', 'Default Speaker')} (Default Output)"
    else:
        target_idx = None
        target_name = "System Default Audio"

    monitor_idx = default_out[0] if default_out else None

    # Clear screen again after interactive pre-flight prompt
    os.system('cls' if os.name == 'nt' else 'clear')

    # 2. Start Receiver
    receiver = PhoneMicReceiver(
        port=DEFAULT_PORT,
        target_device=target_idx,
        monitor_device=monitor_idx
    )
    receiver.cable_detected = cable_ok
    receiver.start()

    notification_msg = ""
    notification_expiry = 0.0

    def set_notice(msg):
        nonlocal notification_msg, notification_expiry
        notification_msg = msg
        notification_expiry = time.time() + 4.0

    if cable_ok:
        set_notice(f"{Colors.GREEN}[STARTED]{Colors.RESET} Listening for PhoneMic Android app")
    else:
        set_notice(f"{Colors.YELLOW}[DEFAULT AUDIO]{Colors.RESET} Output to speakers. Press [O] for VB-CABLE")

    # Hide cursor to prevent cursor flashing/jitter during dashboard redraws
    hide_cursor()

    # 3. Interactive Loop
    try:
        last_draw_time = 0

        while True:
            # Check for keystrokes without blocking
            # Drain all queued keys to prevent multi-triggering
            if msvcrt and msvcrt.kbhit():
                while msvcrt.kbhit():
                    ch = msvcrt.getch()
                    try:
                        char = ch.decode('ascii', errors='ignore').lower()
                    except Exception:
                        char = ''

                    if char == 'q':
                        sys.stdout.write(f"\n{Colors.YELLOW}[*] Shutting down PhoneMic receiver...{Colors.RESET}\n")
                        sys.stdout.flush()
                        return
                    elif char == 'p':
                        is_paused = receiver.toggle_pause()
                        if is_paused:
                            set_notice(f"{Colors.YELLOW}[MUTED]{Colors.RESET} Audio muted to virtual mic")
                        else:
                            set_notice(f"{Colors.GREEN}[LIVE]{Colors.RESET} Stream unmuted and transmitting")
                    elif char == 'r':
                        is_recording, filename = receiver.toggle_recording()
                        if is_recording:
                            set_notice(f"{Colors.RED}● REC STARTED:{Colors.RESET} {filename}")
                        else:
                            set_notice(f"{Colors.GREEN}■ REC SAVED:{Colors.RESET} {filename}")
                    elif char == 'm':
                        mon_active, msg = receiver.toggle_monitor()
                        if mon_active:
                            set_notice(f"{Colors.GREEN}[MONITOR ON]{Colors.RESET} Audio routed to headphones")
                        else:
                            set_notice(f"{Colors.DIM}[MONITOR OFF]{Colors.RESET} Headphone monitor disabled")
                    elif char == 'o':
                        try:
                            webbrowser.open(VB_CABLE_PAGE)
                            set_notice(f"{Colors.GREEN}[BROWSER]{Colors.RESET} Opened VB-CABLE download page")
                        except Exception as e:
                            set_notice(f"{Colors.YELLOW}[ERROR]{Colors.RESET} Could not open browser: {e}")
                    elif char in ('+', '='):
                        gain = receiver.adjust_gain(0.5)
                        set_notice(f"{Colors.CYAN}[GAIN]{Colors.RESET} Boost set to {gain:.1f}x")
                    elif char in ('-', '_'):
                        gain = receiver.adjust_gain(-0.5)
                        set_notice(f"{Colors.CYAN}[GAIN]{Colors.RESET} Boost set to {gain:.1f}x")

            # Redraw dashboard at comfortable 10Hz (every 100ms)
            now = time.time()
            if now - last_draw_time >= 0.10:
                last_draw_time = now
                active_notice = notification_msg if now < notification_expiry else ""
                render_full_screen(receiver, target_name, active_notice)

            time.sleep(0.02)

    except KeyboardInterrupt:
        sys.stdout.write(f"\n{Colors.YELLOW}[*] Stopped by user.{Colors.RESET}\n")
        sys.stdout.flush()
    finally:
        # Restore terminal cursor visibility before exiting
        show_cursor()
        receiver.stop()
        sys.stdout.write(f"{Colors.GREEN}[✓] Receiver stopped cleanly.{Colors.RESET}\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
