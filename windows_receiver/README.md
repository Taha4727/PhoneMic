# PhoneMic Windows Receiver v0.6.0

Turn your Android phone into an ultra-low latency PC microphone over **USB Tethering** or **Wi-Fi**.

---

### 🚀 Quick Start (Windows)

#### Option 1: One-Click Launcher (Easiest)
1. Double-click `start_receiver.bat` (or right-click `start_receiver.ps1` and choose **Run with PowerShell**).
2. It will automatically check Python and install `sounddevice` and `numpy` if missing.
3. The receiver will immediately display your PC's IP addresses and wait for the phone.

#### Option 2: Manual Setup
1. Open PowerShell or Command Prompt:
   ```cmd
   pip install sounddevice numpy
   ```
2. Start the receiver:
   ```cmd
   python phonemic_receiver.py
   ```

---

### 📱 Connecting from the Phone
1. Open the **PhoneMic** app on your Android device.
2. Tap **"AUTO-DETECT PC RECEIVER"** (the receiver will respond instantly with its IP address).
   - *Or manually enter your PC IP address shown in the receiver window*.
3. Tap **"START STREAM"**.

---

### 🎙 Using with Discord, Zoom, OBS, Teams, Games
1. Download and install the free **VB-CABLE Virtual Audio Device** from [vb-audio.com](https://vb-audio.com/Cable/).
2. The receiver will automatically detect **"CABLE Input (VB-Audio Virtual Cable)"** as its output target.
3. In Discord, Zoom, or OBS, simply select **"CABLE Output (VB-Audio Virtual Cable)"** as your **Input Device / Microphone**.

---

### ⚡ Live Console Hotkeys
While the receiver window is open:
- `P` : **Pause / Resume** stream (mute output without dropping network connection).
- `M` : **Monitor Audio** (hear the microphone through your PC headphones/speakers in real-time).
- `R` : **Record WAV** (lossless 48 kHz stereo recording saved to `PhoneMic_YYYYMMDD_HHMMSS.wav`).
- `+` / `-` : **Boost Gain** up or down in 0.5x increments.
- `Q` : **Quit** receiver cleanly.
