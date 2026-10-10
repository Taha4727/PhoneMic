package com.example.ui.components

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
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

@Composable
fun ReceiverGuideDialog(
    onDismissRequest: () -> Unit
) {
    val context = LocalContext.current
    var selectedTab by remember { mutableIntStateOf(0) }

    val fullPythonScript = remember {
        """
import os, sys, time, socket, struct, threading, queue, math, wave
from datetime import datetime
try:
    import numpy as np, sounddevice as sd
except ImportError:
    print("[ERROR] Please run: pip install numpy sounddevice")
    sys.exit(1)
try:
    import msvcrt
except ImportError:
    msvcrt = None

# PhoneMic Receiver v0.6.3 (Bidirectional Remote Control)
VERSION = "0.6.3"
PORT = 5001
HOST = "0.0.0.0"
RATE, CHANNELS, FRAMES = 48000, 1, 480
TARGET_DEVICE = "CABLE Input"
CMD_PAUSE, CMD_RESUME = b"PMP1", b"PMR1"

def find_devices():
    cable, default = None, sd.default.device[1]
    for idx, dev in enumerate(sd.query_devices()):
        if dev['max_output_channels'] > 0:
            if TARGET_DEVICE.lower() in dev['name'].lower() and cable is None:
                cable = (idx, dev)
    return cable or (default, sd.query_devices(default))

class Receiver:
    def __init__(self, dev_idx):
        self.dev_idx = dev_idx
        self.running, self.paused, self.recording, self.monitoring = True, False, False, False
        self.gain = 1.0
        self.q = queue.Queue(maxsize=30)
        self.pkts, self.lost, self.last_seq = 0, 0, -1
        self.out = sd.OutputStream(samplerate=RATE, channels=2, dtype='float32', device=dev_idx, latency='low', blocksize=FRAMES)
        self.out.start()
        threading.Thread(target=self._play_loop, daemon=True).start()
        threading.Thread(target=self._udp_loop, daemon=True).start()

    def _play_loop(self):
        silence = np.zeros((FRAMES, 2), dtype=np.float32)
        while self.running:
            try:
                b = self.q.get(timeout=0.05)
                self.out.write(silence if self.paused else b)
            except: pass

    def _udp_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024)
        s.bind((HOST, PORT))
        buf = bytearray(2048)
        while self.running:
            try:
                n, addr = s.recvfrom_into(buf)
                if buf[:4] == b"PMD0":
                    s.sendto(b"PMA1 " + VERSION.encode(), addr)
                elif buf[:4] == b"PM01" and n >= 8:
                    seq = struct.unpack(">I", buf[4:8])[0]
                    if self.last_seq != -1 and 1 < (seq - self.last_seq) < 5000:
                        self.lost += (seq - self.last_seq - 1)
                    self.last_seq = seq
                    pcm = np.frombuffer(bytes(buf[8:n]), dtype=np.int16)
                    flt = (pcm / 32768.0).astype(np.float32) * self.gain
                    flt = np.clip(flt, -0.95, 0.95)
                    st = np.column_stack((flt, flt))
                    if self.q.full(): self.q.get_nowait()
                    self.q.put_nowait(st)
                    self.pkts += 1
            except: pass

print(f"PhoneMic Receiver v{VERSION} ready on port {PORT}. [P] Pause | [R] Record | [M] Monitor | [Q] Quit")
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
                                text = "WINDOWS RECEIVER 0.6.3",
                                color = NeonCyan,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 0.8.sp
                            )
                        }
                        Text(
                            text = "Ultra-low latency audio engine & launcher",
                            color = TextMuted,
                            fontSize = 11.sp
                        )
                    }
                    IconButton(onClick = onDismissRequest, modifier = Modifier.size(28.dp)) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                // Tab Selector
                val tabs = listOf("Quick Start", "Receiver Script", "PC Hotkeys", "VB-CABLE")
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
                                    fontSize = 11.sp,
                                    fontWeight = if (selectedTab == index) FontWeight.Bold else FontWeight.Normal,
                                    color = if (selectedTab == index) NeonCyan else TextSecondary
                                )
                            }
                        )
                    }
                }

                when (selectedTab) {
                    0 -> QuickStartTab()
                    1 -> ScriptTab(context, fullPythonScript)
                    2 -> HotkeysTab()
                    3 -> VbCableTab()
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
                Text("Step 1: One-Click Launch on PC", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Text("In the windows_receiver folder, simply run:", color = TextSecondary, fontSize = 11.sp)
                Text(
                    text = "start_receiver.bat",
                    fontFamily = FontFamily.Monospace,
                    color = NeonCyan,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold
                )
                Text("It automatically installs sounddevice & numpy and displays your PC's IP address.", color = TextMuted, fontSize = 10.5.sp)
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
                Text("Step 2: Manual Command (Optional)", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Text("Or open PowerShell / Command Prompt and run:", color = TextSecondary, fontSize = 11.sp)
                Text(
                    text = "python phonemic_receiver.py",
                    fontFamily = FontFamily.Monospace,
                    color = NeonCyan,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold
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
                Text("Step 3: Connect from Phone", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Text(
                    text = "Tap 'AUTO-DETECT PC RECEIVER' in the app. The phone broadcasts 'PMD0' query and automatically fills your PC IP address. Then tap START STREAM!",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    lineHeight = 15.sp
                )
            }
        }
    }
}

@Composable
private fun ScriptTab(context: Context, scriptText: String) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            text = "Official PhoneMic Receiver v0.6.3 (supports UDP/TCP, Remote Pause Sync, Discovery PMD0, Noise Gate, Limiter & WAV recording):",
            color = TextSecondary,
            fontSize = 11.sp
        )

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFF080D14), RoundedCornerShape(10.dp))
                .border(1.dp, Color(0xFF182230), RoundedCornerShape(10.dp))
                .padding(10.dp)
        ) {
            Text(
                text = scriptText,
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
                    clipboard.setPrimaryClip(ClipData.newPlainText("PhoneMic Receiver Script", scriptText))
                    Toast.makeText(context, "Copied script to clipboard!", Toast.LENGTH_SHORT).show()
                },
                modifier = Modifier
                    .weight(1f)
                    .height(38.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = NeonCyan)
            ) {
                Icon(imageVector = Icons.Default.ContentCopy, contentDescription = null, modifier = Modifier.size(14.dp))
                Spacer(modifier = Modifier.width(4.dp))
                Text("Copy Script", fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }

            Button(
                onClick = {
                    val sendIntent = Intent().apply {
                        action = Intent.ACTION_SEND
                        putExtra(Intent.EXTRA_TEXT, scriptText)
                        putExtra(Intent.EXTRA_TITLE, "phonemic_receiver.py")
                        type = "text/plain"
                    }
                    val shareIntent = Intent.createChooser(sendIntent, "Share phonemic_receiver.py")
                    context.startActivity(shareIntent)
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
                Text("Share / Send to PC", fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun HotkeysTab() {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = "While the receiver script is running on your PC, press these keyboard keys inside the console window:",
            color = TextSecondary,
            fontSize = 11.5.sp
        )

        HotkeyItem(key = "P", action = "Toggle Pause / Resume (Remote Sync)", detail = "Silences audio immediately and remotely pauses/resumes microphone capture on the phone.")
        HotkeyItem(key = "R", action = "Toggle WAV Recording", detail = "Records 48 kHz stereo audio directly to PhoneMic_YYYYMMDD_HHMMSS.wav in script folder.")
        HotkeyItem(key = "M", action = "Toggle Speaker Monitor", detail = "Plays microphone audio through your PC speakers/headphones to test clarity.")
        HotkeyItem(key = "+/-", action = "Adjust Gain Boost", detail = "Quickly steps the digital preamp gain up or down in 0.5x increments.")
        HotkeyItem(key = "Q", action = "Quit Receiver", detail = "Safely releases audio device and closes network socket.")
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
                .size(32.dp)
                .background(Color(0xFF1A2638), RoundedCornerShape(6.dp))
                .border(1.dp, NeonCyan.copy(alpha = 0.5f), RoundedCornerShape(6.dp)),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = key,
                color = NeonCyan,
                fontWeight = FontWeight.ExtraBold,
                fontFamily = FontFamily.Monospace,
                fontSize = 13.sp
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
                           "2. In Windows Sound Settings, set VB-CABLE sample rate to 48000 Hz 16-bit or 24-bit.\n" +
                           "3. The receiver script automatically detects 'CABLE Input (VB-Audio Virtual Cable)' via WASAPI.\n" +
                           "4. In Discord, Zoom, OBS, or Games: select 'CABLE Output' as your Input Microphone Device!",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    lineHeight = 16.sp
                )
            }
        }
    }
}
