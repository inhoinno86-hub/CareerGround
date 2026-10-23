package dev.careerground.interview.design

import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import dev.careerground.pace.*
import org.junit.Rule
import org.junit.Test
import org.junit.Assert.*

class PaceUiTest {
    @get:Rule val compose=createComposeRule()
    private lateinit var read:()->PaceState
    private var actions=mutableListOf<PaceAction>()
    private fun launch(initial:PaceState) {
        compose.setContent {
            var state by remember { mutableStateOf(initial) }
            read={state}
            val callbacks=PaceCallbacks(action={actions.add(it)},navigate={state=state.copy(screen=it)},
                editDraft={state=state.copy(draft=it,confirmed=false)},confirmAnswer={state=state.copy(confirmed=it)},
                confirmReview={state=state.copy(reviewChecked=it)},selectMode={state=state.copy(mode=it)},
                selectQuestion={state=state.copy(questionId=it,confirmed=false)},editJoinCode={state=state.copy(joinCode=it)})
            PaceTheme { PaceApp(state,callbacks) }
        }
    }
    @Test fun submitRequiresNonblankDraftAndExplicitConfirmationAndEditingRevokesIt() {
        launch(exampleState("interview"))
        compose.onNodeWithTag("submit").assertIsNotEnabled()
        compose.onNodeWithTag("answer-confirm").performClick()
        compose.onNodeWithTag("submit").assertIsNotEnabled()
        compose.onNodeWithTag("draft").performTextInput("제가 직접 분류 기준을 제안했습니다.")
        compose.onNodeWithTag("submit").assertIsNotEnabled()
        compose.onNodeWithTag("answer-confirm").performClick()
        compose.onNodeWithTag("submit").assertIsEnabled().performClick()
        compose.runOnIdle { assertEquals(listOf(PaceAction.SUBMIT),actions) }
        compose.onNodeWithTag("draft").performTextReplacement("팀과 함께 검토했습니다.")
        compose.onNodeWithTag("submit").assertIsNotEnabled()
        compose.runOnIdle { assertFalse(read().confirmed) }
    }
    @Test fun listeningDisablesDraftAndConfirmationAndSubmission() {
        launch(exampleState("voice").copy(confirmed=true))
        compose.onNodeWithTag("draft").assertIsNotEnabled()
        compose.onNodeWithTag("answer-confirm").assertIsNotEnabled()
        compose.onNodeWithTag("submit").assertIsNotEnabled()
    }
    @Test fun pausedAnswerCannotBeSubmitted() {
        launch(exampleState("paused").copy(confirmed=true))
        compose.onNodeWithTag("submit").assertDoesNotExist()
        compose.onNodeWithTag("draft").assertIsNotEnabled()
        compose.onNodeWithText("연습 계속").performClick()
        compose.runOnIdle { assertEquals(listOf(PaceAction.CONTINUE),actions) }
    }
    @Test fun simulationSuppressesFeedbackAndCandidatesEvenIfProvided() {
        val state=exampleState("simulation")
        launch(state)
        compose.onNodeWithTag("feedback").assertDoesNotExist()
        compose.onNodeWithText(state.candidates.first()).assertDoesNotExist()
        compose.onNodeWithText("연습 결과").assertDoesNotExist()
    }
    @Test fun reviewRequiresScopeConfirmation() {
        launch(exampleState("review"))
        compose.onNodeWithTag("review").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithTag("review-confirm").performScrollTo().performClick()
        compose.onNodeWithTag("review").performScrollTo().assertIsEnabled().performClick()
        compose.runOnIdle { assertEquals(listOf(PaceAction.REVIEW),actions) }
    }
    @Test fun resultSaveRequiresPreparedBytesAndDoesNotPretendToSave() {
        launch(exampleState("result"))
        compose.onNodeWithTag("save").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithText("면접 결과 파일 준비").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(listOf(PaceAction.PREPARE_RESULT),actions) }
        compose.onNodeWithTag("save").assertIsNotEnabled()
    }
    @Test fun questionProgressUsesActiveQuestionsRatherThanHardcodedFive() {
        val initial=exampleState("interview")
        launch(initial.copy(questions=initial.questions.take(2)+initial.questions[2].copy(status="stale")))
        compose.onNodeWithText("코칭 · 질문 1 / 2").assertIsDisplayed()
    }
    @Test fun busyDisablesConfirmedSubmission() {
        launch(exampleState("draft").copy(busy=true,confirmed=true))
        compose.onNodeWithTag("busy").assertExists()
        compose.onNodeWithTag("submit").assertIsNotEnabled()
    }
    @Test fun longSourceCanBeReviewedInPagesWithoutRenderingAllPagesAtOnce() {
        launch(exampleState("import").copy(documentContent="가".repeat(12000)+"두 번째 자료 페이지"))
        compose.onNodeWithText("선택 자료 상세 보기").performScrollTo().performClick()
        compose.onNodeWithTag("source-page").performScrollTo().assertTextEquals("1 / 2")
        compose.onNodeWithText("두 번째 자료 페이지").assertDoesNotExist()
        compose.onNodeWithTag("source-next").performScrollTo().performClick()
        compose.onNodeWithTag("source-page").assertTextEquals("2 / 2")
        compose.onNodeWithText("두 번째 자료 페이지").assertExists()
    }
}
