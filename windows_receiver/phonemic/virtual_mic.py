"""Cross-platform virtual microphone helpers.

On Linux (Arch Linux / PipeWire / PulseAudio), manages a dedicated virtual sink (`PhoneMic_Sink`)
and virtual microphone source (`PhoneMic_Virtual_Mic`) using standard `pactl` modules so Discord,
OBS Studio, Firefox, and Chromium see a real input device while cues keep playing on real speakers.
On Windows, reports VB-CABLE detection consistently through the same VirtualMicStatus facade.
"""
import os
import re
import sys
import time
import shutil
import threading
import subprocess
from dataclasses import dataclass

from .const import CABLE_HINT

IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")

SINK_NAME = "PhoneMic_Sink"
SINK_DESC = "PhoneMic_Sink"
SOURCE_NAME = "PhoneMic_Virtual_Mic"
SOURCE_DESC = "PhoneMic_Virtual_Mic"
FRIENDLY_DEVICE_LABEL = "PhoneMic Virtual Mic (PipeWire/Pulse)"

_LOCK = threading.Lock()
_SESSION_MODULES = []


@dataclass(frozen=True)
class VirtualMicStatus:
    supported: bool
    backend: str
    active: bool
    sink_name: str = ""
    source_name: str = ""
    detail: str = ""


@dataclass(frozen=True)
class PulseSink:
    name: str
    description: str
    is_default: bool = False
    is_virtual: bool = False


def pactl_available():
    return IS_LINUX and bool(shutil.which("pactl"))


def mixer_command():
    """Return the first installed Linux graphical audio mixer/patchbay tool or empty list."""
    if not IS_LINUX:
        return []
    for cmd in ("pavucontrol", "pavucontrol-qt"):
        path = shutil.which(cmd)
        if path:
            return [path]
    return []


def patchbay_command():
    """Return a graphical PipeWire/JACK patchbay if installed."""
    if not IS_LINUX:
        return []
    for cmd in ("qpwgraph", "helvum", "carla", "catia"):
        path = shutil.which(cmd)
        if path:
            return [path]
    return []


def _clean_env():
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def _run_pactl(*args, timeout=3.0):
    exe = shutil.which("pactl")
    if not exe:
        return None
    try:
        return subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_clean_env(),
            timeout=timeout,
        )
    except Exception:
        return None


# ==============================================================================
# PURE PARSERS (unit-tested offline without requiring a running audio daemon)
# ==============================================================================
def parse_pactl_info(text):
    """Identify audio server backend and default sink from `pactl info` output."""
    backend = ""
    default_sink = ""
    for line in (text or "").splitlines():
        low = line.lower()
        if low.startswith("server name:"):
            val = line.split(":", 1)[1].strip()
            if "pipewire" in val.lower():
                backend = "PipeWire"
            elif "pulseaudio" in val.lower():
                backend = "PulseAudio"
            elif val:
                backend = val
        elif low.startswith("default sink:"):
            default_sink = line.split(":", 1)[1].strip()
    return backend, default_sink


def parse_pactl_sinks(text, default_sink=""):
    """Parse `LC_ALL=C pactl list sinks` into PulseSink objects."""
    sinks = []
    cur_name = ""
    cur_desc = ""
    cur_driver = ""

    def flush():
        if not cur_name:
            return
        desc = cur_desc or cur_name
        low_n = cur_name.lower()
        low_d = desc.lower()
        is_virt = (
            cur_name == SINK_NAME
            or "phonemic" in low_n
            or "module-null-sink" in cur_driver.lower()
            or "null" in cur_driver.lower()
            or "virtual" in low_d
        )
        sinks.append(
            PulseSink(
                name=cur_name,
                description=desc,
                is_default=(bool(default_sink) and cur_name == default_sink),
                is_virtual=is_virt,
            )
        )

    for raw in (text or "").splitlines():
        s = raw.strip()
        if s.startswith("Sink #"):
            flush()
            cur_name, cur_desc, cur_driver = "", "", ""
            continue
        if s.startswith("Name:"):
            cur_name = s.split(":", 1)[1].strip()
        elif s.startswith("Description:"):
            cur_desc = s.split(":", 1)[1].strip()
        elif s.startswith("Driver:"):
            cur_driver = s.split(":", 1)[1].strip()
    flush()
    return sinks


def parse_pactl_sources_short(text):
    """Extract source names from `pactl list sources short`."""
    names = set()
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            names.add(parts[1].strip())
    return names


def parse_pactl_modules_short(text):
    """Parse `pactl list modules short` into `(module_id, module_name, args)` tuples."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            parts = line.split(None, 2)
        if len(parts) >= 2:
            mid = parts[0].strip()
            mname = parts[1].strip()
            margs = parts[2].strip() if len(parts) >= 3 else ""
            if mid.isdigit():
                out.append((mid, mname, margs))
    return out


# ==============================================================================
# LIVE QUERIES & LIFECYCLE
# ==============================================================================
def server_info():
    """Return `(backend, default_sink)` or `("", "")` when daemon is unreachable."""
    if not pactl_available():
        return "", ""
    p = _run_pactl("info")
    if not p or p.returncode != 0:
        return "", ""
    backend, default_sink = parse_pactl_info(p.stdout)
    p_def = _run_pactl("get-default-sink")
    if p_def and p_def.returncode == 0 and p_def.stdout.strip():
        default_sink = p_def.stdout.strip().splitlines()[0].strip()
    return backend or "PulseAudio", default_sink


def list_sinks():
    if not pactl_available():
        return []
    backend, default_sink = server_info()
    if not backend:
        return []
    p = _run_pactl("list", "sinks")
    if not p or p.returncode != 0:
        return []
    return parse_pactl_sinks(p.stdout, default_sink=default_sink)


def list_sources_short():
    if not pactl_available():
        return set()
    p = _run_pactl("list", "sources", "short")
    if not p or p.returncode != 0:
        return set()
    return parse_pactl_sources_short(p.stdout)


def status(devs=None):
    """Inspect current virtual microphone readiness for either Windows or Linux."""
    if IS_WIN:
        has_cable = bool(devs and any(getattr(d, "is_cable", False) for d in devs))
        return VirtualMicStatus(
            supported=True,
            backend="VB-CABLE",
            active=has_cable,
            sink_name=CABLE_HINT if has_cable else "",
            source_name="CABLE Output (VB-Audio Virtual Cable)" if has_cable else "",
            detail=(
                "VB-CABLE active. Select CABLE Output in Discord, OBS, or Zoom."
                if has_cable
                else f"No VB-CABLE found. Install free VB-CABLE and pick \"{CABLE_HINT}\"."
            ),
        )
    if not IS_LINUX:
        return VirtualMicStatus(
            supported=False,
            backend="Unavailable",
            active=False,
            detail="Automatic virtual mic management requires Linux PipeWire/PulseAudio or Windows VB-CABLE.",
        )
    if not pactl_available():
        return VirtualMicStatus(
            supported=False,
            backend="Unavailable",
            active=False,
            detail="`pactl` not found. Install pipewire-pulse (or pulseaudio) to create virtual microphones.",
        )
    backend, _ = server_info()
    if not backend:
        return VirtualMicStatus(
            supported=False,
            backend="Unavailable",
            active=False,
            detail="PipeWire / PulseAudio user daemon is not responding.",
        )
    sinks = {s.name: s for s in list_sinks()}
    sources = list_sources_short()
    sink_ok = SINK_NAME in sinks
    source_ok = SOURCE_NAME in sources
    if sink_ok and source_ok:
        return VirtualMicStatus(
            supported=True,
            backend=backend,
            active=True,
            sink_name=SINK_NAME,
            source_name=SOURCE_NAME,
            detail=f"{backend} virtual mic active. Choose \"{SOURCE_NAME}\" as microphone in Discord, OBS, or browsers.",
        )
    if sink_ok and not source_ok:
        return VirtualMicStatus(
            supported=True,
            backend=backend,
            active=False,
            sink_name=SINK_NAME,
            source_name="",
            detail=f"{backend} sink exists without remap source. Click Create Virtual Mic to repair.",
        )
    return VirtualMicStatus(
        supported=True,
        backend=backend,
        active=False,
        detail=f"{backend} ready. Click Create Virtual Mic (or enable auto-create) to route to Discord/OBS.",
    )


def has_session_modules():
    with _LOCK:
        return bool(_SESSION_MODULES)


def create_virtual_mic():
    """Ensure `PhoneMic_Sink` and `PhoneMic_Virtual_Mic` exist on Linux.

    Returns `(ok: bool, message: str, created_new: bool)`.
    """
    if not IS_LINUX:
        return False, "Virtual microphone creation via pactl is Linux-only.", False
    if not pactl_available():
        return False, "pactl is missing. Install pipewire-pulse on Arch Linux.", False
    backend, _ = server_info()
    if not backend:
        return False, "PipeWire / PulseAudio daemon is not running in this user session.", False

    sinks = {s.name for s in list_sinks()}
    sources = list_sources_short()
    if SINK_NAME in sinks and SOURCE_NAME in sources:
        return True, f"Virtual microphone '{SOURCE_NAME}' is already active ({backend}).", False

    created_new = False
    new_ids = []
    if SINK_NAME not in sinks:
        p = _run_pactl(
            "load-module",
            "module-null-sink",
            f"sink_name={SINK_NAME}",
            f"sink_properties=device.description={SINK_DESC}",
        )
        if not p or p.returncode != 0:
            err = (p.stderr or p.stdout or "pactl failed").strip() if p else "failed to run pactl"
            return False, f"Could not create {SINK_NAME}: {err}", False
        mid = p.stdout.strip()
        if re.fullmatch(r"\d+", mid):
            new_ids.append(mid)
        created_new = True
        # Give PipeWire/PulseAudio a brief beat to register `<sink>.monitor`
        for _ in range(8):
            if f"{SINK_NAME}.monitor" in list_sources_short():
                break
            time.sleep(0.05)

    sources = list_sources_short()
    if SOURCE_NAME not in sources:
        p2 = _run_pactl(
            "load-module",
            "module-remap-source",
            f"master={SINK_NAME}.monitor",
            f"source_name={SOURCE_NAME}",
            f"source_properties=device.description={SOURCE_DESC}",
        )
        if not p2 or p2.returncode != 0:
            err = (p2.stderr or p2.stdout or "pactl failed").strip() if p2 else "failed to run pactl"
            # Roll back partially created sink if we just loaded it
            for mid in reversed(new_ids):
                _run_pactl("unload-module", mid)
            return False, f"Could not create {SOURCE_NAME}: {err}", False
        mid2 = p2.stdout.strip()
        if re.fullmatch(r"\d+", mid2):
            new_ids.append(mid2)
        created_new = True

    if new_ids:
        with _LOCK:
            for mid in new_ids:
                if mid not in _SESSION_MODULES:
                    _SESSION_MODULES.append(mid)

    return True, f"Created {backend} virtual mic '{SOURCE_NAME}' -> sink '{SINK_NAME}'.", created_new


def remove_virtual_mic(session_only=False):
    """Unload PhoneMic virtual microphone modules. Returns `(ok: bool, message: str)`."""
    if not IS_LINUX or not pactl_available():
        return False, "pactl is not available."

    if session_only:
        with _LOCK:
            ids = list(reversed(_SESSION_MODULES))
            _SESSION_MODULES.clear()
        if not ids:
            return True, "No session virtual microphone modules to clean up."
        unloaded = 0
        for mid in ids:
            p = _run_pactl("unload-module", mid)
            if p and p.returncode == 0:
                unloaded += 1
        return True, f"Removed {unloaded} session virtual microphone module(s)."

    p = _run_pactl("list", "modules", "short")
    if not p or p.returncode != 0:
        return False, "Could not query PipeWire/PulseAudio modules."
    mods = parse_pactl_modules_short(p.stdout)

    # Unload dependent remap-source modules first, then null-sink modules
    targets_source = []
    targets_sink = []
    for mid, mname, margs in mods:
        if SOURCE_NAME in margs or (mname == "module-remap-source" and SINK_NAME in margs):
            targets_source.append(mid)
        elif SINK_NAME in margs:
            targets_sink.append(mid)

    with _LOCK:
        for mid in reversed(_SESSION_MODULES):
            if mid not in targets_source and mid not in targets_sink:
                targets_sink.append(mid)
        _SESSION_MODULES.clear()

    if not targets_source and not targets_sink:
        return True, "No PhoneMic virtual microphone modules were loaded."

    errors = []
    removed = 0
    for mid in targets_source + targets_sink:
        r = _run_pactl("unload-module", mid)
        if r and r.returncode == 0:
            removed += 1
        else:
            errors.append(mid)
    if errors and removed == 0:
        return False, f"Failed to unload module(s): {', '.join(errors)}"
    return True, f"Removed virtual microphone ({removed} module(s) unloaded)."
