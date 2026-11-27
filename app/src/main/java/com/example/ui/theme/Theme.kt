package com.example.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

val LocalPhoneMicColors = staticCompositionLocalOf {
    resolvePhoneMicColors(
        isDark = true,
        oledBlack = false,
        palette = AppPaletteStyle.TONAL_SPOT
    )
}

object PhoneMicTheme {
    val colors: PhoneMicColors
        @Composable
        @ReadOnlyComposable
        get() = LocalPhoneMicColors.current
}

@Composable
fun PhoneMicTheme(
    isDarkMode: Boolean = true,
    oledBlackEnabled: Boolean = false,
    paletteStyle: AppPaletteStyle = AppPaletteStyle.TONAL_SPOT,
    customThemeColorArgb: Long = 0xFF0EA5E9L,
    content: @Composable () -> Unit
) {
    val colors = remember(isDarkMode, oledBlackEnabled, paletteStyle, customThemeColorArgb) {
        resolvePhoneMicColors(
            isDark = isDarkMode,
            oledBlack = oledBlackEnabled,
            palette = paletteStyle,
            customColorArgb = customThemeColorArgb
        )
    }

    val m3Scheme = remember(colors) {
        if (colors.isDark) {
            darkColorScheme(
                primary = colors.accent,
                onPrimary = colors.onAccent,
                primaryContainer = colors.accentSoftBg,
                onPrimaryContainer = colors.accent,
                secondary = colors.secondaryAccent,
                onSecondary = colors.onAccent,
                secondaryContainer = colors.nestedSurface,
                onSecondaryContainer = colors.textPrimary,
                background = colors.background,
                onBackground = colors.textPrimary,
                surface = colors.cardSurface,
                onSurface = colors.textPrimary,
                surfaceContainer = colors.cardSurface,
                surfaceContainerHigh = colors.nestedSurface,
                surfaceContainerLow = colors.bottomBarSurface,
                surfaceVariant = colors.nestedSurface,
                onSurfaceVariant = colors.textSecondary,
                outline = colors.border,
                outlineVariant = colors.border,
                error = colors.statusError
            )
        } else {
            lightColorScheme(
                primary = colors.accent,
                onPrimary = colors.onAccent,
                primaryContainer = colors.accentSoftBg,
                onPrimaryContainer = colors.accent,
                secondary = colors.secondaryAccent,
                onSecondary = colors.onAccent,
                secondaryContainer = colors.nestedSurface,
                onSecondaryContainer = colors.textPrimary,
                background = colors.background,
                onBackground = colors.textPrimary,
                surface = colors.cardSurface,
                onSurface = colors.textPrimary,
                surfaceContainer = colors.cardSurface,
                surfaceContainerHigh = colors.nestedSurface,
                surfaceContainerLow = colors.bottomBarSurface,
                surfaceVariant = colors.nestedSurface,
                onSurfaceVariant = colors.textSecondary,
                outline = colors.border,
                outlineVariant = colors.border,
                error = colors.statusError
            )
        }
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        LaunchedEffect(view, isDarkMode) {
            val window = (view.context as? Activity)?.window
            if (window != null) {
                WindowCompat.getInsetsController(window, view).apply {
                    isAppearanceLightStatusBars = !isDarkMode
                    isAppearanceLightNavigationBars = !isDarkMode
                }
            }
        }
    }

    CompositionLocalProvider(LocalPhoneMicColors provides colors) {
        MaterialTheme(
            colorScheme = m3Scheme,
            typography = Typography,
            content = content
        )
    }
}
