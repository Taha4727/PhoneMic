package com.example

import android.app.Application
import android.content.Context
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.core.app.ApplicationProvider
import com.example.audio.AudioFormatOption
import com.example.audio.VisualizerStyle
import com.example.ui.screens.PhoneMicScreen
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
    assertTrue("Expected bundled phonemic_cli.py to declare VERSION = \"1.4.0\"", script.contains("VERSION = \"1.4.0\""))
    assertTrue("Expected bundled phonemic_cli.py to support PM04", script.contains("PM04"))
  }

  @Test
  fun `viewModel persists new general audio and appearance preferences`() {
    val app = ApplicationProvider.getApplicationContext<Application>()
    app.getSharedPreferences("PhoneMicSettings", Context.MODE_PRIVATE).edit().clear().commit()

    val vm1 = PhoneMicViewModel(app)
    vm1.setAutoStartStreaming(true)
    vm1.setPushToTalkEnabled(true)
    vm1.setAutoReconnectEnabled(true)
    vm1.setSampleRate(44100)
    vm1.setAudioFormat(AudioFormatOption.PCM_FLOAT)
    vm1.setChannels(2)
    vm1.setVisualizerEnabled(false)
    vm1.setVisualizerStyle(VisualizerStyle.SPECTRUM_BARS)

    val vm2 = PhoneMicViewModel(app)
    val state = vm2.uiState.value
    assertTrue(state.autoStartStreaming)
    assertTrue(state.pushToTalkEnabled)
    assertTrue(state.autoReconnectEnabled)
    assertEquals(44100, state.sampleRateHz)
    assertEquals(AudioFormatOption.PCM_FLOAT, state.audioFormat)
    assertEquals(2, state.channels)
    assertFalse(state.visualizerEnabled)
    assertEquals(VisualizerStyle.SPECTRUM_BARS, state.visualizerStyle)
  }

  @Test
  fun `settings navigation shows all four sections and updates visualizer and audio state`() {
    val app = ApplicationProvider.getApplicationContext<Application>()
    app.getSharedPreferences("PhoneMicSettings", Context.MODE_PRIVATE).edit().clear().commit()
    val vm = PhoneMicViewModel(app)

    composeTestRule.setContent {
      PhoneMicTheme {
        PhoneMicScreen(viewModel = vm)
      }
    }
    composeTestRule.waitForIdle()

    // Home initially shows visualizer card by default and opens settings via top gear icon
    composeTestRule.onNodeWithTag("audio_visualizer_card").performScrollTo().assertIsDisplayed()
    composeTestRule.onNodeWithTag("open_settings_button").performClick()
    composeTestRule.waitForIdle()

    composeTestRule.onNodeWithTag("settings_screen").assertIsDisplayed()
    composeTestRule.onNodeWithTag("settings_section_general").assertExists()
    composeTestRule.onNodeWithTag("settings_section_audio").assertExists()
    composeTestRule.onNodeWithTag("settings_section_appearance").assertExists()
    composeTestRule.onNodeWithTag("settings_section_about").assertExists()

    // Change sample rate, format, channels, and visualizer style inside Settings
    composeTestRule.onNodeWithTag("sample_rate_32000").performScrollTo().performClick()
    composeTestRule.onNodeWithTag("audio_format_PCM_8").performScrollTo().performClick()
    composeTestRule.onNodeWithTag("channels_2").performScrollTo().performClick()
    composeTestRule.onNodeWithTag("visualizer_style_CIRCULAR_PULSE").performScrollTo().performClick()
    composeTestRule.onNodeWithTag("setting_ptt_mode").performScrollTo().performClick()
    composeTestRule.waitForIdle()

    assertEquals(32000, vm.uiState.value.sampleRateHz)
    assertEquals(AudioFormatOption.PCM_8BIT, vm.uiState.value.audioFormat)
    assertEquals(2, vm.uiState.value.channels)
    assertEquals(VisualizerStyle.CIRCULAR_PULSE, vm.uiState.value.visualizerStyle)
    assertTrue(vm.uiState.value.pushToTalkEnabled)

    // Scroll to About section to confirm version readout is present
    composeTestRule.onNodeWithText("v1.4.0 (Build 5)").performScrollTo().assertIsDisplayed()

    // Navigate back to Home and verify updated visualizer canvas renders
    composeTestRule.onNodeWithTag("settings_back_button").performClick()
    composeTestRule.waitForIdle()
    composeTestRule.onNodeWithTag("visualizer_canvas_CIRCULAR_PULSE").assertExists()
  }
}
