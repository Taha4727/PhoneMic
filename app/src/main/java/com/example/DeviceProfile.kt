package com.example

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings

/**
 * Hardware and platform profiler with specific support for:
 * 1. Samsung Galaxy J5 (Android 7.1.1 - API 25)
 * 2. Samsung Galaxy A10s (Android 11 - API 30)
 * 3. POCO X6 Pro 5G (Android 16 - API 36 / Xiaomi HyperOS)
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

    val isSamsung: Boolean by lazy {
        Build.MANUFACTURER.equals("SAMSUNG", ignoreCase = true) ||
                Build.BRAND.equals("SAMSUNG", ignoreCase = true)
    }

    val isGalaxyJ5: Boolean by lazy {
        isSamsung && (Build.MODEL.contains("J5", ignoreCase = true) || Build.PRODUCT.contains("j5", ignoreCase = true))
    }

    val isGalaxyA10s: Boolean by lazy {
        isSamsung && (Build.MODEL.contains("A107", ignoreCase = true) ||
                Build.MODEL.contains("A10S", ignoreCase = true) ||
                Build.PRODUCT.contains("a10s", ignoreCase = true))
    }

    val isAndroid16OrNewer: Boolean by lazy {
        Build.VERSION.SDK_INT >= 36 || (Build.VERSION.SDK_INT == 35 && Build.VERSION.CODENAME.equals("Baklava", ignoreCase = true))
    }

    val isAndroid11OrNewer: Boolean by lazy {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.R
    }

    val isAndroid7: Boolean by lazy {
        Build.VERSION.SDK_INT <= Build.VERSION_CODES.N_MR1
    }

    val deviceDisplayName: String by lazy {
        when {
            isPocoX6Pro -> "POCO X6 Pro 5G"
            isGalaxyJ5 -> "Samsung Galaxy J5"
            isGalaxyA10s -> "Samsung Galaxy A10s"
            isSamsung -> "Samsung ${Build.MODEL}"
            Build.BRAND.equals("POCO", ignoreCase = true) -> "POCO ${Build.MODEL}"
            Build.MANUFACTURER.equals("Xiaomi", ignoreCase = true) -> "Xiaomi ${Build.MODEL}"
            else -> "${Build.MANUFACTURER.replaceFirstChar { it.uppercase() }} ${Build.MODEL}"
        }
    }

    val chipsetDisplayName: String by lazy {
        when {
            isPocoX6Pro -> "MediaTek Dimensity 8300-Ultra (Wi-Fi 6 / 5G)"
            isGalaxyA10s -> "MediaTek Helio P22 (Octa-Core)"
            isGalaxyJ5 -> "Qualcomm Snapdragon 410 / Exynos 7570"
            Build.HARDWARE.contains("mt", ignoreCase = true) -> "MediaTek ${Build.HARDWARE.uppercase()}"
            Build.HARDWARE.contains("qcom", ignoreCase = true) -> "Qualcomm Snapdragon"
            Build.HARDWARE.contains("exynos", ignoreCase = true) -> "Samsung Exynos"
            else -> "Audio Engine (${Build.HARDWARE})"
        }
    }

    val osDisplayName: String by lazy {
        val base = if (isAndroid16OrNewer) {
            "Android 16 (API ${Build.VERSION.SDK_INT})"
        } else {
            "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})"
        }

        when {
            isXiaomiOrPoco -> "$base • Xiaomi HyperOS"
            isSamsung && Build.VERSION.SDK_INT >= Build.VERSION_CODES.P -> "$base • Samsung One UI"
            isSamsung -> "$base • Samsung Experience"
            else -> base
        }
    }

    /**
     * Opens vendor-specific battery and background management settings.
     */
    fun openDeviceOptimizationSettings(context: Context): Boolean {
        if (isXiaomiOrPoco) {
            return openHyperOsSettings(context)
        } else if (isSamsung) {
            return openSamsungBatterySettings(context)
        }
        return openAppDetailsSettings(context)
    }

    /**
     * Opens Samsung Device Care / App power management settings.
     */
    fun openSamsungBatterySettings(context: Context): Boolean {
        // Try Samsung Device Care (com.samsung.android.lool)
        val samsungIntent = Intent().apply {
            setClassName("com.samsung.android.lool", "com.samsung.android.sm.battery.ui.BatteryActivity")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            context.startActivity(samsungIntent)
            return true
        } catch (_: Exception) {}

        // Fallback to Samsung Smart Manager
        val smIntent = Intent().apply {
            setClassName("com.samsung.android.sm", "com.samsung.android.sm.ui.battery.BatteryActivity")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            context.startActivity(smIntent)
            return true
        } catch (_: Exception) {}

        return openAppDetailsSettings(context)
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

        return openAppDetailsSettings(context)
    }

    fun openAppDetailsSettings(context: Context): Boolean {
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
