"""Reading, writing, converting and resetting settings through the registry, without any GUI."""
import os
import tempfile
import _path  # noqa: F401
import fake_sd
from phonemic import dsp, settings_meta as sm
from phonemic.bindings import SettingsBinder, NullHooks
from phonemic.config import ConfigManager
from phonemic.engine import Receiver


class Hooks(NullHooks):
    def __init__(self):
        self.calls = []

    def notify(self, message, level="info"):
        self.calls.append(("notify", level))

    def set_advanced(self, flag):
        self.calls.append(("advanced", flag))

    def set_topmost(self, flag):
        self.calls.append(("topmost", flag))


def make():
    cfg = ConfigManager(os.path.join(tempfile.mkdtemp(), "c.json"))
    rx = Receiver(cfg, sd_module=fake_sd)
    hooks = Hooks()
    return cfg, rx, SettingsBinder(rx, hooks), hooks


def test_every_registry_setting_can_be_read_and_reset_to_its_default():
    cfg, rx, b, hooks = make()
    for s in sm.REGISTRY:
        if s.kind == "custom" or s.target == "sys":
            continue
        v = b.get(s)
        assert v is not None, s.key
        d = b.default(s)
        assert b.is_default(s), (s.key, v, d)             # a fresh install is entirely at defaults
    cfg.close()


def test_changing_and_resetting_every_setting_round_trips():
    cfg, rx, b, hooks = make()
    for s in sm.REGISTRY:
        if s.kind == "custom" or s.target == "sys" or s.key == "audio.output_latency":      # latency reopens the sound card; covered below
            continue
        if s.kind == "slider":
            probe = s.hi if abs(b.default(s) - s.hi) > 1e-9 else s.lo
        elif s.kind == "toggle":
            probe = not b.default(s)
        else:
            probe = [c[0] for c in s.choices if c[0] != b.default(s)][0]
        b.set(s, probe)
        assert not b.is_default(s), s.key
        got = b.get(s)
        if s.kind == "slider":
            assert abs(got - probe) < 1e-6 * max(1, abs(probe)) + (1e-9), (s.key, got, probe)
        else:
            assert got == probe, s.key
        b.reset(s)
        assert b.is_default(s), s.key
    cfg.close()


def test_gain_is_shown_in_db_and_stored_linear():
    cfg, rx, b, hooks = make()
    g = sm.BY_KEY["gain"]
    b.set(g, 6.0)
    assert abs(rx.processor.gain - 10 ** (6 / 20)) < 1e-9 and abs(b.get(g) - 6.0) < 1e-9
    assert abs(cfg.data["studio_fx"]["gain"] - rx.processor.gain) < 1e-12, "persisted for the next start"
    cfg.close()


def test_side_effects_reach_the_engine_and_the_window():
    cfg, rx, b, hooks = make()
    b.set(sm.BY_KEY["audio.out_channels"], "left")
    assert rx.main.channel_mode == "left"
    b.set(sm.BY_KEY["audio.adaptive_max_ms"], 30)
    assert rx.jb.max_target == rx.jb.base_target + 3
    b.set(sm.BY_KEY["audio.drift_correction"], False)
    assert rx.jb.drift_correction is False
    b.set(sm.BY_KEY["audio.adaptive_jitter"], False)
    assert rx.jb.adaptive is False
    b.set(sm.BY_KEY["app.always_on_top"], True); b.set(sm.BY_KEY["app.advanced_mode"], True)
    assert ("topmost", True) in hooks.calls and ("advanced", True) in hooks.calls
    b.set(sm.BY_KEY["app.accent"], "blue")
    assert ("notify", "info") in hooks.calls, "restart-only settings tell the user"
    b.set(sm.BY_KEY["audio.output_latency"], "medium")
    assert cfg.data["audio"]["output_latency"] == "medium" and rx.ring_target == int(480 * 2.0)
    b.set(sm.BY_KEY["app.ui_fps"], 60)
    assert cfg.data["app"]["ui_fps"] == 60 and isinstance(cfg.data["app"]["ui_fps"], int)
    cfg.close()


def test_voice_settings_mark_the_preset_as_custom():
    cfg, rx, b, hooks = make()
    rx.processor.voice_changer.load(dsp.VoiceChanger.BUILTIN_PRESETS["Deep Titan / Monster"], "Deep Titan / Monster")
    b.set(sm.BY_KEY["vc.pitch_semitones"], -7.0)
    vc = rx.processor.voice_changer
    assert vc.pitch_semitones == -7.0 and vc.active_preset == "Custom"
    assert cfg.data["voice_changer"]["pitch_semitones"] == -7.0 and cfg.data["voice_changer"]["active_preset"] == "Custom"
    b.set(sm.BY_KEY["vc.enabled"], False); assert vc.enabled is False
    cfg.close()


def test_listeners_dependencies_and_rejection_of_bad_values():
    cfg, rx, b, hooks = make()
    seen, enabled = [], []
    row_a, row_b = (lambda v: seen.append(("a", v))), (lambda v: seen.append(("b", v)))
    b.listen("gate_threshold_db", row_a); b.listen("gate_threshold_db", row_b)
    b.depend("gate_enabled", enabled.append)
    th = sm.BY_KEY["gate_threshold_db"]
    b.set(th, -42.0, source=row_a)
    assert seen == [("b", -42.0)], "the widget that made the change is not told about it"
    b.set(sm.BY_KEY["gate_enabled"], False); assert enabled == [False]
    assert not b.needs_met(th); b.set(sm.BY_KEY["gate_enabled"], True); assert b.needs_met(th)
    before = rx.processor.gate_release_ms
    assert b.set(sm.BY_KEY["gate_release_ms"], float("nan")) is False and rx.processor.gate_release_ms == before
    b.set(sm.BY_KEY["comp_ratio"], 1e9); assert rx.processor.comp_ratio == 20.0, "clamped by the engine, not trusted"
    seen.clear(); b.sync_all(); assert ("b", -42.0) in seen and enabled[-1] is True
    cfg.close()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
