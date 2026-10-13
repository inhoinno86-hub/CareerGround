package dev.careerground.interview

import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant

/** Explicit manual export of the current RAM view, including after runtime expiry.
 * Unsubmitted drafts and evaluations hidden in simulation mode are not in the view.
 * Import always rechecks owner, exact handoff and records; this is not a signed receipt.
 */
internal object ManualSessionSnapshot {
    fun create(report: JSONObject, original: ByteArray, owner: String, authMode: String): ByteArray {
        require(owner.isNotBlank() && authMode in setOf("oidc", "synthetic_dev"))
        require(report.getString("auth_mode") == authMode)
        require(SelectedFiles.sha256(original) == report.getString("raw_sha256")) { "HANDOFF_CONFLICT" }
        val handoff = SelectedFiles.strictObject(original)
        require(handoff.getString("kind") == "career-handoff" && handoff.getString("schema_version") == "1.0")
        require(handoff.getString("handoff_id") == report.getJSONObject("handoff").getString("handoff_id"))
        val now = Instant.now().toString()
        val data = JSONObject().put("kind", "career-interview-session").put("schema_version", "0.1")
            .put("session_id", report.getString("session_id")).put("owner_binding", owner)
            .put("created_at", report.optString("created_at", now)).put("exported_at", now)
            .put("handoff_base64", Base64.encodeToString(original, Base64.NO_WRAP))
            .put("handoff_ref", JSONObject().put("id", handoff.getString("handoff_id"))
                .put("sha256", report.getString("canonical_digest")))
            .put("raw_sha256", report.getString("raw_sha256")).put("state", report.getString("state"))
            .put("mode", report.getString("mode")).put("review", report.opt("review") ?: JSONObject.NULL)
            .put("auth_mode", authMode)
        for (key in listOf("questions", "answers", "feedback", "candidates", "events")) {
            data.put(key, JSONArray(report.optJSONObject("interview")?.optJSONArray(key)?.toString() ?: "[]"))
        }
        return data.toString().toByteArray(Charsets.UTF_8).also { require(it.size <= SelectedFiles.SESSION_LIMIT) }
    }
}
