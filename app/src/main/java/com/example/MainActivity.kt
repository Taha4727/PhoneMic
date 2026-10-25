package com.example

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.example.ui.screens.PhoneMicScreen
import com.example.ui.theme.PhoneMicTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val viewModel: PhoneMicViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Prevent screen from turning off immediately on launch
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        // Sync keepScreenAwake preference with Activity window flag
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    if (state.keepScreenAwake) {
                        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    } else {
                        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    }
                }
            }
        }

        setContent {
            PhoneMicTheme {
                PhoneMicScreen(viewModel = viewModel)
            }
        }
    }

    override fun onStart() {
        super.onStart()
        viewModel.bindService(this)
    }

    override fun onResume() {
        super.onResume()
        viewModel.checkBatteryOptimization()
        viewModel.checkPermissions(this)
    }

    override fun onDestroy() {
        super.onDestroy()
        viewModel.unbindService(this)
    }
}
