package com.example.ui.components

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Headphones
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.BuildConfig
import com.example.ui.theme.JetBrainsMonoFontFamily
import com.example.ui.theme.PhoneMicTheme
import com.example.util.ShareHelper

@Composable
fun ReceiverGuideDialog(
    onDismissRequest: () -> Unit
) {
    val context = LocalContext.current
    val colors = PhoneMicTheme.colors
    var selectedTab by remember { mutableIntStateOf(0) }

    val quickScriptPreview = remember {
        """
# PhoneMic Standalone CLI Receiver v${BuildConfig.VERSION_NAME}
# Zero GUI dependencies • Multi-Phone Mixing • Real-Time Monitoring
# Run on PC / Mac / Linux:
python phonemic_cli.py

# Keybindings in Terminal:
# [M] Toggle Headphone Monitor  [X] Switch Mix Mode (Sum / Duck)
# [P] Mute/Unmute Output        [+/-] Master Preamp Gain
# [H] Detailed Device Telemetry [Q] Quit
        """.trimIndent()
    }

    Dialog(onDismissRequest = onDismissRequest) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 12.dp),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = colors.cardSurface),
            border = BorderStroke(1.dp, colors.border),
            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
        ) {
            Column(
                modifier = Modifier
                    .padding(18.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "PC RECEIVER SETUP",
                            color = colors.accent,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 0.8.sp
                        )
                        Text(
                            text = "Windows & Linux GUI + CLI v${BuildConfig.VERSION_NAME} Guide",
                            color = colors.textMuted,
                            fontSize = 11.sp
                        )
                    }
                    IconButton(
                        onClick = onDismissRequest,
                        modifier = Modifier.size(48.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = colors.textSecondary
                        )
                    }
                }

                val tabs = listOf("Quick Start", "CLI", "Hotkeys", "Multi-Mic", "Virtual Mic")
                TabRow(
                    selectedTabIndex = selectedTab,
                    containerColor = colors.nestedSurface,
                    contentColor = colors.accent,
                    indicator = { tabPositions ->
                        TabRowDefaults.SecondaryIndicator(
                            modifier = Modifier.tabIndicatorOffset(tabPositions[selectedTab]),
                            color = colors.accent,
                            height = 2.dp
                        )
                    }
                ) {
                    tabs.forEachIndexed { index, title ->
                        Tab(
                            selected = selectedTab == index,
                            onClick = { selectedTab = index },
                            text = {
                                Text(
                                    text = title,
                                    fontSize = 10.5.sp,
                                    fontWeight = if (selectedTab == index) FontWeight.Bold else FontWeight.Normal,
                                    color = if (selectedTab == index) colors.accent else colors.textSecondary
                                )
                            }
                        )
                    }
                }

                when (selectedTab) {
                    0 -> QuickStartTab()
                    1 -> CliScriptTab(context, quickScriptPreview)
                    2 -> HotkeysTab()
                    3 -> MultiMicTab()
                    4 -> VbCableTab()
                }

                Button(
                    onClick = onDismissRequest,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = colors.accent,
                        contentColor = colors.onAccent
                    ),
                    elevation = ButtonDefaults.buttonElevation(0.dp, 0.dp, 0.dp)
                ) {
                    Text("Got it", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun QuickStartTab() {
    val colors = PhoneMicTheme.colors
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        GuideStepBox(title = "Step 1: Choose Your Receiver") {
            Text(
                text = "Run the GUI receiver or the lightweight CLI receiver on Windows or Linux:",
                color = colors.textSecondary,
                fontSize = 11.sp
            )
            Text(
                text = "A) Windows GUI: PhoneMicReceiver.exe or start_receiver.bat\n" +
                    "B) Linux GUI: ./setup_linux.sh && ./start_receiver.sh (or PhoneMicReceiver binary)\n" +
                    "C) Standalone CLI (Win/Mac/Linux): python phonemic_cli.py",
                fontFamily = JetBrainsMonoFontFamily,
                color = colors.accent,
                fontSize = 10.5.sp,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "Tip: On Arch Linux you can also install via windows_receiver/linux/PKGBUILD (makepkg -si).",
                color = colors.secondaryAccent,
                fontSize = 10.5.sp
            )
        }

        GuideStepBox(title = "Step 2: Connect from Phone") {
            Text(
                text = "1. Ensure phone & PC are on the same Wi-Fi (or USB Tethering).\n" +
                    "2. Tap 'Scan' next to IP & Port or scan the QR Code on the receiver.\n" +
                    "3. Tap 'Start' to broadcast low-latency audio.",
                color = colors.textSecondary,
                fontSize = 11.sp,
                lineHeight = 16.sp
            )
        }

        GuideStepBox(title = "Step 3: Route to Discord / OBS / Games") {
            Text(
                text = "• Windows: Select 'CABLE Output (VB-Audio Virtual Cable)' as your Microphone.\n" +
                    "• Linux (PipeWire/PulseAudio): Select 'PhoneMic Virtual Mic' as your Microphone.",
                color = colors.textSecondary,
                fontSize = 11.sp,
                lineHeight = 15.sp
            )
        }
    }
}

@Composable
private fun CliScriptTab(context: Context, scriptPreview: String) {
    val colors = PhoneMicTheme.colors
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            text = "Lightweight Standalone Receiver (phonemic_cli.py):",
            color = colors.textPrimary,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = "No GUI dependencies. Supports multiple phones mixed simultaneously, real-time headphone monitoring ('M' key), auto-ducking, and live ANSI volume meters.",
            color = colors.textSecondary,
            fontSize = 11.sp,
            lineHeight = 15.sp
        )

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(colors.nestedSurface, RoundedCornerShape(10.dp))
                .border(1.dp, colors.border, RoundedCornerShape(10.dp))
                .padding(10.dp)
        ) {
            Text(
                text = scriptPreview,
                fontFamily = JetBrainsMonoFontFamily,
                color = colors.accent,
                fontSize = 10.sp,
                lineHeight = 14.sp
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedButton(
                onClick = {
                    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                    clipboard.setPrimaryClip(ClipData.newPlainText("PhoneMic Run Command", "python phonemic_cli.py"))
                    Toast.makeText(context, "Copied run command to clipboard", Toast.LENGTH_SHORT).show()
                },
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp),
                shape = RoundedCornerShape(8.dp),
                border = BorderStroke(1.dp, colors.border),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = colors.accent)
            ) {
                Icon(imageVector = Icons.Default.ContentCopy, contentDescription = null, modifier = Modifier.size(14.dp))
                Spacer(modifier = Modifier.width(4.dp))
                Text("Copy Cmd", fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }

            Button(
                onClick = { ShareHelper.shareCliReceiver(context) },
                modifier = Modifier
                    .weight(1f)
                    .height(48.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = colors.accentSoftBg,
                    contentColor = colors.accent
                ),
                elevation = ButtonDefaults.buttonElevation(0.dp, 0.dp, 0.dp)
            ) {
                Icon(imageVector = Icons.Default.Share, contentDescription = null, modifier = Modifier.size(14.dp))
                Spacer(modifier = Modifier.width(4.dp))
                Text("Share Script", fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun HotkeysTab() {
    val colors = PhoneMicTheme.colors
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = "While running either the CLI receiver or GUI receiver, use these interactive keys:",
            color = colors.textSecondary,
            fontSize = 11.5.sp
        )

        HotkeyItem(key = "M", action = "Toggle Headphone Monitoring", detail = "Routes microphone audio into your headphones for zero-lag monitoring.")
        HotkeyItem(key = "X", action = "Switch Mix Mode (Sum / Duck)", detail = "Toggles between Sum & Soft Limiter and Auto-Duck Priority (75% duck).")
        HotkeyItem(key = "P", action = "Toggle Mute / Output Pause", detail = "Silences all audio output immediately without closing sockets.")
        HotkeyItem(key = "+/-", action = "Preamp Gain Boost / Cut", detail = "Steps master digital volume in 1 dB increments (-24 dB to +18 dB).")
        HotkeyItem(key = "0", action = "Reset Master Gain", detail = "Resets digital gain back to unity (0.0 dB).")
        HotkeyItem(key = "H", action = "Toggle Detailed Telemetry", detail = "Shows/hides bitrate (kbps), jitter buffer depth (ms), and packet loss.")
        HotkeyItem(key = "Q", action = "Quit Receiver", detail = "Cleanly closes audio streams, clears buffers, and exits.")
    }
}

@Composable
private fun MultiMicTab() {
    val colors = PhoneMicTheme.colors
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        GuideStepBox(title = "Multi-Device Simultaneous Connection") {
            Text(
                text = "Connect 2, 3, or more phones to the receiver simultaneously.",
                color = colors.accent,
                fontSize = 11.5.sp,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "• All phones use the same PC IP address and port (default 5001).\n" +
                    "• The receiver identifies each phone and mixes voices in real time.\n" +
                    "• Different sample rates (48k, 24k, 16k) are aligned cleanly.\n" +
                    "• Built-in soft limiter prevents clipping when multiple speakers talk.",
                color = colors.textSecondary,
                fontSize = 11.sp,
                lineHeight = 16.sp
            )
        }

        GuideStepBox(title = "Mixing Profiles") {
            Text("1. Sum & Soft Limiter: Ideal for podcasts or teams with equal voices.", color = colors.textSecondary, fontSize = 10.5.sp)
            Text("2. Auto-Duck Priority: Attenuates secondary mics by 75% during primary speech.", color = colors.textSecondary, fontSize = 10.5.sp)
        }
    }
}

@Composable
private fun HotkeyItem(key: String, action: String, detail: String) {
    val colors = PhoneMicTheme.colors
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(colors.nestedSurface, RoundedCornerShape(8.dp))
            .border(1.dp, colors.border, RoundedCornerShape(8.dp))
            .padding(10.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(34.dp)
                .background(colors.accentSoftBg, RoundedCornerShape(6.dp))
                .border(1.dp, colors.accent.copy(alpha = 0.5f), RoundedCornerShape(6.dp)),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = key,
                color = colors.accent,
                fontWeight = FontWeight.ExtraBold,
                fontFamily = JetBrainsMonoFontFamily,
                fontSize = 12.sp
            )
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(text = action, color = colors.textPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            Text(text = detail, color = colors.textMuted, fontSize = 10.5.sp)
        }
    }
}

@Composable
private fun VbCableTab() {
    val colors = PhoneMicTheme.colors
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(colors.nestedSurface, RoundedCornerShape(10.dp))
                .border(1.dp, colors.border, RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(imageVector = Icons.Default.Headphones, contentDescription = null, tint = colors.accent, modifier = Modifier.size(16.dp))
                    Text("Windows: VB-Audio Virtual Cable", color = colors.textPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }
                Text(
                    text = "1. Download and install free VB-CABLE driver from vb-audio.com.\n" +
                        "2. In Windows Sound Settings, set VB-CABLE sample rate to 48000 Hz (16-bit or 24-bit).\n" +
                        "3. The PhoneMic receiver automatically routes audio to 'CABLE Input' via WASAPI.\n" +
                        "4. In Discord, Zoom, OBS, or Games: select 'CABLE Output' as your Microphone.",
                    color = colors.textSecondary,
                    fontSize = 11.sp,
                    lineHeight = 16.sp
                )
            }
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(colors.nestedSurface, RoundedCornerShape(10.dp))
                .border(1.dp, colors.border, RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(imageVector = Icons.Default.Headphones, contentDescription = null, tint = colors.accent, modifier = Modifier.size(16.dp))
                    Text("Linux: PipeWire / PulseAudio Virtual Mic", color = colors.textPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }
                Text(
                    text = "1. The Linux receiver automatically creates 'PhoneMic_Sink' + 'PhoneMic Virtual Mic' on startup (requires pipewire-pulse / pulseaudio-utils).\n" +
                        "2. Or run: phonemic-receiver --create-virtual-mic.\n" +
                        "3. In Discord, OBS, or browsers: select 'PhoneMic Virtual Mic' as your Microphone.",
                    color = colors.textSecondary,
                    fontSize = 11.sp,
                    lineHeight = 16.sp
                )
            }
        }
    }
}

@Composable
private fun GuideStepBox(
    title: String,
    content: @Composable () -> Unit
) {
    val colors = PhoneMicTheme.colors
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(colors.nestedSurface, RoundedCornerShape(10.dp))
            .border(1.dp, colors.border, RoundedCornerShape(10.dp))
            .padding(12.dp)
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(text = title, color = colors.textPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            content()
        }
    }
}
