package com.example.audio

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.MediaRecorder
import android.os.Build
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.log10
import kotlin.math.sin
import kotlin.math.sqrt

enum class AudioFormatOption(
    val id: String,
    val code: Int,
    val bytesPerSample: Int,
    val minApi: Int,
    val label: String,
    val shortLabel: String
) {
    PCM_16BIT("PCM_16", 0, 2, Build.VERSION_CODES.N, "PCM 16-bit", "16-bit"),
    PCM_8BIT("PCM_8", 1, 1, Build.VERSION_CODES.N, "PCM 8-bit", "8-bit"),
    PCM_24BIT("PCM_24", 2, 3, Build.VERSION_CODES.S, "PCM 24-bit", "24-bit"),
    PCM_FLOAT("PCM_FLOAT", 3, 4, Build.VERSION_CODES.N, "PCM Float 32-bit", "Float 32");

    fun toAndroidEncoding(): Int = when (this) {
        PCM_16BIT -> AudioFormat.ENCODING_PCM_16BIT
        PCM_8BIT -> AudioFormat.ENCODING_PCM_8BIT
        PCM_24BIT -> if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            AudioFormat.ENCODING_PCM_24BIT_PACKED
        } else {
            AudioFormat.ENCODING_PCM_16BIT
        }
        PCM_FLOAT -> AudioFormat.ENCODING_PCM_FLOAT
    }

    val isSupportedOnDevice: Boolean
        get() = Build.VERSION.SDK_INT >= minApi

    companion object {
        fun fromId(id: String?): AudioFormatOption =
            entries.firstOrNull { it.id.equals(id, ignoreCase = true) } ?: PCM_16BIT

        fun fromCode(code: Int): AudioFormatOption =
            entries.firstOrNull { it.code == code } ?: PCM_16BIT
    }
}

enum class AudioChannelOption(
    val id: String,
    val count: Int,
    val androidMask: Int,
    val label: String,
    val shortLabel: String
) {
    MONO("MONO", 1, AudioFormat.CHANNEL_IN_MONO, "Mono (1 ch)", "Mono"),
    STEREO("STEREO", 2, AudioFormat.CHANNEL_IN_STEREO, "Stereo (2 ch)", "Stereo");

    companion object {
        fun fromCount(count: Int): AudioChannelOption = if (count == 2) STEREO else MONO
    }
}

enum class VisualizerStyle(
    val id: String,
    val label: String,
    val description: String
) {
    WAVEFORM("WAVEFORM", "Waveform", "Real-time oscilloscope trace"),
    SPECTRUM_BARS("SPECTRUM_BARS", "Spectrum Bars", "Multi-band harmonic frequency bars"),
    VU_METER("VU_METER", "VU Meter", "Precision peak-hold studio bar"),
    CIRCULAR_PULSE("CIRCULAR_PULSE", "Circular Pulse", "Reactive concentric energy rings");

    companion object {
        fun fromId(id: String?): VisualizerStyle =
            entries.firstOrNull { it.id.equals(id, ignoreCase = true) } ?: WAVEFORM
    }
}

enum class MicDeviceKind {
    DEFAULT,
    BUILTIN,
    WIRED,
    USB,
    BLUETOOTH
}

data class InputMicDevice(
    val id: Int,
    val name: String,
    val typeLabel: String,
    val kind: MicDeviceKind,
    val isSystemDefault: Boolean = false
)

data class VisualizerSnapshot(
    val level: Float = 0f,
    val peakDb: Float = -60f,
    val waveform: FloatArray = FloatArray(32),
    val spectrum: FloatArray = FloatArray(16)
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is VisualizerSnapshot) return false
        return level == other.level &&
            peakDb == other.peakDb &&
            waveform.contentEquals(other.waveform) &&
            spectrum.contentEquals(other.spectrum)
    }

    override fun hashCode(): Int {
        var result = level.hashCode()
        result = 31 * result + peakDb.hashCode()
        result = 31 * result + waveform.contentHashCode()
        result = 31 * result + spectrum.contentHashCode()
        return result
    }
}

object AudioProtocol {
    val SUPPORTED_SAMPLE_RATES = listOf(8000, 16000, 24000, 32000, 44100, 48000)

    const val PM04_HEADER_SIZE = 16
    const val LEGACY_HEADER_SIZE = 8

    fun isLegacyStandardStream(
        sampleRate: Int,
        channels: Int,
        format: AudioFormatOption
    ): Boolean {
        return channels == 1 &&
            format == AudioFormatOption.PCM_16BIT &&
            (sampleRate == 48000 || sampleRate == 24000 || sampleRate == 16000)
    }

    fun frameSamples(sampleRate: Int): Int = ((sampleRate * 10) / 1000).coerceAtLeast(1)

    fun framePayloadBytes(sampleRate: Int, channels: Int, format: AudioFormatOption): Int {
        val ch = if (channels == 2) 2 else 1
        return frameSamples(sampleRate) * ch * format.bytesPerSample
    }

    fun estimatedKbps(sampleRate: Int, channels: Int, format: AudioFormatOption): Int {
        val ch = if (channels == 2) 2 else 1
        return (sampleRate * ch * format.bytesPerSample * 8) / 1000
    }

    fun legacyMagicTagForRate(sampleRate: Int): Byte = when (sampleRate) {
        16000 -> '3'.code.toByte()
        24000 -> '2'.code.toByte()
        else -> '1'.code.toByte()
    }

    /** Zero-allocation big-endian 'PM01'/'PM02'/'PM03' + seq header writer. */
    fun writeLegacyHeader(packet: ByteArray, seq: Int, tag: Byte) {
        packet[0] = 'P'.code.toByte()
        packet[1] = 'M'.code.toByte()
        packet[2] = '0'.code.toByte()
        packet[3] = tag
        packet[4] = ((seq ushr 24) and 0xFF).toByte()
        packet[5] = ((seq ushr 16) and 0xFF).toByte()
        packet[6] = ((seq ushr 8) and 0xFF).toByte()
        packet[7] = (seq and 0xFF).toByte()
    }

    /** Zero-allocation big-endian 16-byte 'PM04' header writer. */
    fun writePm04Header(
        packet: ByteArray,
        seq: Int,
        sampleRate: Int,
        channels: Int,
        formatCode: Int,
        flags: Int = 0
    ) {
        packet[0] = 'P'.code.toByte()
        packet[1] = 'M'.code.toByte()
        packet[2] = '0'.code.toByte()
        packet[3] = '4'.code.toByte()
        packet[4] = ((seq ushr 24) and 0xFF).toByte()
        packet[5] = ((seq ushr 16) and 0xFF).toByte()
        packet[6] = ((seq ushr 8) and 0xFF).toByte()
        packet[7] = (seq and 0xFF).toByte()
        packet[8] = ((sampleRate ushr 24) and 0xFF).toByte()
        packet[9] = ((sampleRate ushr 16) and 0xFF).toByte()
        packet[10] = ((sampleRate ushr 8) and 0xFF).toByte()
        packet[11] = (sampleRate and 0xFF).toByte()
        packet[12] = (channels and 0xFF).toByte()
        packet[13] = (formatCode and 0xFF).toByte()
        packet[14] = ((flags ushr 8) and 0xFF).toByte()
        packet[15] = (flags and 0xFF).toByte()
    }

    fun fillSilence(buf: ByteArray, format: AudioFormatOption) {
        val fillByte: Byte = if (format == AudioFormatOption.PCM_8BIT) 0x80.toByte() else 0
        buf.fill(fillByte)
    }

    fun resolveAudioSource(mode: String): Int = when (mode) {
        "UNPROCESSED" -> if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            MediaRecorder.AudioSource.UNPROCESSED
        } else {
            MediaRecorder.AudioSource.MIC
        }
        "VOICE_RECOGNITION" -> MediaRecorder.AudioSource.VOICE_RECOGNITION
        "CAMCORDER" -> MediaRecorder.AudioSource.CAMCORDER
        "VOICE_COMMUNICATION" -> MediaRecorder.AudioSource.VOICE_COMMUNICATION
        else -> MediaRecorder.AudioSource.MIC
    }

    fun queryInputMicDevices(context: Context): List<InputMicDevice> {
        val result = ArrayList<InputMicDevice>()
        result.add(
            InputMicDevice(
                id = -1,
                name = "System Default",
                typeLabel = "Automatic Selection",
                kind = MicDeviceKind.DEFAULT,
                isSystemDefault = true
            )
        )
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return result
        val devices = try {
            audioManager.getDevices(AudioManager.GET_DEVICES_INPUTS)
        } catch (_: Exception) {
            emptyArray<AudioDeviceInfo>()
        }

        val seenBuiltinAddresses = HashSet<String>()
        var builtinIndex = 0
        for (dev in devices) {
            if (!dev.isSource) continue
            val type = dev.type
            val (kind, baseLabel) = when (type) {
                AudioDeviceInfo.TYPE_BUILTIN_MIC -> MicDeviceKind.BUILTIN to "Built-in Mic"
                AudioDeviceInfo.TYPE_WIRED_HEADSET,
                AudioDeviceInfo.TYPE_WIRED_HEADPHONES -> MicDeviceKind.WIRED to "Wired Headset Mic"
                AudioDeviceInfo.TYPE_USB_DEVICE,
                AudioDeviceInfo.TYPE_USB_HEADSET,
                AudioDeviceInfo.TYPE_USB_ACCESSORY -> MicDeviceKind.USB to "USB Audio Mic"
                AudioDeviceInfo.TYPE_BLUETOOTH_SCO -> MicDeviceKind.BLUETOOTH to "Bluetooth Mic (SCO)"
                AudioDeviceInfo.TYPE_BLE_HEADSET -> MicDeviceKind.BLUETOOTH to "Bluetooth LE Mic"
                AudioDeviceInfo.TYPE_LINE_ANALOG,
                AudioDeviceInfo.TYPE_LINE_DIGITAL,
                AudioDeviceInfo.TYPE_AUX_LINE -> MicDeviceKind.WIRED to "Line Input"
                else -> continue
            }

            val rawAddress = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                dev.address?.trim().orEmpty()
            } else {
                ""
            }
            val product = dev.productName?.toString()?.trim().orEmpty()
            val displayName = when {
                kind == MicDeviceKind.BUILTIN -> {
                    builtinIndex++
                    val loc = when {
                        rawAddress.contains("bottom", ignoreCase = true) -> "Bottom"
                        rawAddress.contains("top", ignoreCase = true) -> "Top"
                        rawAddress.contains("back", ignoreCase = true) ||
                            rawAddress.contains("rear", ignoreCase = true) -> "Back"
                        rawAddress.contains("front", ignoreCase = true) -> "Front"
                        rawAddress.isNotEmpty() && seenBuiltinAddresses.add(rawAddress) -> rawAddress
                        builtinIndex == 1 -> "Primary"
                        else -> "#$builtinIndex"
                    }
                    "Phone Mic ($loc)"
                }
                product.isNotEmpty() && !product.equals(Build.MODEL, ignoreCase = true) -> product
                else -> baseLabel
            }

            result.add(
                InputMicDevice(
                    id = dev.id,
                    name = displayName,
                    typeLabel = baseLabel,
                    kind = kind,
                    isSystemDefault = false
                )
            )
        }
        return result
    }
}

/**
 * Reusable zero-GC frame gain processor & visualizer analyzer.
 * Designed for real-time audio threads without allocating heap arrays per packet.
 */
class AudioFrameProcessor {
    private val waveBins = FloatArray(32)
    private val spectrumBins = FloatArray(16)
    private val waveCounts = IntArray(32)

    // Precomputed 16x32 cosine/sine bank for fast Goertzel-like spectral bins from 32-point frame
    private val cosTable = Array(16) { k ->
        val freq = k + 1
        FloatArray(32) { n -> cos(2.0 * PI * freq * n / 32.0).toFloat() }
    }
    private val sinTable = Array(16) { k ->
        val freq = k + 1
        FloatArray(32) { n -> sin(2.0 * PI * freq * n / 32.0).toFloat() }
    }

    var lastLevel: Float = 0f
        private set
    var lastDb: Float = -60f
        private set

    fun processFrame(
        data: ByteArray,
        length: Int,
        format: AudioFormatOption,
        channels: Int,
        gain: Float,
        buildVisualizer: Boolean
    ): VisualizerSnapshot? {
        val bps = format.bytesPerSample
        val ch = if (channels == 2) 2 else 1
        val frameStride = bps * ch
        val totalFrames = length / frameStride
        if (totalFrames <= 0) {
            lastLevel = 0f
            lastDb = -60f
            return if (buildVisualizer) VisualizerSnapshot() else null
        }

        val applyGain = abs(gain - 1.0f) > 0.05f
        var maxAbs = 0f

        if (buildVisualizer) {
            waveBins.fill(0f)
            waveCounts.fill(0)
        }

        var byteOff = 0
        for (frameIdx in 0 until totalFrames) {
            var monoSample = 0f
            for (c in 0 until ch) {
                var norm: Float
                when (format) {
                    AudioFormatOption.PCM_16BIT -> {
                        val lo = data[byteOff].toInt() and 0xFF
                        val hi = data[byteOff + 1].toInt()
                        var s = (hi shl 8) or lo
                        if (s > 32767) s -= 65536
                        if (applyGain) {
                            s = (s * gain).toInt().coerceIn(-32768, 32767)
                            data[byteOff] = (s and 0xFF).toByte()
                            data[byteOff + 1] = ((s shr 8) and 0xFF).toByte()
                        }
                        norm = s / 32768f
                    }
                    AudioFormatOption.PCM_8BIT -> {
                        val u = data[byteOff].toInt() and 0xFF
                        var centered = u - 128
                        if (applyGain) {
                            centered = (centered * gain).toInt().coerceIn(-128, 127)
                            data[byteOff] = (centered + 128).coerceIn(0, 255).toByte()
                        }
                        norm = centered / 128f
                    }
                    AudioFormatOption.PCM_24BIT -> {
                        val b0 = data[byteOff].toInt() and 0xFF
                        val b1 = data[byteOff + 1].toInt() and 0xFF
                        val b2 = data[byteOff + 2].toInt() // signed top byte
                        var s = (b2 shl 16) or (b1 shl 8) or b0
                        if (applyGain) {
                            s = (s * gain).toInt().coerceIn(-8388608, 8388607)
                            data[byteOff] = (s and 0xFF).toByte()
                            data[byteOff + 1] = ((s ushr 8) and 0xFF).toByte()
                            data[byteOff + 2] = ((s ushr 16) and 0xFF).toByte()
                        }
                        norm = s / 8388608f
                    }
                    AudioFormatOption.PCM_FLOAT -> {
                        val bits = (data[byteOff].toInt() and 0xFF) or
                            ((data[byteOff + 1].toInt() and 0xFF) shl 8) or
                            ((data[byteOff + 2].toInt() and 0xFF) shl 16) or
                            ((data[byteOff + 3].toInt() and 0xFF) shl 24)
                        var f = java.lang.Float.intBitsToFloat(bits)
                        if (!f.isFinite()) f = 0f
                        if (applyGain) {
                            f = (f * gain).coerceIn(-1.0f, 1.0f)
                            val outBits = java.lang.Float.floatToRawIntBits(f)
                            data[byteOff] = (outBits and 0xFF).toByte()
                            data[byteOff + 1] = ((outBits ushr 8) and 0xFF).toByte()
                            data[byteOff + 2] = ((outBits ushr 16) and 0xFF).toByte()
                            data[byteOff + 3] = ((outBits ushr 24) and 0xFF).toByte()
                        }
                        norm = f.coerceIn(-1.0f, 1.0f)
                    }
                }
                val absNorm = abs(norm)
                if (absNorm > maxAbs) maxAbs = absNorm
                monoSample += norm
                byteOff += bps
            }

            if (buildVisualizer) {
                val avgMono = monoSample / ch
                val bucket = (frameIdx * 32) / totalFrames
                if (bucket in 0..31) {
                    waveBins[bucket] += avgMono
                    waveCounts[bucket]++
                }
            }
        }

        val level = maxAbs.coerceIn(0f, 1f)
        val db = if (level > 1e-4f) (20.0 * log10(level.toDouble())).toFloat().coerceIn(-60f, 0f) else -60f
        lastLevel = level
        lastDb = db

        if (!buildVisualizer) return null

        for (i in 0 until 32) {
            val c = waveCounts[i]
            waveBins[i] = if (c > 0) (waveBins[i] / c).coerceIn(-1f, 1f) else 0f
        }

        for (k in 0 until 16) {
            var re = 0f
            var im = 0f
            val cosK = cosTable[k]
            val sinK = sinTable[k]
            for (n in 0 until 32) {
                val x = waveBins[n]
                re += x * cosK[n]
                im -= x * sinK[n]
            }
            val mag = (sqrt(re * re + im * im) / 8f).coerceIn(0f, 1f)
            // Smooth attack/decay across frames
            spectrumBins[k] = maxOf(mag, spectrumBins[k] * 0.65f)
        }

        return VisualizerSnapshot(
            level = level,
            peakDb = db,
            waveform = waveBins.copyOf(),
            spectrum = spectrumBins.copyOf()
        )
    }
}
