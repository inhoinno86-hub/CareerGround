package dev.careerground.interview

import android.app.Application
import androidx.compose.runtime.MutableState
import androidx.test.platform.app.InstrumentationRegistry
import dev.careerground.pace.PaceScreen
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PaceAdapterTest {
    private fun model(state:String="IN_PROGRESS",mode:String="coaching"):InterviewModel {
        val app=InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as Application
        val model=InterviewModel(app)
        val report=JSONObject("""{
            "state":"$state","mode":"$mode","handoff":{
                "profile_ref":{"id":"p","version":2},"jd_ref":{"id":"j","version":1},"resume_ref":{"id":"r","version":1},
                "selection":{"fact_ids":["f1"],"source_ids":["s1"]},
                "workspace":{"artifacts":[
                    {"kind":"profile","id":"p","version":2,"payload":{"facts":[{"id":"f1","text":"선택한 경험"},{"id":"f-secret","text":"선택하지 않은 경험"}],"sources":[{"id":"s1","text":"선택한 근거"},{"id":"s-secret","text":"선택하지 않은 근거"}]}},
                    {"kind":"jd","id":"j","version":99,"payload":{"title":"다른 버전 공고"}},
                    {"kind":"jd","id":"j","version":1,"payload":{"title":"선택한 공고"}},
                    {"kind":"resume","id":"r","version":1,"payload":{"sentences":[]}}
                ]}},
            "interview":{
                "questions":[{"id":"q1","text":"역할을 알려주세요.","status":"answered"}],
                "answers":[{"question_id":"q1","text":"이전 답변","revision":1,"stale":true},{"question_id":"q1","text":"확인 답변","revision":2,"stale":false}],
                "feedback":[{"answer_id":"a1","stale":false,"rubric":[{"criterion":"기여","text":"현재 평가","answer_quote":"확인 답변"}]},{"answer_id":"old","stale":true,"rubric":[{"text":"이전 평가"}]}],
                "candidates":[{"text":"확인 대기 후보","stale":false},{"text":"이전 후보","stale":true}]
            }}""")
        // Inject synthetic response data only; no connection, picker, voice or AI calls.
        @Suppress("UNCHECKED_CAST")
        val holder=InterviewModel::class.java.getDeclaredField("report\$delegate").apply{isAccessible=true}.get(model) as MutableState<JSONObject?>
        holder.value=report
        model.mode=mode
        model.selectQuestion("q1")
        return model
    }
    @Test fun simulationDoesNotExposeEvaluationOrCandidatesBeforeTerminalState() {
        val ui=model(mode="simulation").toPaceState(PaceScreen.INTERVIEW)
        assertTrue(ui.feedback.isEmpty());assertTrue(ui.candidates.isEmpty());assertFalse(ui.showFeedback)
    }
    @Test fun completedSimulationShowsOnlyCurrentRecordsAndConfirmedRevision() {
        val ui=model("COMPLETED","simulation").toPaceState(PaceScreen.RESULT)
        assertEquals(1,ui.feedback.size);assertEquals(listOf("확인 대기 후보"),ui.candidates)
        assertEquals("확인 답변",ui.answers.single().text);assertEquals(2,ui.answers.single().revision)
    }
    @Test fun reviewUsesFixedVersionAndSelectedFactAndSourceIds() {
        val ui=model("REVIEW_REQUIRED").toPaceState(PaceScreen.REVIEW)
        assertEquals("선택한 공고",ui.role)
        val sections=ui.reviewSections.joinToString("\n"){it.text}
        assertTrue(sections.contains("선택한 경험"));assertTrue(sections.contains("선택한 근거"))
        assertFalse(sections.contains("선택하지 않은 경험"));assertFalse(sections.contains("선택하지 않은 근거"))
    }
    @Test fun draftEditInvalidatesConfirmationAndPausedSubmissionIsDisabled() {
        val model=model();model.answerConfirmed=true;model.editAnswer("수정 초안")
        assertFalse(model.toPaceState(PaceScreen.INTERVIEW).confirmed)
        val ui=model("PAUSED").toPaceState(PaceScreen.INTERVIEW).copy(confirmed=true,draft="수정 초안")
        assertFalse(ui.canSubmit)
    }
}
