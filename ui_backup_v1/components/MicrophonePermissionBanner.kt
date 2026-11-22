package com.example.ui.components

import android.content.Context
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
import androidx.compose.material.icons.filled.MicOff
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
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.DeviceProfile
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StreamErrorRed
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary

@Composable
fun MicrophonePermissionBanner(
    hasPermission: Boolean,
    onRequestPermission: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val isXiaomiOrPoco = DeviceProfile.isXiaomiOrPoco

    AnimatedVisibility(visible = !hasPermission, modifier = modifier) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF260E12), RoundedCornerShape(14.dp))
                .border(1.dp, StreamErrorRed.copy(alpha = 0.6f), RoundedCornerShape(14.dp))
                .padding(12.dp)
                .testTag("mic_permission_banner"),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.MicOff,
                    contentDescription = null,
                    tint = StreamErrorRed,
                    modifier = Modifier.size(24.dp)
                )

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = if (isXiaomiOrPoco) {
                            "Microphone Permission Required (HyperOS)"
                        } else {
                            "Microphone Permission Required"
                        },
                        color = TextPrimary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = if (isXiaomiOrPoco) {
                            "On Xiaomi / POCO: Tap 'Grant Permission' and select 'While using the app' (avoid 'Only this time' so HyperOS doesn't revoke access). If the dialog doesn't appear, use 'Open App Settings'."
                        } else {
                            "Microphone permission is required to stream real-time audio from your phone to your PC."
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
                    onClick = onRequestPermission,
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier
                        .height(34.dp)
                        .testTag("grant_mic_permission_button"),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = StreamErrorRed,
                        contentColor = Color.White
                    )
                ) {
                    Text("Grant Permission", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                }

                OutlinedButton(
                    onClick = { DeviceProfile.openAppDetailsSettings(context) },
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier
                        .height(34.dp)
                        .testTag("open_app_settings_button"),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = NeonCyan
                    ),
                    border = ButtonDefaults.outlinedButtonBorder.copy(
                        brush = SolidColor(NeonCyan.copy(alpha = 0.5f))
                    )
                ) {
                    Icon(imageVector = Icons.Default.Settings, contentDescription = null, modifier = Modifier.size(13.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Open App Settings", fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}
