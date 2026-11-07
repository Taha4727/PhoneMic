"""The settings registry drives the whole UI: it must be complete, consistent with the engine, and well written."""
import math
import _path  # noqa: F401
from phonemic import dsp, settings_meta as sm
from phonemic.config import DEFAULTS


def test_every_audio_parameter_is_listed_exactly_once():
    fx_keys = [s.key for s in sm.REGISTRY if s.target == "fx"]
    assert sorted(fx_keys) == sorted(dsp.FX_BASE), set(dsp.FX_BASE) ^ set(fx_keys)
    assert len(set(s.key for s in sm.REGISTRY)) == len(sm.REGISTRY)


def test_kinds_ranges_and_defaults_agree_with_the_engine():
    for s in sm.REGISTRY:
        d = sm.default_of(s)
        if s.target == "fx":
            base = dsp.FX_BASE[s.key]
            want = "toggle" if isinstance(base, bool) else "choice" if isinstance(base, str) else "slider"
            assert s.kind == want, s.key
            if s.kind == "slider":
                lo, hi = dsp.FX_LIMITS.get(s.key, (-1e9, 1e9))
                ui_lo, ui_hi = (10 ** (s.lo / 20), 10 ** (s.hi / 20)) if s.conv == "db_lin" else (s.lo, s.hi)
                assert lo - 1e-9 <= ui_lo and ui_hi <= hi + 1e-9, f"{s.key}: slider range exceeds the engine's hard limits"
            if s.kind == "choice":
                assert {c[0] for c in s.choices} == dsp.FX_CHOICES[s.key], s.key
        if s.kind == "slider":
            assert s.lo < s.hi and s.step > 0, s.key
            if s.target != "vc" or s.key != "vc.pitch_semitones":
                pass
            assert s.lo - 1e-9 <= d <= s.hi + 1e-9, f"{s.key}: default {d} outside {s.lo}..{s.hi}"
            for v in (s.lo, d, s.hi):
                assert sm.format_value(s.fmt, v)
        if s.kind == "choice":
            assert d in [c[0] for c in s.choices], f"{s.key}: default {d!r} not offered"
        if s.kind == "toggle" and s.target in ("fx", "cfg"):
            assert isinstance(d, bool), s.key
        if s.target == "cfg":
            sec, name = s.key.split(".")
            assert name in DEFAULTS[sec], s.key


def test_dependencies_and_stage_wiring():
    toggles = {s.key for s in sm.REGISTRY if s.kind == "toggle"}
    for s in sm.REGISTRY:
        if s.needs:
            assert s.needs in toggles, f"{s.key} needs unknown toggle {s.needs}"
    ids = {st.id for st in sm.STAGES}
    for s in sm.by_page("sound"):
        assert s.group in ids, s.key
    for st in sm.STAGES:
        if st.enable:
            assert st.enable in toggles
        for k in st.led:
            assert k in toggles
    for page, cards in sm.CARDS.items():
        used = {s.group for s in sm.by_page(page)}
        assert used <= {c[0] for c in cards}, (page, used)
    for n in range(1, dsp.EQ_BANDS + 1):
        assert {s.key for s in sm.by_group("sound", "eq") if s.key.startswith(f"eq{n}_")} == {f"eq{n}_{f}" for f in ("gain", "freq", "q", "type", "on")}


def test_writing_follows_the_house_style():
    for s in sm.REGISTRY:
        for text in (s.label, s.short, s.summary, s.details):
            assert text.isascii(), f"{s.key}: non-ASCII character in {text!r}"
            assert " \u00b7 " not in text and "->" not in text and "!" not in text, s.key
        assert s.label[0].isupper() and not s.label.isupper(), s.key
        assert s.summary.endswith(".") and len(s.summary) <= 105, f"{s.key}: summary too long or no full stop"
        assert s.details.endswith(".") and len(s.details) >= 40, s.key
        assert s.details[0].isupper() or s.details[0].isdigit() or s.details[0] == "-", s.key


def test_stated_numbers_match_the_engine():
    assert abs(dsp.SpectralDenoiser(hop=480).delay_ms - 10.0) < 1e-9 and abs(dsp.SpectralDenoiser(hop=240).delay_ms - 5.0) < 1e-9
    assert sm.BY_KEY["noise_quality"].choices[0][1].endswith("+10 ms") and sm.BY_KEY["noise_quality"].choices[1][1].endswith("+5 ms")
    vc = dsp.VoiceChanger(); vc.enabled = True; vc.pitch_semitones = 3.0
    assert vc.latency_ms == 21.0 and "21 ms" in sm.BY_KEY["vc.pitch_semitones"].details
    assert "-20 dBFS" in sm.BY_KEY["agc_target_db"].details and dsp.FX_BASE["agc_target_db"] == -20.0
    assert "-40 dB" in sm.BY_KEY["gate_depth_db"].details and dsp.FX_BASE["gate_depth_db"] == -40.0
    assert "80 Hz" in sm.BY_KEY["lowcut_hz"].details and dsp.FX_BASE["lowcut_hz"] == 80.0
    assert "65 %" in sm.BY_KEY["noise_cancel_amount"].details and dsp.FX_BASE["noise_cancel_amount"] == 0.65
    assert "-1 dBFS" in sm.BY_KEY["limiter_ceiling_db"].details and dsp.FX_BASE["limiter_ceiling_db"] == -1.0
    assert "80 ms" in sm.BY_KEY["audio.adaptive_max_ms"].details and DEFAULTS["audio"]["adaptive_max_ms"] == 80
    assert "120 ms" in sm.BY_KEY["agc_attack_ms"].details and dsp.FX_BASE["agc_attack_ms"] == 120.0


def test_search_finds_things_by_the_words_people_use():
    def keys(q, adv=True):
        return [s.key for s in sm.search(q, adv)]
    assert "lowcut_enabled" in keys("rumble") and "lowcut_hz" in keys("rumble")
    assert keys("webcam")[0] == "delay_ms"
    assert "smart_noise_cancel" in keys("hiss") and "highcut_enabled" in keys("hiss")
    assert "vc.pitch_semitones" in keys("chipmunk")
    assert keys("sibilance")[0] in ("deess_enabled", "deess_freq", "deess_threshold_db", "deess_range_db")
    assert "audio.output_device" in keys("discord") or "audio.output_device" in keys("vb-cable")
    assert "gate_hold_ms" in keys("hold") and "gate_hold_ms" not in keys("hold", adv=False)
    assert sm.search("") == [] and sm.search("zzzzqqq") == []
    assert keys("eq band 1")[:1] and all(k.startswith("eq1_") or k.startswith("eq") for k in keys("eq band 1")[:3])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
    print(len(sm.REGISTRY), "settings;", sum(s.advanced for s in sm.REGISTRY), "advanced")
