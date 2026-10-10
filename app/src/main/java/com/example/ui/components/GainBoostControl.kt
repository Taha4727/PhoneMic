package com.example.ui.components

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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
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
import com.example.PhoneMicService
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary
import java.util.Locale
import kotlin.math.log10
import kotlin.math.roundToInt

@Composable
fun GainBoostControl(
    micMode: String,
    gain: Float,
    isEnabled: Boolean,
    onMicModeChange: (String) -> Unit,
    onGainChange: (Float) -> Unit,
    modifier: Modifier = Modifier
) {
    // Snap cleanly to single decimal place (e.g. 1.0, 1.1, 1.2)
    val cleanGain = ((gain * 10f).roundToInt() / 10f).coerceIn(0.5f, 3.0f)
    val dbVal = if (cleanGain > 0f) 20f * log10(cleanGain) else 0f
    val dbFormatted = if (cleanGain == 1.0f) "0.0 dB" else String.format(Locale.US, "%+.1f dB", dbVal)

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(StudioCard, RoundedCornerShape(14.dp))
            .border(1.dp, StudioBorder, RoundedCornerShape(14.dp))
            .padding(12.dp)
            .testTag("gain_boost_card"),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // Section Header with Exact Clean Readout
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
                    modifier = Modifier.size(14.dp)
                )
                Text(
                    text = "GAIN BOOST & MIC PROFILE",
                    color = TextSecondary,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.8.sp
                )
            }

            // Accurate, non-jumping readout
            Text(
                text = "${String.format(Locale.US, "%.1fx", cleanGain)} ($dbFormatted)",
                color = NeonCyan,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                fontSize = 12.sp
            )
        }

        // Stepper Controls + Slider Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            // Minus Button (-0.1x)
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .background(Color(0xFF142436), RoundedCornerShape(6.dp))
                    .border(1.dp, StudioBorder, RoundedCornerShape(6.dp))
                    .clickable(enabled = isEnabled && cleanGain > 0.5f) {
                        val next = ((cleanGain - 0.1f) * 10f).roundToInt() / 10f
                        onGainChange(next.coerceIn(0.5f, 3.0f))
                    },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Remove,
                    contentDescription = "Decrease Gain",
                    tint = if (cleanGain > 0.5f) NeonCyan else TextMuted,
                    modifier = Modifier.size(16.dp)
                )
            }

            // Precise Slider (25 clean steps from 0.5 to 3.0 = 0.1 per step)
            Slider(
                value = cleanGain,
                onValueChange = { raw ->
                    val rounded = ((raw * 10f).roundToInt() / 10f).coerceIn(0.5f, 3.0f)
                    onGainChange(rounded)
                },
                valueRange = 0.5f..3.0f,
                steps = 24, // 25 intervals of 0.1 each
                enabled = isEnabled,
                colors = SliderDefaults.colors(
                    thumbColor = NeonCyan,
                    activeTrackColor = NeonCyan,
                    inactiveTrackColor = Color(0xFF192535)
                ),
                modifier = Modifier
                    .weight(1f)
                    .height(28.dp)
                    .testTag("gain_slider")
            )

            // Plus Button (+0.1x)
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .background(Color(0xFF142436), RoundedCornerShape(6.dp))
                    .border(1.dp, StudioBorder, RoundedCornerShape(6.dp))
                    .clickable(enabled = isEnabled && cleanGain < 3.0f) {
                        val next = ((cleanGain + 0.1f) * 10f).roundToInt() / 10f
                        onGainChange(next.coerceIn(0.5f, 3.0f))
                    },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Add,
                    contentDescription = "Increase Gain",
                    tint = if (cleanGain < 3.0f) NeonCyan else TextMuted,
                    modifier = Modifier.size(16.dp)
                )
            }
        }

        // Quick Preset Chips (Direct 1-tap exact presets)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            val presets = listOf(0.8f, 1.0f, 1.5f, 2.0f, 2.5f)
            presets.forEach { target ->
                val isSelected = Math.abs(cleanGain - target) < 0.05f
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(26.dp)
                        .background(
                            if (isSelected) Color(0xFF142E44) else Color(0xFF0F1622),
                            RoundedCornerShape(6.dp)
                        )
                        .border(
                            1.dp,
                            if (isSelected) NeonCyan else Color(0xFF1E2838),
                            RoundedCornerShape(6.dp)
                        )
                        .clickable(enabled = isEnabled) { onGainChange(target) },
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = if (target == 1.0f) "1.0x" else "${target}x",
                        color = if (isSelected) NeonCyan else TextSecondary,
                        fontSize = 10.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                    )
                }
            }
        }

        // Mic Profile Segmented Buttons
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF0F1622), RoundedCornerShape(8.dp))
                .padding(3.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            val profiles = listOf(
                Pair(PhoneMicService.MIC_UNPROCESSED, "Studio Raw"),
                Pair(PhoneMicService.MIC_RAW, "Voice Clean"),
                Pair(PhoneMicService.MIC_CALL, "Standard"),
                Pair(PhoneMicService.MIC_CAMCORDER, "Camcorder")
            )

            profiles.forEach { (mode, label) ->
                val isSelected = micMode == mode
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(28.dp)
                        .background(
                            if (isSelected) Color(0xFF14293D) else Color.Transparent,
                            RoundedCornerShape(6.dp)
                        )
                        .border(
                            1.dp,
                            if (isSelected) NeonCyan.copy(alpha = 0.8f) else Color.Transparent,
                            RoundedCornerShape(6.dp)
                        )
                        .clickable(enabled = isEnabled) { onMicModeChange(mode) },
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = label,
                        color = if (isSelected) NeonCyan else TextSecondary,
                        fontSize = 10.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                        maxLines = 1
                    )
                }
            }
        }
    }
}
