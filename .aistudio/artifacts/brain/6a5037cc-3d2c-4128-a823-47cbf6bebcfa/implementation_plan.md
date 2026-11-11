# Implementation Plan - Minimal GUI for Windows Receiver

Create a compact, minimal GUI mode for the Windows receiver that displays all essential controls in a smaller footprint, with instant one-click switching between Default and Minimal modes via a clean button in the corner/title area.

## Proposed Changes

### 1. `windows_receiver/phonemic/config.py`
- Add `"ui_mode": "default"` (`"default"` | `"minimal"`) in `DEFAULTS["app"]`.
- Save and restore the preferred UI mode and window geometry across sessions.

### 2. `windows_receiver/phonemic/minimal_gui.py` (New Module)
- Implement a dedicated `MinimalView(tk.Frame)`:
  - **Compact Header & Switch Button**:
    - App title + version badge
    - Status indicator dot & label (`Streaming`, `Waiting for phone`, `Muted`)
    - Clean Mode Toggle button: `[⛶ Expand]` to switch back to Default UI.
  - **Connection & Device Status**:
    - Active client IP, port, and audio profile (48k / 24k / 16k)
    - Multi-device active counter (e.g. `2 phones mixed`)
    - Target Output Device readout (e.g. `CABLE Input`)
  - **Live VU Meter & Peak Level**:
    - Compact horizontal `LevelMeter` (green/yellow/red)
    - Live numeric dB readout (e.g. `-14.2 dB`)
  - **Essential Control Strip (Compact Buttons)**:
    - `Mute / Unmute` toggle (highlights red when muted)
    - `Monitor` toggle (turns active teal when hearing in headphones)
    - `Record` toggle (shows live elapsed timer when recording)
    - `Effects` bypass toggle (`FX On` / `Bypassed`)
  - **Master Gain & Preamp Control**:
    - Compact slider or quick +/- step buttons for master output gain
  - **Compact Window Sizing**:
    - Compact window geometry (~380x240 dp instead of 920x640 dp), resizable down to a sleek mini widget.
    - Saves separate window geometry for minimal mode so expanding restores the full studio layout.

### 3. `windows_receiver/phonemic/gui.py`
- Add `[⤢ Compact]` mode button in the header bar of the Default UI.
- Implement `switch_ui_mode(mode: str)`:
  - Seamlessly swap between the full sidebar/pages view and `MinimalView`.
  - Adjust window `minsize` and geometry between compact (~380x250) and full (~920x640).
  - Bind hotkey `F10` and `Ctrl+Shift+M` as convenient shortcuts to toggle modes.
- Route periodic `tick()` updates to `MinimalView` (updating meter, status, client IP, timer).

### 4. Tests & Verification
- Compile and run Python test suites:
  - `python3 -m py_compile windows_receiver/phonemic/*.py`
  - `python3 windows_receiver/tests/test_packaging.py`
- Verify Android app compatibility and compile:
  - `compile_applet`

## User Review Required
> [!NOTE]
> All controls from the default UI (Mute, Monitor, Record, FX Bypass, Master Gain, Live VU Meter, Client IP, and Multi-Phone indicators) are preserved in the Minimal mode in a space-efficient design.
