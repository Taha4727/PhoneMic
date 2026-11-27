package com.example.ui.theme

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.luminance

enum class AppPaletteStyle(
    val id: String,
    val label: String,
    val description: String,
    val previewColor: Color
) {
    TONAL_SPOT(
        id = "TONAL_SPOT",
        label = "TonalSpot",
        description = "Balanced studio tint with crisp contrast",
        previewColor = Color(0xFF0EA5E9)
    ),
    NEUTRAL(
        id = "NEUTRAL",
        label = "Neutral",
        description = "Subtle slate surfaces with restrained color",
        previewColor = Color(0xFF64748B)
    ),
    VIBRANT(
        id = "VIBRANT",
        label = "Vibrant",
        description = "High-energy accent saturation on surfaces",
        previewColor = Color(0xFF10B981)
    ),
    MONOCHROME(
        id = "MONOCHROME",
        label = "Monochrome",
        description = "Pure grayscale chrome with minimal distraction",
        previewColor = Color(0xFFD4D4D8)
    ),
    STUDIO_CYAN(
        id = "STUDIO_CYAN",
        label = "Studio Cyan",
        description = "Classic electric broadcast cyan tone",
        previewColor = Color(0xFF00D8F5)
    ),
    EXPRESSIVE(
        id = "EXPRESSIVE",
        label = "Expressive",
        description = "Bold warm coral & high-character accents",
        previewColor = Color(0xFFF43F5E)
    ),
    CUSTOM(
        id = "CUSTOM",
        label = "Custom Color",
        description = "Pick any custom hue, saturation, or hex accent color",
        previewColor = Color(0xFF0EA5E9)
    );

    companion object {
        fun fromId(id: String?): AppPaletteStyle =
            entries.firstOrNull { it.id.equals(id, ignoreCase = true) } ?: TONAL_SPOT
    }
}

@Immutable
data class PhoneMicColors(
    val isDark: Boolean,
    val isOled: Boolean,
    val background: Color,
    val cardSurface: Color,
    val nestedSurface: Color,
    val bottomBarSurface: Color,
    val border: Color,
    val borderActive: Color,
    val textPrimary: Color,
    val textSecondary: Color,
    val textMuted: Color,
    val accent: Color,
    val onAccent: Color,
    val accentSoftBg: Color,
    val secondaryAccent: Color,
    val statusConnected: Color,
    val statusWarning: Color,
    val statusError: Color,
    val visualizerBg: Color
)

// Backwards-compatible semantic defaults for non-theme helpers if needed
val NeonCyan = Color(0xFF00E5FF)
val ElectricBlue = Color(0xFF2979FF)
val NeonTeal = Color(0xFF00B4D8)
val StudioDarkBg = Color(0xFF121212)
val StudioSurface = Color(0xFF1B1B1E)
val StudioCard = Color(0xFF1B1B1E)
val StudioCardSelected = Color(0xFF232830)
val StudioBorder = Color(0xFF2E3138)
val StreamActiveGreen = Color(0xFF16C47F)
val StreamWarningAmber = Color(0xFFF59E0B)
val StreamErrorRed = Color(0xFFEF4444)
val TextPrimary = Color(0xFFF3F4F6)
val TextSecondary = Color(0xFFA1A7B3)
val TextMuted = Color(0xFF6F7682)

fun resolvePhoneMicColors(
    isDark: Boolean,
    oledBlack: Boolean,
    palette: AppPaletteStyle,
    customColorArgb: Long = 0xFF0EA5E9L
): PhoneMicColors {
    val isOledActive = isDark && oledBlack

    val (paletteAccentDark, paletteOnDark, paletteSoftDark, paletteSecondaryDark) = when (palette) {
        AppPaletteStyle.TONAL_SPOT, AppPaletteStyle.CUSTOM -> QuadColor(Color(0xFF38BDF8), Color(0xFF062334), Color(0xFF122836), Color(0xFF818CF8))
        AppPaletteStyle.NEUTRAL -> QuadColor(Color(0xFF94A3B8), Color(0xFF0F172A), Color(0xFF1E242D), Color(0xFFCBD5E1))
        AppPaletteStyle.VIBRANT -> QuadColor(Color(0xFF22D38B), Color(0xFF022C1B), Color(0xFF0D2B20), Color(0xFF38BDF8))
        AppPaletteStyle.MONOCHROME -> QuadColor(Color(0xFFF4F4F5), Color(0xFF09090B), Color(0xFF242429), Color(0xFFA1A1AA))
        AppPaletteStyle.STUDIO_CYAN -> QuadColor(Color(0xFF00E5FF), Color(0xFF002830), Color(0xFF0D2930), Color(0xFF2979FF))
        AppPaletteStyle.EXPRESSIVE -> QuadColor(Color(0xFFFF6B81), Color(0xFF32060E), Color(0xFF32161E), Color(0xFFFBBF24))
    }

    val (paletteAccentLight, paletteOnLight, paletteSoftLight, paletteSecondaryLight) = when (palette) {
        AppPaletteStyle.TONAL_SPOT, AppPaletteStyle.CUSTOM -> QuadColor(Color(0xFF0284C7), Color(0xFFFFFFFF), Color(0xFFE0F2FE), Color(0xFF4F46E5))
        AppPaletteStyle.NEUTRAL -> QuadColor(Color(0xFF334155), Color(0xFFFFFFFF), Color(0xFFE2E8F0), Color(0xFF475569))
        AppPaletteStyle.VIBRANT -> QuadColor(Color(0xFF059669), Color(0xFFFFFFFF), Color(0xFFD1FAE5), Color(0xFF0284C7))
        AppPaletteStyle.MONOCHROME -> QuadColor(Color(0xFF18181B), Color(0xFFFFFFFF), Color(0xFFE4E4E7), Color(0xFF52525B))
        AppPaletteStyle.STUDIO_CYAN -> QuadColor(Color(0xFF008BA3), Color(0xFFFFFFFF), Color(0xFFDDF7FA), Color(0xFF1D4ED8))
        AppPaletteStyle.EXPRESSIVE -> QuadColor(Color(0xFFE11D48), Color(0xFFFFFFFF), Color(0xFFFFE4E6), Color(0xFFD97706))
    }

    val overrideSeedArgb: Long? = if (palette == AppPaletteStyle.CUSTOM) {
        customColorArgb or 0xFF000000L
    } else {
        null
    }

    if (!isDark) {
        val bgLight = when (palette) {
            AppPaletteStyle.TONAL_SPOT, AppPaletteStyle.CUSTOM -> Color(0xFFF3F6FA)
            AppPaletteStyle.NEUTRAL -> Color(0xFFF5F5F6)
            AppPaletteStyle.VIBRANT -> Color(0xFFF2F7F5)
            AppPaletteStyle.MONOCHROME -> Color(0xFFF4F4F5)
            AppPaletteStyle.STUDIO_CYAN -> Color(0xFFF2F7F9)
            AppPaletteStyle.EXPRESSIVE -> Color(0xFFF9F4F5)
        }
        val cardSurface = Color(0xFFFFFFFF)

        val (accent, onAccent, softBg) = if (overrideSeedArgb != null) {
            val raw = Color(overrideSeedArgb.toInt()).copy(alpha = 1f)
            // Keep light-theme accent readable against white cards
            val adjusted = if (raw.luminance() > 0.62f) lerp(raw, Color(0xFF111318), 0.35f) else raw
            val onCol = if (adjusted.luminance() > 0.42f) Color(0xFF111318) else Color.White
            val soft = lerp(cardSurface, adjusted, 0.14f)
            Triple(adjusted, onCol, soft)
        } else {
            Triple(paletteAccentLight, paletteOnLight, paletteSoftLight)
        }

        return PhoneMicColors(
            isDark = false,
            isOled = false,
            background = bgLight,
            cardSurface = cardSurface,
            nestedSurface = Color(0xFFEBEEF3),
            bottomBarSurface = Color(0xFFFFFFFF),
            border = Color(0xFFD6DCE5),
            borderActive = accent,
            textPrimary = Color(0xFF111318),
            textSecondary = Color(0xFF475569),
            textMuted = Color(0xFF6B7280),
            accent = accent,
            onAccent = onAccent,
            accentSoftBg = softBg,
            secondaryAccent = if (overrideSeedArgb != null) lerp(accent, paletteSecondaryLight, 0.35f) else paletteSecondaryLight,
            statusConnected = Color(0xFF15803D),
            statusWarning = Color(0xFFB45309),
            statusError = Color(0xFFDC2626),
            visualizerBg = Color(0xFFEFF2F6)
        )
    }

    val darkBg = if (isOledActive) Color(0xFF000000) else Color(0xFF121212)
    val darkCard = if (isOledActive) {
        Color(0xFF08080A)
    } else {
        when (palette) {
            AppPaletteStyle.TONAL_SPOT, AppPaletteStyle.CUSTOM -> Color(0xFF1A1D22)
            AppPaletteStyle.NEUTRAL -> Color(0xFF1A1A1C)
            AppPaletteStyle.VIBRANT -> Color(0xFF171E1C)
            AppPaletteStyle.MONOCHROME -> Color(0xFF19191B)
            AppPaletteStyle.STUDIO_CYAN -> Color(0xFF171C22)
            AppPaletteStyle.EXPRESSIVE -> Color(0xFF1E191C)
        }
    }
    val darkNested = if (isOledActive) Color(0xFF111114) else Color(0xFF23252B)
    val darkBorder = if (isOledActive) Color(0xFF202026) else Color(0xFF2D3038)
    val darkBottomBar = if (isOledActive) Color(0xFF000000) else Color(0xFF161618)

    val (accent, onAccent, softBg) = if (overrideSeedArgb != null) {
        val raw = Color(overrideSeedArgb.toInt()).copy(alpha = 1f)
        // Ensure dark-theme accent pops clearly on #121212 / #000000
        val adjusted = if (raw.luminance() < 0.14f) lerp(raw, Color.White, 0.38f) else raw
        val onCol = if (adjusted.luminance() > 0.40f) Color(0xFF09090B) else Color.White
        val soft = lerp(darkCard, adjusted, 0.22f)
        Triple(adjusted, onCol, soft)
    } else {
        Triple(paletteAccentDark, paletteOnDark, paletteSoftDark)
    }

    return PhoneMicColors(
        isDark = true,
        isOled = isOledActive,
        background = darkBg,
        cardSurface = darkCard,
        nestedSurface = darkNested,
        bottomBarSurface = darkBottomBar,
        border = darkBorder,
        borderActive = accent,
        textPrimary = if (isOledActive) Color(0xFFFFFFFF) else Color(0xFFF3F4F6),
        textSecondary = Color(0xFFA3AAB7),
        textMuted = Color(0xFF727985),
        accent = accent,
        onAccent = onAccent,
        accentSoftBg = softBg,
        secondaryAccent = if (overrideSeedArgb != null) lerp(accent, paletteSecondaryDark, 0.35f) else paletteSecondaryDark,
        statusConnected = Color(0xFF22C55E),
        statusWarning = Color(0xFFF59E0B),
        statusError = Color(0xFFEF4444),
        visualizerBg = if (isOledActive) Color(0xFF050507) else Color(0xFF141518)
    )
}

fun formatColorHex(argb: Long): String {
    val rgb = (argb and 0x00FFFFFFL).toInt()
    return String.format(java.util.Locale.US, "#%06X", rgb)
}

private data class QuadColor(
    val accent: Color,
    val onAccent: Color,
    val softBg: Color,
    val secondary: Color
)
