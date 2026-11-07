"""Dev tool: render the custom-drawn widgets to kit_sheet.png for a visual check (not part of the test-suite)."""
import _path  # noqa: F401
import fake_tk; fake_tk.install()
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fake_tk import render_canvas, Frame
from phonemic import widgets as W, ui_kit as K, settings_meta as sm, dsp

T = W.T
root = Frame(None, bg=T.SURFACE)
tiles = []
def add(title, img, bg=None):
    if img.width > 1300: img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    tiles.append((title, img))

# icons
strip = Image.new("RGB", (400, 44), T.SURFACE)
x = 8
for kind, lit, faint, label in (("info", False, False, "info"), ("info", True, False, "info open"), ("reset", False, True, "reset (default)"), ("reset", True, False, "reset (changed)")):
    b = K.IconButton(root, kind, bg=T.SURFACE); b.set_lit(lit); b.set_faint(faint)
    img = render_canvas(b, b.px, b.px, scale=4); strip.paste(img.resize((32, 32), Image.LANCZOS), (x, 6)); x += 96
add("Icons: info, info open, reset at default, reset when changed", strip)

# stage list
sl = K.StageList(root, sm.STAGES, lambda sid: None, bg=T.BG)
sl.choose("noise")
for sid, led in (("filters", True), ("noise", True), ("gate", True), ("eq", True), ("comp", False), ("agc", False), ("deess", False), ("voice", False)):
    sl.set_led(sid, led)
for st in sm.STAGES: sl._draw(st.id)          # real Tk fires <Configure> when the widget is shown
rows = [render_canvas(sl.items[st.id], 180, 38, scale=1, bg=T.BG) for st in sm.STAGES]
col = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)), T.BG); y = 0
for r in rows: col.paste(r, (0, y)); y += r.height
add("Signal chain list (Noise suppression selected, lights show what is on)", col)

# gauges
g = Image.new("RGB", (640, 4 * 60), T.SURFACE)
for i, (lab, txt, frac, colr) in enumerate((("Latency", "42 ms", 0.28, T.GOOD), ("Jitter", "9.5 ms", 0.30, T.GOOD), ("Packet loss", "2.40 %", 0.6, T.WARN), ("Bitrate", "768 kbps", 0.9, T.ACCENT))):
    ga = K.GaugeRow(root, lab, bg=T.SURFACE); ga._opts["width"] = 320; ga._build(); ga.set(txt, frac, colr)
    g.paste(render_canvas(ga, 320, 30, scale=2), (0, i * 60))
add("Link health gauges", g)

# EQ editor (Podcast preset, band 3 selected)
p = dsp.AudioProcessor(); p.apply_fx(dsp.fx_preset("Podcast & Streamer")); p.set_param("eq4_type", "notch"); p.set_param("eq4_freq", 5200.0)
ed = K.EQEditor(root, height=210); ed._opts["width"] = 560; ed._opts["height"] = 210
fr = np.geomspace(20, 20000, 160)
ed.set_state([p.eq_band(n) for n in range(1, 6)], fr, p.eq_curve_db(fr), 3, True)
add("EQ editor (band 3 selected, band 4 is a notch)", render_canvas(ed, 560, 210, scale=1))
p.set_param("eq2_on", False); ed.set_state([p.eq_band(n) for n in range(1, 6)], fr, p.eq_curve_db(fr), 2, True)
add("EQ editor (band 2 switched off and selected)", render_canvas(ed, 560, 210, scale=1))

W_ = 700; fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
H = sum(i.height + 26 for _, i in tiles) + 10
sheet = Image.new("RGB", (W_, H), "#10131a"); d = ImageDraw.Draw(sheet); y = 6
for title, img in tiles:
    d.text((12, y), title, fill="#b4bcc9", font=fnt); y += 20; sheet.paste(img, (12, y)); y += img.height + 6
sheet.save("kit_sheet.png"); print(sheet.size)
