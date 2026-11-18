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


def test_denoiser_block_min_equivalence():
    # Verify B=16 +inf-padded block-min cache matches naive hist[:filled].min(axis=0)
    # bit-for-bit across aligned and non-aligned ring sizes (25, 100, 101, 200, 500 frames).
    for frames in (25, 100, 101, 200, 500):
        hist_s = (frames * dsp.FRAME) / FS
        dn = dsp.SpectralDenoiser(hop=dsp.FRAME, fs=FS, history_s=hist_s)
        assert dn.frames == frames
        n_hops = frames + 35
        sig = (rng.standard_normal(n_hops * dsp.FRAME) * 0.05).astype(np.float32)
        for i in range(n_hops):
            blk = sig[i * dsp.FRAME:(i + 1) * dsp.FRAME]
            out = dn.process(blk, 0.65)
            assert out.shape == (dsp.FRAME,) and out.dtype == np.float32
            n_b = (dn.filled + dn._BLOCK - 1) // dn._BLOCK
            cached = dn._block_mins[:n_b].min(axis=0)
            naive = dn.hist[:dn.filled].min(axis=0)
            assert np.array_equal(cached, naive), (frames, i, np.max(np.abs(cached - naive)))

    # Verify FIFO fast-path (len == hop with empty FIFOs) vs variable chunk sizes match within float32 tolerance
    # when total aligned hops complete.
    sig = (rng.standard_normal(dsp.FRAME * 60) * 0.08).astype(np.float32)
    dn_fast = dsp.SpectralDenoiser()
    y_fast = np.concatenate([dn_fast.process(sig[i:i + dsp.FRAME], 0.5) for i in range(0, len(sig), dsp.FRAME)])
    # Also ensure non-empty FIFO forces fallback cleanly on hop-sized blocks after odd chunk
    dn_var = dsp.SpectralDenoiser()
    y_var_parts = []
    pos = 0
    sizes = [17, 240, 333, 480, 1000]
    while pos < len(sig):
        step = min(sizes[len(y_var_parts) % len(sizes)], len(sig) - pos)
        y_var_parts.append(dn_var.process(sig[pos:pos + step], 0.5))
        pos += step
    y_var = np.concatenate(y_var_parts)
    assert y_fast.shape == sig.shape and y_var.shape == sig.shape
    assert np.all(np.isfinite(y_fast)) and np.all(np.isfinite(y_var))

    # Aligned multi-hop chunks [960, 480, 1440, 480] must match single-hop fast-path bit-for-bit
    sig_aligned = (rng.standard_normal(dsp.FRAME * 7) * 0.08).astype(np.float32)
    dn_a = dsp.SpectralDenoiser()
    dn_b = dsp.SpectralDenoiser()
    out_a = np.concatenate([dn_a.process(sig_aligned[i:i + dsp.FRAME], 0.5) for i in range(0, len(sig_aligned), dsp.FRAME)])
    parts_b = []
    pos = 0
    for step in (960, 480, 1440, 480):
        parts_b.append(dn_b.process(sig_aligned[pos:pos + step], 0.5))
        pos += step
    out_b = np.concatenate(parts_b)
    assert np.array_equal(out_a, out_b), np.max(np.abs(out_a - out_b))


def test_analyzer_circular_buffer_equivalence():
    an = dsp.Analyzer(FS)
    ref_buf = np.zeros(an.NFFT, np.float32)
    assert np.array_equal(an.buf, ref_buf)

    # Empty push is a no-op
    an.push(np.zeros(0, np.float32))
    assert np.array_equal(an.buf, ref_buf)

    # Push varied chunks crossing single boundary, wraparound boundary, and >= NFFT overwrite
    chunks = [
        (rng.standard_normal(480) * 0.25).astype(np.float32)
        for _ in range(12)
    ] + [
        (rng.standard_normal(333) * 0.3).astype(np.float32),
        (rng.standard_normal(2500) * 0.4).astype(np.float32),
        (rng.standard_normal(480) * 0.15).astype(np.float32),
        (rng.standard_normal(2047) * 0.2).astype(np.float32),
    ]
    for c in chunks:
        an.push(c)
        ref_buf = np.concatenate((ref_buf, c))[-an.NFFT:]
        assert an.buf.shape == (an.NFFT,)
        assert np.array_equal(an.buf, ref_buf), len(c)

        an.update()
        # Independent reference Analyzer computation on ref_buf
        spec = np.abs(np.fft.rfft(ref_buf * an.window)) / an.norm
        mx = np.maximum.reduceat(spec[:an.end], an.starts)
        db = 20.0 * np.log10(mx + 1e-9)
        ref_bands = np.clip((db - an.DB_MIN) / (an.DB_MAX - an.DB_MIN), 0.0, 1.0).astype(np.float32)
        ref_scope = ref_buf[-1024::8]
        assert np.max(np.abs(an.bands - ref_bands)) < 1e-6
        assert np.array_equal(an.scope, ref_scope)
        # Scope must be a detached copy so further pushes don't mutate snapshot
        snap = an.scope
        assert not np.shares_memory(snap, an._ring)

    # Reset clears ring, bands, and scope
    an.reset()
    assert np.all(an.buf == 0.0) and np.all(an.bands == 0.0) and np.all(an.scope == 0.0)

    # Property setter backwards compatibility
    pat = np.linspace(-0.5, 0.5, an.NFFT, dtype=np.float32)
    an.buf = pat
    assert np.allclose(an.buf, pat, atol=1e-6)


def test_dynamics_rms_dot_equivalence():
    x = (rng.standard_normal(480) * 0.2).astype(np.float32)
    ref_rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    dot_rms = float(np.sqrt(float(np.dot(x, x)) / len(x)))
    assert abs(dot_rms - ref_rms) < 1e-6, (dot_rms, ref_rms)

    # Verify AudioProcessor viz_active toggling and level_rms calculation
    p = dsp.AudioProcessor()
    p.apply_fx({**dsp.FX_BASE, "smart_noise_cancel": False, "gate_enabled": False,
                "agc_enabled": True, "comp_enabled": True, "deess_enabled": True})
    p.viz_active = False
    y1 = p.process(x)
    assert np.all(p.analyzer.buf == 0.0)
    assert abs(p.level_rms - float(np.sqrt(np.mean(y1.astype(np.float64) ** 2)))) < 1e-6
    p.viz_active = True
    y2 = p.process(x)
    assert not np.all(p.analyzer.buf == 0.0) and np.all(np.isfinite(y2))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
