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

from __future__ import annotations

import argparse
import os
import socket
import struct
import sys
import threading
import time
from collections import deque

VERSION = "1.4.2"
DEFAULT_PORT = 5001
DISCOVERY_PROBE = b"PM_DISCOVER"
DISCOVERY_REPLY = b"PMA1"
FRAME_48K = 480       # 10 ms at 48 kHz
FRAME_24K = 240       # 10 ms at 24 kHz
FRAME_16K = 160       # 10 ms at 16 kHz
MASK32 = 0xFFFFFFFF
SIO_UDP_CONNRESET = 0x9800000C

RAW_TCP_RATES = (48000, 24000, 16000)
RATE_TO_FRAME_BYTES = {48000: 960, 24000: 480, 16000: 320}
MAGIC_U32_TO_RATE = {
    0x504D3031: 48000,  # b"PM01"
    0x504D3032: 24000,  # b"PM02"
    0x504D3033: 16000,  # b"PM03"
}
MAGIC_EXT_U32 = 0x504D3034  # b"PM04"
MAGIC_BYTES_TO_RATE = {b"PM01": 48000, b"PM02": 24000, b"PM03": 16000}
FMT_PCM_16 = 0
FMT_PCM_8 = 1
FMT_PCM_24 = 2
FMT_PCM_FLOAT32 = 3
FMT_BYTES_PER_SAMPLE = {
    FMT_PCM_16: 2,
    FMT_PCM_8: 1,
    FMT_PCM_24: 3,
    FMT_PCM_FLOAT32: 4,
}
_PM04_STRUCT = struct.Struct(">IIIBBH")
PM04_HEADER_BYTES = _PM04_STRUCT.size
MIN_EXT_RATE = 8000
MAX_EXT_RATE = 192000
MAX_TCP_ACCUM_BYTES = 65536
TCP_HEADER_PEEK_CAP = 8192
MAX_TCP_CLIENTS = 8

try:
    import numpy as np
    _NP_ERR = ""
except ImportError as _e:
    np = None
    _NP_ERR = str(_e)

if np is not None:
    _INV_I16 = np.float32(1.0 / 32768.0)
    _INV_I8 = np.float32(1.0 / 128.0)
    _INV_I24 = np.float32(1.0 / 8388608.0)
    _RESAMPLE_AXIS_CACHE = {}
    _EMPTY_F32 = np.zeros(0, dtype=np.float32)
    _EMPTY_F32.setflags(write=False)
    _ZERO_FRAME = np.zeros(FRAME_48K, dtype=np.float32)
    _ZERO_FRAME.setflags(write=False)
else:
    _INV_I16 = 1.0 / 32768.0
    _INV_I8 = 1.0 / 128.0
    _INV_I24 = 1.0 / 8388608.0
    _RESAMPLE_AXIS_CACHE = {}
    _EMPTY_F32 = None
    _ZERO_FRAME = None

try:
    import sounddevice as sd
except Exception as e:
    sd = None
    _SD_ERR = str(e)
else:
    _SD_ERR = ""


def enable_ansi():
    """Turn on ANSI colour escapes in Windows 10+ consoles."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


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
    if n == 0:
        return _EMPTY_F32 if _EMPTY_F32 is not None else np.zeros(0, dtype=np.float32)
    out = np.empty(n * 2, dtype=np.float32)
    out[0::2] = x
    if n > 1:
        out[1:-1:2] = (x[:-1] + x[1:]) * np.float32(0.5)
    out[-1] = x[-1]
    return out


def upsample_3x(x: np.ndarray) -> np.ndarray:
    """Upsample 16 kHz float32 samples to 48 kHz using linear interpolation."""
    n = len(x)
    if n == 0:
        return _EMPTY_F32 if _EMPTY_F32 is not None else np.zeros(0, dtype=np.float32)
    out = np.empty(n * 3, dtype=np.float32)
    out[0::3] = x
    if n > 1:
        out[1:-2:3] = x[:-1] * np.float32(2.0 / 3.0) + x[1:] * np.float32(1.0 / 3.0)
        out[2:-1:3] = x[:-1] * np.float32(1.0 / 3.0) + x[1:] * np.float32(2.0 / 3.0)
    out[-2] = x[-1]
    out[-1] = x[-1]
    return out


def _pm04_frame_bytes(sample_rate: int, channels: int, fmt_code: int) -> int:
    if not (MIN_EXT_RATE <= sample_rate <= MAX_EXT_RATE) or channels not in (1, 2):
        return 0
    bps = FMT_BYTES_PER_SAMPLE.get(fmt_code)
    if bps is None:
        return 0
    samples = max(1, (sample_rate * 10) // 1000)
    fb = samples * channels * bps
    if fb <= 0 or (PM04_HEADER_BYTES + fb) > (MAX_TCP_ACCUM_BYTES // 2):
        return 0
    return fb


def _parse_pm04_header(buf, offset: int = 0):
    if len(buf) - offset < PM04_HEADER_BYTES:
        return None
    magic_u32, seq, sr, ch, fmt_code, _flags = _PM04_STRUCT.unpack_from(buf, offset)
    if magic_u32 != MAGIC_EXT_U32:
        return None
    fb = _pm04_frame_bytes(sr, ch, fmt_code)
    if fb <= 0:
        return None
    return seq, sr, ch, fmt_code, fb


def resample_linear_to_48k(x: np.ndarray, sample_rate: int) -> np.ndarray:
    n = len(x)
    if n == 0:
        return _EMPTY_F32 if _EMPTY_F32 is not None else np.zeros(0, dtype=np.float32)
    if sample_rate == 48000:
        return x
    if sample_rate == 24000:
        return upsample_2x(x)
    if sample_rate == 16000:
        return upsample_3x(x)
    if n == 1:
        return np.full(FRAME_48K, x[0], dtype=np.float32)
    out_len = max(1, int(round(n * (48000.0 / float(sample_rate)))))
    key = (n, out_len)
    pair = _RESAMPLE_AXIS_CACHE.get(key)
    if pair is None:
        xp = np.arange(n, dtype=np.float32)
        x_eval = np.arange(out_len, dtype=np.float32) * np.float32(float(n) / float(out_len))
        pair = (xp, x_eval)
        if len(_RESAMPLE_AXIS_CACHE) < 32:
            _RESAMPLE_AXIS_CACHE[key] = pair
    xp, x_eval = pair
    return np.interp(x_eval, xp, x).astype(np.float32)


# -----------------------------------------------------------------------------
# Wire Parser (Raw 48k/24k/16k PCM + Compat Framed PM01..PM04) & Ring Buffer
# -----------------------------------------------------------------------------
class _CliTcpStreamParser:
    """Standalone stateful TCP parser preserving raw PCM across 48k/24k/16k
    plus strict byte-0 dual-header compat detection for PM01..PM04 streams.
    """

    def __init__(self, default_rate: int = 48000):
        rate = int(default_rate) if default_rate in RATE_TO_FRAME_BYTES else 48000
        self.default_rate = rate
        self.sample_rate = rate
        self.frame_bytes = RATE_TO_FRAME_BYTES[rate]
        self.channels = 1
        self.fmt_code = FMT_PCM_16
        self.mode = "unknown"       # "unknown" -> "raw" | "framed"
        self.acc = bytearray()
        self.pos = 0

    @property
    def buffered_bytes(self) -> int:
        return len(self.acc) - self.pos

    def feed(self, chunk):
        return [(seq, pcm, sr) for seq, pcm, sr, _, _ in self.feed_ex(chunk)]

    def feed_ex(self, chunk):
        if not chunk:
            return []
        if self.buffered_bytes + len(chunk) > MAX_TCP_ACCUM_BYTES:
            raise BufferError(f"TCP accumulator exceeded {MAX_TCP_ACCUM_BYTES} bytes")

        self.acc.extend(chunk)
        frames = []

        if self.mode == "unknown":
            self._detect_mode()

        if self.mode == "raw":
            fb = self.frame_bytes
            sr = self.sample_rate
            mv = memoryview(self.acc)
            try:
                while (len(self.acc) - self.pos) >= fb:
                    end = self.pos + fb
                    frames.append((-1, bytes(mv[self.pos:end]), sr, 1, FMT_PCM_16))
                    self.pos = end
            finally:
                mv.release()
        elif self.mode == "framed":
            mv = memoryview(self.acc)
            try:
                while (len(self.acc) - self.pos) >= 8:
                    magic_u32, seq = struct.unpack_from(">II", self.acc, self.pos)
                    if magic_u32 == MAGIC_EXT_U32:
                        if (len(self.acc) - self.pos) < PM04_HEADER_BYTES:
                            break
                        parsed = _parse_pm04_header(self.acc, self.pos)
                        if parsed is None:
                            raise ValueError("Invalid PM04 header inside framed TCP stream")
                        seq, sr, ch, fmt_code, fb = parsed
                        hdr_len = PM04_HEADER_BYTES
                    else:
                        sr = MAGIC_U32_TO_RATE.get(magic_u32)
                        if sr is None:
                            raise ValueError("Invalid magic inside framed TCP stream")
                        ch = 1
                        fmt_code = FMT_PCM_16
                        fb = RATE_TO_FRAME_BYTES[sr]
                        hdr_len = 8
                    if (len(self.acc) - self.pos) < hdr_len + fb:
                        break
                    start = self.pos + hdr_len
                    end = start + fb
                    self.sample_rate = sr
                    self.channels = ch
                    self.fmt_code = fmt_code
                    self.frame_bytes = fb
                    frames.append((seq, bytes(mv[start:end]), sr, ch, fmt_code))
                    self.pos = end
            finally:
                mv.release()

        if self.pos > 0:
            if self.pos >= len(self.acc):
                self.acc.clear()
            else:
                del self.acc[:self.pos]
            self.pos = 0

        if len(self.acc) > MAX_TCP_ACCUM_BYTES:
            raise BufferError(f"TCP accumulator exceeded {MAX_TCP_ACCUM_BYTES} bytes")
        return frames

    def _lock_raw(self):
        self.mode = "raw"
        self.sample_rate = self.default_rate
        self.frame_bytes = RATE_TO_FRAME_BYTES[self.default_rate]
        self.channels = 1
        self.fmt_code = FMT_PCM_16

    def _detect_mode(self):
        avail = len(self.acc) - self.pos
        if avail < 4:
            return
        mv = memoryview(self.acc)
        try:
            head0 = bytes(mv[self.pos:self.pos + 4])
            if head0 == b"PM04":
                if avail < PM04_HEADER_BYTES:
                    return
                parsed0 = _parse_pm04_header(self.acc, self.pos)
                if parsed0 is None:
                    self._lock_raw()
                    return
                seq0, sr0, ch0, fmt0, fb0 = parsed0
                need = PM04_HEADER_BYTES + fb0 + PM04_HEADER_BYTES
                if avail < need:
                    if avail >= TCP_HEADER_PEEK_CAP:
                        self._lock_raw()
                    return
                parsed1 = _parse_pm04_header(self.acc, self.pos + PM04_HEADER_BYTES + fb0)
                if parsed1 is not None and seq0 <= 16 and parsed1[0] == ((seq0 + 1) & MASK32):
                    self.mode = "framed"
                    self.sample_rate = sr0
                    self.channels = ch0
                    self.fmt_code = fmt0
                    self.frame_bytes = fb0
                else:
                    self._lock_raw()
                return

            sr0 = MAGIC_BYTES_TO_RATE.get(head0)
            if sr0 is None:
                self._lock_raw()
                return
            fb0 = RATE_TO_FRAME_BYTES[sr0]
            need = 8 + fb0 + 8
            if avail < need:
                if avail >= TCP_HEADER_PEEK_CAP:
                    self._lock_raw()
                return
            seq0 = struct.unpack_from(">I", self.acc, self.pos + 4)[0]
            head1_off = self.pos + 8 + fb0
            head1 = bytes(mv[head1_off:head1_off + 4])
            seq1 = struct.unpack_from(">I", self.acc, head1_off + 4)[0]
            if head1 == head0 and seq0 <= 16 and seq1 == ((seq0 + 1) & MASK32):
                self.mode = "framed"
                self.sample_rate = sr0
                self.channels = 1
                self.fmt_code = FMT_PCM_16
                self.frame_bytes = fb0
            else:
                self._lock_raw()
        finally:
            mv.release()


class Ring:
    """Lock-isolated float32 circular ring buffer for PortAudio callbacks."""

    def __init__(self, capacity: int = FRAME_48K * 40):
        self.cap = max(FRAME_48K, int(capacity))
        self.buf = np.zeros(self.cap, dtype=np.float32) if np is not None else None
        self.r = 0
        self.w = 0
        self.avail = 0
        self.drops = 0
        self.underruns = 0
        self.lock = threading.Lock()

    def clear(self):
        with self.lock:
            self.r = 0
            self.w = 0
            self.avail = 0

    def write(self, samples: np.ndarray):
        x = np.asarray(samples, dtype=np.float32)
        n = len(x)
        if n == 0 or self.buf is None:
            return
        with self.lock:
            if n > self.cap:
                x = x[-self.cap:]
                n = self.cap
            overflow = (self.avail + n) - self.cap
            if overflow > 0:
                self.r = (self.r + overflow) % self.cap
                self.avail -= overflow
                self.drops += 1
            first = min(n, self.cap - self.w)
            self.buf[self.w:self.w + first] = x[:first]
            rem = n - first
            if rem:
                self.buf[:rem] = x[first:]
            self.w = (self.w + n) % self.cap
            self.avail += n

    def read_into(self, out_1d: np.ndarray) -> int:
        n = len(out_1d)
        if n == 0:
            return 0
        if self.buf is None:
            out_1d.fill(0.0)
            return 0
        with self.lock:
            take = min(n, self.avail)
            if take > 0:
                first = min(take, self.cap - self.r)
                out_1d[:first] = self.buf[self.r:self.r + first]
                rem = take - first
                if rem:
                    out_1d[first:take] = self.buf[:rem]
                self.r = (self.r + take) % self.cap
                self.avail -= take
            if take < n:
                out_1d[take:].fill(0.0)
                self.underruns += 1
            return take

    def available(self) -> int:
        with self.lock:
            return self.avail


# -----------------------------------------------------------------------------
# Per-Client Stream Tracking & Metrics
# -----------------------------------------------------------------------------
class ClientStream:
    def __init__(self, addr, sample_rate=48000, target_packets=3, channels=1, fmt_code=FMT_PCM_16):
        self.addr = addr
        self.ip = addr[0]
        self.port = addr[1]
        self.sample_rate = sample_rate
        self.channels = channels
        self.fmt_code = fmt_code
        self.queue = deque(maxlen=30)
        self.target_packets = target_packets
        self.connected_at = time.monotonic()
        self.last_seen = self.connected_at
        self.packet_count = 0
        self.bytes_count = 0
        self.last_seq = -1
        self.lost_packets = 0
        self.current_peak = 0.0
        self.current_db = -60.0
        self.buffering = True

        # Bandwidth calculation (sliding 1-sec window)
        self.rate_bytes = 0
        self.last_rate_calc = self.connected_at
        self.kbps = 0.0

    def push(self, pcm_bytes: bytes, sample_rate: int, seq: int = -1, channels: int = 1, fmt_code: int = FMT_PCM_16):
        now = time.monotonic()
        self.last_seen = now
        self.packet_count += 1
        nbytes = len(pcm_bytes)
        self.bytes_count += nbytes
        self.rate_bytes += nbytes
        self.sample_rate = sample_rate
        self.channels = 2 if channels == 2 else 1
        self.fmt_code = fmt_code

        # Sequence gap check (uint32 sequence numbers)
        if seq >= 0 and self.last_seq >= 0:
            diff = (seq - self.last_seq) & MASK32
            if 1 < diff < 1000:
                self.lost_packets += (diff - 1)
        if seq >= 0:
            self.last_seq = seq

        # Calculate bit-rate
        dt = now - self.last_rate_calc
        if dt >= 1.0:
            self.kbps = (self.rate_bytes * 8.0) / (dt * 1000.0)
            self.rate_bytes = 0
            self.last_rate_calc = now

        self.queue.append((pcm_bytes, sample_rate, self.channels, fmt_code))
        if self.buffering and len(self.queue) >= self.target_packets:
            self.buffering = False

    def pop_48k(self) -> np.ndarray:
        if self.buffering:
            return _ZERO_FRAME
        if not self.queue:
            self.buffering = True
            self.current_peak = 0.0
            self.current_db = -60.0
            return _ZERO_FRAME

        pcm, sr, ch, fmt_code = self.queue.popleft()
        bps = FMT_BYTES_PER_SAMPLE.get(fmt_code, 2)
        stride = ch * bps
        usable = len(pcm) - (len(pcm) % stride)
        if usable < stride:
            return _ZERO_FRAME
        mv = memoryview(pcm)[:usable]

        if fmt_code == FMT_PCM_16:
            raw = np.frombuffer(mv, dtype="<i2").astype(np.float32) * _INV_I16
        elif fmt_code == FMT_PCM_8:
            raw = (np.frombuffer(mv, dtype=np.uint8).astype(np.float32) - np.float32(128.0)) * _INV_I8
        elif fmt_code == FMT_PCM_24:
            u8 = np.frombuffer(mv, dtype=np.uint8).reshape(-1, 3)
            b0 = u8[:, 0].astype(np.int32)
            b1 = u8[:, 1].astype(np.int32) << 8
            b2 = u8[:, 2].view(np.int8).astype(np.int32) << 16
            raw = (b0 | b1 | b2).astype(np.float32) * _INV_I24
        elif fmt_code == FMT_PCM_FLOAT32:
            raw = np.frombuffer(mv, dtype="<f4").astype(np.float32, copy=True)
            np.nan_to_num(raw, copy=False, nan=0.0, posinf=1.0, neginf=-1.0)
            np.clip(raw, -1.0, 1.0, out=raw)
        else:
            return _ZERO_FRAME

        if ch == 2:
            even_pairs = (len(raw) // 2) * 2
            raw = (raw[0:even_pairs:2] + raw[1:even_pairs:2]) * np.float32(0.5)

        samples = resample_linear_to_48k(raw, sr) if sr != 48000 else raw

        if len(samples) < FRAME_48K:
            padded = np.zeros(FRAME_48K, dtype=np.float32)
            padded[:len(samples)] = samples
            samples = padded
        elif len(samples) > FRAME_48K:
            samples = samples[:FRAME_48K]

        peak = float(np.max(np.abs(samples)))
        self.current_peak = peak
        self.current_db = 20.0 * float(np.log10(peak)) if peak > 1e-4 else -60.0
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
    def __init__(self, port=DEFAULT_PORT, device_name=None, monitor_device=None, mix_mode="sum",
                 use_tcp=False, raw_tcp_rate=48000):
        self.port = port
        self.device_name = device_name
        self.monitor_device_name = monitor_device
        self.mix_mode = mix_mode    # "sum" or "duck"
        self.use_tcp = use_tcp
        self.raw_tcp_rate = int(raw_tcp_rate) if raw_tcp_rate in RAW_TCP_RATES else 48000
        self.running = False
        self.muted = False
        self.gain_db = 0.0
        self.monitoring = False
        self.show_details = True

        # Strictly lock-split state:
        # - clients_lock ONLY protects self.clients and client telemetry (NEVER acquired in callbacks)
        # - main_ring / monitor_ring each own an internal fixed-memcpy Ring.lock
        self.clients_lock = threading.Lock()
        self.lock = self.clients_lock   # legacy alias; never used by audio callbacks
        self.clients = {}               # addr -> ClientStream

        # Lock-isolated float32 circular ring buffers for audio outputs
        self.main_ring = Ring(FRAME_48K * 40)
        self.monitor_ring = Ring(FRAME_48K * 40)
        self.master_peak = 0.0
        self.master_db = -60.0

        # Wakeup & callback diagnostics (audio callbacks never call Event.set())
        self._wake_event = threading.Event()
        self._cb_epoch = 0
        self._mix_sum = np.empty(FRAME_48K, dtype=np.float32) if np is not None else None

        # Thread / socket tracking for deterministic shutdown
        self._tcp_lock = threading.Lock()
        self._tcp_conns = set()
        self._tcp_threads = []
        self._net_thread = None
        self._mixer_thread = None
        self._udp_sock = None
        self._tcp_server = None
        self._ip_cache = {}
        self._bind_error = ""

        # Output Streams
        self.main_stream = None
        self.monitor_stream = None
        self.main_dev_info = "None"
        self.monitor_dev_info = "None"

    def start(self, interactive=True):
        self.running = True
        self._start_main_audio()
        if self.monitor_device_name or self.monitoring:
            self._start_monitor_audio()

        target = self._tcp_loop if self.use_tcp else self._udp_loop
        self._net_thread = threading.Thread(target=target, name="PM-CLI-Net", daemon=True)
        self._net_thread.start()

        self._mixer_thread = threading.Thread(target=self._mixer_loop, name="PM-CLI-Mix", daemon=True)
        self._mixer_thread.start()

        if interactive:
            self._interactive_ui_loop()

    def stop(self):
        self.running = False
        self._wake_event.set()
        for sock_attr in ("_udp_sock", "_tcp_server"):
            s = getattr(self, sock_attr, None)
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
                setattr(self, sock_attr, None)
        with self._tcp_lock:
            conns = list(self._tcp_conns)
            self._tcp_conns.clear()
            tcp_threads = list(self._tcp_threads)
            self._tcp_threads.clear()
        for c in conns:
            try:
                c.close()
            except Exception:
                pass
        for t in (self._net_thread, self._mixer_thread, *tcp_threads):
            if t is not None and t.is_alive() and t is not threading.current_thread():
                t.join(timeout=1.5)
        self._net_thread = None
        self._mixer_thread = None
        for stream_attr in ("main_stream", "monitor_stream"):
            st = getattr(self, stream_attr, None)
            if st is not None:
                try:
                    st.stop()
                    st.close()
                except Exception:
                    pass
                setattr(self, stream_attr, None)

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
            self.monitor_ring.clear()
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
        """Real-time audio callback: never acquires clients_lock and never calls Event.set()."""
        try:
            if self.muted:
                outdata.fill(0.0)
            else:
                self.main_ring.read_into(outdata[:, 0])
            self._cb_epoch += 1
        except Exception:
            outdata.fill(0.0)

    def _monitor_audio_callback(self, outdata, frames, time_info, status):
        """Real-time monitor callback: never acquires clients_lock and never calls Event.set()."""
        try:
            if not self.monitoring or self.muted:
                outdata.fill(0.0)
            else:
                self.monitor_ring.read_into(outdata[:, 0])
        except Exception:
            outdata.fill(0.0)

    # -- Discovery Subnet Cache ------------------------------------------------
    def _reply_for_remote(self, remote_ip: str) -> bytes:
        cached = self._ip_cache.get(remote_ip)
        if cached is not None:
            return cached
        local_ip = "127.0.0.1"
        try:
            s_probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s_probe.connect((remote_ip, self.port))
            local_ip = s_probe.getsockname()[0]
            s_probe.close()
        except Exception:
            try:
                local_ip = socket.gethostbyname(socket.gethostname())
            except Exception:
                pass
        reply = DISCOVERY_REPLY + f" {VERSION} {local_ip}".encode("ascii")
        if len(self._ip_cache) >= 64:
            self._ip_cache.clear()
        self._ip_cache[remote_ip] = reply
        return reply

    # -- UDP Network Loop ------------------------------------------------------
    def _udp_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        if os.name == "nt":
            try:
                sock.ioctl(SIO_UDP_CONNRESET, False)
            except Exception:
                pass
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        except Exception:
            pass
        try:
            sock.bind(("0.0.0.0", self.port))
            sock.settimeout(0.5)
        except Exception as e:
            self._bind_error = str(e)
            print(f"\n[Error] Cannot bind UDP port {self.port}: {e}", file=sys.stderr)
            self.running = False
            self._wake_event.set()
            try:
                sock.close()
            except Exception:
                pass
            return

        self._udp_sock = sock
        buf = bytearray(8192)
        mv = memoryview(buf)
        try:
            while self.running:
                try:
                    n, addr = sock.recvfrom_into(buf)
                except socket.timeout:
                    continue
                except OSError:
                    if not self.running:
                        break
                    continue
                except Exception:
                    continue

                if n < 4:
                    continue

                magic_u32 = struct.unpack_from(">I", buf, 0)[0]
                sr = MAGIC_U32_TO_RATE.get(magic_u32)
                if sr is not None and n >= 8:
                    seq = struct.unpack_from(">I", buf, 4)[0]
                    pcm_len = (n - 8) & ~1
                    if pcm_len >= 2:
                        self._on_client_packet(addr, bytes(mv[8:8 + pcm_len]), sr, seq)
                    continue
                if magic_u32 == MAGIC_EXT_U32 and n >= PM04_HEADER_BYTES:
                    parsed = _parse_pm04_header(buf, 0)
                    if parsed is not None:
                        seq, sr, ch, fmt_code, _ = parsed
                        stride = ch * FMT_BYTES_PER_SAMPLE[fmt_code]
                        avail = n - PM04_HEADER_BYTES
                        usable = avail - (avail % stride)
                        if usable >= stride:
                            self._on_client_packet(
                                addr,
                                bytes(mv[PM04_HEADER_BYTES:PM04_HEADER_BYTES + usable]),
                                sr,
                                seq,
                                channels=ch,
                                fmt_code=fmt_code,
                            )
                    continue

                # Auto-discovery probe (PMD0 or PM_DISCOVER)
                if n >= 4:
                    head = bytes(mv[:min(n, 32)])
                    if (magic_u32 == 0x504D4430 or magic_u32 == 0x504D5F44
                            or head.startswith((b"PMD", DISCOVERY_PROBE))
                            or b"PMD0" in head or DISCOVERY_PROBE in head):
                        try:
                            sock.sendto(self._reply_for_remote(addr[0]), addr)
                        except OSError:
                            pass
                        continue
                if n >= 320 and (n & 1) == 0:
                    # Raw PCM fallback
                    self._on_client_packet(addr, bytes(mv[:n]), 48000, -1)
        finally:
            mv.release()
            self._udp_sock = None
            try:
                sock.close()
            except Exception:
                pass

    # -- TCP Network Loop ------------------------------------------------------
    def _tcp_loop(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        try:
            server.bind(("0.0.0.0", self.port))
            server.listen(MAX_TCP_CLIENTS)
            server.settimeout(0.5)
        except Exception as e:
            self._bind_error = str(e)
            print(f"\n[Error] Cannot bind TCP port {self.port}: {e}", file=sys.stderr)
            self.running = False
            self._wake_event.set()
            try:
                server.close()
            except Exception:
                pass
            return

        self._tcp_server = server
        try:
            while self.running:
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with self._tcp_lock:
                    self._tcp_threads = [t for t in self._tcp_threads if t.is_alive()]
                    if len(self._tcp_threads) >= MAX_TCP_CLIENTS:
                        try:
                            conn.close()
                        except Exception:
                            pass
                        continue
                    self._tcp_conns.add(conn)
                    t = threading.Thread(target=self._handle_tcp_client, args=(conn, addr), name=f"PM-CLI-TCP-{addr[1]}", daemon=True)
                    self._tcp_threads.append(t)
                    t.start()
        finally:
            self._tcp_server = None
            try:
                server.close()
            except Exception:
                pass

    def _handle_tcp_client(self, conn, addr):
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        conn.settimeout(2.0)
        parser = _CliTcpStreamParser(default_rate=self.raw_tcp_rate)
        try:
            while self.running:
                try:
                    chunk = conn.recv(8192)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                for seq, pcm, sr, ch, fmt_code in parser.feed_ex(chunk):
                    self._on_client_packet(addr, pcm, sr, seq, channels=ch, fmt_code=fmt_code)
        except Exception:
            pass
        finally:
            with self._tcp_lock:
                self._tcp_conns.discard(conn)
            try:
                conn.close()
            except Exception:
                pass

    def _on_client_packet(self, addr, pcm, sample_rate, seq, channels=1, fmt_code=FMT_PCM_16):
        now = time.monotonic()
        with self.clients_lock:
            client = self.clients.get(addr)
            if client is None:
                # Cap clients collection at MAX_TCP_CLIENTS to prevent memory exhaustion
                if len(self.clients) >= MAX_TCP_CLIENTS:
                    oldest_addr = min(self.clients.keys(), key=lambda a: self.clients[a].last_seen)
                    if (now - self.clients[oldest_addr].last_seen) > 1.0:
                        del self.clients[oldest_addr]
                    else:
                        return
                client = ClientStream(addr, sample_rate, channels=channels, fmt_code=fmt_code)
                self.clients[addr] = client
            client.push(pcm, sample_rate, seq, channels=channels, fmt_code=fmt_code)
        self._wake_event.set()

    # -- Mixer Engine ----------------------------------------------------------
    def _mixer_loop(self):
        next_tick = time.monotonic()
        while self.running:
            now = time.monotonic()
            rem = next_tick - now
            if rem > 0.001:
                # Clear before waiting and bound sleep by <= 10ms monotonic fallback so lost wakeups never stall audio.
                self._wake_event.clear()
                self._wake_event.wait(timeout=min(0.010, rem))
                now = time.monotonic()
            # Guard against unbounded catch-up bursts after OS suspend/debugger pause
            if now - next_tick > 0.050:
                next_tick = now + 0.010
            else:
                next_tick += 0.010  # 10 ms per 480-sample block

            # Prune dead clients (inactive > 3.0s)
            with self.clients_lock:
                dead = [a for a, c in self.clients.items() if (now - c.last_seen) > 3.0]
                for d in dead:
                    del self.clients[d]
                active = list(self.clients.values())

            if not active:
                self.master_peak = 0.0
                self.master_db = -60.0
                self.main_ring.write(_ZERO_FRAME)
                if self.monitoring:
                    self.monitor_ring.write(_ZERO_FRAME)
                continue

            if len(active) == 1:
                mixed = active[0].pop_48k()
                if abs(self.gain_db) > 0.01:
                    scale = np.float32(10.0 ** (self.gain_db / 20.0))
                    np.multiply(mixed, scale, out=self._mix_sum)
                    np.clip(self._mix_sum, -1.0, 1.0, out=self._mix_sum)
                    mixed = self._mix_sum
            else:
                blocks = [c.pop_48k() for c in active]
                summed = self._mix_sum
                summed.fill(0.0)
                if self.mix_mode == "duck":
                    # Auto-ducking: find loudest speaker, duck others by -12 dB (0.25x weight)
                    powers = [float(np.dot(b, b)) / FRAME_48K for b in blocks]
                    max_idx = int(np.argmax(powers))
                    peak_pow = powers[max_idx]
                    for idx, b in enumerate(blocks):
                        if idx == max_idx or peak_pow < 1e-4:
                            summed += b
                        else:
                            summed += b * np.float32(0.25)
                    summed *= np.float32(1.1)
                    np.tanh(summed, out=summed)
                else:
                    # Sum & Soft-Knee Limiter
                    for b in blocks:
                        summed += b
                    np.tanh(summed, out=summed)

                if abs(self.gain_db) > 0.01:
                    summed *= np.float32(10.0 ** (self.gain_db / 20.0))
                    np.clip(summed, -1.0, 1.0, out=summed)
                mixed = summed

            peak = float(np.max(np.abs(mixed)))
            self.master_peak = peak
            self.master_db = 20.0 * float(np.log10(peak)) if peak > 1e-4 else -60.0

            self.main_ring.write(mixed)
            if self.monitoring:
                self.monitor_ring.write(mixed)

    # -- Interactive Terminal UI & Keybindings ---------------------------------
    def _interactive_ui_loop(self):
        meter_len = 24
        status_msg = ""
        status_until = 0.0
        enable_ansi()

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
                            with self.clients_lock:
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
                    with self.clients_lock:
                        clients_list = list(self.clients.values())
                    m_db = self.master_db
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
                            sr_khz = f"{c.sample_rate / 1000.0:g}k"
                            ch_tag = " ST" if c.channels == 2 else ""
                            meter_color = "\033[32m" if c.current_db < -6.0 else ("\033[33m" if c.current_db < -1.0 else "\033[31m")

                            lines.append(f"   #{idx} \033[1m{c.ip}:{c.port}\033[0m [{sr_khz}{ch_tag}] [{meter_color}{bar}\033[0m] {c.current_db:5.1f} dB")

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
                self.stop()
                print("[*] Goodbye!")


def valid_port(val):
    try:
        p = int(val)
        if 1 <= p <= 65535:
            return p
    except Exception:
        pass
    raise argparse.ArgumentTypeError(f"Invalid port: '{val}'. Must be between 1 and 65535.")


def main():
    parser = argparse.ArgumentParser(description="PhoneMic Standalone CLI Receiver")
    parser.add_argument("--port", type=valid_port, default=DEFAULT_PORT, help="Port to listen on (1-65535, default 5001)")
    parser.add_argument("--mix-mode", choices=["sum", "duck"], default="sum", help="Multi-device mix mode: 'sum' (soft limiter) or 'duck' (auto-duck)")
    parser.add_argument("--device", type=str, default=None, help="Name of main sound output device (e.g. 'CABLE Input')")
    parser.add_argument("--monitor-device", type=str, default=None, help="Name of monitor headphone device")
    parser.add_argument("--monitor", action="store_true", help="Start with audio monitoring enabled immediately")
    parser.add_argument("--tcp", action="store_true", help="Use TCP transport instead of UDP")
    parser.add_argument("--tcp-rate", type=int, choices=list(RAW_TCP_RATES), default=48000,
                        help="Sample rate for unframed raw TCP streams (48000, 24000, or 16000; default 48000)")
    parser.add_argument("--list-devices", action="store_true", help="List audio output devices and exit")
    parser.add_argument("-V", "--version", action="store_true", help="Print version and exit")
    args = parser.parse_args()

    if args.version:
        print(f"PhoneMic CLI Receiver {VERSION}")
        return 0

    if args.list_devices:
        if sd is None:
            print(f"sounddevice error: {_SD_ERR}")
            return 1
        print("Available output devices:")
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0:
                print(f"  [{idx:2d}] {dev['name']} ({dev['max_output_channels']} ch)")
        return 0

    if np is None:
        print("Error: numpy is required for audio processing. Please run: pip install numpy", file=sys.stderr)
        return 1

    rx = CliReceiver(
        port=args.port,
        device_name=args.device,
        monitor_device=args.monitor_device,
        mix_mode=args.mix_mode,
        use_tcp=args.tcp,
        raw_tcp_rate=args.tcp_rate,
    )
    if args.monitor:
        rx.monitoring = True

    rx.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
