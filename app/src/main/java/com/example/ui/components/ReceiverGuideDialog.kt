package com.example.ui.components

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
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
import androidx.compose.material.icons.filled.Terminal
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StudioBorder
import com.example.ui.theme.StudioCard
import com.example.ui.theme.TextMuted
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary
import com.example.util.ShareHelper

@Composable
fun ReceiverGuideDialog(
    onDismissRequest: () -> Unit
) {
    val context = LocalContext.current
    var selectedTab by remember { mutableIntStateOf(0) }

    val quickScriptPreview = remember {
        """
# PhoneMic Standalone CLI Receiver v1.2.0
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
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = StudioCard),
            border = androidx.compose.foundation.BorderStroke(1.dp, StudioBorder)
        ) {
            Column(
                modifier = Modifier
                    .padding(18.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(
                                text = "PC RECEIVER SETUP",
                                color = NeonCyan,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 0.8.sp
                            )
                        }
                        Text(
                            text = "Windows GUI & Standalone CLI v1.2.0 Guide",
                            color = TextMuted,
                            fontSize = 11.sp
                        )
                    }
                    IconButton(onClick = onDismissRequest, modifier = Modifier.size(28.dp)) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                // Tab Selector
                val tabs = listOf("Quick Start", "CLI Receiver", "Hotkeys", "Multi-Mic", "VB-CABLE")
                TabRow(
                    selectedTabIndex = selectedTab,
                    containerColor = Color(0xFF0F1622),
                    contentColor = NeonCyan,
                    indicator = { tabPositions ->
                        TabRowDefaults.SecondaryIndicator(
                            modifier = Modifier.tabIndicatorOffset(tabPositions[selectedTab]),
                            color = NeonCyan,
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
                                    color = if (selectedTab == index) NeonCyan else TextSecondary
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
                        .height(42.dp),
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = NeonCyan,
                        contentColor = Color(0xFF003038)
                    )
                ) {
                    Text("Got it", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun QuickStartTab() {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF0C131D), RoundedCornerShape(10.dp))
                .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Step 1: Choose Your Receiver", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Text("You can run either the Full GUI receiver or the Lightweight CLI receiver on your computer:", color = TextSecondary, fontSize = 11.sp)
                Text(
                    text = "A) GUI App: Run start_receiver.bat in windows_receiver\nB) CLI App: python phonemic_cli.py",
                    fontFamily = FontFamily.Monospace,
                    color = NeonCyan,
                    fontSize = 11.5.sp,
                    fontWeight = FontWeight.Bold
                )
                Text("Tip: Double-click build_exe.bat to package everything into a single standalone PhoneMicReceiver.exe!", color = Color(0xFF38BDF8), fontSize = 10.5.sp)
            }
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF0C131D), RoundedCornerShape(10.dp))
                .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Step 2: Connect from Phone", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Text(
                    text = "1. Ensure phone & PC are on the same Wi-Fi (or USB Tethering).\n" +
                           "2. Tap 'AUTO-DETECT PC' or scan the QR Code on the receiver.\n" +
                           "3. Tap 'START STREAMING' to broadcast crystal-clear audio!",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    lineHeight = 16.sp
                )
            }
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF0C131D), RoundedCornerShape(10.dp))
                .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Step 3: Route to Discord / OBS / Games", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Text(
                    text = "Select 'CABLE Output (VB-Audio Virtual Cable)' as your Microphone in Discord, Zoom, OBS, or Steam voice settings.",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    lineHeight = 15.sp
                )
            }
        }
    }
}

@Composable
private fun CliScriptTab(context: Context, scriptPreview: String) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            text = "Lightweight Standalone Receiver (phonemic_cli.py):",
            color = TextPrimary,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = "No GUI dependencies. Supports multiple phones mixed simultaneously, real-time headphone monitoring ('M' key), auto-ducking, and live ANSI volume meters.",
            color = TextSecondary,
            fontSize = 11.sp,
            lineHeight = 15.sp
        )

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF080D14), RoundedCornerShape(10.dp))
                .border(1.dp, Color(0xFF182230), RoundedCornerShape(10.dp))
                .padding(10.dp)
        ) {
            Text(
                text = scriptPreview,
                fontFamily = FontFamily.Monospace,
                color = Color(0xFF7DD3FC),
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
                    Toast.makeText(context, "Copied run command to clipboard!", Toast.LENGTH_SHORT).show()
                },
                modifier = Modifier
                    .weight(1f)
                    .height(38.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = NeonCyan)
            ) {
                Icon(imageVector = Icons.Default.ContentCopy, contentDescription = null, modifier = Modifier.size(14.dp))
                Spacer(modifier = Modifier.width(4.dp))
                Text("Copy Command", fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }

            Button(
                onClick = {
                    ShareHelper.shareCliReceiver(context)
                },
                modifier = Modifier
                    .weight(1f)
                    .height(38.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFF14293D),
                    contentColor = NeonCyan
                )
            ) {
                Icon(imageVector = Icons.Default.Share, contentDescription = null, modifier = Modifier.size(14.dp))
                Spacer(modifier = Modifier.width(4.dp))
                Text("Share Script to PC", fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun HotkeysTab() {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = "While running either the CLI receiver or GUI receiver, use these interactive keys:",
            color = TextSecondary,
            fontSize = 11.5.sp
        )

        HotkeyItem(key = "M", action = "Toggle Headphone Monitoring", detail = "Directly routes microphone audio into your headphones so you can hear yourself without lag.")
        HotkeyItem(key = "X", action = "Switch Mix Mode (Sum / Duck)", detail = "Toggles between Sum & Soft Limiter (all mics equal) and Auto-Duck Priority (ducks others by 75%).")
        HotkeyItem(key = "P", action = "Toggle Mute / Output Pause", detail = "Silences all audio output immediately without stopping connection sockets.")
        HotkeyItem(key = "+/-", action = "Preamp Gain Boost / Cut", detail = "Steps master digital volume in 1 dB increments (up to +18 dB or down to -24 dB).")
        HotkeyItem(key = "0", action = "Reset Master Gain", detail = "Quickly resets digital gain to unity (0.0 dB).")
        HotkeyItem(key = "H", action = "Toggle Detailed Telemetry", detail = "Shows/hides bit-rate (kbps), jitter buffer depth (ms), and packet loss per device.")
        HotkeyItem(key = "Q", action = "Quit Receiver", detail = "Safely closes PortAudio streams, cleans memory buffers, and exits.")
    }
}

@Composable
private fun MultiMicTab() {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF0C131D), RoundedCornerShape(10.dp))
                .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Multi-Device Simultaneous Connection", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Text(
                    text = "You can connect 2, 3, or more phones to the receiver simultaneously!",
                    color = NeonCyan,
                    fontSize = 11.5.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "• All phones use the exact same PC IP address and port (default 5001).\n" +
                           "• The receiver automatically identifies each phone and mixes their voices in real time.\n" +
                           "• Different audio qualities (48k, 24k, 16k) are seamlessly upsampled and aligned.\n" +
                           "• Built-in tanh soft limiter prevents digital clipping when multiple people speak at once.",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    lineHeight = 16.sp
                )
            }
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF0C131D), RoundedCornerShape(10.dp))
                .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Mixing Profiles", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Text("1. Sum & Soft Limiter: Perfect for group podcasts or gaming teams where everyone has an equal voice.", color = TextSecondary, fontSize = 10.5.sp)
                Text("2. Auto-Duck Priority: Detects the primary active speaker and attenuates background chatter from other phones by 75%.", color = TextSecondary, fontSize = 10.5.sp)
            }
        }
    }
}

@Composable
private fun HotkeyItem(key: String, action: String, detail: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF0C131D), RoundedCornerShape(8.dp))
            .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(8.dp))
            .padding(10.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(34.dp)
                .background(Color(0xFF1A2638), RoundedCornerShape(6.dp))
                .border(1.dp, NeonCyan.copy(alpha = 0.5f), RoundedCornerShape(6.dp)),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = key,
                color = NeonCyan,
                fontWeight = FontWeight.ExtraBold,
                fontFamily = FontFamily.Monospace,
                fontSize = 12.sp
            )
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(text = action, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            Text(text = detail, color = TextMuted, fontSize = 10.5.sp)
        }
    }
}

@Composable
private fun VbCableTab() {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF0C131D), RoundedCornerShape(10.dp))
                .border(1.dp, Color(0xFF1E2838), RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(imageVector = Icons.Default.Headphones, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(16.dp))
                    Text("VB-Audio Virtual Cable Setup", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }
                Text(
                    text = "1. Download and install free VB-CABLE driver from vb-audio.com.\n" +
                           "2. In Windows Sound Settings, set VB-CABLE sample rate to 48000 Hz (16-bit or 24-bit).\n" +
                           "3. The PhoneMic receiver automatically routes audio to 'CABLE Input' via WASAPI.\n" +
                           "4. In Discord, Zoom, OBS, or Games: select 'CABLE Output' as your Input Microphone Device!",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    lineHeight = 16.sp
                )
            }
        }
    }
}
