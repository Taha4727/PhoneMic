package com.example

import android.Manifest
import android.app.Application
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import androidx.compose.runtime.Immutable
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import com.example.audio.AudioFormatOption
import com.example.audio.AudioProtocol
import com.example.audio.InputMicDevice
import com.example.audio.VisualizerSnapshot
import com.example.audio.VisualizerStyle
import com.example.ui.theme.AppPaletteStyle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.util.regex.Pattern
import kotlin.math.max

enum class MainTab {
    STATUS,
    HOME,
    SETTINGS
}

enum class HorizontalNavMode(
    val id: String,
    val label: String,
    val description: String
) {
    BOTTOM_BAR(
        id = "BOTTOM_BAR",
        label = "Bottom Bar (Default)",
        description = "Keep navigation tabs docked along the bottom edge in horizontal mode"
    ),
    SIDE_RAIL(
        id = "SIDE_RAIL",
        label = "Side Rail",
        description = "Move tabs to the left edge in horizontal mode to maximize screen height"
    );

    companion object {
        fun fromId(id: String?): HorizontalNavMode =
            entries.firstOrNull { it.id.equals(id, ignoreCase = true) } ?: BOTTOM_BAR
    }
}

@Immutable
data class PhoneMicUiState(
    val ip: String = "192.168.1.100",
    val wifiIp: String = "192.168.1.100",
    val usbIp: String = "192.168.42.129",
    val port: String = "5001",
    val connectionMode: String = PhoneMicService.CONNECTION_WIFI,
    val transportMode: String = PhoneMicService.TRANSPORT_UDP,
    val micMode: String = PhoneMicService.MIC_STANDARD,
    val gain: Float = 1.0f,
    val isRunning: Boolean = false,
    val isPaused: Boolean = false,
    val isConnected: Boolean = false,
    val statusMessage: String = "Ready to connect",
    val audioLevel: Float = 0f,
    val audioDb: Float = -60f,
    val elapsedSeconds: Long = 0L,
    val isScanningPc: Boolean = false,
    val scanFeedback: String? = null,
    val showGuideDialog: Boolean = false,
    val showSettings: Boolean = false,
    val isIgnoringBatteryOptimizations: Boolean = true,
    val hasMicPermission: Boolean = false,
    val hasNotificationPermission: Boolean = false,
    val hasCameraPermission: Boolean = false,
    val keepScreenAwake: Boolean = true,
    val isOverlayEnabled: Boolean = false,
    val showQrScanner: Boolean = false,
    val audioQuality: PhoneMicService.Companion.AudioQuality = PhoneMicService.Companion.AudioQuality.STUDIO_48K,
    // Upgraded Audio Settings (General / Audio / Appearance)
    val sampleRateHz: Int = 48000,
    val audioFormat: AudioFormatOption = AudioFormatOption.PCM_16BIT,
    val channels: Int = 1,
    val preferredMicId: Int = -1,
    val availableMics: List<InputMicDevice> = listOf(
        InputMicDevice(
            id = -1,
            name = "System Default",
            typeLabel = "Automatic Selection",
            kind = com.example.audio.MicDeviceKind.DEFAULT,
            isSystemDefault = true
        )
    ),
    val autoStartStreaming: Boolean = false,
    val pushToTalkEnabled: Boolean = false,
    val isPttPressed: Boolean = false,
    val autoReconnectEnabled: Boolean = false,
    val visualizerEnabled: Boolean = true,
    val visualizerStyle: VisualizerStyle = VisualizerStyle.WAVEFORM,
    // Redesign UI & Appearance preferences
    val activeTab: MainTab = MainTab.HOME,
    val isDarkMode: Boolean = true,
    val oledBlackEnabled: Boolean = false,
    val paletteStyle: AppPaletteStyle = AppPaletteStyle.TONAL_SPOT,
    val customThemeColorArgb: Long = 0xFF0EA5E9L,
    val horizontalNavMode: HorizontalNavMode = HorizontalNavMode.BOTTOM_BAR,
    // Stream telemetry matched with PC Receiver
    val packetsSent: Long = 0L,
    val packetsDropped: Long = 0L,
    val bytesSent: Long = 0L,
    val packetRate: Float = 0f,
    val receiverVersion: String = "Receiver v${BuildConfig.VERSION_NAME}",
    val targetAudioDevice: String = "CABLE Input (VB-Audio Virtual Cable)"
)

class PhoneMicViewModel(application: Application) : AndroidViewModel(application), PhoneMicService.Listener {

    companion object {
        private const val PREFS_NAME = "PhoneMicSettings"
        private const val PREF_IP = "ip"
        private const val PREF_WIFI_IP = "wifi_ip"
        private const val PREF_USB_IP = "usb_ip"
        private const val PREF_PORT = "port"
        private const val PREF_TRANSPORT = "transport"
        private const val PREF_CONNECTION = "connection"
        private const val PREF_MIC = "mic"
        private const val PREF_GAIN = "gain"
        private const val PREF_KEEP_SCREEN_AWAKE = "keep_screen_awake"
        private const val PREF_OVERLAY = "floating_overlay"
        private const val PREF_AUDIO_QUALITY = "audio_quality"
        private const val PREF_SAMPLE_RATE = "sample_rate_hz"
        private const val PREF_AUDIO_FORMAT = "audio_format"
        private const val PREF_CHANNELS = "channels"
        private const val PREF_PREFERRED_MIC_ID = "preferred_mic_id"
        private const val PREF_AUTO_START = "auto_start_streaming"
        private const val PREF_PUSH_TO_TALK = "push_to_talk_enabled"
        private const val PREF_AUTO_RECONNECT = "auto_reconnect_enabled"
        private const val PREF_VISUALIZER_ENABLED = "visualizer_enabled"
        private const val PREF_VISUALIZER_STYLE = "visualizer_style"
        private const val PREF_DARK_MODE = "dark_mode_enabled"
        private const val PREF_OLED_BLACK = "oled_black_enabled"
        private const val PREF_PALETTE_STYLE = "palette_style"
        private const val PREF_CUSTOM_THEME_COLOR = "custom_theme_color_argb"
        private const val PREF_HORIZONTAL_NAV_MODE = "horizontal_nav_mode"

        private val IPV4_PATTERN = Pattern.compile(
            "^((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)\\.){3}(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)$"
        )
    }

    private val prefs: SharedPreferences = application.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val _uiState = MutableStateFlow(loadInitialState())
    val uiState: StateFlow<PhoneMicUiState> = _uiState.asStateFlow()

    // Isolated high-frequency flows: prevents recomposing screen outside Visualizer / VU meter!
    private val _audioDb = MutableStateFlow(-60f)
    val audioDb: StateFlow<Float> = _audioDb.asStateFlow()

    private val _visualizerSnapshot = MutableStateFlow(VisualizerSnapshot())
    val visualizerSnapshot: StateFlow<VisualizerSnapshot> = _visualizerSnapshot.asStateFlow()

    private var phoneMicService: PhoneMicService? = null
    private var serviceBound = false
    private var autoStartTriggered = false

    private val uiHandler = Handler(Looper.getMainLooper())
    private var elapsedTickerRunning = false

    private val audioDeviceCallback = object : AudioDeviceCallback() {
        override fun onAudioDevicesAdded(addedDevices: Array<out AudioDeviceInfo>?) {
            refreshAvailableMics()
        }

        override fun onAudioDevicesRemoved(removedDevices: Array<out AudioDeviceInfo>?) {
            refreshAvailableMics()
        }
    }

    private val elapsedTicker = object : Runnable {
        override fun run() {
            val startedAt = phoneMicService?.getStreamingStartedAt() ?: 0L
            if (startedAt > 0L) {
                val sec = max(0L, (SystemClock.elapsedRealtime() - startedAt) / 1000L)
                _uiState.update { it.copy(elapsedSeconds = sec) }
            }
            if (elapsedTickerRunning) {
                uiHandler.postDelayed(this, 1000L)
            }
        }
    }

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            val localBinder = binder as? PhoneMicService.LocalBinder
            phoneMicService = localBinder?.service
            serviceBound = true
            phoneMicService?.let { svc ->
                svc.registerListener(this@PhoneMicViewModel)
                val st = _uiState.value
                svc.setVisualizerEnabled(st.visualizerEnabled)
                svc.setAutoReconnect(st.autoReconnectEnabled)
                svc.setPushToTalkConfig(st.pushToTalkEnabled, st.isPttPressed)
                if (svc.isRunning()) {
                    startElapsedTicker()
                }
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            serviceBound = false
            phoneMicService = null
            stopElapsedTicker()
            _visualizerSnapshot.value = VisualizerSnapshot()
            _uiState.update {
                it.copy(
                    isRunning = false,
                    isPaused = false,
                    isConnected = false,
                    isPttPressed = false,
                    statusMessage = "Service disconnected",
                    audioLevel = 0f,
                    audioDb = -60f,
                    elapsedSeconds = 0L,
                    packetsSent = 0L,
                    packetsDropped = 0L,
                    bytesSent = 0L,
                    packetRate = 0f
                )
            }
        }
    }

    init {
        checkBatteryOptimization()
        checkPermissions()
        refreshAvailableMics()
        try {
            val am = application.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
            am?.registerAudioDeviceCallback(audioDeviceCallback, uiHandler)
        } catch (_: Exception) {}
    }

    private fun loadInitialState(): PhoneMicUiState {
        val legacyIp = prefs.getString(PREF_IP, "192.168.1.100") ?: "192.168.1.100"
        val savedWifiIp = prefs.getString(PREF_WIFI_IP, legacyIp) ?: legacyIp
        val savedUsbIp = prefs.getString(PREF_USB_IP, "192.168.42.129") ?: "192.168.42.129"
        val savedPort = prefs.getString(PREF_PORT, "5001") ?: "5001"
        val savedTransport = prefs.getString(PREF_TRANSPORT, PhoneMicService.TRANSPORT_UDP) ?: PhoneMicService.TRANSPORT_UDP
        val savedConnection = prefs.getString(PREF_CONNECTION, PhoneMicService.CONNECTION_WIFI) ?: PhoneMicService.CONNECTION_WIFI
        val savedMic = prefs.getString(PREF_MIC, PhoneMicService.MIC_STANDARD) ?: PhoneMicService.MIC_STANDARD
        val savedGain = prefs.getFloat(PREF_GAIN, 1.0f)
        val savedKeepScreenAwake = prefs.getBoolean(PREF_KEEP_SCREEN_AWAKE, true)
        val savedOverlay = prefs.getBoolean(PREF_OVERLAY, false)
        val savedQualityId = prefs.getString(PREF_AUDIO_QUALITY, PhoneMicService.Companion.AudioQuality.STUDIO_48K.id)
        val savedQuality = PhoneMicService.Companion.AudioQuality.fromId(savedQualityId)

        val savedRate = prefs.getInt(PREF_SAMPLE_RATE, savedQuality.sampleRate)
            .takeIf { it in AudioProtocol.SUPPORTED_SAMPLE_RATES } ?: 48000
        val rawFormat = AudioFormatOption.fromId(prefs.getString(PREF_AUDIO_FORMAT, AudioFormatOption.PCM_16BIT.id))
        val savedFormat = if (rawFormat.isSupportedOnDevice) rawFormat else AudioFormatOption.PCM_16BIT
        val savedChannels = if (prefs.getInt(PREF_CHANNELS, 1) == 2) 2 else 1
        val savedPreferredMicId = prefs.getInt(PREF_PREFERRED_MIC_ID, -1)
        val savedAutoStart = prefs.getBoolean(PREF_AUTO_START, false)
        val savedPtt = prefs.getBoolean(PREF_PUSH_TO_TALK, false)
        val savedAutoReconnect = prefs.getBoolean(PREF_AUTO_RECONNECT, false)
        val savedVizEnabled = prefs.getBoolean(PREF_VISUALIZER_ENABLED, true)
        val savedVizStyle = VisualizerStyle.fromId(prefs.getString(PREF_VISUALIZER_STYLE, VisualizerStyle.WAVEFORM.id))
        val savedDarkMode = prefs.getBoolean(PREF_DARK_MODE, true)
        val savedOledBlack = prefs.getBoolean(PREF_OLED_BLACK, false)
        val rawPalette = AppPaletteStyle.fromId(prefs.getString(PREF_PALETTE_STYLE, AppPaletteStyle.TONAL_SPOT.id))
        val legacyPresetId = prefs.getString("theme_color_preset", null)
        val savedPalette = if (rawPalette != AppPaletteStyle.CUSTOM && legacyPresetId.equals("CUSTOM", ignoreCase = true)) {
            AppPaletteStyle.CUSTOM
        } else {
            rawPalette
        }
        val savedCustomColorArgb = prefs.getLong(PREF_CUSTOM_THEME_COLOR, 0xFF0EA5E9L)
        val savedHorizontalNavMode = HorizontalNavMode.fromId(
            prefs.getString(PREF_HORIZONTAL_NAV_MODE, HorizontalNavMode.BOTTOM_BAR.id)
        )

        val app = getApplication<Application>()
        val hasMic = ContextCompat.checkSelfPermission(
            app,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
        val hasNotif = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                app,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
        } else true
        val hasCamera = ContextCompat.checkSelfPermission(
            app,
            Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED

        val activeIp = if (savedConnection == PhoneMicService.CONNECTION_USB) savedUsbIp else savedWifiIp

        return PhoneMicUiState(
            ip = activeIp,
            wifiIp = savedWifiIp,
            usbIp = savedUsbIp,
            port = savedPort,
            connectionMode = savedConnection,
            transportMode = savedTransport,
            micMode = savedMic,
            gain = savedGain,
            audioQuality = savedQuality,
            sampleRateHz = savedRate,
            audioFormat = savedFormat,
            channels = savedChannels,
            preferredMicId = savedPreferredMicId,
            autoStartStreaming = savedAutoStart,
            pushToTalkEnabled = savedPtt,
            autoReconnectEnabled = savedAutoReconnect,
            visualizerEnabled = savedVizEnabled,
            visualizerStyle = savedVizStyle,
            isDarkMode = savedDarkMode,
            oledBlackEnabled = savedOledBlack,
            paletteStyle = savedPalette,
            customThemeColorArgb = savedCustomColorArgb,
            horizontalNavMode = savedHorizontalNavMode,
            keepScreenAwake = savedKeepScreenAwake,
            isOverlayEnabled = savedOverlay,
            hasMicPermission = hasMic,
            hasNotificationPermission = hasNotif,
            hasCameraPermission = hasCamera
        )
    }

    fun bindService(context: Context) {
        if (!serviceBound) {
            val intent = Intent(context, PhoneMicService::class.java)
            context.bindService(intent, serviceConnection, Context.BIND_AUTO_CREATE)
        }
    }

    fun unbindService(context: Context) {
        if (serviceBound) {
            phoneMicService?.unregisterListener(this)
            try {
                context.unbindService(serviceConnection)
            } catch (_: Exception) {}
            serviceBound = false
            phoneMicService = null
        }
        stopElapsedTicker()
    }

    fun refreshAvailableMics() {
        val list = AudioProtocol.queryInputMicDevices(getApplication())
        var prefMicChanged = false
        _uiState.update { current ->
            val stillExists = current.preferredMicId == -1 || list.any { it.id == current.preferredMicId }
            val nextMicId = if (stillExists) current.preferredMicId else -1
            if (nextMicId != current.preferredMicId) {
                prefMicChanged = true
            }
            if (current.availableMics == list && !prefMicChanged) return@update current
            current.copy(
                availableMics = list,
                preferredMicId = nextMicId
            )
        }
        if (prefMicChanged) {
            prefs.edit().putInt(PREF_PREFERRED_MIC_ID, _uiState.value.preferredMicId).apply()
        }
    }

    fun checkBatteryOptimization() {
        val pm = getApplication<Application>().getSystemService(PowerManager::class.java)
        val pkg = getApplication<Application>().packageName
        val isIgnored = pm?.isIgnoringBatteryOptimizations(pkg) ?: true
        if (_uiState.value.isIgnoringBatteryOptimizations != isIgnored) {
            _uiState.update { it.copy(isIgnoringBatteryOptimizations = isIgnored) }
        }
    }

    fun setIp(newIp: String) {
        val cleanIp = newIp.trim()
        var isUsb = false
        _uiState.update { current ->
            isUsb = current.connectionMode == PhoneMicService.CONNECTION_USB
            if (isUsb) {
                current.copy(ip = cleanIp, usbIp = cleanIp, scanFeedback = null)
            } else {
                current.copy(ip = cleanIp, wifiIp = cleanIp, scanFeedback = null)
            }
        }
        prefs.edit()
            .putString(PREF_IP, cleanIp)
            .putString(if (isUsb) PREF_USB_IP else PREF_WIFI_IP, cleanIp)
            .apply()
    }

    fun setPort(newPort: String) {
        val cleanPort = newPort.trim()
        _uiState.update { it.copy(port = cleanPort) }
        prefs.edit().putString(PREF_PORT, cleanPort).apply()
    }

    fun setConnectionMode(mode: String) {
        _uiState.update { current ->
            val targetIp = if (mode == PhoneMicService.CONNECTION_USB) current.usbIp else current.wifiIp
            current.copy(
                connectionMode = mode,
                ip = targetIp,
                scanFeedback = null
            )
        }
        savePreferences()
    }

    fun setTransportMode(mode: String) {
        _uiState.update { it.copy(transportMode = mode) }
        savePreferences()
    }

    fun setMicMode(mode: String) {
        _uiState.update { it.copy(micMode = mode) }
        savePreferences()
    }

    fun setPreferredMicDevice(deviceId: Int) {
        _uiState.update { it.copy(preferredMicId = deviceId) }
        savePreferences()
    }

    fun setAudioQuality(quality: PhoneMicService.Companion.AudioQuality) {
        _uiState.update {
            it.copy(
                audioQuality = quality,
                sampleRateHz = quality.sampleRate,
                channels = 1,
                audioFormat = AudioFormatOption.PCM_16BIT
            )
        }
        savePreferences()
    }

    fun setSampleRate(rateHz: Int) {
        if (rateHz !in AudioProtocol.SUPPORTED_SAMPLE_RATES) return
        val syncedQuality = when (rateHz) {
            16000 -> PhoneMicService.Companion.AudioQuality.LOW_BANDWIDTH_16K
            24000 -> PhoneMicService.Companion.AudioQuality.BALANCED_24K
            else -> PhoneMicService.Companion.AudioQuality.STUDIO_48K
        }
        _uiState.update { it.copy(sampleRateHz = rateHz, audioQuality = syncedQuality) }
        savePreferences()
    }

    fun setAudioFormat(format: AudioFormatOption) {
        val safeFmt = if (format.isSupportedOnDevice) format else AudioFormatOption.PCM_16BIT
        _uiState.update { it.copy(audioFormat = safeFmt) }
        savePreferences()
    }

    fun setChannels(channels: Int) {
        val safeCh = if (channels == 2) 2 else 1
        _uiState.update { it.copy(channels = safeCh) }
        savePreferences()
    }

    fun setGain(newGain: Float) {
        if (_uiState.value.gain == newGain) return
        _uiState.update { it.copy(gain = newGain) }
        phoneMicService?.setGain(newGain)
        prefs.edit().putFloat(PREF_GAIN, newGain).apply()
    }

    fun setKeepScreenAwake(awake: Boolean) {
        _uiState.update { it.copy(keepScreenAwake = awake) }
        savePreferences()
    }

    fun setAutoStartStreaming(enabled: Boolean) {
        _uiState.update { it.copy(autoStartStreaming = enabled) }
        savePreferences()
    }

    fun setPushToTalkEnabled(enabled: Boolean) {
        _uiState.update { it.copy(pushToTalkEnabled = enabled, isPttPressed = false) }
        phoneMicService?.setPushToTalkConfig(enabled, false)
        savePreferences()
    }

    fun setPttPressed(pressed: Boolean) {
        _uiState.update { current ->
            if (!current.pushToTalkEnabled || current.isPttPressed == pressed) return@update current
            current.copy(isPttPressed = pressed)
        }
        val state = _uiState.value
        phoneMicService?.setPushToTalkConfig(state.pushToTalkEnabled, pressed)
    }

    fun setAutoReconnectEnabled(enabled: Boolean) {
        _uiState.update { it.copy(autoReconnectEnabled = enabled) }
        phoneMicService?.setAutoReconnect(enabled)
        savePreferences()
    }

    fun setVisualizerEnabled(enabled: Boolean) {
        _uiState.update { it.copy(visualizerEnabled = enabled) }
        phoneMicService?.setVisualizerEnabled(enabled)
        if (!enabled) {
            _visualizerSnapshot.value = VisualizerSnapshot()
        }
        savePreferences()
    }

    fun setVisualizerStyle(style: VisualizerStyle) {
        _uiState.update { it.copy(visualizerStyle = style) }
        savePreferences()
    }

    fun setActiveTab(tab: MainTab) {
        if (_uiState.value.activeTab == tab) return
        _uiState.update {
            it.copy(
                activeTab = tab,
                showSettings = tab == MainTab.SETTINGS
            )
        }
    }

    fun setSettingsVisible(visible: Boolean) {
        setActiveTab(if (visible) MainTab.SETTINGS else MainTab.HOME)
    }

    fun setDarkMode(dark: Boolean) {
        _uiState.update { it.copy(isDarkMode = dark) }
        savePreferences()
    }

    fun toggleDarkMode() {
        _uiState.update { it.copy(isDarkMode = !it.isDarkMode) }
        savePreferences()
    }

    fun setOledBlackEnabled(enabled: Boolean) {
        _uiState.update { it.copy(oledBlackEnabled = enabled) }
        savePreferences()
    }

    fun setPaletteStyle(style: AppPaletteStyle) {
        _uiState.update { it.copy(paletteStyle = style) }
        savePreferences()
    }

    fun setCustomThemeColor(argb: Long) {
        val opaqueArgb = argb or 0xFF000000L
        _uiState.update {
            it.copy(
                paletteStyle = AppPaletteStyle.CUSTOM,
                customThemeColorArgb = opaqueArgb
            )
        }
        savePreferences()
    }

    fun setHorizontalNavMode(mode: HorizontalNavMode) {
        _uiState.update { it.copy(horizontalNavMode = mode) }
        savePreferences()
    }

    fun checkPermissions(context: Context = getApplication()) {
        val hasMic = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED

        val hasNotif = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
        } else true

        val hasCam = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED

        _uiState.update {
            it.copy(
                hasMicPermission = hasMic,
                hasNotificationPermission = hasNotif,
                hasCameraPermission = hasCam
            )
        }
    }

    fun maybeAutoStart(context: Context) {
        if (autoStartTriggered) return
        autoStartTriggered = true
        val state = _uiState.value
        if (state.autoStartStreaming &&
            !state.isRunning &&
            state.hasMicPermission &&
            isValidIp(state.ip) &&
            isValidPort(state.port)
        ) {
            startStreaming(context)
        }
    }

    fun setQrScannerVisible(visible: Boolean) {
        _uiState.update { it.copy(showQrScanner = visible) }
    }

    fun applyScannedConfig(config: com.example.ui.components.ScannedReceiverConfig) {
        val cleanIp = config.ip.trim()
        val portStr = config.port.toString()
        _uiState.update { current ->
            if (current.connectionMode == PhoneMicService.CONNECTION_USB) {
                current.copy(
                    ip = cleanIp,
                    usbIp = cleanIp,
                    port = portStr,
                    transportMode = config.transport,
                    scanFeedback = "Paired with $cleanIp:$portStr via QR code"
                )
            } else {
                current.copy(
                    ip = cleanIp,
                    wifiIp = cleanIp,
                    port = portStr,
                    transportMode = config.transport,
                    scanFeedback = "Paired with $cleanIp:$portStr via QR code"
                )
            }
        }
        savePreferences()
    }

    fun toggleFloatingOverlay(context: Context, enabled: Boolean) {
        if (enabled) {
            val intent = Intent(context, FloatingMicOverlayService::class.java).apply {
                action = FloatingMicOverlayService.ACTION_START_OVERLAY
            }
            context.startService(intent)
            _uiState.update { it.copy(isOverlayEnabled = true) }
        } else {
            val intent = Intent(context, FloatingMicOverlayService::class.java).apply {
                action = FloatingMicOverlayService.ACTION_STOP_OVERLAY
            }
            context.startService(intent)
            _uiState.update { it.copy(isOverlayEnabled = false) }
        }
        prefs.edit().putBoolean(PREF_OVERLAY, enabled).apply()
    }

    fun setGuideDialogVisible(visible: Boolean) {
        _uiState.update { it.copy(showGuideDialog = visible) }
    }

    fun isValidIp(ip: String): Boolean = IPV4_PATTERN.matcher(ip).matches()

    fun isValidPort(port: String): Boolean {
        val p = port.toIntOrNull() ?: return false
        return p in 1..65535
    }

    fun startStreaming(context: Context) {
        val state = _uiState.value
        val ip = state.ip
        val portStr = state.port

        if (ip.isEmpty() || !isValidIp(ip)) {
            _uiState.update { it.copy(statusMessage = "Please enter a valid IPv4 address") }
            return
        }

        val port = portStr.toIntOrNull()
        if (port == null || port !in 1..65535) {
            _uiState.update { it.copy(statusMessage = "Port must be between 1 and 65535") }
            return
        }

        savePreferences()

        val intent = Intent(context, PhoneMicService::class.java).apply {
            action = PhoneMicService.ACTION_START
            putExtra(PhoneMicService.EXTRA_IP, ip)
            putExtra(PhoneMicService.EXTRA_PORT, port)
            putExtra(PhoneMicService.EXTRA_TRANSPORT, state.transportMode)
            putExtra(PhoneMicService.EXTRA_CONNECTION, state.connectionMode)
            putExtra(PhoneMicService.EXTRA_MIC, state.micMode)
            putExtra(PhoneMicService.EXTRA_GAIN, state.gain)
            putExtra(PhoneMicService.EXTRA_QUALITY, state.audioQuality.id)
            putExtra(PhoneMicService.EXTRA_SAMPLE_RATE, state.sampleRateHz)
            putExtra(PhoneMicService.EXTRA_AUDIO_FORMAT, state.audioFormat.id)
            putExtra(PhoneMicService.EXTRA_CHANNELS, state.channels)
            putExtra(PhoneMicService.EXTRA_PREFERRED_MIC_ID, state.preferredMicId)
            putExtra(PhoneMicService.EXTRA_AUTO_RECONNECT, state.autoReconnectEnabled)
            putExtra(PhoneMicService.EXTRA_PTT_MODE, state.pushToTalkEnabled)
            putExtra(PhoneMicService.EXTRA_PTT_PRESSED, state.isPttPressed)
            putExtra(PhoneMicService.EXTRA_VISUALIZER_ENABLED, state.visualizerEnabled)
        }

        try {
            ContextCompat.startForegroundService(context, intent)
            _uiState.update { it.copy(statusMessage = "Connecting to $ip:$port…") }
        } catch (e: Exception) {
            _uiState.update { it.copy(statusMessage = "Unable to start stream: ${e.message}") }
        }
    }

    fun stopStreaming(context: Context) {
        autoStartTriggered = true
        if (serviceBound && phoneMicService != null) {
            phoneMicService?.requestStop()
        } else {
            val intent = Intent(context, PhoneMicService::class.java).apply {
                action = PhoneMicService.ACTION_STOP
            }
            context.startService(intent)
        }
        stopElapsedTicker()
        _audioDb.value = -60f
        _visualizerSnapshot.value = VisualizerSnapshot()
        _uiState.update {
            it.copy(
                isRunning = false,
                isPaused = false,
                isConnected = false,
                isPttPressed = false,
                statusMessage = "Streaming stopped",
                audioLevel = 0f,
                audioDb = -60f,
                elapsedSeconds = 0L,
                packetRate = 0f
            )
        }
    }

    fun togglePause() {
        val service = phoneMicService ?: return
        if (!service.isRunning()) return

        if (service.isPaused()) {
            service.resumeStreaming()
        } else {
            service.pauseStreaming()
        }
    }

    fun scanForPc(context: Context) {
        if (_uiState.value.isScanningPc) return

        val port = _uiState.value.port.toIntOrNull() ?: 5001
        val preferUsb = _uiState.value.connectionMode == PhoneMicService.CONNECTION_USB

        _uiState.update {
            it.copy(
                isScanningPc = true,
                scanFeedback = "Sending discovery query PMD0 to network…"
            )
        }

        ReceiverDiscovery.find(
            context,
            port,
            preferUsb,
            object : ReceiverDiscovery.Callback {
                override fun onFound(ip: String) {
                    _uiState.update { current ->
                        val isUsb = current.connectionMode == PhoneMicService.CONNECTION_USB
                        if (isUsb) {
                            current.copy(
                                isScanningPc = false,
                                ip = ip,
                                usbIp = ip,
                                scanFeedback = "Found PhoneMic Receiver at $ip (USB)"
                            )
                        } else {
                            current.copy(
                                isScanningPc = false,
                                ip = ip,
                                wifiIp = ip,
                                scanFeedback = "Found PhoneMic Receiver at $ip (Wi-Fi)"
                            )
                        }
                    }
                    savePreferences()
                }

                override fun onFailed(reason: String) {
                    _uiState.update {
                        it.copy(
                            isScanningPc = false,
                            scanFeedback = reason
                        )
                    }
                }
            }
        )
    }

    private fun startElapsedTicker() {
        if (!elapsedTickerRunning) {
            elapsedTickerRunning = true
            uiHandler.post(elapsedTicker)
        }
    }

    private fun stopElapsedTicker() {
        elapsedTickerRunning = false
        uiHandler.removeCallbacks(elapsedTicker)
    }

    private fun savePreferences() {
        val state = _uiState.value
        prefs.edit()
            .putString(PREF_IP, state.ip)
            .putString(PREF_WIFI_IP, state.wifiIp)
            .putString(PREF_USB_IP, state.usbIp)
            .putString(PREF_PORT, state.port)
            .putString(PREF_TRANSPORT, state.transportMode)
            .putString(PREF_CONNECTION, state.connectionMode)
            .putString(PREF_MIC, state.micMode)
            .putFloat(PREF_GAIN, state.gain)
            .putString(PREF_AUDIO_QUALITY, state.audioQuality.id)
            .putInt(PREF_SAMPLE_RATE, state.sampleRateHz)
            .putString(PREF_AUDIO_FORMAT, state.audioFormat.id)
            .putInt(PREF_CHANNELS, state.channels)
            .putInt(PREF_PREFERRED_MIC_ID, state.preferredMicId)
            .putBoolean(PREF_AUTO_START, state.autoStartStreaming)
            .putBoolean(PREF_PUSH_TO_TALK, state.pushToTalkEnabled)
            .putBoolean(PREF_AUTO_RECONNECT, state.autoReconnectEnabled)
            .putBoolean(PREF_VISUALIZER_ENABLED, state.visualizerEnabled)
            .putString(PREF_VISUALIZER_STYLE, state.visualizerStyle.id)
            .putBoolean(PREF_DARK_MODE, state.isDarkMode)
            .putBoolean(PREF_OLED_BLACK, state.oledBlackEnabled)
            .putString(PREF_PALETTE_STYLE, state.paletteStyle.id)
            .putLong(PREF_CUSTOM_THEME_COLOR, state.customThemeColorArgb)
            .putString(PREF_HORIZONTAL_NAV_MODE, state.horizontalNavMode.id)
            .putBoolean(PREF_KEEP_SCREEN_AWAKE, state.keepScreenAwake)
            .putBoolean(PREF_OVERLAY, state.isOverlayEnabled)
            .apply()
    }

    override fun onStateChanged(running: Boolean, paused: Boolean, connected: Boolean, message: String) {
        _uiState.update {
            it.copy(
                isRunning = running,
                isPaused = paused,
                isConnected = connected,
                isPttPressed = if (running) it.isPttPressed else false,
                statusMessage = if (!running && message == "Idle") "Ready to connect" else message
            )
        }

        if (running) {
            startElapsedTicker()
        } else {
            stopElapsedTicker()
            _audioDb.value = -60f
            _visualizerSnapshot.value = VisualizerSnapshot()
            _uiState.update {
                it.copy(
                    audioLevel = 0f,
                    audioDb = -60f,
                    elapsedSeconds = 0L,
                    packetRate = 0f
                )
            }
        }
    }

    override fun onAudioLevel(normalizedLevel: Float, peakDb: Float) {
        _audioDb.value = peakDb
    }

    override fun onVisualizerData(snapshot: VisualizerSnapshot) {
        _visualizerSnapshot.value = snapshot
    }

    override fun onTelemetry(packetsSent: Long, bytesSent: Long, packetRate: Float, packetsDropped: Long) {
        _uiState.update {
            it.copy(
                packetsSent = packetsSent,
                packetsDropped = packetsDropped,
                bytesSent = bytesSent,
                packetRate = packetRate
            )
        }
    }

    override fun onCleared() {
        stopElapsedTicker()
        try {
            val am = getApplication<Application>().getSystemService(Context.AUDIO_SERVICE) as? AudioManager
            am?.unregisterAudioDeviceCallback(audioDeviceCallback)
        } catch (_: Exception) {}
        super.onCleared()
    }
}
