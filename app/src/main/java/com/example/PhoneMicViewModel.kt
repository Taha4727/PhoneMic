package com.example

import android.app.Application
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.SharedPreferences
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.regex.Pattern

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
    val isIgnoringBatteryOptimizations: Boolean = true,
    // Stream telemetry matched with Windows Receiver v0.6.5
    val packetsSent: Long = 0L,
    val bytesSent: Long = 0L,
    val packetRate: Float = 0f,
    val receiverVersion: String = "Windows Receiver v0.6.5",
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

        private val IPV4_PATTERN = Pattern.compile(
            "^((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)\\.){3}(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)$"
        )
    }

    private val prefs: SharedPreferences = application.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val _uiState = MutableStateFlow(loadInitialState())
    val uiState: StateFlow<PhoneMicUiState> = _uiState.asStateFlow()

    // Isolated high-frequency audio peak level flow:
    // Prevents recomposing the entire screen 12x/sec during streaming on budget devices like Galaxy A10s!
    private val _audioDb = MutableStateFlow(-60f)
    val audioDb: StateFlow<Float> = _audioDb.asStateFlow()

    private var phoneMicService: PhoneMicService? = null
    private var serviceBound = false

    private val uiHandler = Handler(Looper.getMainLooper())
    private var elapsedTickerRunning = false

    private val elapsedTicker = object : Runnable {
        override fun run() {
            val startedAt = phoneMicService?.getStreamingStartedAt() ?: 0L
            if (startedAt > 0L) {
                val sec = Math.max(0L, (SystemClock.elapsedRealtime() - startedAt) / 1000L)
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
            phoneMicService?.registerListener(this@PhoneMicViewModel)

            val service = phoneMicService
            if (service != null && service.isRunning()) {
                startElapsedTicker()
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            serviceBound = false
            phoneMicService = null
            stopElapsedTicker()
            _uiState.update {
                it.copy(
                    isRunning = false,
                    isPaused = false,
                    isConnected = false,
                    statusMessage = "Service disconnected",
                    audioLevel = 0f,
                    audioDb = -60f,
                    elapsedSeconds = 0L,
                    packetsSent = 0L,
                    bytesSent = 0L,
                    packetRate = 0f
                )
            }
        }
    }

    init {
        // Defer service binding to Activity.onStart to prevent cold launch freeze
        checkBatteryOptimization()
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

        val activeIp = if (savedConnection == PhoneMicService.CONNECTION_USB) savedUsbIp else savedWifiIp

        return PhoneMicUiState(
            ip = activeIp,
            wifiIp = savedWifiIp,
            usbIp = savedUsbIp,
            port = savedPort,
            connectionMode = savedConnection,
            transportMode = savedTransport,
            micMode = savedMic,
            gain = savedGain
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

    fun checkBatteryOptimization() {
        val pm = getApplication<Application>().getSystemService(PowerManager::class.java)
        val pkg = getApplication<Application>().packageName
        val isIgnored = pm?.isIgnoringBatteryOptimizations(pkg) ?: true
        _uiState.update { it.copy(isIgnoringBatteryOptimizations = isIgnored) }
    }

    fun setIp(newIp: String) {
        val cleanIp = newIp.trim()
        _uiState.update { current ->
            if (current.connectionMode == PhoneMicService.CONNECTION_USB) {
                current.copy(ip = cleanIp, usbIp = cleanIp, scanFeedback = null)
            } else {
                current.copy(ip = cleanIp, wifiIp = cleanIp, scanFeedback = null)
            }
        }
        savePreferences()
    }

    fun setPort(newPort: String) {
        _uiState.update { it.copy(port = newPort.trim()) }
        savePreferences()
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

    fun setGain(newGain: Float) {
        _uiState.update { it.copy(gain = newGain) }
        phoneMicService?.setGain(newGain)
        savePreferences()
    }

    fun setGuideDialogVisible(visible: Boolean) {
        _uiState.update { it.copy(showGuideDialog = visible) }
    }

    fun isValidIp(ip: String): Boolean {
        return IPV4_PATTERN.matcher(ip).matches()
    }

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
        }

        try {
            ContextCompat.startForegroundService(context, intent)
            _uiState.update { it.copy(statusMessage = "Connecting to $ip:$port…") }
        } catch (e: Exception) {
            _uiState.update { it.copy(statusMessage = "Unable to start stream: ${e.message}") }
        }
    }

    fun stopStreaming(context: Context) {
        if (serviceBound && phoneMicService != null) {
            phoneMicService?.requestStop()
        } else {
            val intent = Intent(context, PhoneMicService::class.java).apply {
                action = PhoneMicService.ACTION_STOP
            }
            context.startService(intent)
        }
        stopElapsedTicker()
        _uiState.update {
            it.copy(
                isRunning = false,
                isPaused = false,
                isConnected = false,
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
            .apply()
    }

    override fun onStateChanged(running: Boolean, paused: Boolean, connected: Boolean, message: String) {
        _uiState.update {
            it.copy(
                isRunning = running,
                isPaused = paused,
                isConnected = connected,
                statusMessage = if (!running && message == "Idle") "Ready to connect" else message
            )
        }

        if (running) {
            startElapsedTicker()
        } else {
            stopElapsedTicker()
            _audioDb.value = -60f
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
        // High-frequency stream level: only update the isolated StateFlow!
        // Does not trigger recomposition of the main screen or text fields!
        _audioDb.value = peakDb
    }

    override fun onTelemetry(packetsSent: Long, bytesSent: Long, packetRate: Float) {
        _uiState.update {
            it.copy(
                packetsSent = packetsSent,
                bytesSent = bytesSent,
                packetRate = packetRate
            )
        }
    }

    override fun onCleared() {
        stopElapsedTicker()
        super.onCleared()
    }
}
