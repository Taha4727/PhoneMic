package com.example

import android.content.Intent
import android.graphics.drawable.Icon
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import androidx.annotation.RequiresApi

@RequiresApi(Build.VERSION_CODES.N)
class PhoneMicTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        updateTileState()
    }

    override fun onClick() {
        super.onClick()
        val snapshot = PhoneMicService.serviceSnapshot.value
        if (snapshot.running) {
            val intent = Intent(this, PhoneMicService::class.java).apply {
                action = PhoneMicService.ACTION_TOGGLE_PAUSE
            }
            startService(intent)
        } else {
            val appIntent = Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                    val pendingIntent = android.app.PendingIntent.getActivity(
                        this,
                        0,
                        appIntent,
                        android.app.PendingIntent.FLAG_IMMUTABLE or android.app.PendingIntent.FLAG_UPDATE_CURRENT
                    )
                    startActivityAndCollapse(pendingIntent)
                } else {
                    @Suppress("DEPRECATION")
                    startActivityAndCollapse(appIntent)
                }
            } catch (_: Exception) {
                startActivity(appIntent)
            }
        }
        updateTileState()
    }

    private fun updateTileState() {
        val tile = qsTile ?: return
        val snapshot = PhoneMicService.serviceSnapshot.value
        if (snapshot.running) {
            if (snapshot.paused) {
                tile.state = Tile.STATE_INACTIVE
                tile.label = getString(R.string.tile_muted)
                tile.icon = Icon.createWithResource(this, android.R.drawable.ic_lock_silent_mode)
            } else {
                tile.state = Tile.STATE_ACTIVE
                tile.label = getString(R.string.tile_streaming)
                tile.icon = Icon.createWithResource(this, android.R.drawable.ic_btn_speak_now)
            }
        } else {
            tile.state = Tile.STATE_INACTIVE
            tile.label = getString(R.string.tile_off)
            tile.icon = Icon.createWithResource(this, android.R.drawable.ic_btn_speak_now)
        }
        tile.updateTile()
    }
}
