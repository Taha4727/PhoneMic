"""Every audio control added in v0.10 is checked against what it is supposed to do (analytic expectation, not just 'runs')."""
import math
import numpy as np
import _path  # noqa: F401
from phonemic import dsp

FS = 48000
rng = np.random.default_rng(11)
db = dsp.lin_to_db


def sine(freq, amp, n, phase=0.0):
    return (amp * np.sin(2 * np.pi * freq * np.arange(n) / FS + phase)).astype(np.float32)


def rms_db(x):
    return db(float(np.sqrt(np.mean(np.asarray(x, np.float64) ** 2))))


def run(fn, x, blk=480):
    return np.concatenate([fn(x[i:i + blk]) for i in range(0, len(x) - blk + 1, blk)])


def reference_biquad(b0, b1, b2, a1, a2, x):
    y = np.empty(len(x)); s1 = s2 = 0.0
    for i, xi in enumerate(x):
        yi = b0 * xi + s1; s1 = b1 * xi - a1 * yi + s2; s2 = b2 * xi - a2 * yi; y[i] = yi
    return y


# ------------------------------------------------------------------ filters
def test_new_biquad_designs_are_exact():
    x = (rng.standard_normal(480 * 20) * 0.2).astype(np.float32)
    for name, design in {"notch": lambda b: b.notch(1000, 2.0), "bandpass": lambda b: b.bandpass(6500, 1.5),
                         "lowshelf q1": lambda b: b.low_shelf(120, 6, 1.0), "highshelf q.5": lambda b: b.high_shelf(8000, -5, 0.5),
                         "peak q3": lambda b: b.peaking(500, 8, 3.0), "lowpass": lambda b: b.lowpass(10000)}.items():
        b = dsp.BlockBiquad(); design(b)
        ref = reference_biquad(*b.coef, x.astype(np.float64))
        y = np.concatenate([b.process(x[i:i + 480]) for i in range(0, len(x), 480)])
        assert np.max(np.abs(y - ref)) < 3e-5, name


def test_shelf_with_default_q_equals_the_v09_slope_one_design():
    # v0.9 used the cookbook "slope S = 1" form; S = 1 is exactly Q = 1/sqrt(2)
    def old_low_shelf(f0, g, slope=1.0):
        A = 10 ** (g / 40); w0 = 2 * math.pi * f0 / FS; c, s = math.cos(w0), math.sin(w0)
        al = (s / 2) * math.sqrt((A + 1 / A) * (1 / slope - 1) + 2); t = 2 * math.sqrt(A) * al
        b0, b1, b2 = A * ((A + 1) - (A - 1) * c + t), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - t)
        a0, a1, a2 = (A + 1) + (A - 1) * c + t, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - t
        return np.array([b0, b1, b2, a1, a2]) / np.array([a0, a0, a0, a0, a0])
    b = dsp.BlockBiquad(); b.low_shelf(120.0, 9.0)
    assert np.max(np.abs(np.array(b.coef) - old_low_shelf(120.0, 9.0))) < 1e-4


def test_eq_band_types_hit_their_target_gain():
    f = np.array([20.0, 100.0, 1000.0, 10000.0, 20000.0])
    pk = dsp.BlockBiquad(); pk.design_band("peak", 1000, 6.0, 1.0)
    r = pk.magnitude_db(f); assert abs(r[2] - 6.0) < 0.05 and abs(r[1]) < 0.7 and abs(r[3]) < 1.0
    ls = dsp.BlockBiquad(); ls.design_band("lowshelf", 120, 9.0, 0.7071)
    r = ls.magnitude_db(f); assert abs(r[0] - 9.0) < 0.5 and abs(r[3]) < 0.15
    hs = dsp.BlockBiquad(); hs.design_band("highshelf", 8000, -6.0, 0.7071)
    r = hs.magnitude_db(f); assert abs(r[4] + 6.0) < 0.8 and abs(r[1]) < 0.1
    nt = dsp.BlockBiquad(); nt.design_band("notch", 1000, 0.0, 4.0)
    r = nt.magnitude_db(f); assert r[2] < -30 and abs(r[1]) < 0.7


def test_lowcut_steepness_and_highcut_corner():
    p = dsp.AudioProcessor()
    p.apply_fx({"lowcut_hz": 100.0, "lowcut_slope": "12"})
    f = np.array([50.0, 100.0, 400.0])
    r12 = p.hp1.magnitude_db(f) + p.hp2.magnitude_db(f)
    p.apply_fx({"lowcut_hz": 100.0, "lowcut_slope": "24"})
    r24 = p.hp1.magnitude_db(f) + p.hp2.magnitude_db(f)
    assert -13.5 < r12[0] < -11.0 and -26.0 < r24[0] < -23.0, (r12, r24)       # one octave below the corner: ~-12 / ~-24 dB
    assert abs(r12[1] + 3.0) < 0.3 and abs(r24[1] + 3.0) < 0.3 and abs(r24[2]) < 0.3
    p.apply_fx({"highcut_hz": 10000.0})
    assert abs(p.lp.magnitude_db(np.array([10000.0]))[0] + 3.0) < 0.3


def test_eq_curve_follows_band_state():
    p = dsp.AudioProcessor()
    f = np.array([1000.0, 2500.0])
    assert np.allclose(p.eq_curve_db(f), 0)
    p.set_param("eq3_gain", 6.0)
    assert abs(p.eq_curve_db(np.array([2500.0]))[0] - 6.0) < 0.3
    p.set_param("eq3_on", False); assert np.allclose(p.eq_curve_db(f), 0)           # band off
    p.set_param("eq3_on", True); p.set_param("eq_enabled", False); assert np.allclose(p.eq_curve_db(f), 0)   # whole EQ off


# ------------------------------------------------------------------ gate
def test_gate_depth_attack_hold_and_hysteresis():
    quiet = np.full(480, 1e-5, np.float32)
    loud = sine(1000, 0.2, 480)
    g = dsp.NoiseGate()
    for _ in range(80): out = g.process(quiet, -50, 100, depth_db=-30.0)
    assert abs(db(g.gain) + 30.0) < 0.3, "closed gate attenuates by the requested depth"
    # attack: 20 ms attack = two 10 ms blocks to open
    g.process(loud, -50, 100, attack_ms=20.0, depth_db=-30.0)
    assert 0.40 < g.gain < 0.60, g.gain
    g.process(loud, -50, 100, attack_ms=20.0, depth_db=-30.0)
    assert g.gain == 1.0
    # hold: stays open ~hold_ms after the signal stops
    g = dsp.NoiseGate(); g.process(loud, -50, 100, hold_ms=100.0)
    for i in range(8): g.process(quiet, -50, 100, hold_ms=100.0)
    assert g.is_open
    for i in range(8): g.process(quiet, -50, 100, hold_ms=100.0)
    assert not g.is_open
    # hysteresis: a level just below the threshold does not close an open gate, a level well below does
    g = dsp.NoiseGate(); g.process(loud, -30, 100, hold_ms=0.0, hysteresis_db=6.0)
    mid = sine(1000, 10 ** (-33 / 20), 480)                                       # 3 dB under the threshold, inside the 6 dB band
    g.process(mid, -30, 100, hold_ms=0.0, hysteresis_db=6.0); assert g.is_open
    g.process(quiet, -30, 100, hold_ms=0.0, hysteresis_db=6.0); assert not g.is_open


# ------------------------------------------------------------------ dynamics
def test_compressor_static_curve_attack_release_knee_mix():
    amp = 10 ** (-10 / 20) * math.sqrt(2)                                          # -10 dBFS RMS sine
    x = sine(300, amp, 480 * 120)
    c = dsp.Compressor()
    y = run(lambda b: c.process(b, -22.0, 4.0, 0.0, 8.0, 160.0, 0.0, 1.0), x)
    assert abs(c.gr_db - 9.0) < 0.4, c.gr_db                                       # 12 dB over, 4:1 -> 9 dB reduction
    assert abs(rms_db(y[-4800:]) - (-19.0)) < 0.5
    # attack speed: one 10 ms block after a step
    for attack, expect in ((8.0, 0.71), (50.0, 0.18)):
        c = dsp.Compressor(); c.process(x[:480], -22.0, 4.0, 0.0, attack, 160.0, 0.0, 1.0)
        assert abs(c.gr_db / 9.0 - expect) < 0.06, (attack, c.gr_db)
    # release: 160 ms after the signal ends the reduction has decayed to ~37 %
    c = dsp.Compressor(); run(lambda b: c.process(b, -22.0, 4.0, 0.0, 8.0, 160.0, 0.0, 1.0), x)
    for _ in range(16): c.process(np.zeros(480, np.float32), -22.0, 4.0, 0.0, 8.0, 160.0, 0.0, 1.0)
    assert abs(c.gr_db / 9.0 - math.exp(-1)) < 0.06, c.gr_db
    # soft knee: exactly at the threshold the knee gives slope*(k/2)^2/(2k)
    x_thr = sine(300, 10 ** (-22 / 20) * math.sqrt(2), 480 * 200)
    c = dsp.Compressor(); run(lambda b: c.process(b, -22.0, 4.0, 0.0, 8.0, 160.0, 12.0, 1.0), x_thr)
    assert abs(c.gr_db - 0.75 * 36 / 24) < 0.1, c.gr_db
    # parallel mix: gain = (1-m) + m*g
    c = dsp.Compressor(); y = run(lambda b: c.process(b, -22.0, 4.0, 0.0, 8.0, 160.0, 0.0, 0.5), x)
    expect_db = db(0.5 + 0.5 * 10 ** (-9 / 20))
    assert abs((rms_db(y[-4800:]) - rms_db(x[-4800:])) - expect_db) < 0.4


def test_auto_gain_reaches_target_and_respects_max_boost():
    x = sine(400, 10 ** (-40 / 20) * math.sqrt(2), 480 * 400)                    # -40 dBFS RMS
    for max_gain, expect in ((24.0, -20.0), (10.0, -30.0)):
        a = dsp.AutoGain()
        y = run(lambda b: a.process(b, -20.0, max_gain, 120.0, 400.0), x)
        assert abs(rms_db(y[-4800:]) - expect) < 1.0, (max_gain, rms_db(y[-4800:]))
    a = dsp.AutoGain()                                                              # silence below the active threshold: gain frozen
    run(lambda b: a.process(b, -20.0, 24.0, 120.0, 400.0), np.full(480 * 50, 1e-5, np.float32))
    assert a.gain_db == 0.0


def test_deesser_only_touches_the_sibilance_band():
    sib = sine(6500, 0.1, 480 * 100)
    d = dsp.DeEsser(); y = run(lambda b: d.process(b, 6500.0, -35.0, 10.0), sib)
    assert abs((rms_db(sib[-4800:]) - rms_db(y[-4800:])) - 9.0) < 1.5               # 12 dB over at 4:1, capped by the 10 dB range
    low = sine(300, 0.3, 480 * 100)
    d = dsp.DeEsser(); y = run(lambda b: d.process(b, 6500.0, -35.0, 10.0), low)
    assert abs(rms_db(low[-4800:]) - rms_db(y[-4800:])) < 0.3                       # voice body untouched
    weak = sine(6500, 0.004, 480 * 30)
    d = dsp.DeEsser(); y = run(lambda b: d.process(b, 6500.0, -35.0, 10.0), weak)
    assert np.array_equal(y, weak[:len(y)])                                         # under the threshold: bit-exact


# ------------------------------------------------------------------ routing-independent utilities
def test_delay_is_sample_exact_and_clickless():
    d = dsp.DelayLine(); n = 480 * 6
    d.process(np.zeros(480, np.float32), 600)          # the first block after a change cross-fades; establish the delay first
    imp = np.zeros(n, np.float32); imp[100] = 1.0
    y = run(lambda b: d.process(b, 600), imp)
    assert int(np.argmax(y)) == 700 and abs(y[700] - 1.0) < 1e-6 and np.count_nonzero(y) == 1
    d = dsp.DelayLine(); s = sine(200, 0.3, 480 * 40); outs = []
    for i in range(40):
        outs.append(d.process(s[i * 480:(i + 1) * 480], 600 if i < 20 else 0))   # remove the delay mid-stream
    y = np.concatenate(outs); assert np.max(np.abs(np.diff(y))) < 0.03, "cross-fade must not click"
    assert not d.active
    assert np.array_equal(dsp.DelayLine().process(s[:480], 0), s[:480])


def test_polarity_and_bypass():
    p = dsp.AudioProcessor(); p.apply_fx(dsp.fx_preset("Pure Raw (Zero FX)")); p.set_param("invert_polarity", True)
    x = sine(300, 0.3, 480)
    assert np.allclose(p.process(x), -x, atol=1e-7)
    p = dsp.AudioProcessor(); p.apply_fx({**dsp.FX_BASE, "comp_enabled": True, "agc_enabled": True, "gain": 3.0, "deess_enabled": True})
    p.voice_changer.enabled = True
    sig = sine(300, 0.2, 480 * 30)
    for i in range(15): p.process(sig[i * 480:(i + 1) * 480])
    p.fx_bypass = True
    for i in range(15, 20):
        blk = sig[i * 480:(i + 1) * 480]; assert np.array_equal(p.process(blk), blk)          # untouched microphone
    p.fx_bypass = False
    out = np.concatenate([p.process(sig[i * 480:(i + 1) * 480]) for i in range(20, 30)])
    assert np.all(np.isfinite(out)) and np.max(np.abs(out)) <= 1.0


# ------------------------------------------------------------------ noise suppression extras
def test_noise_maximum_reduction_cap_and_learning_time():
    noise = (rng.standard_normal(FS * 8) * 0.01).astype(np.float32)
    red = {}
    for cap in (10.0, 35.0):
        dn = dsp.SpectralDenoiser(); y = run(lambda b: dn.process(b, 1.0, cap), noise)
        red[cap] = rms_db(noise[-FS * 2:]) - rms_db(y[-FS * 2:])
    assert 8.5 < red[10.0] < 12.5 and red[35.0] > red[10.0] + 6, red
    # the minimum-statistics bias follows the window length and keeps the noise estimate ~10 % above the true level
    prev = 0
    long_noise = (rng.standard_normal(FS * 12) * 0.01).astype(np.float32)        # must outlast the longest window (8 s) + warm-up
    for hist in (1.0, 2.0, 4.0, 8.0):
        dn = dsp.SpectralDenoiser(history_s=hist); assert dn.bias > prev; prev = dn.bias
        run(lambda b: dn.process(b, 0.5), long_noise[:int(FS * (hist + 3))])
        est = dn.hist[:dn.filled].min(axis=0)[5:-5].mean() * dn.bias / (0.01 ** 2 * np.sum(dn.window ** 2))
        assert 0.95 < est < 1.3, (hist, est)
    p = dsp.AudioProcessor(); p.set_param("noise_learn_s", 6.0)
    assert abs(p.denoiser.history_s - 6.0) < 1e-6


# ------------------------------------------------------------------ parameter safety
def test_sanitize_clamps_migrates_and_rejects():
    s = dsp.sanitize_fx({"gain": 1e9, "lowcut_hz": -5, "noise_quality": "bogus", "nope": 1, "gate_enabled": "yes",
                         "comp_ratio": float("nan"), "eq_low_gain_db": 4.0, "eq_mid_q": 2.0, "eq2_type": "notch", "delay_ms": 9999})
    assert s["gain"] == 16.0 and s["lowcut_hz"] == 20.0 and s["eq1_gain"] == 4.0 and s["eq3_q"] == 2.0
    assert s["eq2_type"] == "notch" and s["delay_ms"] == 500.0
    assert not {"noise_quality", "nope", "gate_enabled", "comp_ratio"} & set(s)
    p = dsp.AudioProcessor()
    assert p.set_param("gain", "loud") is False and p.gain == 1.0


def test_builtin_presets_are_valid_and_complete():
    for name, d in dsp.FX_BUILTIN_PRESETS.items():
        assert dsp.sanitize_fx(d) == dsp.migrate_fx_keys(d) or {k: v for k, v in dsp.sanitize_fx(d).items()} == {k: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v for k, v in d.items()}, name
        full = dsp.fx_preset(name); assert set(full) == set(dsp.FX_BASE), name
        p = dsp.AudioProcessor(); p.apply_fx(full); out = p.process(sine(300, 0.2, 480)); assert np.all(np.isfinite(out))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
