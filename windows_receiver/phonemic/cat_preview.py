"""Cat voice preview WAV asset resolution, PCM/float decoding, downmix, and 48 kHz resampling."""
import io
import os
import sys
import wave
import struct
from typing import Tuple

import numpy as np

from . import system
from .cat_sound_data import get_default_cat_wav_bytes
from .const import FRAME, SAMPLE_RATE

MAX_WAV_BYTES = 32 * 1024 * 1024
MAX_PREVIEW_SECONDS = 30.0
DEFAULT_TARGET_PEAK = 0.7079  # ~ -3 dBFS headroom before user DSP / Gain / Voice Changer


def default_cat_wav_path() -> str:
    """Return the path to the bundled CC0 cat meow WAV (source tree or PyInstaller bundle)."""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "assets", "cat_meow.wav"))
    candidates.append(os.path.join(system.app_dir(), "assets", "cat_meow.wav"))
    candidates.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "cat_meow.wav"))
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return candidates[0]


def _resample_linear(x: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    n = len(x)
    if n == 0 or src_rate == dst_rate:
        return x.astype(np.float32, copy=False)
    out_len = max(1, int(round(n * (float(dst_rate) / float(src_rate)))))
    if n == 1:
        return np.full(out_len, float(x[0]), dtype=np.float32)
    xp = np.arange(n, dtype=np.float64)
    x_eval = np.linspace(0.0, float(n - 1), out_len, dtype=np.float64)
    return np.interp(x_eval, xp, x).astype(np.float32)


def _decode_ieee_float_wav_stream(stream) -> Tuple[np.ndarray, int, int]:
    """Minimal RIFF parser for uncompressed IEEE float WAV (format tag 3 / 32-bit or 64-bit)."""
    header = stream.read(12)
    if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
        raise ValueError("Not a valid RIFF/WAVE audio file.")
    fmt_tag = None
    channels = 0
    rate = 0
    bits = 0
    raw_data = None
    while True:
        ch = stream.read(8)
        if len(ch) < 8:
            break
        cid, csize = ch[:4], struct.unpack("<I", ch[4:8])[0]
        if csize > MAX_WAV_BYTES:
            raise ValueError("WAV file is too large to load for preview.")
        payload = stream.read(csize)
        if len(payload) < csize:
            break
        if csize & 1:
            stream.read(1)
        if cid == b"fmt " and len(payload) >= 16:
            fmt_tag, channels, rate, _, _, bits = struct.unpack("<HHIIHH", payload[:16])
            if fmt_tag == 0xFFFE and len(payload) >= 40:
                sub_tag = struct.unpack("<H", payload[24:26])[0]
                fmt_tag = sub_tag
        elif cid == b"data":
            raw_data = payload
            break
    if fmt_tag != 3 or raw_data is None or channels <= 0 or rate <= 0 or bits not in (32, 64):
        raise ValueError("Unsupported compressed WAV codec; please use uncompressed PCM .wav.")
    dtype = "<f4" if bits == 32 else "<f8"
    stride = channels * (bits // 8)
    usable = len(raw_data) - (len(raw_data) % stride)
    if usable < stride:
        raise ValueError("WAV file contains no audio samples.")
    arr = np.frombuffer(memoryview(raw_data)[:usable], dtype=dtype).astype(np.float32)
    return arr, channels, rate


def _decode_ieee_float_wav(path: str) -> Tuple[np.ndarray, int, int]:
    with open(path, "rb") as f:
        return _decode_ieee_float_wav_stream(f)


def _decode_wav_stream_48k_mono(raw_bytes: bytes, target_rate: int = SAMPLE_RATE, target_peak: float = DEFAULT_TARGET_PEAK) -> np.ndarray:
    """Decode uncompressed PCM or IEEE-float WAV bytes to normalized 48 kHz mono float32."""
    if not raw_bytes or len(raw_bytes) <= 44:
        raise ValueError("Selected WAV file is empty.")
    if len(raw_bytes) > MAX_WAV_BYTES:
        raise ValueError("Selected WAV file is larger than 32 MB.")

    try:
        with wave.open(io.BytesIO(raw_bytes), "rb") as wf:
            comptype = wf.getcomptype()
            if comptype != "NONE":
                raise ValueError(f"Unsupported WAV compression '{comptype}'; please use PCM .wav.")
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            rate = wf.getframerate()
            nframes = wf.getnframes()
            if channels <= 0 or rate <= 0 or nframes <= 0:
                raise ValueError("WAV file contains no audio frames.")
            max_frames = int(rate * MAX_PREVIEW_SECONDS)
            raw = wf.readframes(min(nframes, max_frames))
    except wave.Error as exc:
        if "unknown format: 3" in str(exc).lower():
            arr, channels, rate = _decode_ieee_float_wav_stream(io.BytesIO(raw_bytes))
            max_samples = int(rate * MAX_PREVIEW_SECONDS) * channels
            if len(arr) > max_samples:
                arr = arr[:max_samples]
        else:
            raise ValueError(f"Invalid or unsupported WAV file ({exc}).") from exc
    else:
        stride = channels * sampwidth
        usable = len(raw) - (len(raw) % stride)
        if usable < stride:
            raise ValueError("WAV file contains no audio samples.")
        mv = memoryview(raw)[:usable]
        if sampwidth == 1:
            arr = (np.frombuffer(mv, dtype=np.uint8).astype(np.float32) - np.float32(128.0)) / np.float32(128.0)
        elif sampwidth == 2:
            arr = np.frombuffer(mv, dtype="<i2").astype(np.float32) / np.float32(32768.0)
        elif sampwidth == 3:
            u8 = np.frombuffer(mv, dtype=np.uint8).reshape(-1, 3)
            b0 = u8[:, 0].astype(np.int32)
            b1 = u8[:, 1].astype(np.int32) << 8
            b2 = u8[:, 2].view(np.int8).astype(np.int32) << 16
            arr = (b0 | b1 | b2).astype(np.float32) / np.float32(8388608.0)
        elif sampwidth == 4:
            arr = np.frombuffer(mv, dtype="<i4").astype(np.float32) / np.float32(2147483648.0)
        else:
            raise ValueError(f"Unsupported WAV bit depth ({sampwidth * 8}-bit).")

    if channels > 1:
        even = (len(arr) // channels) * channels
        arr = arr[:even].reshape(-1, channels).mean(axis=1).astype(np.float32)

    np.nan_to_num(arr, copy=False, nan=0.0, posinf=1.0, neginf=-1.0)
    np.clip(arr, -1.0, 1.0, out=arr)

    if rate != target_rate:
        arr = _resample_linear(arr, rate, target_rate)

    if len(arr) == 0:
        raise ValueError("WAV file decoded to 0 samples.")

    peak = float(np.max(np.abs(arr)))
    if peak >= 1e-4 and (peak > target_peak or peak < 0.25):
        arr = arr * np.float32(target_peak / peak)

    # Gentle 3 ms edge ramp prevents start/stop clicks
    edge = min(144, len(arr) // 4)
    if edge > 1:
        ramp = np.linspace(0.0, 1.0, edge, dtype=np.float32)
        arr[:edge] *= ramp
        arr[-edge:] *= ramp[::-1]

    return arr.astype(np.float32, copy=False)


def load_wav_48k_mono(path: str, target_rate: int = SAMPLE_RATE, target_peak: float = DEFAULT_TARGET_PEAK) -> np.ndarray:
    """Decode an uncompressed PCM or IEEE-float WAV file to normalized 48 kHz mono float32."""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"WAV file not found: {path}")
    size = os.path.getsize(path)
    if size <= 44:
        raise ValueError("Selected WAV file is empty.")
    if size > MAX_WAV_BYTES:
        raise ValueError("Selected WAV file is larger than 32 MB.")
    with open(path, "rb") as f:
        raw_bytes = f.read(MAX_WAV_BYTES + 1)
    return _decode_wav_stream_48k_mono(raw_bytes, target_rate=target_rate, target_peak=target_peak)


def load_preview_buffer(
    custom_path: str = "",
    default_path: str = "",
    tail_pad: int = FRAME * 4,
) -> Tuple[np.ndarray, str, bool, str]:
    """Load custom cat WAV if present and valid, else bundled disk asset or embedded CC0 meow bytes.

    Returns (samples, resolved_path, is_custom, fallback_error).
    """
    fallback_error = ""
    custom = (custom_path or "").strip()
    if custom:
        try:
            buf = load_wav_48k_mono(custom)
            if tail_pad > 0:
                buf = np.concatenate((buf, np.zeros(tail_pad, dtype=np.float32)))
            return buf, custom, True, ""
        except Exception as exc:  # noqa: BLE001
            fallback_error = f"Custom cat WAV failed ({exc}); using default cat sound."

    resolved = default_path or default_cat_wav_path()
    if resolved and os.path.isfile(resolved):
        buf = load_wav_48k_mono(resolved)
    else:
        resolved = "embedded:cat_meow.wav"
        buf = _decode_wav_stream_48k_mono(get_default_cat_wav_bytes())
    if tail_pad > 0:
        buf = np.concatenate((buf, np.zeros(tail_pad, dtype=np.float32)))
    return buf, resolved, False, fallback_error
