"""Application-level widgets built on widgets.py: registry-driven setting rows, signal-chain list, gauges, EQ editor, search."""
import math
import tkinter as tk

from . import settings_meta as sm
from .widgets import (T, HAS_CTK, ctk, dp, font, lerp_color, autowrap, bg_of, screen_bounds,
                      Toggle, Slider, Segmented, Combo, Card, FlatButton, TextInput)
from . import hotkeys as hk


# ==============================================================================
# SMALL ICON BUTTONS
# ==============================================================================
class IconButton(tk.Canvas):
    """16 px drawn icon: 'info' (circled i) or 'reset' (circular arrow)."""

    def __init__(self, master, kind, command=None, size=16, bg=None):
        self.px = dp(size)
        super().__init__(master, width=self.px, height=self.px, bg=bg or bg_of(master), highlightthickness=0, bd=0,
                         cursor="hand2")
        self.kind, self.command = kind, command
        self.lit = False
        self.faint = False
        self.hovering = False
        self._draw_key = None
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<Button-1>", self._click)
        self._draw()

    def _hover(self, flag):
        if flag == self.hovering:
            return
        self.hovering = flag
        self._draw()

    def _click(self, _e=None):
        if self.command:
            self.command()

    def set_lit(self, flag):
        if flag != self.lit:
            self.lit = flag
            self._draw()

    def set_faint(self, flag):
        if flag != self.faint:
            self.faint = flag
            self._draw()

    def _color(self):
        if self.hovering:
            return T.TEXT
        if self.lit:
            return T.ACCENT_HI
        return T.DIM if self.faint else T.MUTED

    def _draw(self):
        col = self._color()
        key = (self.kind, col, self.px)
        if key == self._draw_key:
            return
        self._draw_key = key
        self.delete("all")
        c = self.px / 2.0
        if self.kind == "info":
            r = c - dp(2)
            self.create_oval(c - r, c - r, c + r, c + r, outline=col, width=1)
            self.create_text(c, c + 0.5, text="i", fill=col, font=font(8, "bold"))
        else:
            r = self.px * 0.30
            self.create_arc(c - r, c - r, c + r, c + r, start=100, extent=290, style="arc", outline=col, width=max(1, dp(1.5)))
            ang = math.radians(100 + 290)
            px, py = c + r * math.cos(ang), c - r * math.sin(ang)
            dx, dy = -math.sin(ang), -math.cos(ang)
            a, b = self.px * 0.26, self.px * 0.17
            self.create_polygon(px + dx * a, py + dy * a, px - dy * b, py + dx * b, px + dy * b, py - dx * b, fill=col, outline=col)


# ==============================================================================
# THE REGISTRY-DRIVEN ROW
# ==============================================================================
class SettingRow(tk.Frame):
    """One setting row driven from settings_meta, keeping all UI mirrors synchronized."""

    def __init__(self, master, app, setting, bg=None, compact=False, control_factory=None, title=None):
        bg = bg or T.SURFACE
        super().__init__(master, bg=bg, highlightthickness=0, highlightbackground=T.ACCENT, bd=0)
        self.app, self.setting, self.binder = app, setting, app.binder
        self.advanced = setting.advanced
        self.compact = compact
        self.bg = bg
        self.expanded = False
        self.control = None
        self.enabled = True
        self.value_label = None
        self.details_label = None
        self._flash = None
        s = setting

        head = tk.Frame(self, bg=bg)
        head.pack(fill="x")
        self.title_label = tk.Label(head, text=title or s.title, bg=bg, fg=T.TEXT, font=font(10), anchor="w")
        self.title_label.pack(side="left")
        self.info_btn = IconButton(head, "info", self.toggle_details, bg=bg)
        self.info_btn.pack(side="left", padx=(dp(6), 0))
        right = tk.Frame(head, bg=bg)
        right.pack(side="right")
        self.reset_btn = IconButton(right, "reset", self.reset, bg=bg)
        self.reset_btn.pack(side="right", padx=(dp(8), 0))

        value = self.binder.get(s) if s.kind != "custom" else None
        accent_override = T.BLUE if s.key.startswith(("vc.", "eq")) else None
        if s.kind == "toggle":
            self.control = Toggle(right, bool(value), command=self._changed, bg=bg)
            self.control.pack(side="right")
        elif s.kind == "slider":
            self.value_label = tk.Label(right, text="", bg=bg, fg=T.BLUE_HI if accent_override else T.ACCENT_HI,
                                        font=font(10, "bold", True))
            self.value_label.pack(side="right")
            self.control = Slider(self, s.lo, s.hi, value, s.step, default=self.binder.default(s), origin=s.origin,
                                  command=self._changed, bg=bg, accent=accent_override, log=s.log)
            self.control.pack(fill="x", pady=(dp(2), 0))
        elif s.kind == "choice":
            labels = [c[1] for c in s.choices]
            if len(s.choices) <= 3 and sum(len(x) for x in labels) <= 38:
                self.control = Segmented(self, [(k, v) for k, v in s.choices], value, command=self._changed, bg=bg)
                self.control.pack(anchor="w", pady=(dp(4), 0))
            else:
                self.control = _ChoiceCombo(self, s.choices, value, self._changed)
                self.control.pack(anchor="w", pady=(dp(4), 0))
        elif s.kind == "custom" and control_factory is not None:
            self.control = control_factory(self)
            if self.control is not None:
                self.control.pack(fill="x", pady=(dp(4), 0))
            self.reset_btn.pack_forget()

        if not compact:
            autowrap(tk.Label(self, text=s.summary, bg=bg, fg=T.DIM, font=font(9), anchor="w", justify="left",
                              wraplength=dp(240))).pack(fill="x", pady=(dp(3), 0))

        if s.kind != "custom":
            self.binder.listen(s.key, self._external)
            self._show_value(value)
        if s.needs:
            self.binder.depend(s.needs, self.set_enabled)
            self.set_enabled(self.binder.needs_met(s))

    def _show_value(self, value):
        if not self.winfo_exists():
            return
        s = self.setting
        if self.value_label is not None:
            txt = sm.format_value(s.fmt, value)
            if self.value_label.cget("text") != txt:
                self.value_label.configure(text=txt)
        is_def = self.binder.is_default(s)
        self.reset_btn.set_lit(not is_def)
        self.reset_btn.set_faint(is_def)

    def _changed(self, value):
        self.binder.set(self.setting, value, source=self._external)
        if not self.winfo_exists():
            return
        actual = self.binder.get(self.setting)
        if self.control is not None and hasattr(self.control, "set") and self.control.get() != actual:
            self.control.set(actual)
        self._show_value(actual)

    def _external(self, value):
        if not self.winfo_exists():
            return
        if self.control is not None and hasattr(self.control, "set"):
            if self.control.get() != value:
                self.control.set(value)
        self._show_value(value)

    def reset(self):
        if self.setting.kind != "custom":
            self.binder.reset(self.setting)

    def refresh(self):
        if self.setting.kind != "custom":
            self._external(self.binder.get(self.setting))
            if self.setting.needs:
                self.set_enabled(self.binder.needs_met(self.setting))

    def set_enabled(self, flag):
        flag = bool(flag)
        if flag == self.enabled:
            return
        self.enabled = flag
        self.title_label.configure(fg=T.TEXT if flag else T.DIM)
        if self.value_label is not None:
            hi = T.BLUE_HI if self.setting.key.startswith(("vc.", "eq")) else T.ACCENT_HI
            self.value_label.configure(fg=hi if flag else T.DIM)
        if self.control is not None and hasattr(self.control, "set_enabled"):
            self.control.set_enabled(flag)

    def toggle_details(self):
        self.set_details(not self.expanded)

    def set_details(self, flag):
        flag = bool(flag)
        if flag == self.expanded:
            return
        self.expanded = flag
        self.info_btn.set_lit(flag)
        if flag:
            if self.details_label is None:
                self.details_label = autowrap(tk.Label(
                    self, text=self.setting.details, bg=T.SIDEBAR, fg=T.MUTED,
                    font=font(9), anchor="w", justify="left", wraplength=dp(240),
                    padx=dp(10), pady=dp(8), highlightthickness=1, highlightbackground=T.BORDER))
            self.details_label.pack(fill="x", pady=(dp(6), dp(2)))
        elif self.details_label is not None:
            self.details_label.pack_forget()

    def flash(self, ms=1600):
        self.configure(highlightthickness=1)
        if self._flash:
            try:
                self.after_cancel(self._flash)
            except Exception:
                pass
        self._flash = self.after(ms, lambda: self.winfo_exists() and self.configure(highlightthickness=0))


class _ChoiceCombo(Combo):
    """Combo box whose items are (value, label) pairs; get/set use the value."""

    def __init__(self, master, choices, value, command):
        self.pairs = list(choices)
        self.user_command = command
        super().__init__(master, [lab for _, lab in self.pairs], width=24, command=self._picked)
        self.set(value)

    def _picked(self, label):
        for val, lab in self.pairs:
            if lab == label:
                self.user_command(val)
                return

    def get(self):
        shown = super().get()
        for val, lab in self.pairs:
            if lab == shown:
                return val
        return None

    def set(self, value):
        for val, lab in self.pairs:
            if val == value:
                super().set(lab)
                return
        super().set("")


# ==============================================================================
# PANELS
# ==============================================================================
class SettingsCard(Card):
    """A titled Obsidian card of SettingRows."""

    def __init__(self, master, app, title, blurb, settings, custom=None, compact=False):
        super().__init__(master, title, pad=18)
        self.app = app
        if blurb:
            autowrap(tk.Label(self.body, text=blurb, bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left",
                              wraplength=dp(240))).pack(fill="x", pady=(0, dp(10)))
        custom = custom or {}
        self.footer = tk.Frame(self.body, bg=T.SURFACE)
        self.footer.pack(fill="x", side="bottom")
        self.rows = [SettingRow(self.body, app, s, compact=compact, control_factory=custom.get(s.key)) for s in settings]
        self.apply_view(app.advanced)

    def apply_view(self, advanced):
        for r in self.rows:
            r.pack_forget()
        shown = [r for r in self.rows if advanced or not r.advanced]
        for r in shown:
            r.pack(fill="x", pady=(0, dp(12)), before=self.footer)
        return len(shown)

    def row_for(self, key):
        return next((r for r in self.rows if r.setting.key == key), None)


class PanelHeader(tk.Frame):
    """Strip at the top of a stage panel: title, one-line purpose, optional on/off switch and live readout."""

    def __init__(self, master, title, blurb, toggle_setting=None, app=None, accent=None):
        super().__init__(master, bg=T.SURFACE2)
        self.hi_color = accent or T.ACCENT_HI
        left = tk.Frame(self, bg=T.SURFACE2)
        left.pack(side="left", fill="x", expand=True, padx=dp(16), pady=dp(12))
        tk.Label(left, text=title, bg=T.SURFACE2, fg=T.TEXT, font=font(15, "bold", True), anchor="w").pack(fill="x")
        autowrap(tk.Label(left, text=blurb, bg=T.SURFACE2, fg=T.MUTED, font=font(9), anchor="w", justify="left",
                          wraplength=dp(240))).pack(fill="x", pady=(dp(2), 0))
        right = tk.Frame(self, bg=T.SURFACE2)
        right.pack(side="right", padx=dp(16))
        self.readout = tk.Label(right, text="", bg=T.SURFACE2, fg=self.hi_color, font=font(10, "bold", True))
        self.readout.pack(side="top", anchor="e")
        self.switch = None
        if toggle_setting is not None and app is not None:
            b = app.binder
            row = tk.Frame(right, bg=T.SURFACE2)
            row.pack(side="top", anchor="e", pady=(dp(4), 0))
            self.state_label = tk.Label(row, text="", bg=T.SURFACE2, fg=T.MUTED, font=font(9, "bold"))
            self.state_label.pack(side="left", padx=(0, dp(8)))
            self.switch = Toggle(row, bool(b.get(toggle_setting)), command=self._user, bg=T.SURFACE2)
            self.switch.pack(side="left")
            b.listen(toggle_setting.key, self._ext)
            self.toggle_setting = toggle_setting
            self.binder = b
            self._label(bool(b.get(toggle_setting)))

    def _user(self, value):
        self.binder.set(self.toggle_setting, value, source=self._ext)
        if not self.winfo_exists():
            return
        actual = bool(self.binder.get(self.toggle_setting))
        if self.switch is not None and self.switch.get() != actual:
            self.switch.set(actual)
        self._label(actual)

    def _label(self, on):
        if not self.winfo_exists():
            return
        self.state_label.configure(text="On" if on else "Off", fg=self.hi_color if on else T.DIM)

    def _ext(self, value):
        if not self.winfo_exists():
            return
        if self.switch is not None and self.switch.get() != bool(value):
            self.switch.set(bool(value))
        if self.switch is not None:
            self._label(bool(value))

    def set_readout(self, text, color=None):
        self.readout.configure(text=text, fg=color or self.hi_color)


# ==============================================================================
# SIGNAL CHAIN LIST
# ==============================================================================
class StageList(tk.Frame):
    """Signal chain top-to-bottom with multi-color LED indicators per domain."""
    ITEM_H = 38

    @staticmethod
    def _stage_color(sid):
        if sid in ("voice", "eq", "deess"):
            return T.BLUE
        if sid in ("agc", "comp"):
            return T.GOOD
        return T.ACCENT

    def __init__(self, master, stages, on_pick, bg=None):
        super().__init__(master, bg=bg or T.BG)
        self.stages, self.on_pick = list(stages), on_pick
        self.stage_bg = bg or T.BG
        self.selected_id = None
        self.items, self.stage_state = {}, {}
        for i, st in enumerate(self.stages):
            c = tk.Canvas(self, width=dp(190), height=dp(self.ITEM_H), bg=self.stage_bg, highlightthickness=0, bd=0, cursor="hand2")
            c.pack(fill="x")
            self.items[st.id] = c
            self.stage_state[st.id] = {"led": "fixed" if not (st.enable or st.led) else False, "hover": False}
            c.bind("<Configure>", lambda e, sid=st.id: self._draw(sid))
            c.bind("<Button-1>", lambda e, sid=st.id: self.on_pick(sid))
            c.bind("<Enter>", lambda e, sid=st.id: self._hover(sid, True))
            c.bind("<Leave>", lambda e, sid=st.id: self._hover(sid, False))

    def _hover(self, sid, flag):
        if self.stage_state[sid]["hover"] == flag:
            return
        self.stage_state[sid]["hover"] = flag
        self._draw(sid)

    def choose(self, sid):
        old, self.selected_id = self.selected_id, sid
        for k in (old, sid):
            if k in self.items:
                self._draw(k)

    def set_led(self, sid, led):
        if self.stage_state[sid]["led"] != led:
            self.stage_state[sid]["led"] = led
            self._draw(sid)

    def _draw(self, sid):
        c = self.items[sid]
        st = next(s for s in self.stages if s.id == sid)
        idx = self.stages.index(st)
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20:
            w = dp(190)
        h = h if h > 4 else dp(self.ITEM_H)
        sel, hov = sid == self.selected_id, self.stage_state[sid]["hover"]
        led = self.stage_state[sid]["led"]
        dot_color = self._stage_color(sid)
        dkey = (w, h, sel, hov, led, self.stage_bg, dot_color, T.SURFACE, T.BORDER, T.DIM, T.TEXT, T.MUTED)
        if getattr(c, "_stage_draw_key", None) == dkey:
            return
        c._stage_draw_key = dkey
        c.delete("all")
        if sel or hov:
            fill_bg = T.SURFACE if sel else lerp_color(self.stage_bg, T.SURFACE, 0.7)
            c.create_rectangle(dp(2), dp(2), w - dp(2), h - dp(2), fill=fill_bg,
                               outline=T.BORDER if sel else "")
        if sel:
            c.create_rectangle(dp(2), dp(5), dp(5), h - dp(5), fill=dot_color, outline="")
        cx, cy = dp(22), h / 2
        if idx > 0:
            c.create_line(cx, 0, cx, cy - dp(7), fill=T.BORDER, width=max(1, dp(1.5)))
        if idx < len(self.stages) - 1:
            c.create_line(cx, cy + dp(7), cx, h, fill=T.BORDER, width=max(1, dp(1.5)))
        if led is True:
            r = dp(7)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=lerp_color(self.stage_bg, dot_color, 0.3), outline="")
            r = dp(4.5)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=dot_color, outline="")
        elif led == "fixed":
            r = dp(4)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=T.MUTED, outline="")
        else:
            r = dp(5)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self.stage_bg, outline=T.DIM, width=max(1, dp(1.5)))
        c.create_text(dp(42), cy, text=st.title, anchor="w", fill=T.TEXT if (sel or led) else T.MUTED,
                      font=font(10, "bold" if sel else "normal"))


# ==============================================================================
# GAUGES
# ==============================================================================
class GaugeRow(tk.Canvas):
    """Label on the left, coloured bar in the middle, telemetry readout on the right."""

    def __init__(self, master, label, height=30, bg=None, label_w=120, value_w=92):
        self.bg_color = bg or T.SURFACE
        self.label_w, self.value_w = dp(label_w), dp(value_w)
        super().__init__(master, width=dp(300), height=dp(height), bg=self.bg_color, highlightthickness=0, bd=0)
        self.label_text = label
        self._last = None
        self._build_key = None
        self._frac, self._color, self._text = 0.0, T.GOOD, "-"
        self.bind("<Configure>", lambda e: self._build())

    def _build(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20:
            return
        bkey = (w, h, self.bg_color, T.SURFACE3, T.MUTED, T.TEXT)
        if bkey == self._build_key:
            return
        self._build_key = bkey
        self.delete("all")
        self.create_text(0, h / 2, text=self.label_text, anchor="w", fill=T.MUTED, font=font(10))
        self.x0, self.x1 = self.label_w, max(self.label_w + 20, w - self.value_w)
        bh = dp(7)
        self.create_rectangle(self.x0, h / 2 - bh / 2, self.x1, h / 2 + bh / 2, fill=T.SURFACE3, outline="")
        self.bar_item = self.create_rectangle(self.x0, h / 2 - bh / 2, self.x0, h / 2 + bh / 2, fill=self._color, outline="")
        self.text_item = self.create_text(w, h / 2, text=self._text, anchor="e", fill=T.TEXT, font=font(11, "bold", True))
        self._last = None
        self._paint()

    def set(self, text, frac, color=None):
        self._text, self._frac, self._color = text, min(1.0, max(0.0, frac)), color or T.GOOD
        self._paint()

    def _paint(self):
        key = (self._text, round(self._frac, 3), self._color)
        if key == self._last or not hasattr(self, "bar_item"):
            return
        self._last = key
        h, bh = self.winfo_height(), dp(7)
        self.coords(self.bar_item, self.x0, h / 2 - bh / 2, self.x0 + (self.x1 - self.x0) * self._frac, h / 2 + bh / 2)
        self.itemconfigure(self.bar_item, fill=self._color)
        self.itemconfigure(self.text_item, text=self._text)


# ==============================================================================
# EQUALIZER EDITOR
# ==============================================================================
EQ_FMIN, EQ_FMAX, EQ_RANGE = 20.0, 20000.0, 18.0
EQ_TYPE_NAMES = {"peak": "Bell", "lowshelf": "Low shelf", "highshelf": "High shelf", "notch": "Notch"}


def freq_to_frac(f):
    return (math.log10(max(f, EQ_FMIN)) - math.log10(EQ_FMIN)) / (math.log10(EQ_FMAX) - math.log10(EQ_FMIN))


def frac_to_freq(frac):
    frac = min(1.0, max(0.0, frac))
    return 10.0 ** (math.log10(EQ_FMIN) + frac * (math.log10(EQ_FMAX) - math.log10(EQ_FMIN)))


def gain_to_frac(g):
    return (min(EQ_RANGE, max(-EQ_RANGE, g)) + EQ_RANGE) / (2.0 * EQ_RANGE)


def frac_to_gain(frac):
    return min(1.0, max(0.0, frac)) * 2.0 * EQ_RANGE - EQ_RANGE


class EQEditor(tk.Canvas):
    """Frequency-response graph with draggable numbered band points."""

    def __init__(self, master, on_pick=None, on_edit=None, height=210):
        self.canvas_h = dp(height)
        super().__init__(master, width=dp(200), height=self.canvas_h, bg=T.SIDEBAR, highlightthickness=1,
                         highlightbackground=T.BORDER, bd=0, cursor="crosshair")
        self.bands, self.curve_f, self.curve_db = [], None, None
        self.picked, self.eq_on = 1, True
        self.on_pick, self.on_edit = on_pick, on_edit
        self._grab = None
        self._draw_key = None
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Double-Button-1>", self._double)
        self.bind("<Button-3>", self._right)
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda e: self._wheel_step(e, 1))
        self.bind("<Button-5>", lambda e: self._wheel_step(e, -1))

    def _box(self):
        w = self.winfo_width() if self.winfo_width() > 40 else dp(200)
        h = self.winfo_height() if self.winfo_height() > 40 else self.canvas_h
        return dp(38), dp(12), w - dp(12), h - dp(22)

    def x_of(self, f):
        l, t, r, b = self._box()
        return l + freq_to_frac(f) * (r - l)

    def y_of(self, g):
        l, t, r, b = self._box()
        return b - gain_to_frac(g) * (b - t)

    def freq_at(self, x):
        l, t, r, b = self._box()
        return frac_to_freq((x - l) / max(1.0, r - l))

    def gain_at(self, y):
        l, t, r, b = self._box()
        return frac_to_gain((b - y) / max(1.0, b - t))

    def node_xy(self, n):
        band = self.bands[n - 1]
        return self.x_of(band["freq"]), self.y_of(0.0 if band["type"] == "notch" else band["gain"])

    def band_at(self, x, y):
        best, reach = None, dp(13)
        for n in range(1, len(self.bands) + 1):
            nx, ny = self.node_xy(n)
            d = math.hypot(nx - x, ny - y)
            if d <= reach:
                best, reach = n, d
        return best

    def set_state(self, bands, curve_f, curve_db, picked, eq_on):
        self.bands, self.curve_f, self.curve_db = list(bands), curve_f, curve_db
        self.picked, self.eq_on = picked, bool(eq_on)
        self.redraw()

    def _press(self, e):
        n = self.band_at(e.x, e.y)
        if n is None:
            return
        self.picked, self._grab = n, n
        if self.on_pick:
            self.on_pick(n)
        self.redraw()

    def _move(self, e):
        n = self._grab
        if n is None or not self.on_edit:
            return
        band = self.bands[n - 1]
        freq = float(f"{self.freq_at(e.x):.3g}")
        if band["type"] == "notch":
            self.on_edit(n, freq=freq)
        else:
            self.on_edit(n, freq=freq, gain=round(self.gain_at(e.y) * 10) / 10.0)

    def _release(self, _e=None):
        self._grab = None

    def _double(self, e):
        n = self.band_at(e.x, e.y)
        if n is not None and self.on_edit:
            self.on_edit(n, gain=0.0)

    def _right(self, e):
        n = self.band_at(e.x, e.y)
        if n is not None and self.on_edit:
            self.on_edit(n, on=not self.bands[n - 1]["on"])

    def _wheel(self, e):
        return self._wheel_step(e, 1 if e.delta > 0 else -1)

    def _wheel_step(self, e, direction):
        n = self.band_at(e.x, e.y) or self.picked
        if n and self.on_edit and 1 <= n <= len(self.bands):
            q = self.bands[n - 1]["q"] / (1.12 ** direction)
            self.on_edit(n, q=float(f"{min(8.0, max(0.2, q)):.3g}"))
        return "break"

    def redraw(self):
        l, t, r, b = self._box()
        if r - l < 60:
            return
        band_sig = tuple((round(bd["freq"], 2), round(bd["gain"], 2), round(bd["q"], 3), bd["type"], bool(bd["on"]))
                         for bd in self.bands)
        dkey = (l, t, r, b, self.picked, self.eq_on, band_sig, T.SIDEBAR, T.BORDER, T.SURFACE2, T.SURFACE3,
                T.BLUE, T.ACCENT_HI, T.ACCENT_FG, T.DIM, T.MUTED)
        if dkey == self._draw_key:
            return
        self._draw_key = dkey
        self.delete("all")
        for g in (-12, -6, 0, 6, 12):
            y = self.y_of(g)
            self.create_line(l, y, r, y, fill=T.BORDER if g == 0 else T.SURFACE2)
            self.create_text(l - dp(6), y, text=f"{g:+d}" if g else "0", anchor="e", fill=T.DIM, font=font(8, "normal", True))
        for f, lab in ((50, "50"), (100, "100"), (500, "500"), (1000, "1k"), (5000, "5k"), (10000, "10k")):
            x = self.x_of(f)
            self.create_line(x, t, x, b, fill=T.SURFACE2)
            self.create_text(x, b + dp(4), text=lab, anchor="n", fill=T.DIM, font=font(8, "normal", True))
        if self.curve_f is not None and len(self.curve_f) > 1:
            pts = []
            for f, d in zip(self.curve_f, self.curve_db):
                pts.extend((self.x_of(f), self.y_of(float(d))))
            self.create_line(*pts, fill=T.BLUE if self.eq_on else T.DIM, width=max(2, dp(2)), smooth=True)
        active_fg = T.ACCENT_FG if T.IS_MONO else "#051428"
        for n, band in enumerate(self.bands, start=1):
            x, y = self.node_xy(n)
            active = self.eq_on and band["on"]
            sel = n == self.picked
            rad = dp(10) if sel else dp(8)
            if sel:
                self.create_oval(x - rad - dp(3), y - rad - dp(3), x + rad + dp(3), y + rad + dp(3),
                                 outline=T.ACCENT_HI, width=max(1, dp(1.5)))
            fill_col = T.BLUE if active else T.SURFACE3
            self.create_oval(x - rad, y - rad, x + rad, y + rad, fill=fill_col, outline=T.SIDEBAR)
            self.create_text(x, y, text=str(n), fill=active_fg if active else T.DIM, font=font(9, "bold", True))
        if 1 <= self.picked <= len(self.bands):
            band = self.bands[self.picked - 1]
            gain = "" if band["type"] == "notch" else f"   {band['gain']:+.1f} dB"
            self.create_text(r, t + dp(2), anchor="ne", fill=T.MUTED, font=font(9),
                             text=f"Band {self.picked}: {EQ_TYPE_NAMES.get(band['type'], band['type'])}   {sm.format_value('hz', band['freq'])}{gain}   Q {band['q']:.2g}")


# ==============================================================================
# GLOBAL SEARCH
# ==============================================================================
PAGE_NAMES = {
    "sound": "Audio Studio",
    "voice": "Audio Studio",
    "devices": "Connections",
    "network": "Connections",
    "settings": "Settings",
}


def location_of(s):
    """Human-readable location for search results."""
    if s.page in ("sound", "voice"):
        st = sm.STAGE_BY_ID.get(s.group)
        return f"Audio Studio, {st.title}" if st else "Audio Studio, Voice Changer"
    cards = {c[0]: c[1] for c in sm.CARDS.get(s.page, ())}
    name = PAGE_NAMES.get(s.page, s.page)
    return f"{name}, {cards[s.group]}" if s.group in cards else name


_SearchBase = ctk.CTkFrame if HAS_CTK else tk.Frame


class SearchBox(_SearchBase):
    """Rounded Obsidian search pill jumping straight to any setting or DSP stage."""
    PLACEHOLDER = "Search settings (Ctrl+F)"

    def __init__(self, master, app, bg=None, width=28):
        if HAS_CTK:
            super().__init__(master, fg_color=T.SURFACE2, corner_radius=dp(8), border_width=1, border_color=T.BORDER)
        else:
            super().__init__(master, bg=T.SURFACE2, highlightthickness=1, highlightbackground=T.BORDER)
        self.app = app
        self.var = tk.StringVar(value=self.PLACEHOLDER)
        self.showing_hint = True
        self.popup = None
        self.hits = []
        self.cursor = -1
        self._close_job = None

        self.row_wrap = tk.Frame(self, bg=T.SURFACE2)
        self.row_wrap.pack(fill="x", padx=dp(8), pady=dp(2))
        self.icon_c = tk.Canvas(self.row_wrap, width=dp(14), height=dp(14), bg=T.SURFACE2, highlightthickness=0, bd=0)
        self.icon_c.pack(side="left", padx=(0, dp(4)))
        self._draw_lens()

        self.entry = TextInput(self.row_wrap, textvariable=self.var, width=width, size=10,
                               show_border=False, bg=T.SURFACE2)
        self.entry.set_text_color(T.DIM)
        self.entry.pack(side="left", fill="x", expand=True)

        self.clear_lbl = tk.Label(self.row_wrap, text="\u00d7", bg=T.SURFACE2, fg=T.DIM,
                                  font=font(11, "bold"), cursor="hand2", padx=dp(3))
        self.clear_lbl.bind("<Button-1>", lambda _e: (self.clear(), self.focus_set()))

        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.entry.bind("<KeyRelease>", self._typed)
        self.entry.bind("<Return>", lambda e: self.pick(self.cursor if self.cursor >= 0 else 0))
        self.entry.bind("<Escape>", lambda e: (self.clear(), self.focus_set()))
        self.entry.bind("<Down>", lambda e: self._step(1))
        self.entry.bind("<Up>", lambda e: self._step(-1))
        self.bind("<Unmap>", lambda e: self.close())
        self._last_painted_cursor = None

    def _draw_lens(self):
        self.icon_c.delete("all")
        self.icon_c.create_oval(dp(2), dp(2), dp(9), dp(9), outline=T.DIM, width=1.5)
        self.icon_c.create_line(dp(8), dp(8), dp(12), dp(12), fill=T.DIM, width=1.5)

    def _sync_clear_btn(self):
        if not self.showing_hint and self.var.get():
            if self.clear_lbl.packed is None if hasattr(self.clear_lbl, "packed") else not self.clear_lbl.winfo_ismapped():
                self.clear_lbl.pack(side="right", padx=(dp(2), 0), before=self.entry)
        else:
            self.clear_lbl.pack_forget()

    def refresh_theme(self):
        if HAS_CTK:
            self.configure(fg_color=T.SURFACE2, border_color=T.BORDER)
        else:
            self.configure(bg=T.SURFACE2, highlightbackground=T.BORDER)
        self.row_wrap.configure(bg=T.SURFACE2)
        self.icon_c.configure(bg=T.SURFACE2)
        self._draw_lens()
        self.clear_lbl.configure(bg=T.SURFACE2, fg=T.MUTED)
        self.entry.set_text_color(T.DIM if self.showing_hint else T.TEXT)
        self.entry.refresh_theme(T.SURFACE2)
        if self.popup is not None:
            self.show()

    def query(self):
        return "" if self.showing_hint else self.var.get().strip()

    def _focus_in(self, _e=None):
        if self._close_job:
            try:
                self.after_cancel(self._close_job)
            except Exception:
                pass
            self._close_job = None
        if HAS_CTK:
            self.configure(border_color=T.ACCENT)
        if self.showing_hint:
            self.showing_hint = False
            self.var.set("")
            self.entry.set_text_color(T.TEXT)
        self._sync_clear_btn()

    def _focus_out(self, _e=None):
        if HAS_CTK:
            self.configure(border_color=T.BORDER)
        if not self.var.get().strip():
            self.showing_hint = True
            self.var.set(self.PLACEHOLDER)
            self.entry.set_text_color(T.DIM)
        self._sync_clear_btn()
        self._close_job = self.after(220, self.close)

    def clear(self):
        self.close()
        self.showing_hint = True
        self.var.set(self.PLACEHOLDER)
        self.entry.set_text_color(T.DIM)
        self._sync_clear_btn()

    def _typed(self, event=None):
        if event is not None and getattr(event, "keysym", "") in ("Return", "Escape", "Down", "Up", "Tab"):
            return
        self._sync_clear_btn()
        self.hits = sm.search(self.query(), include_advanced=True)
        self.cursor = 0 if self.hits else -1
        self.show()

    def show(self):
        self.close()
        if not self.query():
            return
        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height() + dp(4)
            self.popup = tk.Toplevel(self)
            self.popup.wm_overrideredirect(True)
            frame = tk.Frame(self.popup, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER_HI)
            frame.pack()
            if not self.hits:
                tk.Label(frame, text="No settings match. Try a different word.", bg=T.SURFACE, fg=T.MUTED, font=font(10),
                         padx=dp(14), pady=dp(10)).pack()
            else:
                self.row_widgets = []
                self._last_painted_cursor = None
                for i, s in enumerate(self.hits):
                    row = tk.Frame(frame, bg=T.SURFACE, cursor="hand2")
                    row.pack(fill="x")
                    title = tk.Label(row, text=s.label, bg=T.SURFACE, fg=T.TEXT, font=font(10, "bold"), anchor="w", padx=dp(14))
                    title.pack(fill="x", pady=(dp(6), 0))
                    where = tk.Label(row, text=location_of(s) + ("  (advanced)" if s.advanced else ""), bg=T.SURFACE, fg=T.DIM,
                                     font=font(9), anchor="w", padx=dp(14))
                    where.pack(fill="x", pady=(0, dp(6)))
                    for w in (row, title, where):
                        w.bind("<ButtonPress-1>", lambda e, k=i: self.pick(k))
                        w.bind("<Enter>", lambda e, k=i: self._hover_row(k))
                    self.row_widgets.append((row, title, where))
                self._paint()
            self.popup.update_idletasks()
            vx, vy, vw, vh = screen_bounds(self.popup)
            pw = self.popup.winfo_reqwidth()
            ph = self.popup.winfo_reqheight()
            x = max(vx + dp(6), min(x, vx + vw - pw - dp(8)))
            if y + ph > vy + vh - dp(8):
                y = max(vy + dp(6), self.winfo_rooty() - ph - dp(4))
            else:
                y = max(vy + dp(6), y)
            self.popup.wm_geometry(f"+{x}+{y}")
        except Exception:
            self.popup = None

    def _hover_row(self, index):
        if index != self.cursor:
            self.cursor = index
            self._paint()

    def _paint(self):
        rows = getattr(self, "row_widgets", [])
        if self._last_painted_cursor is None:
            indices = range(len(rows))
        else:
            indices = [idx for idx in (self._last_painted_cursor, self.cursor) if 0 <= idx < len(rows)]
        for i in indices:
            row, title, where = rows[i]
            bg = T.SURFACE3 if i == self.cursor else T.SURFACE
            for w in (row, title, where):
                w.configure(bg=bg)
        self._last_painted_cursor = self.cursor

    def _step(self, d):
        if self.hits:
            self.cursor = (self.cursor + d) % len(self.hits)
            self._paint()
        return "break"

    def close(self):
        if self._close_job:
            try:
                self.after_cancel(self._close_job)
            except Exception:
                pass
            self._close_job = None
        if self.popup is not None:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None
        self.row_widgets = []
        self._last_painted_cursor = None

    def pick(self, index):
        if 0 <= index < len(self.hits):
            s = self.hits[index]
            self.clear()
            self.focus_set()
            self.app.goto_setting(s.key)


# ==============================================================================
# SHORTCUT CAPTURE
# ==============================================================================
HOTKEY_KEYS = [s.key for s in sm.REGISTRY if s.key.startswith("hotkeys.") and s.kind == "custom"]


class HotkeyEntry(tk.Frame):
    """Shortcut button: click, press desired key/mouse side button combo, Esc cancels."""

    def __init__(self, master, app, setting):
        bg = bg_of(master)
        super().__init__(master, bg=bg)
        self.app, self.setting = app, setting
        self.capturing = False
        self.key_btn = FlatButton(self, "", self._start, size=10, padx=12, pady=6)
        self.key_btn.pack(side="left")
        self.clear_btn = FlatButton(self, "Clear", self._clear, style="ghost", size=9)
        self.clear_btn.pack(side="left", padx=(dp(8), 0))
        self._show(app.binder.get(setting))
        app.binder.listen(setting.key, self._show)

    def _show(self, value):
        if not self.capturing:
            self.key_btn.set_text(hk.display(value or ""))
            self.clear_btn.set_enabled(bool(value))

    def _start(self):
        if self.capturing:
            self.app.hotkeys.cancel_capture()
            self.capturing = False
            self._show(self.app.binder.get(self.setting))
            self.key_btn.set_style("normal")
            return
        if not self.app.hotkeys.available:
            self.app.notify("Global shortcuts only work on Windows.", "warn")
            return
        self.capturing = True
        self.key_btn.set_text("Press the keys now (Esc cancels)")
        self.key_btn.set_style("active")
        self.app.hotkeys.capture(lambda text: self.app.post(lambda: self.captured(text)))

    def captured(self, text):
        self.capturing = False
        self.key_btn.set_style("normal")
        if text is not None:
            for key in HOTKEY_KEYS:
                other = sm.BY_KEY[key]
                if key != self.setting.key and self.app.cfg.data["hotkeys"][key.split(".")[1]] == text:
                    self.app.binder.set(other, "")
                    self.app.notify(f"{hk.display(text)} was moved here from \"{other.label}\".", "info", 5000)
            self.app.binder.set(self.setting, text)
        self._show(self.app.binder.get(self.setting))

    def _clear(self):
        self.app.binder.set(self.setting, "")

    def set_enabled(self, flag):
        self.key_btn.set_enabled(flag)
        self.clear_btn.set_enabled(flag and bool(self.app.binder.get(self.setting)))
