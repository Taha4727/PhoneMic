"""Standalone PhoneMic CLI Receiver tests (stdlib wire/AST checks + NumPy/fake_sd engine checks).

Runs wire parser, CLI flag, and standalone-import AST checks in pure Python stdlib;
runs full CliReceiver audio, Ring, mixer, UDP/TCP lifecycle, and callback lock-isolation
tests automatically whenever numpy is installed.
"""
import ast
import os
import socket
import struct
import subprocess
import sys
import time

import _path  # noqa: F401
import phonemic_cli

try:
    import numpy as np
    import fake_sd
    HAS_NUMPY = True
except ImportError:
    np = None
    fake_sd = None
    HAS_NUMPY = False


CLI_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "phonemic_cli.py")


def test_standalone_zero_internal_imports():
    with open(CLI_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=CLI_PATH)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "phonemic" or alias.name.startswith("phonemic."):
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "phonemic" or mod.startswith("phonemic."):
                bad.append(mod)
    assert not bad, f"phonemic_cli.py must stay self-contained without phonemic.* imports: {bad}"


def test_cli_flags_and_version():
    out_ver = subprocess.check_output([sys.executable, CLI_PATH, "--version"], text=True, timeout=5)
    assert phonemic_cli.VERSION in out_ver, out_ver

    out_help = subprocess.check_output([sys.executable, CLI_PATH, "--help"], text=True, timeout=5)
    for flag in ("--port", "--mix-mode", "--device", "--monitor-device", "--monitor", "--tcp", "--tcp-rate"):
        assert flag in out_help, (flag, out_help)


def test_cli_tcp_stream_parser_matrix():
    Parser = phonemic_cli._CliTcpStreamParser
    # 1. Raw unframed 48k, 24k, 16k with awkward splits
    for rate, fb, splits in (
        (48000, 960, [1, 7, 13, 500, 439, 961]),
        (24000, 480, [1, 3, 200, 276, 481]),
        (16000, 320, [1, 19, 100, 200, 321]),
    ):
        p = Parser(default_rate=rate)
        raw = bytes((i & 0xFF for i in range(fb * 4)))
        frames = []
        off = 0
        idx = 0
        while off < len(raw):
            step = splits[idx % len(splits)]
            idx += 1
            frames.extend(p.feed(raw[off:off + step]))
            off += step
        assert p.mode == "raw" and p.sample_rate == rate and p.buffered_bytes == 0
        assert len(frames) == 4
        assert b"".join(f[1] for f in frames) == raw
        assert all(seq == -1 and sr == rate and len(pcm) == fb for seq, pcm, sr in frames)

    # 2. Framed compatibility PM03 (16 kHz) across tiny splits
    fp = Parser(default_rate=48000)
    pkt_payload = b"\x11\x22" * 160  # 320 B
    stream = b"".join(b"PM03" + struct.pack(">I", s) + pkt_payload for s in (0, 1, 2))
    out = []
    for off in range(0, len(stream), 5):
        out.extend(fp.feed(stream[off:off + 5]))
    assert fp.mode == "framed" and fp.sample_rate == 16000
    assert [(s, len(pcm), sr) for s, pcm, sr in out] == [(0, 320, 16000), (1, 320, 16000), (2, 320, 16000)]

    # 3. Bounded buffer protection
    cp = Parser(default_rate=48000)
    raised = False
    try:
        cp.feed(b"\xAA" * (phonemic_cli.MAX_TCP_ACCUM_BYTES + 1))
    except BufferError:
        raised = True
    assert raised


def test_cli_resamplers_and_ring():
    if not HAS_NUMPY:
        print("  SKIP NumPy CLI Ring/resampler tests (numpy not installed)")
        return

    assert len(phonemic_cli.upsample_2x(np.zeros(0, np.float32))) == 0
    assert len(phonemic_cli.upsample_3x(np.zeros(0, np.float32))) == 0

    x24 = np.linspace(-0.5, 0.5, 240, dtype=np.float32)
    y2 = phonemic_cli.upsample_2x(x24)
    ref2 = np.interp(np.arange(480) * 0.5, np.arange(240), x24).astype(np.float32)
    assert y2.shape == (480,) and np.max(np.abs(y2 - ref2)) < 1e-6

    x16 = np.linspace(-0.4, 0.4, 160, dtype=np.float32)
    y3 = phonemic_cli.upsample_3x(x16)
    ref3 = np.interp(np.arange(480) / 3.0, np.arange(160), x16).astype(np.float32)
    assert y3.shape == (480,) and np.max(np.abs(y3 - ref3)) < 1e-6

    # Ring wraparound, drop tracking, and zero-fill underrun
    ring = phonemic_cli.Ring(capacity=960)
    b1 = np.arange(480, dtype=np.float32)
    b2 = np.arange(480, 960, dtype=np.float32)
    b3 = np.arange(960, 1440, dtype=np.float32)
    ring.write(b1)
    ring.write(b2)
    ring.write(b3)  # overflows b1 -> drops == 1, retains b2 + b3
    assert ring.drops == 1 and ring.available() == 960

    out = np.empty(480, dtype=np.float32)
    got = ring.read_into(out)
    assert got == 480 and np.array_equal(out, b2)
    got2 = ring.read_into(out)
    assert got2 == 480 and np.array_equal(out, b3)
    got3 = ring.read_into(out)
    assert got3 == 0 and np.all(out == 0.0) and ring.underruns == 1


def test_cli_callback_never_acquires_clients_lock():
    if not HAS_NUMPY:
        print("  SKIP NumPy CLI callback lock isolation test (numpy not installed)")
        return

    cli = phonemic_cli.CliReceiver(port=25241)
    sample = np.full(phonemic_cli.FRAME_48K, 0.25, dtype=np.float32)
    cli.main_ring.write(sample)
    cli.monitoring = True
    cli.monitor_ring.write(sample)

    out_main = np.zeros((phonemic_cli.FRAME_48K, 1), dtype=np.float32)
    out_mon = np.zeros((phonemic_cli.FRAME_48K, 1), dtype=np.float32)

    # Hold clients_lock while invoking both real-time PortAudio callbacks directly
    with cli.clients_lock:
        t0 = time.monotonic()
        cli._main_audio_callback(out_main, phonemic_cli.FRAME_48K, None, None)
        cli._monitor_audio_callback(out_mon, phonemic_cli.FRAME_48K, None, None)
        elapsed_ms = (time.monotonic() - t0) * 1000.0

    assert elapsed_ms < 20.0, elapsed_ms
    assert np.allclose(out_main[:, 0], 0.25, atol=1e-6)
    assert np.allclose(out_mon[:, 0], 0.25, atol=1e-6)

    # Muted path zero-fills without mutating/blocking
    cli.muted = True
    cli.main_ring.write(sample)
    out_muted = np.ones((phonemic_cli.FRAME_48K, 1), dtype=np.float32)
    cli._main_audio_callback(out_muted, phonemic_cli.FRAME_48K, None, None)
    assert np.all(out_muted == 0.0)


def test_cli_udp_multi_client_duck_and_stop():
    if not HAS_NUMPY:
        print("  SKIP NumPy CLI UDP lifecycle test (numpy not installed)")
        return

    orig_sd = phonemic_cli.sd
    phonemic_cli.sd = fake_sd
    port = 25242
    cli = phonemic_cli.CliReceiver(port=port, mix_mode="duck", use_tcp=False)
    cli.monitoring = True
    cli.start(interactive=False)
    time.sleep(0.15)

    s1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s1.settimeout(1.5)
    try:
        # Discovery probe & subnet reply caching
        s1.sendto(b"PMD0", ("127.0.0.1", port))
        rep1, _ = s1.recvfrom(256)
        s1.sendto(b"PM_DISCOVER", ("127.0.0.1", port))
        rep2, _ = s1.recvfrom(256)
        assert rep1.startswith(b"PMA1 ") and rep1 == rep2
        assert "127.0.0.1" in cli._ip_cache

        # Loud 48k phone on s1 + quieter 24k phone on s2
        pcm48_loud = (np.full(480, 12000, dtype="<i2")).tobytes()
        pcm24_soft = (np.full(240, 1000, dtype="<i2")).tobytes()
        peak_seen = 0.0
        for seq in range(12):
            s1.sendto(b"PM01" + struct.pack(">I", seq) + pcm48_loud, ("127.0.0.1", port))
            s2.sendto(b"PM02" + struct.pack(">I", seq) + pcm24_soft, ("127.0.0.1", port))
            peak_seen = max(peak_seen, cli.master_peak)
            time.sleep(0.010)

        deadline = time.monotonic() + 0.5
        while peak_seen == 0.0 and time.monotonic() < deadline:
            peak_seen = max(peak_seen, cli.master_peak)
            time.sleep(0.005)
        with cli.clients_lock:
            assert len(cli.clients) == 2
        assert cli.main_ring.available() > 0 or cli._cb_epoch > 0
        assert peak_seen > 0.0
    finally:
        s1.close()
        s2.close()
        cli.stop()
        phonemic_cli.sd = orig_sd
    assert cli._net_thread is None and cli._mixer_thread is None


def test_cli_tcp_raw_16k_and_framed_24k():
    if not HAS_NUMPY:
        print("  SKIP NumPy CLI TCP lifecycle test (numpy not installed)")
        return

    orig_sd = phonemic_cli.sd
    phonemic_cli.sd = fake_sd
    port = 25243
    cli = phonemic_cli.CliReceiver(port=port, use_tcp=True, raw_tcp_rate=16000)
    cli.start(interactive=False)
    time.sleep(0.15)

    c1 = socket.create_connection(("127.0.0.1", port), timeout=1.5)
    c2 = socket.create_connection(("127.0.0.1", port), timeout=1.5)
    try:
        pcm16 = (np.full(160, 4000, dtype="<i2")).tobytes()  # 320 B
        pcm24 = (np.full(240, 5000, dtype="<i2")).tobytes()  # 480 B
        for seq in range(5):
            # Split raw 16k stream across odd chunks
            c1.sendall(pcm16[:100])
            c1.sendall(pcm16[100:])
            c2.sendall(b"PM02" + struct.pack(">I", seq) + pcm24)
            time.sleep(0.01)

        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            with cli.clients_lock:
                if len(cli.clients) == 2 and all(c.packet_count >= 5 for c in cli.clients.values()):
                    break
            time.sleep(0.01)

        with cli.clients_lock:
            assert len(cli.clients) == 2
            rates = sorted(c.sample_rate for c in cli.clients.values())
            assert rates == [16000, 24000], rates
    finally:
        c1.close()
        c2.close()
        cli.stop()
        phonemic_cli.sd = orig_sd


def test_cli_pm04_formats():
    Parser = phonemic_cli._CliTcpStreamParser
    hdr = b"PM04" + struct.pack(">IIBBH", 0, 44100, 2, phonemic_cli.FMT_PCM_FLOAT32, 0)
    payload = b"\x00\x00\x00\x3f" * (441 * 2)
    hdr1 = b"PM04" + struct.pack(">IIBBH", 1, 44100, 2, phonemic_cli.FMT_PCM_FLOAT32, 0)
    stream = hdr + payload + hdr1 + payload

    p = Parser(default_rate=48000)
    frames = []
    for off in range(0, len(stream), 500):
        frames.extend(p.feed_ex(stream[off:off + 500]))
    assert p.mode == "framed" and p.sample_rate == 44100 and p.channels == 2
    assert len(frames) == 2 and frames[0][3] == 2 and frames[1][4] == phonemic_cli.FMT_PCM_FLOAT32

    if not HAS_NUMPY:
        print("  SKIP NumPy CLI PM04 tests (numpy not installed)")
        return

    orig_sd = phonemic_cli.sd
    phonemic_cli.sd = fake_sd
    port = 25244
    cli = phonemic_cli.CliReceiver(port=port, use_tcp=False)
    cli.start(interactive=False)
    time.sleep(0.15)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 48 kHz Stereo Float32 UDP packets (3856 B each)
        pcm_f32 = np.full(480 * 2, 0.3, dtype="<f4").tobytes()
        for seq in range(5):
            pkt = b"PM04" + struct.pack(">IIBBH", seq, 48000, 2, phonemic_cli.FMT_PCM_FLOAT32, 0) + pcm_f32
            sock.sendto(pkt, ("127.0.0.1", port))
            time.sleep(0.008)
        deadline = time.monotonic() + 1.0
        while cli.master_peak == 0.0 and time.monotonic() < deadline:
            time.sleep(0.01)
        with cli.clients_lock:
            stream_obj = next(iter(cli.clients.values()))
            assert stream_obj.channels == 2 and stream_obj.fmt_code == phonemic_cli.FMT_PCM_FLOAT32
        assert abs(cli.master_peak - 0.3) < 0.05, cli.master_peak
    finally:
        sock.close()
        cli.stop()
        phonemic_cli.sd = orig_sd


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
