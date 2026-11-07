"""Whole-GUI test against a strict fake Tk (Tk itself is not available in CI): every page is built, every control is
operated, and the new v0.10 behaviour (search, simple/advanced, info/reset, EQ editor, wizard, presets) is checked."""
import os
import json
import time
import socket
import struct
import threading
import tempfile
import random
import traceback
import types
import _path  # noqa: F401
import fake_tk; fake_tk.install()
import numpy as np
import fake_sd
from phonemic.config import ConfigManager
from phonemic.engine import Receiver
from phonemic import system, widgets, ui_kit, gui, pages, settings_meta as sm, presets_io as pio

PORT = 25031
d = tempfile.mkdtemp()
cfg = ConfigManager(os.path.join(d, "c.json"))
cfg.data["network"]["port"] = PORT
cfg.data["recording"]["folder"] = os.path.join(d, "rec")
cfg.data["app"]["first_run_done"] = True
rx = Receiver(cfg, sd_module=fake_sd, netinfo=system.NetworkInfo())
rx.start(); time.sleep(0.3)

stop = threading.Event()
def feeder():                                   # a live signal so meters, spectrum and gauges have data
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); i = 0; t0 = time.perf_counter(); rng = np.random.default_rng(1)
    while not stop.is_set():
        n = np.arange(480) + i * 480
        x = 0.25 * np.sin(2 * np.pi * 220 * n / 48000) + 0.1 * np.sin(2 * np.pi * 1800 * n / 48000) + rng.standard_normal(480) * 0.01
        s.sendto(b"PM01" + struct.pack(">I", i) + (x * 32767).astype('<i2').tobytes(), ("127.0.0.1", PORT)); i += 1
        time.sleep(max(0, t0 + i * 0.01 - time.perf_counter()))
threading.Thread(target=feeder, daemon=True).start(); time.sleep(0.8)

app = gui.App(rx)
NAV = [k for k, _, _ in gui.NAV]
def tick(n=2):
    for _ in range(n):
        app._slow_t = 0.0; app.tick(); time.sleep(0.03)
def walk(w):
    yield w
    for c in list(getattr(w, "children", [])):
        yield from walk(c)
def ev(**kw):
    return types.SimpleNamespace(x=kw.pop("x", 5), y=kw.pop("y", 5), delta=kw.pop("delta", 120), widget=kw.pop("widget", None), **kw)

print("1. every page builds and ticks")
for key in NAV + ["wizard"]:
    app.show_page(key); tick(2)
assert not app._err_seen, app._err_seen
print("   PASS", len(app.pages), "pages")

print("2. <Configure> events (unmapped 1x1, then real sizes) on every canvas widget")
n = 0
for key in NAV:
    app.show_page(key)
    for w in walk(app.pages[key]):
        for fn in list(w._bindings.get("<Configure>", [])):
            for (wd, ht) in ((1, 1), (640, 210), (240, 40)):
                w._opts["width"], w._opts["height"] = wd, ht; fn(types.SimpleNamespace(widget=w, width=wd, height=ht)); n += 1
    tick(1)
assert not app._err_seen, app._err_seen
print("   PASS", n, "events")

print("3. fuzz: operate every control on every page, in both views")
SKIP = ("Reset all settings", "Get VB-CABLE", "Windows sound settings", "Recording devices", "Open folder", "Choose folder", "Open crash log",
        "Open settings folder", "Run setup again", "Skip setup", "Finish", "Close")
errors, counts = [], dict(button=0, slider=0, toggle=0, segmented=0, combo=0, icon=0)
def fuzz():
    rnd = random.Random(9)
    for key in NAV:
        app.show_page(key); tick(1)
        for w in walk(app.pages[key]):
            try:
                if isinstance(w, widgets.FlatButton) and w.command and not any(t in w.cget("text") for t in SKIP) and w._enabled:
                    w.command(); counts["button"] += 1
                elif isinstance(w, widgets.Slider):
                    w._apply(rnd.uniform(w.lo, w.hi)); w._apply(rnd.uniform(w.lo, w.hi)); w._nudge(1); w._nudge(-1); w._reset(); counts["slider"] += 1
                elif isinstance(w, widgets.Toggle):
                    w._click(); w._click(); counts["toggle"] += 1
                elif isinstance(w, widgets.Segmented):
                    w._pick(rnd.choice(list(w.buttons))); counts["segmented"] += 1
                elif isinstance(w, widgets.Combo):
                    vals = list(w.cget("values") or [])
                    if vals and w.command: w.command(rnd.choice(vals)); counts["combo"] += 1
                elif isinstance(w, ui_kit.IconButton):
                    w._click(); w._hover(True); w._hover(False); counts["icon"] += 1
            except Exception:
                errors.append((key, type(w).__name__, traceback.format_exc()))
        tick(2)
for view in (False, True):
    app.binder.set(sm.BY_KEY["app.advanced_mode"], view); fuzz()
for e in errors[:4]: print("   ERROR", e[0], e[1]); print(e[2])
assert not errors and not app._err_seen, (len(errors), app._err_seen)
print("   PASS no exceptions;", counts, "| engine errors:", [m for _, l, m in rx.log.entries if l == "error"])

print("4. simple vs advanced view")
app.show_page("sound"); page = app.pages["sound"]; page.pick_stage("gate")
app.binder.set(sm.BY_KEY["app.advanced_mode"], False)
panel = page.panels["gate"]
simple = sum(r.packed is not None for r in panel["rows"]); total = len(panel["rows"])
app.binder.set(sm.BY_KEY["app.advanced_mode"], True)
adv = sum(r.packed is not None for r in panel["rows"])
assert simple == 2 and adv == total == 6, (simple, adv, total)
assert app.view_toggle.get() is True and cfg.data["app"]["advanced_mode"] is True
app.binder.set(sm.BY_KEY["app.advanced_mode"], False); assert app.view_toggle.get() is False
print(f"   PASS gate stage shows {simple} of {total} rows in Simple view, all {adv} in Advanced")

print("5. search finds settings and jumps to them (turning Advanced on when needed)")
sb = app.search; sb.showing_hint = False
sb.var.set("rumble"); sb._typed(); keys = [s.key for s in sb.hits]
assert "lowcut_hz" in keys and sb.popup is not None
app.show_page("dashboard"); sb.pick(keys.index("lowcut_hz"))
assert app.current == "sound" and page.stage_id == "filters"
row = next(r for r in page.panels["filters"]["rows"] if r.setting.key == "lowcut_hz")
assert row.expanded and row.packed is not None
app.binder.set(sm.BY_KEY["app.advanced_mode"], False)
sb.showing_hint = False; sb.var.set("hold"); sb._typed(); hold = [s.key for s in sb.hits].index("gate_hold_ms")
sb.pick(hold)
assert app.advanced is True and app.current == "sound" and page.stage_id == "gate"
sb.showing_hint = False; sb.var.set("zzzqqq"); sb._typed(); assert sb.hits == []
sb.clear(); assert sb.popup is None and sb.showing_hint
app.binder.set(sm.BY_KEY["app.advanced_mode"], False)
print("   PASS search results navigate to the right stage and row")

print("6. info button and per-setting reset")
page.pick_stage("gate")
row = next(r for r in page.panels["gate"]["rows"] if r.setting.key == "gate_threshold_db")
assert not row.expanded and row.details_label is None
row.info_btn._click(); assert row.expanded and row.details_label.cget("text") == row.setting.details
row.info_btn._click(); assert not row.expanded and row.details_label.packed is None
row.control._apply(-33.0); assert not app.binder.is_default(row.setting) and not row.reset_btn.faint and row.reset_btn.lit
row.reset_btn._click(); assert app.binder.is_default(row.setting) and row.reset_btn.faint
assert abs(app.proc.gate_threshold_db - sm.default_of(row.setting)) < 1e-9
print("   PASS")

print("7. dependent settings dim when their switch is off")
app.binder.set(sm.BY_KEY["gate_enabled"], False)
assert row.enabled is False and row.title_label.cget("fg") == widgets.T.DIM
app.binder.set(sm.BY_KEY["gate_enabled"], True); assert row.enabled is True
print("   PASS")

print("8. chain list: lights follow the effects; the voice entry opens the Voice page")
for sid, key in (("comp", "comp_enabled"), ("deess", "deess_enabled"), ("agc", "agc_enabled")):
    app.binder.set(sm.BY_KEY[key], True); assert page.chain.stage_state[sid]["led"] is True
    app.binder.set(sm.BY_KEY[key], False); assert page.chain.stage_state[sid]["led"] is False
assert page.chain.stage_state["input"]["led"] == "fixed" and page.chain.stage_state["output"]["led"] == "fixed"
page.chain.on_pick("voice"); assert app.current == "voice"
app.show_page("sound")
print("   PASS")

print("9. equalizer editor: drag, wheel, double-click, right-click")
page.pick_stage("eq"); ed = page.editor; ed._opts["width"], ed._opts["height"] = 560, 210
page.eq_pick(3); app.binder.set(sm.BY_KEY["eq3_gain"], 2.0); app.binder.set(sm.BY_KEY["eq3_freq"], 2500.0); app.binder.set(sm.BY_KEY["eq3_on"], True)
x, y = ed.node_xy(3)
ed._press(ev(x=x, y=y)); assert page.eq_band == 3
ed._move(ev(x=x + 60, y=y - 25))
p = app.proc
assert abs(p.eq3_freq - float(f"{ed.freq_at(x + 60):.3g}")) < 1e-6 and p.eq3_gain > 2.0, (p.eq3_freq, p.eq3_gain)
assert abs(p.eq_curve_db(np.array([p.eq3_freq]))[0] - p.eq3_gain) < 0.8, "the drawn curve follows the sound"
ed._release()
q0 = p.eq3_q; nx, ny = ed.node_xy(3)
ed._wheel(ev(x=nx, y=ny, delta=120)); assert p.eq3_q < q0, "wheel up widens the band"
ed._wheel(ev(x=nx, y=ny, delta=-120)); ed._wheel(ev(x=nx, y=ny, delta=-120)); assert p.eq3_q > q0
ed._double(ev(x=nx, y=ny)); assert p.eq3_gain == 0.0
ed._right(ev(x=nx, y=ed.node_xy(3)[1])); assert p.eq3_on is False
ed._right(ev(x=nx, y=ed.node_xy(3)[1])); assert p.eq3_on is True
x1, y1 = ed.node_xy(1); ed._press(ev(x=x1, y=y1)); assert page.eq_band == 1 and page.band_picker.get() == 1
app.binder.set(sm.BY_KEY["eq2_type"], "notch"); ed._press(ev(x=ed.node_xy(2)[0], y=ed.node_xy(2)[1]))
g_before = p.eq2_gain; ed._move(ev(x=ed.node_xy(2)[0] + 30, y=5)); assert p.eq2_gain == g_before, "a notch has no gain to drag"
print("   PASS")

print("10. presets: switching, saving, importing, hostile files, A/B bypass")
app.apply_fx_preset("Podcast & Streamer"); assert abs(p.eq1_gain - 2.5) < 1e-9 and p.comp_enabled
assert page.chain.stage_state["comp"]["led"] is True and "" == app.preset_marks[0].cget("text")
app.binder.set(sm.BY_KEY["gain"], 4.0); assert app.preset_marks[0].cget("text") == "Changed from preset"
app.ask_name = lambda *a, **k: "Evening stream"; app.save_fx_preset(); assert "Evening stream" in cfg.data["user_fx_presets"]
text = pio.dumps(pio.export_preset("fx", "Shared", {"gain": 2.0, "comp_enabled": True}))
assert app.import_preset_text(text) == ["Shared"] and "Shared" in cfg.data["user_fx_presets"]
assert app.import_preset_text(text) == ["Shared (2)"]
assert app.import_preset_text("{ nope") == [] and "not a valid preset" in app.status_left.cget("text") or "valid preset" in app.status_left.cget("text")
app.toggle_bypass(); assert p.fx_bypass and app.btn_fx.style_name == "warn" and "bypassed" in app.btn_fx.cget("text")
tick(1); blk = np.ones(480, np.float32) * 0.1; assert np.array_equal(p.process(blk), blk)
app.toggle_bypass(); assert not p.fx_bypass and app.btn_fx.style_name == "normal"
assert "<Control-b>" in app.root._bindings and "<Control-f>" in app.root._bindings
print("   PASS")

print("11. header actions and live dashboard")
app.toggle_mute(); tick(2); assert rx.paused and app.btn_mute.cget("text") == "Unmute"; app.toggle_mute(); tick(2)
app.toggle_monitor(); tick(1); app.toggle_monitor()
app.toggle_record(); tick(2); time.sleep(0.4); tick(1); assert app.btn_record.style_name == "rec"; app.toggle_record()
app.show_page("dashboard"); tick(6); dash = app.pages["dashboard"]
assert app.chip_text.cget("text") == "Streaming" and dash.g_rate._text.endswith("kbps"), (app.chip_text.cget("text"), dash.g_rate._text)
assert "Connected from" in dash.hero_sub.cget("text") and "dBFS" in dash.read_label.cget("text")
print("   PASS chip:", app.chip_text.cget("text"), "| bitrate gauge:", dash.g_rate._text, "| delay gauge:", dash.g_latency._text)

print("12. setup wizard")
cfg.data["app"]["first_run_done"] = False
app.show_page("wizard"); wz = app.pages["wizard"]; wz.on_show(); assert wz.step == 0
for expect in (1, 2, 3, 4):
    wz.next(); assert wz.step == expect; tick(2); wz.refresh_fast(); wz.refresh_slow()
wz.choose("speakers"); wz.go(1); wz.choose("mic"); wz.back(); assert wz.step == 0
wz.go(4); wz.next()
assert cfg.data["app"]["first_run_done"] is True and app.current == "dashboard"
print("   PASS")

print("13. accent colour is applied before any widget is created")
saved = widgets.T.ACCENT
widgets.apply_accent("violet"); assert widgets.T.ACCENT == widgets.ACCENTS["violet"][0] and widgets.FlatButton.STYLES["primary"][0] == widgets.T.ACCENT
widgets.apply_accent("teal"); assert widgets.T.ACCENT == saved
print("   PASS")

print("14. settings are saved on exit")
stop.set(); app.on_close()
saved_cfg = json.load(open(os.path.join(d, "c.json")))
assert "Evening stream" in saved_cfg["user_fx_presets"] and "eq3_gain" in saved_cfg["studio_fx"] and saved_cfg["app"]["first_run_done"] is True
assert saved_cfg["version"] == __import__("phonemic").const.VERSION
print("   PASS")
