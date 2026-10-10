package com.example.ui.components

import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.provider.Settings
import android.widget.Toast
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.FlashOn
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Radar
import androidx.compose.material.icons.filled.Usb
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.PhoneMicService
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StreamActiveGreen
import com.example.ui.theme.StreamErrorRed
import com.example.ui.theme.StreamWarningAmber
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary

@Composable
fun NetworkConfigSection(
    ip: String,
    port: String,
    isValidIp: Boolean,
    isValidPort: Boolean,
    isEnabled: Boolean,
    isScanningPc: Boolean,
    scanFeedback: String?,
    onIpChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onScanClick: () -> Unit,
    connectionMode: String = PhoneMicService.CONNECTION_WIFI,
    transportMode: String = PhoneMicService.TRANSPORT_UDP,
    onConnectionModeChange: ((String) -> Unit)? = null,
    onTransportModeChange: ((String) -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(StudioCard, RoundedCornerShape(16.dp))
            .border(1.dp, StudioBorder, RoundedCornerShape(16.dp))
            .padding(12.dp)
            .testTag("network_config_card"),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // Section Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "TARGET PC RECEIVER",
                color = TextSecondary,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.8.sp
            )

            if (isValidIp && ip.isNotEmpty()) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(3.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.CheckCircle,
                        contentDescription = "Valid IPv4",
                        tint = StreamActiveGreen,
                        modifier = Modifier.size(12.dp)
                    )
                    Text(
                        text = "READY",
                        color = StreamActiveGreen,
                        fontSize = 9.5.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        // IP and Port Fields Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            // IP Input
            OutlinedTextField(
                value = ip,
                onValueChange = onIpChange,
                enabled = isEnabled,
                label = { Text("Receiver IP", fontSize = 10.5.sp, maxLines = 1) },
                placeholder = { Text("192.168.1.100", fontSize = 11.5.sp, color = TextMuted) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                isError = ip.isNotEmpty() && !isValidIp,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = NeonCyan,
                    unfocusedBorderColor = StudioBorder,
                    errorBorderColor = StreamErrorRed,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                    cursorColor = NeonCyan,
                    focusedLabelColor = NeonCyan,
                    unfocusedLabelColor = TextSecondary
                ),
                textStyle = androidx.compose.ui.text.TextStyle(
                    fontFamily = FontFamily.Monospace,
                    fontSize = 12.5.sp
                ),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier
                    .weight(0.72f)
                    .height(52.dp)
                    .testTag("ip_address_input")
            )

            // Port Input
            OutlinedTextField(
                value = port,
                onValueChange = onPortChange,
                enabled = isEnabled,
                label = { Text("Port", fontSize = 10.5.sp, maxLines = 1) },
                placeholder = { Text("5001", fontSize = 11.5.sp, color = TextMuted) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                isError = port.isNotEmpty() && !isValidPort,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = NeonCyan,
                    unfocusedBorderColor = StudioBorder,
                    errorBorderColor = StreamErrorRed,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                    cursorColor = NeonCyan,
                    focusedLabelColor = NeonCyan,
                    unfocusedLabelColor = TextSecondary
                ),
                textStyle = androidx.compose.ui.text.TextStyle(
                    fontFamily = FontFamily.Monospace,
                    fontSize = 12.5.sp
                ),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier
                    .weight(0.28f)
                    .height(52.dp)
                    .testTag("port_number_input")
            )
        }

        // Auto-Detect PC Button (Clean text that never overflows!)
        Button(
            onClick = onScanClick,
            enabled = isEnabled && !isScanningPc,
            modifier = Modifier
                .fillMaxWidth()
                .height(38.dp)
                .testTag("find_pc_button"),
            shape = RoundedCornerShape(8.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Color(0xFF14293D),
                contentColor = NeonCyan,
                disabledContainerColor = Color(0xFF101B26),
                disabledContentColor = TextMuted
            ),
            border = ButtonDefaults.outlinedButtonBorder.copy(
                brush = androidx.compose.ui.graphics.SolidColor(Color(0xFF1E3A5A))
            )
        ) {
            if (isScanningPc) {
                CircularProgressIndicator(
                    modifier = Modifier.size(13.dp),
                    color = NeonCyan,
                    strokeWidth = 2.dp
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "Searching...",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1
                )
            } else {
                Icon(
                    imageVector = Icons.Default.Radar,
                    contentDescription = null,
                    modifier = Modifier.size(15.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "Auto-Detect PC",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1
                )
            }
        }

        // Scan feedback banner if available
        AnimatedVisibility(visible = scanFeedback != null) {
            val isSuccess = scanFeedback?.startsWith("Found") == true
            val bannerColor = if (isSuccess) StreamActiveGreen else StreamWarningAmber

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(bannerColor.copy(alpha = 0.12f), RoundedCornerShape(6.dp))
                    .border(1.dp, bannerColor.copy(alpha = 0.35f), RoundedCornerShape(6.dp))
                    .padding(horizontal = 8.dp, vertical = 5.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(5.dp)
            ) {
                Icon(
                    imageVector = if (isSuccess) Icons.Default.CheckCircle else Icons.Default.ErrorOutline,
                    contentDescription = null,
                    tint = bannerColor,
                    modifier = Modifier.size(13.dp)
                )
                Text(
                    text = scanFeedback ?: "",
                    color = bannerColor,
                    fontSize = 10.5.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1
                )
            }
        }

        // Quick Route & Protocol Toggles
        if (onConnectionModeChange != null && onTransportModeChange != null) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                // Route Toggle (Wi-Fi vs USB)
                val isWifi = connectionMode == PhoneMicService.CONNECTION_WIFI
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(34.dp)
                        .background(Color(0xFF0F1622), RoundedCornerShape(6.dp))
                        .border(
                            1.dp,
                            if (isWifi) NeonCyan.copy(alpha = 0.7f) else Color(0xFF223044),
                            RoundedCornerShape(6.dp)
                        )
                        .clickable(enabled = isEnabled) {
                            onConnectionModeChange(if (isWifi) PhoneMicService.CONNECTION_USB else PhoneMicService.CONNECTION_WIFI)
                        }
                        .padding(horizontal = 6.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Icon(
                            imageVector = if (isWifi) Icons.Default.Wifi else Icons.Default.Usb,
                            contentDescription = null,
                            tint = if (isWifi) NeonCyan else Color(0xFF38BDF8),
                            modifier = Modifier.size(12.dp)
                        )
                        Text(
                            text = if (isWifi) "Wi-Fi" else "USB Tether",
                            color = TextPrimary,
                            fontSize = 10.5.sp,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 1
                        )
                    }
                }

                // Transport Toggle (UDP vs TCP)
                val isUdp = transportMode == PhoneMicService.TRANSPORT_UDP
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(34.dp)
                        .background(Color(0xFF0F1622), RoundedCornerShape(6.dp))
                        .border(
                            1.dp,
                            if (isUdp) NeonCyan.copy(alpha = 0.7f) else Color(0xFF223044),
                            RoundedCornerShape(6.dp)
                        )
                        .clickable(enabled = isEnabled) {
                            onTransportModeChange(if (isUdp) PhoneMicService.TRANSPORT_TCP else PhoneMicService.TRANSPORT_UDP)
                        }
                        .padding(horizontal = 6.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = if (isUdp) "UDP (Low Latency)" else "TCP (Lossless)",
                        color = if (isUdp) NeonCyan else TextPrimary,
                        fontSize = 10.5.sp,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1
                    )
                }
            }

            // Direct USB Tethering Toggle Action (Handles Android 7.1.1 reflection + Android 10 fallback)
            AnimatedVisibility(visible = connectionMode == PhoneMicService.CONNECTION_USB) {
                OutlinedButton(
                    onClick = { toggleOrOpenUsbTethering(context) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(34.dp),
                    shape = RoundedCornerShape(6.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = NeonCyan),
                    border = ButtonDefaults.outlinedButtonBorder.copy(
                        brush = androidx.compose.ui.graphics.SolidColor(Color(0xFF1E3A5A))
                    )
                ) {
                    Icon(imageVector = Icons.Default.Usb, contentDescription = null, modifier = Modifier.size(13.dp))
                    Spacer(modifier = Modifier.width(5.dp))
                    Text("Turn On USB Tethering", fontSize = 10.5.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
                }
            }
        }
    }
}

/**
 * Tries to enable USB tethering directly via reflection (supported on many Android 7.1.1 builds),
 * and automatically falls back to opening the system Tethering settings on Android 10.
 */
fun toggleOrOpenUsbTethering(context: Context) {
    try {
        val cm = context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        if (cm != null) {
            val method = cm.javaClass.getDeclaredMethod("setUsbTethering", Boolean::class.javaPrimitiveType)
            method.isAccessible = true
            val result = method.invoke(cm, true)
            // If invocation succeeds without exception
            Toast.makeText(context, "Enabling USB Tethering...", Toast.LENGTH_SHORT).show()
            return
        }
    } catch (_: Exception) {
        // Fallback to settings screen
    }

    openTetherSettingsCompatible(context)
}

/**
 * Robust tethering settings launcher compatible with Android 7.1.1 (API 25) and Android 10 (API 29).
 */
fun openTetherSettingsCompatible(context: Context) {
    val intents = listOf(
        Intent(Intent.ACTION_MAIN).apply {
            setClassName("com.android.settings", "com.android.settings.TetherSettings")
        },
        Intent("android.settings.TETHER_SETTINGS"),
        Intent(Settings.ACTION_WIRELESS_SETTINGS),
        Intent(Settings.ACTION_SETTINGS)
    )
    for (intent in intents) {
        try {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            return
        } catch (_: Exception) {}
    }
    Toast.makeText(context, "Please enable USB Tethering in Settings", Toast.LENGTH_SHORT).show()
}
