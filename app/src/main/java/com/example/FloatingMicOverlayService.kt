package com.example

import android.annotation.SuppressLint
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import kotlin.math.abs

class FloatingMicOverlayService : Service() {

    private var windowManager: WindowManager? = null
    private var overlayView: View? = null
    private var params: WindowManager.LayoutParams? = null

    private val serviceScope = CoroutineScope(Dispatchers.Main + Job())

    companion object {
        const val ACTION_START_OVERLAY = "com.example.phonemic.START_OVERLAY"
        const val ACTION_STOP_OVERLAY = "com.example.phonemic.STOP_OVERLAY"
        @Volatile var isOverlayRunning = false
            private set
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP_OVERLAY) {
            stopSelf()
            return START_NOT_STICKY
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            stopSelf()
            return START_NOT_STICKY
        }

        if (overlayView == null) {
            setupOverlay()
        }

        return START_STICKY
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun setupOverlay() {
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val wm = windowManager ?: return

        val layoutType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

        val density = resources.displayMetrics.density
        val dp = { value: Float -> (value * density).toInt() }

        val wmParams = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = dp(20f)
            y = dp(120f)
        }
        params = wmParams

        // Build floating container: Horizontal pill
        val container = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(10f), dp(6f), dp(10f), dp(6f))
            background = GradientDrawable().apply {
                setColor(0xEE121820.toInt())
                cornerRadius = dp(24f).toFloat()
                setStroke(dp(1.5f), 0xFF00F0FF.toInt())
            }
            elevation = dp(8f).toFloat()
        }

        // Status Indicator Dot
        val dot = View(this).apply {
            this.layoutParams = LinearLayout.LayoutParams(dp(12f), dp(12f)).apply {
                marginEnd = dp(8f)
            }
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(0xFF00E676.toInt()) // Green initially
            }
        }
        container.addView(dot)

        // Mic Label
        val label = TextView(this).apply {
            text = "MIC"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            this.layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                marginEnd = dp(8f)
            }
        }
        container.addView(label)

        // Close button (X)
        val closeBtn = ImageView(this).apply {
            setImageResource(android.R.drawable.ic_menu_close_clear_cancel)
            this.layoutParams = LinearLayout.LayoutParams(dp(16f), dp(16f))
            setColorFilter(0xFF8B949E.toInt())
            setOnClickListener {
                stopSelf()
            }
        }
        container.addView(closeBtn)

        // Touch listener for dragging & tapping
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f
        var isClick = false

        container.setOnTouchListener { _, event ->
            val p = params ?: return@setOnTouchListener false
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialX = p.x
                    initialY = p.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    isClick = true
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = (event.rawX - initialTouchX).toInt()
                    val dy = (event.rawY - initialTouchY).toInt()
                    if (abs(dx) > 10 || abs(dy) > 10) {
                        isClick = false
                    }
                    p.x = initialX + dx
                    p.y = initialY + dy
                    wm.updateViewLayout(container, p)
                    true
                }
                MotionEvent.ACTION_UP -> {
                    if (isClick) {
                        // Toggle Mute / Pause!
                        val toggleIntent = Intent(this, PhoneMicService::class.java).apply {
                            action = PhoneMicService.ACTION_TOGGLE_PAUSE
                        }
                        startService(toggleIntent)
                    }
                    true
                }
                else -> false
            }
        }

        try {
            wm.addView(container, wmParams)
            overlayView = container
            isOverlayRunning = true
        } catch (_: Exception) {
            stopSelf()
            return
        }

        // Observe PhoneMicService state to update dot color and label
        serviceScope.launch {
            PhoneMicService.serviceSnapshot.collectLatest { state ->
                val dotBg = dot.background as? GradientDrawable ?: return@collectLatest
                val containerBg = container.background as? GradientDrawable ?: return@collectLatest

                if (state.running) {
                    if (state.paused) {
                        dotBg.setColor(0xFFFF5252.toInt()) // Red: Muted
                        label.text = "MUTED"
                        label.setTextColor(0xFFFF5252.toInt())
                        containerBg.setStroke(dp(1.5f), 0xFFFF5252.toInt())
                    } else {
                        dotBg.setColor(0xFF00E676.toInt()) // Green: Live
                        label.text = "LIVE"
                        label.setTextColor(0xFF00E676.toInt())
                        containerBg.setStroke(dp(1.5f), 0xFF00F0FF.toInt())
                    }
                } else {
                    dotBg.setColor(0xFF8B949E.toInt()) // Gray: Off
                    label.text = "OFF"
                    label.setTextColor(0xFF8B949E.toInt())
                    containerBg.setStroke(dp(1.5f), 0xFF8B949E.toInt())
                }
            }
        }
    }

    override fun onDestroy() {
        isOverlayRunning = false
        serviceScope.cancel()
        overlayView?.let { view ->
            try {
                windowManager?.removeView(view)
            } catch (_: Exception) {}
        }
        overlayView = null
        super.onDestroy()
    }
}
