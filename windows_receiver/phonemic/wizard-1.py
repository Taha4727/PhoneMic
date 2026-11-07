"""First-run setup: a short guided path from 'installed' to 'my phone is a microphone'."""
import time
import webbrowser
import tkinter as tk

from . import system
from .const import VB_CABLE_URL
from .widgets import T, dp, font, autowrap, FlatButton, Combo, Card, LevelMeter
from .gui import Page

STEP_TITLES = ("Welcome", "Where the voice goes", "Windows Firewall", "Connect your phone", "All set")


class WizardPage(Page):
    def build(self):
        self.step = 0
        self.mode = "mic"                       # mic = send into VB-CABLE, speakers = just listen
        self.refs = {}
        b = self.body
        b.grid_columnconfigure(0, weight=1)
        b.grid_columnconfigure(1, weight=0, minsize=dp(600))
        b.grid_columnconfigure(2, weight=1)
        self.card = Card(b, pad=26)
        self.card.grid(row=0, column=1, sticky="nsew", pady=(dp(8), 0))
        body = self.card.body

        self.progress = tk.Canvas(body, height=dp(14), bg=T.SURFACE, highlightthickness=0, bd=0)
        self.progress.pack(fill="x")
        self.step_label = tk.Label(body, text="", bg=T.SURFACE, fg=T.DIM, font=font(9), anchor="w")
        self.step_label.pack(fill="x", pady=(dp(6), dp(14)))
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
        self.progress.bind("<Configure>", lambda e: self._paint_progress())
        self.render()

    # ---- navigation ------------------------------------------------------------------------------------------------------
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

    # ---- rendering -------------------------------------------------------------------------------------------------------
    def _paint_progress(self):
        c = self.progress
        c.delete("all")
        n = len(STEP_TITLES)
        r = dp(4)
        gap = dp(22)
        for i in range(n):
            x = r + i * gap
            if i < self.step:
                c.create_oval(x - r, dp(7) - r, x + r, dp(7) + r, fill=T.ACCENT, outline="")
            elif i == self.step:
                c.create_oval(x - r - dp(1), dp(7) - r - dp(1), x + r + dp(1), dp(7) + r + dp(1), fill=T.ACCENT_HI, outline="")
            else:
                c.create_oval(x - r, dp(7) - r, x + r, dp(7) + r, fill=T.SURFACE, outline=T.DIM)

    def render(self):
        for w in self.stage.winfo_children():
            w.destroy()
        self.refs = {}
        self.step_label.configure(text=f"Step {self.step + 1} of {len(STEP_TITLES)}: {STEP_TITLES[self.step]}")
        self._paint_progress()
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
            autowrap(tk.Label(self.stage, text=sub, bg=T.SURFACE, fg=T.MUTED, font=font(10), anchor="w", justify="left", wraplength=dp(500))).pack(fill="x", pady=(dp(6), dp(14)))

    def _text(self, text, color=None, size=10, pady=(0, dp(8))):
        w = autowrap(tk.Label(self.stage, text=text, bg=T.SURFACE, fg=color or T.MUTED, font=font(size), anchor="w", justify="left", wraplength=dp(500)))
        w.pack(fill="x", pady=pady)
        return w

    # ---- steps ---------------------------------------------------------------------------------------------------------------
    def step_welcome(self):
        self._title("Let's turn your phone into a microphone",
                    "This takes about two minutes. You will choose where the voice goes, check that Windows lets the phone connect, and start streaming.")
        self._text("What you need", T.TEXT, 11, (dp(4), dp(4)))
        for line in ("The PhoneMic app on your phone.",
                     "Your phone and this PC on the same Wi-Fi, or a USB cable with USB tethering turned on.",
                     "Optional and free: VB-CABLE, so other apps such as Discord or OBS can use the phone as a microphone."):
            self._text(line, pady=(0, dp(4)))

    def step_output(self):
        app, rx = self.app, self.app.rx
        self._title("Where should the voice go?", "You can change this at any time on the Audio Devices page.")
        pool = system.devices_for_api(rx.devices, rx.api)
        cable = next((d for d in pool if d.is_cable), None)
        row = tk.Frame(self.stage, bg=T.SURFACE)
        row.pack(fill="x")
        self.refs["mic"] = FlatButton(row, "Use it as a microphone in other apps", lambda: self.choose("mic"), size=10, padx=14, pady=9)
        self.refs["mic"].pack(side="left")
        self.refs["spk"] = FlatButton(row, "Just listen on my headphones", lambda: self.choose("speakers"), size=10, padx=14, pady=9)
        self.refs["spk"].pack(side="left", padx=(dp(8), 0))
        self.refs["detail"] = tk.Frame(self.stage, bg=T.SURFACE)
        self.refs["detail"].pack(fill="x", pady=(dp(14), 0))
        self.refs["cable"] = cable
        self.choose(self.mode if (cable or self.mode == "speakers") else "mic")

    def choose(self, mode):
        self.mode = mode
        if "mic" not in self.refs or not self.refs["detail"].winfo_exists():       # the step is not on screen
            return
        app, rx = self.app, self.app.rx
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
                tk.Label(d, text="VB-CABLE was found and selected. In Discord, OBS or Zoom, choose \"CABLE Output (VB-Audio Virtual Cable)\" as your microphone.",
                         bg=T.SURFACE, fg=T.GOOD, font=font(10), anchor="w", justify="left", wraplength=dp(500)).pack(fill="x")
            else:
                tk.Label(d, text="VB-CABLE is not installed yet. It is a free virtual audio cable. Install it, restart this app, and it will be selected automatically.",
                         bg=T.SURFACE, fg=T.WARN, font=font(10), anchor="w", justify="left", wraplength=dp(500)).pack(fill="x")
                row = tk.Frame(d, bg=T.SURFACE)
                row.pack(fill="x", pady=(dp(10), 0))
                FlatButton(row, "Get VB-CABLE", lambda: webbrowser.open(VB_CABLE_URL), style="primary", size=9).pack(side="left")
                FlatButton(row, "I installed it, check again", self._recheck, size=9).pack(side="left", padx=(dp(8), 0))
        else:
            names = [x.name for x in pool if not x.is_cable] or [x.name for x in pool]
            tk.Label(d, text="Choose the headphones or speakers that should play the phone's voice.", bg=T.SURFACE, fg=T.MUTED, font=font(10), anchor="w").pack(fill="x", pady=(0, dp(6)))
            current = rx.main_dev.name if rx.main_dev and rx.main_dev.name in names else (names[0] if names else "")
            combo = Combo(d, names, width=44, command=self._pick_speakers)
            combo.set(current)
            combo.pack(anchor="w")
            if current and (not rx.main_dev or rx.main_dev.name != current):
                self._pick_speakers(current)
        row = tk.Frame(d, bg=T.SURFACE)
        row.pack(fill="x", pady=(dp(14), 0))
        FlatButton(row, "Play test tone", rx.play_test_tone, size=9).pack(side="left")
        tk.Label(row, text="Speakers play it. With VB-CABLE the CABLE Output level bar in Windows sound settings moves instead.", bg=T.SURFACE,
                 fg=T.DIM, font=font(9), anchor="w", justify="left", wraplength=dp(380)).pack(side="left", padx=(dp(10), 0))

    def _pick_speakers(self, name):
        pool = system.devices_for_api(self.app.rx.devices, self.app.rx.api)
        dev = next((x for x in pool if x.name == name), None)
        if dev:
            self.app.rx.set_output_device(dev)

    def _recheck(self):
        self.app.rx.refresh_devices()
        self.app.rx.open_main()
        self.render()

    def step_firewall(self):
        app = self.app
        self._title("Let Windows know the phone may connect",
                    "Windows Firewall blocks unknown incoming connections. USB tethering is treated as a public network, so it needs a rule. Wi-Fi at home often works without one.")
        self.refs["fw"] = tk.Label(self.stage, text="Checking...", bg=T.SURFACE, fg=T.MUTED, font=font(12, "bold"), anchor="w")
        self.refs["fw"].pack(fill="x", pady=(0, dp(10)))
        row = tk.Frame(self.stage, bg=T.SURFACE)
        row.pack(fill="x")
        FlatButton(row, "Allow PhoneMic through the firewall", app.fix_firewall, style="primary", size=10, padx=14, pady=8).pack(side="left")
        FlatButton(row, "Check again", app.refresh_firewall_async, size=9).pack(side="left", padx=(dp(8), 0))
        self._text("Windows will ask for administrator approval. You can skip this and come back from the Network page.", T.DIM, 9, (dp(12), 0))
        app.refresh_firewall_async()

    def step_connect(self):
        app = self.app
        self._title("Connect your phone")
        tk.Label(self.stage, text="Your PC's address", bg=T.SURFACE, fg=T.DIM, font=font(9), anchor="w").pack(fill="x")
        ip = tk.Label(self.stage, text=app.rx.netinfo.best_ip(), bg=T.SURFACE, fg=T.ACCENT_HI, font=font(30, "bold", True), anchor="w", cursor="hand2")
        ip.pack(fill="x")
        ip.bind("<Button-1>", lambda e: app.copy(app.rx.netinfo.best_ip(), "Copied the address"))
        self.refs["ip"] = ip
        usb = app.rx.netinfo.first("USB Tether")
        tk.Label(self.stage, text=f"Port {app.cfg.data['network']['port']}" + (f"     USB tether address {usb}" if usb else ""), bg=T.SURFACE,
                 fg=T.DIM, font=font(9), anchor="w").pack(fill="x", pady=(0, dp(14)))
        for line in ("Open PhoneMic on your phone and choose Wi-Fi or USB.",
                     "Tap Scan or Auto-Detect PC. If it does not find this PC, type the address above.",
                     "Start streaming and say something."):
            self._text(line, pady=(0, dp(3)))
        self.refs["live"] = tk.Label(self.stage, text="Waiting for your phone...", bg=T.SURFACE, fg=T.MUTED, font=font(12, "bold"), anchor="w")
        self.refs["live"].pack(fill="x", pady=(dp(16), dp(6)))
        self.refs["meter"] = LevelMeter(self.stage, height=36)
        self.refs["meter"].pack(fill="x")

    def step_done(self):
        self._title("You are all set", "Everything can be changed later. A few things worth knowing:")
        for head, text in (("Presets", "The Sound page has ready-made voices for streaming, podcasts and gaming. Save your own with Save as."),
                           ("Compare", "Press Ctrl+B to switch every effect off and hear the plain microphone, then on again."),
                           ("Mute and shortcuts", "Ctrl+M mutes the output and tells the phone to pause. On the Settings page you can set keys that work in any app, including a push-to-talk key."),
                           ("Find anything", "Use the search box at the top to find a setting by what it does. Turn on Advanced settings in the sidebar for every control.")):
            row = tk.Frame(self.stage, bg=T.SURFACE)
            row.pack(fill="x", pady=(0, dp(8)))
            tk.Label(row, text=head, bg=T.SURFACE, fg=T.TEXT, font=font(10, "bold"), anchor="w").pack(fill="x")
            autowrap(tk.Label(row, text=text, bg=T.SURFACE, fg=T.MUTED, font=font(10), anchor="w", justify="left", wraplength=dp(500))).pack(fill="x")

    # ---- live updates ---------------------------------------------------------------------------------------------------------
    def refresh_slow(self):
        app, rx = self.app, self.app.rx
        if self.step == 2 and "fw" in self.refs:
            fw = app.fw_state
            text, col = (("Checking...", T.MUTED) if fw is None else (("The firewall rules are in place.", T.GOOD) if fw else ("The firewall rules are missing.", T.WARN)))
            self.refs["fw"].configure(text=text, fg=col)
        if self.step == 3 and "live" in self.refs:
            state = rx.state()
            if state == "streaming":
                self.refs["live"].configure(text=f"Connected from {rx.client_ip}. Say something and watch the bar move.", fg=T.GOOD)
            elif state == "error":
                self.refs["live"].configure(text="Cannot listen. " + rx.net.udp_error, fg=T.BAD)
            else:
                self.refs["live"].configure(text="Waiting for your phone...", fg=T.MUTED)
            self.refs["ip"].configure(text=rx.netinfo.best_ip())

    def refresh_fast(self):
        if self.step == 3 and "meter" in self.refs:
            rx, p = self.app.rx, self.app.proc
            live = rx.state() == "streaming"
            db = p.level_db if live else -80.0
            self.refs["meter"].update_levels(db, db - 10.0, db, False)
