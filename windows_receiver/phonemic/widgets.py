"""Small, dependency-free widget kit for the dark UI (pure Tkinter, canvas-drawn so it looks identical everywhere)."""
import sys
import math
import tkinter as tk
from tkinter import ttk

IS_WIN = sys.platform.startswith("win")
FONT = "Segoe UI" if IS_WIN else "Helvetica"


class Theme:
    """Graphite console palette. Text colours are checked for WCAG AA contrast in the test-suite."""
    BG = "#1b1f26"          # window
    SIDEBAR = "#151920"     # navigation rail
    SURFACE = "#232830"     # panels
    SURFACE2 = "#2b313b"    # inputs, inactive controls, panel headers
    SURFACE3 = "#363e4b"    # hover, slider tracks
    BORDER = "#3a4352"
    TEXT = "#e9edf3"
    MUTED = "#b4bcc9"
    DIM = "#949eae"
    ACCENT = "#35c6c3"
    ACCENT_HI = "#7fe3df"
    ACCENT_FG = "#06201f"
    GOOD = "#4cd48a"
    WARN = "#ffb547"
    BAD = "#ff6c71"
    VIOLET = "#a78bfa"


ACCENTS = {   # (accent, highlight, text on accent)
    "teal": ("#35c6c3", "#7fe3df", "#06201f"),
    "blue": ("#4aa3ff", "#8cc4ff", "#04131f"),
    "violet": ("#9b87ff", "#c1b5ff", "#120c2e"),
    "amber": ("#ffb547", "#ffd08a", "#2a1a00"),
    "rose": ("#ff7aa8", "#ffa6c4", "#2e0a18"),
}
T = Theme
_SCALE = 1.0


def set_scale(s):
    global _SCALE
    _SCALE = max(1.0, float(s))


def dp(x):
    return max(1, int(round(x * _SCALE))) if x else 0


FONT_DISPLAY = FONT          # replaced by init_fonts() when a more distinctive installed font is found


def init_fonts(root):
    """Numbers and titles use Bahnschrift (an industrial DIN-style face that ships with Windows 10 and 11)."""
    global FONT_DISPLAY
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families(root))
        FONT_DISPLAY = "Bahnschrift" if "Bahnschrift" in families else FONT
    except Exception:
        FONT_DISPLAY = FONT


def font(size=10, weight="normal", display=False):
    return (FONT_DISPLAY if display else FONT, size, weight)


def apply_accent(name):
    """Switch the accent colour. Must run before any widget is created (colours are read at creation time)."""
    acc, hi, fg = ACCENTS.get(name, ACCENTS["teal"])
    T.ACCENT, T.ACCENT_HI, T.ACCENT_FG = acc, hi, fg
    FlatButton.rebuild_styles()


def lerp_color(c1, c2, t):
    t = min(1.0, max(0.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ==============================================================================
# TTK STYLES
# ==============================================================================
def apply_styles(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    st.configure("PM.TCombobox", fieldbackground=T.SURFACE2, background=T.SURFACE2, foreground=T.TEXT,
                 arrowcolor=T.MUTED, bordercolor=T.BORDER, lightcolor=T.SURFACE2, darkcolor=T.SURFACE2,
                 selectbackground=T.SURFACE2, selectforeground=T.TEXT, padding=dp(6), relief="flat")
    st.map("PM.TCombobox",
           fieldbackground=[("readonly", T.SURFACE2), ("disabled", T.SURFACE)],
           foreground=[("readonly", T.TEXT), ("disabled", T.DIM)],
           selectbackground=[("readonly", T.SURFACE2)], selectforeground=[("readonly", T.TEXT)],
           arrowcolor=[("hover", T.TEXT)], bordercolor=[("focus", T.ACCENT), ("hover", T.DIM)])
    st.configure("PM.Vertical.TScrollbar", troughcolor=T.BG, background=T.SURFACE3, bordercolor=T.BG,
                 arrowcolor=T.MUTED, lightcolor=T.SURFACE3, darkcolor=T.SURFACE3, relief="flat", gripcount=0)
    st.map("PM.Vertical.TScrollbar", background=[("active", T.DIM)])
    root.option_add("*TCombobox*Listbox.background", T.SURFACE2)
    root.option_add("*TCombobox*Listbox.foreground", T.TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", T.ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", T.ACCENT_FG)
    root.option_add("*TCombobox*Listbox.font", font(10))
    root.option_add("*TCombobox*Listbox.borderWidth", 0)


# ==============================================================================
# SIMPLE CONTROLS
# ==============================================================================
def autowrap(label, pad=6):
    """Wrap a label's text to its *actual* width (a fixed wraplength overflows narrow columns and gets clipped)."""
    def on_configure(e):
        w = max(80, e.width - dp(pad))
        try:
            current = int(str(label.cget("wraplength")) or 0)
        except ValueError:
            current = 0
        if current != w:
            label.configure(wraplength=w)
    label.bind("<Configure>", on_configure, add="+")
    return label


class FlatButton(tk.Label):
    """Flat label-button with hover/press feedback. style: normal | primary | danger | ghost | active"""
    STYLES = {}

    @classmethod
    def rebuild_styles(cls):
        accent_active = lerp_color(T.SURFACE, T.ACCENT, 0.22)
        cls.STYLES = {
            "normal": (T.SURFACE2, T.SURFACE3, T.TEXT),
            "primary": (T.ACCENT, T.ACCENT_HI, T.ACCENT_FG),
            "danger": ("#4a2229", "#612b34", "#ff9aa2"),
            "ghost": (T.SURFACE, T.SURFACE2, T.MUTED),
            "active": (accent_active, lerp_color(T.SURFACE, T.ACCENT, 0.32), T.ACCENT_HI),
            "rec": (T.BAD, "#ff7f84", "#2b0409"),
            "warn": ("#4d3a10", "#634c16", T.WARN),
        }

    def __init__(self, master, text="", command=None, style="normal", padx=12, pady=6, size=10, weight="normal", **kw):
        self.style_name = style
        bg, _, fg = self.STYLES[style]
        super().__init__(master, text=text, bg=bg, fg=fg, font=font(size, weight), padx=dp(padx), pady=dp(pady),
                         cursor="hand2", **kw)
        self.command = command
        self._enabled = True
        self._down = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)

    def _colors(self):
        return self.STYLES[self.style_name]

    def _enter(self, _e=None):
        if self._enabled:
            self.configure(bg=self._colors()[1])

    def _leave(self, _e=None):
        self._down = False
        self.configure(bg=self._colors()[0])

    def _press(self, _e=None):
        self._down = True

    def _release(self, e):
        was = self._down
        self._down = False
        if self._enabled and was and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            if self.command:
                self.command()

    def set_style(self, style):
        if style != self.style_name:
            self.style_name = style
            bg, _, fg = self._colors()
            self.configure(bg=bg, fg=fg)

    def set_text(self, text):
        if self.cget("text") != text:
            self.configure(text=text)

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        bg, _, fg = self._colors()
        self.configure(bg=bg, fg=fg if enabled else T.DIM, cursor="hand2" if enabled else "arrow")


class Toggle(tk.Canvas):
    """iOS-style switch. set() never fires the command; user clicks do."""

    def __init__(self, master, value=False, command=None, bg=None):
        self.w, self.h = dp(40), dp(22)
        super().__init__(master, width=self.w, height=self.h, bg=bg or master.cget("bg"), highlightthickness=0, bd=0,
                         cursor="hand2")
        self.value = bool(value)
        self.command = command
        self._enabled = True
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.w, self.h
        on = self.value
        track = T.ACCENT if on else T.SURFACE3
        if not self._enabled:
            track = T.SURFACE2
        r = h / 2
        self.create_line(r, h / 2, w - r, h / 2, width=h - 2, capstyle="round", fill=track)
        kx = w - r if on else r
        kr = r - dp(3)
        self.create_oval(kx - kr, h / 2 - kr, kx + kr, h / 2 + kr, fill="#ffffff" if self._enabled else T.DIM, outline="")

    def _click(self, _e=None):
        if not self._enabled:
            return
        self.value = not self.value
        self._draw()
        if self.command:
            self.command(self.value)

    def set(self, value, notify=False):
        value = bool(value)
        if value != self.value:
            self.value = value
            self._draw()
        if notify and self.command:
            self.command(self.value)

    def get(self):
        return self.value

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        self._draw()


class Slider(tk.Canvas):
    """Horizontal slider. `origin` makes bipolar sliders fill from the centre. Double-click resets to `default`."""

    def __init__(self, master, from_=0.0, to=1.0, value=0.0, step=0.01, default=None, origin=None, command=None,
                 bg=None, accent=None, log=False):
        super().__init__(master, width=dp(100), height=dp(24), bg=bg or master.cget("bg"), highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.lo, self.hi, self.step = float(from_), float(to), float(step)
        self.log = bool(log)                       # logarithmic travel for frequencies and Q
        self.default = default if default is not None else value
        self.origin = origin
        self.command = command
        self.accent = accent or T.ACCENT
        self.value = self._clamp(value)
        self._enabled = True
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._down)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Double-Button-1>", self._reset)
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda e: self._nudge(1))
        self.bind("<Button-5>", lambda e: self._nudge(-1))
        self.bind("<Left>", lambda e: self._nudge(-1))
        self.bind("<Right>", lambda e: self._nudge(1))

    def _clamp(self, v):
        v = min(self.hi, max(self.lo, float(v)))
        if self.log:                               # keep three significant figures
            v = float(f"{v:.3g}")
        elif self.step > 0:
            v = round(round((v - self.lo) / self.step) * self.step + self.lo, 6)
        return min(self.hi, max(self.lo, v))

    def _frac(self, v):
        if self.log:
            return (math.log(max(v, 1e-9)) - math.log(self.lo)) / ((math.log(self.hi) - math.log(self.lo)) or 1.0)
        return (v - self.lo) / ((self.hi - self.lo) or 1.0)

    def _value_at(self, frac):
        if self.log:
            return math.exp(math.log(self.lo) + frac * (math.log(self.hi) - math.log(self.lo)))
        return self.lo + frac * (self.hi - self.lo)

    def _geom(self):
        pad = dp(9)
        return pad, max(pad + 1, self.winfo_width() - pad)

    def _x_of(self, v):
        x0, x1 = self._geom()
        return x0 + self._frac(v) * (x1 - x0)

    def _draw(self):
        self.delete("all")
        h = self.winfo_height() or dp(24)
        cy = h / 2
        x0, x1 = self._geom()
        acc = self.accent if self._enabled else T.DIM
        self.create_line(x0, cy, x1, cy, width=dp(4), capstyle="round", fill=T.SURFACE3)
        xv = self._x_of(self.value)
        xo = self._x_of(self.origin) if self.origin is not None else x0
        if abs(xv - xo) > 0.5:
            self.create_line(xo, cy, xv, cy, width=dp(4), capstyle="round", fill=acc)
        if self.origin is not None:
            self.create_line(xo, cy - dp(5), xo, cy + dp(5), width=1, fill=T.DIM)
        r = dp(7)
        self.create_oval(xv - r, cy - r, xv + r, cy + r, fill="#f4f8fc" if self._enabled else T.MUTED, outline=acc, width=dp(2))

    def _from_x(self, x):
        x0, x1 = self._geom()
        frac = min(1.0, max(0.0, (x - x0) / ((x1 - x0) or 1)))
        self._apply(self._value_at(frac))

    def _apply(self, v, notify=True):
        v = self._clamp(v)
        if v != self.value:
            self.value = v
            self._draw()
            if notify and self.command:
                self.command(v)

    def _down(self, e):
        if self._enabled:
            self.focus_set()
            self._from_x(e.x)

    def _drag(self, e):
        if self._enabled:
            self._from_x(e.x)

    def _reset(self, _e=None):
        if self._enabled:
            self._apply(self.default)

    def _wheel(self, e):
        try:
            focused = self.focus_get() is self
        except Exception:                       # tkinter raises KeyError('popdown') while a combobox list is open
            focused = False
        if self._enabled and focused:
            self._nudge(1 if e.delta > 0 else -1)
            return "break"

    def _nudge(self, direction):
        if not self._enabled:
            return
        if self.log:                               # one nudge = 2 % of the travel
            self._apply(self._value_at(min(1.0, max(0.0, self._frac(self.value) + direction * 0.02))))
        else:
            self._apply(self.value + direction * (self.step or (self.hi - self.lo) / 100.0))

    def set(self, v, notify=False):
        self._apply(v, notify)
        self._draw()

    def get(self):
        return self.value

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()


class LabeledSlider(tk.Frame):
    """Label + live value + slider. `fmt(value)` formats the readout; `hint` is shown dimmed under the label."""

    def __init__(self, master, label, from_, to, value, step, fmt=None, command=None, default=None, origin=None,
                 bg=None, hint=None, accent=None):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg)
        self.fmt = fmt or (lambda v: f"{v:g}")
        self.user_command = command
        top = tk.Frame(self, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=bg, fg=T.TEXT, font=font(10)).pack(side="left")
        self.value_label = tk.Label(top, text="", bg=bg, fg=T.ACCENT_HI, font=font(10, "bold"))
        self.value_label.pack(side="right")
        self.slider = Slider(self, from_, to, value, step, default=default, origin=origin, command=self._changed,
                             bg=bg, accent=accent)
        self.slider.pack(fill="x", pady=(dp(2), 0))
        if hint:
            autowrap(tk.Label(self, text=hint, bg=bg, fg=T.DIM, font=font(8), anchor="w", justify="left",
                              wraplength=dp(240))).pack(fill="x")
        self.value_label.configure(text=self.fmt(self.slider.value))

    def _changed(self, v):
        self.value_label.configure(text=self.fmt(v))
        if self.user_command:
            self.user_command(v)

    def set(self, v, notify=False):
        self.slider.set(v, notify)
        self.value_label.configure(text=self.fmt(self.slider.value))

    def get(self):
        return self.slider.value

    def set_enabled(self, enabled):
        self.slider.set_enabled(enabled)
        self.value_label.configure(fg=T.ACCENT_HI if enabled else T.DIM)


class SwitchRow(tk.Frame):
    """Toggle with a title and optional description on one row."""

    def __init__(self, master, title, value=False, command=None, desc=None, bg=None):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg)
        text = tk.Frame(self, bg=bg)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=bg, fg=T.TEXT, font=font(10), anchor="w").pack(fill="x")
        if desc:
            autowrap(tk.Label(text, text=desc, bg=bg, fg=T.DIM, font=font(8), anchor="w", justify="left",
                              wraplength=dp(240))).pack(fill="x")
        self.toggle = Toggle(self, value, command, bg=bg)
        self.toggle.pack(side="right", padx=(dp(8), 0))

    def set(self, v, notify=False):
        self.toggle.set(v, notify)

    def get(self):
        return self.toggle.get()


class Segmented(tk.Frame):
    """Row of mutually exclusive buttons. options = [(key, text), ...]"""

    def __init__(self, master, options, value=None, command=None, bg=None, size=9):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg)
        self.command = command
        self.value = value
        self.buttons = {}
        for i, (key, text) in enumerate(options):
            b = FlatButton(self, text, command=lambda k=key: self._pick(k), style="normal", padx=10, pady=4, size=size)
            b.pack(side="left", padx=(0 if i == 0 else dp(2), 0))
            self.buttons[key] = b
        self._paint()

    def _paint(self):
        for k, b in self.buttons.items():
            b.set_style("active" if k == self.value else "normal")

    def _pick(self, key):
        if key != self.value:
            self.value = key
            self._paint()
            if self.command:
                self.command(key)

    def set(self, key, notify=False):
        self.value = key
        self._paint()
        if notify and self.command:
            self.command(key)

    def get(self):
        return self.value


class Combo(ttk.Combobox):
    def __init__(self, master, values=(), width=36, command=None):
        super().__init__(master, values=list(values), state="readonly", width=width, style="PM.TCombobox",
                         exportselection=False, font=font(10))
        self.command = command
        self.bind("<<ComboboxSelected>>", self._selected)

    def _selected(self, _e=None):
        self.selection_clear()
        if self.command:
            self.command(self.get())

    def set_values(self, values, current=None):
        self.configure(values=list(values))
        if current is not None:
            self.set(current)


class Card(tk.Frame):
    """Surface panel with a title row. Put content in `.body`; add header widgets via `.header`."""

    def __init__(self, master, title=None, subtitle=None, pad=14, bg=None, **kw):
        super().__init__(master, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER,
                         highlightcolor=T.BORDER, bd=0, **kw)
        self.header = None
        if title:
            self.header = tk.Frame(self, bg=T.SURFACE)
            self.header.pack(fill="x", padx=dp(pad), pady=(dp(pad - 2), 0))
            tk.Label(self.header, text=title, bg=T.SURFACE, fg=T.TEXT, font=font(11, "bold")).pack(side="left")
            if subtitle:
                tk.Label(self.header, text=subtitle, bg=T.SURFACE, fg=T.DIM, font=font(9)).pack(side="left", padx=(dp(8), 0))
        self.body = tk.Frame(self, bg=T.SURFACE)
        self.body.pack(fill="both", expand=True, padx=dp(pad), pady=(dp(8) if title else dp(pad), dp(pad)))


class StatTile(tk.Frame):
    def __init__(self, master, label, hint=""):
        super().__init__(master, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER, bd=0)
        tk.Label(self, text=label, bg=T.SURFACE, fg=T.DIM, font=font(9), anchor="w").pack(
            fill="x", padx=dp(12), pady=(dp(10), 0))
        self.value = tk.Label(self, text="-", bg=T.SURFACE, fg=T.TEXT, font=font(17, "bold", True), anchor="w")
        self.value.pack(fill="x", padx=dp(12))
        self.sub = tk.Label(self, text=hint, bg=T.SURFACE, fg=T.DIM, font=font(8), anchor="w")
        self.sub.pack(fill="x", padx=dp(12), pady=(0, dp(10)))

    def set(self, text, color=None, sub=None):
        self.value.configure(text=text, fg=color or T.TEXT)
        if sub is not None:
            self.sub.configure(text=sub)


class Separator(tk.Frame):
    def __init__(self, master, bg=None):
        super().__init__(master, height=1, bg=T.BORDER)


class Tooltip:
    def __init__(self, widget, text, delay=600):
        self.widget, self.text, self.delay = widget, text, delay
        self._job = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._hide()
        self._job = self.widget.after(self.delay, self._show)

    def _show(self):
        try:
            x = self.widget.winfo_rootx() + dp(10)
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + dp(4)
            self._tip = tk.Toplevel(self.widget)
            self._tip.wm_overrideredirect(True)
            self._tip.wm_geometry(f"+{x}+{y}")
            tk.Label(self._tip, text=self.text, bg=T.SURFACE3, fg=T.TEXT, font=font(9), padx=dp(8), pady=dp(5),
                     justify="left", wraplength=dp(320), highlightthickness=1, highlightbackground=T.BORDER).pack()
        except Exception:
            self._tip = None

    def _hide(self, _e=None):
        if self._job:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# ==============================================================================
# SCROLLING
# ==============================================================================
class ScrollFrame(tk.Frame):
    def __init__(self, master, bg=None):
        bg = bg or T.BG
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style="PM.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._inner_changed)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))

    def _inner_changed(self, _e=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def scroll_to(self, widget):
        """Bring a widget inside the scrolled content into view (a little below the top edge)."""
        try:
            self.inner.update_idletasks()
            y, w = 0, widget
            while w is not None and w is not self.inner:
                y += w.winfo_y()
                w = w.master
            total = max(1, self.inner.winfo_height())
            self.canvas.yview_moveto(min(1.0, max(0.0, (y - dp(48)) / total)))
        except Exception:
            pass

    def scroll_units(self, units):
        """Scroll only when the content is taller than the viewport."""
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(units, "units")


# ==============================================================================
# ICONS
# ==============================================================================
def draw_icon(c, name, color, size):
    k = size / 20.0
    w = max(1, int(round(1.6 * k)))
    c.delete("all")
    if name == "dashboard":
        for x, y in ((2, 2), (11, 2), (2, 11), (11, 11)):
            c.create_rectangle(x * k, y * k, (x + 7) * k, (y + 7) * k, outline=color, width=w)
    elif name == "sound":
        for x, ky in ((5, 7), (10, 13), (15, 9)):
            c.create_line(x * k, 3 * k, x * k, 17 * k, fill=color, width=w)
            c.create_oval((x - 2.5) * k, (ky - 2.5) * k, (x + 2.5) * k, (ky + 2.5) * k, fill=color, outline=color)
    elif name == "voice":
        for x, h in ((3, 4), (6.5, 10), (10, 16), (13.5, 9), (17, 5)):
            c.create_line(x * k, (10 - h / 2) * k, x * k, (10 + h / 2) * k, fill=color, width=w + 1, capstyle="round")
    elif name == "devices":
        c.create_polygon(2 * k, 8 * k, 6 * k, 8 * k, 11 * k, 4 * k, 11 * k, 16 * k, 6 * k, 12 * k, 2 * k, 12 * k,
                         outline=color, fill="", width=w)
        c.create_arc(8 * k, 6 * k, 16 * k, 14 * k, start=-50, extent=100, style="arc", outline=color, width=w)
        c.create_arc(8 * k, 3 * k, 19 * k, 17 * k, start=-50, extent=100, style="arc", outline=color, width=w)
    elif name == "network":
        for r in (4, 8, 12):
            c.create_arc((10 - r) * k, (16 - r) * k, (10 + r) * k, (16 + r) * k, start=50, extent=80, style="arc",
                         outline=color, width=w)
        c.create_oval(8.8 * k, 14.8 * k, 11.2 * k, 17.2 * k, fill=color, outline=color)
    elif name == "settings":
        c.create_oval(6 * k, 6 * k, 14 * k, 14 * k, outline=color, width=w)
        for i in range(8):
            a = i * math.pi / 4
            c.create_line((10 + 6.5 * math.cos(a)) * k, (10 + 6.5 * math.sin(a)) * k,
                          (10 + 9 * math.cos(a)) * k, (10 + 9 * math.sin(a)) * k, fill=color, width=w + 1)
    elif name == "log":
        for y, x2 in ((5, 17), (10, 13), (15, 16)):
            c.create_line(3 * k, y * k, x2 * k, y * k, fill=color, width=w, capstyle="round")
    elif name == "mic":
        c.create_rectangle(7 * k, 2 * k, 13 * k, 12 * k, outline=color, width=w)
        c.create_arc(4 * k, 6 * k, 16 * k, 16 * k, start=200, extent=140, style="arc", outline=color, width=w)
        c.create_line(10 * k, 15 * k, 10 * k, 18 * k, fill=color, width=w)


class NavButton(tk.Frame):
    def __init__(self, master, icon, text, command):
        super().__init__(master, bg=T.SIDEBAR, cursor="hand2")
        self.command, self.icon, self.active = command, icon, False
        self.bar = tk.Frame(self, width=dp(3), bg=T.SIDEBAR)
        self.bar.pack(side="left", fill="y")
        self.canvas = tk.Canvas(self, width=dp(22), height=dp(22), bg=T.SIDEBAR, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", padx=(dp(14), dp(10)), pady=dp(10))
        self.label = tk.Label(self, text=text, bg=T.SIDEBAR, fg=T.MUTED, font=font(10), anchor="w")
        self.label.pack(side="left", fill="x", expand=True)
        for w in (self, self.canvas, self.label):
            w.bind("<Button-1>", lambda e: self.command())
            w.bind("<Enter>", lambda e: self._paint(hover=True))
            w.bind("<Leave>", lambda e: self._paint(hover=False))
        self._paint()

    def _paint(self, hover=False):
        bg = T.SURFACE2 if (self.active or hover) else T.SIDEBAR
        fg = T.TEXT if self.active else (T.TEXT if hover else T.MUTED)
        icon_color = T.ACCENT if self.active else fg
        for w in (self, self.canvas, self.label):
            w.configure(bg=bg)
        self.label.configure(fg=fg, font=font(10, "bold" if self.active else "normal"))
        self.bar.configure(bg=T.ACCENT if self.active else bg)
        draw_icon(self.canvas, self.icon, icon_color, dp(22))

    def set_active(self, active):
        self.active = bool(active)
        self._paint()


# ==============================================================================
# VISUALISERS
# ==============================================================================
class LevelMeter(tk.Canvas):
    """Segmented dBFS meter with RMS marker, peak-hold and clip LED."""
    SEGMENTS = 54
    DB_MIN = -60.0

    def __init__(self, master, height=34, bg=None):
        super().__init__(master, width=dp(200), height=dp(height), bg=bg or T.SURFACE, highlightthickness=0, bd=0)
        self._items = []
        self._lit = [-1] * self.SEGMENTS
        self._rms = None
        self._hold = None
        self._led = None
        self._labels_built = False
        self.bind("<Configure>", lambda e: self._build())

    def _x(self, db):
        return self._pad + (min(0.0, max(self.DB_MIN, db)) - self.DB_MIN) / -self.DB_MIN * self._span

    def _build(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        self._pad = dp(2)
        self._led_w = dp(16)
        self._span = max(10, w - 2 * self._pad - self._led_w)
        bar_h = dp(16)
        self._bar_y0 = dp(2)
        self._bar_y1 = self._bar_y0 + bar_h
        seg_w = self._span / self.SEGMENTS
        self._items = []
        for i in range(self.SEGMENTS):
            x0 = self._pad + i * seg_w
            self._items.append(self.create_rectangle(x0 + 1, self._bar_y0, x0 + seg_w - 1, self._bar_y1, fill=T.SURFACE2, outline=""))
        self._rms = self.create_rectangle(0, self._bar_y0 - 2, 0, self._bar_y1 + 2, fill="#ffffff", outline="")
        self._hold = self.create_rectangle(0, self._bar_y0 - 2, 0, self._bar_y1 + 2, fill=T.TEXT, outline="")
        self._led = self.create_oval(w - self._led_w + dp(3), self._bar_y0, w - dp(1), self._bar_y1, fill=T.SURFACE3, outline="")
        for db in (-60, -48, -36, -24, -12, -6, 0):
            x = self._x(db)
            self.create_text(x, self._bar_y1 + dp(9), text=str(db), fill=T.DIM, font=font(7), anchor="n" if db > -60 else "nw")
        self._lit = [-1] * self.SEGMENTS

    def _color(self, i):
        db = self.DB_MIN + (i + 0.5) / self.SEGMENTS * -self.DB_MIN
        if db > -3:
            return T.BAD
        if db > -12:
            return T.WARN
        return T.GOOD

    def update_levels(self, peak_db, rms_db, hold_db, clipped):
        if not self._items:
            return
        lit = int((min(0.0, max(self.DB_MIN, peak_db)) - self.DB_MIN) / -self.DB_MIN * self.SEGMENTS)
        for i, item in enumerate(self._items):
            state = 1 if i < lit else 0
            if state != self._lit[i]:
                self._lit[i] = state
                self.itemconfigure(item, fill=self._color(i) if state else T.SURFACE2)
        xr = self._x(rms_db)
        self.coords(self._rms, xr - 1, self._bar_y0 - 2, xr + 1, self._bar_y1 + 2)
        xh = self._x(hold_db)
        self.coords(self._hold, xh - 1, self._bar_y0, xh + 1, self._bar_y1)
        self.itemconfigure(self._led, fill=T.BAD if clipped else T.SURFACE3)


class SpectrumView(tk.Canvas):
    """40-band spectrum with falling bars + peak caps, or an oscilloscope trace."""

    def __init__(self, master, height=140, bands=40):
        super().__init__(master, width=dp(200), height=dp(height), bg=T.SURFACE, highlightthickness=0, bd=0)
        self.n = bands
        self.mode = "spectrum"
        self.vals = [0.0] * bands
        self.caps = [0.0] * bands
        self.cap_t = [0] * bands
        self._bars, self._cap_items, self._scope = [], [], None
        self.bind("<Configure>", lambda e: self._build())

    def set_mode(self, mode):
        self.mode = mode
        self._build()

    def _build(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        self._cw, self._ch = w, h
        self._bars, self._cap_items, self._scope = [], [], None
        for frac in (0.25, 0.5, 0.75):
            self.create_line(0, h * frac, w, h * frac, fill=T.SURFACE2)
        if self.mode == "spectrum":
            gap = dp(2)
            bw = (w - gap * (self.n + 1)) / self.n
            for i in range(self.n):
                x0 = gap + i * (bw + gap)
                col = lerp_color(T.ACCENT, T.VIOLET, i / max(1, self.n - 1))
                self._bars.append(self.create_rectangle(x0, h, x0 + bw, h, fill=col, outline=""))
                self._cap_items.append(self.create_rectangle(x0, h, x0 + bw, h, fill=T.TEXT, outline=""))
            for f, lab in ((100, "100"), (1000, "1k"), (10000, "10k")):
                pos = (math.log10(f) - math.log10(60)) / (math.log10(18000) - math.log10(60))
                self.create_text(pos * w, h - dp(2), text=lab, fill=T.DIM, font=font(7), anchor="s")
        else:
            self.create_line(0, h / 2, w, h / 2, fill=T.BORDER)
            self._scope = self.create_line(0, h / 2, w, h / 2, fill=T.ACCENT, width=dp(2), smooth=True)

    def feed(self, bands, scope):
        if self.mode == "spectrum":
            if not self._bars:
                return
            h, gap = self._ch, dp(2)
            bw = (self._cw - gap * (self.n + 1)) / self.n
            for i in range(self.n):
                v = float(bands[i]) if i < len(bands) else 0.0
                self.vals[i] = v if v > self.vals[i] else max(v, self.vals[i] - 0.045)
                if self.vals[i] >= self.caps[i]:
                    self.caps[i], self.cap_t[i] = self.vals[i], 18
                elif self.cap_t[i] > 0:
                    self.cap_t[i] -= 1
                else:
                    self.caps[i] = max(self.vals[i], self.caps[i] - 0.03)
                x0 = gap + i * (bw + gap)
                top = h - self.vals[i] * (h - dp(14))
                self.coords(self._bars[i], x0, top, x0 + bw, h)
                ct = h - self.caps[i] * (h - dp(14))
                self.coords(self._cap_items[i], x0, ct - dp(2), x0 + bw, ct)
        elif self._scope is not None and len(scope) > 1:
            pts = []
            step = self._cw / (len(scope) - 1)
            amp = self._ch * 0.45
            for i, s in enumerate(scope):
                pts.extend((i * step, self._ch / 2 - max(-1.0, min(1.0, float(s) * 2.5)) * amp))
            self.coords(self._scope, *pts)

    def idle(self):
        self.feed([0.0] * self.n, [0.0] * 128)


class EQCurve(tk.Canvas):
    """Read-only frequency-response plot with band markers (20 Hz - 20 kHz, +/-15 dB)."""
    FMIN, FMAX, DBR = 20.0, 20000.0, 15.0

    def __init__(self, master, height=120):
        super().__init__(master, width=dp(200), height=dp(height), bg=T.SURFACE2, highlightthickness=0, bd=0)
        self.curve = None
        self.nodes = []
        self.bind("<Configure>", lambda e: self.redraw())

    def _x(self, f):
        w = self.winfo_width()
        return (math.log10(max(self.FMIN, f)) - math.log10(self.FMIN)) / (math.log10(self.FMAX) - math.log10(self.FMIN)) * w

    def _y(self, db):
        h = self.winfo_height()
        return h / 2 - max(-self.DBR, min(self.DBR, db)) / self.DBR * (h / 2 - dp(6))

    def set_curve(self, freqs, db, nodes):
        self.curve = (list(freqs), list(db))
        self.nodes = nodes
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20:
            return
        for db in (-10, -5, 0, 5, 10):
            self.create_line(0, self._y(db), w, self._y(db), fill=T.BORDER if db == 0 else T.SURFACE3)
        for f, lab in ((100, "100"), (1000, "1k"), (10000, "10k")):
            self.create_line(self._x(f), 0, self._x(f), h, fill=T.SURFACE3)
            self.create_text(self._x(f) + dp(3), h - dp(2), text=lab, fill=T.DIM, font=font(7), anchor="sw")
        if self.curve:
            pts = []
            for f, d in zip(*self.curve):
                pts.extend((self._x(f), self._y(d)))
            if len(pts) >= 4:
                self.create_line(*pts, fill=T.ACCENT, width=dp(2), smooth=True)
        for f, g in self.nodes:
            x, y, r = self._x(f), self._y(g), dp(4)
            self.create_oval(x - r, y - r, x + r, y + r, fill=T.TEXT, outline=T.ACCENT)


FlatButton.rebuild_styles()
