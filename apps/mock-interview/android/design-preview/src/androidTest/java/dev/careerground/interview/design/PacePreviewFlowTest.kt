package dev.careerground.interview.design

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import org.junit.Rule
import org.junit.Test

class PacePreviewFlowTest {
    @get:Rule val compose=createAndroidComposeRule<DesignPreviewActivity>()
    @Test fun focusedPracticeKeepsDraftAndConfirmationAcrossActivityRecreation() {
        compose.onNodeWithText("한 답변에 집중").performScrollTo().performClick()
        compose.onNodeWithTag("generate").performScrollTo().performClick()
        compose.onNodeWithTag("draft").performTextInput("제가 직접 정리했습니다.")
        compose.onNodeWithTag("answer-confirm").performClick()
        compose.onNodeWithTag("submit").assertIsEnabled()
        compose.activityRule.scenario.recreate()
        compose.onNodeWithTag("draft").assertTextContains("제가 직접 정리했습니다.")
        compose.onNodeWithTag("submit").assertIsEnabled()
        compose.onNodeWithText("한 답변에 집중 · 질문 1 / 5").assertExists()
    }
}
