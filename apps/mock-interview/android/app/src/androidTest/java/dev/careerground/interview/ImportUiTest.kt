package dev.careerground.interview

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ImportUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun startsDisconnectedWithExplicitAuthChoicesWithoutAutomaticSession() {
        compose.onNodeWithText("모의 면접 · 개발 시험").assertIsDisplayed()
        compose.onNodeWithText("개인 계정 로그인").assertIsDisplayed()
        compose.onNodeWithText("합성 개발 연결").assertIsDisplayed()
        compose.onNodeWithText("자동 저장 없음 · 앱 종료 시 미저장 내용이 사라집니다.").assertIsDisplayed()
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
