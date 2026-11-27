package com.example.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.NavigationRailItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.DeviceProfile
import com.example.HorizontalNavMode
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

    val onSelectTab: (MainTab) -> Unit = remember(viewModel) { { tab -> viewModel.setActiveTab(tab) } }
    val onSelectStatus: () -> Unit = remember(viewModel) { { viewModel.setActiveTab(MainTab.STATUS) } }
    val onSelectHome: () -> Unit = remember(viewModel) { { viewModel.setActiveTab(MainTab.HOME) } }
    val onSelectSettings: () -> Unit = remember(viewModel) { { viewModel.setActiveTab(MainTab.SETTINGS) } }
    val onToggleDarkMode: () -> Unit = remember(viewModel) { { viewModel.toggleDarkMode() } }
    val onRequestMicPermission: () -> Unit = remember(micPermissionLauncher) {
        { micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO) }
    }
    val onQrCodeClick: () -> Unit = remember(context, viewModel, cameraPermissionLauncher) {
        {
            val hasCam = ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.CAMERA
            ) == PackageManager.PERMISSION_GRANTED
            if (hasCam) {
                viewModel.setQrScannerVisible(true)
            } else {
                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
        }
    }
    val onStartClick: () -> Unit = remember(context, viewModel, micPermissionLauncher, notificationPermissionLauncher) {
        { handleStartStream() }
    }
    val onStopClick: () -> Unit = remember(context, viewModel) { { viewModel.stopStreaming(context) } }
    val onPauseClick: () -> Unit = remember(viewModel) { { viewModel.togglePause() } }
    val onScanClick: () -> Unit = remember(context, viewModel) { { viewModel.scanForPc(context) } }
    val onOverlayToggle: (Boolean) -> Unit = remember(context, viewModel) { { viewModel.toggleFloatingOverlay(context, it) } }
    val onShareCli: () -> Unit = remember(context) { { ShareHelper.shareCliReceiver(context) } }

    BoxWithConstraints(modifier = modifier.fillMaxSize()) {
        val isHorizontal = maxWidth > maxHeight && maxWidth >= 560.dp
        val useSideRail = isHorizontal && uiState.horizontalNavMode == HorizontalNavMode.SIDE_RAIL
        val maxContentWidth = if (isHorizontal && uiState.activeTab != MainTab.SETTINGS) 1200.dp else 640.dp

        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = colors.background,
            bottomBar = {
                if (!useSideRail) {
                    if (isHorizontal) {
                        CompactHorizontalBottomBar(
                            activeTab = uiState.activeTab,
                            onSelectTab = onSelectTab
                        )
                    } else {
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
                                onClick = onSelectStatus,
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
                                onClick = onSelectHome,
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
                                onClick = onSelectSettings,
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
                }
            }
        ) { innerPadding ->
            Row(modifier = Modifier.fillMaxSize()) {
                if (useSideRail) {
                    val railColors = NavigationRailItemDefaults.colors(
                        selectedIconColor = colors.accent,
                        selectedTextColor = colors.accent,
                        indicatorColor = colors.accentSoftBg,
                        unselectedIconColor = colors.textSecondary,
                        unselectedTextColor = colors.textSecondary
                    )

                    NavigationRail(
                        containerColor = colors.bottomBarSurface,
                        contentColor = colors.textPrimary,
                        windowInsets = WindowInsets.safeDrawing.only(WindowInsetsSides.Vertical + WindowInsetsSides.Start),
                        modifier = Modifier.testTag("nav_rail")
                    ) {
                        Spacer(modifier = Modifier.weight(1f))

                        NavigationRailItem(
                            selected = uiState.activeTab == MainTab.STATUS,
                            onClick = onSelectStatus,
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
                            colors = railColors,
                            modifier = Modifier.testTag("nav_tab_status")
                        )

                        NavigationRailItem(
                            selected = uiState.activeTab == MainTab.HOME,
                            onClick = onSelectHome,
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
                            colors = railColors,
                            modifier = Modifier.testTag("nav_tab_home")
                        )

                        NavigationRailItem(
                            selected = uiState.activeTab == MainTab.SETTINGS,
                            onClick = onSelectSettings,
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
                            colors = railColors,
                            modifier = Modifier.testTag("open_settings_button")
                        )

                        Spacer(modifier = Modifier.weight(1f))
                    }

                    VerticalDivider(color = colors.border)
                }

                val contentInsetsModifier = if (useSideRail) {
                    Modifier.windowInsetsPadding(
                        WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Bottom + WindowInsetsSides.End)
                    )
                } else {
                    Modifier
                        .windowInsetsPadding(
                            WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal)
                        )
                        .padding(bottom = innerPadding.calculateBottomPadding())
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .then(contentInsetsModifier),
                    contentAlignment = Alignment.TopCenter
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .widthIn(max = maxContentWidth)
                    ) {
                        when (uiState.activeTab) {
                            MainTab.STATUS -> StatusScreen(
                                uiState = uiState,
                                selectedMicName = selectedMicName,
                                onBatteryDismissOrGranted = remember(viewModel) { { viewModel.checkBatteryOptimization() } }
                            )

                            MainTab.HOME -> HomeScreen(
                                uiState = uiState,
                                visualizerSnapshotFlow = viewModel.visualizerSnapshot,
                                isValidIp = remember(uiState.ip) { viewModel.isValidIp(uiState.ip) },
                                isValidPort = remember(uiState.port) { viewModel.isValidPort(uiState.port) },
                                onToggleTheme = onToggleDarkMode,
                                onRequestMicPermission = onRequestMicPermission,
                                onConnectionModeSelected = remember(viewModel) { { mode -> viewModel.setConnectionMode(mode) } },
                                onQrCodeClick = onQrCodeClick,
                                onIpChange = remember(viewModel) { { viewModel.setIp(it) } },
                                onPortChange = remember(viewModel) { { viewModel.setPort(it) } },
                                onScanClick = onScanClick,
                                onTransportModeSelected = remember(viewModel) { { viewModel.setTransportMode(it) } },
                                onPttToggleChange = remember(viewModel) { { viewModel.setPushToTalkEnabled(it) } },
                                onPttPressChange = remember(viewModel) { { viewModel.setPttPressed(it) } },
                                onVisualizerEnabledChange = remember(viewModel) { { viewModel.setVisualizerEnabled(it) } },
                                onStartClick = onStartClick,
                                onStopClick = onStopClick,
                                onPauseClick = onPauseClick
                            )

                            MainTab.SETTINGS -> SettingsScreen(
                                uiState = uiState,
                                onBackToHome = onSelectHome,
                                onAutoStartChange = remember(viewModel) { { viewModel.setAutoStartStreaming(it) } },
                                onPushToTalkChange = remember(viewModel) { { viewModel.setPushToTalkEnabled(it) } },
                                onAutoReconnectChange = remember(viewModel) { { viewModel.setAutoReconnectEnabled(it) } },
                                onKeepScreenAwakeChange = remember(viewModel) { { viewModel.setKeepScreenAwake(it) } },
                                onOverlayToggle = onOverlayToggle,
                                onTransportModeChange = remember(viewModel) { { viewModel.setTransportMode(it) } },
                                onRefreshMics = remember(viewModel) { { viewModel.refreshAvailableMics() } },
                                onSelectMicDevice = remember(viewModel) { { viewModel.setPreferredMicDevice(it) } },
                                onSelectAudioSource = remember(viewModel) { { viewModel.setMicMode(it) } },
                                onSelectSampleRate = remember(viewModel) { { viewModel.setSampleRate(it) } },
                                onSelectAudioFormat = remember(viewModel) { { viewModel.setAudioFormat(it) } },
                                onSelectChannels = remember(viewModel) { { viewModel.setChannels(it) } },
                                onGainChange = remember(viewModel) { { viewModel.setGain(it) } },
                                onDarkModeChange = remember(viewModel) { { viewModel.setDarkMode(it) } },
                                onOledBlackChange = remember(viewModel) { { viewModel.setOledBlackEnabled(it) } },
                                onPaletteStyleChange = remember(viewModel) { { viewModel.setPaletteStyle(it) } },
                                onCustomThemeColorChange = remember(viewModel) { { viewModel.setCustomThemeColor(it) } },
                                onHorizontalNavModeChange = remember(viewModel) { { viewModel.setHorizontalNavMode(it) } },
                                onVisualizerEnabledChange = remember(viewModel) { { viewModel.setVisualizerEnabled(it) } },
                                onVisualizerStyleChange = remember(viewModel) { { viewModel.setVisualizerStyle(it) } },
                                onOpenGuide = remember(viewModel) { { viewModel.setGuideDialogVisible(true) } },
                                onShareCli = onShareCli
                            )
                        }
                    }
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

@Composable
private fun CompactHorizontalBottomBar(
    activeTab: MainTab,
    onSelectTab: (MainTab) -> Unit
) {
    val colors = PhoneMicTheme.colors
    Surface(
        color = colors.bottomBarSurface,
        modifier = Modifier
            .fillMaxWidth()
            .testTag("bottom_nav_bar")
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .windowInsetsPadding(WindowInsets.navigationBars.only(WindowInsetsSides.Bottom + WindowInsetsSides.Horizontal))
        ) {
            HorizontalDivider(color = colors.border)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp)
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally),
                verticalAlignment = Alignment.CenterVertically
            ) {
                val tabs = remember {
                    listOf(
                        Triple(MainTab.STATUS, R.string.nav_status, "nav_tab_status"),
                        Triple(MainTab.HOME, R.string.nav_home, "nav_tab_home"),
                        Triple(MainTab.SETTINGS, R.string.nav_settings, "open_settings_button")
                    )
                }

                tabs.forEach { (tab, labelRes, tag) ->
                    val selected = activeTab == tab
                    val icon = when (tab) {
                        MainTab.STATUS -> if (selected) Icons.Filled.Analytics else Icons.Outlined.Analytics
                        MainTab.HOME -> if (selected) Icons.Filled.Mic else Icons.Outlined.Mic
                        MainTab.SETTINGS -> if (selected) Icons.Filled.Settings else Icons.Outlined.Settings
                    }
                    val contentColor = if (selected) colors.accent else colors.textSecondary

                    Surface(
                        onClick = { onSelectTab(tab) },
                        color = Color.Transparent,
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier
                            .weight(1f)
                            .widthIn(max = 200.dp)
                            .fillMaxHeight()
                            .testTag(tag)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxSize(),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Box(
                                contentAlignment = Alignment.Center,
                                modifier = Modifier
                                    .size(width = 44.dp, height = 26.dp)
                                    .background(
                                        color = if (selected) colors.accentSoftBg else Color.Transparent,
                                        shape = CircleShape
                                    )
                                    .testTag("nav_pill_${tab.name.lowercase()}")
                            ) {
                                Icon(
                                    imageVector = icon,
                                    contentDescription = stringResource(labelRes),
                                    tint = contentColor,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = stringResource(labelRes),
                                color = contentColor,
                                fontSize = 12.sp,
                                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                                maxLines = 1
                            )
                        }
                    }
                }
            }
        }
    }
}
