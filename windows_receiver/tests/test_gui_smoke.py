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

print("8. chain list: lights follow the effects; voice selects inline in Audio Studio")
for sid, key in (("comp", "comp_enabled"), ("deess", "deess_enabled"), ("agc", "agc_enabled")):
    app.binder.set(sm.BY_KEY[key], True); assert page.chain.stage_state[sid]["led"] is True
    app.binder.set(sm.BY_KEY[key], False); assert page.chain.stage_state[sid]["led"] is False
assert page.chain.stage_state["input"]["led"] == "fixed" and page.chain.stage_state["output"]["led"] == "fixed"
page.chain.on_pick("voice"); assert app.current == "sound" and page.stage_id == "voice"
page.pick_stage("noise")
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
app.toggle_bypass(); assert not p.fx_bypass and app.btn_fx.style_name == "blue"
assert "<Control-b>" in app.root._bindings and "<Control-f>" in app.root._bindings
print("   PASS")

print("11. header actions and live dashboard")
app.toggle_mute(); tick(2); assert rx.paused and app.btn_mute.cget("text") == "Unmute"; app.toggle_mute(); tick(2)
app.toggle_monitor(); tick(1); app.toggle_monitor()
app.toggle_record(); tick(2); time.sleep(0.4); tick(1); assert app.btn_record.style_name == "rec"; app.toggle_record()
app.show_page("dashboard"); tick(6); dash = app.pages["dashboard"]
assert app.chip_text.cget("text") == "Streaming" and dash.g_rate._text.endswith("kbps"), (app.chip_text.cget("text"), dash.g_rate._text)
assert "Connected from" in dash.hero_sub.cget("text") and "dBFS" in dash.read_label.cget("text")
dash._viz_mode("pills"); tick(2); assert dash.spectrum.mode == "pills" and cfg.data["visualizer_mode"] == "pills"
dash._viz_mode("spectrum"); tick(1)
app.toggle_sidebar(); assert app.sidebar_collapsed is True and cfg.data["app"]["sidebar_collapsed"] is True
app.toggle_sidebar(); assert app.sidebar_collapsed is False and cfg.data["app"]["sidebar_collapsed"] is False
# Quick FX pills sync bidirectionally with AudioProcessor / binder
comp_btn, comp_style = dash.fx_pills["comp_enabled"]
was_comp = app.proc.comp_enabled
comp_btn.command(); assert app.proc.comp_enabled is (not was_comp) and comp_btn.style_name == (comp_style if app.proc.comp_enabled else "ghost")
comp_btn.command(); assert app.proc.comp_enabled is was_comp
# Quick Output Device switcher stays synced with ConnectPage
out_vals = list(dash.out_combo.cget("values") or [])
if len(out_vals) > 1:
    other_dev = next(n for n in out_vals if n != dash.out_combo.get())
    dash.out_combo.command(other_dev)
    assert rx.main_dev.name == other_dev and app.pages["connect"].out_combo.get() == other_dev
# Responsive two-tier header & Dashboard 2-col / 1-col + hero + QuickFX reflow
app._layout_header(900); assert app._header_wide is True and app.search.packed[1]["row"] == 0
app._layout_header(600); assert app._header_wide is False and app.search.packed[1]["row"] == 1
dash._layout_hero(700); assert dash._hero_cols == 2 and dash.h_right.packed[1]["row"] == 0
dash._layout_hero(500); assert dash._hero_cols == 1 and dash.h_right.packed[1]["row"] == 1
dash._layout_hero(700)
dash._layout_fx(600); assert dash._fx_wide is True
dash._layout_fx(440); assert dash._fx_wide is False and dash._fx_buttons[-1].packed[1]["row"] == 1
dash._layout_fx(600)
dash._reflow(780); assert dash._layout_cols == 2 and dash.col_right.packed[1]["row"] == 0
dash._reflow(480); assert dash._layout_cols == 1 and dash.col_right.packed[1]["row"] == 1
dash._reflow(780); app._layout_header(720)
# LogPage 4-col vs 2x2 tiles reflow
app.show_page("log"); lp = app.pages["log"]
lp._layout_tiles(700); assert lp._tile_cols == 4 and lp.t_dsp.packed[1]["row"] == 0
lp._layout_tiles(500); assert lp._tile_cols == 2 and lp.t_dsp.packed[1]["row"] == 1
lp._layout_tiles(700)
# LevelMeter scale labels fit cleanly without bottom clipping or clip-LED overlap
dash.meter._opts["width"], dash.meter._opts["height"] = 420, 42
dash.meter._build_key = None
dash.meter._build()
text_items = [it for it in dash.meter.items.values() if it["type"] == "text"]
assert [it["opts"]["text"] for it in text_items] == ["-60", "-48", "-36", "-24", "-12", "-6", "0"]
assert all(it["coords"][1] <= 27 for it in text_items), text_items
assert text_items[-1]["opts"]["anchor"] == "ne"

# ConnectPage responsive stack & empty/populated device safety
app.show_page("connect"); conn = app.pages["connect"]; cols = conn.body.winfo_children()[0]
for cw in (360, 540, 660, 940):
    cols._reflow(cw)
cols._reflow(540); assert cols._cols == 1
cols._reflow(940); assert cols._cols == 2
saved_devs = list(rx.devices)
rx.devices = []
conn.fill_devices(); conn.refresh_addresses(); tick(1)
rx.devices = saved_devs
conn.fill_devices(); tick(1)
assert not app._err_seen, app._err_seen

# LevelMeter and SpectrumView idle fast-path settles cleanly
app.show_page("dashboard")
for _ in range(40):
    dash.meter.update_levels(-80.0, -80.0, -80.0, False)
    dash.spectrum.idle()
assert dash.meter._idle_settled is True and dash.spectrum._idle_settled is True
print("   PASS chip:", app.chip_text.cget("text"), "| bitrate gauge:", dash.g_rate._text, "| delay gauge:", dash.g_latency._text)

print("12. setup wizard, lazy settings tabs, and compact mode toggle")
sp = app.pages["settings"]
assert sp.card_general is not None
sp._pick_tab("shortcuts"); assert sp.card_keys is not None and "shortcuts" in sp.tabs
sp._pick_tab("recording"); assert sp.card_rec is not None and "recording" in sp.tabs
sp._pick_tab("general")
cfg.data["app"]["first_run_done"] = False
app.show_page("wizard"); wz = app.pages["wizard"]; wz.on_show(); assert wz.step == 0
wz._fit_card(640); assert wz.body._colcfg[0]["minsize"] == 0
for expect in (1, 2, 3, 4):
    wz.next(); assert wz.step == expect; tick(2); wz.refresh_fast(); wz.refresh_slow()
wz.choose("speakers"); wz.go(1); wz.choose("mic"); wz.back(); assert wz.step == 0
wz.go(4); wz.next()
assert cfg.data["app"]["first_run_done"] is True and app.current == "dashboard"
app.toggle_ui_mode(); assert app.ui_mode == "minimal" and app.minimal_view is not None
tick(2); app.minimal_view._step_gain(1.5); assert abs(p.out_gain_db - 1.5) < 1e-6
app.minimal_view._set_gain(0.0)
app.toggle_ui_mode(); assert app.ui_mode == "default"
print("   PASS")

print("13. live theme rebuild, monochrome/soft modes, and binder scope cleanup")
saved = widgets.T.ACCENT
widgets.apply_accent("blue"); assert widgets.T.ACCENT == widgets.ACCENTS["blue"][0] and widgets.FlatButton.STYLES["primary"][0] == widgets.T.ACCENT
widgets.apply_accent("mono"); assert widgets.T.IS_MONO and widgets.T.ACCENT == widgets.ACCENTS["mono"][0]
widgets.apply_accent("teal", soft=True); assert widgets.T.SOFT_COLORS and widgets.T.ACCENT == widgets.SOFT_ACCENTS["teal"][0]
widgets.apply_accent("teal", soft=False); assert not widgets.T.SOFT_COLORS and not widgets.T.IS_MONO and widgets.T.ACCENT == saved

# Full live rebuild via binder on Settings(recording tab) & Sound(eq stage) without leaking binder callbacks
app.show_page("settings"); app.pages["settings"]._pick_tab("recording")
base_any = len(app.binder.any_listeners)
app.binder.set(sm.BY_KEY["app.accent"], "blue")
assert app.current == "settings" and app.pages["settings"].active_tab == "recording"
assert widgets.T.ACCENT == widgets.ACCENTS["blue"][0] and "Restart" not in app.status_left.cget("text")
app.binder.set(sm.BY_KEY["app.accent"], "mono")
assert widgets.T.IS_MONO and app.pages["settings"].active_tab == "recording"
app.show_page("sound"); app.pages["sound"].pick_stage("eq"); app.pages["sound"].eq_pick(2)
app.binder.set(sm.BY_KEY["app.soft_colors"], True)
assert app.current == "sound" and app.pages["sound"].stage_id == "eq" and app.pages["sound"].eq_band == 2
app.binder.set(sm.BY_KEY["app.soft_colors"], False)
app.binder.set(sm.BY_KEY["app.accent"], "teal")
assert len(app.binder.any_listeners) == base_any, (len(app.binder.any_listeners), base_any)
assert not widgets.T.IS_MONO and not widgets.T.SOFT_COLORS and widgets.T.ACCENT == saved
app.show_page("dashboard"); tick(2)
print("   PASS")

print("14. settings are saved on exit & pythonw-safe crash logger works without stderr")
import sys
import phonemic_receiver
old_stderr, old_hook = sys.stderr, sys.excepthook
old_crash_fn = system.crash_log_path
crash_dir = tempfile.mkdtemp()
crash_file = os.path.join(crash_dir, "phonemic_crash.log")
try:
    system.crash_log_path = lambda: crash_file
    sys.stderr = None
    writer = phonemic_receiver.install_crash_handlers(lambda: None)
    try:
        raise RuntimeError("synthetic connect failure")
    except RuntimeError:
        writer(*sys.exc_info(), "smoke test")
    if getattr(writer, "_fault_file", None) is not None:
        writer._fault_file.close()
    assert os.path.exists(crash_file) and "synthetic connect failure" in open(crash_file, encoding="utf-8").read()
finally:
    sys.stderr = old_stderr
    sys.excepthook = old_hook
    system.crash_log_path = old_crash_fn

stop.set(); app.on_close()
saved_cfg = json.load(open(os.path.join(d, "c.json")))
assert "Evening stream" in saved_cfg["user_fx_presets"] and "eq3_gain" in saved_cfg["studio_fx"] and saved_cfg["app"]["first_run_done"] is True
assert saved_cfg["version"] == __import__("phonemic").const.VERSION
print("   PASS")
