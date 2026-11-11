# PhoneMic v1.2.0 — Release Notes

**Target Version:** `v1.2.0` (Tag: `v1.2.0`)  
**Release Title:** `PhoneMic v1.2.0 — Compact Minimal GUI & Stability / Security Fixes`

---

## 🌟 What's New in v1.2.0

### 🎛️ Compact Minimal GUI for Windows Receiver
* **One-Click Switchable Modes**: Toggle between **Full Studio** and the new **Minimal GUI** widget at any time via the `[⤢ Compact]` / `[⛶ Full UI]` buttons in the header or via keyboard shortcuts (**F10** / **Ctrl+Shift+M**).
* **All Essential Controls in a Compact Footprint**:
  * **Live Animated VU Meter**: Real-time volume level meter with numeric peak dB readout (`-∞ dB` to `0 dB`).
  * **Quick Action Controls**: Mute (with phone pause signaling), Monitor (headphone playback), WAV Recording, and FX Bypass toggles.
  * **Master Gain Stepper**: Instant `-`, `+`, and `0 dB` unity reset buttons with live numeric gain feedback.
  * **Connection & Multi-Phone Readout**: Clean display showing client phone IP, opened sample rate profile, jitter buffer depth, and multi-phone mixing counts.
* **Persistent Window State**: Remembers window coordinates and dimensions for both Full Studio and Minimal modes independently.

---

## 🛠️ Security & Bug Fixes

### 1. Wi-Fi Discovery & Network Routing
* **Accurate IP Discovery**: The standalone CLI and embedded asset receiver now query routing sockets to supply the PC's actual local interface IP rather than `127.0.0.1`, fixing Wi-Fi auto-discovery failures.
* **Spoof Protection & Loopback Fallback**: Android discovery logic now ignores loopback and unspecified embedded addresses, validating against the actual UDP packet sender address.
* **Strict Port Range Validation**: Validates `1`–`65535` across all command-line arguments, GUI inputs, and saved configuration files, gracefully catching `OverflowError` and `ValueError`.

### 2. Audio Capture, Rate Sync & Engine Stability
* **Audio Format & Magic Alignment**: Fixed an issue where sample-rate fallback (e.g. 24 kHz or 16 kHz falling back to 48 kHz) caused packet headers (`PM01`/`PM02`/`PM03`) to mismatch the capture rate, eliminating pitch and playback speed warping.
* **Multi-Phone Jitter Isolation**: Receiver tracks primary and secondary client sessions cleanly. Alternating packets from multiple phones no longer reset jitter buffers or trigger false disconnect warnings.
* **WAV Recording 2 GB Rollover**: Engine automatically rolls over into a numbered segment when nearing 2 GB, preventing wave header 4 GB corruption on long sessions.

### 3. Android Foreground Service & Overlay Robustness
* **Silence Recovery Cleanup**: The silence recovery watchdog now re-uses the original audio source and configured sample rate, and verifies `AudioRecord.state == STATE_INITIALIZED`.
* **Resampler Buffer Safety**: Fixed partial-read handling in `resample441To480` to loop until the requested buffer length is fulfilled.
* **TCP Stream Fragmentation**: Control channel reader now buffers until complete 4-byte command packets arrive.
* **Overlay & Quick Settings Tiles**: Wrapped service toggles with `ContextCompat.startForegroundService` and `try/catch` to avoid background execution crashes on Android 8+.
* **Overlay Sync**: Synchronized `PREF_OVERLAY` preference state when closing the overlay bubble.

---

## 📦 Assets & Downloads
* `PhoneMicReceiver-Setup-1.2.0.exe` (Windows Installer with automatic Windows Firewall configuration)
* `PhoneMicReceiver.exe` (Portable Windows Receiver executable)
* `phonemic_cli.py` (Standalone Python CLI receiver)
* `PhoneMic-v1.2.0.apk` (Android companion app)
