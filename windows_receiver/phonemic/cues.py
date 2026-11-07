"""Short audible cues (beeps) for shortcuts. Played through the Windows default sound device via winsound, so they never go
into the receiver's output (and therefore never reach other people)."""
import io
import math
import struct
import sys
import threading
import wave

IS_WIN = sys.platform.startswith("win")
RATE = 44100
_cache = {}


def make_cue_wav(kind):
    """'mute' = two falling notes, 'unmute' = two rising notes, 'on'/'off' = one note. Soft edges, so no click."""
    notes = {"mute": (784.0, 587.0), "unmute": (587.0, 784.0), "on": (880.0,), "off": (660.0,)}.get(kind, (660.0,))
    frames = bytearray()
    for f in notes:
        n = int(RATE * 0.075)
        for i in range(n):
            env = min(1.0, i / (RATE * 0.008), (n - 1 - i) / (RATE * 0.012))
            frames += struct.pack("<h", int(9000 * env * math.sin(2 * math.pi * f * i / RATE)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def play(kind):
    """Fire and forget. Does nothing off Windows."""
    if not IS_WIN:
        return False
    try:
        import winsound
    except Exception:
        return False
    data = _cache.setdefault(kind, make_cue_wav(kind))
    threading.Thread(target=lambda: _play(winsound, data), name="PM-Cue", daemon=True).start()   # SND_MEMORY cannot be async
    return True


def _play(winsound, data):
    try:
        winsound.PlaySound(data, winsound.SND_MEMORY)
    except Exception:
        pass
