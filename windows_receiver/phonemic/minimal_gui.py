"""Compact, streamlined Minimal GUI widget for PhoneMic Receiver.

Obsidian floating widget displaying live VU meter, Mute, Monitor, Record, FX Bypass,
Master Gain trim, connection state, and output device with instant toggle back to Full Studio.
"""
import time
import tkinter as tk

from .const import VERSION, APP_NAME
from .dsp import lin_to_db
from .widgets import T, HAS_CTK, ctk, dp, font, FlatButton, LevelMeter, Tooltip


def _state_style(state):
    return {
        "waiting": (T.ACCENT, "Waiting"),
        "streaming": (T.GOOD, "Live"),
        "muted": (T.WARN, "Muted"),
        "lost": (T.WARN, "Lost"),
        "error": (T.BAD, "Error"),
    }[state]

_MinimalBase = ctk.CTkFrame if HAS_CTK else tk.Frame


class MinimalView(_MinimalBase):
    """Compact Obsidian desktop widget view of PhoneMic Receiver."""

    def __init__(self, parent, app):
        if HAS_CTK:
            super().__init__(parent, fg_color=T.BG, corner_radius=0)
        else:
            super().__init__(parent, bg=T.BG)
        self.app = app
        self.rx = app.rx
        self.proc = app.proc
        self.last = time.monotonic()
        self.peak_s = -80.0
        self.hold = -80.0
        self.hold_t = 0.0
        self.clip_until = 0.0
        self._ctrl_cache = None
        self._db_last = None
        self._build_ui()

    def _build_ui(self):
        # 1. Top Header Bar (Brand, State Pill, Expand Button)
        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", padx=dp(8), pady=(dp(6), dp(4)))

        title_box = tk.Frame(top, bg=T.BG)
        title_box.pack(side="left")
        tk.Label(title_box, text=APP_NAME, bg=T.BG, fg=T.TEXT, font=font(10, "bold", True)).pack(side="left")
        tk.Label(title_box, text=f"v{VERSION}", bg=T.BG, fg=T.DIM, font=font(8)).pack(side="left", padx=(dp(4), 0))

        btn_expand = FlatButton(top, "Full View", lambda: self.app.switch_ui_mode("default"),
                                style="normal", padx=8, pady=2, size=8, corner=7)
        btn_expand.pack(side="right", padx=(dp(5), 0))
        Tooltip(btn_expand, "Switch to full Studio interface with EQ, Voice Changer & Connections (F10)")

        if HAS_CTK:
            self.chip = ctk.CTkFrame(top, fg_color=T.SURFACE, corner_radius=dp(7), border_width=1, border_color=T.BORDER)
        else:
            self.chip = tk.Frame(top, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER)
        self.chip.pack(side="right")
        chip_in = tk.Frame(self.chip, bg=T.SURFACE)
        chip_in.pack(padx=dp(7), pady=dp(2))
        self.chip_dot = tk.Label(chip_in, text="\u25cf", bg=T.SURFACE, fg=T.ACCENT, font=font(8))
        self.chip_dot.pack(side="left", padx=(0, dp(4)))
        self.chip_text = tk.Label(chip_in, text="Starting", bg=T.SURFACE, fg=T.TEXT, font=font(8, "bold"))
        self.chip_text.pack(side="left")

        # 2. Matte Obsidian Connection Card
        if HAS_CTK:
            info_card = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=dp(8), border_width=1, border_color=T.BORDER)
        else:
            info_card = tk.Frame(self, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER)
        info_card.pack(fill="x", padx=dp(8), pady=(0, dp(4)))

        info_top = tk.Frame(info_card, bg=T.SURFACE)
        info_top.pack(fill="x", padx=dp(8), pady=(dp(5), dp(1)))
        self.lbl_devices = tk.Label(info_top, text="", bg=T.SURFACE, fg=T.BLUE_HI, font=font(8, "bold"), anchor="e")
        self.lbl_devices.pack(side="right", padx=(dp(6), 0))
        self.lbl_client = tk.Label(info_top, text="Waiting...", bg=T.SURFACE, fg=T.TEXT, font=font(8, "bold"), anchor="w")
        self.lbl_client.pack(side="left", fill="x", expand=True)

        info_bot = tk.Frame(info_card, bg=T.SURFACE)
        info_bot.pack(fill="x", padx=dp(8), pady=(0, dp(5)))
        self.lbl_stats = tk.Label(info_bot, text="", bg=T.SURFACE, fg=T.ACCENT_HI, font=font(8), anchor="e")
        self.lbl_stats.pack(side="right", padx=(dp(6), 0))
        self.lbl_output = tk.Label(info_bot, text="Output: Default", bg=T.SURFACE, fg=T.MUTED, font=font(8), anchor="w")
        self.lbl_output.pack(side="left", fill="x", expand=True)

        # 3. Live Volume VU Meter
        meter_row = tk.Frame(self, bg=T.BG)
        meter_row.pack(fill="x", padx=dp(8), pady=(0, dp(4)))

        self.meter = LevelMeter(meter_row, height=16, bg=T.SURFACE)
        self.meter.pack(side="left", fill="x", expand=True)

        self.lbl_db = tk.Label(meter_row, text="-∞ dB", bg=T.BG, fg=T.DIM, font=font(8, "bold", True), width=6, anchor="e")
        self.lbl_db.pack(side="right", padx=(dp(4), 0))

        # 4. Essential Action Buttons Strip
        btn_strip = tk.Frame(self, bg=T.BG)
        btn_strip.pack(fill="x", padx=dp(8), pady=(0, dp(4)))

        self.btn_mute = FlatButton(btn_strip, "Mute", self.app.toggle_mute, size=8, padx=6, pady=3, corner=7)
        self.btn_mute.pack(side="left", fill="x", expand=True, padx=(0, dp(2)))
        Tooltip(self.btn_mute, "Mute microphone output (Ctrl+M)")

        self.btn_monitor = FlatButton(btn_strip, "Monitor", self.app.toggle_monitor, size=8, padx=6, pady=3, corner=7)
        self.btn_monitor.pack(side="left", fill="x", expand=True, padx=dp(2))
        Tooltip(self.btn_monitor, "Hear your microphone in headphones (Ctrl+E)")

        self.btn_record = FlatButton(btn_strip, "Record", self.app.toggle_record, size=8, padx=6, pady=3, corner=7)
        self.btn_record.pack(side="left", fill="x", expand=True, padx=dp(2))
        Tooltip(self.btn_record, "Record output to WAV file (Ctrl+R)")

        self.btn_fx = FlatButton(btn_strip, "FX On", self.app.toggle_bypass, style="blue", size=8, padx=6, pady=3, corner=7)
        self.btn_fx.pack(side="left", fill="x", expand=True, padx=(dp(2), 0))
        Tooltip(self.btn_fx, "Bypass all DSP effects for comparison (Ctrl+B)")

        # 5. Master Gain Trim Strip
        gain_row = tk.Frame(self, bg=T.BG)
        gain_row.pack(fill="x", padx=dp(8), pady=(0, dp(5)))

        tk.Label(gain_row, text="Gain", bg=T.BG, fg=T.MUTED, font=font(8)).pack(side="left")

        btn_minus = FlatButton(gain_row, "-", lambda: self._step_gain(-1.0), size=8, padx=6, pady=1, corner=6)
        btn_minus.pack(side="left", padx=(dp(5), dp(2)))
        Tooltip(btn_minus, "Reduce output gain by 1 dB")

        btn_plus = FlatButton(gain_row, "+", lambda: self._step_gain(1.0), size=8, padx=6, pady=1, corner=6)
        btn_plus.pack(side="left", padx=dp(2))
        Tooltip(btn_plus, "Increase output gain by 1 dB")

        btn_zero = FlatButton(gain_row, "0 dB", lambda: self._set_gain(0.0), style="ghost", size=8, padx=6, pady=1, corner=6)
        btn_zero.pack(side="left", padx=dp(2))
        Tooltip(btn_zero, "Reset gain to unity (0 dB)")

        self.lbl_gain_val = tk.Label(gain_row, text="0.0 dB", bg=T.BG, fg=T.ACCENT_HI, font=font(8, "bold", True), anchor="w")
        self.lbl_gain_val.pack(side="left", padx=(dp(5), 0))

        tk.Label(gain_row, text="F10: Full", bg=T.BG, fg=T.DIM, font=font(8)).pack(side="right")

    def _step_gain(self, delta_db):
        cur = float(getattr(self.proc, "out_gain_db", 0.0))
        new_val = max(-24.0, min(18.0, cur + delta_db))
        self._set_gain(new_val)

    def _set_gain(self, val_db):
        val_db = round(val_db * 2.0) / 2.0
        self.proc.set_param("out_gain_db", val_db)
        self.app.binder.persist_fx()
        self.refresh_controls()

    def refresh_controls(self, force=False):
        rx = self.rx
        state = rx.state()
        color, text = _state_style(state)
        if state == "error":
            text = "Port in use" if "unavailable" in rx.net.udp_error else text
        silent = state == "streaming" and rx.gate_closed
        if silent:
            color, text = T.WARN, "Silent"

        rec_sec = int(rx.recorder.seconds) if rx.recorder.active else -1
        streams_count = len(rx.client_streams)
        out_name = rx.main_dev.name if rx.main_dev else "Default"
        if len(out_name) > 25:
            out_name = out_name[:22] + "..."
        best_ip = rx.netinfo.best_ip() if not (rx.is_streaming and rx.client_ip) else ""
        port = self.app.cfg.data["network"]["port"]
        buf_ms = int(round(rx.jb.depth_ms)) if rx.is_streaming else -1
        gain = float(getattr(self.proc, "out_gain_db", 0.0))

        key = (color, text, rx.paused, rx.monitoring, self.proc.fx_bypass, rec_sec,
               rx.is_streaming, rx.client_ip, rx.client_sample_rate, best_ip, port,
               streams_count, out_name, buf_ms, gain, T.BLUE_HI, T.ACCENT_HI)
        if not force and key == self._ctrl_cache:
            return
        self._ctrl_cache = key

        self.chip_dot.configure(fg=color)
        self.chip_text.configure(text=text)
        self.lbl_devices.configure(fg=T.BLUE_HI)
        self.lbl_stats.configure(fg=T.ACCENT_HI)
        self.lbl_gain_val.configure(fg=T.ACCENT_HI)

        self.btn_mute.set_text("Unmute" if rx.paused else "Mute")
        self.btn_mute.set_style("danger" if rx.paused else "normal")
        self.btn_monitor.set_text("Monitor on" if rx.monitoring else "Monitor")
        self.btn_monitor.set_style("active" if rx.monitoring else "normal")
        self.btn_fx.set_text("FX Off" if self.proc.fx_bypass else "FX On")
        self.btn_fx.set_style("warn" if self.proc.fx_bypass else "blue")

        if rx.recorder.active:
            from .gui import fmt_time
            self.btn_record.set_text(f"Rec {fmt_time(rx.recorder.seconds)}")
            self.btn_record.set_style("rec")
        else:
            self.btn_record.set_text("Record")
            self.btn_record.set_style("normal")

        if rx.is_streaming and rx.client_ip:
            sr = rx.client_sample_rate // 1000
            self.lbl_client.configure(text=f"Phone: {rx.client_ip} ({sr}kHz)", fg=T.TEXT)
        else:
            self.lbl_client.configure(text=f"PC: {best_ip}:{port}", fg=T.DIM)

        self.lbl_devices.configure(text=f"{streams_count} mixed" if streams_count > 1 else "")
        self.lbl_output.configure(text=f"Out: {out_name}")
        self.lbl_stats.configure(text=f"{buf_ms} ms" if rx.is_streaming else "")
        self.lbl_gain_val.configure(text=f"{gain:+.1f} dB")

    def refresh_fast(self):
        rx, proc = self.rx, self.proc
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
        db_text = f"{self.peak_s:5.0f} dB" if live and self.peak_s > -79.0 else "-∞ dB"
        if db_text != self._db_last:
            self._db_last = db_text
            self.lbl_db.configure(text=db_text)
