"""Readability: every text colour must meet WCAG AA (4.5 : 1) on every surface it can appear on, for every accent."""
import _path  # noqa: F401
import fake_tk; fake_tk.install()
from phonemic import widgets as W


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_text_contrast_on_every_surface():
    T = W.T
    for fg in ("TEXT", "MUTED", "DIM", "GOOD", "WARN", "BAD"):
        for bg in ("BG", "SURFACE", "SURFACE2", "SIDEBAR"):
            assert ratio(getattr(T, fg), getattr(T, bg)) >= 4.5, (fg, bg, ratio(getattr(T, fg), getattr(T, bg)))


def test_every_accent_is_readable_and_buttons_have_readable_labels():
    T = W.T
    saved = (T.ACCENT, T.ACCENT_HI, T.ACCENT_FG)
    try:
        for name, (acc, hi, fg) in W.ACCENTS.items():
            W.apply_accent(name)
            for bg in ("BG", "SURFACE", "SURFACE2", "SIDEBAR"):
                assert ratio(T.ACCENT, getattr(T, bg)) >= 4.5 and ratio(T.ACCENT_HI, getattr(T, bg)) >= 4.5, (name, bg)
            for style, (bgc, hover, fgc) in W.FlatButton.STYLES.items():
                assert ratio(fgc, bgc) >= 4.5, (name, style, "label on button", ratio(fgc, bgc))
                assert ratio(fgc, hover) >= 4.0, (name, style, "label on hovered button", ratio(fgc, hover))
    finally:
        T.ACCENT, T.ACCENT_HI, T.ACCENT_FG = saved
        W.FlatButton.rebuild_styles()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
