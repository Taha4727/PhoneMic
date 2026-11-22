package com.example.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Analytics
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.outlined.Analytics
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.DeviceProfile
import com.example.MainTab
import com.example.PhoneMicViewModel
import com.example.R
import com.example.ui.components.QrScannerDialog
import com.example.ui.components.ReceiverGuideDialog
import com.example.ui.theme.PhoneMicTheme
import com.example.util.ShareHelper

@Composable
fun PhoneMicScreen(
    viewModel: PhoneMicViewModel,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsState()
    val visualizerSnapshot by viewModel.visualizerSnapshot.collectAsState()
    val context = LocalContext.current
    val colors = PhoneMicTheme.colors

    var showMicPermissionRationaleDialog by remember { mutableStateOf(false) }

    LaunchedEffect(uiState.autoStartStreaming, uiState.hasMicPermission) {
        if (uiState.autoStartStreaming && uiState.hasMicPermission) {
            viewModel.maybeAutoStart(context)
        }
    }

    BackHandler(enabled = uiState.activeTab != MainTab.HOME) {
        viewModel.setActiveTab(MainTab.HOME)
    }

    val micPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        viewModel.checkPermissions(context)
        if (isGranted) {
            viewModel.startStreaming(context)
        } else {
            showMicPermissionRationaleDialog = true
            Toast.makeText(
                context,
                "Microphone permission is required to stream audio to PC",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { _ ->
        viewModel.checkPermissions(context)
    }

    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        viewModel.checkPermissions(context)
        if (isGranted) {
            viewModel.setQrScannerVisible(true)
        } else {
            Toast.makeText(context, "Camera permission needed to scan PC QR code", Toast.LENGTH_SHORT).show()
        }
    }

    fun handleStartStream() {
        val hasMicPermission = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED

        if (!hasMicPermission) {
            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            return
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val hasNotificationPermission = ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED

            if (!hasNotificationPermission) {
                try {
                    notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                } catch (_: Exception) {}
            }
        }

        viewModel.startStreaming(context)
    }

    val selectedMicName = remember(uiState.availableMics, uiState.preferredMicId) {
        uiState.availableMics.firstOrNull { it.id == uiState.preferredMicId }?.name ?: "System Default"
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = colors.background,
        bottomBar = {
            NavigationBar(
                containerColor = colors.bottomBarSurface,
                contentColor = colors.textPrimary,
                tonalElevation = 0.dp,
                windowInsets = WindowInsets.navigationBars,
                modifier = Modifier.testTag("bottom_nav_bar")
            ) {
                    val itemColors = NavigationBarItemDefaults.colors(
                        selectedIconColor = colors.accent,
                        selectedTextColor = colors.accent,
                        indicatorColor = colors.accentSoftBg,
                        unselectedIconColor = colors.textSecondary,
                        unselectedTextColor = colors.textSecondary
                    )

                    NavigationBarItem(
                        selected = uiState.activeTab == MainTab.STATUS,
                        onClick = { viewModel.setActiveTab(MainTab.STATUS) },
                        icon = {
                            Icon(
                                imageVector = if (uiState.activeTab == MainTab.STATUS) Icons.Filled.Analytics else Icons.Outlined.Analytics,
                                contentDescription = stringResource(R.string.nav_status)
                            )
                        },
                        label = {
                            Text(
                                text = stringResource(R.string.nav_status),
                                fontSize = 11.sp,
                                fontWeight = if (uiState.activeTab == MainTab.STATUS) FontWeight.Bold else FontWeight.Medium
                            )
                        },
                        colors = itemColors,
                        modifier = Modifier.testTag("nav_tab_status")
                    )

                    NavigationBarItem(
                        selected = uiState.activeTab == MainTab.HOME,
                        onClick = { viewModel.setActiveTab(MainTab.HOME) },
                        icon = {
                            Icon(
                                imageVector = if (uiState.activeTab == MainTab.HOME) Icons.Filled.Mic else Icons.Outlined.Mic,
                                contentDescription = stringResource(R.string.nav_home)
                            )
                        },
                        label = {
                            Text(
                                text = stringResource(R.string.nav_home),
                                fontSize = 11.sp,
                                fontWeight = if (uiState.activeTab == MainTab.HOME) FontWeight.Bold else FontWeight.Medium
                            )
                        },
                        colors = itemColors,
                        modifier = Modifier.testTag("nav_tab_home")
                    )

                    NavigationBarItem(
                        selected = uiState.activeTab == MainTab.SETTINGS,
                        onClick = { viewModel.setActiveTab(MainTab.SETTINGS) },
                        icon = {
                            Icon(
                                imageVector = if (uiState.activeTab == MainTab.SETTINGS) Icons.Filled.Settings else Icons.Outlined.Settings,
                                contentDescription = stringResource(R.string.nav_settings)
                            )
                        },
                        label = {
                            Text(
                                text = stringResource(R.string.nav_settings),
                                fontSize = 11.sp,
                                fontWeight = if (uiState.activeTab == MainTab.SETTINGS) FontWeight.Bold else FontWeight.Medium
                            )
                        },
                        colors = itemColors,
                        modifier = Modifier.testTag("open_settings_button")
                    )
                }
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .padding(bottom = innerPadding.calculateBottomPadding()),
            contentAlignment = Alignment.TopCenter
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .widthIn(max = 640.dp)
            ) {
                when (uiState.activeTab) {
                    MainTab.STATUS -> StatusScreen(
                        uiState = uiState,
                        selectedMicName = selectedMicName,
                        onBatteryDismissOrGranted = { viewModel.checkBatteryOptimization() }
                    )

                    MainTab.HOME -> HomeScreen(
                        uiState = uiState,
                        visualizerSnapshot = visualizerSnapshot,
                        isValidIp = viewModel.isValidIp(uiState.ip),
                        isValidPort = viewModel.isValidPort(uiState.port),
                        onToggleTheme = { viewModel.toggleDarkMode() },
                        onRequestMicPermission = {
                            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        },
                        onConnectionModeSelected = { mode -> viewModel.setConnectionMode(mode) },
                        onQrCodeClick = {
                            val hasCam = ContextCompat.checkSelfPermission(
                                context,
                                Manifest.permission.CAMERA
                            ) == PackageManager.PERMISSION_GRANTED
                            if (hasCam) {
                                viewModel.setQrScannerVisible(true)
                            } else {
                                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                            }
                        },
                        onIpChange = { viewModel.setIp(it) },
                        onPortChange = { viewModel.setPort(it) },
                        onScanClick = { viewModel.scanForPc(context) },
                        onTransportModeSelected = { viewModel.setTransportMode(it) },
                        onPttToggleChange = { viewModel.setPushToTalkEnabled(it) },
                        onPttPressChange = { viewModel.setPttPressed(it) },
                        onStartClick = { handleStartStream() },
                        onStopClick = { viewModel.stopStreaming(context) },
                        onPauseClick = { viewModel.togglePause() }
                    )

                    MainTab.SETTINGS -> SettingsScreen(
                        uiState = uiState,
                        onBackToHome = { viewModel.setActiveTab(MainTab.HOME) },
                        onAutoStartChange = { viewModel.setAutoStartStreaming(it) },
                        onPushToTalkChange = { viewModel.setPushToTalkEnabled(it) },
                        onAutoReconnectChange = { viewModel.setAutoReconnectEnabled(it) },
                        onKeepScreenAwakeChange = { viewModel.setKeepScreenAwake(it) },
                        onOverlayToggle = { viewModel.toggleFloatingOverlay(context, it) },
                        onTransportModeChange = { viewModel.setTransportMode(it) },
                        onRefreshMics = { viewModel.refreshAvailableMics() },
                        onSelectMicDevice = { viewModel.setPreferredMicDevice(it) },
                        onSelectAudioSource = { viewModel.setMicMode(it) },
                        onSelectSampleRate = { viewModel.setSampleRate(it) },
                        onSelectAudioFormat = { viewModel.setAudioFormat(it) },
                        onSelectChannels = { viewModel.setChannels(it) },
                        onGainChange = { viewModel.setGain(it) },
                        onDarkModeChange = { viewModel.setDarkMode(it) },
                        onOledBlackChange = { viewModel.setOledBlackEnabled(it) },
                        onPaletteStyleChange = { viewModel.setPaletteStyle(it) },
                        onThemeColorPresetChange = { viewModel.setThemeColorPreset(it) },
                        onCustomThemeColorChange = { viewModel.setCustomThemeColor(it) },
                        onVisualizerEnabledChange = { viewModel.setVisualizerEnabled(it) },
                        onVisualizerStyleChange = { viewModel.setVisualizerStyle(it) },
                        onOpenGuide = { viewModel.setGuideDialogVisible(true) },
                        onShareCli = { ShareHelper.shareCliReceiver(context) }
                    )
                }
            }
        }
    }

    if (uiState.showGuideDialog) {
        ReceiverGuideDialog(
            onDismissRequest = { viewModel.setGuideDialogVisible(false) }
        )
    }

    if (showMicPermissionRationaleDialog) {
        AlertDialog(
            onDismissRequest = { showMicPermissionRationaleDialog = false },
            title = {
                Text(
                    text = "Microphone Access Required",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "PhoneMic needs microphone permission to capture your voice and stream it in real time to your PC.",
                        color = colors.textSecondary,
                        fontSize = 12.sp,
                        lineHeight = 16.sp
                    )
                    Text(
                        text = if (DeviceProfile.isXiaomiOrPoco) {
                            "On Xiaomi HyperOS / POCO F6:\n1. Tap 'Open Settings' below.\n2. Tap 'Permissions' → 'Microphone'.\n3. Select 'Allow only while using the app'.\n4. Turn off 'Pause app activity if unused' to prevent HyperOS from revoking it."
                        } else {
                            "Please grant microphone access in system settings to use PhoneMic."
                        },
                        color = colors.accent,
                        fontSize = 11.5.sp,
                        fontWeight = FontWeight.Medium,
                        lineHeight = 15.sp
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        showMicPermissionRationaleDialog = false
                        DeviceProfile.openAppDetailsSettings(context)
                    }
                ) {
                    Text("Open Settings", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = { showMicPermissionRationaleDialog = false }
                ) {
                    Text("Dismiss")
                }
            },
            containerColor = colors.cardSurface,
            shape = RoundedCornerShape(14.dp)
        )
    }

    if (uiState.showQrScanner) {
        QrScannerDialog(
            onDismiss = { viewModel.setQrScannerVisible(false) },
            onConfigScanned = { config ->
                viewModel.applyScannedConfig(config)
                Toast.makeText(
                    context,
                    "Paired with ${config.ip}:${config.port} via QR",
                    Toast.LENGTH_SHORT
                ).show()
            }
        )
    }
}
