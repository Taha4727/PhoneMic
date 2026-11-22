package com.example

import android.app.Application
import android.content.Context
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextReplacement
import androidx.test.core.app.ApplicationProvider
import com.example.audio.AudioFormatOption
import com.example.audio.VisualizerStyle
import com.example.ui.screens.PhoneMicScreen
import com.example.ui.theme.AppPaletteStyle
import com.example.ui.theme.PhoneMicTheme
import com.example.ui.theme.ThemeColorPreset
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [36])
class ExampleRobolectricTest {

  @get:Rule
  val composeTestRule = createComposeRule()

  @Test
  fun `read string from context`() {
    val context = ApplicationProvider.getApplicationContext<Context>()
    val appName = context.getString(R.string.app_name)
    assertEquals("PhoneMic", appName)
  }

  @Test
  fun `bundled cli receiver matches app version`() {
    val context = ApplicationProvider.getApplicationContext<Context>()
    val script = context.assets.open("phonemic_cli.py").bufferedReader().use { it.readText() }
    assertTrue("Expected bundled phonemic_cli.py to declare VERSION = \"1.4.0\"", script.contains("VERSION = \"1.4.0\""))
    assertTrue("Expected bundled phonemic_cli.py to support PM04", script.contains("PM04"))
  }

  @Test
  fun `viewModel persists general audio appearance and custom theme color preferences`() {
    val app = ApplicationProvider.getApplicationContext<Application>()
    app.getSharedPreferences("PhoneMicSettings", Context.MODE_PRIVATE).edit().clear().commit()

    val vm1 = PhoneMicViewModel(app)
    assertEquals(MainTab.HOME, vm1.uiState.value.activeTab)

    vm1.setAutoStartStreaming(true)
    vm1.setPushToTalkEnabled(true)
    vm1.setAutoReconnectEnabled(true)
    vm1.setSampleRate(44100)
    vm1.setAudioFormat(AudioFormatOption.PCM_FLOAT)
    vm1.setChannels(2)
    vm1.setVisualizerEnabled(false)
    vm1.setVisualizerStyle(VisualizerStyle.SPECTRUM_BARS)
    vm1.setDarkMode(false)
    vm1.setOledBlackEnabled(true)
    vm1.setPaletteStyle(AppPaletteStyle.VIBRANT)
    vm1.setCustomThemeColor(0xFFEC4899L)

    val vm2 = PhoneMicViewModel(app)
    val state = vm2.uiState.value
    assertEquals(MainTab.HOME, state.activeTab)
    assertTrue(state.autoStartStreaming)
    assertTrue(state.pushToTalkEnabled)
    assertTrue(state.autoReconnectEnabled)
    assertEquals(44100, state.sampleRateHz)
    assertEquals(AudioFormatOption.PCM_FLOAT, state.audioFormat)
    assertEquals(2, state.channels)
    assertFalse(state.visualizerEnabled)
    assertEquals(VisualizerStyle.SPECTRUM_BARS, state.visualizerStyle)
    assertFalse(state.isDarkMode)
    assertTrue(state.oledBlackEnabled)
    assertEquals(AppPaletteStyle.VIBRANT, state.paletteStyle)
    assertEquals(ThemeColorPreset.CUSTOM, state.themeColorPreset)
    assertEquals(0xFFEC4899L, state.customThemeColorArgb)
  }

  @Test
  @Config(qualifiers = "w411dp-h840dp")
  fun `home screen fits without scrolling and supports theme and ptt toggles`() {
    val app = ApplicationProvider.getApplicationContext<Application>()
    app.getSharedPreferences("PhoneMicSettings", Context.MODE_PRIVATE).edit().clear().commit()
    val vm = PhoneMicViewModel(app)

    composeTestRule.setContent {
      val uiState by vm.uiState.collectAsState()
      PhoneMicTheme(
        isDarkMode = uiState.isDarkMode,
        oledBlackEnabled = uiState.oledBlackEnabled,
        paletteStyle = uiState.paletteStyle,
        themeColorPreset = uiState.themeColorPreset,
        customThemeColorArgb = uiState.customThemeColorArgb
      ) {
        PhoneMicScreen(viewModel = vm)
      }
    }
    composeTestRule.waitForIdle()

    composeTestRule.onNodeWithTag("home_screen").assertIsDisplayed()
    composeTestRule.onNodeWithTag("bottom_nav_bar").assertIsDisplayed()

    composeTestRule.onNodeWithTag("home_connection_status").assertIsDisplayed()
    composeTestRule.onNodeWithTag("home_connection_timer").assertIsDisplayed()
    composeTestRule.onNodeWithTag("theme_toggle_button").assertIsDisplayed()
    composeTestRule.onNodeWithTag("home_section_controls").assertIsDisplayed()
    composeTestRule.onNodeWithTag("conn_mode_wifi").assertIsDisplayed()
    composeTestRule.onNodeWithTag("conn_mode_usb").assertIsDisplayed()
    composeTestRule.onNodeWithTag("conn_mode_qr").assertIsDisplayed()
    composeTestRule.onNodeWithTag("ip_address_input").assertIsDisplayed()
    composeTestRule.onNodeWithTag("port_input").assertIsDisplayed()
    composeTestRule.onNodeWithTag("scan_pc_button").assertIsDisplayed()
    composeTestRule.onNodeWithTag("home_transport_udp").assertIsDisplayed()
    composeTestRule.onNodeWithTag("home_transport_tcp").assertIsDisplayed()
    composeTestRule.onNodeWithTag("home_ptt_toggle").assertIsDisplayed()
    composeTestRule.onNodeWithTag("start_streaming_button").assertIsDisplayed()
    composeTestRule.onNodeWithTag("pause_resume_button").assertIsDisplayed()
    composeTestRule.onNodeWithTag("audio_visualizer_card").assertIsDisplayed()

    // Section 2 (~2/3 workspace) and Section 3 (~1/3 workspace) must remain balanced without clipping
    val controlsHeightPx = composeTestRule.onNodeWithTag("home_section_controls").fetchSemanticsNode().size.height
    val visualizerHeightPx = composeTestRule.onNodeWithTag("audio_visualizer_card").fetchSemanticsNode().size.height
    assertTrue(
      "Expected Section 2 ($controlsHeightPx px) to stay well above Section 3 ($visualizerHeightPx px)",
      controlsHeightPx >= (visualizerHeightPx * 1.75f).toInt()
    )
    assertTrue(
      "Expected Section 3 visualizer ($visualizerHeightPx px) not to be overly compacted",
      visualizerHeightPx >= 150
    )

    assertEquals(PhoneMicService.TRANSPORT_UDP, vm.uiState.value.transportMode)
    composeTestRule.onNodeWithTag("home_transport_tcp").performClick()
    composeTestRule.waitForIdle()
    assertEquals(PhoneMicService.TRANSPORT_TCP, vm.uiState.value.transportMode)

    assertTrue(vm.uiState.value.isDarkMode)
    composeTestRule.onNodeWithTag("theme_toggle_button").performClick()
    composeTestRule.waitForIdle()
    assertFalse(vm.uiState.value.isDarkMode)

    composeTestRule.onNodeWithTag("home_ptt_toggle").performClick()
    composeTestRule.waitForIdle()
    assertTrue(vm.uiState.value.pushToTalkEnabled)
  }

  @Test
  @Config(qualifiers = "w411dp-h840dp")
  fun `status tab renders live stream audio and device sections`() {
    val app = ApplicationProvider.getApplicationContext<Application>()
    app.getSharedPreferences("PhoneMicSettings", Context.MODE_PRIVATE).edit().clear().commit()
    val vm = PhoneMicViewModel(app)

    composeTestRule.setContent {
      val uiState by vm.uiState.collectAsState()
      PhoneMicTheme(
        isDarkMode = uiState.isDarkMode,
        oledBlackEnabled = uiState.oledBlackEnabled,
        paletteStyle = uiState.paletteStyle,
        themeColorPreset = uiState.themeColorPreset,
        customThemeColorArgb = uiState.customThemeColorArgb
      ) {
        PhoneMicScreen(viewModel = vm)
      }
    }
    composeTestRule.waitForIdle()

    composeTestRule.onNodeWithTag("nav_tab_status").performClick()
    composeTestRule.waitForIdle()

    composeTestRule.onNodeWithTag("status_screen").assertIsDisplayed()
    composeTestRule.onNodeWithTag("status_section_live_stream").performScrollTo().assertIsDisplayed()
    composeTestRule.onNodeWithText("PACKET LOSS").performScrollTo().assertIsDisplayed()
    composeTestRule.onNodeWithText("STREAM RATE").performScrollTo().assertIsDisplayed()
    composeTestRule.onNodeWithText("TRANSFERRED").performScrollTo().assertIsDisplayed()
    composeTestRule.onNodeWithText("BITRATE").performScrollTo().assertIsDisplayed()

    composeTestRule.onNodeWithTag("status_section_audio").performScrollTo().assertIsDisplayed()
    composeTestRule.onNodeWithTag("status_section_device").performScrollTo().assertIsDisplayed()
  }

  @Test
  @Config(qualifiers = "w411dp-h840dp")
  fun `settings dropdowns and theme color picker update audio and appearance state`() {
    val app = ApplicationProvider.getApplicationContext<Application>()
    app.getSharedPreferences("PhoneMicSettings", Context.MODE_PRIVATE).edit().clear().commit()
    val vm = PhoneMicViewModel(app)

    composeTestRule.setContent {
      val uiState by vm.uiState.collectAsState()
      PhoneMicTheme(
        isDarkMode = uiState.isDarkMode,
        oledBlackEnabled = uiState.oledBlackEnabled,
        paletteStyle = uiState.paletteStyle,
        themeColorPreset = uiState.themeColorPreset,
        customThemeColorArgb = uiState.customThemeColorArgb
      ) {
        PhoneMicScreen(viewModel = vm)
      }
    }
    composeTestRule.waitForIdle()

    composeTestRule.onNodeWithTag("open_settings_button").performClick()
    composeTestRule.waitForIdle()

    composeTestRule.onNodeWithTag("settings_screen").assertIsDisplayed()
    composeTestRule.onNodeWithTag("settings_section_general").assertExists()
    composeTestRule.onNodeWithTag("settings_section_audio").assertExists()
    composeTestRule.onNodeWithTag("settings_section_appearance").assertExists()
    composeTestRule.onNodeWithTag("settings_section_about").assertExists()

    // Toggle PTT switch
    composeTestRule.onNodeWithTag("setting_ptt_mode").performScrollTo().performClick()

    // Select Audio options via Dropdowns
    composeTestRule.onNodeWithTag("dropdown_sample_rate").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("sample_rate_32000").performClick()

    composeTestRule.onNodeWithTag("dropdown_audio_format").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("audio_format_PCM_8").performClick()

    composeTestRule.onNodeWithTag("dropdown_channels").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("channels_2").performClick()

    // Select Appearance options via Switches & Dropdowns
    composeTestRule.onNodeWithTag("setting_oled_colors").performScrollTo().performClick()

    composeTestRule.onNodeWithTag("dropdown_palette_style").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("palette_style_VIBRANT").performClick()

    composeTestRule.onNodeWithTag("dropdown_theme_color").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("theme_color_EMERALD").performClick()
    composeTestRule.waitForIdle()
    assertEquals(ThemeColorPreset.EMERALD, vm.uiState.value.themeColorPreset)

    // Open Custom Theme Color Picker Dialog, select a swatch, and apply
    composeTestRule.onNodeWithTag("open_color_picker_button").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("custom_color_preview").assertIsDisplayed()
    composeTestRule.onNodeWithTag("color_swatch_#F43F5E").performClick()
    composeTestRule.onNodeWithTag("custom_color_apply_button").performClick()
    composeTestRule.waitForIdle()

    assertEquals(ThemeColorPreset.CUSTOM, vm.uiState.value.themeColorPreset)
    assertEquals(0xFFF43F5EL, vm.uiState.value.customThemeColorArgb)

    // Enter exact custom hex code directly in Appearance card field
    composeTestRule.onNodeWithTag("custom_color_hex_input").performScrollTo().performTextReplacement("#FF5500")
    composeTestRule.waitForIdle()

    assertEquals(ThemeColorPreset.CUSTOM, vm.uiState.value.themeColorPreset)
    assertEquals(0xFFFF5500L, vm.uiState.value.customThemeColorArgb)

    composeTestRule.onNodeWithTag("setting_bottom_bar_border").assertDoesNotExist()

    composeTestRule.onNodeWithTag("dropdown_visualizer_style").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("visualizer_style_CIRCULAR_PULSE").performClick()
    composeTestRule.waitForIdle()

    assertEquals(32000, vm.uiState.value.sampleRateHz)
    assertEquals(AudioFormatOption.PCM_8BIT, vm.uiState.value.audioFormat)
    assertEquals(2, vm.uiState.value.channels)
    assertEquals(VisualizerStyle.CIRCULAR_PULSE, vm.uiState.value.visualizerStyle)
    assertEquals(AppPaletteStyle.VIBRANT, vm.uiState.value.paletteStyle)
    assertTrue(vm.uiState.value.oledBlackEnabled)
    assertTrue(vm.uiState.value.pushToTalkEnabled)

    // Scroll to About section to confirm version readout is present
    composeTestRule.onNodeWithText("v1.4.0 (Build 5)").performScrollTo().assertIsDisplayed()

    // Navigate back to Home and verify updated visualizer canvas renders
    composeTestRule.onNodeWithTag("settings_back_button").performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("visualizer_canvas_CIRCULAR_PULSE").assertExists()
  }
}
