# PhoneMic Windows Receiver v0.7.5 (Studio DSP & Modern UI Native Engine)

Turn your Android phone into a studio-grade, ultra-low latency PC microphone over **Wi-Fi** or **USB Tethering**.

Tested and optimized for:
* **Samsung Galaxy J5** (Android 7.1.1 / API 25)
* **Samsung Galaxy A10s** (Android 11 / API 30)
* **POCO X6 Pro 5G / HyperOS** (Android 16 / API 36)

---

### 🌟 What's New in v0.7.5 (Studio DSP & UI Redesign)
1. **Redesigned Modern Obsidian UI**:
   - Elevated obsidian card aesthetic (`#0d1117` background, `#161b22` cards, `#30363d` borders) inspired by modern DAWs and Windows 11 Fluent 2.
   - Segmented pill tab bar navigation (`📊 Studio Dashboard`, `🎛️ Audio FX & Equalizer`, `🌐 Network & Routing`).
   - 32-Band neon spectrum visualizer with ballistic peak-hold gravity and oscilloscope wave mode.
   - Stereo VU meter with calibrated dB indicators (-40 to 0 dB) and peak hold.
   - 4-tile telemetry grid displaying protocol, client medium, jitter, bitrate, packets, loss, and uptime.
2. **Studio-Grade WOLA Noise Suppression (No Artifacts, No Buzz)**:
   - Fixed the previous block-FFT windowing issue that caused 100Hz buzz and musical chirping noise.
   - Now uses 50% Weighted Overlap-Add (WOLA) with Princen-Bradley sine windowing, time-smoothed and frequency-smoothed Wiener gain masking, and 80Hz Butterworth 2nd-order subsonic rumble cut.
   - 100% bit-exact transparent when bypassed; clean, natural voice preservation when active.
3. **Artifact-Free Voice Harmonizer Pitch Shifter**:
   - Replaced naive block resampling with a continuous Dual-Tap Rotating Harmonizer using raised-cosine crossfading ($w_1 + w_2 = 1.0$ everywhere).
   - Zero clicks, zero discontinuities, and smooth continuous pitch shifting from -12.0st to +12.0st.
   - One-click presets: `Natural (0st)`, `Deep Voice (-3st)`, `Announcer (-1.5st)`, `Crisp (+1.5st)`, `Helium (+5st)`.
4. **Real 3-Band Parametric Studio Equalizer**:
   - Implemented real Robert Bristow-Johnson (RBJ) Biquad IIR filters in Direct Form II Transposed with continuous state retention.
   - Low Shelf (Warmth @ 120Hz, ±12dB), Mid Peaking (Clarity/Presence @ 2500Hz, ±12dB), High Shelf (Air/Sparkle @ 8000Hz, ±12dB).
   - Instant studio presets: `Flat`, `Warmth`, `Crisp`, `De-Boom`.
5. **Anti-Click Studio Noise Gate & Headphone Monitor**:
   - Exponential attack/release envelope eliminates keyboard clicks and breathing between phrases.
   - Independent headphone monitoring volume slider and output routing.
6. **Silent Background Execution**:
   - All network scans and firewall configurations run asynchronously with `CREATE_NO_WINDOW`, preventing command window flashes or UI freezing.
   - Suspends canvas animations when minimized (`<Unmap>`) for 0% background CPU usage.

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
