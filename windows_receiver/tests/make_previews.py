"""Dev tool: render every page to tests/previews/*.png using the layout simulator (see layout_preview.py)."""
import os, sys, time, socket, struct, threading, tempfile
import _path  # noqa: F401
import fake_tk; fake_tk.install()
import numpy as np
import fake_sd
from phonemic.config import ConfigManager
from phonemic.engine import Receiver
from phonemic import system, gui, settings_meta as sm
import layout_preview as lp

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "previews"); os.makedirs(OUT, exist_ok=True)
PORT = 25081
d = tempfile.mkdtemp(); cfg = ConfigManager(os.path.join(d, "c.json")); cfg.data["network"]["port"] = PORT; cfg.data["app"]["first_run_done"] = True
rx = Receiver(cfg, sd_module=fake_sd, netinfo=system.NetworkInfo()); rx.start(); time.sleep(0.3)
stop = threading.Event()
def feeder():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); i = 0; t0 = time.perf_counter(); rng = np.random.default_rng(1)
    while not stop.is_set():
        n = np.arange(480) + i * 480
        x = 0.22 * np.sin(2 * np.pi * 180 * n / 48000) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * n / 48000)) + 0.08 * np.sin(2 * np.pi * 2400 * n / 48000) + rng.standard_normal(480) * 0.006
        s.sendto(b"PM01" + struct.pack(">I", i) + (x * 32767).astype('<i2').tobytes(), ("127.0.0.1", PORT)); i += 1
        time.sleep(max(0, t0 + i * 0.01 - time.perf_counter()))
threading.Thread(target=feeder, daemon=True).start(); time.sleep(1.2)
app = gui.App(rx)

def settle(n=6):
    for _ in range(n):
        app._slow_t = 0; app.tick(); time.sleep(0.05)

def shot(name, W=1100, H=780, adv=False, setup=None):
    app.binder.set(sm.BY_KEY["app.advanced_mode"], adv)
    if setup: setup()
    settle()
    img, sim = lp.render_window(app, W, H)
    img.save(os.path.join(OUT, name + ".png")); return img

shot("dashboard", setup=lambda: app.show_page("dashboard"))
shot("sound_noise", setup=lambda: (app.show_page("sound"), app.pages["sound"].pick_stage("noise")))
shot("sound_noise_adv", adv=True, setup=lambda: (app.show_page("sound"), app.pages["sound"].pick_stage("noise")))
def eq_setup():
    app.show_page("sound"); pg = app.pages["sound"]; pg.pick_stage("eq")
    app.apply_fx_preset("Podcast & Streamer"); app.binder.set(sm.BY_KEY["eq4_gain"], -3.0); app.binder.set(sm.BY_KEY["eq4_freq"], 5200.0)
shot("sound_eq", setup=eq_setup)
shot("sound_eq_adv", adv=True, setup=eq_setup)
shot("voice", setup=lambda: app.show_page("voice"))
shot("devices", setup=lambda: app.show_page("devices"))
shot("network", setup=lambda: app.show_page("network"))
shot("settings", setup=lambda: app.show_page("settings"))
shot("log", setup=lambda: app.show_page("log"))
cfg.data["app"]["first_run_done"] = False
shot("wizard1", setup=lambda: (app.show_page("wizard"), app.pages["wizard"].go(1)))
shot("wizard3", setup=lambda: (app.show_page("wizard"), app.pages["wizard"].go(3)))
shot("dashboard_min", W=920, H=640, setup=lambda: app.show_page("dashboard"))
shot("sound_min", W=920, H=640, adv=True, setup=lambda: (app.show_page("sound"), app.pages["sound"].pick_stage("comp")))
stop.set(); rx.stop(); cfg.close()
print(sorted(os.listdir(OUT)))
