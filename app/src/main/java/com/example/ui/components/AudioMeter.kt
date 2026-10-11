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
import com.example.ui.theme.StreamActiveGreen
import com.example.ui.theme.StreamErrorRed
import com.example.ui.theme.StreamWarningAmber
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextSecondary
import java.util.Locale

@Composable
fun AudioMeter(
    audioDb: Float,
    isRunning: Boolean,
    isPaused: Boolean,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(StudioCard, RoundedCornerShape(12.dp))
            .border(1.dp, StudioBorder, RoundedCornerShape(12.dp))
            .padding(horizontal = 12.dp, vertical = 8.dp)
            .testTag("audio_meter_card"),
        verticalArrangement = Arrangement.spacedBy(5.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "MIC INPUT LEVEL",
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

        // Horizontal Segmented VU Peak Bar (Hardware-accelerated single Canvas)
        Canvas(
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
        ) {
            val totalSegments = 20
            val activeSegments = if (isRunning && !isPaused) {
                ((audioDb + 60f) / 60f * totalSegments).toInt().coerceIn(0, totalSegments)
            } else 0

            val spacingPx = 2.dp.toPx()
            val totalSpacing = spacingPx * (totalSegments - 1)
            val segmentWidth = (size.width - totalSpacing) / totalSegments
            val cornerRadius = CornerRadius(1.dp.toPx(), 1.dp.toPx())

            for (index in 0 until totalSegments) {
                val isActive = index < activeSegments
                val segmentColor = when {
                    index >= 17 -> StreamErrorRed
                    index >= 13 -> StreamWarningAmber
                    else -> StreamActiveGreen
                }
                val x = index * (segmentWidth + spacingPx)
                drawRoundRect(
                    color = if (isActive) segmentColor else Color(0xFF192331),
                    topLeft = Offset(x, 0f),
                    size = Size(segmentWidth, size.height),
                    cornerRadius = cornerRadius
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
            Text(text = "-3 dB", color = TextMuted, fontSize = 8.sp)
            Text(text = "0 dB", color = TextMuted, fontSize = 8.sp)
        }
    }
}
