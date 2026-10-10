package com.example.ui.components

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material.icons.filled.BatteryAlert
import androidx.compose.material.icons.filled.ElectricBolt
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.DeviceProfile
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StreamWarningAmber
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary

@Composable
fun BatteryOptimizationBanner(
    isIgnored: Boolean,
    onDismissOrGranted: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val isPocoOrXiaomi = DeviceProfile.isXiaomiOrPoco

    AnimatedVisibility(visible = !isIgnored, modifier = modifier) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF221708), RoundedCornerShape(14.dp))
                .border(1.dp, StreamWarningAmber.copy(alpha = 0.5f), RoundedCornerShape(14.dp))
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Icon(
                    imageVector = if (isPocoOrXiaomi) Icons.Default.ElectricBolt else Icons.Default.BatteryAlert,
                    contentDescription = null,
                    tint = StreamWarningAmber,
                    modifier = Modifier.size(24.dp)
                )

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = if (DeviceProfile.isPocoX6Pro) {
                            "POCO X6 Pro 5G • HyperOS Background Guard"
                        } else if (isPocoOrXiaomi) {
                            "Xiaomi / POCO • HyperOS Background Guard"
                        } else {
                            "Background Streaming Protection"
                        },
                        color = TextPrimary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = if (isPocoOrXiaomi) {
                            "HyperOS restricts background apps when screen locks. Allow battery exemption, set Battery Saver to 'No restrictions', and enable 'Autostart'."
                        } else {
                            "Prevent Android Doze from cutting Wi-Fi audio when screen locks."
                        },
                        color = TextSecondary,
                        fontSize = 11.sp,
                        lineHeight = 14.5.sp
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Button(
                    onClick = {
                        requestBatteryExemption(context)
                        onDismissOrGranted()
                    },
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.height(34.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = StreamWarningAmber,
                        contentColor = Color(0xFF2C1900)
                    )
                ) {
                    Text("Allow Doze Exemption", fontSize = 10.5.sp, fontWeight = FontWeight.Bold)
                }

                if (isPocoOrXiaomi) {
                    OutlinedButton(
                        onClick = {
                            DeviceProfile.openHyperOsSettings(context)
                        },
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.height(34.dp),
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = NeonCyan
                        ),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(NeonCyan.copy(alpha = 0.5f))
                        )
                    ) {
                        Icon(imageVector = Icons.Default.Settings, contentDescription = null, modifier = Modifier.size(13.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("HyperOS App Info", fontSize = 10.5.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }
        }
    }
}

private fun requestBatteryExemption(context: Context) {
    try {
        val intent = Intent(
            Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
            Uri.parse("package:" + context.packageName)
        ).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    } catch (_: Exception) {
        try {
            val fallback = Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(fallback)
        } catch (_: Exception) {}
    }
}
