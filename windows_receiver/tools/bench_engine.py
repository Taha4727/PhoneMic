#!/usr/bin/env python3
"""Three-tier performance benchmark & comparison harness for PhoneMic Receiver (GUI & CLI).

Levels:
  1. Isolated microbenchmarks (wall/CPU ns & tracemalloc allocations over 3,000 calls).
  2. Synthetic integration benchmarks (1-phone and 4-phone mixed UDP/TCP pumps via fake_sd).
  3. Real-device live session baseline recorder (optional ADB telemetry correlation).

Usage:
  python tools/bench_engine.py --level all --json-out phase0.json --md-out phase0.md
  python tools/bench_engine.py --level all --compare phase0.json --json-out phase2.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(ROOT, "tests")
for p in (ROOT, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import numpy as np
except ImportError as exc:
    np = None
    _NP_ERR = str(exc)
else:
    _NP_ERR = ""


def _read_first(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def collect_metadata(args):
    git_sha = "uninitialized"
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            git_sha = out
    except Exception:
        pass

    ram_gb = "unknown"
    if os.path.exists("/proc/meminfo"):
        for line in _read_first("/proc/meminfo").splitlines():
            if line.startswith("MemTotal:"):
                kb = int(line.split()[1])
                ram_gb = f"{kb / (1024 * 1024):.1f} GiB"
                break
    elif os.name == "nt":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                ram_gb = f"{stat.ullTotalPhys / (1024 ** 3):.1f} GiB"
        except Exception:
            pass

    power_profile = "unknown"
    gov = _read_first("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    if gov:
        power_profile = f"linux:{gov}"
    elif shutil.which("powerprofilesctl"):
        try:
            power_profile = "linux:" + subprocess.check_output(["powerprofilesctl", "get"], text=True).strip()
        except Exception:
            pass
    elif os.name == "nt" and shutil.which("powercfg"):
        try:
            power_profile = subprocess.check_output(["powercfg", "/getactivescheme"], text=True).strip()
        except Exception:
            pass

    sd_ver = "missing"
    pa_ver = "missing"
    try:
        import sounddevice as sd

        sd_ver = getattr(sd, "__version__", "installed")
        try:
            pa_ver = str(sd.get_portaudio_version())
        except Exception:
            pa_ver = "unknown"
    except Exception:
        pass

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": git_sha,
        "host_cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count() or 1,
        "host_ram": ram_gb,
        "os": f"{platform.system()} {platform.release()}",
        "kernel": platform.version(),
        "power_profile": power_profile,
        "python_version": platform.python_version(),
        "numpy_version": getattr(np, "__version__", "missing"),
        "sounddevice_version": sd_ver,
        "portaudio_version": pa_ver,
        "audio_backend": args.audio_backend,
        "output_latency": args.latency_mode,
        "android_model": args.android_model or "n/a",
        "android_api": args.android_api or "n/a",
        "workload": f"level={args.level}, calls={args.calls}, duration_s={args.duration}",
    }


def _bench_fn(name, fn, calls=3000, warmup=200):
    for _ in range(warmup):
        fn()
    tracemalloc.start()
    s0 = tracemalloc.take_snapshot()
    w0 = time.perf_counter_ns()
    c0 = time.process_time_ns()
    for _ in range(calls):
        fn()
    c1 = time.process_time_ns()
    w1 = time.perf_counter_ns()
    s1 = tracemalloc.take_snapshot()
    tracemalloc.stop()
    diffs = s1.compare_to(s0, "lineno")
    # Also track total new bytes/blocks allocated cleanly via get_traced_memory on a clean window
    tracemalloc.start()
    tracemalloc.clear_traces()
    for _ in range(calls):
        fn()
    cur_b, peak_b = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    alloc_blocks = sum(max(0, d.count_diff) for d in diffs)
    return {
        "name": name,
        "calls": calls,
        "wall_ns_per_call": round((w1 - w0) / calls, 1),
        "cpu_ns_per_call": round((c1 - c0) / calls, 1),
        "retained_bytes": cur_b,
        "peak_traced_bytes_per_call": round(peak_b / calls, 1),
        "net_alloc_blocks": alloc_blocks,
    }


def run_level1(calls=3000):
    from phonemic import dsp
    from phonemic.config import ConfigManager
    from phonemic.engine import JitterBuffer, Receiver, upsample_2x, upsample_3x
    from phonemic import system
    import fake_sd

    tmp = tempfile.mkdtemp()
    cfg = ConfigManager(os.path.join(tmp, "l1.json"))
    cfg.data["network"]["beacon"] = False
    rx = Receiver(cfg, sd_module=fake_sd, netinfo=system.NetworkInfo())

    rng = np.random.default_rng(7)
    pcm_480 = (rng.standard_normal(480) * 0.2 * 32767).astype("<i2").tobytes()
    pcm_240 = (rng.standard_normal(240) * 0.2 * 32767).astype("<i2").tobytes()
    pkt_pm01 = bytearray(b"PM01" + struct.pack(">I", 42) + pcm_480)
    pkt_pm02 = bytearray(b"PM02" + struct.pack(">I", 42) + pcm_240)
    pkt_pmd0 = bytearray(b"PMD0")

    class NullSock:
        def sendto(self, data, addr):
            return len(data)

    nsock = NullSock()
    seq_box = [0]

    def call_datagram_pm01():
        seq_box[0] = (seq_box[0] + 1) & 0xFFFFFFFF
        struct.pack_into(">I", pkt_pm01, 4, seq_box[0])
        rx.net._handle_datagram(nsock, pkt_pm01, len(pkt_pm01), ("127.0.0.1", 5555))

    def call_datagram_pm02():
        seq_box[0] = (seq_box[0] + 1) & 0xFFFFFFFF
        struct.pack_into(">I", pkt_pm02, 4, seq_box[0])
        rx.net._handle_datagram(nsock, pkt_pm02, len(pkt_pm02), ("127.0.0.2", 5555))

    def call_datagram_pmd0():
        rx.net._handle_datagram(nsock, pkt_pmd0, len(pkt_pmd0), ("127.0.0.1", 5555))

    jb = JitterBuffer(30, adaptive=True)
    jb_seq = [0]

    def call_jb_push_pop():
        jb_seq[0] += 1
        jb.push(jb_seq[0], pcm_480)
        if jb_seq[0] > 3:
            jb.pop()

    x480 = (rng.standard_normal(480) * 0.15).astype(np.float32)
    x240 = (rng.standard_normal(240) * 0.15).astype(np.float32)
    x160 = (rng.standard_normal(160) * 0.15).astype(np.float32)
    x333 = (rng.standard_normal(333) * 0.15).astype(np.float32)

    dn_short = dsp.SpectralDenoiser(history_s=2.0)  # 200 frames
    dn_long = dsp.SpectralDenoiser(history_s=8.0)   # 800 frames
    bq = dsp.BlockBiquad()
    bq.highpass(80.0)
    gate = dsp.NoiseGate()
    agc = dsp.AutoGain()
    comp = dsp.Compressor()
    deess = dsp.DeEsser()
    anz = dsp.Analyzer()
    proc = dsp.AudioProcessor()

    results = [
        _bench_fn("net_handle_datagram_pm01", call_datagram_pm01, calls=calls),
        _bench_fn("net_handle_datagram_pm02", call_datagram_pm02, calls=calls),
        _bench_fn("net_handle_datagram_pmd0", call_datagram_pmd0, calls=calls),
        _bench_fn("jitter_buffer_push_pop", call_jb_push_pop, calls=calls),
        _bench_fn("upsample_2x", lambda: upsample_2x(x240), calls=calls),
        _bench_fn("upsample_3x", lambda: upsample_3x(x160), calls=calls),
        _bench_fn("spectral_denoiser_hop_2s", lambda: dn_short._hop(x480, 0.65, 0.0), calls=calls),
        _bench_fn("spectral_denoiser_hop_8s", lambda: dn_long._hop(x480, 0.65, 0.0), calls=calls),
        _bench_fn("spectral_denoiser_process_480", lambda: dn_short.process(x480, 0.65, 0.0), calls=calls),
        _bench_fn("spectral_denoiser_process_333", lambda: dn_short.process(x333, 0.65, 0.0), calls=calls),
        _bench_fn("block_biquad_process", lambda: bq.process(x480), calls=calls),
        _bench_fn("noise_gate_process", lambda: gate.process(x480, -55.0, 180.0), calls=calls),
        _bench_fn("auto_gain_process", lambda: agc.process(x480, -20.0), calls=calls),
        _bench_fn("compressor_process", lambda: comp.process(x480, -22.0, 3.0, 3.0), calls=calls),
        _bench_fn("deesser_process", lambda: deess.process(x480, 6500.0, -30.0, 6.0), calls=calls),
        _bench_fn("analyzer_push_update", lambda: (anz.push(x480), anz.update()), calls=calls),
        _bench_fn("audio_processor_default", lambda: proc.process(x480), calls=calls),
    ]
    rx.stop()
    cfg.close()
    return results


def _pcm_frame(samples, seq, sr):
    n = np.arange(samples, dtype=np.float32) + seq * samples
    return (np.sin(2.0 * np.pi * 440.0 * n / sr) * 0.25 * 32767.0).astype("<i2").tobytes()


def run_level2_gui(duration_s=2.0, phones=1, transport="udp", port_base=25510):
    from phonemic.config import ConfigManager
    from phonemic.engine import Receiver
    from phonemic import system
    import fake_sd

    fake_sd.OutputStream.registry.clear()
    tmp = tempfile.mkdtemp()
    cfg = ConfigManager(os.path.join(tmp, f"l2_{transport}_{phones}.json"))
    port = port_base + phones + (100 if transport == "tcp" else 0)
    cfg.data["network"]["port"] = port
    cfg.data["network"]["beacon"] = False
    rx = Receiver(cfg, sd_module=fake_sd, netinfo=system.NetworkInfo())
    rx.start()
    time.sleep(0.25)

    loop_samples = []
    orig_produce = rx._produce

    def timed_produce():
        t0 = time.perf_counter_ns()
        r = orig_produce()
        if r:
            loop_samples.append((time.perf_counter_ns() - t0) / 1e6)
        return r

    rx._produce = timed_produce

    rates = [48000, 24000, 16000, 48000][:phones]
    magics = {48000: b"PM01", 24000: b"PM02", 16000: b"PM03"}
    frame_samples = {48000: 480, 24000: 240, 16000: 160}
    pre_pcm = {sr: _pcm_frame(frame_samples[sr], 0, sr) for sr in set(rates)}

    tracemalloc.start()
    cpu0 = time.process_time()
    wall0 = time.perf_counter()

    if transport == "udp":
        socks = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in rates]
        total_ticks = int(duration_s * 100)
        for tick in range(total_ticks):
            for idx, sr in enumerate(rates):
                # Deterministic 5% synthetic loss on phone 0 when phones > 1
                if phones > 1 and idx == 0 and tick % 20 == 19:
                    continue
                socks[idx].sendto(magics[sr] + struct.pack(">I", tick) + pre_pcm[sr], ("127.0.0.1", port))
            nxt = wall0 + (tick + 1) * 0.010
            now = time.perf_counter()
            if nxt > now:
                time.sleep(nxt - now)
        for s in socks:
            s.close()
    else:
        tsocks = []
        for idx, sr in enumerate(rates):
            try:
                c = socket.create_connection(("127.0.0.1", port), timeout=0.5)
                c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                tsocks.append((idx, sr, c))
            except Exception:
                pass
        total_ticks = int(duration_s * 100)
        for tick in range(total_ticks):
            for idx, sr, c in list(tsocks):
                try:
                    c.sendall(magics[sr] + struct.pack(">I", tick) + pre_pcm[sr])
                except Exception:
                    pass
            nxt = wall0 + (tick + 1) * 0.010
            now = time.perf_counter()
            if nxt > now:
                time.sleep(nxt - now)
        for _, _, c in tsocks:
            try:
                c.close()
            except Exception:
                pass

    wall_dt = max(1e-6, time.perf_counter() - wall0)
    cpu_dt = time.process_time() - cpu0
    cur_b, peak_b = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    ls = sorted(loop_samples)
    p50 = ls[len(ls) // 2] if ls else 0.0
    p95 = ls[min(len(ls) - 1, int(len(ls) * 0.95))] if ls else 0.0
    pmax = ls[-1] if ls else 0.0

    out = {
        "scenario": f"gui_{transport}_{phones}p",
        "wall_s": round(wall_dt, 3),
        "cpu_pct": round(100.0 * cpu_dt / wall_dt, 2),
        "dsp_ms_ema": round(rx.processor.dsp_ms, 3),
        "produce_p50_ms": round(p50, 3),
        "produce_p95_ms": round(p95, 3),
        "produce_max_ms": round(pmax, 3),
        "traced_peak_kib": round(peak_b / 1024.0, 1),
        "retained_kib_per_s": round((cur_b / 1024.0) / wall_dt, 2),
        "jb_depth_ms": round(rx.jb.depth_ms, 1),
        "plc_frames": rx.stats.plc_frames,
        "packets": rx.stats.packets,
        "client_streams": len(rx.client_streams),
    }
    rx.stop()
    cfg.close()
    return out


def run_level2_cli(duration_s=2.0, phones=1, port_base=25710):
    import phonemic_cli
    import fake_sd

    orig_sd = phonemic_cli.sd
    phonemic_cli.sd = fake_sd
    port = port_base + phones
    cli = phonemic_cli.CliReceiver(port=port, use_tcp=False)
    cli.running = True
    cli._start_main_audio()

    net_t = threading.Thread(target=cli._udp_loop, daemon=True)
    mix_ticks = []
    orig_mixer = cli._mixer_loop

    # Instrument callback latency cleanly without altering core logic
    orig_cb = cli._main_audio_callback
    cb_ns = []

    def timed_cb(outdata, frames, time_info, status):
        t0 = time.perf_counter_ns()
        orig_cb(outdata, frames, time_info, status)
        cb_ns.append(time.perf_counter_ns() - t0)

    cli._main_audio_callback = timed_cb
    if cli.main_stream:
        cli.main_stream.cb = timed_cb

    net_t.start()
    mix_t = threading.Thread(target=orig_mixer, daemon=True)
    mix_t.start()
    time.sleep(0.15)

    rates = [48000, 24000, 16000, 48000][:phones]
    magics = {48000: b"PM01", 24000: b"PM02", 16000: b"PM03"}
    samples = {48000: 480, 24000: 240, 16000: 160}
    pre_pcm = {sr: _pcm_frame(samples[sr], 0, sr) for sr in set(rates)}
    socks = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in rates]

    tracemalloc.start()
    cpu0 = time.process_time()
    wall0 = time.perf_counter()
    ticks = int(duration_s * 100)
    for tick in range(ticks):
        for idx, sr in enumerate(rates):
            socks[idx].sendto(magics[sr] + struct.pack(">I", tick) + pre_pcm[sr], ("127.0.0.1", port))
        nxt = wall0 + (tick + 1) * 0.010
        now = time.perf_counter()
        if nxt > now:
            time.sleep(nxt - now)
    wall_dt = max(1e-6, time.perf_counter() - wall0)
    cpu_dt = time.process_time() - cpu0
    cur_b, peak_b = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    cli.running = False
    for s in socks:
        s.close()
    if cli.main_stream:
        cli.main_stream.stop()
        cli.main_stream.close()
    net_t.join(timeout=1.5)
    mix_t.join(timeout=1.5)
    phonemic_cli.sd = orig_sd

    cbs = sorted(cb_ns)
    return {
        "scenario": f"cli_udp_{phones}p",
        "wall_s": round(wall_dt, 3),
        "cpu_pct": round(100.0 * cpu_dt / wall_dt, 2),
        "traced_peak_kib": round(peak_b / 1024.0, 1),
        "retained_kib_per_s": round((cur_b / 1024.0) / wall_dt, 2),
        "cb_p50_us": round((cbs[len(cbs) // 2] / 1000.0) if cbs else 0.0, 2),
        "cb_p95_us": round((cbs[min(len(cbs) - 1, int(len(cbs) * 0.95))] / 1000.0) if cbs else 0.0, 2),
        "cb_max_us": round((cbs[-1] / 1000.0) if cbs else 0.0, 2),
    }


def run_level3(duration_s=600.0, port=5001):
    from phonemic.config import ConfigManager
    from phonemic.engine import Receiver
    from phonemic import system

    tmp = tempfile.mkdtemp()
    cfg = ConfigManager(os.path.join(tmp, "l3.json"))
    cfg.data["network"]["port"] = port
    rx = Receiver(cfg, sd_module="auto", netinfo=system.NetworkInfo())
    rx.start()
    print(f"[Level 3] Listening on port {port} for {duration_s:.0f}s (device: {rx.main_dev.name if rx.main_dev else 'none'})...")
    cpu0 = time.process_time()
    wall0 = time.perf_counter()
    try:
        while time.perf_counter() - wall0 < duration_s:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    wall_dt = max(1e-6, time.perf_counter() - wall0)
    cpu_dt = time.process_time() - cpu0
    res = {
        "scenario": "real_device_session",
        "wall_s": round(wall_dt, 2),
        "cpu_pct": round(100.0 * cpu_dt / wall_dt, 2),
        "device": rx.main_dev.name if rx.main_dev else "none",
        "backend": rx.api or "none",
        "packets": rx.stats.packets,
        "lost_pct": round(rx.stats.loss_pct, 3),
        "jitter_ms": round(rx.stats.jitter_ms, 2),
        "plc_frames": rx.stats.plc_frames,
        "xruns": rx.main.xruns,
        "starved": rx.main.starved,
        "latency_est_ms": round(rx.latency_estimate_ms(), 1),
    }
    rx.stop()
    cfg.close()
    return [res]


def format_markdown(report, baseline=None):
    lines = ["# PhoneMic Benchmark Report", "", "## Environment Metadata"]
    for k, v in report["metadata"].items():
        lines.append(f"- **{k}**: `{v}`")
    lines.append("")

    base_l1 = {r["name"]: r for r in baseline.get("level1", [])} if baseline else {}
    if report.get("level1"):
        lines += [
            "## Level 1: Isolated Microbenchmarks",
            "| Kernel | Wall ns/call | CPU ns/call | Peak B/call |" + (" vs Baseline |" if base_l1 else ""),
            "|---|---:|---:|---:|" + ("---:|" if base_l1 else ""),
        ]
        for r in report["level1"]:
            delta = ""
            if r["name"] in base_l1 and base_l1[r["name"]]["wall_ns_per_call"] > 0:
                b = base_l1[r["name"]]["wall_ns_per_call"]
                pct = ((r["wall_ns_per_call"] - b) / b) * 100.0
                delta = f" {pct:+.1f}% |"
            lines.append(
                f"| `{r['name']}` | {r['wall_ns_per_call']:.1f} | {r['cpu_ns_per_call']:.1f} | {r['peak_traced_bytes_per_call']:.1f} |"
                + delta
            )
        lines.append("")

    base_l2 = {r["scenario"]: r for r in baseline.get("level2", [])} if baseline else {}
    if report.get("level2"):
        lines += [
            "## Level 2: Synthetic Integration Benchmarks",
            "| Scenario | CPU % | Peak Trace KiB | Details |" + (" vs Baseline CPU |" if base_l2 else ""),
            "|---|---:|---:|---|" + ("---:|" if base_l2 else ""),
        ]
        for r in report["level2"]:
            if r["scenario"].startswith("gui_"):
                det = f"p50={r['produce_p50_ms']}ms p95={r['produce_p95_ms']}ms pkts={r['packets']} plc={r['plc_frames']}"
            else:
                det = f"cb_p50={r['cb_p50_us']}us cb_p95={r['cb_p95_us']}us cb_max={r['cb_max_us']}us"
            delta = ""
            if r["scenario"] in base_l2 and base_l2[r["scenario"]]["cpu_pct"] > 0:
                b = base_l2[r["scenario"]]["cpu_pct"]
                pct = ((r["cpu_pct"] - b) / b) * 100.0
                delta = f" {pct:+.1f}% |"
            lines.append(f"| `{r['scenario']}` | {r['cpu_pct']:.2f}% | {r['traced_peak_kib']:.1f} | {det} |" + delta)
        lines.append("")

    if report.get("level3"):
        lines += ["## Level 3: Real-Device Session", "```json", json.dumps(report["level3"], indent=2), "```"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="PhoneMic 3-Tier Benchmark Harness")
    parser.add_argument("--level", choices=["1", "2", "3", "all"], default="all")
    parser.add_argument("--calls", type=int, default=3000)
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--audio-backend", default="fake_sd")
    parser.add_argument("--latency-mode", default="low")
    parser.add_argument("--android-model", default="")
    parser.add_argument("--android-api", default="")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--md-out", default="")
    parser.add_argument("--compare", default="")
    args = parser.parse_args()

    if np is None:
        print(f"Benchmark requires numpy ({_NP_ERR}). Metadata-only preview:", file=sys.stderr)
        print(json.dumps(collect_metadata(args), indent=2))
        return 2

    report = {"metadata": collect_metadata(args), "level1": [], "level2": [], "level3": []}
    if args.level in ("1", "all"):
        report["level1"] = run_level1(calls=args.calls)
    if args.level in ("2", "all"):
        report["level2"] = [
            run_level2_gui(args.duration, phones=1, transport="udp"),
            run_level2_gui(args.duration, phones=4, transport="udp"),
            run_level2_gui(args.duration, phones=2, transport="tcp"),
            run_level2_cli(args.duration, phones=1),
            run_level2_cli(args.duration, phones=4),
        ]
    if args.level == "3":
        report["level3"] = run_level3(duration_s=args.duration, port=args.port)

    baseline = None
    if args.compare and os.path.exists(args.compare):
        with open(args.compare, "r", encoding="utf-8") as f:
            baseline = json.load(f)

    md = format_markdown(report, baseline=baseline)
    print(md)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    if args.md_out:
        with open(args.md_out, "w", encoding="utf-8") as f:
            f.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
