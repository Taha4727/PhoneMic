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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.R
import com.example.audio.VisualizerSnapshot
import com.example.audio.VisualizerStyle
import com.example.ui.theme.JetBrainsMonoFontFamily
import com.example.ui.theme.PhoneMicColors
import com.example.ui.theme.PhoneMicTheme
import kotlinx.coroutines.flow.StateFlow
import java.util.Locale
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

@Composable
fun AudioVisualizer(
    snapshotFlow: StateFlow<VisualizerSnapshot>,
    style: VisualizerStyle,
    isRunning: Boolean,
    isPaused: Boolean,
    isPttMuted: Boolean = false,
    onHideClick: (() -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    val colors = PhoneMicTheme.colors

    Column(
        modifier = modifier
            .fillMaxWidth()
            .testTag("audio_visualizer_card")
            .background(colors.cardSurface, RoundedCornerShape(14.dp))
            .border(1.dp, colors.border, RoundedCornerShape(14.dp))
            .padding(start = 12.dp, end = 12.dp, top = if (onHideClick != null) 4.dp else 12.dp, bottom = 10.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
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
                letterSpacing = 0.8.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f)
            )

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                VisualizerDbReadout(
                    snapshotFlow = snapshotFlow,
                    isRunning = isRunning,
                    isPaused = isPaused,
                    isPttMuted = isPttMuted
                )
                if (onHideClick != null) {
                    IconButton(
                        onClick = onHideClick,
                        modifier = Modifier
                            .size(48.dp)
                            .testTag("visualizer_hide_button")
                    ) {
                        Icon(
                            imageVector = Icons.Outlined.VisibilityOff,
                            contentDescription = stringResource(R.string.hide_visualizer_cd),
                            tint = colors.textSecondary,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }

        VisualizerCanvasBox(
            snapshotFlow = snapshotFlow,
            style = style,
            isRunning = isRunning,
            isPaused = isPaused,
            isPttMuted = isPttMuted,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
        )

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

@Composable
private fun VisualizerDbReadout(
    snapshotFlow: StateFlow<VisualizerSnapshot>,
    isRunning: Boolean,
    isPaused: Boolean,
    isPttMuted: Boolean
) {
    val colors = PhoneMicTheme.colors
    val snapshotState = snapshotFlow.collectAsState()
    val audioDb = if (isRunning && !isPaused && !isPttMuted) snapshotState.value.peakDb else -60f

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

@Composable
private fun VisualizerCanvasBox(
    snapshotFlow: StateFlow<VisualizerSnapshot>,
    style: VisualizerStyle,
    isRunning: Boolean,
    isPaused: Boolean,
    isPttMuted: Boolean,
    modifier: Modifier = Modifier
) {
    val colors = PhoneMicTheme.colors
    val snapshotState: State<VisualizerSnapshot> = snapshotFlow.collectAsState()
    val activeSignal = isRunning && !isPaused && !isPttMuted
    val mutedOrIdle = (isPaused || isPttMuted) && isRunning

    Box(
        modifier = modifier
            .background(colors.visualizerBg, RoundedCornerShape(10.dp))
            .border(1.dp, colors.border, RoundedCornerShape(10.dp))
            .padding(horizontal = 10.dp, vertical = 8.dp)
    ) {
        Canvas(
            modifier = Modifier
                .fillMaxSize()
                .testTag("visualizer_canvas_${style.id}")
        ) {
            val snapshot = snapshotState.value
            val audioLevel = snapshot.level
            val audioDb = snapshot.peakDb
            when (style) {
                VisualizerStyle.WAVEFORM -> drawWaveform(
                    waveform = snapshot.waveform,
                    fallbackLevel = audioLevel,
                    active = activeSignal,
                    muted = mutedOrIdle,
                    colors = colors
                )
                VisualizerStyle.SPECTRUM_BARS -> drawSpectrumBars(
                    spectrum = snapshot.spectrum,
                    fallbackLevel = audioLevel,
                    active = activeSignal,
                    muted = mutedOrIdle,
                    colors = colors
                )
                VisualizerStyle.VU_METER -> drawVuMeter(
                    level = audioLevel,
                    peakDb = audioDb,
                    active = activeSignal,
                    muted = mutedOrIdle,
                    colors = colors
                )
                VisualizerStyle.CIRCULAR_PULSE -> drawCircularPulse(
                    level = audioLevel,
                    spectrum = snapshot.spectrum,
                    active = activeSignal,
                    muted = mutedOrIdle,
                    colors = colors
                )
            }
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
    val center = Offset(cx, cy)
    val maxR = (min(size.width, size.height) * 0.46f).coerceAtLeast(16.dp.toPx())
    val baseRingR = maxR * 0.48f
    val clampedLevel = if (active) level.coerceIn(0f, 1f) else 0f

    val coreColor: Color = when {
        muted -> colors.statusWarning
        active -> when {
            clampedLevel > 0.82f -> lerp(
                colors.statusWarning,
                colors.statusError,
                ((clampedLevel - 0.82f) / 0.18f).coerceIn(0f, 1f)
            )
            clampedLevel > 0.52f -> lerp(
                colors.accent,
                colors.statusWarning,
                ((clampedLevel - 0.52f) / 0.30f).coerceIn(0f, 1f)
            )
            else -> colors.accent
        }
        else -> colors.accent
    }

    // 1. Soft center radial aura driven by vocal level (zero per-frame allocations)
    val auraR = (baseRingR * (0.64f + 0.32f * clampedLevel)).coerceAtLeast(10.dp.toPx())
    val outerAuraAlpha = if (active) 0.06f + 0.04f * clampedLevel else if (muted) 0.05f else 0.03f
    val midAuraAlpha = if (active) 0.12f + 0.08f * clampedLevel else if (muted) 0.08f else 0.05f
    val innerAuraAlpha = if (active) 0.22f + 0.14f * clampedLevel else if (muted) 0.14f else 0.07f
    drawCircle(color = coreColor.copy(alpha = outerAuraAlpha), radius = auraR, center = center)
    drawCircle(color = coreColor.copy(alpha = midAuraAlpha), radius = auraR * 0.72f, center = center)
    drawCircle(color = coreColor.copy(alpha = innerAuraAlpha), radius = auraR * 0.46f, center = center)

    // 2. Reactive glowing center core dot
    val coreDotR = (baseRingR * (0.20f + 0.15f * clampedLevel)).coerceIn(3.5.dp.toPx(), baseRingR * 0.38f)
    drawCircle(
        color = coreColor.copy(alpha = if (active) 0.28f else if (muted) 0.18f else 0.10f),
        radius = coreDotR * 1.45f,
        center = center
    )
    drawCircle(
        color = if (active || muted) coreColor else colors.border,
        radius = coreDotR,
        center = center
    )
    drawCircle(
        color = Color.White.copy(alpha = if (active) 0.50f else if (muted) 0.22f else 0.14f),
        radius = coreDotR * 0.36f,
        center = center
    )

    // 3. Precision outer guide ring & inner base anchor ring
    drawCircle(
        color = colors.border.copy(alpha = 0.32f),
        radius = maxR * 0.96f,
        center = center,
        style = Stroke(width = 1.dp.toPx())
    )
    drawCircle(
        color = when {
            active -> coreColor.copy(alpha = 0.50f)
            muted -> colors.statusWarning.copy(alpha = 0.45f)
            else -> colors.border.copy(alpha = 0.72f)
        },
        radius = baseRingR,
        center = center,
        style = Stroke(width = 1.5.dp.toPx())
    )

    // 4. Dense 40 smooth rounded radial frequency bars around the ring
    val barCount = 40
    val barStartR = baseRingR + 2.5.dp.toPx()
    val maxBarLen = (maxR * 0.96f - barStartR).coerceAtLeast(4.dp.toPx())
    val minBarLen = 2.dp.toPx()
    val barStroke = ((2.0 * PI * baseRingR / barCount).toFloat() * 0.50f)
        .coerceIn(2.dp.toPx(), 4.2.dp.toPx())

    val specSize = spectrum.size.coerceAtLeast(1)

    for (i in 0 until barCount) {
        val angle = (2.0 * PI * i / barCount) - (PI / 2.0)
        val rawMag = if (active) {
            val prev = sampleCircularSpectrumBin(spectrum, specSize, i - 1, barCount, clampedLevel)
            val curr = sampleCircularSpectrumBin(spectrum, specSize, i, barCount, clampedLevel)
            val next = sampleCircularSpectrumBin(spectrum, specSize, i + 1, barCount, clampedLevel)
            (prev * 0.22f + curr * 0.56f + next * 0.22f).coerceIn(0f, 1f)
        } else {
            0f
        }

        val barLen = if (active) (minBarLen + (maxBarLen - minBarLen) * rawMag) else minBarLen
        val cosA = cos(angle).toFloat()
        val sinA = sin(angle).toFloat()
        val startOffset = Offset(cx + barStartR * cosA, cy + barStartR * sinA)
        val endOffset = Offset(cx + (barStartR + barLen) * cosA, cy + (barStartR + barLen) * sinA)

        val barColor = when {
            muted -> colors.statusWarning.copy(alpha = 0.45f)
            !active -> colors.border.copy(alpha = 0.70f)
            else -> {
                val radialBlend = ((0.5f - 0.5f * cos(angle)).toFloat() * 0.75f).coerceIn(0f, 1f)
                val themeBase = lerp(colors.accent, colors.secondaryAccent, radialBlend)
                when {
                    rawMag > 0.80f -> lerp(
                        colors.statusWarning,
                        colors.statusError,
                        ((rawMag - 0.80f) / 0.20f).coerceIn(0f, 1f)
                    )
                    rawMag > 0.52f -> lerp(
                        themeBase,
                        colors.statusWarning,
                        ((rawMag - 0.52f) / 0.28f).coerceIn(0f, 1f)
                    )
                    else -> themeBase
                }
            }
        }

        if (active && rawMag > 0.35f) {
            drawLine(
                color = barColor.copy(alpha = 0.22f),
                start = startOffset,
                end = endOffset,
                strokeWidth = barStroke * 1.9f,
                cap = StrokeCap.Round
            )
        }

        drawLine(
            color = barColor,
            start = startOffset,
            end = endOffset,
            strokeWidth = barStroke,
            cap = StrokeCap.Round
        )
    }
}

private fun sampleCircularSpectrumBin(
    spectrum: FloatArray,
    specSize: Int,
    idx: Int,
    barCount: Int,
    clampedLevel: Float
): Float {
    val wrapped = ((idx % barCount) + barCount) % barCount
    val half = barCount / 2f
    val distFromTop = abs(((wrapped + half) % barCount) - half)
    val normPos = (distFromTop / half).coerceIn(0f, 1f)
    val exactBin = normPos * (specSize - 1)
    val lo = exactBin.toInt().coerceIn(0, specSize - 1)
    val hi = (lo + 1).coerceIn(0, specSize - 1)
    val frac = exactBin - lo
    val specVal = spectrum[lo] * (1f - frac) + spectrum[hi] * frac
    return maxOf(specVal.coerceIn(0f, 1f), clampedLevel * (0.48f - normPos * 0.18f))
}
