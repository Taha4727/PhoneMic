"""Dev tool: approximate Tk's pack/grid geometry over the fake widget tree and render pages to PNG.

Not a pixel-exact preview (fonts differ: DejaVu Sans is wider than Segoe UI, which makes this pessimistic about
clipping), but pack/grid sizing, expansion, wrapping and clipping follow Tk's algorithms, so overflow and crowding show up.
"""
import math
import types
from PIL import Image, ImageDraw, ImageFont
import _path  # noqa: F401
import fake_tk
from fake_tk import render_canvas

FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_cache = {}


def pil_font(spec):
    fam, size, weight = (list(spec) + ["normal"] * 3)[:3] if isinstance(spec, (tuple, list)) else ("x", 10, "normal")
    px = max(6, int(round(float(size) * 96 / 72)))
    key = (px, weight == "bold")
    if key not in _cache:
        _cache[key] = ImageFont.truetype(FONT_B if weight == "bold" else FONT_R, px)
    return _cache[key]


def metrics(spec):
    f = pil_font(spec)
    a, d = f.getmetrics()
    return f, a + d, f.getlength("0")


def wrap_lines(text, font, wrap):
    lines = []
    for para in str(text).split("\n"):
        if wrap and wrap > 0:
            words, cur = para.split(" "), ""
            for w in words:
                trial = (cur + " " + w).strip()
                if font.getlength(trial) <= wrap or not cur:
                    cur = trial
                else:
                    lines.append(cur); cur = w
            lines.append(cur)
        else:
            lines.append(para)
    return lines


def num(v, default=0):
    try:
        return float(v)
    except Exception:
        return default


def kind(w):
    for cls in type(w).__mro__:
        if cls.__name__ in ("Frame", "Label", "Canvas", "Entry", "Text", "Combobox", "Scrollbar", "TtkScrollbar", "Toplevel", "Tk"):
            return cls.__name__
    return "Frame"


def pads(kw, which):
    v = kw.get(which, 0)
    if isinstance(v, (tuple, list)):
        return num(v[0]), num(v[1])
    return num(v), num(v)


class Sim:
    def __init__(self):
        self.req_cache = {}
        self.boxes = {}                  # widget -> (x, y, w, h) relative to parent

    # ------------------------------------------------------------------ natural sizes
    def managed(self, w):
        return [c for c in w.children if c.packed is not None and not getattr(c, "destroyed", False)]

    def req(self, w):
        if w in self.req_cache:
            return self.req_cache[w]
        k = kind(w)
        o = w._opts
        if k == "Label":
            font, lh, cw = metrics(o.get("font", ("x", 10, "normal")))
            bd = 1 if o.get("borderwidth", o.get("bd")) is None else num(o.get("borderwidth", o.get("bd")))
            px, py = num(o.get("padx", 1)), num(o.get("pady", 1))
            lines = wrap_lines(o.get("text", ""), font, num(o.get("wraplength", 0)))
            tw = max((font.getlength(l) for l in lines), default=0)
            if o.get("width"):
                tw = num(o["width"]) * cw
            r = (tw + 2 * px + 2 * bd, len(lines) * lh + 2 * py + 2 * bd)
        elif k == "Canvas":
            r = (num(o.get("width", 378)) + 2 * num(o.get("highlightthickness", 2)), num(o.get("height", 265)) + 2 * num(o.get("highlightthickness", 2)))
        elif k == "Entry":
            font, lh, cw = metrics(o.get("font", ("x", 10, "normal")))
            hl = num(o.get("highlightthickness", 1))
            r = (num(o.get("width", 20)) * cw + 2 * (2 + hl) + 2, lh + 2 * (2 + hl) + 2)
        elif k == "Combobox":
            font, lh, cw = metrics(o.get("font", ("x", 10, "normal")))
            r = (num(o.get("width", 20)) * cw + 34, lh + 16)
        elif k == "Text":
            font, lh, cw = metrics(o.get("font", ("x", 10, "normal")))
            r = (num(o.get("width", 80)) * cw + 2 * num(o.get("padx", 1)), num(o.get("height", 24)) * lh + 2 * num(o.get("pady", 1)))
        elif k in ("Scrollbar", "TtkScrollbar"):
            r = (16, 16)
        else:                                            # Frame / Toplevel
            hl = 2 * num(o.get("highlightthickness", 0)) + 2 * num(o.get("borderwidth", o.get("bd", 0)))
            kids = self.managed(w)
            if not kids or getattr(w, "_pack_prop", True) is False:
                r = (num(o.get("width", 0)) + hl, num(o.get("height", 0)) + hl)
            elif kids[0].packed[0] == "grid":
                r = self.grid_req(w, kids)
                r = (r[0] + hl, r[1] + hl)
            else:
                r = self.pack_req(w, kids)
                r = (r[0] + hl, r[1] + hl)
                r = (max(r[0], num(o.get("width", 0))), max(r[1], num(o.get("height", 0)))) if kids else r
        self.req_cache[w] = r
        return r

    def slave_req(self, c):
        kw = c.packed[1]
        w, h = self.req(c)
        if kw.get("ipadx") or kw.get("ipady"):
            w, h = w + 2 * num(kw.get("ipadx", 0)), h + 2 * num(kw.get("ipady", 0))
        return w, h

    def pack_req(self, w, kids):
        width = height = maxw = maxh = 0
        for c in kids:
            kw = c.packed[1]
            rw, rh = self.slave_req(c)
            pl, pr = pads(kw, "padx"); pt, pb = pads(kw, "pady")
            side = kw.get("side", "top")
            if side in ("top", "bottom"):
                maxw = max(maxw, rw + pl + pr + width)
                height += rh + pt + pb
            else:
                maxh = max(maxh, rh + pt + pb + height)
                width += rw + pl + pr
        return max(maxw, width), max(maxh, height)

    # ------------------------------------------------------------------ grid
    def grid_tracks(self, w, kids, avail_w=None, avail_h=None):
        cols, rows = {}, {}
        for c in kids:
            kw = c.packed[1]
            col, row = int(kw.get("column", 0)), int(kw.get("row", 0))
            cs, rs = int(kw.get("columnspan", 1)), int(kw.get("rowspan", 1))
            rw, rh = self.slave_req(c)
            pl, pr = pads(kw, "padx"); pt, pb = pads(kw, "pady")
            rw, rh = rw + pl + pr, rh + pt + pb
            for i in range(cs):
                cols[col + i] = max(cols.get(col + i, 0), rw / cs if cs > 1 else rw)
            for i in range(rs):
                rows[row + i] = max(rows.get(row + i, 0), rh / rs if rs > 1 else rh)
        ccfg, rcfg = getattr(w, "_colcfg", {}), getattr(w, "_rowcfg", {})
        for i, cfg in ccfg.items():
            cols[i] = max(cols.get(i, 0), num(cfg.get("minsize", 0)))
        for i, cfg in rcfg.items():
            rows[i] = max(rows.get(i, 0), num(cfg.get("minsize", 0)))
        # uniform groups: widths proportional to weights, sized by the largest requirement per unit weight
        groups = {}
        for i, cfg in ccfg.items():
            if cfg.get("uniform") is not None:
                groups.setdefault(cfg["uniform"], []).append(i)
        for g, idxs in groups.items():
            unit = max(cols.get(i, 0) / max(1e-9, num(ccfg[i].get("weight", 1)) or 1) for i in idxs)
            for i in idxs:
                cols[i] = unit * (num(ccfg[i].get("weight", 1)) or 1)
        return cols, rows, ccfg, rcfg

    def grid_req(self, w, kids):
        cols, rows, _, _ = self.grid_tracks(w, kids)
        return sum(cols.values()), sum(rows.values())

    def grid_sizes(self, w, kids, W, H):
        cols, rows, ccfg, rcfg = self.grid_tracks(w, kids)
        def distribute(sizes, cfg, total):
            order = sorted(set(list(sizes) + list(cfg)))
            sizes = {i: sizes.get(i, 0) for i in order}
            extra = total - sum(sizes.values())
            wts = {i: num(cfg.get(i, {}).get("weight", 0)) for i in order}
            tw = sum(wts.values())
            if tw > 0 and extra != 0:
                if extra > 0:
                    for i in order:
                        sizes[i] += extra * wts[i] / tw
                else:                                   # too small: weighted columns give up space (never below 0)
                    for i in order:
                        if wts[i] > 0:
                            sizes[i] = max(0.0, sizes[i] + extra * wts[i] / tw)
            # uniform groups again after distribution
            groups = {}
            for i in order:
                u = cfg.get(i, {}).get("uniform")
                if u is not None:
                    groups.setdefault(u, []).append(i)
            for g, idxs in groups.items():
                tot = sum(sizes[i] for i in idxs); ws = sum((wts[i] or 1) for i in idxs)
                for i in idxs:
                    sizes[i] = tot * (wts[i] or 1) / ws
            return sizes
        return distribute(cols, ccfg, W), distribute(rows, rcfg, 0 if H is None else max(H, sum(rows.values())))

    # ------------------------------------------------------------------ arrangement
    def arrange(self, w, W, H):
        """Place the managed children of `w` inside a W x H box. Fills self.boxes (relative to w)."""
        k = kind(w)
        hl = num(w._opts.get("highlightthickness", 0)) + num(w._opts.get("borderwidth", w._opts.get("bd", 0))) if k in ("Frame", "Toplevel", "Tk") else 0
        ox = oy = hl
        W, H = W - 2 * hl, H - 2 * hl
        if k == "Canvas":
            for item in w.items.values():
                if item["type"] == "window" and item["opts"].get("window") is not None:
                    inner = item["opts"]["window"]
                    iw = num(item["opts"].get("width", W)) or W
                    ih = self.req(inner)[1]
                    self.boxes[inner] = (0, 0, iw, ih)
                    self.arrange(inner, iw, ih)
            return
        kids = self.managed(w)
        if not kids:
            return
        if kids[0].packed[0] == "grid":
            cw, rh = self.grid_sizes(w, kids, W, H)
            xs, ys, acc = {}, {}, 0
            for i in sorted(cw): xs[i] = acc; acc += cw[i]
            acc = 0
            for i in sorted(rh): ys[i] = acc; acc += rh[i]
            for c in kids:
                kw = c.packed[1]
                col, row = int(kw.get("column", 0)), int(kw.get("row", 0))
                cs, rs = int(kw.get("columnspan", 1)), int(kw.get("rowspan", 1))
                cellw = sum(cw.get(col + i, 0) for i in range(cs)); cellh = sum(rh.get(row + i, 0) for i in range(rs))
                pl, pr = pads(kw, "padx"); pt, pb = pads(kw, "pady")
                rw, rhh = self.slave_req(c)
                st = kw.get("sticky", "")
                width = cellw - pl - pr if ("e" in st and "w" in st) else min(rw, cellw - pl - pr)
                height = cellh - pt - pb if ("n" in st and "s" in st) else min(rhh, cellh - pt - pb)
                x = xs.get(col, 0) + pl + ((cellw - pl - pr - width) if ("e" in st and "w" not in st) else (0 if "w" in st else (cellw - pl - pr - width) / 2))
                y = ys.get(row, 0) + pt + ((cellh - pt - pb - height) if ("s" in st and "n" not in st) else (0 if "n" in st else (cellh - pt - pb - height) / 2))
                self.boxes[c] = (ox + x, oy + y, max(0, width), max(0, height))
                self.arrange(c, max(0, width), max(0, height))
            return
        # ---- pack (Tk's ArrangePacking)
        cavx = cavy = 0.0
        cavw, cavh = W, H
        for idx, c in enumerate(kids):
            kw = c.packed[1]
            rw, rh = self.slave_req(c)
            pl, pr = pads(kw, "padx"); pt, pb = pads(kw, "pady")
            side = kw.get("side", "top")
            expand = bool(kw.get("expand")) and kw.get("expand") not in (0, "0", "no", False)
            if side in ("top", "bottom"):
                fw = cavw
                fh = rh + pt + pb
                if expand:
                    fh += self.y_expansion(kids[idx:], cavh)
                cavh -= fh
                if cavh < 0:
                    fh += cavh; cavh = 0
                fx = cavx
                if side == "top":
                    fy = cavy; cavy += fh
                else:
                    fy = cavy + cavh
            else:
                fh = cavh
                fw = rw + pl + pr
                if expand:
                    fw += self.x_expansion(kids[idx:], cavw)
                cavw -= fw
                if cavw < 0:
                    fw += cavw; cavw = 0
                fy = cavy
                if side == "left":
                    fx = cavx; cavx += fw
                else:
                    fx = cavx + cavw
            fill = kw.get("fill", "none")
            width, height = rw, rh
            if fill in ("x", "both") or width > fw - pl - pr:
                width = fw - pl - pr
            if fill in ("y", "both") or height > fh - pt - pb:
                height = fh - pt - pb
            width, height = max(0, width), max(0, height)
            anchor = kw.get("anchor", "center")
            anchor = "" if anchor == "center" else anchor
            x = fx + pl
            y = fy + pt
            spare_x, spare_y = fw - pl - pr - width, fh - pt - pb - height
            x += spare_x if "e" in anchor else (0 if "w" in anchor else spare_x / 2)
            y += spare_y if "s" in anchor else (0 if "n" in anchor else spare_y / 2)
            self.boxes[c] = (ox + x, oy + y, width, height)
            self.arrange(c, width, height)

    def x_expansion(self, slaves, cavw):
        num_expand, min_expand = 0, cavw
        for c in slaves:
            kw = c.packed[1]
            cw = self.slave_req(c)[0] + sum(pads(kw, "padx"))
            if kw.get("side", "top") in ("top", "bottom"):
                tmp = (cavw - cw) / num_expand if num_expand else cavw
                min_expand = min(min_expand, tmp)
            else:
                cavw -= cw
                if kw.get("expand") not in (None, 0, False, "0"):
                    num_expand += 1
        if num_expand:
            min_expand = min(min_expand, cavw / num_expand)
        return max(0, min_expand if num_expand else 0)

    def y_expansion(self, slaves, cavh):
        num_expand, min_expand = 0, cavh
        for c in slaves:
            kw = c.packed[1]
            ch = self.slave_req(c)[1] + sum(pads(kw, "pady"))
            if kw.get("side", "top") in ("left", "right"):
                tmp = (cavh - ch) / num_expand if num_expand else cavh
                min_expand = min(min_expand, tmp)
            else:
                cavh -= ch
                if kw.get("expand") not in (None, 0, False, "0"):
                    num_expand += 1
        if num_expand:
            min_expand = min(min_expand, cavh / num_expand)
        return max(0, min_expand if num_expand else 0)

    # ------------------------------------------------------------------ rendering
    def render(self, w, W, H):
        W, H = max(1, int(W)), max(1, int(H))
        k = kind(w)
        bg = w._opts.get("bg", w._opts.get("background", "#202020"))
        img = Image.new("RGB", (W, H), bg if isinstance(bg, str) and bg.startswith("#") else "#202020")
        d = ImageDraw.Draw(img)
        hl = num(w._opts.get("highlightthickness", 0))
        if k in ("Frame", "Toplevel", "Tk") and hl >= 1:
            d.rectangle((0, 0, W - 1, H - 1), outline=w._opts.get("highlightbackground", "#444444"))
        if k == "Label":
            font, lh, cw = metrics(w._opts.get("font", ("x", 10, "normal")))
            lines = wrap_lines(w._opts.get("text", ""), font, num(w._opts.get("wraplength", 0)))
            anchor = w._opts.get("anchor", "center"); anchor = "" if anchor == "center" else anchor
            justify = w._opts.get("justify", "center")
            px, py = num(w._opts.get("padx", 1)) + 1, num(w._opts.get("pady", 1)) + 1
            tw = max((font.getlength(l) for l in lines), default=0)
            block_h = len(lines) * lh
            bx = px if "w" in anchor else (W - px - tw if "e" in anchor else (W - tw) / 2)
            by = py if "n" in anchor else (H - py - block_h if "s" in anchor else (H - block_h) / 2)
            for i, line in enumerate(lines):
                lw = font.getlength(line)
                lx = bx + ((tw - lw) if justify == "right" else ((tw - lw) / 2 if justify == "center" else 0))
                d.text((lx, by + i * lh), line, fill=w._opts.get("fg", w._opts.get("foreground", "#ffffff")), font=font)
        elif k == "Canvas":
            w._opts["width"], w._opts["height"] = W, H
            for fn in list(w._bindings.get("<Configure>", [])):
                try:
                    fn(types.SimpleNamespace(widget=w, width=W, height=H))
                except Exception:
                    pass
            img.paste(render_canvas(w, W, H, scale=1), (0, 0))
        elif k == "Entry":
            d.rectangle((0, 0, W - 1, H - 1), fill=w._opts.get("bg", "#333"), outline=w._opts.get("highlightbackground", "#555"))
            font, lh, cw = metrics(w._opts.get("font", ("x", 10, "normal")))
            var = w._opts.get("textvariable")
            d.text((8, (H - lh) / 2), str(var.get() if var is not None else ""), fill=w._opts.get("fg", "#fff"), font=font)
        elif k == "Combobox":
            d.rectangle((0, 0, W - 1, H - 1), fill="#2b313b", outline="#3a4352")
            font, lh, cw = metrics(w._opts.get("font", ("x", 10, "normal")))
            d.text((8, (H - lh) / 2), str(getattr(w, "_val", "")), fill="#e9edf3", font=font)
            d.polygon((W - 20, H / 2 - 3, W - 10, H / 2 - 3, W - 15, H / 2 + 3), fill="#b4bcc9")
        elif k == "Text":
            font, lh, cw = metrics(w._opts.get("font", ("x", 10, "normal")))
            d.text((6, 4), getattr(w, "content", "")[:400], fill="#e9edf3", font=font)
        for c in self.managed(w):
            if c in self.boxes:
                x, y, cw_, ch_ = self.boxes[c]
                if kind(c) == "Canvas" and any(i["type"] == "window" for i in c.items.values()):
                    inner = next(i["opts"]["window"] for i in c.items.values() if i["type"] == "window")
                    ix, iy, iw, ih = self.boxes.get(inner, (0, 0, cw_, ch_))
                    ci = Image.new("RGB", (max(1, int(cw_)), max(1, int(ch_))), c._opts.get("bg", "#111"))
                    ci.paste(self.render(inner, iw, ih), (0, 0))
                    img.paste(ci, (int(x), int(y)))
                else:
                    img.paste(self.render(c, cw_, ch_), (int(x), int(y)))
        return img


def settle_layout(sim, root, W, H, passes=4):
    """Real Tk delivers <Configure> after layout; labels react by re-wrapping, which changes the layout again."""
    def walk(w):
        yield w
        for c in sim.managed(w):
            yield from walk(c)
        if kind(w) == "Canvas":
            for it in w.items.values():
                if it["type"] == "window" and it["opts"].get("window") is not None:
                    yield from walk(it["opts"]["window"])
    for _ in range(passes):
        sim.req_cache.clear(); sim.boxes.clear()
        sim.boxes[root] = (0, 0, W, H)
        sim.arrange(root, W, H)
        changed = False
        for w in walk(root):
            if kind(w) == "Canvas" or w not in sim.boxes:
                continue
            fns = w._bindings.get("<Configure>", [])
            if not fns:
                continue
            bw, bh = sim.boxes[w][2], sim.boxes[w][3]
            before = dict(w._opts)
            for fn in list(fns):
                try:
                    fn(types.SimpleNamespace(widget=w, width=int(bw), height=int(bh)))
                except Exception:
                    pass
            changed = changed or before != w._opts
        if not changed:
            break
    sim.req_cache.clear(); sim.boxes.clear()
    sim.boxes[root] = (0, 0, W, H)
    sim.arrange(root, W, H)


def render_window(app, W=1100, H=780, scale_out=1.0):
    """The whole main window as the user would see it at W x H."""
    sim = Sim()
    root = app.root
    root._opts.setdefault("bg", "#1b1f26")
    settle_layout(sim, root, W, H)
    return sim.render(root, W, H), sim


def render_page_full(app, key, content_w):
    """One page's whole content (not clipped by the scroll viewport) at a given content width."""
    app.show_page(key)
    page = app.pages[key]
    sim = Sim()
    body = page.body
    h = sim.req(body)[1]
    settle_layout(sim, body, content_w, h)
    h = sim.req(body)[1]
    sim.boxes[body] = (0, 0, content_w, h)
    sim.arrange(body, content_w, h)
    return sim.render(body, content_w, h), sim
