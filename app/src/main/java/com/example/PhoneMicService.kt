package com.example

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.net.wifi.WifiManager
import android.os.Binder
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import androidx.core.content.ContextCompat
import java.io.IOException
import java.io.OutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketException
import java.net.SocketTimeoutException
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Arrays
import java.util.Locale
import java.util.concurrent.CopyOnWriteArrayList
import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.max

class PhoneMicService : Service() {

    interface Listener {
        fun onStateChanged(running: Boolean, paused: Boolean, connected: Boolean, message: String)
        fun onAudioLevel(normalizedLevel: Float, peakDb: Float)
        fun onTelemetry(packetsSent: Long, bytesSent: Long, packetRate: Float)
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
                fun fromId(id: String?): AudioQuality = values().firstOrNull { it.id.equals(id, ignoreCase = true) } ?: STUDIO_48K
            }
        }

        const val MIC_STANDARD = "MIC"
        const val MIC_CALL = "VOICE_COMMUNICATION"
        const val MIC_UNPROCESSED = "UNPROCESSED"
        const val MIC_RAW = "VOICE_RECOGNITION"
        const val MIC_CAMCORDER = "CAMCORDER"

        // 480 samples * 2 bytes = 960 bytes = 10 ms at 48 kHz mono 16-bit
        private const val SAMPLE_RATE = 48000
        private const val PACKET_SIZE = 960

        private const val CHANNEL_ID = "PhoneMic"
        private const val NOTIFICATION_ID = 1001
        private const val CONNECT_TIMEOUT_MS = 5000
        private const val TAG = "PhoneMic"

        // Bidirectional remote commands from Windows Receiver
        private const val CMD_PAUSE = "PMP1"
        private const val CMD_RESUME = "PMR1"

        data class ServiceSnapshot(
            val running: Boolean = false,
            val paused: Boolean = false,
            val connected: Boolean = false,
            val message: String = "Idle"
        )

        private val _serviceSnapshot = kotlinx.coroutines.flow.MutableStateFlow(ServiceSnapshot())
        val serviceSnapshot: kotlinx.coroutines.flow.StateFlow<ServiceSnapshot> = _serviceSnapshot

        private val _audioLevelFlow = kotlinx.coroutines.flow.MutableStateFlow(0f)
        val audioLevelFlow: kotlinx.coroutines.flow.StateFlow<Float> = _audioLevelFlow
    }

    private val binder = LocalBinder()
    private val listeners = CopyOnWriteArrayList<Listener>()
    private val mainHandler = Handler(Looper.getMainLooper())

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

    @Volatile private var totalPacketsSent = 0L
    @Volatile private var totalBytesSent = 0L

    // Throttling for UI audio level updates (80ms eliminates frame drops on Android 7.1.1)
    private var lastLevelReportTime = 0L
    private var lastTelemetryReportTime = 0L

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
        mainHandler.post {
            listener.onStateChanged(r, p, c, m)
            listener.onTelemetry(pkts, b, if (r && !p) 100.0f else 0f)
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

    private fun reportAudioLevel(level: Float, db: Float) {
        _audioLevelFlow.value = level
        val now = SystemClock.uptimeMillis()
        if (now - lastLevelReportTime < 80) {
            return
        }
        lastLevelReportTime = now
        mainHandler.post {
            for (listener in listeners) {
                listener.onAudioLevel(level, db)
            }
        }
    }

    private fun reportTelemetry(packets: Long, bytes: Long, rate: Float) {
        val now = SystemClock.uptimeMillis()
        if (now - lastTelemetryReportTime < 500) {
            return
        }
        lastTelemetryReportTime = now
        mainHandler.post {
            for (listener in listeners) {
                listener.onTelemetry(packets, bytes, rate)
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
            gain = intent.getFloatExtra(EXTRA_GAIN, 1.0f).coerceIn(0.5f, 4.0f)
            startStreaming(ip, port, transport, connection, mic, quality)
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
            reportAudioLevel(0f, -60f)
        }
    }

    fun resumeStreaming() {
        if (running) {
            paused = false
            setState(connected, if (connected) connectedLabel else "Streaming")
        }
    }

    // ========================================================
    // STREAM CONTROL
    // ========================================================

    private var currentQuality = AudioQuality.STUDIO_48K
    private var actualSampleRate = SAMPLE_RATE
    private var needsResampling44k = false

    private fun resolveMicSource(mode: String): Int {
        return when (mode) {
            MIC_UNPROCESSED -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                    MediaRecorder.AudioSource.UNPROCESSED
                } else {
                    MediaRecorder.AudioSource.MIC
                }
            }
            MIC_RAW -> MediaRecorder.AudioSource.VOICE_RECOGNITION
            MIC_CAMCORDER -> MediaRecorder.AudioSource.CAMCORDER
            MIC_CALL -> MediaRecorder.AudioSource.VOICE_COMMUNICATION
            MIC_STANDARD -> MediaRecorder.AudioSource.MIC
            else -> MediaRecorder.AudioSource.MIC
        }
    }

    private fun createAudioRecorder(requestedSource: Int, targetRate: Int): AudioRecord? {
        val sampleRates = when (targetRate) {
            16000 -> intArrayOf(16000, 48000)
            24000 -> intArrayOf(24000, 16000, 48000)
            else -> intArrayOf(48000, 44100)
        }
        val sourcesToTry = intArrayOf(
            requestedSource,
            MediaRecorder.AudioSource.MIC,
            MediaRecorder.AudioSource.DEFAULT
        ).distinct().toIntArray()

        val packetBytes = currentQuality.packetSize
        for (rate in sampleRates) {
            val minBuffer = AudioRecord.getMinBufferSize(
                rate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            )
            if (minBuffer <= 0) continue

            val bufferSize = max(minBuffer * 2, packetBytes * 4)

            for (source in sourcesToTry) {
                try {
                    val rec = AudioRecord(
                        source,
                        rate,
                        AudioFormat.CHANNEL_IN_MONO,
                        AudioFormat.ENCODING_PCM_16BIT,
                        bufferSize
                    )
                    if (rec.state == AudioRecord.STATE_INITIALIZED) {
                        actualSampleRate = rate
                        needsResampling44k = (rate == 44100)
                        Log.i(TAG, "AudioRecord initialized: source=$source, rate=$rate, bufferSize=$bufferSize")
                        return rec
                    } else {
                        rec.release()
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "Failed AudioRecord source=$source, rate=$rate: ${e.message}")
                }
            }
        }
        return null
    }


    private fun resample441To480(src: ByteArray, dst: ByteArray) {
        // src has 441 16-bit samples (882 bytes), dst has 480 16-bit samples (960 bytes)
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

    @Synchronized
    private fun startStreaming(
        ip: String,
        port: Int,
        transport: String,
        connection: String,
        micMode: String,
        quality: AudioQuality = AudioQuality.STUDIO_48K
    ) {
        if (running) return

        currentQuality = quality

        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            stateMessage = "Microphone permission denied"
            sendState()
            updateNotification(stateMessage)
            stopForegroundCompat()
            stopSelf()
            return
        }

        stopRequested = false

        val micSource = resolveMicSource(micMode)
        recorder = createAudioRecorder(micSource, quality.sampleRate)

        val rec = recorder
        if (rec == null || rec.state != AudioRecord.STATE_INITIALIZED) {
            rec?.release()
            recorder = null
            failStart("Could not initialize microphone on this device")
            return
        }

        // Align currentQuality to the actual rate that successfully opened
        currentQuality = when (actualSampleRate) {
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
        lastTelemetryReportTime = 0L
        sendState()

        val bindWifi = CONNECTION_WIFI == connection
        val useUdp = TRANSPORT_UDP == transport
        val myGeneration = ++generation

        audioThread = Thread({
            acquireLocks(bindWifi)
            try {
                if (useUdp) {
                    udpLoop(ip.trim(), port, myGeneration)
                } else {
                    tcpLoop(ip.trim(), port, myGeneration)
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
            reportAudioLevel(0f, -60f)
            reportTelemetry(totalPacketsSent, totalBytesSent, 0f)

            try {
                tcpSocket?.close()
            } catch (_: Exception) {}
            tcpSocket = null

            try {
                udpSocket?.close()
            } catch (_: Exception) {}
            udpSocket = null

            try {
                recorder?.stop()
            } catch (_: Exception) {}

            t = audioThread
            audioThread = null
        }

        if (t != null) {
            t.interrupt()
            try {
                t.join(1000)
            } catch (_: InterruptedException) {}
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
            reportAudioLevel(0f, -60f)
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

    // ========================================================
    // AUDIO PROCESSING & LEVEL CALCULATION
    // ========================================================

    private fun processAudioBuffer(data: ByteArray, length: Int, currentGain: Float): Pair<Float, Float> {
        var maxAmplitude = 0
        val applyGain = abs(currentGain - 1.0f) > 0.05f

        for (i in 0 until length - 1 step 2) {
            val low = data[i].toInt() and 0xFF
            val high = data[i + 1].toInt()
            var sample = (high shl 8) or low
            if (sample > 32767) sample -= 65536

            if (applyGain) {
                val amplified = (sample * currentGain).toInt().coerceIn(-32768, 32767)
                data[i] = (amplified and 0xFF).toByte()
                data[i + 1] = ((amplified shr 8) and 0xFF).toByte()
                sample = amplified
            }

            val absSample = abs(sample)
            if (absSample > maxAmplitude) {
                maxAmplitude = absSample
            }
        }

        val normalized = (maxAmplitude / 32767f).coerceIn(0f, 1f)
        val db = if (maxAmplitude > 0) (20.0 * log10(maxAmplitude / 32767.0)).toFloat().coerceIn(-60f, 0f) else -60f
        return Pair(normalized, db)
    }

    // ========================================================
    // TCP
    // ========================================================

    private fun tcpLoop(ip: String, port: Int, myGeneration: Int) {
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

            setState(true, "Connected (TCP)")

            // Remote control listener thread for incoming commands from Windows Receiver
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
                    } catch (_: SocketException) {
                        break
                    } catch (_: Exception) {
                        break
                    }
                }
            }, "PhoneMic-TcpControl")
            ctrlThread.isDaemon = true
            ctrlThread.start()

            val packetSize = currentQuality.packetSize
            val raw44k = if (needsResampling44k) ByteArray(882) else ByteArray(0)
            val data = ByteArray(packetSize)
            val silence = ByteArray(packetSize)
            var packetsInWindow = 0
            var windowStart = SystemClock.uptimeMillis()
            var consecutiveSilence = 0

            while (running && !stopRequested && !socket.isClosed && myGeneration == generation) {
                if (paused) {
                    if (socket.isClosed || stopRequested || !running) break
                    try {
                        out.write(silence)
                    } catch (se: SocketException) {
                        if (stopRequested || !running || socket.isClosed || myGeneration != generation) {
                            break
                        }
                        throw se
                    }
                    totalPacketsSent++
                    totalBytesSent += silence.size
                    reportAudioLevel(0f, -60f)
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
                    val (level, db) = processAudioBuffer(data, read, gain)
                    reportAudioLevel(level, db)

                    if (level == 0f) {
                        consecutiveSilence++
                        if (consecutiveSilence == 40) {
                            Log.w(TAG, "Silence detected in TCP stream, recovering with MIC")
                            try {
                                recorder?.stop()
                                recorder?.release()
                                val recBufSize = currentQuality.packetSize * 4
                                val newRec = AudioRecord(
                                    MediaRecorder.AudioSource.MIC,
                                    actualSampleRate,
                                    AudioFormat.CHANNEL_IN_MONO,
                                    AudioFormat.ENCODING_PCM_16BIT,
                                    recBufSize
                                )
                                if (newRec.state == AudioRecord.STATE_INITIALIZED) {
                                    recorder = newRec
                                    newRec.startRecording()
                                } else {
                                    newRec.release()
                                }
                            } catch (_: Exception) {}
                        }
                    } else {
                        consecutiveSilence = 0
                    }

                    if (socket.isClosed || stopRequested || !running) break
                    try {
                        out.write(data, 0, read)
                    } catch (se: SocketException) {
                        if (stopRequested || !running || socket.isClosed || myGeneration != generation) {
                            break
                        }
                        throw se
                    }
                    totalPacketsSent++
                    totalBytesSent += read
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
                    sleepPacketMs()
                }
            }
        } catch (e: Exception) {
            handleStreamError(e, myGeneration)
        } finally {
            tcpSocket = null
            try {
                socket?.close()
            } catch (_: Exception) {}
        }
    }

    // ========================================================
    // UDP
    // ========================================================

    private fun udpLoop(ip: String, port: Int, myGeneration: Int) {
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

            setState(true, "Sending (UDP)")
            Log.i(TAG, "Starting UDP stream to $address:$port")

            // Remote control listener thread for incoming commands from Windows Receiver
            val ctrlThread = Thread({
                val cmdBuf = ByteArray(64)
                val cmdPacket = DatagramPacket(cmdBuf, cmdBuf.size)
                while (running && !stopRequested && !socket.isClosed && myGeneration == generation) {
                    try {
                        socket.receive(cmdPacket)
                        // B6: Security - only accept remote control commands from the connected receiver IP
                        if (cmdPacket.address != address) {
                            continue
                        }
                        if (cmdPacket.length >= 4) {
                            val cmdStr = String(cmdBuf, 0, 4, Charsets.US_ASCII)
                            if (cmdStr == CMD_PAUSE) {
                                mainHandler.post { pauseStreaming() }
                            } else if (cmdStr == CMD_RESUME) {
                                mainHandler.post { resumeStreaming() }
                            }
                        }
                    } catch (_: SocketTimeoutException) {
                        // Expected: continue looping without locking socket
                    } catch (_: SocketException) {
                        break
                    } catch (_: Exception) {
                        if (!running || stopRequested || socket.isClosed || myGeneration != generation) break
                    }
                }
            }, "PhoneMic-UdpControl")
            ctrlThread.isDaemon = true
            ctrlThread.start()

            val packetSize = currentQuality.packetSize
            val raw44k = if (needsResampling44k) ByteArray(882) else ByteArray(0)
            val audio = ByteArray(packetSize)
            val packet = ByteArray(packetSize + 8)
            val silence = ByteArray(packetSize)
            var sequence = 0
            var packetsInWindow = 0
            var windowStart = SystemClock.uptimeMillis()
            var consecutiveSilence = 0

            // Pre-create DatagramPacket for high performance and zero GC pauses on Android 7.1.1
            val udpPacket = DatagramPacket(packet, packet.size, address, port)

            while (running && !stopRequested && !socket.isClosed && myGeneration == generation) {
                if (paused) {
                    writeHeader(packet, sequence++)
                    System.arraycopy(silence, 0, packet, 8, silence.size)
                    if (socket.isClosed || stopRequested || !running) break
                    try {
                        socket.send(udpPacket)
                    } catch (se: SocketException) {
                        if (stopRequested || !running || socket.isClosed || myGeneration != generation) {
                            break
                        }
                        throw se
                    }
                    totalPacketsSent++
                    totalBytesSent += packet.size
                    reportAudioLevel(0f, -60f)
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
                    sleepPacketMs()
                    continue
                }

                val (level, db) = processAudioBuffer(audio, read, gain)
                reportAudioLevel(level, db)

                if (level == 0f) {
                    consecutiveSilence++
                    if (consecutiveSilence == 40) {
                        Log.w(TAG, "Silence detected in UDP stream, recovering with MIC")
                        try {
                            recorder?.stop()
                            recorder?.release()
                            val recBufSize = currentQuality.packetSize * 4
                            val newRec = AudioRecord(
                                MediaRecorder.AudioSource.MIC,
                                actualSampleRate,
                                AudioFormat.CHANNEL_IN_MONO,
                                AudioFormat.ENCODING_PCM_16BIT,
                                recBufSize
                            )
                            if (newRec.state == AudioRecord.STATE_INITIALIZED) {
                                recorder = newRec
                                newRec.startRecording()
                            } else {
                                newRec.release()
                            }
                        } catch (_: Exception) {}
                    }
                } else {
                    consecutiveSilence = 0
                }

                writeHeader(packet, sequence++)
                System.arraycopy(audio, 0, packet, 8, read)
                if (read < packetSize) {
                    Arrays.fill(packet, 8 + read, packet.size, 0.toByte())
                }
                if (socket.isClosed || stopRequested || !running) {
                    break
                }
                try {
                    socket.send(udpPacket)
                } catch (se: SocketException) {
                    if (stopRequested || !running || socket.isClosed || myGeneration != generation) {
                        break
                    }
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
        } catch (e: Exception) {
            handleStreamError(e, myGeneration)
        } finally {
            udpSocket = null
            try {
                socket?.close()
            } catch (_: Exception) {}
        }
    }

    private fun handleStreamError(e: Exception, myGeneration: Int) {
        val msg = e.message?.lowercase(Locale.ROOT) ?: ""
        val isSocketClosed = e is SocketException && (
            msg.contains("closed") ||
            msg.contains("interrupted") ||
            msg.contains("pipe") ||
            msg.contains("reset")
        )
        val isInterrupted = e is InterruptedException || Thread.currentThread().isInterrupted

        // Clean termination during stop or shutdown should not be logged as a stream error
        if (stopRequested || !running || myGeneration != generation || isInterrupted) {
            Log.d(TAG, "Stream ended gracefully: ${e.javaClass.simpleName} ($msg)")
            return
        }

        // If socket was closed/reset by peer or network drop while stream was active
        if (isSocketClosed) {
            Log.i(TAG, "Stream socket closed: $msg")
            stateMessage = "Disconnected"
            sendState()
            updateNotification(stateMessage)
            return
        }

        Log.e(TAG, "Stream error", e)
        val detail = e.message
        stateMessage = "Connection failed" + if (detail != null) ": $detail" else ""
        sendState()
        updateNotification(stateMessage)
    }

    private fun sleepPacketMs() {
        try {
            Thread.sleep(10)
        } catch (_: InterruptedException) {}
    }

    // Packet layout: 'P','M','0',tag + 4-byte big-endian sequence number
    private fun writeHeader(packet: ByteArray, seq: Int, tag: Byte = currentQuality.magicTag) {
        packet[0] = 'P'.code.toByte()
        packet[1] = 'M'.code.toByte()
        packet[2] = '0'.code.toByte()
        packet[3] = tag
        ByteBuffer.wrap(packet, 4, 4)
            .order(ByteOrder.BIG_ENDIAN)
            .putInt(seq)
    }

    // ========================================================
    // POWER LOCKS
    // ========================================================

    private fun acquireLocks(wifi: Boolean) {
        val pm = getSystemService(PowerManager::class.java)
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "PhoneMic:stream")
            wakeLock?.setReferenceCounted(false)
            wakeLock?.acquire(24 * 60 * 60 * 1000L) // 24h safety limit
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
        try {
            if (wakeLock?.isHeld == true) {
                wakeLock?.release()
            }
        } catch (_: Exception) {}
        wakeLock = null

        try {
            if (wifiLock?.isHeld == true) {
                wifiLock?.release()
            }
        } catch (_: Exception) {}
        wifiLock = null
    }

    // ========================================================
    // NOTIFICATION
    // ========================================================

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "PhoneMic Streaming",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Active microphone streaming session"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
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

        val stopIntent = Intent(this, PhoneMicService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this,
            1,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val pauseResumeIntent = Intent(this, PhoneMicService::class.java).apply {
            action = ACTION_TOGGLE_PAUSE
        }
        val pauseResumePendingIntent = PendingIntent.getService(
            this,
            2,
            pauseResumeIntent,
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
            .addAction(
                pauseActionIcon,
                pauseActionTitle,
                pauseResumePendingIntent
            )
            .addAction(
                android.R.drawable.ic_menu_close_clear_cancel,
                getString(R.string.btn_stop),
                stopPendingIntent
            )
            .build()
    }

    private fun updateNotification(text: String) {
        try {
            val manager = getSystemService(NotificationManager::class.java)
            manager?.notify(NOTIFICATION_ID, createNotification(text))
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
