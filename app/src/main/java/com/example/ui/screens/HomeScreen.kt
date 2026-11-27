package com.example.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Radar
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.TouchApp
import androidx.compose.material.icons.filled.Usb
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.LightMode
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.PhoneMicService
import com.example.PhoneMicUiState
import com.example.R
import com.example.audio.VisualizerSnapshot
import com.example.ui.components.AudioVisualizer
import com.example.ui.theme.JetBrainsMonoFontFamily
import com.example.ui.theme.PhoneMicTheme
import kotlinx.coroutines.flow.StateFlow
import java.util.Locale

@Composable
fun HomeScreen(
    uiState: PhoneMicUiState,
    visualizerSnapshotFlow: StateFlow<VisualizerSnapshot>,
    isValidIp: Boolean,
    isValidPort: Boolean,
    onToggleTheme: () -> Unit,
    onRequestMicPermission: () -> Unit,
    onConnectionModeSelected: (String) -> Unit,
    onQrCodeClick: () -> Unit,
    onIpChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onScanClick: () -> Unit,
    onTransportModeSelected: (String) -> Unit,
    onPttToggleChange: (Boolean) -> Unit,
    onPttPressChange: (Boolean) -> Unit,
    onVisualizerEnabledChange: (Boolean) -> Unit,
    onStartClick: () -> Unit,
    onStopClick: () -> Unit,
    onPauseClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val colors = PhoneMicTheme.colors
    val controlsEditable = !uiState.isRunning
    val isPttMuted = uiState.isRunning && uiState.pushToTalkEnabled && !uiState.isPttPressed

    DisposableEffect(uiState.isRunning, uiState.pushToTalkEnabled) {
        onDispose {
            onPttPressChange(false)
        }
    }

    BoxWithConstraints(
        modifier = modifier
            .fillMaxSize()
            .testTag("home_screen")
    ) {
        val isHorizontal = maxWidth > maxHeight && maxWidth >= 560.dp

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp, vertical = if (isHorizontal) 4.dp else 10.dp),
            verticalArrangement = Arrangement.spacedBy(if (isHorizontal) 6.dp else 10.dp)
        ) {
            // =====================================================================
            // 1. TOP BAR: Connection Status + Timer (Full Width in Portrait & Horizontal)
            // =====================================================================
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("home_top_bar"),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                val statusColor = when {
                    !uiState.isRunning -> colors.textMuted
                    uiState.isPaused || isPttMuted -> colors.statusWarning
                    uiState.isConnected -> colors.statusConnected
                    else -> colors.statusWarning
                }
                val statusLabel = when {
                    !uiState.isRunning -> stringResource(R.string.status_disconnected)
                    uiState.pushToTalkEnabled && uiState.isPttPressed -> "PTT Live"
                    uiState.pushToTalkEnabled -> "PTT Ready"
                    uiState.isPaused -> "Muted"
                    uiState.isConnected -> stringResource(R.string.status_connected)
                    else -> stringResource(R.string.status_connecting)
                }

                OutlinedCard(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.outlinedCardColors(containerColor = colors.cardSurface),
                    border = BorderStroke(1.dp, colors.border)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = if (isHorizontal) 10.dp else 12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(9.dp)
                                    .background(statusColor, CircleShape)
                            )
                            Text(
                                text = statusLabel,
                                color = colors.textPrimary,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.testTag("home_connection_status")
                            )
                        }

                        Text(
                            text = formatElapsedHms(uiState.elapsedSeconds),
                            color = if (uiState.isRunning) colors.accent else colors.textMuted,
                            fontSize = 14.sp,
                            fontFamily = JetBrainsMonoFontFamily,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.testTag("home_connection_timer")
                        )
                    }
                }

                if (!uiState.visualizerEnabled) {
                    FilledTonalIconButton(
                        onClick = { onVisualizerEnabledChange(true) },
                        shape = RoundedCornerShape(10.dp),
                        colors = IconButtonDefaults.filledTonalIconButtonColors(
                            containerColor = colors.accentSoftBg,
                            contentColor = colors.accent
                        ),
                        modifier = Modifier
                            .size(48.dp)
                            .testTag("visualizer_show_button")
                    ) {
                        Icon(
                            imageVector = Icons.Outlined.Visibility,
                            contentDescription = stringResource(R.string.show_visualizer_cd),
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }

                FilledTonalIconButton(
                    onClick = onToggleTheme,
                    shape = RoundedCornerShape(10.dp),
                    colors = IconButtonDefaults.filledTonalIconButtonColors(
                        containerColor = colors.cardSurface,
                        contentColor = colors.textPrimary
                    ),
                    modifier = Modifier
                        .size(48.dp)
                        .testTag("theme_toggle_button")
                ) {
                    Icon(
                        imageVector = if (uiState.isDarkMode) Icons.Outlined.LightMode else Icons.Outlined.DarkMode,
                        contentDescription = stringResource(R.string.toggle_theme_cd),
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            // Compact Permission Strip if Microphone Permission Missing
            if (!uiState.hasMicPermission) {
                OutlinedCard(
                    onClick = onRequestMicPermission,
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.outlinedCardColors(
                        containerColor = colors.statusError.copy(alpha = 0.12f)
                    ),
                    border = BorderStroke(1.dp, colors.statusError.copy(alpha = 0.5f)),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp)
                        .testTag("mic_permission_strip")
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Microphone access required",
                            color = colors.statusError,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = "GRANT",
                            color = colors.statusError,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = JetBrainsMonoFontFamily
                        )
                    }
                }
            }

            // =====================================================================
            // 2 & 3. WORKSPACE BODY (Horizontal 50/50 Split OR Portrait 2:1 Stack)
            // =====================================================================
            if (isHorizontal) {
                if (uiState.visualizerEnabled) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f)
                            .testTag("home_horizontal_split"),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.Top
                    ) {
                        HomeControlsCard(
                            uiState = uiState,
                            controlsEditable = controlsEditable,
                            isValidIp = isValidIp,
                            isValidPort = isValidPort,
                            compactHorizontal = true,
                            visualizerVisible = true,
                            onConnectionModeSelected = onConnectionModeSelected,
                            onQrCodeClick = onQrCodeClick,
                            onIpChange = onIpChange,
                            onPortChange = onPortChange,
                            onScanClick = onScanClick,
                            onTransportModeSelected = onTransportModeSelected,
                            onPttToggleChange = onPttToggleChange,
                            onPttPressChange = onPttPressChange,
                            onStartClick = onStartClick,
                            onStopClick = onStopClick,
                            onPauseClick = onPauseClick,
                            modifier = Modifier
                                .weight(1f)
                                .fillMaxHeight()
                                .testTag("home_section_controls")
                        )

                        AudioVisualizer(
                            snapshotFlow = visualizerSnapshotFlow,
                            style = uiState.visualizerStyle,
                            isRunning = uiState.isRunning,
                            isPaused = uiState.isPaused,
                            isPttMuted = isPttMuted,
                            onHideClick = { onVisualizerEnabledChange(false) },
                            modifier = Modifier
                                .weight(1f)
                                .fillMaxHeight()
                        )
                    }
                } else {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f)
                            .testTag("home_horizontal_split"),
                        contentAlignment = Alignment.Center
                    ) {
                        HomeControlsCard(
                            uiState = uiState,
                            controlsEditable = controlsEditable,
                            isValidIp = isValidIp,
                            isValidPort = isValidPort,
                            compactHorizontal = true,
                            visualizerVisible = false,
                            onConnectionModeSelected = onConnectionModeSelected,
                            onQrCodeClick = onQrCodeClick,
                            onIpChange = onIpChange,
                            onPortChange = onPortChange,
                            onScanClick = onScanClick,
                            onTransportModeSelected = onTransportModeSelected,
                            onPttToggleChange = onPttToggleChange,
                            onPttPressChange = onPttPressChange,
                            onStartClick = onStartClick,
                            onStopClick = onStopClick,
                            onPauseClick = onPauseClick,
                            modifier = Modifier
                                .fillMaxWidth()
                                .widthIn(max = 820.dp)
                                .fillMaxHeight()
                                .testTag("home_section_controls")
                        )
                    }
                }
            } else {
                HomeControlsCard(
                    uiState = uiState,
                    controlsEditable = controlsEditable,
                    isValidIp = isValidIp,
                    isValidPort = isValidPort,
                    compactHorizontal = false,
                    visualizerVisible = uiState.visualizerEnabled,
                    onConnectionModeSelected = onConnectionModeSelected,
                    onQrCodeClick = onQrCodeClick,
                    onIpChange = onIpChange,
                    onPortChange = onPortChange,
                    onScanClick = onScanClick,
                    onTransportModeSelected = onTransportModeSelected,
                    onPttToggleChange = onPttToggleChange,
                    onPttPressChange = onPttPressChange,
                    onStartClick = onStartClick,
                    onStopClick = onStopClick,
                    onPauseClick = onPauseClick,
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(if (uiState.visualizerEnabled) 2f else 1f)
                        .testTag("home_section_controls")
                )

                if (uiState.visualizerEnabled) {
                    AudioVisualizer(
                        snapshotFlow = visualizerSnapshotFlow,
                        style = uiState.visualizerStyle,
                        isRunning = uiState.isRunning,
                        isPaused = uiState.isPaused,
                        isPttMuted = isPttMuted,
                        onHideClick = { onVisualizerEnabledChange(false) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f)
                            .heightIn(min = 140.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun HomeControlsCard(
    uiState: PhoneMicUiState,
    controlsEditable: Boolean,
    isValidIp: Boolean,
    isValidPort: Boolean,
    compactHorizontal: Boolean,
    visualizerVisible: Boolean,
    onConnectionModeSelected: (String) -> Unit,
    onQrCodeClick: () -> Unit,
    onIpChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onScanClick: () -> Unit,
    onTransportModeSelected: (String) -> Unit,
    onPttToggleChange: (Boolean) -> Unit,
    onPttPressChange: (Boolean) -> Unit,
    onStartClick: () -> Unit,
    onStopClick: () -> Unit,
    onPauseClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val colors = PhoneMicTheme.colors
    val segmentedColors = SegmentedButtonDefaults.colors(
        activeContainerColor = colors.accent,
        activeContentColor = colors.onAccent,
        activeBorderColor = colors.accent,
        inactiveContainerColor = colors.nestedSurface,
        inactiveContentColor = colors.textPrimary,
        inactiveBorderColor = colors.border,
        disabledActiveContainerColor = colors.accent.copy(alpha = 0.5f),
        disabledInactiveContainerColor = colors.nestedSurface.copy(alpha = 0.5f)
    )

    OutlinedCard(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.outlinedCardColors(containerColor = colors.cardSurface),
        border = BorderStroke(1.dp, colors.border)
    ) {
        BoxWithConstraints(
            modifier = Modifier
                .fillMaxSize()
                .padding(
                    horizontal = if (compactHorizontal) 14.dp else 14.dp,
                    vertical = if (compactHorizontal) 8.dp else 10.dp
                )
        ) {
            val twoColumnExpanded = compactHorizontal && !visualizerVisible && maxWidth >= 560.dp

            if (twoColumnExpanded) {
                val needTwoColScroll = maxHeight < 185.dp
                Row(
                    modifier = Modifier
                        .fillMaxSize()
                        .then(if (needTwoColScroll) Modifier.verticalScroll(rememberScrollState()) else Modifier)
                        .testTag("home_controls_two_column"),
                    horizontalArrangement = Arrangement.spacedBy(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Left Half inside Section 2: Connection Mode + Target IP/Port/Scan
                    Column(
                        modifier = Modifier
                            .weight(1.1f)
                            .then(if (needTwoColScroll) Modifier else Modifier.fillMaxHeight()),
                        verticalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterVertically)
                    ) {
                        Text(
                            text = "CONNECTION & TARGET",
                            color = colors.textSecondary,
                            fontSize = 10.5.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 0.7.sp
                        )

                        ConnectionModeSegmentedRow(
                            uiState = uiState,
                            controlsEditable = controlsEditable,
                            segmentedColors = segmentedColors,
                            onConnectionModeSelected = onConnectionModeSelected,
                            onQrCodeClick = onQrCodeClick
                        )

                        IpPortScanSection(
                            uiState = uiState,
                            controlsEditable = controlsEditable,
                            isValidIp = isValidIp,
                            isValidPort = isValidPort,
                            compactHorizontal = true,
                            onIpChange = onIpChange,
                            onPortChange = onPortChange,
                            onScanClick = onScanClick
                        )
                    }

                    Box(
                        modifier = Modifier
                            .width(1.dp)
                            .fillMaxHeight(0.84f)
                            .background(colors.border)
                    )

                    // Right Half inside Section 2: Transport Protocol + Push-to-Talk + Primary Actions
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .then(if (needTwoColScroll) Modifier else Modifier.fillMaxHeight()),
                        verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterVertically)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "TRANSPORT & STREAM",
                                color = colors.textSecondary,
                                fontSize = 10.5.sp,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 0.7.sp
                            )
                            if (!controlsEditable) {
                                Text(
                                    text = "Locked while live",
                                    color = colors.textMuted,
                                    fontSize = 10.5.sp
                                )
                            }
                        }

                        TransportSegmentedRow(
                            uiState = uiState,
                            controlsEditable = controlsEditable,
                            segmentedColors = segmentedColors,
                            shortLabels = false,
                            onTransportModeSelected = onTransportModeSelected,
                            modifier = Modifier.fillMaxWidth()
                        )

                        PttQuickToggleSurface(
                            pushToTalkEnabled = uiState.pushToTalkEnabled,
                            showIcon = true,
                            labelText = "Push-to-Talk",
                            onPttToggleChange = onPttToggleChange,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(48.dp)
                        )

                        PrimaryStreamActionsRow(
                            uiState = uiState,
                            actionHeight = 48.dp,
                            onPttPressChange = onPttPressChange,
                            onStartClick = onStartClick,
                            onStopClick = onStopClick,
                            onPauseClick = onPauseClick
                        )
                    }
                }
            } else {
                val useInternalScroll = compactHorizontal && maxHeight < 192.dp
                val compactSpacing = compactHorizontal && maxHeight < 228.dp
                val wideInlineRow = compactHorizontal && maxWidth >= 460.dp

                Column(
                    modifier = if (useInternalScroll) {
                        Modifier
                            .fillMaxWidth()
                            .verticalScroll(rememberScrollState())
                    } else {
                        Modifier.fillMaxSize()
                    },
                    verticalArrangement = when {
                        useInternalScroll -> Arrangement.spacedBy(6.dp)
                        compactSpacing -> Arrangement.spacedBy(4.dp, Alignment.CenterVertically)
                        else -> Arrangement.SpaceEvenly
                    }
                ) {

                    // 2A. M3 SingleChoiceSegmentedButtonRow: Wi-Fi | USB | QR Code
                    ConnectionModeSegmentedRow(
                        uiState = uiState,
                        controlsEditable = controlsEditable,
                        segmentedColors = segmentedColors,
                        onConnectionModeSelected = onConnectionModeSelected,
                        onQrCodeClick = onQrCodeClick
                    )

                    // 2B. Target IP + Port + Instant Scan Button (+ feedback)
                    IpPortScanSection(
                        uiState = uiState,
                        controlsEditable = controlsEditable,
                        isValidIp = isValidIp,
                        isValidPort = isValidPort,
                        compactHorizontal = compactHorizontal,
                        onIpChange = onIpChange,
                        onPortChange = onPortChange,
                        onScanClick = onScanClick
                    )

                    // 2C & 2D. Transport Protocol + Push-to-Talk
                    if (compactHorizontal) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            TransportSegmentedRow(
                                uiState = uiState,
                                controlsEditable = controlsEditable,
                                segmentedColors = segmentedColors,
                                shortLabels = !wideInlineRow,
                                onTransportModeSelected = onTransportModeSelected,
                                modifier = Modifier.weight(1.35f)
                            )

                            PttQuickToggleSurface(
                                pushToTalkEnabled = uiState.pushToTalkEnabled,
                                showIcon = false,
                                labelText = if (wideInlineRow) "Push-to-Talk" else "PTT",
                                onPttToggleChange = onPttToggleChange,
                                modifier = Modifier
                                    .weight(1f)
                                    .height(48.dp)
                            )
                        }
                    } else {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "TRANSPORT PROTOCOL",
                                    color = colors.textSecondary,
                                    fontSize = 10.5.sp,
                                    fontWeight = FontWeight.Bold,
                                    letterSpacing = 0.7.sp
                                )
                                if (!controlsEditable) {
                                    Text(
                                        text = "Locked while streaming",
                                        color = colors.textMuted,
                                        fontSize = 10.5.sp
                                    )
                                }
                            }

                            TransportSegmentedRow(
                                uiState = uiState,
                                controlsEditable = controlsEditable,
                                segmentedColors = segmentedColors,
                                shortLabels = false,
                                onTransportModeSelected = onTransportModeSelected,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }

                        PttQuickToggleSurface(
                            pushToTalkEnabled = uiState.pushToTalkEnabled,
                            showIcon = true,
                            labelText = "Push-to-Talk",
                            onPttToggleChange = onPttToggleChange,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(48.dp)
                        )
                    }

                    // 2E. Primary Actions: Start / Stop + Mute (or Hold to Talk when PTT active)
                    PrimaryStreamActionsRow(
                        uiState = uiState,
                        actionHeight = if (compactHorizontal) 48.dp else 50.dp,
                        onPttPressChange = onPttPressChange,
                        onStartClick = onStartClick,
                        onStopClick = onStopClick,
                        onPauseClick = onPauseClick
                    )
                }
            }
        }
    }
}

@Composable
private fun ConnectionModeSegmentedRow(
    uiState: PhoneMicUiState,
    controlsEditable: Boolean,
    segmentedColors: androidx.compose.material3.SegmentedButtonColors,
    onConnectionModeSelected: (String) -> Unit,
    onQrCodeClick: () -> Unit
) {
    SingleChoiceSegmentedButtonRow(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("connection_segmented_bar")
    ) {
        SegmentedButton(
            selected = uiState.connectionMode == PhoneMicService.CONNECTION_WIFI && !uiState.showQrScanner,
            onClick = { onConnectionModeSelected(PhoneMicService.CONNECTION_WIFI) },
            enabled = controlsEditable,
            shape = SegmentedButtonDefaults.itemShape(index = 0, count = 3),
            colors = segmentedColors,
            icon = {},
            label = {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(5.dp)
                ) {
                    Icon(Icons.Default.Wifi, contentDescription = null, modifier = Modifier.size(16.dp))
                    Text(stringResource(R.string.conn_wifi), fontSize = 12.sp, maxLines = 1)
                }
            },
            modifier = Modifier.testTag("conn_mode_wifi")
        )

        SegmentedButton(
            selected = uiState.connectionMode == PhoneMicService.CONNECTION_USB && !uiState.showQrScanner,
            onClick = { onConnectionModeSelected(PhoneMicService.CONNECTION_USB) },
            enabled = controlsEditable,
            shape = SegmentedButtonDefaults.itemShape(index = 1, count = 3),
            colors = segmentedColors,
            icon = {},
            label = {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(5.dp)
                ) {
                    Icon(Icons.Default.Usb, contentDescription = null, modifier = Modifier.size(16.dp))
                    Text(stringResource(R.string.conn_usb), fontSize = 12.sp, maxLines = 1)
                }
            },
            modifier = Modifier.testTag("conn_mode_usb")
        )

        SegmentedButton(
            selected = uiState.showQrScanner,
            onClick = onQrCodeClick,
            enabled = controlsEditable,
            shape = SegmentedButtonDefaults.itemShape(index = 2, count = 3),
            colors = segmentedColors,
            icon = {},
            label = {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(5.dp)
                ) {
                    Icon(Icons.Default.QrCodeScanner, contentDescription = null, modifier = Modifier.size(16.dp))
                    Text(stringResource(R.string.conn_qr_code), fontSize = 12.sp, maxLines = 1)
                }
            },
            modifier = Modifier.testTag("conn_mode_qr")
        )
    }
}

@Composable
private fun IpPortScanSection(
    uiState: PhoneMicUiState,
    controlsEditable: Boolean,
    isValidIp: Boolean,
    isValidPort: Boolean,
    compactHorizontal: Boolean,
    onIpChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onScanClick: () -> Unit
) {
    val colors = PhoneMicTheme.colors
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = uiState.ip,
                onValueChange = onIpChange,
                enabled = controlsEditable,
                singleLine = true,
                isError = !isValidIp && uiState.ip.isNotEmpty(),
                label = { Text("IP Address", fontSize = 11.sp) },
                textStyle = TextStyle(
                    fontFamily = JetBrainsMonoFontFamily,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    color = colors.textPrimary
                ),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                shape = RoundedCornerShape(10.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = colors.accent,
                    unfocusedBorderColor = colors.border,
                    focusedLabelColor = colors.accent,
                    unfocusedLabelColor = colors.textSecondary,
                    focusedContainerColor = colors.nestedSurface,
                    unfocusedContainerColor = colors.nestedSurface,
                    disabledContainerColor = colors.nestedSurface.copy(alpha = 0.6f),
                    disabledBorderColor = colors.border.copy(alpha = 0.6f),
                    disabledTextColor = colors.textMuted
                ),
                modifier = Modifier
                    .weight(1.65f)
                    .testTag("ip_address_input")
            )

            OutlinedTextField(
                value = uiState.port,
                onValueChange = onPortChange,
                enabled = controlsEditable,
                singleLine = true,
                isError = !isValidPort && uiState.port.isNotEmpty(),
                label = { Text("Port", fontSize = 11.sp) },
                textStyle = TextStyle(
                    fontFamily = JetBrainsMonoFontFamily,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    color = colors.textPrimary
                ),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                shape = RoundedCornerShape(10.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = colors.accent,
                    unfocusedBorderColor = colors.border,
                    focusedLabelColor = colors.accent,
                    unfocusedLabelColor = colors.textSecondary,
                    focusedContainerColor = colors.nestedSurface,
                    unfocusedContainerColor = colors.nestedSurface,
                    disabledContainerColor = colors.nestedSurface.copy(alpha = 0.6f),
                    disabledBorderColor = colors.border.copy(alpha = 0.6f),
                    disabledTextColor = colors.textMuted
                ),
                modifier = Modifier
                    .weight(0.95f)
                    .testTag("port_input")
            )

            OutlinedButton(
                onClick = onScanClick,
                enabled = controlsEditable && !uiState.isScanningPc,
                shape = RoundedCornerShape(10.dp),
                border = BorderStroke(1.dp, if (controlsEditable) colors.accent else colors.border),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = colors.accent,
                    containerColor = colors.accentSoftBg
                ),
                modifier = Modifier
                    .padding(top = if (compactHorizontal) 3.dp else 5.dp)
                    .height(if (compactHorizontal) 48.dp else 52.dp)
                    .testTag("scan_pc_button")
            ) {
                if (uiState.isScanningPc) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = colors.accent
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.Radar,
                        contentDescription = "Auto-detect PC",
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = stringResource(R.string.btn_scan_auto),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1
                    )
                }
            }
        }

        if (!uiState.scanFeedback.isNullOrBlank()) {
            Text(
                text = uiState.scanFeedback,
                color = colors.accent,
                fontSize = 11.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
private fun TransportSegmentedRow(
    uiState: PhoneMicUiState,
    controlsEditable: Boolean,
    segmentedColors: androidx.compose.material3.SegmentedButtonColors,
    shortLabels: Boolean,
    onTransportModeSelected: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    SingleChoiceSegmentedButtonRow(
        modifier = modifier.testTag("transport_segmented_bar")
    ) {
        SegmentedButton(
            selected = uiState.transportMode == PhoneMicService.TRANSPORT_UDP,
            onClick = { onTransportModeSelected(PhoneMicService.TRANSPORT_UDP) },
            enabled = controlsEditable,
            shape = SegmentedButtonDefaults.itemShape(index = 0, count = 2),
            colors = segmentedColors,
            icon = {},
            label = {
                Text(
                    text = if (shortLabels) "UDP" else stringResource(R.string.transport_udp_short),
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            },
            modifier = Modifier.testTag("home_transport_udp")
        )

        SegmentedButton(
            selected = uiState.transportMode == PhoneMicService.TRANSPORT_TCP,
            onClick = { onTransportModeSelected(PhoneMicService.TRANSPORT_TCP) },
            enabled = controlsEditable,
            shape = SegmentedButtonDefaults.itemShape(index = 1, count = 2),
            colors = segmentedColors,
            icon = {},
            label = {
                Text(
                    text = if (shortLabels) "TCP" else stringResource(R.string.transport_tcp_short),
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            },
            modifier = Modifier.testTag("home_transport_tcp")
        )
    }
}

@Composable
private fun PttQuickToggleSurface(
    pushToTalkEnabled: Boolean,
    showIcon: Boolean,
    labelText: String,
    onPttToggleChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier
) {
    val colors = PhoneMicTheme.colors
    Surface(
        onClick = { onPttToggleChange(!pushToTalkEnabled) },
        shape = RoundedCornerShape(10.dp),
        color = colors.nestedSurface,
        border = BorderStroke(1.dp, colors.border),
        modifier = modifier
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = if (showIcon) 12.dp else 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                if (showIcon) {
                    Icon(
                        imageVector = Icons.Default.TouchApp,
                        contentDescription = null,
                        tint = if (pushToTalkEnabled) colors.accent else colors.textSecondary,
                        modifier = Modifier.size(18.dp)
                    )
                }
                Text(
                    text = labelText,
                    color = colors.textPrimary,
                    fontSize = if (showIcon) 13.sp else 12.5.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }

            Switch(
                checked = pushToTalkEnabled,
                onCheckedChange = onPttToggleChange,
                modifier = Modifier.testTag("home_ptt_toggle"),
                colors = SwitchDefaults.colors(
                    checkedThumbColor = colors.onAccent,
                    checkedTrackColor = colors.accent,
                    uncheckedThumbColor = colors.textSecondary,
                    uncheckedTrackColor = colors.cardSurface
                )
            )
        }
    }
}

@Composable
private fun PrimaryStreamActionsRow(
    uiState: PhoneMicUiState,
    actionHeight: androidx.compose.ui.unit.Dp,
    onPttPressChange: (Boolean) -> Unit,
    onStartClick: () -> Unit,
    onStopClick: () -> Unit,
    onPauseClick: () -> Unit
) {
    val colors = PhoneMicTheme.colors
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (!uiState.isRunning) {
            Button(
                onClick = onStartClick,
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = colors.accent,
                    contentColor = colors.onAccent
                ),
                elevation = ButtonDefaults.buttonElevation(0.dp, 0.dp, 0.dp),
                modifier = Modifier
                    .weight(1.45f)
                    .height(actionHeight)
                    .testTag("start_streaming_button")
            ) {
                Icon(
                    imageVector = Icons.Default.PlayArrow,
                    contentDescription = null,
                    modifier = Modifier.size(19.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = stringResource(R.string.btn_start_short),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold
                )
            }

            OutlinedButton(
                onClick = {},
                enabled = false,
                shape = RoundedCornerShape(10.dp),
                border = BorderStroke(1.dp, colors.border.copy(alpha = 0.6f)),
                colors = ButtonDefaults.outlinedButtonColors(
                    disabledContentColor = colors.textMuted
                ),
                modifier = Modifier
                    .weight(1f)
                    .height(actionHeight)
                    .testTag("pause_resume_button")
            ) {
                Icon(
                    imageVector = Icons.Default.MicOff,
                    contentDescription = null,
                    modifier = Modifier.size(17.dp)
                )
                Spacer(modifier = Modifier.width(5.dp))
                Text(
                    text = stringResource(R.string.btn_mute_short),
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }
        } else if (uiState.pushToTalkEnabled) {
            Button(
                onClick = onStopClick,
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = colors.statusError,
                    contentColor = Color.White
                ),
                elevation = ButtonDefaults.buttonElevation(0.dp, 0.dp, 0.dp),
                modifier = Modifier
                    .weight(0.9f)
                    .height(actionHeight)
                    .testTag("stop_streaming_button")
            ) {
                Icon(
                    imageVector = Icons.Default.Stop,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = stringResource(R.string.btn_stop_short),
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold
                )
            }

            Surface(
                shape = RoundedCornerShape(10.dp),
                color = if (uiState.isPttPressed) colors.statusConnected else colors.accentSoftBg,
                border = BorderStroke(
                    width = 1.5.dp,
                    color = if (uiState.isPttPressed) colors.statusConnected else colors.accent
                ),
                modifier = Modifier
                    .weight(1.6f)
                    .height(actionHeight)
                    .pointerInput(Unit) {
                        detectTapGestures(
                            onPress = {
                                onPttPressChange(true)
                                try {
                                    awaitRelease()
                                } finally {
                                    onPttPressChange(false)
                                }
                            }
                        )
                    }
                    .testTag("ptt_hold_button")
            ) {
                Row(
                    modifier = Modifier.fillMaxSize(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = if (uiState.isPttPressed) Icons.Default.Mic else Icons.Default.TouchApp,
                        contentDescription = "Hold to talk",
                        tint = if (uiState.isPttPressed) Color.White else colors.accent,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = if (uiState.isPttPressed) "TALKING" else "HOLD TO TALK",
                        color = if (uiState.isPttPressed) Color.White else colors.accent,
                        fontSize = 12.5.sp,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1
                    )
                }
            }
        } else {
            Button(
                onClick = onStopClick,
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = colors.statusError,
                    contentColor = Color.White
                ),
                elevation = ButtonDefaults.buttonElevation(0.dp, 0.dp, 0.dp),
                modifier = Modifier
                    .weight(1.25f)
                    .height(actionHeight)
                    .testTag("stop_streaming_button")
            ) {
                Icon(
                    imageVector = Icons.Default.Stop,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = stringResource(R.string.btn_stop_short),
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold
                )
            }

            OutlinedButton(
                onClick = onPauseClick,
                shape = RoundedCornerShape(10.dp),
                border = BorderStroke(
                    1.5.dp,
                    if (uiState.isPaused) colors.statusWarning else colors.border
                ),
                colors = ButtonDefaults.outlinedButtonColors(
                    containerColor = if (uiState.isPaused) colors.statusWarning.copy(alpha = 0.14f) else colors.nestedSurface,
                    contentColor = if (uiState.isPaused) colors.statusWarning else colors.textPrimary
                ),
                modifier = Modifier
                    .weight(1f)
                    .height(actionHeight)
                    .testTag("pause_resume_button")
            ) {
                Icon(
                    imageVector = if (uiState.isPaused) Icons.Default.PlayArrow else Icons.Default.Pause,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(5.dp))
                Text(
                    text = stringResource(if (uiState.isPaused) R.string.btn_resume_short else R.string.btn_mute_short),
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

internal fun formatElapsedHms(elapsedSeconds: Long): String {
    val hrs = elapsedSeconds / 3600
    val mins = (elapsedSeconds % 3600) / 60
    val secs = elapsedSeconds % 60
    return String.format(Locale.US, "%02d:%02d:%02d", hrs, mins, secs)
}
