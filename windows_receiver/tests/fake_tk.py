"""Headless stand-in for tkinter (no Tk in the sandbox): enough surface to construct and exercise the whole GUI,
plus a canvas recorder that can be rendered with PIL to eyeball the custom-drawn widgets."""
import sys
import types
import itertools

_ids = itertools.count(1)


class TclError(Exception):
    pass


# ---- the checks below mirror real Tk behaviour that a permissive fake would hide ---------------------------------
PROTECTED = {"_w", "master", "children", "tk", "_name", "widgetName", "_tclCommands"}   # tkinter's own instance state

_ALIASES = {"bg": "background", "fg": "foreground", "bd": "borderwidth"}
_COMMON = {"background", "bg", "borderwidth", "bd", "cursor", "highlightbackground", "highlightcolor", "highlightthickness",
           "relief", "takefocus", "width", "height"}
VALID = {
    "Frame": _COMMON | {"padx", "pady", "class", "container", "colormap", "visual"},
    "Toplevel": _COMMON | {"padx", "pady", "class", "container", "colormap", "visual", "menu", "screen", "use"},
    "Label": _COMMON | {"activebackground", "activeforeground", "anchor", "bitmap", "compound", "disabledforeground", "fg",
                        "font", "foreground", "image", "justify", "padx", "pady", "state", "text", "textvariable",
                        "underline", "wraplength"},
    "Entry": _COMMON | {"disabledbackground", "disabledforeground", "exportselection", "fg", "font", "foreground",
                        "insertbackground", "insertborderwidth", "insertofftime", "insertontime", "insertwidth",
                        "invalidcommand", "justify", "readonlybackground", "selectbackground", "selectborderwidth",
                        "selectforeground", "show", "state", "textvariable", "validate", "validatecommand",
                        "xscrollcommand"},
    "Text": _COMMON | {"autoseparators", "blockcursor", "endline", "exportselection", "fg", "font", "foreground",
                       "inactiveselectbackground", "insertbackground", "insertborderwidth", "insertofftime",
                       "insertontime", "insertunfocussed", "insertwidth", "maxundo", "padx", "pady", "selectbackground",
                       "selectborderwidth", "selectforeground", "setgrid", "spacing1", "spacing2", "spacing3", "startline",
                       "state", "tabs", "tabstyle", "undo", "wrap", "xscrollcommand", "yscrollcommand"},
    "Canvas": _COMMON | {"closeenough", "confine", "insertbackground", "insertborderwidth", "insertofftime",
                         "insertontime", "insertwidth", "offset", "scrollregion", "selectbackground",
                         "selectborderwidth", "selectforeground", "state", "xscrollcommand", "xscrollincrement",
                         "yscrollcommand", "yscrollincrement"},
    "Scrollbar": {"class", "command", "cursor", "orient", "style", "takefocus"},            # ttk
    "Combobox": {"class", "cursor", "exportselection", "font", "foreground", "height", "invalidcommand", "justify",
                 "postcommand", "show", "state", "style", "takefocus", "textvariable", "validate", "validatecommand",
                 "values", "width", "xscrollcommand"},
}
_ITEM_COMMON = {"state", "tags", "dash", "dashoffset", "activedash", "disableddash"}
ITEM_VALID = {
    "line": _ITEM_COMMON | {"arrow", "arrowshape", "capstyle", "fill", "joinstyle", "offset", "smooth", "splinesteps", "stipple", "width"},
    "rect": _ITEM_COMMON | {"fill", "offset", "outline", "outlineoffset", "outlinestipple", "stipple", "width"},
    "oval": _ITEM_COMMON | {"fill", "offset", "outline", "outlineoffset", "outlinestipple", "stipple", "width"},
    "polygon": _ITEM_COMMON | {"fill", "joinstyle", "offset", "outline", "outlineoffset", "outlinestipple", "smooth",
                               "splinesteps", "stipple", "width"},
    "arc": _ITEM_COMMON | {"extent", "fill", "offset", "outline", "outlineoffset", "outlinestipple", "start", "stipple",
                           "style", "width"},
    "text": {"anchor", "angle", "fill", "font", "justify", "offset", "state", "stipple", "tags", "text", "width"},
    "window": {"anchor", "height", "state", "tags", "width", "window"},
}
_ENUMS = {("line", "capstyle"): {"butt", "projecting", "round"}, ("arc", "style"): {"pieslice", "chord", "arc"},
          ("text", "anchor"): {"n", "ne", "e", "se", "s", "sw", "w", "nw", "center"}}
_COLOR_OPTS = {"background", "bg", "foreground", "fg", "highlightbackground", "highlightcolor", "insertbackground",
               "selectbackground", "selectforeground", "activebackground", "activeforeground", "disabledforeground",
               "disabledbackground", "readonlybackground"}
_PACK = {"after", "anchor", "before", "expand", "fill", "side", "in", "in_", "ipadx", "ipady", "padx", "pady"}
_GRID = {"column", "columnspan", "in", "in_", "ipadx", "ipady", "padx", "pady", "row", "rowspan", "sticky"}
_NAMED = {"white", "black", "red", "green", "blue", "gray", "grey", "SystemButtonFace"}


def _check_color(opt, v, allow_empty=False):
    if v == "" and allow_empty:
        return
    if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7, 10, 13) and all(c in "0123456789abcdefABCDEF" for c in v[1:]):
        return
    if v in _NAMED:
        return
    raise TclError(f'unknown color name "{v}" (option -{opt})')


def _check_number(what, v):
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise TclError(f'bad screen distance "{v}" for {what}')


def _check_pad(what, v):
    if isinstance(v, (tuple, list)):
        if len(v) != 2:
            raise TclError(f"bad pad value for {what}")
        for x in v:
            _check_number(what, x)
    else:
        _check_number(what, v)
LOG = []          # (widget class, option) pairs that were configured with unknown-looking options (diagnostics)


class Misc:
    _kind = None

    def __setattr__(self, name, value):
        if name in PROTECTED and self.__dict__.get("_pm_init"):
            raise TclError(f"attribute '{name}' collides with tkinter's own widget state - rename it "
                           f"(real Tk would fail later with: invalid command name \"{value}\")")
        object.__setattr__(self, name, value)

    def _validate(self, kw):
        kind = self._kind or type(self).__mro__[0].__name__
        for cls in type(self).__mro__:
            if cls.__name__ in VALID:
                kind = cls.__name__
                break
        valid = VALID.get(kind)
        if valid is None:
            return
        for k, v in kw.items():
            if k not in valid:
                raise TclError(f'unknown option "-{k}" for {kind}')
            if k in _COLOR_OPTS:
                _check_color(k, v)
            if k in ("padx", "pady") and kind != "Frame":
                _check_number(k, v)
            if k in ("width", "height", "borderwidth", "bd", "highlightthickness"):
                _check_number(k, v)

    def __init__(self, master=None, **kw):
        self._w = f".w{next(_ids)}"
        self.master = master
        self.children = []
        self._mgr = {"pack": set(), "grid": set()}
        self._validate(kw)
        self._opts = dict(kw)
        self._bindings = {}
        self._after = {}
        self.destroyed = False
        self.packed = None
        if master is not None and hasattr(master, "children"):
            master.children.append(self)
        self._pm_init = True

    # options
    def cget(self, k):
        return self._opts.get(k, "")

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        if kw:
            self._validate(kw)
            self._opts.update(kw)
        return None

    config = configure

    def __getitem__(self, k):
        return self._opts.get(k)

    def __setitem__(self, k, v):
        self._opts[k] = v

    # geometry managers
    def _manage(self, how, kw, allowed):
        for k in kw:
            if k not in allowed:
                raise TclError(f'bad option "-{k}" for {how}')
        for k in ("padx", "pady"):
            if k in kw:
                _check_pad(k, kw[k])
        m = self.master
        if m is not None:
            other = "grid" if how == "pack" else "pack"
            if m._mgr[other]:
                raise TclError(f"cannot use geometry manager {how} inside {m._w} which already has slaves managed by {other}")
            m._mgr[how].add(self)
        self.packed = (how, kw)

    def pack(self, **kw):
        self._manage("pack", kw, _PACK)

    def grid(self, **kw):
        self._manage("grid", kw, _GRID)

    def place(self, **kw):
        self.packed = ("place", kw)

    def pack_forget(self):
        if self.master is not None:
            self.master._mgr["pack"].discard(self)
            self.master._mgr["grid"].discard(self)
        self.packed = None

    grid_forget = pack_forget

    def pack_propagate(self, flag=None):
        if flag is not None:
            self._pack_prop = bool(flag)

    grid_propagate = pack_propagate

    def grid_columnconfigure(self, index, **kw):
        self.__dict__.setdefault("_colcfg", {}).setdefault(index, {}).update(kw)

    def grid_rowconfigure(self, index, **kw):
        self.__dict__.setdefault("_rowcfg", {}).setdefault(index, {}).update(kw)

    # events / scheduling
    def bind(self, seq, fn=None, add=None):
        if fn is not None:
            self._bindings.setdefault(seq, []).append(fn) if add else self._bindings.__setitem__(seq, [fn])
        return ""

    def unbind(self, seq, funcid=None):
        self._bindings.pop(seq, None)

    bind_all = bind
    unbind_all = unbind
    bind_class = bind

    def event_generate(self, seq, **kw):
        for fn in self._bindings.get(seq, []):
            fn(types.SimpleNamespace(widget=self, x=5, y=5, delta=120, width=self.winfo_width(), height=self.winfo_height()))

    def after(self, ms, fn=None, *args):
        i = f"after#{next(_ids)}"
        self._after[i] = (ms, fn, args)
        return i

    def after_cancel(self, i):
        self._after.pop(i, None)

    # window info
    def winfo_width(self):
        w = self._opts.get("width")
        return int(w) if isinstance(w, (int, float)) and w > 1 else 600

    def winfo_height(self):
        h = self._opts.get("height")
        return int(h) if isinstance(h, (int, float)) and h > 1 else 40

    def winfo_reqheight(self):
        return 900

    def winfo_reqwidth(self):
        return 300

    def winfo_x(self):
        return 0

    def winfo_y(self):
        return 0

    def winfo_rootx(self):
        return 100

    def winfo_rooty(self):
        return 100

    def winfo_children(self):
        return list(self.children)

    def winfo_fpixels(self, s):
        return 96.0

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def winfo_geometry(self):
        return "1020x740+120+80"

    def winfo_exists(self):
        return not self.destroyed

    def focus_set(self):
        pass

    def focus_get(self):
        return None

    def update_idletasks(self):
        pass

    def update(self):
        pass

    def destroy(self):
        self.pack_forget()
        self.destroyed = True
        for c in list(self.children):
            c.destroy()
        if self.master is not None and self in getattr(self.master, "children", []):
            self.master.children.remove(self)

    def selection_clear(self, *a):
        pass

    def clipboard_clear(self):
        self._clip = ""

    def clipboard_append(self, s):
        self._clip = getattr(self, "_clip", "") + s


class Tk(Misc):
    def __init__(self, *a, **k):
        super().__init__(None)
        self._state = "normal"

    def title(self, t=None):
        self._title = t

    def geometry(self, g=None):
        self._geo = g

    def minsize(self, *a):
        pass

    def resizable(self, *a):
        pass

    def protocol(self, name, fn):
        self._protocols = getattr(self, "_protocols", {})
        self._protocols[name] = fn

    def iconify(self):
        self._state = "iconic"

    def withdraw(self):
        self._state = "withdrawn"

    def deiconify(self):
        self._state = "normal"

    def lift(self, *a):
        pass

    def focus_force(self):
        pass

    def state(self, s=None):
        if s:
            self._state = s
        return self._state

    def attributes(self, *a):
        pass

    def option_add(self, *a):
        pass

    def iconphoto(self, *a):
        pass

    def wait_window(self, w):
        pass

    def mainloop(self):
        pass

    def transient(self, *a):
        pass

    def grab_set(self):
        pass

    def wm_overrideredirect(self, f):
        pass

    def wm_geometry(self, g):
        pass


class Toplevel(Tk):
    def __init__(self, master=None, **kw):
        Misc.__init__(self, master, **kw)
        self._state = "normal"


class Frame(Misc):
    pass


class Label(Misc):
    pass


class Entry(Misc):
    def select_range(self, *a):
        pass

    def insert(self, *a):
        pass

    def delete(self, *a):
        pass


class Scrollbar(Misc):
    def set(self, *a):
        pass


class TtkScrollbar(Scrollbar):
    pass


class Text(Misc):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.content = ""

    def insert(self, idx, s, *tags):
        self.content += s

    def delete(self, a, b=None):
        self.content = ""

    def see(self, i):
        pass

    def yview(self):
        return (0.0, 1.0)

    def tag_configure(self, *a, **k):
        pass


class Canvas(Misc):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.items = {}
        self.order = []

    def _add(self, kind, args, kw):
        flat = []
        for a in args:                               # real tkinter flattens tuple/list coordinates
            flat.extend(a) if isinstance(a, (tuple, list)) else flat.append(a)
        args = tuple(flat)
        valid = ITEM_VALID[kind]
        for k, v in kw.items():
            if k not in valid:
                raise TclError(f'unknown option "-{k}" for canvas item "{kind}"')
            if k in ("fill", "outline"):
                _check_color(k, v, allow_empty=True)
            if (kind, k) in _ENUMS and v not in _ENUMS[(kind, k)]:
                raise TclError(f'bad {k} "{v}" for {kind}')
        if kind in ("line", "polygon") and len([a for a in args if isinstance(a, (int, float))]) < 4:
            raise TclError("wrong # coordinates")
        for a in args:
            if not isinstance(a, (int, float, str)) or isinstance(a, bool):
                raise TclError(f'bad coordinate "{a}"')
        i = next(_ids)
        coords = [a for a in args if isinstance(a, (int, float))]
        self.items[i] = {"type": kind, "coords": list(coords), "opts": dict(kw)}
        self.order.append(i)
        return i

    def create_line(self, *a, **k):
        return self._add("line", a, k)

    def create_rectangle(self, *a, **k):
        return self._add("rect", a, k)

    def create_oval(self, *a, **k):
        return self._add("oval", a, k)

    def create_arc(self, *a, **k):
        return self._add("arc", a, k)

    def create_polygon(self, *a, **k):
        return self._add("polygon", a, k)

    def create_text(self, *a, **k):
        return self._add("text", a, k)

    def create_window(self, *a, **k):
        return self._add("window", a, k)

    def delete(self, tag):
        if tag == "all":
            self.items.clear()
            self.order.clear()
        else:
            self.items.pop(tag, None)
            if tag in self.order:
                self.order.remove(tag)

    def coords(self, i, *new):
        if new:
            if len(new) == 1 and isinstance(new[0], (list, tuple)):
                new = new[0]
            self.items[i]["coords"] = list(new)
        return self.items[i]["coords"]

    def itemconfigure(self, i, **kw):
        if i in self.items:
            valid = ITEM_VALID[self.items[i]["type"]]
            for k, v in kw.items():
                if k not in valid:
                    raise TclError(f'unknown option "-{k}"')
                if k in ("fill", "outline"):
                    _check_color(k, v, allow_empty=True)
            self.items[i]["opts"].update(kw)

    itemconfig = itemconfigure

    def bbox(self, *a):
        return (0, 0, 600, 900)

    def yview(self, *a):
        return (0.0, 1.0)

    def yview_scroll(self, *a):
        pass


class _Var:
    def __init__(self, master=None, value=None):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v

    def trace_add(self, *a):
        pass


class StringVar(_Var):
    pass


class IntVar(_Var):
    pass


class BooleanVar(_Var):
    pass


class DoubleVar(_Var):
    pass


class PhotoImage:
    def __init__(self, *a, **k):
        pass


# ---------------------------------------------------------------------------------- ttk
class Style:
    def __init__(self, *a):
        pass

    def theme_use(self, *a):
        pass

    def configure(self, *a, **k):
        pass

    def map(self, *a, **k):
        pass


class Combobox(Misc):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._val = ""

    def get(self):
        return self._val

    def set(self, v):
        self._val = v

    def current(self, *a):
        return 0


def install():
    tk = types.ModuleType("tkinter")
    for name in ("Tk", "Toplevel", "Frame", "Label", "Entry", "Scrollbar", "Text", "Canvas", "StringVar", "IntVar",
                 "BooleanVar", "DoubleVar", "PhotoImage"):
        setattr(tk, name, globals()[name])
    ttk = types.ModuleType("tkinter.ttk")
    ttk.Style, ttk.Combobox, ttk.Scrollbar = Style, Combobox, TtkScrollbar
    fd = types.ModuleType("tkinter.filedialog")
    fd.askdirectory = lambda **k: ""
    fd.asksaveasfilename = lambda **k: ""
    fd.askopenfilename = lambda **k: ""
    fd.askopenfilenames = lambda **k: ()
    mb = types.ModuleType("tkinter.messagebox")
    mb.askyesno = lambda *a, **k: True
    mb.showinfo = lambda *a, **k: None
    mb.showerror = lambda *a, **k: None
    tk.TclError = TclError
    tk.ttk, tk.filedialog, tk.messagebox = ttk, fd, mb
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.filedialog": fd, "tkinter.messagebox": mb})
    return tk


# ---------------------------------------------------------------------------------- PIL renderer
def render_canvas(canvas, width=None, height=None, scale=2, bg=None):
    from PIL import Image, ImageDraw, ImageFont
    w = width or canvas.winfo_width()
    h = height or canvas.winfo_height()
    S = scale
    img = Image.new("RGB", (w * S, h * S), bg or canvas._opts.get("bg", "#000000"))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9 * S)
    except Exception:
        f = ImageFont.load_default()

    def col(v, default=None):
        return v if v not in ("", None) else default

    for i in canvas.order:
        it = canvas.items.get(i)
        if not it:
            continue
        t, c, o = it["type"], [v * S for v in it["coords"]], it["opts"]
        if t == "rect" and len(c) >= 4:
            d.rectangle(c[:4], fill=col(o.get("fill")), outline=col(o.get("outline")))
        elif t == "oval" and len(c) >= 4:
            d.ellipse(c[:4], fill=col(o.get("fill")), outline=col(o.get("outline")), width=int(o.get("width", 1) * S) if o.get("outline") else 0)
        elif t == "line" and len(c) >= 4:
            wd = int(float(o.get("width", 1)) * S)
            d.line(c, fill=col(o.get("fill"), "#ffffff"), width=max(1, wd), joint="curve")
            if o.get("capstyle") == "round":
                r = wd / 2
                for x, y in ((c[0], c[1]), (c[-2], c[-1])):
                    d.ellipse((x - r, y - r, x + r, y + r), fill=col(o.get("fill"), "#ffffff"))
        elif t == "polygon" and len(c) >= 6:
            d.polygon(c, fill=col(o.get("fill")), outline=col(o.get("outline")))
        elif t == "arc" and len(c) >= 4:
            d.arc(c[:4], start=-(float(o.get("start", 0)) + float(o.get("extent", 90))), end=-float(o.get("start", 0)),
                  fill=col(o.get("outline"), "#ffffff"), width=int(float(o.get("width", 1)) * S))
        elif t == "text" and len(c) >= 2:
            anchor = o.get("anchor", "center")
            txt = str(o.get("text", ""))
            bb = d.textbbox((0, 0), txt, font=f)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            x, y = c[0], c[1]
            if "n" in anchor:
                pass
            elif "s" in anchor:
                y -= th
            else:
                y -= th / 2
            if "w" in anchor:
                pass
            elif "e" in anchor:
                x -= tw
            else:
                x -= tw / 2
            d.text((x, y), txt, fill=col(o.get("fill"), "#ffffff"), font=f)
    return img
