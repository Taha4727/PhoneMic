package com.example.ui.screens

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.HelpOutline
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Colorize
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.BuildConfig
import com.example.DeviceProfile
import com.example.HorizontalNavMode
import com.example.PhoneMicService
import com.example.PhoneMicUiState
import com.example.R
import com.example.audio.AudioChannelOption
import com.example.audio.AudioFormatOption
import com.example.audio.AudioProtocol
import com.example.audio.InputMicDevice
import com.example.audio.VisualizerStyle
import com.example.ui.theme.AppPaletteStyle
import com.example.ui.theme.JetBrainsMonoFontFamily
import com.example.ui.theme.PhoneMicTheme
import com.example.ui.theme.formatColorHex
import java.util.Locale
import kotlin.math.roundToInt

@Immutable
private data class DropdownChoice<T>(
    val value: T,
    val label: String,
    val explanation: String,
    val enabled: Boolean = true,
    val tag: String,
    val swatchColor: Color? = null
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    uiState: PhoneMicUiState,
    onBackToHome: () -> Unit,
    onAutoStartChange: (Boolean) -> Unit,
    onPushToTalkChange: (Boolean) -> Unit,
    onAutoReconnectChange: (Boolean) -> Unit,
    onKeepScreenAwakeChange: (Boolean) -> Unit,
    onOverlayToggle: (Boolean) -> Unit,
    onTransportModeChange: (String) -> Unit,
    onRefreshMics: () -> Unit,
    onSelectMicDevice: (Int) -> Unit,
    onSelectAudioSource: (String) -> Unit,
    onSelectSampleRate: (Int) -> Unit,
    onSelectAudioFormat: (AudioFormatOption) -> Unit,
    onSelectChannels: (Int) -> Unit,
    onGainChange: (Float) -> Unit,
    onDarkModeChange: (Boolean) -> Unit,
    onOledBlackChange: (Boolean) -> Unit,
    onPaletteStyleChange: (AppPaletteStyle) -> Unit,
    onCustomThemeColorChange: (Long) -> Unit,
    onHorizontalNavModeChange: (HorizontalNavMode) -> Unit,
    onVisualizerEnabledChange: (Boolean) -> Unit,
    onVisualizerStyleChange: (VisualizerStyle) -> Unit,
    onOpenGuide: () -> Unit,
    onShareCli: () -> Unit,
    modifier: Modifier = Modifier
) {
    val colors = PhoneMicTheme.colors
    val audioEditable = !uiState.isRunning
    var showCustomColorDialog by remember { mutableStateOf(false) }
    val onOpenCustomColorPicker = remember { { showCustomColorDialog = true } }

    Column(
        modifier = modifier
            .fillMaxSize()
            .testTag("settings_screen")
    ) {
        // Sticky Top Header Row
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            IconButton(
                onClick = onBackToHome,
                modifier = Modifier
                    .size(48.dp)
                    .testTag("settings_back_button")
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = stringResource(R.string.settings_back_cd),
                    tint = colors.textPrimary
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = stringResource(R.string.settings_title),
                    color = colors.textPrimary,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "General, Audio, Appearance & About",
                    color = colors.textMuted,
                    fontSize = 11.sp
                )
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 6.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            SettingsGeneralSection(
                autoStartStreaming = uiState.autoStartStreaming,
                pushToTalkEnabled = uiState.pushToTalkEnabled,
                autoReconnectEnabled = uiState.autoReconnectEnabled,
                keepScreenAwake = uiState.keepScreenAwake,
                isOverlayEnabled = uiState.isOverlayEnabled,
                transportMode = uiState.transportMode,
                audioEditable = audioEditable,
                onAutoStartChange = onAutoStartChange,
                onPushToTalkChange = onPushToTalkChange,
                onAutoReconnectChange = onAutoReconnectChange,
                onKeepScreenAwakeChange = onKeepScreenAwakeChange,
                onOverlayToggle = onOverlayToggle,
                onTransportModeChange = onTransportModeChange
            )

            SettingsAudioSection(
                audioEditable = audioEditable,
                gain = uiState.gain,
                availableMics = uiState.availableMics,
                preferredMicId = uiState.preferredMicId,
                micMode = uiState.micMode,
                sampleRateHz = uiState.sampleRateHz,
                audioFormat = uiState.audioFormat,
                channels = uiState.channels,
                onGainChange = onGainChange,
                onRefreshMics = onRefreshMics,
                onSelectMicDevice = onSelectMicDevice,
                onSelectAudioSource = onSelectAudioSource,
                onSelectSampleRate = onSelectSampleRate,
                onSelectAudioFormat = onSelectAudioFormat,
                onSelectChannels = onSelectChannels
            )

            SettingsAppearanceSection(
                isDarkMode = uiState.isDarkMode,
                oledBlackEnabled = uiState.oledBlackEnabled,
                paletteStyle = uiState.paletteStyle,
                customThemeColorArgb = uiState.customThemeColorArgb,
                horizontalNavMode = uiState.horizontalNavMode,
                visualizerEnabled = uiState.visualizerEnabled,
                visualizerStyle = uiState.visualizerStyle,
                onDarkModeChange = onDarkModeChange,
                onOledBlackChange = onOledBlackChange,
                onPaletteStyleChange = onPaletteStyleChange,
                onCustomThemeColorChange = onCustomThemeColorChange,
                onOpenCustomColorPicker = onOpenCustomColorPicker,
                onHorizontalNavModeChange = onHorizontalNavModeChange,
                onVisualizerEnabledChange = onVisualizerEnabledChange,
                onVisualizerStyleChange = onVisualizerStyleChange
            )

            SettingsAboutSection(
                onOpenGuide = onOpenGuide,
                onShareCli = onShareCli
            )

            Spacer(modifier = Modifier.height(8.dp))
        }
    }

    if (showCustomColorDialog) {
        CustomThemeColorPickerDialog(
            initialColorArgb = uiState.customThemeColorArgb,
            onDismiss = { showCustomColorDialog = false },
            onApplyColor = { argb ->
                onCustomThemeColorChange(argb)
                showCustomColorDialog = false
            }
        )
    }
}

@Composable
private fun SettingsGeneralSection(
    autoStartStreaming: Boolean,
    pushToTalkEnabled: Boolean,
    autoReconnectEnabled: Boolean,
    keepScreenAwake: Boolean,
    isOverlayEnabled: Boolean,
    transportMode: String,
    audioEditable: Boolean,
    onAutoStartChange: (Boolean) -> Unit,
    onPushToTalkChange: (Boolean) -> Unit,
    onAutoReconnectChange: (Boolean) -> Unit,
    onKeepScreenAwakeChange: (Boolean) -> Unit,
    onOverlayToggle: (Boolean) -> Unit,
    onTransportModeChange: (String) -> Unit
) {
    val colors = PhoneMicTheme.colors
    val context = LocalContext.current
    val transportChoices = remember {
        listOf(
            DropdownChoice(
                value = PhoneMicService.TRANSPORT_UDP,
                label = "UDP (Low Latency)",
                explanation = "Fastest real-time voice with lowest jitter",
                tag = "transport_${PhoneMicService.TRANSPORT_UDP}"
            ),
            DropdownChoice(
                value = PhoneMicService.TRANSPORT_TCP,
                label = "TCP (Reliable)",
                explanation = "Ordered packet delivery for congested Wi-Fi",
                tag = "transport_${PhoneMicService.TRANSPORT_TCP}"
            )
        )
    }
    val onOverlayChecked = remember(context, onOverlayToggle) {
        { checked: Boolean ->
            if (checked && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(context)) {
                Toast.makeText(
                    context,
                    "Please allow 'Display over other apps' first",
                    Toast.LENGTH_LONG
                ).show()
                try {
                    context.startActivity(
                        Intent(
                            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                            Uri.parse("package:${context.packageName}")
                        ).apply { addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) }
                    )
                } catch (_: Exception) {}
            } else {
                onOverlayToggle(checked)
            }
        }
    }

    M3SettingsCard(
        title = stringResource(R.string.settings_section_general),
        icon = Icons.Default.Settings,
        tag = "settings_section_general"
    ) {
        SettingsSwitchListItem(
            title = stringResource(R.string.setting_auto_start_title),
            explanation = stringResource(R.string.setting_auto_start_desc),
            checked = autoStartStreaming,
            onCheckedChange = onAutoStartChange,
            tag = "setting_auto_start"
        )
        HorizontalDivider(color = colors.border)

        SettingsSwitchListItem(
            title = stringResource(R.string.setting_ptt_title),
            explanation = stringResource(R.string.setting_ptt_desc),
            checked = pushToTalkEnabled,
            onCheckedChange = onPushToTalkChange,
            tag = "setting_ptt_mode"
        )
        HorizontalDivider(color = colors.border)

        SettingsSwitchListItem(
            title = stringResource(R.string.setting_auto_reconnect_title),
            explanation = stringResource(R.string.setting_auto_reconnect_desc),
            checked = autoReconnectEnabled,
            onCheckedChange = onAutoReconnectChange,
            tag = "setting_auto_reconnect"
        )
        HorizontalDivider(color = colors.border)

        SettingsSwitchListItem(
            title = stringResource(R.string.setting_keep_awake_title),
            explanation = stringResource(R.string.setting_keep_awake_desc),
            checked = keepScreenAwake,
            onCheckedChange = onKeepScreenAwakeChange,
            tag = "setting_keep_awake"
        )
        HorizontalDivider(color = colors.border)

        SettingsSwitchListItem(
            title = stringResource(R.string.setting_overlay_title),
            explanation = stringResource(R.string.setting_overlay_desc),
            checked = isOverlayEnabled,
            onCheckedChange = onOverlayChecked,
            tag = "setting_overlay"
        )
        HorizontalDivider(color = colors.border)

        SettingsDropdownField(
            label = "Transport Protocol",
            explanation = "UDP delivers minimal voice latency; TCP adds automatic retransmission on unstable Wi-Fi.",
            selectedLabel = if (transportMode == PhoneMicService.TRANSPORT_UDP) "UDP (Low Latency)" else "TCP (Reliable)",
            options = transportChoices,
            selectedValue = transportMode,
            enabled = audioEditable,
            onSelect = onTransportModeChange,
            anchorTag = "dropdown_transport_mode"
        )
    }
}

@Composable
private fun SettingsAudioSection(
    audioEditable: Boolean,
    gain: Float,
    availableMics: List<InputMicDevice>,
    preferredMicId: Int,
    micMode: String,
    sampleRateHz: Int,
    audioFormat: AudioFormatOption,
    channels: Int,
    onGainChange: (Float) -> Unit,
    onRefreshMics: () -> Unit,
    onSelectMicDevice: (Int) -> Unit,
    onSelectAudioSource: (String) -> Unit,
    onSelectSampleRate: (Int) -> Unit,
    onSelectAudioFormat: (AudioFormatOption) -> Unit,
    onSelectChannels: (Int) -> Unit
) {
    val colors = PhoneMicTheme.colors

    val micChoices = remember(availableMics) {
        availableMics.map { mic ->
            DropdownChoice(
                value = mic.id,
                label = "${mic.name} (${mic.typeLabel})",
                explanation = if (mic.isSystemDefault) "Lets Android pick the active default mic" else "Route capture directly to ${mic.typeLabel}",
                tag = "mic_device_${mic.id}"
            )
        }
    }
    val selectedMic = remember(availableMics, preferredMicId) {
        availableMics.firstOrNull { it.id == preferredMicId }
    }

    val sourceChoices = remember {
        listOf(
            DropdownChoice(PhoneMicService.MIC_STANDARD, "Standard Mic", "Balanced hardware microphone input", tag = "audio_source_${PhoneMicService.MIC_STANDARD}"),
            DropdownChoice(PhoneMicService.MIC_UNPROCESSED, "Unprocessed (Raw)", "Bypasses AGC and phone noise filtering when supported", tag = "audio_source_${PhoneMicService.MIC_UNPROCESSED}"),
            DropdownChoice(PhoneMicService.MIC_RAW, "Voice Recognition", "Tuned for clear near-field speech", tag = "audio_source_${PhoneMicService.MIC_RAW}"),
            DropdownChoice(PhoneMicService.MIC_CALL, "Voice Communication", "Hardware echo cancellation & voice isolation", tag = "audio_source_${PhoneMicService.MIC_CALL}"),
            DropdownChoice(PhoneMicService.MIC_CAMCORDER, "Camcorder Mic", "Wide dynamic range for room & ambient audio", tag = "audio_source_${PhoneMicService.MIC_CAMCORDER}")
        )
    }

    val rateChoices = remember {
        AudioProtocol.SUPPORTED_SAMPLE_RATES.map { rate ->
            val label = if (rate % 1000 == 0) "${rate / 1000} kHz" else "44.1 kHz"
            val desc = when (rate) {
                48000 -> "Studio standard clarity & best compatibility"
                44100 -> "CD-quality frequency"
                32000 -> "High speech clarity with lower traffic"
                24000 -> "Balanced voice quality & bandwidth"
                16000 -> "Lightweight bandwidth for weaker Wi-Fi"
                else -> "Ultra-low bandwidth narrowband voice"
            }
            DropdownChoice(
                value = rate,
                label = label,
                explanation = desc,
                tag = "sample_rate_$rate"
            )
        }
    }

    val formatChoices = remember {
        AudioFormatOption.entries.map { fmt ->
            val supported = fmt.isSupportedOnDevice
            val desc = when (fmt) {
                AudioFormatOption.PCM_16BIT -> "Recommended standard bit depth for voice & OBS"
                AudioFormatOption.PCM_8BIT -> "Half bandwidth, compact retro/voice mode"
                AudioFormatOption.PCM_24BIT -> if (supported) "Extended studio dynamic range (PM04)" else "Requires Android 12+ (API 31+)"
                AudioFormatOption.PCM_FLOAT -> "32-bit floating point headroom (PM04)"
            }
            DropdownChoice(
                value = fmt,
                label = if (supported) fmt.label else "${fmt.shortLabel} (API 31+)",
                explanation = desc,
                enabled = supported,
                tag = "audio_format_${fmt.id}"
            )
        }
    }

    val channelChoices = remember {
        AudioChannelOption.entries.map { ch ->
            DropdownChoice(
                value = ch.count,
                label = ch.label,
                explanation = if (ch.count == 1) "Single voice channel — halves network load" else "Dual-channel capture for stereo devices (PM04)",
                tag = "channels_${ch.count}"
            )
        }
    }

    val wireSummaryText = remember(sampleRateHz, channels, audioFormat) {
        val kbps = AudioProtocol.estimatedKbps(sampleRateHz, channels, audioFormat)
        val payload = AudioProtocol.framePayloadBytes(sampleRateHz, channels, audioFormat)
        val protoLabel = if (AudioProtocol.isLegacyStandardStream(sampleRateHz, channels, audioFormat)) {
            "PM01–PM03 Standard"
        } else {
            "PM04 Extended"
        }
        "~$kbps kbps • $payload B / 10 ms • $protoLabel"
    }

    M3SettingsCard(
        title = stringResource(R.string.settings_section_audio),
        icon = Icons.Default.Tune,
        tag = "settings_section_audio"
    ) {
        if (!audioEditable) {
            Surface(
                shape = RoundedCornerShape(8.dp),
                color = colors.statusWarning.copy(alpha = 0.14f),
                border = BorderStroke(1.dp, colors.statusWarning.copy(alpha = 0.5f)),
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("audio_locked_banner")
            ) {
                Text(
                    text = stringResource(R.string.setting_audio_locked_note),
                    color = colors.statusWarning,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp)
                )
            }
        }

        SettingsGainControl(
            gain = gain,
            onGainChange = onGainChange
        )

        HorizontalDivider(color = colors.border)

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.Top
        ) {
            SettingsDropdownField(
                label = stringResource(R.string.setting_physical_mic_title),
                explanation = "Selects whether audio captures from built-in, headset, USB, or Bluetooth microphones.",
                selectedLabel = selectedMic?.let { "${it.name} (${it.typeLabel})" } ?: "System Default",
                options = micChoices,
                selectedValue = preferredMicId,
                enabled = audioEditable,
                onSelect = onSelectMicDevice,
                anchorTag = "dropdown_mic_device",
                modifier = Modifier.weight(1f)
            )

            FilledTonalIconButton(
                onClick = onRefreshMics,
                shape = RoundedCornerShape(10.dp),
                colors = IconButtonDefaults.filledTonalIconButtonColors(
                    containerColor = colors.nestedSurface,
                    contentColor = colors.accent
                ),
                modifier = Modifier
                    .padding(top = 6.dp)
                    .size(52.dp)
                    .testTag("refresh_mics_button")
            ) {
                Icon(
                    imageVector = Icons.Default.Refresh,
                    contentDescription = stringResource(R.string.setting_physical_mic_refresh)
                )
            }
        }

        HorizontalDivider(color = colors.border)

        SettingsDropdownField(
            label = stringResource(R.string.setting_audio_source_title),
            explanation = "Chooses Android's internal capture preset (raw vs hardware noise suppression/AGC).",
            selectedLabel = sourceChoices.firstOrNull { it.value == micMode }?.label ?: "Standard Mic",
            options = sourceChoices,
            selectedValue = micMode,
            enabled = audioEditable,
            onSelect = onSelectAudioSource,
            anchorTag = "dropdown_audio_source"
        )

        HorizontalDivider(color = colors.border)

        SettingsDropdownField(
            label = stringResource(R.string.setting_sample_rate_title),
            explanation = "Sets audio capture frequency per second; higher kHz captures crisper detail.",
            selectedLabel = if (sampleRateHz % 1000 == 0) "${sampleRateHz / 1000} kHz" else "44.1 kHz",
            options = rateChoices,
            selectedValue = sampleRateHz,
            enabled = audioEditable,
            onSelect = onSelectSampleRate,
            anchorTag = "dropdown_sample_rate"
        )

        HorizontalDivider(color = colors.border)

        SettingsDropdownField(
            label = stringResource(R.string.setting_audio_format_title),
            explanation = "Determines sample precision (bit depth) vs network data rate.",
            selectedLabel = audioFormat.label,
            options = formatChoices,
            selectedValue = audioFormat,
            enabled = audioEditable,
            onSelect = onSelectAudioFormat,
            anchorTag = "dropdown_audio_format"
        )

        HorizontalDivider(color = colors.border)

        SettingsDropdownField(
            label = stringResource(R.string.setting_channels_title),
            explanation = "Mono focuses on speech clarity; Stereo transmits left and right channels.",
            selectedLabel = AudioChannelOption.fromCount(channels).label,
            options = channelChoices,
            selectedValue = channels,
            enabled = audioEditable,
            onSelect = onSelectChannels,
            anchorTag = "dropdown_channels"
        )

        Text(
            text = wireSummaryText,
            color = colors.accent,
            fontSize = 11.sp,
            fontFamily = JetBrainsMonoFontFamily,
            modifier = Modifier.testTag("audio_wire_summary")
        )
    }
}

@Composable
private fun SettingsGainControl(
    gain: Float,
    onGainChange: (Float) -> Unit
) {
    val colors = PhoneMicTheme.colors
    val cleanGain = ((gain * 10f).roundToInt() / 10f).coerceIn(0.5f, 3.0f)
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Gain Boost",
                color = colors.textPrimary,
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = String.format(Locale.US, "%.1fx", cleanGain),
                color = colors.accent,
                fontFamily = JetBrainsMonoFontFamily,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold
            )
        }
        Text(
            text = "Boosts or attenuates captured microphone loudness (0.5x to 3.0x) live during streaming.",
            color = colors.textMuted,
            fontSize = 11.sp,
            lineHeight = 14.sp
        )
        Slider(
            value = cleanGain,
            onValueChange = { raw ->
                onGainChange(((raw * 10f).roundToInt() / 10f).coerceIn(0.5f, 3.0f))
            },
            valueRange = 0.5f..3.0f,
            steps = 24,
            colors = SliderDefaults.colors(
                thumbColor = colors.accent,
                activeTrackColor = colors.accent,
                inactiveTrackColor = colors.nestedSurface
            ),
            modifier = Modifier
                .fillMaxWidth()
                .testTag("settings_gain_slider")
        )
    }
}

@Composable
private fun SettingsAppearanceSection(
    isDarkMode: Boolean,
    oledBlackEnabled: Boolean,
    paletteStyle: AppPaletteStyle,
    customThemeColorArgb: Long,
    horizontalNavMode: HorizontalNavMode,
    visualizerEnabled: Boolean,
    visualizerStyle: VisualizerStyle,
    onDarkModeChange: (Boolean) -> Unit,
    onOledBlackChange: (Boolean) -> Unit,
    onPaletteStyleChange: (AppPaletteStyle) -> Unit,
    onCustomThemeColorChange: (Long) -> Unit,
    onOpenCustomColorPicker: () -> Unit,
    onHorizontalNavModeChange: (HorizontalNavMode) -> Unit,
    onVisualizerEnabledChange: (Boolean) -> Unit,
    onVisualizerStyleChange: (VisualizerStyle) -> Unit
) {
    val colors = PhoneMicTheme.colors

    val themeModeChoices = remember {
        listOf(
            DropdownChoice(true, "Dark (#121212)", "Low-glare studio background for dim rooms", tag = "theme_mode_dark"),
            DropdownChoice(false, "Light", "Crisp daylight theme with dark text", tag = "theme_mode_light")
        )
    }
    val paletteChoices = remember(customThemeColorArgb) {
        AppPaletteStyle.entries.map { palette ->
            val dot = if (palette == AppPaletteStyle.CUSTOM) {
                Color((customThemeColorArgb or 0xFF000000L).toInt())
            } else {
                palette.previewColor
            }
            DropdownChoice(
                value = palette,
                label = if (palette == AppPaletteStyle.CUSTOM) "Custom Color Picker…" else palette.label,
                explanation = palette.description,
                tag = "palette_style_${palette.id}",
                swatchColor = dot
            )
        }
    }
    val horizontalNavChoices = remember {
        HorizontalNavMode.entries.map { mode ->
            DropdownChoice(
                value = mode,
                label = mode.label,
                explanation = mode.description,
                tag = "horizontal_nav_${mode.id}"
            )
        }
    }
    val visualizerStyleChoices = remember {
        VisualizerStyle.entries.map { style ->
            DropdownChoice(
                value = style,
                label = style.label,
                explanation = style.description,
                tag = "visualizer_style_${style.id}"
            )
        }
    }

    val activePaletteSwatch: Color = remember(paletteStyle, customThemeColorArgb) {
        if (paletteStyle == AppPaletteStyle.CUSTOM) {
            Color((customThemeColorArgb or 0xFF000000L).toInt())
        } else {
            paletteStyle.previewColor
        }
    }
    val selectedPaletteLabel = remember(paletteStyle, customThemeColorArgb) {
        if (paletteStyle == AppPaletteStyle.CUSTOM) {
            "Custom (${formatColorHex(customThemeColorArgb)})"
        } else {
            paletteStyle.label
        }
    }

    M3SettingsCard(
        title = stringResource(R.string.settings_section_appearance),
        icon = Icons.Default.Palette,
        tag = "settings_section_appearance"
    ) {
        SettingsDropdownField(
            label = stringResource(R.string.setting_theme_mode_title),
            explanation = "Switches between high-contrast Dark (#121212) and bright Light studio surfaces.",
            selectedLabel = if (isDarkMode) "Dark (#121212)" else "Light",
            options = themeModeChoices,
            selectedValue = isDarkMode,
            enabled = true,
            onSelect = onDarkModeChange,
            anchorTag = "dropdown_theme_mode"
        )

        HorizontalDivider(color = colors.border)

        SettingsSwitchListItem(
            title = stringResource(R.string.setting_oled_colors_title),
            explanation = stringResource(R.string.setting_oled_colors_desc),
            checked = oledBlackEnabled,
            onCheckedChange = onOledBlackChange,
            tag = "setting_oled_colors"
        )

        HorizontalDivider(color = colors.border)

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.Top
        ) {
            SettingsDropdownField(
                label = stringResource(R.string.setting_palette_style_title),
                explanation = stringResource(R.string.setting_palette_style_desc),
                selectedLabel = selectedPaletteLabel,
                options = paletteChoices,
                selectedValue = paletteStyle,
                enabled = true,
                onSelect = { palette ->
                    if (palette == AppPaletteStyle.CUSTOM) {
                        onOpenCustomColorPicker()
                    } else {
                        onPaletteStyleChange(palette)
                    }
                },
                anchorTag = "dropdown_palette_style",
                selectedSwatchColor = activePaletteSwatch,
                modifier = Modifier.weight(1f)
            )

            FilledTonalIconButton(
                onClick = onOpenCustomColorPicker,
                shape = RoundedCornerShape(10.dp),
                colors = IconButtonDefaults.filledTonalIconButtonColors(
                    containerColor = colors.accentSoftBg,
                    contentColor = colors.accent
                ),
                modifier = Modifier
                    .padding(top = 6.dp)
                    .size(52.dp)
                    .testTag("open_color_picker_button")
            ) {
                Icon(
                    imageVector = Icons.Default.Colorize,
                    contentDescription = stringResource(R.string.setting_custom_color_action)
                )
            }
        }

        if (paletteStyle == AppPaletteStyle.CUSTOM) {
            var hexInput by remember { mutableStateOf(formatColorHex(customThemeColorArgb)) }
            LaunchedEffect(customThemeColorArgb) {
                val externalHex = formatColorHex(customThemeColorArgb)
                val currentClean = hexInput.trim().removePrefix("#").uppercase(Locale.US)
                val externalClean = externalHex.removePrefix("#").uppercase(Locale.US)
                if (currentClean != externalClean) {
                    hexInput = externalHex
                }
            }

            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                OutlinedTextField(
                    value = hexInput,
                    onValueChange = { raw ->
                        hexInput = raw
                        val normalized = raw.trim().removePrefix("#")
                        if (normalized.length == 6) {
                            normalized.toLongOrNull(16)?.let { rgb ->
                                onCustomThemeColorChange(0xFF000000L or rgb)
                            }
                        }
                    },
                    singleLine = true,
                    label = { Text("Custom Hex Color (#RRGGBB)", fontSize = 12.sp) },
                    leadingIcon = {
                        Box(
                            modifier = Modifier
                                .size(16.dp)
                                .background(activePaletteSwatch, CircleShape)
                        )
                    },
                    shape = RoundedCornerShape(10.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = colors.accent,
                        unfocusedBorderColor = colors.border,
                        focusedLabelColor = colors.accent,
                        unfocusedLabelColor = colors.textSecondary,
                        focusedTextColor = colors.textPrimary,
                        unfocusedTextColor = colors.textPrimary,
                        focusedContainerColor = colors.nestedSurface,
                        unfocusedContainerColor = colors.nestedSurface
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("custom_color_hex_input")
                )
                Text(
                    text = "Enter a 6-digit hex code directly or tap the eyedropper button to adjust Hue, Saturation, and Brightness sliders.",
                    color = colors.textMuted,
                    fontSize = 11.sp,
                    lineHeight = 14.5.sp,
                    modifier = Modifier.padding(horizontal = 2.dp)
                )
            }
        }

        HorizontalDivider(color = colors.border)

        SettingsDropdownField(
            label = stringResource(R.string.setting_horizontal_nav_title),
            explanation = stringResource(R.string.setting_horizontal_nav_desc),
            selectedLabel = horizontalNavMode.label,
            options = horizontalNavChoices,
            selectedValue = horizontalNavMode,
            enabled = true,
            onSelect = onHorizontalNavModeChange,
            anchorTag = "dropdown_horizontal_nav"
        )

        HorizontalDivider(color = colors.border)

        SettingsSwitchListItem(
            title = stringResource(R.string.setting_visualizer_title),
            explanation = stringResource(R.string.setting_visualizer_desc),
            checked = visualizerEnabled,
            onCheckedChange = onVisualizerEnabledChange,
            tag = "setting_visualizer_toggle"
        )

        HorizontalDivider(color = colors.border)

        SettingsDropdownField(
            label = stringResource(R.string.setting_visualizer_style_title),
            explanation = "Selects the live audio meter style rendered at the bottom of the Home screen.",
            selectedLabel = visualizerStyle.label,
            options = visualizerStyleChoices,
            selectedValue = visualizerStyle,
            enabled = visualizerEnabled,
            onSelect = onVisualizerStyleChange,
            anchorTag = "dropdown_visualizer_style"
        )
    }
}

@Composable
private fun SettingsAboutSection(
    onOpenGuide: () -> Unit,
    onShareCli: () -> Unit
) {
    val colors = PhoneMicTheme.colors
    M3SettingsCard(
        title = stringResource(R.string.settings_section_about),
        icon = Icons.Default.Info,
        tag = "settings_section_about"
    ) {
        CompactAboutRow(
            label = stringResource(R.string.setting_about_version),
            value = "v${BuildConfig.VERSION_NAME} (Build ${BuildConfig.VERSION_CODE})"
        )
        CompactAboutRow(
            label = stringResource(R.string.setting_about_device),
            value = "${DeviceProfile.deviceDisplayName} • ${DeviceProfile.osDisplayName}"
        )
        CompactAboutRow(
            label = stringResource(R.string.setting_about_protocol),
            value = stringResource(R.string.setting_about_protocol_val)
        )
        Text(
            text = "Open the PC setup guide for VB-CABLE routing & hotkeys, or export the lightweight Python CLI receiver script.",
            color = colors.textMuted,
            fontSize = 11.sp,
            lineHeight = 14.5.sp
        )
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
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = colors.accent)
            ) {
                Icon(Icons.AutoMirrored.Filled.HelpOutline, contentDescription = null, modifier = Modifier.size(16.dp))
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
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = colors.textPrimary)
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
}

@Composable
private fun M3SettingsCard(
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
private fun SettingsSwitchListItem(
    title: String,
    explanation: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    tag: String
) {
    val colors = PhoneMicTheme.colors
    ListItem(
        colors = ListItemDefaults.colors(
            containerColor = Color.Transparent,
            headlineColor = colors.textPrimary,
            supportingColor = colors.textMuted
        ),
        headlineContent = {
            Text(
                text = title,
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold
            )
        },
        supportingContent = {
            Text(
                text = explanation,
                fontSize = 11.sp,
                lineHeight = 14.5.sp
            )
        },
        trailingContent = {
            Switch(
                checked = checked,
                onCheckedChange = onCheckedChange,
                modifier = Modifier.testTag(tag),
                colors = SwitchDefaults.colors(
                    checkedThumbColor = colors.onAccent,
                    checkedTrackColor = colors.accent,
                    uncheckedThumbColor = colors.textSecondary,
                    uncheckedTrackColor = colors.nestedSurface
                )
            )
        },
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onCheckedChange(!checked) }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun <T> SettingsDropdownField(
    label: String,
    explanation: String,
    selectedLabel: String,
    options: List<DropdownChoice<T>>,
    selectedValue: T,
    enabled: Boolean,
    onSelect: (T) -> Unit,
    anchorTag: String,
    modifier: Modifier = Modifier,
    selectedSwatchColor: Color? = null
) {
    val colors = PhoneMicTheme.colors
    var expanded by remember { mutableStateOf(false) }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .alpha(if (enabled) 1f else 0.55f),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        ExposedDropdownMenuBox(
            expanded = expanded && enabled,
            onExpandedChange = { next -> if (enabled) expanded = next }
        ) {
            OutlinedTextField(
                value = selectedLabel,
                onValueChange = {},
                readOnly = true,
                enabled = enabled,
                singleLine = true,
                label = { Text(label, fontSize = 12.sp) },
                leadingIcon = selectedSwatchColor?.let { dot ->
                    {
                        Box(
                            modifier = Modifier
                                .size(14.dp)
                                .background(dot, CircleShape)
                        )
                    }
                },
                trailingIcon = {
                    ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded && enabled)
                },
                shape = RoundedCornerShape(10.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = colors.accent,
                    unfocusedBorderColor = colors.border,
                    focusedLabelColor = colors.accent,
                    unfocusedLabelColor = colors.textSecondary,
                    focusedTextColor = colors.textPrimary,
                    unfocusedTextColor = colors.textPrimary,
                    focusedContainerColor = colors.nestedSurface,
                    unfocusedContainerColor = colors.nestedSurface,
                    disabledContainerColor = colors.nestedSurface.copy(alpha = 0.6f),
                    disabledTextColor = colors.textMuted,
                    disabledBorderColor = colors.border.copy(alpha = 0.6f)
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .menuAnchor(MenuAnchorType.PrimaryNotEditable, enabled = enabled)
                    .testTag(anchorTag)
            )

            ExposedDropdownMenu(
                expanded = expanded && enabled,
                onDismissRequest = { expanded = false },
                containerColor = colors.cardSurface
            ) {
                options.forEach { option ->
                    val isSelected = option.value == selectedValue
                    DropdownMenuItem(
                        enabled = option.enabled,
                        leadingIcon = option.swatchColor?.let { dot ->
                            {
                                Box(
                                    modifier = Modifier
                                        .size(14.dp)
                                        .background(dot, CircleShape)
                                )
                            }
                        },
                        text = {
                            Column(verticalArrangement = Arrangement.spacedBy(1.dp)) {
                                Text(
                                    text = option.label,
                                    color = if (isSelected) colors.accent else colors.textPrimary,
                                    fontSize = 13.sp,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                                )
                                Text(
                                    text = option.explanation,
                                    color = colors.textMuted,
                                    fontSize = 11.sp,
                                    lineHeight = 14.sp
                                )
                            }
                        },
                        trailingIcon = if (isSelected) {
                            {
                                Icon(
                                    imageVector = Icons.Default.Check,
                                    contentDescription = "Selected",
                                    tint = colors.accent,
                                    modifier = Modifier.size(16.dp)
                                )
                            }
                        } else null,
                        onClick = {
                            expanded = false
                            onSelect(option.value)
                        },
                        modifier = Modifier.testTag(option.tag)
                    )
                }
            }
        }

        Text(
            text = explanation,
            color = colors.textMuted,
            fontSize = 11.sp,
            lineHeight = 14.5.sp,
            modifier = Modifier.padding(horizontal = 2.dp)
        )
    }
}

@Composable
private fun CustomThemeColorPickerDialog(
    initialColorArgb: Long,
    onDismiss: () -> Unit,
    onApplyColor: (Long) -> Unit
) {
    val colors = PhoneMicTheme.colors

    val initialHsv = remember(initialColorArgb) {
        FloatArray(3).also { out ->
            android.graphics.Color.colorToHSV((initialColorArgb or 0xFF000000L).toInt(), out)
        }
    }

    var hue by remember(initialColorArgb) { mutableFloatStateOf(initialHsv[0]) }
    var saturation by remember(initialColorArgb) { mutableFloatStateOf(initialHsv[1].coerceAtLeast(0.15f)) }
    var value by remember(initialColorArgb) { mutableFloatStateOf(initialHsv[2].coerceAtLeast(0.45f)) }

    val hsvScratch = remember { FloatArray(3) }
    val activeColorInt = remember(hue, saturation, value) {
        hsvScratch[0] = hue
        hsvScratch[1] = saturation
        hsvScratch[2] = value
        android.graphics.Color.HSVToColor(hsvScratch)
    }
    val activeColorLong = activeColorInt.toLong() and 0xFFFFFFFFL
    val activeColor = remember(activeColorInt) { Color(activeColorInt) }

    val quickSwatches = remember {
        listOf(
            0xFF0EA5E9L, 0xFF00D8F5L, 0xFF10B981L,
            0xFF8B5CF6L, 0xFFF59E0BL, 0xFFF43F5EL,
            0xFFEC4899L, 0xFF6366F1L
        )
    }

    val previewTextColor = remember(activeColor) {
        if (activeColor.luminance() > 0.42f) Color(0xFF09090B) else Color.White
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = colors.cardSurface,
        title = {
            Text(
                text = stringResource(R.string.custom_color_dialog_title),
                color = colors.textPrimary,
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text(
                    text = "Pick a quick swatch or adjust hue, saturation, and brightness sliders for buttons, switches, and visualizers.",
                    color = colors.textMuted,
                    fontSize = 11.5.sp,
                    lineHeight = 15.sp
                )

                // Live Preview Swatch Banner
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = activeColor,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp)
                        .testTag("custom_color_preview")
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 14.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Accent Preview",
                            color = previewTextColor,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = formatColorHex(activeColorLong),
                            color = previewTextColor,
                            fontFamily = JetBrainsMonoFontFamily,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                // Quick Preset Swatches (2 rows of 4, 48dp touch targets)
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    quickSwatches.chunked(4).forEach { rowSwatches ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceEvenly
                        ) {
                            rowSwatches.forEach { swatchArgb ->
                                val swatchColor = Color(swatchArgb.toInt())
                                val swatchHex = formatColorHex(swatchArgb)
                                Box(
                                    modifier = Modifier
                                        .size(48.dp)
                                        .clickable {
                                            val hsv = FloatArray(3)
                                            android.graphics.Color.colorToHSV(swatchColor.toArgb(), hsv)
                                            hue = hsv[0]
                                            saturation = hsv[1]
                                            value = hsv[2]
                                        }
                                        .testTag("color_swatch_$swatchHex"),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Surface(
                                        shape = CircleShape,
                                        color = swatchColor,
                                        border = BorderStroke(1.5.dp, colors.border),
                                        modifier = Modifier.size(30.dp)
                                    ) {}
                                }
                            }
                        }
                    }
                }

                // Hue Slider
                ColorComponentSlider(
                    label = "Hue",
                    valueText = "${hue.roundToInt()}°",
                    value = hue,
                    valueRange = 0f..360f,
                    onValueChange = { hue = it },
                    accent = activeColor,
                    tag = "color_slider_hue"
                )

                // Saturation Slider
                ColorComponentSlider(
                    label = "Saturation",
                    valueText = "${(saturation * 100f).roundToInt()}%",
                    value = saturation,
                    valueRange = 0f..1f,
                    onValueChange = { saturation = it },
                    accent = activeColor,
                    tag = "color_slider_saturation"
                )

                // Brightness Slider
                ColorComponentSlider(
                    label = "Brightness",
                    valueText = "${(value * 100f).roundToInt()}%",
                    value = value,
                    valueRange = 0.2f..1f,
                    onValueChange = { value = it },
                    accent = activeColor,
                    tag = "color_slider_brightness"
                )
            }
        },
        confirmButton = {
            Button(
                onClick = { onApplyColor(activeColorLong) },
                colors = ButtonDefaults.buttonColors(
                    containerColor = activeColor,
                    contentColor = previewTextColor
                ),
                modifier = Modifier.testTag("custom_color_apply_button")
            ) {
                Text(stringResource(R.string.custom_color_apply), fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel", color = colors.textSecondary)
            }
        },
        shape = RoundedCornerShape(16.dp)
    )
}

@Composable
private fun ColorComponentSlider(
    label: String,
    valueText: String,
    value: Float,
    valueRange: ClosedFloatingPointRange<Float>,
    onValueChange: (Float) -> Unit,
    accent: Color,
    tag: String
) {
    val colors = PhoneMicTheme.colors
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(label, color = colors.textSecondary, fontSize = 11.5.sp, fontWeight = FontWeight.Medium)
            Text(
                text = valueText,
                color = colors.textPrimary,
                fontFamily = JetBrainsMonoFontFamily,
                fontSize = 11.5.sp,
                fontWeight = FontWeight.SemiBold
            )
        }
        Slider(
            value = value,
            onValueChange = onValueChange,
            valueRange = valueRange,
            colors = SliderDefaults.colors(
                thumbColor = accent,
                activeTrackColor = accent,
                inactiveTrackColor = colors.nestedSurface
            ),
            modifier = Modifier
                .fillMaxWidth()
                .testTag(tag)
        )
    }
}

@Composable
private fun CompactAboutRow(label: String, value: String) {
    val colors = PhoneMicTheme.colors
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            color = colors.textSecondary,
            fontSize = 12.sp
        )
        Spacer(modifier = Modifier.width(10.dp))
        Text(
            text = value,
            color = colors.textPrimary,
            fontSize = 11.5.sp,
            fontFamily = JetBrainsMonoFontFamily,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}
