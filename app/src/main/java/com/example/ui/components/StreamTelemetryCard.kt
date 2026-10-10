package com.example.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Router
import androidx.compose.material.icons.filled.Smartphone
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.DeviceProfile
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StreamActiveGreen
import com.example.ui.theme.StreamWarningAmber
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary
import java.util.Locale

@Composable
fun StreamTelemetryCard(
    isRunning: Boolean,
    isPaused: Boolean,
    isConnected: Boolean,
    packetsSent: Long,
    bytesSent: Long,
    packetRate: Float,
    transportMode: String,
    ip: String = "",
    port: String = "",
    connectionMode: String = "",
    elapsedSeconds: Long = 0L,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .testTag("stream_telemetry_card"),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        // 1. Live Stream Telemetry Grid Card
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(StudioCard, RoundedCornerShape(16.dp))
                .border(1.dp, StudioBorder, RoundedCornerShape(16.dp))
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Header: Icon, Title, and Status Badge
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Speed,
                        contentDescription = null,
                        tint = NeonCyan,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = "LIVE STREAM STATS",
                        color = TextPrimary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.5.sp
                    )
                }

                // Status Badge
                val (statusBg, statusBorder, statusColor, statusLabel) = when {
                    !isRunning -> Quad(
                        Color(0xFF131D28),
                        StudioBorder,
                        TextMuted,
                        "STANDBY"
                    )
                    isPaused -> Quad(
                        Color(0xFF332600),
                        StreamWarningAmber.copy(alpha = 0.5f),
                        StreamWarningAmber,
                        "MUTED"
                    )
                    isConnected -> Quad(
                        Color(0xFF003823),
                        StreamActiveGreen.copy(alpha = 0.5f),
                        StreamActiveGreen,
                        "STREAMING"
                    )
                    else -> Quad(
                        Color(0xFF332600),
                        StreamWarningAmber.copy(alpha = 0.5f),
                        StreamWarningAmber,
                        "CONNECTING"
                    )
                }

                Box(
                    modifier = Modifier
                        .background(statusBg, RoundedCornerShape(6.dp))
                        .border(1.dp, statusBorder, RoundedCornerShape(6.dp))
                        .padding(horizontal = 8.dp, vertical = 3.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .background(statusColor, CircleShape)
                        )
                        Text(
                            text = statusLabel,
                            color = statusColor,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }

            // 2x2 Telemetry Metric Grid
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Metric: Packets Sent
                TelemetryMetricTile(
                    title = "PACKETS SENT",
                    value = if (isRunning) String.format(Locale.US, "%,d", packetsSent) else "--",
                    unit = "pkts",
                    modifier = Modifier.weight(1f)
                )

                // Metric: Stream Rate
                val rateText = if (isRunning && !isPaused) {
                    if (packetRate > 0) String.format(Locale.US, "%.1f", packetRate) else "100.0"
                } else "0.0"
                TelemetryMetricTile(
                    title = "STREAM RATE",
                    value = rateText,
                    unit = "pkt/sec",
                    modifier = Modifier.weight(1f)
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Metric: Data Transferred
                val mb = bytesSent / (1024f * 1024f)
                val transValue = when {
                    !isRunning -> "--"
                    mb >= 0.1f -> String.format(Locale.US, "%.2f", mb)
                    else -> String.format(Locale.US, "%.1f", bytesSent / 1024f)
                }
                val transUnit = if (isRunning && mb < 0.1f) "KB" else "MB"
                TelemetryMetricTile(
                    title = "TRANSFERRED",
                    value = transValue,
                    unit = transUnit,
                    modifier = Modifier.weight(1f)
                )

                // Metric: Audio Bitrate
                TelemetryMetricTile(
                    title = "BITRATE",
                    value = if (isRunning && !isPaused) "768.0" else "0.0",
                    unit = "kbps",
                    modifier = Modifier.weight(1f)
                )
            }
        }

        // 2. Clean Audio Specifications Card
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(StudioCard, RoundedCornerShape(16.dp))
                .border(1.dp, StudioBorder, RoundedCornerShape(16.dp))
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.GraphicEq,
                    contentDescription = null,
                    tint = NeonCyan,
                    modifier = Modifier.size(16.dp)
                )
                Text(
                    text = "AUDIO SPECIFICATIONS",
                    color = TextPrimary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.5.sp
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF0F1622), RoundedCornerShape(10.dp))
                    .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                SpecRow(label = "Sampling Rate", value = "48,000 Hz")
                SpecRow(label = "Audio Format", value = "16-bit Linear PCM")
                SpecRow(label = "Channels", value = "1 (Mono)")
                SpecRow(label = "Packet Buffer", value = "10 ms (960 bytes)")
                SpecRow(label = "Transport Protocol", value = transportMode.uppercase(Locale.US))
            }
        }

        // 3. Receiver & Endpoint Card
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(StudioCard, RoundedCornerShape(16.dp))
                .border(1.dp, StudioBorder, RoundedCornerShape(16.dp))
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Router,
                    contentDescription = null,
                    tint = NeonCyan,
                    modifier = Modifier.size(16.dp)
                )
                Text(
                    text = "RECEIVER CONFIGURATION",
                    color = TextPrimary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.5.sp
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF0F1622), RoundedCornerShape(10.dp))
                    .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                if (ip.isNotEmpty()) {
                    SpecRow(label = "Target Host", value = if (port.isNotEmpty()) "$ip:$port" else ip)
                }
                if (connectionMode.isNotEmpty()) {
                    SpecRow(label = "Connection Mode", value = connectionMode)
                }
                SpecRow(label = "Receiver Script", value = "v0.6.3 (Python)")
                SpecRow(label = "Audio Output", value = "VB-CABLE / WASAPI")
            }
        }

        // 4. Hardware & Platform Profile Card (POCO X6 Pro 5G / Android 16)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(StudioCard, RoundedCornerShape(16.dp))
                .border(1.dp, StudioBorder, RoundedCornerShape(16.dp))
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Smartphone,
                    contentDescription = null,
                    tint = NeonCyan,
                    modifier = Modifier.size(16.dp)
                )
                Text(
                    text = "DEVICE & HARDWARE PROFILE",
                    color = TextPrimary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.5.sp
                )
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF0F1622), RoundedCornerShape(10.dp))
                    .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                SpecRow(label = "Device Model", value = DeviceProfile.deviceDisplayName)
                SpecRow(label = "Platform OS", value = DeviceProfile.osDisplayName)
                SpecRow(label = "Chipset / SoC", value = DeviceProfile.chipsetDisplayName)
                SpecRow(label = "Audio Pipeline", value = "Direct 48 kHz 16-bit PCM (Low Latency)")
                SpecRow(label = "FGS Type", value = "Microphone FGS (API 36 Compliant)")
            }
        }
    }
}

@Composable
private fun TelemetryMetricTile(
    title: String,
    value: String,
    unit: String,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .background(Color(0xFF0F1622), RoundedCornerShape(10.dp))
            .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
            .padding(vertical = 10.dp, horizontal = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            Text(
                text = title,
                color = TextMuted,
                fontSize = 9.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.5.sp,
                maxLines = 1
            )
            Text(
                text = value,
                color = TextPrimary,
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                maxLines = 1
            )
            Text(
                text = unit,
                color = NeonCyan,
                fontSize = 9.5.sp,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}

@Composable
private fun SpecRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            color = TextSecondary,
            fontSize = 11.sp
        )
        Text(
            text = value,
            color = TextPrimary,
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            fontFamily = FontFamily.Monospace
        )
    }
}

private data class Quad<A, B, C, D>(
    val first: A,
    val second: B,
    val third: C,
    val fourth: D
)
