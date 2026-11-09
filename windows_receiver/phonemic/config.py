"""Persistent settings: typed defaults, forward/backward-compatible loading, debounced atomic saving."""
import os
import json
import copy
import time
import threading

from .const import VERSION, DEFAULT_PORT
from .dsp import FX_BASE, migrate_fx_keys, sanitize_fx, sanitize_voice
from .system import config_path

DEFAULTS = {
    "version": VERSION,
    "target_device_name": None,      # main output (kept from v0.8)
    "monitor_device_name": None,
    "visualizer_mode": "spectrum",   # spectrum | scope
    "studio_fx": {"active_preset": "Default (Studio Clean)", **FX_BASE},
    "voice_changer": {
        "enabled": False,
        "active_preset": "Normal (Bypass)",
        "mode": "Natural Pitch",
        "pitch_semitones": 0.0,
        "formant_semitones": 0.0,
        "mix": 1.0,
    },
    "network": {
        "port": DEFAULT_PORT,
        "beacon": True,              # broadcast presence so the phone can auto-detect the PC
        "lock_client": False,        # allow multiple phones to connect and mix simultaneously (can be toggled in settings)
        "mix_mode": "sum",           # "sum" (Sum & Soft Limiter) | "duck" (Auto-Duck Priority)
        "accept_raw": True,          # accept header-less PCM datagrams
        "stream_timeout_s": 1.5,     # silence for this long = "connection lost"
    },
    "audio": {
        "api": "auto",               # auto | WASAPI | DirectSound | MME
        "jitter_ms": 30,             # target playout buffer (Balanced)
        "adaptive_jitter": True,
        "output_latency": "low",     # low | medium | high  (PortAudio stream latency)
        "adaptive_max_ms": 80,       # how much extra cushion the adaptive buffer may add
        "drift_correction": True,    # trim standing excess delay caused by a slightly fast phone clock
        "plc_mode": "repeat",        # repeat (repeat + fade the last frame) | silence
        "out_channels": "both",      # both | left | right
        "high_priority": True,
    },
    "hotkeys": {
        "enabled": True,             # global shortcuts (work in any app, including games)
        "toggle_mute": "",           # e.g. "ctrl+alt+m"; empty = not set
        "push_to_talk": "",
        "push_to_mute": "",
        "toggle_monitor": "",
        "toggle_record": "",
        "toggle_bypass": "",
        "show_window": "",
        "sound_cues": False,         # beep (Windows default device) when a shortcut mutes or unmutes
    },
    "recording": {
        "folder": "",
        "source": "processed",       # processed | raw
    },
    "app": {
        "start_minimized": False,
        "always_on_top": False,
        "ui_fps": 30,
        "tray_icon": True,           # notification-area icon with quick controls (needs pystray)
        "close_to_tray": False,      # the close button hides the window instead of quitting
        "advanced_mode": False,      # show every setting, not just the essentials
        "accent": "teal",            # applied at start-up
        "first_run_done": False,
        "window_geometry": "",
    },
    "user_fx_presets": {},
    "user_voice_presets": {},
}

_REPLACE_WHOLESALE = ("user_fx_presets", "user_voice_presets")


def _coerce(default, value):
    """Return value converted to default's type, or raise ValueError if it makes no sense."""
    if default is None:
        return value
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        raise ValueError
    if isinstance(default, int) and not isinstance(default, bool):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError
        return int(value)
    if isinstance(default, float):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError
        return float(value)
    if isinstance(default, str):
        if isinstance(value, str):
            return value
        raise ValueError
    return value


def merge_into(base, saved, path=""):
    """Overlay `saved` on `base` in place, ignoring unknown keys inside typed sections and bad types."""
    for key, val in saved.items():
        if key in _REPLACE_WHOLESALE:
            if isinstance(val, dict):
                base[key] = {str(k): v for k, v in val.items() if isinstance(v, dict)}
            continue
        if key not in base:
            continue
        if isinstance(base[key], dict) and isinstance(val, dict):
            merge_into(base[key], val, f"{path}{key}.")
        else:
            try:
                base[key] = _coerce(base[key], val)
            except ValueError:
                pass


def _version_tuple(v):
    try:
        return tuple(int(x) for x in str(v).split(".")[:3])
    except Exception:
        return (0, 0, 0)


class ConfigManager:
    """Thread-safe settings store. Call save_soon() after any change; it is coalesced (0.6 s)."""

    SAVE_DELAY = 0.6

    def __init__(self, filepath=None):
        self.filepath = filepath or config_path()
        self.data = copy.deepcopy(DEFAULTS)
        self.load_error = ""
        self.migrated_from = None
        self._lock = threading.RLock()
        self._deadline = 0.0
        self._cv = threading.Condition()
        self._stop = False
        self.load()
        self._thread = threading.Thread(target=self._saver, name="PM-ConfigSaver", daemon=True)
        self._thread.start()

    # -- load / migrate ------------------------------------------------------------
    def load(self):
        try:
            if not os.path.exists(self.filepath):
                return
            with open(self.filepath, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if not isinstance(saved, dict):
                raise ValueError("config root is not an object")
            with self._lock:
                self._migrate(saved)
                merge_into(self.data, saved)
                self._sanitize()
        except Exception as e:
            self.load_error = f"Settings file unreadable ({e}); defaults used."
            try:    # keep the broken file for inspection instead of silently overwriting it
                os.replace(self.filepath, self.filepath + f".corrupt-{int(time.time())}")
            except Exception:
                pass

    def _sanitize(self):
        """Clamp/validate effect values and stored presets so a hand-edited file can't break the audio."""
        fx = self.data["studio_fx"]
        clean = sanitize_fx({k: v for k, v in fx.items() if k != "active_preset"})
        for k in FX_BASE:
            fx[k] = clean.get(k, FX_BASE[k])
        for name, p in list(self.data["user_fx_presets"].items()):
            self.data["user_fx_presets"][name] = sanitize_fx(p)
        for name, p in list(self.data["user_voice_presets"].items()):
            self.data["user_voice_presets"][name] = sanitize_voice(p)

    def _migrate(self, saved):
        old_ver = _version_tuple(saved.get("version", "0.0.0"))
        if old_ver < (0, 10, 0):
            # three fixed EQ bands -> five-band parametric EQ; people upgrading already know the app, so skip the wizard
            if isinstance(saved.get("studio_fx"), dict):
                saved["studio_fx"] = migrate_fx_keys(saved["studio_fx"])
            if isinstance(saved.get("user_fx_presets"), dict):
                saved["user_fx_presets"] = {n: migrate_fx_keys(p) for n, p in saved["user_fx_presets"].items() if isinstance(p, dict)}
            app = saved.setdefault("app", {})
            if isinstance(app, dict):
                app["first_run_done"] = True
            self.migrated_from = self.migrated_from or saved.get("version", "unknown")
        if old_ver < (0, 9, 0):
            self.migrated_from = saved.get("version", "unknown")
            fx = saved.get("studio_fx")
            if isinstance(fx, dict) and "gate_enabled" not in fx:
                # v0.8: a threshold of -80..-78 dB meant 'gate off'
                fx["gate_enabled"] = float(fx.get("gate_threshold_db", -55.0)) > -78.0
                if not fx["gate_enabled"]:
                    fx["gate_threshold_db"] = -55.0

    # -- save ----------------------------------------------------------------------
    def save(self):
        with self._lock:
            self.data["version"] = VERSION
            payload = json.dumps(self.data, indent=2)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.filepath)), exist_ok=True)
            tmp = self.filepath + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.filepath)           # atomic on Windows and POSIX
            return True
        except Exception as e:
            self.load_error = f"Could not save settings: {e}"
            return False

    def save_soon(self):
        with self._cv:
            self._deadline = time.monotonic() + self.SAVE_DELAY
            self._cv.notify()

    def _saver(self):
        while True:
            with self._cv:
                while not self._stop and self._deadline == 0.0:
                    self._cv.wait()
                if self._stop:
                    return
                remaining = self._deadline - time.monotonic()
                if remaining > 0:
                    self._cv.wait(remaining)
                    continue
                self._deadline = 0.0
            self.save()

    def flush(self):
        """Write immediately (call on exit)."""
        with self._cv:
            self._deadline = 0.0
        return self.save()

    def close(self):
        self.flush()
        with self._cv:
            self._stop = True
            self._cv.notify()

    # -- helpers -------------------------------------------------------------------
    def section(self, name):
        return self.data[name]

    def reset(self, keep_presets=True):
        with self._lock:
            keep = {k: copy.deepcopy(self.data[k]) for k in _REPLACE_WHOLESALE} if keep_presets else {}
            self.data = copy.deepcopy(DEFAULTS)
            self.data.update(keep)
        self.save_soon()
