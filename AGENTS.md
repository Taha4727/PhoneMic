# PhoneMic Agent Handoff Rules (UI Redesign Contract)

> **Purpose:** This repository splits work between **Core/Backend** (audio capture, `PM01–PM04` wire protocol, foreground services, LAN discovery, and PC GUI/CLI receivers) and **UI Redesign** (Jetpack Compose screens, Material 3 theming, visualizers, dialogs, and Appearance customization).
>
> **If you are running the UI Redesign session:** Read both this file and `UI_REDESIGN_GUIDE.md` before modifying any file.

---

## 1. File Ownership & Scope Lock

### DO NOT MODIFY (Locked Core / Backend)
Leave these modules untouched so audio streaming, Xiaomi/Samsung mic recovery, and PC receiver decoding never break:
- `app/src/main/java/com/example/audio/AudioProtocol.kt` (wire framing `PM01–PM04`, `AudioFormatOption`, `AudioChannelOption`, `InputMicDevice`, `VisualizerSnapshot`, `AudioFrameProcessor` — **except** adding new enum entries to `VisualizerStyle` if accompanied by matching `AudioVisualizer` Canvas renderers)
- `app/src/main/java/com/example/PhoneMicService.kt` (audio capture loop, `AudioRecord`, socket send, auto-reconnect, PTT gating, Intent extras)
- `app/src/main/java/com/example/FloatingMicOverlayService.kt`
- `app/src/main/java/com/example/PhoneMicTileService.kt`
- `app/src/main/java/com/example/ReceiverDiscovery.kt`
- `app/src/main/java/com/example/DeviceProfile.kt`
- `app/src/main/java/com/example/util/ShareHelper.kt`
- `app/src/main/assets/phonemic_cli.py`
- `windows_receiver/` (entire PC GUI + CLI receiver codebase)
- `app/build.gradle.kts` (`applicationId`, `signingConfigs`, `minSdk`/`compileSdk`/`targetSdk`, `versionCode`, `versionName`)
- `metadata.json` (must keep `"name": "PhoneMic"` and `MAJOR_CAPABILITY_SERVER_SIDE_GEMINI_API` intact)
- `debug.keystore` / `debug.keystore.base64`

### OWNED BY UI REDESIGN (Free to Rebuild)
- `app/src/main/java/com/example/ui/**` (`theme/`, `screens/`, `components/`)
- `app/src/main/res/**` (`values/strings.xml`, `values/themes.xml`, `font/`, `drawable/`, adaptive launcher resources if needed)
- **Allowed targeted UI-only extensions outside `ui/`:**
  - `app/src/main/java/com/example/PhoneMicViewModel.kt`: May add **UI-only / Appearance fields and setters** (e.g., color theme enum, dark/light/AMOLED mode, accent palette, compact layout toggle, extra `VisualizerStyle`) plus their `SharedPreferences` keys inside `savePreferences()`/`loadInitialState()`. **Never alter** `startStreaming()`, `stopStreaming()`, `togglePause()`, `setPttPressed()`, `maybeAutoStart()`, `scanForPc()`, or any `PhoneMicService` listener/Intent wiring.
  - `app/src/main/java/com/example/MainActivity.kt`: May pass Appearance theme state from `viewModel.uiState` into `PhoneMicTheme(...)`. **Never alter** `enableEdgeToEdge()`, `FLAG_KEEP_SCREEN_ON` synchronization, `bindService()`, `unbindService()`, `checkPermissions()`, or `checkBatteryOptimization()`.
  - `app/src/test/java/com/example/ExampleRobolectricTest.kt`: Update or expand Compose UI assertions when layouts change, keeping contract `testTag` assertions intact.

---

## 2. Hard Technical & Behavioral Rules

1. **Preserve High-Frequency Flow Isolation:**
   - Read `viewModel.audioDb` (`StateFlow<Float>`) and `viewModel.visualizerSnapshot` (`StateFlow<VisualizerSnapshot>`) **only inside small leaf composables** (meters and `Canvas` visualizers).
   - Never copy high-frequency audio levels back into `PhoneMicUiState` on every frame (would recompose the entire screen ~12–100x/sec and cause GC stutter on low-RAM phones).
2. **Stream Lock State (`!uiState.isRunning`):**
   - `sampleRateHz`, `audioFormat`, `channels`, `micMode`, `preferredMicId`, `audioQuality`, `ip`, `port`, `connectionMode`, and `transportMode` **must be disabled** while `uiState.isRunning == true`, with a clear status note shown to the user.
   - `gain` (`0.5f..3.0f`), `visualizerEnabled`, `visualizerStyle`, `pushToTalkEnabled` (`isPttPressed`), `autoReconnectEnabled`, `keepScreenAwake`, and `isOverlayEnabled` work live even while streaming.
3. **Device Compatibility Gate:**
   - Gate `AudioFormatOption.PCM_24BIT` selection behind `format.isSupportedOnDevice` (requires Android 12 / API 31+).
4. **Push-to-Talk & Permission Integrity:**
   - Keep `RECORD_AUDIO`, `POST_NOTIFICATIONS` (API 33+), `CAMERA` (for QR scan), and `SYSTEM_ALERT_WINDOW` (`Settings.canDrawOverlays`) runtime permission checks intact.
   - Always reset `viewModel.setPttPressed(false)` in a `DisposableEffect` if the PTT hold control leaves composition or streaming stops.
   - Maintain the `LaunchedEffect(uiState.autoStartStreaming, uiState.hasMicPermission)` one-shot call to `viewModel.maybeAutoStart(context)`.
5. **Material 3, Edge-to-Edge & Accessibility:**
   - Respect `enableEdgeToEdge()` with proper `statusBarsPadding()`, `navigationBarsPadding()`, and `Scaffold` `innerPadding`.
   - Minimum `48.dp` interactive touch targets (`minimumInteractiveComponentSize()` or `.size(48.dp)`).
   - Non-null `contentDescription` on interactive icons/images; no hardcoded hex strings inside screen composables (centralize in `ui/theme/`).
   - Every secondary view, sheet, or settings route must register `BackHandler` (or Navigation Compose type-safe route backstack).

---

## 3. Naming Conventions (`snake_case` + Stable `testTag` Contract)

- **Compose `testTag`s:** Always `snake_case`.
- **String IDs (`strings.xml`):** Always descriptive `snake_case` (never `text1`, `label2`). Wait to migrate remaining inline strings into `strings.xml` incrementally as you rebuild components.
- **Drawables:** Prefix vector/bitmap icons with `ic_`, backgrounds/banners with `bg_` or `illu_`.
- **Protected Contract `testTag`s (Keep These IDs Working Across Redesigns):**
  - Top bar / Navigation: `open_settings_button`, `settings_screen`, `settings_back_button`
  - Hero / Stream Controls: `start_streaming_button`, `stop_streaming_button`, `pause_resume_button`, `ptt_hold_button`
  - Home Visualizer: `audio_visualizer_card` (and `visualizer_canvas_${style.id}` when rendered)
  - Settings Sections: `settings_section_general`, `settings_section_audio`, `settings_section_appearance`, `settings_section_about`
  - Key Settings Controls: `setting_auto_start`, `setting_ptt_mode`, `setting_auto_reconnect`, `setting_visualizer_toggle`, `sample_rate_${rate}`, `audio_format_${fmt.id}`, `channels_${count}`, `visualizer_style_${style.id}`

---

## 4. Build & Test Commands

- Use `compile_applet` for Android compilation checks.
- If running Gradle directly, **always use `gradle`** (never `./gradlew`).
- Run unit + Robolectric UI verification after major UI passes:
  ```bash
  gradle :app:testDebugUnitTest
  ```
- Do **not** write instrumented `androidTest/` tests or run `adb`. Use Robolectric in `app/src/test/java/com/example/` instead.
