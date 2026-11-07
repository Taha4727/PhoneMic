"""Preset files are untrusted input: round-trips must be exact, hostile files must be rejected or neutralised."""
import json
import _path  # noqa: F401
from phonemic import dsp, presets_io as pio


def raises(text):
    try:
        pio.parse(text)
    except pio.PresetError as e:
        return str(e)
    raise AssertionError("expected PresetError")


def test_round_trip_is_exact():
    params = dsp.fx_preset("Podcast & Streamer")
    (kind, name, back), = pio.parse(pio.dumps(pio.export_preset("fx", "My voice", params)))
    assert kind == "fx" and name == "My voice" and back == dsp.sanitize_fx(params)
    voice = dsp.VoiceChanger.BUILTIN_PRESETS["Deep Titan / Monster"]
    (kind, name, back), = pio.parse(pio.dumps(pio.export_preset("voice", "Deep", voice)))
    assert kind == "voice" and back == dsp.sanitize_voice(voice)


def test_bundle_round_trip_and_import_never_overwrites():
    fx = {"A": {"gain": 2.0}, "Podcast & Streamer": {"gain": 3.0}}
    voice = {"V": {"mode": "Helium / Chipmunk", "pitch_semitones": 5.0}}
    items = pio.parse(pio.dumps(pio.export_bundle(fx, voice)))
    assert len(items) == 3
    user_fx, user_voice = {"A": {"gain": 1.0}}, {}
    added = pio.import_items(user_fx, user_voice, items)
    assert user_fx["A"] == {"gain": 1.0}, "existing preset untouched"
    assert ("fx", "A (2)") in added and ("fx", "Podcast & Streamer (2)") in added and ("voice", "V") in added
    assert pio.unique_name("A", {"A", "A (2)"}) == "A (3)"


def test_hostile_values_are_clamped_and_unknown_keys_dropped():
    text = json.dumps({"format": "phonemic-preset", "version": 1, "kind": "fx", "name": "x\x00\x1b[31m  evil\n" + "y" * 500,
                       "params": {"gain": 1e12, "lowcut_hz": -1, "noise_quality": "rm -rf", "__class__": 1, "gate_enabled": "yes",
                                  "comp_ratio": "NaN", "eq1_gain": 99, "eq_low_freq": 300}})
    (kind, name, p), = pio.parse(text)
    assert p["gain"] == 16.0 and p["lowcut_hz"] == 20.0 and p["eq1_gain"] == 18.0 and p["eq1_freq"] == 300.0     # legacy key mapped
    assert not ({"noise_quality", "__class__", "gate_enabled", "comp_ratio"} & set(p))
    assert len(name) <= pio.MAX_NAME and "\x00" not in name and "\x1b" not in name and "\n" not in name


def test_bad_files_get_clear_messages():
    assert "valid preset" in raises("{not json")
    assert "not a PhoneMic preset" in raises("[1, 2, 3]") and "not a PhoneMic preset" in raises('{"format": "other"}')
    assert "newer version" in raises('{"format": "phonemic-preset", "version": 99, "kind": "fx", "params": {"gain": 1}}')
    assert "too large" in raises(" " * (pio.MAX_BYTES + 1))
    assert "no settings" in raises('{"format": "phonemic-preset", "version": 1, "kind": "fx", "params": 5}')
    assert "recognised" in raises('{"format": "phonemic-preset", "version": 1, "kind": "fx", "params": {"foo": 1}}')
    assert "Unknown preset type" in raises('{"format": "phonemic-preset", "version": 1, "kind": "evil", "params": {"gain": 1}}')
    assert "usable" in raises('{"format": "phonemic-preset", "version": 1, "kind": "bundle", "fx": {"a": 5}, "voice": {}}')
    assert "damaged" in raises('{"format": "phonemic-preset", "version": 1, "kind": "bundle", "fx": [], "voice": 3}')
    deep = "[" * 100000
    raises(deep)                                         # a nesting bomb must be an error, not a crash


def test_voice_values_are_validated():
    (_, _, p), = pio.parse(json.dumps({"format": "phonemic-preset", "version": 1, "kind": "voice", "name": "v",
                                       "params": {"mode": "Nope", "pitch_semitones": 99, "mix": -3, "enabled": "x"}}))
    assert p == {"pitch_semitones": 12.0, "mix": 0.0}
    vc = dsp.VoiceChanger(); vc.load({"mode": "Nope", "pitch_semitones": float("inf")})
    assert vc.mode == "Natural Pitch" and vc.pitch_semitones == 0.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
