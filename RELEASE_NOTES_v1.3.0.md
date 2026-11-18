# PhoneMic v1.3.0 — Release Notes

**Target Version:** `v1.3.0` (Tag: `v1.3.0`)  
**Release Title:** `PhoneMic v1.3.0 — Obsidian Studio UI, CLI Parity & Crash-Resilient Diagnostics`

---

## 🌟 What's New in v1.3.0

### 🖥️ Windows Receiver — Obsidian Studio UI & Stability
* **Refined Studio Workspace Layout**: Combines compact Discord-style navigation, OBS-style telemetry tiles, and NVIDIA Broadcast / Wave Link control ergonomics while keeping Signal Monitor, Quick FX, gain, mute, and device selection immediately accessible.
* **Readable Signal Monitor & Level Meter**: Adjusted container sizing and scale margins so numeric dBFS labels, peak-hold markers, and clipping indicators display cleanly without squashing.
* **Live Theme & Monochrome Rebuild**: Changing the accent theme or toggling monochrome mode now updates all open Studio pages, Minimal widget, and Setup Wizard consistently in real time.
* **Connections Page Crash Fix & Crash Diagnostics**: Debounced `<Configure>` resize handlers to eliminate layout recursion crashes on the Connections page, and added `faulthandler` with write-verified crash logging (`phonemic_crash.log`) for `pythonw.exe` launches.

### ⌨️ Standalone CLI Receiver (`phonemic_cli.py` v1.3.0)
* **CLI Flags & Port Validation**: Added `-V` / `--version` (prints version cleanly even before `numpy` checks) and strict `1`–`65535` `--port` validation matching `phonemic_receiver.py`.
* **Protocol & Socket Hardening**:
  * Fixed 32-bit unsigned sequence gap tracking (`MASK32`) to match Android `PM01`/`PM02`/`PM03` packet headers.
  * Added even-byte PCM frame alignment and empty-array resampler guards to handle malformed packets safely.
  * Enabled Windows VT ANSI console processing (`ENABLE_VIRTUAL_TERMINAL_PROCESSING`) so color VU meters render crisply on Windows consoles, plus `SO_REUSEADDR`, `SIO_UDP_CONNRESET`, and clean socket shutdown timeouts.

### 📱 Android Companion App (`v1.3.0`, `versionCode 4`)
* **Dynamic Audio Telemetry & Version Sync**: Live telemetry and spec rows (`StreamTelemetryCard`, `ReceiverGuideDialog`, `PhoneMicViewModel`) now pull `BuildConfig.VERSION_NAME` (`v1.3.0`) and reflect the selected audio quality profile (`48 kHz`, `24 kHz`, or `16 kHz`) accurately.
* **Updated Embedded CLI Asset**: Bundles the synchronized `phonemic_cli.py v1.3.0` for direct sharing to any PC via Android Share Sheet.

---

## 📦 Assets & Downloads
* `PhoneMicReceiver-Setup-1.3.0.exe` (Windows Installer with automatic Windows Firewall configuration)
* `PhoneMicReceiver.exe` (Portable Windows Receiver executable)
* `phonemic_cli.py` (Standalone Python CLI receiver)
* `PhoneMic-v1.3.0.apk` (Android companion app)
