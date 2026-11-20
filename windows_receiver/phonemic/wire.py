"""Zero-numpy wire-protocol framing and stream parsing helpers.

Preserves full backwards compatibility with all shipped PhoneMic Android APKs:
  * UDP: 'PM01' (48 kHz), 'PM02' (24 kHz), 'PM03' (16 kHz) + big-endian uint32 seq + 16-bit LE mono PCM
         'PM04' extended 16B header: magic(4) + seq(u32) + rate(u32) + ch(u8) + fmt(u8) + flags(u16)
  * TCP: Unframed raw 16-bit LE mono PCM (960 B @ 48 kHz, 480 B @ 24 kHz, 320 B @ 16 kHz per 10 ms),
         plus strict byte-0 dual-header auto-detection for compatible framed PM01..PM04 TCP streams.
"""
import struct

from .const import (
    FMT_BYTES_PER_SAMPLE,
    FMT_PCM_16,
    PACKET_MAGIC_16K,
    PACKET_MAGIC_24K,
    PACKET_MAGIC_48K,
    PACKET_MAGIC_EXT,
)

RAW_TCP_RATES = (48000, 24000, 16000)
RATE_TO_FRAME_BYTES = {48000: 960, 24000: 480, 16000: 320}
MAGIC_TO_RATE = {
    PACKET_MAGIC_48K: 48000,
    PACKET_MAGIC_24K: 24000,
    PACKET_MAGIC_16K: 16000,
}

MAGIC_48K_U32 = 0x504D3031  # b"PM01"
MAGIC_24K_U32 = 0x504D3032  # b"PM02"
MAGIC_16K_U32 = 0x504D3033  # b"PM03"
MAGIC_EXT_U32 = 0x504D3034  # b"PM04"
MAGIC_U32_TO_RATE = {
    MAGIC_48K_U32: 48000,
    MAGIC_24K_U32: 24000,
    MAGIC_16K_U32: 16000,
}

_PM04_STRUCT = struct.Struct(">IIIBBH")
PM04_HEADER_BYTES = _PM04_STRUCT.size  # 16 bytes
MIN_EXT_RATE = 8000
MAX_EXT_RATE = 192000

MAX_TCP_ACCUM_BYTES = 65536     # ~680 ms at 48 kHz mono; protects memory against malformed streams
TCP_HEADER_PEEK_CAP = 8192      # accommodates 2 consecutive 48 kHz stereo float32 PM04 frames (7712 B)
_MAX_FRAMED_START_SEQ = 16


def pm04_frame_bytes(sample_rate: int, channels: int, fmt_code: int) -> int:
    """Compute exact 10 ms PCM payload byte size for validated PM04 parameters, or 0 if invalid."""
    if not (MIN_EXT_RATE <= sample_rate <= MAX_EXT_RATE):
        return 0
    if channels not in (1, 2):
        return 0
    bps = FMT_BYTES_PER_SAMPLE.get(fmt_code)
    if bps is None:
        return 0
    samples = max(1, (sample_rate * 10) // 1000)
    fb = samples * channels * bps
    if fb <= 0 or (PM04_HEADER_BYTES + fb) > (MAX_TCP_ACCUM_BYTES // 2):
        return 0
    return fb


def parse_pm04_header(buf, offset: int = 0):
    """Unpack and validate a 16-byte PM04 header at offset.

    Returns (seq, sample_rate, channels, fmt_code, frame_bytes) or None if invalid.
    """
    if len(buf) - offset < PM04_HEADER_BYTES:
        return None
    magic_u32, seq, sr, ch, fmt_code, _flags = _PM04_STRUCT.unpack_from(buf, offset)
    if magic_u32 != MAGIC_EXT_U32:
        return None
    fb = pm04_frame_bytes(sr, ch, fmt_code)
    if fb <= 0:
        return None
    return seq, sr, ch, fmt_code, fb


class TcpStreamParser:
    """Per-connection stateful TCP parser supporting unframed raw PCM (48k/24k/16k)
    and optional byte-0 dual-header framed compatibility (PM01..PM04) without mid-stream false positives.
    """

    def __init__(self, default_rate=48000):
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
    def buffered_bytes(self):
        return len(self.acc) - self.pos

    def feed(self, chunk):
        """Backwards-compatible 3-tuple API: returns [(seq | None, pcm_bytes, sample_rate), ...]."""
        return [(seq, pcm, sr) for seq, pcm, sr, _, _ in self.feed_ex(chunk)]

    def feed_ex(self, chunk):
        """Append bytes/memoryview and return list of (seq | None, pcm_bytes, sample_rate, channels, fmt_code)."""
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
                    frames.append((None, bytes(mv[self.pos:end]), sr, 1, FMT_PCM_16))
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
                        parsed = parse_pm04_header(self.acc, self.pos)
                        if parsed is None:
                            raise ValueError("Invalid PM04 parameters inside framed TCP stream")
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
            if head0 == PACKET_MAGIC_EXT:
                if avail < PM04_HEADER_BYTES:
                    return
                parsed0 = parse_pm04_header(self.acc, self.pos)
                if parsed0 is None:
                    self._lock_raw()
                    return
                seq0, sr0, ch0, fmt0, fb0 = parsed0
                need = PM04_HEADER_BYTES + fb0 + PM04_HEADER_BYTES
                if avail < need:
                    if avail >= TCP_HEADER_PEEK_CAP:
                        self._lock_raw()
                    return
                parsed1 = parse_pm04_header(self.acc, self.pos + PM04_HEADER_BYTES + fb0)
                if (
                    parsed1 is not None
                    and seq0 <= _MAX_FRAMED_START_SEQ
                    and parsed1[0] == ((seq0 + 1) & 0xFFFFFFFF)
                ):
                    self.mode = "framed"
                    self.sample_rate = sr0
                    self.channels = ch0
                    self.fmt_code = fmt0
                    self.frame_bytes = fb0
                else:
                    self._lock_raw()
                return

            sr0 = MAGIC_TO_RATE.get(head0)
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
            if head1 == head0 and seq0 <= _MAX_FRAMED_START_SEQ and seq1 == ((seq0 + 1) & 0xFFFFFFFF):
                self.mode = "framed"
                self.sample_rate = sr0
                self.channels = 1
                self.fmt_code = FMT_PCM_16
                self.frame_bytes = fb0
            else:
                self._lock_raw()
        finally:
            mv.release()
