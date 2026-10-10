package com.example

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings

/**
 * Hardware and platform profiler with specific support for Android 16 (API 36)
 * and the POCO X6 Pro 5G (Xiaomi HyperOS / MediaTek Dimensity 8300 Ultra).
 */
object DeviceProfile {

    val isPocoX6Pro: Boolean by lazy {
        val model = Build.MODEL.uppercase()
        val product = Build.PRODUCT.uppercase()
        val device = Build.DEVICE.uppercase()
        val brand = Build.BRAND.uppercase()

        (brand.contains("POCO") || brand.contains("XIAOMI")) &&
                (model.contains("2311DRK48") || model.contains("POCO X6 PRO") ||
                 product.contains("DUCHAMP") || device.contains("DUCHAMP"))
    }

    val isXiaomiOrPoco: Boolean by lazy {
        val brand = Build.BRAND.uppercase()
        val manufacturer = Build.MANUFACTURER.uppercase()
        brand.contains("POCO") || brand.contains("XIAOMI") || brand.contains("REDMI") ||
                manufacturer.contains("XIAOMI") || manufacturer.contains("POCO")
    }

    val isAndroid16OrNewer: Boolean by lazy {
        Build.VERSION.SDK_INT >= 36 || (Build.VERSION.SDK_INT == 35 && Build.VERSION.CODENAME.equals("Baklava", ignoreCase = true))
    }

    val deviceDisplayName: String by lazy {
        when {
            isPocoX6Pro -> "POCO X6 Pro 5G"
            Build.BRAND.equals("POCO", ignoreCase = true) -> "POCO ${Build.MODEL}"
            Build.MANUFACTURER.equals("Xiaomi", ignoreCase = true) -> "Xiaomi ${Build.MODEL}"
            else -> "${Build.MANUFACTURER.replaceFirstChar { it.uppercase() }} ${Build.MODEL}"
        }
    }

    val chipsetDisplayName: String by lazy {
        when {
            isPocoX6Pro -> "MediaTek Dimensity 8300-Ultra (Wi-Fi 6 / 5G)"
            Build.HARDWARE.contains("mt", ignoreCase = true) -> "MediaTek ${Build.HARDWARE.uppercase()}"
            Build.HARDWARE.contains("qcom", ignoreCase = true) -> "Qualcomm Snapdragon"
            else -> "Audio DSP (${Build.HARDWARE})"
        }
    }

    val osDisplayName: String by lazy {
        val base = if (isAndroid16OrNewer) {
            "Android 16 (API ${Build.VERSION.SDK_INT})"
        } else {
            "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})"
        }

        if (isXiaomiOrPoco) {
            "$base • Xiaomi HyperOS"
        } else {
            base
        }
    }

    /**
     * Opens the app info / battery settings for Xiaomi HyperOS / POCO to disable background killing.
     */
    fun openHyperOsSettings(context: Context): Boolean {
        // 1. Try Xiaomi Autostart intent
        val autostartIntent = Intent().apply {
            setClassName("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            context.startActivity(autostartIntent)
            return true
        } catch (_: Exception) {}

        // 2. Try Xiaomi Powerkeeper hidden apps
        val powerkeeperIntent = Intent().apply {
            setClassName("com.miui.powerkeeper", "com.miui.powerkeeper.ui.HiddenAppsConfigActivity")
            putExtra("package_name", context.packageName)
            putExtra("package_label", "PhoneMic")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            context.startActivity(powerkeeperIntent)
            return true
        } catch (_: Exception) {}

        // 3. Fallback to standard Application Details Settings (works everywhere)
        return try {
            val appDetailsIntent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.parse("package:" + context.packageName)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(appDetailsIntent)
            true
        } catch (_: Exception) {
            false
        }
    }
}
