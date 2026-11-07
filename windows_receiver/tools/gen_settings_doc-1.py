"""Writes SETTINGS.md from the settings registry, so the reference can never disagree with the app.
Run:  python tools/gen_settings_doc.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from phonemic import settings_meta as sm            # noqa: E402
from phonemic.const import VERSION                  # noqa: E402

PAGES = (("sound", "Sound"), ("voice", "Voice Changer"), ("devices", "Audio Devices"), ("network", "Network"), ("settings", "Settings"))


def value_info(s):
    d = sm.default_of(s)
    if s.kind == "slider":
        lo, hi = sm.format_value(s.fmt, s.lo), sm.format_value(s.fmt, s.hi)
        return f"{lo} to {hi}, default {sm.format_value(s.fmt, d)}"
    if s.kind == "toggle":
        return "on or off, default " + ("on" if d else "off") if d is not None else "on or off"
    if s.kind == "choice":
        names = dict(s.choices)
        return "one of " + ", ".join(names[k] for k in names) + f"; default {names.get(d, d)}"
    return ""


def main():
    out = [f"# PhoneMic Receiver {VERSION}: settings reference", "",
           "Generated from the settings registry that drives the app, so it always matches what you see. "
           "Settings marked *advanced* only appear when **Settings view: Advanced** is turned on (bottom of the sidebar). "
           "You can also find any setting with the search box at the top of the window.", ""]
    for page, title in PAGES:
        out += [f"## {title}", ""]
        if page == "sound":
            groups = [(st.id, st.title, st.blurb) for st in sm.STAGES if not st.link]
        else:
            groups = [(c[0], c[1], c[2]) for c in sm.CARDS.get(page, ())] or [("voice", "Voice changer", "")]
        for gid, gtitle, blurb in groups:
            items = sm.by_group(page, gid)
            if not items:
                continue
            out += [f"### {gtitle}", "", blurb, ""] if blurb else [f"### {gtitle}", ""]
            for s in items:
                tag = " *(advanced)*" if s.advanced else ""
                out += [f"**{s.label}**{tag}  ", f"{s.summary} {s.details}  ", f"_{value_info(s)}_" if value_info(s) else "", ""]
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SETTINGS.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"wrote {path} ({len(sm.REGISTRY)} settings)")


if __name__ == "__main__":
    main()
