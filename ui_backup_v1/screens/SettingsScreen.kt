package com.example.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.BluetoothAudio
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.HeadsetMic
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.Usb
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.BuildConfig
import com.example.DeviceProfile
import com.example.PhoneMicService
import com.example.PhoneMicUiState
import com.example.R
import com.example.audio.AudioChannelOption
import com.example.audio.AudioFormatOption
import com.example.audio.AudioProtocol
import com.example.audio.MicDeviceKind
import com.example.audio.VisualizerStyle
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StreamWarningAmber
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.StudioCardSelected
import com.example.ui.theme.StudioDarkBg
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary
import java.util.Locale
import kotlin.math.roundToInt

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(
    uiState: PhoneMicUiState,
    onBack: () -> Unit,
    onAutoStartChange: (Boolean) -> Unit,
    onPushToTalkChange: (Boolean) -> Unit,
    onAutoReconnectChange: (Boolean) -> Unit,
    onKeepScreenAwakeChange: (Boolean) -> Unit,
    onOverlayToggle: (Boolean) -> Unit,
    onRefreshMics: () -> Unit,
    onSelectMicDevice: (Int) -> Unit,
    onSelectAudioSource: (String) -> Unit,
    onSelectSampleRate: (Int) -> Unit,
    onSelectAudioFormat: (AudioFormatOption) -> Unit,
    onSelectChannels: (Int) -> Unit,
    onGainChange: (Float) -> Unit,
    onVisualizerEnabledChange: (Boolean) -> Unit,
    onVisualizerStyleChange: (VisualizerStyle) -> Unit,
    onOpenGuide: () -> Unit,
    onShareCli: () -> Unit,
    modifier: Modifier = Modifier
) {
    BackHandler(onBack = onBack)

    val audioEditable = !uiState.isRunning

    Scaffold(
        modifier = modifier
            .fillMaxSize()
            .background(StudioDarkBg)
            .testTag("settings_screen"),
        containerColor = StudioDarkBg,
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(StudioDarkBg)
                    .statusBarsPadding()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(
                        onClick = onBack,
                        modifier = Modifier
                            .size(48.dp)
                            .testTag("settings_back_button")
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.settings_back_cd),
                            tint = TextPrimary
                        )
                    }

                    Spacer(modifier = Modifier.width(4.dp))

                    Column {
                        Text(
                            text = stringResource(R.string.settings_title),
                            color = TextPrimary,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Stream, Audio Engine, Visualizer & App Info",
                            color = TextMuted,
                            fontSize = 11.sp
                        )
                    }
                }
                HorizontalDivider(color = StudioBorder)
            }
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .navigationBarsPadding()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 640.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // =============================================================
                // 1. GENERAL
                // =============================================================
                SettingsSectionCard(
                    title = stringResource(R.string.settings_section_general),
                    icon = Icons.Default.Settings,
                    sectionTag = "settings_section_general"
                ) {
                    SettingsSwitchRow(
                        title = stringResource(R.string.setting_auto_start_title),
                        subtitle = stringResource(R.string.setting_auto_start_desc),
                        checked = uiState.autoStartStreaming,
                        onCheckedChange = onAutoStartChange,
                        tag = "setting_auto_start"
                    )
                    HorizontalDivider(color = Color(0xFF202C3D))
                    SettingsSwitchRow(
                        title = stringResource(R.string.setting_ptt_title),
                        subtitle = stringResource(R.string.setting_ptt_desc),
                        checked = uiState.pushToTalkEnabled,
                        onCheckedChange = onPushToTalkChange,
                        tag = "setting_ptt_mode"
                    )
                    HorizontalDivider(color = Color(0xFF202C3D))
                    SettingsSwitchRow(
                        title = stringResource(R.string.setting_auto_reconnect_title),
                        subtitle = stringResource(R.string.setting_auto_reconnect_desc),
                        checked = uiState.autoReconnectEnabled,
                        onCheckedChange = onAutoReconnectChange,
                        tag = "setting_auto_reconnect"
                    )
                    HorizontalDivider(color = Color(0xFF202C3D))
                    SettingsSwitchRow(
                        title = stringResource(R.string.setting_keep_awake_title),
                        subtitle = stringResource(R.string.setting_keep_awake_desc),
                        checked = uiState.keepScreenAwake,
                        onCheckedChange = onKeepScreenAwakeChange,
                        tag = "setting_keep_awake"
                    )
                    HorizontalDivider(color = Color(0xFF202C3D))
                    SettingsSwitchRow(
                        title = stringResource(R.string.setting_overlay_title),
                        subtitle = stringResource(R.string.setting_overlay_desc),
                        checked = uiState.isOverlayEnabled,
                        onCheckedChange = onOverlayToggle,
                        tag = "setting_overlay"
                    )
                }

                // =============================================================
                // 2. AUDIO
                // =============================================================
                SettingsSectionCard(
                    title = stringResource(R.string.settings_section_audio),
                    icon = Icons.Default.Tune,
                    sectionTag = "settings_section_audio"
                ) {
                    if (!audioEditable) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(Color(0xFF332600), RoundedCornerShape(8.dp))
                                .border(1.dp, StreamWarningAmber.copy(alpha = 0.5f), RoundedCornerShape(8.dp))
                                .padding(horizontal = 10.dp, vertical = 8.dp)
                                .testTag("audio_locked_banner")
                        ) {
                            Text(
                                text = stringResource(R.string.setting_audio_locked_note),
                                color = StreamWarningAmber,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }

                    // 2A. Physical Microphone Device Picker
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = stringResource(R.string.setting_physical_mic_title),
                            color = TextPrimary,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                        IconButton(
                            onClick = onRefreshMics,
                            modifier = Modifier
                                .size(48.dp)
                                .testTag("refresh_mics_button")
                        ) {
                            Icon(
                                imageVector = Icons.Default.Refresh,
                                contentDescription = stringResource(R.string.setting_physical_mic_refresh),
                                tint = NeonCyan,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }

                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        uiState.availableMics.forEach { mic ->
                            val selected = uiState.preferredMicId == mic.id
                            val micIcon = when (mic.kind) {
                                MicDeviceKind.BLUETOOTH -> Icons.Default.BluetoothAudio
                                MicDeviceKind.USB -> Icons.Default.Usb
                                MicDeviceKind.WIRED -> Icons.Default.HeadsetMic
                                else -> Icons.Default.Mic
                            }
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(48.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(if (selected) StudioCardSelected else Color(0xFF101824))
                                    .border(
                                        1.dp,
                                        if (selected) NeonCyan else Color(0xFF1E293B),
                                        RoundedCornerShape(8.dp)
                                    )
                                    .alpha(if (audioEditable) 1f else 0.55f)
                                    .clickable(enabled = audioEditable) { onSelectMicDevice(mic.id) }
                                    .padding(horizontal = 10.dp)
                                    .testTag("mic_device_${mic.id}"),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Icon(
                                    imageVector = micIcon,
                                    contentDescription = null,
                                    tint = if (selected) NeonCyan else TextSecondary,
                                    modifier = Modifier.size(18.dp)
                                )
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = mic.name,
                                        color = if (selected) NeonCyan else TextPrimary,
                                        fontSize = 12.sp,
                                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Text(
                                        text = mic.typeLabel,
                                        color = TextMuted,
                                        fontSize = 10.sp,
                                        maxLines = 1
                                    )
                                }
                                if (selected) {
                                    Text(
                                        text = "ACTIVE",
                                        color = NeonCyan,
                                        fontSize = 9.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }
                    }

                    HorizontalDivider(color = Color(0xFF202C3D))

                    // 2B. Android AudioSource Processing Mode
                    SettingSubLabel(stringResource(R.string.setting_audio_source_title))
                    val audioSources = listOf(
                        Triple(PhoneMicService.MIC_STANDARD, "Standard", "Default MIC"),
                        Triple(PhoneMicService.MIC_UNPROCESSED, "Unprocessed", "Studio Raw"),
                        Triple(PhoneMicService.MIC_RAW, "Voice Recog.", "NS + Clean"),
                        Triple(PhoneMicService.MIC_CALL, "Voice Comm.", "AEC + AGC"),
                        Triple(PhoneMicService.MIC_CAMCORDER, "Camcorder", "Wide Room")
                    )
                    FlowRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        audioSources.forEach { (mode, title, note) ->
                            OptionChip(
                                title = title,
                                subtitle = note,
                                selected = uiState.micMode == mode,
                                enabled = audioEditable,
                                onClick = { onSelectAudioSource(mode) },
                                tag = "audio_source_$mode"
                            )
                        }
                    }

                    HorizontalDivider(color = Color(0xFF202C3D))

                    // 2C. Sample Rate
                    SettingSubLabel(stringResource(R.string.setting_sample_rate_title))
                    FlowRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        AudioProtocol.SUPPORTED_SAMPLE_RATES.forEach { rate ->
                            val label = if (rate % 1000 == 0) "${rate / 1000} kHz" else "44.1 kHz"
                            OptionChip(
                                title = label,
                                subtitle = "$rate Hz",
                                selected = uiState.sampleRateHz == rate,
                                enabled = audioEditable,
                                onClick = { onSelectSampleRate(rate) },
                                tag = "sample_rate_$rate"
                            )
                        }
                    }

                    HorizontalDivider(color = Color(0xFF202C3D))

                    // 2D. Audio Format
                    SettingSubLabel(stringResource(R.string.setting_audio_format_title))
                    FlowRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        AudioFormatOption.entries.forEach { fmt ->
                            val supported = fmt.isSupportedOnDevice
                            OptionChip(
                                title = fmt.label,
                                subtitle = if (supported) "${fmt.bytesPerSample * 8}-bit" else "Requires Android 12+",
                                selected = uiState.audioFormat == fmt,
                                enabled = audioEditable && supported,
                                onClick = { onSelectAudioFormat(fmt) },
                                tag = "audio_format_${fmt.id}"
                            )
                        }
                    }

                    HorizontalDivider(color = Color(0xFF202C3D))

                    // 2E. Channels
                    SettingSubLabel(stringResource(R.string.setting_channels_title))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        AudioChannelOption.entries.forEach { chOpt ->
                            val selected = uiState.channels == chOpt.count
                            Box(
                                modifier = Modifier
                                    .weight(1f)
                                    .height(48.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(if (selected) StudioCardSelected else Color(0xFF101824))
                                    .border(
                                        1.dp,
                                        if (selected) NeonCyan else Color(0xFF1E293B),
                                        RoundedCornerShape(8.dp)
                                    )
                                    .alpha(if (audioEditable) 1f else 0.55f)
                                    .clickable(enabled = audioEditable) { onSelectChannels(chOpt.count) }
                                    .testTag("channels_${chOpt.count}"),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = chOpt.label,
                                    color = if (selected) NeonCyan else TextPrimary,
                                    fontSize = 12.sp,
                                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium
                                )
                            }
                        }
                    }

                    // 2F. Gain Boost
                    val cleanGain = ((uiState.gain * 10f).roundToInt() / 10f).coerceIn(0.5f, 3.0f)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Microphone Gain Boost",
                            color = TextPrimary,
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = String.format(Locale.US, "%.1fx", cleanGain),
                            color = NeonCyan,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Slider(
                        value = cleanGain,
                        onValueChange = { raw ->
                            onGainChange(((raw * 10f).roundToInt() / 10f).coerceIn(0.5f, 3.0f))
                        },
                        valueRange = 0.5f..3.0f,
                        steps = 24,
                        colors = SliderDefaults.colors(
                            thumbColor = NeonCyan,
                            activeTrackColor = NeonCyan,
                            inactiveTrackColor = Color(0xFF192535)
                        ),
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("settings_gain_slider")
                    )

                    // Live Wire Packet Readout
                    val kbps = AudioProtocol.estimatedKbps(uiState.sampleRateHz, uiState.channels, uiState.audioFormat)
                    val frameBytes = AudioProtocol.framePayloadBytes(uiState.sampleRateHz, uiState.channels, uiState.audioFormat)
                    val proto = if (AudioProtocol.isLegacyStandardStream(uiState.sampleRateHz, uiState.channels, uiState.audioFormat)) {
                        "PM01–PM03 Standard"
                    } else {
                        "PM04 Extended Header"
                    }
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFF0E1622), RoundedCornerShape(8.dp))
                            .border(1.dp, Color(0xFF1E2A3C), RoundedCornerShape(8.dp))
                            .padding(horizontal = 10.dp, vertical = 8.dp)
                            .testTag("audio_wire_summary")
                    ) {
                        Text(
                            text = "~$kbps kbps  •  $frameBytes B / 10 ms  •  $proto",
                            color = NeonCyan,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }

                // =============================================================
                // 3. APPEARANCE
                // =============================================================
                SettingsSectionCard(
                    title = stringResource(R.string.settings_section_appearance),
                    icon = Icons.Default.Palette,
                    sectionTag = "settings_section_appearance"
                ) {
                    SettingsSwitchRow(
                        title = stringResource(R.string.setting_visualizer_title),
                        subtitle = stringResource(R.string.setting_visualizer_desc),
                        checked = uiState.visualizerEnabled,
                        onCheckedChange = onVisualizerEnabledChange,
                        tag = "setting_visualizer_toggle"
                    )

                    HorizontalDivider(color = Color(0xFF202C3D))

                    SettingSubLabel(stringResource(R.string.setting_visualizer_style_title))
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        VisualizerStyle.entries.forEach { style ->
                            val selected = uiState.visualizerStyle == style
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(48.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(if (selected) StudioCardSelected else Color(0xFF101824))
                                    .border(
                                        1.dp,
                                        if (selected) NeonCyan else Color(0xFF1E293B),
                                        RoundedCornerShape(8.dp)
                                    )
                                    .alpha(if (uiState.visualizerEnabled) 1f else 0.55f)
                                    .clickable(enabled = uiState.visualizerEnabled) {
                                        onVisualizerStyleChange(style)
                                    }
                                    .padding(horizontal = 10.dp)
                                    .testTag("visualizer_style_${style.id}"),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.GraphicEq,
                                    contentDescription = null,
                                    tint = if (selected) NeonCyan else TextSecondary,
                                    modifier = Modifier.size(18.dp)
                                )
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = style.label,
                                        color = if (selected) NeonCyan else TextPrimary,
                                        fontSize = 12.sp,
                                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium
                                    )
                                    Text(
                                        text = style.description,
                                        color = TextMuted,
                                        fontSize = 10.sp
                                    )
                                }
                                if (selected) {
                                    Text(
                                        text = "SELECTED",
                                        color = NeonCyan,
                                        fontSize = 9.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }
                    }

                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFF101824), RoundedCornerShape(8.dp))
                            .border(1.dp, Color(0xFF1E293B), RoundedCornerShape(8.dp))
                            .padding(10.dp)
                            .testTag("appearance_redesign_note")
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(
                                text = stringResource(R.string.setting_appearance_redesign_title),
                                color = TextPrimary,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = stringResource(R.string.setting_appearance_redesign_desc),
                                color = TextMuted,
                                fontSize = 11.sp,
                                lineHeight = 15.sp
                            )
                        }
                    }
                }

                // =============================================================
                // 4. ABOUT
                // =============================================================
                SettingsSectionCard(
                    title = stringResource(R.string.settings_section_about),
                    icon = Icons.Default.Info,
                    sectionTag = "settings_section_about"
                ) {
                    AboutInfoRow(
                        label = stringResource(R.string.setting_about_version),
                        value = "v${BuildConfig.VERSION_NAME} (Build ${BuildConfig.VERSION_CODE})"
                    )
                    AboutInfoRow(
                        label = stringResource(R.string.setting_about_device),
                        value = "${DeviceProfile.deviceDisplayName} • ${DeviceProfile.osDisplayName}"
                    )
                    AboutInfoRow(
                        label = stringResource(R.string.setting_about_protocol),
                        value = stringResource(R.string.setting_about_protocol_val)
                    )

                    HorizontalDivider(color = Color(0xFF202C3D))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedButton(
                            onClick = onOpenGuide,
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp)
                                .testTag("settings_open_guide_button"),
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = NeonCyan)
                        ) {
                            Icon(Icons.Default.HelpOutline, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = stringResource(R.string.setting_about_guide),
                                fontSize = 11.5.sp,
                                fontWeight = FontWeight.Bold,
                                maxLines = 1
                            )
                        }

                        OutlinedButton(
                            onClick = onShareCli,
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp)
                                .testTag("settings_share_cli_button"),
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = TextPrimary)
                        ) {
                            Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = stringResource(R.string.setting_about_share_cli),
                                fontSize = 11.5.sp,
                                fontWeight = FontWeight.Bold,
                                maxLines = 1
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }
}

@Composable
private fun SettingsSectionCard(
    title: String,
    icon: ImageVector,
    sectionTag: String,
    content: @Composable () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(StudioCard, RoundedCornerShape(14.dp))
            .border(1.dp, StudioBorder, RoundedCornerShape(14.dp))
            .padding(14.dp)
            .testTag(sectionTag),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = NeonCyan,
                modifier = Modifier.size(16.dp)
            )
            Text(
                text = title,
                color = NeonCyan,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.8.sp
            )
        }
        content()
    }
}

@Composable
private fun SettingSubLabel(text: String) {
    Text(
        text = text,
        color = TextPrimary,
        fontSize = 12.5.sp,
        fontWeight = FontWeight.SemiBold
    )
}

@Composable
private fun SettingsSwitchRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    tag: String
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .clickable { onCheckedChange(!checked) }
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                text = title,
                color = TextPrimary,
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = subtitle,
                color = TextMuted,
                fontSize = 11.sp,
                lineHeight = 14.sp
            )
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            modifier = Modifier.testTag(tag),
            colors = SwitchDefaults.colors(
                checkedThumbColor = Color(0xFF003038),
                checkedTrackColor = NeonCyan,
                uncheckedThumbColor = TextSecondary,
                uncheckedTrackColor = Color(0xFF141E2C)
            )
        )
    }
}

@Composable
private fun OptionChip(
    title: String,
    subtitle: String,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    tag: String
) {
    Column(
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(if (selected) StudioCardSelected else Color(0xFF101824))
            .border(
                1.dp,
                if (selected) NeonCyan else Color(0xFF1E293B),
                RoundedCornerShape(8.dp)
            )
            .alpha(if (enabled) 1f else 0.45f)
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp)
            .testTag(tag),
        verticalArrangement = Arrangement.spacedBy(1.dp)
    ) {
        Text(
            text = title,
            color = if (selected) NeonCyan else TextPrimary,
            fontSize = 11.5.sp,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium
        )
        Text(
            text = subtitle,
            color = TextMuted,
            fontSize = 9.5.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun AboutInfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            color = TextSecondary,
            fontSize = 12.sp
        )
        Spacer(modifier = Modifier.width(12.dp))
        Text(
            text = value,
            color = TextPrimary,
            fontSize = 11.5.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}
