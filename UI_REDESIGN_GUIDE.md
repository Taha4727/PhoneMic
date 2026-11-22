# PhoneMic UI Redesign & Architecture Guide

This document is the complete API and architecture reference for rebuilding the PhoneMic Android UI in **Google AI Studio Build** while keeping the audio capture engine, `PM01–PM04` protocol, and PC receivers untouched.

---

## Starter Prompt for Your New Google AI Studio Chat

Copy and paste this into a fresh Google AI Studio chat inside this project to kick off the UI redesign cleanly:

```text
Read `/AGENTS.md` and `/UI_REDESIGN_GUIDE.md` first before making any edits.

Let's completely redesign the PhoneMic Android UI from the ground up while keeping all backend audio capture, networking, services, and ViewModel wiring intact per those two guides.

First, tell me a brief visual direction plan (color palette, typography pairing, home studio layout, stats layout, settings layout, and Appearance theme options we should add), then wait for my confirmation before editing code.
```

---

## 1. Current Architecture & Active vs Legacy Inventory

| Layer | Status | Location & Role |
|---|---|---|
| **Locked Backend** | Do NOT edit | `PhoneMicService.kt`, `audio/AudioProtocol.kt`, `FloatingMicOverlayService.kt`, `PhoneMicTileService.kt`, `ReceiverDiscovery.kt`, `DeviceProfile.kt`, `util/ShareHelper.kt`, `windows_receiver/`, `assets/phonemic_cli.py` |
| **Shared Bridge** | Read & UI-extend only | `PhoneMicViewModel.kt`, `MainActivity.kt` |
| **Active UI Screens** | 3-Tab Flat Studio UI | `ui/screens/PhoneMicScreen.kt` (Bottom Bar shell), `ui/screens/HomeScreen.kt` (Zero-scroll main controls + visualizer), `ui/screens/StatusScreen.kt` (Live Audio Stream, Audio, Device), `ui/screens/SettingsScreen.kt` (General, Audio, Appearance, About) |
| **Active Theme** | Palette & OLED system | `ui/theme/Color.kt` (`AppPaletteStyle`, `PhoneMicColors`, Dark `#121212`, OLED `#000000`, Light), `ui/theme/Type.kt` (`PlusJakartaFontFamily`, `JetBrainsMonoFontFamily`), `ui/theme/Theme.kt` |
| **Active Components** | Slimmed & Theme-aware | `AudioVisualizer.kt`, `BatteryOptimizationBanner.kt`, `QrScannerDialog.kt`, `ReceiverGuideDialog.kt` |
| **Archived v1 UI Backup** | Excluded from Gradle | `/ui_backup_v1/` (`theme/`, `screens/`, `components/`, `RESTORE_NOTES.md`) |

---

## 2. Exact ViewModel Contract (`PhoneMicViewModel`)

### State Flows
1. `viewModel.uiState: StateFlow<PhoneMicUiState>` — General screen state.
2. `viewModel.audioDb: StateFlow<Float>` — High-frequency dB meter value (`-60f..0f`). **Collect only in leaf meter composables.**
3. `viewModel.visualizerSnapshot: StateFlow<VisualizerSnapshot>` — High-frequency (~12.5 Hz) snapshot containing `level: Float`, `peakDb: Float`, `waveform: FloatArray` (size 32), `spectrum: FloatArray` (size 16). **Collect only in the Visualizer composable.**

### `PhoneMicUiState` Fields (Read-Only Reference for Core Fields)
- **Connection & Target:** `ip`, `wifiIp`, `usbIp`, `port`, `connectionMode` (`PhoneMicService.CONNECTION_WIFI` / `CONNECTION_USB`), `transportMode` (`PhoneMicService.TRANSPORT_UDP` / `TRANSPORT_TCP`), `isScanningPc`, `scanFeedback`
- **Audio Configuration (Locked while `isRunning == true`):**
  - `micMode`: `"MIC"`, `"VOICE_RECOGNITION"`, `"UNPROCESSED"`, `"VOICE_COMMUNICATION"`, `"CAMCORDER"`
  - `audioQuality`: `AudioQuality.STUDIO_48K`, `BALANCED_24K`, `LOW_BANDWIDTH_16K`
  - `sampleRateHz`: `8000`, `16000`, `24000`, `32000`, `44100`, `48000` (`AudioProtocol.SUPPORTED_SAMPLE_RATES`)
  - `audioFormat`: `AudioFormatOption` (`PCM_16BIT`, `PCM_8BIT`, `PCM_24BIT` [check `.isSupportedOnDevice`], `PCM_FLOAT`)
  - `channels`: `1` (Mono) or `2` (Stereo) (`AudioChannelOption.fromCount(channels)`)
  - `preferredMicId`: `Int` (`-1` = System Default, matched against `availableMics: List<InputMicDevice>`)
- **Live Controls (Editable anytime):**
  - `gain: Float` (`0.5f..3.0f`)
  - `autoStartStreaming: Boolean`
  - `pushToTalkEnabled: Boolean`, `isPttPressed: Boolean`
  - `autoReconnectEnabled: Boolean`
  - `keepScreenAwake: Boolean`, `isOverlayEnabled: Boolean`
  - `visualizerEnabled: Boolean`, `visualizerStyle: VisualizerStyle` (`WAVEFORM`, `SPECTRUM_BARS`, `VU_METER`, `CIRCULAR_PULSE`)
- **Runtime & Permissions:** `isRunning`, `isPaused`, `isConnected`, `statusMessage`, `elapsedSeconds`, `packetsSent`, `bytesSent`, `packetRate`, `hasMicPermission`, `hasNotificationPermission`, `hasCameraPermission`, `isIgnoringBatteryOptimizations`, `showGuideDialog`, `showSettings`, `showQrScanner`

### Public Actions on `PhoneMicViewModel`
- Lifecycle/Service: `startStreaming(context)`, `stopStreaming(context)`, `togglePause()`, `maybeAutoStart(context)`, `checkPermissions(context)`, `checkBatteryOptimization()`
- Network/QR: `setIp(ip)`, `setPort(port)`, `setConnectionMode(mode)`, `setTransportMode(mode)`, `scanForPc(context)`, `setQrScannerVisible(visible)`, `applyScannedConfig(config: ScannedReceiverConfig)`
- Audio/Mic: `refreshAvailableMics()`, `setPreferredMicDevice(id)`, `setMicMode(mode)`, `setAudioQuality(quality)`, `setSampleRate(rateHz)`, `setAudioFormat(format)`, `setChannels(channels)`, `setGain(gain)`
- Feature Toggles & Navigation: `setKeepScreenAwake(awake)`, `toggleFloatingOverlay(context, enabled)`, `setAutoStartStreaming(enabled)`, `setPushToTalkEnabled(enabled)`, `setPttPressed(pressed)`, `setAutoReconnectEnabled(enabled)`, `setVisualizerEnabled(enabled)`, `setVisualizerStyle(style)`, `setSettingsVisible(visible)`, `setGuideDialogVisible(visible)`
- Validation & Wire Helpers: `viewModel.isValidIp(ip)`, `viewModel.isValidPort(port)`, `AudioProtocol.framePayloadBytes(rate, ch, fmt)`, `AudioProtocol.estimatedKbps(rate, ch, fmt)`, `AudioProtocol.isLegacyStandardStream(rate, ch, fmt)`

---

## 3. How to Add New Appearance & UI Features Safely

When adding new Appearance customization (for example: **App Theme Presets**, **AMOLED Dark / Light Mode**, **Accent Colors**, **UI Density / Compact View**, **Home Quick-Card Toggles**, or **Extra Visualizer Styles**):

1. **Define Typed Models in `ui/theme/` or `ui/`:**
   - Example: `enum class AppThemePreset(val id: String, val label: String, ...)`.
2. **Extend `PhoneMicUiState` & `PhoneMicViewModel` cleanly (UI fields only):**
   - Add UI fields with safe defaults in `PhoneMicUiState`.
   - Add a `PREF_*` constant in `PhoneMicViewModel.companion`, read it in `loadInitialState()`, persist it in `savePreferences()`, and expose a `fun set*(...)` setter.
   - Do **not** add UI-theme extras to `startStreaming()` Intent.
3. **Wire Theme at Root (`MainActivity.kt` -> `PhoneMicTheme`):**
   - Observe `viewModel.uiState` or theme slice in `MainActivity` and pass chosen theme/dynamic/dark options to `PhoneMicTheme(...)`. Update status/navigation bar icon brightness cleanly with `WindowCompat.getInsetsController`.
4. **Update `SettingsScreen` Appearance Section:**
   - Keep Settings organized into **General**, **Audio**, **Appearance**, and **About** with a `BackHandler` and top-bar back button (`settings_back_button`).
   - Add descriptive `Modifier.testTag("<snake_case>")` to every new toggle/selector.
5. **Respect Special Integrations:**
   - **Floating Mute Pill Toggle:** Before enabling, check `Settings.canDrawOverlays(context)` on Android 6+; launch `Settings.ACTION_MANAGE_OVERLAY_PERMISSION` if ungranted (keep logic from `FloatingOverlayControl`).
   - **QR Scanner:** Keep CameraX + ZXing decode logic returning `ScannedReceiverConfig(ip, port, transport)` to `viewModel.applyScannedConfig(config)` (you are encouraged to modernize the dialog chrome, viewfinder frame, and animations!).
   - **Mic Permission Banner & HyperOS/Samsung Battery Banners:** Keep OEM guidance helpers via `DeviceProfile.deviceDisplayName`, `DeviceProfile.isXiaomiOrPoco`, `DeviceProfile.openHyperOsSettings(context)`, `DeviceProfile.openSamsungBatterySettings(context)`, `DeviceProfile.openAppDetailsSettings(context)`.

---

## 4. UI Rebuild Checklist (Before Finishing Any Redesign Turn)

- [ ] All protected `testTag` IDs listed in `AGENTS.md` still exist and point to the right interactive elements.
- [ ] Every icon/image has non-null `contentDescription` (or `null` only if purely decorative).
- [ ] Interactive controls meet `48.dp` minimum touch targets.
- [ ] Custom visualizers allocate zero `Paint`/`Path`/arrays per frame inside `Canvas` draw scopes (`remember` reusable `Path` instances if drawing continuous waveform lines).
- [ ] `compile_applet` succeeds and `gradle :app:testDebugUnitTest` passes cleanly (including Robolectric Compose UI tests).
