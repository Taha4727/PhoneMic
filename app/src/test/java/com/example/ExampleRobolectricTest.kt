package com.example

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [36])
class ExampleRobolectricTest {

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
    assertTrue("Expected bundled phonemic_cli.py to declare VERSION = \"1.3.0\"", script.contains("VERSION = \"1.3.0\""))
  }
}
