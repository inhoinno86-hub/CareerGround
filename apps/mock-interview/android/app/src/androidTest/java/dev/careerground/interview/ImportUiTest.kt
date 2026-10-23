package dev.careerground.interview

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import android.view.WindowManager
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ImportUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun startsDisconnectedWithExplicitAuthChoicesWithoutAutomaticSession() {
        compose.onNodeWithText("CareerGround").assertIsDisplayed()
        compose.onNodeWithText("개인 계정 로그인").assertIsDisplayed()
        compose.onNodeWithText("자동 저장되지 않습니다. 앱을 닫기 전에 복구 파일을 저장해 주세요.").assertIsDisplayed()
        compose.onNodeWithText("개발 시험 연결").performScrollTo().performClick()
        compose.onNodeWithText("합성 개발 연결").performScrollTo().assertIsDisplayed().assertIsNotEnabled()
        compose.runOnIdle {
            val model = ViewModelProvider(compose.activity)[InterviewModel::class.java]
            assertFalse(model.connected)
            assertNull(model.report)
            assertTrue(compose.activity.window.attributes.flags and WindowManager.LayoutParams.FLAG_SECURE != 0)
        }
    }

    @Test fun strictReaderRejectsNestedDuplicatesTrailingDataAndInvalidUtf8() {
        for (raw in listOf(
            "{\"x\":{\"id\":1,\"id\":2}}".toByteArray(),
            "{}{}".toByteArray(), byteArrayOf(0xff.toByte()),
            "{\"x\":NaN}".toByteArray()
        )) {
            assertThrows(Exception::class.java) { SelectedFiles.strictObject(raw) }
        }
    }

    @Test fun sessionEnvelopeAllowsBoundedOriginalFileButRegularTextIsLimited() {
        val blob = "YQ==".repeat(6000)
        assertEquals(blob, SelectedFiles.strictObject("{\"handoff_base64\":\"$blob\"}".toByteArray())
            .getString("handoff_base64"))
        assertThrows(IllegalArgumentException::class.java) {
            SelectedFiles.strictObject("{\"text\":\"$blob\"}".toByteArray())
        }
    }
}
