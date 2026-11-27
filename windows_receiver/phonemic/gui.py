"""Main Obsidian Studio window, navigation, shared presets/notifications, Compact toggle, and Studio Home dashboard."""
import re
import sys
import time
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from . import system, virtual_mic, presets_io as pio, settings_meta as sm, cues
from .hotkeys import HotkeyService, parse_combo
from .tray import TrayIcon
from .bindings import SettingsBinder
from .const import VERSION, APP_NAME
from .dsp import FX_BUILTIN_PRESETS, VoiceChanger, fx_preset, lin_to_db
from .widgets import (T, HAS_CTK, ctk, dp, font, set_scale, create_root, create_toplevel, apply_styles, apply_accent,
                      init_fonts, draw_icon, lerp_color, screen_bounds, FlatButton, Segmented, Combo, Card, ScrollFrame,
                      NavButton, LevelMeter, SpectrumView, Tooltip, autowrap,
                      TextInput, ProgressBar, SurfaceBox, PillBadge, CatPreviewButton, _FrameBase)
from .ui_kit import SettingRow, GaugeRow, SearchBox
from .minimal_gui import MinimalView
from .qr import generate_qr_matrix
from . import icon


NAV = [
    ("dashboard", "Studio Home", "dashboard"),
    ("sound", "Audio Studio", "sound"),
    ("connect", "Connections", "devices"),
    ("settings", "Settings", "settings"),
    ("log", "Diagnostics", "log"),
]

TITLES = {
    "dashboard": "Studio Home",
    "sound": "Audio Studio",
    "voice": "Audio Studio",
    "connect": "Connections",
    "devices": "Connections",
    "network": "Connections",
    "settings": "Settings",
    "log": "Diagnostics",
    "wizard": "Setup",
}

HOTKEY_ACTIONS = ("toggle_mute", "push_to_talk", "push_to_mute", "toggle_monitor", "toggle_record", "toggle_bypass", "show_window")

def _state_style(state):
    return {
        "waiting": (T.ACCENT, "Waiting for phone"),
        "streaming": (T.GOOD, "Streaming"),
        "muted": (T.WARN, "Muted"),
        "lost": (T.WARN, "Connection lost"),
        "error": (T.BAD, "Network error"),
    }[state]


def fmt_time(seconds):
    seconds = int(max(0, seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ==============================================================================
# DIALOGS
# ==============================================================================
class PromptDialog:
    def __init__(self, parent, title, prompt, initial=""):
        self.result = None
        self.win = win = create_toplevel(parent, fg_color=T.SURFACE)
        win.title(title)
        win.resizable(False, False)
        win.transient(parent)
        system.apply_dark_titlebar(win, True)

        tk.Label(win, text=prompt, bg=T.SURFACE, fg=T.TEXT, font=font(10), anchor="w").pack(
            fill="x", padx=dp(18), pady=(dp(16), dp(6)))
        self.var = tk.StringVar(value=initial)
        e = TextInput(win, textvariable=self.var, width=34, size=11)
        e.pack(padx=dp(18), ipady=0 if HAS_CTK else dp(5))
        e.focus_set()
        e.select_all()

        row = tk.Frame(win, bg=T.SURFACE)
        row.pack(fill="x", padx=dp(18), pady=dp(16))
        FlatButton(row, "Save", self._ok, style="primary").pack(side="right")
        FlatButton(row, "Cancel", win.destroy, style="normal").pack(side="right", padx=(0, dp(8)))
        e.bind("<Return>", lambda ev: self._ok())
        win.bind("<Escape>", lambda ev: win.destroy())
        try:
            win.update_idletasks()
            vx, vy, vw, vh = screen_bounds(win)
            ww = win.winfo_width() or win.winfo_reqwidth()
            wh = win.winfo_height() or win.winfo_reqheight()
            x = parent.winfo_rootx() + (parent.winfo_width() - ww) // 2
            y = parent.winfo_rooty() + dp(120)
            x = max(vx + dp(6), min(x, vx + vw - ww - dp(6)))
            y = max(vy + dp(6), min(y, vy + vh - wh - dp(6)))
            win.geometry(f"+{x}+{y}")
            win.grab_set()
        except Exception:
            pass

    def _ok(self):
        self.result = self.var.get().strip()
        self.win.destroy()


class QRPopupDialog:
    """Modal QR pairing popup accessible straight from Studio Home."""

    def __init__(self, app, payload):
        parent = app.root
        win = create_toplevel(parent, fg_color=T.SURFACE)
        win.title("Scan to Pair Phone")
        win.resizable(False, False)
        win.transient(parent)
        system.apply_dark_titlebar(win, True)

        tk.Label(win, text="Instant QR Code Pairing", bg=T.SURFACE, fg=T.TEXT, font=font(14, "bold", True)).pack(
            padx=dp(20), pady=(dp(16), dp(4)))
        tk.Label(win, text="Open PhoneMic on your phone and tap Scan PC QR.", bg=T.SURFACE, fg=T.MUTED,
                 font=font(9)).pack(padx=dp(20), pady=(0, dp(12)))

        box = SurfaceBox(win, bg="#ffffff", border=T.BORDER_HI, corner=10)
        box.pack(padx=dp(24))
        sz = dp(200)
        canvas = tk.Canvas(box, width=sz, height=sz, bg="#ffffff", highlightthickness=0)
        canvas.pack(padx=dp(6), pady=dp(6))
        try:
            matrix = generate_qr_matrix(payload)
            n = len(matrix)
            cell = sz / (n + 4)
            off = cell * 2
            canvas.create_rectangle(0, 0, sz, sz, fill="#ffffff", outline="")
            for y in range(n):
                for x in range(n):
                    if matrix[y][x]:
                        x1 = off + x * cell
                        y1 = off + y * cell
                        canvas.create_rectangle(x1, y1, x1 + cell, y1 + cell, fill="#000000", outline="")
        except Exception:
            pass

        PillBadge(win, payload, fg=T.ACCENT_HI, bg=T.SURFACE2, border=T.BORDER, size=9,
                  display=True, padx=12, pady=4, corner=8).pack(padx=dp(20), pady=(dp(10), dp(12)))

        row = tk.Frame(win, bg=T.SURFACE)
        row.pack(fill="x", padx=dp(20), pady=(0, dp(16)))
        FlatButton(row, "Close", win.destroy, style="normal").pack(side="right")
        FlatButton(row, "Copy Address", lambda: app.copy(payload, "Copied pairing URI"), style="primary").pack(
            side="right", padx=(0, dp(8)))
        win.bind("<Escape>", lambda ev: win.destroy())
        try:
            win.update_idletasks()
            vx, vy, vw, vh = screen_bounds(win)
            ww = win.winfo_width() or win.winfo_reqwidth()
            wh = win.winfo_height() or win.winfo_reqheight()
            x = parent.winfo_rootx() + (parent.winfo_width() - ww) // 2
            y = parent.winfo_rooty() + dp(90)
            x = max(vx + dp(6), min(x, vx + vw - ww - dp(6)))
            y = max(vy + dp(6), min(y, vy + vh - wh - dp(6)))
            win.geometry(f"+{x}+{y}")
        except Exception:
            pass


# ==============================================================================
# PAGE BASE
# ==============================================================================
class Page(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.body = tk.Frame(self.scroll.inner, bg=T.BG)
        self.body.pack(fill="both", expand=True, padx=dp(22), pady=(dp(4), dp(22)))
        self.build()

    def build(self):
        pass

    def on_show(self):
        pass

    def apply_view(self, advanced):
        pass

    def focus_setting(self, setting):
        pass

    def refresh_fast(self):
        pass

    def refresh_slow(self):
        pass


# ==============================================================================
# APPLICATION SHELL
# ==============================================================================
class App:
    def __init__(self, receiver, start_minimized=False, crash_writer=None):
        self.rx = receiver
        self.cfg = receiver.config
        self.proc = receiver.processor
        self._crash_writer = crash_writer
        self.root = root = create_root()
        if crash_writer is not None:
            root.report_callback_exception = lambda t, v, tb: crash_writer(t, v, tb, "UI callback")
        try:
            set_scale(root.winfo_fpixels("1i") / 96.0)
        except Exception:
            pass
        init_fonts(root)
        apply_accent(self.cfg.data["app"]["accent"], soft=self.cfg.data["app"].get("soft_colors", False))
        root.title(f"{APP_NAME} {VERSION}")
        if HAS_CTK:
            root.configure(fg_color=T.BG)
        else:
            root.configure(bg=T.BG)
        root.minsize(dp(820), dp(560))
        self._restore_geometry()
        apply_styles(root)
        icon.apply(root)
        system.apply_dark_titlebar(root, True)
        if self.cfg.data["app"]["always_on_top"]:
            root.attributes("-topmost", True)

        self.advanced = bool(self.cfg.data["app"]["advanced_mode"])
        self.sidebar_collapsed = bool(self.cfg.data["app"].get("sidebar_collapsed", False))
        self.ui_mode = self.cfg.data["app"].get("ui_mode", "default")
        self.minimal_view = None
        self.binder = SettingsBinder(receiver, hooks=self)
        self.binder.listen_any(self._setting_changed, scope="shell")
        self.pages, self.page_classes, self.nav = {}, {}, {}
        self.current = None
        self.preset_combos, self.preset_marks, self.voice_combos = [], [], []
        self.fw_state, self.fw_label, self.fw_busy = None, "", False
        self._slow_t = 0.0
        self._notice_job = None
        self._err_seen = set()
        self._hdr_cache = None
        self._sb_cache = None
        self._header_wide = None
        self._hdr_job = None
        self._pending_hdr_w = None
        self._syncing_devices = False
        self._cat_menu = None
        self.actions_q = queue.Queue()
        self._tray_hint_shown = False
        self.hotkeys = HotkeyService(self._hk_press, self._hk_hold, log=lambda m: self.rx.log.warn(m))
        self.tray = TrayIcon({"show": lambda: self.post(self.show_window), "mute": lambda: self.post(self.toggle_mute),
                              "monitor": lambda: self.post(self.toggle_monitor), "record": lambda: self.post(self.toggle_record),
                              "bypass": lambda: self.post(self.toggle_bypass), "quit": lambda: self.post(self.quit_app)}, self._tray_state)
        self.stop_instance = system.start_instance_listener(lambda: self.post(self.show_window))

        self._build_shell()
        from .pages import SoundPage, ConnectPage, SettingsPage, LogPage
        from .wizard import WizardPage
        self.page_classes = {
            "dashboard": DashboardPage,
            "sound": SoundPage,
            "connect": ConnectPage,
            "devices": ConnectPage,
            "network": ConnectPage,
            "settings": SettingsPage,
            "log": LogPage,
            "wizard": WizardPage,
        }
        self.show_page("dashboard" if self.cfg.data["app"]["first_run_done"] else "wizard")
        self.refresh_preset_ui()
        self.apply_hotkeys()
        self.apply_tray()

        if self.ui_mode == "minimal":
            self.switch_ui_mode("minimal", save_previous_geo=False)

        root.bind_all("<MouseWheel>", self._on_wheel)
        root.bind_all("<Button-4>", lambda e: self._on_wheel(e, 1))
        root.bind_all("<Button-5>", lambda e: self._on_wheel(e, -1))
        root.bind("<Control-m>", lambda e: self.toggle_mute())
        root.bind("<Control-e>", lambda e: self.toggle_monitor())
        root.bind("<Control-r>", lambda e: self.toggle_record())
        root.bind("<Control-b>", lambda e: self.toggle_bypass())
        root.bind("<Control-f>", lambda e: self.search.entry.focus_set())
        root.bind("<F10>", lambda e: self.toggle_ui_mode())
        root.bind("<Control-Shift-M>", lambda e: self.toggle_ui_mode())
        root.bind("<Control-Shift-m>", lambda e: self.toggle_ui_mode())
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        if start_minimized:
            root.withdraw() if self.tray.running else root.iconify()
        self.refresh_firewall_async()
        if self.cfg.load_error:
            self.notify(self.cfg.load_error, "warn", 8000)
        elif self.cfg.migrated_from:
            self.notify(f"Your settings from version {self.cfg.migrated_from} were carried over.", "info", 6000)
        root.after(30, self._pump)
        root.after(100, self.tick)

    def post(self, fn):
        self.actions_q.put(fn)

    def _pump(self):
        try:
            for _ in range(30):
                fn = self.actions_q.get_nowait()
                try:
                    fn()
                except Exception as e:      # noqa: BLE001
                    self.rx.log.error(f"Action failed: {e!r}")
        except queue.Empty:
            pass
        self.root.after(30, self._pump)

    def _cue(self, kind):
        h = self.cfg.data["hotkeys"]
        if h["enabled"] and h["sound_cues"]:
            cues.play(kind)

    def _hk_press(self, action):
        self.post(lambda: self.do_action(action))

    def _hk_hold(self, action, down):
        if action == "push_to_talk":
            self.rx.set_ptt_held(down)
            self._cue("on" if down else "off")
        elif action == "push_to_mute":
            self.rx.set_hold_mute(down)
            self._cue("mute" if down else "unmute")
        self.post(self.refresh_header)

    def do_action(self, action):
        if action == "toggle_mute":
            self.toggle_mute()
            self._cue("mute" if self.rx.paused else "unmute")
        elif action == "toggle_monitor":
            self.toggle_monitor()
        elif action == "toggle_record":
            self.toggle_record()
        elif action == "toggle_bypass":
            self.toggle_bypass()
        elif action == "show_window":
            self.show_window()

    def apply_hotkeys(self):
        h = self.cfg.data["hotkeys"]
        self.hotkeys.set_bindings({a: h[a] for a in HOTKEY_ACTIONS} if h["enabled"] else {})
        self.rx.configure_talk_keys(bool(h["enabled"] and parse_combo(h["push_to_talk"])))
        if not (h["enabled"] and parse_combo(h["push_to_mute"])):
            self.rx.set_hold_mute(False)
        self.refresh_header()

    def _tray_state(self):
        return {"muted": self.rx.paused, "monitoring": self.rx.monitoring, "recording": self.rx.recorder.active,
                "bypassed": self.proc.fx_bypass}

    def apply_tray(self):
        want = bool(self.cfg.data["app"]["tray_icon"]) and self.tray.available
        if want and not self.tray.running:
            self.tray.start(self.rx.state())
            self._hdr_cache = None
            self.refresh_header()
        elif not want and self.tray.running:
            self.tray.stop()

    def show_window(self):
        r = self.root
        r.deiconify()
        try:
            r.state("normal")
        except Exception:
            pass
        r.lift()
        r.attributes("-topmost", True)
        r.after(150, lambda: r.attributes("-topmost", bool(self.cfg.data["app"]["always_on_top"])))
        r.focus_force()
        system.apply_dark_titlebar(r, True)

    def hide_window(self):
        self.root.withdraw()

    def set_advanced(self, flag):
        self.advanced = bool(flag)
        for page in self.pages.values():
            page.apply_view(self.advanced)

    def set_topmost(self, flag):
        self.root.attributes("-topmost", bool(flag))

    def _setting_changed(self, setting):
        self.refresh_preset_marks()

    @staticmethod
    def _parse_geometry(geo):
        m = re.fullmatch(r"(\d+)x(\d+)(?:\+|(?=-))(-?\d+)(?:\+|(?=-))(-?\d+)", geo or "")
        if not m:
            return None
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))

    def _restore_geometry(self):
        geo = self.cfg.data["app"]["window_geometry"]
        parsed = self._parse_geometry(geo)
        ok = False
        w = dp(940)
        if parsed:
            w, h, x, y = parsed
            vx, vy, vw, vh = screen_bounds(self.root)
            ok = (w >= dp(720) and h >= dp(480)
                  and vx - dp(50) <= x < vx + vw - dp(150)
                  and vy - dp(10) <= y < vy + vh - dp(100))
        self._init_w = w if ok else dp(940)
        self.root.geometry(geo if ok else f"{dp(940)}x{dp(630)}")

    # ---- Obsidian Studio Shell -------------------------------------------------------------------------------------------
    def _build_shell(self):
        root = self.root
        self.side_frame = side = tk.Frame(root, bg=T.SIDEBAR, width=dp(218))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        # Crisp 1px vertical divider on the right edge of sidebar
        self.side_divider = tk.Frame(side, bg=T.BORDER, width=1)
        self.side_divider.pack(side="right", fill="y")

        self.logo_box = logo = tk.Frame(side, bg=T.SIDEBAR)
        logo.pack(fill="x", padx=dp(16), pady=(dp(18), dp(14)))
        self.brand_row = brand_row = tk.Frame(logo, bg=T.SIDEBAR)
        brand_row.pack(fill="x")
        self.brand_dot = tk.Label(brand_row, text="\u25c9", bg=T.SIDEBAR, fg=T.ACCENT, font=font(16, "bold"))
        self.brand_dot.pack(side="left", padx=(0, dp(6)))
        self.brand_title = tk.Label(brand_row, text="PhoneMic", bg=T.SIDEBAR, fg=T.TEXT, font=font(19, "bold", True))
        self.brand_title.pack(side="left")
        self.brand_sub = tk.Label(logo, text=f"Studio Receiver v{VERSION}", bg=T.SIDEBAR, fg=T.DIM, font=font(9))
        self.brand_sub.pack(anchor="w", pady=(dp(2), 0))

        self.nav_wrap = tk.Frame(side, bg=T.SIDEBAR)
        self.nav_wrap.pack(fill="x")
        for key, text, ic in NAV:
            b = NavButton(self.nav_wrap, ic, text, lambda k=key: self.show_page(k))
            b.pack(fill="x", padx=dp(10), pady=dp(2))
            self.nav[key] = b

        self.side_foot = foot = tk.Frame(side, bg=T.SIDEBAR)
        foot.pack(side="bottom", fill="x", padx=dp(16), pady=dp(16))
        self.side_view_label = tk.Label(foot, text="SETTINGS VIEW", bg=T.SIDEBAR, fg=T.DIM, font=font(8, "bold"), anchor="w")
        self.side_view_label.pack(fill="x", pady=(0, dp(5)))
        adv = sm.BY_KEY["app.advanced_mode"]
        self.view_toggle = Segmented(foot, [(False, "Simple"), (True, "Advanced")], self.advanced,
                                     lambda v: self.binder.set(adv, v), bg=T.SIDEBAR)
        self.view_toggle.pack(anchor="w")
        Tooltip(self.view_toggle, "Simple shows essentials. Advanced reveals every DSP and buffer parameter.")
        self.btn_view_compact = FlatButton(foot, "Adv" if self.advanced else "Sim",
                                           lambda: self.binder.set(adv, not self.advanced),
                                           style="active" if self.advanced else "normal", size=8, padx=6, pady=3, corner=6)
        Tooltip(self.btn_view_compact, "Toggle Simple / Advanced settings view")
        self.binder.listen(adv.key, self._view_listener, scope="shell")
        self.side_state = tk.Label(foot, text="", bg=T.SIDEBAR, fg=T.DIM, font=font(9), anchor="w", justify="left")
        self.side_state.pack(fill="x", pady=(dp(14), 0))

        self.main_frame = main = tk.Frame(root, bg=T.BG)
        main.pack(side="right", fill="both", expand=True)

        # ---- Responsive Two-Tier Header (Tier 1: nav + title + status/compact; Tier 2: quick transport + search fallback)
        self.header_box = hb = tk.Frame(main, bg=T.BG)
        hb.pack(fill="x", padx=dp(22), pady=(dp(14), dp(8)))
        hb.grid_columnconfigure(0, weight=0)
        hb.grid_columnconfigure(1, weight=1)
        hb.grid_columnconfigure(2, weight=0)

        self.head_left = head_left = tk.Frame(hb, bg=T.BG)
        self.btn_sidebar_wrap = SurfaceBox(head_left, bg=T.SURFACE2, border=T.BORDER, corner=8)
        self.btn_sidebar_wrap.pack(side="left", padx=(0, dp(10)))
        self.btn_sidebar = tk.Canvas(self.btn_sidebar_wrap, width=dp(24), height=dp(24), bg=T.SURFACE2,
                                     highlightthickness=0, bd=0, cursor="hand2")
        self.btn_sidebar.pack(padx=dp(3), pady=dp(3))
        self.btn_sidebar.bind("<Button-1>", lambda e: self.toggle_sidebar())
        self.btn_sidebar.bind("<Enter>", lambda e: self._paint_sidebar_btn(hover=True))
        self.btn_sidebar.bind("<Leave>", lambda e: self._paint_sidebar_btn(hover=False))
        self._sidebar_btn_hover = False
        Tooltip(self.btn_sidebar, "Collapse or expand the navigation sidebar")

        self.title_label = tk.Label(head_left, text="", bg=T.BG, fg=T.TEXT, font=font(20, "bold", True))
        self.title_label.pack(side="left")

        self.head_right = head_right = tk.Frame(hb, bg=T.BG)
        self.btn_compact = FlatButton(head_right, "Compact", lambda: self.switch_ui_mode("minimal"),
                                      style="normal", size=9, padx=10, pady=4)
        self.btn_compact.pack(side="right", padx=(dp(8), 0))
        Tooltip(self.btn_compact, "Switch to compact Minimal GUI widget (F10)")

        self.chip = chip = SurfaceBox(head_right, bg=T.SURFACE, border=T.BORDER, corner=8)
        chip.pack(side="right")
        self.chip_in = chip_in = tk.Frame(chip, bg=T.SURFACE)
        chip_in.pack(padx=dp(9), pady=dp(4))
        self.chip_dot = tk.Label(chip_in, text="\u25cf", bg=T.SURFACE, fg=T.ACCENT, font=font(9))
        self.chip_dot.pack(side="left", padx=(0, dp(5)))
        self.chip_text = tk.Label(chip_in, text="Starting", bg=T.SURFACE, fg=T.TEXT, font=font(9, "bold"))
        self.chip_text.pack(side="left")

        self.search = SearchBox(hb, self, width=22)

        self.actions = actions = tk.Frame(hb, bg=T.BG)
        self.btn_fx = FlatButton(actions, "Effects on", self.toggle_bypass, style="blue", size=9, padx=9, pady=3)
        self.btn_mute = FlatButton(actions, "Mute", self.toggle_mute, size=9, padx=9, pady=3)
        self.btn_monitor = FlatButton(actions, "Monitor", self.toggle_monitor, size=9, padx=9, pady=3)
        self.btn_record = FlatButton(actions, "Record", self.toggle_record, size=9, padx=9, pady=3)
        for i, (b, tip) in enumerate((
            (self.btn_fx, "Switch every effect off to compare plain mic vs processed sound (Ctrl+B)"),
            (self.btn_mute, "Mute PC output and pause phone transmission (Ctrl+M)"),
            (self.btn_monitor, "Hear your processed voice on headphones (Ctrl+E)"),
            (self.btn_record, "Record audio stream to WAV file (Ctrl+R)"),
        )):
            b.pack(side="left", padx=(0 if i == 0 else dp(6), 0))
            Tooltip(b, tip)

        self.head_left.grid(row=0, column=0, sticky="w")
        self.head_right.grid(row=0, column=2, sticky="e")
        self._layout_header(max(dp(400), getattr(self, "_init_w", dp(940)) - dp(64 if self.sidebar_collapsed else 218)))
        main.bind("<Configure>", lambda e: self._schedule_header(e.width), add="+")

        self.status_wrap = status_wrap = tk.Frame(main, bg=T.SIDEBAR)
        status_wrap.pack(side="bottom", fill="x")
        self.status_divider = tk.Frame(status_wrap, bg=T.BORDER, height=1)
        self.status_divider.pack(fill="x")
        self.status_bar = status = tk.Frame(status_wrap, bg=T.SIDEBAR)
        status.pack(fill="x")
        self.status_left = tk.Label(status, text="", bg=T.SIDEBAR, fg=T.MUTED, font=font(9), anchor="w")
        self.status_left.pack(side="left", padx=dp(16), pady=dp(6))
        self.status_right = tk.Label(status, text="", bg=T.SIDEBAR, fg=T.DIM, font=font(9, "normal", True), anchor="e")
        self.status_right.pack(side="right", padx=dp(16))

        self.content = tk.Frame(main, bg=T.BG)
        self.content.pack(fill="both", expand=True)
        self.apply_sidebar(save=False)

    def _schedule_header(self, width_px):
        if not width_px or width_px < 40:
            return
        self._pending_hdr_w = width_px
        if self._hdr_job:
            try:
                self.main_frame.after_cancel(self._hdr_job)
            except Exception:
                pass
        self._hdr_job = self.main_frame.after(16, self._run_header)

    def _run_header(self):
        self._hdr_job = None
        if self.main_frame.winfo_exists() and self._pending_hdr_w is not None:
            self._layout_header(self._pending_hdr_w, hysteresis=True)

    def _layout_header(self, width_px=None, hysteresis=False):
        if width_px is None:
            width_px = self.main_frame.winfo_width()
        if not width_px or width_px < 40:
            return
        bp = dp(760)
        if hysteresis and self._header_wide is not None:
            wide = (width_px >= bp + dp(12)) if not self._header_wide else (width_px >= bp - dp(12))
        else:
            wide = width_px >= bp
        if wide == self._header_wide:
            return
        self._header_wide = wide
        self.search.grid_forget()
        self.actions.grid_forget()
        if wide:
            self.search.grid(row=0, column=1, sticky="e", padx=(dp(12), dp(12)))
            self.actions.grid(row=1, column=0, columnspan=3, sticky="w", pady=(dp(8), 0))
        else:
            self.actions.grid(row=1, column=0, columnspan=2, sticky="w", pady=(dp(8), 0))
            self.search.grid(row=1, column=2, sticky="e", padx=(dp(10), 0), pady=(dp(8), 0))

    def _paint_sidebar_btn(self, hover=None):
        if hover is not None:
            self._sidebar_btn_hover = hover
        bg = T.SURFACE3 if self._sidebar_btn_hover else T.SURFACE2
        border = T.BORDER_HI if self._sidebar_btn_hover else T.BORDER
        self.btn_sidebar_wrap.refresh_theme(bg=bg, border=border)
        self.btn_sidebar.configure(bg=bg)
        icon_name = "sidebar_expand" if self.sidebar_collapsed else "sidebar_collapse"
        draw_icon(self.btn_sidebar, icon_name, T.TEXT if self._sidebar_btn_hover else T.MUTED, dp(18))

    def toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed
        self.apply_sidebar(save=True)

    def apply_sidebar(self, save=False):
        collapsed = self.sidebar_collapsed
        self.side_frame.configure(width=dp(64) if collapsed else dp(218))
        for key, b in self.nav.items():
            b.set_compact(collapsed)
            b.pack(fill="x", padx=dp(8 if collapsed else 10), pady=dp(2))
        if collapsed:
            self.logo_box.pack(fill="x", padx=dp(8), pady=(dp(18), dp(14)))
            self.brand_title.pack_forget()
            self.brand_sub.pack_forget()
            self.brand_dot.pack(side="top", padx=0)
            self.side_foot.pack(side="bottom", fill="x", padx=dp(8), pady=dp(14))
            self.side_view_label.pack_forget()
            self.view_toggle.pack_forget()
            self.side_state.pack_forget()
            self.btn_view_compact.pack(fill="x")
            self.side_state.pack(fill="x", pady=(dp(10), 0))
        else:
            self.logo_box.pack(fill="x", padx=dp(16), pady=(dp(18), dp(14)))
            self.brand_dot.pack(side="left", padx=(0, dp(6)))
            self.brand_title.pack(side="left")
            self.brand_sub.pack(anchor="w", pady=(dp(2), 0))
            self.side_foot.pack(side="bottom", fill="x", padx=dp(16), pady=dp(16))
            self.btn_view_compact.pack_forget()
            self.side_state.pack_forget()
            self.side_view_label.pack(fill="x", pady=(0, dp(5)))
            self.view_toggle.pack(anchor="w")
            self.side_state.pack(fill="x", pady=(dp(14), 0))
        self._paint_sidebar_btn()
        self._sb_cache = None
        self.refresh_statusbar()
        rw = self.root.winfo_width()
        if rw and rw > dp(300):
            self._layout_header(max(dp(400), rw - dp(64 if collapsed else 218)))
        if save:
            self.cfg.data["app"]["sidebar_collapsed"] = collapsed
            self.cfg.save_soon()

    def apply_theme(self):
        app_cfg = self.cfg.data["app"]
        apply_accent(app_cfg["accent"], soft=app_cfg.get("soft_colors", False))
        apply_styles(self.root)
        if HAS_CTK:
            self.root.configure(fg_color=T.BG)
        else:
            self.root.configure(bg=T.BG)

        # Snapshot current page & sub-state so live rebuild preserves the user's spot
        prev_page = self.current
        sound_stage = self.pages["sound"].stage_id if "sound" in self.pages else None
        eq_band = getattr(self.pages.get("sound"), "eq_band", 3)
        settings_tab = getattr(self.pages.get("settings"), "active_tab", "general")
        wizard_state = (self.pages["wizard"].step, self.pages["wizard"].mode) if "wizard" in self.pages else None

        # Restyle persistent shell chrome
        for w in (self.side_frame, self.logo_box, self.brand_row, self.nav_wrap, self.side_foot):
            w.configure(bg=T.SIDEBAR)
        self.side_divider.configure(bg=T.BORDER)
        self.brand_dot.configure(bg=T.SIDEBAR, fg=T.ACCENT)
        self.brand_title.configure(bg=T.SIDEBAR, fg=T.TEXT)
        self.brand_sub.configure(bg=T.SIDEBAR, fg=T.DIM)
        self.side_view_label.configure(bg=T.SIDEBAR, fg=T.DIM)
        self.side_state.configure(bg=T.SIDEBAR, fg=T.DIM)
        for b in self.nav.values():
            b.refresh_theme()
        self.view_toggle.refresh_theme(T.SIDEBAR)
        self.btn_view_compact.refresh_theme()

        for w in (self.main_frame, self.header_box, self.head_left, self.head_right, self.actions, self.content):
            w.configure(bg=T.BG)
        self.title_label.configure(bg=T.BG, fg=T.TEXT)
        self.chip.refresh_theme(bg=T.SURFACE, border=T.BORDER)
        self.chip_in.configure(bg=T.SURFACE)
        self.chip_dot.configure(bg=T.SURFACE)
        self.chip_text.configure(bg=T.SURFACE, fg=T.TEXT)
        self.btn_compact.refresh_theme()
        self.search.refresh_theme()
        for b in (self.btn_fx, self.btn_mute, self.btn_monitor, self.btn_record):
            b.refresh_theme()
        for w in (self.status_wrap, self.status_bar):
            w.configure(bg=T.SIDEBAR)
        self.status_divider.configure(bg=T.BORDER)
        self.status_left.configure(bg=T.SIDEBAR, fg=T.MUTED)
        self.status_right.configure(bg=T.SIDEBAR, fg=T.DIM)
        self._paint_sidebar_btn()

        # Drop page-scoped binder listeners cleanly, destroy stale pages, and rebuild active view
        self.binder.clear_scope("page")
        self.preset_combos.clear()
        self.preset_marks.clear()
        self.voice_combos.clear()
        for p in list(self.pages.values()):
            p.destroy()
        self.pages.clear()
        self.current = None

        self.show_page(prev_page or "dashboard")
        if prev_page == "sound" and "sound" in self.pages:
            sp_page = self.pages["sound"]
            if sound_stage:
                sp_page.pick_stage(sound_stage)
            if hasattr(sp_page, "eq_pick") and sp_page.editor is not None:
                sp_page.eq_pick(eq_band)
        elif prev_page == "settings" and "settings" in self.pages:
            self.pages["settings"]._pick_tab(settings_tab)
        elif prev_page == "wizard" and wizard_state and "wizard" in self.pages:
            wz = self.pages["wizard"]
            wz.mode = wizard_state[1]
            wz.go(wizard_state[0])

        if self.minimal_view is not None:
            was_minimal = (self.ui_mode == "minimal")
            self.minimal_view.destroy()
            self.minimal_view = MinimalView(self.root, self)
            if was_minimal:
                self.minimal_view.pack(fill="both", expand=True)
                self.minimal_view.refresh_controls(force=True)

        self._hdr_cache = None
        self._sb_cache = None
        self._close_cat_menu()
        self.refresh_preset_ui()
        self.refresh_cat_ui()
        self.binder.sync_all()
        self.refresh_header()
        self.refresh_statusbar()
        self.notify("Theme updated.", "info", 3000)

    def sync_output_devices(self):
        if self._syncing_devices:
            return
        self._syncing_devices = True
        try:
            dash = self.pages.get("dashboard")
            if dash is not None and hasattr(dash, "sync_outputs"):
                dash.sync_outputs()
            conn = self.pages.get("connect")
            if conn is not None and hasattr(conn, "fill_devices"):
                conn.fill_devices()
        finally:
            self._syncing_devices = False

    def _view_listener(self, value):
        flag = bool(value)
        if self.view_toggle.get() != flag:
            self.view_toggle.set(flag)
        if hasattr(self, "btn_view_compact"):
            self.btn_view_compact.set_text("Adv" if flag else "Sim")
            self.btn_view_compact.set_style("active" if flag else "normal")

    # ---- UI Mode Switching (Default Studio <-> Compact Widget) -----------------------------------------------------------
    def toggle_ui_mode(self):
        new_mode = "default" if self.ui_mode == "minimal" else "minimal"
        self.switch_ui_mode(new_mode)

    def switch_ui_mode(self, mode, save_previous_geo=True):
        if mode == self.ui_mode and self.minimal_view is not None:
            return
        root = self.root

        if mode == "minimal":
            if save_previous_geo and self.ui_mode == "default" and root.state() == "normal":
                self.cfg.data["app"]["window_geometry"] = root.winfo_geometry()

            try:
                if root.state() == "zoomed":
                    root.state("normal")
            except Exception:
                pass

            self.side_frame.pack_forget()
            self.main_frame.pack_forget()

            if self.minimal_view is None:
                self.minimal_view = MinimalView(root, self)
            self.minimal_view.pack(fill="both", expand=True)
            self.minimal_view.refresh_controls()

            root.minsize(dp(320), dp(175))
            mg = self.cfg.data["app"].get("minimal_geometry")
            parsed = self._parse_geometry(mg)
            ok = False
            if parsed:
                w, h, x, y = parsed
                vx, vy, vw, vh = screen_bounds(root)
                ok = (w >= dp(280) and h >= dp(150)
                      and vx - dp(50) <= x < vx + vw - dp(100)
                      and vy - dp(10) <= y < vy + vh - dp(80))
            root.geometry(mg if ok else f"{dp(330)}x{dp(185)}")

            self.ui_mode = "minimal"
            self.cfg.data["app"]["ui_mode"] = "minimal"
            self.cfg.save_soon()

        else:
            if save_previous_geo and self.ui_mode == "minimal" and root.state() == "normal":
                self.cfg.data["app"]["minimal_geometry"] = root.winfo_geometry()

            if self.minimal_view is not None:
                self.minimal_view.pack_forget()

            self.side_frame.pack(side="left", fill="y")
            self.main_frame.pack(side="right", fill="both", expand=True)

            root.minsize(dp(820), dp(560))
            self._restore_geometry()
            self._header_wide = None
            self.apply_sidebar(save=False)
            self._layout_header(max(dp(400), getattr(self, "_init_w", dp(940)) - dp(64 if self.sidebar_collapsed else 218)))
            self._hdr_cache = None
            self._sb_cache = None
            self.refresh_preset_ui()
            self.refresh_header()
            self.refresh_statusbar()

            self.ui_mode = "default"
            self.cfg.data["app"]["ui_mode"] = "default"
            self.cfg.save_soon()
        system.apply_dark_titlebar(root, True)

    # ---- Navigation & Alias Routing --------------------------------------------------------------------------------------
    def show_page(self, key):
        want_voice = key == "voice"
        canonical = "sound" if key == "voice" else ("connect" if key in ("devices", "network") else key)
        if self.current != canonical:
            if canonical not in self.pages:
                try:
                    page = self.page_classes[canonical](self.content, self)
                    page.apply_view(self.advanced)
                    self.pages[canonical] = page
                    self.refresh_preset_ui()
                except Exception:
                    if self._crash_writer is not None:
                        self._crash_writer(*sys.exc_info(), f"show_page({canonical})")
                        self.notify(f"Could not open {TITLES.get(canonical, canonical)}. Details saved to crash log.", "error", 7000)
                        return
                    raise
            if self.current:
                self.pages[self.current].pack_forget()
                if self.current in self.nav:
                    self.nav[self.current].set_active(False)
            self.current = canonical
            self.pages[canonical].pack(fill="both", expand=True)
            if canonical in self.nav:
                self.nav[canonical].set_active(True)
            self.title_label.configure(text=TITLES.get(canonical, canonical.title()))
            try:
                self.pages[canonical].on_show()
            except Exception:
                if self._crash_writer is not None:
                    self._crash_writer(*sys.exc_info(), f"on_show({canonical})")
                    self.notify(f"Error updating {TITLES.get(canonical, canonical)}. Details saved to crash log.", "error", 7000)
                else:
                    raise
        if want_voice and "sound" in self.pages:
            self.pages["sound"].pick_stage("voice")

    def goto_setting(self, key):
        s = sm.BY_KEY[key]
        if s.advanced and not self.advanced:
            self.binder.set(sm.BY_KEY["app.advanced_mode"], True)
            self.notify("Advanced settings were turned on to show this setting.", "info", 5000)
        target = "sound" if s.page == "voice" else ("connect" if s.page in ("devices", "network") else s.page)
        self.show_page(target)
        self.pages[target].focus_setting(s)

    def _on_wheel(self, e, direction=None):
        if self.ui_mode == "minimal":
            return
        w = str(getattr(e, "widget", ""))
        if "popdown" in w or isinstance(getattr(e, "widget", None), tk.Text):
            return
        page = self.pages.get(self.current)
        if page is not None:
            d = direction if direction is not None else (1 if e.delta > 0 else -1)
            page.scroll.scroll_units(-3 * d)

    # ---- Notifications ---------------------------------------------------------------------------------------------------
    def notify(self, msg, level="info", ms=4000):
        color = {"info": T.MUTED, "good": T.GOOD, "warn": T.WARN, "error": T.BAD}.get(level, T.MUTED)
        self.status_left.configure(text=msg, fg=color)
        if self._notice_job:
            try:
                self.root.after_cancel(self._notice_job)
            except Exception:
                pass
        self._notice_job = self.root.after(ms, lambda: self.status_left.configure(text="", fg=T.MUTED))

    def copy(self, text, what="Copied"):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.notify(f"{what}: {text}", "good", 2500)

    def ask_name(self, title, prompt, initial=""):
        d = PromptDialog(self.root, title, prompt, initial)
        self.root.wait_window(d.win)
        return d.result

    # ---- Quick Actions ---------------------------------------------------------------------------------------------------
    def toggle_mute(self):
        muted = self.rx.toggle_pause()
        self.notify("Muted. The phone was asked to pause." if muted else "Unmuted.", "warn" if muted else "good", 2500)
        self.refresh_header()

    def toggle_monitor(self):
        on, msg = self.rx.toggle_monitor()
        self.notify(msg, "good" if on else ("info" if "off" in msg else "error"), 3500)
        self.refresh_header()

    def toggle_record(self):
        on, info = self.rx.toggle_recording()
        if on:
            self.notify(f"Recording to {info}", "good", 4000)
        elif info and not info.startswith("Recording"):
            self.notify(f"Saved to {info}", "good", 6000)
        self.refresh_header()

    def toggle_bypass(self):
        self.proc.fx_bypass = not self.proc.fx_bypass
        self.notify("Effects are off. You are hearing the plain microphone." if self.proc.fx_bypass else "Effects are back on.",
                    "warn" if self.proc.fx_bypass else "good", 3500)
        self.refresh_header()

    # ---- Sound Presets ---------------------------------------------------------------------------------------------------
    def fx_preset_names(self):
        return list(FX_BUILTIN_PRESETS) + sorted(self.cfg.data["user_fx_presets"])

    def fx_modified(self):
        base = fx_preset(self.proc.active_preset, self.cfg.data["user_fx_presets"])
        if base is None:
            return True
        cur = self.proc.export_fx()
        for k, v in base.items():
            c = cur.get(k)
            if isinstance(v, float):
                if abs(c - v) > 1e-3:
                    return True
            elif c != v:
                return True
        return False

    def apply_fx_preset(self, name):
        d = fx_preset(name, self.cfg.data["user_fx_presets"])
        if d is None:
            return
        self.proc.apply_fx(d, name)
        self.binder.persist_fx()
        self.binder.sync_all()
        self.refresh_preset_ui()
        self.notify(f"Sound preset: {name}", "good", 2500)

    def save_fx_preset(self):
        name = self.ask_name("Save sound preset", "Name for your preset:",
                             "" if self.proc.active_preset in FX_BUILTIN_PRESETS else self.proc.active_preset)
        if not name:
            return
        name = pio.clean_name(name)
        if name in FX_BUILTIN_PRESETS:
            self.notify("That name belongs to a built-in preset.", "warn")
            return
        self.cfg.data["user_fx_presets"][name] = self.proc.export_fx()
        self.proc.active_preset = name
        self.binder.persist_fx()
        self.refresh_preset_ui()
        self.notify(f"Saved preset \"{name}\".", "good")

    def delete_fx_preset(self):
        name = self.proc.active_preset
        if name not in self.cfg.data["user_fx_presets"]:
            self.notify("Built-in presets cannot be deleted.", "warn")
            return
        if messagebox.askyesno("Delete preset", f"Delete your preset \"{name}\"?", parent=self.root):
            del self.cfg.data["user_fx_presets"][name]
            self.apply_fx_preset("Default (Studio Clean)")

    def refresh_preset_ui(self):
        names = self.fx_preset_names()
        for c in self.preset_combos:
            c.set_values(names, self.proc.active_preset)
        vnames = self.voice_preset_names()
        for c in self.voice_combos:
            c.set_values(vnames, self.proc.voice_changer.active_preset)
        self.refresh_preset_marks()

    def refresh_preset_marks(self):
        txt = "Changed from preset" if self.fx_modified() else ""
        for m in self.preset_marks:
            m.configure(text=txt)

    # ---- Voice Presets ---------------------------------------------------------------------------------------------------
    def voice_preset_names(self):
        return list(VoiceChanger.BUILTIN_PRESETS) + sorted(self.cfg.data["user_voice_presets"])

    def apply_voice_preset(self, name):
        d = VoiceChanger.BUILTIN_PRESETS.get(name) or self.cfg.data["user_voice_presets"].get(name)
        if d is None:
            return
        self.proc.voice_changer.load(d, name)
        self.binder.persist_voice()
        self.binder.sync_all()
        self.refresh_preset_ui()
        sound_page = self.pages.get("sound")
        if sound_page is not None and hasattr(sound_page, "sync_voice"):
            sound_page.sync_voice()
        self.notify(f"Voice preset: {name}", "good", 2500)

    # ---- Cat Voice Preview -----------------------------------------------------------------------------------------------
    def cat_preview_visible(self):
        return bool(self.cfg.data["app"].get("show_cat_preview", False))

    def set_cat_preview_visible(self, visible):
        flag = bool(visible)
        self.cfg.data["app"]["show_cat_preview"] = flag
        self.cfg.save_soon()
        if not flag:
            self.rx.stop_cat_preview()
            self._close_cat_menu()
        self.refresh_cat_ui()

    def refresh_cat_ui(self):
        dash = self.pages.get("dashboard")
        if dash is not None and hasattr(dash, "sync_cat_preview"):
            dash.sync_cat_preview()
        sound_page = self.pages.get("sound")
        if sound_page is not None and hasattr(sound_page, "sync_cat_preview"):
            sound_page.sync_cat_preview()
        settings_page = self.pages.get("settings")
        if settings_page is not None and hasattr(settings_page, "sync_cat_toggle"):
            settings_page.sync_cat_toggle()

    def preview_cat_voice(self):
        ok, msg = self.rx.play_cat_preview()
        if not ok:
            self.notify(msg or "Could not preview cat sound.", "error", 5000)
        dash = self.pages.get("dashboard")
        if dash is not None and hasattr(dash, "cat_btn") and self.cat_preview_visible():
            dash.cat_btn.set_playing(ok and self.rx.preview_active)

    def stop_cat_preview(self):
        self.rx.stop_cat_preview()
        dash = self.pages.get("dashboard")
        if dash is not None and hasattr(dash, "cat_btn"):
            dash.cat_btn.set_playing(False)

    def upload_cat_wav(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Choose custom cat sound (.wav)",
            filetypes=[("WAV audio", "*.wav"), ("All files", "*.*")],
        )
        if not path:
            return
        ok, msg = self.rx.set_cat_preview_wav(path)
        if ok:
            self.refresh_cat_ui()
            self.notify(f"Cat preview sound set to {msg}.", "good", 4000)
        else:
            self.notify(f"Could not load WAV: {msg}", "error", 6000)

    def reset_cat_wav(self):
        ok, msg = self.rx.set_cat_preview_wav("")
        if ok:
            self.refresh_cat_ui()
            self.notify("Cat preview reset to built-in meow.", "good", 3000)
        else:
            self.notify(f"Could not reset cat sound: {msg}", "error", 5000)

    def _close_cat_menu(self):
        pop = self._cat_menu
        self._cat_menu = None
        if pop is not None:
            try:
                if pop.winfo_exists():
                    pop.destroy()
            except Exception:
                pass

    def show_cat_menu(self, anchor_widget, event=None):
        self._close_cat_menu()
        pop = create_toplevel(self.root, fg_color=T.SURFACE)
        self._cat_menu = pop
        try:
            pop.wm_overrideredirect(True)
        except Exception:
            pass
        try:
            pop.transient(self.root)
            pop.attributes("-topmost", True)
        except Exception:
            pass
        box = SurfaceBox(pop, bg=T.SURFACE, border=T.BORDER_HI, corner=8)
        box.pack(fill="both", expand=True)

        def run_item(fn):
            self._close_cat_menu()
            fn()

        def add_item(text, fn, fg=None):
            row = tk.Label(
                box,
                text=text,
                bg=T.SURFACE,
                fg=fg or T.TEXT,
                font=font(9),
                anchor="w",
                padx=dp(12),
                pady=dp(6),
                cursor="hand2",
            )
            row.pack(fill="x", padx=dp(2), pady=dp(1))
            row.bind("<Enter>", lambda _e, r=row: r.configure(bg=T.SURFACE3))
            row.bind("<Leave>", lambda _e, r=row: r.configure(bg=T.SURFACE))
            row.bind("<Button-1>", lambda _e, cb=fn: run_item(cb))

        add_item("Preview meow", self.preview_cat_voice)
        if self.rx.preview_active:
            add_item("Stop preview", self.stop_cat_preview, fg=T.WARN)
        add_item("Upload custom WAV...", self.upload_cat_wav)
        _label, is_custom = self.rx.cat_preview_info()
        if is_custom:
            add_item("Use default cat", self.reset_cat_wav, fg=T.MUTED)

        pop.bind("<Escape>", lambda _e: self._close_cat_menu())
        pop.bind("<FocusOut>", lambda _e: self._close_cat_menu())
        try:
            pop.update_idletasks()
            vx, vy, vw, vh = screen_bounds(pop)
            ww = max(dp(168), pop.winfo_reqwidth())
            wh = max(dp(60), pop.winfo_reqheight())
            ax = getattr(event, "x_root", None)
            ay = getattr(event, "y_root", None)
            if not isinstance(ax, int) or not isinstance(ay, int):
                ax = anchor_widget.winfo_rootx()
                ay = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + dp(4)
            x = max(vx + dp(6), min(ax, vx + vw - ww - dp(6)))
            y = max(vy + dp(6), min(ay, vy + vh - wh - dp(6)))
            pop.geometry(f"+{x}+{y}")
            pop.focus_set()
        except Exception:
            pass

    # ---- Preset Import / Export ------------------------------------------------------------------------------------------
    def export_preset(self, kind):
        if kind == "fx":
            name, params = self.proc.active_preset, self.proc.export_fx()
        else:
            vc = self.proc.voice_changer
            name, params = vc.active_preset, vc.export()
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                                            initialfile=f"{pio.clean_name(name, 'preset')}.json",
                                            filetypes=[("PhoneMic preset", "*.json")], title="Export preset")
        if path:
            self._write_text(path, pio.dumps(pio.export_preset(kind, name, params)), "Preset exported.")

    def export_all_presets(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json", initialfile="phonemic_presets.json",
                                            filetypes=[("PhoneMic presets", "*.json")], title="Export all my presets")
        if path:
            self._write_text(path, pio.dumps(pio.export_bundle(self.cfg.data["user_fx_presets"], self.cfg.data["user_voice_presets"])),
                             "All your presets were exported.")

    def _write_text(self, path, text, done):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.notify(done, "good")
        except OSError as e:
            self.notify(f"Could not save the file: {e.strerror or e}", "error", 7000)

    def import_presets(self):
        paths = filedialog.askopenfilenames(parent=self.root, filetypes=[("PhoneMic presets", "*.json")], title="Import presets")
        for path in paths or ():
            try:
                with open(path, "rb") as f:
                    data = f.read(pio.MAX_BYTES + 1)
            except OSError as e:
                self.notify(f"Could not read the file: {e.strerror or e}", "error", 7000)
                continue
            self.import_preset_text(data)

    def import_preset_text(self, data):
        try:
            items = pio.parse(data)
        except pio.PresetError as e:
            self.notify(str(e), "error", 8000)
            return []
        added = pio.import_items(self.cfg.data["user_fx_presets"], self.cfg.data["user_voice_presets"], items)
        self.cfg.save_soon()
        self.refresh_preset_ui()
        names = ", ".join(f"\"{n}\"" for _, n in added[:3]) + (f" and {len(added) - 3} more" if len(added) > 3 else "")
        self.notify(f"Imported {names}.", "good", 6000)
        return [n for _, n in added]

    # ---- Virtual Microphone (Linux PipeWire / PulseAudio) ----------------------------------------------------------------
    def ensure_virtual_mic(self, quiet_if_active=False):
        ok, msg = self.rx.ensure_virtual_mic()
        self.sync_output_devices()
        if ok:
            if not quiet_if_active or "Created" in msg:
                self.notify(msg, "good", 4500)
        else:
            self.notify(msg, "warn" if "already" in msg.lower() else "error", 5500)
        return ok

    def remove_virtual_mic(self):
        ok, msg = self.rx.remove_virtual_mic(session_only=False)
        self.sync_output_devices()
        self.notify(msg, "good" if ok else "error", 4500)
        return ok

    # ---- Firewall --------------------------------------------------------------------------------------------------------
    def refresh_firewall_async(self):
        if self.fw_busy:
            return
        self.fw_busy = True
        port = self.cfg.data["network"]["port"]

        def work():
            ok, fw_label, _detail = system.firewall_summary(port)
            self.fw_state, self.fw_label, self.fw_busy = ok, fw_label, False

        threading.Thread(target=work, name="PM-FwCheck", daemon=True).start()

    def fix_firewall(self):
        port = self.cfg.data["network"]["port"]
        self.fw_state = None
        self.fw_label = ""
        self.notify("Configuring firewall...", "info", 6000)

        def work():
            launched, msg = system.configure_firewall(port)
            self.post(lambda: self.notify(msg, "good" if launched else "error", 7000))
            time.sleep(4.0 if system.IS_WIN else 0.1)
            ok, fw_label, _detail = system.firewall_summary(port)
            self.fw_busy = False
            self.fw_state, self.fw_label = ok, fw_label

        self.fw_busy = True
        threading.Thread(target=work, name="PM-FwFix", daemon=True).start()

    # ---- Diagnostics Text ------------------------------------------------------------------------------------------------
    def diagnostics_text(self):
        import platform
        import sys
        rx = self.rx
        vm = virtual_mic.status(rx.devices)
        lines = [f"{APP_NAME} {VERSION}", f"Python {sys.version.split()[0]} on {platform.platform()}",
                 f"Settings file: {self.cfg.filepath}", f"Audio backend: {rx.api or 'none'}",
                 f"Output: {rx.main_dev.name if rx.main_dev else 'none'} (open: {rx.main.active}, error: {rx.main.error or 'none'})",
                 f"Virtual mic: {vm.detail}",
                 f"Network: port {self.cfg.data['network']['port']}, UDP error: {rx.net.udp_error or 'none'}, "
                 f"TCP error: {rx.net.tcp_error or 'none'}, firewall rules: {self.fw_label or self.fw_state}",
                 "Addresses: " + ", ".join(i.label() for i in rx.netinfo.get()),
                 "Output devices: " + "; ".join(f"{d.name} [{d.api}]" for d in rx.devices),
                 f"State: {rx.state()}, packets {rx.stats.packets}, lost {rx.stats.lost}, concealed {rx.stats.plc_frames}, "
                 f"jitter {rx.stats.jitter_ms:.1f} ms, buffer {rx.jb.depth_ms:.0f}/{rx.jb.target_ms:.0f} ms",
                 f"Preset: {self.proc.active_preset} (changed: {self.fx_modified()}), voice: {self.proc.voice_changer.active_preset}",
                 f"Tray icon: available {self.tray.available}, running {self.tray.running}; shortcuts: available {self.hotkeys.available}, "
                 f"{len(self.hotkeys.bindings)} set",
                 "", "Recent events:", rx.log.text()]
        return "\n".join(lines)

    # ---- Periodic Updates ------------------------------------------------------------------------------------------------
    def refresh_header(self):
        rx = self.rx
        state = rx.state()
        color, text = _state_style(state)
        if state == "error":
            text = "Port in use" if "unavailable" in rx.net.udp_error else text
        silent = state == "streaming" and rx.gate_closed
        if silent:
            color, text = T.WARN, "Silent"
        rec_sec = int(rx.recorder.seconds) if rx.recorder.active else -1
        best_ip = rx.netinfo.best_ip()
        key = (color, text, silent, rx.paused, rx.monitoring, self.proc.fx_bypass, rec_sec, best_ip, rx.client_ip)
        if key == self._hdr_cache:
            return
        self._hdr_cache = key

        self.chip_dot.configure(fg=color)
        self.chip_text.configure(text=text)
        tips = {"waiting": f"Waiting for your phone ({best_ip})", "streaming": f"Streaming from {rx.client_ip}",
                "muted": "Muted", "lost": "Connection lost", "error": "Cannot listen: " + (rx.net.udp_error or "network error")}
        self.tray.set_state("silent" if silent else state,
                            "PhoneMic Receiver: " + ("Silent, " + tips["streaming"] if silent else tips[state]))
        self.btn_mute.set_text("Unmute" if rx.paused else "Mute")
        self.btn_mute.set_style("danger" if rx.paused else "normal")
        self.btn_monitor.set_text("Monitor on" if rx.monitoring else "Monitor")
        self.btn_monitor.set_style("active" if rx.monitoring else "normal")
        self.btn_fx.set_text("Effects bypassed" if self.proc.fx_bypass else "Effects on")
        self.btn_fx.set_style("warn" if self.proc.fx_bypass else "blue")
        if rx.recorder.active:
            self.btn_record.set_text(f"Recording {fmt_time(rx.recorder.seconds)}")
            self.btn_record.set_style("rec")
        else:
            self.btn_record.set_text("Record")
            self.btn_record.set_style("normal")

    def refresh_statusbar(self):
        rx = self.rx
        dev = rx.main_dev.name if rx.main_dev else "no output device"
        busy = int(round(self.proc.dsp_ms / 10.0 * 100.0))
        lat_ms = int(round(rx.latency_estimate_ms()))
        port = self.cfg.data["network"]["port"]
        best_ip = rx.netinfo.best_ip()
        left_empty = not self.status_left.cget("text")
        key = (dev, busy, lat_ms, port, self.sidebar_collapsed, best_ip, left_empty)
        if key == self._sb_cache:
            return
        self._sb_cache = key
        if left_empty:
            self.status_left.configure(text=f"Output: {dev}", fg=T.MUTED)
        self.status_right.configure(text=f"DSP load {busy}%     Latency ~{lat_ms} ms")
        self.side_state.configure(
            text=f":{port}" if self.sidebar_collapsed else f"{best_ip}\nPort {port}",
            anchor="center" if self.sidebar_collapsed else "w",
            justify="center" if self.sidebar_collapsed else "left",
        )

    def tick(self):
        fps = max(5, int(self.cfg.data["app"]["ui_fps"] or 30))
        delay = int(1000 / fps)
        try:
            if self.root.state() in ("iconic", "withdrawn"):
                self.proc.viz_active = False
                self.root.after(500, self.tick)
                return

            if self.ui_mode == "minimal" and self.minimal_view is not None:
                self.proc.viz_active = True
                self.minimal_view.refresh_fast()
                now = time.monotonic()
                if now - self._slow_t > 0.25:
                    self._slow_t = now
                    self.minimal_view.refresh_controls()
            else:
                page = self.pages.get(self.current)
                self.proc.viz_active = self.current == "dashboard"
                now = time.monotonic()
                if page is not None:
                    page.refresh_fast()
                if now - self._slow_t > 0.25:
                    self._slow_t = now
                    self.refresh_header()
                    self.refresh_statusbar()
                    if page is not None:
                        page.refresh_slow()
        except Exception as e:      # noqa: BLE001
            key = repr(e)
            if key not in self._err_seen:
                self._err_seen.add(key)
                self.rx.log.error(f"UI error: {key}")
        self.root.after(delay, self.tick)

    def on_close(self):
        if self.cfg.data["app"]["close_to_tray"] and self.tray.running:
            self.hide_window()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.notify("PhoneMic Receiver is still running here. Right-click the icon to quit.")
            return
        self.quit_app()

    def quit_app(self):
        if getattr(self, "_quitting", False):
            return
        self._quitting = True
        try:
            if self.root.state() == "normal":
                geo_key = "minimal_geometry" if self.ui_mode == "minimal" else "window_geometry"
                self.cfg.data["app"][geo_key] = self.root.winfo_geometry()
        except Exception:
            pass
        self.hotkeys.shutdown()
        self.tray.stop()
        if self.stop_instance:
            self.stop_instance()
        self.rx.stop()
        self.cfg.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ==============================================================================
# STUDIO HOME DASHBOARD
# ==============================================================================
class TelemetryTile(_FrameBase):
    """OBS-style compact matte telemetry cell with dot, label, bold numeric value, and rounded ProgressBar."""

    def __init__(self, master, label, accent=None):
        if HAS_CTK:
            super().__init__(master, fg_color=T.SURFACE2, corner_radius=dp(8), border_width=1, border_color=T.BORDER)
        else:
            super().__init__(master, bg=T.SURFACE2, highlightthickness=1, highlightbackground=T.BORDER, bd=0)
        self._text = "-"
        self._frac = 0.0
        self._color = accent or T.ACCENT
        self._last = None

        top = tk.Frame(self, bg=T.SURFACE2)
        top.pack(fill="x", padx=dp(9), pady=(dp(6), dp(1)))
        self.dot = tk.Label(top, text="\u25cf", bg=T.SURFACE2, fg=self._color, font=font(7))
        self.dot.pack(side="left", padx=(0, dp(4)))
        tk.Label(top, text=label, bg=T.SURFACE2, fg=T.DIM, font=font(8), anchor="w").pack(side="left", fill="x")

        self.val = tk.Label(self, text="-", bg=T.SURFACE2, fg=T.DIM, font=font(13, "bold", True), anchor="w")
        self.val.pack(fill="x", padx=dp(9), pady=(0, dp(3)))

        self.bar = ProgressBar(self, height=4, color=self._color, bg=T.SURFACE3, corner=2)
        self.bar.pack(fill="x", padx=dp(9), pady=(0, dp(6)))

    def set(self, text, frac=0.0, color=None):
        c = color or self._color
        f = min(1.0, max(0.0, float(frac)))
        key = (text, round(f, 2), c)
        if key == self._last:
            return
        self._last = key
        self._text, self._frac, self._color = text, f, c
        self.val.configure(text=text, fg=c if text != "-" else T.DIM)
        self.dot.configure(fg=c)
        self.bar.set_progress(f, c)


class DashboardPage(Page):
    QUICK_FX = (
        ("smart_noise_cancel", "Noise", "active"),
        ("gate_enabled", "Gate", "active"),
        ("eq_enabled", "EQ", "blue"),
        ("comp_enabled", "Comp", "active"),
        ("deess_enabled", "De-ess", "blue"),
        ("vc.enabled", "Voice FX", "blue"),
    )

    def build(self):
        app, b = self.app, self.body
        gap = dp(10)
        self._hero_cols = None
        self._fx_wide = None
        self._layout_cols = None
        self._hero_job = None
        self._pending_hero_w = None
        self._fx_job = None
        self._pending_fx_w = None
        self._reflow_job = None
        self._pending_reflow_w = None
        self._last_read_text = None
        self._last_slow_key = None
        self.dev_map = {}

        # ---- Row 0: Connection & Quick Output Bar (NVIDIA Broadcast clarity) ---------------------------------
        hero = Card(b, pad=12, accent_border=T.BORDER_HI)
        hero.pack(fill="x", pady=(0, gap))
        self.hero_body = hero.body

        self.h_left = h_left = tk.Frame(hero.body, bg=T.SURFACE)

        top_line = tk.Frame(h_left, bg=T.SURFACE)
        top_line.pack(fill="x")
        self.hero_title = tk.Label(top_line, text="", bg=T.SURFACE, fg=T.TEXT, font=font(17, "bold", True), anchor="w")
        self.hero_title.pack(side="left")

        ip_pill = SurfaceBox(top_line, bg=T.SURFACE2, border=T.BORDER, corner=7)
        ip_pill.pack(side="left", padx=(dp(10), dp(6)))
        self.hero_ip = tk.Label(ip_pill, text="", bg=T.SURFACE2, fg=T.ACCENT_HI, font=font(11, "bold", True),
                                cursor="hand2", padx=dp(8), pady=dp(2))
        self.hero_ip.pack(side="left")
        self.hero_ip.bind("<Button-1>", lambda e: app.copy(app.rx.netinfo.best_ip(), "Copied IP"))
        Tooltip(self.hero_ip, "Click to copy this PC IP address")
        FlatButton(top_line, "Scan QR", self._open_qr, style="active", size=8, padx=8, pady=2, corner=6).pack(side="left")

        self.hero_sub = autowrap(tk.Label(h_left, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left",
                                          wraplength=dp(320)))
        self.hero_sub.pack(fill="x", pady=(dp(3), 0))
        self.hero_alt = tk.Label(h_left, text="", bg=T.SURFACE, fg=T.DIM, font=font(8), anchor="w")
        self.hero_alt.pack(fill="x", pady=(dp(1), 0))

        self.h_right = h_right = tk.Frame(hero.body, bg=T.SURFACE)
        out_head = tk.Frame(h_right, bg=T.SURFACE)
        out_head.pack(fill="x")
        tk.Label(out_head, text="OUTPUT DEVICE", bg=T.SURFACE, fg=T.DIM, font=font(8, "bold")).pack(side="left")
        FlatButton(out_head, "Tone", app.rx.play_test_tone, style="normal", size=8, padx=7, pady=1, corner=6).pack(side="right")

        self.out_combo = Combo(h_right, [], width=25, command=self._pick_output)
        self.out_combo.pack(anchor="e", pady=(dp(3), dp(2)))
        self.hero_route_hint = tk.Label(h_right, text="", bg=T.SURFACE, fg=T.DIM, font=font(8), anchor="e")
        self.hero_route_hint.pack(fill="x")

        self._layout_hero(dp(700))
        hero.body.bind("<Configure>", lambda e: self._schedule_hero(e.width), add="+")

        # ---- Row 1: Responsive Stage Grid (Two-Column Zero-Scroll <-> Stacked Mobile/Narrow Reflow) ----------
        self.stage_grid = tk.Frame(b, bg=T.BG)
        self.stage_grid.pack(fill="both", expand=True)

        self.col_left = tk.Frame(self.stage_grid, bg=T.BG)
        self.col_right = tk.Frame(self.stage_grid, bg=T.BG)

        # ---- Left Column (~58%): Centerpiece Signal Monitor + Quick FX Stage Rack (Wave Link / Sonar) --------
        lv = Card(self.col_left, "Signal Monitor", pad=12)
        lv.pack(fill="both", expand=True)

        ctrl_head = tk.Frame(lv.header, bg=T.SURFACE)
        ctrl_head.pack(side="right")
        mode = app.cfg.data["visualizer_mode"]
        mode = mode if mode in ("spectrum", "pills", "scope") else ("scope" if "osc" in mode else "spectrum")
        self.viz_seg = Segmented(ctrl_head, [("spectrum", "Spectrum"), ("pills", "Pill Bars"), ("scope", "Waveform")],
                                 mode, self._viz_mode, bg=T.SURFACE, size=8)
        self.viz_seg.pack(side="right")

        read_row = tk.Frame(lv.body, bg=T.SURFACE)
        read_row.pack(fill="x", pady=(0, dp(4)))
        self.read_label = tk.Label(read_row, text="No signal", bg=T.SURFACE, fg=T.MUTED, font=font(9, "normal", True), anchor="w")
        self.read_label.pack(side="left", fill="x", expand=True)
        tk.Label(read_row, text="Click meter to clear clip", bg=T.SURFACE, fg=T.DIM, font=font(8), anchor="e").pack(side="right")

        self.meter = LevelMeter(lv.body, height=42)
        self.meter.pack(fill="x", pady=(0, dp(6)))

        self.fx_bar = fx_bar = tk.Frame(lv.body, bg=T.SURFACE)
        fx_bar.pack(side="bottom", fill="x")
        tk.Frame(lv.body, height=1, bg=T.BORDER).pack(side="bottom", fill="x", pady=(dp(8), dp(7)))

        self.spectrum = SpectrumView(lv.body, height=144)
        self.spectrum.mode = mode
        self.spectrum.pack(fill="both", expand=True)

        self.fx_lbl = tk.Label(fx_bar, text="QUICK FX", bg=T.SURFACE, fg=T.DIM, font=font(8, "bold"))
        self.fx_pills_wrap = tk.Frame(fx_bar, bg=T.SURFACE)

        self.fx_pills = {}
        self._fx_buttons = []
        for skey, title, on_style in self.QUICK_FX:
            setting = sm.BY_KEY[skey]
            btn = FlatButton(self.fx_pills_wrap, title, command=lambda k=skey: self._toggle_fx(k),
                             style=on_style if app.binder.get(setting) else "ghost",
                             size=8, padx=7, pady=3, corner=6)
            Tooltip(btn, f"Toggle {setting.label} (advanced tweaks live in Audio Studio)")
            self.fx_pills[skey] = (btn, on_style)
            self._fx_buttons.append(btn)
            app.binder.listen(skey, lambda v, k=skey: self._paint_fx_pill(k, v))

        self.fx_studio_btn = FlatButton(fx_bar, "Studio \u2192", lambda: app.show_page("sound"),
                                        style="ghost", size=8, padx=7, pady=3, corner=6)
        self._layout_fx(dp(560))
        fx_bar.bind("<Configure>", lambda e: self._schedule_fx(e.width), add="+")

        self.peak_s, self.hold, self.hold_t, self.clip_until = -80.0, -80.0, 0.0, 0.0
        self.last = time.monotonic()
        self.meter.bind("<Button-1>", lambda e: setattr(self, "clip_until", 0.0))

        # ---- Right Column (~42%): Quick Mix + OBS 2x2 Compact Telemetry --------------------------------------
        q = Card(self.col_right, "Quick Mix & Presets", pad=12)
        q.pack(fill="x", pady=(0, gap))
        self.preset_mark = tk.Label(q.header, text="", bg=T.SURFACE, fg=T.WARN, font=font(8, "bold"))
        self.preset_mark.pack(side="right")
        app.preset_marks.append(self.preset_mark)

        pr = tk.Frame(q.body, bg=T.SURFACE)
        pr.pack(fill="x", pady=(0, dp(5)))
        tk.Label(pr, text="Sound preset", bg=T.SURFACE, fg=T.TEXT, font=font(9)).pack(side="left")
        combo = Combo(pr, app.fx_preset_names(), width=20, command=app.apply_fx_preset)
        combo.pack(side="right")
        app.preset_combos.append(combo)

        vr = tk.Frame(q.body, bg=T.SURFACE)
        vr.pack(fill="x", pady=(0, dp(6)))
        self.voice_lbl = tk.Label(vr, text="Voice FX", bg=T.SURFACE, fg=T.BLUE_HI, font=font(9))
        self.voice_lbl.pack(side="left")
        vcombo = Combo(vr, app.voice_preset_names(), width=20, command=app.apply_voice_preset)
        vcombo.set(app.proc.voice_changer.active_preset)
        vcombo.pack(side="right")
        app.voice_combos.append(vcombo)
        self.cat_btn = CatPreviewButton(
            vr,
            command=app.preview_cat_voice,
            menu_command=app.show_cat_menu,
            size=17,
        )
        self.cat_tip = Tooltip(
            self.cat_btn.canvas,
            "Preview cat voice with current effects (right-click for custom WAV)",
        )
        self.sync_cat_preview()

        self.gain_row = SettingRow(q.body, app, sm.BY_KEY["gain"], compact=True)
        self.gain_row.pack(fill="x")
        self.rows = [self.gain_row]

        h = Card(self.col_right, "OBS Telemetry", pad=12)
        h.pack(fill="both", expand=True)

        obs_grid = tk.Frame(h.body, bg=T.SURFACE)
        obs_grid.pack(fill="x")
        obs_grid.grid_columnconfigure(0, weight=1, uniform="t")
        obs_grid.grid_columnconfigure(1, weight=1, uniform="t")

        self.g_latency = TelemetryTile(obs_grid, "Delay", accent=T.GOOD)
        self.g_jitter = TelemetryTile(obs_grid, "Network jitter", accent=T.ACCENT)
        self.g_loss = TelemetryTile(obs_grid, "Packet loss", accent=T.WARN)
        self.g_rate = TelemetryTile(obs_grid, "Bitrate", accent=T.ACCENT)
        self.g_latency.grid(row=0, column=0, sticky="ew", padx=(0, dp(3)), pady=(0, dp(6)))
        self.g_jitter.grid(row=0, column=1, sticky="ew", padx=(dp(3), 0), pady=(0, dp(6)))
        self.g_loss.grid(row=1, column=0, sticky="ew", padx=(0, dp(3)))
        self.g_rate.grid(row=1, column=1, sticky="ew", padx=(dp(3), 0))

        foot = tk.Frame(h.body, bg=T.SURFACE)
        foot.pack(fill="x", pady=(dp(8), 0))
        foot.grid_columnconfigure(0, weight=1, uniform="f")
        foot.grid_columnconfigure(1, weight=1, uniform="f")

        def mini_stat(parent, row_i, col_i, title):
            cell = tk.Frame(parent, bg=T.SURFACE)
            cell.grid(row=row_i, column=col_i, sticky="ew", padx=(0 if col_i == 0 else dp(6), dp(6) if col_i == 0 else 0), pady=dp(1))
            tk.Label(cell, text=title, bg=T.SURFACE, fg=T.DIM, font=font(8)).pack(side="left")
            v = tk.Label(cell, text="-", bg=T.SURFACE, fg=T.MUTED, font=font(8, "bold", True))
            v.pack(side="right")
            return v

        self.v_buffer = mini_stat(foot, 0, 0, "Buffer")
        self.v_dsp = mini_stat(foot, 0, 1, "DSP load")
        self.v_time = mini_stat(foot, 1, 0, "Session")
        self.v_lost = mini_stat(foot, 1, 1, "Concealed")
        self.v_under = mini_stat(foot, 2, 0, "Underruns")

        self.sync_outputs()
        self._reflow(dp(680))
        self.stage_grid.bind("<Configure>", lambda e: self._schedule_reflow(e.width), add="+")

    def _schedule_hero(self, width_px):
        if not width_px or width_px < 40:
            return
        self._pending_hero_w = width_px
        if self._hero_job:
            try:
                self.hero_body.after_cancel(self._hero_job)
            except Exception:
                pass
        self._hero_job = self.hero_body.after(16, self._run_hero)

    def _run_hero(self):
        self._hero_job = None
        if self.hero_body.winfo_exists() and self._pending_hero_w is not None:
            self._layout_hero(self._pending_hero_w, hysteresis=True)

    def _layout_hero(self, width_px=None, hysteresis=False):
        if width_px is None:
            width_px = self.hero_body.winfo_width()
        if not width_px or width_px < 40:
            return
        bp = dp(620)
        if hysteresis and self._hero_cols is not None:
            want = (1 if width_px < bp + dp(10) else 2) if self._hero_cols == 1 else (1 if width_px < bp - dp(10) else 2)
        else:
            want = 1 if width_px < bp else 2
        if want == self._hero_cols:
            return
        self._hero_cols = want
        self.h_left.grid_forget()
        self.h_right.grid_forget()
        if want == 2:
            self.hero_body.grid_columnconfigure(0, weight=1)
            self.hero_body.grid_columnconfigure(1, weight=0)
            self.h_left.grid(row=0, column=0, sticky="new", padx=(0, dp(12)), pady=0)
            self.h_right.grid(row=0, column=1, sticky="ne", padx=0, pady=0)
            self.out_combo.pack(anchor="e", pady=(dp(3), dp(2)))
            self.hero_route_hint.configure(anchor="e")
        else:
            self.hero_body.grid_columnconfigure(0, weight=1)
            self.hero_body.grid_columnconfigure(1, weight=0)
            self.h_left.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, dp(8)))
            self.h_right.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
            self.out_combo.pack(anchor="w", pady=(dp(3), dp(2)))
            self.hero_route_hint.configure(anchor="w")

    def _schedule_fx(self, width_px):
        if not width_px or width_px < 40:
            return
        self._pending_fx_w = width_px
        if self._fx_job:
            try:
                self.fx_bar.after_cancel(self._fx_job)
            except Exception:
                pass
        self._fx_job = self.fx_bar.after(16, self._run_fx)

    def _run_fx(self):
        self._fx_job = None
        if self.fx_bar.winfo_exists() and self._pending_fx_w is not None:
            self._layout_fx(self._pending_fx_w, hysteresis=True)

    def _layout_fx(self, width_px=None, hysteresis=False):
        if width_px is None:
            width_px = self.fx_bar.winfo_width()
        if not width_px or width_px < 40:
            return
        bp = dp(520)
        if hysteresis and self._fx_wide is not None:
            wide = (width_px >= bp + dp(10)) if not self._fx_wide else (width_px >= bp - dp(10))
        else:
            wide = width_px >= bp
        if wide == self._fx_wide:
            return
        self._fx_wide = wide
        self.fx_lbl.grid_forget()
        self.fx_pills_wrap.grid_forget()
        self.fx_studio_btn.grid_forget()
        for b in self._fx_buttons:
            b.grid_forget()
        if wide:
            self.fx_bar.grid_columnconfigure(0, weight=0)
            self.fx_bar.grid_columnconfigure(1, weight=1)
            self.fx_bar.grid_columnconfigure(2, weight=0)
            self.fx_lbl.grid(row=0, column=0, sticky="w", padx=(0, dp(8)))
            self.fx_pills_wrap.grid(row=0, column=1, sticky="w")
            self.fx_studio_btn.grid(row=0, column=2, sticky="e")
            for i, b in enumerate(self._fx_buttons):
                b.grid(row=0, column=i, padx=(0 if i == 0 else dp(4), 0), pady=0)
        else:
            self.fx_bar.grid_columnconfigure(0, weight=1)
            self.fx_bar.grid_columnconfigure(1, weight=0)
            self.fx_bar.grid_columnconfigure(2, weight=0)
            self.fx_lbl.grid(row=0, column=0, sticky="w")
            self.fx_studio_btn.grid(row=0, column=2, sticky="e")
            self.fx_pills_wrap.grid(row=1, column=0, columnspan=3, sticky="w", pady=(dp(6), 0))
            for i, b in enumerate(self._fx_buttons):
                r, c = divmod(i, 3)
                b.grid(row=r, column=c, sticky="w", padx=(0 if c == 0 else dp(4), 0), pady=(0 if r == 0 else dp(4), 0))

    def _schedule_reflow(self, width_px):
        if not width_px or width_px < 40:
            return
        self._pending_reflow_w = width_px
        if self._reflow_job:
            try:
                self.stage_grid.after_cancel(self._reflow_job)
            except Exception:
                pass
        self._reflow_job = self.stage_grid.after(16, self._run_reflow)

    def _run_reflow(self):
        self._reflow_job = None
        if self.stage_grid.winfo_exists() and self._pending_reflow_w is not None:
            self._reflow(self._pending_reflow_w, hysteresis=True)

    def _reflow(self, width_px=None, hysteresis=False):
        if width_px is None:
            width_px = self.stage_grid.winfo_width()
        if not width_px or width_px < 40:
            return
        bp = dp(620)
        if hysteresis and self._layout_cols is not None:
            want = (1 if width_px < bp + dp(10) else 2) if self._layout_cols == 1 else (1 if width_px < bp - dp(10) else 2)
        else:
            want = 1 if width_px < bp else 2
        if want == self._layout_cols:
            return
        self._layout_cols = want
        self.col_left.grid_forget()
        self.col_right.grid_forget()
        if want == 2:
            self.stage_grid.grid_columnconfigure(0, weight=14, uniform="dash")
            self.stage_grid.grid_columnconfigure(1, weight=10, uniform="dash")
            self.col_left.grid(row=0, column=0, sticky="nsew", padx=(0, dp(5)), pady=0)
            self.col_right.grid(row=0, column=1, sticky="nsew", padx=(dp(5), 0), pady=0)
        else:
            self.stage_grid.grid_columnconfigure(0, weight=1, uniform="")
            self.stage_grid.grid_columnconfigure(1, weight=0, uniform="")
            self.col_left.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=0, pady=(0, dp(10)))
            self.col_right.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)

    def _toggle_fx(self, key):
        s = sm.BY_KEY[key]
        cur = bool(self.app.binder.get(s))
        self.app.binder.set(s, not cur)

    def _paint_fx_pill(self, key, val):
        pair = self.fx_pills.get(key)
        if pair:
            btn, on_style = pair
            btn.set_style(on_style if bool(val) else "ghost")

    def _paint_all_fx(self):
        for skey, _, _ in self.QUICK_FX:
            self._paint_fx_pill(skey, self.app.binder.get(sm.BY_KEY[skey]))

    def _pick_output(self, name):
        d = self.dev_map.get(name)
        if d:
            self.app.rx.set_output_device(d)
            self.app.sync_output_devices()

    def sync_outputs(self):
        rx = self.app.rx
        pool = system.devices_for_api(rx.devices, rx.api)
        self.dev_map = {d.name: d for d in pool}
        names = list(self.dev_map)
        cur = rx.main_dev.name if rx.main_dev else ""
        self.out_combo.set_values(names, cur)

    def _open_qr(self):
        rx = self.app.rx
        port = self.app.cfg.data["network"]["port"]
        payload = f"phonemic://{rx.netinfo.best_ip()}:{port}?t=UDP"
        QRPopupDialog(self.app, payload)

    def _viz_mode(self, mode):
        self.spectrum.set_mode(mode)
        self.app.cfg.data["visualizer_mode"] = mode
        self.app.cfg.save_soon()

    def sync_cat_preview(self):
        if not hasattr(self, "cat_btn"):
            return
        if self.app.cat_preview_visible():
            if self.cat_btn.winfo_manager() != "pack":
                self.cat_btn.pack(side="right", padx=(0, dp(6)))
            self.cat_btn.set_playing(self.app.rx.preview_active)
        else:
            self.cat_btn.set_playing(False)
            self.cat_btn.pack_forget()

    def sync(self):
        self.gain_row.refresh()
        self._paint_all_fx()
        self.sync_outputs()
        self.sync_cat_preview()

    def on_show(self):
        self.sync()
        self.spectrum._build()
        self._last_slow_key = None

    def refresh_fast(self):
        rx, proc = self.app.rx, self.app.proc
        now = time.monotonic()
        dt = min(0.2, now - self.last)
        self.last = now
        previewing = bool(rx.preview_active)
        streaming = rx.state() == "streaming"
        live = streaming or previewing
        if hasattr(self, "cat_btn") and self.app.cat_preview_visible():
            self.cat_btn.set_playing(previewing)
        peak = proc.level_db if live else -80.0
        rms = lin_to_db(proc.level_rms, -80.0) if live else -80.0
        self.peak_s = peak if peak > self.peak_s else max(peak, self.peak_s - 60.0 * dt)
        if self.peak_s >= self.hold:
            self.hold, self.hold_t = self.peak_s, now
        elif now - self.hold_t > 1.2:
            self.hold = max(self.peak_s, self.hold - 30.0 * dt)
        if live and proc.clipped:
            self.clip_until = now + 3.0
        self.meter.update_levels(self.peak_s, rms, self.hold, now < self.clip_until)
        if live:
            self.spectrum.feed(proc.analyzer.bands, proc.analyzer.scope)
        else:
            self.spectrum.idle()
        if live:
            prefix = "Preview  \u00b7  " if (previewing and not streaming) else ""
            text = f"{prefix}Peak {self.peak_s:5.1f} dBFS  \u00b7  Avg {rms:5.1f} dBFS"
            if proc.comp_enabled and proc.gain_reduction_db > 0.3:
                text += f"  \u00b7  GR {proc.gain_reduction_db:.1f} dB"
        else:
            text = "No signal"
        if text != self._last_read_text:
            self._last_read_text = text
            self.read_label.configure(text=text)

    def refresh_slow(self):
        app, rx = self.app, self.app.rx
        st = rx.stats
        state = rx.state()
        net = rx.netinfo
        port = app.cfg.data["network"]["port"]
        titles = {"waiting": "Waiting for your phone", "streaming": "Streaming live", "muted": "Muted",
                  "lost": "Connection lost", "error": "Cannot receive audio"}
        silent = state == "streaming" and rx.gate_closed
        hero_txt = "You are silent" if silent else titles[state]
        hero_fg = T.WARN if silent else _state_style(state)[0]

        since = fmt_time(time.monotonic() - st.stream_start) if st.stream_start else "00:00"
        if silent:
            sub = ("Hold your push-to-talk key to speak." if rx.ptt_active and not rx.ptt_held and not rx.hold_mute
                   else "Push-to-mute is held. Release the key to unmute.")
        elif state == "streaming":
            sub = f"Connected from {rx.client_ip} via {rx.transport} ({since})."
        elif state == "muted":
            sub = "Output is muted and the phone was asked to pause. Press Unmute to resume."
        elif state == "lost":
            sub = f"No audio from {rx.client_ip} for {time.monotonic() - st.last_packet:.0f}s. Auto-resumes on reconnect."
        elif state == "error":
            sub = rx.net.udp_error + " Change port in Connections or close the conflicting app."
        else:
            sub = "Open PhoneMic on your phone and scan the QR code or enter the IP."

        best_ip = net.best_ip()
        usb = net.first("USB Tether")
        alt_txt = f"Port {port}" + (f"  ·  USB tether {usb}" if usb else "")
        if rx.main.error:
            route_txt, route_fg = f"Device error: {rx.main.error}", T.BAD
        elif rx.main.active and rx.main_dev:
            route_txt, route_fg = f"{rx.main_dev.api}  ·  {rx.main.latency_ms:.0f} ms card delay", T.DIM
        else:
            route_txt, route_fg = "No output stream open", T.WARN

        live = state in ("streaming", "muted")
        lat = rx.latency_estimate_ms()
        j = st.jitter_ms
        lp = st.loss_pct
        rate = st.bitrate_kbps

        self.g_latency.set(f"{lat:.0f} ms", lat / 250.0, T.GOOD if lat < 90 else T.WARN if lat < 160 else T.BAD)
        self.g_jitter.set(f"{j:.1f} ms" if live else "-", j / 60.0 if live else 0, T.GOOD if j < 15 else T.WARN if j < 40 else T.BAD)
        self.g_loss.set(f"{lp:.2f} %" if live else "-", lp / 5.0 if live else 0, T.GOOD if lp < 0.5 else T.WARN if lp < 3 else T.BAD)
        self.g_rate.set(f"{rate:.0f} kbps" if live else "-", rate / 1000.0 if live else 0, T.ACCENT)

        buf_txt = f"{rx.jb.depth_ms:.0f}/{rx.jb.target_ms:.0f} ms"
        load = app.proc.dsp_ms / 10.0 * 100.0
        load_txt = f"{load:.1f}%"
        load_fg = T.GOOD if load < 25 else T.WARN if load < 60 else T.BAD
        under_txt = str(rx.main.starved) if live else "-"
        time_txt = fmt_time(time.monotonic() - st.stream_start) if st.stream_start else "-"
        lost_txt = f"{st.lost}/{st.plc_frames}" if live else "-"

        slow_key = (hero_txt, hero_fg, sub, best_ip, alt_txt, route_txt, route_fg,
                    buf_txt, load_txt, load_fg, under_txt, time_txt, lost_txt)
        if slow_key == self._last_slow_key:
            return
        self._last_slow_key = slow_key

        self.hero_title.configure(text=hero_txt, fg=hero_fg)
        self.hero_sub.configure(text=sub)
        self.hero_ip.configure(text=best_ip)
        self.hero_alt.configure(text=alt_txt)
        self.hero_route_hint.configure(text=route_txt, fg=route_fg)
        self.v_buffer.configure(text=buf_txt)
        self.v_dsp.configure(text=load_txt, fg=load_fg)
        self.v_under.configure(text=under_txt)
        self.v_time.configure(text=time_txt)
        self.v_lost.configure(text=lost_txt)
