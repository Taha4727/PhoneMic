package com.example.ui.screens

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.PhoneMicViewModel
import com.example.ui.components.BatteryOptimizationBanner
import com.example.ui.components.GainBoostControl
import com.example.ui.components.HeroMicControl
import com.example.ui.components.NetworkConfigSection
import com.example.ui.components.ReceiverGuideDialog
import com.example.ui.components.StreamTelemetryCard
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StreamActiveGreen
import com.example.ui.theme.StreamErrorRed
import com.example.ui.theme.StreamWarningAmber
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioDarkBg
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary
import java.util.Locale

@Composable
fun PhoneMicScreen(
    viewModel: PhoneMicViewModel,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsState()
    val audioDb by viewModel.audioDb.collectAsState()
    val context = LocalContext.current
    var selectedTab by remember { mutableIntStateOf(0) }

    // Compatibility check for Android 7.1.1 (API 25) and Android 10 (API 29)
    val permissionsLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val recordAudioGranted = permissions[Manifest.permission.RECORD_AUDIO] ?: false
        if (recordAudioGranted) {
            viewModel.startStreaming(context)
        } else {
            Toast.makeText(
                context,
                "Microphone permission is required to stream audio to PC",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    fun handleStartStream() {
        val hasMicPermission = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED

        val hasNotificationPermission = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
        } else true

        val permissionsToRequest = mutableListOf<String>()
        if (!hasMicPermission) permissionsToRequest.add(Manifest.permission.RECORD_AUDIO)
        if (!hasNotificationPermission && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissionsToRequest.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        if (permissionsToRequest.isNotEmpty()) {
            permissionsLauncher.launch(permissionsToRequest.toTypedArray())
        } else {
            viewModel.startStreaming(context)
        }
    }

    Scaffold(
        modifier = modifier
            .fillMaxSize()
            .background(StudioDarkBg),
        containerColor = StudioDarkBg,
        topBar = {
            // Minimal Header Bar without bulky top app bar
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(StudioDarkBg)
                    .statusBarsPadding()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Left: Live status and target IP
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .background(
                                    when {
                                        !uiState.isRunning -> NeonCyan
                                        uiState.isPaused -> StreamWarningAmber
                                        uiState.isConnected -> StreamActiveGreen
                                        else -> StreamWarningAmber
                                    },
                                    CircleShape
                                )
                        )
                        Text(
                            text = if (uiState.isRunning) {
                                val s = uiState.elapsedSeconds
                                val m = s / 60
                                val sec = s % 60
                                String.format(Locale.US, "LIVE %02d:%02d", m, sec)
                            } else {
                                "READY"
                            },
                            color = TextPrimary,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        Text(
                            text = "•",
                            color = TextMuted,
                            fontSize = 10.sp
                        )
                        Text(
                            text = "${uiState.ip}:${uiState.port}",
                            color = TextMuted,
                            fontSize = 10.5.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }

                    // Right: Studio/Stats Switch + Help Button
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .background(Color(0xFF0F1622), RoundedCornerShape(8.dp))
                                .border(1.dp, StudioBorder, RoundedCornerShape(8.dp))
                                .padding(2.dp)
                        ) {
                            Row(horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                                Box(
                                    modifier = Modifier
                                        .height(28.dp)
                                        .background(
                                            if (selectedTab == 0) Color(0xFF14293D) else Color.Transparent,
                                            RoundedCornerShape(6.dp)
                                        )
                                        .clickable { selectedTab = 0 }
                                        .padding(horizontal = 10.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "Studio",
                                        color = if (selectedTab == 0) NeonCyan else TextSecondary,
                                        fontSize = 11.sp,
                                        fontWeight = if (selectedTab == 0) FontWeight.Bold else FontWeight.Normal
                                    )
                                }

                                Box(
                                    modifier = Modifier
                                        .height(28.dp)
                                        .background(
                                            if (selectedTab == 1) Color(0xFF14293D) else Color.Transparent,
                                            RoundedCornerShape(6.dp)
                                        )
                                        .clickable { selectedTab = 1 }
                                        .padding(horizontal = 10.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "Stats",
                                        color = if (selectedTab == 1) NeonCyan else TextSecondary,
                                        fontSize = 11.sp,
                                        fontWeight = if (selectedTab == 1) FontWeight.Bold else FontWeight.Normal
                                    )
                                }
                            }
                        }

                        IconButton(
                            onClick = { viewModel.setGuideDialogVisible(true) },
                            modifier = Modifier
                                .size(32.dp)
                                .testTag("help_guide_button")
                        ) {
                            Icon(
                                imageVector = Icons.Default.HelpOutline,
                                contentDescription = "Setup Guide",
                                tint = TextSecondary,
                                modifier = Modifier.size(17.dp)
                            )
                        }
                    }
                }

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(1.dp)
                        .background(StudioBorder)
                )
            }
        },
        bottomBar = {
            // Slim Bottom Bar when Streaming
            AnimatedVisibility(
                visible = uiState.isRunning,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Color(0xFF0A1017))
                        .border(1.dp, StudioBorder)
                        .navigationBarsPadding()
                        .padding(horizontal = 14.dp, vertical = 6.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .background(
                                        if (uiState.isPaused) StreamWarningAmber else StreamActiveGreen,
                                        CircleShape
                                    )
                            )
                            Text(
                                text = if (uiState.isPaused) "MUTED" else "STREAMING",
                                color = if (uiState.isPaused) StreamWarningAmber else StreamActiveGreen,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            OutlinedButton(
                                onClick = { viewModel.togglePause() },
                                modifier = Modifier.height(34.dp),
                                shape = RoundedCornerShape(6.dp),
                                colors = ButtonDefaults.outlinedButtonColors(
                                    contentColor = if (uiState.isPaused) StreamWarningAmber else TextPrimary
                                )
                            ) {
                                Text(if (uiState.isPaused) "Resume" else "Mute", fontSize = 11.sp, fontWeight = FontWeight.Bold, maxLines = 1)
                            }

                            Button(
                                onClick = { viewModel.stopStreaming(context) },
                                modifier = Modifier.height(34.dp),
                                shape = RoundedCornerShape(6.dp),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = StreamErrorRed,
                                    contentColor = Color.White
                                )
                            ) {
                                Text("Stop", fontSize = 11.sp, fontWeight = FontWeight.Bold, maxLines = 1)
                            }
                        }
                    }
                }
            }
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 640.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {

                    // Battery Optimization Banner (Only visible if not exempted)
                    BatteryOptimizationBanner(
                        isIgnored = uiState.isIgnoringBatteryOptimizations,
                        onDismissOrGranted = { viewModel.checkBatteryOptimization() }
                    )

                    when (selectedTab) {
                        0 -> {
                            // ==========================================
                            // MAIN PAGE: ALL IN ONE PLACE WITHOUT SCROLLING!
                            // ==========================================

                            // 1. Unified Microphone Control & Live Audio Meter Console
                            HeroMicControl(
                                isRunning = uiState.isRunning,
                                isPaused = uiState.isPaused,
                                isConnected = uiState.isConnected,
                                statusMessage = uiState.statusMessage,
                                elapsedSeconds = uiState.elapsedSeconds,
                                ip = uiState.ip,
                                port = uiState.port,
                                transportMode = uiState.transportMode,
                                connectionMode = uiState.connectionMode,
                                audioDb = audioDb,
                                onStartClick = { handleStartStream() },
                                onPauseClick = { viewModel.togglePause() },
                                onStopClick = { viewModel.stopStreaming(context) }
                            )

                            // 3. TARGET PC RECEIVER (IP, Port, Auto-Detect PC, Wi-Fi vs USB toggle, Direct USB tethering button)
                            NetworkConfigSection(
                                ip = uiState.ip,
                                port = uiState.port,
                                isValidIp = viewModel.isValidIp(uiState.ip),
                                isValidPort = viewModel.isValidPort(uiState.port),
                                isEnabled = !uiState.isRunning,
                                isScanningPc = uiState.isScanningPc,
                                scanFeedback = uiState.scanFeedback,
                                onIpChange = { viewModel.setIp(it) },
                                onPortChange = { viewModel.setPort(it) },
                                onScanClick = { viewModel.scanForPc(context) },
                                connectionMode = uiState.connectionMode,
                                transportMode = uiState.transportMode,
                                onConnectionModeChange = { viewModel.setConnectionMode(it) },
                                onTransportModeChange = { viewModel.setTransportMode(it) }
                            )

                            // 4. ACCURATE GAIN BOOST & MIC PROFILE (Clean 0.1x steps, +/- buttons, presets)
                            GainBoostControl(
                                micMode = uiState.micMode,
                                gain = uiState.gain,
                                isEnabled = !uiState.isRunning,
                                onMicModeChange = { viewModel.setMicMode(it) },
                                onGainChange = { viewModel.setGain(it) }
                            )
                        }

                        1 -> {
                            // ==========================================
                            // STATS & RECEIVER TELEMETRY PAGE
                            // ==========================================
                            StreamTelemetryCard(
                                isRunning = uiState.isRunning,
                                isPaused = uiState.isPaused,
                                isConnected = uiState.isConnected,
                                packetsSent = uiState.packetsSent,
                                bytesSent = uiState.bytesSent,
                                packetRate = uiState.packetRate,
                                transportMode = uiState.transportMode,
                                ip = uiState.ip,
                                port = uiState.port,
                                connectionMode = uiState.connectionMode,
                                elapsedSeconds = uiState.elapsedSeconds
                            )

                            OutlinedButton(
                                onClick = { viewModel.setGuideDialogVisible(true) },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(40.dp),
                                shape = RoundedCornerShape(8.dp),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = NeonCyan)
                            ) {
                                Icon(Icons.Default.HelpOutline, contentDescription = null, modifier = Modifier.size(15.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("Open Receiver Guide & Python Script (v0.6.3)", fontSize = 11.5.sp, fontWeight = FontWeight.Bold, maxLines = 1)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))
                }
            }
        }
    }

    if (uiState.showGuideDialog) {
        ReceiverGuideDialog(
            onDismissRequest = { viewModel.setGuideDialogVisible(false) }
        )
    }
}
