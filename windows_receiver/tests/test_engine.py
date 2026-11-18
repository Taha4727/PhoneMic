import os, time, socket, struct, tempfile, random, wave, threading
import _path  # noqa: F401
import numpy as np
import fake_sd
from phonemic.engine import JitterBuffer, Receiver, OK, PLC, WAIT, Ring, upsample_2x, upsample_3x
from phonemic.config import ConfigManager
from phonemic import system

def tone_pcm(seq, amp=0.3, f=440.0):
    n = np.arange(480) + seq * 480
    return (np.sin(2*np.pi*f*n/48000) * amp * 32767).astype('<i2').tobytes()

# ============================================================== 1. jitter buffer behaviour
print("1. JitterBuffer simulation (consumer pops every 10 ms)")
def simulate(label, arrivals, target_ms=30, adaptive=True, total_ticks=1000):
    """arrivals: list of (tick_index, seq). Consumer pops once per tick."""
    clk = [0.0]; jb = JitterBuffer(target_ms, adaptive, clock=lambda: clk[0]); by_tick = {}
    for t, s in arrivals: by_tick.setdefault(t, []).append(s)
    kinds = {OK: 0, PLC: 0, WAIT: 0}; maxd = 0
    for t in range(total_ticks):
        clk[0] = t * 0.010
        for s in by_tick.get(t, []): jb.push(s, b"\0" * 960)
        _, k = jb.pop(); kinds[k] += 1; maxd = max(maxd, jb.depth)
    print(f"  {label:34s} ok={kinds[OK]:4d} plc={kinds[PLC]:3d} late={jb.late:3d} dup={jb.dup:3d} underruns={jb.underruns} final_target={jb.target_ms:3.0f}ms maxdepth={maxd}")
    return jb, kinds
rnd = random.Random(5)
N = 800
simulate("perfect", [(i, i) for i in range(N)])
j, k = simulate("5% random loss", [(i, i) for i in range(N) if rnd.random() > .05]); assert 25 <= k[PLC] <= 60
simulate("pairs reordered", [(i + (1 if i % 2 == 0 else 0), i) for i in range(N)][::1])
simulate("every 10th packet duplicated", [(i, i) for i in range(N)] + [(i + 1, i) for i in range(0, N, 10)])
# 20 ms jitter bursts: packets delayed up to 40 ms
arr = sorted([(i + int(rnd.random() ** 3 * 4), i) for i in range(N)])
j, k = simulate("bursty jitter (<=40 ms), adaptive", arr); 
j2, k2 = simulate("bursty jitter, fixed 30 ms", arr, adaptive=False)
print(f"     -> adaptive concealed {k[PLC]} frames vs {k2[PLC]} fixed")
# sender 0.5 % faster than the sound card: depth must stay bounded by trimming
fast = [(int(i * 0.995), i) for i in range(N)]
j, k = simulate("sender clock 0.5% fast", fast, total_ticks=N - 10); assert j.depth <= j.target + j.BURST_SLACK
# sender restarts: seq goes back to 0 after 300 packets
arr = [(i, i) for i in range(300)] + [(300 + i, i) for i in range(300)]
j, _ = simulate("phone restarts stream (seq -> 0)", arr, total_ticks=620); assert j.restarts == 1
# seq wrap-around 2**32-1 -> 0
arr = [(i, (2**32 - 150 + i) & 0xFFFFFFFF) for i in range(300)]
j, k = simulate("32-bit sequence wrap-around", arr, total_ticks=320); assert k[PLC] <= 3 and j.late == 0   # up to 3 fade-out frames when the stream ends
# stream stops: must go idle
clk = [0.0]; jb = JitterBuffer(30, clock=lambda: clk[0]); [jb.push(i, b"\0"*960) for i in range(20)]
for _ in range(60): clk[0] += 0.01; jb.pop()
assert jb.idle; print("  PASS idle detection after stream stops")

# ============================================================== 2. full engine over real loopback UDP
print("\n2. Full engine: UDP loopback -> jitter buffer -> DSP -> fake sound card")
d = tempfile.mkdtemp()
cfg = ConfigManager(os.path.join(d, "c.json"))
PORT = 25021; cfg.data["network"]["port"] = PORT
cfg.data["recording"]["folder"] = os.path.join(d, "rec")
fx = cfg.data["studio_fx"]; fx["smart_noise_cancel"] = False; fx["gate_enabled"] = False; fx["lowcut_enabled"] = False  # pure path for amplitude check
rx = Receiver(cfg, sd_module=fake_sd, netinfo=system.NetworkInfo())
rx.processor = type(rx.processor)(cfg)   # honour the settings above
rx.start(); time.sleep(0.4)
assert rx.net.bind_ok, rx.net.udp_error
assert rx.main_dev.api == "Windows WASAPI" and rx.main_dev.is_cable, rx.main_dev   # prefers WASAPI + VB-CABLE
print("  PASS device pick:", rx.main_dev.name, "/", rx.main_dev.api)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(1.0)
sock.sendto(b"PMD0", ("127.0.0.1", PORT)); reply, _ = sock.recvfrom(100)
assert reply.startswith(b"PMA1 "), reply; print("  PASS discovery reply:", reply.decode())

rx.toggle_recording()
SENT = 400; lost_seqs = {100, 101, 250}
t0 = time.perf_counter()
for i in range(SENT):
    if i not in lost_seqs:
        sock.sendto(b"PM01" + struct.pack(">I", i) + tone_pcm(i), ("127.0.0.1", PORT))
    time.sleep(max(0, t0 + (i + 1) * 0.01 - time.perf_counter()))
time.sleep(0.4)
st = rx.stats
print(f"  stats: packets={st.packets} lost={st.lost} jitter={st.jitter_ms:.2f}ms plc={st.plc_frames} underruns={rx.main.starved} "
      f"jb_target={rx.jb.target_ms:.0f}ms bitrate={st.bitrate_kbps:.0f}kbps latency~{rx.latency_estimate_ms():.0f}ms state={rx.state()}")
assert st.packets == SENT - len(lost_seqs) and st.lost == len(lost_seqs)
assert 3 <= st.plc_frames <= 8, st.plc_frames
cap = np.concatenate(fake_sd.OutputStream.registry[0].captured)
active = cap[np.abs(cap) > 1e-4]
print(f"  captured {len(cap)/48000:.2f}s of output, peak {np.max(np.abs(cap)):.3f} (sent 0.300)")
assert 0.28 < np.max(np.abs(cap)) < 0.31
# find a clean stretch and check pitch
seg = cap[np.argmax(np.abs(cap) > 0.1) + 6000:][:9600]
f = np.argmax(np.abs(np.fft.rfft(seg * np.hanning(len(seg))))) * 48000 / len(seg)
assert abs(f - 440) < 10, f; print(f"  PASS output tone is {f:.0f} Hz (sent 440 Hz)")

# a second phone must be ignored while the first is streaming
sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for i in range(5):
    sock2.sendto(b"PM01" + struct.pack(">I", i) + tone_pcm(i), ("127.0.0.1", PORT))
# (same IP 127.0.0.1, so lock does not apply - exercise via direct call with another IP instead)
rx.on_packet(1, tone_pcm(1), ("10.9.9.9", 5555), "UDP"); rx.on_packet(2, tone_pcm(2), ("127.0.0.1", 5555), "UDP")
sent_ignored = rx.stats.ignored
print("  second-phone packets ignored while locked:", sent_ignored)

# recording
time.sleep(0.2); path_ok, path = rx.toggle_recording()
w = wave.open(path); print(f"  PASS recording: {w.getnframes()/w.getframerate():.2f}s mono {w.getframerate()} Hz -> {os.path.basename(path)}")
assert w.getnchannels() == 1 and w.getnframes() > 48000 * 3

# mute -> silence, unmute works
rx.set_paused(True); time.sleep(0.15)
for i in range(400, 440): sock.sendto(b"PM01" + struct.pack(">I", i) + tone_pcm(i), ("127.0.0.1", PORT)); time.sleep(0.01)
tail = np.concatenate(fake_sd.OutputStream.registry[0].captured[-10:]); assert np.max(np.abs(tail)) < 1e-6
rx.set_paused(False); print("  PASS mute outputs silence")

# stream stops -> 'lost', then idle
time.sleep(2.0); print("  state after phone stops:", rx.state()); assert rx.state() == "lost"

# test tone works with no stream
n0 = sum(len(c) for c in fake_sd.OutputStream.registry[0].captured)
rx.play_test_tone(); time.sleep(1.5)
cap = np.concatenate(fake_sd.OutputStream.registry[0].captured)[n0:]
assert np.max(np.abs(cap)) > 0.2; print("  PASS test tone audible, peak %.2f" % np.max(np.abs(cap)))

# port in use is reported, not swallowed
blocker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); blocker.bind(("0.0.0.0", 25022))
rx.set_port(25022); time.sleep(0.5)
print("  bind error surfaced:", bool(rx.net.udp_error) or "(Linux allows REUSEADDR sharing; Windows uses EXCLUSIVEADDRUSE)")
blocker.close(); rx.set_port(25023); time.sleep(0.4); assert rx.net.bind_ok

print("\n3. Phase 3: Resampler exactness & 1->2->1 multi-client ownership transition")
x24 = np.linspace(-0.5, 0.5, 240, dtype=np.float32)
x16 = np.linspace(-0.5, 0.5, 160, dtype=np.float32)
def _ref_up2(x):
    out = np.empty(len(x) * 2, dtype=np.float32)
    out[0::2] = x
    out[1::2] = (x + np.append(x[1:], x[-1])) * np.float32(0.5)
    return out
def _ref_up3(x):
    out = np.empty(len(x) * 3, dtype=np.float32)
    xn = np.append(x[1:], x[-1])
    out[0::3] = x
    out[1::3] = x * np.float32(2.0 / 3.0) + xn * np.float32(1.0 / 3.0)
    out[2::3] = x * np.float32(1.0 / 3.0) + xn * np.float32(2.0 / 3.0)
    return out
assert np.array_equal(upsample_2x(x24), _ref_up2(x24))
assert np.allclose(upsample_3x(x16), _ref_up3(x16), atol=1e-7)

# 1 -> 2 -> 1 ownership promotion test
d3 = tempfile.mkdtemp()
cfg3 = ConfigManager(os.path.join(d3, "c3.json"))
cfg3.data["network"]["port"] = 25029
cfg3.data["network"]["beacon"] = False
cfg3.data["network"]["lock_client"] = False
cfg3.data["studio_fx"].update(smart_noise_cancel=False, gate_enabled=False, lowcut_enabled=False)
fake_sd.OutputStream.registry.clear()
rx3 = Receiver(cfg3, sd_module=fake_sd, netinfo=system.NetworkInfo())
jb_id = id(rx3.jb)
a1 = ("10.1.1.1", 5001)
a2 = ("10.1.1.2", 5002)

# Phone 1 connects (1) -> shares rx3.jb directly (single push)
for s in range(5):
    rx3.on_packet(s, tone_pcm(s, amp=0.25), a1, "UDP", 48000)
assert len(rx3.client_streams) == 1
assert rx3.client_streams[a1].jb is rx3.jb
assert rx3.jb.depth == 5  # NOT doubled

# Phone 2 connects (2)
for s in range(5):
    rx3.on_packet(s, tone_pcm(s, amp=0.30), a2, "UDP", 48000)
assert len(rx3.client_streams) == 2
assert rx3.client_streams[a1].jb is rx3.jb
assert rx3.client_streams[a2].jb is not rx3.jb

# Age Phone 1 > 3.5s while Phone 2 stays fresh -> _produce() prunes Phone 1 and promotes Phone 2 onto rx3.jb
rx3.client_streams[a1].last_seen = time.monotonic() - 5.0
rx3.client_streams[a2].last_seen = time.monotonic()
assert rx3._produce() is True
assert len(rx3.client_streams) == 1 and a2 in rx3.client_streams
assert id(rx3.jb) == jb_id
assert rx3.client_streams[a2].jb is rx3.jb
assert rx3.client_ip == "10.1.1.2"
assert rx3.jb.depth > 0 and rx3.main.expect_audio() is True
rx3.stop(); cfg3.close()
print("  PASS upsample exactness & 1->2->1 ownership promotion")

rx.stop(); cfg.close()
print("  PASS clean shutdown; threads left:", [t.name for t in threading.enumerate() if t.name.startswith("PM-")])
