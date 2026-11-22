package com.example.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.audio.VisualizerSnapshot
import com.example.audio.VisualizerStyle
import com.example.ui.theme.JetBrainsMonoFontFamily
import com.example.ui.theme.PhoneMicColors
import com.example.ui.theme.PhoneMicTheme
import java.util.Locale
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

@Composable
fun AudioVisualizer(
    snapshot: VisualizerSnapshot,
    style: VisualizerStyle,
    isRunning: Boolean,
    isPaused: Boolean,
    isPttMuted: Boolean = false,
    modifier: Modifier = Modifier
) {
    val colors = PhoneMicTheme.colors
    val audioDb = snapshot.peakDb
    val audioLevel = snapshot.level

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(colors.cardSurface, RoundedCornerShape(14.dp))
            .border(1.dp, colors.border, RoundedCornerShape(14.dp))
            .padding(12.dp)
            .testTag("audio_visualizer_card"),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "VISUALIZER • ${style.label.uppercase(Locale.US)}",
                color = colors.textSecondary,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.8.sp
            )

            val dbText = when {
                !isRunning -> "OFFLINE"
                isPttMuted -> "PTT STANDBY"
                isPaused -> "MUTED"
                audioDb <= -59.5f -> "< -60 dB"
                else -> String.format(Locale.US, "%.1f dB", audioDb)
            }

            val dbColor = when {
                !isRunning -> colors.textMuted
                isPttMuted || isPaused -> colors.statusWarning
                audioDb > -3f -> colors.statusError
                audioDb > -12f -> colors.statusWarning
                else -> colors.statusConnected
            }

            Text(
                text = dbText,
                color = dbColor,
                fontSize = 11.sp,
                fontFamily = JetBrainsMonoFontFamily,
                fontWeight = FontWeight.Bold
            )
        }

        val activeSignal = isRunning && !isPaused && !isPttMuted
        val mutedOrIdle = isPaused || isPttMuted

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .background(colors.visualizerBg, RoundedCornerShape(10.dp))
                .border(1.dp, colors.border, RoundedCornerShape(10.dp))
                .padding(horizontal = 10.dp, vertical = 8.dp)
        ) {
            Canvas(
                modifier = Modifier
                    .fillMaxSize()
                    .testTag("visualizer_canvas_${style.id}")
            ) {
                when (style) {
                    VisualizerStyle.WAVEFORM -> drawWaveform(
                        waveform = snapshot.waveform,
                        fallbackLevel = audioLevel,
                        active = activeSignal,
                        muted = mutedOrIdle && isRunning,
                        colors = colors
                    )
                    VisualizerStyle.SPECTRUM_BARS -> drawSpectrumBars(
                        spectrum = snapshot.spectrum,
                        fallbackLevel = audioLevel,
                        active = activeSignal,
                        muted = mutedOrIdle && isRunning,
                        colors = colors
                    )
                    VisualizerStyle.VU_METER -> drawVuMeter(
                        level = audioLevel,
                        peakDb = audioDb,
                        active = activeSignal,
                        muted = mutedOrIdle && isRunning,
                        colors = colors
                    )
                    VisualizerStyle.CIRCULAR_PULSE -> drawCircularPulse(
                        level = audioLevel,
                        spectrum = snapshot.spectrum,
                        active = activeSignal,
                        muted = mutedOrIdle && isRunning,
                        colors = colors
                    )
                }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(text = "-60 dB", color = colors.textMuted, fontSize = 9.sp, fontFamily = JetBrainsMonoFontFamily)
            Text(text = "-24 dB", color = colors.textMuted, fontSize = 9.sp, fontFamily = JetBrainsMonoFontFamily)
            Text(text = "-12 dB", color = colors.textMuted, fontSize = 9.sp, fontFamily = JetBrainsMonoFontFamily)
            Text(text = "0 dB", color = colors.textMuted, fontSize = 9.sp, fontFamily = JetBrainsMonoFontFamily)
        }
    }
}

private fun DrawScope.drawWaveform(
    waveform: FloatArray,
    fallbackLevel: Float,
    active: Boolean,
    muted: Boolean,
    colors: PhoneMicColors
) {
    val count = waveform.size.coerceAtLeast(1)
    val spacing = 3.dp.toPx()
    val totalSpacing = spacing * (count - 1)
    val barWidth = ((size.width - totalSpacing) / count).coerceAtLeast(2f)
    val centerY = size.height / 2f
    val maxHalf = size.height * 0.45f
    val corner = CornerRadius(2.dp.toPx(), 2.dp.toPx())
    val idleBarColor = colors.border

    drawLine(
        color = colors.border.copy(alpha = 0.7f),
        start = Offset(0f, centerY),
        end = Offset(size.width, centerY),
        strokeWidth = 1.dp.toPx()
    )

    for (i in 0 until count) {
        val sample = abs(waveform[i]).coerceIn(0f, 1f)
        val effective = maxOf(sample, fallbackLevel * 0.35f)
        val halfH = when {
            active -> (maxHalf * effective).coerceIn(2.dp.toPx(), maxHalf)
            muted -> 2.dp.toPx()
            else -> 2.dp.toPx()
        }
        val barColor = when {
            muted -> colors.statusWarning.copy(alpha = 0.6f)
            active -> when {
                effective > 0.85f -> colors.statusError
                effective > 0.60f -> colors.statusWarning
                else -> colors.accent
            }
            else -> idleBarColor
        }
        val x = i * (barWidth + spacing)
        drawRoundRect(
            color = barColor,
            topLeft = Offset(x, centerY - halfH),
            size = Size(barWidth, halfH * 2f),
            cornerRadius = corner
        )
    }
}

private fun DrawScope.drawSpectrumBars(
    spectrum: FloatArray,
    fallbackLevel: Float,
    active: Boolean,
    muted: Boolean,
    colors: PhoneMicColors
) {
    val count = spectrum.size.coerceAtLeast(1)
    val spacing = 4.dp.toPx()
    val totalSpacing = spacing * (count - 1)
    val barWidth = ((size.width - totalSpacing) / count).coerceAtLeast(3f)
    val corner = CornerRadius(2.dp.toPx(), 2.dp.toPx())
    val minH = 3.dp.toPx()

    for (i in 0 until count) {
        val mag = maxOf(spectrum[i].coerceIn(0f, 1f), fallbackLevel * (0.65f - (i / (count * 2f))))
        val barH = if (active) (size.height * mag).coerceIn(minH, size.height) else minH
        val x = i * (barWidth + spacing)
        val top = size.height - barH
        val barColor = when {
            muted -> colors.statusWarning.copy(alpha = 0.55f)
            active -> when {
                mag > 0.85f -> colors.statusError
                mag > 0.60f -> colors.statusWarning
                i % 2 == 0 -> colors.accent
                else -> colors.secondaryAccent
            }
            else -> colors.border
        }
        drawRoundRect(
            color = barColor,
            topLeft = Offset(x, top),
            size = Size(barWidth, barH),
            cornerRadius = corner
        )
    }
}

private fun DrawScope.drawVuMeter(
    level: Float,
    peakDb: Float,
    active: Boolean,
    muted: Boolean,
    colors: PhoneMicColors
) {
    val segments = 24
    val spacing = 3.dp.toPx()
    val segW = ((size.width - spacing * (segments - 1)) / segments).coerceAtLeast(2f)
    val dbRatio = ((peakDb + 60f) / 60f).coerceIn(0f, 1f)
    val activeSegs = if (active) (maxOf(dbRatio, level) * segments).toInt().coerceIn(0, segments) else 0
    val topBarH = size.height * 0.58f
    val bottomBarH = size.height * 0.22f
    val bottomY = size.height - bottomBarH
    val corner = CornerRadius(2.dp.toPx(), 2.dp.toPx())

    for (i in 0 until segments) {
        val lit = i < activeSegs
        val x = i * (segW + spacing)
        val activeColor = when {
            i >= 20 -> colors.statusError
            i >= 15 -> colors.statusWarning
            else -> colors.statusConnected
        }
        drawRoundRect(
            color = when {
                muted -> colors.statusWarning.copy(alpha = 0.25f)
                lit -> activeColor
                else -> colors.border.copy(alpha = 0.65f)
            },
            topLeft = Offset(x, 0f),
            size = Size(segW, topBarH),
            cornerRadius = corner
        )
    }

    drawRoundRect(
        color = colors.border.copy(alpha = 0.45f),
        topLeft = Offset(0f, bottomY),
        size = Size(size.width, bottomBarH),
        cornerRadius = corner
    )
    if (active) {
        val fillW = (size.width * level.coerceIn(0f, 1f)).coerceAtLeast(4.dp.toPx())
        drawRoundRect(
            color = colors.accent,
            topLeft = Offset(0f, bottomY),
            size = Size(fillW, bottomBarH),
            cornerRadius = corner
        )
    } else if (muted) {
        drawRoundRect(
            color = colors.statusWarning.copy(alpha = 0.5f),
            topLeft = Offset(0f, bottomY),
            size = Size(size.width * 0.15f, bottomBarH),
            cornerRadius = corner
        )
    }
}

private fun DrawScope.drawCircularPulse(
    level: Float,
    spectrum: FloatArray,
    active: Boolean,
    muted: Boolean,
    colors: PhoneMicColors
) {
    val cx = size.width / 2f
    val cy = size.height / 2f
    val maxR = min(size.width, size.height) * 0.44f
    val clamped = if (active) level.coerceIn(0f, 1f) else 0f
    val ringColor: Color = when {
        muted -> colors.statusWarning
        active -> if (clamped > 0.85f) colors.statusError else colors.accent
        else -> colors.border
    }

    drawCircle(
        color = colors.border.copy(alpha = 0.7f),
        radius = maxR,
        center = Offset(cx, cy),
        style = Stroke(width = 1.5.dp.toPx())
    )

    val pulseR = (maxR * (0.28f + 0.65f * clamped)).coerceAtLeast(6.dp.toPx())
    drawCircle(
        color = ringColor.copy(alpha = if (active) 0.22f else 0.10f),
        radius = pulseR,
        center = Offset(cx, cy)
    )
    drawCircle(
        color = ringColor,
        radius = pulseR * 0.65f,
        center = Offset(cx, cy),
        style = Stroke(width = 2.dp.toPx())
    )

    val spokeCount = 16
    val innerBase = maxR * 0.52f
    for (i in 0 until spokeCount) {
        val angle = (2.0 * PI * i / spokeCount) - PI / 2.0
        val mag = if (active) spectrum[i % spectrum.size].coerceIn(0f, 1f) else 0.05f
        val outerR = innerBase + (maxR * 0.48f * mag)
        val sx = cx + (innerBase * cos(angle)).toFloat()
        val sy = cy + (innerBase * sin(angle)).toFloat()
        val ex = cx + (outerR * cos(angle)).toFloat()
        val ey = cy + (outerR * sin(angle)).toFloat()
        drawLine(
            color = when {
                active && mag > 0.75f -> colors.statusWarning
                active -> colors.secondaryAccent
                muted -> colors.statusWarning.copy(alpha = 0.45f)
                else -> colors.border
            },
            start = Offset(sx, sy),
            end = Offset(ex, ey),
            strokeWidth = 2.dp.toPx()
        )
    }
}
