MADE WITH AI

# PhoneMic 🎙️

**PhoneMic** streams high-quality microphone audio from your Android phone directly to your Windows PC over **Wi-Fi** or **USB Tethering** with ultra-low latency.

- **Target OS:** Android 16 (API 36) with support back to Android 7.1.1 (API 24)
- **Special Hardware Tuning:** Xiaomi HyperOS & POCO X6 Pro 5G (MediaTek Dimensity 8300-Ultra)
- **Audio Specs:** 48,000 Hz, 16-bit Mono Linear PCM, 10 ms packet windows
- **Virtual Audio Device:** Seamless integration with VB-Audio Virtual Cable (WASAPI) for Discord, OBS, Zoom, and games.

---

## 🚀 Releases & Automated CI Builds

### What's New in v1.1.0
- **Keep Screen Awake**: Toggle in Settings and automatic `FLAG_KEEP_SCREEN_ON` prevention so the phone screen doesn't turn off during active sessions.
- **POCO F6 & Xiaomi HyperOS / Android 16 Support**:
  - Independent Microphone Permission Banner with direct "Open App Settings" shortcut to grant "While using the app" without repeat prompts.
  - Resolved installation compatibility for Android 16.
- **Graceful Socket Lifecycle**: Fixed `SocketException: Socket is closed` on stream termination/disconnect for both UDP and TCP streaming.
- **Multi-Platform CI**: Automated GitHub Actions workflows for building both the Android APK (`PhoneMic-debug.apk`) and Windows Receiver standalone executable bundle (`PhoneMicReceiver-Windows.zip`).

### How to Publish a New Release
1. In the AI Studio interface, use the **Push to GitHub** option to push the latest codebase to your GitHub repository.
2. In your GitHub repository:
   - Navigate to **Releases** → **Draft a new release**.
   - Create a new tag (e.g. `v1.1.0`) targeting `main` (or run `git tag v1.1.0 && git push --tags` locally).
   - Click **Publish release**.
3. GitHub Actions will automatically compile the Android APK and the Windows Receiver ZIP package, attaching both binaries directly to the release!

---

## ⚡ POCO & Xiaomi HyperOS Optimization

1. **Wi-Fi 6 Low-Latency Lock:** Automatically acquires `WIFI_MODE_FULL_LOW_LATENCY` to disable Wi-Fi power-save sleep cycles.
2. **Studio Raw (Unprocessed):** Bypasses hardware echo-cancellation to stream studio-quality vocal dynamic range.
3. **HyperOS Background Guard:** Tap the in-app banner to grant battery optimization exemption and open HyperOS settings to set Battery Saver to **"No restrictions"** and enable **"Autostart"**.
4. **Persistent Microphone Access:** Grant permission via the dedicated banner or App Info → Permissions to select "While using the app" to avoid system permission resets.

---

## 💻 Windows Receiver Setup

1. Navigate to the `windows_receiver/` folder.
2. Double-click `start_receiver.bat` (or run `python phonemic_receiver.py`).
3. Press **AUTO-DETECT PC RECEIVER** in the Android app to automatically discover your PC on the network.
4. Tap **START STREAMING**.

### Keyboard Controls on PC

| Key | Action | Description |
|:---:|:---|:---|
| `P` | **Pause / Mute** | Remote bidirectional sync: pauses audio on both PC and Android phone |
| `R` | **Record WAV** | Records live audio directly to `PhoneMic_YYYYMMDD_HHMMSS.wav` |
| `M` | **Monitor** | Plays audio through PC speakers/headphones for live sound check |
| `+` / `-` | **Digital Gain** | Adjusts receiver digital preamp gain |
| `Q` | **Quit** | Gracefully disconnects and restores console cursor |
