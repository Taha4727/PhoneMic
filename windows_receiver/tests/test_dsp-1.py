"""DSP correctness: exact biquads, denoiser reconstruction + noise reduction, soak with random parameter changes."""
import random
import numpy as np
import _path  # noqa: F401
from phonemic import dsp

FS = 48000
rng = np.random.default_rng(3)


def reference_biquad(b0, b1, b2, a1, a2, x):
    """Plain sample-by-sample Direct Form II Transposed."""
    y = np.empty(len(x)); s1 = s2 = 0.0
    for i, xi in enumerate(x):
        yi = b0 * xi + s1
        s1 = b1 * xi - a1 * yi + s2
        s2 = b2 * xi - a2 * yi
        y[i] = yi
    return y


def test_biquads_are_exact():
    x = (rng.standard_normal(480 * 40) * 0.2).astype(np.float32)
    designs = {"hp80": lambda b: b.highpass(80.0), "lowshelf": lambda b: b.low_shelf(120.0, 9.0),
               "peak": lambda b: b.peaking(2500.0, -7.0, 2.0), "highshelf": lambda b: b.high_shelf(8000.0, 12.0)}
    for name, design in designs.items():
        b = dsp.BlockBiquad(); design(b)
        ref = reference_biquad(*b.coef, x.astype(np.float64))
        y = np.concatenate([b.process(x[i:i + 480]) for i in range(0, len(x), 480)])
        assert np.max(np.abs(y - ref)) < 2e-5, name
    # mixed block sizes must keep the filter state consistent
    b = dsp.BlockBiquad(); b.highpass(80.0)
    ref = reference_biquad(*b.coef, x.astype(np.float64))
    out, pos, sizes = [], 0, [480, 333, 480, 1000, 17]
    while pos < len(x):
        n = sizes[len(out) % len(sizes)]; out.append(b.process(x[pos:pos + n])); pos += n
    y = np.concatenate(out)
    assert np.max(np.abs(y - ref[:len(y)])) < 2e-5


def _run(fn, x, blk=480):
    return np.concatenate([fn(x[i:i + blk]) for i in range(0, len(x) - blk + 1, blk)])


def _speechlike(dur):
    t = np.arange(int(dur * FS)) / FS
    sig = sum(np.sin(2 * np.pi * 120 * h * t + h) / h ** 0.9 for h in range(1, 40) if 120 * h < 7000)
    env = np.convolve((np.sin(2 * np.pi * 1.5 * t) > -0.1).astype(float), np.ones(960) / 960, mode="same")
    sig = sig * env
    return (sig / np.sqrt(np.mean(sig[env > 0.99] ** 2)) * 0.1).astype(np.float32), env


def test_denoiser_reduces_noise_and_keeps_speech():
    clean, env = _speechlike(12.0)
    x = clean + (rng.standard_normal(len(clean)) * 0.01).astype(np.float32)
    dn = dsp.SpectralDenoiser()
    y = _run(lambda b: dn.process(b, 0.65), x)[dn.hop:]
    pause = env[:len(y)] < 0.01; speech = env[:len(y)] > 0.99
    skip = np.arange(len(y)) >= 2 * FS
    rms = lambda v: 20 * np.log10(np.sqrt(np.mean(v ** 2)) + 1e-12)
    reduction = rms(x[:len(y)][pause & skip]) - rms(y[pause & skip])
    loss = rms(x[:len(y)][speech & skip]) - rms(y[speech & skip])
    print(f"   noise reduction {reduction:.1f} dB, speech loss {loss:.2f} dB")
    assert reduction > 12 and loss < 2.0


def test_chain_soak():
    r = random.Random(2)
    p = dsp.AudioProcessor()
    p.apply_fx({**dsp.FX_BASE, "agc_enabled": True, "comp_enabled": True, "gain": 6.0})
    p.voice_changer.enabled = True
    sig = (rng.standard_normal(FS * 20) * 0.3).astype(np.float32)
    for i in range(len(sig) // 480):
        if i % 10 == 0:
            p.set_param("eq3_gain", r.uniform(-12, 12)); p.set_param("noise_cancel_amount", r.uniform(0, 1))
        if i % 400 == 0:
            p.voice_changer.mode = r.choice(dsp.VoiceChanger.MODES); p.voice_changer.pitch_semitones = r.uniform(-12, 12)
        y = p.process(sig[i * 480:(i + 1) * 480])
        assert y.shape == (480,) and np.all(np.isfinite(y)) and np.max(np.abs(y)) <= 1.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
