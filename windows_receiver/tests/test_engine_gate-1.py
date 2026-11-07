"""Push-to-talk / push-to-mute gate: silent output, click-free ramps, no pause commands to the phone, silent recordings."""
import os, time, socket, struct, tempfile, wave
import _path  # noqa: F401
import numpy as np
import fake_sd
from phonemic.config import ConfigManager
from phonemic.engine import Receiver
from phonemic import system

PORT = 25061


def tone(i, amp=0.3):
    n = np.arange(480) + i * 480
    return (np.sin(2 * np.pi * 440 * n / 48000) * amp * 32767).astype("<i2").tobytes()


def test_gate_silences_output_ramps_without_clicks_and_never_pauses_the_phone():
    d = tempfile.mkdtemp(); cfg = ConfigManager(os.path.join(d, "c.json")); cfg.data["network"]["port"] = PORT
    cfg.data["recording"]["folder"] = os.path.join(d, "rec"); cfg.data["recording"]["source"] = "raw"
    fx = cfg.data["studio_fx"]; fx.update(smart_noise_cancel=False, gate_enabled=False, lowcut_enabled=False)
    fake_sd.OutputStream.registry.clear()
    rx = Receiver(cfg, sd_module=fake_sd, netinfo=system.NetworkInfo())
    commands = []
    rx.net.send_control = lambda cmd, addr, transport: commands.append(cmd) or True
    rx.start(); time.sleep(0.3)
    stream = fake_sd.OutputStream.registry[0]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sent = [0]
    def pump(seconds):
        t0 = time.perf_counter(); n0 = sent[0]
        while time.perf_counter() - t0 < seconds:
            sock.sendto(b"PM01" + struct.pack(">I", sent[0]) + tone(sent[0]), ("127.0.0.1", PORT)); sent[0] += 1
            time.sleep(max(0, t0 + (sent[0] - n0) * 0.01 - time.perf_counter()))
    def tail(sec=0.1):
        return np.concatenate(stream.captured[-int(sec * 100):])
    rx.toggle_recording()
    pump(0.6); assert np.max(np.abs(tail())) > 0.25, "open microphone passes audio"

    rx.configure_talk_keys(True)                       # a push-to-talk key is set and not held
    n_before = len(stream.captured); pump(0.5)
    cap = np.concatenate(stream.captured[n_before:])
    assert np.max(np.abs(cap[-4800:])) < 1e-6, "silent while the key is not held"
    assert np.max(np.abs(np.diff(cap))) < 0.03, "closing ramps instead of clicking"
    assert rx.processor.level_db == -80.0, "meters show silence while gated"

    n_before = len(stream.captured); rx.set_ptt_held(True); pump(0.5)
    cap = np.concatenate(stream.captured[n_before:])
    assert np.max(np.abs(cap[-4800:])) > 0.25 and np.max(np.abs(np.diff(cap))) < 0.03, "opening ramps too"

    rx.set_hold_mute(True); pump(0.4); assert np.max(np.abs(tail())) < 1e-6, "push-to-mute wins over an open talk key"
    rx.set_hold_mute(False); pump(0.4); assert np.max(np.abs(tail())) > 0.25
    rx.configure_talk_keys(False); rx.set_ptt_held(False); pump(0.3); assert np.max(np.abs(tail())) > 0.25, "clearing the key re-opens the microphone"
    assert commands == [], "gating must not send pause/resume commands to the phone"

    rx.set_paused(True); pump(0.2); rx.set_paused(False)
    assert len(commands) == 2, "the Mute button still tells the phone"

    rx.configure_talk_keys(True); rx.set_ptt_held(False); pump(0.4)                # recorded raw track must be silent while gated
    path = rx.toggle_recording()[1]; time.sleep(0.2)
    w = wave.open(path); frames = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768.0
    assert np.max(np.abs(frames[:20000])) > 0.2, "the first seconds were open"
    assert np.max(np.abs(frames[-9600:])) < 1e-4, "the recording is silent while the gate is closed"
    rx.stop(); cfg.close()


if __name__ == "__main__":
    test_gate_silences_output_ramps_without_clicks_and_never_pauses_the_phone(); print("PASS gate")
