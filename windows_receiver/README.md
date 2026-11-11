> [!NOTE]
> **🤖 100% Made With AI**  
> This entire receiver engine, GUI, DSP chain, and CLI tool were authored using Artificial Intelligence.

# PhoneMic Windows Receiver v1.2.0

Turn your Android phone into a low-latency PC microphone over **Wi-Fi** or **USB tethering**.
The wire protocol is unchanged, so the Android app needs no update, and settings from earlier versions are carried over.

---

## What's new in 1.2.0

### Compact Minimal GUI
* **Streamlined Widget View**: Toggle anytime between Full Studio and a compact desktop Minimal GUI via the `⤢ Compact` / `⛶ Full UI` button or shortcut **F10** / **Ctrl+Shift+M**.
* **Essential Controls Kept Handy**: Live animated VU meter with numeric dB readout, Quick Mute, Monitor, Record, Effects Bypass, and Master Gain step buttons (`-`, `+`, `0 dB`).
* **Connection Status**: Real-time readouts of client IP, sample rate profile, jitter/buffer depth, and active multi-phone count.
* **Independent Window Geometry**: Remembers your preferred desktop placement and dimensions for both Full Studio and Minimal modes independently.

### Protocol, Networking & Audio Fixes
* **Wi-Fi Discovery Routing**: CLI receiver now queries routing sockets to reply with the accurate local host interface IP rather than 127.0.0.1.
* **Audio Format & Sample Rate Consistency**: Android client and receiver strictly sync actual hardware capture sample rates with packet magics and packet sizes.
* **Multi-Phone Jitter Stability**: Per-client session isolation prevents alternating packets from resetting audio buffers or swapping sample rates.
* **WAV Recording 2 GB Rollover**: Engine automatically segments prolonged recordings to adhere to WAV 32-bit limits cleanly without corruption.
* **Strict Port Validation**: Bounds check `1`–`65535` across all command line flags, GUI inputs, and config files with graceful error recovery.

---

## What's new in 0.11

### Works in the background
* **Global shortcuts** that work in any app, including full-screen games (Settings, Shortcuts): mute, **push-to-talk**,
  **push-to-mute**, monitoring, recording, effects comparison and "show window". Click a shortcut, press the keys you want
  (Esc cancels). Keyboard keys, combinations such as Ctrl+Alt+M, and mouse side buttons all work. The key is never blocked,
  so the game still receives it. Push-to-talk opens and closes in 5 ms without clicks, never pauses the phone, and a muted
  microphone is not recorded either.
* **Tray icon** with a menu (Show, Mute, Monitor, Record, Effects bypassed, Quit). Its colour follows the connection state
  and the tooltip says what is happening. Optional **keep running when the window is closed**.
* **A second launch brings the window forward** instead of showing an error, so a hidden or tray-only app is easy to find.
* Optional **sound cues**: a short beep when a shortcut mutes or unmutes you (plays on your Windows default device, never into the
  microphone output).
* The header, Dashboard and tray say **Silent** while the push-to-talk gate is closed.

### Installing
* **Installer** (`installer\build_installer.bat`, needs the free Inno Setup 6): installs to Program Files, adds a Start Menu entry,
  **creates the firewall rules during setup** (so USB tethering works immediately) and removes them again on uninstall.
  Uninstalling asks whether to delete your settings and presets.
* `build_exe.bat` now also bundles the tray packages (`pystray`, `pillow`).

### Checking the Windows-only parts
* **Self-test**: `PhoneMicReceiver.exe --selftest`, or Diagnostics, Run self-test. It checks keyboard polling, the tray icon,
  the second-launch channel, sound cues, firewall rules and network adapters, and prints a PASS/FAIL report you can send.

---

## What's new in 0.10

### A new interface built around the signal path
* **Sound page = the signal chain.** The stages are listed in the order the audio really flows through them
  (Input, Low-cut and high-cut, Noise suppression, Noise gate, Auto gain, Voice changer, Equalizer, De-esser, Compressor, Output).
  A light shows what is on, and one panel at a time keeps each stage uncluttered.
* **Every setting explains itself.** Each control has a one-line summary, an **i** button for the longer explanation (what it does,
  when to change it, what it costs), and a reset button that lights up when the value differs from the default.
  The full text is in [SETTINGS.md](SETTINGS.md), generated from the same table the app uses.
* **Simple and Advanced views** (bottom of the sidebar). Simple shows the essentials; Advanced adds 39 more controls.
* **Search** (top of the window, `Ctrl+F`): type what you want to do ("rumble", "webcam", "hiss") and jump straight to the setting.
* **Setup wizard** on the first start (output choice, VB-CABLE, firewall, connecting the phone). Run it again from Settings.
* New look: graphite palette, five accent colours, instrument-style numbers, text colours checked for contrast.
* **Dashboard:** connection-quality gauges (delay, jitter, loss, bitrate) replace the plain number tiles.

### More control
* **Five-band parametric EQ** with a draggable graph (frequency and gain by dragging, width with the mouse wheel,
  right-click to switch a band off). Each band can be a bell, low shelf, high shelf or notch.
* **De-esser**, **lip-sync delay** (0 to 500 ms, for matching a webcam), **output level**, polarity invert,
  low-cut steepness (12 or 24 dB per octave) and a **high-cut** filter.
* **Gate:** attack, hold, closed depth and hysteresis. **Compressor:** attack, release, knee and dry/wet mix.
  **Auto gain:** maximum boost, reduction and recovery speed. **Noise suppression:** maximum reduction and learning time.
* **Effects on / bypassed** button (`Ctrl+B`) to compare your processed voice with the plain microphone.
* Network and audio: output channel (both, left, right), connection-lost timeout, adaptive-buffer headroom,
  drift correction on/off, and what to play for a lost packet.
* **Presets as files:** export the current preset or all of yours, import files from friends. Imports are validated,
  never overwrite anything, and cannot break the app even if the file is damaged.
* Two new sound presets (Smooth Vocal, Voice Chat) and a diagnostics export for bug reports.

### Under the hood
* Biquad filters use a float32 matrix form: about 3x faster than 0.9 for the same output; the processor with
  *every* stage enabled costs roughly 2 ms per 10 ms of audio.
* Every audio parameter is range-checked, so a hand-edited settings file or a hostile preset cannot cause a crash or a blast of noise.
* Your 0.9 EQ settings and presets are converted to the new five-band EQ automatically.
* Tests cover each new control against its expected behaviour (not just "runs"), the settings registry, preset files,
  contrast of every colour, and the whole GUI against a simulated Tk.

---

## Running

**Standalone:** double-click `PhoneMicReceiver.exe` (see *Building* below).

**From source:** Python 3.8+, then
```
pip install -r requirements.txt
python phonemic_receiver.py
```
or just double-click `start_receiver.bat` (installs the two packages on first run).

Command line: `--cli` (console mode) - `--check` (environment check) - `--selftest` - `--list-devices` - `--port N` - `--minimized` - `--reset-config` - `--version`

First start: click **Network -> Fix firewall** once (or run `fix_firewall.bat`), then on the phone tap **Scan / Auto-Detect PC**.

### Wi-Fi
1. Phone and PC on the same network. 2. Choose **Wi-Fi** in the app. 3. Scan / Auto-Detect, or type the address from the Dashboard. 4. Start streaming.

### USB tethering (lowest latency)
1. Plug in the phone, enable **USB tethering** in Android settings. 2. Choose **USB** in the app.
3. The receiver lists the tether address (green "USB Tether" badge on the Network page). 4. Scan or type it, start streaming.
5. If nothing arrives, press **Fix firewall**: Windows treats the tether as a *Public* network and blocks it by default.

### Using it in Discord / OBS / Zoom
Install the free [VB-CABLE](https://vb-audio.com/Cable/). The receiver selects **CABLE Input** automatically; in the other app choose
**CABLE Output (VB-Audio Virtual Cable)** as the microphone. *Audio Devices -> Play test tone* confirms the routing.

---

## Tuning latency

PC-side delay is roughly the **jitter profile** you pick (10-120 ms), plus about 10 ms when noise suppression is on, plus the sound card's own buffer.
Measured through the engine on a loopback test: Ultra-low 20 ms, Balanced + noise suppression 40 ms, Stable + noise suppression 70 ms
(phone capture, the network and Windows' audio stack come on top).

| Situation | Suggested setting |
|---|---|
| USB tethering | Ultra-low or Low, adaptive on |
| Good Wi-Fi (5 GHz, near the router) | Low or Balanced (default) |
| Crackles / "Concealed gaps" climbing on the Dashboard | Stable or Max stability, or leave **Adaptive** on |
| Need the very lowest delay | Ultra-low + Noise suppression *Fast* + Sound card buffer *Low* |

The Dashboard tiles and **Diagnostics** page show jitter, loss, concealed frames, buffer depth and underruns live.

---

## Building the .exe

```
build_exe.bat            single portable .exe   (dist\PhoneMicReceiver.exe)
build_exe.bat onedir     folder build           (dist\PhoneMicReceiver\ - starts instantly, no unpacking)
```
The spec bundles the `phonemic\` package, the app icon, NumPy, Tk and PortAudio. UPX is off on purpose (faster start, fewer antivirus false positives).
If you build with GitHub Actions, make sure the workflow still builds from `PhoneMicReceiver.spec` and that the whole `windows_receiver` folder
(including `phonemic\` and `assets\`) is checked out - the entry file name is unchanged.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Phone can't find the PC | **Network** page: is the status "listening"? Press **Fix firewall**. Try typing the IP manually. |
| "Port in use" in the header | Another receiver (or program) owns the port. Close it, or change the port on the Network page (and on the phone). |
| Connected but silent | **Audio Devices**: pick the right output and press *Play test tone*. In Discord/OBS pick *CABLE Output*. |
| Crackling | Raise the latency profile one step, keep Adaptive on, prefer USB over Wi-Fi, try backend *WASAPI*. |
| Output device missing | Press *Refresh devices*, or switch the backend (some devices only appear under MME/DirectSound). |
| Anything weird | **Diagnostics -> Copy log**; a crash writes `phonemic_crash.log` next to the app. |

Settings live in `phonemic_config.json` next to the app (or `%LOCALAPPDATA%\PhoneMic` if that folder is read-only).

---

---

## Project layout
```
phonemic_receiver.py      launcher (GUI / --cli / --check)
phonemic/
  const.py                protocol + audio constants, version
  config.py               typed settings, migration, validation, debounced atomic saves
  system.py               paths, firewall, network discovery, startup entry, audio device listing
  dsp.py                  biquads, denoiser, gate, AGC, compressor, de-esser, delay, limiter, voice changer, processor chain
  engine.py               jitter buffer, rings, UDP/TCP/beacon, output ports, recorder, Receiver facade
  settings_meta.py        THE table of every setting: label, summary, explanation, range, default, units
  bindings.py             connects those settings to the engine and the settings file (no GUI code)
  presets_io.py           preset files: export, import, validation
  widgets.py / ui_kit.py  dark widget kit, registry-driven rows, signal-chain list, EQ editor, gauges, search
  gui.py / pages.py       window, Dashboard and the other pages
  wizard.py               first-run setup
  hotkeys.py              global shortcuts: parsing, keyboard/mouse polling, capture
  tray.py / cues.py       tray icon (optional pystray), sound cues
  selftest.py             checks for the Windows-only features
  cli.py                  console mode, dependency check
installer/                Inno Setup script and build_installer.bat
tools/gen_settings_doc.py regenerates SETTINGS.md from the registry
tests/                    python tests/run_all.py  (no sound card, no Tk, no network needed)
```
The wire protocol (`PM01` + 32-bit sequence + 16-bit mono PCM @ 48 kHz, `PMD0`/`PMA1` discovery, `PMP1`/`PMR1` pause/resume) is unchanged.

## Earlier versions
* **0.10.0** redesigned interface (signal-chain Sound page, explained settings, search, wizard) and many more controls.
* **0.9.1** fixed a start-up crash in 0.9.0 (`TclError: invalid command name "1"`).
* **0.9.0** rebuilt the engine (jitter buffer, concealment, callback output, WASAPI), the DSP chain and the interface.
