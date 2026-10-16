package dev.careerground.interview

import android.graphics.Bitmap
import android.os.ParcelFileDescriptor
import android.net.Uri
import android.view.WindowManager
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.compose.runtime.MutableState
import androidx.test.platform.app.InstrumentationRegistry
import dev.careerground.pace.PaceScreen
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import java.io.File
import kotlin.math.roundToInt

/** Real app + loopback HTTP + deterministic synthetic provider. No personal login or AI calls. */
class PaceRuntimeUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val model get() = ViewModelProvider(compose.activity)[InterviewModel::class.java]
    private val resolver get() = compose.activity.contentResolver
    private val answer = "동료 의견을 받아 체크리스트 순서를 수정했습니다."

    private fun settle() {
        compose.waitUntil(20000) { !model.busy }
        compose.waitForIdle()
        assertFalse(model.message, model.message.startsWith("작업 실패"))
    }

    private fun click(text: String) {
        compose.onNodeWithText(text).performScrollTo().performClick()
        settle()
    }

    private fun showBusyState() {
        compose.runOnIdle {
            @Suppress("UNCHECKED_CAST")
            val holder = InterviewModel::class.java.getDeclaredField("busy\$delegate")
                .apply { isAccessible = true }.get(model) as MutableState<Boolean>
            holder.value = true
        }
        compose.waitForIdle()
    }

    private fun capture(name: String) {
        if (InstrumentationRegistry.getArguments().getString("pace_capture") != "true") return
        // Only this synthetic test temporarily permits capture. Production FLAG_SECURE stays enabled.
        assertEquals("synthetic_dev", model.authMode)
        compose.runOnIdle { compose.activity.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE) }
        instrumentation.waitForIdleSync()
        Thread.sleep(300)
        try {
            val image = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
            val dir = File(compose.activity.cacheDir, "pace-validation").apply { mkdirs() }
            File(dir, "$name.png").outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
            image.recycle()
        } finally {
            compose.runOnIdle { compose.activity.window.addFlags(WindowManager.LayoutParams.FLAG_SECURE) }
        }
    }

    private fun start(mode: String) {
        val code = InstrumentationRegistry.getArguments().getString("pace_synthetic_join")
        assumeTrue("Requires the dedicated synthetic loopback test driver", !code.isNullOrBlank())
        // Enter the same UI connection control as a user. The credential is never logged or persisted.
        click("개발 시험 연결")
        compose.onNodeWithText("임시 연결 코드").performScrollTo().performTextInput(code!!)
        click("합성 개발 연결")
        assertTrue(model.connected)
        assertEquals("synthetic_dev", model.authMode)
        assertEquals("MOCK_ONLY", model.aiStatus)
        val file = File(compose.activity.cacheDir, "pace-synthetic-handoff.json")
        file.writeBytes(instrumentation.context.assets.open("pace-handoff.json").use { it.readBytes() })
        compose.runOnIdle { model.pick(resolver, Uri.fromFile(file), false) }
        settle()
        compose.onNodeWithTag("validate").performScrollTo().performClick()
        settle()
        assertEquals("REVIEW_REQUIRED", model.state)
        capture("$mode-review")
        if (mode == "simulation") click("모의 면접")
        compose.onNodeWithTag("review").assertIsNotEnabled()
        compose.onNodeWithTag("review-confirm").performScrollTo().performClick()
        compose.onNodeWithTag("review").performScrollTo().performClick()
        settle()
        assertEquals("READY", model.state)
        capture("$mode-home")
        click("한 답변에 집중")
        compose.onNodeWithTag("generate").performScrollTo().performClick()
        settle()
        assertEquals("IN_PROGRESS", model.state)
        assertEquals(5, model.questions().size)
        compose.onNodeWithTag("submit").assertIsNotEnabled()
        compose.onNodeWithTag("draft").performScrollTo().performClick().performTextInput(answer)
        val keyboard = InstrumentationRegistry.getArguments().getString("pace_keyboard") == "true"
        if (keyboard) {
            // A real OS touch establishes IME/window focus; semantics-only text injection may not.
            val point = compose.onNodeWithTag("draft").fetchSemanticsNode().boundsInWindow.center
            ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand(
                "input tap ${point.x.roundToInt()} ${point.y.roundToInt()}"
            )).use { it.readBytes() }
            compose.runOnIdle {
                WindowCompat.getInsetsController(compose.activity.window, compose.activity.window.decorView)
                    .show(WindowInsetsCompat.Type.ime())
            }
            compose.waitUntil(20000) {
                ViewCompat.getRootWindowInsets(compose.activity.window.decorView)?.isVisible(WindowInsetsCompat.Type.ime()) == true
            }
        }
        capture("$mode-interview-${if(keyboard) "keyboard" else "draft"}")
        compose.onNodeWithTag("submit").assertIsNotEnabled()
        compose.onNodeWithTag("answer-confirm").performClick()
        compose.onNodeWithTag("submit").assertIsEnabled().performClick()
        settle()
        assertEquals(answer, model.currentAnswer()?.getString("text"))
        compose.onNodeWithTag("submit").assertIsNotEnabled()
    }

    @Test fun coachingSupportsRevisionRecreationPauseAndManualFileRoundtrip() {
        start("coaching")
        compose.onNodeWithTag("answer-confirm").performClick()
        compose.onNodeWithContentDescription("홈으로").performClick()
        assertFalse(model.answerConfirmed)
        assertEquals(answer, model.answerDraft)
        click("연습 이어가기")
        compose.onNodeWithTag("draft").performScrollTo().performTextReplacement("$answer 제 역할은 초안 정리였습니다.")
        assertFalse(model.answerConfirmed)
        compose.activityRule.scenario.recreate()
        compose.waitForIdle()
        assertTrue(model.answerDraft.endsWith("초안 정리였습니다."))
        compose.onNodeWithTag("answer-confirm").performClick()
        compose.onNodeWithTag("submit").performClick()
        settle()
        assertEquals(2, model.currentAnswer()?.getInt("revision"))
        showBusyState()
        compose.onNodeWithTag("submit").assertIsNotEnabled()
        compose.onNodeWithText("연습 중지·수동 저장").performScrollTo().performClick()
        compose.waitForIdle()
        compose.onNodeWithText("일시 중지").assertIsEnabled()
        compose.onNodeWithText("평가 없이 중단 · 확인 답변 유지").assertIsEnabled()
        click("일시 중지")
        assertEquals("PAUSED", model.state)
        compose.onNodeWithTag("draft").assertIsNotEnabled()
        compose.onNodeWithTag("submit").assertDoesNotExist()
        click("연습 계속")
        val questionId = model.questionId
        compose.runOnIdle { model.prepareSnapshot() }
        settle()
        val recovery = File(compose.activity.cacheDir, "pace-synthetic-recovery.json")
        compose.runOnIdle { assertTrue(model.beginSave()); model.save(resolver, Uri.fromFile(recovery)) }
        settle()
        compose.runOnIdle { model.pick(resolver, Uri.fromFile(recovery), true) }
        settle()
        compose.onNodeWithTag("validate").performScrollTo().performClick()
        settle()
        assertEquals("REVIEW_REQUIRED", model.state)
        assertTrue(model.isRestore)
        compose.onNodeWithTag("review").assertIsNotEnabled()
        compose.onNodeWithTag("review-confirm").performScrollTo().performClick()
        compose.onNodeWithTag("review").performScrollTo().performClick()
        settle()
        click("한 답변에 집중")
        compose.runOnIdle { model.selectQuestion(questionId) }
        compose.waitForIdle()
        assertEquals(2, model.currentAnswer()?.getInt("revision"))
        click("현재 답변 AI 평가")
        assertEquals(1, model.toPaceState(PaceScreen.INTERVIEW).feedback.size)
        assertEquals(6, model.questions().size)
        click("현재 답변으로 면접 완료")
        assertEquals("COMPLETED", model.state)
        capture("coaching-result")
        click("면접 결과 파일 준비")
        val result = JSONObject(String(requireNotNull(model.exportBytes), Charsets.UTF_8))
        assertEquals("career-interview-result", result.getString("kind"))
        compose.onNodeWithTag("save").performScrollTo().assertIsEnabled()
        click("다시 이어갈 세션 파일 준비")
        val bytes = requireNotNull(model.exportBytes).copyOf()
        compose.runOnIdle { assertTrue(model.beginSave()); model.save(resolver, null) }
        assertNull(model.pendingExport)
        assertArrayEquals(bytes, model.exportBytes)
        val session = File(compose.activity.cacheDir, "pace-synthetic-session.json")
        // Resaving a shorter JSON must truncate old bytes, including an otherwise-invalid suffix.
        session.writeBytes(bytes + byteArrayOf(0))
        compose.runOnIdle { assertTrue(model.beginSave()); model.save(resolver, Uri.fromFile(session)) }
        settle()
        assertArrayEquals(bytes, session.readBytes())
        compose.runOnIdle { model.pick(resolver, Uri.fromFile(session), true) }
        settle()
        compose.onNodeWithTag("validate").performScrollTo().performClick()
        settle()
        assertEquals("COMPLETED", model.state)
        assertTrue(model.isRestore)
        assertEquals(2, model.answers().last().getInt("revision"))
        assertTrue(model.toPaceState(PaceScreen.REVIEW).feedback.isEmpty())
        compose.onNodeWithContentDescription("홈으로").performClick()
        showBusyState()
        click("연결 해제·앱 메모리 비우기")
        assertFalse(model.connected)
        assertNull(model.report)
        compose.onNodeWithText("개인 계정 로그인").assertIsDisplayed()
    }

    @Test fun simulationKeepsEvaluationHiddenUntilCompletion() {
        start("simulation")
        click("평가 준비 · 종료 후 표시")
        assertTrue(model.toPaceState(PaceScreen.INTERVIEW).feedback.isEmpty())
        compose.onNodeWithTag("feedback").assertDoesNotExist()
        compose.onNodeWithText("새로운 사실 후보 · 확인 대기").assertDoesNotExist()
        click("현재 답변으로 면접 완료")
        assertEquals("COMPLETED", model.state)
        assertEquals(1, model.toPaceState(PaceScreen.RESULT).feedback.size)
        compose.onNodeWithTag("feedback").assertExists()
        capture("simulation-result")
        compose.runOnIdle { model.disconnect() }
        settle()
    }
}
