package dev.careerground.interview

import org.junit.Assert.*
import org.junit.Test

class VoiceCaptureTest {
    @Test fun earlyUtteranceResultContinuesAndLaterSentencesAccumulate() {
        val window = VoiceCaptureWindow(); val draft = VoiceTranscript()
        window.begin(0); val first = window.nextAttempt(0)!!; draft.beginAttempt()
        draft.partial("2024년 3월"); draft.final("2024년 3월부터 6월까지 정리했습니다.")
        assertEquals(VoiceCaptureWindow.Next.CONTINUE, window.terminal(first, 3000))
        assertTrue(window.active)
        val second = window.nextAttempt(3200)!!; draft.beginAttempt()
        draft.partial("배포 실행은"); draft.final("배포 실행은 동료가 담당했습니다.")
        assertEquals(VoiceCaptureWindow.Next.CONTINUE, window.terminal(second, 6000))
        assertEquals("2024년 3월부터 6월까지 정리했습니다. 배포 실행은 동료가 담당했습니다.", draft.text)
    }
    @Test fun segmentedResultsReplaceHypothesesAndDoNotDuplicateAggregate() {
        val draft = VoiceTranscript(); draft.beginAttempt()
        draft.partial("2023년"); draft.partial("2024년")
        draft.segment("2024년 정리했습니다."); draft.partial("동료가")
        draft.segment("동료가 배포했습니다.")
        draft.final("2024년 정리했습니다. 동료가 배포했습니다.")
        assertEquals("2024년 정리했습니다. 동료가 배포했습니다.", draft.text)
    }
    @Test fun stopBetweenUtterancesPreventsScheduledRestart() {
        val window = VoiceCaptureWindow(); window.begin(0)
        val token = window.nextAttempt(0)!!
        assertEquals(VoiceCaptureWindow.Next.CONTINUE, window.terminal(token, 10))
        window.requestStop()
        assertNull(window.nextAttempt(210)); assertFalse(window.canContinue(210))
    }
    @Test fun explicitStopAllowsLastResultButNeverRestarts() {
        val window = VoiceCaptureWindow(); window.begin(0); val token = window.nextAttempt(0)!!
        window.requestStop(); assertTrue(window.accepts(token))
        assertEquals(VoiceCaptureWindow.Next.FINISH, window.terminal(token, 20))
        assertNull(window.nextAttempt(220))
    }
    @Test fun twoMinuteDeadlineIsNotResetByUtteranceResults() {
        val window = VoiceCaptureWindow(); window.begin(0)
        val first = window.nextAttempt(0)!!; window.terminal(first, 60000)
        val second = window.nextAttempt(60200)!!
        assertEquals(VoiceCaptureWindow.Next.FINISH, window.terminal(second, 120000))
        assertNull(window.nextAttempt(120200))
    }
    @Test fun cancelAndNewCaptureRejectOldOrDuplicateCallbacks() {
        val window = VoiceCaptureWindow(); val oldSession = window.begin(0)
        val old = window.nextAttempt(0)!!; window.cancel()
        assertFalse(window.accepts(old)); assertEquals(VoiceCaptureWindow.Next.IGNORE, window.terminal(old, 10))
        assertNotEquals(oldSession, window.begin(20)); val fresh = window.nextAttempt(20)!!
        assertFalse(window.accepts(old)); assertTrue(window.accepts(fresh))
        window.terminal(fresh, 30)
        assertEquals(VoiceCaptureWindow.Next.IGNORE, window.terminal(fresh, 30))
    }
    @Test fun timeoutKeepsUnconfirmedPartialAndNewAttemptDoesNotOverwriteIt() {
        val draft = VoiceTranscript(); draft.beginAttempt(); draft.partial("미측정입니다")
        draft.preservePartial(); draft.beginAttempt(); draft.partial("동료 의견")
        assertEquals("미측정입니다 동료 의견", draft.text)
    }
    @Test fun finalCorrectionAtCharacterLimitIsRetainedAndBounded() {
        val draft = VoiceTranscript(8); draft.beginAttempt(); draft.partial("12345678")
        draft.final("corrected"); assertEquals("correcte", draft.text)
        draft.segment("overflow"); assertEquals(8, draft.text.length)
    }
}
