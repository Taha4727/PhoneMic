"""Pages of the main window. Settings rows come from the registry (settings_meta), so labels, explanations, ranges and
defaults are defined in exactly one place."""
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

from . import system, settings_meta as sm
from .const import VERSION, VB_CABLE_URL, CABLE_HINT
from .widgets import T, dp, font, autowrap, FlatButton, Segmented, Combo, Card, Tooltip
from .ui_kit import SettingRow, SettingsCard, PanelHeader, StageList, EQEditor, HotkeyEntry
from .gui import Page, fmt_time

GAP = 14
EQ_FREQS = np.geomspace(20.0, 20000.0, 160)


def label(parent, text, fg=None, size=10, weight="normal", bg=None, **kw):
    return tk.Label(parent, text=text, bg=bg or parent.cget("bg"), fg=fg or T.TEXT, font=font(size, weight), **kw)


def hint(parent, text):
    return autowrap(tk.Label(parent, text=text, bg=parent.cget("bg"), fg=T.DIM, font=font(9), anchor="w", justify="left",
                             wraplength=dp(240)))


def two_columns(parent):
    cols = tk.Frame(parent, bg=T.BG)
    cols.pack(fill="both", expand=True)
    cols.grid_columnconfigure(0, weight=1, uniform="c")
    cols.grid_columnconfigure(1, weight=1, uniform="c")
    left = tk.Frame(cols, bg=T.BG)
    right = tk.Frame(cols, bg=T.BG)
    left.grid(row=0, column=0, sticky="new", padx=(0, dp(GAP // 2)))
    right.grid(row=0, column=1, sticky="new", padx=(dp(GAP // 2), 0))
    return left, right


def button_row(parent, items, bg=None):
    """items: [(text, command, style)] laid out left to right."""
    row = tk.Frame(parent, bg=bg or parent.cget("bg"))
    for i, (text, cmd, style) in enumerate(items):
        FlatButton(row, text, cmd, style=style, size=9).pack(side="left", padx=(0 if i == 0 else dp(6), 0))
    return row


# ==============================================================================
# SOUND: the signal chain
# ==============================================================================
class SoundPage(Page):
    """Left: the processing order with a light per stage. Right: the settings of the chosen stage."""

    def build(self):
        app = self.app
        gap = dp(GAP)
        self.panels, self.stage_id = {}, None
        self.eq_band = 3
        self.editor = None

        bar = Card(self.body, pad=14)
        bar.pack(fill="x", pady=(0, gap))
        top = tk.Frame(bar.body, bg=T.SURFACE)
        top.pack(fill="x")
        label(top, "Preset", bg=T.SURFACE).pack(side="left")
        combo = Combo(top, app.fx_preset_names(), width=30, command=app.apply_fx_preset)
        combo.pack(side="left", padx=(dp(10), dp(10)))
        app.preset_combos.append(combo)
        mark = tk.Label(top, text="", bg=T.SURFACE, fg=T.WARN, font=font(9))
        mark.pack(side="left")
        app.preset_marks.append(mark)
        button_row(bar.body, [("Save as...", app.save_fx_preset, "primary"), ("Delete", app.delete_fx_preset, "danger"),
                              ("Import...", app.import_presets, "normal"), ("Export...", lambda: app.export_preset("fx"), "normal"),
                              ("Reset to default", lambda: app.apply_fx_preset("Default (Studio Clean)"), "ghost")]
                   ).pack(anchor="w", pady=(dp(10), 0))

        split = tk.Frame(self.body, bg=T.BG)
        split.pack(fill="both", expand=True)
        split.grid_columnconfigure(1, weight=1)
        rail = tk.Frame(split, bg=T.BG)
        rail.grid(row=0, column=0, sticky="n", padx=(0, gap))
        tk.Label(rail, text="Signal path", bg=T.BG, fg=T.DIM, font=font(9), anchor="w").pack(fill="x", padx=dp(4), pady=(0, dp(6)))
        self.chain = StageList(rail, sm.STAGES, self.pick_stage, bg=T.BG)
        self.chain.pack(fill="x")
        self.holder = tk.Frame(split, bg=T.BG)
        self.holder.grid(row=0, column=1, sticky="nsew")

        app.binder.listen_any(self._changed)
        self.pick_stage("noise")
        self.refresh_leds()

    # ---- stage panels ----------------------------------------------------------------------------------------------------
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
        self.refresh_readout()

    def build_panel(self, stage):
        app = self.app
        frame = tk.Frame(self.holder, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER)
        header = PanelHeader(frame, stage.title, stage.blurb, sm.BY_KEY[stage.enable] if stage.enable else None, app)
        header.pack(fill="x")
        body = tk.Frame(frame, bg=T.SURFACE)
        body.pack(fill="both", expand=True, padx=dp(18), pady=dp(16))
        foot = tk.Frame(body, bg=T.SURFACE)
        foot.pack(side="bottom", fill="x")
        FlatButton(foot, "Reset this stage", lambda sid=stage.id: self.reset_stage(sid), style="ghost", size=9).pack(anchor="e", pady=(dp(4), 0))
        panel = {"frame": frame, "header": header, "body": body, "foot": foot, "rows": [], "bands": {}, "band_frames": {}}
        settings = [s for s in sm.by_group("sound", stage.id) if s.key != stage.enable]
        if stage.id == "eq":
            self.build_eq(panel, settings)
        else:
            panel["rows"] = [SettingRow(body, app, s) for s in settings]
        return panel

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
        hint(top, "Drag a numbered point on the graph, or use the controls below. Scroll over a point to change its width. "
                  "Right-click a point to switch that band on or off.").pack(fill="x", pady=(dp(6), 0))
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
        for s in sm.by_group("sound", sid):
            if s.key != sm.STAGE_BY_ID[sid].enable:
                self.app.binder.reset(s)
        self.app.notify(f"{sm.STAGE_BY_ID[sid].title} was reset to its defaults.", "good", 3000)

    # ---- equalizer wiring ------------------------------------------------------------------------------------------------------
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

    # ---- live state ----------------------------------------------------------------------------------------------------------------
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
            return (f"Reducing {p.gain_reduction_db:.1f} dB", T.ACCENT_HI) if p.gain_reduction_db > 0.3 else ("Not reducing", T.DIM)
        if sid == "deess" and p.deess_enabled:
            return (f"Reducing {p.deess_reduction_db:.1f} dB", T.ACCENT_HI) if p.deess_reduction_db > 0.3 else ("Not reducing", T.DIM)
        if sid == "agc" and p.agc_enabled:
            return f"Gain {p.agc.gain_db:+.1f} dB", T.ACCENT_HI
        if sid == "gate" and p.gate_enabled:
            return ("Open", T.GOOD) if p.gate.is_open else ("Closed", T.DIM)
        if sid == "noise" and p.smart_noise_cancel and p.noise_cancel_amount > 0.02:
            return f"Adds {p.denoiser.delay_ms:.0f} ms", T.MUTED
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

    def on_show(self):
        self.refresh_leds()
        self.refresh_eq()
        self.refresh_readout()

    def refresh_slow(self):
        self.refresh_leds()
        self.refresh_readout()

    def focus_setting(self, s):
        if s.group in sm.STAGE_BY_ID and not sm.STAGE_BY_ID[s.group].link:
            self.pick_stage(s.group)
        panel = self.panels.get(s.group)
        if not panel:
            return
        rows = list(panel["rows"])
        if s.group == "eq" and s.key[:2] == "eq" and s.key[2:3].isdigit():
            self.eq_pick(int(s.key[2]))
            rows = panel["bands"][int(s.key[2])]
        for r in rows:
            if r.setting.key == s.key:
                r.set_details(True)
                r.flash()
                self.scroll.scroll_to(r)
                return


# ==============================================================================
# VOICE CHANGER
# ==============================================================================
class VoicePage(Page):
    def build(self):
        app = self.app
        from .dsp import VoiceChanger
        self.VC = VoiceChanger
        gap = dp(GAP)
        vc = app.proc.voice_changer

        top = Card(self.body, "Voice changer", pad=18)
        top.pack(fill="x", pady=(0, gap))
        self.enable_row = SettingRow(top.body, app, sm.BY_KEY["vc.enabled"])
        self.enable_row.pack(fill="x", pady=(0, dp(14)))
        row = tk.Frame(top.body, bg=T.SURFACE)
        row.pack(fill="x")
        label(row, "Preset", bg=T.SURFACE).pack(side="left")
        self.combo = Combo(row, app.voice_preset_names(), width=28, command=app.apply_voice_preset)
        self.combo.set(vc.active_preset)
        self.combo.pack(side="left", padx=(dp(10), 0))
        app.voice_combos.append(self.combo)
        button_row(top.body, [("Save as...", self._save, "primary"), ("Delete", self._delete, "danger"),
                              ("Import...", app.import_presets, "normal"), ("Export...", lambda: app.export_preset("voice"), "normal")]
                   ).pack(anchor="w", pady=(dp(10), 0))

        card = Card(self.body, "Character", pad=18)
        card.pack(fill="x", pady=(0, gap))
        autowrap(tk.Label(card.body, text="Each character changes the colour of the voice. Pitch and effect amount are set below.",
                          bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left", wraplength=dp(240))).pack(fill="x", pady=(0, dp(10)))
        grid = tk.Frame(card.body, bg=T.SURFACE)
        grid.pack(fill="x")
        self.mode_buttons = {}
        for i, mode in enumerate(VoiceChanger.MODES):
            grid.grid_columnconfigure(i % 4, weight=1, uniform="m")
            b = FlatButton(grid, mode.replace(" / ", "\n"), command=lambda m=mode: self._mode(m), size=9, pady=9)
            b.grid(row=i // 4, column=i % 4, sticky="nsew", padx=dp(3), pady=dp(3))
            self.mode_buttons[mode] = b
        self.desc = autowrap(tk.Label(card.body, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left", wraplength=dp(240)))
        self.desc.pack(fill="x", pady=(dp(10), 0))

        card = Card(self.body, "Tuning", pad=18)
        card.pack(fill="x", pady=(0, gap))
        self.pitch_row = SettingRow(card.body, app, sm.BY_KEY["vc.pitch_semitones"])
        self.pitch_row.pack(fill="x", pady=(0, dp(14)))
        self.mix_row = SettingRow(card.body, app, sm.BY_KEY["vc.mix"])
        self.mix_row.pack(fill="x", pady=(0, dp(10)))
        self.latency = hint(card.body, "")
        self.latency.pack(fill="x")
        self.sync()

    def _mode(self, mode):
        vc = self.app.proc.voice_changer
        vc.mode = mode
        vc.active_preset = "Custom"
        self.app.binder.persist_voice()
        self.app.refresh_preset_ui()
        self.sync()

    def _save(self):
        app = self.app
        name = app.ask_name("Save voice preset", "Name for your voice preset:")
        if not name:
            return
        from . import presets_io as pio
        name = pio.clean_name(name)
        if name in self.VC.BUILTIN_PRESETS:
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

    def _delete(self):
        app = self.app
        name = app.proc.voice_changer.active_preset
        if name not in app.cfg.data["user_voice_presets"]:
            app.notify("Built-in presets cannot be deleted.", "warn")
            return
        if messagebox.askyesno("Delete preset", f"Delete your voice preset \"{name}\"?", parent=app.root):
            del app.cfg.data["user_voice_presets"][name]
            app.apply_voice_preset("Normal (Bypass)")

    def sync(self):
        app = self.app
        vc = app.proc.voice_changer
        for r in (self.enable_row, self.pitch_row, self.mix_row):
            r.refresh()
        self.combo.set_values(app.voice_preset_names(), vc.active_preset)
        for m, b in self.mode_buttons.items():
            b.set_style("active" if m == vc.mode else "normal")
        self.desc.configure(text=self.VC.MODE_DESCRIPTIONS.get(vc.mode, ""))
        ms = vc.latency_ms
        self.latency.configure(text=(f"This setting adds about {ms:.0f} ms of delay." if ms else "This setting adds no delay.")
                               + ("" if vc.enabled else " The voice changer is currently off."))

    def on_show(self):
        self.sync()

    def focus_setting(self, s):
        row = {"vc.enabled": self.enable_row, "vc.pitch_semitones": self.pitch_row, "vc.mix": self.mix_row}.get(s.key)
        if row:
            row.set_details(True)
            row.flash()
            self.scroll.scroll_to(row)


# ==============================================================================
# AUDIO DEVICES
# ==============================================================================
class DevicesPage(Page):
    JITTER_PROFILES = [(10, "Ultra-low"), (20, "Low"), (30, "Balanced"), (60, "Stable"), (120, "Max stability")]

    def build(self):
        app, rx = self.app, self.app.rx
        gap = dp(GAP)
        self.dev_map = {}
        self.out_combo = self.mon_combo = None

        def api_control(row):
            cur = app.cfg.data["audio"]["api"]
            seg = Segmented(row, [("auto", "Auto"), ("WASAPI", "WASAPI"), ("DirectSound", "DirectSound"), ("MME", "MME")],
                            cur if cur in ("auto", "WASAPI", "DirectSound", "MME") else "auto", self._api, bg=T.SURFACE)
            return seg

        def output_control(row):
            box = tk.Frame(row, bg=T.SURFACE)
            self.out_combo = Combo(box, [], width=44, command=self._out)
            self.out_combo.pack(anchor="w")
            button_row(box, [("Play test tone", rx.play_test_tone, "primary"), ("Refresh devices", self._refresh, "normal"),
                             ("Windows sound settings", lambda: self._open("ms-settings:sound"), "ghost"),
                             ("Recording devices", lambda: self._open("control mmsys.cpl,,1"), "ghost")]).pack(anchor="w", pady=(dp(8), 0))
            return box

        def jitter_control(row):
            ms = app.cfg.data["audio"]["jitter_ms"]
            nearest = min((p[0] for p in self.JITTER_PROFILES), key=lambda v: abs(v - ms))
            self.jit_seg = Segmented(row, [(v, n) for v, n in self.JITTER_PROFILES], nearest, self._jitter, bg=T.SURFACE)
            return self.jit_seg

        def monitor_control(row):
            self.mon_combo = Combo(row, [], width=44, command=self._mon)
            return self.mon_combo

        self.card_out = SettingsCard(self.body, app, "Output device", "Where the PC plays the phone's voice.",
                                     sm.by_group("devices", "output"), {"audio.api": api_control, "audio.output_device": output_control})
        self.card_out.pack(fill="x", pady=(0, gap))
        self.out_status = autowrap(tk.Label(self.card_out.footer, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left", wraplength=dp(300)))
        self.out_status.pack(fill="x", pady=(dp(4), 0))
        cable = tk.Frame(self.card_out.footer, bg=T.SURFACE)
        cable.pack(fill="x", pady=(dp(8), 0))
        self.cable_label = autowrap(tk.Label(cable, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left", wraplength=dp(300)))
        self.cable_label.pack(side="left", fill="x", expand=True)
        self.cable_btn = FlatButton(cable, "Get VB-CABLE (free)", lambda: webbrowser.open(VB_CABLE_URL), size=9)

        self.card_lat = SettingsCard(self.body, app, "Delay and stability", "Trade a little delay for protection against network hiccups.",
                                     sm.by_group("devices", "latency"), {"audio.jitter_ms": jitter_control})
        self.card_lat.pack(fill="x", pady=(0, gap))
        self.breakdown = autowrap(tk.Label(self.card_lat.footer, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left", wraplength=dp(300)))
        self.breakdown.pack(fill="x", pady=(dp(4), 0))

        self.card_mon = SettingsCard(self.body, app, "Monitoring", "Hear your processed voice on headphones.",
                                     sm.by_group("devices", "monitor"), {"audio.monitor_device": monitor_control})
        self.card_mon.pack(fill="x", pady=(0, gap))
        self.vol_row = SettingRow(self.card_mon.footer, app, sm.BY_KEY["monitor_volume"])
        self.vol_row.pack(fill="x", pady=(0, dp(10)))
        self.mon_btn = FlatButton(self.card_mon.footer, "Start monitoring", app.toggle_monitor, size=9)
        self.mon_btn.pack(anchor="w")
        self.fill_devices()

    # ---- helpers ---------------------------------------------------------------------------------------------------------------
    def apply_view(self, advanced):
        for c in (self.card_out, self.card_lat, self.card_mon):
            c.apply_view(advanced)

    def _open(self, target):
        try:
            if system.IS_WIN:
                if target.startswith("control"):
                    subprocess.Popen(["control.exe", target.split(" ", 1)[1]])           # no console window
                else:
                    os.startfile(target)  # noqa: S606
            else:
                self.app.notify("This is only available on Windows.", "warn")
        except Exception as e:      # noqa: BLE001
            self.app.notify(f"Could not open it: {e}", "error")

    def fill_devices(self):
        rx = self.app.rx
        pool = system.devices_for_api(rx.devices, rx.api)
        self.dev_map = {d.name: d for d in pool}
        names = list(self.dev_map)
        if self.out_combo is not None:
            self.out_combo.set_values(names, rx.main_dev.name if rx.main_dev else "")
        if self.mon_combo is not None:
            self.mon_combo.set_values(names, rx.monitor_dev.name if rx.monitor_dev else "")
        has_cable = any(d.is_cable for d in pool)
        if has_cable:
            self.cable_label.configure(text="VB-CABLE is installed. In Discord, OBS or Zoom choose \"CABLE Output (VB-Audio Virtual Cable)\" as your microphone.", fg=T.GOOD)
            self.cable_btn.pack_forget()
        else:
            self.cable_label.configure(text=f"No virtual cable found. To use your phone as a microphone in other apps, install VB-CABLE and then choose \"{CABLE_HINT}\" above.", fg=T.WARN)
            self.cable_btn.pack(side="right", padx=(dp(8), 0))

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

    def _mon(self, name):
        d = self.dev_map.get(name)
        if d:
            self.app.rx.set_monitor_device(d)

    def _jitter(self, ms):
        self.app.rx.set_jitter(int(ms), self.app.cfg.data["audio"]["adaptive_jitter"])

    def on_show(self):
        self.fill_devices()

    def refresh_slow(self):
        rx = self.app.rx
        if rx.main.error:
            self.out_status.configure(text=f"This device could not be opened: {rx.main.error}", fg=T.BAD)
        elif rx.main.active and rx.main_dev:
            self.out_status.configure(text=f"Playing on {rx.main_dev.name} through {rx.main_dev.api}, {rx.main.channels} channels, "
                                           f"device delay {rx.main.latency_ms:.0f} ms.", fg=T.MUTED)
        else:
            self.out_status.configure(text="No output stream is open. Choose a device above.", fg=T.WARN)
        jb = rx.jb
        self.breakdown.configure(
            text=f"Right now: network buffer {jb.depth_ms:.0f} ms (target {jb.target_ms:.0f}), sound card {rx.main.latency_ms:.0f} ms, "
                 f"effects {rx.processor.latency_ms:.0f} ms, about {rx.latency_estimate_ms():.0f} ms in total. "
                 f"Concealed gaps {rx.stats.plc_frames}, buffer growths {jb.grown}.")
        self.mon_btn.set_text("Stop monitoring" if rx.monitoring else "Start monitoring")
        self.mon_btn.set_style("active" if rx.monitoring else "normal")

    def focus_setting(self, s):
        for card in (self.card_out, self.card_lat, self.card_mon):
            row = card.row_for(s.key)
            if row is not None:
                row.set_details(True)
                row.flash()
                self.scroll.scroll_to(row)
                return
        if s.key == "monitor_volume":
            self.vol_row.set_details(True)
            self.vol_row.flash()


# ==============================================================================
# NETWORK
# ==============================================================================
class NetworkPage(Page):
    BADGES = {"Wi-Fi": T.ACCENT, "Ethernet": T.VIOLET, "USB Tether": T.GOOD, "PC Hotspot": T.WARN, "Virtual": T.DIM, "Network": T.MUTED}

    def build(self):
        app, rx = self.app, self.app.rx
        gap = dp(GAP)
        left, right = two_columns(self.body)

        c = Card(left, "This PC's addresses", pad=18)
        c.pack(fill="x", pady=(0, gap))
        hint(c.body, "Type one of these into the phone, or let the phone find this PC automatically.").pack(fill="x", pady=(0, dp(10)))
        self.addr_box = tk.Frame(c.body, bg=T.SURFACE)
        self.addr_box.pack(fill="x")
        self._addr_key = None
        FlatButton(c.body, "Rescan adapters", self._rescan, size=9).pack(anchor="w", pady=(dp(10), 0))

        c = Card(left, "Phone connection", pad=18)
        c.pack(fill="x", pady=(0, gap))
        self.conn = {}
        for key, title in (("client", "Phone"), ("transport", "Transport"), ("since", "Connected for"), ("packets", "Packets received"),
                           ("ignored", "Packets from other phones")):
            r = tk.Frame(c.body, bg=T.SURFACE)
            r.pack(fill="x", pady=2)
            label(r, title, T.MUTED, 9, bg=T.SURFACE).pack(side="left")
            v = label(r, "-", T.TEXT, 10, "bold", bg=T.SURFACE)
            v.pack(side="right")
            self.conn[key] = v
        FlatButton(c.body, "Reset connection", self._reset, size=9).pack(anchor="w", pady=(dp(10), 0))

        def port_control(row):
            box = tk.Frame(row, bg=T.SURFACE)
            self.port_var = tk.StringVar(value=str(app.cfg.data["network"]["port"]))
            e = tk.Entry(box, textvariable=self.port_var, width=8, bg=T.SURFACE2, fg=T.TEXT, insertbackground=T.TEXT, relief="flat",
                         font=font(12, "normal", True), justify="center", highlightthickness=1, highlightbackground=T.BORDER,
                         highlightcolor=T.ACCENT)
            e.pack(side="left", ipady=dp(3))
            e.bind("<Return>", lambda ev: self._apply_port())
            FlatButton(box, "Apply", self._apply_port, style="primary", size=9).pack(side="left", padx=(dp(8), 0))
            return box

        self.card_listen = SettingsCard(right, app, "Listening", "How the PC accepts audio from the phone.",
                                        sm.by_group("network", "listen"), {"network.port": port_control})
        self.card_listen.pack(fill="x", pady=(0, gap))
        self.status = {}
        for key, title in (("udp", "UDP audio"), ("tcp", "TCP audio"), ("fw", "Windows Firewall")):
            r = tk.Frame(self.card_listen.footer, bg=T.SURFACE)
            r.pack(fill="x", pady=2)
            label(r, title, T.MUTED, 9, bg=T.SURFACE).pack(side="left")
            v = label(r, "-", T.TEXT, 10, "bold", bg=T.SURFACE)
            v.pack(side="right")
            self.status[key] = v
        FlatButton(self.card_listen.footer, "Fix firewall (asks for administrator approval)", app.fix_firewall, style="primary", size=9).pack(anchor="w", pady=(dp(10), 0))
        hint(self.card_listen.footer, "This adds rules for the port on every network profile. USB tethering needs it because Windows treats the tether as a public network.").pack(fill="x", pady=(dp(6), 0))

        self.card_opts = SettingsCard(right, app, "Connection options", "Rules for finding and accepting phones.", sm.by_group("network", "options"))
        self.card_opts.pack(fill="x", pady=(0, gap))

        c = Card(right, "How to connect", pad=18)
        c.pack(fill="x", pady=(0, gap))
        for line in ("Put the phone and this PC on the same Wi-Fi, or plug in USB and turn on USB tethering.",
                     "Open PhoneMic on the phone and choose Wi-Fi or USB.",
                     "Tap Scan or Auto-Detect PC, or type one of the addresses shown on this page.",
                     "Start streaming. If nothing arrives, press Fix firewall."):
            autowrap(tk.Label(c.body, text=line, bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left", wraplength=dp(240))).pack(fill="x", pady=2)
        self.refresh_addresses()

    def apply_view(self, advanced):
        self.card_listen.apply_view(advanced)
        self.card_opts.apply_view(advanced)

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
        self.app.notify(f"Now listening on port {port}. Enter the same port on the phone if it has a port setting.", "good", 6000)

    def _rescan(self):
        self.app.rx.netinfo.refresh_async(lambda res: self.app.root.after(0, self.refresh_addresses))
        self.app.notify("Scanning network adapters...", "info", 2000)

    def _reset(self):
        rx = self.app.rx
        rx.jb.reset()
        rx.stats.reset_session()
        rx.client_ip, rx.client_addr = "", None
        self.app.notify("Connection reset. Waiting for the phone.", "good", 2500)

    def refresh_addresses(self):
        ifaces = self.app.rx.netinfo.get()
        key = tuple((i.category, i.ip) for i in ifaces)
        if key == self._addr_key:
            return
        self._addr_key = key
        for w in self.addr_box.winfo_children():
            w.destroy()
        if not ifaces:
            label(self.addr_box, "No network adapters found.", T.WARN, 10, bg=T.SURFACE).pack(anchor="w")
        for i in ifaces:
            r = tk.Frame(self.addr_box, bg=T.SURFACE)
            r.pack(fill="x", pady=dp(3))
            tk.Label(r, text=f" {i.category} ", bg=T.SURFACE2, fg=self.BADGES.get(i.category, T.MUTED), font=font(8, "bold"), width=11).pack(side="left")
            ip = tk.Label(r, text=i.ip, bg=T.SURFACE, fg=T.TEXT, font=font(14, "bold", True), cursor="hand2")
            ip.pack(side="left", padx=dp(10))
            ip.bind("<Button-1>", lambda e, a=i.ip: self.app.copy(a, "Copied the address"))
            FlatButton(r, "Copy", lambda a=i.ip: self.app.copy(a, "Copied the address"), size=8, padx=8, pady=3).pack(side="right")

    def on_show(self):
        self.refresh_addresses()

    def refresh_slow(self):
        app, rx = self.app, self.app.rx
        self.refresh_addresses()
        st = rx.stats
        live = rx.state() in ("streaming", "muted", "lost")
        self.conn["client"].configure(text=rx.client_ip or "none yet")
        self.conn["transport"].configure(text=rx.transport if rx.client_ip else "-")
        self.conn["since"].configure(text=fmt_time(time.monotonic() - st.stream_start) if live and st.stream_start else "-")
        self.conn["packets"].configure(text=f"{st.packets:,}")
        self.conn["ignored"].configure(text=str(st.ignored))
        net = rx.net
        self.status["udp"].configure(text="Port unavailable" if net.udp_error else f"Listening on {net.port}", fg=T.BAD if net.udp_error else T.GOOD)
        self.status["tcp"].configure(text="Unavailable" if net.tcp_error else f"Listening on {net.port}", fg=T.WARN if net.tcp_error else T.GOOD)
        fw = app.fw_state
        txt, col = (("Checking", T.MUTED) if fw is None else (("Rules present", T.GOOD) if fw else ("Rules missing", T.WARN)))
        self.status["fw"].configure(text=txt, fg=col)

    def focus_setting(self, s):
        for card in (self.card_listen, self.card_opts):
            row = card.row_for(s.key)
            if row is not None:
                row.set_details(True)
                row.flash()
                self.scroll.scroll_to(row)
                return


# ==============================================================================
# SETTINGS
# ==============================================================================
class SettingsPage(Page):
    def build(self):
        app = self.app
        gap = dp(GAP)
        left, right = two_columns(self.body)

        self.card_general = SettingsCard(left, app, "General", "How the app starts and behaves.", sm.by_group("settings", "general"))
        self.card_general.pack(fill="x", pady=(0, gap))
        self.card_look = SettingsCard(left, app, "Appearance", "How the app looks.", sm.by_group("settings", "appearance"))
        self.card_look.pack(fill="x", pady=(0, gap))

        keys = {k: (lambda row, k=k: HotkeyEntry(row, app, sm.BY_KEY[k])) for k in sm.BY_KEY if k.startswith("hotkeys.") and sm.BY_KEY[k].kind == "custom"}
        self.card_keys = SettingsCard(right, app, "Shortcuts", "Keys that work in any app, including full-screen games.",
                                      sm.by_group("settings", "shortcuts"), keys)
        self.card_keys.pack(fill="x", pady=(0, gap))
        self.keys_note = hint(self.card_keys.footer, "")
        self.keys_note.pack(fill="x")

        def folder_control(row):
            box = tk.Frame(row, bg=T.SURFACE)
            self.folder = autowrap(tk.Label(box, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9), anchor="w", justify="left", wraplength=dp(240)))
            self.folder.pack(fill="x", pady=(0, dp(8)))
            button_row(box, [("Choose folder...", self._browse, "normal"), ("Open folder", self._open_folder, "ghost")]).pack(anchor="w")
            return box

        self.card_rec = SettingsCard(right, app, "Recording", "Where recordings go and what they contain.", sm.by_group("settings", "recording"),
                                     {"recording.folder": folder_control})
        self.card_rec.pack(fill="x", pady=(0, gap))
        self.update_folder()

        c = Card(right, "Presets and backup", pad=18)
        c.pack(fill="x", pady=(0, gap))
        hint(c.body, "Presets are saved as small files you can share with friends. A settings backup includes everything, your presets too.").pack(fill="x", pady=(0, dp(10)))
        button_row(c.body, [("Import presets...", app.import_presets, "normal"), ("Export my presets...", app.export_all_presets, "normal")]).pack(anchor="w")
        button_row(c.body, [("Export settings...", self._export, "normal"), ("Import settings...", self._import, "normal")]).pack(anchor="w", pady=(dp(8), 0))
        button_row(c.body, [("Open settings folder", lambda: system.open_in_explorer(os.path.dirname(app.cfg.filepath)), "ghost"),
                            ("Reset all settings", self._reset_all, "danger")]).pack(anchor="w", pady=(dp(8), 0))
        self.cfg_path = autowrap(tk.Label(c.body, text=app.cfg.filepath, bg=T.SURFACE, fg=T.DIM, font=font(8), anchor="w", justify="left", wraplength=dp(240)))
        self.cfg_path.pack(fill="x", pady=(dp(10), 0))

        c = Card(right, "Help and about", pad=18)
        c.pack(fill="x", pady=(0, gap))
        label(c.body, f"PhoneMic Receiver {VERSION}", T.TEXT, 12, "bold", bg=T.SURFACE, anchor="w").pack(fill="x")
        autowrap(tk.Label(c.body, text=self._versions(), bg=T.SURFACE, fg=T.DIM, font=font(9), anchor="w", justify="left", wraplength=dp(240))).pack(fill="x", pady=(dp(4), dp(10)))
        button_row(c.body, [("Run setup again", lambda: app.show_page("wizard"), "primary"), ("Copy diagnostics", self._copy_diag, "normal")]).pack(anchor="w")

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
            c.apply_view(advanced)

    def on_show(self):
        a = self.app
        if not a.hotkeys.available:
            self.keys_note.configure(text="Global shortcuts need Windows. They are not available on this system.")
        else:
            self.keys_note.configure(text="Shortcuts do not block the key, so the game still receives it too. Mouse side buttons make good "
                                          "push-to-talk keys. A key can only do one job: assigning it again moves it.")
        row = self.card_general.row_for("app.tray_icon")
        if row is not None and not a.tray.available:
            row.title_label.configure(text="Tray icon (needs the pystray package)")

    def update_folder(self):
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
        self.app.notify("Diagnostics copied. Paste them into a message when you ask for help.", "good", 4000)

    def focus_setting(self, s):
        for card in (self.card_general, self.card_look, self.card_rec, self.card_keys):
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
        c = Card(self.body, "Live statistics", pad=18)
        c.pack(fill="x", pady=(0, gap))
        grid = tk.Frame(c.body, bg=T.SURFACE)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="g")
        grid.grid_columnconfigure(1, weight=1, uniform="g")
        self.vals = {}
        for i, (k, title) in enumerate(self.ROWS):
            cell = tk.Frame(grid, bg=T.SURFACE)
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else dp(16), dp(16) if i % 2 == 0 else 0), pady=1)
            label(cell, title, T.MUTED, 9, bg=T.SURFACE).pack(side="left")
            v = label(cell, "-", T.TEXT, 10, "bold", bg=T.SURFACE)
            v.pack(side="right")
            self.vals[k] = v
        button_row(c.body, [("Reset counters", app.rx.reset_stats, "normal")]).pack(anchor="w", pady=(dp(12), 0))

        c = Card(self.body, "Self-test", pad=18)
        c.pack(fill="x", pady=(0, gap))
        hint(c.body, "Checks the Windows features that cannot be tested anywhere else: global shortcuts, tray icon, firewall rules and more. "
                     "Run it when something does not work and send the result.").pack(fill="x", pady=(0, dp(10)))
        button_row(c.body, [("Run self-test", self._selftest, "primary"), ("Copy result", self._copy_selftest, "normal")]).pack(anchor="w")
        self.selftest_text = tk.Text(c.body, height=10, bg=T.SURFACE2, fg=T.TEXT, relief="flat", font=("Consolas" if system.IS_WIN else "Courier", 9),
                                     wrap="none", highlightthickness=0, padx=dp(8), pady=dp(6))
        self.selftest_text.pack(fill="x", pady=(dp(10), 0))
        self.selftest_text.configure(state="disabled")
        self.selftest_result = ""

        c = Card(self.body, "Event log", pad=18)
        c.pack(fill="both", expand=True, pady=(0, gap))
        button_row(c.body, [("Copy diagnostics", self._copy, "primary"), ("Save diagnostics...", self._save, "normal"),
                            ("Open crash log", self._crash, "ghost")]).pack(anchor="w", pady=(0, dp(10)))
        self.text = tk.Text(c.body, height=16, bg=T.SURFACE2, fg=T.TEXT, relief="flat", font=("Consolas" if system.IS_WIN else "Courier", 9),
                            wrap="none", highlightthickness=0, padx=dp(8), pady=dp(6))
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("warn", foreground=T.WARN)
        self.text.tag_configure("error", foreground=T.BAD)
        self.text.tag_configure("info", foreground=T.MUTED)
        self._serial = -1

    def _selftest(self):
        from . import selftest
        self._set_selftest("Running the checks. The tray icon appears for a moment.")

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
        self.app.notify("Diagnostics copied to the clipboard.", "good", 2500)

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

    def on_show(self):
        self._serial = -1
        self.refresh_slow()

    def refresh_slow(self):
        rx = self.app.rx
        st, jb = rx.stats, rx.jb
        v = self.vals
        v["state"].configure(text=rx.state())
        v["client"].configure(text=f"{rx.client_ip or '-'}  {rx.transport if rx.client_ip else ''}")
        v["packets"].configure(text=f"{st.packets:,}")
        v["lost"].configure(text=f"{st.lost}  ({st.loss_pct:.2f}%)")
        v["reordered"].configure(text=str(st.reordered))
        v["late"].configure(text=str(jb.late))
        v["dup"].configure(text=str(jb.dup))
        v["plc"].configure(text=str(st.plc_frames))
        v["jitter"].configure(text=f"{st.jitter_ms:.2f} ms")
        v["buffer"].configure(text=f"{jb.depth_ms:.0f} of {jb.target_ms:.0f} ms")
        v["grown"].configure(text=str(jb.grown))
        v["drift"].configure(text=str(jb.skipped_total))
        v["underruns"].configure(text=f"{rx.main.starved} (xruns {rx.main.xruns})")
        v["restarts"].configure(text=str(jb.restarts))
        v["dsp"].configure(text=f"{rx.processor.dsp_ms:.3f} ms")
        v["device"].configure(text="open" if rx.main.active else "closed", fg=T.GOOD if rx.main.active else T.WARN)
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
