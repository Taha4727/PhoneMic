package com.example

import org.junit.Assert.assertEquals
import org.junit.Test

class ExampleUnitTest {
  @Test
  fun addition_isCorrect() {
    assertEquals(4, 2 + 2)
  }

  @Test
  fun appVersion_is130() {
    assertEquals("1.3.0", BuildConfig.VERSION_NAME)
    assertEquals(4, BuildConfig.VERSION_CODE)
  }
}
