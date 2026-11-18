"""Short audible cues (beeps) for shortcuts. Played through the OS default speaker device (winsound on Windows,
pw-play / paplay / aplay on Linux with sink env cleared), so cues never reach the virtual microphone."""
import io
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import wave

IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")
RATE = 44100
_cache = {}
_LINUX_PLAYERS = ("pw-play", "paplay", "aplay")


def backend_name():
    """Return active sound-cue backend name, or empty string if unavailable."""
    if IS_WIN:
        return "winsound"
    if IS_LINUX:
        for cmd in _LINUX_PLAYERS:
            if shutil.which(cmd):
                return cmd
    return ""


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


def _cue_wav_path(kind, data):
    uid = os.getuid() if hasattr(os, "getuid") else 0
    path = os.path.join(tempfile.gettempdir(), f"phonemic_cue_{kind}_{uid}.wav")
    if not os.path.isfile(path) or os.path.getsize(path) != len(data):
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    return path


def play(kind):
    """Fire and forget via OS default speaker output. Safe no-op when backend is missing."""
    data = _cache.setdefault(kind, make_cue_wav(kind))
    if IS_WIN:
        try:
            import winsound
        except Exception:
            return False
        threading.Thread(target=lambda: _play_win(winsound, data), name="PM-Cue", daemon=True).start()   # SND_MEMORY cannot be async
        return True
    if IS_LINUX:
        player = backend_name()
        if not player:
            return False
        try:
            wav_path = _cue_wav_path(kind, data)
        except OSError:
            return False
        threading.Thread(target=lambda: _play_linux(player, wav_path), name="PM-Cue", daemon=True).start()
        return True
    return False


def _play_win(winsound, data):
    try:
        winsound.PlaySound(data, winsound.SND_MEMORY)
    except Exception:
        pass


def _play_linux(player, wav_path):
    try:
        env = os.environ.copy()
        env.pop("PIPEWIRE_NODE", None)
        env.pop("PULSE_SINK", None)
        subprocess.run(
            [player, wav_path],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.5,
        )
    except Exception:
        pass
