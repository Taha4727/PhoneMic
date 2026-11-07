"""Desktop integration through the real App: shortcuts (fake keyboard), tray (fake pystray), close-to-tray, second launch."""
import os, time, socket, struct, threading, tempfile, json
import _path  # noqa: F401
import fake_tk; fake_tk.install()
import numpy as np
from PIL import Image, ImageDraw
import fake_sd
from test_desktop import FakePystray, FakeIcon, FakeMenu
from test_hotkeys import FakeKeys
from phonemic.config import ConfigManager
from phonemic.engine import Receiver
from phonemic import system, gui, tray, hotkeys as hk, settings_meta as sm, ui_kit

PORT = 25071
kb = FakeKeys()
tray.load_modules = lambda: (FakePystray, Image, ImageDraw)           # pretend pystray is installed
hk.default_backend = lambda: kb                                        # and that this is Windows with a keyboard

d = tempfile.mkdtemp(); cfg = ConfigManager(os.path.join(d, "c.json")); cfg.data["network"]["port"] = PORT
cfg.data["app"]["first_run_done"] = True
rx = Receiver(cfg, sd_module=fake_sd, netinfo=system.NetworkInfo()); rx.start(); time.sleep(0.3)
stop = threading.Event()
def feeder():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); i = 0; t0 = time.perf_counter()
    while not stop.is_set():
        n = np.arange(480) + i * 480
        s.sendto(b"PM01" + struct.pack(">I", i) + (np.sin(2 * np.pi * 300 * n / 48000) * 0.3 * 32767).astype("<i2").tobytes(), ("127.0.0.1", PORT)); i += 1
        time.sleep(max(0, t0 + i * 0.01 - time.perf_counter()))
threading.Thread(target=feeder, daemon=True).start(); time.sleep(0.8)

app = gui.App(rx)
def pump(wait=0.15):
    time.sleep(wait); app._pump()
def press(*keys, hold=0.12):
    kb.press(*keys); time.sleep(hold); kb.release(*keys); time.sleep(0.05)
def walk(w):
    yield w
    for c in list(getattr(w, "children", [])):
        yield from walk(c)

print("1. tray icon starts and follows the connection state")
assert app.tray.running and FakeIcon.instances, "tray started because the setting is on and pystray is available"
icon = FakeIcon.instances[-1]
app._slow_t = 0; app.tick(); app.refresh_header()
assert "Streaming from 127.0.0.1" in icon.title and app.tray.state_key == "streaming"
print("   PASS tooltip:", icon.title)

print("2. the Shortcuts card has one capture button per action")
app.show_page("settings"); page = app.pages["settings"]
entries = [w for w in walk(page) if isinstance(w, ui_kit.HotkeyEntry)]
assert len(entries) == 7 and {e.setting.key for e in entries} == set(ui_kit.HOTKEY_KEYS)
by_key = {e.setting.key: e for e in entries}
assert by_key["hotkeys.toggle_mute"].key_btn.cget("text") == "Not set"
print("   PASS", len(entries), "entries")

print("3. capture: click, press the keys, the shortcut is saved and active")
e = by_key["hotkeys.toggle_mute"]; e._start()
assert e.capturing and "Press the keys" in e.key_btn.cget("text")
time.sleep(0.05); press("ctrl", "alt", "m"); pump()
assert cfg.data["hotkeys"]["toggle_mute"] == "ctrl+alt+m" and not e.capturing and e.key_btn.cget("text") == "Ctrl+Alt+M"
assert "toggle_mute" in app.hotkeys.bindings
print("   PASS saved:", cfg.data["hotkeys"]["toggle_mute"])

print("4. pressing the shortcut anywhere runs the action (mute toggles, phone is told)")
sent = []; rx.net.send_control = lambda cmd, addr, transport: sent.append(cmd) or True
assert not rx.paused
press("ctrl", "alt", "m"); pump(); assert rx.paused and len(sent) == 1
press("ctrl", "alt", "m"); pump(); assert not rx.paused and len(sent) == 2
print("   PASS")

print("5. push-to-talk flips the gate immediately on the shortcut thread, with no UI round trip")
app.binder.set(sm.BY_KEY["hotkeys.push_to_talk"], "xbutton1")
assert rx.ptt_active and rx.gate_closed
app._slow_t = 0; app.tick(); assert app.chip_text.cget("text") == "Silent" and app.tray.state_key == "silent"
kb.press("xbutton1"); time.sleep(0.08)
assert rx.ptt_held and not rx.gate_closed, "no pump() call: the engine heard it straight away"
kb.release("xbutton1"); time.sleep(0.08); assert not rx.ptt_held and rx.gate_closed
app.binder.set(sm.BY_KEY["hotkeys.push_to_talk"], ""); assert not rx.ptt_active and not rx.gate_closed
app.binder.set(sm.BY_KEY["hotkeys.push_to_mute"], "f9")
kb.press("f9"); time.sleep(0.08); assert rx.hold_mute and rx.gate_closed
kb.release("f9"); time.sleep(0.08); assert not rx.hold_mute
print("   PASS")

print("6. a key can only do one job: assigning it again moves it")
other = by_key["hotkeys.toggle_record"]; other._start(); time.sleep(0.05); press("ctrl", "alt", "m"); pump()
assert cfg.data["hotkeys"]["toggle_record"] == "ctrl+alt+m" and cfg.data["hotkeys"]["toggle_mute"] == ""
assert "was moved here" in app.status_left.cget("text") and by_key["hotkeys.toggle_mute"].key_btn.cget("text") == "Not set"
assert not rx.paused, "reassigning the keys must not also trigger the old action"
other._start(); time.sleep(0.05); kb.held.add(hk.VK_ESCAPE); time.sleep(0.05); kb.held.discard(hk.VK_ESCAPE); pump()
assert cfg.data["hotkeys"]["toggle_record"] == "ctrl+alt+m", "Escape cancels without changing anything"
print("   PASS")

print("7. turning global shortcuts off removes every binding and re-opens the microphone")
app.binder.set(sm.BY_KEY["hotkeys.push_to_talk"], "f7"); assert rx.gate_closed
app.binder.set(sm.BY_KEY["hotkeys.enabled"], False)
assert app.hotkeys.bindings == {} and not rx.ptt_active and not rx.gate_closed
app.binder.set(sm.BY_KEY["hotkeys.enabled"], True); assert "push_to_talk" in app.hotkeys.bindings
app.binder.set(sm.BY_KEY["hotkeys.push_to_talk"], "")
print("   PASS")

print("8. tray menu actions reach the app through the queue")
items = [i for i in icon.menu.items if i is not FakeMenu.SEPARATOR]
show, mute, monitor, record, bypass, quit_item = items
mute.action(None, mute); assert app.actions_q.qsize() == 1 and not rx.paused, "nothing runs on the tray thread"
pump(0.01); assert rx.paused; mute.action(None, mute); pump(0.01); assert not rx.paused
monitor.action(None, monitor); pump(0.01); assert rx.monitoring; monitor.action(None, monitor); pump(0.01); assert not rx.monitoring
bypass.action(None, bypass); pump(0.01); assert app.proc.fx_bypass; bypass.action(None, bypass); pump(0.01); assert not app.proc.fx_bypass
print("   PASS")

print("9. close-to-tray hides the window; a second launch or the tray brings it back")
app.binder.set(sm.BY_KEY["app.close_to_tray"], True)
app.on_close(); assert app.root.state() == "withdrawn" and rx.running, "still running in the background"
assert icon.notified, "tells the user where it went (once)"; n = len(icon.notified); app.show_window(); app.on_close(); assert len(icon.notified) == n
app.tick(); assert app.root.state() == "withdrawn"
assert system.signal_running_instance() is True; pump(0.1); assert app.root.state() == "normal"
app.on_close(); show.action(None, show); pump(0.05); assert app.root.state() == "normal"
print("   PASS")

print("10. without the tray, the close button quits")
app.binder.set(sm.BY_KEY["app.tray_icon"], False); assert not app.tray.running and icon.stopped
app.binder.set(sm.BY_KEY["app.tray_icon"], True); assert app.tray.running
app.binder.set(sm.BY_KEY["app.tray_icon"], False)
print("   PASS")

print("11. self-test button fills the result box")
app.show_page("log"); log = app.pages["log"]; log._selftest(); time.sleep(2.5); pump(0.05)
assert "Network adapters" in log.selftest_result and "Network adapters" in log.selftest_text.content
print("   PASS")

print("12. quit stops everything and saves; quitting twice is harmless")
app.binder.set(sm.BY_KEY["app.close_to_tray"], False)
stop.set(); app.on_close(); app.quit_app()
assert not rx.running and app.hotkeys._thread is None and app.root.destroyed
saved = json.load(open(os.path.join(d, "c.json")))
assert saved["hotkeys"]["toggle_record"] == "ctrl+alt+m" and saved["app"]["tray_icon"] is False
print("   PASS")
