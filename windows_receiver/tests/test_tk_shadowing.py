"""Static check: no widget subclass may define an attribute or method that shadows tkinter's own.

Real incident (v0.9.0): SpectrumView stored its pixel width in `self._w`, which is the widget's Tcl path name, so the first
canvas call failed with  _tkinter.TclError: invalid command name "1".  A permissive fake Tk cannot reveal that, so this
test lists tkinter's reserved names and scans our widget classes with the AST.
"""
import ast
import os

import _path  # noqa: F401

# Instance state tkinter itself keeps on every widget - overwriting any of these breaks the widget.
STATE = {"_w", "_name", "master", "children", "tk", "widgetName", "_tclCommands", "_last_child_ids", "_windowingsystem_cached",
         "_root", "_setup", "_options", "_register", "_bind", "_configure", "_substitute", "_nametowidget", "_displayof",
         "_getints", "_getdoubles", "_getboolean", "_report_exception", "_grid_configure", "_gridconvvalue", "_getconfigure",
         "_getconfigure1", "_noarg_", "_subst_format", "_subst_format_str", "_windowingsystem"}

# Public methods of Misc / Pack / Grid / Place / Wm / Canvas / Entry / Text / ttk widgets that a subclass must not redefine by accident.
METHODS = {
    "destroy", "deletecommand", "wait_variable", "waitvar", "wait_window", "wait_visibility", "setvar", "getvar", "getint",
    "getdouble", "getboolean", "focus_set", "focus", "focus_force", "focus_get", "focus_displayof", "focus_lastfor", "after",
    "after_idle", "after_cancel", "bell", "clipboard_get", "clipboard_clear", "clipboard_append", "grab_current",
    "grab_release", "grab_set", "grab_set_global", "grab_status", "option_add", "option_clear", "option_get",
    "option_readfile", "selection_clear", "selection_get", "selection_handle", "selection_own", "selection_own_get", "send",
    "lower", "tkraise", "lift", "update", "update_idletasks", "bindtags", "bind", "unbind", "bind_all", "unbind_all",
    "bind_class", "unbind_class", "mainloop", "quit", "nametowidget", "register", "configure", "config", "cget", "keys",
    "pack_propagate", "propagate", "pack_slaves", "slaves", "place_slaves", "grid_anchor", "anchor", "grid_bbox", "bbox",
    "grid_columnconfigure", "columnconfigure", "grid_location", "grid_propagate", "grid_rowconfigure", "rowconfigure",
    "grid_size", "size", "grid_slaves", "event_add", "event_delete", "event_generate", "event_info", "image_names",
    "image_types", "pack", "pack_configure", "pack_forget", "forget", "pack_info", "info", "place", "place_configure",
    "place_forget", "place_info", "grid", "grid_configure", "grid_forget", "grid_remove", "grid_info", "location",
    "title", "geometry", "state", "iconify", "deiconify", "withdraw", "transient", "resizable", "protocol", "attributes",
    "minsize", "maxsize", "overrideredirect", "iconbitmap", "iconphoto", "wm_title", "wm_geometry",
    # Canvas
    "addtag", "addtag_above", "addtag_all", "addtag_below", "addtag_closest", "addtag_enclosed", "addtag_overlapping",
    "addtag_withtag", "tag_bind", "tag_unbind", "canvasx", "canvasy", "coords", "create_arc", "create_bitmap",
    "create_image", "create_line", "create_oval", "create_polygon", "create_rectangle", "create_text", "create_window",
    "dchars", "delete", "dtag", "find", "find_above", "find_all", "find_below", "find_closest", "find_enclosed",
    "find_overlapping", "find_withtag", "gettags", "icursor", "index", "insert", "itemcget", "itemconfigure", "itemconfig",
    "tag_lower", "tag_raise", "move", "moveto", "postscript", "scale", "scan_mark", "scan_dragto", "select_adjust",
    "select_clear", "select_from", "select_item", "select_to", "type", "xview", "xview_moveto", "xview_scroll", "yview",
    "yview_moveto", "yview_scroll",
    # Entry / Text / ttk
    "selection_adjust", "selection_from", "selection_present", "selection_range", "selection_to", "select_present",
    "select_range", "get", "see", "tag_configure", "tag_add", "tag_remove", "tag_delete", "mark_set", "window_create",
    "current", "instate", "identify", "validate",
}
# `set`/`get`/`value` style helper names are fine on Canvas/Frame/Label subclasses, but NOT on classes whose Tk base defines them.
BASES_WITH_GET_SET = {"Combo": {"get", "set", "current"}, "Scrollbar": {"get", "set"}}


def _classes():
    base = os.path.join(_path.ROOT, "phonemic")
    for fn in ("widgets.py", "gui.py", "pages.py"):
        tree = ast.parse(open(os.path.join(base, fn), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases]
                if any(b.startswith(("tk.", "ttk.")) or b == "Page" for b in bases):
                    yield fn, node, bases


def _own_names(node):
    names = {}
    for n in node.body:                                         # methods + class attributes
        if isinstance(n, ast.FunctionDef) and n.name != "__init__":
            names[n.name] = n.lineno
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names[t.id] = n.lineno
    for n in ast.walk(node):                                    # self.x = ...
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store) and isinstance(n.value, ast.Name) and n.value.id == "self":
            names.setdefault(n.attr, n.lineno)
    return names


def test_no_widget_shadows_tkinter_internals():
    bad = []
    for fn, node, bases in _classes():
        for name, line in _own_names(node).items():
            reserved = name in STATE or name in METHODS
            # Combo/ttk bases legitimately keep get/set; our own Canvas/Frame helpers named set/get/config are fine
            if name in ("set", "get") and not any("Combobox" in b for b in bases):
                reserved = False
            if node.name in ("Page",) or any(b == "Page" for b in bases):
                if name in ("build", "on_show", "refresh_fast", "refresh_slow"):
                    reserved = False
            if reserved:
                bad.append(f"{fn}:{line} {node.name}({', '.join(bases)}) shadows tkinter name '{name}'")
    assert not bad, "\n" + "\n".join(bad)


if __name__ == "__main__":
    test_no_widget_shadows_tkinter_internals()
    print("PASS test_no_widget_shadows_tkinter_internals")
