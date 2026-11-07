"""Tray icon (with a fake pystray), cues, the second-launch channel and the self-test."""
import io
import time
import wave
import _path  # noqa: F401
from PIL import Image, ImageDraw
from phonemic import tray, cues, system, selftest


class FakeMenuItem:
    def __init__(self, text, action, checked=None, default=False):
        self.text, self.action, self.checked, self.default = text, action, checked, default


class FakeMenu:
    SEPARATOR = object()

    def __init__(self, *items):
        self.items = items


class FakeIcon:
    instances = []

    def __init__(self, name, icon, title, menu):
        self.name, self.icon, self.title, self.menu = name, icon, title, menu
        self.ran = self.stopped = False
        self.updated = 0
        self.notified = []
        FakeIcon.instances.append(self)

    def run(self):
        self.ran = True

    def stop(self):
        self.stopped = True

    def update_menu(self):
        self.updated += 1

    def notify(self, message, title):
        self.notified.append((message, title))


class FakePystray:
    Icon, Menu, MenuItem = FakeIcon, FakeMenu, FakeMenuItem


def make_tray(state=None):
    calls = []
    actions = {k: (lambda k=k: calls.append(k)) for k in ("show", "mute", "monitor", "record", "bypass", "quit")}
    st = state or {"muted": False, "monitoring": False, "recording": False, "bypassed": False}
    return tray.TrayIcon(actions, lambda: st, modules=(FakePystray, Image, ImageDraw)), calls, st


def test_tray_menu_structure_labels_and_callbacks():
    t, calls, st = make_tray()
    assert t.available and not t.running
    assert t.start("waiting") is True and t.running
    icon = FakeIcon.instances[-1]; time.sleep(0.05)
    assert icon.ran and icon.title == "PhoneMic Receiver"
    items = [i for i in icon.menu.items if i is not FakeMenu.SEPARATOR]
    assert [i.text if isinstance(i.text, str) else i.text(None) for i in items] == ["Show PhoneMic Receiver", "Mute", "Monitor", "Record", "Effects bypassed", "Quit"]
    assert items[0].default, "clicking the icon shows the window"
    st["muted"] = True; assert items[1].text(None) == "Unmute"
    st["recording"] = True; assert items[3].checked(None) is True and items[2].checked(None) is False
    for item, name in zip(items, ("show", "mute", "monitor", "record", "bypass", "quit")):
        item.action(None, item)
    assert calls == ["show", "mute", "monitor", "record", "bypass", "quit"]
    t.stop(); assert icon.stopped and not t.running


def test_tray_state_updates_only_when_something_changed():
    t, _, _ = make_tray(); t.start("waiting"); icon = FakeIcon.instances[-1]
    first = icon.icon
    t.set_state("waiting", "PhoneMic Receiver"); assert icon.icon is first, "no change, no redraw"
    t.set_state("streaming", "Streaming from 192.168.1.5"); assert icon.icon is not first and icon.title == "Streaming from 192.168.1.5"
    t.set_state("streaming", "x" * 300); assert len(icon.title) == 127, "Windows tooltips are limited to 127 characters"
    t.refresh_menu(); assert icon.updated == 1
    t.notify("Still running in the tray."); assert icon.notified == [("Still running in the tray.", "PhoneMic Receiver")]
    t.stop(); t.set_state("muted"); t.refresh_menu(); t.notify("x")          # everything is safe after stop


def test_tray_without_the_optional_packages_is_a_no_op():
    t = tray.TrayIcon({}, lambda: {}, modules=None)
    assert not t.available and t.start() is False and not t.running
    t.set_state("streaming"); t.stop()


def test_tray_images_are_distinct_per_state_and_the_right_size():
    imgs = {k: tray.make_image(c, Image, ImageDraw) for k, c in tray.STATE_COLORS.items()}
    assert all(i.size == (64, 64) and i.mode == "RGBA" for i in imgs.values())
    assert imgs["streaming"].tobytes() != imgs["muted"].tobytes() != imgs["error"].tobytes()
    px = imgs["streaming"].getpixel((54, 54))
    assert px[1] > px[0] and px[3] == 255, "the status dot is green when streaming"


def test_cues_are_valid_short_clickless_wavs():
    for kind in ("mute", "unmute", "on", "off"):
        data = cues.make_cue_wav(kind)
        w = wave.open(io.BytesIO(data)); n = w.getnframes(); frames = w.readframes(n)
        assert w.getframerate() == 44100 and w.getnchannels() == 1 and 0.07 < n / 44100 < 0.2, kind
        first, last = int.from_bytes(frames[:2], "little", signed=True), int.from_bytes(frames[-2:], "little", signed=True)
        assert abs(first) < 100 and abs(last) < 100, "starts and ends at silence"
    assert cues.make_cue_wav("mute") != cues.make_cue_wav("unmute")
    assert cues.play("mute") in (True, False)                      # never raises, silent off Windows


def test_second_launch_reaches_the_running_copy():
    got = []
    stop = system.start_instance_listener(lambda: got.append(1), port=47590)
    assert stop is not None
    assert system.start_instance_listener(lambda: None, port=47590) is None, "only one listener per port"
    assert system.signal_running_instance(port=47590) is True
    for _ in range(40):
        if got:
            break
        time.sleep(0.025)
    assert got == [1]
    stop(); time.sleep(0.7)
    assert system.signal_running_instance(port=47590, timeout=0.3) is False, "nobody is listening any more"


def test_selftest_runs_everywhere_and_formats_a_readable_report():
    results = selftest.run_selftest()
    assert {"Version and platform", "Second-launch channel", "Network adapters"} <= {r.name for r in results}
    assert all(r.status in ("pass", "fail", "skip") for r in results)
    text = selftest.format_results(results)
    assert "PASS" in text and "PhoneMic Receiver" in text and not any(r.status == "fail" for r in results), text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
