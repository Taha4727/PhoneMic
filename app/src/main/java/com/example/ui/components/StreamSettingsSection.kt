package com.example.ui.components

import android.content.Context
import android.content.Intent
import android.provider.Settings
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Usb
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.PhoneMicService
import com.example.ui.theme.ElectricBlue
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary
import java.util.Locale

@Composable
fun StreamSettingsSection(
    connectionMode: String,
    transportMode: String,
    micMode: String,
    gain: Float,
    isEnabled: Boolean,
    onConnectionModeChange: (String) -> Unit,
    onTransportModeChange: (String) -> Unit,
    onMicModeChange: (String) -> Unit,
    onGainChange: (Float) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(StudioCard, RoundedCornerShape(20.dp))
            .border(1.dp, StudioBorder, RoundedCornerShape(20.dp))
            .padding(18.dp)
            .testTag("stream_settings_card"),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "AUDIO & STREAM CONFIGURATION",
            color = TextSecondary,
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp
        )

        // 1. Connection Mode (Wi-Fi vs USB)
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Connection Route", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF0F1622), RoundedCornerShape(12.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                val isWifi = connectionMode == PhoneMicService.CONNECTION_WIFI
                SegmentOption(
                    title = "Wi-Fi (Wireless)",
                    icon = Icons.Default.Wifi,
                    isSelected = isWifi,
                    enabled = isEnabled,
                    onClick = { onConnectionModeChange(PhoneMicService.CONNECTION_WIFI) },
                    modifier = Modifier.weight(1f)
                )
                SegmentOption(
                    title = "USB Tethering",
                    icon = Icons.Default.Usb,
                    isSelected = !isWifi,
                    enabled = isEnabled,
                    onClick = { onConnectionModeChange(PhoneMicService.CONNECTION_USB) },
                    modifier = Modifier.weight(1f)
                )
            }

            AnimatedVisibility(visible = connectionMode == PhoneMicService.CONNECTION_USB) {
                OutlinedButton(
                    onClick = { openTetherSettings(context) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(42.dp),
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = NeonCyan
                    ),
                    border = ButtonDefaults.outlinedButtonBorder.copy(
                        brush = androidx.compose.ui.graphics.SolidColor(Color(0xFF1E3A5A))
                    )
                ) {
                    Icon(imageVector = Icons.Default.OpenInNew, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Open System USB Tethering Settings", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                }
            }
        }

        // 2. Transport Protocol (UDP vs TCP)
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Transport Protocol", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                Text(
                    text = if (transportMode == PhoneMicService.TRANSPORT_UDP) "Low Latency (Recommended)" else "Lossless Delivery",
                    color = TextMuted,
                    fontSize = 11.sp
                )
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF0F1622), RoundedCornerShape(12.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                val isUdp = transportMode == PhoneMicService.TRANSPORT_UDP
                SegmentOption(
                    title = "UDP (Gaming/Calls)",
                    icon = null,
                    isSelected = isUdp,
                    enabled = isEnabled,
                    onClick = { onTransportModeChange(PhoneMicService.TRANSPORT_UDP) },
                    modifier = Modifier.weight(1f)
                )
                SegmentOption(
                    title = "TCP (Podcasts/Lossless)",
                    icon = null,
                    isSelected = !isUdp,
                    enabled = isEnabled,
                    onClick = { onTransportModeChange(PhoneMicService.TRANSPORT_TCP) },
                    modifier = Modifier.weight(1f)
                )
            }
        }

        // 3. Microphone Profile
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Microphone Profile", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF0F1622), RoundedCornerShape(12.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                val profiles = listOf(
                    Triple(PhoneMicService.MIC_UNPROCESSED, "Studio Raw", "Unprocessed pure master"),
                    Triple(PhoneMicService.MIC_RAW, "Voice Clean", "Processed noise-free"),
                    Triple(PhoneMicService.MIC_CALL, "Standard", "Hardware default"),
                    Triple(PhoneMicService.MIC_CAMCORDER, "Camcorder", "Wide room pickup")
                )
                profiles.forEach { (mode, label, _) ->
                    SegmentOption(
                        title = label,
                        icon = null,
                        isSelected = micMode == mode,
                        enabled = isEnabled,
                        onClick = { onMicModeChange(mode) },
                        modifier = Modifier.weight(1f)
                    )
                }
            }

            // Profile Hint Box
            val hintText = when (micMode) {
                PhoneMicService.MIC_UNPROCESSED -> "Studio Raw (Unprocessed). Zero DSP compression, raw 48 kHz linear PCM input ideal for POCO X6 Pro / Android 16."
                PhoneMicService.MIC_CALL -> "Standard phone call tuning. Direct standard hardware microphone."
                PhoneMicService.MIC_CAMCORDER -> "Wide dynamic range with ambient acoustic sensitivity for studio/room capture."
                else -> "Voice Recognition tuning. Background noise suppression and acoustic echo cancellation active."
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF0F1723), RoundedCornerShape(8.dp))
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Info,
                    contentDescription = null,
                    tint = NeonCyan,
                    modifier = Modifier.size(14.dp)
                )
                Text(
                    text = hintText,
                    color = TextSecondary,
                    fontSize = 11.sp,
                    lineHeight = 15.sp
                )
            }
        }

        // 4. Digital Mic Gain Booster Slider
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.VolumeUp,
                        contentDescription = null,
                        tint = NeonCyan,
                        modifier = Modifier.size(16.dp)
                    )
                    Text("Digital Gain Boost", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                }

                val percent = (gain * 100).toInt()
                Text(
                    text = "$percent% (${String.format(Locale.US, "%+.1f dB", 20 * kotlin.math.log10(gain.toDouble()))})",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 12.sp
                )
            }

            Slider(
                value = gain,
                onValueChange = onGainChange,
                valueRange = 0.5f..3.0f,
                steps = 25,
                colors = SliderDefaults.colors(
                    thumbColor = NeonCyan,
                    activeTrackColor = NeonCyan,
                    inactiveTrackColor = Color(0xFF1E2838)
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("gain_slider")
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("0.5x (Quiet)", color = TextMuted, fontSize = 10.sp)
                Text("1.0x (Normal)", color = TextSecondary, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                Text("3.0x (Max Boost)", color = TextMuted, fontSize = 10.sp)
            }
        }
    }
}

@Composable
private fun SegmentOption(
    title: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector?,
    isSelected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val bgColor = if (isSelected) Color(0xFF14293D) else Color.Transparent
    val borderColor = if (isSelected) NeonCyan.copy(alpha = 0.8f) else Color.Transparent
    val textColor = if (isSelected) NeonCyan else TextSecondary

    Box(
        modifier = modifier
            .height(38.dp)
            .background(bgColor, RoundedCornerShape(10.dp))
            .border(1.dp, borderColor, RoundedCornerShape(10.dp))
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 6.dp),
        contentAlignment = Alignment.Center
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            if (icon != null) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = textColor,
                    modifier = Modifier.size(14.dp)
                )
            }
            Text(
                text = title,
                color = textColor,
                fontSize = 11.sp,
                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                maxLines = 1
            )
        }
    }
}

private fun openTetherSettings(context: Context) {
    val direct = Intent(Intent.ACTION_MAIN).apply {
        setClassName("com.android.settings", "com.android.settings.TetherSettings")
    }
    try {
        context.startActivity(direct)
        return
    } catch (_: Exception) {}

    try {
        context.startActivity(Intent("android.settings.TETHER_SETTINGS"))
        return
    } catch (_: Exception) {}

    try {
        context.startActivity(Intent(Settings.ACTION_WIRELESS_SETTINGS))
    } catch (_: Exception) {}
}
