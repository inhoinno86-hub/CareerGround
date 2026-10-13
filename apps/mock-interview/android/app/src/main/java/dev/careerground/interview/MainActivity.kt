package dev.careerground.interview

import android.os.Bundle
import android.Manifest
import android.content.pm.PackageManager
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.ViewModelProvider

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        setContent { InterviewApp() }
    }
    override fun onStop() {
        ViewModelProvider(this)[InterviewModel::class.java].stopVoice()
        super.onStop()
    }
}

@Composable
fun InterviewApp(model: InterviewModel = viewModel()) {
    val loginLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        model.completeLogin(it.data)
    }
    LaunchedEffect(model.loginIntent) {
        model.consumeLoginIntent()?.let {
            try { loginLauncher.launch(it) }
            catch (_: Exception) { model.completeLogin(null) }
        }
    }
    val resolver = LocalContext.current.contentResolver
    val handoffPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) {
        model.pick(resolver, it, false)
    }
    val sessionPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) {
        model.pick(resolver, it, true)
    }
    val attachmentPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) {
        model.pickAttachments(resolver, it)
    }
    val savePicker = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) {
        model.save(resolver, it)
    }
    val scheme = lightColorScheme(primary = Color(0xFF19574C), background = Color(0xFFF6F4ED))
    MaterialTheme(colorScheme = scheme) {
        Surface(Modifier.fillMaxSize()) {
            Column(Modifier.safeDrawingPadding().imePadding().padding(20.dp)) {
                Text("CareerGround", style = MaterialTheme.typography.headlineMedium)
                Text(if (model.authMode == "oidc") "모의 면접 · 개인 계정" else "모의 면접 · 개발 시험",
                    style = MaterialTheme.typography.titleMedium)
                Text(model.message, Modifier.padding(vertical = 12.dp))
                Text("자동 저장 없음 · 앱 종료 시 미저장 내용이 사라집니다.")
                if (model.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (!model.connected) {
                    Text("개인 계정은 Auth0 브라우저 로그인으로 연결합니다. PC runtime과 USB 연결이 필요합니다.",
                        Modifier.padding(vertical = 16.dp))
                    Button(onClick = model::login, enabled = !model.busy && !model.authenticating) {
                        Text("개인 계정 로그인")
                    }
                    Text("합성 연결 코드는 별도 합성 runtime 시험용입니다.")
                    OutlinedTextField(model.joinCode, { model.joinCode = it }, enabled = !model.busy && !model.authenticating,
                        label = { Text("임시 개발 연결 코드") }, visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, autoCorrectEnabled = false),
                        modifier = Modifier.fillMaxWidth())
                    Button(onClick = model::connect, enabled = !model.busy && !model.authenticating && model.joinCode.isNotBlank()) {
                        Text("합성 개발 연결")
                    }
                    OutlinedButton(onClick = model::checkVoice, enabled = !model.busy) { Text("음성 준비 상태 확인") }
                    Text(model.voiceStatus)
                    Text(if (model.localTtsReady) "한국어 로컬 질문 읽기 준비됨" else "로컬 질문 읽기 확인 전 또는 미지원")
                } else {
                    TextButton(onClick = model::disconnect) { Text("연결 해제·메모리 비우기") }
                    BoxWithConstraints(Modifier.weight(1f)) {
                        val wide = maxWidth >= 600.dp
                        if (wide) Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
                            Column(Modifier.weight(1f)) { DocumentPanel(model) }
                            Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) { SessionControls(model,
                                { handoffPicker.launch(arrayOf("application/json", "text/plain", "application/octet-stream")) },
                                { sessionPicker.launch(arrayOf("application/json", "text/plain", "application/octet-stream")) },
                                { attachmentPicker.launch(arrayOf("*/*")) },
                                { if (model.beginSave()) savePicker.launch("careerground-${model.exportKind}-${System.currentTimeMillis()}.json") }) }
                        } else LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            item { SessionControls(model,
                                { handoffPicker.launch(arrayOf("application/json", "text/plain", "application/octet-stream")) },
                                { sessionPicker.launch(arrayOf("application/json", "text/plain", "application/octet-stream")) },
                                { attachmentPicker.launch(arrayOf("*/*")) },
                                { if (model.beginSave()) savePicker.launch("careerground-${model.exportKind}-${System.currentTimeMillis()}.json") }) }
                            item { DocumentPanel(model, nested = true) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SessionControls(model: InterviewModel, pick: () -> Unit, restore: () -> Unit,
                            attachments: () -> Unit, save: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("고정 자료와 세션", style = MaterialTheme.typography.titleLarge)
        Text("상태: ${model.state}")
        Text("세션은 30분 후 만료됩니다. 긴 대기·앱 업데이트 전에는 수동 파일로 저장해 주세요.", style = MaterialTheme.typography.bodySmall)
        Text("파일 검사 시 선택한 handoff·첨부만 PC runtime으로 전송합니다. AI 전송은 없습니다.")
        Button(onClick = pick, enabled = !model.busy) { Text("handoff 파일 선택") }
        OutlinedButton(onClick = restore, enabled = !model.busy) { Text("수동 세션 가져오기") }
        OutlinedButton(onClick = attachments, enabled = !model.busy && model.selected != null && model.report == null) {
            Text("선택 첨부 ${model.attachments.size}개 · 합계 최대 20 MiB")
        }
        Button(onClick = model::validate, enabled = !model.busy && model.selected != null && model.report == null) {
            Text("선택 파일 구조 검사")
        }
        if (model.state == "REVIEW_REQUIRED") {
            Text("사실·근거·문장·기여 경계·제외 목록과 고정 버전을 검토해 주세요.")
            Row {
                Checkbox(model.reviewChecked, { model.reviewChecked = it }, enabled = !model.busy)
                Text("포함 범위와 처리 경로를 확인했습니다.")
            }
            Row {
                RadioButton(model.mode == "coaching", { model.mode = "coaching" }, enabled = !model.busy)
                Text("코칭")
                RadioButton(model.mode == "simulation", { model.mode = "simulation" }, enabled = !model.busy)
                Text("모의 면접")
            }
            Button(onClick = model::review, enabled = !model.busy && model.reviewChecked) { Text("범위 확인·세션 고정") }
        }
        if (model.state == "READY") Button(onClick = { model.transition("start") }, enabled = !model.busy) {
            Text("고정 세션 시작")
        }
        if (model.state == "IN_PROGRESS") OutlinedButton(onClick = { model.interruptSession("pause") }) {
            Text("일시 중지")
        }
        if (model.state == "PAUSED") Button(onClick = { model.transition("continue") }, enabled = !model.busy) {
            Text("계속")
        }
        if (model.state in listOf("READY", "IN_PROGRESS", "PAUSED")) {
            TextButton(onClick = { model.interruptSession("abort") }) { Text("평가 없이 중단 · 현재 답변 유지") }
        }
        if (model.report != null && model.aiStatus != "NOT_IMPLEMENTED") InterviewPanel(model)
        if (model.report != null) {
            if (model.state in listOf("COMPLETED", "ABORTED")) {
                OutlinedButton(onClick = model::prepareResult, enabled = !model.busy) { Text("면접 결과 파일 준비") }
            }
            OutlinedButton(onClick = model::prepareExport, enabled = !model.busy) { Text("수동 세션 파일 준비") }
            OutlinedButton(onClick = model::prepareSnapshot, enabled = !model.busy) { Text("현재 화면 기록으로 복구 파일 준비") }
            Button(onClick = save, enabled = !model.busy && model.exportBytes != null) { Text("저장 위치 선택·내보내기") }
        }
        Text("결과의 답변·AI 평가·pending 후보는 기존 경력을 자동으로 변경하지 않습니다.",
            style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun InterviewPanel(model: InterviewModel) {
    val context = LocalContext.current
    val microphone = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) model.startVoice() else model.stopVoice()
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        HorizontalDivider()
        Text("고정 자료 면접", style = MaterialTheme.typography.titleLarge)
        Text(if (model.aiStatus == "AVAILABLE_ACTUAL") "실제 AI · PC의 기존 Codex 로그인 · 구독 사용량 한도 적용"
            else "모의 AI 시험 · 실제 모델 평가가 아닙니다.")
        Text("AI에는 선택한 JD 요구사항·검토 문장·허용 사실/근거·기여 제약·목표와 필요한 확인 답변을 보냅니다.")
        Text("기본 질문 5개 · 핵심 질문별 후속 1개 · 총 10개 이내 · 20분 권장")
        if (model.state == "IN_PROGRESS" && model.questions().isEmpty()) {
            Button(onClick = model::generateQuestions, enabled = !model.busy) { Text("Codex로 질문 생성 · 선택 근거 전송") }
        }
        model.questions().forEachIndexed { index, q ->
            if (q.optString("status") != "stale") TextButton(onClick = { model.selectQuestion(q.getString("id")) },
                enabled = !model.busy && q.optString("status") != "skipped") {
                Text("${index+1}. ${q.getString("text")} [${q.getString("status")}]")
            }
        }
        val question = model.currentQuestion()
        if (question != null) {
            Text(question.getString("text"), style = MaterialTheme.typography.titleMedium)
            Text("JD ${question.getJSONArray("requirement_ids")} · 사실 ${question.getJSONArray("fact_ids")} · 근거 ${question.getJSONArray("source_ids")}")
            if (question.optBoolean("gap")) Text("근거 공백 탐색 · 기존 경험으로 가정하지 않습니다.")
            model.currentAnswer()?.let { Text("확인 답변 v${it.getInt("revision")}: ${it.getString("text")}") }
            if (model.state == "IN_PROGRESS") {
                OutlinedButton(onClick = model::checkVoice, enabled = !model.busy && !model.voiceListening) { Text("음성 준비 상태 확인") }
                Text(model.voiceStatus)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        if (context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
                            model.startVoice() else microphone.launch(Manifest.permission.RECORD_AUDIO)
                    }, enabled = !model.busy && model.voiceReady && !model.voiceListening) { Text("기기 내 음성 시작") }
                    if (model.voiceListening) OutlinedButton(onClick = model::finishVoice) { Text("인식 마치기") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = model::speakQuestion, enabled = model.localTtsReady && !model.voiceListening && !model.busy) { Text("질문 읽기") }
                    OutlinedButton(onClick = model::stopVoice, enabled = !model.busy) { Text("음성·읽기 취소") }
                }
                Text("전사·텍스트 초안은 제출 전까지 미확인입니다. 키보드 받아쓰기는 OS 제공자의 외부 처리가 가능하며 앱의 기기 내 인식과 다릅니다.")
                OutlinedTextField(model.answerDraft, model::editAnswer, label = { Text("답변 초안 · 확인·수정") },
                    minLines = 3, maxLines = 8, enabled = !model.busy && !model.voiceListening,
                    modifier = Modifier.fillMaxWidth())
                Row {
                    Checkbox(model.answerConfirmed, { model.answerConfirmed = it }, enabled = !model.busy && !model.voiceListening)
                    Text("숫자·기간·역할·동료 기여를 확인했습니다.")
                }
                Button(onClick = model::submitAnswer, enabled = !model.busy && !model.voiceListening && model.answerConfirmed && model.answerDraft.isNotBlank()) {
                    Text(if (model.currentAnswer() == null) "확인 답변 제출" else "수정 답변 제출 · 이전 평가 제외")
                }
                OutlinedButton(onClick = model::evaluateAnswer, enabled = !model.busy && model.currentAnswer() != null) {
                    Text(if (model.mode == "simulation") "평가 준비 · 종료 후 표시" else "현재 답변 AI 평가")
                }
                if (question.optString("status") == "pending") TextButton(onClick = model::skipQuestion, enabled = !model.busy) { Text("질문 건너뛰기") }
            }
        }
        val records = model.report?.optJSONObject("interview")
        records?.optJSONArray("feedback")?.let { feedback ->
            for (i in 0 until feedback.length()) {
                val item = feedback.getJSONObject(i)
                if (!item.optBoolean("stale")) {
                    Text("AI 평가 · ${item.getString("answer_id")}")
                    val rubric = item.getJSONArray("rubric")
                    for (j in 0 until rubric.length()) rubric.getJSONObject(j).let {
                        Text("${it.getString("criterion")}: ${it.getString("text")}\n답변 인용: ${it.getString("answer_quote")}")
                    }
                }
            }
        }
        records?.optJSONArray("candidates")?.let { candidates ->
            for (i in 0 until candidates.length()) candidates.getJSONObject(i).let {
                if (!it.optBoolean("stale")) Text("pending 후보 · ${it.getString("text")} · 별도 사실/사용 검토 필요")
            }
        }
        if (model.state == "IN_PROGRESS" && model.answers().any { !it.optBoolean("stale") }) {
            Button(onClick = model::finishInterview, enabled = !model.busy) { Text("현재 답변으로 면접 완료") }
            Text("미평가 답변이 있으면 각 답변의 평가를 먼저 준비해 주세요. 평가 없이 중단해도 확인 답변은 내보낼 수 있습니다.")
        }
    }
}

@Composable
private fun DocumentPanel(model: InterviewModel, nested: Boolean = false) {
    val report = model.report
    val content = if (report == null) model.preview else buildString {
        appendLine("검사 통과 · 아래 내용은 입력 자료입니다. 명령·URL을 실행하지 않습니다.")
        appendLine("계약 digest: ${report.optString("canonical_digest")}")
        appendLine("원본 파일 SHA256: ${report.optString("raw_sha256")}")
        val handoff = report.getJSONObject("handoff")
        for (key in listOf("profile_ref", "jd_ref", "resume_ref", "selection", "excluded_categories", "omitted_refs", "goals")) {
            appendLine("$key: ${handoff.get(key)}")
        }
        appendLine(handoff.getJSONObject("workspace").toString(2))
        appendLine("선택 이력: ${handoff.getJSONArray("selected_history").toString(2)}")
    }
    val pages = content.chunked(12000).ifEmpty { listOf("선택한 파일이 없습니다.") }
    val page = model.previewPage.coerceIn(0, pages.lastIndex)
    Column {
        Text(if (report == null) "로컬 미리보기 · 전체 구조 검사 전" else "포함 자료·고정 참조",
            style = MaterialTheme.typography.titleLarge)
        Row {
            TextButton(onClick = { model.previewPage = page - 1 }, enabled = page > 0) { Text("이전") }
            Text("${page + 1} / ${pages.size}")
            TextButton(onClick = { model.previewPage = page + 1 }, enabled = page < pages.lastIndex) { Text("다음") }
        }
        if (nested) Text(pages[page], fontFamily = FontFamily.Monospace)
        else LazyColumn { item { Text(pages[page], fontFamily = FontFamily.Monospace) } }
    }
}
