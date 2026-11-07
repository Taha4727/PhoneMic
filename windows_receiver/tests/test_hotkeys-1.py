"""Global shortcuts: parsing, exact-modifier matching, hold actions, capture. Uses a fake keyboard, never the real one."""
import time
import _path  # noqa: F401
from phonemic import hotkeys as hk


class FakeKeys:
    available = True

    def __init__(self):
        self.held = set()

    def down(self, vk):
        return vk in self.held

    def press(self, *names):
        for n in names:
            self.held.add(hk.MOD_VKS[n][0] if n in hk.MOD_VKS else hk.KEYS[n])

    def release(self, *names):
        for n in names:
            self.held.discard(hk.MOD_VKS[n][0] if n in hk.MOD_VKS else hk.KEYS[n])


def service(bindings):
    kb, log = FakeKeys(), []
    svc = hk.HotkeyService(lambda a: log.append(("press", a)), lambda a, d: log.append(("hold", a, d)), backend=kb)
    svc.backend = kb
    svc.bindings = {a: hk.parse_combo(t) for a, t in bindings.items() if hk.parse_combo(t)}
    svc.active = {a: False for a in svc.bindings}          # no thread: the test drives poll_once() itself
    return svc, kb, log


def test_parse_format_roundtrip():
    for text in ("ctrl+alt+m", "f9", "xbutton1", "ctrl+shift+f12", "win+space", "numadd", "alt+num5", "mouse3", "ctrl+;", "shift+pageup"):
        c = hk.parse_combo(text)
        assert c is not None and hk.canonical(c) == text, text
    assert hk.parse_combo("Control+Alt+M") == hk.parse_combo("ctrl+alt+m") and hk.canonical(hk.parse_combo("alt+ctrl+m")) == "ctrl+alt+m"
    for bad in ("", "  ", "ctrl+", "ctrl+alt", "banana", "ctrl+banana", "m+ctrl", None, 5, "ctrl++"):
        assert hk.parse_combo(bad) is None, bad
    assert hk.display("ctrl+alt+m") == "Ctrl+Alt+M" and hk.display("f9") == "F9" and hk.display("") == "Not set"
    assert hk.display("xbutton1") == "Mouse side button 1" and hk.display("num5") == "Numpad 5" and hk.display("numadd") == "Numpad +"
    assert hk.display("alt+pageup") == "Alt+Page Up"


def test_toggle_fires_once_per_press():
    svc, kb, log = service({"toggle_mute": "ctrl+alt+m"})
    kb.press("ctrl", "alt"); svc.poll_once(); assert log == []
    kb.press("m"); svc.poll_once(); svc.poll_once(); svc.poll_once()
    assert log == [("press", "toggle_mute")], "held key fires once, not on every poll"
    kb.release("m"); svc.poll_once(); kb.press("m"); svc.poll_once()
    assert log.count(("press", "toggle_mute")) == 2


def test_modifiers_must_match_exactly():
    svc, kb, log = service({"toggle_record": "f9", "toggle_mute": "ctrl+f9"})
    kb.press("ctrl", "f9"); svc.poll_once()
    assert log == [("press", "toggle_mute")], "Ctrl+F9 must not also trigger plain F9"
    kb.release("ctrl", "f9"); svc.poll_once(); log.clear()
    kb.press("shift", "f9"); svc.poll_once(); assert log == []
    kb.release("shift"); svc.poll_once(); assert log == [("press", "toggle_record")], "F9 fires once Shift is let go while the key is held"
    log.clear(); kb.release("f9"); svc.poll_once(); kb.press("f9"); svc.poll_once(); assert log == [("press", "toggle_record")]


def test_hold_actions_report_both_edges_including_mouse_buttons():
    svc, kb, log = service({"push_to_talk": "xbutton1", "push_to_mute": "ctrl+alt+x"})
    kb.press("xbutton1"); svc.poll_once(); kb.release("xbutton1"); svc.poll_once()
    kb.press("ctrl", "alt", "x"); svc.poll_once(); kb.release("x"); svc.poll_once()
    assert log == [("hold", "push_to_talk", True), ("hold", "push_to_talk", False),
                   ("hold", "push_to_mute", True), ("hold", "push_to_mute", False)]


def test_rebinding_does_not_fire_for_a_key_that_is_already_held():
    svc, kb, log = service({})
    kb.press("f9")
    svc.backend = kb
    svc.set_bindings({"toggle_mute": "f9"})
    svc.shutdown(); log.clear()
    svc.poll_once(); assert log == [], "F9 was held while binding: wait for release"
    kb.release("f9"); svc.poll_once(); kb.press("f9"); svc.poll_once(); assert log == [("press", "toggle_mute")]


def test_removing_a_held_hold_shortcut_releases_cleanly():
    svc, kb, log = service({"push_to_talk": "f10"})
    kb.press("f10"); svc.poll_once(); assert log == [("hold", "push_to_talk", True)]
    svc.set_bindings({}); svc.shutdown()
    assert log[-1] == ("hold", "push_to_talk", False), "the talk gate must not stay open after the key is unbound"


def test_capture_takes_the_next_key_with_modifiers_and_ignores_keys_already_down():
    svc, kb, log = service({})
    got = []
    kb.press("enter")                                    # e.g. the key that started the capture
    svc.capture(got.append)
    svc._stop.set()
    svc.poll_once(); assert got == [], "a key that was already down is not the answer"
    kb.release("enter"); svc.poll_once()
    kb.press("ctrl", "shift"); svc.poll_once(); assert got == [], "modifiers alone are not a shortcut"
    kb.press("f7"); svc.poll_once()
    assert got == ["ctrl+shift+f7"] and svc._capture is None
    svc.capture(got.append); kb.held.clear(); kb.held.add(hk.VK_ESCAPE); svc.poll_once()
    assert got[-1] is None, "Escape cancels"
    kb.held.clear(); svc.capture(got.append); kb.press("xbutton2"); svc.poll_once(); assert got[-1] == "xbutton2"
    log.clear(); kb.press("f1"); svc.bindings = {"toggle_mute": hk.parse_combo("f1")}; svc.active = {"toggle_mute": False}
    svc.capture(got.append); kb.release("f1"); svc.poll_once(); assert log == [], "shortcuts are suspended while capturing"


def test_keys_held_at_the_end_of_a_capture_do_not_trigger_old_bindings():
    svc, kb, log = service({"toggle_mute": "ctrl+alt+m", "push_to_talk": "f4"})
    got = []
    svc.capture(got.append)
    kb.press("ctrl", "alt", "m"); svc.poll_once()
    assert got == ["ctrl+alt+m"]
    svc.poll_once(); svc.poll_once()
    assert log == [], "reassigning ctrl+alt+m must not also fire the action it used to have"
    kb.release("m"); svc.poll_once(); kb.press("m"); svc.poll_once()
    assert log == [("press", "toggle_mute")], "the next real press works"


def test_starting_a_capture_while_a_hold_key_is_down_releases_the_gate():
    svc, kb, log = service({"push_to_talk": "f4"})
    kb.press("f4"); svc.poll_once(); assert log == [("hold", "push_to_talk", True)]
    svc.capture(lambda t: None)
    assert log[-1] == ("hold", "push_to_talk", False), "the talk gate must not stay open while shortcuts are suspended"


def test_real_thread_delivers_events_and_survives_bad_callbacks():
    kb, log = FakeKeys(), []
    def press(a):
        log.append(a)
        raise RuntimeError("boom")
    svc = hk.HotkeyService(press, lambda a, d: log.append((a, d)), backend=kb, poll_s=0.005)
    svc.set_bindings({"toggle_mute": "f5", "push_to_talk": "f6"})
    kb.press("f5"); time.sleep(0.1); kb.release("f5"); kb.press("f6"); time.sleep(0.1); kb.release("f6"); time.sleep(0.05)
    svc.shutdown()
    assert log == ["toggle_mute", ("push_to_talk", True), ("push_to_talk", False)], log
    assert svc._thread is None


def test_null_backend_is_harmless():
    svc = hk.HotkeyService(lambda a: None, lambda a, d: None, backend=hk.NullBackend())
    svc.set_bindings({"toggle_mute": "f9"}); assert not svc.available and svc._thread is None
    svc.capture(lambda t: None); svc.cancel_capture(); svc.shutdown()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
