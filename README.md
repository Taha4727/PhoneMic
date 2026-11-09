> [!NOTE]
> **🤖 100% Made With AI**  
> PhoneMic is an experimental open-source project generated and engineered from scratch using Artificial Intelligence (Google AI Studio Build). Every line of code across both the Android application (Kotlin/Jetpack Compose) and the Windows/cross-platform PC audio engines (Python/Tkinter/CFFI) was authored by AI.

# PhoneMic 🎙️

**PhoneMic** turns one or more Android phones into ultra-low-latency studio microphones for your PC over **Wi-Fi** or **USB Tethering**.

Whether you're streaming on Twitch, gaming on Discord, recording a podcast with friends, or making work calls on Zoom/OBS, PhoneMic captures 16-bit linear PCM audio directly from your phone's microphone hardware and streams it to your computer with sub-25 ms latency.

---

## 🌟 Key Features

### 📱 Android Application
* **Multi-Rate Audio Profiles**:
  * **Studio (48 kHz)**: Uncompressed 16-bit PCM for pristine broadcast quality (~768 kbps).
  * **Balanced (24 kHz)**: Crisp voice frequency response up to 12 kHz at half bandwidth (~384 kbps).
  * **Economy (16 kHz)**: Speech-optimized low-bandwidth profile for congested Wi-Fi / mobile hotspots (~256 kbps).
* **Multiple Phone Mixing**: Connect 2, 3, or more phones to the exact same receiver IP and port simultaneously.
* **Auto-Discovery & QR Code Pairing**:
  * Tap **"Auto-Detect Receiver"** to find your PC on the local network automatically using UDP beacons (`PMD0`).
  * Or scan the receiver's QR code on screen with instant orientation-independent camera scanning.
* **Low-Latency Architecture**:
  * Direct non-blocking AudioRecord loop reading in 10 ms chunks (160 to 480 samples).
  * Android 14/15/16 foreground service with high-priority wake locks and `WIFI_MODE_FULL_LOW_LATENCY`.
* **Built-in CLI Receiver Sharing**:
  * Share the lightweight CLI receiver script directly from your phone to any computer via Android Share Sheet (Bluetooth, Quick Share, Nearby Share, Google Drive, or email).
* **System Overlay & Quick Tile**:
  * Floating draggable bubble for muting/unmuting your mic while playing mobile games or browsing.
  * Android Quick Settings tile for 1-tap connection toggle.

### 💻 Windows & Cross-Platform Receivers

#### 1. Full GUI Receiver (`windows_receiver/`)
* **Real-time Signal Chain**:
  * Input -> Low/High-Cut Filter -> Noise Suppression -> Noise Gate -> Auto-Gain -> Voice Changer -> 5-Band Parametric EQ -> De-Esser -> Compressor -> Output.
* **Multi-Device Mixing**:
  * Mixes multiple connected devices simultaneously.
  * **Sum & Soft Limiter**: Sums all voices with a hyperbolic tangent (`tanh`) non-linear soft limiter to eliminate digital clipping.
  * **Auto-Duck Priority**: Detects primary active speaker and ducks other connected phones by 75% (-12 dB).
* **Virtual Cable Integration**:
  * Automatically routes audio into **VB-Audio Virtual Cable (WASAPI)** for zero-setup Discord/OBS selection.
* **System Tray & Global Hotkeys**:
  * Works in full-screen games with system-wide Push-to-Talk, Push-to-Mute, and Audio Monitoring shortcuts.

#### 2. Standalone CLI Receiver (`windows_receiver/phonemic_cli.py`)
* Lightweight, single-file receiver with **zero GUI dependencies** (runs on Windows, macOS, Linux, and Raspberry Pi).
* Interactive live ANSI dual-channel volume VU meters for each connected phone.
* **Real-Time Headphone Monitoring**: Press **`M`** to monitor microphone audio through your headphones without lag.
* **Interactive Terminal Keybindings**:
  * `[M]` Toggle Headphone Monitoring
  * `[X]` Cycle Mix Mode (Sum / Auto-Duck)
  * `[P]` Toggle Mute
  * `[+]` / `[-]` Master Digital Preamp Gain
  * `[0]` Reset Gain to 0 dB
  * `[C]` Reset Packet Statistics
  * `[H]` Toggle Detailed Telemetry (kbps, jitter buffer ms, drop %)
  * `[Q]` Clean Exit

---

## 🚀 Quick Start Guide

### 1. Computer Setup

#### Option A: Lightweight CLI Receiver (Recommended for any PC/Mac/Linux)
Requirements: Python 3.8+ and numpy (`pip install numpy sounddevice`)

```bash
# Clone the repository
git clone https://github.com/your-username/PhoneMic.git
cd PhoneMic/windows_receiver

# Run the CLI receiver (Default port: 5001)
python phonemic_cli.py

# Optional: Run with real-time headphone monitoring enabled
python phonemic_cli.py --monitor

# Optional: Run with Auto-Duck priority mixing for group calls
python phonemic_cli.py --mix-mode duck
```

#### Option B: Full Windows GUI Receiver
1. Navigate to `windows_receiver/`.
2. Double-click `start_receiver.bat` (or compile with `build_exe.bat` to generate `PhoneMicReceiver.exe`).
3. If connecting over USB tethering for the first time, click **"Fix Firewall"** (or run `fix_firewall.bat`).

---

### 2. Connect Your Phone(s)

1. Connect your phone to the same Wi-Fi network as your computer (or plug in a USB cable and enable **USB Tethering** in Android Settings for the lowest latency).
2. Open the **PhoneMic** app on your phone.
3. Tap **"Auto-Detect Receiver"** (or scan the QR code on the receiver screen).
4. Tap **"Start Streaming"**.
5. Your computer will immediately begin receiving audio!

#### Connecting Multiple Phones
- Open PhoneMic on Phone 2, 3, etc.
- Enter the **exact same PC IP address and port**.
- Tap **"Start Streaming"**.
- Both voices will mix together in real time.

---

### 3. Route Audio to Discord, OBS, Zoom, or Games

1. Download and install the free [VB-Audio Virtual Cable](https://vb-audio.com/Cable/).
2. In Windows Sound Settings, verify that **CABLE Input** is set to 48000 Hz.
3. In PhoneMic Receiver, select **CABLE Input** as your Target Device (selected by default).
4. In Discord, OBS, Zoom, or Steam:
   * Go to **Voice & Video Settings**.
   * Set **Input Device (Microphone)** to: `CABLE Output (VB-Audio Virtual Cable)`.

---

## 📦 Releases & GitHub Actions (Manual Trigger)

Releases are triggered **manually on-demand** from GitHub Actions:

1. **Android APK**: Compiled with Gradle (`PhoneMic-debug.apk`).
2. **Windows Receiver ZIP**: Built with PyInstaller (`PhoneMicReceiver-Windows.zip`) containing:
   * `PhoneMicReceiver.exe` (Standalone GUI)
   * `phonemic_cli.py` (Standalone CLI)
   * `fix_firewall.bat`
   * Documentation

### How to Create a Release:
1. In your GitHub repository, go to the **Actions** tab.
2. Select **"Manual Release (APK & Windows Receiver)"** from the left sidebar.
3. Click **"Run workflow"**.
4. (Optional) Enter your desired release tag (e.g. `v1.2.0`) and title.
5. Click the green **"Run workflow"** button.
6. GitHub will build both the Android APK and Windows bundle and publish them directly to your repository's **Releases** page!

---

## 🛠️ Architecture & Wire Protocol

```
+-------------------------------------------------------------+
|                     Android Phone                           |
|  [AudioRecord] -> 16-bit PCM Buffer (10ms frames)           |
|         |                                                   |
|  [Network Header] PM01 (48k) / PM02 (24k) / PM03 (16k)      |
+-------------------------------------------------------------+
                              |
                     UDP / TCP (Port 5001)
                              |
+-------------------------------------------------------------+
|                   PC Receiver Engine                        |
|  * UDP Beacon Discovery Responder (PMD0 -> PMA1)            |
|  * Multi-Client Demuxer & Per-Device Jitter Buffers         |
|  * Dynamic Linear Upsamplers (16k->48k 3x, 24k->48k 2x)     |
|  * Real-Time Mixer (Tanh Soft Limiter / Auto-Ducking)       |
|  * Low-Latency WASAPI Output Engine (PortAudio)             |
+-------------------------------------------------------------+
                              |
                  VB-Audio Virtual Cable / Speakers
```

### Packet Format
- **Byte 0..3**: Magic header (`b"PM01"` for 48 kHz, `b"PM02"` for 24 kHz, `b"PM03"` for 16 kHz).
- **Byte 4..7**: Big-endian unsigned 32-bit packet sequence number (`seq`).
- **Byte 8..N**: 16-bit signed little-endian linear PCM mono audio samples.

---

## 📄 License
This project is open-source and available under the MIT License.
