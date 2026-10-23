package dev.careerground.interview

import android.content.ContentResolver
import android.app.Application
import android.content.Intent
import android.net.Uri
import android.util.Base64
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.UUID

class InterviewModel(application: Application) : AndroidViewModel(application) {
    // Deliberately no SavedStateHandle, rememberSaveable, file cache or preferences.
    var joinCode by mutableStateOf("")
    var connected by mutableStateOf(false); private set
    var busy by mutableStateOf(false); private set
    var message by mutableStateOf("개인 계정 또는 합성 개발 연결 · 고정 자료 면접")
        private set
    var loginIntent by mutableStateOf<Intent?>(null); private set
    var authenticating by mutableStateOf(false); private set
    var authMode by mutableStateOf(""); private set
    private var oidc: NativeOidc? = null
    var selected by mutableStateOf<ByteArray?>(null); private set
    var isRestore by mutableStateOf(false); private set
    var attachments by mutableStateOf<Map<String, ByteArray>>(emptyMap()); private set
    var preview by mutableStateOf(""); private set
    var previewPage by mutableIntStateOf(0)
    var report by mutableStateOf<JSONObject?>(null); private set
    var reviewChecked by mutableStateOf(false)
    var mode by mutableStateOf("coaching")
    var exportBytes by mutableStateOf<ByteArray?>(null); private set
    var pendingExport by mutableStateOf<ByteArray?>(null); private set
    private var client: RuntimeClient? = null
    private var ownerBinding: String? = null
    private var epoch = 0
    private var activeJob: Job? = null
    private var localHandoffHash: String? = null
    private var localCanonical: String? = null
    var aiStatus by mutableStateOf("NOT_IMPLEMENTED"); private set
    var questionId by mutableStateOf(""); private set
    var answerDraft by mutableStateOf(""); private set
    var answerConfirmed by mutableStateOf(false)
    var answerKind by mutableStateOf("text"); private set
    private var voice: DeviceVoice? = null
    var voiceVersion by mutableIntStateOf(0); private set
    val voiceStatus: String get() { voiceVersion; return voice?.status ?: "기기 내 한국어 준비 확인 전" }
    val voiceReady: Boolean get() { voiceVersion; return voice?.ready == true }
    val voiceListening: Boolean get() { voiceVersion; return voice?.listening == true }
    val localTtsReady: Boolean get() { voiceVersion; return voice?.localTtsReady == true }
    var exportKind by mutableStateOf("session"); private set
    private var voiceBase = ""
    private var pendingAnswer: JSONObject? = null
    fun questions(): List<JSONObject> = report?.optJSONObject("interview")?.optJSONArray("questions")
        ?.let { array -> (0 until array.length()).map { array.getJSONObject(it) } } ?: emptyList()
    fun answers(): List<JSONObject> = report?.optJSONObject("interview")?.optJSONArray("answers")
        ?.let { array -> (0 until array.length()).map { array.getJSONObject(it) } } ?: emptyList()
    fun currentQuestion(): JSONObject? = questions().find { it.optString("id") == questionId }
    fun currentAnswer(): JSONObject? = answers().lastOrNull { it.optString("question_id") == questionId && !it.optBoolean("stale") }

    fun selectQuestion(id: String) {
        if (busy) return
        voice?.cancel()
        questionId = id
        answerDraft = currentAnswer()?.optString("text") ?: ""
        answerConfirmed = false; answerKind = "text"; pendingAnswer = null
    }
    fun editAnswer(text: String) {
        if (text.length > 20000 || busy || voiceListening) return
        answerDraft = text; answerConfirmed = false; pendingAnswer = null
    }
    fun checkVoice() {
        val controller = voice ?: DeviceVoice(getApplication(), { voiceVersion++ }) { text, _ ->
            answerDraft = (voiceBase + " " + text).trim().take(20000)
            answerKind = "on_device_confirmed"; answerConfirmed = false; pendingAnswer = null
        }.also { voice = it }
        controller.check()
    }
    fun startVoice() {
        if (busy || state != "IN_PROGRESS" || currentQuestion() == null) return
        voiceBase = answerDraft
        answerConfirmed = false
        voice?.start()
    }
    fun stopVoice() { voice?.cancel(); answerConfirmed = false }
    fun finishVoice() { voice?.stop() }
    fun speakQuestion() { currentQuestion()?.optString("text")?.let { voice?.speak(it) } }

    fun generateQuestions() = work {
        update("questions", JSONObject())
        questionId = questions().firstOrNull { it.optString("status") == "pending" }?.getString("id") ?: ""
        message = "질문과 고정 근거를 확인하고 답변을 명시적으로 제출해 주세요."
    }
    fun submitAnswer() = work {
        require(answerConfirmed && !voiceListening && answerDraft.isNotBlank()) { "ANSWER_CONFIRMATION_REQUIRED" }
        val data = pendingAnswer ?: JSONObject().put("question_id", questionId).put("text", answerDraft)
            .put("input_kind", answerKind).put("request_id", UUID.randomUUID().toString()).put("confirmed", true)
            .also { pendingAnswer = it }
        update("answer", data)
        pendingAnswer = null; answerConfirmed = false
        message = "확인 답변 저장됨 · AI 평가·후보와 별개입니다."
    }
    fun evaluateAnswer() = work {
        update("evaluate", JSONObject().put("answer_id", requireNotNull(currentAnswer()).getString("id")))
        message = if (mode == "simulation") "평가 준비됨 · 모의 면접 종료 후 표시합니다." else "AI 피드백·pending 후보 · 사실 확정이 아닙니다."
    }
    fun skipQuestion() = work {
        voice?.cancel()
        update("skip", JSONObject().put("question_id", questionId))
        questionId = ""; answerDraft = ""; answerConfirmed = false
        message = "질문 건너뛰기 · 다음 질문을 선택해 주세요."
    }
    fun finishInterview() = work {
        voice?.cancel(); update("finish", JSONObject())
        message = "면접 완료 · 결과와 질문 추적 세션을 각각 내보낼 수 있습니다."
    }
    fun interruptSession(action: String) {
        activeJob?.cancel(); epoch++; busy = false; voice?.cancel(); transition(action)
    }
    fun disconnect() { activeJob?.cancel(); epoch++; busy = false; voice?.cancel(); logout() }
    val state: String get() = report?.optString("state") ?: "EMPTY"
    val sessionId: String? get() = report?.optString("session_id")

    private fun work(task: suspend () -> Unit) {
        if (busy) return
        busy = true
        val generation = epoch
        activeJob = viewModelScope.launch {
            try { task() }
            catch (error: Exception) {
                val code = error.message?.takeIf { it.length <= 256 &&
                    Regex("[A-Z0-9_\\[\\]\", :]+").matches(it) } ?: "CONNECTION_OR_FILE_ERROR"
                if (generation == epoch) message = "작업 실패 [$code] · 선택 파일과 연결을 확인해 주세요."
            } finally { if (generation == epoch) busy = false }
        }
    }

    fun connect() = work {
        require(!connected && !authenticating)
        val candidate = RuntimeClient(joinCode.trim())
        val result = withContext(Dispatchers.IO) { candidate.request("/v1/status") }
        val status = JSONObject(String(result, Charsets.UTF_8))
        require(status.getString("auth_mode") == "synthetic_dev")
        client = candidate
        ownerBinding = status.getString("owner")
        joinCode = ""
        connected = true
        authMode = "synthetic_dev"
        aiStatus = status.optString("ai_status", "NOT_IMPLEMENTED")
        message = "합성 개발 연결됨 · 실제 개인 계정 로그인이 아닙니다."
    }

    fun login() = work {
        require(!connected && !authenticating)
        val login = oidc ?: NativeOidc(getApplication()).also { oidc = it }
        loginIntent = login.begin()
        authenticating = true
        message = "외부 브라우저에서 로그인해 주세요. 앱은 비밀번호를 받지 않습니다."
    }

    fun consumeLoginIntent(): Intent? = loginIntent.also { loginIntent = null }

    fun completeLogin(data: Intent?) = work {
        var candidate: RuntimeClient? = null
        try {
            val token = requireNotNull(oidc).complete(data)
            candidate = RuntimeClient(token.accessToken, token.expiresAtMillis)
            val status = JSONObject(String(withContext(Dispatchers.IO) {
                candidate.request("/v1/status")
            }, Charsets.UTF_8))
            require(status.getString("auth_mode") == "oidc") { "OIDC_RUNTIME_MODE_MISMATCH" }
            client = candidate; ownerBinding = status.getString("owner")
            connected = true; authMode = "oidc"; joinCode = ""
            aiStatus = status.optString("ai_status", "NOT_IMPLEMENTED")
            message = "개인 계정 연결됨 · runtime 서명·사용자 검증 통과 · 합성 자료로 시험 중"
        } catch (error: Exception) {
            candidate?.clear()
            throw error
        } finally { authenticating = false; oidc?.cancel() }
    }

    fun pick(resolver: ContentResolver, uri: Uri?, restore: Boolean) {
        if (uri == null) { message = "파일 선택 취소 · 기존 선택 유지"; return }
        work {
            val raw = withContext(Dispatchers.IO) { SelectedFiles.read(resolver, uri,
                if (restore) SelectedFiles.SESSION_LIMIT else SelectedFiles.JSON_LIMIT) }
            val data = SelectedFiles.strictObject(raw,
                if (restore) SelectedFiles.SESSION_LIMIT else SelectedFiles.JSON_LIMIT)
            require(data.getString("kind") == if (restore) "career-interview-session" else "career-handoff")
            require(data.getString("schema_version") == if (restore) "0.1" else "1.0")
            val hash = if (restore) {
                val original = Base64.decode(data.getString("handoff_base64"), Base64.NO_WRAP)
                require(original.size <= SelectedFiles.JSON_LIMIT)
                data.getString("raw_sha256").also { require(it == SelectedFiles.sha256(original)) }
            } else SelectedFiles.sha256(raw)
            // Parse before replacing. Never silently change a pinned session.
            val old = sessionId
            if (old != null) withContext(Dispatchers.IO) {
                try { client?.request("/v1/sessions/$old", "DELETE") }
                catch (error: IllegalStateException) {
                    if (error.message != "[\"SESSION_UNAVAILABLE\"]") throw error
                }
            }
            selected = raw
            isRestore = restore
            attachments = emptyMap()
            preview = data.toString(2)
            previewPage = 0
            report = null
            localCanonical = null
            exportBytes = null
            reviewChecked = false
            questionId = ""; answerDraft = ""; answerConfirmed = false; voice?.cancel()
            localHandoffHash = hash
            message = "로컬 미리보기 · 전체 구조 검사는 아직입니다. 검사를 누르면 선택 자료를 PC로 보냅니다."
        }
    }

    fun pickAttachments(resolver: ContentResolver, uris: List<Uri>) {
        if (uris.isEmpty()) { message = "첨부 선택 취소 · 기존 선택 유지"; return }
        if (report != null) { message = "고정 자료 변경은 handoff를 다시 선택해 주세요."; return }
        work {
            val chosen = withContext(Dispatchers.IO) {
                require(uris.size <= 500)
                val files = linkedMapOf<String, ByteArray>()
                var total = 0
                for (uri in uris) {
                    val name = SelectedFiles.name(resolver, uri)
                    require(name !in files) { "DUPLICATE_ATTACHMENT_PATH" }
                    val bytes = SelectedFiles.read(resolver, uri, SelectedFiles.ATTACHMENT_LIMIT)
                    total += bytes.size
                    require(total <= SelectedFiles.ATTACHMENTS_TOTAL) { "ATTACHMENT_TOTAL_LIMIT" }
                    files[name] = bytes
                }
                files.toMap()
            }
            attachments = chosen
            message = "첨부 ${chosen.size}개 선택 · 아직 전체 검사 전"
        }
    }

    fun validate() = work {
        require(report == null)
        val active = requireNotNull(client)
        val raw = requireNotNull(selected)
        val payload = JSONObject().put(if (isRestore) "session_base64" else "handoff_base64",
            Base64.encodeToString(raw, Base64.NO_WRAP)).put("attachments", JSONObject().apply {
                attachments.forEach { (name, data) -> put(name, Base64.encodeToString(data, Base64.NO_WRAP)) }
            })
        val result = withContext(Dispatchers.IO) {
            active.request(if (isRestore) "/v1/restore" else "/v1/import", "POST", payload)
        }
        val parsed = JSONObject(String(result, Charsets.UTF_8))
        require(parsed.getString("raw_sha256") == localHandoffHash) { "HANDOFF_CONFLICT" }
        localCanonical = parsed.getString("canonical_digest")
        report = parsed
        mode = parsed.getString("mode")
        message = "구조·참조 검사 통과 · 내용·개인정보 검토와 사실의 외부 인증은 별개입니다."
    }

    fun review() = work {
        require(reviewChecked)
        update("review", JSONObject().put("canonical_digest", localCanonical)
            .put("record", "앱에서 고정 ID·버전·포함 자료·기여 경계·제외 범위를 검토하고 확인함")
            .put("mode", mode))
        message = "포함 범위 확인됨 · 고정 세션 준비 완료"
    }

    fun transition(action: String) = work {
        if (action != "start" && action != "continue") voice?.cancel()
        update("transition", JSONObject().put("action", action))
        message = if (state == "IN_PROGRESS") "고정 자료 면접 · 질문 생성 전에 AI 전달 범위를 확인해 주세요." else "상태: $state"
    }

    private suspend fun update(action: String, payload: JSONObject) {
        val sid = requireNotNull(sessionId)
        val active = requireNotNull(client)
        val generation = epoch
        val bytes = withContext(Dispatchers.IO) { active.request("/v1/sessions/$sid/$action", "POST", payload) }
        check(generation == epoch) { "STALE_RESPONSE" }
        val next = JSONObject(String(bytes, Charsets.UTF_8))
        require(next.getString("session_id") == sid && next.getString("canonical_digest") == localCanonical
            && next.getString("raw_sha256") == localHandoffHash) { "HANDOFF_CONFLICT" }
        report = next
        exportBytes = null
    }

    fun prepareExport() = work {
        val active = requireNotNull(client)
        val sid = requireNotNull(sessionId)
        try {
            exportBytes = withContext(Dispatchers.IO) { active.request("/v1/sessions/$sid/export") }
            exportKind = "session"
            message = "수동 세션 파일 준비됨 · 저장 위치 선택 전"
        } catch (error: IllegalStateException) {
            if (error.message != "[\"SESSION_UNAVAILABLE\"]") throw error
            prepareSnapshotBytes()
        }
    }


    fun prepareSnapshot() = work { prepareSnapshotBytes() }
    private fun prepareSnapshotBytes() {
        val raw = requireNotNull(selected)
        val original = if (isRestore) Base64.decode(SelectedFiles.strictObject(raw, SelectedFiles.SESSION_LIMIT)
            .getString("handoff_base64"), Base64.NO_WRAP) else raw
        exportBytes = ManualSessionSnapshot.create(requireNotNull(report), original, requireNotNull(ownerBinding), authMode)
        exportKind = "session"
        message = "화면 기록 복구 파일 준비됨 · 미제출 초안·숨긴 평가는 제외 · 재가져온 뒤 다시 검토 필요"
    }

    fun prepareResult() = work {
        val active = requireNotNull(client)
        val sid = requireNotNull(sessionId)
        exportBytes = withContext(Dispatchers.IO) { active.request("/v1/sessions/$sid/result") }
        exportKind = "result"
        message = "result 1.0 준비됨 · 사용자 답변 / AI 평가 / pending 후보 · 경력 자동 반영 없음"
    }

    fun beginSave(): Boolean {
        pendingExport = exportBytes?.copyOf()
        return pendingExport != null
    }

    fun save(resolver: ContentResolver, uri: Uri?) {
        val bytes = pendingExport
        pendingExport = null
        if (uri == null) { message = "저장 취소 · 세션은 메모리에 유지"; return }
        if (bytes == null) { message = "프로세스 재시작으로 저장 내용이 없습니다. 파일을 다시 준비해 주세요."; return }
        work {
            withContext(Dispatchers.IO) {
                requireNotNull(resolver.openOutputStream(uri, "wt")).use { it.write(bytes); it.flush() }
            }
            message = "파일 쓰기 완료 · 세션을 다시 가져와 검사할 수 있습니다."
        }
    }

    fun logout() = work {
        val active = client
        try { withContext(Dispatchers.IO) { active?.request("/v1/logout", "POST") } }
        finally {
            active?.clear(); oidc?.cancel()
            epoch++
            authMode = ""; authenticating = false; loginIntent = null
            connected = false; joinCode = ""; client = null; ownerBinding = null; selected = null
            attachments = emptyMap(); preview = ""; report = null; reviewChecked = false
            exportBytes = null; pendingExport = null; localCanonical = null; localHandoffHash = null
            questionId = ""; answerDraft = ""; answerConfirmed = false; pendingAnswer = null
            aiStatus = "NOT_IMPLEMENTED"; voice?.dispose(); voice = null
            busy = false
            message = "앱 메모리 해제 · 저장 파일과 브라우저 로그인은 별도로 유지됩니다."
        }
    }

    override fun onCleared() {
        voice?.dispose()
        client?.clear(); oidc?.dispose()
        super.onCleared()
    }
}
