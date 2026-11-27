"""Tests for the Cat Voice Preview feature (assets, config, DSP/engine routing, and Studio UI)."""
import hashlib
import io
import os
import re
import struct
import tempfile
import types
import sys
import wave

import _path  # noqa: F401
import fake_tk; fake_tk.install()

try:
    import numpy as np
    HAS_NUMPY = True
except ModuleNotFoundError:
    HAS_NUMPY = False

    class _DummyArr(list):
        dtype = float

        def __init__(self, seq=(), shape=None):
            if isinstance(seq, int):
                seq = [0.0] * seq
            super().__init__(seq)
            self.shape = shape if shape is not None else (len(self),)

        def __truediv__(self, o): return self
        def __rtruediv__(self, o): return self
        def __mul__(self, o): return self
        def __rmul__(self, o): return self
        def __add__(self, o): return self
        def __sub__(self, o): return self
        def astype(self, *a, **k): return self
        def copy(self): return _DummyArr(self, shape=self.shape)
        def setflags(self, *a, **k): pass
        def max(self): return max(self) if self else 0.0
        def min(self): return min(self) if self else 0.0

    class _NpStub(types.ModuleType):
        float32 = float
        float64 = float
        int16 = int
        int32 = int
        uint8 = int
        int8 = int
        __version__ = "0.0-stub"

        def zeros(self, n, *a, **k):
            if isinstance(n, tuple):
                return _DummyArr(int(n[0]) if n else 0, shape=n)
            return _DummyArr(int(n) if isinstance(n, (int, float)) else 0)

        def ones(self, n, *a, **k):
            k_n = int(n) if isinstance(n, (int, float)) else 0
            return _DummyArr([1.0] * k_n)

        def full(self, n, val, *a, **k):
            k_n = int(n) if isinstance(n, (int, float)) else 0
            return _DummyArr([val] * k_n)

        def arange(self, *a, **k):
            nums = [int(x) for x in a[:3]]
            return _DummyArr(range(*nums) if nums else ())

        def geomspace(self, a, b, n=50, *args, **k):
            return _DummyArr([float(a)] * int(n))

        def linspace(self, a, b, n=50, *args, **k):
            cnt = max(1, int(n))
            step = (b - a) / max(1, cnt - 1)
            return _DummyArr([a + i * step for i in range(cnt)])

        def array(self, x, *a, **k):
            return _DummyArr(x)

        def any(self, x):
            return any(bool(v) for v in x)

        def abs(self, x):
            return _DummyArr([abs(v) for v in x])

        def max(self, x):
            return max(x) if x else 0.0

        def sqrt(self, x):
            return _DummyArr(x) if isinstance(x, list) else float(x) ** 0.5

        def concatenate(self, seqs, *a, **k):
            out = []
            for s in seqs:
                out.extend(s)
            return _DummyArr(out)

        def __getattr__(self, name):
            return lambda *a, **k: _DummyArr()

    np = _NpStub("numpy")
    sys.modules["numpy"] = np

import fake_sd
from phonemic import cat_preview, cat_sound_data, config as cfg_mod, settings_meta as sm, system, widgets, gui
from phonemic.const import FRAME, SAMPLE_RATE
from phonemic.engine import Receiver


def _walk(w):
    yield w
    for c in list(getattr(w, "children", [])):
        yield from _walk(c)


def _write_pcm16_wav(path, frames_list, rate=44100, channels=1):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack("<" + "h" * len(frames_list), *frames_list))


def test_bundled_asset_and_spec():
    asset = cat_preview.default_cat_wav_path()
    assert os.path.isfile(asset), f"Missing bundled cat asset: {asset}"
    with wave.open(asset, "rb") as wf:
        assert wf.getcomptype() == "NONE"
        assert wf.getnchannels() in (1, 2)
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100
        assert wf.getnframes() > 20000

    spec_path = os.path.join(_path.ROOT, "PhoneMicReceiver.spec")
    spec = open(spec_path, encoding="utf-8").read()
    assert '("assets", "assets")' in spec
    assert '"phonemic.cat_preview"' in spec
    assert '"phonemic.cat_sound_data"' in spec


def test_receiver_icon_matches_android_app():
    import base64
    from phonemic import icon as icon_mod
    png_disk = os.path.join(_path.ROOT, "assets", "phonemic.png")
    ico_disk = os.path.join(_path.ROOT, "assets", "phonemic.ico")
    assert os.path.isfile(png_disk) and os.path.isfile(ico_disk)
    raw_disk = open(png_disk, "rb").read()
    assert base64.b64decode(icon_mod.TRAY_PNG_B64) == raw_disk
    assert len(base64.b64decode(icon_mod.PNG_B64)) > 1000


def test_embedded_cat_sound_fallback():
    raw = cat_sound_data.get_default_cat_wav_bytes()
    assert hashlib.sha256(raw).hexdigest() == cat_sound_data.CAT_MEOW_SHA256
    asset = cat_preview.default_cat_wav_path()
    assert raw == open(asset, "rb").read()
    with wave.open(io.BytesIO(raw), "rb") as wf:
        assert wf.getcomptype() == "NONE"
        assert wf.getnchannels() in (1, 2)
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100
        assert wf.getnframes() > 20000

    # Verify load_preview_buffer resolves to embedded bytes when disk asset is missing
    seen = []
    orig_decode = cat_preview._decode_wav_stream_48k_mono
    try:
        if not HAS_NUMPY:
            cat_preview._decode_wav_stream_48k_mono = lambda b, **k: (seen.append(b) or np.zeros(100))
        else:
            def _spy(b, **k):
                seen.append(b)
                return orig_decode(b, **k)
            cat_preview._decode_wav_stream_48k_mono = _spy
        buf, resolved, is_custom, fallback_err = cat_preview.load_preview_buffer(
            default_path="/nonexistent/_MEI_missing/assets/cat_meow.wav"
        )
    finally:
        cat_preview._decode_wav_stream_48k_mono = orig_decode

    assert resolved == "embedded:cat_meow.wav"
    assert is_custom is False
    assert fallback_err == ""
    assert seen == [raw]
    assert len(buf) > 0


def test_config_defaults_and_registry_isolation():
    assert cfg_mod.DEFAULTS["app"]["show_cat_preview"] is False
    assert cfg_mod.DEFAULTS["voice_changer"]["preview_wav_path"] == ""
    assert all("cat" not in s.key.lower() for s in sm.REGISTRY), "cat toggle must stay out of settings_meta.REGISTRY"

    # Also verify config serialization round-trip preserves defaults
    d = tempfile.mkdtemp()
    cm = cfg_mod.ConfigManager(os.path.join(d, "cfg.json"))
    assert cm.data["app"]["show_cat_preview"] is False
    assert cm.data["voice_changer"]["preview_wav_path"] == ""
    cm.close()


def test_vector_cat_icon_and_widget():
    root = widgets.create_root()
    canvas = widgets.tk.Canvas(root, width=20, height=20)
    widgets.draw_icon(canvas, "cat", widgets.T.BLUE_HI, 20)
    types_drawn = [it["type"] for it in canvas.items.values()]
    assert "polygon" in types_drawn and "oval" in types_drawn and "line" in types_drawn
    assert "text" not in types_drawn, "cat icon must use vector geometry, never emoji/text"

    clicks = []
    menus = []
    btn = widgets.CatPreviewButton(
        root,
        command=lambda: clicks.append("play"),
        menu_command=lambda w, e: menus.append((w, e)),
        size=18,
    )
    assert [it["type"] for it in btn.canvas.items.values() if it["type"] == "text"] == []
    btn.canvas.event_generate("<Button-1>")
    assert clicks == ["play"]
    btn.canvas.event_generate("<Button-3>")
    assert len(menus) == 1 and menus[0][0] is btn

    btn.set_playing(True)
    assert btn._cat_playing is True
    btn.set_playing(False)
    assert btn._cat_playing is False
    btn.refresh_theme()


def test_ui_visibility_bare_toggle_and_controls():
    d = tempfile.mkdtemp()
    cfg = cfg_mod.ConfigManager(os.path.join(d, "ui.json"))
    cfg.data["app"]["first_run_done"] = True

    # Build a lightweight mock Receiver when running without real numpy
    if HAS_NUMPY:
        rx = Receiver(cfg, sd_module=fake_sd, netinfo=system.NetworkInfo())
    else:
        from phonemic.dsp import FX_BASE, VoiceChanger

        class _MockVoice(VoiceChanger):
            def __init__(self):
                self.enabled = False
                self.mode = "Natural Pitch"
                self.pitch_semitones = 0.0
                self.formant_semitones = 0.0
                self.mix = 1.0
                self.active_preset = "Normal (Bypass)"
            def export(self):
                return {"enabled": self.enabled, "mode": self.mode, "pitch_semitones": self.pitch_semitones,
                        "formant_semitones": self.formant_semitones, "mix": self.mix}
            def load(self, d, name=None):
                for k, v in d.items():
                    setattr(self, k, v)
                if name is not None:
                    self.active_preset = name

        class _MockProc:
            def __init__(self):
                for k, v in FX_BASE.items():
                    setattr(self, k, v)
                self.active_preset = "Default (Studio Clean)"
                self.fx_bypass = False
                self.viz_active = False
                self.dsp_ms = 0.2
                self.level_db = -80.0
                self.level_rms = 0.0
                self.clipped = False
                self.gain_reduction_db = 0.0
                self.deess_reduction_db = 0.0
                self.noise_cancel_amount = 0.65
                self.monitor_volume = 0.8
                self.denoiser = types.SimpleNamespace(delay_ms=10.0)
                self.agc = types.SimpleNamespace(gain_db=0.0)
                self.gate = types.SimpleNamespace(is_open=False)
                self.voice_changer = _MockVoice()
                self.analyzer = types.SimpleNamespace(bands=[0.0] * 40, scope=[0.0] * 128)
            def export_fx(self):
                return {k: getattr(self, k) for k in FX_BASE}
            def apply_fx(self, d, name=None):
                for k, v in d.items():
                    setattr(self, k, v)
                if name is not None:
                    self.active_preset = name
            def set_param(self, k, v):
                setattr(self, k, v)
                return True
            def eq_band(self, n):
                return {"on": False, "type": "peak", "freq": 1000.0, "gain": 0.0, "q": 1.0}
            def eq_curve_db(self, freqs):
                return [0.0] * len(freqs)
            @property
            def latency_ms(self):
                return 0.0

        class _MockPort:
            active = False
            error = ""
            latency_ms = 5.0
            starved = 0
            xruns = 0
            class _Ring:
                def level(self): return 0
            ring = _Ring()

        class _MockRx:
            def __init__(self):
                self.config = cfg
                self.processor = _MockProc()
                self.devices = system.list_output_devices(fake_sd)
                self.api = "WASAPI"
                self.main_dev = self.devices[0] if self.devices else None
                self.monitor_dev = self.devices[0] if self.devices else None
                self.main = _MockPort()
                self.monitor = _MockPort()
                self.netinfo = system.NetworkInfo()
                self.net = types.SimpleNamespace(port=50000, udp_error="", tcp_error="")
                self.jb = types.SimpleNamespace(
                    depth_ms=20.0, target_ms=20.0, late=0, dup=0, grown=0,
                    skipped_total=0, restarts=0, underruns=0, reset=lambda: None,
                )
                self.stats = types.SimpleNamespace(
                    stream_start=0.0, packets=0, lost=0, plc_frames=0, jitter_ms=0.0,
                    reordered=0, loss_pct=0.0, bitrate_kbps=0.0,
                    last_packet=0.0, uptime_s=0.0, reset_session=lambda: None,
                )
                self.recorder = types.SimpleNamespace(active=False, seconds=0.0)
                self.client_streams = {}
                self.client_ip = ""
                self.transport = "UDP"
                self.client_sample_rate = 48000
                self.paused = False
                self.monitoring = False
                self.gate_closed = False
                self.ptt_active = False
                self.ptt_held = False
                self.hold_mute = False
                self.log = types.SimpleNamespace(
                    serial=0, entries=[],
                    warn=lambda m: None, error=lambda m: None, info=lambda m: None, text=lambda: "",
                )
                self.preview_active = False
                self.play_calls = 0
                self.stop_calls = 0
                self.custom_path = ""
            def state(self): return "waiting"
            def latency_estimate_ms(self): return 20.0
            def play_test_tone(self): pass
            def cat_preview_info(self):
                if self.custom_path and os.path.isfile(self.custom_path):
                    return os.path.basename(self.custom_path), True
                return "Default cat", False
            def set_cat_preview_wav(self, p=""):
                self.custom_path = p
                self.config.data["voice_changer"]["preview_wav_path"] = p
                self.config.save_soon()
                return True, self.cat_preview_info()[0]
            def play_cat_preview(self):
                self.play_calls += 1
                self.preview_active = True
                return True, self.cat_preview_info()[0]
            def stop_cat_preview(self):
                self.stop_calls += 1
                self.preview_active = False
            def configure_talk_keys(self, *a, **k): pass
            def toggle_pause(self): self.paused = not self.paused; return self.paused
            def toggle_monitor(self): self.monitoring = not self.monitoring; return self.monitoring, ""
            def toggle_recording(self): return False, ""
            def stop(self): pass
            def refresh_devices(self): pass
            def open_main(self): pass
            def __getattr__(self, name):
                return lambda *a, **k: None

        rx = _MockRx()

    app = gui.App(rx)
    dash = app.pages["dashboard"]

    # 1. Hidden by default on Studio Home and Audio Studio Voice FX
    assert app.cat_preview_visible() is False
    assert dash.cat_btn.packed is None
    app.show_page("sound")
    snd = app.pages["sound"]
    snd.pick_stage("voice")
    assert snd.voice_widgets["cat_bar"].packed is None

    # 2. Settings General tab has bare 'cat' toggle with NO explanation text
    app.show_page("settings")
    sp = app.pages["settings"]
    assert sp.cat_toggle.get() is False
    cat_labels = [
        w.cget("text")
        for w in _walk(sp.cat_row)
        if isinstance(w, widgets.tk.Label)
    ]
    assert cat_labels == ["cat"], f"Expected bare 'cat' label with zero explanation, got {cat_labels}"

    # 3. Toggling 'cat' ON reveals icon on Home and bar in Voice FX without restart
    sp.cat_toggle._click()
    assert app.cat_preview_visible() is True
    assert cfg.data["app"]["show_cat_preview"] is True
    assert dash.cat_btn.packed is not None
    assert snd.voice_widgets["cat_bar"].packed is not None

    # Verify zero cat emoji characters exist on any cat button/bar
    for w in list(_walk(dash.cat_btn)) + list(_walk(snd.voice_widgets["cat_bar"])):
        if isinstance(w, widgets.tk.Label):
            txt = w.cget("text") or ""
            assert "\U0001f431" not in txt and "\U0001f408" not in txt

    # 4. Left click previews cat voice; right-click opens dark popup menu
    dash.cat_btn.canvas.event_generate("<Button-1>")
    assert rx.preview_active is True
    app.show_page("dashboard")
    dash.refresh_fast()
    assert dash.cat_btn._cat_playing is True
    assert "Preview" in dash.read_label.cget("text")

    dash.cat_btn.canvas.event_generate("<Button-3>")
    assert app._cat_menu is not None and app._cat_menu.winfo_exists()
    app._close_cat_menu()
    assert app._cat_menu is None

    # 5. Theme rebuild keeps cat preview enabled & visible
    app.binder.set(sm.BY_KEY["app.accent"], "blue")
    assert app.cat_preview_visible() is True
    assert app.pages["dashboard"].cat_btn.packed is not None
    app.binder.set(sm.BY_KEY["app.accent"], "teal")

    # 6. Toggling 'cat' OFF hides UI and stops playback
    app.show_page("settings")
    sp = app.pages["settings"]
    sp.cat_toggle._click()
    assert app.cat_preview_visible() is False
    assert rx.preview_active is False
    assert app.pages["dashboard"].cat_btn.packed is None
    app.show_page("sound")
    snd = app.pages["sound"]
    snd.pick_stage("voice")
    assert snd.voice_widgets["cat_bar"].packed is None

    # 7. Upload & reset via filedialog
    tmp_wav = os.path.join(d, "custom_cat.wav")
    _write_pcm16_wav(tmp_wav, [0, 5000, -5000, 0] * 100, rate=44100)
    orig_open = gui.filedialog.askopenfilename
    try:
        gui.filedialog.askopenfilename = lambda **k: tmp_wav
        app.set_cat_preview_visible(True)
        app.upload_cat_wav()
        lbl, is_cust = rx.cat_preview_info()
        assert is_cust is True and lbl == "custom_cat.wav"
        app.reset_cat_wav()
        lbl2, is_cust2 = rx.cat_preview_info()
        assert is_cust2 is False and lbl2 == "Default cat"
    finally:
        gui.filedialog.askopenfilename = orig_open

    # 8. Multi-page navigation and MinimalView live meter during preview
    for key in ("connect", "log", "sound", "settings", "dashboard"):
        app.show_page(key)
        app._slow_t = 0.0
        app.tick()
    assert not app._err_seen, app._err_seen

    app.toggle_ui_mode()
    assert app.ui_mode == "minimal" and app.minimal_view is not None
    mv = app.minimal_view
    if isinstance(rx, Receiver):
        rx._preview_left = FRAME
    else:
        rx.preview_active = True
    rx.processor.level_db = -12.0
    rx.processor.level_rms = 0.25
    mv.refresh_fast()
    assert "-∞" not in mv.lbl_db.cget("text")
    if isinstance(rx, Receiver):
        rx._preview_left = 0
    else:
        rx.preview_active = False
    mv.peak_s = -80.0
    mv.refresh_fast()
    assert mv.lbl_db.cget("text") == "-∞ dB"
    app.toggle_ui_mode()

    # 9. Real-Tk parity guard: sync_cat_preview uses standard winfo_manager(), not fake_tk's .packed
    for fname in ("gui.py", "pages.py"):
        src = open(os.path.join(_path.ROOT, "phonemic", fname), encoding="utf-8").read()
        assert ".packed" not in src, f"{fname} must use winfo_manager() instead of fake_tk-only .packed"

    app.on_close()


def test_real_numpy_cat_dsp_and_routing():
    if not HAS_NUMPY:
        print("   SKIP numpy-only engine DSP/WAV decoding checks (numpy not installed in this container)")
        return

    # 1. Custom 22.05kHz stereo WAV decoding & normalization
    d = tempfile.mkdtemp()
    wav_path = os.path.join(d, "meow_22k_stereo.wav")
    samples = []
    for i in range(2205):
        v = int(8000 * np.sin(2.0 * np.pi * 440.0 * i / 22050.0))
        samples.extend((v, v))
    _write_pcm16_wav(wav_path, samples, rate=22050, channels=2)

    buf = cat_preview.load_wav_48k_mono(wav_path)
    assert buf.dtype == np.float32
    assert abs(len(buf) - 4800) <= 5
    assert 0.65 <= float(np.max(np.abs(buf))) <= 0.72

    # 2. Corrupt file validation error
    bad_path = os.path.join(d, "bad.wav")
    with open(bad_path, "wb") as f:
        f.write(b"NOT_A_RIFF_FILE" * 10)
    ok_raised = False
    try:
        cat_preview.load_wav_48k_mono(bad_path)
    except ValueError:
        ok_raised = True
    assert ok_raised

    # 3. Engine preview routing (monitor vs main), recorder exclusion, and Voice Changer DSP effect
    cfg = cfg_mod.ConfigManager(os.path.join(d, "engine.json"))
    rx = Receiver(cfg, sd_module=fake_sd, netinfo=system.NetworkInfo())

    # Active main stream, monitor off -> opens _preview_port on monitor_dev so user hears preview, NOT main.ring/recorder
    rx.refresh_devices(initial=True)
    rx.open_main()
    ok, _ = rx.set_cat_preview_wav(wav_path)
    assert ok is True
    rx.processor.voice_changer.load({"enabled": True, "mode": "Robot", "pitch_semitones": -4.0, "formant_semitones": -2.0, "mix": 1.0}, "Robot")
    rx.recorder.q = object()
    assert rx.recorder.active is True
    rec_writes = []
    rx.recorder.write = lambda blk: rec_writes.append(blk)

    ok_play, _ = rx.play_cat_preview()
    assert ok_play and rx.preview_active
    assert rx.monitoring is False
    assert rx._preview_port.active is True
    assert rx._pace_port() is rx._preview_port
    rx.main.ring.clear()
    rx.monitor.ring.clear()
    rx._preview_port.ring.clear()
    assert rx._produce() is True
    assert rx._preview_port.ring.level() == FRAME
    assert rx.main.ring.level() == 0
    assert rx.monitor.ring.level() == 0
    assert rec_writes == [], "Preview audio must NEVER be recorded"

    # When monitor is off and no speaker/monitor port can open -> falls back to main.ring cleanly
    rx.stop_cat_preview()
    rx._preview_port.close()
    orig_mon_dev = rx.monitor_dev
    orig_main_dev = rx.main_dev
    rx.monitor_dev = None
    rx.main_dev = None
    try:
        ok_fb, _ = rx.play_cat_preview()
        assert ok_fb and rx._preview_port.active is False
        rx.main.ring.clear()
        assert rx._produce() is True
        assert rx.main.ring.level() == FRAME
        assert rec_writes == []
    finally:
        rx.monitor_dev = orig_mon_dev
        rx.main_dev = orig_main_dev

    # With monitor active -> closes _preview_port and routes ONLY to monitor.ring, NOT main.ring
    rx.monitoring = True
    assert rx._open_monitor() is True
    assert rx._preview_port.active is False
    rx.main.ring.clear()
    rx.monitor.ring.clear()
    assert rx._produce() is True
    assert rx.monitor.ring.level() == FRAME
    assert rx.main.ring.level() == 0
    assert rx._pace_port() is rx.monitor

    # Active phone + preview does not break when phone is paused/muted either
    rx.paused = True
    rx.main.ring.clear()
    rx.monitor.ring.clear()
    assert rx._produce() is True
    assert rx.monitor.ring.level() == FRAME

    rx.stop_cat_preview()
    assert rx.preview_active is False

    # 4. Engine plays embedded fallback cleanly when bundled disk asset is absent
    rx.set_cat_preview_wav("")
    orig_default = cat_preview.default_cat_wav_path
    import phonemic.engine as eng_mod
    orig_eng_default = eng_mod.default_cat_wav_path
    missing_path = os.path.join(d, "missing_bundle", "cat_meow.wav")
    try:
        cat_preview.default_cat_wav_path = lambda: missing_path
        eng_mod.default_cat_wav_path = lambda: missing_path
        ok_emb, lbl_emb = rx.play_cat_preview()
        assert ok_emb is True and lbl_emb == "Default cat"
        assert rx._preview_path == "embedded:cat_meow.wav"
        assert rx.preview_active is True
    finally:
        cat_preview.default_cat_wav_path = orig_default
        eng_mod.default_cat_wav_path = orig_eng_default
        rx.stop_cat_preview()

    rx.recorder.q = None
    rx._preview_port.close()
    rx.monitor.close()
    rx.main.close()
    cfg.close()


def test_preview_plays_when_monitor_is_off_stubbed():
    import threading
    from phonemic import engine as eng_mod

    class _NoThreadStream:
        def __init__(self, samplerate, channels, dtype, callback, blocksize=0, latency="low", device=None, extra_settings=None):
            self.device = device
            self.latency = 0.012
            self.active = False
        def start(self): self.active = True
        def stop(self): self.active = False
        def close(self): self.active = False

    sync_sd = types.SimpleNamespace(
        OutputStream=_NoThreadStream,
        WasapiSettings=fake_sd.WasapiSettings,
        query_devices=fake_sd.query_devices,
        query_hostapis=fake_sd.query_hostapis,
    )

    d = tempfile.mkdtemp()
    cfg = cfg_mod.ConfigManager(os.path.join(d, "stub_preview.json"))
    rx = Receiver.__new__(Receiver)
    rx.config = cfg
    rx.sd = sync_sd
    rx.log = eng_mod.EventLog()
    rx.stats = eng_mod.Stats()
    rx.netinfo = system.NetworkInfo()
    rx.jb = eng_mod.JitterBuffer(30, True)
    rx.processor = types.SimpleNamespace(monitor_volume=0.0)
    rx.monitoring = False
    rx.client_streams = {}
    rx.tone_left = 0
    rx._preview_lock = threading.Lock()
    rx._preview_samples = np.zeros(FRAME * 4)
    rx._preview_source_key = ("", "stub", 0, 0)
    rx._preview_is_custom = False
    rx._preview_path = "stub"
    rx._preview_pos = 0
    rx._preview_left = 0
    rx._preview_reset_dsp = False
    rx._preview_idle_at = 0.0
    if not HAS_NUMPY:
        rx._ensure_preview_loaded = lambda force=False: None
    rx._wake = threading.Event()
    rx.main = eng_mod.OutputPort("Main output", rx._wake, rx.sd, rx.log)
    rx.monitor = eng_mod.OutputPort("Monitor", rx._wake, rx.sd, rx.log)
    rx._preview_port = eng_mod.OutputPort("Cat Preview", rx._wake, rx.sd, rx.log)
    rx._preview_port.expect_audio = lambda: rx._preview_left > 0
    rx.refresh_devices(initial=True)
    rx.open_main()

    assert rx.main_dev.is_cable is True
    assert rx.monitor_dev.is_cable is False
    assert rx.monitoring is False

    ok, _ = rx.play_cat_preview()
    assert ok is True
    assert rx.monitoring is False
    assert rx._preview_port.active is True
    assert rx._preview_port.device is rx.monitor_dev
    assert rx._pace_port() is rx._preview_port
    assert rx._preview_gain() >= 0.8

    if HAS_NUMPY:
        rx._preview_port.ring.clear()
        rx.main.ring.clear()
        rx._route_preview_only(np.zeros(FRAME))
        assert rx._preview_port.ring.level() == FRAME
        assert rx.main.ring.level() == 0

    # Turning Monitor on cleanly closes _preview_port before opening monitor
    assert rx._open_monitor() is True
    assert rx._preview_port.active is False
    rx.monitoring = True
    assert rx._pace_port() is rx.monitor

    rx.stop_cat_preview()
    rx.monitor.close()
    rx.main.close()
    cfg.close()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
