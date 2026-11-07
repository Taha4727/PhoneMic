"""Global shortcuts that work in any app, including full-screen games.

How it works: a small thread polls the keyboard and mouse-button state (GetAsyncKeyState) about 100 times a second.
Polling (instead of RegisterHotKey) gives us both the press AND the release, which push-to-talk needs, does not install a
keyboard hook (anti-cheat software dislikes those) and never blocks the key from the game.

Shortcuts are stored as text such as "ctrl+alt+m", "f9" or "xbutton1". A shortcut is active when its key is down and exactly
its modifiers are down, so "f9" does not fire while Ctrl+F9 is held.
"""
import sys
import threading
from collections import namedtuple

IS_WIN = sys.platform.startswith("win")

Combo = namedtuple("Combo", "mods vk")

MOD_ORDER = ("ctrl", "alt", "shift", "win")
MOD_VKS = {"ctrl": (0x11,), "alt": (0x12,), "shift": (0x10,), "win": (0x5B, 0x5C)}
MOD_ALIASES = {"control": "ctrl", "windows": "win", "cmd": "win", "super": "win", "option": "alt"}

KEYS = {}
for _i in range(26):
    KEYS[chr(97 + _i)] = 0x41 + _i
for _i in range(10):
    KEYS[str(_i)] = 0x30 + _i
    KEYS[f"num{_i}"] = 0x60 + _i
for _i in range(1, 25):
    KEYS[f"f{_i}"] = 0x6F + _i
KEYS.update({"space": 0x20, "enter": 0x0D, "tab": 0x09, "backspace": 0x08, "insert": 0x2D, "delete": 0x2E, "home": 0x24,
             "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
             "capslock": 0x14, "scrolllock": 0x91, "numlock": 0x90, "pause": 0x13, "printscreen": 0x2C,
             "nummul": 0x6A, "numadd": 0x6B, "numsub": 0x6D, "numdecimal": 0x6E, "numdiv": 0x6F,
             ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF, "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
             "mouse3": 0x04, "xbutton1": 0x05, "xbutton2": 0x06})
VK_TO_NAME = {v: k for k, v in KEYS.items()}
VK_ESCAPE = 0x1B
CAPTURE_VKS = sorted(set(KEYS.values()))                # mouse left/right (0x01, 0x02) are deliberately not capturable

PRETTY = {"mouse3": "Mouse middle button", "xbutton1": "Mouse side button 1", "xbutton2": "Mouse side button 2",
          "pageup": "Page Up", "pagedown": "Page Down", "printscreen": "Print Screen", "capslock": "Caps Lock",
          "scrolllock": "Scroll Lock", "numlock": "Num Lock", "backspace": "Backspace", "space": "Space", "enter": "Enter",
          "tab": "Tab", "insert": "Insert", "delete": "Delete", "home": "Home", "end": "End", "pause": "Pause",
          "up": "Up", "down": "Down", "left": "Left", "right": "Right",
          "nummul": "Numpad *", "numadd": "Numpad +", "numsub": "Numpad -", "numdecimal": "Numpad .", "numdiv": "Numpad /"}


def parse_combo(text):
    """'ctrl+alt+m' -> Combo; None when the text is empty or not a valid shortcut."""
    if not isinstance(text, str) or not text.strip():
        return None
    parts = [p.strip().lower() for p in text.strip().split("+")]
    if parts and parts[-1] == "":
        return None
    mods = set()
    for p in parts[:-1]:
        p = MOD_ALIASES.get(p, p)
        if p not in MOD_VKS:
            return None
        mods.add(p)
    key = parts[-1]
    if key not in KEYS:
        return None
    return Combo(frozenset(mods), KEYS[key])


def canonical(combo):
    """Combo -> storage text, modifiers in a fixed order."""
    return "+".join([m for m in MOD_ORDER if m in combo.mods] + [VK_TO_NAME[combo.vk]])


def display(text):
    """Storage text -> what the user reads: 'Ctrl+Alt+M'. Empty text -> 'Not set'."""
    combo = parse_combo(text)
    if combo is None:
        return "Not set"
    key = VK_TO_NAME[combo.vk]
    if key in PRETTY:
        shown = PRETTY[key]
    elif key.startswith("num") and key[3:].isdigit():
        shown = "Numpad " + key[3:]
    else:
        shown = key.upper()                                  # letters, digits, F keys, punctuation
    return "+".join([("Ctrl" if m == "ctrl" else m.capitalize()) for m in MOD_ORDER if m in combo.mods] + [shown])


class NullBackend:
    available = False

    def down(self, vk):
        return False


class WinKeyBackend:
    available = True

    def __init__(self):
        import ctypes
        self._f = ctypes.windll.user32.GetAsyncKeyState
        self._f.argtypes = [ctypes.c_int]
        self._f.restype = ctypes.c_short

    def down(self, vk):
        return bool(self._f(vk) & 0x8000)


def default_backend():
    if IS_WIN:
        try:
            return WinKeyBackend()
        except Exception:
            pass
    return NullBackend()


class HotkeyService:
    """Watches the configured shortcuts. `on_press(action)` fires once per press (toggle actions); `on_hold(action, down)`
    fires on both edges for the hold actions. Both run on the polling thread, so keep them short."""
    HOLD_ACTIONS = ("push_to_talk", "push_to_mute")

    def __init__(self, on_press, on_hold, backend=None, poll_s=0.01, log=None):
        self.on_press, self.on_hold = on_press, on_hold
        self.backend = backend or default_backend()
        self.poll_s = poll_s
        self.log = log or (lambda msg: None)
        self.bindings = {}              # action -> Combo
        self.active = {}                # action -> bool (last seen)
        self._capture = None
        self._ignore = set()
        self._lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()

    @property
    def available(self):
        return bool(self.backend.available)

    # ---- configuration ---------------------------------------------------------------------------------------------------
    def set_bindings(self, mapping):
        """mapping: {action: text}. Invalid or empty entries are ignored. A key that is already held when it is bound
        does not fire until it has been released and pressed again."""
        new = {}
        for action, text in mapping.items():
            combo = parse_combo(text)
            if combo is not None:
                new[action] = combo
        with self._lock:
            released = [a for a in self.active if self.active[a] and a not in new and a in self.HOLD_ACTIONS]
            self.bindings = new
            mods = self._mods()
            self.active = {a: self._is_active(c, mods) for a, c in new.items()}
        for a in released:                               # a hold shortcut was removed while held: let go cleanly
            self._safe(self.on_hold, a, False)
        if new and self.available:
            self.start()
        elif not new:
            self.stop()

    # ---- polling -------------------------------------------------------------------------------------------------------------
    def _mods(self):
        return frozenset(m for m, vks in MOD_VKS.items() if any(self.backend.down(v) for v in vks))

    def _is_active(self, combo, mods):
        return mods == combo.mods and self.backend.down(combo.vk)

    def poll_once(self):
        if self._capture is not None:
            self._poll_capture()
            return
        mods = self._mods()
        with self._lock:
            items = list(self.bindings.items())
        for action, combo in items:
            now = self._is_active(combo, mods)
            if now != self.active.get(action, False):
                self.active[action] = now
                if action in self.HOLD_ACTIONS:
                    self._safe(self.on_hold, action, now)
                elif now:
                    self._safe(self.on_press, action)

    def _safe(self, fn, *args):
        try:
            fn(*args)
        except Exception as e:      # noqa: BLE001 - a broken callback must never stop the poller
            self.log(f"Shortcut handler error: {e!r}")

    # ---- capturing a new shortcut -------------------------------------------------------------------------------------------
    def capture(self, callback):
        """Next key (with its modifiers) pressed anywhere becomes the result: callback(text) or callback(None) on Escape."""
        with self._lock:
            held = [a for a in self.HOLD_ACTIONS if self.active.get(a)]
            for a in held:
                self.active[a] = False
            self._ignore = {vk for vk in CAPTURE_VKS if self.backend.down(vk)}      # keys already down are not the answer
            self._capture = callback
        for a in held:                                   # shortcuts are suspended while capturing: let go of any held gate
            self._safe(self.on_hold, a, False)
        if self.available:
            self.start()

    def cancel_capture(self):
        with self._lock:
            self._capture = None

    def _poll_capture(self):
        cb = self._capture
        if self.backend.down(VK_ESCAPE):
            self._finish_capture(cb, None)
            return
        mods = self._mods()
        for vk in CAPTURE_VKS:
            down = self.backend.down(vk)
            if vk in self._ignore:
                if not down:
                    self._ignore.discard(vk)
                continue
            if down:
                self._finish_capture(cb, canonical(Combo(mods, vk)))
                return

    def _finish_capture(self, cb, text):
        with self._lock:
            self._capture = None
            mods = self._mods()                          # the keys just pressed are still down: they are not a new press
            self.active = {a: self._is_active(c, mods) for a, c in self.bindings.items()}
        self._safe(cb, text)
        if not self.bindings:
            self.stop()

    # ---- thread ---------------------------------------------------------------------------------------------------------------
    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="PM-Hotkeys", daemon=True)
        self._thread.start()

    def stop(self):
        if self._capture is not None:
            return                                       # keep polling until the pending capture finishes
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None and t is not threading.current_thread():
            t.join(timeout=1.0)

    def shutdown(self):
        self._capture = None
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None and t is not threading.current_thread():
            t.join(timeout=1.0)

    def _run(self):
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception as e:      # noqa: BLE001
                self.log(f"Shortcut poller error: {e!r}")
            self._stop.wait(self.poll_s)
