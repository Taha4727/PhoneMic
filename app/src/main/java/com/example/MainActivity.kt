package com.example

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.example.ui.screens.PhoneMicScreen
import com.example.ui.theme.PhoneMicTheme

class MainActivity : ComponentActivity() {

    private val viewModel: PhoneMicViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

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
    }

    override fun onDestroy() {
        super.onDestroy()
        viewModel.unbindService(this)
    }
}
