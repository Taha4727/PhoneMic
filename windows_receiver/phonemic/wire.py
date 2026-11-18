"""Zero-numpy wire-protocol framing and stream parsing helpers.

Preserves full backwards compatibility with all shipped PhoneMic Android APKs:
  * UDP: 'PM01' (48 kHz), 'PM02' (24 kHz), 'PM03' (16 kHz) + big-endian uint32 seq + 16-bit LE mono PCM
  * TCP: Unframed raw 16-bit LE mono PCM (960 B @ 48 kHz, 480 B @ 24 kHz, 320 B @ 16 kHz per 10 ms),
         plus strict byte-0 dual-header auto-detection for compatible framed TCP streams.
"""
import struct

from .const import PACKET_MAGIC_48K, PACKET_MAGIC_24K, PACKET_MAGIC_16K

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
MAGIC_U32_TO_RATE = {
    MAGIC_48K_U32: 48000,
    MAGIC_24K_U32: 24000,
    MAGIC_16K_U32: 16000,
}

MAX_TCP_ACCUM_BYTES = 65536     # ~680 ms at 48 kHz; protects memory against malformed streams
TCP_HEADER_PEEK_CAP = 1936      # max 2 consecutive 48 kHz framed packets (8 + 960 + 8 + 960)
_MAX_FRAMED_START_SEQ = 16


class TcpStreamParser:
    """Per-connection stateful TCP parser supporting unframed raw PCM (48k/24k/16k)
    and optional byte-0 dual-header framed compatibility without mid-stream false positives.
    """

    def __init__(self, default_rate=48000):
        rate = int(default_rate) if default_rate in RATE_TO_FRAME_BYTES else 48000
        self.default_rate = rate
        self.sample_rate = rate
        self.frame_bytes = RATE_TO_FRAME_BYTES[rate]
        self.mode = "unknown"       # "unknown" -> "raw" | "framed"
        self.acc = bytearray()
        self.pos = 0

    @property
    def buffered_bytes(self):
        return len(self.acc) - self.pos

    def feed(self, chunk):
        """Append bytes/memoryview and return list of (seq | None, pcm_bytes, sample_rate)."""
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
                    frames.append((None, bytes(mv[self.pos:end]), sr))
                    self.pos = end
            finally:
                mv.release()
        elif self.mode == "framed":
            mv = memoryview(self.acc)
            try:
                while (len(self.acc) - self.pos) >= 8:
                    magic_u32, seq = struct.unpack_from(">II", self.acc, self.pos)
                    sr = MAGIC_U32_TO_RATE.get(magic_u32)
                    if sr is None:
                        raise ValueError("Invalid magic inside framed TCP stream")
                    fb = RATE_TO_FRAME_BYTES[sr]
                    if (len(self.acc) - self.pos) < 8 + fb:
                        break
                    start = self.pos + 8
                    end = start + fb
                    self.sample_rate = sr
                    self.frame_bytes = fb
                    frames.append((seq, bytes(mv[start:end]), sr))
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

    def _detect_mode(self):
        avail = len(self.acc) - self.pos
        if avail < 4:
            return
        mv = memoryview(self.acc)
        try:
            head0 = bytes(mv[self.pos:self.pos + 4])
            sr0 = MAGIC_TO_RATE.get(head0)
            if sr0 is None:
                self.mode = "raw"
                self.sample_rate = self.default_rate
                self.frame_bytes = RATE_TO_FRAME_BYTES[self.default_rate]
                return

            fb0 = RATE_TO_FRAME_BYTES[sr0]
            need = 8 + fb0 + 8
            if avail < need:
                if avail >= TCP_HEADER_PEEK_CAP:
                    self.mode = "raw"
                    self.sample_rate = self.default_rate
                    self.frame_bytes = RATE_TO_FRAME_BYTES[self.default_rate]
                return

            seq0 = struct.unpack_from(">I", self.acc, self.pos + 4)[0]
            head1_off = self.pos + 8 + fb0
            head1 = bytes(mv[head1_off:head1_off + 4])
            seq1 = struct.unpack_from(">I", self.acc, head1_off + 4)[0]
            if head1 == head0 and seq0 <= _MAX_FRAMED_START_SEQ and seq1 == ((seq0 + 1) & 0xFFFFFFFF):
                self.mode = "framed"
                self.sample_rate = sr0
                self.frame_bytes = fb0
            else:
                self.mode = "raw"
                self.sample_rate = self.default_rate
                self.frame_bytes = RATE_TO_FRAME_BYTES[self.default_rate]
        finally:
            mv.release()
