package com.example.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
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
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary
import java.util.Locale

@Composable
fun HeroMicControl(
    isRunning: Boolean,
    isPaused: Boolean,
    isConnected: Boolean,
    statusMessage: String,
    elapsedSeconds: Long,
    ip: String,
    port: String,
    transportMode: String,
    connectionMode: String,
    audioDb: Float = -60f,
    onStartClick: () -> Unit,
    onPauseClick: () -> Unit,
    onStopClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val activeColor = when {
        !isRunning -> NeonCyan
        isPaused -> StreamWarningAmber
        isConnected -> StreamActiveGreen
        else -> StreamWarningAmber
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(StudioCard, RoundedCornerShape(16.dp))
            .border(1.dp, StudioBorder, RoundedCornerShape(16.dp))
            .padding(14.dp)
            .testTag("hero_mic_control_card"),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        // 1. Top Bar: Status & Duration Pill (Left) + Target Info (Right)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                modifier = Modifier
                    .background(Color(0xFF0F1722), RoundedCornerShape(50.dp))
                    .border(1.dp, StudioBorder, RoundedCornerShape(50.dp))
                    .padding(horizontal = 10.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(7.dp)
                        .background(activeColor, CircleShape)
                )

                Text(
                    text = statusMessage.uppercase(Locale.US),
                    color = TextPrimary,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.5.sp
                )

                if (isRunning && elapsedSeconds > 0) {
                    Text(text = "•", color = TextMuted, fontSize = 9.sp)
                    val mins = (elapsedSeconds % 3600) / 60
                    val secs = elapsedSeconds % 60
                    Text(
                        text = String.format(Locale.US, "%02d:%02d", mins, secs),
                        color = NeonCyan,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            if (ip.isNotEmpty()) {
                Text(
                    text = "$transportMode • $ip:$port",
                    color = TextMuted,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    maxLines = 1
                )
            }
        }

        // 2. Combined Mic Disc (Left) + High-Readability VU Level Meter (Right)
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Tactile Studio Mic Disc (tap to start/stop)
            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier
                    .size(62.dp)
                    .clip(CircleShape)
                    .background(
                        brush = Brush.verticalGradient(
                            colors = if (isRunning) {
                                if (isPaused) listOf(Color(0xFF6E4E00), Color(0xFF382700))
                                else listOf(Color(0xFF00695C), Color(0xFF00382E))
                            } else {
                                listOf(Color(0xFF0D3268), Color(0xFF081A36))
                            }
                        )
                    )
                    .border(
                        width = 2.dp,
                        color = activeColor,
                        shape = CircleShape
                    )
                    .clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null
                    ) {
                        if (!isRunning) onStartClick() else onStopClick()
                    }
                    .testTag("hero_mic_button")
            ) {
                Icon(
                    imageVector = when {
                        !isRunning -> Icons.Default.Mic
                        isPaused -> Icons.Default.MicOff
                        else -> Icons.Default.Mic
                    },
                    contentDescription = if (isRunning) "Microphone active" else "Microphone ready",
                    tint = if (isPaused) StreamWarningAmber else TextPrimary,
                    modifier = Modifier.size(30.dp)
                )
            }

            // Integrated "MIC INPUT LEVEL" Box
            Column(
                modifier = Modifier
                    .weight(1f)
                    .background(Color(0xFF0F1722), RoundedCornerShape(10.dp))
                    .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                    .padding(horizontal = 10.dp, vertical = 7.dp)
                    .testTag("integrated_audio_meter"),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                // Meter Title + Real-time dB Value
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "MIC INPUT LEVEL",
                        color = TextSecondary,
                        fontSize = 9.5.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.5.sp
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
                        fontSize = 10.5.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                }

                // Segmented LED Meter Bar (18 segments)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(2.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    val totalSegments = 18
                    val activeSegments = if (isRunning && !isPaused) {
                        ((audioDb + 60f) / 60f * totalSegments).toInt().coerceIn(0, totalSegments)
                    } else 0

                    for (index in 0 until totalSegments) {
                        val isActive = index < activeSegments
                        val segmentColor = when {
                            index >= 15 -> StreamErrorRed
                            index >= 11 -> StreamWarningAmber
                            else -> StreamActiveGreen
                        }

                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .height(7.dp)
                                .background(
                                    color = if (isActive) segmentColor else Color(0xFF192331),
                                    shape = RoundedCornerShape(1.dp)
                                )
                        )
                    }
                }

                // dB Reference Scale
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(text = "-60", color = TextMuted, fontSize = 7.5.sp, fontFamily = FontFamily.Monospace)
                    Text(text = "-24", color = TextMuted, fontSize = 7.5.sp, fontFamily = FontFamily.Monospace)
                    Text(text = "-12", color = TextMuted, fontSize = 7.5.sp, fontFamily = FontFamily.Monospace)
                    Text(text = "-3", color = TextMuted, fontSize = 7.5.sp, fontFamily = FontFamily.Monospace)
                    Text(text = "0 dB", color = TextMuted, fontSize = 7.5.sp, fontFamily = FontFamily.Monospace)
                }
            }
        }

        // 3. Reliable Primary Action Buttons
        if (!isRunning) {
            Button(
                onClick = onStartClick,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(44.dp)
                    .testTag("start_streaming_button"),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = NeonCyan,
                    contentColor = Color(0xFF003038)
                )
            ) {
                Icon(
                    imageVector = Icons.Default.PlayArrow,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "START STREAM",
                    fontSize = 12.5.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.5.sp
                )
            }
        } else {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = onPauseClick,
                    modifier = Modifier
                        .weight(1f)
                        .height(40.dp)
                        .testTag("pause_resume_button"),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = if (isPaused) StreamWarningAmber else TextPrimary
                    ),
                    border = ButtonDefaults.outlinedButtonBorder.copy(
                        brush = Brush.horizontalGradient(
                            listOf(
                                if (isPaused) StreamWarningAmber else StudioBorder,
                                if (isPaused) StreamWarningAmber else StudioBorder
                            )
                        )
                    )
                ) {
                    Icon(
                        imageVector = if (isPaused) Icons.Default.PlayArrow else Icons.Default.Pause,
                        contentDescription = null,
                        modifier = Modifier.size(15.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = if (isPaused) "Resume" else "Mute",
                        fontWeight = FontWeight.Bold,
                        fontSize = 12.sp,
                        maxLines = 1
                    )
                }

                Button(
                    onClick = onStopClick,
                    modifier = Modifier
                        .weight(1f)
                        .height(40.dp)
                        .testTag("stop_streaming_button"),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = StreamErrorRed,
                        contentColor = Color.White
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.Stop,
                        contentDescription = null,
                        modifier = Modifier.size(15.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = "Stop",
                        fontWeight = FontWeight.Bold,
                        fontSize = 12.sp,
                        maxLines = 1
                    )
                }
            }
        }
    }
}
