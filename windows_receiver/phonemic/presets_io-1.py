"""Preset files: export, import and validation. Pure functions, no GUI.

A preset file is JSON:  {"format": "phonemic-preset", "version": 1, "kind": "fx" | "voice", "name": ..., "params": {...}}
A bundle holds many:    {"format": "phonemic-preset", "version": 1, "kind": "bundle", "fx": {name: params}, "voice": {...}}
Everything read from a file is treated as untrusted: unknown keys are dropped, values are clamped, names are cleaned.
"""
import json
import re

from . import dsp
from .const import VERSION

FORMAT = "phonemic-preset"
FILE_VERSION = 1
MAX_BYTES = 512 * 1024
MAX_PRESETS = 200
MAX_NAME = 60


class PresetError(ValueError):
    """Raised with a message that is safe to show to the user."""


def clean_name(name, fallback="Imported preset"):
    name = re.sub(r"[\x00-\x1f\x7f]", " ", str(name or ""))
    name = re.sub(r"\s+", " ", name).strip()[:MAX_NAME].strip()
    return name or fallback


def unique_name(name, taken):
    """`name`, or `name (2)`, `name (3)` ... so an import never overwrites anything."""
    name = clean_name(name)
    if name not in taken:
        return name
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"


# ---- export ----------------------------------------------------------------------------------------------------------
def export_preset(kind, name, params):
    clean = dsp.sanitize_fx(params) if kind == "fx" else dsp.sanitize_voice(params)
    return {"format": FORMAT, "version": FILE_VERSION, "kind": kind, "name": clean_name(name, "Preset"), "app": VERSION,
            "params": clean}


def export_bundle(fx_presets, voice_presets):
    return {"format": FORMAT, "version": FILE_VERSION, "kind": "bundle", "app": VERSION,
            "fx": {clean_name(n): dsp.sanitize_fx(p) for n, p in fx_presets.items()},
            "voice": {clean_name(n): dsp.sanitize_voice(p) for n, p in voice_presets.items()}}


def dumps(obj):
    return json.dumps(obj, indent=2, sort_keys=False)


# ---- import ----------------------------------------------------------------------------------------------------------
def _one(kind, name, params):
    if not isinstance(params, dict):
        raise PresetError("The preset has no settings in it.")
    if kind == "fx":
        clean = dsp.sanitize_fx(params)
    elif kind == "voice":
        clean = dsp.sanitize_voice(params)
    else:
        raise PresetError(f"Unknown preset type \"{str(kind)[:20]}\".")
    if not clean:
        raise PresetError("None of the settings in this preset are recognised. It may come from a different program.")
    return kind, clean_name(name), clean


def parse(text):
    """-> list of (kind, name, params). Raises PresetError for anything that is not a usable preset file."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    if len(text) > MAX_BYTES:
        raise PresetError("This file is too large to be a preset.")
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        raise PresetError("This file is not a valid preset (it could not be read as JSON).") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise PresetError("This is not a PhoneMic preset file.")
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version > FILE_VERSION:
        raise PresetError("This preset was made by a newer version of the app. Update the receiver to open it.")
    kind = data.get("kind")
    if kind == "bundle":
        items = []
        for sub in ("fx", "voice"):
            group = data.get(sub, {})
            if not isinstance(group, dict):
                raise PresetError("The preset bundle is damaged.")
            for name, params in list(group.items())[:MAX_PRESETS]:
                try:
                    items.append(_one(sub, name, params))
                except PresetError:
                    continue                                    # skip unusable entries, keep the rest
        if not items:
            raise PresetError("The bundle does not contain any usable presets.")
        return items
    return [_one(kind, data.get("name"), data.get("params"))]


def import_items(user_fx, user_voice, items):
    """Adds items to the two user-preset dicts without overwriting. Returns [(kind, final_name), ...]."""
    added = []
    for kind, name, params in items:
        target = user_fx if kind == "fx" else user_voice
        builtin = dsp.FX_BUILTIN_PRESETS if kind == "fx" else dsp.VoiceChanger.BUILTIN_PRESETS
        final = unique_name(name, set(target) | set(builtin))
        target[final] = params
        added.append((kind, final))
    return added
