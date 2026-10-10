# PhoneMic Windows Receiver v0.6.0

Turn your Android phone into an ultra-low latency PC microphone over **USB Tethering** or **Wi-Fi**.

---

### 🚀 Quick Start (Windows)

#### Option 0: Dependency & Audio Diagnostic Checker (New)
1. Double-click `check_dependencies.bat` (or run `python check_dependencies.py`).
2. Checks Python, pip, NumPy, SoundDevice, and scans your Windows audio devices for VB-CABLE.
3. If packages are missing, it prompts to install them automatically or provides direct links.
4. If VB-CABLE is missing, it provides direct download links and opens the setup page in your browser.

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
- `O` : **Get VB-CABLE** (opens VB-Audio driver download page in browser).
- `+` / `-` : **Boost Gain** up or down in 0.5x increments.
- `Q` : **Quit** receiver cleanly.

---

### 📦 Build Standalone `PhoneMicReceiver.exe` (PyInstaller)

To compile the receiver and dependency checker into a **single standalone `.exe`** that runs on any Windows PC without needing Python installed:

#### Method 1: Double-Click Builder (Easiest)
Double-click **`build_exe.bat`**. It will automatically:
1. Install PyInstaller if not already installed.
2. Compile everything using `PhoneMicReceiver.spec` with all PortAudio DLLs and NumPy binaries bundled.
3. Place the final `PhoneMicReceiver.exe` in the `dist/` folder and open it for you.

#### Method 2: Command Line
```cmd
cd windows_receiver
pip install pyinstaller sounddevice numpy
pyinstaller --clean PhoneMicReceiver.spec
```
The compiled executable will be located at:
`windows_receiver\dist\PhoneMicReceiver.exe`

