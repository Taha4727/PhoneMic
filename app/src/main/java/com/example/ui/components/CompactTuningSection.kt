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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Icon
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
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

@Composable
fun CompactTuningSection(
    micMode: String,
    gain: Float,
    isEnabled: Boolean,
    onMicModeChange: (String) -> Unit,
    onGainChange: (Float) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(StudioCard, RoundedCornerShape(16.dp))
            .border(1.dp, StudioBorder, RoundedCornerShape(16.dp))
            .padding(12.dp)
            .testTag("compact_tuning_card"),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // Section Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "MIC PROFILE & GAIN BOOST",
                color = TextSecondary,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.8.sp
            )

            val percent = (gain * 100).toInt()
            Text(
                text = "$percent% (${String.format(Locale.US, "%+.1f dB", 20 * kotlin.math.log10(gain.toDouble()))})",
                color = NeonCyan,
                fontWeight = FontWeight.Bold,
                fontSize = 11.sp
            )
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
                        .height(30.dp)
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

        // Compact Gain Slider
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Icon(
                imageVector = Icons.Default.VolumeUp,
                contentDescription = null,
                tint = TextMuted,
                modifier = Modifier.size(14.dp)
            )

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
                    .weight(1f)
                    .height(28.dp)
                    .testTag("gain_slider")
            )

            Text(
                text = "3x",
                color = TextMuted,
                fontSize = 9.5.sp
            )
        }
    }
}
