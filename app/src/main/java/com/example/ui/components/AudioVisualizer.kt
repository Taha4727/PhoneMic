package com.example.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.audio.VisualizerSnapshot
import com.example.audio.VisualizerStyle
import com.example.ui.theme.ElectricBlue
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.NeonTeal
import com.example.ui.theme.StreamActiveGreen
import com.example.ui.theme.StreamErrorRed
import com.example.ui.theme.StreamWarningAmber
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextSecondary
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
    val audioDb = snapshot.peakDb
    val audioLevel = snapshot.level

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(StudioCard, RoundedCornerShape(14.dp))
            .border(1.dp, StudioBorder, RoundedCornerShape(14.dp))
            .padding(12.dp)
            .testTag("audio_visualizer_card"),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "VISUALIZER • ${style.label.uppercase(Locale.US)}",
                color = TextSecondary,
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
                !isRunning -> TextMuted
                isPttMuted || isPaused -> StreamWarningAmber
                audioDb > -3f -> StreamErrorRed
                audioDb > -12f -> StreamWarningAmber
                else -> StreamActiveGreen
            }

            Text(
                text = dbText,
                color = dbColor,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }

        val canvasHeight = if (style == VisualizerStyle.CIRCULAR_PULSE) 92.dp else 56.dp
        val activeSignal = isRunning && !isPaused && !isPttMuted
        val mutedOrIdle = isPaused || isPttMuted

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(canvasHeight)
                .background(Color(0xFF0F1520), RoundedCornerShape(8.dp))
                .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(8.dp))
                .padding(horizontal = 8.dp, vertical = 6.dp)
        ) {
            Canvas(
                modifier = Modifier
                    .matchParentSize()
                    .testTag("visualizer_canvas_${style.id}")
            ) {
                when (style) {
                    VisualizerStyle.WAVEFORM -> drawWaveform(
                        waveform = snapshot.waveform,
                        fallbackLevel = audioLevel,
                        active = activeSignal,
                        muted = mutedOrIdle && isRunning
                    )
                    VisualizerStyle.SPECTRUM_BARS -> drawSpectrumBars(
                        spectrum = snapshot.spectrum,
                        fallbackLevel = audioLevel,
                        active = activeSignal,
                        muted = mutedOrIdle && isRunning
                    )
                    VisualizerStyle.VU_METER -> drawVuMeter(
                        level = audioLevel,
                        peakDb = audioDb,
                        active = activeSignal,
                        muted = mutedOrIdle && isRunning
                    )
                    VisualizerStyle.CIRCULAR_PULSE -> drawCircularPulse(
                        level = audioLevel,
                        spectrum = snapshot.spectrum,
                        active = activeSignal,
                        muted = mutedOrIdle && isRunning
                    )
                }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(text = "-60 dB", color = TextMuted, fontSize = 8.sp)
            Text(text = "-24 dB", color = TextMuted, fontSize = 8.sp)
            Text(text = "-12 dB", color = TextMuted, fontSize = 8.sp)
            Text(text = "0 dB", color = TextMuted, fontSize = 8.sp)
        }
    }
}

private fun DrawScope.drawWaveform(
    waveform: FloatArray,
    fallbackLevel: Float,
    active: Boolean,
    muted: Boolean
) {
    val count = waveform.size.coerceAtLeast(1)
    val spacing = 2.5.dp.toPx()
    val totalSpacing = spacing * (count - 1)
    val barWidth = ((size.width - totalSpacing) / count).coerceAtLeast(2f)
    val centerY = size.height / 2f
    val maxHalf = size.height * 0.45f
    val corner = CornerRadius(2.dp.toPx(), 2.dp.toPx())

    // Subtle baseline
    drawLine(
        color = Color(0xFF1F2D42),
        start = Offset(0f, centerY),
        end = Offset(size.width, centerY),
        strokeWidth = 1.dp.toPx()
    )

    for (i in 0 until count) {
        val sample = abs(waveform[i]).coerceIn(0f, 1f)
        val effective = maxOf(sample, fallbackLevel * 0.35f)
        val halfH = when {
            active -> (maxHalf * effective).coerceIn(2.dp.toPx(), maxHalf)
            muted -> 1.5.dp.toPx()
            else -> 1.5.dp.toPx()
        }
        val color = when {
            muted -> StreamWarningAmber.copy(alpha = 0.55f)
            active -> when {
                effective > 0.85f -> StreamErrorRed
                effective > 0.60f -> StreamWarningAmber
                else -> NeonCyan
            }
            else -> Color(0xFF26364A)
        }
        val x = i * (barWidth + spacing)
        drawRoundRect(
            color = color,
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
    muted: Boolean
) {
    val count = spectrum.size.coerceAtLeast(1)
    val spacing = 4.dp.toPx()
    val totalSpacing = spacing * (count - 1)
    val barWidth = ((size.width - totalSpacing) / count).coerceAtLeast(3f)
    val corner = CornerRadius(2.dp.toPx(), 2.dp.toPx())
    val minH = 3.dp.toPx()

    for (i in 0 until count) {
        val mag = maxOf(spectrum[i].coerceIn(0f, 1f), fallbackLevel * (0.65f - (i / (count * 2f))))
        val barH = when {
            active -> (size.height * mag).coerceIn(minH, size.height)
            muted -> minH
            else -> minH
        }
        val x = i * (barWidth + spacing)
        val top = size.height - barH
        val color = when {
            muted -> StreamWarningAmber.copy(alpha = 0.5f)
            active -> when {
                mag > 0.85f -> StreamErrorRed
                mag > 0.60f -> StreamWarningAmber
                i % 2 == 0 -> NeonCyan
                else -> ElectricBlue
            }
            else -> Color(0xFF26364A)
        }
        drawRoundRect(
            color = color,
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
    muted: Boolean
) {
    val segments = 24
    val spacing = 3.dp.toPx()
    val segW = ((size.width - spacing * (segments - 1)) / segments).coerceAtLeast(2f)
    val dbRatio = ((peakDb + 60f) / 60f).coerceIn(0f, 1f)
    val activeSegs = if (active) (maxOf(dbRatio, level) * segments).toInt().coerceIn(0, segments) else 0
    val topBarH = size.height * 0.58f
    val bottomBarH = size.height * 0.24f
    val bottomY = size.height - bottomBarH
    val corner = CornerRadius(2.dp.toPx(), 2.dp.toPx())

    for (i in 0 until segments) {
        val lit = i < activeSegs
        val x = i * (segW + spacing)
        val activeColor = when {
            i >= 20 -> StreamErrorRed
            i >= 15 -> StreamWarningAmber
            else -> StreamActiveGreen
        }
        drawRoundRect(
            color = when {
                muted -> StreamWarningAmber.copy(alpha = 0.22f)
                lit -> activeColor
                else -> Color(0xFF1A2433)
            },
            topLeft = Offset(x, 0f),
            size = Size(segW, topBarH),
            cornerRadius = corner
        )
    }

    // Continuous RMS envelope fill bar underneath
    drawRoundRect(
        color = Color(0xFF182230),
        topLeft = Offset(0f, bottomY),
        size = Size(size.width, bottomBarH),
        cornerRadius = corner
    )
    if (active) {
        val fillW = (size.width * level.coerceIn(0f, 1f)).coerceAtLeast(4.dp.toPx())
        drawRoundRect(
            color = NeonCyan,
            topLeft = Offset(0f, bottomY),
            size = Size(fillW, bottomBarH),
            cornerRadius = corner
        )
    } else if (muted) {
        drawRoundRect(
            color = StreamWarningAmber.copy(alpha = 0.5f),
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
    muted: Boolean
) {
    val cx = size.width / 2f
    val cy = size.height / 2f
    val maxR = min(size.width, size.height) * 0.44f
    val clamped = if (active) level.coerceIn(0f, 1f) else 0f
    val ringColor = when {
        muted -> StreamWarningAmber
        active -> if (clamped > 0.85f) StreamErrorRed else NeonCyan
        else -> Color(0xFF26364A)
    }

    // Outer ambient ring
    drawCircle(
        color = Color(0xFF1D2B3D),
        radius = maxR,
        center = Offset(cx, cy),
        style = Stroke(width = 2.dp.toPx())
    )

    // Reactive inner circles
    val pulseR = (maxR * (0.28f + 0.65f * clamped)).coerceAtLeast(6.dp.toPx())
    drawCircle(
        color = ringColor.copy(alpha = if (active) 0.25f else 0.12f),
        radius = pulseR,
        center = Offset(cx, cy)
    )
    drawCircle(
        color = ringColor,
        radius = pulseR * 0.65f,
        center = Offset(cx, cy),
        style = Stroke(width = 2.5.dp.toPx())
    )

    // Radial harmonic spokes from spectrum bins
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
            color = if (active) {
                if (mag > 0.75f) StreamWarningAmber else NeonTeal
            } else if (muted) {
                StreamWarningAmber.copy(alpha = 0.4f)
            } else {
                Color(0xFF28374A)
            },
            start = Offset(sx, sy),
            end = Offset(ex, ey),
            strokeWidth = 2.2.dp.toPx()
        )
    }
}
