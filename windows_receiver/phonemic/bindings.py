"""Connects registry settings to the engine and the settings file. No GUI code, so it can be tested without Tk.

UI values are what the user sees (dB, Hz, percent as 0..1); stored values are what the engine uses (a linear gain factor
for "Mic gain"). `conv` in the registry describes the difference.
"""
import math

from . import settings_meta as sm, system
from .dsp import db_to_lin


class NullHooks:
    """What the GUI provides; the defaults make the binder usable in tests."""

    def notify(self, message, level="info"):
        pass

    def set_advanced(self, flag):
        pass

    def set_topmost(self, flag):
        pass

    def apply_hotkeys(self):
        pass

    def apply_tray(self):
        pass


def _close(a, b):
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or isinstance(b, str):
        return a == b
    return abs(float(a) - float(b)) <= 1e-6 + 1e-6 * abs(float(b))


class SettingsBinder:
    def __init__(self, receiver, hooks=None):
        self.rx = receiver
        self.cfg = receiver.config
        self.proc = receiver.processor
        self.hooks = hooks or NullHooks()
        self.listeners = {}        # key -> [callable(ui_value)]
        self.any_listeners = []    # callable(setting), after every change
        self.dependents = {}       # toggle key -> [callable(enabled)]

    # ---- reading ---------------------------------------------------------------------------------------------------
    def get(self, s):
        if s.target == "fx":
            v = getattr(self.proc, s.key)
            return 20.0 * math.log10(v) if s.conv == "db_lin" else v
        if s.target == "vc":
            return getattr(self.proc.voice_changer, s.key.split(".", 1)[1])
        if s.target == "sys":
            return system.get_startup_enabled() if s.key == "sys.start_with_windows" else None
        sec, name = s.key.split(".")
        return self.cfg.data[sec][name]

    def default(self, s):
        return sm.default_of(s)

    def is_default(self, s):
        d = self.default(s)
        return d is None or _close(self.get(s), d)

    def needs_met(self, s):
        return not s.needs or bool(self.get(sm.BY_KEY[s.needs]))

    # ---- writing ---------------------------------------------------------------------------------------------------
    def set(self, s, ui_value, source=None):
        """Apply a UI value. Returns True if something changed. `source` is skipped when listeners are told."""
        before = self.get(s)
        if s.target == "fx":
            v = db_to_lin(ui_value) if s.conv == "db_lin" else ui_value
            if not self.proc.set_param(s.key, v):
                return False
            self._persist_fx()
        elif s.target == "vc":
            vc = self.proc.voice_changer
            name = s.key.split(".", 1)[1]
            setattr(vc, name, bool(ui_value) if name == "enabled" else float(ui_value))
            if name != "enabled":
                vc.active_preset = "Custom"
            self.persist_voice()
        elif s.target == "sys":
            if s.key == "sys.start_with_windows" and not system.set_startup_enabled(bool(ui_value)):
                self.hooks.notify("Could not change the Windows startup entry.", "error")
                return False
        else:
            sec, name = s.key.split(".")
            current = self.cfg.data[sec][name]
            if isinstance(current, bool):
                value = bool(ui_value)
            elif isinstance(current, int):
                value = int(round(ui_value)) if not isinstance(ui_value, str) else int(ui_value)
            elif isinstance(current, float):
                value = float(ui_value)
            else:
                value = ui_value
            self.cfg.data[sec][name] = value
            self.cfg.save_soon()
            self._after_cfg(s, value)
        changed = not _close(before, self.get(s)) if before is not None else True
        self.announce(s, source)
        for fn in self.any_listeners:
            fn(s)
        if s.kind == "toggle":
            for fn in self.dependents.get(s.key, []):
                fn(bool(self.get(s)))
        return changed

    def reset(self, s, source=None):
        d = self.default(s)
        if d is not None:
            self.set(s, d, source)

    def _after_cfg(self, s, value):
        k, rx = s.key, self.rx
        if k in ("audio.adaptive_max_ms", "audio.drift_correction", "audio.out_channels"):
            rx.apply_audio_settings()
        elif k == "audio.adaptive_jitter":
            rx.set_jitter(self.cfg.data["audio"]["jitter_ms"], bool(value))
        elif k == "audio.output_latency":
            rx.set_output_latency(value)
        elif k == "app.always_on_top":
            self.hooks.set_topmost(bool(value))
        elif k == "app.advanced_mode":
            self.hooks.set_advanced(bool(value))
        elif k.startswith("hotkeys."):
            self.hooks.apply_hotkeys()
        elif k == "app.tray_icon":
            self.hooks.apply_tray()
        elif s.restart:
            self.hooks.notify("This takes effect the next time the app starts.", "info")

    # ---- persistence of the processor state -------------------------------------------------------------------------
    def _persist_fx(self):
        fx = self.cfg.data["studio_fx"]
        fx.update(self.proc.export_fx())
        fx["active_preset"] = self.proc.active_preset
        self.cfg.save_soon()

    persist_fx = _persist_fx

    def persist_voice(self):
        vc = self.proc.voice_changer
        d = self.cfg.data["voice_changer"]
        d.update(vc.export())
        d["active_preset"] = vc.active_preset
        self.cfg.save_soon()

    # ---- listeners (widgets) ------------------------------------------------------------------------------------------
    def listen(self, key, fn):
        self.listeners.setdefault(key, []).append(fn)

    def listen_any(self, fn):
        self.any_listeners.append(fn)

    def depend(self, toggle_key, fn):
        self.dependents.setdefault(toggle_key, []).append(fn)

    def announce(self, s, source=None):
        value = self.get(s)
        for fn in self.listeners.get(s.key, []):
            if fn is not source:
                fn(value)

    def sync_all(self):
        """Tell every widget to re-read its value (after a preset is applied, settings imported, ...)."""
        for key in list(self.listeners):
            self.announce(sm.BY_KEY[key])
        for toggle, fns in self.dependents.items():
            on = bool(self.get(sm.BY_KEY[toggle]))
            for fn in fns:
                fn(on)
        for fn in self.any_listeners:
            fn(None)
