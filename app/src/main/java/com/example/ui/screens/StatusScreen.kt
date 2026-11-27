package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Smartphone
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.BuildConfig
import com.example.DeviceProfile
import com.example.PhoneMicUiState
import com.example.R
import com.example.audio.AudioChannelOption
import com.example.audio.AudioProtocol
import com.example.ui.components.BatteryOptimizationBanner
import com.example.ui.theme.JetBrainsMonoFontFamily
import com.example.ui.theme.PhoneMicTheme
import java.util.Locale

@Composable
fun StatusScreen(
    uiState: PhoneMicUiState,
    selectedMicName: String,
    onBatteryDismissOrGranted: () -> Unit,
    modifier: Modifier = Modifier
) {
    val colors = PhoneMicTheme.colors

    val totalFrames = uiState.packetsSent + uiState.packetsDropped
    val packetLossPct = if (totalFrames > 0L) {
        (uiState.packetsDropped.toFloat() / totalFrames.toFloat()) * 100f
    } else 0f

    val payloadBytes = remember(uiState.sampleRateHz, uiState.channels, uiState.audioFormat) {
        AudioProtocol.framePayloadBytes(uiState.sampleRateHz, uiState.channels, uiState.audioFormat)
    }
    val nominalKbps = remember(uiState.sampleRateHz, uiState.channels, uiState.audioFormat) {
        AudioProtocol.estimatedKbps(uiState.sampleRateHz, uiState.channels, uiState.audioFormat)
    }
    val channelOption = remember(uiState.channels) {
        AudioChannelOption.fromCount(uiState.channels)
    }
    val wireProtocol = remember(uiState.sampleRateHz, uiState.channels, uiState.audioFormat, uiState.transportMode) {
        if (AudioProtocol.isLegacyStandardStream(uiState.sampleRateHz, uiState.channels, uiState.audioFormat)) {
            "${uiState.transportMode} (PM01–PM03)"
        } else {
            "${uiState.transportMode} (PM04)"
        }
    }
    val targetReceiverText = remember(uiState.ip, uiState.port, uiState.connectionMode) {
        if (uiState.ip.isNotEmpty()) "${uiState.ip}:${uiState.port} (${uiState.connectionMode})" else "Not set"
    }

    BoxWithConstraints(
        modifier = modifier
            .fillMaxSize()
            .testTag("status_screen")
    ) {
        val isHorizontal = maxWidth > maxHeight && maxWidth >= 560.dp

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Stream Status",
                    color = colors.textPrimary,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )

                val (badgeColor, badgeLabel) = when {
                    !uiState.isRunning -> colors.textMuted to "STANDBY"
                    uiState.isPaused || (uiState.pushToTalkEnabled && !uiState.isPttPressed) -> colors.statusWarning to "MUTED"
                    uiState.isConnected -> colors.statusConnected to "STREAMING"
                    else -> colors.statusWarning to "CONNECTING"
                }

                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = badgeColor.copy(alpha = 0.14f),
                    border = BorderStroke(1.dp, badgeColor.copy(alpha = 0.45f))
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(7.dp)
                                .background(badgeColor, CircleShape)
                        )
                        Text(
                            text = badgeLabel,
                            color = badgeColor,
                            fontSize = 10.5.sp,
                            fontFamily = JetBrainsMonoFontFamily,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            if (isHorizontal) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("status_horizontal_columns"),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.Top
                ) {
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        BatteryOptimizationBanner(
                            isIgnored = uiState.isIgnoringBatteryOptimizations,
                            onDismissOrGranted = onBatteryDismissOrGranted
                        )

                        StatusLiveStreamSection(
                            uiState = uiState,
                            totalFrames = totalFrames,
                            packetLossPct = packetLossPct,
                            nominalKbps = nominalKbps
                        )
                    }

                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        StatusAudioSection(
                            sampleRateHz = uiState.sampleRateHz,
                            audioFormatLabel = uiState.audioFormat.label,
                            channelLabel = channelOption.label,
                            payloadBytes = payloadBytes,
                            wireProtocol = wireProtocol,
                            selectedMicName = selectedMicName
                        )

                        StatusDeviceSection(
                            targetReceiverText = targetReceiverText,
                            elapsedSeconds = uiState.elapsedSeconds
                        )
                    }
                }
            } else {
                BatteryOptimizationBanner(
                    isIgnored = uiState.isIgnoringBatteryOptimizations,
                    onDismissOrGranted = onBatteryDismissOrGranted
                )

                StatusLiveStreamSection(
                    uiState = uiState,
                    totalFrames = totalFrames,
                    packetLossPct = packetLossPct,
                    nominalKbps = nominalKbps
                )

                StatusAudioSection(
                    sampleRateHz = uiState.sampleRateHz,
                    audioFormatLabel = uiState.audioFormat.label,
                    channelLabel = channelOption.label,
                    payloadBytes = payloadBytes,
                    wireProtocol = wireProtocol,
                    selectedMicName = selectedMicName
                )

                StatusDeviceSection(
                    targetReceiverText = targetReceiverText,
                    elapsedSeconds = uiState.elapsedSeconds
                )
            }

            Spacer(modifier = Modifier.height(8.dp))
        }
    }
}

@Composable
private fun StatusLiveStreamSection(
    uiState: PhoneMicUiState,
    totalFrames: Long,
    packetLossPct: Float,
    nominalKbps: Int
) {
    val colors = PhoneMicTheme.colors
    StatusSectionCard(
        title = stringResource(R.string.status_section_live_stream),
        icon = Icons.Default.Speed,
        tag = "status_section_live_stream"
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            val lossStr = if (uiState.isRunning || totalFrames > 0L) {
                String.format(Locale.US, "%.2f%%", packetLossPct)
            } else "0.00%"
            val lossColor = when {
                packetLossPct >= 3f -> colors.statusError
                packetLossPct >= 0.5f -> colors.statusWarning
                else -> colors.textPrimary
            }
            MetricTile(
                label = stringResource(R.string.stat_packet_loss),
                value = lossStr,
                sub = "${uiState.packetsDropped} dropped",
                valueColor = lossColor,
                modifier = Modifier.weight(1f)
            )

            val isActivelySending = uiState.isRunning && !uiState.isPaused &&
                (!uiState.pushToTalkEnabled || uiState.isPttPressed)
            val rateStr = if (isActivelySending) {
                if (uiState.packetRate > 0f) String.format(Locale.US, "%.1f", uiState.packetRate) else "100.0"
            } else "0.0"
            MetricTile(
                label = stringResource(R.string.stat_stream_rate),
                value = rateStr,
                sub = "pkt/sec",
                modifier = Modifier.weight(1f)
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            val mb = uiState.bytesSent / (1024f * 1024f)
            val transferredVal = when {
                uiState.bytesSent == 0L && !uiState.isRunning -> "0.00"
                else -> String.format(Locale.US, "%.2f", mb)
            }
            MetricTile(
                label = stringResource(R.string.stat_transferred),
                value = "$transferredVal MB",
                sub = String.format(Locale.US, "%,d pkts", uiState.packetsSent),
                modifier = Modifier.weight(1f)
            )

            val bitrateVal = if (uiState.isRunning && !uiState.isPaused &&
                (!uiState.pushToTalkEnabled || uiState.isPttPressed)
            ) {
                String.format(Locale.US, "%d", nominalKbps)
            } else "0"
            MetricTile(
                label = stringResource(R.string.stat_bitrate),
                value = bitrateVal,
                sub = "kbps",
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun StatusAudioSection(
    sampleRateHz: Int,
    audioFormatLabel: String,
    channelLabel: String,
    payloadBytes: Int,
    wireProtocol: String,
    selectedMicName: String
) {
    val sampleRateLabel = remember(sampleRateHz) { String.format(Locale.US, "%,d Hz", sampleRateHz) }
    val bufferLabel = remember(payloadBytes) { "10 ms ($payloadBytes B)" }
    StatusSectionCard(
        title = stringResource(R.string.status_section_audio),
        icon = Icons.Default.GraphicEq,
        tag = "status_section_audio"
    ) {
        StatusSpecRow(label = "Sampling Rate", value = sampleRateLabel)
        StatusSpecRow(label = "Audio Format", value = audioFormatLabel)
        StatusSpecRow(label = "Channels", value = channelLabel)
        StatusSpecRow(label = "Packet Buffer", value = bufferLabel)
        StatusSpecRow(label = "Protocol", value = wireProtocol)
        StatusSpecRow(label = "Input Device", value = selectedMicName)
    }
}

@Composable
private fun StatusDeviceSection(
    targetReceiverText: String,
    elapsedSeconds: Long
) {
    StatusSectionCard(
        title = stringResource(R.string.status_section_device),
        icon = Icons.Default.Smartphone,
        tag = "status_section_device"
    ) {
        StatusSpecRow(label = "Device Model", value = DeviceProfile.deviceDisplayName)
        StatusSpecRow(label = "Platform OS", value = DeviceProfile.osDisplayName)
        StatusSpecRow(label = "Chipset / SoC", value = DeviceProfile.chipsetDisplayName)
        StatusSpecRow(label = "Target Receiver", value = targetReceiverText)
        StatusSpecRow(label = "Session Timer", value = formatElapsedHms(elapsedSeconds))
        StatusSpecRow(label = "Receiver Version", value = "v${BuildConfig.VERSION_NAME}")
    }
}

@Composable
private fun StatusSectionCard(
    title: String,
    icon: ImageVector,
    tag: String,
    content: @Composable () -> Unit
) {
    val colors = PhoneMicTheme.colors
    OutlinedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(tag),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.outlinedCardColors(containerColor = colors.cardSurface),
        border = BorderStroke(1.dp, colors.border)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = colors.accent,
                    modifier = Modifier.size(16.dp)
                )
                Text(
                    text = title,
                    color = colors.accent,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.8.sp
                )
            }
            content()
        }
    }
}

@Composable
private fun MetricTile(
    label: String,
    value: String,
    sub: String,
    modifier: Modifier = Modifier,
    valueColor: Color = PhoneMicTheme.colors.textPrimary
) {
    val colors = PhoneMicTheme.colors
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(10.dp),
        color = colors.nestedSurface,
        border = BorderStroke(1.dp, colors.border)
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            Text(
                text = label,
                color = colors.textMuted,
                fontSize = 9.5.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.5.sp,
                maxLines = 1
            )
            Text(
                text = value,
                color = valueColor,
                fontSize = 16.sp,
                fontFamily = JetBrainsMonoFontFamily,
                fontWeight = FontWeight.Bold,
                maxLines = 1
            )
            Text(
                text = sub,
                color = colors.accent,
                fontSize = 10.sp,
                fontFamily = JetBrainsMonoFontFamily,
                maxLines = 1
            )
        }
    }
}

@Composable
private fun StatusSpecRow(label: String, value: String) {
    val colors = PhoneMicTheme.colors
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = colors.nestedSurface
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 10.dp, vertical = 9.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = label,
                color = colors.textSecondary,
                fontSize = 12.sp
            )
            Text(
                text = value,
                color = colors.textPrimary,
                fontSize = 12.sp,
                fontFamily = JetBrainsMonoFontFamily,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}
