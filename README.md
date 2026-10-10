MADE WITH AI

# PhoneMic 🎙️

**PhoneMic** streams high-quality microphone audio from your Android phone directly to your Windows PC over **Wi-Fi** or **USB Tethering** with ultra-low latency.

- **Target OS:** Android 16 (API 36) with support back to Android 7.1.1 (API 24)
- **Special Hardware Tuning:** Xiaomi HyperOS & POCO X6 Pro 5G (MediaTek Dimensity 8300-Ultra)
- **Audio Specs:** 48,000 Hz, 16-bit Mono Linear PCM, 10 ms packet windows
- **Virtual Audio Device:** Seamless integration with VB-Audio Virtual Cable (WASAPI) for Discord, OBS, Zoom, and games.

---

## 🚀 Automated GitHub Actions APK Builds

This repository includes an automated GitHub Actions CI workflow (`.github/workflows/build-apk.yml`):

- **Automatic Trigger:** Runs on every `push` to `main`/`master`, on pull requests, or manually via **Workflow Dispatch**.
- **Download the APK:**
  1. Go to the **Actions** tab in your GitHub repository.
  2. Click on the latest workflow run.
  3. Under **Artifacts**, download `PhoneMic-debug-apk.zip` to get your ready-to-install `PhoneMic-debug.apk`.
- **GitHub Releases:** Creating a git release tag (e.g. `git tag v1.0 && git push --tags`) automatically creates a GitHub Release and attaches the compiled APK file.

---

## ⚡ POCO X6 Pro 5G & Xiaomi HyperOS Optimization

1. **Wi-Fi 6 Low-Latency Lock:** Automatically acquires `WIFI_MODE_FULL_LOW_LATENCY` to disable Wi-Fi power-save sleep cycles.
2. **Studio Raw (Unprocessed):** Bypasses hardware echo-cancellation to stream studio-quality vocal dynamic range.
3. **HyperOS Background Guard:** Tap the in-app banner to grant battery optimization exemption and open HyperOS settings to set Battery Saver to **"No restrictions"** and enable **"Autostart"**.

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
