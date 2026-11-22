package com.example.ui.components

import android.content.Context
import android.content.ContextWrapper
import android.content.pm.PackageManager
import android.graphics.ImageFormat
import android.util.Log
import android.util.Size
import androidx.activity.ComponentActivity
import androidx.camera.core.CameraControl
import androidx.camera.core.CameraSelector
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.FlashOn
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import com.example.R
import com.example.ui.theme.NeonCyan
import com.example.ui.theme.StudioDarkBg
import com.example.ui.theme.TextPrimary
import com.example.ui.theme.TextSecondary
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.MultiFormatReader
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.common.HybridBinarizer
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.net.URI
import java.util.EnumMap
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.math.roundToInt

data class ScannedReceiverConfig(
    val ip: String,
    val port: Int,
    val transport: String
)

private fun Context.findActivity(): ComponentActivity? {
    var cur: Context? = this
    while (cur is ContextWrapper) {
        if (cur is ComponentActivity) return cur
        cur = cur.baseContext
    }
    return null
}

@Composable
fun QrScannerDialog(
    onDismiss: () -> Unit,
    onConfigScanned: (ScannedReceiverConfig) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val hostActivity = remember(context) { context.findActivity() }
    val fallbackLifecycle = LocalLifecycleOwner.current
    val lifecycleOwner = hostActivity ?: fallbackLifecycle
    val coroutineScope = rememberCoroutineScope()

    var hasScanned by remember { mutableStateOf(false) }
    var torchEnabled by remember { mutableStateOf(false) }
    var cameraControl: CameraControl? by remember { mutableStateOf(null) }
    var activePreviewView by remember { mutableStateOf<PreviewView?>(null) }
    var cameraErrorMessage by remember { mutableStateOf<String?>(null) }

    // Tap-to-focus visual ring state
    var focusRingPos by remember { mutableStateOf<Offset?>(null) }
    val focusRingScale = remember { Animatable(1.4f) }
    val focusRingAlpha = remember { Animatable(0f) }

    val cameraExecutor = remember { Executors.newSingleThreadExecutor() }

    val infiniteTransition = rememberInfiniteTransition(label = "laser_transition")
    val laserProgress by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "laser_progress"
    )

    DisposableEffect(Unit) {
        onDispose {
            try {
                cameraExecutor.shutdown()
            } catch (e: Exception) {
                Log.w("QrScanner", "Executor shutdown error", e)
            }
        }
    }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .background(Color.Black)
                .statusBarsPadding()
                .navigationBarsPadding()
                .testTag("qr_scanner_dialog")
                .pointerInput(Unit) {
                    detectTapGestures { offset ->
                        focusRingPos = offset
                        activePreviewView?.let { pv ->
                            try {
                                val factory = pv.meteringPointFactory
                                val point = factory.createPoint(offset.x, offset.y)
                                val action = FocusMeteringAction.Builder(
                                    point,
                                    FocusMeteringAction.FLAG_AF or FocusMeteringAction.FLAG_AE
                                ).setAutoCancelDuration(3, TimeUnit.SECONDS).build()
                                cameraControl?.startFocusAndMetering(action)
                            } catch (e: Exception) {
                                Log.w("QrScanner", "Focus metering not supported", e)
                            }
                        }
                        coroutineScope.launch {
                            focusRingScale.snapTo(1.4f)
                            focusRingAlpha.snapTo(1f)
                            launch { focusRingScale.animateTo(1.0f, tween(250)) }
                            launch {
                                delay(700)
                                focusRingAlpha.animateTo(0f, tween(350))
                                focusRingPos = null
                            }
                        }
                    }
                }
        ) {
            if (cameraErrorMessage != null) {
                // Fallback UI when device lacks camera or fails to bind
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = null,
                        tint = NeonCyan,
                        modifier = Modifier.size(56.dp)
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "Camera Unavailable",
                        color = TextPrimary,
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = cameraErrorMessage ?: "Unable to access camera preview.",
                        color = TextSecondary,
                        fontSize = 14.sp,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(24.dp))
                    Button(
                        onClick = onDismiss,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = NeonCyan,
                            contentColor = Color(0xFF003038)
                        )
                    ) {
                        Text("Enter IP Manually", fontWeight = FontWeight.Bold)
                    }
                }
            } else {
                // CameraX Live Preview View
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = { ctx ->
                        val previewView = PreviewView(ctx).apply {
                            scaleType = PreviewView.ScaleType.FILL_CENTER
                        }
                        activePreviewView = previewView

                        val hasCameraPermission = ContextCompat.checkSelfPermission(
                            ctx,
                            android.Manifest.permission.CAMERA
                        ) == PackageManager.PERMISSION_GRANTED

                        if (!hasCameraPermission) {
                            cameraErrorMessage = "Camera permission is not granted. Please allow camera access in Settings."
                            return@AndroidView previewView
                        }

                        val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                        cameraProviderFuture.addListener({
                            try {
                                val cameraProvider = cameraProviderFuture.get()

                                val cameraSelector = when {
                                    cameraProvider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA) ->
                                        CameraSelector.DEFAULT_BACK_CAMERA
                                    cameraProvider.hasCamera(CameraSelector.DEFAULT_FRONT_CAMERA) ->
                                        CameraSelector.DEFAULT_FRONT_CAMERA
                                    else -> null
                                }

                                if (cameraSelector == null) {
                                    cameraErrorMessage = "No camera hardware detected on this device."
                                    return@addListener
                                }

                                val resolutionSelector = ResolutionSelector.Builder()
                                    .setResolutionStrategy(
                                        ResolutionStrategy(
                                            Size(960, 720),
                                            ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER
                                        )
                                    )
                                    .build()

                                val preview = Preview.Builder()
                                    .setResolutionSelector(resolutionSelector)
                                    .build()
                                    .also {
                                        it.setSurfaceProvider(previewView.surfaceProvider)
                                    }

                                val imageAnalysis = ImageAnalysis.Builder()
                                    .setResolutionSelector(resolutionSelector)
                                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                                    .build()

                                imageAnalysis.setAnalyzer(cameraExecutor) { imageProxy ->
                                    try {
                                        if (hasScanned) return@setAnalyzer

                                        val rawText = decodeQrCode(imageProxy)
                                        if (rawText != null) {
                                            val parsed = parsePhoneMicQrPayload(rawText)
                                            if (parsed != null && !hasScanned) {
                                                hasScanned = true
                                                ContextCompat.getMainExecutor(ctx).execute {
                                                    onConfigScanned(parsed)
                                                    onDismiss()
                                                }
                                            }
                                        }
                                    } catch (t: Throwable) {
                                        Log.e("QrScanner", "Frame decode error", t)
                                    } finally {
                                        imageProxy.close()
                                    }
                                }

                                cameraProvider.unbindAll()
                                val camera = cameraProvider.bindToLifecycle(
                                    lifecycleOwner,
                                    cameraSelector,
                                    preview,
                                    imageAnalysis
                                )
                                val ctrl = camera.cameraControl
                                cameraControl = ctrl

                                // Initial center auto-focus
                                previewView.post {
                                    try {
                                        val w = previewView.width.toFloat()
                                        val h = previewView.height.toFloat()
                                        if (w > 0 && h > 0) {
                                            val center = previewView.meteringPointFactory.createPoint(w / 2f, h / 2f)
                                            val initAction = FocusMeteringAction.Builder(
                                                center,
                                                FocusMeteringAction.FLAG_AF or FocusMeteringAction.FLAG_AE
                                            ).setAutoCancelDuration(3, TimeUnit.SECONDS).build()
                                            ctrl.startFocusAndMetering(initAction)
                                        }
                                    } catch (e: Exception) {
                                        Log.w("QrScanner", "Initial focus error", e)
                                    }
                                }
                            } catch (e: Exception) {
                                Log.e("QrScanner", "Camera bind failed", e)
                                cameraErrorMessage = "Unable to start camera preview. Please check camera permissions or enter IP manually."
                            }
                        }, ContextCompat.getMainExecutor(ctx))

                        previewView
                    }
                )
            }

            // Tap-to-focus animated ring indicator
            focusRingPos?.let { pos ->
                Box(
                    modifier = Modifier
                        .offset {
                            IntOffset(
                                (pos.x - 30.dp.toPx()).roundToInt(),
                                (pos.y - 30.dp.toPx()).roundToInt()
                            )
                        }
                        .size(60.dp)
                        .graphicsLayer {
                            scaleX = focusRingScale.value
                            scaleY = focusRingScale.value
                            alpha = focusRingAlpha.value
                        }
                        .border(2.dp, NeonCyan, CircleShape)
                )
            }

            // Scanning Viewfinder Overlay
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                // Top Header Row
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier
                            .background(StudioDarkBg.copy(alpha = 0.7f), CircleShape)
                            .size(44.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close scanner",
                            tint = Color.White
                        )
                    }

                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.QrCodeScanner,
                            contentDescription = null,
                            tint = NeonCyan,
                            modifier = Modifier.size(20.dp)
                        )
                        Text(
                            text = stringResource(R.string.qr_scanner_title),
                            color = TextPrimary,
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp
                        )
                    }

                    IconButton(
                        onClick = {
                            try {
                                val next = !torchEnabled
                                torchEnabled = next
                                cameraControl?.enableTorch(next)
                            } catch (e: Exception) {
                                Log.w("QrScanner", "Flashlight toggle error", e)
                            }
                        },
                        modifier = Modifier
                            .background(
                                if (torchEnabled) NeonCyan.copy(alpha = 0.3f) else StudioDarkBg.copy(alpha = 0.7f),
                                CircleShape
                            )
                            .size(44.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.FlashOn,
                            contentDescription = "Toggle flashlight",
                            tint = if (torchEnabled) NeonCyan else Color.White
                        )
                    }
                }

                // Center Viewfinder Target with animated laser
                if (cameraErrorMessage == null) {
                    Box(
                        modifier = Modifier
                            .size(260.dp)
                            .border(2.dp, NeonCyan.copy(alpha = 0.8f), RoundedCornerShape(16.dp))
                    ) {
                        Canvas(modifier = Modifier.fillMaxSize()) {
                            val y = size.height * laserProgress
                            drawLine(
                                color = NeonCyan,
                                start = Offset(0f, y),
                                end = Offset(size.width, y),
                                strokeWidth = 3.dp.toPx()
                            )
                        }
                    }
                }

                // Bottom Hint Text
                Box(
                    modifier = Modifier
                        .background(StudioDarkBg.copy(alpha = 0.85f), RoundedCornerShape(12.dp))
                        .padding(horizontal = 16.dp, vertical = 10.dp)
                ) {
                    Text(
                        text = stringResource(R.string.qr_scanner_hint),
                        color = TextSecondary,
                        fontSize = 13.sp,
                        textAlign = TextAlign.Center
                    )
                }
            }
        }
    }
}

private fun decodeQrCode(image: ImageProxy): String? {
    return try {
        if (image.format != ImageFormat.YUV_420_888 &&
            image.format != ImageFormat.YUV_422_888 &&
            image.format != ImageFormat.YUV_444_888
        ) {
            return null
        }

        val planes = image.planes
        if (planes.isNullOrEmpty()) return null
        val yPlane = planes[0] ?: return null
        val yBuffer = yPlane.buffer ?: return null
        val rowStride = yPlane.rowStride
        val width = image.width
        val height = image.height

        if (width <= 0 || height <= 0 || rowStride < width) return null

        val bufferRemaining = yBuffer.remaining()
        val totalSize = rowStride * height
        val bytes = ByteArray(totalSize)
        val toCopy = minOf(bufferRemaining, totalSize)
        val originalPos = yBuffer.position()
        yBuffer.get(bytes, 0, toCopy)
        yBuffer.position(originalPos)

        val hints = EnumMap<DecodeHintType, Any>(DecodeHintType::class.java).apply {
            put(DecodeHintType.POSSIBLE_FORMATS, listOf(BarcodeFormat.QR_CODE))
            put(DecodeHintType.CHARACTER_SET, "UTF-8")
            put(DecodeHintType.TRY_HARDER, java.lang.Boolean.TRUE)
        }

        // Standard orientation
        val source = PlanarYUVLuminanceSource(
            bytes,
            rowStride,
            height,
            0,
            0,
            width,
            height,
            false
        )

        try {
            val bitmap = BinaryBitmap(HybridBinarizer(source))
            val res = MultiFormatReader().decode(bitmap, hints)?.text
            if (!res.isNullOrBlank()) return res
        } catch (_: Exception) {}

        // Rotated orientation fallback (handles 90-degree sensor orientation mismatch)
        try {
            val rotated = source.rotateCounterClockwise()
            val bitmap = BinaryBitmap(HybridBinarizer(rotated))
            val res = MultiFormatReader().decode(bitmap, hints)?.text
            if (!res.isNullOrBlank()) return res
        } catch (_: Exception) {}

        null
    } catch (_: Exception) {
        null
    }
}

fun parsePhoneMicQrPayload(raw: String): ScannedReceiverConfig? {
    val trimmed = raw.trim()
    try {
        if (trimmed.startsWith("phonemic://", ignoreCase = true)) {
            val uri = URI(trimmed)
            val host = uri.host ?: return null
            if (!isValidIpv4(host)) return null
            val port = if (uri.port > 0) uri.port else 5001
            if (port !in 1..65535) return null
            val query = uri.query ?: ""
            var transport = "UDP"
            for (param in query.split("&")) {
                val parts = param.split("=")
                if (parts.size == 2) {
                    if (parts[0].equals("t", ignoreCase = true) || parts[0].equals("transport", ignoreCase = true)) {
                        transport = if (parts[1].equals("TCP", ignoreCase = true)) "TCP" else "UDP"
                    }
                }
            }
            return ScannedReceiverConfig(host, port, transport)
        }

        // Alternative formats: 192.168.1.50:5001
        if (trimmed.contains(":")) {
            val parts = trimmed.split(":")
            if (parts.size == 2 && isValidIpv4(parts[0])) {
                val port = parts[1].toIntOrNull()
                if (port != null && port in 1..65535) {
                    return ScannedReceiverConfig(parts[0], port, "UDP")
                }
            }
        }

        // Just IP: 192.168.1.50
        if (isValidIpv4(trimmed)) {
            return ScannedReceiverConfig(trimmed, 5001, "UDP")
        }
    } catch (e: Exception) {
        Log.w("QrScanner", "Invalid QR payload: $raw", e)
    }
    return null
}

private fun isValidIpv4(ip: String): Boolean {
    val parts = ip.split(".")
    if (parts.size != 4) return false
    for (p in parts) {
        val num = p.toIntOrNull() ?: return false
        if (num !in 0..255) return false
    }
    return true
}
