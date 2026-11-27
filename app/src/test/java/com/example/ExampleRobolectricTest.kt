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
    assertTrue("Expected bundled phonemic_cli.py to declare VERSION = \"1.4.2\"", script.contains("VERSION = \"1.4.2\""))
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
    vm1.setHorizontalNavMode(HorizontalNavMode.SIDE_RAIL)

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
    assertEquals(AppPaletteStyle.CUSTOM, state.paletteStyle)
    assertEquals(0xFFEC4899L, state.customThemeColorArgb)
    assertEquals(HorizontalNavMode.SIDE_RAIL, state.horizontalNavMode)
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

    composeTestRule.onNodeWithTag("dropdown_theme_color").assertDoesNotExist()

    composeTestRule.onNodeWithTag("dropdown_palette_style").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("palette_style_VIBRANT").performClick()
    composeTestRule.waitForIdle()
    assertEquals(AppPaletteStyle.VIBRANT, vm.uiState.value.paletteStyle)

    // Open Custom Palette Color Picker Dialog via Palette Style, select a swatch, and apply
    composeTestRule.onNodeWithTag("dropdown_palette_style").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("palette_style_CUSTOM").performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("custom_color_preview").assertIsDisplayed()
    composeTestRule.onNodeWithTag("color_swatch_#F43F5E").performClick()
    composeTestRule.onNodeWithTag("custom_color_apply_button").performClick()
    composeTestRule.waitForIdle()

    assertEquals(AppPaletteStyle.CUSTOM, vm.uiState.value.paletteStyle)
    assertEquals(0xFFF43F5EL, vm.uiState.value.customThemeColorArgb)

    // Enter exact custom hex code directly in Appearance card field
    composeTestRule.onNodeWithTag("custom_color_hex_input").performScrollTo().performTextReplacement("#FF5500")
    composeTestRule.waitForIdle()

    assertEquals(AppPaletteStyle.CUSTOM, vm.uiState.value.paletteStyle)
    assertEquals(0xFFFF5500L, vm.uiState.value.customThemeColorArgb)

    composeTestRule.onNodeWithTag("open_color_picker_button").assertExists()
    composeTestRule.onNodeWithTag("setting_bottom_bar_border").assertDoesNotExist()

    // Select Side Rail for Horizontal Navigation
    composeTestRule.onNodeWithTag("dropdown_horizontal_nav").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("horizontal_nav_SIDE_RAIL").performClick()
    composeTestRule.waitForIdle()
    assertEquals(HorizontalNavMode.SIDE_RAIL, vm.uiState.value.horizontalNavMode)

    composeTestRule.onNodeWithTag("dropdown_visualizer_style").performScrollTo().performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("visualizer_style_CIRCULAR_PULSE").performClick()
    composeTestRule.waitForIdle()

    assertEquals(32000, vm.uiState.value.sampleRateHz)
    assertEquals(AudioFormatOption.PCM_8BIT, vm.uiState.value.audioFormat)
    assertEquals(2, vm.uiState.value.channels)
    assertEquals(VisualizerStyle.CIRCULAR_PULSE, vm.uiState.value.visualizerStyle)
    assertEquals(AppPaletteStyle.CUSTOM, vm.uiState.value.paletteStyle)
    assertTrue(vm.uiState.value.oledBlackEnabled)
    assertTrue(vm.uiState.value.pushToTalkEnabled)

    // Scroll to About section to confirm version readout is present
    composeTestRule.onNodeWithText("v1.4.2 (Build 6)").performScrollTo().assertIsDisplayed()

    // Navigate back to Home and verify updated visualizer canvas renders
    composeTestRule.onNodeWithTag("settings_back_button").performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("visualizer_canvas_CIRCULAR_PULSE").assertExists()
  }

  @Test
  @Config(qualifiers = "w840dp-h411dp")
  fun `horizontal home splits section 2 and visualizer 50 50 and expands when hidden`() {
    val app = ApplicationProvider.getApplicationContext<Application>()
    app.getSharedPreferences("PhoneMicSettings", Context.MODE_PRIVATE).edit().clear().commit()
    val vm = PhoneMicViewModel(app)

    composeTestRule.setContent {
      val uiState by vm.uiState.collectAsState()
      PhoneMicTheme(
        isDarkMode = uiState.isDarkMode,
        oledBlackEnabled = uiState.oledBlackEnabled,
        paletteStyle = uiState.paletteStyle,
        customThemeColorArgb = uiState.customThemeColorArgb
      ) {
        PhoneMicScreen(viewModel = vm)
      }
    }
    composeTestRule.waitForIdle()

    // Bottom NavigationBar is the default in horizontal mode and stays compact vertically
    assertEquals(HorizontalNavMode.BOTTOM_BAR, vm.uiState.value.horizontalNavMode)
    composeTestRule.onNodeWithTag("bottom_nav_bar").assertIsDisplayed()
    composeTestRule.onNodeWithTag("nav_rail").assertDoesNotExist()
    val bottomNavBounds = composeTestRule.onNodeWithTag("bottom_nav_bar").fetchSemanticsNode().boundsInRoot
    assertTrue(
      "Expected compact horizontal bottom nav bar (height=${bottomNavBounds.height} px <= 56 px)",
      bottomNavBounds.height <= 56f
    )
    val homeTabBounds = composeTestRule.onNodeWithTag("nav_tab_home").fetchSemanticsNode().boundsInRoot
    val homePillBounds = composeTestRule.onNodeWithTag("nav_pill_home", useUnmergedTree = true).fetchSemanticsNode().boundsInRoot
    assertTrue("Expected nav tab height >= 48 px (got ${homeTabBounds.height})", homeTabBounds.height >= 48f)
    assertTrue(
      "Expected compact icon-only pill width (${homePillBounds.width} px <= 52 px), much narrower than tab (${homeTabBounds.width} px)",
      homePillBounds.width <= 52f && homePillBounds.width < homeTabBounds.width * 0.5f
    )

    // Full-width top bar above 50/50 split workspace
    composeTestRule.onNodeWithTag("home_top_bar").assertIsDisplayed()
    composeTestRule.onNodeWithTag("home_horizontal_split").assertIsDisplayed()
    composeTestRule.onNodeWithTag("home_section_controls").assertIsDisplayed()
    composeTestRule.onNodeWithTag("audio_visualizer_card").assertIsDisplayed()
    composeTestRule.onNodeWithTag("start_streaming_button").assertIsDisplayed()

    // Circular Pulse style renders cleanly in horizontal split
    vm.setVisualizerStyle(VisualizerStyle.CIRCULAR_PULSE)
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("visualizer_canvas_CIRCULAR_PULSE").assertIsDisplayed()

    val topBarBounds = composeTestRule.onNodeWithTag("home_top_bar").fetchSemanticsNode().boundsInRoot
    val controlsBounds = composeTestRule.onNodeWithTag("home_section_controls").fetchSemanticsNode().boundsInRoot
    val visualizerBounds = composeTestRule.onNodeWithTag("audio_visualizer_card").fetchSemanticsNode().boundsInRoot

    assertTrue("Expected Section 1 full-width top bar above split", topBarBounds.bottom <= controlsBounds.top + 2f)
    assertTrue("Expected Section 2 on the left of Visualizer", controlsBounds.right <= visualizerBounds.left + 2f)
    val widthDiff = kotlin.math.abs(controlsBounds.width - visualizerBounds.width)
    assertTrue("Expected 50/50 horizontal split (diff=$widthDiff px)", widthDiff <= 20f)

    // Hide visualizer via small header button; Section 2 expands and splits into two compact columns
    composeTestRule.onNodeWithTag("visualizer_hide_button").performClick()
    composeTestRule.waitForIdle()

    assertFalse(vm.uiState.value.visualizerEnabled)
    composeTestRule.onNodeWithTag("audio_visualizer_card").assertDoesNotExist()
    composeTestRule.onNodeWithTag("visualizer_show_button").assertIsDisplayed()
    composeTestRule.onNodeWithTag("home_controls_two_column").assertIsDisplayed()

    val expandedBounds = composeTestRule.onNodeWithTag("home_section_controls").fetchSemanticsNode().boundsInRoot
    assertTrue(
      "Expected Section 2 (${expandedBounds.width} px) to expand when visualizer hidden (${controlsBounds.width} px)",
      expandedBounds.width >= controlsBounds.width * 1.6f
    )

    val ipBounds = composeTestRule.onNodeWithTag("ip_address_input").fetchSemanticsNode().boundsInRoot
    val startBounds = composeTestRule.onNodeWithTag("start_streaming_button").fetchSemanticsNode().boundsInRoot
    assertTrue(
      "Expected IP field on left (${ipBounds.right}) of Start button (${startBounds.left}) in two-column mode",
      ipBounds.right <= startBounds.left + 2f
    )
    assertTrue(
      "Expected IP field width (${ipBounds.width} px) to stay compact inside two-column Section 2 (${expandedBounds.width} px)",
      ipBounds.width < expandedBounds.width * 0.6f
    )

    // Restore visualizer directly from Home top bar
    composeTestRule.onNodeWithTag("visualizer_show_button").performClick()
    composeTestRule.waitForIdle()

    assertTrue(vm.uiState.value.visualizerEnabled)
    composeTestRule.onNodeWithTag("audio_visualizer_card").assertIsDisplayed()
  }

  @Test
  @Config(qualifiers = "w840dp-h411dp")
  fun `horizontal status uses two columns and side rail setting switches navigation`() {
    val app = ApplicationProvider.getApplicationContext<Application>()
    app.getSharedPreferences("PhoneMicSettings", Context.MODE_PRIVATE).edit().clear().commit()
    val vm = PhoneMicViewModel(app)
    vm.setHorizontalNavMode(HorizontalNavMode.SIDE_RAIL)

    composeTestRule.setContent {
      val uiState by vm.uiState.collectAsState()
      PhoneMicTheme(
        isDarkMode = uiState.isDarkMode,
        oledBlackEnabled = uiState.oledBlackEnabled,
        paletteStyle = uiState.paletteStyle,
        customThemeColorArgb = uiState.customThemeColorArgb
      ) {
        PhoneMicScreen(viewModel = vm)
      }
    }
    composeTestRule.waitForIdle()

    // Side Rail active instead of Bottom Bar
    composeTestRule.onNodeWithTag("nav_rail").assertIsDisplayed()
    composeTestRule.onNodeWithTag("bottom_nav_bar").assertDoesNotExist()

    // Status tab shows 2 balanced side-by-side columns
    composeTestRule.onNodeWithTag("nav_tab_status").performClick()
    composeTestRule.waitForIdle()

    composeTestRule.onNodeWithTag("status_horizontal_columns").assertIsDisplayed()
    val liveBounds = composeTestRule.onNodeWithTag("status_section_live_stream").fetchSemanticsNode().boundsInRoot
    val audioBounds = composeTestRule.onNodeWithTag("status_section_audio").fetchSemanticsNode().boundsInRoot
    assertTrue("Expected Live Stream left of Audio in horizontal Status", liveBounds.right <= audioBounds.left + 2f)

    // Settings tab stays focused single column capped cleanly
    composeTestRule.onNodeWithTag("open_settings_button").performClick()
    composeTestRule.waitForIdle()

    composeTestRule.onNodeWithTag("settings_screen").assertIsDisplayed()
    val settingsBounds = composeTestRule.onNodeWithTag("settings_screen").fetchSemanticsNode().boundsInRoot
    val rootBounds = composeTestRule.onNodeWithTag("nav_rail").fetchSemanticsNode().boundsInRoot
    assertTrue("Expected Settings to remain to the right of Side Rail", settingsBounds.left >= rootBounds.right - 2f)
  }
}
