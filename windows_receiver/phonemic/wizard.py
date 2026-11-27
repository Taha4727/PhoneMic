"""First-run setup wizard: a guided Obsidian flow from install to streaming."""
import time
import webbrowser
import tkinter as tk

from . import system, virtual_mic
from .const import VB_CABLE_URL
from .dsp import lin_to_db
from .widgets import T, dp, font, autowrap, FlatButton, Combo, Card, LevelMeter, ProgressBar, SurfaceBox, PillBadge
from .gui import Page
from .qr import generate_qr_matrix

STEP_TITLES = (
    "Welcome",
    "Output Routing",
    "Firewall" if system.IS_LINUX else "Windows Firewall",
    "Connect Your Phone",
    "All Set",
)


class WizardPage(Page):
    def build(self):
        self.step = 0
        self.mode = "mic"
        self.refs = {}
        self._slow_cache = None
        self._peak_s, self._hold, self._hold_t, self._clip_until = -80.0, -80.0, 0.0, 0.0
        self._last_t = time.monotonic()
        b = self.body
        self._last_fit_w = None
        self._fit_job = None
        self._pending_fit_w = None
        b.grid_columnconfigure(0, weight=1, minsize=0)
        b.grid_columnconfigure(1, weight=20)
        b.grid_columnconfigure(2, weight=1, minsize=0)
        self.card = Card(b, pad=20)
        self.card.grid(row=0, column=1, sticky="nsew", pady=(dp(8), 0))
        b.bind("<Configure>", lambda e: self._schedule_fit(e.width), add="+")
        body = self.card.body

        hdr_row = tk.Frame(body, bg=T.SURFACE)
        hdr_row.pack(fill="x", pady=(0, dp(8)))
        self.step_badge = PillBadge(hdr_row, "", fg=T.ACCENT_HI, bg=T.SURFACE2, border=T.BORDER, size=8, padx=10, pady=3)
        self.step_badge.pack(side="left")
        self.step_label = tk.Label(hdr_row, text="", bg=T.SURFACE, fg=T.MUTED, font=font(9, "bold"), anchor="w")
        self.step_label.pack(side="left", padx=(dp(10), 0))
        self.progress_bar = ProgressBar(body, height=6, color=T.ACCENT, bg=T.SURFACE2, corner=3)
        self.progress_bar.pack(fill="x", pady=(0, dp(16)))
        self.stage = tk.Frame(body, bg=T.SURFACE)
        self.stage.pack(fill="x")
        nav = tk.Frame(body, bg=T.SURFACE)
        nav.pack(fill="x", pady=(dp(24), 0))
        self.btn_next = FlatButton(nav, "Continue", self.next, style="primary", size=10, padx=18, pady=8)
        self.btn_next.pack(side="right")
        self.btn_back = FlatButton(nav, "Back", self.back, style="normal", size=10)
        self.btn_back.pack(side="right", padx=(0, dp(8)))
        self.btn_skip = FlatButton(nav, "Skip setup", self.finish, style="ghost", size=9)
        self.btn_skip.pack(side="left")
        self.render()

    def next(self):
        if self.step >= len(STEP_TITLES) - 1:
            self.finish()
            return
        self.go(self.step + 1)

    def back(self):
        if self.step > 0:
            self.go(self.step - 1)

    def go(self, step):
        self.step = max(0, min(len(STEP_TITLES) - 1, step))
        self.render()

    def finish(self):
        self.app.cfg.data["app"]["first_run_done"] = True
        self.app.cfg.save_soon()
        self.app.show_page("dashboard")

    def on_show(self):
        self.step = 0
        self.render()

    def _schedule_fit(self, width_px):
        if not width_px or width_px < 40:
            return
        self._pending_fit_w = width_px
        if self._fit_job:
            try:
                self.body.after_cancel(self._fit_job)
            except Exception:
                pass
        self._fit_job = self.body.after(16, self._run_fit)

    def _run_fit(self):
        self._fit_job = None
        if self.body.winfo_exists() and self._pending_fit_w is not None:
            self._fit_card(self._pending_fit_w)

    def _fit_card(self, width_px):
        if not width_px or width_px < 40 or width_px == self._last_fit_w:
            return
        self._last_fit_w = width_px
        margin = max(0, (width_px - dp(660)) // 2)
        self.body.grid_columnconfigure(0, weight=1, minsize=margin)
        self.body.grid_columnconfigure(2, weight=1, minsize=margin)

    def render(self):
        for w in self.stage.winfo_children():
            w.destroy()
        self.refs = {}
        self._slow_cache = None
        self.step_badge.set_badge(f"STEP {self.step + 1} OF {len(STEP_TITLES)}")
        self.step_label.configure(text=STEP_TITLES[self.step].upper())
        self.progress_bar.set_progress((self.step + 1) / len(STEP_TITLES))
        [self.step_welcome, self.step_output, self.step_firewall, self.step_connect, self.step_done][self.step]()
        if self.step == 0:
            self.btn_back.pack_forget()
        else:
            self.btn_back.pack(side="right", padx=(0, dp(8)), before=self.btn_next)
        self.btn_next.set_text("Finish" if self.step == len(STEP_TITLES) - 1 else "Continue")
        self.btn_skip.set_text("Skip setup" if self.step < len(STEP_TITLES) - 1 else "Close")

    def _title(self, text, sub=None):
        tk.Label(self.stage, text=text, bg=T.SURFACE, fg=T.TEXT, font=font(20, "bold", True), anchor="w").pack(fill="x")
        if sub:
            autowrap(tk.Label(self.stage, text=sub, bg=T.SURFACE, fg=T.MUTED, font=font(10), anchor="w", justify="left",
                              wraplength=dp(500))).pack(fill="x", pady=(dp(6), dp(14)))

    def _text(self, text, color=None, size=10, pady=(0, dp(8))):
        w = autowrap(tk.Label(self.stage, text=text, bg=T.SURFACE, fg=color or T.MUTED, font=font(size), anchor="w",
                              justify="left", wraplength=dp(500)))
        w.pack(fill="x", pady=pady)
        return w

    def step_welcome(self):
        fw_txt = "check firewall rules" if system.IS_LINUX else "permit Windows Firewall"
        virt_line = (
            "• Virtual mic: PhoneMic creates a PipeWire/PulseAudio mic source automatically on Linux."
            if system.IS_LINUX
            else "• Optional (Free): VB-CABLE to send your mic into Discord, OBS, or Zoom."
        )
        self._title("Turn your phone into a studio microphone",
                    f"Takes about two minutes. Route your audio output, {fw_txt}, and pair your phone.")
        box = SurfaceBox(self.stage, bg=T.SIDEBAR, border=T.BORDER, corner=10)
        box.pack(fill="x", pady=(dp(4), 0))
        inner = tk.Frame(box, bg=T.SIDEBAR)
        inner.pack(fill="x", padx=dp(14), pady=dp(12))
        tk.Label(inner, text="Checklist", bg=T.SIDEBAR, fg=T.ACCENT_HI, font=font(10, "bold"), anchor="w").pack(fill="x", pady=(0, dp(6)))
        for line in ("• PhoneMic app installed on your phone.",
                     "• Phone and PC on the same Wi-Fi, or USB cable with USB tethering.",
                     virt_line):
            autowrap(tk.Label(inner, text=line, bg=T.SIDEBAR, fg=T.MUTED, font=font(10), anchor="w", justify="left",
                              wraplength=dp(480))).pack(fill="x", pady=(0, dp(4)))

    def step_output(self):
        app, rx = self.app, self.app.rx
        self._title("Where should your voice play?", "You can adjust this later on the Connections tab.")
        pool = system.devices_for_api(rx.devices, rx.api)
        cable = next((d for d in pool if d.is_cable), None)
        row = tk.Frame(self.stage, bg=T.SURFACE)
        row.pack(fill="x")
        row.grid_columnconfigure(0, weight=1, uniform="wo")
        row.grid_columnconfigure(1, weight=1, uniform="wo")
        mic_label = "Use as virtual mic" if system.IS_LINUX else "Use as mic (VB-CABLE)"
        self.refs["mic"] = FlatButton(row, mic_label, lambda: self.choose("mic"), size=10, padx=12, pady=8)
        self.refs["mic"].grid(row=0, column=0, sticky="ew", padx=(0, dp(4)))
        self.refs["spk"] = FlatButton(row, "Listen on speakers", lambda: self.choose("speakers"), size=10, padx=12, pady=8)
        self.refs["spk"].grid(row=0, column=1, sticky="ew", padx=(dp(4), 0))
        self.refs["detail"] = tk.Frame(self.stage, bg=T.SURFACE)
        self.refs["detail"].pack(fill="x", pady=(dp(14), 0))
        self.refs["cable"] = cable
        self.choose(self.mode if (cable or self.mode == "speakers") else "mic")

    def choose(self, mode):
        self.mode = mode
        if "mic" not in self.refs or not self.refs["detail"].winfo_exists():
            return
        rx = self.app.rx
        for key, btn in (("mic", self.refs["mic"]), ("speakers", self.refs["spk"])):
            btn.set_style("active" if mode == key else "normal")
        for w in self.refs["detail"].winfo_children():
            w.destroy()
        d = self.refs["detail"]
        pool = system.devices_for_api(rx.devices, rx.api)
        cable = next((x for x in pool if x.is_cable), None)
        if mode == "mic":
            if cable:
                rx.set_output_device(cable)
                self.app.sync_output_devices()
                msg = (
                    f"Virtual microphone active! Choose \"{virtual_mic.SOURCE_NAME}\" as your microphone in Discord, OBS, or browsers."
                    if system.IS_LINUX
                    else "VB-CABLE active! In Discord, OBS or Zoom choose \"CABLE Output (VB-Audio Virtual Cable)\" as your microphone."
                )
                autowrap(tk.Label(d, text=msg, bg=T.SURFACE, fg=T.GOOD, font=font(10), anchor="w", justify="left",
                                  wraplength=dp(440))).pack(fill="x")
            elif system.IS_LINUX:
                st = virtual_mic.status(pool)
                autowrap(tk.Label(d, text=st.detail, bg=T.SURFACE, fg=T.WARN, font=font(10), anchor="w", justify="left",
                                  wraplength=dp(440))).pack(fill="x")
                row = tk.Frame(d, bg=T.SURFACE)
                row.pack(fill="x", pady=(dp(10), 0))
                if st.supported:
                    FlatButton(row, "Create Virtual Mic", self._create_virtual_mic, style="primary", size=9).pack(side="left")
                FlatButton(row, "Check again", self._recheck, size=9).pack(side="left", padx=(dp(8) if st.supported else 0, 0))
            else:
                autowrap(tk.Label(d, text="VB-CABLE is not installed yet. Install this free virtual audio cable, then click Check again.",
                                  bg=T.SURFACE, fg=T.WARN, font=font(10), anchor="w", justify="left", wraplength=dp(440))).pack(fill="x")
                row = tk.Frame(d, bg=T.SURFACE)
                row.pack(fill="x", pady=(dp(10), 0))
                FlatButton(row, "Get VB-CABLE", lambda: webbrowser.open(VB_CABLE_URL), style="primary", size=9).pack(side="left")
                FlatButton(row, "I installed it, check again", self._recheck, size=9).pack(side="left", padx=(dp(8), 0))
        else:
            names = [x.name for x in pool if not x.is_cable] or [x.name for x in pool]
            tk.Label(d, text="Choose the headphones or speakers to play the phone's voice.", bg=T.SURFACE, fg=T.MUTED, font=font(10), anchor="w").pack(fill="x", pady=(0, dp(6)))
            current = rx.main_dev.name if rx.main_dev and rx.main_dev.name in names else (names[0] if names else "")
            combo = Combo(d, names, width=38, command=self._pick_speakers)
            combo.set(current)
            combo.pack(anchor="w")
            if current and (not rx.main_dev or rx.main_dev.name != current):
                self._pick_speakers(current)
        row = tk.Frame(d, bg=T.SURFACE)
        row.pack(fill="x", pady=(dp(14), 0))
        FlatButton(row, "Play test tone", rx.play_test_tone, size=9).pack(side="left")
        tone_hint = (
            "Plays a tone through the selected device (and pulses the virtual mic meter)."
            if system.IS_LINUX
            else "Speakers play the tone directly; VB-CABLE pulses the CABLE Output bar in Windows Sound."
        )
        autowrap(tk.Label(row, text=tone_hint, bg=T.SURFACE, fg=T.DIM, font=font(9), anchor="w", justify="left",
                          wraplength=dp(320))).pack(side="left", fill="x", expand=True, padx=(dp(10), 0))

    def _create_virtual_mic(self):
        self.app.ensure_virtual_mic()
        self.render()

    def _pick_speakers(self, name):
        pool = system.devices_for_api(self.app.rx.devices, self.app.rx.api)
        dev = next((x for x in pool if x.name == name), None)
        if dev:
            self.app.rx.set_output_device(dev)
            self.app.sync_output_devices()

    def _recheck(self):
        self.app.rx.refresh_devices()
        self.app.rx.open_main()
        self.render()

    def step_firewall(self):
        app = self.app
        port = app.cfg.data["network"]["port"]
        if system.IS_LINUX:
            self._title("Allow PhoneMic through Linux Firewall",
                        f"If ufw or firewalld is active, incoming UDP/TCP port {port} must be open for Wi-Fi and USB tethering.")
            hint_txt = f"UFW manual command: sudo ufw allow {port}/udp && sudo ufw allow {port}/tcp"
            btn_txt = "Configure Firewall"
        else:
            self._title("Allow PhoneMic through Windows Firewall",
                        "Windows blocks incoming UDP/TCP streams on public or USB tethering networks unless permitted.")
            hint_txt = "Windows will ask for administrator approval. You can also configure this later on Connections."
            btn_txt = "Configure Firewall Rules"
        self.refs["fw"] = tk.Label(self.stage, text="Checking...", bg=T.SURFACE, fg=T.MUTED, font=font(12, "bold"), anchor="w")
        self.refs["fw"].pack(fill="x", pady=(0, dp(10)))
        row = tk.Frame(self.stage, bg=T.SURFACE)
        row.pack(fill="x")
        FlatButton(row, btn_txt, app.fix_firewall, style="primary", size=10, padx=14, pady=8).pack(side="left")
        FlatButton(row, "Check again", app.refresh_firewall_async, size=9).pack(side="left", padx=(dp(8), 0))
        self._text(hint_txt, T.DIM, 9, (dp(12), 0))
        app.refresh_firewall_async()

    def step_connect(self):
        app = self.app
        self._title("Pair and test your phone")
        top = tk.Frame(self.stage, bg=T.SURFACE)
        top.pack(fill="x")

        left = tk.Frame(top, bg=T.SURFACE)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="PC IP Address (click to copy)", bg=T.SURFACE, fg=T.DIM, font=font(9), anchor="w").pack(fill="x")
        best_ip = app.rx.netinfo.best_ip()
        port = app.cfg.data["network"]["port"]
        ip = tk.Label(left, text=best_ip, bg=T.SURFACE, fg=T.ACCENT_HI, font=font(26, "bold", True), anchor="w", cursor="hand2")
        ip.pack(fill="x")
        ip.bind("<Button-1>", lambda e: app.copy(app.rx.netinfo.best_ip(), "Copied IP"))
        self.refs["ip"] = ip
        usb = app.rx.netinfo.first("USB Tether")
        tk.Label(left, text=f"Port {port}" + (f"   |   USB tether {usb}" if usb else ""), bg=T.SURFACE,
                 fg=T.DIM, font=font(9), anchor="w").pack(fill="x", pady=(0, dp(10)))
        for line in ("1. Open PhoneMic on your phone.",
                     "2. Scan the QR code on the right or tap Auto-Detect PC.",
                     "3. Start streaming and speak to see live audio."):
            autowrap(tk.Label(left, text=line, bg=T.SURFACE, fg=T.MUTED, font=font(10), anchor="w", justify="left",
                              wraplength=dp(360))).pack(fill="x", pady=(0, dp(3)))

        qr_box = SurfaceBox(top, bg="#ffffff", border=T.BORDER_HI, corner=10)
        qr_box.pack(side="right", padx=(dp(14), 0))
        qr_c = tk.Canvas(qr_box, width=dp(116), height=dp(116), bg="#ffffff", highlightthickness=0)
        qr_c.pack(padx=dp(4), pady=dp(4))
        self.refs["qr"] = qr_c
        self._paint_qr(qr_c, f"phonemic://{best_ip}:{port}?t=UDP")

        self.refs["live"] = tk.Label(self.stage, text="Waiting for your phone...", bg=T.SURFACE, fg=T.MUTED, font=font(11, "bold"), anchor="w")
        self.refs["live"].pack(fill="x", pady=(dp(16), dp(6)))
        self.refs["meter"] = LevelMeter(self.stage, height=38)
        self.refs["meter"].pack(fill="x")

    @staticmethod
    def _paint_qr(canvas, payload):
        try:
            matrix = generate_qr_matrix(payload)
            canvas.delete("all")
            n = len(matrix)
            sz = dp(116)
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

    def step_done(self):
        self._title("You are ready to go", "Handy shortcuts and tips for daily use:")
        for head, text in (("Audio Studio & Voice Changer", "Shape tone with presets, 5-band Parametric EQ, Compressor, and Voice Changer characters."),
                           ("Compact Widget Mode (F10)", "Click Compact in the header or press F10 to switch into a tiny floating desktop bar."),
                           ("Global Shortcuts & A/B Compare", "Press Ctrl+M to mute, Ctrl+B to bypass all effects, and configure Push-to-Talk in Settings.")):
            row = tk.Frame(self.stage, bg=T.SURFACE)
            row.pack(fill="x", pady=(0, dp(10)))
            tk.Label(row, text=head, bg=T.SURFACE, fg=T.ACCENT_HI, font=font(10, "bold"), anchor="w").pack(fill="x")
            autowrap(tk.Label(row, text=text, bg=T.SURFACE, fg=T.MUTED, font=font(10), anchor="w", justify="left",
                              wraplength=dp(500))).pack(fill="x")

    def refresh_slow(self):
        app, rx = self.app, self.app.rx
        best_ip = rx.netinfo.best_ip()
        state = rx.state()
        key = (self.step, app.fw_state, state, rx.client_ip, rx.net.udp_error, best_ip)
        if key == self._slow_cache:
            return
        self._slow_cache = key
        if self.step == 2 and "fw" in self.refs:
            fw = app.fw_state
            lbl = getattr(app, "fw_label", "") or ("Firewall rules are active." if fw else "Firewall rules are missing.")
            text, col = (("Checking...", T.MUTED) if fw is None else ((lbl, T.GOOD) if fw else (lbl, T.WARN)))
            self.refs["fw"].configure(text=text, fg=col)
        if self.step == 3 and "live" in self.refs:
            if state == "streaming":
                self.refs["live"].configure(text=f"Connected from {rx.client_ip}! Watch the audio meter respond.", fg=T.GOOD)
            elif state == "error":
                self.refs["live"].configure(text="Cannot listen: " + rx.net.udp_error, fg=T.BAD)
            else:
                self.refs["live"].configure(text="Waiting for your phone...", fg=T.MUTED)
            self.refs["ip"].configure(text=best_ip)

    def refresh_fast(self):
        if self.step == 3 and "meter" in self.refs:
            rx, p = self.app.rx, self.app.proc
            now = time.monotonic()
            dt = min(0.2, now - self._last_t)
            self._last_t = now
            live = rx.state() == "streaming"
            peak = p.level_db if live else -80.0
            rms = lin_to_db(p.level_rms, -80.0) if live else -80.0
            self._peak_s = peak if peak > self._peak_s else max(peak, self._peak_s - 60.0 * dt)
            if self._peak_s >= self._hold:
                self._hold, self._hold_t = self._peak_s, now
            elif now - self._hold_t > 1.2:
                self._hold = max(self._peak_s, self._hold - 30.0 * dt)
            if live and p.clipped:
                self._clip_until = now + 3.0
            self.refs["meter"].update_levels(self._peak_s, rms, self._hold, now < self._clip_until)
