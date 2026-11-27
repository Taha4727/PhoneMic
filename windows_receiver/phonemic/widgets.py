"""Obsidian / Graphite UI widget kit built on CustomTkinter with Canvas visualizers.

Falls back cleanly to pure Tkinter if CustomTkinter is absent or in headless fake_tk environments.
"""
import sys
import math
import tkinter as tk
from tkinter import ttk

try:
    import customtkinter as ctk
    HAS_CTK = True
except Exception:
    ctk = None
    HAS_CTK = False

IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")
FONT = "Segoe UI" if IS_WIN else "DejaVu Sans"
MONO_FONT = "Consolas" if IS_WIN else "DejaVu Sans Mono"


class Theme:
    """Matte Obsidian & Graphite palette with restrained multi-color accents (WCAG AA checked)."""
    BG = "#07080B"          # true obsidian window background
    SIDEBAR = "#0B0D12"     # deep graphite navigation rail
    SURFACE = "#11141B"     # primary card surface
    SURFACE2 = "#171B24"    # inputs, recessed controls, headers
    SURFACE3 = "#202633"    # hover states, muted tracks
    BORDER = "#232A38"      # crisp 1px card border
    BORDER_HI = "#333D52"   # highlighted border
    TEXT = "#EEF2F8"        # crisp matte off-white ink
    MUTED = "#ACB6C6"       # secondary readable copy
    DIM = "#8B96AA"         # subtle caption / hint copy (>= 4.5:1 on SURFACE2)
    ACCENT = "#36AEBF"      # matte cyan-teal primary accent
    ACCENT_HI = "#5CD0E0"   # matte cyan highlight
    ACCENT_FG = "#04161D"   # high-contrast text on primary accent fill
    GOOD = "#42BF8F"        # matte emerald (live / healthy / USB)
    WARN = "#DFA946"        # matte amber (mute / standby / peak mid)
    BAD = "#DE7286"         # matte crimson-rose (record / clip / error)
    BLUE = "#6398DF"        # matte studio blue (voice changer / EQ / ethernet)
    BLUE_HI = "#91BBF2"     # matte light studio blue
    SOFT_COLORS = False
    IS_MONO = False


ACCENTS = {   # (matte accent, highlight, text_on_accent)
    "teal": ("#36AEBF", "#5CD0E0", "#04161D"),
    "blue": ("#6398DF", "#91BBF2", "#051326"),
    "indigo": ("#768CE0", "#A5B5F2", "#08102A"),
    "amber": ("#DFA946", "#EBC16E", "#241702"),
    "rose": ("#DE7286", "#EC9AA9", "#28080F"),
    "mono": ("#C4CEDB", "#E4EAF2", "#07080B"),
}

SOFT_ACCENTS = {   # gentler matte saturation for eye comfort (WCAG AA checked)
    "teal": ("#4AAAB9", "#7CC6D2", "#05191F"),
    "blue": ("#6B95CA", "#96B7E0", "#071422"),
    "indigo": ("#7B8ECD", "#A6B5E2", "#0B1124"),
    "amber": ("#CFA04D", "#E2BA74", "#221704"),
    "rose": ("#D37385", "#E49BA8", "#26080F"),
    "mono": ("#B4BECB", "#DAE1EB", "#07080B"),
}

_NORMAL_SEMANTIC = {
    "TEXT": "#EEF2F8",
    "MUTED": "#ACB6C6",
    "DIM": "#8B96AA",
    "GOOD": "#42BF8F",
    "WARN": "#DFA946",
    "BAD": "#DE7286",
    "BLUE": "#6398DF",
    "BLUE_HI": "#91BBF2",
}

_SOFT_SEMANTIC = {
    "TEXT": "#E1E6EE",
    "MUTED": "#A5B0C0",
    "DIM": "#8894A6",
    "GOOD": "#5AB289",
    "WARN": "#CFA04D",
    "BAD": "#D37385",
    "BLUE": "#6B95CA",
    "BLUE_HI": "#96B7E0",
}

_MONO_SEMANTIC = {
    "TEXT": "#EBEEF2",
    "MUTED": "#B2BAC6",
    "DIM": "#8D96A4",
    "GOOD": "#CBD3DF",
    "WARN": "#A8B2C0",
    "BAD": "#E2E6EC",
    "BLUE": "#98A2B2",
    "BLUE_HI": "#C4CEDB",
}

T = Theme
_SCALE = 1.0


def set_scale(s):
    global _SCALE
    _SCALE = max(1.0, float(s))


def dp(x):
    return max(1, int(round(x * _SCALE))) if x else 0


FONT_DISPLAY = FONT          # replaced by init_fonts() when Bahnschrift (Win) or Linux sans fonts are installed


def init_fonts(root):
    """Select crisp display/body/mono fonts for the host platform."""
    global FONT, FONT_DISPLAY, MONO_FONT
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families(root))
        if IS_WIN:
            FONT_DISPLAY = "Bahnschrift" if "Bahnschrift" in families else FONT
            MONO_FONT = "Consolas"
        else:
            for candidate in ("Noto Sans", "Inter", "Ubuntu", "Cantarell", "Liberation Sans", "DejaVu Sans", "Helvetica"):
                if candidate in families:
                    FONT = candidate
                    break
            FONT_DISPLAY = FONT
            for mcandidate in ("JetBrains Mono", "Noto Sans Mono", "Ubuntu Mono", "Liberation Mono", "DejaVu Sans Mono", "Courier"):
                if mcandidate in families:
                    MONO_FONT = mcandidate
                    break
    except Exception:
        FONT_DISPLAY = FONT


def font(size=10, weight="normal", display=False):
    return (FONT_DISPLAY if display else FONT, size, weight)


def create_root():
    """Create main window root using CustomTkinter when available (with deterministic dp() scaling)."""
    if HAS_CTK:
        ctk.set_appearance_mode("dark")
        try:
            # Lock CustomTkinter's internal scaling before CTk() initializes Windows DPI tracking
            # so PhoneMic's dp() helper scales raw tk.Canvas and CTk widgets 1:1 without double-scaling.
            if hasattr(ctk, "deactivate_automatic_dpi_awareness"):
                ctk.deactivate_automatic_dpi_awareness()
            ctk.set_widget_scaling(1.0)
            ctk.set_window_scaling(1.0)
        except Exception:
            pass
        try:
            root = ctk.CTk(fg_color=T.BG, className="PhoneMicReceiver")
        except TypeError:
            root = ctk.CTk(fg_color=T.BG)
        return root
    try:
        return tk.Tk(className="PhoneMicReceiver")
    except TypeError:
        return tk.Tk()


def screen_bounds(widget):
    """Return virtual desktop bounds (vx, vy, vw, vh), supporting multi-monitor setups."""
    if IS_WIN:
        try:
            import ctypes
            sm_fn = ctypes.windll.user32.GetSystemMetrics
            vx, vy = int(sm_fn(76)), int(sm_fn(77))
            vw, vh = int(sm_fn(78)), int(sm_fn(79))
            if vw > 0 and vh > 0:
                return (vx, vy, vw, vh)
        except Exception:
            pass
    try:
        sw, sh = int(widget.winfo_screenwidth()), int(widget.winfo_screenheight())
    except Exception:
        return (0, 0, 1920, 1080)
    try:
        vx, vy = int(widget.winfo_vrootx()), int(widget.winfo_vrooty())
        vw, vh = int(widget.winfo_vrootwidth()), int(widget.winfo_vrootheight())
        if vw >= sw and vh >= sh:
            return (vx, vy, vw, vh)
    except Exception:
        pass
    return (0, 0, sw, sh)


def create_toplevel(parent, fg_color=None):
    """Create a dark CustomTkinter toplevel dialog when available."""
    bg = fg_color or T.SURFACE
    if HAS_CTK:
        win = ctk.CTkToplevel(parent, fg_color=bg)
        return win
    win = tk.Toplevel(parent)
    win.configure(bg=bg)
    return win


def bg_of(widget, default=None):
    """Safely read an explicit hex background from either CTk* or tk.* containers."""
    if widget is None:
        return default or T.SURFACE
    try:
        c = widget.cget("fg_color")
        if isinstance(c, (tuple, list)):
            c = c[1] if len(c) > 1 else c[0]
        if isinstance(c, str) and c.startswith("#"):
            return c
    except Exception:
        pass
    try:
        c = widget.cget("bg")
        if isinstance(c, str) and c.startswith("#"):
            return c
    except Exception:
        pass
    return default or T.SURFACE


def apply_theme(name, soft=False):
    """Apply active accent preset (including 'mono') and optional soft eye-comfort palette."""
    key = "blue" if name == "violet" else (name if name in ACCENTS else "teal")
    T.IS_MONO = (key == "mono")
    T.SOFT_COLORS = bool(soft)
    if T.IS_MONO:
        tokens = _MONO_SEMANTIC
    elif T.SOFT_COLORS:
        tokens = _SOFT_SEMANTIC
    else:
        tokens = _NORMAL_SEMANTIC
    for attr, val in tokens.items():
        setattr(T, attr, val)
    palette = SOFT_ACCENTS if T.SOFT_COLORS else ACCENTS
    acc, hi, fg = palette.get(key, palette["teal"])
    T.ACCENT, T.ACCENT_HI, T.ACCENT_FG = acc, hi, fg
    FlatButton.rebuild_styles()


def apply_accent(name, soft=None):
    """Switch the accent colour before widgets are constructed (or live)."""
    apply_theme(name, soft=T.SOFT_COLORS if soft is None else soft)


def lerp_color(c1, c2, t):
    t = min(1.0, max(0.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ==============================================================================
# TTK FALLBACK STYLES (for headless / minimal ttk widgets)
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
    try:
        root.option_add("*TCombobox*Listbox.background", T.SURFACE2)
        root.option_add("*TCombobox*Listbox.foreground", T.TEXT)
        root.option_add("*TCombobox*Listbox.selectBackground", T.ACCENT)
        root.option_add("*TCombobox*Listbox.selectForeground", T.ACCENT_FG)
        root.option_add("*TCombobox*Listbox.font", font(10))
        root.option_add("*TCombobox*Listbox.borderWidth", 0)
    except Exception:
        pass


# ==============================================================================
# HELPERS & CONTROLS
# ==============================================================================
def autowrap(label, pad=6):
    """Wrap a label's text to its real allocated width without synchronous <Configure> loops."""
    def apply_wrap(target_w):
        label._wrap_job = None
        try:
            if not label.winfo_exists():
                return
            current = int(str(label.cget("wraplength")) or 0)
            if abs(current - target_w) > dp(2):
                label.configure(wraplength=target_w)
        except Exception:
            pass

    def on_configure(e):
        if not e.width or e.width < dp(40):
            return
        w = max(dp(80), e.width - dp(pad))
        try:
            current = int(str(label.cget("wraplength")) or 0)
        except ValueError:
            current = 0
        if abs(current - w) <= dp(2):
            return
        job = getattr(label, "_wrap_job", None)
        if job:
            try:
                label.after_cancel(job)
            except Exception:
                pass
        label._wrap_job = label.after(16, lambda tw=w: apply_wrap(tw))

    label.bind("<Configure>", on_configure, add="+")
    return label


_ButtonBase = ctk.CTkButton if HAS_CTK else tk.Label


class FlatButton(_ButtonBase):
    """Rounded Obsidian button with semantic variants: normal | primary | danger | ghost | active | rec | warn | blue."""
    STYLES = {}
    BORDERS = {}

    @classmethod
    def rebuild_styles(cls):
        accent_active = lerp_color(T.SURFACE, T.ACCENT, 0.22)
        accent_hover = lerp_color(T.SURFACE, T.ACCENT, 0.34)
        if T.IS_MONO:
            cls.STYLES = {
                "normal": (T.SURFACE2, T.SURFACE3, T.TEXT),
                "primary": (T.ACCENT, T.ACCENT_HI, T.ACCENT_FG),
                "danger": ("#272B33", "#363B46", "#E5E7EB"),
                "ghost": (T.SURFACE, T.SURFACE2, T.MUTED),
                "active": (accent_active, accent_hover, T.ACCENT_HI),
                "rec": (T.BAD, "#F8FAFC", "#0D0F14"),
                "warn": ("#22262E", "#303540", T.WARN),
                "blue": ("#1E222A", "#2C323E", "#CBD5E1"),
            }
            cls.BORDERS = {
                "normal": T.BORDER,
                "primary": T.ACCENT,
                "danger": "#4B5262",
                "ghost": T.BORDER,
                "active": T.ACCENT,
                "rec": T.BAD,
                "warn": "#464C5B",
                "blue": T.BLUE,
            }
        elif T.SOFT_COLORS:
            cls.STYLES = {
                "normal": (T.SURFACE2, T.SURFACE3, T.TEXT),
                "primary": (T.ACCENT, T.ACCENT_HI, T.ACCENT_FG),
                "danger": ("#351820", "#4A222D", "#F0A8B4"),
                "ghost": (T.SURFACE, T.SURFACE2, T.MUTED),
                "active": (accent_active, accent_hover, T.ACCENT_HI),
                "rec": (T.BAD, "#E899A8", "#22060C"),
                "warn": ("#36270B", "#4A3510", T.WARN),
                "blue": ("#162336", "#20334E", "#96B7E0"),
            }
            cls.BORDERS = {
                "normal": T.BORDER,
                "primary": T.ACCENT,
                "danger": "#632A38",
                "ghost": T.BORDER,
                "active": T.ACCENT,
                "rec": T.BAD,
                "warn": "#6E4F18",
                "blue": T.BLUE,
            }
        else:
            cls.STYLES = {
                "normal": (T.SURFACE2, T.SURFACE3, T.TEXT),
                "primary": (T.ACCENT, T.ACCENT_HI, T.ACCENT_FG),
                "danger": ("#381620", "#4E1E2B", "#F5A5B2"),
                "ghost": (T.SURFACE, T.SURFACE2, T.MUTED),
                "active": (accent_active, accent_hover, T.ACCENT_HI),
                "rec": (T.BAD, "#EC9AA9", "#26050B"),
                "warn": ("#382809", "#4E370E", T.WARN),
                "blue": ("#152236", "#1E314D", "#91BBF2"),
            }
            cls.BORDERS = {
                "normal": T.BORDER,
                "primary": T.ACCENT,
                "danger": "#682436",
                "ghost": T.BORDER,
                "active": T.ACCENT,
                "rec": T.BAD,
                "warn": "#725014",
                "blue": T.BLUE,
            }

    def __init__(self, master, text="", command=None, style="normal", padx=12, pady=6, size=10, weight="normal", corner=7, **kw):
        self.style_name = style
        self.command = command
        self._enabled = True
        self._down = False
        bg, hover, fg = self.STYLES[style]
        border_col = self.BORDERS.get(style, T.BORDER)
        if HAS_CTK:
            lines = max(1, str(text).count("\n") + 1)
            h_px = dp(max(24, int(size * 1.9 * lines + pady * 1.6)))
            min_w = dp(max(24, int(padx * 2))) if padx else 0
            bw = 0 if style == "primary" else 1
            super().__init__(
                master,
                text=text,
                command=self._invoke,
                fg_color=bg,
                hover_color=hover,
                text_color=fg,
                text_color_disabled=T.DIM,
                border_color=border_col,
                border_width=bw,
                corner_radius=dp(corner),
                height=h_px,
                width=min_w,
                font=font(size, weight),
                cursor="hand2",
                **kw,
            )
        else:
            super().__init__(master, text=text, bg=bg, fg=fg, font=font(size, weight), padx=dp(padx), pady=dp(pady),
                             cursor="hand2", **kw)
            self.bind("<Enter>", self._tk_enter)
            self.bind("<Leave>", self._tk_leave)
            self.bind("<ButtonPress-1>", self._tk_press)
            self.bind("<ButtonRelease-1>", self._tk_release)

    def _invoke(self):
        if self._enabled and self.command:
            self.command()

    def _colors(self):
        return self.STYLES[self.style_name]

    def _tk_enter(self, _e=None):
        if not HAS_CTK and self._enabled:
            self.configure(bg=self._colors()[1])

    def _tk_leave(self, _e=None):
        self._down = False
        if not HAS_CTK:
            self.configure(bg=self._colors()[0])

    def _tk_press(self, _e=None):
        self._down = True

    def _tk_release(self, e):
        was = self._down
        self._down = False
        if not HAS_CTK and self._enabled and was and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            if self.command:
                self.command()

    def refresh_theme(self):
        old = self.style_name
        self.style_name = None
        self.set_style(old)
        if not self._enabled:
            self.set_enabled(False)

    def set_style(self, style):
        if style != self.style_name:
            self.style_name = style
            bg, hover, fg = self._colors()
            if HAS_CTK:
                bcol = self.BORDERS.get(style, T.BORDER)
                bw = 0 if style == "primary" else 1
                self.configure(fg_color=bg, hover_color=hover, text_color=fg if self._enabled else T.DIM,
                               text_color_disabled=T.DIM, border_color=bcol, border_width=bw)
            else:
                self.configure(bg=bg, fg=fg if self._enabled else T.DIM)

    def set_text(self, text):
        if self.cget("text") != text:
            self.configure(text=text)

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        bg, hover, fg = self._colors()
        if HAS_CTK:
            self.configure(state="normal" if enabled else "disabled",
                           fg_color=bg, hover_color=hover, text_color=fg if enabled else T.DIM)
            try:
                self.configure(cursor="hand2" if enabled else "arrow")
            except Exception:
                pass
        else:
            self.configure(bg=bg, fg=fg if enabled else T.DIM, cursor="hand2" if enabled else "arrow")


_ToggleBase = tk.Canvas


class Toggle(_ToggleBase):
    """Canvas pill switch (consistent across Windows & Linux). set() never fires command; user clicks do."""

    def __init__(self, master, value=False, command=None, bg=None):
        self.value = bool(value)
        self.command = command
        self._enabled = True
        self._hovering = False
        self._bg = bg or bg_of(master)
        self._paint_key = None
        self.w, self.h = dp(44), dp(24)
        super().__init__(master, width=self.w, height=self.h, bg=self._bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.bind("<Configure>", lambda _e: self._paint())
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self.bind("<Button-1>", self._click)
        self.bind("<space>", self._click)
        self.bind("<Return>", self._click)
        self._paint()

    def _set_hover(self, flag):
        flag = bool(flag)
        if flag == self._hovering:
            return
        self._hovering = flag
        self._paint()

    def _paint(self):
        w, h = self.w, self.h
        on = self.value
        key = (w, h, on, self._enabled, self._hovering, self._bg,
               T.ACCENT, T.ACCENT_HI, T.SURFACE2, T.SURFACE3, T.BORDER, T.BORDER_HI, T.TEXT, T.DIM)
        if key == self._paint_key:
            return
        self._paint_key = key
        self.delete("all")

        pad = dp(1)
        x0, y0, x1, y1 = pad, pad, w - pad, h - pad
        d = max(4, y1 - y0)
        r = d / 2.0

        if not self._enabled:
            track = T.SURFACE2
            border = T.BORDER
            knob = T.DIM
        elif on:
            track = T.ACCENT_HI if self._hovering else T.ACCENT
            border = track
            knob = "#ffffff" if self._hovering else T.TEXT
        else:
            track = T.SURFACE3
            border = T.BORDER_HI if self._hovering else T.BORDER
            knob = "#ffffff" if self._hovering else T.TEXT

        # Border pill + inset track pill (sharp at every Windows/Linux DPI)
        self.create_oval(x0, y0, x0 + d, y1, fill=border, outline="")
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=border, outline="")
        self.create_oval(x1 - d, y0, x1, y1, fill=border, outline="")

        inset = 1
        id_ = max(2, d - 2 * inset)
        ir = id_ / 2.0
        self.create_oval(x0 + inset, y0 + inset, x0 + inset + id_, y1 - inset, fill=track, outline="")
        self.create_rectangle(x0 + inset + ir, y0 + inset, x1 - inset - ir, y1 - inset, fill=track, outline="")
        self.create_oval(x1 - inset - id_, y0 + inset, x1 - inset, y1 - inset, fill=track, outline="")

        # Thumb knob
        cy = h / 2.0
        kr = max(3.0, r - dp(3))
        kx = (x1 - r) if on else (x0 + r)
        self.create_oval(kx - kr, cy - kr, kx + kr, cy + kr, fill=knob, outline="")

    def _click(self, _e=None):
        if not self._enabled:
            return
        try:
            self.focus_set()
        except Exception:
            pass
        self.value = not self.value
        self._paint_key = None
        self._paint()
        if self.command:
            self.command(self.value)

    def set(self, value, notify=False):
        value = bool(value)
        if value != self.value:
            self.value = value
            self._paint_key = None
            self._paint()
        if notify and self.command:
            self.command(self.value)

    def get(self):
        return self.value

    def set_enabled(self, enabled):
        flag = bool(enabled)
        if flag == self._enabled:
            return
        self._enabled = flag
        self.configure(cursor="hand2" if flag else "arrow")
        self._paint_key = None
        self._paint()

    def refresh_theme(self, bg=None):
        if bg:
            self._bg = bg
            self.configure(bg=bg)
        self._paint_key = None
        self._paint()


class Slider(tk.Canvas):
    """Precision horizontal slider with bipolar origin, log scale, mousewheel & double-click reset."""

    def __init__(self, master, from_=0.0, to=1.0, value=0.0, step=0.01, default=None, origin=None, command=None,
                 bg=None, accent=None, log=False):
        super().__init__(master, width=dp(100), height=dp(26), bg=bg or bg_of(master), highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.lo, self.hi, self.step = float(from_), float(to), float(step)
        self.log = bool(log)
        self.default = default if default is not None else value
        self.origin = origin
        self.command = command
        self.accent = accent or T.ACCENT
        self.value = self._clamp(value)
        self._enabled = True
        self._hovering = False
        self._draw_key = None
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", self._down)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Double-Button-1>", self._reset)
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda e: self._nudge(1))
        self.bind("<Button-5>", lambda e: self._nudge(-1))
        self.bind("<Left>", lambda e: self._nudge(-1))
        self.bind("<Right>", lambda e: self._nudge(1))

    def _set_hover(self, flag):
        if flag == self._hovering:
            return
        self._hovering = flag
        self._draw()

    def _clamp(self, v):
        v = min(self.hi, max(self.lo, float(v)))
        if self.log:
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
        pad = dp(10)
        return pad, max(pad + 1, self.winfo_width() - pad)

    def _x_of(self, v):
        x0, x1 = self._geom()
        return x0 + self._frac(v) * (x1 - x0)

    def _draw(self):
        w = self.winfo_width() or dp(100)
        h = self.winfo_height() or dp(26)
        key = (w, h, round(self.value, 6), self._enabled, self._hovering, self.accent, T.SURFACE3, T.TEXT, T.BORDER_HI)
        if key == self._draw_key:
            return
        self._draw_key = key
        self.delete("all")
        cy = h / 2
        x0, x1 = self._geom()
        acc = self.accent if self._enabled else T.DIM
        # Outer obsidian track groove
        self.create_line(x0, cy, x1, cy, width=dp(5), capstyle="round", fill=T.SURFACE3)
        xv = self._x_of(self.value)
        xo = self._x_of(self.origin) if self.origin is not None else x0
        if abs(xv - xo) > 0.5:
            self.create_line(xo, cy, xv, cy, width=dp(5), capstyle="round", fill=acc)
        if self.origin is not None:
            self.create_line(xo, cy - dp(6), xo, cy + dp(6), width=1, fill=T.BORDER_HI)
        if self._hovering and self._enabled:
            hr = dp(10)
            self.create_oval(xv - hr, cy - hr, xv + hr, cy + hr, fill=lerp_color(T.SURFACE, acc, 0.25), outline="")
        r = dp(7)
        self.create_oval(xv - r, cy - r, xv + r, cy + r, fill=T.TEXT if self._enabled else T.MUTED,
                         outline=acc, width=dp(2))

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
        except Exception:
            focused = False
        if self._enabled and focused:
            self._nudge(1 if e.delta > 0 else -1)
            return "break"

    def _nudge(self, direction):
        if not self._enabled:
            return
        if self.log:
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
        bg = bg or bg_of(master)
        super().__init__(master, bg=bg)
        self.fmt = fmt or (lambda v: f"{v:g}")
        self.user_command = command
        top = tk.Frame(self, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=bg, fg=T.TEXT, font=font(10)).pack(side="left")
        self.value_label = tk.Label(top, text="", bg=bg, fg=T.ACCENT_HI, font=font(10, "bold", True))
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
        bg = bg or bg_of(master)
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


_FrameBase = ctk.CTkFrame if HAS_CTK else tk.Frame
_EntryBase = ctk.CTkEntry if HAS_CTK else tk.Entry
_ProgressBase = ctk.CTkProgressBar if HAS_CTK else tk.Canvas


class _SegProxy:
    """Lightweight per-option button view exposed via Segmented.buttons when backed by CTkSegmentedButton."""

    def __init__(self, seg, key):
        self._seg = seg
        self._key = key

    @property
    def _enabled(self):
        return self._seg._enabled

    def set_enabled(self, enabled):
        self._seg.set_enabled(enabled)


class Segmented(_FrameBase):
    """Rounded pill segmented control backed by CTkSegmentedButton (with FlatButton fallback)."""

    def __init__(self, master, options, value=None, command=None, bg=None, size=9, padx=9, pady=3):
        self.command = command
        self.value = value
        self._enabled = True
        self._pairs = [(k, str(t)) for k, t in options]
        self._k2l = {k: lab for k, lab in self._pairs}
        self._l2k = {lab: k for k, lab in self._pairs}
        self._bg = bg or bg_of(master)
        self.buttons = {}
        self._seg = None
        if HAS_CTK:
            super().__init__(master, fg_color=self._bg, corner_radius=0, border_width=0, width=10, height=10)
            labels = [lab for _, lab in self._pairs] or [""]
            h_px = dp(28 if size <= 9 else 32)
            sel_bg = lerp_color(T.SURFACE2, T.ACCENT, 0.28)
            sel_hv = lerp_color(T.SURFACE2, T.ACCENT, 0.38)
            self._seg = ctk.CTkSegmentedButton(
                self,
                values=labels,
                command=self._ctk_pick,
                height=h_px,
                corner_radius=dp(8),
                border_width=dp(3),
                fg_color=T.SURFACE2,
                selected_color=sel_bg,
                selected_hover_color=sel_hv,
                unselected_color=T.SURFACE2,
                unselected_hover_color=T.SURFACE3,
                text_color=T.TEXT,
                text_color_disabled=T.DIM,
                font=font(size, "bold"),
            )
            self._seg.pack(fill="both", expand=True)
            for k, _ in self._pairs:
                self.buttons[k] = _SegProxy(self, k)
            if self.value in self._k2l:
                self._seg.set(self._k2l[self.value])
        else:
            super().__init__(master, bg=self._bg)
            for i, (key, text) in enumerate(self._pairs):
                init_style = "active" if key == self.value else "normal"
                b = FlatButton(self, text, command=lambda k=key: self._pick(k), style=init_style,
                               padx=padx, pady=pady, size=size, corner=6)
                b.pack(side="left", padx=(0 if i == 0 else dp(2), 0))
                self.buttons[key] = b

    def _ctk_pick(self, label):
        if not self._enabled:
            if self._seg is not None and self.value in self._k2l:
                self._seg.set(self._k2l[self.value])
            return
        key = self._l2k.get(label)
        if key is not None and key != self.value:
            self.value = key
            if self.command:
                self.command(key)

    def _paint(self):
        if HAS_CTK:
            if self._seg is not None and self.value in self._k2l:
                self._seg.set(self._k2l[self.value])
        else:
            for k, b in self.buttons.items():
                b.set_style("active" if k == self.value else "normal")

    def _pick(self, key):
        if not self._enabled:
            return
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

    def set_enabled(self, enabled):
        flag = bool(enabled)
        self._enabled = flag
        if HAS_CTK and self._seg is not None:
            try:
                self._seg.configure(state="normal" if flag else "disabled")
            except Exception:
                pass
            if hasattr(self._seg, "_buttons_dict"):
                for b in self._seg._buttons_dict.values():
                    try:
                        b.configure(state="normal" if flag else "disabled")
                    except Exception:
                        pass
                    try:
                        b.configure(cursor="hand2" if flag else "arrow")
                    except Exception:
                        pass
        else:
            for b in self.buttons.values():
                b.set_enabled(flag)

    def refresh_theme(self, bg=None):
        if bg:
            self._bg = bg
        if HAS_CTK and self._seg is not None:
            self.configure(fg_color=self._bg)
            sel_bg = lerp_color(T.SURFACE2, T.ACCENT, 0.28)
            sel_hv = lerp_color(T.SURFACE2, T.ACCENT, 0.38)
            self._seg.configure(
                fg_color=T.SURFACE2,
                selected_color=sel_bg,
                selected_hover_color=sel_hv,
                unselected_color=T.SURFACE2,
                unselected_hover_color=T.SURFACE3,
                text_color=T.TEXT,
                text_color_disabled=T.DIM,
            )
            self._paint()
        else:
            self.configure(bg=bg or bg_of(self.master))
            for b in self.buttons.values():
                b.refresh_theme()


class TextInput(_EntryBase):
    """Rounded Obsidian single-line text input backed by CTkEntry (with tk.Entry fallback)."""

    def __init__(self, master, textvariable=None, width=20, placeholder="", size=10, weight="normal",
                 display=False, justify="left", show_border=True, bg=None):
        self._bg = bg or T.SURFACE2
        self._show_border = bool(show_border)
        self._enabled = True
        self._custom_text_color = None
        if HAS_CTK:
            px_w = dp(max(52, int(width * 8.5)))
            super().__init__(
                master,
                textvariable=textvariable,
                width=px_w,
                height=dp(30),
                corner_radius=dp(8 if self._show_border else 0),
                border_width=1 if self._show_border else 0,
                fg_color=self._bg,
                border_color=T.BORDER,
                text_color=T.TEXT,
                placeholder_text=placeholder or None,
                placeholder_text_color=T.DIM,
                font=font(size, weight, display),
                justify=justify,
            )
        else:
            super().__init__(
                master,
                textvariable=textvariable,
                width=width,
                bg=self._bg,
                fg=T.TEXT,
                insertbackground=T.ACCENT_HI,
                relief="flat",
                font=font(size, weight, display),
                justify=justify,
                highlightthickness=1 if self._show_border else 0,
                highlightbackground=T.BORDER,
                highlightcolor=T.ACCENT,
                bd=0,
            )

    def set_text_color(self, color):
        self._custom_text_color = color
        if HAS_CTK:
            self.configure(text_color=color)
        else:
            self.configure(fg=color)

    def set_border_color(self, color):
        if HAS_CTK:
            self.configure(border_color=color)
        elif self._show_border:
            self.configure(highlightbackground=color)

    def select_all(self):
        target = getattr(self, "_entry", self)
        try:
            target.select_range(0, "end")
            target.icursor("end")
        except Exception:
            pass

    def set_enabled(self, enabled):
        flag = bool(enabled)
        self._enabled = flag
        self.configure(state="normal" if flag else "disabled")
        self.set_text_color((self._custom_text_color or T.TEXT) if flag else T.DIM)

    def refresh_theme(self, bg=None):
        if bg:
            self._bg = bg
        fg = (self._custom_text_color or T.TEXT) if self._enabled else T.DIM
        if HAS_CTK:
            self.configure(fg_color=self._bg, border_color=T.BORDER, text_color=fg, placeholder_text_color=T.DIM)
        else:
            self.configure(bg=self._bg, fg=fg, insertbackground=T.ACCENT_HI)
            if self._show_border:
                self.configure(highlightbackground=T.BORDER, highlightcolor=T.ACCENT)


class ProgressBar(_ProgressBase):
    """Slim rounded progress bar backed by CTkProgressBar (with Canvas fallback)."""

    def __init__(self, master, height=4, color=None, bg=None, corner=2):
        self._color = color or T.ACCENT
        self._bg = bg or T.SURFACE3
        self._frac = 0.0
        self._fill = None
        if HAS_CTK:
            super().__init__(
                master,
                width=dp(60),
                height=max(2, dp(height)),
                corner_radius=dp(corner),
                border_width=0,
                fg_color=self._bg,
                progress_color=self._color,
            )
            super().set(0.0)
        else:
            super().__init__(master, height=max(2, dp(height)), bg=self._bg, highlightthickness=0, bd=0)
            self.bind("<Configure>", lambda _e: self._paint_fallback())

    def _paint_fallback(self):
        w = self.winfo_width()
        if w < 8:
            return
        h = max(2, self.winfo_height() or dp(3))
        if self._fill is None:
            self._fill = self.create_rectangle(0, 0, w * self._frac, h, fill=self._color, outline="")
        else:
            self.coords(self._fill, 0, 0, w * self._frac, h)
            self.itemconfigure(self._fill, fill=self._color)

    def set_progress(self, frac, color=None):
        f = min(1.0, max(0.0, float(frac)))
        color_changed = bool(color and color != self._color)
        if color:
            self._color = color
        self._frac = f
        if HAS_CTK:
            if color_changed:
                self.configure(progress_color=self._color)
            super().set(f)
        else:
            self._paint_fallback()

    def refresh_theme(self, color=None, bg=None):
        if color:
            self._color = color
        if bg:
            self._bg = bg
        if HAS_CTK:
            self.configure(fg_color=self._bg, progress_color=self._color)
        else:
            self.configure(bg=self._bg)
            self._paint_fallback()


class SurfaceBox(_FrameBase):
    """Rounded Obsidian container panel with 1px border (CTkFrame with tk.Frame fallback)."""

    def __init__(self, master, bg=None, border=None, corner=8, **kw):
        self._box_bg = bg or T.SURFACE2
        self._box_border = border or T.BORDER
        if HAS_CTK:
            super().__init__(master, fg_color=self._box_bg, corner_radius=dp(corner),
                             border_width=1, border_color=self._box_border, **kw)
        else:
            super().__init__(master, bg=self._box_bg, highlightthickness=1,
                             highlightbackground=self._box_border, highlightcolor=self._box_border, bd=0, **kw)

    def refresh_theme(self, bg=None, border=None):
        if bg:
            self._box_bg = bg
        if border:
            self._box_border = border
        if HAS_CTK:
            self.configure(fg_color=self._box_bg, border_color=self._box_border)
        else:
            self.configure(bg=self._box_bg, highlightbackground=self._box_border)


class PillBadge(_FrameBase):
    """Compact rounded status badge pill."""

    def __init__(self, master, text="", fg=None, bg=None, border=None, size=8, bold=True,
                 display=False, padx=8, pady=2, corner=7, width=None):
        self._badge_fg = fg or T.TEXT
        self._badge_bg = bg or T.SURFACE2
        self._badge_border = border or T.BORDER
        if HAS_CTK:
            super().__init__(master, fg_color=self._badge_bg, corner_radius=dp(corner),
                             border_width=1, border_color=self._badge_border)
        else:
            super().__init__(master, bg=self._badge_bg, highlightthickness=1,
                             highlightbackground=self._badge_border, bd=0)
        lbl_kw = {"width": width} if width is not None else {}
        self._label = tk.Label(self, text=text, bg=self._badge_bg, fg=self._badge_fg,
                               font=font(size, "bold" if bold else "normal", display), **lbl_kw)
        self._label.pack(padx=dp(padx), pady=dp(pady))

    def set_badge(self, text, fg=None, bg=None, border=None):
        if fg:
            self._badge_fg = fg
        if bg:
            self._badge_bg = bg
        if border:
            self._badge_border = border
        if HAS_CTK:
            self.configure(fg_color=self._badge_bg, border_color=self._badge_border)
        else:
            self.configure(bg=self._badge_bg, highlightbackground=self._badge_border)
        self._label.configure(text=text, fg=self._badge_fg, bg=self._badge_bg)

    def refresh_theme(self, fg=None, bg=None, border=None):
        self.set_badge(self._label.cget("text"), fg=fg, bg=bg, border=border)


_ComboBase = ctk.CTkOptionMenu if HAS_CTK else ttk.Combobox


class Combo(_ComboBase):
    """Rounded dark dropdown menu."""

    def __init__(self, master, values=(), width=36, command=None):
        self.command = command
        self._items = list(values)
        if HAS_CTK:
            px_w = dp(max(130, min(420, int(width * 8.2))))
            init_vals = self._items if self._items else [""]
            super().__init__(
                master,
                values=init_vals,
                width=px_w,
                height=dp(30),
                corner_radius=dp(8),
                fg_color=T.SURFACE2,
                button_color=T.SURFACE3,
                button_hover_color=T.BORDER_HI,
                dropdown_fg_color=T.SURFACE,
                dropdown_hover_color=T.SURFACE3,
                dropdown_text_color=T.TEXT,
                text_color=T.TEXT,
                text_color_disabled=T.DIM,
                font=font(10),
                dropdown_font=font(10),
                command=self._ctk_selected,
            )
            if not self._items:
                super().set("")
        else:
            super().__init__(master, values=self._items, state="readonly", width=width, style="PM.TCombobox",
                             exportselection=False, font=font(10))
            self.bind("<<ComboboxSelected>>", self._selected)

    def _ctk_selected(self, choice):
        if self.command and choice in self._items:
            self.command(choice)

    def _selected(self, _e=None):
        self.selection_clear()
        if self.command:
            self.command(self.get())

    def set_values(self, values, current=None):
        self._items = [str(v) for v in values if v is not None]
        if HAS_CTK:
            self.configure(values=self._items if self._items else [""])
            if current is not None:
                super().set(str(current))
            elif self._items:
                if super().get() not in self._items:
                    super().set(self._items[0])
            else:
                super().set("")
        else:
            self.configure(values=self._items)
            if current is not None:
                self.set(str(current))

    def set_enabled(self, enabled):
        flag = bool(enabled)
        if HAS_CTK:
            self.configure(state="normal" if flag else "disabled")
        else:
            self.configure(state="readonly" if flag else "disabled")


class Card(_FrameBase):
    """Obsidian card panel with crisp 1px border, rounded corners, `.header`, and `.body`."""

    def __init__(self, master, title=None, subtitle=None, pad=16, bg=None, accent_border=None, **kw):
        card_bg = bg or T.SURFACE
        border_col = accent_border or T.BORDER
        if HAS_CTK:
            super().__init__(master, fg_color=card_bg, corner_radius=dp(10), border_width=1, border_color=border_col, **kw)
        else:
            super().__init__(master, bg=card_bg, highlightthickness=1, highlightbackground=border_col,
                             highlightcolor=border_col, bd=0, **kw)
        self.card_bg = card_bg
        self.header = None
        safe_pad = max(pad, 10)
        if title:
            self.header = tk.Frame(self, bg=card_bg)
            self.header.pack(fill="x", padx=dp(safe_pad), pady=(dp(max(10, safe_pad - 2)), 0))
            tk.Label(self.header, text=title, bg=card_bg, fg=T.TEXT, font=font(11, "bold")).pack(side="left")
            if subtitle:
                tk.Label(self.header, text=subtitle, bg=card_bg, fg=T.DIM, font=font(9)).pack(side="left", padx=(dp(8), 0))
        self.body = tk.Frame(self, bg=card_bg)
        self.body.pack(fill="both", expand=True, padx=dp(safe_pad), pady=(dp(8) if title else dp(safe_pad), dp(safe_pad)))


class StatTile(_FrameBase):
    """Compact metric readout tile with obsidian border and semantic accent bar."""

    def __init__(self, master, label, hint="", accent=None):
        if HAS_CTK:
            super().__init__(master, fg_color=T.SURFACE, corner_radius=dp(8), border_width=1, border_color=T.BORDER)
        else:
            super().__init__(master, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER, bd=0)
        self._last = None
        head = tk.Frame(self, bg=T.SURFACE)
        head.pack(fill="x", padx=dp(12), pady=(dp(9), 0))
        self.dot = tk.Label(head, text="\u25cf", bg=T.SURFACE, fg=accent or T.ACCENT, font=font(8))
        self.dot.pack(side="left", padx=(0, dp(5)))
        tk.Label(head, text=label, bg=T.SURFACE, fg=T.DIM, font=font(9), anchor="w").pack(side="left", fill="x")
        self.value = tk.Label(self, text="-", bg=T.SURFACE, fg=T.TEXT, font=font(17, "bold", True), anchor="w")
        self.value.pack(fill="x", padx=dp(12))
        self.sub = tk.Label(self, text=hint, bg=T.SURFACE, fg=T.DIM, font=font(8), anchor="w")
        self.sub.pack(fill="x", padx=dp(12), pady=(0, dp(9)))

    def set(self, text, color=None, sub=None):
        c = color or T.TEXT
        key = (text, c, sub)
        if key == self._last:
            return
        self._last = key
        self.value.configure(text=text, fg=c)
        if color:
            self.dot.configure(fg=color)
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
        self._attach(widget)

    def _attach(self, widget):
        src = getattr(widget, "_seg", widget)
        targets = (
            list(src._buttons_dict.values())
            if hasattr(src, "_buttons_dict") and isinstance(src._buttons_dict, dict)
            else [widget]
        )
        for t in targets:
            try:
                t.bind("<Enter>", self._schedule, add="+")
                t.bind("<Leave>", self._hide, add="+")
                t.bind("<ButtonPress>", self._hide, add="+")
                t.bind("<Unmap>", self._hide, add="+")
                t.bind("<Destroy>", self._hide, add="+")
            except NotImplementedError:
                for child in t.winfo_children():
                    try:
                        child.bind("<Enter>", self._schedule, add="+")
                        child.bind("<Leave>", self._hide, add="+")
                        child.bind("<ButtonPress>", self._hide, add="+")
                        child.bind("<Unmap>", self._hide, add="+")
                        child.bind("<Destroy>", self._hide, add="+")
                    except Exception:
                        pass
            except Exception:
                pass
        if src is not widget:
            try:
                widget.bind("<Unmap>", self._hide, add="+")
                widget.bind("<Destroy>", self._hide, add="+")
            except Exception:
                pass

    def _schedule(self, _e=None):
        self._hide()
        self._job = self.widget.after(self.delay, self._show)

    def _show(self):
        try:
            if not self.widget.winfo_exists():
                return
            x = self.widget.winfo_rootx() + dp(10)
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + dp(4)
            self._tip = tk.Toplevel(self.widget)
            self._tip.wm_overrideredirect(True)
            tk.Label(self._tip, text=self.text, bg=T.SURFACE2, fg=T.TEXT, font=font(9), padx=dp(10), pady=dp(6),
                     justify="left", wraplength=dp(320), highlightthickness=1, highlightbackground=T.BORDER_HI).pack()
            self._tip.update_idletasks()
            vx, vy, vw, vh = screen_bounds(self._tip)
            tw = self._tip.winfo_reqwidth()
            th = self._tip.winfo_reqheight()
            x = max(vx + dp(6), min(x, vx + vw - tw - dp(8)))
            if y + th > vy + vh - dp(8):
                y = max(vy + dp(6), self.widget.winfo_rooty() - th - dp(4))
            else:
                y = max(vy + dp(6), y)
            self._tip.wm_geometry(f"+{x}+{y}")
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
# SCROLLING (High-FPS Obsidian Canvas Viewport + Slim Thumb Scrollbar)
# ==============================================================================
class _DarkScrollbar(tk.Canvas):
    """Slim obsidian pill scrollbar with smooth click-drag and hover feedback."""

    def __init__(self, master, command, bg=None):
        self._bg = bg or T.BG
        super().__init__(master, width=dp(10), bg=self._bg, highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self._first = 0.0
        self._last = 1.0
        self._hover = False
        self._drag_y = None
        self._drag_first = 0.0
        self._paint_key = None
        self.bind("<Configure>", lambda e: self._paint())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag_y", None))

    def _set_hover(self, flag):
        if flag == self._hover:
            return
        self._hover = flag
        self._paint()

    def set(self, first, last):
        f, l = float(first), float(last)
        if abs(f - self._first) < 1e-4 and abs(l - self._last) < 1e-4:
            return
        self._first, self._last = f, l
        self._paint()

    def _paint(self):
        w, h = self.winfo_width(), self.winfo_height()
        hidden = w < 2 or h < 10 or self._last - self._first >= 0.999
        col = T.BORDER_HI if (self._hover or self._drag_y is not None) else T.SURFACE3
        key = ("hidden", w, h, self._bg) if hidden else (w, h, round(self._first, 4), round(self._last, 4), col, self._bg)
        if key == self._paint_key:
            return
        self._paint_key = key
        self.delete("all")
        if hidden:
            return
        pad_x = dp(2)
        y0 = max(dp(3), self._first * h)
        y1 = min(h - dp(3), max(y0 + dp(28), self._last * h))
        r = max(2, (w - 2 * pad_x) / 2.0)
        self.create_line(w / 2.0, y0 + r, w / 2.0, y1 - r, width=max(2, w - 2 * pad_x), capstyle="round", fill=col)

    def _press(self, e):
        h = max(1, self.winfo_height())
        y0, y1 = self._first * h, self._last * h
        if y0 <= e.y <= y1:
            self._drag_y = e.y
            self._drag_first = self._first
        else:
            span = self._last - self._first
            target = max(0.0, min(1.0 - span, e.y / h - span / 2.0))
            self.command("moveto", target)

    def _drag(self, e):
        if self._drag_y is None:
            return
        h = max(1, self.winfo_height())
        delta = (e.y - self._drag_y) / h
        span = self._last - self._first
        target = max(0.0, min(1.0 - span, self._drag_first + delta))
        self.command("moveto", target)


class ScrollFrame(tk.Frame):
    """Fast native-Canvas scrollable viewport with crisp dark scrollbar and instant wheel scrolling."""

    def __init__(self, master, bg=None):
        bg = bg or T.BG
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, yscrollincrement=dp(20))
        self.vsb = _DarkScrollbar(self, self.canvas.yview, bg=bg)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._last_win_w = None
        self._last_bbox = None
        self._scroll_job = None
        self.inner.bind("<Configure>", self._inner_changed)
        self.canvas.bind("<Configure>", self._canvas_changed)

    def _flush_scrollregion(self):
        self._scroll_job = None
        try:
            if not self.winfo_exists():
                return
            bbox = self.canvas.bbox("all")
            if bbox != self._last_bbox:
                self._last_bbox = bbox
                self.canvas.configure(scrollregion=bbox)
        except Exception:
            pass

    def _inner_changed(self, _e=None):
        if self._last_bbox is None:
            self._flush_scrollregion()
        elif self._scroll_job is None:
            self._scroll_job = self.after(16, self._flush_scrollregion)

    def refresh_theme(self, bg=None):
        c = bg or T.BG
        self.configure(bg=c)
        self.canvas.configure(bg=c)
        self.inner.configure(bg=c)
        self.vsb._bg = c
        self.vsb._paint_key = None
        self.vsb.configure(bg=c)
        self.vsb._paint()

    def _canvas_changed(self, e):
        if e.width >= 20 and e.width != self._last_win_w and self.winfo_exists():
            self._last_win_w = e.width
            self.canvas.itemconfigure(self._win, width=e.width)

    def scroll_to(self, widget):
        """Bring a widget inside `.inner` into view."""
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
        """Scroll smoothly when content overflows the viewport."""
        try:
            if self.inner.winfo_reqheight() > self.canvas.winfo_height():
                self.canvas.yview_scroll(units, "units")
        except Exception:
            pass


class ScrollTextBox(SurfaceBox):
    """Rounded Obsidian container wrapping a tk.Text widget with a slim dark scrollbar."""

    def __init__(self, master, height=10, text_font=None, bg=None, wrap="none", **text_kw):
        box_bg = bg or T.SIDEBAR
        super().__init__(master, bg=box_bg, border=T.BORDER, corner=8)
        self.vsb = _DarkScrollbar(self, self._scroll, bg=box_bg)
        self.vsb.pack(side="right", fill="y", padx=(0, dp(3)), pady=dp(4))
        self.textbox = tk.Text(
            self,
            height=height,
            bg=box_bg,
            fg=T.TEXT,
            relief="flat",
            font=text_font or (MONO_FONT, 9),
            wrap=wrap,
            highlightthickness=0,
            bd=0,
            padx=dp(10),
            pady=dp(8),
            yscrollcommand=self.vsb.set,
            **text_kw,
        )
        self.textbox.pack(side="left", fill="both", expand=True, padx=(dp(4), 0), pady=dp(4))

    def _scroll(self, *args):
        self.textbox.yview(*args)


# ==============================================================================
# VECTOR ICONS & SIDEBAR NAV
# ==============================================================================
def draw_icon(c, name, color, size):
    k = size / 20.0
    w = max(1, int(round(1.6 * k)))
    c.delete("all")
    if name == "dashboard":
        # Modern asymmetric bento dashboard icon
        c.create_rectangle(2.5 * k, 2.5 * k, 8.8 * k, 17.5 * k, outline=color, width=w)
        c.create_rectangle(11.2 * k, 2.5 * k, 17.5 * k, 9.0 * k, outline=color, width=w)
        c.create_rectangle(11.2 * k, 11.2 * k, 17.5 * k, 17.5 * k, outline=color, width=w)
        c.create_oval(4.7 * k, 13.3 * k, 6.7 * k, 15.3 * k, fill=color, outline="")
    elif name == "sound":
        # 3-fader precision studio mixer with ringed slider caps
        for x, ky in ((4.5, 6.8), (10.0, 13.2), (15.5, 8.5)):
            c.create_line(x * k, 2.8 * k, x * k, 17.2 * k, fill=color, width=w, capstyle="round")
            c.create_rectangle((x - 2.2) * k, (ky - 1.5) * k, (x + 2.2) * k, (ky + 1.5) * k,
                               fill=color, outline=color)
    elif name == "voice":
        for x, h in ((3, 4), (6.5, 10), (10, 16), (13.5, 9), (17, 5)):
            c.create_line(x * k, (10 - h / 2) * k, x * k, (10 + h / 2) * k, fill=color, width=w + 1, capstyle="round")
    elif name == "devices":
        # Clean wireless broadcast link icon
        c.create_oval(8.0 * k, 12.6 * k, 12.0 * k, 16.6 * k, outline=color, width=w)
        c.create_arc(4.8 * k, 7.6 * k, 15.2 * k, 18.0 * k, start=38, extent=104, style="arc", outline=color, width=w)
        c.create_arc(1.8 * k, 3.6 * k, 18.2 * k, 20.0 * k, start=42, extent=96, style="arc", outline=color, width=w)
        c.create_line(10 * k, 16.6 * k, 10 * k, 18.4 * k, fill=color, width=w, capstyle="round")
    elif name == "network":
        for r in (4, 8, 12):
            c.create_arc((10 - r) * k, (16 - r) * k, (10 + r) * k, (16 + r) * k, start=50, extent=80, style="arc",
                         outline=color, width=w)
        c.create_oval(8.8 * k, 14.8 * k, 11.2 * k, 17.2 * k, fill=color, outline=color)
    elif name == "settings":
        # 6-tooth precision sprocket gear (reads cleanly at 20px)
        c.create_oval(5.2 * k, 5.2 * k, 14.8 * k, 14.8 * k, outline=color, width=w)
        c.create_oval(8.3 * k, 8.3 * k, 11.7 * k, 11.7 * k, fill=color, outline="")
        for i in range(6):
            a = i * math.pi / 3.0 - math.pi / 6.0
            c.create_line((10 + 4.8 * math.cos(a)) * k, (10 + 4.8 * math.sin(a)) * k,
                          (10 + 7.8 * math.cos(a)) * k, (10 + 7.8 * math.sin(a)) * k,
                          fill=color, width=w + 1, capstyle="round")
    elif name == "log":
        # Framed heartbeat diagnostics pulse
        c.create_rectangle(2.5 * k, 3.5 * k, 17.5 * k, 16.5 * k, outline=color, width=w)
        c.create_line(4.0 * k, 10.5 * k, 7.2 * k, 10.5 * k, 8.8 * k, 6.2 * k, 11.2 * k, 14.2 * k,
                      12.8 * k, 10.5 * k, 16.0 * k, 10.5 * k, fill=color, width=w, capstyle="round", joinstyle="round")
    elif name == "sidebar_collapse":
        c.create_line(4.5 * k, 3.5 * k, 4.5 * k, 16.5 * k, fill=color, width=w, capstyle="round")
        c.create_line(14.5 * k, 5.5 * k, 9.2 * k, 10.0 * k, 14.5 * k, 14.5 * k,
                      fill=color, width=w, capstyle="round", joinstyle="round")
    elif name == "sidebar_expand":
        c.create_line(4.5 * k, 3.5 * k, 4.5 * k, 16.5 * k, fill=color, width=w, capstyle="round")
        c.create_line(9.5 * k, 5.5 * k, 14.8 * k, 10.0 * k, 9.5 * k, 14.5 * k,
                      fill=color, width=w, capstyle="round", joinstyle="round")
    elif name == "mic":
        c.create_rectangle(7 * k, 2 * k, 13 * k, 12 * k, outline=color, width=w)
        c.create_arc(4 * k, 6 * k, 16 * k, 16 * k, start=200, extent=140, style="arc", outline=color, width=w)
        c.create_line(10 * k, 15 * k, 10 * k, 18 * k, fill=color, width=w)
    elif name == "cat":
        ww = max(1, int(round(1.15 * k)))
        c.create_polygon(
            4.2 * k, 8.2 * k,
            3.6 * k, 3.0 * k,
            7.4 * k, 5.8 * k,
            12.6 * k, 5.8 * k,
            16.4 * k, 3.0 * k,
            15.8 * k, 8.2 * k,
            16.6 * k, 12.6 * k,
            13.2 * k, 16.5 * k,
            6.8 * k, 16.5 * k,
            3.4 * k, 12.6 * k,
            fill="",
            outline=color,
            width=w,
            joinstyle="round",
        )
        er = 0.95 * k
        c.create_oval(7.4 * k - er, 10.2 * k - er, 7.4 * k + er, 10.2 * k + er, fill=color, outline="")
        c.create_oval(12.6 * k - er, 10.2 * k - er, 12.6 * k + er, 10.2 * k + er, fill=color, outline="")
        c.create_polygon(9.0 * k, 12.1 * k, 11.0 * k, 12.1 * k, 10.0 * k, 13.4 * k, fill=color, outline="")
        c.create_line(1.5 * k, 11.4 * k, 5.2 * k, 11.9 * k, fill=color, width=ww, capstyle="round")
        c.create_line(1.8 * k, 13.8 * k, 5.2 * k, 13.4 * k, fill=color, width=ww, capstyle="round")
        c.create_line(14.8 * k, 11.9 * k, 18.5 * k, 11.4 * k, fill=color, width=ww, capstyle="round")
        c.create_line(14.8 * k, 13.4 * k, 18.2 * k, 13.8 * k, fill=color, width=ww, capstyle="round")


class CatPreviewButton(SurfaceBox):
    """Compact vector cat button for Voice FX previewing and custom WAV management."""

    def __init__(self, master, command=None, menu_command=None, size=18):
        self._cat_cmd = command
        self._cat_menu_cmd = menu_command
        self._cat_sz = dp(size)
        self._cat_hover = False
        self._cat_playing = False
        self._cat_paint_key = None
        super().__init__(master, bg=T.SURFACE2, border=T.BORDER, corner=6, cursor="hand2")
        self.canvas = tk.Canvas(
            self,
            width=self._cat_sz,
            height=self._cat_sz,
            bg=T.SURFACE2,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.canvas.pack(padx=dp(5), pady=dp(4))
        for w in (self, self.canvas):
            w.bind("<Enter>", lambda _e: self._paint_cat(hover=True))
            w.bind("<Leave>", lambda _e: self._paint_cat(hover=False))
            w.bind("<Button-1>", self._on_left_click)
            w.bind("<Button-3>", self._on_right_click)
            w.bind("<Button-2>", self._on_right_click)
        self._paint_cat()

    def _on_left_click(self, _e=None):
        if self._cat_cmd:
            self._cat_cmd()

    def _on_right_click(self, e=None):
        if self._cat_menu_cmd:
            self._cat_menu_cmd(self, e)

    def _paint_cat(self, hover=None):
        if hover is not None:
            self._cat_hover = bool(hover)
        hi_col = T.ACCENT if T.IS_MONO else T.BLUE
        hi_fg = T.ACCENT_HI if T.IS_MONO else T.BLUE_HI
        if self._cat_playing:
            bg = lerp_color(T.SURFACE2, hi_col, 0.24)
            border = hi_col
            fg = hi_fg
        elif self._cat_hover:
            bg = T.SURFACE3
            border = T.BORDER_HI
            fg = T.TEXT
        else:
            bg = T.SURFACE2
            border = T.BORDER
            fg = hi_fg if not T.IS_MONO else T.MUTED
        pkey = (bg, border, fg, self._cat_sz)
        if pkey == self._cat_paint_key:
            return
        self._cat_paint_key = pkey
        super().refresh_theme(bg=bg, border=border)
        self.canvas.configure(bg=bg)
        draw_icon(self.canvas, "cat", fg, self._cat_sz)

    def set_playing(self, playing):
        flag = bool(playing)
        if flag != self._cat_playing:
            self._cat_playing = flag
            self._paint_cat()

    def refresh_theme(self, bg=None, border=None):
        self._cat_paint_key = None
        self._paint_cat()


class NavButton(_FrameBase):
    """Sidebar navigation pill supporting both expanded labels and slim 64px icon-only rail."""

    def __init__(self, master, icon, text, command):
        if HAS_CTK:
            super().__init__(master, fg_color=T.SIDEBAR, corner_radius=dp(8), border_width=1, border_color=T.SIDEBAR, cursor="hand2")
        else:
            super().__init__(master, bg=T.SIDEBAR, cursor="hand2")
        self.command, self.icon, self.nav_text = command, icon, text
        self.active = False
        self.compact = False
        self._hover = False
        self._last_bg = None
        self._paint_key = None
        self.bar = tk.Frame(self, width=dp(3), bg=T.SIDEBAR)
        self.bar.pack(side="left", fill="y", padx=(dp(6), 0), pady=dp(8))
        self.canvas = tk.Canvas(self, width=dp(20), height=dp(20), bg=T.SIDEBAR, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", padx=(dp(10), dp(10)), pady=dp(10))
        self.label = tk.Label(self, text=text, bg=T.SIDEBAR, fg=T.MUTED, font=font(10), anchor="w")
        self.label.pack(side="left", fill="x", expand=True, padx=(0, dp(8)))
        draw_icon(self.canvas, self.icon, T.MUTED, dp(20))
        for w in (self, self.bar, self.canvas, self.label):
            w.bind("<Button-1>", lambda e: self.command())
            w.bind("<Enter>", lambda e: self._paint(hover=True))
            w.bind("<Leave>", lambda e: self._paint(hover=False))

    def refresh_theme(self):
        self._last_bg = None
        self._paint_key = None
        self._paint()

    def _paint(self, hover=None):
        if hover is not None:
            self._hover = hover
        is_hover = self._hover
        if self.active:
            bg = lerp_color(T.SIDEBAR, T.ACCENT, 0.14)
            border = lerp_color(T.SIDEBAR, T.ACCENT, 0.30)
        elif is_hover:
            bg = T.SURFACE2
            border = T.BORDER
        else:
            bg = T.SIDEBAR
            border = T.SIDEBAR
        fg = T.TEXT if (self.active or is_hover) else T.MUTED
        icon_color = T.ACCENT if self.active else fg
        pkey = (self.active, is_hover, self.compact, bg, border, fg, icon_color)
        if pkey == self._paint_key:
            return
        self._paint_key = pkey
        if bg != self._last_bg:
            self._last_bg = bg
            if HAS_CTK:
                self.configure(fg_color=bg, border_color=border)
            else:
                self.configure(bg=bg)
            for w in (self.canvas, self.label):
                w.configure(bg=bg)
        elif HAS_CTK:
            self.configure(border_color=border)
        self.label.configure(fg=fg, font=font(10, "bold" if self.active else "normal"))
        self.bar.configure(bg=T.ACCENT if self.active else bg)
        draw_icon(self.canvas, self.icon, icon_color, dp(20))

    def set_active(self, active):
        self.active = bool(active)
        self._paint()

    def set_compact(self, compact):
        compact = bool(compact)
        if compact == self.compact:
            return
        self.compact = compact
        self._paint_key = None
        if compact:
            self.label.pack_forget()
            self.bar.pack_forget()
            self.canvas.pack_forget()
            self.bar.pack(side="left", fill="y", padx=(dp(4), 0), pady=dp(8))
            self.canvas.pack(side="left", expand=True, padx=(0, dp(4)), pady=dp(10))
        else:
            self.bar.pack_forget()
            self.canvas.pack_forget()
            self.bar.pack(side="left", fill="y", padx=(dp(6), 0), pady=dp(8))
            self.canvas.pack(side="left", padx=(dp(10), dp(10)), pady=dp(10))
            self.label.pack(side="left", fill="x", expand=True, padx=(0, dp(8)))
        self._paint()


# ==============================================================================
# REALTIME AUDIO VISUALISERS
# ==============================================================================
class LevelMeter(tk.Canvas):
    """Segmented dBFS meter with RMS marker, peak-hold, clip LED, and idle fast-path."""
    SEGMENTS = 54
    DB_MIN = -60.0

    def __init__(self, master, height=38, bg=None):
        super().__init__(master, width=dp(200), height=dp(height), bg=bg or T.SURFACE, highlightthickness=0, bd=0)
        self._items = []
        self._lit = [-1] * self.SEGMENTS
        self._seg_colors = []
        self._rms = None
        self._hold = None
        self._led = None
        self._labels_built = False
        self._idle_settled = False
        self._last_xr = None
        self._last_xh = None
        self._last_clipped = None
        self._last_lit = -1
        self._build_key = None
        self.bind("<Configure>", lambda e: self._build())

    def _x(self, db):
        return self._pad + (min(0.0, max(self.DB_MIN, db)) - self.DB_MIN) / -self.DB_MIN * self._span

    def _build(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 8:
            return
        bkey = (w, h, T.SURFACE, T.SURFACE2, T.SURFACE3, T.GOOD, T.WARN, T.BAD, T.TEXT, T.DIM)
        if bkey == self._build_key:
            return
        self._build_key = bkey
        self.delete("all")
        self._pad = dp(2)
        self._led_w = dp(18)
        self._span = max(10, w - 2 * self._pad - self._led_w)
        show_labels = h >= dp(30)
        label_reserve = dp(16) if show_labels else dp(4)
        bar_h = min(dp(18), max(dp(10), h - dp(3) - label_reserve)) if show_labels else max(dp(8), h - dp(4))
        self._bar_y0 = dp(2)
        self._bar_y1 = self._bar_y0 + bar_h
        seg_w = self._span / self.SEGMENTS
        self._items = []
        self._seg_colors = [self._calc_color(i) for i in range(self.SEGMENTS)]
        for i in range(self.SEGMENTS):
            x0 = self._pad + i * seg_w
            self._items.append(self.create_rectangle(x0 + 1, self._bar_y0, x0 + seg_w - 1, self._bar_y1, fill=T.SURFACE2, outline=""))
        self._rms = self.create_rectangle(0, self._bar_y0 - 2, 0, self._bar_y1 + 2, fill=T.TEXT, outline="")
        self._hold = self.create_rectangle(0, self._bar_y0 - 2, 0, self._bar_y1 + 2, fill=T.TEXT, outline="")
        led_d = min(dp(14), bar_h)
        led_y0 = self._bar_y0 + (bar_h - led_d) / 2.0
        self._led = self.create_oval(w - led_d - dp(1), led_y0, w - dp(1), led_y0 + led_d, fill=T.SURFACE3, outline="")
        if show_labels:
            label_y = self._bar_y1 + dp(3)
            for db in (-60, -48, -36, -24, -12, -6, 0):
                x = self._x(db)
                anch = "nw" if db == -60 else ("ne" if db == 0 else "n")
                self.create_text(x, label_y, text=str(db), fill=T.DIM, font=font(8), anchor=anch)
        self._lit = [-1] * self.SEGMENTS
        self._last_lit = -1
        self._idle_settled = False
        self._last_xr = None
        self._last_xh = None
        self._last_clipped = None

    def _calc_color(self, i):
        db = self.DB_MIN + (i + 0.5) / self.SEGMENTS * -self.DB_MIN
        if db > -3:
            return T.BAD
        if db > -12:
            return T.WARN
        return T.GOOD

    def _color(self, i):
        return self._seg_colors[i] if i < len(self._seg_colors) else self._calc_color(i)

    def update_levels(self, peak_db, rms_db, hold_db, clipped):
        if not self._items:
            return
        clipped_b = bool(clipped)
        is_quiet = (
            peak_db <= self.DB_MIN + 0.5
            and rms_db <= self.DB_MIN + 0.5
            and hold_db <= self.DB_MIN + 0.5
            and not clipped_b
        )
        if is_quiet and self._idle_settled:
            return
        lit = int((min(0.0, max(self.DB_MIN, peak_db)) - self.DB_MIN) / -self.DB_MIN * self.SEGMENTS)
        if self._last_lit < 0:
            idx_range = range(self.SEGMENTS)
        elif lit != self._last_lit:
            idx_range = range(min(self._last_lit, lit), max(self._last_lit, lit))
        else:
            idx_range = ()
        for i in idx_range:
            state = 1 if i < lit else 0
            if state != self._lit[i]:
                self._lit[i] = state
                self.itemconfigure(self._items[i], fill=self._color(i) if state else T.SURFACE2)
        self._last_lit = lit
        xr = round(self._x(rms_db), 1)
        if xr != self._last_xr:
            self._last_xr = xr
            self.coords(self._rms, xr - 1, self._bar_y0 - 2, xr + 1, self._bar_y1 + 2)
        xh = round(self._x(hold_db), 1)
        if xh != self._last_xh:
            self._last_xh = xh
            self.coords(self._hold, xh - 1, self._bar_y0, xh + 1, self._bar_y1)
        if clipped_b != self._last_clipped:
            self._last_clipped = clipped_b
            self.itemconfigure(self._led, fill=T.BAD if clipped_b else T.SURFACE3)
        self._idle_settled = is_quiet and lit <= 0


class SpectrumView(tk.Canvas):
    """Frequency visualizer: 40-band matte Spectrum, 24-column Pill Bars, or dual-layer Waveform."""
    PILL_BANDS = 24

    def __init__(self, master, height=130, bands=40):
        super().__init__(master, width=dp(200), height=dp(height), bg=T.SIDEBAR, highlightthickness=1,
                         highlightbackground=T.BORDER, bd=0)
        self.n = bands
        self.mode = "spectrum"
        self.vals = [0.0] * bands
        self.caps = [0.0] * bands
        self.cap_t = [0] * bands
        self._pill_vals = [0.0] * self.PILL_BANDS
        self._pill_caps = [0.0] * self.PILL_BANDS
        self._pill_cap_t = [0] * self.PILL_BANDS
        self._bars, self._cap_items, self._pills, self._scope, self._scope_halo = [], [], [], None, None
        self._pill_states = []
        self._pill_cap_states = []
        self._spec_colors = []
        self._pill_colors = []
        self._bar_coords = []
        self._cap_coords = []
        self._pill_y_cache = []
        self._pill_cap_cache = []
        self._scope_zeroed = False
        self._build_key = None
        self._idle_settled = False
        self.bind("<Configure>", lambda e: self._build())

    def set_mode(self, mode):
        self.mode = mode
        self._idle_settled = False
        self._build_key = None
        self._build()

    @staticmethod
    def _matte_grad(t):
        # Restrained matte gradient ramp between T.ACCENT and T.BLUE over dark canvas
        c0 = lerp_color(T.SIDEBAR, T.ACCENT, 0.84)
        c1 = lerp_color(T.SIDEBAR, T.BLUE, 0.84)
        return lerp_color(c0, c1, t)

    def _build(self):
        w, h = self.winfo_width(), self.winfo_height()
        bkey = (w, h, self.mode, T.SIDEBAR, T.SURFACE2, T.BORDER, T.ACCENT, T.ACCENT_HI, T.BLUE, T.MUTED, T.DIM)
        if bkey == self._build_key:
            return
        self._build_key = bkey
        self.delete("all")
        self._cw, self._ch = w, h
        self._bars, self._cap_items, self._pills = [], [], []
        self._pill_states, self._pill_cap_states = [], []
        self._bar_coords = [None] * self.n
        self._cap_coords = [None] * self.n
        self._pill_y_cache = [None] * self.PILL_BANDS
        self._pill_cap_cache = [None] * self.PILL_BANDS
        self._scope_zeroed = False
        self._scope, self._scope_halo = None, None
        self._idle_settled = False
        self._spec_colors = [self._matte_grad(i / max(1, self.n - 1)) for i in range(self.n)]
        self._pill_colors = [self._matte_grad(i / max(1, self.PILL_BANDS - 1)) for i in range(self.PILL_BANDS)]
        for frac in (0.25, 0.5, 0.75):
            self.create_line(0, h * frac, w, h * frac, fill=T.SURFACE2)
        if self.mode == "spectrum":
            gap = dp(2)
            pad_x = dp(4)
            bw = max(2.0, (w - 2 * pad_x - gap * (self.n - 1)) / self.n)
            for i in range(self.n):
                x0 = pad_x + i * (bw + gap)
                col = self._spec_colors[i]
                self._bars.append(self.create_rectangle(x0, h, x0 + bw, h, fill=col, outline=""))
                self._cap_items.append(self.create_rectangle(x0, h, x0 + bw, h, fill=T.MUTED, outline=""))
            for f, lab in ((100, "100"), (1000, "1k"), (10000, "10k")):
                pos = (math.log10(f) - math.log10(60)) / (math.log10(18000) - math.log10(60))
                self.create_text(pos * w, h - dp(3), text=lab, fill=T.DIM, font=font(7), anchor="s")
        elif self.mode == "pills":
            pn = self.PILL_BANDS
            pad_x = dp(8)
            y_top, y_bot = dp(8), max(dp(20), h - dp(15))
            gap = dp(4)
            bw = max(4.0, (w - 2 * pad_x - gap * (pn - 1)) / pn)
            r = min(bw * 0.36, dp(4.5))
            for i in range(pn):
                x0 = pad_x + i * (bw + gap)
                x1 = x0 + bw
                # Recessed matte track pill slot
                self.create_oval(x0, y_top, x1, y_top + 2 * r, fill=T.SURFACE2, outline="")
                self.create_rectangle(x0, y_top + r, x1, y_bot - r, fill=T.SURFACE2, outline="")
                self.create_oval(x0, y_bot - 2 * r, x1, y_bot, fill=T.SURFACE2, outline="")
                col = self._pill_colors[i]
                b_top = self.create_oval(x0, y_bot, x1, y_bot, fill=col, outline="", state="hidden")
                b_mid = self.create_rectangle(x0, y_bot, x1, y_bot, fill=col, outline="", state="hidden")
                b_bot = self.create_oval(x0, y_bot, x1, y_bot, fill=col, outline="", state="hidden")
                p_cap = self.create_rectangle(x0 + 1, y_bot, x1 - 1, y_bot, fill=T.MUTED, outline="", state="hidden")
                self._pills.append((x0, x1, y_top, y_bot, r, b_top, b_mid, b_bot, p_cap))
                self._pill_states.append(False)
                self._pill_cap_states.append(False)
            for f, lab in ((100, "100"), (1000, "1k"), (10000, "10k")):
                pos = (math.log10(f) - math.log10(60)) / (math.log10(18000) - math.log10(60))
                self.create_text(pos * w, h - dp(2), text=lab, fill=T.DIM, font=font(7), anchor="s")
        else:
            self.create_line(0, h / 2, w, h / 2, fill=T.BORDER)
            self._scope_halo = self.create_line(0, h / 2, w, h / 2, fill=lerp_color(T.SIDEBAR, T.ACCENT, 0.24),
                                                width=dp(4), smooth=True)
            self._scope = self.create_line(0, h / 2, w, h / 2, fill=T.ACCENT_HI, width=dp(2), smooth=True)

    def feed(self, bands, scope):
        self._idle_settled = False
        if self.mode == "spectrum":
            if not self._bars:
                return
            h, gap, pad_x = self._ch, dp(2), dp(4)
            bw = max(2.0, (self._cw - 2 * pad_x - gap * (self.n - 1)) / self.n)
            for i in range(self.n):
                v = float(bands[i]) if i < len(bands) else 0.0
                self.vals[i] = v if v > self.vals[i] else max(v, self.vals[i] - 0.045)
                if self.vals[i] >= self.caps[i]:
                    self.caps[i], self.cap_t[i] = self.vals[i], 18
                elif self.cap_t[i] > 0:
                    self.cap_t[i] -= 1
                else:
                    self.caps[i] = max(self.vals[i], self.caps[i] - 0.03)
                x0 = pad_x + i * (bw + gap)
                top = round(h - self.vals[i] * (h - dp(16)), 1)
                if top != self._bar_coords[i]:
                    self._bar_coords[i] = top
                    self.coords(self._bars[i], x0, top, x0 + bw, h)
                ct = round(h - self.caps[i] * (h - dp(16)), 1)
                if ct != self._cap_coords[i]:
                    self._cap_coords[i] = ct
                    self.coords(self._cap_items[i], x0, ct - dp(2), x0 + bw, ct)
        elif self.mode == "pills":
            if not self._pills:
                return
            pn = self.PILL_BANDS
            blen = max(1, len(bands))
            for i, (x0, x1, y_top, y_bot, r, b_top, b_mid, b_bot, p_cap) in enumerate(self._pills):
                lo = int(i * blen / pn)
                hi = max(lo + 1, int((i + 1) * blen / pn))
                v = max((float(bands[j]) for j in range(lo, min(blen, hi))), default=0.0)
                self._pill_vals[i] = v if v > self._pill_vals[i] else max(v, self._pill_vals[i] - 0.045)
                if self._pill_vals[i] >= self._pill_caps[i]:
                    self._pill_caps[i], self._pill_cap_t[i] = self._pill_vals[i], 16
                elif self._pill_cap_t[i] > 0:
                    self._pill_cap_t[i] -= 1
                else:
                    self._pill_caps[i] = max(self._pill_vals[i], self._pill_caps[i] - 0.03)
                usable = max(6.0, y_bot - y_top)
                active_h = self._pill_vals[i] * usable
                show_pill = active_h >= dp(3)
                if show_pill:
                    top_y = round(max(y_top, y_bot - active_h), 1)
                    if top_y != self._pill_y_cache[i]:
                        self._pill_y_cache[i] = top_y
                        ch = min(r, (y_bot - top_y) * 0.5)
                        self.coords(b_top, x0, top_y, x1, top_y + 2 * ch)
                        self.coords(b_bot, x0, y_bot - 2 * ch, x1, y_bot)
                        self.coords(b_mid, x0, top_y + ch, x1, y_bot - ch)
                if show_pill != self._pill_states[i]:
                    self._pill_states[i] = show_pill
                    st = "normal" if show_pill else "hidden"
                    for item in (b_top, b_mid, b_bot):
                        self.itemconfigure(item, state=st)
                cap_h = self._pill_caps[i] * usable
                show_cap = cap_h >= dp(4)
                if show_cap:
                    ct = round(max(y_top, y_bot - cap_h), 1)
                    if ct != self._pill_cap_cache[i]:
                        self._pill_cap_cache[i] = ct
                        self.coords(p_cap, x0 + dp(1), ct - dp(2.5), x1 - dp(1), ct)
                if show_cap != self._pill_cap_states[i]:
                    self._pill_cap_states[i] = show_cap
                    self.itemconfigure(p_cap, state="normal" if show_cap else "hidden")
        elif self._scope is not None and len(scope) > 1:
            is_zero = not any(abs(float(s)) > 1e-4 for s in scope)
            if is_zero and self._scope_zeroed:
                return
            self._scope_zeroed = is_zero
            pts = []
            step = self._cw / (len(scope) - 1)
            amp = self._ch * 0.44
            for i, s in enumerate(scope):
                pts.extend((i * step, self._ch / 2 - max(-1.0, min(1.0, float(s) * 2.5)) * amp))
            if self._scope_halo is not None:
                self.coords(self._scope_halo, *pts)
            self.coords(self._scope, *pts)

    def idle(self):
        if self._idle_settled:
            return
        self.feed([0.0] * self.n, [0.0] * 128)
        if self.mode == "spectrum":
            settled = max(self.vals, default=0.0) < 0.002 and max(self.caps, default=0.0) < 0.002
        elif self.mode == "pills":
            settled = max(self._pill_vals, default=0.0) < 0.002 and max(self._pill_caps, default=0.0) < 0.002
        else:
            settled = True
        if settled:
            self._idle_settled = True


class EQCurve(tk.Canvas):
    """Read-only frequency-response plot with band markers (20 Hz - 20 kHz, +/-15 dB)."""
    FMIN, FMAX, DBR = 20.0, 20000.0, 15.0

    def __init__(self, master, height=120):
        super().__init__(master, width=dp(200), height=dp(height), bg=T.SIDEBAR, highlightthickness=1,
                         highlightbackground=T.BORDER, bd=0)
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
            self.create_line(0, self._y(db), w, self._y(db), fill=T.BORDER if db == 0 else T.SURFACE2)
        for f, lab in ((100, "100"), (1000, "1k"), (10000, "10k")):
            self.create_line(self._x(f), 0, self._x(f), h, fill=T.SURFACE2)
            self.create_text(self._x(f) + dp(3), h - dp(2), text=lab, fill=T.DIM, font=font(7), anchor="sw")
        if self.curve:
            pts = []
            for f, d in zip(*self.curve):
                pts.extend((self._x(f), self._y(d)))
            if len(pts) >= 4:
                self.create_line(*pts, fill=T.BLUE, width=dp(2), smooth=True)
        for f, g in self.nodes:
            x, y, r = self._x(f), self._y(g), dp(4)
            self.create_oval(x - r, y - r, x + r, y + r, fill=T.TEXT, outline=T.ACCENT)


FlatButton.rebuild_styles()
