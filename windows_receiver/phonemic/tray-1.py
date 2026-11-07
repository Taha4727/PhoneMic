"""Notification-area (tray) icon. Optional: needs the `pystray` and `Pillow` packages; without them the app simply has no tray."""
import threading

STATE_COLORS = {"waiting": "#949eae", "streaming": "#4cd48a", "muted": "#ffb547", "silent": "#ffb547", "lost": "#ffb547",
                "error": "#ff6c71"}

_base = {}


def load_modules():
    """-> (pystray, PIL.Image, PIL.ImageDraw) or None when the optional packages are not installed."""
    try:
        import pystray
        from PIL import Image, ImageDraw
        return pystray, Image, ImageDraw
    except Exception:
        return None


def make_image(color, Image, ImageDraw, size=64):
    """The app icon with a coloured status dot in the corner."""
    key = (id(Image), size)
    if key not in _base:
        big = 256
        grad = Image.new("RGB", (2, 2))
        grad.putpixel((0, 0), (62, 166, 255)); grad.putpixel((1, 0), (101, 129, 250))
        grad.putpixel((0, 1), (101, 129, 250)); grad.putpixel((1, 1), (139, 92, 246))
        grad = grad.resize((big, big), Image.BILINEAR)
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=int(big * 0.22), fill=255)
        img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        img.paste(grad, (0, 0), mask)
        d, w, c = ImageDraw.Draw(img), (255, 255, 255, 255), big // 2
        d.rounded_rectangle((c - 31, 48, c + 31, 150), radius=31, fill=w)
        d.arc((c - 56, 85, c + 56, 186), start=20, end=160, fill=w, width=13)
        d.rectangle((c - 6, 186, c + 6, 210), fill=w)
        d.rounded_rectangle((c - 33, 205, c + 33, 218), radius=6, fill=w)
        _base[key] = img
    img = _base[key].copy()
    d = ImageDraw.Draw(img)
    big = img.size[0]
    r = int(big * 0.17)
    cx, cy = big - r - 6, big - r - 6
    d.ellipse((cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6), fill=(21, 25, 32, 255))     # dark ring so the dot reads on any taskbar
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    return img.resize((size, size), Image.LANCZOS)


class TrayIcon:
    """`actions`: callables (show, mute, monitor, record, bypass, quit) run on the tray thread - the owner must hand them to
    the UI thread. `get_state()` returns {'muted','monitoring','recording','bypassed'} for the menu check marks."""

    def __init__(self, actions, get_state, title="PhoneMic Receiver", modules="auto"):
        self.actions, self.get_state, self.title = actions, get_state, title
        self.mods = load_modules() if modules == "auto" else modules
        self.icon = None
        self.state_key = None
        self.tooltip = title
        self._lock = threading.Lock()

    @property
    def available(self):
        return self.mods is not None

    @property
    def running(self):
        return self.icon is not None

    def _menu(self):
        pystray = self.mods[0]
        Item, a, st = pystray.MenuItem, self.actions, self.get_state
        return pystray.Menu(
            Item("Show PhoneMic Receiver", lambda *_: a["show"](), default=True),
            pystray.Menu.SEPARATOR,
            Item(lambda item: "Unmute" if st()["muted"] else "Mute", lambda *_: a["mute"]()),
            Item("Monitor", lambda *_: a["monitor"](), checked=lambda item: st()["monitoring"]),
            Item("Record", lambda *_: a["record"](), checked=lambda item: st()["recording"]),
            Item("Effects bypassed", lambda *_: a["bypass"](), checked=lambda item: st()["bypassed"]),
            pystray.Menu.SEPARATOR,
            Item("Quit", lambda *_: a["quit"]()))

    def start(self, state_key="waiting"):
        """Show the icon. Returns False (and does nothing) when the optional packages are missing or the shell refuses."""
        if not self.available or self.icon is not None:
            return self.icon is not None
        pystray, Image, ImageDraw = self.mods
        try:
            self.state_key = state_key
            self.icon = pystray.Icon("PhoneMicReceiver", make_image(STATE_COLORS.get(state_key, STATE_COLORS["waiting"]), Image, ImageDraw),
                                     self.tooltip, self._menu())
            threading.Thread(target=self.icon.run, name="PM-Tray", daemon=True).start()
            return True
        except Exception:
            self.icon = None
            return False

    def set_state(self, state_key, tooltip=None):
        """Change the dot colour and tooltip. Cheap to call often: nothing happens unless something changed."""
        if self.icon is None:
            return
        tooltip = (tooltip or self.title)[:127]                        # Windows limits the tooltip to 127 characters
        with self._lock:
            try:
                if state_key != self.state_key:
                    self.state_key = state_key
                    self.icon.icon = make_image(STATE_COLORS.get(state_key, STATE_COLORS["waiting"]), self.mods[1], self.mods[2])
                if tooltip != self.tooltip:
                    self.tooltip = tooltip
                    self.icon.title = tooltip
            except Exception:
                pass

    def refresh_menu(self):
        if self.icon is not None:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def notify(self, message, title=None):
        if self.icon is not None:
            try:
                self.icon.notify(message, title or self.title)
            except Exception:
                pass

    def stop(self):
        icon, self.icon = self.icon, None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
