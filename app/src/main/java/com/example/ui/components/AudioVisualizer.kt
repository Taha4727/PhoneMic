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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StreamActiveGreen
import com.example.ui.theme.StreamErrorRed
import com.example.ui.theme.StreamWarningAmber
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextSecondary
import java.util.Locale

@Composable
fun AudioVisualizer(
    audioLevel: Float,
    audioDb: Float,
    isRunning: Boolean,
    isPaused: Boolean,
    modifier: Modifier = Modifier
) {
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
                text = "AUDIO SIGNAL & VU METER",
                color = TextSecondary,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.8.sp
            )

            val dbText = when {
                !isRunning -> "OFFLINE"
                isPaused -> "MUTED"
                audioDb <= -59.5f -> "< -60 dB"
                else -> String.format(Locale.US, "%.1f dB", audioDb)
            }

            val dbColor = when {
                !isRunning -> TextMuted
                isPaused -> StreamWarningAmber
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

        // Lightweight Multi-Bar Waveform Canvas (Zero CPU trigonometry loops for 7.1.1 smoothness)
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(38.dp)
                .background(Color(0xFF0F1520), RoundedCornerShape(8.dp))
                .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(8.dp))
                .padding(horizontal = 6.dp, vertical = 4.dp)
        ) {
            Canvas(modifier = Modifier.matchParentSize()) {
                val numBars = 24
                val spacing = 3.dp.toPx()
                val totalSpacing = spacing * (numBars - 1)
                val barWidth = (size.width - totalSpacing) / numBars
                val centerY = size.height / 2f
                val maxBarHeight = size.height * 0.9f
                val clampedLevel = audioLevel.coerceIn(0f, 1f)

                for (i in 0 until numBars) {
                    val x = i * (barWidth + spacing)
                    val barHeight = when {
                        isRunning && !isPaused -> {
                            val centerFactor = 1f - kotlin.math.abs((i - numBars / 2f) / (numBars / 2f)) * 0.45f
                            (maxBarHeight * clampedLevel * centerFactor).coerceIn(3.dp.toPx(), maxBarHeight)
                        }
                        isPaused -> 2.dp.toPx()
                        else -> 3.dp.toPx()
                    }

                    val top = centerY - (barHeight / 2f)
                    val color = when {
                        isPaused -> StreamWarningAmber.copy(alpha = 0.6f)
                        isRunning -> {
                            val ratio = barHeight / maxBarHeight
                            when {
                                ratio > 0.85f -> StreamErrorRed
                                ratio > 0.60f -> StreamWarningAmber
                                else -> NeonCyan
                            }
                        }
                        else -> Color(0xFF26364A)
                    }

                    drawRoundRect(
                        color = color,
                        topLeft = Offset(x, top),
                        size = Size(barWidth, barHeight),
                        cornerRadius = CornerRadius(2.dp.toPx(), 2.dp.toPx())
                    )
                }
            }
        }

        // Horizontal Segmented VU Peak Bar
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(2.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            val totalSegments = 16
            val activeSegments = if (isRunning && !isPaused) {
                ((audioDb + 60f) / 60f * totalSegments).toInt().coerceIn(0, totalSegments)
            } else 0

            for (index in 0 until totalSegments) {
                val isActive = index < activeSegments
                val segmentColor = when {
                    index >= 13 -> StreamErrorRed
                    index >= 10 -> StreamWarningAmber
                    else -> StreamActiveGreen
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(3.5.dp)
                        .background(
                            color = if (isActive) segmentColor else Color(0xFF1A2433),
                            shape = RoundedCornerShape(1.dp)
                        )
                )
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
