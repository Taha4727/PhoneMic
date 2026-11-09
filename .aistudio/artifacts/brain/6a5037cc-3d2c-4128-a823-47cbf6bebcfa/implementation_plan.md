# Implementation Plan: Multi-Device Mixing, CLI Receiver Sharing & Low-Bandwidth Mode

Support multiple simultaneous phone microphones connected to the receiver, build a standalone single-file CLI receiver that can be shared directly from the Android app, implement selectable low-bandwidth audio quality profiles, and apply stability enhancements across both platforms.

---

## User Review Required

> [!IMPORTANT]
> - **Multi-Device Mixing:** The Windows Receiver and CLI will support simultaneous connections from multiple phones over UDP and TCP. Users can toggle between **Sum & Soft Limiter** (all voices combined with clipping protection) and **Auto-Duck Priority** (quieter lines dip when the primary speaker talks).
> - **CLI Receiver Sharing:** A standalone, single-file Python script (`phonemic_cli.py`) will be bundled in the Android app assets and exportable via Android's native Share Sheet (QuickShare / email / Google Drive / Bluetooth).
> - **Low-Bandwidth Mode:** Users will have a simple dropdown in the Android app:
>   - **Studio (48 kHz / 16-bit):** ~768 kbps (Original studio fidelity)
>   - **Balanced (24 kHz / 16-bit):** ~384 kbps (50% bandwidth reduction)
>   - **Low Bandwidth (16 kHz / 16-bit or companded):** ~128–256 kbps (>65% reduction for weak Wi-Fi or mobile hotspots)
>   Packets include a lightweight protocol header tag so the receiver automatically adapts to any incoming profile on the fly.

---

## Proposed Changes

### Windows & CLI Receiver

#### 1. Multi-Device Audio Mixer (`windows_receiver/phonemic/engine.py`)
- Refactor the audio engine socket loop to maintain a dictionary of active client streams keyed by remote endpoint `(ip, port)`.
- Implement per-client jitter/sample ringbuffers and timestamp trackers.
- Automatically age out and remove disconnected clients after 3.5 seconds of inactivity.
- Implement mixing strategies:
  - **Sum & Soft-Limiter:** Linearly combine active samples and apply smooth tanh-based saturation headroom protection to prevent digital harsh clipping.
  - **Auto-Duck:** Calculate envelope energy per stream; when a primary speaker is active, attenuate concurrent streams by -9 dB.
- Expose mixer mode in GUI and CLI arguments (`--mix-mode sum` / `--mix-mode duck`).

#### 2. Standalone Lightweight CLI Receiver (`windows_receiver/phonemic_cli.py`)
- Create a self-contained, single-file CLI script that runs with standard Python 3 and minimal `sounddevice` / `numpy` (with fallback output support).
- Features:
  - Zero GUI / Tkinter overhead — perfect for headless PCs, Raspberry Pi, Linux, macOS, and lightweight Windows setups.
  - Interactive ASCII / ANSI live volume meter for each connected client.
  - Automatic detection and decoding of 48 kHz, 24 kHz, and 16 kHz stream profiles.
  - Multi-device simultaneous mixing with clipping limiter.
  - Command-line flags: `--port`, `--tcp`, `--device`, `--mix-mode`, `--buffer-ms`.

#### 3. Low-Bandwidth Packet Header Protocol (`windows_receiver/phonemic/engine.py`, `dsp.py`)
- Standardize packet format:
  - Byte 0: Magic byte `0x50` ('P')
  - Byte 1: Audio Profile (`0` = 48 kHz 16-bit, `1` = 24 kHz 16-bit, `2` = 16 kHz 16-bit, `3` = 16 kHz 8-bit μ-law)
  - Byte 2: Stream Sequence byte
  - Byte 3: Stream Flags (Mute, Priority)
  - Bytes 4+: Audio payload
  - Backward compatibility: If the packet does not start with magic byte `0x50`, seamlessly treat it as raw legacy 48 kHz 16-bit PCM.
- When receiving 24 kHz or 16 kHz packets, upsample cleanly with linear/cubic interpolation to the receiver's output hardware sample rate (48 kHz).

---

### Android Application

#### 4. Low-Bandwidth Quality Profiles (`AudioStreamService.kt`, `PhoneMicViewModel.kt`, `PhoneMicScreen.kt`)
- Add `AudioQualityProfile` enum:
  - `STUDIO_48K` (48,000 Hz, 16-bit PCM, ~768 kbps)
  - `BALANCED_24K` (24,000 Hz, 16-bit PCM, ~384 kbps)
  - `LOW_BANDWIDTH_16K` (16,000 Hz, 16-bit PCM, ~256 kbps)
- Update `AudioRecord` configuration to record at the selected sample rate with matched minimum buffer sizes.
- Attach the 4-byte packet header to each outbound UDP/TCP frame.
- Add an **Audio Quality / Bandwidth** selector card to `PhoneMicScreen` with live bandwidth estimates.

#### 5. CLI Receiver Asset & Share Integration (`MainActivity.kt`, `PhoneMicScreen.kt`)
- Bundle `phonemic_cli.py` into `app/src/main/assets/phonemic_cli.py`.
- Configure `FileProvider` in `AndroidManifest.xml` and `res/xml/file_paths.xml` for sharing files from app cache.
- Wire the top bar share icon to copy `phonemic_cli.py` to cache and launch Android's native `Intent.ACTION_SEND` share sheet so users can instantly send the CLI script to their PC via QuickShare, Nearby Share, Telegram, email, or Bluetooth.
- Add a "Share CLI Receiver" action directly inside the Setup Guide dialog.

#### 6. Cross-Platform Bug Fixes & Stability
- Prevent service restarts when changing audio profile while idle.
- Fix UI spacing and touch targets on small screens.
- Clean up tests and ensure full test suite passes.

---

## Verification Plan

### Automated Tests
1. **Android Unit Tests:** Run `gradle :app:testDebugUnitTest` to verify packet header serialization, audio profile calculations, and viewmodel state transitions.
2. **Android Compilation:** Run `compile_applet` to ensure clean build with zero Kotlin compiler errors.
3. **Python Packaging & CLI Tests:** Run `python3 windows_receiver/tests/test_packaging.py` and execute `python3 -m py_compile windows_receiver/phonemic_cli.py`.
4. **Mixer Verification:** Test `phonemic_cli.py` multi-stream audio buffer combination and upsampling logic.

### Manual Verification Steps
1. Tap the Share button on the Android app top bar -> Verify the Android Share Sheet opens with `phonemic_cli.py`.
2. Switch Audio Quality between Studio (48kHz), Balanced (24kHz), and Low Bandwidth (16kHz) -> Verify streaming adjusts seamlessly.
3. Test multiple client packets reaching the receiver -> Verify all devices are mixed together without distortion or crash.
