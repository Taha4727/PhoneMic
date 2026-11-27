"""Regression tests for Windows UI fixes (pure-Python + fake_tk, no numpy/PIL required)."""
import os
import sys
import tempfile
import types

import _path  # noqa: F401
import fake_tk; fake_tk.install()

try:
    import numpy  # noqa: F401
except ModuleNotFoundError:
    class _DummyArr(list):
        dtype = float
        shape = (0,)
        def __truediv__(self, o): return self
        def __rtruediv__(self, o): return self
        def __mul__(self, o): return self
        def __rmul__(self, o): return self
        def __add__(self, o): return self
        def __sub__(self, o): return self
        def astype(self, *a, **k): return self
        def setflags(self, *a, **k): pass

    class _NpStub(types.ModuleType):
        float32 = float
        int16 = int
        def __getattr__(self, name):
            return lambda *a, **k: _DummyArr()
    sys.modules["numpy"] = _NpStub("numpy")

from phonemic import settings_meta as sm, system, ui_kit, widgets


def _knob_cx(toggle):
    ovals = [toggle.items[i] for i in toggle.order if toggle.items[i]["type"] == "oval"]
    x0, _y0, x1, _y1 = ovals[-1]["coords"]
    return (x0 + x1) / 2.0


def test_toggle_canvas_rendering_and_interaction():
    root = widgets.create_root()
    calls = []

    t_on = widgets.Toggle(root, value=True, command=lambda v: calls.append(("on", v)))
    assert t_on.get() is True and t_on.value is True
    on_cx = _knob_cx(t_on)

    t_off = widgets.Toggle(root, value=False, command=lambda v: calls.append(("off", v)))
    assert t_off.get() is False and t_off.value is False
    off_cx = _knob_cx(t_off)

    assert on_cx > off_cx, (on_cx, off_cx)
    assert calls == []

    t_off._click()
    assert t_off.get() is True and _knob_cx(t_off) > off_cx
    assert calls == [("off", True)]

    t_off.set(False, notify=False)
    assert t_off.get() is False and _knob_cx(t_off) == off_cx
    assert calls == [("off", True)]

    t_off.event_generate("<space>")
    assert t_off.get() is True
    assert calls == [("off", True), ("off", True)]

    t_off.set_enabled(False)
    t_off._click()
    t_off.event_generate("<Return>")
    assert t_off.get() is True and len(calls) == 2

    t_off.set_enabled(True)
    t_off.refresh_theme(widgets.T.SURFACE2)
    assert t_off.cget("bg") == widgets.T.SURFACE2


def test_create_root_locks_ctk_scaling_before_instantiation():
    order = []
    orig_deact = widgets.ctk.deactivate_automatic_dpi_awareness
    orig_wscale = widgets.ctk.set_widget_scaling
    orig_winscale = widgets.ctk.set_window_scaling
    orig_ctk = widgets.ctk.CTk

    class TrackingCTk(orig_ctk):
        def __init__(self, *a, **kw):
            order.append("CTk")
            super().__init__(*a, **kw)

    try:
        widgets.ctk.deactivate_automatic_dpi_awareness = lambda: order.append("deactivate_dpi")
        widgets.ctk.set_widget_scaling = lambda s: order.append(("widget_scaling", s))
        widgets.ctk.set_window_scaling = lambda s: order.append(("window_scaling", s))
        widgets.ctk.CTk = TrackingCTk
        widgets.create_root()
    finally:
        widgets.ctk.deactivate_automatic_dpi_awareness = orig_deact
        widgets.ctk.set_widget_scaling = orig_wscale
        widgets.ctk.set_window_scaling = orig_winscale
        widgets.ctk.CTk = orig_ctk

    assert order.index("deactivate_dpi") < order.index("CTk")
    assert order.index(("widget_scaling", 1.0)) < order.index("CTk")
    assert order.index(("window_scaling", 1.0)) < order.index("CTk")


def test_flat_button_segmented_and_combo_set_enabled():
    root = widgets.create_root()
    btn = widgets.FlatButton(root, "Apply", lambda: None)

    orig_cfg = btn.configure
    def strict_cfg(cnf=None, **kw):
        if "cursor" in kw:
            raise ValueError("CTkButton rejects cursor option here")
        return orig_cfg(cnf, **kw)

    btn.configure = strict_cfg
    btn.set_enabled(False)
    assert btn._enabled is False
    btn.set_enabled(True)
    assert btn._enabled is True

    seg_calls = []
    seg = widgets.Segmented(root, [("a", "A"), ("b", "B")], value="a", command=seg_calls.append)
    seg.set_enabled(False)
    seg._pick("b")
    assert seg.get() == "a" and seg_calls == []
    assert seg.buttons["a"]._enabled is False and seg.buttons["b"]._enabled is False
    seg.set_enabled(True)
    seg._pick("b")
    assert seg.get() == "b" and seg_calls == ["b"]

    combo = widgets.Combo(root, ["One", "Two"])
    combo.set_enabled(False)
    assert combo.cget("state") == "disabled"
    combo.set_enabled(True)
    assert combo.cget("state") == "normal"


class _DummyBinder:
    def __init__(self, initial, reject=False):
        self.values = dict(initial)
        self.reject = reject
        self._listeners = {}

    def get(self, s):
        return self.values[s.key]

    def set(self, s, value, source=None):
        if self.reject:
            return False
        self.values[s.key] = value
        return True

    def default(self, s):
        return sm.default_of(s)

    def is_default(self, s):
        return self.values[s.key] == sm.default_of(s)

    def listen(self, key, fn):
        self._listeners.setdefault(key, []).append(fn)

    def depend(self, key, fn):
        pass

    def needs_met(self, s):
        return True


def test_setting_row_and_panel_header_revert_if_binder_rejects():
    root = widgets.create_root()
    setting = sm.BY_KEY["gate_enabled"]
    binder = _DummyBinder({"gate_enabled": True}, reject=True)
    app = types.SimpleNamespace(binder=binder)

    row = ui_kit.SettingRow(root, app, setting)
    assert row.control.get() is True
    row.control._click()
    assert row.control.get() is True, "failed binder.set must revert toggle back to actual binder value"

    header = ui_kit.PanelHeader(root, "Gate", "Cut background room noise", toggle_setting=setting, app=app)
    assert header.switch.get() is True and header.state_label.cget("text") == "On"
    header.switch._click()
    assert header.switch.get() is True and header.state_label.cget("text") == "On"


def test_screen_bounds_and_multi_monitor_popup_clamping():
    root = widgets.create_root()
    root.winfo_screenwidth = lambda: 1920
    root.winfo_screenheight = lambda: 1080
    root.winfo_vrootx = lambda: -1920
    root.winfo_vrooty = lambda: 0
    root.winfo_vrootwidth = lambda: 3840
    root.winfo_vrootheight = lambda: 1080

    assert widgets.screen_bounds(root) == (-1920, 0, 3840, 1080)

    # Tooltip positioned on a left secondary monitor (negative X) should stay on that monitor
    anchor = fake_tk.Frame(root)
    anchor.winfo_rootx = lambda: -1200
    anchor.winfo_rooty = lambda: 200
    anchor.winfo_vrootx = lambda: -1920
    anchor.winfo_vrooty = lambda: 0
    anchor.winfo_vrootwidth = lambda: 3840
    anchor.winfo_vrootheight = lambda: 1080
    tip = widgets.Tooltip(anchor, "Secondary monitor tooltip")

    orig_tl = widgets.tk.Toplevel
    class MultiMonToplevel(orig_tl):
        def winfo_vrootx(self): return -1920
        def winfo_vrooty(self): return 0
        def winfo_vrootwidth(self): return 3840
        def winfo_vrootheight(self): return 1080

    try:
        widgets.tk.Toplevel = MultiMonToplevel
        tip._show()
        assert tip._tip is not None
        assert tip._tip._wm_geo.startswith("+-11"), f"expected negative monitor X, got {tip._tip._wm_geo}"
        tip._hide()
    finally:
        widgets.tk.Toplevel = orig_tl

    # SearchBox popup positioned on a left secondary monitor (negative X) stays on that monitor
    app = types.SimpleNamespace(goto_setting=lambda k: None)
    sb = ui_kit.SearchBox(root, app)
    sb.winfo_rootx = lambda: -1100
    sb.winfo_rooty = lambda: 80
    sb.winfo_height = lambda: 30
    sb.showing_hint = False
    sb.var.set("rumble")
    sb.hits = sm.search("rumble", include_advanced=True)
    sb.cursor = 0
    try:
        ui_kit.tk.Toplevel = MultiMonToplevel
        sb.show()
        assert sb.popup is not None
        assert sb.popup._wm_geo.startswith("+-1100+"), f"expected negative monitor X, got {sb.popup._wm_geo}"
        sb.close()
    finally:
        ui_kit.tk.Toplevel = orig_tl


def test_configure_firewall_uses_oem_encoding_for_non_ascii_exe_path():
    orig_win = system.IS_WIN
    orig_linux = system.IS_LINUX
    orig_frozen = system.FROZEN
    orig_exe = sys.executable
    orig_tmp = tempfile.gettempdir
    orig_is_admin = system.is_admin
    orig_oem = system._oem_encoding
    d = tempfile.mkdtemp()
    try:
        system.IS_WIN = True
        system.IS_LINUX = False
        system.FROZEN = True
        sys.executable = os.path.join("C:\\Users", "J\u00f6rg", "PhoneMic", "PhoneMicReceiver.exe")
        tempfile.gettempdir = lambda: d
        system.is_admin = lambda: False
        system._oem_encoding = lambda: "cp850"
        fake_shell32 = types.SimpleNamespace(ShellExecuteW=lambda *a: 42)
        orig_ctypes = __import__("ctypes")
        had_windll = hasattr(orig_ctypes, "windll")
        old_windll = getattr(orig_ctypes, "windll", None)
        orig_ctypes.windll = types.SimpleNamespace(shell32=fake_shell32)
        try:
            ok, _msg = system.configure_firewall(50000)
        finally:
            if had_windll:
                orig_ctypes.windll = old_windll
            else:
                delattr(orig_ctypes, "windll")
        assert ok is True
        bat_path = os.path.join(d, "phonemic_firewall.bat")
        content = open(bat_path, encoding="cp850").read()
        assert "J\u00f6rg" in content, content
    finally:
        system.IS_WIN = orig_win
        system.IS_LINUX = orig_linux
        system.FROZEN = orig_frozen
        sys.executable = orig_exe
        tempfile.gettempdir = orig_tmp
        system.is_admin = orig_is_admin
        system._oem_encoding = orig_oem


def test_ready_to_use_ctk_components():
    root = widgets.create_root()

    # 1. Segmented wraps CTkSegmentedButton via composition: native button clicks work without set() collision
    calls = []
    seg = widgets.Segmented(root, [("spectrum", "Spectrum"), ("pills", "Pill Bars"), ("scope", "Waveform")],
                            value="spectrum", command=calls.append)
    assert isinstance(seg, fake_tk.CTkFrame) and isinstance(seg._seg, fake_tk.CTkSegmentedButton)
    assert seg.get() == "spectrum"
    seg.set("pills", notify=False)
    assert seg.get() == "pills" and seg._seg.get() == "Pill Bars" and calls == []
    # Simulate real CTkSegmentedButton button click -> self._seg.set("Waveform", from_button_callback=True) -> _ctk_pick
    seg._seg._buttons_dict["Waveform"].cget("command")()
    assert seg.get() == "scope" and seg._seg.get() == "Waveform" and calls == ["scope"]
    seg._seg._buttons_dict["Spectrum"].cget("command")()
    assert seg.get() == "spectrum" and calls == ["scope", "spectrum"]
    seg.set_enabled(False)
    seg._ctk_pick("Pill Bars")
    assert seg.get() == "spectrum" and seg._seg.get() == "Spectrum" and calls == ["scope", "spectrum"]
    seg.set_enabled(True)
    tip = widgets.Tooltip(seg, "Segmented tooltip test")
    for b in seg._seg._buttons_dict.values():
        assert "<Enter>" in b._bindings and "<Leave>" in b._bindings
    tip._show()
    assert tip._tip is not None
    tip._hide()
    for acc in widgets.ACCENTS:
        widgets.apply_accent(acc)
        seg.refresh_theme()
        assert seg._seg.cget("text_color") == widgets.T.TEXT
    widgets.apply_accent("teal")

    # 2. TextInput
    var = fake_tk.StringVar(value="50000")
    ti = widgets.TextInput(root, textvariable=var, width=8, size=11, weight="bold", display=True, justify="center")
    assert isinstance(ti, fake_tk.CTkEntry)
    ti.set_text_color(widgets.T.ACCENT_HI)
    ti.set_border_color(widgets.T.ACCENT)
    ti.select_all()
    ti.set_enabled(False)
    assert ti.cget("state") == "disabled"
    ti.set_enabled(True)
    ti.refresh_theme()

    # 3. ProgressBar
    pb = widgets.ProgressBar(root, height=6, color=widgets.T.ACCENT, bg=widgets.T.SURFACE2, corner=3)
    assert isinstance(pb, fake_tk.CTkProgressBar)
    pb.set_progress(1.5, widgets.T.GOOD)
    assert pb.get() == 1.0 and pb.cget("progress_color") == widgets.T.GOOD
    pb.set_progress(-0.2)
    assert pb.get() == 0.0
    pb.refresh_theme(color=widgets.T.BLUE, bg=widgets.T.SURFACE3)
    assert pb.cget("progress_color") == widgets.T.BLUE

    # 4. SurfaceBox, PillBadge, ScrollTextBox
    box = widgets.SurfaceBox(root, bg=widgets.T.SURFACE2, border=widgets.T.BORDER, corner=8)
    assert isinstance(box, fake_tk.CTkFrame)
    box.refresh_theme(bg=widgets.T.SURFACE, border=widgets.T.BORDER_HI)
    assert box.cget("fg_color") == widgets.T.SURFACE

    badge = widgets.PillBadge(root, "Wi-Fi", fg=widgets.T.GOOD, bg=widgets.T.SIDEBAR, border=widgets.T.BORDER, display=True)
    assert badge._label.cget("text") == "Wi-Fi"
    badge.set_badge("USB Tether", fg=widgets.T.ACCENT_HI)
    assert badge._label.cget("text") == "USB Tether" and badge._label.cget("fg") == widgets.T.ACCENT_HI
    badge.refresh_theme()

    stb = widgets.ScrollTextBox(root, height=9)
    assert isinstance(stb, widgets.SurfaceBox) and isinstance(stb.textbox, fake_tk.Text)

    # 5. SearchBox uses TextInput and manages inline clear button visibility
    app = types.SimpleNamespace(goto_setting=lambda k: None)
    sb = ui_kit.SearchBox(root, app)
    assert isinstance(sb.entry, widgets.TextInput)
    assert sb.clear_lbl.packed is None
    sb._focus_in()
    sb.var.set("eq")
    sb._typed()
    assert sb.clear_lbl.packed is not None
    sb.clear()
    assert sb.showing_hint is True and sb.clear_lbl.packed is None


def test_setting_row_and_panel_header_safe_when_destroyed_by_theme_rebuild():
    root = widgets.create_root()
    setting = sm.BY_KEY["app.soft_colors"]

    class ThemeRebuildingBinder(_DummyBinder):
        def set(self, s, value, source=None):
            self.values[s.key] = value
            for w in list(target_widgets):
                w.destroy()
            return True

    target_widgets = []
    binder = ThemeRebuildingBinder({"app.soft_colors": False})
    app = types.SimpleNamespace(binder=binder)

    row = ui_kit.SettingRow(root, app, setting)
    header = ui_kit.PanelHeader(root, "Look", "Soft colors", toggle_setting=setting, app=app)
    target_widgets.extend([row, header])

    def fail_on_destroyed(*_a, **_kw):
        raise AssertionError("must not touch widget after destroy()")

    row.reset_btn.delete = fail_on_destroyed
    row.control._click()
    assert row.destroyed is True

    # Rebuild a fresh PanelHeader and verify destroying it during binder.set is also safe
    header2 = ui_kit.PanelHeader(root, "Look", "Soft colors", toggle_setting=setting, app=app)
    target_widgets.append(header2)
    header2.state_label.configure = fail_on_destroyed
    header2.switch._click()
    assert header2.destroyed is True

    # Flash callback scheduled before destroy must also be safe
    row2 = ui_kit.SettingRow(root, app, setting)
    row2.flash(ms=50)
    pending = list(row2._after.values())
    row2.destroy()
    row2.configure = fail_on_destroyed
    for _ms, fn, args in pending:
        fn(*args)


def test_flat_button_multiline_height_and_progress_cache():
    root = widgets.create_root()
    single = widgets.FlatButton(root, "Studio", size=9, pady=8)
    multi = widgets.FlatButton(root, "Walkie-Talkie\nComm Radio", size=9, pady=8)
    assert multi.cget("height") > single.cget("height")
    assert multi.cget("height") >= widgets.dp(36)

    pb = widgets.ProgressBar(root, height=6, color=widgets.T.ACCENT)
    cfg_calls = []
    orig_cfg = pb.configure
    def spy_cfg(cnf=None, **kw):
        cfg_calls.append(dict(kw))
        return orig_cfg(cnf, **kw)
    pb.configure = spy_cfg
    pb.set_progress(0.5, widgets.T.ACCENT)
    assert cfg_calls == []
    pb.set_progress(0.6, widgets.T.GOOD)
    assert cfg_calls == [{"progress_color": widgets.T.GOOD}]


def test_searchbox_escape_and_pick_unfocus_and_tooltip_destroy_cleanup():
    root = widgets.create_root()
    picked = []
    app = types.SimpleNamespace(goto_setting=picked.append)
    sb = ui_kit.SearchBox(root, app)
    focused = []
    sb.focus_set = lambda: focused.append(True)

    sb._focus_in()
    sb.var.set("gate")
    sb.entry.event_generate("<Escape>")
    assert sb.showing_hint is True and len(focused) == 1

    sb._focus_in()
    sb.hits = [sm.BY_KEY["gate_enabled"]]
    sb.pick(0)
    assert picked == ["gate_enabled"] and sb.showing_hint is True and len(focused) == 2

    # Tooltip hides on destroy/unmap and refuses to show on destroyed widget
    anchor = fake_tk.Frame(root)
    tip = widgets.Tooltip(anchor, "Safe tip")
    assert "<Destroy>" in anchor._bindings and "<Unmap>" in anchor._bindings
    tip._show()
    assert tip._tip is not None
    anchor.event_generate("<Destroy>")
    assert tip._tip is None
    anchor.destroy()
    tip._show()
    assert tip._tip is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
