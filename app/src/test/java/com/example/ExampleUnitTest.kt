package com.example

import com.example.audio.AudioFormatOption
import com.example.audio.AudioFrameProcessor
import com.example.audio.AudioProtocol
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class ExampleUnitTest {
  @Test
  fun addition_isCorrect() {
    assertEquals(4, 2 + 2)
  }

  @Test
  fun appVersion_is140() {
    assertEquals("1.4.0", BuildConfig.VERSION_NAME)
    assertEquals(5, BuildConfig.VERSION_CODE)
  }

  @Test
  fun audioProtocol_legacyVsExtendedRouting() {
    assertTrue(AudioProtocol.isLegacyStandardStream(48000, 1, AudioFormatOption.PCM_16BIT))
    assertTrue(AudioProtocol.isLegacyStandardStream(24000, 1, AudioFormatOption.PCM_16BIT))
    assertTrue(AudioProtocol.isLegacyStandardStream(16000, 1, AudioFormatOption.PCM_16BIT))

    assertFalse(AudioProtocol.isLegacyStandardStream(44100, 1, AudioFormatOption.PCM_16BIT))
    assertFalse(AudioProtocol.isLegacyStandardStream(48000, 2, AudioFormatOption.PCM_16BIT))
    assertFalse(AudioProtocol.isLegacyStandardStream(48000, 1, AudioFormatOption.PCM_8BIT))
    assertFalse(AudioProtocol.isLegacyStandardStream(48000, 1, AudioFormatOption.PCM_FLOAT))
  }

  @Test
  fun audioProtocol_pm04HeaderAndPayloadCalculations() {
    val header = ByteArray(AudioProtocol.PM04_HEADER_SIZE)
    AudioProtocol.writePm04Header(
      packet = header,
      seq = 0x01020304,
      sampleRate = 44100,
      channels = 2,
      formatCode = AudioFormatOption.PCM_FLOAT.code,
      flags = 7
    )

    assertEquals('P'.code.toByte(), header[0])
    assertEquals('M'.code.toByte(), header[1])
    assertEquals('0'.code.toByte(), header[2])
    assertEquals('4'.code.toByte(), header[3])

    val bb = ByteBuffer.wrap(header).order(ByteOrder.BIG_ENDIAN)
    bb.position(4)
    assertEquals(0x01020304, bb.int)
    assertEquals(44100, bb.int)
    assertEquals(2, bb.get().toInt())
    assertEquals(AudioFormatOption.PCM_FLOAT.code, bb.get().toInt())
    assertEquals(7, bb.short.toInt())

    assertEquals(1764, AudioProtocol.framePayloadBytes(44100, 2, AudioFormatOption.PCM_16BIT))
    assertEquals(3528, AudioProtocol.framePayloadBytes(44100, 2, AudioFormatOption.PCM_FLOAT))
    assertEquals(1536, AudioProtocol.estimatedKbps(48000, 2, AudioFormatOption.PCM_16BIT))
  }

  @Test
  fun audioProtocol_silenceAndFrameProcessorFormats() {
    val silence8 = ByteArray(16)
    AudioProtocol.fillSilence(silence8, AudioFormatOption.PCM_8BIT)
    assertTrue(silence8.all { it == 0x80.toByte() })

    val processor = AudioFrameProcessor()

    // 16-bit mono gain
    val pcm16 = byteArrayOf(0x00, 0x10, 0x00, 0xF0.toByte()) // +4096, -4096
    val snap16 = processor.processFrame(pcm16, pcm16.size, AudioFormatOption.PCM_16BIT, 1, 2.0f, true)
    assertNotNull(snap16)
    assertEquals(0, pcm16[0].toInt() and 0xFF)
    assertEquals(0x20, pcm16[1].toInt() and 0xFF) // +8192
    assertTrue(snap16!!.level > 0.2f)

    // 8-bit stereo midpoint & gain
    val pcm8 = byteArrayOf((128 + 32).toByte(), (128 - 32).toByte())
    val snap8 = processor.processFrame(pcm8, pcm8.size, AudioFormatOption.PCM_8BIT, 2, 2.0f, true)
    assertNotNull(snap8)
    assertEquals(192, pcm8[0].toInt() and 0xFF)
    assertEquals(64, pcm8[1].toInt() and 0xFF)

    // 32-bit float mono gain
    val pcmFloat = ByteArray(8)
    val fbb = ByteBuffer.wrap(pcmFloat).order(ByteOrder.LITTLE_ENDIAN)
    fbb.putFloat(0.25f)
    fbb.putFloat(-0.25f)
    val snapFloat = processor.processFrame(pcmFloat, pcmFloat.size, AudioFormatOption.PCM_FLOAT, 1, 2.0f, true)
    assertNotNull(snapFloat)
    val outFbb = ByteBuffer.wrap(pcmFloat).order(ByteOrder.LITTLE_ENDIAN)
    assertEquals(0.5f, outFbb.float, 0.001f)
    assertEquals(-0.5f, outFbb.float, 0.001f)
    assertEquals(16, snapFloat!!.spectrum.size)
    assertEquals(32, snapFloat.waveform.size)
  }
}
