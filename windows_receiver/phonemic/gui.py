"""Main window, navigation, shared helpers (presets, notifications, search target) and the Dashboard page."""
import re
import time
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from . import system, presets_io as pio, settings_meta as sm, cues
from .hotkeys import HotkeyService, parse_combo
from .tray import TrayIcon
from .bindings import SettingsBinder
from .const import VERSION, APP_NAME
from .dsp import FX_BUILTIN_PRESETS, VoiceChanger, fx_preset, lin_to_db
from .widgets import (T, dp, font, set_scale, apply_styles, apply_accent, init_fonts, autowrap, FlatButton, Segmented, Combo,
                      Card, ScrollFrame, NavButton, LevelMeter, SpectrumView, Tooltip)
from .ui_kit import SettingRow, GaugeRow, SearchBox
from . import icon

NAV = [("dashboard", "Dashboard", "dashboard"), ("sound", "Sound", "sound"), ("voice", "Voice Changer", "voice"),
       ("devices", "Audio Devices", "devices"), ("network", "Network", "network"),
       ("settings", "Settings", "settings"), ("log", "Diagnostics", "log")]

TITLES = {"dashboard": "Dashboard", "sound": "Sound", "voice": "Voice Changer", "devices": "Audio Devices",
          "network": "Network", "settings": "Settings", "log": "Diagnostics", "wizard": "Setup"}

HOTKEY_ACTIONS = ("toggle_mute", "push_to_talk", "push_to_mute", "toggle_monitor", "toggle_record", "toggle_bypass", "show_window")

STATE_STYLE = {
    "waiting": (T.ACCENT, "Waiting for phone"),
    "streaming": (T.GOOD, "Streaming"),
    "muted": (T.WARN, "Muted"),
    "lost": (T.WARN, "Connection lost"),
    "error": (T.BAD, "Network error"),
}


def fmt_time(seconds):
    seconds = int(max(0, seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ==============================================================================
# SMALL DIALOG
# ==============================================================================
class PromptDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt, initial=""):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.configure(bg=T.SURFACE)
        self.resizable(False, False)
        self.transient(parent)
        tk.Label(self, text=prompt, bg=T.SURFACE, fg=T.TEXT, font=font(10), anchor="w").pack(fill="x", padx=dp(18), pady=(dp(16), dp(6)))
        self.var = tk.StringVar(value=initial)
        e = tk.Entry(self, textvariable=self.var, bg=T.SURFACE2, fg=T.TEXT, insertbackground=T.TEXT, relief="flat",
                     font=font(11), width=34, highlightthickness=1, highlightbackground=T.BORDER, highlightcolor=T.ACCENT)
        e.pack(padx=dp(18), ipady=dp(5))
        e.focus_set()
        e.select_range(0, "end")
        row = tk.Frame(self, bg=T.SURFACE)
        row.pack(fill="x", padx=dp(18), pady=dp(16))
        FlatButton(row, "Save", self._ok, style="primary").pack(side="right")
        FlatButton(row, "Cancel", self.destroy, style="normal").pack(side="right", padx=(0, dp(8)))
        e.bind("<Return>", lambda ev: self._ok())
        self.bind("<Escape>", lambda ev: self.destroy())
        try:
            self.update_idletasks()
            x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_rooty() + dp(120)
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
            self.grab_set()
        except Exception:
            pass

    def _ok(self):
        self.result = self.var.get().strip()
        self.destroy()


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
        self.body.pack(fill="both", expand=True, padx=dp(24), pady=(dp(4), dp(24)))
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
# APPLICATION
# ==============================================================================
class App:
    def __init__(self, receiver, start_minimized=False):
        self.rx = receiver
        self.cfg = receiver.config
        self.proc = receiver.processor
        self.root = root = tk.Tk()
        try:
            set_scale(root.winfo_fpixels("1i") / 96.0)
        except Exception:
            pass
        init_fonts(root)
        apply_accent(self.cfg.data["app"]["accent"])           # before any widget exists: colours are read at creation
        root.title(f"{APP_NAME} {VERSION}")
        root.configure(bg=T.BG)
        root.minsize(dp(920), dp(640))
        self._restore_geometry()
        apply_styles(root)
        icon.apply(root)
        if self.cfg.data["app"]["always_on_top"]:
            root.attributes("-topmost", True)

        self.advanced = bool(self.cfg.data["app"]["advanced_mode"])
        self.binder = SettingsBinder(receiver, hooks=self)
        self.binder.listen_any(self._setting_changed)
        self.pages, self.page_classes, self.nav = {}, {}, {}
        self.current = None
        self.preset_combos, self.preset_marks, self.voice_combos = [], [], []
        self.fw_state, self.fw_busy = None, False
        self._slow_t = 0.0
        self._notice_job = None
        self._err_seen = set()
        self.actions_q = queue.Queue()                  # work handed over from other threads (tray, shortcuts, second launch)
        self._tray_hint_shown = False
        self.hotkeys = HotkeyService(self._hk_press, self._hk_hold, log=lambda m: self.rx.log.warn(m))
        self.tray = TrayIcon({"show": lambda: self.post(self.show_window), "mute": lambda: self.post(self.toggle_mute),
                              "monitor": lambda: self.post(self.toggle_monitor), "record": lambda: self.post(self.toggle_record),
                              "bypass": lambda: self.post(self.toggle_bypass), "quit": lambda: self.post(self.quit_app)}, self._tray_state)
        self.stop_instance = system.start_instance_listener(lambda: self.post(self.show_window))

        self._build_shell()
        from .pages import SoundPage, VoicePage, DevicesPage, NetworkPage, SettingsPage, LogPage
        from .wizard import WizardPage
        self.page_classes = {"dashboard": DashboardPage, "sound": SoundPage, "voice": VoicePage, "devices": DevicesPage,
                             "network": NetworkPage, "settings": SettingsPage, "log": LogPage, "wizard": WizardPage}
        self.show_page("dashboard" if self.cfg.data["app"]["first_run_done"] else "wizard")
        self.refresh_preset_ui()
        self.apply_hotkeys()
        self.apply_tray()

        root.bind_all("<MouseWheel>", self._on_wheel)
        root.bind_all("<Button-4>", lambda e: self._on_wheel(e, 1))
        root.bind_all("<Button-5>", lambda e: self._on_wheel(e, -1))
        root.bind("<Control-m>", lambda e: self.toggle_mute())
        root.bind("<Control-e>", lambda e: self.toggle_monitor())
        root.bind("<Control-r>", lambda e: self.toggle_record())
        root.bind("<Control-b>", lambda e: self.toggle_bypass())
        root.bind("<Control-f>", lambda e: self.search.entry.focus_set())
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

    # ---- work from other threads, shortcuts, tray -------------------------------------------------------------------------
    def post(self, fn):
        """Thread-safe: run `fn` on the UI thread soon."""
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
        self.root.after(30, self._pump)            # independent of tick(), so shortcuts stay responsive while minimized

    def _cue(self, kind):
        h = self.cfg.data["hotkeys"]
        if h["enabled"] and h["sound_cues"]:
            cues.play(kind)

    def _hk_press(self, action):                   # runs on the shortcut thread
        self.post(lambda: self.do_action(action))

    def _hk_hold(self, action, down):              # runs on the shortcut thread: flip the gate right away, no UI hop
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
        r.attributes("-topmost", True)                  # the usual trick to pull a window in front of a game
        r.after(150, lambda: r.attributes("-topmost", bool(self.cfg.data["app"]["always_on_top"])))
        r.focus_force()

    def hide_window(self):
        self.root.withdraw()

    # ---- hooks used by the settings binder ---------------------------------------------------------------------------------
    def set_advanced(self, flag):
        self.advanced = bool(flag)
        for page in self.pages.values():
            page.apply_view(self.advanced)

    def set_topmost(self, flag):
        self.root.attributes("-topmost", bool(flag))

    def _setting_changed(self, setting):
        self.refresh_preset_marks()

    # ---- geometry ------------------------------------------------------------------------------------------------------------
    def _restore_geometry(self):
        geo = self.cfg.data["app"]["window_geometry"]
        ok = False
        m = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", geo or "")
        if m:
            w, h, x, y = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            ok = w >= dp(760) and h >= dp(520) and -50 <= x < sw - 150 and -10 <= y < sh - 100
        self.root.geometry(geo if ok else f"{dp(1100)}x{dp(780)}")

    # ---- layout ---------------------------------------------------------------------------------------------------------------
    def _build_shell(self):
        root = self.root
        side = tk.Frame(root, bg=T.SIDEBAR, width=dp(218))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        logo = tk.Frame(side, bg=T.SIDEBAR)
        logo.pack(fill="x", padx=dp(20), pady=(dp(24), dp(20)))
        tk.Label(logo, text="PhoneMic", bg=T.SIDEBAR, fg=T.TEXT, font=font(20, "bold", True)).pack(anchor="w")
        tk.Label(logo, text=f"Receiver {VERSION}", bg=T.SIDEBAR, fg=T.DIM, font=font(9)).pack(anchor="w")
        for key, text, ic in NAV:
            b = NavButton(side, ic, text, lambda k=key: self.show_page(k))
            b.pack(fill="x")
            self.nav[key] = b

        foot = tk.Frame(side, bg=T.SIDEBAR)
        foot.pack(side="bottom", fill="x", padx=dp(18), pady=dp(16))
        tk.Label(foot, text="Settings view", bg=T.SIDEBAR, fg=T.DIM, font=font(9), anchor="w").pack(fill="x", pady=(0, dp(4)))
        adv = sm.BY_KEY["app.advanced_mode"]
        self.view_toggle = Segmented(foot, [(False, "Simple"), (True, "Advanced")], self.advanced,
                                     lambda v: self.binder.set(adv, v, source=self._view_listener), bg=T.SIDEBAR)
        self.view_toggle.pack(anchor="w")
        Tooltip(self.view_toggle, "Simple shows the essentials. Advanced shows every control.")
        self.binder.listen(adv.key, self._view_listener)
        self.side_state = tk.Label(foot, text="", bg=T.SIDEBAR, fg=T.DIM, font=font(9), anchor="w", justify="left")
        self.side_state.pack(fill="x", pady=(dp(14), 0))

        main = tk.Frame(root, bg=T.BG)
        main.pack(side="right", fill="both", expand=True)
        head = tk.Frame(main, bg=T.BG)
        head.pack(fill="x", padx=dp(24), pady=(dp(18), dp(8)))
        self.title_label = tk.Label(head, text="", bg=T.BG, fg=T.TEXT, font=font(22, "bold", True))
        self.title_label.pack(side="left")
        chip = tk.Frame(head, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER)
        chip.pack(side="right")
        self.chip_dot = tk.Label(chip, text="\u25cf", bg=T.SURFACE, fg=T.ACCENT, font=font(11))
        self.chip_dot.pack(side="left", padx=(dp(10), dp(4)), pady=dp(5))
        self.chip_text = tk.Label(chip, text="Starting", bg=T.SURFACE, fg=T.TEXT, font=font(10, "bold"))
        self.chip_text.pack(side="left", padx=(0, dp(12)))

        bar = tk.Frame(main, bg=T.BG)                    # second row: search on the left, quick actions on the right
        bar.pack(fill="x", padx=dp(24), pady=(0, dp(12)))
        self.search = SearchBox(bar, self, width=34)
        self.search.pack(side="left")
        actions = tk.Frame(bar, bg=T.BG)
        actions.pack(side="right")
        self.btn_record = FlatButton(actions, "Record", self.toggle_record, size=9)
        self.btn_monitor = FlatButton(actions, "Monitor", self.toggle_monitor, size=9)
        self.btn_mute = FlatButton(actions, "Mute", self.toggle_mute, size=9)
        self.btn_fx = FlatButton(actions, "Effects on", self.toggle_bypass, size=9)
        for b, tip in ((self.btn_fx, "Switch every effect off to hear the plain microphone, then back on to compare (Ctrl+B)"),
                       (self.btn_mute, "Mute the PC output and tell the phone to pause (Ctrl+M)"),
                       (self.btn_monitor, "Hear the processed voice on your headphones (Ctrl+E)"),
                       (self.btn_record, "Record the audio to a WAV file (Ctrl+R)")):
            b.pack(side="left", padx=(dp(6), 0))
            Tooltip(b, tip)

        status = tk.Frame(main, bg=T.SIDEBAR)
        status.pack(side="bottom", fill="x")
        self.status_left = tk.Label(status, text="", bg=T.SIDEBAR, fg=T.MUTED, font=font(9), anchor="w")
        self.status_left.pack(side="left", padx=dp(16), pady=dp(7))
        self.status_right = tk.Label(status, text="", bg=T.SIDEBAR, fg=T.DIM, font=font(9, "normal", True), anchor="e")
        self.status_right.pack(side="right", padx=dp(16))

        self.content = tk.Frame(main, bg=T.BG)
        self.content.pack(fill="both", expand=True)

    def _view_listener(self, value):
        if self.view_toggle.get() != bool(value):
            self.view_toggle.set(bool(value))

    # ---- navigation ------------------------------------------------------------------------------------------------------------
    def show_page(self, key):
        if self.current == key:
            return
        if self.current:
            self.pages[self.current].pack_forget()
            if self.current in self.nav:
                self.nav[self.current].set_active(False)
        if key not in self.pages:
            self.pages[key] = self.page_classes[key](self.content, self)
            self.pages[key].apply_view(self.advanced)
            self.refresh_preset_ui()                     # combos created by this page show the current preset
        self.current = key
        self.pages[key].pack(fill="both", expand=True)
        if key in self.nav:
            self.nav[key].set_active(True)
        self.title_label.configure(text=TITLES[key])
        self.pages[key].on_show()

    def goto_setting(self, key):
        """Open the page that holds a setting, reveal it, and outline it (search results use this)."""
        s = sm.BY_KEY[key]
        if s.advanced and not self.advanced:
            self.binder.set(sm.BY_KEY["app.advanced_mode"], True)
            self.notify("Advanced settings were turned on to show this setting.", "info", 5000)
        self.show_page(s.page)
        self.pages[s.page].focus_setting(s)

    def _on_wheel(self, e, direction=None):
        """One global wheel handler: scrolls the visible page unless the pointer is over a text box or a dropdown list."""
        w = str(getattr(e, "widget", ""))
        if "popdown" in w or isinstance(getattr(e, "widget", None), tk.Text):
            return
        page = self.pages.get(self.current)
        if page is not None:
            d = direction if direction is not None else (1 if e.delta > 0 else -1)
            page.scroll.scroll_units(-3 * d)

    # ---- notifications -------------------------------------------------------------------------------------------------------------
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
        self.root.wait_window(d)
        return d.result

    # ---- header actions --------------------------------------------------------------------------------------------------------------
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

    # ---- sound presets ----------------------------------------------------------------------------------------------------------------
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
        name = self.ask_name("Save sound preset", "Name for your preset:", "" if self.proc.active_preset in FX_BUILTIN_PRESETS else self.proc.active_preset)
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

    # ---- voice presets -----------------------------------------------------------------------------------------------------------------
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
        page = self.pages.get("voice")
        if page is not None:
            page.sync()
        self.notify(f"Voice preset: {name}", "good", 2500)

    # ---- preset files ------------------------------------------------------------------------------------------------------------------
    def export_preset(self, kind):
        if kind == "fx":
            name, params = self.proc.active_preset, self.proc.export_fx()
        else:
            vc = self.proc.voice_changer
            name, params = vc.active_preset, vc.export()
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json", initialfile=f"{pio.clean_name(name, 'preset')}.json",
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
        """Validate preset file contents and add the presets. Returns the names that were added."""
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

    # ---- firewall -----------------------------------------------------------------------------------------------------------------------
    def refresh_firewall_async(self):
        if self.fw_busy:
            return
        self.fw_busy = True
        port = self.cfg.data["network"]["port"]

        def work():
            ok = system.firewall_rules_ok(port)
            self.fw_state, self.fw_busy = ok, False

        threading.Thread(target=work, name="PM-FwCheck", daemon=True).start()

    def fix_firewall(self):
        port = self.cfg.data["network"]["port"]
        self.fw_state = None
        self.notify("Configuring Windows Firewall...", "info", 6000)

        def work():
            launched, msg = system.configure_firewall(port)
            self.root.after(0, lambda: self.notify(msg, "good" if launched else "error", 7000))
            time.sleep(4.0 if system.IS_WIN else 0.1)
            self.fw_busy = False
            self.fw_state = system.firewall_rules_ok(port)

        self.fw_busy = True
        threading.Thread(target=work, name="PM-FwFix", daemon=True).start()

    # ---- diagnostics ----------------------------------------------------------------------------------------------------------------------
    def diagnostics_text(self):
        import platform
        import sys
        rx = self.rx
        lines = [f"{APP_NAME} {VERSION}", f"Python {sys.version.split()[0]} on {platform.platform()}",
                 f"Settings file: {self.cfg.filepath}", f"Audio backend: {rx.api or 'none'}",
                 f"Output: {rx.main_dev.name if rx.main_dev else 'none'} (open: {rx.main.active}, error: {rx.main.error or 'none'})",
                 f"Network: port {self.cfg.data['network']['port']}, UDP error: {rx.net.udp_error or 'none'}, "
                 f"TCP error: {rx.net.tcp_error or 'none'}, firewall rules: {self.fw_state}",
                 "Addresses: " + ", ".join(i.label() for i in rx.netinfo.get()),
                 "Output devices: " + "; ".join(f"{d.name} [{d.api}]" for d in rx.devices),
                 f"State: {rx.state()}, packets {rx.stats.packets}, lost {rx.stats.lost}, concealed {rx.stats.plc_frames}, "
                 f"jitter {rx.stats.jitter_ms:.1f} ms, buffer {rx.jb.depth_ms:.0f}/{rx.jb.target_ms:.0f} ms",
                 f"Preset: {self.proc.active_preset} (changed: {self.fx_modified()}), voice: {self.proc.voice_changer.active_preset}",
                 f"Tray icon: available {self.tray.available}, running {self.tray.running}; shortcuts: available {self.hotkeys.available}, "
                 f"{len(self.hotkeys.bindings)} set",
                 "", "Recent events:", rx.log.text()]
        return "\n".join(lines)

    # ---- periodic updates ------------------------------------------------------------------------------------------------------------------
    def refresh_header(self):
        rx = self.rx
        state = rx.state()
        color, text = STATE_STYLE[state]
        if state == "error":
            text = "Port in use" if "unavailable" in rx.net.udp_error else text
        silent = state == "streaming" and rx.gate_closed
        if silent:
            color, text = T.WARN, "Silent"
        self.chip_dot.configure(fg=color)
        self.chip_text.configure(text=text)
        tips = {"waiting": f"Waiting for your phone ({rx.netinfo.best_ip()})", "streaming": f"Streaming from {rx.client_ip}",
                "muted": "Muted", "lost": "Connection lost", "error": "Cannot listen: " + (rx.net.udp_error or "network error")}
        self.tray.set_state("silent" if silent else state, "PhoneMic Receiver: " + ("Silent, " + tips["streaming"] if silent else tips[state]))
        self.btn_mute.set_text("Unmute" if rx.paused else "Mute")
        self.btn_mute.set_style("danger" if rx.paused else "normal")
        self.btn_monitor.set_text("Monitor on" if rx.monitoring else "Monitor")
        self.btn_monitor.set_style("active" if rx.monitoring else "normal")
        self.btn_fx.set_text("Effects bypassed" if self.proc.fx_bypass else "Effects on")
        self.btn_fx.set_style("warn" if self.proc.fx_bypass else "normal")
        if rx.recorder.active:
            self.btn_record.set_text(f"Recording {fmt_time(rx.recorder.seconds)}")
            self.btn_record.set_style("rec")
        else:
            self.btn_record.set_text("Record")
            self.btn_record.set_style("normal")

    def refresh_statusbar(self):
        rx = self.rx
        dev = rx.main_dev.name if rx.main_dev else "no output device"
        if not self.status_left.cget("text"):
            self.status_left.configure(text=f"Output: {dev}", fg=T.MUTED)
        busy = self.proc.dsp_ms / 10.0 * 100.0
        self.status_right.configure(text=f"DSP load {busy:.0f}%     Delay about {rx.latency_estimate_ms():.0f} ms")
        self.side_state.configure(text=f"{rx.netinfo.best_ip()}\nPort {self.cfg.data['network']['port']}")

    def tick(self):
        fps = max(5, int(self.cfg.data["app"]["ui_fps"] or 30))
        delay = int(1000 / fps)
        try:
            if self.root.state() in ("iconic", "withdrawn"):
                self.proc.viz_active = False
                self.root.after(500, self.tick)
                return
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
        except Exception as e:      # noqa: BLE001 - the UI loop must never die
            key = repr(e)
            if key not in self._err_seen:
                self._err_seen.add(key)
                self.rx.log.error(f"UI error: {key}")
        self.root.after(delay, self.tick)

    # ---- lifecycle ----------------------------------------------------------------------------------------------------------------------------
    def on_close(self):
        """The window's close button: hide to the tray when asked to, otherwise quit."""
        if self.cfg.data["app"]["close_to_tray"] and self.tray.running:
            self.hide_window()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self.tray.notify("PhoneMic Receiver is still running here. Right-click the icon to quit.")
            return
        self.quit_app()

    def quit_app(self):
        if getattr(self, "_quitting", False):               # the tray and the window can both ask at the same moment
            return
        self._quitting = True
        try:
            if self.root.state() == "normal":
                self.cfg.data["app"]["window_geometry"] = self.root.winfo_geometry()
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
# DASHBOARD
# ==============================================================================
def _line(parent, label):
    row = tk.Frame(parent, bg=T.SURFACE)
    row.pack(fill="x", pady=(dp(3), 0))
    tk.Label(row, text=label, bg=T.SURFACE, fg=T.MUTED, font=font(10)).pack(side="left")
    value = tk.Label(row, text="-", bg=T.SURFACE, fg=T.TEXT, font=font(10, "bold", True))
    value.pack(side="right")
    return value


class DashboardPage(Page):
    def build(self):
        app, b = self.app, self.body
        gap = dp(14)
        b.grid_columnconfigure(0, weight=1, uniform="c")
        b.grid_columnconfigure(1, weight=1, uniform="c")

        # ---- status and the address to type into the phone --------------------------------------------------------------
        hero = Card(b, pad=20)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, gap))
        left = tk.Frame(hero.body, bg=T.SURFACE)
        left.pack(side="left", fill="x", expand=True)
        self.hero_title = tk.Label(left, text="", bg=T.SURFACE, fg=T.TEXT, font=font(24, "bold", True), anchor="w")
        self.hero_title.pack(fill="x")
        self.hero_sub = autowrap(tk.Label(left, text="", bg=T.SURFACE, fg=T.MUTED, font=font(10), anchor="w", justify="left",
                                          wraplength=dp(300)))
        self.hero_sub.pack(fill="x", pady=(dp(4), 0))
        right = tk.Frame(hero.body, bg=T.SURFACE)
        right.pack(side="right", padx=(dp(20), 0))
        tk.Label(right, text="Phone address", bg=T.SURFACE, fg=T.DIM, font=font(9), anchor="e").pack(anchor="e")
        self.hero_ip = tk.Label(right, text="", bg=T.SURFACE, fg=T.ACCENT_HI, font=font(24, "bold", True), cursor="hand2")
        self.hero_ip.pack(anchor="e")
        self.hero_ip.bind("<Button-1>", lambda e: app.copy(app.rx.netinfo.best_ip(), "Copied the address"))
        Tooltip(self.hero_ip, "Click to copy this address")
        self.hero_alt = tk.Label(right, text="", bg=T.SURFACE, fg=T.DIM, font=font(9), anchor="e")
        self.hero_alt.pack(anchor="e")

        # ---- level -------------------------------------------------------------------------------------------------------------
        lv = Card(b, "Input level", pad=18)
        lv.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, gap))
        self.read_label = tk.Label(lv.header, text="", bg=T.SURFACE, fg=T.MUTED, font=font(10, "normal", True))
        self.read_label.pack(side="right")
        self.meter = LevelMeter(lv.body, height=36)
        self.meter.pack(fill="x")
        row = tk.Frame(lv.body, bg=T.SURFACE)
        row.pack(fill="x", pady=(dp(12), dp(6)))
        tk.Label(row, text="Frequency view", bg=T.SURFACE, fg=T.DIM, font=font(9)).pack(side="left")
        mode = app.cfg.data["visualizer_mode"]
        mode = mode if mode in ("spectrum", "scope") else ("scope" if "osc" in mode else "spectrum")   # v0.8 stored "oscilloscope"
        Segmented(row, [("spectrum", "Spectrum"), ("scope", "Waveform")], mode, self._viz_mode, bg=T.SURFACE, size=8).pack(side="right")
        self.spectrum = SpectrumView(lv.body, height=130)
        self.spectrum.mode = mode
        self.spectrum.pack(fill="x")
        self.peak_s, self.hold, self.hold_t, self.clip_until = -80.0, -80.0, 0.0, 0.0
        self.last = time.monotonic()
        self.meter.bind("<Button-1>", lambda e: setattr(self, "clip_until", 0.0))

        # ---- quick controls (the same settings as on the Sound page) ----------------------------------------------------------
        q = Card(b, "Quick sound", pad=18)
        q.grid(row=2, column=0, sticky="nsew", padx=(0, gap // 2), pady=(0, gap))
        pr = tk.Frame(q.body, bg=T.SURFACE)
        pr.pack(fill="x", pady=(0, dp(4)))
        tk.Label(pr, text="Preset", bg=T.SURFACE, fg=T.TEXT, font=font(10)).pack(side="left")
        combo = Combo(pr, app.fx_preset_names(), width=24, command=app.apply_fx_preset)
        combo.pack(side="right")
        app.preset_combos.append(combo)
        mark = tk.Label(q.body, text="", bg=T.SURFACE, fg=T.WARN, font=font(9), anchor="e")
        mark.pack(fill="x", pady=(0, dp(8)))
        app.preset_marks.append(mark)
        self.rows = [SettingRow(q.body, app, sm.BY_KEY[k], compact=True) for k in ("gain", "smart_noise_cancel", "noise_cancel_amount")]
        for r in self.rows:
            r.pack(fill="x", pady=(0, dp(12)))
        vr = tk.Frame(q.body, bg=T.SURFACE)
        vr.pack(fill="x", pady=(dp(4), dp(8)))
        tk.Label(vr, text="Voice", bg=T.SURFACE, fg=T.TEXT, font=font(10)).pack(side="left")
        vcombo = Combo(vr, app.voice_preset_names(), width=24, command=app.apply_voice_preset)
        vcombo.set(app.proc.voice_changer.active_preset)
        vcombo.pack(side="right")
        app.voice_combos.append(vcombo)
        self.voice_row = SettingRow(q.body, app, sm.BY_KEY["vc.enabled"], compact=True)
        self.voice_row.pack(fill="x")

        # ---- connection quality ---------------------------------------------------------------------------------------------------
        h = Card(b, "Connection quality", pad=18)
        h.grid(row=2, column=1, sticky="nsew", padx=(gap // 2, 0), pady=(0, gap))
        self.g_latency = GaugeRow(h.body, "Delay")
        self.g_jitter = GaugeRow(h.body, "Network jitter")
        self.g_loss = GaugeRow(h.body, "Packet loss")
        self.g_rate = GaugeRow(h.body, "Bitrate")
        for g in (self.g_latency, self.g_jitter, self.g_loss, self.g_rate):
            g.pack(fill="x", pady=(0, dp(2)))
        tk.Frame(h.body, height=1, bg=T.BORDER).pack(fill="x", pady=(dp(10), dp(8)))
        self.v_buffer = _line(h.body, "Network buffer")
        self.v_dsp = _line(h.body, "Effects load")
        self.v_under = _line(h.body, "Output underruns")
        self.v_time = _line(h.body, "Session time")
        self.v_lost = _line(h.body, "Lost or concealed")

    # ---- callbacks ------------------------------------------------------------------------------------------------------------
    def _viz_mode(self, mode):
        self.spectrum.set_mode(mode)
        self.app.cfg.data["visualizer_mode"] = mode
        self.app.cfg.save_soon()

    def sync(self):
        for r in self.rows + [self.voice_row]:
            r.refresh()

    def on_show(self):
        self.sync()
        self.spectrum._build()

    # ---- live updates ---------------------------------------------------------------------------------------------------------
    def refresh_fast(self):
        rx, proc = self.app.rx, self.app.proc
        now = time.monotonic()
        dt = min(0.2, now - self.last)
        self.last = now
        live = rx.state() == "streaming"
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
            text = f"Peak {self.peak_s:5.1f} dBFS     Average {rms:5.1f} dBFS"
            if proc.comp_enabled and proc.gain_reduction_db > 0.3:
                text += f"     Compressor {proc.gain_reduction_db:.1f} dB"
        else:
            text = "No signal"
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
        self.hero_title.configure(text="You are silent" if silent else titles[state], fg=T.WARN if silent else STATE_STYLE[state][0])
        since = fmt_time(time.monotonic() - st.stream_start) if st.stream_start else "00:00"
        if silent:
            sub = ("Hold your push-to-talk key to speak." if rx.ptt_active and not rx.ptt_held and not rx.hold_mute
                   else "Push-to-mute is held. Let go of the key to be heard again.")
        elif state == "streaming":
            sub = f"Connected from {rx.client_ip} over {rx.transport} for {since}."
        elif state == "muted":
            sub = "The output is silent and the phone was asked to pause. Press Unmute to continue."
        elif state == "lost":
            sub = f"No audio from {rx.client_ip} for {time.monotonic() - st.last_packet:.0f} seconds. It resumes on its own."
        elif state == "error":
            sub = rx.net.udp_error + " Close the other program or choose a different port on the Network page."
        else:
            sub = "Open PhoneMic on your phone and tap Scan or Auto-Detect PC, or type the address shown on the right."
        self.hero_sub.configure(text=sub)
        self.hero_ip.configure(text=net.best_ip())
        usb = net.first("USB Tether")
        self.hero_alt.configure(text=f"Port {port}" + (f"     USB tether {usb}" if usb else ""))

        live = state in ("streaming", "muted")
        lat = rx.latency_estimate_ms()
        self.g_latency.set(f"{lat:.0f} ms", lat / 250.0, T.GOOD if lat < 90 else T.WARN if lat < 160 else T.BAD)
        j = st.jitter_ms
        self.g_jitter.set(f"{j:.1f} ms" if live else "-", j / 60.0 if live else 0, T.GOOD if j < 15 else T.WARN if j < 40 else T.BAD)
        lp = st.loss_pct
        self.g_loss.set(f"{lp:.2f} %" if live else "-", lp / 5.0 if live else 0, T.GOOD if lp < 0.5 else T.WARN if lp < 3 else T.BAD)
        self.g_rate.set(f"{st.bitrate_kbps:.0f} kbps" if live else "-", st.bitrate_kbps / 1000.0 if live else 0, T.ACCENT)
        self.v_buffer.configure(text=f"{rx.jb.depth_ms:.0f} of {rx.jb.target_ms:.0f} ms")
        load = app.proc.dsp_ms / 10.0 * 100.0
        self.v_dsp.configure(text=f"{load:.1f}%", fg=T.GOOD if load < 25 else T.WARN if load < 60 else T.BAD)
        self.v_under.configure(text=str(rx.main.starved) if live else "-")
        self.v_time.configure(text=fmt_time(time.monotonic() - st.stream_start) if st.stream_start else "-")
        self.v_lost.configure(text=f"{st.lost} lost, {st.plc_frames} concealed" if live else "-")
