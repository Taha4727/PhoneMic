"""Studio pages: Audio Studio (DSP + inline Voice Changer + EQ), Connections (Devices + Network + QR), Settings (sub-tabbed), Diagnostics."""
import os
import sys
import json
import time
import shutil
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np

from . import system, virtual_mic, settings_meta as sm
from .const import VERSION, VB_CABLE_URL, CABLE_HINT
from .widgets import (T, HAS_CTK, ctk, dp, font, MONO_FONT, autowrap, bg_of, lerp_color,
                      FlatButton, Segmented, Combo, Card, StatTile, Toggle, CatPreviewButton,
                      TextInput, SurfaceBox, PillBadge, ScrollTextBox)
from .ui_kit import SettingRow, SettingsCard, PanelHeader, StageList, EQEditor, HotkeyEntry
from .gui import Page, fmt_time
from .qr import generate_qr_matrix

GAP = 14
EQ_FREQS = np.geomspace(20.0, 20000.0, 160)


def label(parent, text, fg=None, size=10, weight="normal", bg=None, **kw):
    return tk.Label(parent, text=text, bg=bg or bg_of(parent), fg=fg or T.TEXT, font=font(size, weight), **kw)


def hint(parent, text):
    return autowrap(tk.Label(parent, text=text, bg=bg_of(parent), fg=T.DIM, font=font(9), anchor="w", justify="left",
                             wraplength=dp(240)))


class ResponsiveColumns(tk.Frame):
    """Two equal columns when wide (>= breakpoint dp), stacking cleanly into 1 column when narrow."""

    def __init__(self, master, breakpoint=640):
        super().__init__(master, bg=T.BG)
        self._bp = breakpoint
        self._cols = None
        self._reflow_job = None
        self._pending_w = None
        self.left = tk.Frame(self, bg=T.BG)
        self.right = tk.Frame(self, bg=T.BG)
        self._reflow(dp(max(700, breakpoint + 40)))
        self.bind("<Configure>", lambda e: self._schedule_reflow(e.width), add="+")

    def _schedule_reflow(self, width_px):
        if not width_px or width_px < 40:
            return
        self._pending_w = width_px
        if self._reflow_job:
            try:
                self.after_cancel(self._reflow_job)
            except Exception:
                pass
        self._reflow_job = self.after(16, self._run_scheduled_reflow)

    def _run_scheduled_reflow(self):
        self._reflow_job = None
        if not self.winfo_exists():
            return
        w = self._pending_w
        if w is not None:
            self._reflow(w, hysteresis=True)

    def _reflow(self, width_px=None, hysteresis=False):
        if not width_px or width_px < 40:
            return
        bp = dp(self._bp)
        if hysteresis and self._cols is not None:
            want = (1 if width_px < bp + dp(10) else 2) if self._cols == 1 else (1 if width_px < bp - dp(10) else 2)
        else:
            want = 1 if width_px < bp else 2
        if want == self._cols:
            return
        self._cols = want
        self.left.grid_forget()
        self.right.grid_forget()
        if want == 2:
            self.grid_columnconfigure(0, weight=1, uniform="c")
            self.grid_columnconfigure(1, weight=1, uniform="c")
            self.left.grid(row=0, column=0, sticky="new", padx=(0, dp(GAP // 2)), pady=0)
            self.right.grid(row=0, column=1, sticky="new", padx=(dp(GAP // 2), 0), pady=0)
        else:
            self.grid_columnconfigure(0, weight=1, uniform="")
            self.grid_columnconfigure(1, weight=0, uniform="")
            self.left.grid(row=0, column=0, columnspan=2, sticky="new", padx=0, pady=(0, dp(GAP)))
            self.right.grid(row=1, column=0, columnspan=2, sticky="new", padx=0, pady=0)


def two_columns(parent, breakpoint=640):
    cols = ResponsiveColumns(parent, breakpoint=breakpoint)
    cols.pack(fill="both", expand=True)
    return cols.left, cols.right


def button_row(parent, items, bg=None):
    """items: [(text, command, style)] laid out left to right."""
    row = tk.Frame(parent, bg=bg or bg_of(parent))
    for i, (text, cmd, style) in enumerate(items):
        FlatButton(row, text, cmd, style=style, size=9, padx=10, pady=5).pack(side="left", padx=(0 if i == 0 else dp(6), 0))
    return row


# ==============================================================================
# AUDIO STUDIO (DSP Chain + Inline Voice Changer + Interactive EQ)
# ==============================================================================
class SoundPage(Page):
    """Left: interactive multi-color signal path. Right: controls for the chosen stage (including Voice Changer)."""

    def build(self):
        app = self.app
        gap = dp(GAP)
        self.panels, self.stage_id = {}, None
        self.eq_band = 3
        self.editor = None
        self.voice_widgets = None

        bar = Card(self.body, pad=14)
        bar.pack(fill="x", pady=(0, gap))
        top = tk.Frame(bar.body, bg=T.SURFACE)
        top.pack(fill="x")
        label(top, "Sound preset", fg=T.MUTED, bg=T.SURFACE).pack(side="left")
        combo = Combo(top, app.fx_preset_names(), width=26, command=app.apply_fx_preset)
        combo.pack(side="left", padx=(dp(10), dp(10)))
        app.preset_combos.append(combo)
        mark = tk.Label(top, text="", bg=T.SURFACE, fg=T.WARN, font=font(9, "bold"))
        mark.pack(side="left")
        app.preset_marks.append(mark)
        btn_row = tk.Frame(bar.body, bg=T.SURFACE)
        btn_row.pack(anchor="w", pady=(dp(10), 0))
        for i, (txt, cmd, st) in enumerate((
            ("Save as...", app.save_fx_preset, "primary"),
            ("Delete", app.delete_fx_preset, "danger"),
            ("Import...", app.import_presets, "normal"),
            ("Export...", lambda: app.export_preset("fx"), "normal"),
            ("Reset to default", lambda: app.apply_fx_preset("Default (Studio Clean)"), "ghost"),
        )):
            FlatButton(btn_row, txt, cmd, style=st, size=9, padx=8, pady=4).pack(side="left", padx=(0 if i == 0 else dp(5), 0))

        split = tk.Frame(self.body, bg=T.BG)
        split.pack(fill="both", expand=True)
        split.grid_columnconfigure(1, weight=1)
        rail = tk.Frame(split, bg=T.BG)
        rail.grid(row=0, column=0, sticky="n", padx=(0, gap))
        tk.Label(rail, text="SIGNAL PATH", bg=T.BG, fg=T.DIM, font=font(8, "bold"), anchor="w").pack(
            fill="x", padx=dp(6), pady=(0, dp(6)))
        self.chain = StageList(rail, sm.STAGES, self.pick_stage, bg=T.BG)
        self.chain.pack(fill="x")
        self.holder = tk.Frame(split, bg=T.BG)
        self.holder.grid(row=0, column=1, sticky="nsew")

        app.binder.listen_any(self._changed)
        self.pick_stage("noise")
        self.refresh_leds()

    def pick_stage(self, sid):
        stage = sm.STAGE_BY_ID[sid]
        if stage.link:
            self.app.show_page(stage.link)
            return
        if self.stage_id and self.stage_id in self.panels:
            self.panels[self.stage_id]["frame"].pack_forget()
        if sid not in self.panels:
            self.panels[sid] = self.build_panel(stage)
            self.layout_panel(self.panels[sid], self.app.advanced)
        self.stage_id = sid
        self.panels[sid]["frame"].pack(fill="both", expand=True)
        self.chain.choose(sid)
        if sid == "voice":
            self.sync_voice()
        self.refresh_readout()

    def build_panel(self, stage):
        app = self.app
        is_blue = stage.id in ("voice", "eq", "deess")
        border_col = lerp_color(T.BORDER, T.BLUE, 0.25) if is_blue else T.BORDER
        if HAS_CTK:
            frame = ctk.CTkFrame(self.holder, fg_color=T.SURFACE, corner_radius=dp(10), border_width=1, border_color=border_col)
        else:
            frame = tk.Frame(self.holder, bg=T.SURFACE, highlightthickness=1, highlightbackground=border_col)
        inset = tk.Frame(frame, bg=T.SURFACE)
        inset.pack(fill="both", expand=True, padx=dp(1), pady=dp(1))

        header = PanelHeader(inset, stage.title, stage.blurb, sm.BY_KEY[stage.enable] if stage.enable else None,
                             app, accent=T.BLUE_HI if is_blue else T.ACCENT_HI)
        header.pack(fill="x")
        body = tk.Frame(inset, bg=T.SURFACE)
        body.pack(fill="both", expand=True, padx=dp(18), pady=dp(16))
        foot = tk.Frame(body, bg=T.SURFACE)
        foot.pack(side="bottom", fill="x")
        FlatButton(foot, "Reset this stage", lambda sid=stage.id: self.reset_stage(sid), style="ghost", size=9).pack(
            anchor="e", pady=(dp(6), 0))
        panel = {"frame": frame, "header": header, "body": body, "foot": foot, "rows": [], "bands": {}, "band_frames": {}}

        if stage.id == "eq":
            settings = [s for s in sm.by_group("sound", stage.id) if s.key != stage.enable]
            self.build_eq(panel, settings)
        elif stage.id == "voice":
            self.build_voice(panel)
        else:
            settings = [s for s in sm.by_group("sound", stage.id) if s.key != stage.enable]
            panel["rows"] = [SettingRow(body, app, s) for s in settings]
        return panel

    # ---- inline Voice Changer studio panel --------------------------------------------------------------------------
    def build_voice(self, panel):
        app = self.app
        from .dsp import VoiceChanger
        vc = app.proc.voice_changer
        body, foot = panel["body"], panel["foot"]

        p_row = tk.Frame(body, bg=T.SURFACE)
        p_row.pack(fill="x", before=foot, pady=(0, dp(10)))
        label(p_row, "Voice preset", fg=T.MUTED, bg=T.SURFACE).pack(side="left")
        vcombo = Combo(p_row, app.voice_preset_names(), width=22, command=app.apply_voice_preset)
        vcombo.set(vc.active_preset)
        vcombo.pack(side="left", padx=(dp(8), dp(8)))
        app.voice_combos.append(vcombo)
        button_row(p_row, [("Save...", self._voice_save, "blue"), ("Delete", self._voice_delete, "danger")]
                   ).pack(side="left")

        cat_bar = tk.Frame(body, bg=T.SURFACE)
        cat_btn = CatPreviewButton(cat_bar, command=app.preview_cat_voice, menu_command=app.show_cat_menu, size=17)
        cat_btn.pack(side="left")
        FlatButton(cat_bar, "Preview", app.preview_cat_voice, style="blue", size=8, padx=8, pady=3).pack(
            side="left", padx=(dp(6), dp(4)))
        FlatButton(cat_bar, "Upload WAV...", app.upload_cat_wav, style="normal", size=8, padx=8, pady=3).pack(
            side="left", padx=(0, dp(4)))
        cat_reset_btn = FlatButton(cat_bar, "Reset", app.reset_cat_wav, style="ghost", size=8, padx=8, pady=3)
        cat_lbl = tk.Label(cat_bar, text="", bg=T.SURFACE, fg=T.DIM, font=font(8), anchor="w")
        cat_lbl.pack(side="left", fill="x", expand=True, padx=(dp(6), 0))

        morph_lbl = label(body, "Character morph", T.BLUE_HI, 9, "bold", bg=T.SURFACE, anchor="w")
        morph_lbl.pack(fill="x", before=foot, pady=(dp(4), dp(6)))
        grid = tk.Frame(body, bg=T.SURFACE)
        grid.pack(fill="x", before=foot)
        mode_buttons = {}
        for i, mode in enumerate(VoiceChanger.MODES):
            grid.grid_columnconfigure(i % 4, weight=1, uniform="m")
            b = FlatButton(grid, mode.replace(" / ", "\n"), command=lambda m=mode: self._voice_mode(m),
                           size=9, pady=8, corner=8)
            b.grid(row=i // 4, column=i % 4, sticky="nsew", padx=dp(3), pady=dp(3))
            mode_buttons[mode] = b
        desc = autowrap(tk.Label(body, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left",
                                 wraplength=dp(300)))
        desc.pack(fill="x", before=foot, pady=(dp(8), dp(12)))

        pitch_row = SettingRow(body, app, sm.BY_KEY["vc.pitch_semitones"])
        formant_row = SettingRow(body, app, sm.BY_KEY["vc.formant_semitones"])
        mix_row = SettingRow(body, app, sm.BY_KEY["vc.mix"])
        panel["rows"] = [pitch_row, formant_row, mix_row]

        lat = hint(body, "")
        lat.pack(fill="x", before=foot, pady=(dp(4), 0))
        self.voice_widgets = {
            "VC": VoiceChanger,
            "combo": vcombo,
            "buttons": mode_buttons,
            "desc": desc,
            "latency": lat,
            "rows": [pitch_row, formant_row, mix_row],
            "anchor": morph_lbl,
            "cat_bar": cat_bar,
            "cat_btn": cat_btn,
            "cat_reset": cat_reset_btn,
            "cat_lbl": cat_lbl,
        }
        self.sync_voice()

    def _voice_mode(self, mode):
        vc = self.app.proc.voice_changer
        vc.mode = mode
        vc.active_preset = "Custom"
        self.app.binder.persist_voice()
        self.app.refresh_preset_ui()
        self.sync_voice()

    def _voice_save(self):
        app = self.app
        name = app.ask_name("Save voice preset", "Name for your voice preset:")
        if not name:
            return
        from . import presets_io as pio
        name = pio.clean_name(name)
        from .dsp import VoiceChanger
        if name in VoiceChanger.BUILTIN_PRESETS:
            app.notify("That name belongs to a built-in preset.", "warn")
            return
        vc = app.proc.voice_changer
        d = vc.export()
        d["enabled"] = True
        app.cfg.data["user_voice_presets"][name] = d
        vc.active_preset = name
        app.binder.persist_voice()
        app.refresh_preset_ui()
        app.notify(f"Saved voice preset \"{name}\".", "good")

    def _voice_delete(self):
        app = self.app
        name = app.proc.voice_changer.active_preset
        if name not in app.cfg.data["user_voice_presets"]:
            app.notify("Built-in presets cannot be deleted.", "warn")
            return
        if messagebox.askyesno("Delete preset", f"Delete your voice preset \"{name}\"?", parent=app.root):
            del app.cfg.data["user_voice_presets"][name]
            app.apply_voice_preset("Normal (Bypass)")

    def sync_cat_preview(self):
        vw = self.voice_widgets
        if not vw or "cat_bar" not in vw:
            return
        bar = vw["cat_bar"]
        if self.app.cat_preview_visible():
            if bar.winfo_manager() != "pack":
                bar.pack(fill="x", before=vw["anchor"], pady=(0, dp(10)))
            lbl, is_custom = self.app.rx.cat_preview_info()
            vw["cat_lbl"].configure(text=lbl)
            vw["cat_btn"].set_playing(self.app.rx.preview_active)
            rst = vw["cat_reset"]
            if is_custom:
                if rst.winfo_manager() != "pack":
                    rst.pack(side="left", before=vw["cat_lbl"], padx=(0, dp(4)))
            else:
                rst.pack_forget()
        else:
            vw["cat_btn"].set_playing(False)
            bar.pack_forget()

    def sync_voice(self):
        vw = self.voice_widgets
        if not vw:
            return
        vc = self.app.proc.voice_changer
        for r in vw["rows"]:
            r.refresh()
        vw["combo"].set_values(self.app.voice_preset_names(), vc.active_preset)
        for m, b in vw["buttons"].items():
            b.set_style("blue" if m == vc.mode else "normal")
        vw["desc"].configure(text=vw["VC"].MODE_DESCRIPTIONS.get(vc.mode, ""))
        ms = vc.latency_ms
        vw["latency"].configure(text=(f"Adds ~{ms:.0f} ms of pitch-shifting latency." if ms else "Zero added latency.")
                                + ("" if vc.enabled else " (Voice changer is currently off)"))
        self.sync_cat_preview()

    def build_eq(self, panel, settings):
        app, body = self.app, panel["body"]
        top = tk.Frame(body, bg=T.SURFACE)
        top.pack(fill="x", before=panel["foot"])
        self.editor = EQEditor(top, on_pick=self.eq_pick, on_edit=self.eq_edit, height=210)
        self.editor.pack(fill="x")
        sel = tk.Frame(top, bg=T.SURFACE)
        sel.pack(fill="x", pady=(dp(10), dp(4)))
        label(sel, "Band", bg=T.SURFACE).pack(side="left", padx=(0, dp(10)))
        self.band_picker = Segmented(sel, [(n, str(n)) for n in range(1, 6)], self.eq_band, self.eq_pick, bg=T.SURFACE)
        self.band_picker.pack(side="left")
        hint(top, "Drag numbered points to adjust frequency & gain. Scroll wheel changes Q width; right-click toggles band."
             ).pack(fill="x", pady=(dp(6), 0))
        for n in range(1, 6):
            bf = tk.Frame(body, bg=T.SURFACE)
            order = [f"eq{n}_freq", f"eq{n}_gain", f"eq{n}_q", f"eq{n}_type", f"eq{n}_on"]
            panel["bands"][n] = [SettingRow(bf, app, sm.BY_KEY[k]) for k in order]
            panel["band_frames"][n] = bf
        self.show_band(panel)
        self.refresh_eq()

    def layout_panel(self, panel, advanced):
        for r in panel["rows"]:
            r.pack_forget()
        for r in (r for r in panel["rows"] if advanced or not r.advanced):
            r.pack(fill="x", pady=(0, dp(14)), before=panel["foot"])
        for n, rows in panel["bands"].items():
            for r in rows:
                r.pack_forget()
            for r in (r for r in rows if advanced or not r.advanced):
                r.pack(fill="x", pady=(0, dp(14)))

    def show_band(self, panel):
        for n, bf in panel["band_frames"].items():
            bf.pack_forget()
        panel["band_frames"][self.eq_band].pack(fill="x", before=panel["foot"], pady=(dp(8), 0))

    def apply_view(self, advanced):
        for panel in self.panels.values():
            self.layout_panel(panel, advanced)

    def reset_stage(self, sid):
        if sid == "voice":
            self.app.apply_voice_preset("Normal (Bypass)")
            return
        for s in sm.by_group("sound", sid):
            if s.key != sm.STAGE_BY_ID[sid].enable:
                self.app.binder.reset(s)
        self.app.notify(f"{sm.STAGE_BY_ID[sid].title} was reset to its defaults.", "good", 3000)

    def eq_pick(self, n):
        self.eq_band = int(n)
        panel = self.panels.get("eq")
        if panel:
            self.band_picker.set(self.eq_band)
            self.show_band(panel)
            self.refresh_eq()

    def eq_edit(self, n, **kw):
        names = {"freq": f"eq{n}_freq", "gain": f"eq{n}_gain", "q": f"eq{n}_q", "on": f"eq{n}_on"}
        for field, value in kw.items():
            self.app.binder.set(sm.BY_KEY[names[field]], value)

    def refresh_eq(self):
        if self.editor is None:
            return
        p = self.app.proc
        self.editor.set_state([p.eq_band(n) for n in range(1, 6)], EQ_FREQS, p.eq_curve_db(EQ_FREQS), self.eq_band, p.eq_enabled)

    def led_state(self, st):
        p = self.app.proc
        if st.id == "voice":
            return bool(p.voice_changer.enabled)
        if st.enable:
            return bool(getattr(p, st.enable))
        if st.led:
            return any(getattr(p, k) for k in st.led)
        return "fixed"

    def refresh_leds(self):
        for st in sm.STAGES:
            self.chain.set_led(st.id, self.led_state(st))

    def readout_for(self, sid):
        p = self.app.proc
        if sid == "comp" and p.comp_enabled:
            return (f"Reducing {p.gain_reduction_db:.1f} dB", T.GOOD) if p.gain_reduction_db > 0.3 else ("Not reducing", T.DIM)
        if sid == "deess" and p.deess_enabled:
            return (f"Reducing {p.deess_reduction_db:.1f} dB", T.BLUE_HI) if p.deess_reduction_db > 0.3 else ("Not reducing", T.DIM)
        if sid == "agc" and p.agc_enabled:
            return f"Gain {p.agc.gain_db:+.1f} dB", T.GOOD
        if sid == "gate" and p.gate_enabled:
            return ("Open", T.GOOD) if p.gate.is_open else ("Closed", T.DIM)
        if sid == "noise" and p.smart_noise_cancel and p.noise_cancel_amount > 0.02:
            return f"Adds {p.denoiser.delay_ms:.0f} ms", T.MUTED
        if sid == "voice" and p.voice_changer.enabled:
            ms = p.voice_changer.latency_ms
            return (f"{p.voice_changer.mode} (+{ms:.0f} ms)" if ms else p.voice_changer.mode), T.BLUE_HI
        return "", None

    def refresh_readout(self):
        panel = self.panels.get(self.stage_id)
        if panel:
            text, color = self.readout_for(self.stage_id)
            panel["header"].set_readout(text, color)

    def _changed(self, setting):
        self.refresh_leds()
        if setting is None or setting.key.startswith("eq"):
            self.refresh_eq()
        if setting is None or setting.key.startswith("vc."):
            self.sync_voice()

    def on_show(self):
        self.refresh_leds()
        self.refresh_eq()
        self.sync_voice()
        self.refresh_readout()

    def refresh_slow(self):
        self.refresh_leds()
        self.refresh_readout()

    def focus_setting(self, s):
        sid = "voice" if s.page == "voice" or s.group == "voice" else s.group
        if sid in sm.STAGE_BY_ID:
            self.pick_stage(sid)
        panel = self.panels.get(sid)
        if not panel:
            return
        if sid == "voice" and s.key == "vc.enabled":
            panel["header"].flash() if hasattr(panel["header"], "flash") else None
            return
        rows = list(panel["rows"])
        if sid == "eq" and s.key[:2] == "eq" and s.key[2:3].isdigit():
            self.eq_pick(int(s.key[2]))
            rows = panel["bands"][int(s.key[2])]
        for r in rows:
            if r.setting.key == s.key:
                r.set_details(True)
                r.flash()
                self.scroll.scroll_to(r)
                return


# ==============================================================================
# UNIFIED CONNECTIONS (Audio Devices + Network + Instant QR Code)
# ==============================================================================
class ConnectPage(Page):
    JITTER_PROFILES = [(10, "Ultra-low"), (20, "Low"), (30, "Balanced"), (60, "Stable"), (120, "Max")]
    @staticmethod
    def _badge_color(cat):
        return {
            "Wi-Fi": T.ACCENT,
            "Ethernet": T.BLUE,
            "USB Tether": T.GOOD,
            "PC Hotspot": T.WARN,
            "Virtual": T.DIM,
            "Network": T.MUTED,
        }.get(cat, T.MUTED)

    def build(self):
        app, rx = self.app, self.app.rx
        gap = dp(GAP)
        left, right = two_columns(self.body, breakpoint=660)
        self.dev_map = {}
        self.out_combo = self.mon_combo = None
        self._addr_key = None
        self._slow_cache = None

        # ---- LEFT: Output Device, Delay/Buffer, Monitoring ---------------------------------------------------------
        def api_control(row):
            cur = app.cfg.data["audio"]["api"]
            if system.IS_WIN:
                choices = [("auto", "Auto"), ("WASAPI", "WASAPI"), ("DirectSound", "DirectSound"), ("MME", "MME")]
            else:
                choices = [("auto", "Auto")]
                seen_k = {"auto"}
                for candidate in ("PipeWire", "PulseAudio", "ALSA", "JACK"):
                    if candidate == "JACK" and "JACK" not in " ".join(system.available_apis(rx.devices)):
                        continue
                    choices.append((candidate, candidate))
                    seen_k.add(candidate)
                for a in system.available_apis(rx.devices):
                    if a not in seen_k and len(choices) < 5:
                        choices.append((a, a))
                        seen_k.add(a)
            keys = [k for k, _ in choices]
            return Segmented(row, choices, cur if cur in keys else "auto", self._api, bg=T.SURFACE,
                             size=8, padx=6, pady=3)

        def output_control(row):
            box = tk.Frame(row, bg=T.SURFACE)
            self.out_combo = Combo(box, [], width=28, command=self._out)
            self.out_combo.pack(anchor="w")
            btns = tk.Frame(box, bg=T.SURFACE)
            btns.pack(anchor="w", pady=(dp(8), 0))
            if system.IS_LINUX:
                actions = (
                    ("Test tone", rx.play_test_tone, "primary"),
                    ("Refresh", self._refresh, "normal"),
                    ("Sound Mixer", self._open_mixer, "ghost"),
                    ("Patchbay", self._open_patchbay, "ghost"),
                )
            else:
                actions = (
                    ("Test tone", rx.play_test_tone, "primary"),
                    ("Refresh", self._refresh, "normal"),
                    ("Win Sound", lambda: self._open("ms-settings:sound"), "ghost"),
                    ("Recording", lambda: self._open("control mmsys.cpl,,1"), "ghost"),
                )
            for i, (txt, cmd, st) in enumerate(actions):
                FlatButton(btns, txt, cmd, style=st, size=8, padx=6, pady=3).pack(side="left", padx=(0 if i == 0 else dp(4), 0))
            return box

        def jitter_control(row):
            ms = app.cfg.data["audio"]["jitter_ms"]
            nearest = min((p[0] for p in self.JITTER_PROFILES), key=lambda v: abs(v - ms))
            self.jit_seg = Segmented(row, [(v, n) for v, n in self.JITTER_PROFILES], nearest, self._jitter,
                                     bg=T.SURFACE, size=8, padx=6, pady=3)
            return self.jit_seg

        def monitor_control(row):
            self.mon_combo = Combo(row, [], width=28, command=self._mon)
            return self.mon_combo

        out_settings = [s for s in sm.by_group("devices", "output") if system.IS_LINUX or not s.key.startswith("audio.linux_")]
        self.card_out = SettingsCard(left, app, "Output device", "Where the PC plays the phone's voice.",
                                     out_settings, {"audio.api": api_control, "audio.output_device": output_control})
        self.card_out.pack(fill="x", pady=(0, gap))
        self.out_status = autowrap(tk.Label(self.card_out.footer, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9),
                                            anchor="w", justify="left", wraplength=dp(260)))
        self.out_status.pack(fill="x", pady=(dp(4), 0))

        cable = SurfaceBox(self.card_out.footer, bg=T.SIDEBAR, border=T.BORDER, corner=8)
        cable.pack(fill="x", pady=(dp(10), 0))
        cable_in = tk.Frame(cable, bg=T.SIDEBAR)
        cable_in.pack(fill="x", padx=dp(10), pady=dp(8))
        self.cable_label = autowrap(tk.Label(cable_in, text="", bg=T.SIDEBAR, fg=T.MUTED, font=font(9),
                                             anchor="w", justify="left", wraplength=dp(260)))
        self.cable_label.pack(fill="x")
        self.cable_btn = FlatButton(cable_in, "Get VB-CABLE", lambda: webbrowser.open(VB_CABLE_URL),
                                    style="warn", size=8, padx=8, pady=4)
        self.virt_btns = None
        if system.IS_LINUX:
            self.virt_btns = tk.Frame(cable_in, bg=T.SIDEBAR)
            self.btn_create_vmic = FlatButton(self.virt_btns, "Create Virtual Mic", self._create_virtual_mic,
                                              style="primary", size=8, padx=8, pady=4)
            self.btn_create_vmic.pack(side="left")
            self.btn_remove_vmic = FlatButton(self.virt_btns, "Remove Virtual Mic", self._remove_virtual_mic,
                                              style="ghost", size=8, padx=8, pady=4)
            self.btn_remove_vmic.pack(side="left", padx=(dp(6), 0))

        self.card_lat = SettingsCard(left, app, "Delay and stability", "Trade buffer headroom for smoother audio on Wi-Fi.",
                                     sm.by_group("devices", "latency"), {"audio.jitter_ms": jitter_control})
        self.card_lat.pack(fill="x", pady=(0, gap))
        self.breakdown = autowrap(tk.Label(self.card_lat.footer, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9),
                                           anchor="w", justify="left", wraplength=dp(300)))
        self.breakdown.pack(fill="x", pady=(dp(4), 0))

        self.card_mon = SettingsCard(left, app, "Headphone monitor", "Hear your processed voice live.",
                                     sm.by_group("devices", "monitor"), {"audio.monitor_device": monitor_control})
        self.card_mon.pack(fill="x", pady=(0, gap))
        self.vol_row = SettingRow(self.card_mon.footer, app, sm.BY_KEY["monitor_volume"])
        self.vol_row.pack(fill="x", pady=(0, dp(10)))
        self.mon_btn = FlatButton(self.card_mon.footer, "Start monitoring", app.toggle_monitor, size=9)
        self.mon_btn.pack(anchor="w")

        # ---- RIGHT: Network Addresses, Instant QR Code, Firewall & Options -----------------------------------------
        c_net = Card(right, "Network & Instant QR Pairing", pad=18)
        c_net.pack(fill="x", pady=(0, gap))
        hint(c_net.body, "Scan the QR code from PhoneMic on your phone, or tap an IP below to copy it.").pack(fill="x", pady=(0, dp(10)))

        qr_row = tk.Frame(c_net.body, bg=T.SURFACE)
        qr_row.pack(fill="x", pady=(0, dp(10)))
        qr_box = SurfaceBox(qr_row, bg="#ffffff", border=T.BORDER_HI, corner=10)
        qr_box.pack(side="left")
        self.qr_canvas = tk.Canvas(qr_box, width=dp(146), height=dp(146), bg="#ffffff", highlightthickness=0)
        self.qr_canvas.pack(padx=dp(5), pady=dp(5))

        qr_info = tk.Frame(qr_row, bg=T.SURFACE)
        qr_info.pack(side="left", fill="both", expand=True, padx=(dp(14), 0))
        label(qr_info, "SCAN TO PAIR", T.ACCENT, 8, "bold", bg=T.SURFACE, anchor="w").pack(fill="x")
        self.qr_payload_label = autowrap(tk.Label(qr_info, text="", bg=T.SURFACE, fg=T.TEXT, font=font(9, "bold", True),
                                                  anchor="w", justify="left", wraplength=dp(180)))
        self.qr_payload_label.pack(fill="x", pady=(dp(4), dp(8)))
        autowrap(tk.Label(qr_info, text="Works on Wi-Fi, PC Hotspot, or USB Tethering. Phone opens the stream instantly.",
                          bg=T.SURFACE, fg=T.DIM, font=font(8), anchor="w", justify="left", wraplength=dp(180))).pack(fill="x")
        FlatButton(qr_info, "Rescan adapters", self._rescan, size=8, padx=10, pady=4).pack(anchor="w", pady=(dp(10), 0))

        self.addr_box = tk.Frame(c_net.body, bg=T.SURFACE)
        self.addr_box.pack(fill="x", pady=(dp(4), 0))

        def port_control(row):
            box = tk.Frame(row, bg=T.SURFACE)
            self.port_var = tk.StringVar(value=str(app.cfg.data["network"]["port"]))
            e = TextInput(box, textvariable=self.port_var, width=8, size=11, weight="bold", display=True, justify="center")
            e.pack(side="left", ipady=0 if HAS_CTK else dp(4))
            e.bind("<Return>", lambda ev: self._apply_port())
            FlatButton(box, "Apply", self._apply_port, style="primary", size=9, padx=10, pady=4).pack(side="left", padx=(dp(8), 0))
            return box

        fw_blurb = (
            "Port binding and Linux firewall status (UFW / firewalld)."
            if system.IS_LINUX
            else "Port binding and Windows Defender Firewall status."
        )
        self.card_listen = SettingsCard(right, app, "Listening & Firewall", fw_blurb,
                                        sm.by_group("network", "listen"), {"network.port": port_control})
        self.card_listen.pack(fill="x", pady=(0, gap))
        self.status = {}
        fw_row_title = "Linux Firewall" if system.IS_LINUX else "Windows Firewall"
        for key, title in (("udp", "UDP audio"), ("tcp", "TCP audio"), ("fw", fw_row_title)):
            r = tk.Frame(self.card_listen.footer, bg=T.SURFACE)
            r.pack(fill="x", pady=2)
            label(r, title, T.MUTED, 9, bg=T.SURFACE).pack(side="left")
            v = label(r, "-", T.TEXT, 10, "bold", bg=T.SURFACE)
            v.pack(side="right")
            self.status[key] = v
        fw_btn_text = "Configure Firewall" if system.IS_LINUX else "Fix firewall (requires Admin)"
        FlatButton(self.card_listen.footer, fw_btn_text, app.fix_firewall, style="primary", size=9).pack(
            anchor="w", pady=(dp(10), 0))

        self.card_opts = SettingsCard(right, app, "Connection options & Session", "Discovery beacon, multi-phone lock, and live stats.",
                                      sm.by_group("network", "options"))
        self.card_opts.pack(fill="x", pady=(0, gap))
        self.conn = {}
        for key, title in (("client", "Phone"), ("transport", "Transport"), ("since", "Connected for"), ("packets", "Packets")):
            r = tk.Frame(self.card_opts.footer, bg=T.SURFACE)
            r.pack(fill="x", pady=2)
            label(r, title, T.MUTED, 9, bg=T.SURFACE).pack(side="left")
            v = label(r, "-", T.TEXT, 10, "bold", bg=T.SURFACE)
            v.pack(side="right")
            self.conn[key] = v
        FlatButton(self.card_opts.footer, "Reset session", self._reset, style="ghost", size=9).pack(anchor="w", pady=(dp(8), 0))

        self.fill_devices()
        self.refresh_addresses()

    def apply_view(self, advanced):
        for c in (self.card_out, self.card_lat, self.card_mon, self.card_listen, self.card_opts):
            c.apply_view(advanced)

    def _open(self, target):
        try:
            if system.IS_WIN:
                if target.startswith("control"):
                    subprocess.Popen(["control.exe", target.split(" ", 1)[1]])
                else:
                    os.startfile(target)  # noqa: S606
            else:
                self.app.notify("This is only available on Windows.", "warn")
        except Exception as e:      # noqa: BLE001
            self.app.notify(f"Could not open it: {e}", "error")

    def _open_mixer(self):
        cmd = virtual_mic.mixer_command()
        if not cmd:
            self.app.notify("Install pavucontrol (sudo pacman -S pavucontrol) to open the graphical mixer.", "info", 4500)
            return
        try:
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:      # noqa: BLE001
            self.app.notify(f"Could not launch mixer: {e}", "error")

    def _open_patchbay(self):
        cmd = virtual_mic.patchbay_command()
        if not cmd:
            self.app.notify("Install qpwgraph or helvum (sudo pacman -S qpwgraph) for a PipeWire patchbay.", "info", 4500)
            return
        try:
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:      # noqa: BLE001
            self.app.notify(f"Could not launch patchbay: {e}", "error")

    def _create_virtual_mic(self):
        self.app.ensure_virtual_mic()
        self.fill_devices()

    def _remove_virtual_mic(self):
        self.app.remove_virtual_mic()
        self.fill_devices()

    def fill_devices(self):
        rx = self.app.rx
        pool = system.devices_for_api(rx.devices, rx.api)
        self.dev_map = {d.name: d for d in pool}
        names = list(self.dev_map)
        if self.out_combo is not None:
            self.out_combo.set_values(names, rx.main_dev.name if rx.main_dev else "")
        if self.mon_combo is not None:
            self.mon_combo.set_values(names, rx.monitor_dev.name if rx.monitor_dev else "")
        if system.IS_LINUX:
            self.cable_btn.pack_forget()
            vm = virtual_mic.status(pool)
            self.cable_label.configure(text=vm.detail, fg=T.GOOD if vm.active else (T.WARN if vm.supported else T.DIM))
            if self.virt_btns is not None:
                if vm.supported:
                    self.virt_btns.pack(anchor="w", pady=(dp(6), 0))
                    self.btn_create_vmic.set_style("active" if vm.active else "primary")
                else:
                    self.virt_btns.pack_forget()
        else:
            has_cable = any(d.is_cable for d in pool)
            if has_cable:
                self.cable_label.configure(
                    text="VB-CABLE active. Choose \"CABLE Output (VB-Audio Virtual Cable)\" in Discord, OBS, or Zoom.",
                    fg=T.GOOD)
                self.cable_btn.pack_forget()
            else:
                self.cable_label.configure(
                    text=f"No virtual mic found. Install free VB-CABLE and select \"{CABLE_HINT}\" above.",
                    fg=T.WARN)
                self.cable_btn.pack(anchor="w", pady=(dp(6), 0))
        if hasattr(self.app, "sync_output_devices"):
            self.app.sync_output_devices()

    def _refresh(self):
        self.app.rx.refresh_devices()
        self.app.rx.open_main()
        self.fill_devices()
        self.app.notify("Audio devices refreshed.", "good", 2000)

    def _api(self, key):
        self.app.rx.set_api(key)
        self.fill_devices()

    def _out(self, name):
        d = self.dev_map.get(name)
        if d:
            self.app.rx.set_output_device(d)
            if hasattr(self.app, "sync_output_devices"):
                self.app.sync_output_devices()

    def _mon(self, name):
        d = self.dev_map.get(name)
        if d:
            self.app.rx.set_monitor_device(d)

    def _jitter(self, ms):
        self.app.rx.set_jitter(int(ms), self.app.cfg.data["audio"]["adaptive_jitter"])

    def _apply_port(self):
        try:
            port = int(self.port_var.get())
            if not 1024 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.app.notify("The port must be a number between 1024 and 65535.", "error")
            return
        self.app.rx.set_port(port)
        self.app.fw_state = None
        self.app.refresh_firewall_async()
        self._addr_key = None
        self.refresh_addresses()
        self.app.notify(f"Now listening on port {port}.", "good", 4000)

    def _rescan(self):
        self.app.rx.netinfo.refresh_async(lambda res: self.app.post(self.refresh_addresses))
        self.app.notify("Scanning network adapters...", "info", 2000)

    def _reset(self):
        rx = self.app.rx
        rx.jb.reset()
        rx.stats.reset_session()
        rx.client_ip, rx.client_addr = "", None
        self.app.notify("Connection reset. Waiting for the phone.", "good", 2500)

    def refresh_addresses(self):
        ifaces = self.app.rx.netinfo.get()
        port = self.app.cfg.data["network"]["port"]
        key = (tuple((i.category, i.ip) for i in ifaces), port)
        if key == self._addr_key:
            return
        self._addr_key = key
        for w in self.addr_box.winfo_children():
            w.destroy()
        if not ifaces:
            label(self.addr_box, "No network adapters found.", T.WARN, 10, bg=T.SURFACE).pack(anchor="w")
        for i in ifaces:
            r = SurfaceBox(self.addr_box, bg=T.SURFACE2, border=T.BORDER, corner=8)
            r.pack(fill="x", pady=dp(3))
            badge_col = self._badge_color(i.category)
            PillBadge(r, i.category, fg=badge_col, bg=T.SIDEBAR, border=lerp_color(T.BORDER, badge_col, 0.35),
                      size=8, padx=8, pady=2, corner=6, width=10).pack(side="left", padx=(dp(8), 0), pady=dp(5))
            ip = tk.Label(r, text=i.ip, bg=T.SURFACE2, fg=T.TEXT, font=font(12, "bold", True), cursor="hand2")
            ip.pack(side="left", padx=dp(10))
            ip.bind("<Button-1>", lambda e, a=i.ip: self.app.copy(a, "Copied IP"))
            FlatButton(r, "Copy", lambda a=i.ip: self.app.copy(a, "Copied IP"), size=8, padx=8, pady=2, corner=6).pack(
                side="right", padx=dp(8), pady=dp(4))

        best_ip = next((i.ip for i in ifaces if i.category in ("Wi-Fi", "USB Tether", "Ethernet")),
                       ifaces[0].ip if ifaces else "192.168.1.100")
        self._draw_qr(f"phonemic://{best_ip}:{port}?t=UDP")

    def _draw_qr(self, payload):
        try:
            matrix = generate_qr_matrix(payload)
            self.qr_canvas.delete("all")
            n = len(matrix)
            c_size = dp(146)
            cell = c_size / (n + 4)
            offset = cell * 2
            self.qr_canvas.create_rectangle(0, 0, c_size, c_size, fill="#ffffff", outline="")
            for y in range(n):
                for x in range(n):
                    if matrix[y][x]:
                        x1 = offset + x * cell
                        y1 = offset + y * cell
                        self.qr_canvas.create_rectangle(x1, y1, x1 + cell, y1 + cell, fill="#000000", outline="")
            self.qr_payload_label.configure(text=payload)
        except Exception:
            pass

    def on_show(self):
        self.fill_devices()
        self.refresh_addresses()

    def refresh_slow(self):
        app, rx = self.app, self.app.rx
        self.refresh_addresses()
        jb = rx.jb
        st = rx.stats
        net = rx.net
        live = rx.state() in ("streaming", "muted", "lost")
        since_txt = fmt_time(time.monotonic() - st.stream_start) if live and st.stream_start else "-"
        dev_name = rx.main_dev.name if rx.main_dev else None
        dev_api = rx.main_dev.api if rx.main_dev else None
        card_ms = round(rx.main.latency_ms, 0)
        buf_ms = round(jb.depth_ms, 0)
        tgt_ms = round(jb.target_ms, 0)
        fx_ms = round(rx.processor.latency_ms, 0)
        tot_ms = round(rx.latency_estimate_ms(), 0)
        key = (rx.main.error, rx.main.active, dev_name, dev_api, card_ms, buf_ms, tgt_ms, fx_ms, tot_ms,
               rx.monitoring, rx.client_ip, rx.transport, since_txt, st.packets, net.port,
               bool(net.udp_error), bool(net.tcp_error), app.fw_state)
        if key == self._slow_cache:
            return
        self._slow_cache = key

        if rx.main.error:
            self.out_status.configure(text=f"Device open error: {rx.main.error}", fg=T.BAD)
        elif rx.main.active and rx.main_dev:
            self.out_status.configure(text=f"{dev_name} ({dev_api}, {card_ms:.0f} ms device delay)",
                                      fg=T.MUTED)
        else:
            self.out_status.configure(text="No output stream open.", fg=T.WARN)
        self.breakdown.configure(
            text=f"Buffer {buf_ms:.0f}/{tgt_ms:.0f} ms + Card {card_ms:.0f} ms + FX {fx_ms:.0f} ms "
                 f"(~{tot_ms:.0f} ms total)")
        self.mon_btn.set_text("Stop monitoring" if rx.monitoring else "Start monitoring")
        self.mon_btn.set_style("active" if rx.monitoring else "normal")

        self.conn["client"].configure(text=rx.client_ip or "waiting")
        self.conn["transport"].configure(text=rx.transport if rx.client_ip else "-")
        self.conn["since"].configure(text=since_txt)
        self.conn["packets"].configure(text=f"{st.packets:,}")
        self.status["udp"].configure(text="Port busy" if net.udp_error else f"Listening :{net.port}", fg=T.BAD if net.udp_error else T.GOOD)
        self.status["tcp"].configure(text="Unavailable" if net.tcp_error else f"Listening :{net.port}", fg=T.WARN if net.tcp_error else T.GOOD)
        fw = app.fw_state
        fw_label = getattr(app, "fw_label", "")
        if fw is None:
            txt, col = "Checking...", T.MUTED
        elif fw is True:
            txt, col = (fw_label or "Rules present"), T.GOOD
        else:
            txt, col = (fw_label or "Rules missing"), T.WARN
        self.status["fw"].configure(text=txt, fg=col)

    def focus_setting(self, s):
        for card in (self.card_out, self.card_lat, self.card_mon, self.card_listen, self.card_opts):
            row = card.row_for(s.key)
            if row is not None:
                row.set_details(True)
                row.flash()
                self.scroll.scroll_to(row)
                return
        if s.key == "monitor_volume":
            self.vol_row.set_details(True)
            self.vol_row.flash()
            self.scroll.scroll_to(self.vol_row)


# Backwards compatibility aliases for external imports/tests if any
DevicesPage = ConnectPage
NetworkPage = ConnectPage


# ==============================================================================
# SUB-TABBED SETTINGS
# ==============================================================================
class SettingsPage(Page):
    def build(self):
        app = self.app
        gap = dp(GAP)
        self.active_tab = "general"
        self.card_keys = None
        self.keys_note = None
        self.card_rec = None
        self.folder = None
        self.cfg_path = None

        nav_row = tk.Frame(self.body, bg=T.BG)
        nav_row.pack(fill="x", pady=(0, gap))
        self.tab_picker = Segmented(nav_row, [
            ("general", "General & Theme"),
            ("shortcuts", "Global Hotkeys"),
            ("recording", "Recording & Backups"),
        ], "general", self._pick_tab, bg=T.BG, size=10)
        self.tab_picker.pack(anchor="w")

        self.tab_holder = tk.Frame(self.body, bg=T.BG)
        self.tab_holder.pack(fill="both", expand=True)
        self.tabs = {}
        self._tab_builders = {
            "shortcuts": self._build_shortcuts_tab,
            "recording": self._build_recording_tab,
        }

        # ---- Tab 1: General & Theme (eagerly built) ------------------------------------------------------------------
        t_gen = tk.Frame(self.tab_holder, bg=T.BG)
        g_left, g_right = two_columns(t_gen)
        self.card_general = SettingsCard(g_left, app, "General", "Startup, system tray, and window behaviour.",
                                         sm.by_group("settings", "general"))
        self.card_general.pack(fill="x", pady=(0, gap))
        self.cat_row = tk.Frame(self.card_general.footer, bg=T.SURFACE)
        self.cat_row.pack(fill="x", pady=(dp(2), 0))
        tk.Label(self.cat_row, text="cat", bg=T.SURFACE, fg=T.TEXT, font=font(10), anchor="w").pack(side="left")
        self.cat_toggle = Toggle(
            self.cat_row,
            value=app.cat_preview_visible(),
            command=app.set_cat_preview_visible,
            bg=T.SURFACE,
        )
        self.cat_toggle.pack(side="right")
        self.card_look = SettingsCard(g_right, app, "Appearance", "Refresh rate and highlight theme.",
                                      sm.by_group("settings", "appearance"))
        self.card_look.pack(fill="x", pady=(0, gap))

        about = Card(g_right, "Help and diagnostics", pad=18)
        about.pack(fill="x", pady=(0, gap))
        label(about.body, f"PhoneMic Receiver {VERSION}", T.TEXT, 12, "bold", bg=T.SURFACE, anchor="w").pack(fill="x")
        autowrap(tk.Label(about.body, text=self._versions(), bg=T.SURFACE, fg=T.DIM, font=font(9),
                          anchor="w", justify="left", wraplength=dp(240))).pack(fill="x", pady=(dp(4), dp(12)))
        button_row(about.body, [("Run setup wizard", lambda: app.show_page("wizard"), "primary"),
                                ("Copy diagnostics", self._copy_diag, "normal")]).pack(anchor="w")
        self.tabs["general"] = t_gen

        self._pick_tab("general")

    def _build_shortcuts_tab(self):
        app, gap = self.app, dp(GAP)
        t_keys = tk.Frame(self.tab_holder, bg=T.BG)
        keys = {k: (lambda row, k=k: HotkeyEntry(row, app, sm.BY_KEY[k])) for k in sm.BY_KEY
                if k.startswith("hotkeys.") and sm.BY_KEY[k].kind == "custom"}
        self.card_keys = SettingsCard(t_keys, app, "Global shortcuts", "Keys and mouse side buttons that work inside full-screen games.",
                                      sm.by_group("settings", "shortcuts"), keys)
        self.card_keys.pack(fill="x", pady=(0, gap))
        self.keys_note = hint(self.card_keys.footer, "")
        self.keys_note.pack(fill="x")
        self.tabs["shortcuts"] = t_keys
        self._sync_keys_note()

    def _build_recording_tab(self):
        app, gap = self.app, dp(GAP)
        t_rec = tk.Frame(self.tab_holder, bg=T.BG)
        r_left, r_right = two_columns(t_rec)

        def folder_control(row):
            box = tk.Frame(row, bg=T.SURFACE)
            self.folder = autowrap(tk.Label(box, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9),
                                            anchor="w", justify="left", wraplength=dp(240)))
            self.folder.pack(fill="x", pady=(0, dp(8)))
            button_row(box, [("Choose folder...", self._browse, "normal"), ("Open folder", self._open_folder, "ghost")]).pack(anchor="w")
            return box

        self.card_rec = SettingsCard(r_left, app, "Recording", "Destination folder and signal tap point.",
                                     sm.by_group("settings", "recording"), {"recording.folder": folder_control})
        self.card_rec.pack(fill="x", pady=(0, gap))
        self.update_folder()

        bak = Card(r_right, "Presets and configuration backups", pad=18)
        bak.pack(fill="x", pady=(0, gap))
        hint(bak.body, "Export presets to share with friends, or save a full settings backup file.").pack(fill="x", pady=(0, dp(10)))
        button_row(bak.body, [("Import presets...", app.import_presets, "normal"),
                              ("Export all presets...", app.export_all_presets, "normal")]).pack(anchor="w")
        button_row(bak.body, [("Export settings...", self._export, "normal"),
                              ("Import settings...", self._import, "normal")]).pack(anchor="w", pady=(dp(8), 0))
        button_row(bak.body, [("Open config folder", lambda: system.open_in_explorer(os.path.dirname(app.cfg.filepath)), "ghost"),
                              ("Reset all settings", self._reset_all, "danger")]).pack(anchor="w", pady=(dp(8), 0))
        self.cfg_path = autowrap(tk.Label(bak.body, text=app.cfg.filepath, bg=T.SURFACE, fg=T.DIM, font=font(8),
                                          anchor="w", justify="left", wraplength=dp(240)))
        self.cfg_path.pack(fill="x", pady=(dp(10), 0))
        self.tabs["recording"] = t_rec

    def _ensure_tab(self, tab_id):
        if tab_id not in self.tabs and tab_id in self._tab_builders:
            self._tab_builders[tab_id]()
            card = self.card_keys if tab_id == "shortcuts" else self.card_rec
            if card is not None:
                card.apply_view(self.app.advanced)

    def _pick_tab(self, tab_id):
        self._ensure_tab(tab_id)
        self.active_tab = tab_id
        for tid, frame in self.tabs.items():
            if tid == tab_id:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        if self.tab_picker.get() != tab_id:
            self.tab_picker.set(tab_id)

    @staticmethod
    def _versions():
        parts = [f"Python {sys.version.split()[0]}", f"NumPy {np.__version__}"]
        try:
            import sounddevice as sd
            parts.append(f"sounddevice {sd.__version__}")
            parts.append(sd.get_portaudio_version()[1])
        except Exception:
            parts.append("sounddevice is not available")
        return ", ".join(parts)

    def apply_view(self, advanced):
        for c in (self.card_general, self.card_look, self.card_rec, self.card_keys):
            if c is not None:
                c.apply_view(advanced)

    def _sync_keys_note(self):
        if self.keys_note is None:
            return
        if not self.app.hotkeys.available:
            self.keys_note.configure(
                text="In-app shortcuts (Ctrl+M/E/R/B/F, F10) work on Linux. Global background hotkeys require Windows."
            )
        else:
            self.keys_note.configure(text="Shortcuts pass through to games cleanly. Mouse side buttons work great for Push-to-Talk.")

    def sync_cat_toggle(self):
        if hasattr(self, "cat_toggle"):
            self.cat_toggle.set(self.app.cat_preview_visible(), notify=False)

    def on_show(self):
        a = self.app
        self._sync_keys_note()
        self.sync_cat_toggle()
        row = self.card_general.row_for("app.tray_icon")
        if row is not None and not a.tray.available:
            row.title_label.configure(text="Tray icon (needs the pystray package)")

    def update_folder(self):
        if self.folder is not None:
            self.folder.configure(text=self.app.cfg.data["recording"]["folder"] or system.default_recordings_dir())

    def _browse(self):
        d = filedialog.askdirectory(parent=self.app.root, title="Folder for recordings",
                                    initialdir=self.app.cfg.data["recording"]["folder"] or system.default_recordings_dir())
        if d:
            self.app.cfg.data["recording"]["folder"] = d
            self.app.cfg.save_soon()
            self.update_folder()

    def _open_folder(self):
        f = self.app.cfg.data["recording"]["folder"] or system.default_recordings_dir()
        os.makedirs(f, exist_ok=True)
        system.open_in_explorer(f)

    def _export(self):
        path = filedialog.asksaveasfilename(parent=self.app.root, defaultextension=".json", initialfile="phonemic_settings.json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            self.app.cfg.flush()
            try:
                shutil.copyfile(self.app.cfg.filepath, path)
                self.app.notify("Settings exported.", "good")
            except Exception as e:      # noqa: BLE001
                self.app.notify(f"Export failed: {e}", "error")

    def _import(self):
        path = filedialog.askopenfilename(parent=self.app.root, filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
            shutil.copyfile(path, self.app.cfg.filepath)
            self.app.cfg.load()
            messagebox.showinfo("Settings imported", "The settings were imported. Restart PhoneMic Receiver to apply them everywhere.", parent=self.app.root)
        except Exception as e:      # noqa: BLE001
            self.app.notify(f"Import failed: {e}", "error")

    def _reset_all(self):
        if messagebox.askyesno("Reset settings", "Reset every setting to its default? Your saved presets are kept.", parent=self.app.root):
            self.app.cfg.reset(keep_presets=True)
            self.app.cfg.flush()
            messagebox.showinfo("Settings reset", "Done. Restart PhoneMic Receiver to apply the defaults.", parent=self.app.root)

    def _copy_diag(self):
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(self.app.diagnostics_text())
        self.app.notify("Diagnostics copied.", "good", 4000)

    def focus_setting(self, s):
        tab_map = {"general": "general", "appearance": "general", "shortcuts": "shortcuts", "recording": "recording"}
        self._pick_tab(tab_map.get(s.group, "general"))
        for card in (self.card_general, self.card_look, self.card_rec, self.card_keys):
            if card is None:
                continue
            row = card.row_for(s.key)
            if row is not None:
                row.set_details(True)
                row.flash()
                self.scroll.scroll_to(row)
                return


# ==============================================================================
# DIAGNOSTICS
# ==============================================================================
class LogPage(Page):
    ROWS = [("state", "State"), ("client", "Phone"), ("packets", "Packets received"), ("lost", "Lost on the network"),
            ("reordered", "Arrived out of order"), ("late", "Arrived too late"), ("dup", "Duplicates"), ("plc", "Concealed frames"),
            ("jitter", "Network jitter"), ("buffer", "Network buffer"), ("grown", "Adaptive growths"),
            ("drift", "Drift corrections"), ("underruns", "Output underruns"), ("restarts", "Stream restarts"),
            ("dsp", "Effects time per block"), ("device", "Output stream")]

    def build(self):
        app = self.app
        gap = dp(GAP)

        # Compact KPI StatTiles strip (4 columns wide <-> 2x2 narrow)
        self._tiles_wrap = tiles = tk.Frame(self.body, bg=T.BG)
        tiles.pack(fill="x", pady=(0, gap))
        self._tile_cols = None
        self.t_state = StatTile(tiles, "Stream State", "UDP / TCP receiver", accent=T.ACCENT)
        self.t_jit = StatTile(tiles, "Network Jitter", "Arrival variance", accent=T.GOOD)
        self.t_loss = StatTile(tiles, "Packet Loss", "Concealed gaps", accent=T.WARN)
        self.t_dsp = StatTile(tiles, "DSP Block Time", "10 ms frame budget", accent=T.BLUE)
        self._stat_tiles = (self.t_state, self.t_jit, self.t_loss, self.t_dsp)
        self._tiles_job = None
        self._pending_tiles_w = None
        self._layout_tiles(dp(700))
        tiles.bind("<Configure>", lambda e: self._schedule_tiles(e.width), add="+")
        self._slow_cache = None

        c = Card(self.body, "Live counters", pad=18)
        c.pack(fill="x", pady=(0, gap))
        grid = tk.Frame(c.body, bg=T.SURFACE)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="g")
        grid.grid_columnconfigure(1, weight=1, uniform="g")
        self.vals = {}
        for i, (k, title) in enumerate(self.ROWS):
            cell = tk.Frame(grid, bg=T.SURFACE)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else dp(16), dp(16) if i % 2 == 0 else 0), pady=2)
            label(cell, title, T.MUTED, 9, bg=T.SURFACE).pack(side="left")
            v = label(cell, "-", T.TEXT, 10, "bold", bg=T.SURFACE)
            v.pack(side="right")
            self.vals[k] = v
        button_row(c.body, [("Reset counters", app.rx.reset_stats, "normal")]).pack(anchor="w", pady=(dp(12), 0))

        c = Card(self.body, "System Self-Test" if system.IS_LINUX else "Windows System Self-Test", pad=18)
        c.pack(fill="x", pady=(0, gap))
        hint(c.body, "Checks shortcuts, tray icon, firewall rules, virtual microphone, and audio backend availability.").pack(fill="x", pady=(0, dp(10)))
        button_row(c.body, [("Run self-test", self._selftest, "primary"), ("Copy result", self._copy_selftest, "normal")]).pack(anchor="w")
        self.selftest_box = ScrollTextBox(c.body, height=9, text_font=(MONO_FONT, 9), bg=T.SIDEBAR, wrap="none")
        self.selftest_box.pack(fill="x", pady=(dp(10), 0))
        self.selftest_text = self.selftest_box.textbox
        self.selftest_text.configure(state="disabled")
        self.selftest_result = ""

        c = Card(self.body, "Event Log", pad=18)
        c.pack(fill="both", expand=True, pady=(0, gap))
        button_row(c.body, [("Copy diagnostics", self._copy, "primary"), ("Save diagnostics...", self._save, "normal"),
                            ("Open crash log", self._crash, "ghost")]).pack(anchor="w", pady=(0, dp(10)))
        self.log_box = ScrollTextBox(c.body, height=14, text_font=(MONO_FONT, 9), bg=T.SIDEBAR, wrap="none")
        self.log_box.pack(fill="both", expand=True)
        self.text = self.log_box.textbox
        self.text.tag_configure("warn", foreground=T.WARN)
        self.text.tag_configure("error", foreground=T.BAD)
        self.text.tag_configure("info", foreground=T.MUTED)
        self._serial = -1

    def _selftest(self):
        from . import selftest
        self._set_selftest("Running the checks. The tray icon appears for a moment...")

        def work():
            text = selftest.format_results(selftest.run_selftest())
            self.app.post(lambda: self._set_selftest(text))

        threading.Thread(target=work, name="PM-SelfTest", daemon=True).start()

    def _set_selftest(self, text):
        self.selftest_result = text
        self.selftest_text.configure(state="normal")
        self.selftest_text.delete("1.0", "end")
        self.selftest_text.insert("end", text)
        self.selftest_text.configure(state="disabled")

    def _copy_selftest(self):
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(self.selftest_result or "The self-test has not been run yet.")
        self.app.notify("Self-test result copied.", "good", 2500)

    def _copy(self):
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(self.app.diagnostics_text())
        self.app.notify("Diagnostics copied to clipboard.", "good", 2500)

    def _save(self):
        path = filedialog.asksaveasfilename(parent=self.app.root, defaultextension=".txt", initialfile="phonemic_diagnostics.txt",
                                            filetypes=[("Text", "*.txt")])
        if path:
            self.app._write_text(path, self.app.diagnostics_text(), "Diagnostics saved.")

    def _crash(self):
        p = system.crash_log_path()
        if os.path.exists(p):
            system.open_in_explorer(p)
        else:
            self.app.notify("There is no crash log. Nothing has crashed.", "good")

    def _schedule_tiles(self, width_px):
        if not width_px or width_px < 40:
            return
        self._pending_tiles_w = width_px
        if self._tiles_job:
            try:
                self._tiles_wrap.after_cancel(self._tiles_job)
            except Exception:
                pass
        self._tiles_job = self._tiles_wrap.after(16, self._run_scheduled_tiles)

    def _run_scheduled_tiles(self):
        self._tiles_job = None
        if self._tiles_wrap.winfo_exists() and self._pending_tiles_w is not None:
            self._layout_tiles(self._pending_tiles_w)

    def _layout_tiles(self, width_px=None):
        if not width_px or width_px < 40:
            return
        want = 2 if width_px < dp(620) else 4
        if want == self._tile_cols:
            return
        self._tile_cols = want
        tiles = self._tiles_wrap
        for tile in self._stat_tiles:
            tile.grid_forget()
        if want == 4:
            for i in range(4):
                tiles.grid_columnconfigure(i, weight=1, uniform="t")
            for i, tile in enumerate(self._stat_tiles):
                tile.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else dp(5), 0 if i == 3 else dp(5)))
        else:
            tiles.grid_columnconfigure(0, weight=1, uniform="t")
            tiles.grid_columnconfigure(1, weight=1, uniform="t")
            tiles.grid_columnconfigure(2, weight=0, uniform="")
            tiles.grid_columnconfigure(3, weight=0, uniform="")
            for i, tile in enumerate(self._stat_tiles):
                r, c = divmod(i, 2)
                tile.grid(row=r, column=c, sticky="ew", padx=(0 if c == 0 else dp(5), dp(5) if c == 0 else 0),
                          pady=(0, dp(8) if r == 0 else 0))

    def on_show(self):
        self._serial = -1
        self._slow_cache = None
        self.refresh_slow()

    def refresh_slow(self):
        rx = self.app.rx
        st, jb = rx.stats, rx.jb
        state = rx.state()
        client_txt = f"{rx.client_ip or '-'}  {rx.transport if rx.client_ip else ''}"
        pkts_txt = f"{st.packets:,}"
        lost_txt = f"{st.lost}  ({st.loss_pct:.2f}%)"
        reord_txt = str(st.reordered)
        late_txt = str(jb.late)
        dup_txt = str(jb.dup)
        plc_txt = str(st.plc_frames)
        jit_txt = f"{st.jitter_ms:.2f} ms"
        buf_txt = f"{jb.depth_ms:.0f} of {jb.target_ms:.0f} ms"
        grown_txt = str(jb.grown)
        drift_txt = str(jb.skipped_total)
        under_txt = f"{rx.main.starved} (xruns {rx.main.xruns})"
        rest_txt = str(jb.restarts)
        dsp_txt = f"{rx.processor.dsp_ms:.3f} ms"
        dev_txt = "open" if rx.main.active else "closed"
        dev_fg = T.GOOD if rx.main.active else T.WARN

        slow_key = (state, client_txt, pkts_txt, lost_txt, reord_txt, late_txt, dup_txt, plc_txt, jit_txt, buf_txt,
                    grown_txt, drift_txt, under_txt, rest_txt, dsp_txt, dev_txt, st.jitter_ms < 15, st.jitter_ms < 40,
                    st.loss_pct < 0.5, st.loss_pct < 3.0)
        if slow_key != self._slow_cache:
            self._slow_cache = slow_key
            self.t_state.set(state.capitalize(), T.GOOD if state == "streaming" else (T.BAD if state == "error" else T.ACCENT))
            self.t_jit.set(f"{st.jitter_ms:.1f} ms", T.GOOD if st.jitter_ms < 15 else (T.WARN if st.jitter_ms < 40 else T.BAD))
            self.t_loss.set(f"{st.loss_pct:.2f}%", T.GOOD if st.loss_pct < 0.5 else (T.WARN if st.loss_pct < 3 else T.BAD))
            self.t_dsp.set(f"{rx.processor.dsp_ms:.2f} ms", T.BLUE_HI)

            v = self.vals
            v["state"].configure(text=state)
            v["client"].configure(text=client_txt)
            v["packets"].configure(text=pkts_txt)
            v["lost"].configure(text=lost_txt)
            v["reordered"].configure(text=reord_txt)
            v["late"].configure(text=late_txt)
            v["dup"].configure(text=dup_txt)
            v["plc"].configure(text=plc_txt)
            v["jitter"].configure(text=jit_txt)
            v["buffer"].configure(text=buf_txt)
            v["grown"].configure(text=grown_txt)
            v["drift"].configure(text=drift_txt)
            v["underruns"].configure(text=under_txt)
            v["restarts"].configure(text=rest_txt)
            v["dsp"].configure(text=dsp_txt)
            v["device"].configure(text=dev_txt, fg=dev_fg)

        log = rx.log
        if log.serial != self._serial:
            self._serial = log.serial
            at_end = self.text.yview()[1] > 0.98
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            for ts, lvl, msg in log.entries:
                self.text.insert("end", f"{time.strftime('%H:%M:%S', time.localtime(ts))}  {msg}\n", lvl)
            self.text.configure(state="disabled")
            if at_end:
                self.text.see("end")
