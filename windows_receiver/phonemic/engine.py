"""Receiver engine.

Thread layout (nothing heavy ever runs on a socket thread):

    UDP/TCP threads --push--> JitterBuffer --pop--> Engine thread (DSP) --write--> Ring --callback--> sound card
                                                                     \\--> monitor Ring --callback--> headphones
                                                                     \\--> Recorder queue --> WAV writer thread

The sound card clock drives everything: output callbacks wake the engine thread when they need more audio, so
the jitter buffer level directly reflects network jitter and clock drift (and is corrected there).
"""
import os
import time
import wave
import queue
import socket
import struct
import threading
from collections import deque

import numpy as np

from . import system, virtual_mic
from .const import (VERSION, FRAME, FRAME_MS, SAMPLE_RATE, PACKET_MAGIC, PACKET_MAGIC_24K, PACKET_MAGIC_16K,
                    DISCOVERY_PROBE, DISCOVERY_REPLY, CMD_PAUSE, CMD_RESUME, SIO_UDP_CONNRESET)
from .dsp import AudioProcessor
from .wire import MAGIC_U32_TO_RATE, TcpStreamParser

try:                                    # PortAudio missing raises OSError, not ImportError
    import sounddevice as _sd
    SD_ERROR = ""
except Exception as _e:                 # noqa: BLE001
    _sd = None
    SD_ERROR = str(_e)

MASK32 = 0xFFFFFFFF

_PCM_SCALE = np.float32(1.0 / 32768.0)
_TWO_THIRDS = np.float32(2.0 / 3.0)
_ONE_THIRD = np.float32(1.0 / 3.0)
_ZERO_FRAME = np.zeros(FRAME, np.float32)
_ZERO_FRAME.setflags(write=False)
_PLC_RAMP1 = np.linspace(0.8, 0.4, FRAME, dtype=np.float32)
_PLC_RAMP1.setflags(write=False)
_PLC_RAMP2 = np.linspace(0.4, 0.0, FRAME, dtype=np.float32)
_PLC_RAMP2.setflags(write=False)
_GAP_RAMP = np.linspace(0.0, 1.0, 48, dtype=np.float32)
_GAP_RAMP.setflags(write=False)


def upsample_2x(x: np.ndarray) -> np.ndarray:
    """Upsample 24 kHz float32 samples to 48 kHz using linear interpolation."""
    n = len(x)
    if n == 0:
        return np.zeros(0, dtype=np.float32)
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
        return np.zeros(0, dtype=np.float32)
    out = np.empty(n * 3, dtype=np.float32)
    out[0::3] = x
    if n > 1:
        a = x[:-1]
        b = x[1:]
        out[1:-2:3] = a * _TWO_THIRDS + b * _ONE_THIRD
        out[2:-1:3] = a * _ONE_THIRD + b * _TWO_THIRDS
    last = x[-1]
    out[-2] = last * _TWO_THIRDS + last * _ONE_THIRD
    out[-1] = last * _ONE_THIRD + last * _TWO_THIRDS
    return out


class ClientSession:
    def __init__(self, addr, transport, sample_rate, jb):
        self.addr = addr
        self.ip = addr[0]
        self.transport = transport
        self.sample_rate = sample_rate
        self.jb = jb
        self.last_seen = time.monotonic()
        self.last_seq = None
        self.last_arrival = 0.0
        self.packets = 0
        self.bytes = 0


# ==============================================================================
# EVENT LOG
# ==============================================================================
class EventLog:
    def __init__(self, maxlen=400):
        self.entries = deque(maxlen=maxlen)
        self.serial = 0

    def add(self, level, msg):
        self.entries.append((time.time(), level, msg))
        self.serial += 1

    def info(self, msg):
        self.add("info", msg)

    def warn(self, msg):
        self.add("warn", msg)

    def error(self, msg):
        self.add("error", msg)

    def text(self):
        out = []
        for ts, lvl, msg in self.entries:
            out.append(f"{time.strftime('%H:%M:%S', time.localtime(ts))}  {lvl.upper():5s} {msg}")
        return "\n".join(out)


# ==============================================================================
# STATS
# ==============================================================================
class Stats:
    def __init__(self):
        self.reset_session()
        self.bitrate_kbps = 0.0
        self.packets_per_sec = 0.0
        self._rate_t = time.monotonic()
        self._rate_bytes = 0
        self._rate_packets = 0

    def reset_session(self):
        self.packets = 0
        self.bytes = 0
        self.lost = 0            # sequence gaps never filled
        self.reordered = 0
        self.ignored = 0         # packets from a second phone while locked to the first
        self.jitter_ms = 0.0
        self.stream_start = 0.0
        self.last_packet = 0.0
        self.last_arrival = 0.0
        self.last_seq = None
        self.plc_frames = 0
        self.underruns = 0       # sound-card ring starved while streaming
        self.dropped_drift = 0
        self.bitrate_kbps = 0.0
        self.packets_per_sec = 0.0
        self._rate_t = time.monotonic()
        self._rate_bytes = 0
        self._rate_packets = 0

    def tick(self, now):
        dt = now - self._rate_t
        if dt >= 1.0:
            self.bitrate_kbps = max(0, self.bytes - self._rate_bytes) * 8.0 / (dt * 1000.0)
            self.packets_per_sec = max(0, self.packets - self._rate_packets) / dt
            self._rate_t, self._rate_bytes, self._rate_packets = now, self.bytes, self.packets

    @property
    def loss_pct(self):
        total = self.packets + self.lost
        return 100.0 * self.lost / total if total else 0.0


# ==============================================================================
# JITTER BUFFER
# ==============================================================================
OK, PLC, WAIT = "ok", "plc", "wait"


class JitterBuffer:
    """Sequence-aware playout buffer: reorders, drops late/duplicate packets, signals loss, trims drift,
    and (optionally) adapts its depth to the observed network jitter."""

    MAX_AHEAD = 400            # sequence jump larger than this => the phone restarted its stream
    BURST_SLACK = 6            # backlog this far above target (stall/resync) is trimmed straight back to target
    DRIFT_WINDOW = 1.0         # standing excess is measured as the minimum depth over this many seconds
    MAX_DRIFT_DROP = 3
    HARD_CAP = 100             # never hold more than 1 s
    PREBUFFER_TIMEOUT = 0.15
    IDLE_MISSES = 25           # consecutive empty pops (250 ms) => stream considered gone
    LATE_RUN_RESTART = 8       # this many late packets in a row => sender restarted

    def __init__(self, target_ms=30, adaptive=True, clock=time.monotonic):
        self.lock = threading.Lock()
        self.clock = clock                      # injectable so tests can simulate real time
        self.adaptive = adaptive
        self.extra_frames = 8
        self.drift_correction = True
        self.set_target_ms(target_ms)
        self.late = self.dup = self.skipped_total = self.underruns = self.restarts = self.grown = 0
        self.reset()

    def set_target_ms(self, ms):
        with self.lock:
            self.base_target = max(1, int(round(ms / FRAME_MS)))
            self.target = self.base_target
            self.max_target = self.base_target + self.extra_frames

    def set_limits(self, extra_ms, drift_correction):
        with self.lock:
            self.extra_frames = max(0, int(round(extra_ms / FRAME_MS)))
            self.max_target = self.base_target + self.extra_frames
            self.target = min(self.target, self.max_target)
            self.drift_correction = bool(drift_correction)

    def reset(self):
        with self.lock:
            self.target = self.base_target
            self.frames = {}
            self.next_seq = None
            self.buffering = True
            self.prebuffer_t = self.clock()
            self.misses = 0
            self.idle = True
            self.raw_seq = 0
            self.skipped = False
            self._stable_t = self.clock()
            self._last_grow = 0.0
            self._late_run = 0
            self._miss_t = 0.0
            self._win_min = 10 ** 9
            self._win_t = self.clock()

    @property
    def depth(self):
        return len(self.frames)

    @property
    def target_ms(self):
        return self.target * FRAME_MS

    @property
    def depth_ms(self):
        return len(self.frames) * FRAME_MS

    def take_skipped(self):
        with self.lock:
            s, self.skipped = self.skipped, False
            return s

    def _restart(self, seq):
        self.frames.clear()
        self.next_seq = seq
        self.buffering = True
        self.prebuffer_t = self.clock()
        self.restarts += 1

    def _oldest(self):
        base = self.next_seq
        return min(self.frames, key=lambda s: (s - base) & MASK32)

    def push(self, seq, pcm):
        """seq=None for header-less (raw / TCP) audio."""
        with self.lock:
            now = self.clock()
            if seq is None:
                seq = self.raw_seq
                self.raw_seq = (seq + 1) & MASK32
            if self.next_seq is None:
                self.next_seq = seq
            diff = ((seq - self.next_seq + 0x80000000) & MASK32) - 0x80000000
            if diff < 0:
                self._late_run += 1
                if diff < -self.MAX_AHEAD or self._late_run >= self.LATE_RUN_RESTART:
                    self._restart(seq)                    # sender restarted its sequence numbers
                    self._late_run = 0
                else:
                    self.late += 1                        # slot already played/concealed: buffer was too shallow
                    self._deepen(now)
                    return
            else:
                self._late_run = 0
                if diff > self.MAX_AHEAD:
                    self._restart(seq)
            if self._miss_t and now - self._miss_t < 0.3:  # we ran dry and audio resumed right away => jitter, not a stop
                self._miss_t = 0.0
                self._deepen(now)
            if seq in self.frames:
                self.dup += 1
                return
            self.frames[seq] = pcm
            self.idle = False
            if len(self.frames) > self.HARD_CAP:
                old = self._oldest()
                del self.frames[old]
                self.next_seq = (old + 1) & MASK32
                self.skipped = True

    def pop(self):
        """-> (pcm | None, kind) with kind in OK / PLC (conceal this slot) / WAIT (nothing to play)."""
        with self.lock:
            now = self.clock()
            n = len(self.frames)
            if self.buffering:
                if n == 0:
                    if self.idle:
                        return None, WAIT
                    self.misses += 1                      # stream stopped (or is badly late): fade out, then go idle
                    if self.misses >= self.IDLE_MISSES:
                        self.idle = True
                    return None, (PLC if self.misses <= 3 else WAIT)
                if n >= self.target or now - self.prebuffer_t > self.PREBUFFER_TIMEOUT:
                    self.buffering = False
                    self.misses = 0
                    self._win_min, self._win_t = 10 ** 9, now
                else:
                    return None, WAIT

            self._control_depth(now)

            if self.next_seq in self.frames:
                pcm = self.frames.pop(self.next_seq)
                self.next_seq = (self.next_seq + 1) & MASK32
                self.misses = 0
                self._maybe_shrink(now)
                return pcm, OK

            if self.frames:                              # a later frame is here: the missing one is lost
                self.next_seq = (self.next_seq + 1) & MASK32
                self.misses = 0
                return None, PLC

            # nothing buffered at all: a late packet, or the stream has stopped
            self.misses = 1
            self.underruns += 1
            self._miss_t = now
            self.buffering = True                         # rebuild the cushion before resuming
            self.prebuffer_t = now
            return None, PLC

    def _drop_oldest(self, count):
        for _ in range(count):
            if not self.frames:
                break
            old = self._oldest()
            del self.frames[old]
            self.next_seq = (old + 1) & MASK32
            self.skipped = True
            self.skipped_total += 1

    def _control_depth(self, now):
        """Keep latency at the target without reacting to ordinary network bursts.
        * big backlog (stall, resync): trim straight back to target
        * small standing excess (sender clock slightly fast): the *minimum* depth over a window is the excess that
          never drained, so only that is removed - a few frames at a time."""
        depth = len(self.frames)
        if depth > self.target + self.BURST_SLACK:
            self._drop_oldest(depth - self.target)
            self._win_min, self._win_t = 10 ** 9, now
            return
        if depth < self._win_min:
            self._win_min = depth
        if now - self._win_t >= self.DRIFT_WINDOW:
            excess = self._win_min - (self.target + 1)
            if excess > 0 and self.drift_correction:
                self._drop_oldest(min(excess, self.MAX_DRIFT_DROP))
            self._win_min, self._win_t = 10 ** 9, now

    def _deepen(self, now):
        """Adaptive mode: network delivered audio later than the cushion allowed -> add one frame of cushion
        (at most every 0.5 s, up to +80 ms) and refill to the new depth."""
        self._stable_t = now
        if self.adaptive and self.target < self.max_target and now - self._last_grow > 0.5:
            self.target += 1
            self.grown += 1
            self._last_grow = now
            self.buffering = True
            self.prebuffer_t = now

    def _maybe_shrink(self, now):
        if self.adaptive and self.target > self.base_target and now - self._stable_t > 20.0:
            self.target -= 1
            self._stable_t = now


# ==============================================================================
# RING BUFFER (mono float32)
# ==============================================================================
class Ring:
    def __init__(self, capacity=SAMPLE_RATE // 4):
        self.buf = np.zeros(capacity, np.float32)
        self.cap = capacity
        self.r = 0
        self.n = 0
        self.lock = threading.Lock()
        self.overflows = 0

    def level(self):
        return self.n

    def clear(self):
        with self.lock:
            self.r = self.n = 0

    def write(self, x):
        k = len(x)
        if k == 0:
            return
        with self.lock:
            if k > self.cap:
                x, k = x[-self.cap:], self.cap
            free = self.cap - self.n
            if k > free:                          # overwrite oldest audio, keep latency bounded
                drop = k - free
                self.r = (self.r + drop) % self.cap
                self.n -= drop
                self.overflows += 1
            w = (self.r + self.n) % self.cap
            first = min(k, self.cap - w)
            self.buf[w:w + first] = x[:first]
            if first < k:
                self.buf[:k - first] = x[first:]
            self.n += k

    def read(self, k, out):
        with self.lock:
            m = min(k, self.n)
            first = min(m, self.cap - self.r)
            out[:first] = self.buf[self.r:self.r + first]
            if first < m:
                out[first:m] = self.buf[:m - first]
            self.r = (self.r + m) % self.cap
            self.n -= m
            return m


# ==============================================================================
# OUTPUT PORT (one PortAudio stream fed from a Ring by callback)
# ==============================================================================
LATENCY_MODES = {"low": "low", "medium": 0.04, "high": 0.10}
_PA_OPEN_LOCK = threading.Lock()


class OutputPort:
    def __init__(self, name, wake, sd_module, log):
        self.name = name
        self.wake = wake
        self.sd = sd_module
        self.log = log
        self.ring = Ring()
        self.stream = None
        self.device = None
        self.channels = 2
        self.latency_ms = 0.0
        self.error = ""
        self.xruns = 0
        self.starved = 0
        self.expect_audio = lambda: False
        self.channel_mode = "both"          # both | left | right
        self._tmp = np.zeros(8192, np.float32)

    @property
    def active(self):
        s = self.stream
        try:
            return bool(s is not None and s.active)
        except Exception:
            return False

    def close(self):
        s, self.stream = self.stream, None
        if s is not None:
            try:
                s.stop()
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass
        self.ring.clear()

    def open(self, dev, latency_mode="low"):
        self.close()
        self.error = ""
        self.device = dev
        if self.sd is None:
            self.error = SD_ERROR or "sounddevice is not installed"
            return False
        lat = LATENCY_MODES.get(latency_mode, "low")
        extras = [None]
        if dev is not None and "wasapi" in dev.api.lower():
            try:
                extras = [self.sd.WasapiSettings(auto_convert=True), None]
            except Exception:
                pass
        chans = [2, 1] if (dev is None or dev.channels >= 2) else [1]
        sink_name = getattr(dev, "sink_name", "") if dev is not None else ""
        last = None
        for extra in extras:
            for ch in chans:
                for blocksize, latency in ((FRAME, lat), (0, lat), (0, "high")):
                    try:
                        kw = dict(samplerate=SAMPLE_RATE, channels=ch, dtype="float32", callback=self._callback,
                                  blocksize=blocksize, latency=latency,
                                  device=None if dev is None else dev.index)
                        if extra is not None:
                            kw["extra_settings"] = extra
                        if system.IS_LINUX and getattr(self.sd, "__name__", "") != "fake_sd":
                            with _PA_OPEN_LOCK:
                                prev_pw = os.environ.get("PIPEWIRE_NODE")
                                prev_pa = os.environ.get("PULSE_SINK")
                                try:
                                    if sink_name:
                                        os.environ["PIPEWIRE_NODE"] = sink_name
                                        os.environ["PULSE_SINK"] = sink_name
                                    else:
                                        os.environ.pop("PIPEWIRE_NODE", None)
                                        os.environ.pop("PULSE_SINK", None)
                                    s = self.sd.OutputStream(**kw)
                                    s.start()
                                finally:
                                    if prev_pw is None:
                                        os.environ.pop("PIPEWIRE_NODE", None)
                                    else:
                                        os.environ["PIPEWIRE_NODE"] = prev_pw
                                    if prev_pa is None:
                                        os.environ.pop("PULSE_SINK", None)
                                    else:
                                        os.environ["PULSE_SINK"] = prev_pa
                        else:
                            s = self.sd.OutputStream(**kw)
                            s.start()
                        self.stream, self.channels = s, ch
                        try:
                            self.latency_ms = float(s.latency) * 1000.0
                        except Exception:
                            self.latency_ms = 0.0
                        return True
                    except Exception as e:      # noqa: BLE001
                        last = e
        self.error = str(last) if last else "unknown error"
        self.log.error(f"{self.name}: could not open '{dev.name if dev else 'default'}': {self.error}")
        return False

    def _callback(self, outdata, frames, time_info, status):
        try:
            if status and getattr(status, "output_underflow", False):
                self.xruns += 1
            if frames > len(self._tmp):
                self._tmp = np.zeros(frames * 2, np.float32)
            tmp = self._tmp
            got = self.ring.read(frames, tmp)
            if got < frames:
                tmp[got:frames] = 0.0
                if got == 0 and self.expect_audio():
                    self.starved += 1
            mode = self.channel_mode
            if mode == "both" or outdata.shape[1] == 1:
                outdata[:, 0] = tmp[:frames]
                if outdata.shape[1] > 1:
                    outdata[:, 1:] = tmp[:frames, None]
            else:
                outdata.fill(0)
                outdata[:, 0 if mode == "left" else 1] = tmp[:frames]
        except Exception:
            outdata.fill(0)
        self.wake.set()


# ==============================================================================
# RECORDER
# ==============================================================================
class Recorder:
    def __init__(self, log):
        self.log = log
        self.q = None
        self.thread = None
        self.path = ""
        self.frames = 0
        self.dropped = 0
        self.error = ""
        self.started = 0.0

    @property
    def active(self):
        return self.q is not None

    @property
    def size_bytes(self):
        return self.frames * 2 + 44

    @property
    def seconds(self):
        return self.frames / SAMPLE_RATE

    def start(self, folder):
        if self.active:
            return self.path
        try:
            os.makedirs(folder, exist_ok=True)
            self.path = os.path.join(folder, f"PhoneMic_{time.strftime('%Y%m%d_%H%M%S')}.wav")
            wf = wave.open(self.path, "wb")
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
        except Exception as e:      # noqa: BLE001
            self.error = str(e)
            self.log.error(f"Recording failed to start: {e}")
            return ""
        self.frames = self.dropped = 0
        self.error = ""
        self.started = time.time()
        self.q = queue.Queue(maxsize=600)
        self.thread = threading.Thread(target=self._writer, args=(wf, self.q), name="PM-WavWriter", daemon=True)
        self.thread.start()
        self.log.info(f"Recording to {self.path}")
        return self.path

    def write(self, block):
        q = self.q
        if q is None:
            return
        try:
            q.put_nowait(block)
        except queue.Full:
            self.dropped += 1

    def _writer(self, wf, q):
        part = 1
        base_path = self.path
        MAX_FRAMES_PER_FILE = 950_000_000  # ~1.9 GB in 16-bit mono PCM (under 2GB / 4GB limit)
        part_frames = 0
        try:
            while True:
                blk = q.get()
                if blk is None:
                    break
                pcm = (np.clip(blk, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
                wf.writeframes(pcm)
                self.frames += len(blk)
                part_frames += len(blk)

                # Rollover before hitting 2GB boundary
                if part_frames >= MAX_FRAMES_PER_FILE:
                    try:
                        wf.close()
                    except Exception:
                        pass
                    part += 1
                    stem, ext = os.path.splitext(base_path)
                    new_path = f"{stem}_part{part}{ext}"
                    wf = wave.open(new_path, "wb")
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(SAMPLE_RATE)
                    part_frames = 0
                    self.path = new_path
                    self.log.info(f"WAV limit approaching; rolled over to {new_path}")
        except Exception as e:      # noqa: BLE001
            self.error = str(e)
            self.log.error(f"Recording error: {e}")
        finally:
            try:
                wf.close()
            except Exception:
                pass

    def stop(self):
        q, t = self.q, self.thread
        if q is None:
            return self.path
        self.q = None
        q.put(None)
        if t is not None:
            t.join(timeout=3.0)
        self.log.info(f"Recording saved: {self.path} ({self.seconds:.1f} s)")
        return self.path


# ==============================================================================
# NETWORK SERVER
# ==============================================================================
class NetServer:
    """UDP + TCP listeners and the discovery beacon. Threads only parse and hand packets to the Receiver."""

    MAX_TCP_CLIENTS = 8

    def __init__(self, receiver):
        self.rx = receiver
        self.port = 0
        self.gen = 0
        self.udp = None
        self.tcp_server = None
        self._tcp_lock = threading.Lock()
        self._tcp_clients = {}
        self._tcp_threads = []
        self._reply_cache = {}
        self.udp_error = ""
        self.tcp_error = ""
        self.threads = []

    @property
    def tcp_client(self):
        with self._tcp_lock:
            return next(reversed(self._tcp_clients.values()), None)

    # -- lifecycle -------------------------------------------------------------------
    def start(self, port):
        self.stop()
        self.port = port
        self.gen += 1
        gen = self.gen
        self.udp_error = self.tcp_error = ""
        self._reply_cache.clear()
        self.threads = [
            threading.Thread(target=self._udp_loop, args=(gen,), name="PM-UDP", daemon=True),
            threading.Thread(target=self._tcp_loop, args=(gen,), name="PM-TCP", daemon=True),
            threading.Thread(target=self._beacon_loop, args=(gen,), name="PM-Beacon", daemon=True),
        ]
        for t in self.threads:
            t.start()

    def stop(self):
        self.gen += 1
        with self._tcp_lock:
            clients = list(self._tcp_clients.values())
            self._tcp_clients.clear()
            workers = list(self._tcp_threads)
            self._tcp_threads.clear()
        for s in (self.udp, self.tcp_server, *clients):
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        self.udp = self.tcp_server = None
        cur = threading.current_thread()
        for t in (*self.threads, *workers):
            if t is not cur:
                t.join(timeout=1.5)
        self.threads = []
        self._reply_cache.clear()

    @property
    def bind_ok(self):
        return not self.udp_error

    def _cfg(self):
        return self.rx.config.data["network"]

    def _make_socket(self, kind):
        s = socket.socket(socket.AF_INET, kind)
        if system.IS_WIN and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)   # fail loudly if the port is taken
        else:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s

    # -- UDP -------------------------------------------------------------------------
    def _udp_loop(self, gen):
        rx = self.rx
        if rx.config.data["audio"]["high_priority"]:
            system.boost_current_thread(1)
        sock = self._make_socket(socket.SOCK_DGRAM)
        if system.IS_WIN:
            try:
                sock.ioctl(SIO_UDP_CONNRESET, False)
            except Exception:
                pass
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 512 * 1024)
        except Exception:
            pass
        try:
            sock.bind(("0.0.0.0", self.port))
        except OSError as e:
            self.udp_error = f"UDP port {self.port} unavailable: {e}"
            rx.log.error(self.udp_error + " - another program (or a second PhoneMic receiver) may be using it.")
            sock.close()
            return
        sock.settimeout(0.5)
        self.udp = sock
        rx.log.info(f"Listening on UDP {self.port}")
        buf = bytearray(4096)
        while gen == self.gen:
            try:
                n, addr = sock.recvfrom_into(buf)
            except socket.timeout:
                continue
            except OSError:
                if gen != self.gen:
                    break
                time.sleep(0.01)
                continue
            try:
                self._handle_datagram(sock, buf, n, addr)
            except Exception as e:      # noqa: BLE001
                rx.log.error(f"Packet handler error: {e}")

    def _handle_datagram(self, sock, buf, n, addr):
        if n < 4:
            return
        if n >= 8:
            magic_u32, seq = struct.unpack_from(">II", buf, 0)
            sr = MAGIC_U32_TO_RATE.get(magic_u32)
            if sr is not None:
                pcm_end = n - ((n - 8) & 1)
                if pcm_end >= 10:
                    mv = memoryview(buf)
                    try:
                        pcm = bytes(mv[8:pcm_end])
                    finally:
                        mv.release()
                    self.rx.on_packet(seq, pcm, addr, "UDP", sample_rate=sr)
                return
        head_end = min(n, 32)
        if (
            buf.find(b"PMD", 0, 3) == 0
            or buf.find(DISCOVERY_PROBE, 0, head_end) != -1
            or buf.find(b"PMD0", 0, head_end) != -1
        ):
            ip = self.rx.netinfo.matching_ip(addr[0])
            reply = self._reply_cache.get(ip)
            if reply is None:
                reply = DISCOVERY_REPLY + f" {VERSION} {ip}".encode("ascii")
                self._reply_cache[ip] = reply
            sock.sendto(reply, addr)
            return
        if self._cfg()["accept_raw"] and n >= 480 and (n & 1) == 0:
            mv = memoryview(buf)
            try:
                pcm = bytes(mv[:n])
            finally:
                mv.release()
            self.rx.on_packet(None, pcm, addr, "UDP (raw)")

    # -- TCP -------------------------------------------------------------------------
    def _tcp_loop(self, gen):
        rx = self.rx
        server = self._make_socket(socket.SOCK_STREAM)
        try:
            server.bind(("0.0.0.0", self.port))
            server.listen(self.MAX_TCP_CLIENTS)
            server.settimeout(0.5)
        except OSError as e:
            self.tcp_error = f"TCP port {self.port} unavailable: {e}"
            rx.log.warn(self.tcp_error)
            server.close()
            return
        self.tcp_server = server
        while gen == self.gen:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except OSError:
                if gen != self.gen:
                    break
                continue
            with self._tcp_lock:
                self._tcp_threads = [t for t in self._tcp_threads if t.is_alive()]
                if len(self._tcp_clients) >= self.MAX_TCP_CLIENTS:
                    rx.log.warn(f"Rejecting TCP connection from {addr[0]}: client cap ({self.MAX_TCP_CLIENTS}) reached")
                    try:
                        conn.close()
                    except Exception:
                        pass
                    continue
                self._tcp_clients[addr] = conn
                worker = threading.Thread(
                    target=self._tcp_client_loop,
                    args=(gen, conn, addr),
                    name=f"PM-TCP-{addr[0]}:{addr[1]}",
                    daemon=True,
                )
                self._tcp_threads.append(worker)
            worker.start()

    def _tcp_client_loop(self, gen, conn, addr):
        rx = self.rx
        default_rate = self._cfg().get("raw_tcp_rate", 48000)
        parser = TcpStreamParser(default_rate=default_rate)
        buf = bytearray(4096)
        mv = memoryview(buf)
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.settimeout(0.5)
            rx.log.info(f"TCP connection from {addr[0]}:{addr[1]}")
            idle = 0.0
            while gen == self.gen:
                try:
                    n = conn.recv_into(buf)
                except socket.timeout:
                    idle += 0.5
                    if idle >= 2.0:
                        rx.log.warn(f"TCP client {addr[0]} timed out after {idle:.1f}s of silence")
                        break
                    continue
                if n <= 0:
                    break
                idle = 0.0
                try:
                    frames = parser.feed(mv[:n])
                except (BufferError, ValueError) as exc:
                    rx.log.warn(f"Closing invalid TCP stream from {addr[0]}: {exc}")
                    break
                for seq, frame_pcm, sr in frames:
                    rx.on_packet(seq, frame_pcm, addr, "TCP", sample_rate=sr)
        except OSError:
            pass
        finally:
            mv.release()
            with self._tcp_lock:
                if self._tcp_clients.get(addr) is conn:
                    del self._tcp_clients[addr]
            try:
                conn.close()
            except Exception:
                pass
            rx.log.info(f"TCP connection closed ({addr[0]}:{addr[1]})")

    # -- discovery beacon ------------------------------------------------------------
    def _beacon_loop(self, gen):
        rx = self.rx
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass
        beacon_cache = {}
        while gen == self.gen:
            if self._cfg()["beacon"]:
                try:
                    for ip, bcast in rx.netinfo.broadcast_targets():
                        pkt = beacon_cache.get(ip)
                        if pkt is None:
                            pkt = DISCOVERY_REPLY + f" {VERSION} {ip}".encode("ascii")
                            beacon_cache[ip] = pkt
                        try:
                            sock.sendto(pkt, (bcast, self.port))
                        except Exception:
                            pass
                    best = rx.netinfo.best_ip()
                    pkt = beacon_cache.get(best)
                    if pkt is None:
                        pkt = DISCOVERY_REPLY + f" {VERSION} {best}".encode("ascii")
                        beacon_cache[best] = pkt
                    try:
                        sock.sendto(pkt, ("255.255.255.255", self.port))
                    except Exception:
                        pass
                except Exception:
                    pass
            for _ in range(15):                       # 1.5 s, but responsive to stop()
                if gen != self.gen:
                    break
                time.sleep(0.1)
        sock.close()

    def send_control(self, cmd, addr, transport):
        sent = False
        if self.udp is not None and addr and "UDP" in transport:
            try:
                self.udp.sendto(cmd, addr)
                sent = True
            except Exception:
                pass
        with self._tcp_lock:
            conns = list(self._tcp_clients.items())
        if conns:
            locked = bool(self._cfg().get("lock_client", False))
            if locked and addr is not None:
                targets = [c for a, c in conns if a == addr] or [c for a, c in conns if a[0] == addr[0]]
            else:
                targets = [c for _, c in conns]
            for c in targets:
                try:
                    c.sendall(cmd)
                    sent = True
                except Exception:
                    pass
        return sent


# ==============================================================================
# THE RECEIVER (public facade used by GUI and CLI)
# ==============================================================================
class Receiver:
    RING_FRAMES = {"low": 1.5, "medium": 2.0, "high": 3.0}

    def __init__(self, config, sd_module="auto", netinfo=None):
        self.config = config
        self.sd = _sd if sd_module == "auto" else sd_module
        self.log = EventLog()
        self.stats = Stats()
        self.netinfo = netinfo or system.NetworkInfo()
        a = config.data["audio"]
        self.jb = JitterBuffer(a["jitter_ms"], a["adaptive_jitter"])
        self.processor = AudioProcessor(config)
        self.recorder = Recorder(self.log)
        self.net = NetServer(self)

        self.paused = False
        self.ptt_active = False           # a push-to-talk key is configured: silent unless it is held
        self.ptt_held = False
        self.hold_mute = False            # push-to-mute key is held
        self._gate_gain = 1.0
        self.monitoring = False
        self.running = False
        self.client_ip = ""
        self.client_addr = None
        self.client_sample_rate = 48000
        self._clients_lock = threading.RLock()
        self.client_streams = {}          # addr -> ClientSession for multi-device mixing
        self.transport = "UDP"
        self.tone_left = 0
        self.tone_total = 0
        self.tone_phase = 0.0

        self._wake = threading.Event()
        self.main = OutputPort("Main output", self._wake, self.sd, self.log)
        self.monitor = OutputPort("Monitor", self._wake, self.sd, self.log)
        self.main.expect_audio = self.monitor.expect_audio = lambda: not self.jb.buffering and not self.jb.idle
        self.apply_audio_settings()

        self.devices = []
        self.api = ""
        self.main_dev = None
        self.monitor_dev = None

        self._thread = None
        self._created_virtual_mic = False
        self._reset_dsp = False
        self._last_raw = None
        self._plc_run = 0
        self._after_gap = False
        self._next_block_t = 0.0
        self._health_t = 0.0
        self._dsp_loop_ms = 0.0

    # -- lifecycle -------------------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        if self.config.data["audio"]["high_priority"] and system.IS_WIN:
            try:
                import ctypes
                ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x8000)  # ABOVE_NORMAL
            except Exception:
                pass
        if (
            system.IS_LINUX
            and getattr(self.sd, "__name__", "") != "fake_sd"
            and self.config.data["audio"].get("linux_auto_virtual_mic", True)
            and virtual_mic.pactl_available()
        ):
            ok, msg, created = virtual_mic.create_virtual_mic()
            self._created_virtual_mic = bool(created)
            if ok:
                self.log.info(msg)
            else:
                self.log.warn(msg)
        self.refresh_devices(initial=True)
        self.open_main()
        self.net.start(self.config.data["network"]["port"])
        self._thread = threading.Thread(target=self._engine_loop, name="PM-Engine", daemon=True)
        self._thread.start()
        self.log.info(f"PhoneMic Receiver v{VERSION} started")

    def stop(self):
        self.running = False
        self._wake.set()
        self.recorder.stop()
        self.net.stop()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.main.close()
        self.monitor.close()
        if (
            system.IS_LINUX
            and getattr(self.sd, "__name__", "") != "fake_sd"
            and self._created_virtual_mic
            and self.config.data["audio"].get("linux_cleanup_virtual_mic", True)
        ):
            ok, msg = virtual_mic.remove_virtual_mic(session_only=True)
            self._created_virtual_mic = False
            if ok:
                self.log.info(msg)
            else:
                self.log.warn(msg)

    def ensure_virtual_mic(self):
        """Create Linux virtual mic, refresh devices, and route to it if currently unconfigured or on fallback."""
        if not system.IS_LINUX:
            return False, "Virtual microphone management via pactl is Linux-only."
        ok, msg, created = virtual_mic.create_virtual_mic()
        if created:
            self._created_virtual_mic = True
        self.refresh_devices()
        if ok:
            pool = system.devices_for_api(self.devices, self.api)
            virt = next((d for d in pool if d.is_cable), None)
            if virt and (not self.config.data["target_device_name"] or (self.main_dev and self.main_dev.is_cable)):
                self.set_output_device(virt)
            elif self.main_dev:
                self.open_main()
            self.log.info(msg)
        else:
            self.log.warn(msg)
        return ok, msg

    def remove_virtual_mic(self, session_only=False):
        """Unload Linux virtual mic modules and switch output back to default device if needed."""
        if not system.IS_LINUX:
            return False, "Virtual microphone management via pactl is Linux-only."
        was_on_virt = bool(self.main_dev and self.main_dev.is_cable)
        ok, msg = virtual_mic.remove_virtual_mic(session_only=session_only)
        if ok:
            self._created_virtual_mic = False
            if was_on_virt:
                self.config.data["target_device_name"] = None
                self.config.save_soon()
            self.refresh_devices()
            self.open_main()
            self.log.info(msg)
        else:
            self.log.warn(msg)
        return ok, msg

    # -- devices ---------------------------------------------------------------------
    def refresh_devices(self, initial=False):
        a = self.config.data["audio"]
        self.devices = system.list_output_devices(self.sd)
        self.api = system.resolve_api(self.devices, a["api"])
        cfg = self.config.data
        dev = system.find_device(self.devices, cfg["target_device_name"], self.api) if cfg["target_device_name"] else None
        self.main_dev = dev or system.pick_default_output(self.devices, self.api)
        mon = system.find_device(self.devices, cfg["monitor_device_name"], self.api) if cfg["monitor_device_name"] else None
        self.monitor_dev = mon or system.pick_default_monitor(self.devices, self.api)
        if initial:
            self.log.info(f"Audio backend: {self.api or 'none'}; output: {self.main_dev.name if self.main_dev else 'none'}")

    def open_main(self):
        ok = self.main.open(self.main_dev, self.config.data["audio"]["output_latency"])
        if ok:
            self.log.info(f"Output open: {self.main_dev.name if self.main_dev else 'default'} "
                          f"({self.main.latency_ms:.0f} ms device latency)")
        return ok

    def set_api(self, api_pref):
        self.config.data["audio"]["api"] = api_pref
        self.refresh_devices()
        self.open_main()
        if self.monitoring:
            self._open_monitor()
        self.config.save_soon()

    def set_output_device(self, dev):
        self.main_dev = dev
        self.config.data["target_device_name"] = dev.name if dev else None
        self.config.save_soon()
        self.open_main()

    def set_monitor_device(self, dev):
        self.monitor_dev = dev
        self.config.data["monitor_device_name"] = dev.name if dev else None
        self.config.save_soon()
        if self.monitoring:
            self._open_monitor()

    def set_output_latency(self, mode):
        self.config.data["audio"]["output_latency"] = mode
        self.config.save_soon()
        self.open_main()
        if self.monitoring:
            self._open_monitor()

    @property
    def stream_timeout(self):
        return float(self.config.data["network"]["stream_timeout_s"])

    def apply_audio_settings(self):
        """(Re)read the advanced audio options from the settings."""
        a = self.config.data["audio"]
        self.jb.set_limits(a["adaptive_max_ms"], a["drift_correction"])
        with self._clients_lock:
            for s in self.client_streams.values():
                if s.jb is not self.jb:
                    s.jb.set_limits(a["adaptive_max_ms"], a["drift_correction"])
        self.main.channel_mode = a["out_channels"] if a["out_channels"] in ("both", "left", "right") else "both"

    def set_jitter(self, ms, adaptive):
        a = self.config.data["audio"]
        a["jitter_ms"], a["adaptive_jitter"] = int(ms), bool(adaptive)
        self.jb.adaptive = bool(adaptive)
        self.jb.set_target_ms(ms)
        with self._clients_lock:
            for s in self.client_streams.values():
                if s.jb is not self.jb:
                    s.jb.adaptive = bool(adaptive)
                    s.jb.set_target_ms(ms)
        self.config.save_soon()

    def set_port(self, port):
        try:
            port = int(port)
            if not (1 <= port <= 65535):
                raise ValueError(f"Port {port} out of range (1-65535)")
            self.config.data["network"]["port"] = port
            self.config.save_soon()
            self.net.start(port)
            self.log.info(f"Port changed to {port}")
            return True
        except (OSError, OverflowError, ValueError) as e:
            self.log.error(f"Failed to set port to {port}: {e}")
            return False

    # -- controls --------------------------------------------------------------------
    @property
    def is_streaming(self):
        return self.stats.last_packet > 0 and (time.monotonic() - self.stats.last_packet) < self.stream_timeout

    def state(self):
        if self.net.udp_error:
            return "error"
        if self.paused:
            return "muted"
        if self.is_streaming:
            return "streaming"
        if self.stats.last_packet > 0 and self.client_ip:
            return "lost"
        return "waiting"

    def send_control(self, cmd):
        return self.net.send_control(cmd, self.client_addr, self.transport)

    def set_paused(self, paused):
        paused = bool(paused)
        if paused == self.paused:
            return paused
        self.paused = paused
        if not paused:
            self._reset_dsp = True
        self.send_control(CMD_PAUSE if paused else CMD_RESUME)
        return paused

    def toggle_pause(self):
        return self.set_paused(not self.paused)

    # ---- talk gate (push-to-talk / push-to-mute): silences the output WITHOUT telling the phone to pause --------------------
    @property
    def gate_closed(self):
        return (self.ptt_active and not self.ptt_held) or self.hold_mute

    def configure_talk_keys(self, ptt_configured):
        self.ptt_active = bool(ptt_configured)
        if not ptt_configured:
            self.ptt_held = False

    def set_ptt_held(self, held):
        self.ptt_held = bool(held)

    def set_hold_mute(self, flag):
        self.hold_mute = bool(flag)

    def _open_monitor(self):
        ok = self.monitor.open(self.monitor_dev, self.config.data["audio"]["output_latency"])
        if not ok:
            self.monitoring = False
        return ok

    def toggle_monitor(self):
        if self.monitoring:
            self.monitoring = False
            self.monitor.close()
            return False, "Monitoring off"
        if not self._open_monitor():
            return False, f"Monitor error: {self.monitor.error}"
        self.monitoring = True
        return True, "Monitoring on"

    def toggle_recording(self):
        if self.recorder.active:
            path = self.recorder.stop()
            return False, path
        folder = self.config.data["recording"]["folder"] or system.default_recordings_dir()
        path = self.recorder.start(folder)
        return bool(path), path or self.recorder.error

    def play_test_tone(self, seconds=1.2):
        self.tone_phase = 0.0
        self.tone_total = int(seconds * SAMPLE_RATE)
        self.tone_left = self.tone_total
        self._wake.set()

    def reset_stats(self):
        self.stats.reset_session()
        self.jb.late = self.jb.dup = self.jb.underruns = self.jb.grown = self.jb.skipped_total = 0
        self.main.starved = self.main.xruns = 0

    @property
    def ring_target(self):
        return int(FRAME * self.RING_FRAMES.get(self.config.data["audio"]["output_latency"], 2.0))

    def latency_estimate_ms(self):
        ring_ms = self.main.ring.level() * 1000.0 / SAMPLE_RATE
        return self.jb.depth_ms + ring_ms + self.main.latency_ms + self.processor.latency_ms

    # -- session ownership & packet ingest -----------------------------------------
    def _transfer_jb_state(self, src_jb, dst_jb):
        """Transfer frames & adaptation state from src_jb into dst_jb cleanly (called under _clients_lock)."""
        with src_jb.lock, dst_jb.lock:
            dst_jb.base_target = src_jb.base_target
            dst_jb.extra_frames = src_jb.extra_frames
            dst_jb.max_target = src_jb.max_target
            dst_jb.target = src_jb.target
            dst_jb.adaptive = src_jb.adaptive
            dst_jb.drift_correction = src_jb.drift_correction
            dst_jb.frames = dict(src_jb.frames)
            dst_jb.next_seq = src_jb.next_seq
            dst_jb.buffering = src_jb.buffering
            dst_jb.prebuffer_t = src_jb.prebuffer_t
            dst_jb.misses = src_jb.misses
            dst_jb.idle = src_jb.idle
            dst_jb.raw_seq = src_jb.raw_seq
            dst_jb.skipped = src_jb.skipped
            dst_jb._stable_t = src_jb._stable_t
            dst_jb._last_grow = src_jb._last_grow
            dst_jb._late_run = src_jb._late_run
            dst_jb._miss_t = src_jb._miss_t
            dst_jb._win_min = src_jb._win_min
            dst_jb._win_t = src_jb._win_t
            src_jb.frames.clear()
            src_jb.idle = True

    def _promote_survivor_if_needed(self, removed_session):
        """Ensure an active surviving session inherits self.jb whenever its owner is removed."""
        if removed_session.jb is not self.jb or not self.client_streams:
            return
        survivor = max(self.client_streams.values(), key=lambda s: s.last_seen)
        if survivor.jb is not self.jb:
            self._transfer_jb_state(survivor.jb, self.jb)
            survivor.jb = self.jb
        self.client_ip = survivor.ip
        self.client_addr = survivor.addr
        self.transport = survivor.transport
        self.client_sample_rate = survivor.sample_rate

    def _decode_pcm_48k(self, pcm, sample_rate):
        x = np.frombuffer(pcm, dtype="<i2").astype(np.float32) * _PCM_SCALE
        if sample_rate == 24000:
            x = upsample_2x(x)
        elif sample_rate == 16000:
            x = upsample_3x(x)
        n = len(x)
        if n < FRAME:
            padded = np.zeros(FRAME, np.float32)
            padded[:n] = x
            return padded
        if n > FRAME:
            return x[:FRAME]
        return x

    def on_packet(self, seq, pcm, addr, transport, sample_rate=48000):
        now = time.monotonic()
        st = self.stats
        ip = addr[0]
        cfg_data = self.config.data
        net_cfg = cfg_data["network"]
        audio_cfg = cfg_data["audio"]
        gap = now - st.last_packet
        alive = st.last_packet > 0 and gap < float(net_cfg["stream_timeout_s"])

        # Lock to first phone check (lock_client)
        if self.client_ip and ip != self.client_ip and alive and net_cfg["lock_client"]:
            st.ignored += 1
            if st.ignored == 1 or st.ignored % 500 == 0:
                self.log.warn(f"Ignoring audio from {ip}: already receiving from {self.client_ip}")
            return

        self.client_sample_rate = sample_rate

        with self._clients_lock:
            session = self.client_streams.get(addr)
            if session is None:
                if len(self.client_streams) >= 8:
                    oldest_addr = min(self.client_streams.keys(), key=lambda a: self.client_streams[a].last_seen)
                    if (now - self.client_streams[oldest_addr].last_seen) > 1.0:
                        removed = self.client_streams.pop(oldest_addr)
                        self._promote_survivor_if_needed(removed)
                    else:
                        st.ignored += 1
                        return
                if not any(s.jb is self.jb for s in self.client_streams.values()):
                    self.jb.reset()
                    jb = self.jb
                else:
                    jb = JitterBuffer(audio_cfg["jitter_ms"], audio_cfg["adaptive_jitter"])
                    jb.set_limits(audio_cfg["adaptive_max_ms"], audio_cfg["drift_correction"])
                session = ClientSession(addr, transport, sample_rate, jb)
                self.client_streams[addr] = session
                total = len(self.client_streams)
                if total > 1:
                    self.log.info(f"Additional phone connected: {ip} ({sample_rate // 1000}kHz) [Total: {total} devices]")
            else:
                session.sample_rate = sample_rate
                session.transport = transport
                session.last_seen = now

            is_new_primary = not alive or not self.client_ip
            if is_new_primary:
                if session.jb is self.jb:
                    self.jb.reset()
                else:
                    # Reclaim self.jb if previous primary is already idle
                    for s in self.client_streams.values():
                        if s is not session and s.jb is self.jb:
                            s.jb = JitterBuffer(audio_cfg["jitter_ms"], audio_cfg["adaptive_jitter"])
                            s.jb.set_limits(audio_cfg["adaptive_max_ms"], audio_cfg["drift_correction"])
                            self._transfer_jb_state(self.jb, s.jb)
                            break
                    session.jb.reset()
                    self._transfer_jb_state(session.jb, self.jb)
                    session.jb = self.jb

            # Single push to this session's JitterBuffer (primary session owns self.jb directly)
            session.jb.push(seq, pcm)

        # Primary client metadata & stats assignment
        if is_new_primary:
            first = st.last_packet == 0 or ip != self.client_ip
            self.client_ip, self.client_addr, self.transport = ip, addr, transport
            ignored = st.ignored
            st.reset_session()
            st.ignored = ignored
            st.stream_start = now
            self._reset_dsp = True
            self.log.info(f"{'Phone connected' if first else 'Stream resumed'}: {ip} via {transport} ({sample_rate // 1000}kHz)")
        elif ip == self.client_ip:
            self.client_addr, self.transport = addr, transport

        st.packets += 1
        st.bytes += len(pcm)
        st.last_packet = now

        # sequence accounting + RFC3550-style jitter
        if seq is not None:
            if st.last_seq is not None:
                step = (seq - st.last_seq) & MASK32
                if 1 <= step < 1000:
                    st.lost += step - 1
                    if st.last_arrival and step < 50:
                        d = (now - st.last_arrival) * 1000.0 - step * FRAME_MS
                        st.jitter_ms += (abs(d) - st.jitter_ms) / 16.0
                    st.last_seq = seq
                elif step == 0:
                    pass
                elif step > 0xFFFFF000:           # slightly older than the newest (reordered)
                    st.reordered += 1
                    st.lost = max(0, st.lost - 1)
                else:
                    st.last_seq = seq
            else:
                st.last_seq = seq
        else:
            if st.last_arrival:
                d = (now - st.last_arrival) * 1000.0 - len(pcm) * 500.0 / SAMPLE_RATE
                st.jitter_ms += (abs(d) - st.jitter_ms) / 16.0
        st.last_arrival = now

    # -- engine thread ---------------------------------------------------------------
    def _engine_loop(self):
        if self.config.data["audio"]["high_priority"]:
            system.boost_current_thread(1)
        self._next_block_t = time.monotonic()
        while self.running:
            try:
                self._wake.wait(0.02 if self.main.active else 0.004)
                self._wake.clear()
                now = time.monotonic()
                self.stats.tick(now)
                if now - self._health_t > 2.0:
                    self._health_t = now
                    self._health_check()
                t0 = time.perf_counter()
                if self.main.active:
                    guard = 0
                    while self.main.ring.level() < self.ring_target and guard < 8:
                        guard += 1
                        if not self._produce():
                            break
                else:                                   # no sound card: pace by wall clock so meters/recording still work
                    while now >= self._next_block_t:
                        if not self._produce():
                            self._next_block_t = now + 0.005
                            break
                        self._next_block_t += FRAME_MS / 1000.0
                        if now - self._next_block_t > 0.1:
                            self._next_block_t = now
                self._dsp_loop_ms = 0.9 * self._dsp_loop_ms + 0.1 * (time.perf_counter() - t0) * 1000.0
            except Exception as e:      # noqa: BLE001
                self.log.error(f"Engine error: {e!r}")
                time.sleep(0.05)

    def _health_check(self):
        """Reopen the output if the device vanished (USB headset unplugged, driver reset...)."""
        if self.sd is None or self.main_dev is None:
            return
        if not self.main.active:
            self.log.warn("Output device stopped - trying to reopen")
            self.refresh_devices()
            if not self.open_main():
                self._health_t = time.monotonic() + 8.0         # back off after a failure
        if self.monitoring and not self.monitor.active:
            if not self._open_monitor():
                self.log.warn("Monitor device unavailable - monitoring turned off")

    def _tone_block(self, n):
        """Short two-note beep (880 Hz, then 1320 Hz) with soft edges, used to verify routing."""
        if self.tone_left <= 0:
            return None
        k = min(n, self.tone_left)
        total = self.tone_total
        idx = np.arange(k)
        remaining = (self.tone_left - idx) / SAMPLE_RATE
        elapsed = (total - self.tone_left + idx) / SAMPLE_RATE
        freq = np.where(elapsed < total / SAMPLE_RATE / 2.0, 880.0, 1320.0)
        phase = self.tone_phase + 2.0 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        env = np.clip(np.minimum(elapsed, remaining) * 40.0, 0.0, 1.0)
        out = np.zeros(n, np.float32)
        out[:k] = (0.25 * env * np.sin(phase)).astype(np.float32)
        self.tone_phase = float(phase[-1]) % (2.0 * np.pi)
        self.tone_left -= k
        return out

    def _produce(self):
        """Pull one block from the jitter buffer, run the DSP chain, fan out. Returns False if there was nothing."""
        now = time.monotonic()
        cfg_data = self.config.data
        net_cfg = cfg_data["network"]
        audio_cfg = cfg_data["audio"]
        rec_cfg = cfg_data["recording"]

        with self._clients_lock:
            dead = [a for a, s in self.client_streams.items() if (now - s.last_seen) > 3.5]
            for d in dead:
                removed = self.client_streams.pop(d)
                self._promote_survivor_if_needed(removed)
            sessions = list(self.client_streams.values())

        n_sessions = len(sessions)
        multi_blocks = None
        pcm = None
        kind = WAIT

        if n_sessions > 1:
            multi_blocks = []
            primary_kind = WAIT
            for s in sessions:
                p_pcm, p_kind = s.jb.pop()
                if s.jb is self.jb:
                    primary_kind = p_kind
                if p_pcm is not None:
                    multi_blocks.append(self._decode_pcm_48k(p_pcm, s.sample_rate))
            kind = primary_kind
        else:
            # Single-session (shares self.jb) or zero sessions (fade-out/idle drain)
            pcm, kind = self.jb.pop()
            if n_sessions == 1 and pcm is not None:
                self.client_sample_rate = sessions[0].sample_rate

        tone = self._tone_block(FRAME)

        if self._reset_dsp:
            self._reset_dsp = False
            self.processor.reset()
            self._after_gap = True

        if multi_blocks:
            # Multi-device active mixing (sum or auto-duck)
            if net_cfg.get("mix_mode", "sum") == "duck":
                powers = [float(np.dot(b, b)) / len(b) for b in multi_blocks]
                max_idx = int(np.argmax(powers))
                summed = np.zeros(FRAME, dtype=np.float32)
                for idx, b in enumerate(multi_blocks):
                    weight = np.float32(1.0 if idx == max_idx or powers[max_idx] < 1e-4 else 0.25)
                    summed += b * weight
                x = np.tanh(summed * np.float32(1.1))
            else:
                summed = np.zeros(FRAME, dtype=np.float32)
                for b in multi_blocks:
                    summed += b
                x = np.tanh(summed)
            self._last_raw = x
            self._plc_run = 0
            pcm = True
            if self.jb.take_skipped():
                self._after_gap = True
        elif n_sessions > 1 and kind == WAIT:
            self._plc_run = 0
            self._last_raw = None
            self._after_gap = True
            if tone is None:
                self.processor.level_peak = 0.0
                self.processor.level_rms = 0.0
                self.processor.level_db = -80.0
                return False
            self._emit(tone, tone, tone, rec_cfg)
            return True
        elif n_sessions <= 1 and pcm is None and kind == WAIT:
            self._plc_run = 0
            self._last_raw = None
            self._after_gap = True
            if tone is None:
                self.processor.level_peak = 0.0
                self.processor.level_rms = 0.0
                self.processor.level_db = -80.0
                return False
            self._emit(tone, tone, tone, rec_cfg)
            return True

        if not multi_blocks:
            if pcm is not None:
                x = self._decode_pcm_48k(pcm, self.client_sample_rate)
                self._last_raw = x
                self._plc_run = 0
                if self.jb.take_skipped():
                    self._after_gap = True
            else:                                           # packet lost: repeat + fade the last block
                self._plc_run += 1
                self.stats.plc_frames += 1
                base = self._last_raw
                if base is None or audio_cfg["plc_mode"] == "silence" or self._plc_run > 2:
                    x = _ZERO_FRAME
                elif self._plc_run == 1:
                    ramp = _PLC_RAMP1 if len(base) == FRAME else np.linspace(0.8, 0.4, len(base), dtype=np.float32)
                    x = base * ramp
                else:
                    ramp = _PLC_RAMP2 if len(base) == FRAME else np.linspace(0.4, 0.0, len(base), dtype=np.float32)
                    x = base * ramp
                self._after_gap = True

        raw = x
        if self.paused:
            out = _ZERO_FRAME if len(x) == FRAME else np.zeros(len(x), np.float32)
            raw = out                                   # a muted microphone is not recorded either
            self.processor.level_peak = self.processor.level_rms = 0.0
            self.processor.level_db = -80.0
        else:
            if self._after_gap and pcm is not None:
                x = x.copy()
                m = min(len(x), 48)
                x[:m] *= _GAP_RAMP[:m]
                self._after_gap = False
            out = self.processor.process(x)             # keep processing while gated so the noise model stays current
            target = 0.0 if self.gate_closed else 1.0
            g0 = self._gate_gain
            if g0 != target:                            # 5 ms ramp: opening and closing never click
                m = min(len(out), 240)
                curve = np.full(len(out), target, np.float32)
                curve[:m] = np.linspace(g0, target, m + 1, dtype=np.float32)[1:]
                out = out * curve
                raw = raw * curve
                self._gate_gain = target
            elif target == 0.0:
                out = _ZERO_FRAME if len(out) == FRAME else np.zeros(len(out), np.float32)
                raw = out
            if target == 0.0 and self._gate_gain == 0.0 and not np.any(out):
                self.processor.level_peak = self.processor.level_rms = 0.0
                self.processor.level_db = -80.0
        if tone is not None and len(tone) == len(out):
            out = out + tone
        self._emit(out, raw, out, rec_cfg)
        return True

    def _emit(self, out, raw, processed, rec_cfg=None):
        self.main.ring.write(out)
        if self.monitoring:
            self.monitor.ring.write(out * np.float32(self.processor.monitor_volume))
        if self.recorder.active:
            source = rec_cfg["source"] if rec_cfg is not None else self.config.data["recording"]["source"]
            self.recorder.write(raw if source == "raw" else processed)
