package com.example.ui.components

import androidx.compose.animation.animateColorAsState
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
import androidx.compose.material.icons.filled.CellTower
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.PhoneMicService
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StreamActiveGreen
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary

@Composable
fun AudioQualitySelector(
    selectedQuality: PhoneMicService.Companion.AudioQuality,
    isEnabled: Boolean,
    onQualitySelected: (PhoneMicService.Companion.AudioQuality) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(StudioCard, RoundedCornerShape(16.dp))
            .border(1.dp, StudioBorder, RoundedCornerShape(16.dp))
            .padding(12.dp)
            .testTag("audio_quality_selector_card"),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "AUDIO QUALITY & BANDWIDTH",
                color = TextSecondary,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.8.sp
            )

            // Live bandwidth badge
            Box(
                modifier = Modifier
                    .background(
                        when (selectedQuality) {
                            PhoneMicService.Companion.AudioQuality.LOW_BANDWIDTH_16K -> StreamActiveGreen.copy(alpha = 0.15f)
                            PhoneMicService.Companion.AudioQuality.BALANCED_24K -> NeonCyan.copy(alpha = 0.15f)
                            else -> Color(0xFF132030)
                        },
                        RoundedCornerShape(6.dp)
                    )
                    .border(
                        1.dp,
                        when (selectedQuality) {
                            PhoneMicService.Companion.AudioQuality.LOW_BANDWIDTH_16K -> StreamActiveGreen.copy(alpha = 0.5f)
                            PhoneMicService.Companion.AudioQuality.BALANCED_24K -> NeonCyan.copy(alpha = 0.5f)
                            else -> StudioBorder
                        },
                        RoundedCornerShape(6.dp)
                    )
                    .padding(horizontal = 7.dp, vertical = 2.dp)
            ) {
                Text(
                    text = selectedQuality.estBandwidth,
                    color = when (selectedQuality) {
                        PhoneMicService.Companion.AudioQuality.LOW_BANDWIDTH_16K -> StreamActiveGreen
                        PhoneMicService.Companion.AudioQuality.BALANCED_24K -> NeonCyan
                        else -> TextPrimary
                    },
                    fontSize = 10.5.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }

        // 3 Quality Options
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            val qualities = listOf(
                Triple(PhoneMicService.Companion.AudioQuality.STUDIO_48K, "Studio", "48 kHz"),
                Triple(PhoneMicService.Companion.AudioQuality.BALANCED_24K, "Balanced", "24 kHz"),
                Triple(PhoneMicService.Companion.AudioQuality.LOW_BANDWIDTH_16K, "Economy", "16 kHz")
            )

            qualities.forEach { (q, title, rate) ->
                val isSelected = selectedQuality == q
                val bgColor by animateColorAsState(
                    targetValue = if (isSelected) Color(0xFF14293D) else Color(0xFF0F1622),
                    label = "bg_${q.id}"
                )
                val borderColor by animateColorAsState(
                    targetValue = if (isSelected) NeonCyan.copy(alpha = 0.8f) else StudioBorder,
                    label = "border_${q.id}"
                )

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .background(bgColor, RoundedCornerShape(10.dp))
                        .border(1.dp, borderColor, RoundedCornerShape(10.dp))
                        .clickable(enabled = isEnabled) { onQualitySelected(q) }
                        .padding(vertical = 8.dp, horizontal = 6.dp)
                        .testTag("quality_option_${q.id}"),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(2.dp)
                    ) {
                        Icon(
                            imageVector = when (q) {
                                PhoneMicService.Companion.AudioQuality.STUDIO_48K -> Icons.Default.GraphicEq
                                PhoneMicService.Companion.AudioQuality.BALANCED_24K -> Icons.Default.Speed
                                else -> Icons.Default.CellTower
                            },
                            contentDescription = null,
                            tint = if (isSelected) NeonCyan else TextMuted,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = title,
                            color = if (isSelected) TextPrimary else TextSecondary,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                            fontSize = 11.5.sp
                        )
                        Text(
                            text = rate,
                            color = if (isSelected) NeonCyan else TextMuted,
                            fontSize = 9.5.sp
                        )
                    }
                }
            }
        }

        // Hint description
        Text(
            text = selectedQuality.desc,
            color = TextSecondary,
            fontSize = 10.5.sp
        )
    }
}
