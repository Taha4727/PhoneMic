"""Minimal stand-in for `sounddevice` so the engine can be tested without PortAudio / a sound card."""
import threading, time
import numpy as np

class _Status:
    output_underflow = False

class OutputStream:
    registry = []
    def __init__(self, samplerate, channels, dtype, callback, blocksize=0, latency="low", device=None, extra_settings=None):
        self.cb, self.ch, self.bs = callback, channels, blocksize or 480
        self.sr = samplerate; self.active = False; self.latency = 0.012
        self.captured = []; self._t = None; self.device = device
        OutputStream.registry.append(self)
    def start(self):
        self.active = True
        self._t = threading.Thread(target=self._run, daemon=True); self._t.start()
    def _run(self):
        period = self.bs / self.sr; nxt = time.perf_counter()
        while self.active:
            out = np.zeros((self.bs, self.ch), np.float32)
            self.cb(out, self.bs, None, _Status())
            self.captured.append(out[:, 0].copy())
            nxt += period; d = nxt - time.perf_counter()
            if d > 0: time.sleep(d)
            else: nxt = time.perf_counter()
    def stop(self): self.active = False
    def close(self): self.active = False

class WasapiSettings:
    def __init__(self, auto_convert=False): self.auto_convert = auto_convert

_DEVICES = [
    dict(name="Speakers (Realtek)", hostapi=0, max_output_channels=2, default_samplerate=48000.0),
    dict(name="CABLE Input (VB-Audio Virtual Cable)", hostapi=0, max_output_channels=2, default_samplerate=48000.0),
    dict(name="Speakers (Realtek)", hostapi=1, max_output_channels=2, default_samplerate=44100.0),
    dict(name="CABLE Input (VB-Audio Virtual C", hostapi=1, max_output_channels=2, default_samplerate=44100.0),
    dict(name="Microphone (Realtek)", hostapi=0, max_output_channels=0, default_samplerate=48000.0),
]
def query_devices(): return _DEVICES
def query_hostapis(): return [dict(name="Windows WASAPI", default_output_device=0), dict(name="MME", default_output_device=2)]
