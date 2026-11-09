"""Studio DSP chain (NumPy only).

Design rules
------------
* Everything works on float32 mono blocks of any length (normally 480 samples = 10 ms).
* No per-sample Python loops on the hot path: IIR filters use exact block matrices, the pitch shifter / echo / delay are
  vectorised, gains are applied as per-sample ramps.
* Parameters are plain attributes that the GUI thread may change at any time; filter coefficient sets are swapped
  atomically so the audio thread never sees half-updated state.
"""
import math
import time

import numpy as np

from .const import SAMPLE_RATE, FRAME

TWO_PI = 2.0 * math.pi


def db_to_lin(db):
    return 10.0 ** (db / 20.0)


def lin_to_db(x, floor=-120.0):
    return 20.0 * math.log10(x) if x > 1e-6 else floor


def _clamp_f(f0, fs):
    return min(max(float(f0), 5.0), 0.47 * fs)


# ==============================================================================
# BIQUAD (exact, block-vectorised)
# ==============================================================================
class BlockBiquad:
    """Direct-Form-II-Transposed biquad evaluated one block at a time with matrices.

    For a fixed block length N the filter is   y = T @ x + Z @ s   and   s' = Sx @ x + Ss @ s
    where T is the (lower-triangular Toeplitz) impulse-response matrix and Z/Sx/Ss are derived
    from powers of the 2x2 state matrix. This is *mathematically identical* to the sample loop
    (verified in the test-suite) but ~10x faster in pure NumPy. Blocks of a different length fall
    back to the plain recursion, so any chunk size works.
    """

    def __init__(self, block=FRAME):
        self.block = block
        self.coef = (1.0, 0.0, 0.0, 0.0, 0.0)
        self.bypass = True
        self._plan = None
        self.s = np.zeros(2)

    # -- configuration -------------------------------------------------------------
    def reset(self):
        self.s = np.zeros(2)

    def set_bypass(self):
        self.bypass = True
        self._plan = None
        self.coef = (1.0, 0.0, 0.0, 0.0, 0.0)

    def set_coeffs(self, b0, b1, b2, a0, a1, a2):
        b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
        self.coef = (b0, b1, b2, a1, a2)
        self._plan = self._build_plan(b0, b1, b2, a1, a2)
        self.bypass = False

    def _build_plan(self, b0, b1, b2, a1, a2):
        N = self.block
        p11 = np.empty(N + 1); p12 = np.empty(N + 1); p21 = np.empty(N + 1); p22 = np.empty(N + 1)
        c11, c12, c21, c22 = 1.0, 0.0, 0.0, 1.0            # A^0 = I
        for k in range(N + 1):
            p11[k], p12[k], p21[k], p22[k] = c11, c12, c21, c22
            # A^(k+1) = A @ A^k with A = [[-a1, 1], [-a2, 0]]
            c11, c12, c21, c22 = (-a1 * c11 + c21, -a1 * c12 + c22, -a2 * c11, -a2 * c12)
        v1, v2 = b1 - a1 * b0, b2 - a2 * b0
        h = np.empty(N)
        h[0] = b0
        h[1:] = p11[:N - 1] * v1 + p12[:N - 1] * v2
        idx = np.subtract.outer(np.arange(N), np.arange(N))
        T = np.where(idx >= 0, h[np.clip(idx, 0, N - 1)], 0.0)
        Z = np.stack((p11[:N], p12[:N]), axis=1)                       # N x 2
        k = N - 1 - np.arange(N)
        Sx = np.stack((p11[k] * v1 + p12[k] * v2, p21[k] * v1 + p22[k] * v2))   # 2 x N
        Ss = np.array([[p11[N], p12[N]], [p21[N], p22[N]]])
        return (T.astype(np.float32), Z, Sx, Ss, b0, b1, b2, a1, a2)      # float32 matrix: 3x faster; the state stays float64

    # -- RBJ cookbook designs -------------------------------------------------------
    def highpass(self, f0, q=0.7071, fs=SAMPLE_RATE):
        w0 = TWO_PI * _clamp_f(f0, fs) / fs
        c, s = math.cos(w0), math.sin(w0)
        al = s / (2 * q)
        self.set_coeffs((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + al, -2 * c, 1 - al)

    def lowpass(self, f0, q=0.7071, fs=SAMPLE_RATE):
        w0 = TWO_PI * _clamp_f(f0, fs) / fs
        c, s = math.cos(w0), math.sin(w0)
        al = s / (2 * q)
        self.set_coeffs((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + al, -2 * c, 1 - al)

    def bandpass(self, f0, q=1.0, fs=SAMPLE_RATE):
        """Constant 0 dB peak gain band-pass."""
        w0 = TWO_PI * _clamp_f(f0, fs) / fs
        c, s = math.cos(w0), math.sin(w0)
        al = s / (2 * q)
        self.set_coeffs(al, 0.0, -al, 1 + al, -2 * c, 1 - al)

    def notch(self, f0, q=1.0, fs=SAMPLE_RATE):
        w0 = TWO_PI * _clamp_f(f0, fs) / fs
        c, s = math.cos(w0), math.sin(w0)
        al = s / (2 * q)
        self.set_coeffs(1.0, -2 * c, 1.0, 1 + al, -2 * c, 1 - al)

    def low_shelf(self, f0, gain_db, q=0.7071, fs=SAMPLE_RATE):
        if abs(gain_db) < 0.05:
            return self.set_bypass()
        A = 10 ** (gain_db / 40.0)
        w0 = TWO_PI * _clamp_f(f0, fs) / fs
        c, s = math.cos(w0), math.sin(w0)
        t = 2 * math.sqrt(A) * (s / (2 * q))
        self.set_coeffs(A * ((A + 1) - (A - 1) * c + t), 2 * A * ((A - 1) - (A + 1) * c),
                        A * ((A + 1) - (A - 1) * c - t),
                        (A + 1) + (A - 1) * c + t, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - t)

    def high_shelf(self, f0, gain_db, q=0.7071, fs=SAMPLE_RATE):
        if abs(gain_db) < 0.05:
            return self.set_bypass()
        A = 10 ** (gain_db / 40.0)
        w0 = TWO_PI * _clamp_f(f0, fs) / fs
        c, s = math.cos(w0), math.sin(w0)
        t = 2 * math.sqrt(A) * (s / (2 * q))
        self.set_coeffs(A * ((A + 1) + (A - 1) * c + t), -2 * A * ((A - 1) + (A + 1) * c),
                        A * ((A + 1) + (A - 1) * c - t),
                        (A + 1) - (A - 1) * c + t, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - t)

    def peaking(self, f0, gain_db, q=1.0, fs=SAMPLE_RATE):
        if abs(gain_db) < 0.05:
            return self.set_bypass()
        A = 10 ** (gain_db / 40.0)
        w0 = TWO_PI * _clamp_f(f0, fs) / fs
        c, s = math.cos(w0), math.sin(w0)
        al = s / (2 * q)
        self.set_coeffs(1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A)

    def design_band(self, kind, f0, gain_db, q, fs=SAMPLE_RATE):
        """Parametric-EQ band of any supported type."""
        if kind == "lowshelf":
            self.low_shelf(f0, gain_db, q, fs)
        elif kind == "highshelf":
            self.high_shelf(f0, gain_db, q, fs)
        elif kind == "notch":
            self.notch(f0, q, fs)
        else:
            self.peaking(f0, gain_db, q, fs)

    # -- processing -----------------------------------------------------------------
    def process(self, x):
        if self.bypass:
            return x
        plan = self._plan
        s = self.s
        n = len(x)
        if n == self.block and plan is not None:
            T, Z, Sx, Ss = plan[0], plan[1], plan[2], plan[3]
            x32 = x.astype(np.float32, copy=False)
            y = T @ x32                                            # float32 product (audio is float32 anyway)
            y += (Z @ s).astype(np.float32)
            s = Sx @ x32.astype(np.float64) + Ss @ s
        else:                                   # odd-sized block: exact recursion
            b0, b1, b2, a1, a2 = self.coef
            s1, s2 = float(s[0]), float(s[1])
            out = [0.0] * n
            for i, xi in enumerate(x.tolist()):
                yi = b0 * xi + s1
                s1 = b1 * xi - a1 * yi + s2
                s2 = b2 * xi - a2 * yi
                out[i] = yi
            y = np.asarray(out)
            s = np.array((s1, s2))
        if not (np.isfinite(s[0]) and np.isfinite(s[1])) or abs(s[0]) > 1e6:
            s = np.zeros(2)
            y = np.nan_to_num(y)
        self.s = s
        return y.astype(np.float32, copy=False)

    def magnitude_db(self, freqs, fs=SAMPLE_RATE):
        """Frequency response (dB) at `freqs` - used by the GUI to draw the EQ curve."""
        if self.bypass:
            return np.zeros(len(freqs))
        b0, b1, b2, a1, a2 = self.coef
        z1 = np.exp(-1j * TWO_PI * np.asarray(freqs) / fs)
        z2 = z1 * z1
        h = (b0 + b1 * z1 + b2 * z2) / (1.0 + a1 * z1 + a2 * z2)
        return 20.0 * np.log10(np.maximum(np.abs(h), 1e-6))


# ==============================================================================
# SPECTRAL NOISE SUPPRESSION
# ==============================================================================
class SpectralDenoiser:
    """Streaming STFT noise suppressor.

    * 50 % overlap, sine window (Princen-Bradley => perfect reconstruction at unity gain)
    * noise floor = per-bin minimum of the smoothed power spectrum over `history_s` seconds (minimum statistics)
    * decision-directed a-priori SNR (Ephraim-Malah) -> Wiener gain, which avoids "musical noise"
    * 3-tap frequency smoothing of the gain mask
    Works with arbitrary input chunk sizes; algorithmic delay is exactly one hop.
    """
    ALPHA = 0.90        # decision-directed smoothing

    def __init__(self, hop=FRAME, fs=SAMPLE_RATE, history_s=2.0):
        self.hop = hop
        self.win = 2 * hop
        self.nb = hop + 1
        n = np.arange(self.win)
        self.window = np.sin(np.pi * (n + 0.5) / self.win).astype(np.float32)
        self.history_s = float(history_s)
        self.frames = max(16, int(self.history_s * fs / hop))
        # The minimum of N noisy estimates is biased low by a factor that grows with N (calibrated empirically,
        # with ~10 % safety margin so that the noise floor is never under-estimated).
        self.bias = 1.1 * (0.529 + 0.307 * math.log(self.frames * hop / FRAME))
        self.reset()

    def reset(self):
        self.in_fifo = np.zeros(0, np.float32)
        self.out_fifo = np.zeros(0, np.float32)
        self.prev = np.zeros(self.hop, np.float32)
        self.tail = np.zeros(self.hop, np.float32)
        self.hist = np.full((self.frames, self.nb), np.inf, np.float32)
        self.pos = 0
        self.filled = 0
        self.ps = None
        self.g_prev = np.ones(self.nb, np.float32)
        self.gamma_prev = np.ones(self.nb, np.float32)

    @property
    def delay_ms(self):
        return 1000.0 * self.hop / SAMPLE_RATE

    def _hop(self, x, amount, max_red_db):
        frame = np.concatenate((self.prev, x))
        self.prev = x
        X = np.fft.rfft(frame * self.window)
        P = (X.real * X.real + X.imag * X.imag).astype(np.float32)

        # --- noise floor tracking (minimum statistics) ---------------------------------
        self.ps = P.copy() if self.ps is None else 0.85 * self.ps + 0.15 * P
        self.hist[self.pos] = self.ps
        self.pos = (self.pos + 1) % self.frames
        self.filled = min(self.frames, self.filled + 1)
        noise = self.hist[:self.filled].min(axis=0) * self.bias
        noise = noise * (1.0 + 1.5 * amount) + 1e-12

        # --- gain ---------------------------------------------------------------------------
        gamma = P / noise
        xi = self.ALPHA * (self.g_prev * self.g_prev * self.gamma_prev) + (1 - self.ALPHA) * np.maximum(gamma - 1.0, 0.0)
        g = xi / (1.0 + xi)
        reduction_db = max_red_db if max_red_db > 0.0 else (6.0 + 24.0 * amount)     # 0 = follow the strength slider
        g = np.maximum(g, 10.0 ** (-reduction_db / 20.0))
        gs = g.copy()
        gs[1:-1] = 0.25 * g[:-2] + 0.5 * g[1:-1] + 0.25 * g[2:]
        self.g_prev = gs.astype(np.float32)
        self.gamma_prev = gamma.astype(np.float32)

        y = np.fft.irfft(X * gs, n=self.win).astype(np.float32) * self.window
        out = y[:self.hop] + self.tail
        self.tail = y[self.hop:]
        return out

    def process(self, samples, amount, max_reduction_db=0.0):
        n = len(samples)
        self.in_fifo = np.concatenate((self.in_fifo, samples.astype(np.float32, copy=False)))
        produced = []
        while len(self.in_fifo) >= self.hop:
            produced.append(self._hop(self.in_fifo[:self.hop], amount, max_reduction_db))
            self.in_fifo = self.in_fifo[self.hop:]
        if produced:
            self.out_fifo = np.concatenate([self.out_fifo] + produced)
        if len(self.out_fifo) < n:
            # Only happens when chunk sizes are not multiples of the hop (e.g. header-less raw PCM). Pad once with
            # enough cushion that it can never happen again - costs at most one extra hop of latency, no mid-stream gaps.
            pad = n - len(self.out_fifo) + self.hop
            self.out_fifo = np.concatenate((np.zeros(pad, np.float32), self.out_fifo))
        out = self.out_fifo[:n]
        self.out_fifo = self.out_fifo[n:]
        return out


# ==============================================================================
# DYNAMICS
# ==============================================================================
def _ramp(g0, g1, n):
    """Per-sample linear gain ramp from g0 (exclusive) to g1 (inclusive) over n samples."""
    return g0 + (g1 - g0) * (np.arange(1, n + 1, dtype=np.float32) / n)


def _smooth(current, target, block_ms, tau_ms):
    return current + (target - current) * (1.0 - math.exp(-block_ms / max(tau_ms, 0.1)))


class NoiseGate:
    """Gate with hysteresis, hold, attack and release. Each phase is configurable; defaults open within 2 ms."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.gain = 1.0
        self.is_open = True
        self.hold_left = 0.0

    def process(self, x, threshold_db, release_ms, attack_ms=2.0, hold_ms=60.0, depth_db=-40.0, hysteresis_db=3.0):
        n = len(x)
        if n == 0:
            return x
        floor = db_to_lin(min(depth_db, -1.0))
        block_ms = 1000.0 * n / SAMPLE_RATE
        level = lin_to_db(float(np.max(np.abs(x))))
        if level >= threshold_db:
            self.is_open, self.hold_left = True, hold_ms
        elif level < threshold_db - hysteresis_db:
            if self.hold_left > 0:
                self.hold_left -= block_ms
            else:
                self.is_open = False
        g0 = self.gain
        span = 1.0 - floor
        if self.is_open:
            if g0 >= 0.9999:
                self.gain = 1.0
                return x
            slope = span / max(1.0, attack_ms * SAMPLE_RATE / 1000.0)           # gain per sample
            curve = np.minimum(1.0, g0 + slope * np.arange(1, n + 1, dtype=np.float32))
            self.gain = float(curve[-1])
        else:
            if g0 <= floor + 1e-6:
                self.gain = floor
                return x * np.float32(floor)
            slope = span / max(1.0, release_ms * SAMPLE_RATE / 1000.0)
            curve = np.maximum(floor, g0 - slope * np.arange(1, n + 1, dtype=np.float32))
            self.gain = float(curve[-1])
        return x * curve.astype(np.float32)


class AutoGain:
    """Slow level rider: brings speech to a target RMS, frozen while the signal is below the noise floor."""
    ACTIVE_DB = -52.0
    MIN_GAIN_DB = -12.0

    def __init__(self):
        self.reset()

    def reset(self):
        self.gain_db = 0.0

    def process(self, x, target_db, max_gain_db=24.0, attack_ms=120.0, release_ms=900.0):
        n = len(x)
        if n == 0:
            return x
        block_ms = 1000.0 * n / SAMPLE_RATE
        rms = float(np.sqrt(np.mean(x * x)))
        peak = float(np.max(np.abs(x)))
        lvl = lin_to_db(rms)
        g0 = self.gain_db
        if lvl > self.ACTIVE_DB:
            desired = min(max(target_db - lvl, self.MIN_GAIN_DB), max_gain_db)
            desired = min(desired, -1.5 - lin_to_db(peak))          # never push peaks into clipping
            g1 = _smooth(g0, desired, block_ms, attack_ms if desired < g0 else release_ms)
        else:
            g1 = min(g0, max_gain_db)
        self.gain_db = g1
        if abs(g1 - g0) < 1e-4:
            return x * np.float32(db_to_lin(g1)) if abs(g1) > 0.01 else x
        return x * _ramp(db_to_lin(g0), db_to_lin(g1), n)


class Compressor:
    """Soft-knee feed-forward RMS compressor (block detector, per-sample gain ramps)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.gr_db = 0.0
        self.makeup_db = 0.0
        self.mix = 1.0

    def process(self, x, threshold_db, ratio, makeup_db, attack_ms=8.0, release_ms=160.0, knee_db=6.0, mix=1.0):
        n = len(x)
        if n == 0:
            return x
        block_ms = 1000.0 * n / SAMPLE_RATE
        lvl = lin_to_db(float(np.sqrt(np.mean(x * x))))
        over = lvl - threshold_db
        slope = 1.0 - 1.0 / max(ratio, 1.0)
        k = max(knee_db, 0.0)
        if over <= -k / 2:
            target = 0.0
        elif over >= k / 2 or k < 1e-6:
            target = max(0.0, over) * slope
        else:
            target = slope * (over + k / 2) ** 2 / (2 * k)
        gr1 = _smooth(self.gr_db, target, block_ms, attack_ms if target > self.gr_db else release_ms)
        # parallel compression: blend the compressed gain with unity; make-up is applied to the blend
        g0 = db_to_lin(self.makeup_db) * ((1.0 - self.mix) + self.mix * db_to_lin(-self.gr_db))
        g1 = db_to_lin(makeup_db) * ((1.0 - mix) + mix * db_to_lin(-gr1))
        self.gr_db, self.makeup_db, self.mix = gr1, makeup_db, mix
        if abs(g1 - 1.0) < 1e-4 and abs(g0 - 1.0) < 1e-4:
            return x
        return x * _ramp(g0, g1, n)


class DeEsser:
    """Split-band de-esser: only the sibilance band is turned down when it exceeds the threshold."""

    def __init__(self):
        self.bp = BlockBiquad()
        self._freq = None
        self.reset()

    def reset(self):
        self.bp.reset()
        self.gr_db = 0.0

    def process(self, x, freq, threshold_db, range_db):
        n = len(x)
        if n == 0:
            return x
        if freq != self._freq:
            self.bp.bandpass(freq, 1.5)
            self._freq = freq
        band = self.bp.process(x)
        block_ms = 1000.0 * n / SAMPLE_RATE
        over = lin_to_db(float(np.sqrt(np.mean(band * band)))) - threshold_db
        target = min(range_db, over * 0.75) if over > 0 else 0.0           # 4:1 above the threshold, capped by the range
        gr1 = _smooth(self.gr_db, target, block_ms, 3.0 if target > self.gr_db else 60.0)
        g0, g1 = db_to_lin(-self.gr_db), db_to_lin(-gr1)
        self.gr_db = gr1
        if self.gr_db < 0.05 and abs(g0 - 1.0) < 0.006:
            return x
        return x - (1.0 - _ramp(g0, g1, n)) * band


class DelayLine:
    """Fixed delay (lip-sync). Changing the delay cross-fades, so it never clicks."""
    MAX_S = 0.6

    def __init__(self):
        self.size = int(SAMPLE_RATE * self.MAX_S) + 4096
        self.reset()

    def reset(self):
        self.buf = np.zeros(self.size, np.float32)
        self.w = 0
        self.cur = 0

    @property
    def active(self):
        return self.cur > 0

    def process(self, x, delay_samples):
        n = len(x)
        d = int(min(max(delay_samples, 0), self.size - n - 1))
        if d == 0 and self.cur == 0:
            return x
        idx = (self.w + np.arange(n)) % self.size
        self.buf[idx] = x
        new = self.buf[(idx - d) % self.size]
        if d == self.cur:
            out = new
        else:                                           # linear cross-fade from the old tap to the new tap over this block
            old = self.buf[(idx - self.cur) % self.size]
            t = np.arange(1, n + 1, dtype=np.float32) / n
            out = old * (1.0 - t) + new * t
        self.cur = d
        self.w = (self.w + n) % self.size
        return out.astype(np.float32, copy=False)


def soft_limit(x, ceiling):
    """Transparent below 80 % of the ceiling, smooth tanh saturation above it. Returns (y, clipped)."""
    a = np.abs(x)
    knee = 0.8 * ceiling
    if float(a.max(initial=0.0)) <= knee:
        return x, False
    over = a > knee
    y = x.copy()
    span = ceiling - knee
    y[over] = np.sign(x[over]) * (knee + span * np.tanh((a[over] - knee) / span))
    return y, bool(float(a.max()) >= 1.0)


# ==============================================================================
# VOICE CHANGER
# ==============================================================================
class SmoothHarmonizer:
    """Synchronised dual-tap pitch shifter with 4-point cubic Hermite interpolation.

    Uses complementary raised-cosine grains (w1 + w2 = 1.0) with an optimal 30 ms (1440 sample)
    vocal window. Because grains do not overlap statically, there is zero comb-filtering
    and no robotic metallic ringing. Hermite interpolation eliminates high-frequency loss.
    """

    def __init__(self, size=8192, window=1440, base_delay=720):
        self.size, self.window, self.base_delay = size, window, base_delay
        self.reset()

    def reset(self):
        self.buf = np.zeros(self.size, dtype=np.float32)
        self.w = 0
        self.phase = 0.0

    def process(self, x, semitones):
        if abs(semitones) < 0.15:
            return x
        n = len(x)
        if n > self.base_delay:                      # keep reads strictly behind writes
            return np.concatenate([self.process(x[i:i + self.base_delay], semitones)
                                   for i in range(0, n, self.base_delay)])
        size = self.size
        T = float(self.window)
        delta = 1.0 - 2.0 ** (semitones / 12.0)
        i = np.arange(n, dtype=np.float32)
        widx = (self.w + np.arange(n)) % size
        self.buf[widx] = x

        p1 = (self.phase + delta * i) % T
        p2 = (p1 + T * 0.5) % T

        w1 = (0.5 - 0.5 * np.cos(p1 * (TWO_PI / T))).astype(np.float32)
        w2 = 1.0 - w1

        out = np.zeros(n, dtype=np.float32)
        for p, w in ((p1, w1), (p2, w2)):
            r = (widx - self.base_delay - p) % size
            i0 = np.floor(r).astype(np.int64)
            f = (r - i0).astype(np.float32)

            im1 = (i0 - 1) % size
            ip1 = (i0 + 1) % size
            ip2 = (i0 + 2) % size

            y0 = self.buf[im1]
            y1 = self.buf[i0]
            y2 = self.buf[ip1]
            y3 = self.buf[ip2]

            # 4-point Cubic Hermite interpolation
            c0 = y1
            c1 = 0.5 * (y2 - y0)
            c2 = y0 - 2.5 * y1 + 2.0 * y2 - 0.5 * y3
            c3 = 0.5 * (y3 - y0) + 1.5 * (y1 - y2)
            out += w * (((c3 * f + c2) * f + c1) * f + c0)

        self.w = (self.w + n) % size
        self.phase = (self.phase + delta * n) % T
        return out.astype(np.float32, copy=False)


# Backwards compatibility aliases
DualTapHarmonizer = SmoothHarmonizer
MultiPhaseHarmonizer = SmoothHarmonizer


class VoiceChanger:
    """Isolated voice transformation stage. When disabled the audio is returned untouched."""
    MODES = ["Natural Pitch", "Deep Titan / Monster", "Helium / Chipmunk", "Robot / Cybernetic",
             "Walkie-Talkie / Comm Radio", "Telephone / Vintage Lo-Fi", "Echo / Stadium Delay", "Demon / Dark Lord", "Alien / Vibrato"]

    MODE_DESCRIPTIONS = {
        "Natural Pitch": "Clean, smooth pitch shifting with zero robotic coloration.",
        "Deep Titan / Monster": "Deep, authoritative voice with rich vocal resonance.",
        "Helium / Chipmunk": "High-pitched character voice with natural human clarity.",
        "Robot / Cybernetic": "Subtle futuristic synthesized cybernetic character.",
        "Walkie-Talkie / Comm Radio": "Tactical two-way radio with authentic bandwidth limit.",
        "Telephone / Vintage Lo-Fi": "Classic 300Hz-3.4kHz telephone line with gentle warmth.",
        "Echo / Stadium Delay": "Slap-back arena echo like a live stadium announcer.",
        "Demon / Dark Lord": "Deep guttural underworld growl with dark harmonics.",
        "Alien / Vibrato": "Smooth extraterrestrial pitch vibrato modulation.",
    }

    BUILTIN_PRESETS = {
        "Normal (Bypass)": {"enabled": False, "mode": "Natural Pitch", "pitch_semitones": 0.0, "formant_semitones": 0.0, "mix": 1.0},
        "Deep Titan / Monster": {"enabled": True, "mode": "Deep Titan / Monster", "pitch_semitones": -4.0, "formant_semitones": -1.0, "mix": 1.0},
        "Announcer / Radio Host": {"enabled": True, "mode": "Natural Pitch", "pitch_semitones": -1.5, "formant_semitones": 0.5, "mix": 1.0},
        "Helium / Chipmunk": {"enabled": True, "mode": "Helium / Chipmunk", "pitch_semitones": 5.0, "formant_semitones": 1.5, "mix": 1.0},
        "Walkie-Talkie / Comm Radio": {"enabled": True, "mode": "Walkie-Talkie / Comm Radio", "pitch_semitones": 0.0, "formant_semitones": 1.0, "mix": 1.0},
        "Telephone / Vintage Lo-Fi": {"enabled": True, "mode": "Telephone / Vintage Lo-Fi", "pitch_semitones": 0.0, "formant_semitones": 0.0, "mix": 1.0},
        "Robot / Cybernetic": {"enabled": True, "mode": "Robot / Cybernetic", "pitch_semitones": -1.0, "formant_semitones": 0.0, "mix": 1.0},
        "Demon / Dark Lord": {"enabled": True, "mode": "Demon / Dark Lord", "pitch_semitones": -5.0, "formant_semitones": -1.5, "mix": 1.0},
        "Echo / Stadium Announcer": {"enabled": True, "mode": "Echo / Stadium Delay", "pitch_semitones": 0.0, "formant_semitones": 0.0, "mix": 0.85},
        "Alien / Vibrato": {"enabled": True, "mode": "Alien / Vibrato", "pitch_semitones": 2.0, "formant_semitones": 0.0, "mix": 1.0},
    }

    ECHO_DELAY = int(SAMPLE_RATE * 0.14)
    ECHO_BUF = int(SAMPLE_RATE * 0.25)

    def __init__(self, fs=SAMPLE_RATE):
        self.fs = fs
        self.enabled = False
        self.mode = "Natural Pitch"
        self.pitch_semitones = 0.0
        self.formant_semitones = 0.0
        self.mix = 1.0
        self.active_preset = "Normal (Bypass)"
        self.harmonizer = SmoothHarmonizer()
        self.formant_filter = BlockBiquad()
        self._last_formant_st = 0.0
        self.tel_hp = BlockBiquad()
        self.tel_lp = BlockBiquad()
        self.tel_hp.highpass(300.0, 0.7071, fs)
        self.tel_lp.lowpass(3400.0, 0.7071, fs)
        self.reset()

    def reset(self):
        self.harmonizer.reset()
        self.formant_filter.reset()
        self._last_formant_st = 0.0
        self.tel_hp.reset()
        self.tel_lp.reset()
        self._mod_phase = 0.0
        self._lfo_phase = 0.0
        self._echo = np.zeros(self.ECHO_BUF, np.float32)
        self._echo_idx = 0

    def load(self, d, name=None):
        d = sanitize_voice(d)
        self.enabled = d.get("enabled", True)
        self.mode = d.get("mode", "Natural Pitch")
        self.pitch_semitones = d.get("pitch_semitones", 0.0)
        self.formant_semitones = d.get("formant_semitones", 0.0)
        self.mix = d.get("mix", 1.0)
        if name is not None:
            self.active_preset = name

    def export(self):
        return {"enabled": self.enabled, "mode": self.mode,
                "pitch_semitones": self.pitch_semitones,
                "formant_semitones": self.formant_semitones,
                "mix": self.mix}

    @property
    def latency_ms(self):
        if not self.enabled:
            return 0.0
        pitched = abs(self.pitch_semitones) > 0.15 or self.mode == "Alien / Vibrato"
        return 15.0 if pitched else 0.0

    # -- processing ------------------------------------------------------------------
    def process(self, x):
        if not self.enabled or len(x) == 0:
            return x
        n = len(x)
        pitch = self.pitch_semitones
        if self.mode == "Alien / Vibrato":
            pitch += 1.2 * math.sin(self._lfo_phase)
            self._lfo_phase = (self._lfo_phase + TWO_PI * 4.5 * n / self.fs) % TWO_PI
        shifted = self.harmonizer.process(x, pitch) if abs(pitch) > 0.15 else x

        # Formant shaping - only recalculate biquad coefficients when slider or preset changes
        if abs(self.formant_semitones - self._last_formant_st) > 0.05:
            self._last_formant_st = self.formant_semitones
            if abs(self.formant_semitones) > 0.15:
                gain_db = min(max(self.formant_semitones * 1.5, -8.0), 8.0)
                center_f = min(max(2400.0 * (2.0 ** (self.formant_semitones / 24.0)), 500.0), 5500.0)
                self.formant_filter.peaking(center_f, gain_db, q=1.1, fs=self.fs)
            else:
                self.formant_filter.set_bypass()

        if not self.formant_filter.bypass:
            shifted = self.formant_filter.process(shifted)

        m = self.mode
        if m == "Robot / Cybernetic":
            mod = 0.70 + 0.30 * self._carrier(60.0, n)
            wet = shifted * mod
        elif m == "Walkie-Talkie / Comm Radio":
            wet = np.tanh(shifted * 1.8) * 0.88
        elif m == "Telephone / Vintage Lo-Fi":
            band = self.tel_lp.process(self.tel_hp.process(shifted))
            wet = np.tanh(band * 1.4) * 0.92
        elif m == "Echo / Stadium Delay":
            wet = self._echo_fx(shifted)
        elif m == "Deep Titan / Monster":
            wet = np.tanh(shifted * 1.2) * 0.95
        elif m == "Demon / Dark Lord":
            wet = np.tanh(shifted * 1.4) * (0.65 + 0.35 * self._carrier(40.0, n))
        else:
            wet = shifted
        wet = np.asarray(wet, np.float32)

        if self.mix >= 0.99:
            return wet
        if self.mix <= 0.01:
            return x
        return (1.0 - self.mix) * x + self.mix * wet

    def _carrier(self, freq, n):
        t = np.arange(n, dtype=np.float32)
        c = np.sin(self._mod_phase + TWO_PI * freq * t / self.fs).astype(np.float32)
        self._mod_phase = (self._mod_phase + TWO_PI * freq * n / self.fs) % TWO_PI
        return c

    def _echo_fx(self, x):
        n = len(x)
        if n > self.ECHO_DELAY:
            return x
        i = np.arange(n)
        ridx = (self._echo_idx + i - self.ECHO_DELAY) % self.ECHO_BUF
        widx = (self._echo_idx + i) % self.ECHO_BUF
        out = x + 0.35 * self._echo[ridx]
        self._echo[widx] = out
        self._echo_idx = (self._echo_idx + n) % self.ECHO_BUF
        return out


# ==============================================================================
# VISUALISER FEED
# ==============================================================================
class Analyzer:
    """40-band log spectrum (dB-scaled 0..1) and a decimated waveform, refreshed at ~30 Hz on demand."""
    BANDS = 40
    NFFT = 2048
    DB_MIN, DB_MAX = -80.0, -10.0

    def __init__(self, fs=SAMPLE_RATE):
        self.fs = fs
        self.buf = np.zeros(self.NFFT, np.float32)
        self.window = np.hanning(self.NFFT).astype(np.float32)
        edges_hz = np.geomspace(60.0, 18000.0, self.BANDS + 1)
        bins = np.rint(edges_hz / (fs / self.NFFT)).astype(int)
        for i in range(1, len(bins)):                      # strictly increasing so every band owns >= 1 bin
            bins[i] = max(bins[i], bins[i - 1] + 1)
        self.starts = bins[:-1]
        self.end = int(bins[-1])
        self.bands = np.zeros(self.BANDS, np.float32)
        self.scope = np.zeros(128, np.float32)
        self.norm = self.NFFT / 4.0                         # full-scale sine -> 1.0 after Hann window

    def push(self, x):
        n = len(x)
        if n >= self.NFFT:
            self.buf = x[-self.NFFT:].astype(np.float32)
        else:
            self.buf = np.concatenate((self.buf[n:], x.astype(np.float32, copy=False)))

    def update(self):
        spec = np.abs(np.fft.rfft(self.buf * self.window)) / self.norm
        mx = np.maximum.reduceat(spec[:self.end], self.starts)
        db = 20.0 * np.log10(mx + 1e-9)
        self.bands = np.clip((db - self.DB_MIN) / (self.DB_MAX - self.DB_MIN), 0.0, 1.0).astype(np.float32)
        self.scope = self.buf[-1024:][::8].copy()




def sanitize_voice(d):
    """Valid voice-changer settings only (clamped); never raises."""
    out = {}
    if not isinstance(d, dict):
        return out
    if isinstance(d.get("enabled"), bool):
        out["enabled"] = d["enabled"]
    if d.get("mode") in VoiceChanger.MODES:
        out["mode"] = d["mode"]
    for key, lo, hi in (("pitch_semitones", -12.0, 12.0), ("formant_semitones", -12.0, 12.0), ("mix", 0.0, 1.0)):
        v = d.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            out[key] = float(min(max(v, lo), hi))
    return out


# ==============================================================================
# PARAMETERS, LIMITS, PRESETS
# ==============================================================================
EQ_BANDS = 5
EQ_TYPES = ("peak", "lowshelf", "highshelf", "notch")
_EQ_DEFAULTS = [("lowshelf", 120.0, 0.7071), ("peak", 350.0, 1.0), ("peak", 2500.0, 1.0),
                ("peak", 5500.0, 1.0), ("highshelf", 8000.0, 0.7071)]

FX_BASE = {
    # input
    "gain": 1.0, "invert_polarity": False,
    "lowcut_enabled": True, "lowcut_hz": 80.0, "lowcut_slope": "12",
    "highcut_enabled": False, "highcut_hz": 14000.0,
    # noise suppression
    "smart_noise_cancel": True, "noise_cancel_amount": 0.65, "noise_quality": "high",
    "noise_max_reduction_db": 0.0, "noise_learn_s": 2.0,
    # gate
    "gate_enabled": True, "gate_threshold_db": -55.0, "gate_release_ms": 180.0,
    "gate_attack_ms": 2.0, "gate_hold_ms": 60.0, "gate_depth_db": -40.0, "gate_hysteresis_db": 3.0,
    # auto gain
    "agc_enabled": False, "agc_target_db": -20.0, "agc_max_gain_db": 24.0, "agc_attack_ms": 120.0, "agc_release_ms": 900.0,
    # equalizer (bands are added below)
    "eq_enabled": True,
    # de-esser
    "deess_enabled": False, "deess_freq": 6500.0, "deess_threshold_db": -30.0, "deess_range_db": 6.0,
    # compressor
    "comp_enabled": False, "comp_threshold_db": -22.0, "comp_ratio": 3.0, "comp_makeup_db": 3.0,
    "comp_attack_ms": 8.0, "comp_release_ms": 160.0, "comp_knee_db": 6.0, "comp_mix": 1.0,
    # output
    "out_gain_db": 0.0, "limiter_enabled": True, "limiter_ceiling_db": -1.0, "delay_ms": 0.0, "monitor_volume": 0.85,
}
for _n, (_type, _f, _q) in enumerate(_EQ_DEFAULTS, start=1):
    FX_BASE.update({f"eq{_n}_on": True, f"eq{_n}_type": _type, f"eq{_n}_freq": _f, f"eq{_n}_gain": 0.0, f"eq{_n}_q": _q})

FX_PARAMS = list(FX_BASE)

# Hard limits: anything outside is clamped, so a corrupt settings file or an imported preset can never break the audio.
FX_LIMITS = {
    "gain": (0.05, 16.0), "lowcut_hz": (20.0, 400.0), "highcut_hz": (3000.0, 22000.0),
    "noise_cancel_amount": (0.0, 1.0), "noise_max_reduction_db": (0.0, 50.0), "noise_learn_s": (0.5, 10.0),
    "gate_threshold_db": (-90.0, 0.0), "gate_release_ms": (10.0, 2000.0), "gate_attack_ms": (0.1, 200.0),
    "gate_hold_ms": (0.0, 1000.0), "gate_depth_db": (-90.0, -1.0), "gate_hysteresis_db": (0.0, 24.0),
    "agc_target_db": (-40.0, -3.0), "agc_max_gain_db": (0.0, 40.0), "agc_attack_ms": (10.0, 5000.0),
    "agc_release_ms": (50.0, 10000.0),
    "deess_freq": (2000.0, 12000.0), "deess_threshold_db": (-80.0, -5.0), "deess_range_db": (0.0, 24.0),
    "comp_threshold_db": (-60.0, 0.0), "comp_ratio": (1.0, 20.0), "comp_makeup_db": (0.0, 24.0),
    "comp_attack_ms": (0.5, 200.0), "comp_release_ms": (10.0, 2000.0), "comp_knee_db": (0.0, 30.0), "comp_mix": (0.0, 1.0),
    "out_gain_db": (-30.0, 18.0), "limiter_ceiling_db": (-12.0, 0.0), "delay_ms": (0.0, 500.0), "monitor_volume": (0.0, 1.0),
}
FX_CHOICES = {"noise_quality": {"high", "fast"}, "lowcut_slope": {"12", "24"}}
for _n in range(1, EQ_BANDS + 1):
    FX_LIMITS.update({f"eq{_n}_freq": (20.0, 20000.0), f"eq{_n}_gain": (-18.0, 18.0), f"eq{_n}_q": (0.1, 10.0)})
    FX_CHOICES[f"eq{_n}_type"] = set(EQ_TYPES)

# Names used before v0.10 (three fixed EQ bands)
LEGACY_FX_KEYS = {"eq_low_gain_db": "eq1_gain", "eq_low_freq": "eq1_freq", "eq_mid_gain_db": "eq3_gain",
                  "eq_mid_freq": "eq3_freq", "eq_mid_q": "eq3_q", "eq_high_gain_db": "eq5_gain", "eq_high_freq": "eq5_freq"}


def migrate_fx_keys(d):
    return {LEGACY_FX_KEYS.get(k, k): v for k, v in d.items()}


def sanitize_fx(d):
    """Keep only known parameters with sane types and values (clamped). Never raises."""
    out = {}
    for k, v in migrate_fx_keys(d).items():
        base = FX_BASE.get(k)
        if base is None:
            continue
        if isinstance(base, bool):
            if isinstance(v, bool):
                out[k] = v
        elif isinstance(base, str):
            v = str(v)
            if v in FX_CHOICES.get(k, {v}):
                out[k] = v
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            lo, hi = FX_LIMITS.get(k, (-1e9, 1e9))
            out[k] = float(min(max(v, lo), hi))
    return out


FX_BUILTIN_PRESETS = {
    "Default (Studio Clean)": {},
    "Studio Vocal (Unprocessed Clean)": {"gain": 1.15, "lowcut_enabled": True, "lowcut_hz": 75.0,
                                         "smart_noise_cancel": True, "noise_cancel_amount": 0.35, "noise_max_reduction_db": 12.0,
                                         "gate_enabled": True, "gate_threshold_db": -58.0, "gate_release_ms": 220.0, "gate_hold_ms": 90.0,
                                         "eq_enabled": True, "eq1_gain": 1.5, "eq3_gain": 2.0, "eq4_gain": 1.5, "eq5_gain": 3.0,
                                         "comp_enabled": True, "comp_threshold_db": -22.0, "comp_ratio": 2.2, "comp_makeup_db": 2.5,
                                         "limiter_enabled": True, "limiter_ceiling_db": -1.0},
    "Podcast & Streamer": {"gain": 1.1, "noise_cancel_amount": 0.70, "gate_threshold_db": -50.0,
                           "eq1_gain": 2.5, "eq3_gain": 1.5, "eq5_gain": 2.5,
                           "comp_enabled": True, "comp_threshold_db": -24.0, "comp_ratio": 3.0, "comp_makeup_db": 4.0},
    "Broadcast Warmth": {"eq1_gain": 4.0, "eq3_gain": 0.5, "eq5_gain": 1.5,
                         "comp_enabled": True, "comp_threshold_db": -22.0, "comp_ratio": 2.5, "comp_makeup_db": 3.0},
    "Crisp & Articulate": {"noise_cancel_amount": 0.60, "gate_threshold_db": -52.0,
                           "eq1_gain": -1.5, "eq3_gain": 3.0, "eq5_gain": 4.5},
    "Smooth Vocal (De-essed)": {"eq1_gain": 2.0, "eq3_gain": 1.5, "eq5_gain": 3.0,
                                "deess_enabled": True, "deess_freq": 6500.0, "deess_threshold_db": -32.0, "deess_range_db": 8.0,
                                "comp_enabled": True, "comp_threshold_db": -24.0, "comp_ratio": 2.5, "comp_makeup_db": 3.0},
    "De-Boom (Bass Cut)": {"lowcut_hz": 120.0, "eq1_gain": -5.5, "eq3_gain": 1.0, "eq5_gain": 2.0},
    "Heavy Noise Cut (Keyboard)": {"noise_cancel_amount": 0.85, "gate_threshold_db": -42.0, "eq3_gain": 1.0, "eq5_gain": 2.0},
    "Voice Chat (Gaming)": {"lowcut_hz": 100.0, "noise_cancel_amount": 0.80, "gate_threshold_db": -45.0,
                            "comp_enabled": True, "comp_threshold_db": -26.0, "comp_ratio": 4.0, "comp_makeup_db": 5.0,
                            "agc_enabled": True, "agc_target_db": -20.0},
    "Quiet Phone Boost": {"gain": 2.0, "noise_cancel_amount": 0.60, "agc_enabled": True, "agc_target_db": -20.0},
    "Pure Raw (Zero FX)": {"lowcut_enabled": False, "smart_noise_cancel": False, "noise_cancel_amount": 0.0,
                           "gate_enabled": False, "eq_enabled": False, "limiter_enabled": False},
}


def fx_preset(name, user_presets=None):
    """Full parameter dict for a built-in or user preset (missing keys come from FX_BASE), or None."""
    if name in FX_BUILTIN_PRESETS:
        d = dict(FX_BASE)
        d.update(sanitize_fx(FX_BUILTIN_PRESETS[name]))
        return d
    if user_presets and name in user_presets:
        d = dict(FX_BASE)
        d.update(sanitize_fx(user_presets[name]))
        return d
    return None


# ==============================================================================
# THE CHAIN
# ==============================================================================
class AudioProcessor:
    """gain -> polarity -> low/high-cut -> noise suppression -> gate -> auto-gain -> voice changer -> EQ -> de-esser
    -> compressor -> output gain -> limiter -> delay."""

    def __init__(self, config=None, fs=SAMPLE_RATE):
        self.fs = fs
        for k, v in FX_BASE.items():
            setattr(self, k, v)
        self.active_preset = "Default (Studio Clean)"
        self.fx_bypass = False            # runtime A/B switch (never saved in presets)

        self.hp1, self.hp2, self.lp = BlockBiquad(), BlockBiquad(), BlockBiquad()
        self.eq = [BlockBiquad() for _ in range(EQ_BANDS)]
        self.denoiser = SpectralDenoiser(hop=FRAME)
        self.gate, self.agc, self.comp = NoiseGate(), AutoGain(), Compressor()
        self.deesser, self.delay = DeEsser(), DelayLine()
        self.voice_changer = VoiceChanger(fs)
        self.analyzer = Analyzer(fs)
        self.viz_active = True

        # live meters (read by the GUI)
        self.level_peak = 0.0
        self.level_rms = 0.0
        self.level_db = -80.0
        self.clipped = False
        self.dsp_ms = 0.0
        self.gain_reduction_db = 0.0
        self.deess_reduction_db = 0.0
        self._viz_t = 0.0
        self._active = {}
        self._declick = False
        self._bypassed = False

        if config is not None:
            s = config.data["studio_fx"]
            self.apply_fx({k: s[k] for k in s if k != "active_preset"}, name=s.get("active_preset"))
            self.voice_changer.load(config.data["voice_changer"], config.data["voice_changer"].get("active_preset"))
        else:
            self.apply_fx(FX_BASE)

    # -- parameters --------------------------------------------------------------------
    def apply_fx(self, d, name=None):
        for k, v in sanitize_fx(d).items():
            setattr(self, k, v)
        if name is not None:
            self.active_preset = name
        self._rebuild_all()

    def export_fx(self):
        return {k: getattr(self, k) for k in FX_PARAMS}

    def set_param(self, name, value):
        if name not in FX_BASE:
            raise KeyError(name)
        clean = sanitize_fx({name: value})
        if name not in clean:
            return False
        setattr(self, name, clean[name])
        if name.startswith("lowcut"):
            self._rebuild_lowcut()
        elif name.startswith("highcut"):
            self._rebuild_highcut()
        elif name.startswith("eq") and name[2:3].isdigit():
            self._rebuild_eq_band(int(name[2]))
        elif name in ("noise_quality", "noise_learn_s"):
            self._rebuild_denoiser()
        return True

    def eq_band(self, n):
        """Parameters of band n (1-based) as a dict - used by the EQ editor."""
        return {"on": getattr(self, f"eq{n}_on"), "type": getattr(self, f"eq{n}_type"), "freq": getattr(self, f"eq{n}_freq"),
                "gain": getattr(self, f"eq{n}_gain"), "q": getattr(self, f"eq{n}_q")}

    def _band_active(self, n):
        b = self.eq_band(n)
        return bool(self.eq_enabled and b["on"] and (b["type"] == "notch" or abs(b["gain"]) >= 0.1))

    def _rebuild_all(self):
        self._rebuild_lowcut()
        self._rebuild_highcut()
        self._rebuild_eq()
        self._rebuild_denoiser()

    def _rebuild_lowcut(self):
        f = self.lowcut_hz
        if self.lowcut_slope == "24":                    # 4th-order Butterworth = two cascaded sections
            self.hp1.highpass(f, 0.5412, self.fs)
            self.hp2.highpass(f, 1.3066, self.fs)
        else:
            self.hp1.highpass(f, 0.7071, self.fs)
            self.hp2.set_bypass()

    def _rebuild_highcut(self):
        self.lp.lowpass(self.highcut_hz, 0.7071, self.fs)

    def _rebuild_eq_band(self, n):
        b = self.eq_band(n)
        self.eq[n - 1].design_band(b["type"], b["freq"], b["gain"], b["q"], self.fs)

    def _rebuild_eq(self):
        for n in range(1, EQ_BANDS + 1):
            self._rebuild_eq_band(n)

    def _rebuild_denoiser(self):
        hop = 240 if self.noise_quality == "fast" else FRAME
        if self.denoiser.hop != hop or abs(self.denoiser.history_s - self.noise_learn_s) > 1e-6:
            self.denoiser = SpectralDenoiser(hop=hop, fs=self.fs, history_s=self.noise_learn_s)

    def eq_curve_db(self, freqs):
        total = np.zeros(len(freqs))
        for n, f in enumerate(self.eq, start=1):
            if self._band_active(n):
                total += f.magnitude_db(freqs, self.fs)
        return total

    @property
    def latency_ms(self):
        ms = 0.0
        if self.smart_noise_cancel and self.noise_cancel_amount > 0.02:
            ms += self.denoiser.delay_ms
        return ms + self.voice_changer.latency_ms + (self.delay_ms if self.delay_ms > 0.5 else 0.0)

    def reset(self):
        for f in (self.hp1, self.hp2, self.lp, *self.eq):
            f.reset()
        self.denoiser.reset()
        self.gate.reset(); self.agc.reset(); self.comp.reset(); self.deesser.reset(); self.delay.reset()
        self.voice_changer.reset()
        self._active.clear()

    # -- processing --------------------------------------------------------------------
    def _became_active(self, key, now_active):
        was = self._active.get(key, False)
        self._active[key] = now_active
        return now_active and not was

    def _finish(self, x, clipped, t0):
        peak = float(np.max(np.abs(x)))
        self.level_peak = peak
        self.level_rms = float(np.sqrt(np.mean(x * x)))
        self.level_db = lin_to_db(peak, -80.0)
        self.clipped = clipped
        if self.viz_active:
            self.analyzer.push(x)
            now = time.perf_counter()
            if now - self._viz_t >= 0.033:
                self._viz_t = now
                self.analyzer.update()
        self.dsp_ms = 0.95 * self.dsp_ms + 0.05 * (time.perf_counter() - t0) * 1000.0
        return x

    def process(self, x):
        """float32 mono block in -> float32 mono block out (same length)."""
        t0 = time.perf_counter()
        if len(x) == 0:
            return x

        if self.fx_bypass:                                   # A/B: hear the untouched microphone
            self._bypassed = True
            self.gain_reduction_db = self.deess_reduction_db = 0.0
            y = np.clip(x, -1.0, 1.0)
            return self._finish(y, bool(np.max(np.abs(x)) > 1.0), t0)
        if self._bypassed:
            self._bypassed = False
            self.reset()
            self._declick = True

        if abs(self.gain - 1.0) > 1e-3:
            x = x * np.float32(self.gain)
        if self.invert_polarity:
            x = -x

        if self.lowcut_enabled:
            x = self.hp1.process(x)
            x = self.hp2.process(x)
        if self.highcut_enabled:
            if self._became_active("hc", True):
                self.lp.reset()
            x = self.lp.process(x)
        else:
            self._active["hc"] = False

        nc = self.smart_noise_cancel and self.noise_cancel_amount > 0.02
        prev_nc = self._active.get("nc", False)
        if nc != prev_nc:                       # the stage adds/removes its 5-10 ms delay: hide the seam
            self._declick = True
            if nc:
                self.denoiser.reset()
        self._active["nc"] = nc
        if nc:
            x = self.denoiser.process(x, self.noise_cancel_amount, self.noise_max_reduction_db)

        if self.gate_enabled:
            if self._became_active("gate", True):
                self.gate.reset()
            x = self.gate.process(x, self.gate_threshold_db, self.gate_release_ms, self.gate_attack_ms,
                                  self.gate_hold_ms, self.gate_depth_db, self.gate_hysteresis_db)
        else:
            self._active["gate"] = False

        if self.agc_enabled:
            if self._became_active("agc", True):
                self.agc.reset()
            x = self.agc.process(x, self.agc_target_db, self.agc_max_gain_db, self.agc_attack_ms, self.agc_release_ms)
        else:
            self._active["agc"] = False

        vc = self.voice_changer
        if self._became_active("vc", vc.enabled):
            vc.reset()
        if vc.enabled:
            x = vc.process(x)

        for n, f in enumerate(self.eq, start=1):
            on = self._band_active(n)
            if self._became_active(f"eq{n}", on):
                f.reset()
            if on:
                x = f.process(x)

        if self.deess_enabled:
            if self._became_active("deess", True):
                self.deesser.reset()
            x = self.deesser.process(x, self.deess_freq, self.deess_threshold_db, self.deess_range_db)
            self.deess_reduction_db = self.deesser.gr_db
        else:
            self._active["deess"] = False
            self.deess_reduction_db = 0.0

        if self.comp_enabled:
            if self._became_active("comp", True):
                self.comp.reset()
            x = self.comp.process(x, self.comp_threshold_db, self.comp_ratio, self.comp_makeup_db, self.comp_attack_ms,
                                  self.comp_release_ms, self.comp_knee_db, self.comp_mix)
            self.gain_reduction_db = self.comp.gr_db
        else:
            self._active["comp"] = False
            self.gain_reduction_db = 0.0

        if abs(self.out_gain_db) > 0.01:
            x = x * np.float32(db_to_lin(self.out_gain_db))

        if self._declick:
            n = min(len(x), 96)
            x = x.copy()
            x[:n] *= np.linspace(0.0, 1.0, n, dtype=np.float32)
            self._declick = False

        ceiling = db_to_lin(self.limiter_ceiling_db) if self.limiter_enabled else 0.999
        if self.limiter_enabled:
            x, clipped = soft_limit(x, ceiling)
        else:
            clipped = float(np.max(np.abs(x))) > 1.0
        x = np.clip(x, -1.0, 1.0)

        if self.delay_ms > 0.5 or self.delay.active:
            x = self.delay.process(x, int(round(self.delay_ms * self.fs / 1000.0)) if self.delay_ms > 0.5 else 0)

        return self._finish(x, clipped, t0)
