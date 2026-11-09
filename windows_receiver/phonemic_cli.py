#!/usr/bin/env python3
"""PhoneMic Standalone CLI Receiver.

Lightweight, high-performance, zero-GUI receiver for streaming microphone audio from one
or more phones to a PC, laptop, or Raspberry Pi.

Features:
  * Multi-device concurrent mixing with soft-knee limiter and auto-ducking.
  * Real-time audio monitoring to headphones/speakers with 'M' hotkey.
  * Interactive keybindings:
      [M] Toggle Audio Monitoring (hear yourself in headphones)
      [X] Cycle Mixing Mode (Sum & Soft Limiter <-> Auto-Duck Priority)
      [P] Toggle Mute / Pause
      [+] Gain Boost (+1 dB)
      [-] Gain Cut (-1 dB)
      [0] Reset Gain (0 dB)
      [C] Clear / Reset Packet Statistics
      [H] Show / Hide Detailed Device & Network Info
      [Q] Quit Receiver
  * Auto-detects 48 kHz (Studio), 24 kHz (Balanced), and 16 kHz (Economy) streams.
  * Responds to Android auto-discovery beacons ("Find PC").
  * Terminal live ANSI volume meters for each connected phone and master mix.
  * Detailed per-device metrics: IP, Port, Sample Rate, Bandwidth (kbps), Latency buffer,
    Packets received, Packet drops, and Duration.

Usage:
  python phonemic_cli.py [--port 5001] [--device "CABLE Input"] [--monitor-device "Headphones"] [--mix-mode sum]
"""

import argparse
import os
import socket
import struct
import sys
import threading
import time
from collections import deque

VERSION = "1.2.0"
DEFAULT_PORT = 5001
DISCOVERY_PROBE = b"PM_DISCOVER"
DISCOVERY_REPLY = b"PMA1"
FRAME_48K = 480       # 10 ms at 48 kHz
FRAME_24K = 240       # 10 ms at 24 kHz
FRAME_16K = 160       # 10 ms at 16 kHz

try:
    import numpy as np
except ImportError:
    print("Error: numpy is required for audio processing. Please run: pip install numpy", file=sys.stderr)
    sys.exit(1)

try:
    import sounddevice as sd
except Exception as e:
    sd = None
    _SD_ERR = str(e)
else:
    _SD_ERR = ""


# -----------------------------------------------------------------------------
# Cross-Platform Non-Blocking Keyboard Input
# -----------------------------------------------------------------------------
class KeyPoller:
    def __init__(self):
        self.is_windows = os.name == "nt"
        if not self.is_windows:
            import termios
            import tty
            self.termios = termios
            self.tty = tty
            self.old_settings = None

    def __enter__(self):
        if not self.is_windows and sys.stdin.isatty():
            try:
                self.old_settings = self.termios.tcgetattr(sys.stdin)
                self.tty.setcbreak(sys.stdin.fileno())
            except Exception:
                pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.is_windows and self.old_settings and sys.stdin.isatty():
            try:
                self.termios.tcsetattr(sys.stdin, self.termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass

    def poll(self):
        """Returns uppercase character if pressed, None otherwise."""
        if self.is_windows:
            import msvcrt
            if msvcrt.kbhit():
                try:
                    ch = msvcrt.getch()
                    if ch in (b"\x00", b"\xe0"):  # Special keys
                        msvcrt.getch()
                        return None
                    return ch.decode("latin1", errors="ignore").upper()
                except Exception:
                    return None
            return None
        else:
            import select
            if sys.stdin.isatty():
                try:
                    dr, _, _ = select.select([sys.stdin], [], [], 0)
                    if dr:
                        ch = sys.stdin.read(1)
                        return ch.upper()
                except Exception:
                    return None
            return None


# -----------------------------------------------------------------------------
# Integer Resamplers (24k -> 48k is 2x, 16k -> 48k is 3x)
# -----------------------------------------------------------------------------
def upsample_2x(x: np.ndarray) -> np.ndarray:
    """Upsample 24 kHz float32 samples to 48 kHz using linear interpolation."""
    n = len(x)
    out = np.empty(n * 2, dtype=np.float32)
    out[0::2] = x
    x_next = np.append(x[1:], x[-1])
    out[1::2] = (x + x_next) * 0.5
    return out


def upsample_3x(x: np.ndarray) -> np.ndarray:
    """Upsample 16 kHz float32 samples to 48 kHz using linear interpolation."""
    n = len(x)
    out = np.empty(n * 3, dtype=np.float32)
    x_next = np.append(x[1:], x[-1])
    out[0::3] = x
    out[1::3] = x * (2.0 / 3.0) + x_next * (1.0 / 3.0)
    out[2::3] = x * (1.0 / 3.0) + x_next * (2.0 / 3.0)
    return out


# -----------------------------------------------------------------------------
# Per-Client Stream Tracking & Metrics
# -----------------------------------------------------------------------------
class ClientStream:
    def __init__(self, addr, sample_rate=48000, target_packets=3):
        self.addr = addr
        self.ip = addr[0]
        self.port = addr[1]
        self.sample_rate = sample_rate
        self.queue = deque(maxlen=30)
        self.target_packets = target_packets
        self.connected_at = time.monotonic()
        self.last_seen = time.monotonic()
        self.packet_count = 0
        self.bytes_count = 0
        self.last_seq = -1
        self.lost_packets = 0
        self.current_peak = 0.0
        self.current_db = -60.0
        self.buffering = True

        # Bandwidth calculation (sliding 1-sec window)
        self.rate_bytes = 0
        self.last_rate_calc = time.monotonic()
        self.kbps = 0.0

    def push(self, pcm_bytes: bytes, sample_rate: int, seq: int = -1):
        now = time.monotonic()
        self.last_seen = now
        self.packet_count += 1
        nbytes = len(pcm_bytes)
        self.bytes_count += nbytes
        self.rate_bytes += nbytes
        self.sample_rate = sample_rate

        # Sequence gap check
        if seq >= 0 and self.last_seq >= 0:
            diff = (seq - self.last_seq) & 0xFFFF
            if diff > 1 and diff < 1000:
                self.lost_packets += (diff - 1)
        if seq >= 0:
            self.last_seq = seq

        # Calculate bit-rate
        dt = now - self.last_rate_calc
        if dt >= 1.0:
            self.kbps = (self.rate_bytes * 8.0) / (dt * 1000.0)
            self.rate_bytes = 0
            self.last_rate_calc = now

        self.queue.append(pcm_bytes)
        if self.buffering and len(self.queue) >= self.target_packets:
            self.buffering = False

    def pop_48k(self) -> np.ndarray:
        if self.buffering:
            return np.zeros(FRAME_48K, dtype=np.float32)
        if not self.queue:
            self.buffering = True
            self.current_peak = 0.0
            self.current_db = -60.0
            return np.zeros(FRAME_48K, dtype=np.float32)

        pcm = self.queue.popleft()
        raw = np.frombuffer(pcm, dtype="<i2").astype(np.float32) * (1.0 / 32768.0)

        # Upsample to 48k master clock if sender is 24k or 16k
        if self.sample_rate == 24000:
            samples = upsample_2x(raw)
        elif self.sample_rate == 16000:
            samples = upsample_3x(raw)
        else:
            samples = raw

        if len(samples) < FRAME_48K:
            samples = np.pad(samples, (0, FRAME_48K - len(samples)))
        elif len(samples) > FRAME_48K:
            samples = samples[:FRAME_48K]

        peak = float(np.max(np.abs(samples)))
        self.current_peak = peak
        self.current_db = 20.0 * np.log10(peak) if peak > 1e-4 else -60.0
        return samples

    @property
    def buffer_ms(self) -> float:
        # Each frame is 10 ms
        return len(self.queue) * 10.0

    @property
    def duration_str(self) -> str:
        secs = int(time.monotonic() - self.connected_at)
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# -----------------------------------------------------------------------------
# Main CLI Receiver Engine
# -----------------------------------------------------------------------------
class CliReceiver:
    def __init__(self, port=DEFAULT_PORT, device_name=None, monitor_device=None, mix_mode="sum", use_tcp=False):
        self.port = port
        self.device_name = device_name
        self.monitor_device_name = monitor_device
        self.mix_mode = mix_mode    # "sum" or "duck"
        self.use_tcp = use_tcp
        self.running = False
        self.muted = False
        self.gain_db = 0.0
        self.monitoring = False
        self.show_details = True

        self.lock = threading.Lock()
        self.clients = {}  # addr -> ClientStream

        # Ringbuffers for audio outputs
        self.main_ring = deque(maxlen=40)
        self.monitor_ring = deque(maxlen=40)
        self.master_peak = 0.0
        self.master_db = -60.0

        # Output Streams
        self.main_stream = None
        self.monitor_stream = None
        self.main_dev_info = "None"
        self.monitor_dev_info = "None"

    def start(self):
        self.running = True
        self._start_main_audio()
        if self.monitor_device_name:
            self._start_monitor_audio()

        if self.use_tcp:
            t = threading.Thread(target=self._tcp_loop, daemon=True)
        else:
            t = threading.Thread(target=self._udp_loop, daemon=True)
        t.start()

        # Engine mixer thread
        m = threading.Thread(target=self._mixer_loop, daemon=True)
        m.start()

        # Interactive Terminal UI loop
        self._interactive_ui_loop()

    # -- Device Resolution & Audio Streams -------------------------------------
    def _find_device_idx(self, query=None, prefer_cable=True, prefer_headphones=False):
        if sd is None:
            return None, "sounddevice missing"
        devices = sd.query_devices()

        if query:
            q = query.lower()
            for idx, d in enumerate(devices):
                if q in d["name"].lower() and d["max_output_channels"] > 0:
                    return idx, d["name"]

        if prefer_cable:
            for idx, d in enumerate(devices):
                if "cable" in d["name"].lower() and d["max_output_channels"] > 0:
                    return idx, d["name"]

        if prefer_headphones:
            for idx, d in enumerate(devices):
                name = d["name"].lower()
                if ("headphone" in name or "headset" in name or "earphone" in name) and d["max_output_channels"] > 0:
                    return idx, d["name"]

        # Default system output
        try:
            default_idx = sd.default.device[1]
            if default_idx is not None and default_idx >= 0:
                return default_idx, devices[default_idx]["name"]
        except Exception:
            pass

        for idx, d in enumerate(devices):
            if d["max_output_channels"] > 0:
                return idx, d["name"]
        return None, "No output device found"

    def _start_main_audio(self):
        if sd is None:
            self.main_dev_info = f"Disabled ({_SD_ERR})"
            return

        idx, name = self._find_device_idx(self.device_name, prefer_cable=True)
        self.main_dev_info = name
        try:
            self.main_stream = sd.OutputStream(
                samplerate=48000,
                channels=1,
                dtype="float32",
                blocksize=FRAME_48K,
                device=idx,
                callback=self._main_audio_callback
            )
            self.main_stream.start()
        except Exception as e:
            self.main_dev_info = f"Failed ({e})"

    def _start_monitor_audio(self):
        if sd is None:
            self.monitor_dev_info = f"Disabled ({_SD_ERR})"
            self.monitoring = False
            return False

        idx, name = self._find_device_idx(self.monitor_device_name, prefer_cable=False, prefer_headphones=True)
        self.monitor_dev_info = name
        try:
            self.monitor_stream = sd.OutputStream(
                samplerate=48000,
                channels=1,
                dtype="float32",
                blocksize=FRAME_48K,
                device=idx,
                callback=self._monitor_audio_callback
            )
            self.monitor_stream.start()
            self.monitoring = True
            return True
        except Exception as e:
            self.monitor_dev_info = f"Failed ({e})"
            self.monitoring = False
            return False

    def toggle_monitoring(self):
        if self.monitoring:
            self.monitoring = False
            if self.monitor_stream:
                try:
                    self.monitor_stream.stop()
                    self.monitor_stream.close()
                except Exception:
                    pass
                self.monitor_stream = None
            return False
        else:
            return self._start_monitor_audio()

    def _main_audio_callback(self, outdata, frames, time_info, status):
        try:
            with self.lock:
                if self.main_ring and not self.muted:
                    block = self.main_ring.popleft()
                else:
                    block = np.zeros(frames, dtype=np.float32)
            outdata[:, 0] = block
        except Exception:
            outdata.fill(0)

    def _monitor_audio_callback(self, outdata, frames, time_info, status):
        try:
            with self.lock:
                if self.monitor_ring and self.monitoring and not self.muted:
                    block = self.monitor_ring.popleft()
                else:
                    block = np.zeros(frames, dtype=np.float32)
            outdata[:, 0] = block
        except Exception:
            outdata.fill(0)

    # -- UDP Network Loop ------------------------------------------------------
    def _udp_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        except Exception:
            pass
        try:
            sock.bind(("0.0.0.0", self.port))
        except Exception as e:
            print(f"\n[Error] Cannot bind UDP port {self.port}: {e}", file=sys.stderr)
            self.running = False
            return

        buf = bytearray(4096)
        while self.running:
            try:
                n, addr = sock.recvfrom_into(buf)
            except Exception:
                continue

            if n < 4:
                continue

            # Auto-discovery probe
            if buf[:4] == b"PMD0" or DISCOVERY_PROBE in buf[:min(n, 32)]:
                sock.sendto(DISCOVERY_REPLY + f" {VERSION} 127.0.0.1".encode("ascii"), addr)
                continue

            # Packet headers:
            # PM01 -> 48 kHz 16-bit
            # PM02 -> 24 kHz 16-bit
            # PM03 -> 16 kHz 16-bit
            magic = bytes(buf[:4])
            if magic in (b"PM01", b"PM02", b"PM03") and n >= 8:
                sr = 48000 if magic == b"PM01" else (24000 if magic == b"PM02" else 16000)
                seq = struct.unpack_from(">I", buf, 4)[0]
                pcm = bytes(buf[8:n])
                self._on_client_packet(addr, pcm, sr, seq)
            elif n >= 320 and n % 2 == 0:
                # Raw PCM fallback
                self._on_client_packet(addr, bytes(buf[:n]), 48000, -1)

    # -- TCP Network Loop ------------------------------------------------------
    def _tcp_loop(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind(("0.0.0.0", self.port))
            server.listen(8)
        except Exception as e:
            print(f"\n[Error] Cannot bind TCP port {self.port}: {e}", file=sys.stderr)
            self.running = False
            return

        while self.running:
            try:
                conn, addr = server.accept()
                threading.Thread(target=self._handle_tcp_client, args=(conn, addr), daemon=True).start()
            except Exception:
                break

    def _handle_tcp_client(self, conn, addr):
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        acc = bytearray()
        try:
            while self.running:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                acc.extend(chunk)
                while len(acc) >= 960:
                    pcm = bytes(acc[:960])
                    del acc[:960]
                    self._on_client_packet(addr, pcm, 48000, -1)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _on_client_packet(self, addr, pcm, sample_rate, seq):
        with self.lock:
            client = self.clients.get(addr)
            if client is None:
                client = ClientStream(addr, sample_rate)
                self.clients[addr] = client
            client.push(pcm, sample_rate, seq)

    # -- Mixer Engine ----------------------------------------------------------
    def _mixer_loop(self):
        next_tick = time.monotonic()
        while self.running:
            now = time.monotonic()
            if now < next_tick:
                time.sleep(max(0.001, next_tick - now))
            next_tick += 0.010  # 10 ms per 480-sample block

            # Prune dead clients (inactive > 3.0s)
            with self.lock:
                dead = [a for a, c in self.clients.items() if (now - c.last_seen) > 3.0]
                for d in dead:
                    del self.clients[d]

                active = list(self.clients.values())

            if not active:
                mixed = np.zeros(FRAME_48K, dtype=np.float32)
            elif len(active) == 1:
                mixed = active[0].pop_48k()
            else:
                # Multiple devices connected!
                blocks = [c.pop_48k() for c in active]
                if self.mix_mode == "duck":
                    # Auto-ducking: find loudest speaker, duck others by -10 dB (~0.32x)
                    powers = [float(np.mean(b ** 2)) for b in blocks]
                    max_idx = int(np.argmax(powers))
                    summed = np.zeros(FRAME_48K, dtype=np.float32)
                    for idx, b in enumerate(blocks):
                        weight = 1.0 if idx == max_idx or powers[max_idx] < 1e-4 else 0.32
                        summed += b * weight
                    mixed = np.tanh(summed * 1.1)  # Soft limiter
                else:
                    # Sum & Soft-Knee Limiter
                    summed = np.sum(blocks, axis=0)
                    mixed = np.tanh(summed)  # Soft non-linear saturation prevents clipping

            # Apply gain adjustment
            if abs(self.gain_db) > 0.01:
                scale = 10.0 ** (self.gain_db / 20.0)
                mixed = np.clip(mixed * scale, -1.0, 1.0)

            peak = float(np.max(np.abs(mixed)))
            self.master_peak = peak
            self.master_db = 20.0 * np.log10(peak) if peak > 1e-4 else -60.0

            with self.lock:
                self.main_ring.append(mixed)
                if self.monitoring:
                    self.monitor_ring.append(mixed)

    # -- Interactive Terminal UI & Keybindings ---------------------------------
    def _interactive_ui_loop(self):
        meter_len = 24
        status_msg = ""
        status_until = 0.0

        with KeyPoller() as poller:
            try:
                # Clear screen once at startup
                os.system("cls" if os.name == "nt" else "clear")

                while self.running:
                    time.sleep(0.08)

                    # Poll keys
                    key = poller.poll()
                    if key:
                        now = time.monotonic()
                        if key == "Q":
                            self.running = False
                            break
                        elif key == "M":
                            is_on = self.toggle_monitoring()
                            status_msg = f"[M] Headphone Monitoring: {'ON (' + self.monitor_dev_info + ')' if is_on else 'OFF'}"
                            status_until = now + 2.5
                        elif key == "X":
                            self.mix_mode = "duck" if self.mix_mode == "sum" else "sum"
                            status_msg = f"[X] Mixing Mode: {self.mix_mode.upper()} ({'Auto-Duck Priority' if self.mix_mode == 'duck' else 'Sum & Soft Limiter'})"
                            status_until = now + 2.5
                        elif key == "P":
                            self.muted = not self.muted
                            status_msg = f"[P] Output Mute: {'MUTED' if self.muted else 'ACTIVE'}"
                            status_until = now + 2.5
                        elif key in ("+", "="):
                            self.gain_db = min(18.0, self.gain_db + 1.0)
                            status_msg = f"[+] Master Gain: {self.gain_db:+.1f} dB"
                            status_until = now + 2.0
                        elif key in ("-", "_"):
                            self.gain_db = max(-24.0, self.gain_db - 1.0)
                            status_msg = f"[-] Master Gain: {self.gain_db:+.1f} dB"
                            status_until = now + 2.0
                        elif key == "0":
                            self.gain_db = 0.0
                            status_msg = "[0] Master Gain Reset: 0.0 dB"
                            status_until = now + 2.0
                        elif key == "C":
                            with self.lock:
                                for c in self.clients.values():
                                    c.packet_count = 0
                                    c.lost_packets = 0
                                    c.bytes_count = 0
                            status_msg = "[C] Packet counters cleared"
                            status_until = now + 2.0
                        elif key == "H":
                            self.show_details = not self.show_details
                            os.system("cls" if os.name == "nt" else "clear")

                    now = time.monotonic()
                    with self.lock:
                        clients_list = list(self.clients.values())
                        m_db = self.master_db
                        m_peak = self.master_peak
                        is_muted = self.muted
                        mon_active = self.monitoring
                        gain = self.gain_db

                    # Build UI Output
                    lines = []
                    lines.append("\033[1;36m================================================================================\033[0m")
                    lines.append(f"\033[1m  PhoneMic CLI Receiver v{VERSION}\033[0m  |  Port: \033[33m{self.port}\033[0m  |  Protocol: \033[32m{'TCP' if self.use_tcp else 'UDP'}\033[0m")
                    lines.append(f"  Target Device : \033[32m{self.main_dev_info}\033[0m")
                    lines.append(f"  Monitor Audio : \033[{'32mENABLED' if mon_active else '90mDISABLED'}\033[0m ({self.monitor_dev_info})")
                    lines.append(f"  Mixer Mode    : \033[35m{self.mix_mode.upper()}\033[0m ({'Auto-Duck Priority' if self.mix_mode == 'duck' else 'Sum & Soft Limiter'}) | Gain: \033[33m{gain:+.1f} dB\033[0m | State: \033[{'31mMUTED' if is_muted else '32mSTREAMING'}\033[0m")
                    lines.append("\033[1;36m================================================================================\033[0m")

                    # Hotkey Bar
                    lines.append("  \033[93m[M]\033[0m Monitor  \033[93m[X]\033[0m MixMode  \033[93m[P]\033[0m Mute  \033[93m[+/-]\033[0m Gain  \033[93m[0]\033[0m ResetGain  \033[93m[C]\033[0m ClearStats  \033[93m[H]\033[0m Info  \033[93m[Q]\033[0m Quit")
                    lines.append("--------------------------------------------------------------------------------")

                    # Live Connected Devices
                    if not clients_list:
                        lines.append("  \033[33m[Waiting for connection...]\033[0m Point PhoneMic app to this PC's IP address.")
                        lines.append("  (Discovery beacon is ACTIVE - or use QR Code / Auto-Detect on phone)")
                    else:
                        lines.append(f"  \033[1mConnected Phones ({len(clients_list)} active):\033[0m")
                        for idx, c in enumerate(clients_list, 1):
                            # VU Meter Bar
                            ratio = max(0.0, min(1.0, (c.current_db + 60.0) / 60.0))
                            filled = int(round(ratio * meter_len))
                            bar = "#" * filled + "-" * (meter_len - filled)
                            sr_khz = f"{c.sample_rate // 1000}k"
                            meter_color = "\033[32m" if c.current_db < -6.0 else ("\033[33m" if c.current_db < -1.0 else "\033[31m")

                            lines.append(f"   #{idx} \033[1m{c.ip}:{c.port}\033[0m [{sr_khz}] [{meter_color}{bar}\033[0m] {c.current_db:5.1f} dB")

                            if self.show_details:
                                drop_pct = (c.lost_packets / max(1, c.packet_count + c.lost_packets)) * 100.0
                                lines.append(f"       \033[90m↳ Rate: {c.kbps:5.1f} kbps | Buffer: {c.buffer_ms:2.0f}ms | Pkts: {c.packet_count} | Lost: {c.lost_packets} ({drop_pct:.1f}%) | Uptime: {c.duration_str}\033[0m")

                    lines.append("--------------------------------------------------------------------------------")

                    # Master Output Meter
                    m_ratio = max(0.0, min(1.0, (m_db + 60.0) / 60.0))
                    m_filled = int(round(m_ratio * meter_len))
                    m_bar = "#" * m_filled + "-" * (meter_len - m_filled)
                    m_color = "\033[32m" if m_db < -6.0 else ("\033[33m" if m_db < -1.0 else "\033[31m")
                    lines.append(f"  \033[1mMaster Mix Output\033[0m  [{m_color}{m_bar}\033[0m] {m_db:5.1f} dB {'[MUTED]' if is_muted else ''}")

                    # Status Toast
                    if now < status_until:
                        lines.append(f"\n  \033[1;33m>>> {status_msg} <<<\033[0m")
                    else:
                        lines.append("")

                    # Render to terminal (overwrite in place)
                    sys.stdout.write("\033[H" + "\n".join(lines) + "\n\033[J")
                    sys.stdout.flush()

            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                print("\n\n[*] Shutting down PhoneMic CLI Receiver...")
                self.running = False
                if self.main_stream:
                    try:
                        self.main_stream.stop()
                        self.main_stream.close()
                    except Exception:
                        pass
                if self.monitor_stream:
                    try:
                        self.monitor_stream.stop()
                        self.monitor_stream.close()
                    except Exception:
                        pass
                print("[*] Goodbye!")


def main():
    parser = argparse.ArgumentParser(description="PhoneMic Standalone CLI Receiver")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on (default 5001)")
    parser.add_argument("--mix-mode", choices=["sum", "duck"], default="sum", help="Multi-device mix mode: 'sum' (soft limiter) or 'duck' (auto-duck)")
    parser.add_argument("--device", type=str, default=None, help="Name of main sound output device (e.g. 'CABLE Input')")
    parser.add_argument("--monitor-device", type=str, default=None, help="Name of monitor headphone device")
    parser.add_argument("--monitor", action="store_true", help="Start with audio monitoring enabled immediately")
    parser.add_argument("--tcp", action="store_true", help="Use TCP transport instead of UDP")
    parser.add_argument("--list-devices", action="store_true", help="List audio output devices and exit")
    args = parser.parse_args()

    if args.list_devices:
        if sd is None:
            print(f"sounddevice error: {_SD_ERR}")
            return
        print("Available output devices:")
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0:
                print(f"  [{idx:2d}] {dev['name']} ({dev['max_output_channels']} ch)")
        return

    rx = CliReceiver(
        port=args.port,
        device_name=args.device,
        monitor_device=args.monitor_device,
        mix_mode=args.mix_mode,
        use_tcp=args.tcp
    )
    if args.monitor:
        rx.monitoring = True

    rx.start()


if __name__ == "__main__":
    main()
