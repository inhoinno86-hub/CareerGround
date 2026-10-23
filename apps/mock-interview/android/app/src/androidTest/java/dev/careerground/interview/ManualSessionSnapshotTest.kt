package dev.careerground.interview

import android.util.Base64
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ManualSessionSnapshotTest {
    private val raw = """{"kind":"career-handoff","schema_version":"1.0","handoff_id":"snapshot-synthetic"}""".toByteArray()
    private fun report() = JSONObject("""{
        "session_id":"session-synthetic", "auth_mode":"oidc", "state":"IN_PROGRESS", "mode":"coaching",
        "handoff":{"handoff_id":"snapshot-synthetic"}, "canonical_digest":"${"a".repeat(64)}",
        "raw_sha256":"${SelectedFiles.sha256(raw)}", "created_at":"2026-10-11T01:00:00Z", "review":null,
        "answerDraft":"unsubmitted and excluded",
        "interview":{"questions":[],"answers":[{"id":"confirmed-original","text":"동료가 배포했습니다."}],
        "feedback":[],"candidates":[],"events":[]}
    }""")
    @Test fun preservesVisibleRecordsAndOriginalBytesWithoutSubmittingDraft() {
        val view = report(); val before = view.toString()
        val data = JSONObject(String(ManualSessionSnapshot.create(view, raw, "owner-synthetic", "oidc")))
        assertEquals("career-interview-session", data.getString("kind"))
        assertEquals("0.1", data.getString("schema_version"))
        assertArrayEquals(raw, Base64.decode(data.getString("handoff_base64"), Base64.NO_WRAP))
        assertEquals("owner-synthetic", data.getString("owner_binding"))
        assertEquals("2026-10-11T01:00:00Z", data.getString("created_at"))
        assertEquals(view.getJSONObject("interview").getJSONArray("answers").toString(), data.getJSONArray("answers").toString())
        assertFalse(data.has("answerDraft")); assertEquals(before, view.toString())
    }
    @Test fun rejectsWrongOriginalOrAuthenticationMode() {
        assertThrows(IllegalArgumentException::class.java) { ManualSessionSnapshot.create(report(), raw + 32.toByte(), "owner-synthetic", "oidc") }
        assertThrows(IllegalArgumentException::class.java) { ManualSessionSnapshot.create(report(), raw, "owner-synthetic", "synthetic_dev") }
        assertThrows(IllegalArgumentException::class.java) { ManualSessionSnapshot.create(report(), raw, "", "oidc") }
    }
    @Test fun simulationSnapshotDoesNotInventHiddenEvaluations() {
        val view = report().put("mode", "simulation")
        val data = JSONObject(String(ManualSessionSnapshot.create(view, raw, "owner-synthetic", "oidc")))
        assertEquals("simulation", data.getString("mode"))
        assertEquals(0, data.getJSONArray("feedback").length())
        assertEquals(0, data.getJSONArray("candidates").length())
    }
}
