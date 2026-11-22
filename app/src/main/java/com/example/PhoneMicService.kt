package com.example

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.net.wifi.WifiManager
import android.os.Binder
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import android.util.Log
import androidx.core.content.ContextCompat
import com.example.audio.AudioChannelOption
import com.example.audio.AudioFormatOption
import com.example.audio.AudioFrameProcessor
import com.example.audio.AudioProtocol
import com.example.audio.VisualizerSnapshot
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.io.IOException
import java.io.OutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketException
import java.net.SocketTimeoutException
import java.util.Arrays
import java.util.Locale
import java.util.concurrent.CopyOnWriteArrayList
import kotlin.math.max

class PhoneMicService : Service() {

    interface Listener {
        fun onStateChanged(running: Boolean, paused: Boolean, connected: Boolean, message: String)
        fun onAudioLevel(normalizedLevel: Float, peakDb: Float)
        fun onTelemetry(packetsSent: Long, bytesSent: Long, packetRate: Float, packetsDropped: Long = 0L)
        fun onVisualizerData(snapshot: VisualizerSnapshot) {}
    }

    companion object {
        const val CONNECTION_USB = "USB"
        const val CONNECTION_WIFI = "Wi-Fi"
        const val TRANSPORT_TCP = "TCP"
        const val TRANSPORT_UDP = "UDP"

        const val ACTION_START = "com.example.phonemic.START"
        const val ACTION_STOP = "com.example.phonemic.STOP"
        const val ACTION_PAUSE = "com.example.phonemic.PAUSE"
        const val ACTION_RESUME = "com.example.phonemic.RESUME"
        const val ACTION_TOGGLE_PAUSE = "com.example.phonemic.TOGGLE_PAUSE"

        const val EXTRA_IP = "ip"
        const val EXTRA_PORT = "port"
        const val EXTRA_TRANSPORT = "transport"
        const val EXTRA_CONNECTION = "connection"
        const val EXTRA_MIC = "mic"
        const val EXTRA_GAIN = "gain"
        const val EXTRA_QUALITY = "quality"
        const val EXTRA_SAMPLE_RATE = "sample_rate"
        const val EXTRA_AUDIO_FORMAT = "audio_format"
        const val EXTRA_CHANNELS = "channels"
        const val EXTRA_PREFERRED_MIC_ID = "preferred_mic_id"
        const val EXTRA_AUTO_RECONNECT = "auto_reconnect"
        const val EXTRA_PTT_MODE = "ptt_mode"
        const val EXTRA_PTT_PRESSED = "ptt_pressed"
        const val EXTRA_VISUALIZER_ENABLED = "visualizer_enabled"

        const val QUALITY_STUDIO_48K = "48K"
        const val QUALITY_BALANCED_24K = "24K"
        const val QUALITY_LOW_16K = "16K"

        enum class AudioQuality(
            val id: String,
            val sampleRate: Int,
            val frameSamples: Int,
            val magicTag: Byte,
            val label: String,
            val desc: String,
            val estBandwidth: String
        ) {
            STUDIO_48K("48K", 48000, 480, '1'.code.toByte(), "Studio 48 kHz", "Full Audio Fidelity & Dynamics", "~768 kbps"),
            BALANCED_24K("24K", 24000, 240, '2'.code.toByte(), "Balanced 24 kHz", "Clear Voice, 50% Bandwidth", "~384 kbps"),
            LOW_BANDWIDTH_16K("16K", 16000, 160, '3'.code.toByte(), "Economy 16 kHz", "Low Data for Weak/Mobile Wi-Fi", "~256 kbps");

            val packetSize: Int get() = frameSamples * 2

            companion object {
                fun fromId(id: String?): AudioQuality =
                    entries.firstOrNull { it.id.equals(id, ignoreCase = true) } ?: STUDIO_48K
            }
        }

        const val MIC_STANDARD = "MIC"
        const val MIC_CALL = "VOICE_COMMUNICATION"
        const val MIC_UNPROCESSED = "UNPROCESSED"
        const val MIC_RAW = "VOICE_RECOGNITION"
        const val MIC_CAMCORDER = "CAMCORDER"

        private const val SAMPLE_RATE = 48000
        private const val PACKET_SIZE = 960

        private const val CHANNEL_ID = "PhoneMic"
        private const val NOTIFICATION_ID = 1001
        private const val CONNECT_TIMEOUT_MS = 5000
        private const val TAG = "PhoneMic"

        private const val CMD_PAUSE = "PMP1"
        private const val CMD_RESUME = "PMR1"

        data class ServiceSnapshot(
            val running: Boolean = false,
            val paused: Boolean = false,
            val connected: Boolean = false,
            val message: String = "Idle"
        )

        private val _serviceSnapshot = MutableStateFlow(ServiceSnapshot())
        val serviceSnapshot: StateFlow<ServiceSnapshot> = _serviceSnapshot

        private val _audioLevelFlow = MutableStateFlow(0f)
        val audioLevelFlow: StateFlow<Float> = _audioLevelFlow
    }

    private val binder = LocalBinder()
    private val listeners = CopyOnWriteArrayList<Listener>()
    private val mainHandler = Handler(Looper.getMainLooper())
    private val frameProcessor = AudioFrameProcessor()

    private var recorder: AudioRecord? = null
    private var audioThread: Thread? = null

    @Volatile private var tcpSocket: Socket? = null
    @Volatile private var udpSocket: DatagramSocket? = null

    private var wifiLock: WifiManager.WifiLock? = null
    private var wakeLock: PowerManager.WakeLock? = null

    @Volatile private var running = false
    @Volatile private var paused = false
    @Volatile private var connected = false
    @Volatile private var stopRequested = false
    @Volatile private var stateMessage = "Idle"
    @Volatile private var connectedLabel = "Connected"
    @Volatile private var generation = 0
    @Volatile private var streamingStartedAt = 0L
    @Volatile private var gain = 1.0f

    @Volatile private var autoReconnect = false
    @Volatile private var pttMode = false
    @Volatile private var pttPressed = false
    @Volatile private var visualizerEnabled = true

    @Volatile private var totalPacketsSent = 0L
    @Volatile private var totalBytesSent = 0L
    @Volatile private var totalPacketsDropped = 0L

    private var lastLevelReportTime = 0L
    private var lastTelemetryReportTime = 0L

    private var currentQuality = AudioQuality.STUDIO_48K
    private var actualSampleRate = SAMPLE_RATE
    private var actualChannels = AudioChannelOption.MONO
    private var actualFormat = AudioFormatOption.PCM_16BIT
    private var useExtendedPm04 = false
    private var needsResampling44k = false

    inner class LocalBinder : Binder() {
        val service: PhoneMicService
            get() = this@PhoneMicService
    }

    override fun onBind(intent: Intent?): IBinder = binder

    fun getStreamingStartedAt(): Long = streamingStartedAt
    fun isRunning(): Boolean = running
    fun isPaused(): Boolean = paused
    fun isConnected(): Boolean = connected
    fun getStateMessage(): String = stateMessage
    fun getGain(): Float = gain
    fun getTotalPackets(): Long = totalPacketsSent
    fun getTotalBytes(): Long = totalBytesSent

    fun setGain(newGain: Float) {
        gain = newGain.coerceIn(0.5f, 4.0f)
    }

    fun setPushToTalkConfig(enabled: Boolean, pressed: Boolean) {
        pttMode = enabled
        pttPressed = pressed
        if (running && pttMode && !paused) {
            if (pttPressed) {
                setState(connected, "PTT Transmitting")
            } else {
                setState(connected, "PTT Ready (Hold to Talk)")
                reportAudioLevel(0f, -60f, null)
            }
        }
    }

    fun setAutoReconnect(enabled: Boolean) {
        autoReconnect = enabled
    }

    fun setVisualizerEnabled(enabled: Boolean) {
        visualizerEnabled = enabled
    }

    // ========================================================
    // LISTENERS
    // ========================================================

    fun registerListener(listener: Listener) {
        listeners.add(listener)
        val r = running
        val p = paused
        val c = connected
        val m = stateMessage
        val pkts = totalPacketsSent
        val b = totalBytesSent
        val dropped = totalPacketsDropped
        mainHandler.post {
            listener.onStateChanged(r, p, c, m)
            listener.onTelemetry(pkts, b, if (r && !p) 100.0f else 0f, dropped)
        }
    }

    fun unregisterListener(listener: Listener) {
        listeners.remove(listener)
    }

    private fun sendState() {
        val r = running
        val p = paused
        val c = connected
        val m = stateMessage
        _serviceSnapshot.value = ServiceSnapshot(r, p, c, m)
        mainHandler.post {
            for (listener in listeners) {
                listener.onStateChanged(r, p, c, m)
            }
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            try {
                android.service.quicksettings.TileService.requestListeningState(
                    this@PhoneMicService,
                    android.content.ComponentName(this@PhoneMicService, PhoneMicTileService::class.java)
                )
            } catch (_: Exception) {}
        }
    }

    private fun reportAudioLevel(level: Float, db: Float, snapshot: VisualizerSnapshot? = null) {
        _audioLevelFlow.value = level
        val now = SystemClock.uptimeMillis()
        if (now - lastLevelReportTime < 80) {
            return
        }
        lastLevelReportTime = now
        val snapToPost = snapshot ?: if (visualizerEnabled) VisualizerSnapshot(level = level, peakDb = db) else null
        mainHandler.post {
            for (listener in listeners) {
                listener.onAudioLevel(level, db)
                if (snapToPost != null) {
                    listener.onVisualizerData(snapToPost)
                }
            }
        }
    }

    private fun reportTelemetry(packets: Long, bytes: Long, rate: Float, dropped: Long = totalPacketsDropped) {
        val now = SystemClock.uptimeMillis()
        if (now - lastTelemetryReportTime < 500) {
            return
        }
        lastTelemetryReportTime = now
        mainHandler.post {
            for (listener in listeners) {
                listener.onTelemetry(packets, bytes, rate, dropped)
            }
        }
    }

    private fun setState(conn: Boolean, text: String) {
        connected = conn
        stateMessage = text
        if (conn) {
            connectedLabel = text
        }
        sendState()
        updateNotification(text)
    }

    // ========================================================
    // LIFECYCLE
    // ========================================================

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onDestroy() {
        stopStreaming()
        super.onDestroy()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) {
            return START_NOT_STICKY
        }

        val action = intent.action
        if (ACTION_STOP == action) {
            requestStop()
            return START_NOT_STICKY
        }
        if (ACTION_PAUSE == action) {
            pauseStreaming()
            return START_NOT_STICKY
        }
        if (ACTION_RESUME == action) {
            resumeStreaming()
            return START_NOT_STICKY
        }
        if (ACTION_TOGGLE_PAUSE == action) {
            if (paused) resumeStreaming() else pauseStreaming()
            return START_NOT_STICKY
        }

        if (ACTION_START == action) {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED
            ) {
                failStart("Microphone permission required")
                return START_NOT_STICKY
            }

            startForegroundCompat(createNotification(stateMessage))

            val ip = intent.getStringExtra(EXTRA_IP)?.trim() ?: ""
            val port = intent.getIntExtra(EXTRA_PORT, 5001)
            val transport = intent.getStringExtra(EXTRA_TRANSPORT) ?: TRANSPORT_UDP
            val connection = intent.getStringExtra(EXTRA_CONNECTION) ?: CONNECTION_WIFI
            val mic = intent.getStringExtra(EXTRA_MIC) ?: MIC_STANDARD
            val qualityStr = intent.getStringExtra(EXTRA_QUALITY) ?: QUALITY_STUDIO_48K
            val quality = AudioQuality.fromId(qualityStr)
            val requestedRate = intent.getIntExtra(EXTRA_SAMPLE_RATE, quality.sampleRate)
            val requestedFmt = AudioFormatOption.fromId(intent.getStringExtra(EXTRA_AUDIO_FORMAT))
            val requestedCh = AudioChannelOption.fromCount(intent.getIntExtra(EXTRA_CHANNELS, 1))
            val preferredMicId = intent.getIntExtra(EXTRA_PREFERRED_MIC_ID, -1)
            autoReconnect = intent.getBooleanExtra(EXTRA_AUTO_RECONNECT, false)
            pttMode = intent.getBooleanExtra(EXTRA_PTT_MODE, false)
            pttPressed = intent.getBooleanExtra(EXTRA_PTT_PRESSED, false)
            visualizerEnabled = intent.getBooleanExtra(EXTRA_VISUALIZER_ENABLED, true)
            gain = intent.getFloatExtra(EXTRA_GAIN, 1.0f).coerceIn(0.5f, 4.0f)

            startStreaming(
                ip = ip,
                port = port,
                transport = transport,
                connection = connection,
                micMode = mic,
                quality = quality,
                requestedRate = requestedRate,
                requestedFormat = requestedFmt,
                requestedChannels = requestedCh,
                preferredMicId = preferredMicId
            )
        }

        return START_NOT_STICKY
    }

    fun requestStop() {
        stopStreaming()
        stopForegroundCompat()
        stopSelf()
    }

    fun pauseStreaming() {
        if (running) {
            paused = true
            setState(false, "Paused")
            reportAudioLevel(0f, -60f, null)
        }
    }

    fun resumeStreaming() {
        if (running) {
            paused = false
            val msg = if (pttMode && !pttPressed) "PTT Ready (Hold to Talk)" else if (connected) connectedLabel else "Streaming"
            setState(connected, msg)
        }
    }

    // ========================================================
    // RECORDER INITIALIZATION & RESAMPLING
    // ========================================================

    private fun applyPreferredMicDevice(rec: AudioRecord, preferredMicId: Int) {
        if (preferredMicId < 0) return
        try {
            val am = getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return
            val targetDevice = am.getDevices(AudioManager.GET_DEVICES_INPUTS)
                .firstOrNull { it.isSource && it.id == preferredMicId }
            if (targetDevice != null) {
                val ok = rec.setPreferredDevice(targetDevice)
                Log.i(TAG, "setPreferredDevice(id=$preferredMicId, type=${targetDevice.type}) -> $ok")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed setPreferredDevice: ${e.message}")
        }
    }

    private fun buildRateFallbackList(requestedRate: Int): IntArray {
        return intArrayOf(requestedRate, 48000, 44100, 16000).distinct().toIntArray()
    }

    private fun createAudioRecorder(
        requestedSource: Int,
        preferredMicId: Int,
        targetRate: Int,
        targetChannels: AudioChannelOption,
        targetFormat: AudioFormatOption
    ): AudioRecord? {
        val sampleRates = buildRateFallbackList(targetRate)
        val formats = if (targetFormat == AudioFormatOption.PCM_16BIT) {
            listOf(AudioFormatOption.PCM_16BIT)
        } else {
            listOf(targetFormat, AudioFormatOption.PCM_16BIT)
        }
        val channels = if (targetChannels == AudioChannelOption.MONO) {
            listOf(AudioChannelOption.MONO)
        } else {
            listOf(targetChannels, AudioChannelOption.MONO)
        }
        val sourcesToTry = intArrayOf(
            requestedSource,
            MediaRecorder.AudioSource.MIC,
            MediaRecorder.AudioSource.DEFAULT
        ).distinct().toIntArray()

        for (fmt in formats) {
            if (!fmt.isSupportedOnDevice) continue
            for (ch in channels) {
                for (rate in sampleRates) {
                    val minBuffer = AudioRecord.getMinBufferSize(
                        rate,
                        ch.androidMask,
                        fmt.toAndroidEncoding()
                    )
                    if (minBuffer <= 0) continue

                    val frameBytes = AudioProtocol.framePayloadBytes(rate, ch.count, fmt)
                    val bufferSize = max(minBuffer * 2, frameBytes * 4)

                    for (source in sourcesToTry) {
                        try {
                            val rec = AudioRecord(
                                source,
                                rate,
                                ch.androidMask,
                                fmt.toAndroidEncoding(),
                                bufferSize
                            )
                            if (rec.state == AudioRecord.STATE_INITIALIZED) {
                                applyPreferredMicDevice(rec, preferredMicId)
                                actualSampleRate = rate
                                actualChannels = ch
                                actualFormat = fmt
                                val wantsLegacy48k = targetRate == 48000 &&
                                    targetChannels == AudioChannelOption.MONO &&
                                    targetFormat == AudioFormatOption.PCM_16BIT
                                needsResampling44k = wantsLegacy48k &&
                                    rate == 44100 &&
                                    ch == AudioChannelOption.MONO &&
                                    fmt == AudioFormatOption.PCM_16BIT
                                val effectiveRate = if (needsResampling44k) 48000 else rate
                                useExtendedPm04 = !AudioProtocol.isLegacyStandardStream(
                                    effectiveRate,
                                    ch.count,
                                    fmt
                                )
                                Log.i(
                                    TAG,
                                    "AudioRecord initialized: source=$source, mic=$preferredMicId, rate=$rate, ch=${ch.count}, fmt=${fmt.id}, pm04=$useExtendedPm04, bufferSize=$bufferSize"
                                )
                                return rec
                            } else {
                                rec.release()
                            }
                        } catch (e: Exception) {
                            Log.w(TAG, "Failed AudioRecord source=$source rate=$rate ch=${ch.count} fmt=${fmt.id}: ${e.message}")
                        }
                    }
                }
            }
        }
        return null
    }

    private fun resample441To480(src: ByteArray, dst: ByteArray) {
        val step = 440f / 479f
        for (i in 0 until 480) {
            val pos = i * step
            val idx = pos.toInt()
            val frac = pos - idx
            val s1 = getSample16(src, idx)
            val s2 = if (idx + 1 < 441) getSample16(src, idx + 1) else s1
            val interp = (s1 + (s2 - s1) * frac).toInt().coerceIn(-32768, 32767)
            setSample16(dst, i, interp)
        }
    }

    private fun getSample16(buf: ByteArray, sampleIdx: Int): Int {
        val byteIdx = sampleIdx * 2
        if (byteIdx + 1 >= buf.size) return 0
        val low = buf[byteIdx].toInt() and 0xFF
        val high = buf[byteIdx + 1].toInt()
        var s = (high shl 8) or low
        if (s > 32767) s -= 65536
        return s
    }

    private fun setSample16(buf: ByteArray, sampleIdx: Int, value: Int) {
        val byteIdx = sampleIdx * 2
        if (byteIdx + 1 >= buf.size) return
        buf[byteIdx] = (value and 0xFF).toByte()
        buf[byteIdx + 1] = ((value shr 8) and 0xFF).toByte()
    }

    // ========================================================
    // STREAM START / STOP & AUTO-RECONNECT LOOP
    // ========================================================

    @Synchronized
    private fun startStreaming(
        ip: String,
        port: Int,
        transport: String,
        connection: String,
        micMode: String,
        quality: AudioQuality = AudioQuality.STUDIO_48K,
        requestedRate: Int = quality.sampleRate,
        requestedFormat: AudioFormatOption = AudioFormatOption.PCM_16BIT,
        requestedChannels: AudioChannelOption = AudioChannelOption.MONO,
        preferredMicId: Int = -1
    ) {
        if (running) return

        currentQuality = quality

        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            failStart("Microphone permission denied")
            return
        }

        stopRequested = false

        val micSource = AudioProtocol.resolveAudioSource(micMode)
        recorder = createAudioRecorder(micSource, preferredMicId, requestedRate, requestedChannels, requestedFormat)

        val rec = recorder
        if (rec == null || rec.state != AudioRecord.STATE_INITIALIZED) {
            rec?.release()
            recorder = null
            failStart("Could not initialize microphone on this device")
            return
        }

        val streamRate = if (needsResampling44k) 48000 else actualSampleRate
        currentQuality = when (streamRate) {
            16000 -> AudioQuality.LOW_BANDWIDTH_16K
            24000 -> AudioQuality.BALANCED_24K
            else -> AudioQuality.STUDIO_48K
        }

        running = true
        paused = false
        connected = false
        connectedLabel = "Connected"
        stateMessage = "Connecting..."
        streamingStartedAt = SystemClock.elapsedRealtime()
        totalPacketsSent = 0L
        totalBytesSent = 0L
        totalPacketsDropped = 0L
        lastTelemetryReportTime = 0L
        sendState()

        val bindWifi = CONNECTION_WIFI == connection
        val useUdp = TRANSPORT_UDP == transport
        val myGeneration = ++generation
        val cleanIp = ip.trim()

        audioThread = Thread({
            try {
                Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_AUDIO)
            } catch (_: Exception) {}
            acquireLocks(bindWifi)
            try {
                var attempt = 0
                var backoffMs = 1000L
                while (running && !stopRequested && myGeneration == generation) {
                    val attemptStarted = SystemClock.elapsedRealtime()
                    if (recorder == null || recorder?.state != AudioRecord.STATE_INITIALIZED) {
                        recorder = createAudioRecorder(
                            micSource,
                            preferredMicId,
                            requestedRate,
                            requestedChannels,
                            requestedFormat
                        )
                    }
                    val activeRec = recorder
                    if (activeRec == null || activeRec.state != AudioRecord.STATE_INITIALIZED) {
                        handleStreamError(IOException("Microphone unavailable"), myGeneration)
                        break
                    }

                    val cleanExit = if (useUdp) {
                        udpLoop(cleanIp, port, myGeneration, micSource, preferredMicId)
                    } else {
                        tcpLoop(cleanIp, port, myGeneration, micSource, preferredMicId)
                    }

                    if (cleanExit || !autoReconnect || stopRequested || myGeneration != generation) {
                        break
                    }

                    if (SystemClock.elapsedRealtime() - attemptStarted > 5000L) {
                        backoffMs = 1000L
                        attempt = 0
                    }
                    attempt++
                    totalPacketsDropped++
                    val waitSec = max(1, (backoffMs / 1000L).toInt())
                    setState(false, "Reconnecting in ${waitSec}s (#$attempt)…")
                    var slept = 0L
                    while (running && !stopRequested && myGeneration == generation && slept < backoffMs) {
                        try {
                            Thread.sleep(100L)
                        } catch (_: InterruptedException) {
                            break
                        }
                        slept += 100L
                    }
                    backoffMs = (backoffMs * 2L).coerceAtMost(10_000L)
                }
            } finally {
                releaseLocks()
                onStreamThreadExit(myGeneration)
            }
        }, "PhoneMic-Stream")
        audioThread?.start()
    }

    private fun failStart(reason: String) {
        stateMessage = reason
        sendState()
        updateNotification(reason)
        stopForegroundCompat()
        stopSelf()
    }

    private fun stopStreaming() {
        val t: Thread?
        synchronized(this) {
            stopRequested = true
            running = false
            paused = false
            connected = false
            stateMessage = "Stopped"
            streamingStartedAt = 0L
            sendState()
            reportAudioLevel(0f, -60f, VisualizerSnapshot())
            reportTelemetry(totalPacketsSent, totalBytesSent, 0f)

            try { tcpSocket?.close() } catch (_: Exception) {}
            tcpSocket = null
            try { udpSocket?.close() } catch (_: Exception) {}
            udpSocket = null
            try { recorder?.stop() } catch (_: Exception) {}

            t = audioThread
            audioThread = null
        }

        if (t != null) {
            t.interrupt()
            try { t.join(1000) } catch (_: InterruptedException) {}
        }

        synchronized(this) {
            cleanupRecorder()
            releaseLocks()
        }
    }

    private fun onStreamThreadExit(myGeneration: Int) {
        synchronized(this) {
            if (myGeneration != generation) {
                cleanupRecorder()
                return
            }
            running = false
            connected = false
            paused = false
            streamingStartedAt = 0L
            reportAudioLevel(0f, -60f, VisualizerSnapshot())
            reportTelemetry(totalPacketsSent, totalBytesSent, 0f)

            if (!stopRequested && myGeneration == generation) {
                val hasDetailedError = stateMessage.startsWith("Connection failed") || stateMessage == "Stopped"
                if (!hasDetailedError && stateMessage != "Connecting...") {
                    stateMessage = "Disconnected"
                }
                sendState()
                updateNotification(stateMessage)
            }
            cleanupRecorder()
        }
    }

    private fun cleanupRecorder() {
        try {
            recorder?.release()
        } catch (_: Exception) {}
        recorder = null
    }

    private fun recoverSilentRecorder(preferredMicId: Int, frameBytes: Int) {
        try {
            recorder?.stop()
            recorder?.release()
            val recBufSize = max(frameBytes * 4, AudioRecord.getMinBufferSize(
                actualSampleRate,
                actualChannels.androidMask,
                actualFormat.toAndroidEncoding()
            ) * 2)
            val newRec = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                actualSampleRate,
                actualChannels.androidMask,
                actualFormat.toAndroidEncoding(),
                recBufSize
            )
            if (newRec.state == AudioRecord.STATE_INITIALIZED) {
                applyPreferredMicDevice(newRec, preferredMicId)
                recorder = newRec
                newRec.startRecording()
            } else {
                newRec.release()
            }
        } catch (_: Exception) {}
    }

    private fun effectiveStreamRate(): Int = if (needsResampling44k) 48000 else actualSampleRate

    private fun effectivePayloadSize(): Int =
        if (needsResampling44k) PACKET_SIZE
        else AudioProtocol.framePayloadBytes(actualSampleRate, actualChannels.count, actualFormat)

    private fun isEffectivelyMuted(): Boolean = paused || (pttMode && !pttPressed)

    // ========================================================
    // TCP
    // ========================================================

    private fun tcpLoop(
        ip: String,
        port: Int,
        myGeneration: Int,
        micSource: Int,
        preferredMicId: Int
    ): Boolean {
        var socket: Socket? = null
        try {
            socket = Socket()
            tcpSocket = socket
            socket.tcpNoDelay = true
            socket.connect(InetSocketAddress(ip, port), CONNECT_TIMEOUT_MS)

            val out: OutputStream = socket.getOutputStream()
            val input = socket.getInputStream()

            val rec = recorder ?: throw IOException("AudioRecord not initialized")
            try {
                if (rec.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
                    rec.startRecording()
                }
            } catch (e: Exception) {
                Log.w(TAG, "TCP startRecording retry: ${e.message}")
            }

            val connStatus = if (pttMode && !pttPressed) "PTT Ready (Hold to Talk)" else "Connected (TCP)"
            setState(true, connStatus)

            val ctrlThread = Thread({
                val cmdBuf = ByteArray(4)
                while (running && !stopRequested && !socket.isClosed && myGeneration == generation) {
                    try {
                        var totalRead = 0
                        while (totalRead < 4) {
                            val count = input.read(cmdBuf, totalRead, 4 - totalRead)
                            if (count < 0) break
                            totalRead += count
                        }
                        if (totalRead == 4) {
                            val cmdStr = String(cmdBuf, Charsets.US_ASCII)
                            if (cmdStr == CMD_PAUSE) {
                                mainHandler.post { pauseStreaming() }
                            } else if (cmdStr == CMD_RESUME) {
                                mainHandler.post { resumeStreaming() }
                            }
                        } else {
                            break
                        }
                    } catch (_: Exception) {
                        break
                    }
                }
            }, "PhoneMic-TcpControl")
            ctrlThread.isDaemon = true
            ctrlThread.start()

            val streamRate = effectiveStreamRate()
            val payloadSize = effectivePayloadSize()
            val headerSize = if (useExtendedPm04) AudioProtocol.PM04_HEADER_SIZE else 0
            val raw44k = if (needsResampling44k) ByteArray(882) else ByteArray(0)
            val data = ByteArray(payloadSize)
            val packet = if (headerSize > 0) ByteArray(headerSize + payloadSize) else ByteArray(0)
            val silence = ByteArray(payloadSize)
            AudioProtocol.fillSilence(silence, actualFormat)

            var sequence = 0
            var packetsInWindow = 0
            var windowStart = SystemClock.uptimeMillis()
            var consecutiveSilence = 0

            while (running && !stopRequested && !socket.isClosed && myGeneration == generation) {
                val activeMuted = isEffectivelyMuted()
                if (activeMuted) {
                    consecutiveSilence = 0
                    // Flush stale samples while muted/PTT released by reading or sending silence rhythmically
                    val writeLen = if (useExtendedPm04) {
                        AudioProtocol.writePm04Header(
                            packet, sequence++, streamRate, actualChannels.count, actualFormat.code
                        )
                        System.arraycopy(silence, 0, packet, AudioProtocol.PM04_HEADER_SIZE, silence.size)
                        out.write(packet, 0, packet.size)
                        packet.size
                    } else {
                        out.write(silence, 0, silence.size)
                        silence.size
                    }
                    totalPacketsSent++
                    totalBytesSent += writeLen
                    reportAudioLevel(0f, -60f, null)
                    reportTelemetry(totalPacketsSent, totalBytesSent, 0f)
                    sleepPacketMs()
                    continue
                }

                val currentRec = recorder ?: break
                val read: Int
                if (needsResampling44k) {
                    var total44k = 0
                    while (total44k < raw44k.size && running && !stopRequested) {
                        val count = currentRec.read(raw44k, total44k, raw44k.size - total44k)
                        if (count <= 0) break
                        total44k += count
                    }
                    if (total44k == raw44k.size) {
                        resample441To480(raw44k, data)
                        read = PACKET_SIZE
                    } else {
                        read = total44k
                    }
                } else {
                    read = currentRec.read(data, 0, data.size)
                }

                if (read > 0) {
                    val snap = frameProcessor.processFrame(
                        data = data,
                        length = read,
                        format = actualFormat,
                        channels = actualChannels.count,
                        gain = gain,
                        buildVisualizer = visualizerEnabled && (SystemClock.uptimeMillis() - lastLevelReportTime >= 75)
                    )
                    val level = frameProcessor.lastLevel
                    val db = frameProcessor.lastDb
                    reportAudioLevel(level, db, snap)

                    if (level == 0f) {
                        consecutiveSilence++
                        if (consecutiveSilence == 40) {
                            Log.w(TAG, "Silence detected in TCP stream, recovering recorder")
                            recoverSilentRecorder(preferredMicId, payloadSize)
                        }
                    } else {
                        consecutiveSilence = 0
                    }

                    if (socket.isClosed || stopRequested || !running) break
                    val sentLen = if (useExtendedPm04) {
                        AudioProtocol.writePm04Header(
                            packet, sequence++, streamRate, actualChannels.count, actualFormat.code
                        )
                        System.arraycopy(data, 0, packet, AudioProtocol.PM04_HEADER_SIZE, read)
                        if (read < payloadSize) {
                            Arrays.fill(packet, AudioProtocol.PM04_HEADER_SIZE + read, packet.size, 0.toByte())
                        }
                        out.write(packet, 0, packet.size)
                        packet.size
                    } else {
                        out.write(data, 0, read)
                        read
                    }

                    totalPacketsSent++
                    totalBytesSent += sentLen
                    packetsInWindow++

                    val now = SystemClock.uptimeMillis()
                    val elapsed = now - windowStart
                    if (elapsed >= 500) {
                        val rate = (packetsInWindow * 1000f) / elapsed
                        reportTelemetry(totalPacketsSent, totalBytesSent, rate)
                        packetsInWindow = 0
                        windowStart = now
                    }
                } else if (read < 0) {
                    if (stopRequested || !running || myGeneration != generation) break
                    throw IOException("AudioRecord error $read")
                } else {
                    totalPacketsDropped++
                    sleepPacketMs()
                }
            }
            return true
        } catch (e: Exception) {
            return handleStreamError(e, myGeneration)
        } finally {
            tcpSocket = null
            try { socket?.close() } catch (_: Exception) {}
        }
    }

    // ========================================================
    // UDP
    // ========================================================

    private fun udpLoop(
        ip: String,
        port: Int,
        myGeneration: Int,
        micSource: Int,
        preferredMicId: Int
    ): Boolean {
        var socket: DatagramSocket? = null
        try {
            socket = DatagramSocket()
            socket.soTimeout = 100
            udpSocket = socket

            val address = InetAddress.getByName(ip)

            val rec = recorder ?: throw IOException("AudioRecord not initialized")
            try {
                if (rec.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
                    rec.startRecording()
                }
            } catch (e: Exception) {
                Log.w(TAG, "UDP startRecording retry: ${e.message}")
            }

            val connStatus = if (pttMode && !pttPressed) "PTT Ready (Hold to Talk)" else "Sending (UDP)"
            setState(true, connStatus)
            Log.i(TAG, "Starting UDP stream to $address:$port (pm04=$useExtendedPm04, rate=${effectiveStreamRate()}, ch=${actualChannels.count}, fmt=${actualFormat.id})")

            val ctrlThread = Thread({
                val cmdBuf = ByteArray(64)
                val cmdPacket = DatagramPacket(cmdBuf, cmdBuf.size)
                while (running && !stopRequested && !socket.isClosed && myGeneration == generation) {
                    try {
                        socket.receive(cmdPacket)
                        if (cmdPacket.address != address) continue
                        if (cmdPacket.length >= 4) {
                            val cmdStr = String(cmdBuf, 0, 4, Charsets.US_ASCII)
                            if (cmdStr == CMD_PAUSE) {
                                mainHandler.post { pauseStreaming() }
                            } else if (cmdStr == CMD_RESUME) {
                                mainHandler.post { resumeStreaming() }
                            }
                        }
                    } catch (_: SocketTimeoutException) {
                    } catch (_: SocketException) {
                        break
                    } catch (_: Exception) {
                        if (!running || stopRequested || socket.isClosed || myGeneration != generation) break
                    }
                }
            }, "PhoneMic-UdpControl")
            ctrlThread.isDaemon = true
            ctrlThread.start()

            val streamRate = effectiveStreamRate()
            val payloadSize = effectivePayloadSize()
            val headerSize = if (useExtendedPm04) AudioProtocol.PM04_HEADER_SIZE else AudioProtocol.LEGACY_HEADER_SIZE
            val raw44k = if (needsResampling44k) ByteArray(882) else ByteArray(0)
            val audio = ByteArray(payloadSize)
            val packet = ByteArray(headerSize + payloadSize)
            val silence = ByteArray(payloadSize)
            AudioProtocol.fillSilence(silence, actualFormat)
            val legacyTag = AudioProtocol.legacyMagicTagForRate(streamRate)

            var sequence = 0
            var packetsInWindow = 0
            var windowStart = SystemClock.uptimeMillis()
            var consecutiveSilence = 0

            val udpPacket = DatagramPacket(packet, packet.size, address, port)

            while (running && !stopRequested && !socket.isClosed && myGeneration == generation) {
                val activeMuted = isEffectivelyMuted()
                if (activeMuted) {
                    consecutiveSilence = 0
                    writeUdpHeader(packet, sequence++, streamRate, legacyTag)
                    System.arraycopy(silence, 0, packet, headerSize, silence.size)
                    if (socket.isClosed || stopRequested || !running) break
                    try {
                        socket.send(udpPacket)
                    } catch (se: SocketException) {
                        if (stopRequested || !running || socket.isClosed || myGeneration != generation) break
                        throw se
                    }
                    totalPacketsSent++
                    totalBytesSent += packet.size
                    reportAudioLevel(0f, -60f, null)
                    reportTelemetry(totalPacketsSent, totalBytesSent, 0f)
                    sleepPacketMs()
                    continue
                }

                val currentRec = recorder ?: break
                val read: Int
                if (needsResampling44k) {
                    var total44k = 0
                    while (total44k < raw44k.size && running && !stopRequested) {
                        val count = currentRec.read(raw44k, total44k, raw44k.size - total44k)
                        if (count <= 0) break
                        total44k += count
                    }
                    if (total44k == raw44k.size) {
                        resample441To480(raw44k, audio)
                        read = PACKET_SIZE
                    } else {
                        read = total44k
                    }
                } else {
                    read = currentRec.read(audio, 0, audio.size)
                }

                if (read < 0) {
                    if (stopRequested || !running || myGeneration != generation) break
                    throw IOException("AudioRecord error $read")
                }
                if (read == 0) {
                    totalPacketsDropped++
                    sleepPacketMs()
                    continue
                }

                val snap = frameProcessor.processFrame(
                    data = audio,
                    length = read,
                    format = actualFormat,
                    channels = actualChannels.count,
                    gain = gain,
                    buildVisualizer = visualizerEnabled && (SystemClock.uptimeMillis() - lastLevelReportTime >= 75)
                )
                val level = frameProcessor.lastLevel
                val db = frameProcessor.lastDb
                reportAudioLevel(level, db, snap)

                if (level == 0f) {
                    consecutiveSilence++
                    if (consecutiveSilence == 40) {
                        Log.w(TAG, "Silence detected in UDP stream, recovering recorder")
                        recoverSilentRecorder(preferredMicId, payloadSize)
                    }
                } else {
                    consecutiveSilence = 0
                }

                writeUdpHeader(packet, sequence++, streamRate, legacyTag)
                System.arraycopy(audio, 0, packet, headerSize, read)
                if (read < payloadSize) {
                    Arrays.fill(packet, headerSize + read, packet.size, 0.toByte())
                }
                if (socket.isClosed || stopRequested || !running) break
                try {
                    socket.send(udpPacket)
                } catch (se: SocketException) {
                    if (stopRequested || !running || socket.isClosed || myGeneration != generation) break
                    throw se
                }
                totalPacketsSent++
                totalBytesSent += packet.size
                packetsInWindow++

                val now = SystemClock.uptimeMillis()
                val elapsed = now - windowStart
                if (elapsed >= 500) {
                    val rate = (packetsInWindow * 1000f) / elapsed
                    reportTelemetry(totalPacketsSent, totalBytesSent, rate)
                    packetsInWindow = 0
                    windowStart = now
                }
            }
            return true
        } catch (e: Exception) {
            return handleStreamError(e, myGeneration)
        } finally {
            udpSocket = null
            try { socket?.close() } catch (_: Exception) {}
        }
    }

    private fun writeUdpHeader(packet: ByteArray, seq: Int, streamRate: Int, legacyTag: Byte) {
        if (useExtendedPm04) {
            AudioProtocol.writePm04Header(packet, seq, streamRate, actualChannels.count, actualFormat.code)
        } else {
            AudioProtocol.writeLegacyHeader(packet, seq, legacyTag)
        }
    }

    /** Returns true if exit was intentional/clean (do NOT auto-reconnect), false if retryable failure. */
    private fun handleStreamError(e: Exception, myGeneration: Int): Boolean {
        val msg = e.message?.lowercase(Locale.ROOT) ?: ""
        val isSocketClosed = e is SocketException && (
            msg.contains("closed") ||
                msg.contains("interrupted") ||
                msg.contains("pipe") ||
                msg.contains("reset")
            )
        val isInterrupted = e is InterruptedException || Thread.currentThread().isInterrupted

        if (stopRequested || !running || myGeneration != generation || isInterrupted) {
            Log.d(TAG, "Stream ended gracefully: ${e.javaClass.simpleName} ($msg)")
            return true
        }

        if (autoReconnect) {
            Log.w(TAG, "Transient stream failure (auto-reconnect active): ${e.message}")
            return false
        }

        if (isSocketClosed) {
            Log.i(TAG, "Stream socket closed: $msg")
            stateMessage = "Disconnected"
            sendState()
            updateNotification(stateMessage)
            return true
        }

        Log.e(TAG, "Stream error", e)
        val detail = e.message
        stateMessage = "Connection failed" + if (detail != null) ": $detail" else ""
        sendState()
        updateNotification(stateMessage)
        return true
    }

    private fun sleepPacketMs() {
        try {
            Thread.sleep(10)
        } catch (_: InterruptedException) {}
    }

    // ========================================================
    // POWER LOCKS & NOTIFICATION
    // ========================================================

    private fun acquireLocks(wifi: Boolean) {
        val pm = getSystemService(PowerManager::class.java)
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "PhoneMic:stream")
            wakeLock?.setReferenceCounted(false)
            wakeLock?.acquire(24 * 60 * 60 * 1000L)
        }
        if (wifi) {
            val wm = applicationContext.getSystemService(WIFI_SERVICE) as? WifiManager
            if (wm != null) {
                val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    WifiManager.WIFI_MODE_FULL_LOW_LATENCY
                } else {
                    @Suppress("DEPRECATION")
                    WifiManager.WIFI_MODE_FULL_HIGH_PERF
                }
                wifiLock = wm.createWifiLock(mode, "PhoneMic:wifi")
                wifiLock?.setReferenceCounted(false)
                wifiLock?.acquire()
            }
        }
    }

    private fun releaseLocks() {
        try { if (wakeLock?.isHeld == true) wakeLock?.release() } catch (_: Exception) {}
        wakeLock = null
        try { if (wifiLock?.isHeld == true) wifiLock?.release() } catch (_: Exception) {}
        wifiLock = null
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "PhoneMic Streaming",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Active microphone streaming session"
            }
            getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
        }
    }

    private fun createNotification(text: String): Notification {
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val openPendingIntent = PendingIntent.getActivity(
            this,
            0,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopPendingIntent = PendingIntent.getService(
            this,
            1,
            Intent(this, PhoneMicService::class.java).apply { action = ACTION_STOP },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val pauseResumePendingIntent = PendingIntent.getService(
            this,
            2,
            Intent(this, PhoneMicService::class.java).apply { action = ACTION_TOGGLE_PAUSE },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val pauseActionTitle = if (paused) getString(R.string.btn_resume) else getString(R.string.btn_pause)
        val pauseActionIcon = if (paused) android.R.drawable.ic_media_play else android.R.drawable.ic_media_pause

        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }

        return builder
            .setContentTitle("PhoneMic Live Stream")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentIntent(openPendingIntent)
            .setOngoing(true)
            .addAction(pauseActionIcon, pauseActionTitle, pauseResumePendingIntent)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, getString(R.string.btn_stop), stopPendingIntent)
            .build()
    }

    private fun updateNotification(text: String) {
        try {
            getSystemService(NotificationManager::class.java)?.notify(NOTIFICATION_ID, createNotification(text))
        } catch (_: Exception) {}
    }

    private fun startForegroundCompat(notification: Notification) {
        try {
            val hasMic = ContextCompat.checkSelfPermission(
                this,
                android.Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && hasMic) {
                startForeground(
                    NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
                )
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Foreground service start failed", e)
        }
    }

    private fun stopForegroundCompat() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            stopForeground(STOP_FOREGROUND_REMOVE)
        } else {
            @Suppress("DEPRECATION")
            stopForeground(true)
        }
    }
}
