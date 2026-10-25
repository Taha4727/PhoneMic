# PhoneMic Windows Receiver v0.8.0 (Studio DSP, Voice Changer & Modern UI)

Turn your Android phone into a studio-grade, ultra-low latency PC microphone over **Wi-Fi** or **USB Tethering**.

Tested and optimized for:
* **Samsung Galaxy J5** (Android 7.1.1 / API 25)
* **Samsung Galaxy A10s** (Android 11 / API 30)
* **POCO X6 Pro 5G / HyperOS** (Android 16 / API 36)

---

### 🌟 What's New in v0.8.0

1. **Persistent Settings & Auto-Save**:
   - Automatically saves and restores all user adjustments: slider values, active presets, audio devices, visualizer mode, and toggles.
   - Settings persist across sessions in `phonemic_config.json`.

2. **Dedicated, Isolated "Voice Changer" Section**:
   - Completely separated into its own top-level tab (`🎭 Voice Changer`) and modular DSP engine.
   - 100% isolated from networking framing, socket threads, jitter buffers, and device output streams. When bypassed, audio passes through untouched with zero risk and zero CPU overhead.
   - **8 Transformation Modes**:
     * `Natural Pitch`: Clean, transparent pitch shifting without distortion.
     * `Deep Titan / Monster`: Low, authoritative sub-harmonic rumble.
     * `Helium / Chipmunk`: High-pitched formant cartoon voice.
     * `Robot / Cybernetic`: Sci-Fi metallic ring modulation.
     * `Walkie-Talkie / Comm Radio`: Military two-way radio comms with authentic crunch.
     * `Echo / Stadium Delay`: Slapback stadium announcement echo.
     * `Demon / Dark Lord`: Deep guttural transformation with dark growl.
     * `Alien / Vibrato`: Undulating extraterrestrial pitch modulation.
   - **Built-in Voice Presets & User Custom Presets**:
     * Built-in presets: `Normal (Bypass)`, `Deep Titan`, `Announcer / Radio Host`, `Helium / Chipmunk`, `Robot / Cybernetic`, `Walkie-Talkie`, `Demon / Dark Lord`, `Echo / Stadium Announcer`, `Alien / Vibrato`.
     * `+ Save Voice Preset...`: Create and name your own custom voice presets!
     * `🗑 Delete`: Delete custom voice presets with one click.
   - **Fine Pitch Shift & Dry/Wet Blend**:
     * -12.0 to +12.0 semitones with dynamic musical interval readout.
     * Dry/Wet mix slider (0% to 100%).

3. **Studio Sound Presets & User Custom Presets (Audio FX & EQ)**:
   - Dedicated Studio Presets: `Default (Studio Clean)`, `Broadcast Warmth`, `Crisp & Articulate`, `Podcast & Streamer`, `De-Boom (Bass Cut)`, `Heavy Noise Cut (Keyboard)`, `Pure Raw (Zero FX)`.
   - `+ Save Preset...`: Save your own custom noise suppression and EQ configurations.
   - `🗑 Delete`: Remove user presets when no longer needed.

4. **Studio-Grade WOLA Noise Suppression (No Artifacts, No Buzz)**:
   - 50% Weighted Overlap-Add (WOLA) with Princen-Bradley sine windowing, Wiener gain masking, and 80Hz Butterworth rumble cut.
   - Artifact-free and zero buzzing.

5. **Real 3-Band Parametric Studio Equalizer**:
   - Robert Bristow-Johnson (RBJ) Biquad IIR filters in Direct Form II Transposed with continuous state retention.
   - Low Shelf (Warmth @ 120Hz), Mid Peaking (Clarity @ 2500Hz), High Shelf (Air @ 8000Hz).

6. **Redesigned Modern Obsidian UI**:
   - 4-tab segmented pill navigation: `📊 Studio Dashboard`, `🎛️ Audio FX & Equalizer`, `🎭 Voice Changer`, `🌐 Network & Devices`.
   - 32-Band neon spectrum visualizer with ballistic peak hold & oscilloscope mode.
   - Full telemetry tiles: protocol, client medium, jitter, bitrate, packets, loss, and uptime.

---

### 🚀 How to Run

#### Option 1: Standalone `.exe` (Easiest, No Python Needed)
* Double-click **`PhoneMicReceiver.exe`** (found in `windows_receiver\dist\` or downloaded from GitHub Actions).
* The dark GUI appears instantly.
* Click **"Fix Firewall"** once if prompted, or run `fix_firewall.bat` as Administrator.
* On your phone, tap **"Scan / Auto-Detect PC"** and start streaming!

#### Option 2: Run via Python
* Double-click **`start_receiver.bat`** (or run `python phonemic_receiver.py`).
* Runs the GUI by default. (For console mode, pass `--cli`).

---

### 📦 How to Build the Standalone `.exe`

#### Method A: Double-Click Local Builder (Windows PC)
1. Make sure Python 3.8+ is installed on your PC with "Add Python to PATH" checked.
2. Inside `windows_receiver\`, double-click **`build_exe.bat`**.
3. The script will automatically install `pyinstaller`, `sounddevice`, `numpy` and compile `PhoneMicReceiver.exe` into the `dist\` folder.

#### Method B: Automated GitHub Actions Cloud Builder
If you push this repository to GitHub:
1. Go to the **Actions** tab on your GitHub repository.
2. Select **"Build Windows Receiver EXE"** and click **"Run workflow"**.
3. Once completed, download the **`PhoneMicReceiver-Windows-v0.6.5`** artifact zip which contains the compiled standalone `PhoneMicReceiver.exe` ready to use!

---

### 🔌 USB Tethering vs Wi-Fi: Quick Guide

#### Using USB Tethering (Recommended for Lowest Latency):
1. Plug your phone into the PC with a USB cable.
2. On your phone: Go to **Settings > Connections / Network > Tethering** and enable **USB Tethering**.
3. In PhoneMic on Android: Tap the **"USB"** mode button.
4. The app switches to the USB Host IP (typically `192.168.42.129`).
5. In PhoneMic Receiver on PC: The **USB Tether IP** will be highlighted in green with a Copy button.
6. Tap **"Scan / Auto-Detect PC"** or enter the USB IP, then tap **"Start Streaming"**.
7. If audio doesn't flow, click **"Fix Firewall"** in the PC receiver to allow Public network packets.

#### Using Wi-Fi:
1. Connect both phone and PC to the same Wi-Fi network.
2. In PhoneMic on Android: Tap the **"Wi-Fi"** mode button.
3. Tap **"Scan / Auto-Detect PC"** or enter the Wi-Fi IP shown in the PC receiver.
4. Tap **"Start Streaming"**.

---

### 🎙 Virtual Cable Setup for Discord, OBS, Zoom
1. Download the free **VB-CABLE Driver** from [vb-audio.com/Cable](https://vb-audio.com/Cable/).
2. PhoneMic Receiver automatically selects **"CABLE Input"** as its audio output.
3. In Discord, Zoom, OBS, or Windows Settings, choose **"CABLE Output (VB-Audio Virtual Cable)"** as your input microphone.
