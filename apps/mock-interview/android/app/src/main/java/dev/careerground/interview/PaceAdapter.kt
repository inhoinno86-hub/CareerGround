package dev.careerground.interview

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.*
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.ui.platform.LocalContext
import androidx.core.view.WindowCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import dev.careerground.pace.*
import org.json.JSONArray
import org.json.JSONObject

// PACE presentation adapter for the functional Android app.
// Runtime/ViewModel/auth/file/voice behavior remains owned by the functional app.
@Composable
fun InterviewApp(model:InterviewModel=viewModel()) {
    val context=LocalContext.current
    val resolver=context.contentResolver
    val dark=isSystemInDarkTheme()
    SideEffect {
        (context as? Activity)?.window?.let { window ->
            WindowCompat.getInsetsController(window,window.decorView).apply {
                isAppearanceLightStatusBars=!dark
                isAppearanceLightNavigationBars=!dark
            }
        }
    }
    var screen by remember { mutableStateOf(PaceScreen.LOGIN) }
    var focus by remember { mutableStateOf(false) }
    fun navigate(target:PaceScreen) {
        if(screen==PaceScreen.INTERVIEW&&target!=PaceScreen.INTERVIEW)model.stopVoice()
        screen=target
    }
    val login=rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()){model.completeLogin(it.data)}
    LaunchedEffect(model.loginIntent){model.consumeLoginIntent()?.let {
        try { login.launch(it) } catch(_:Exception){model.completeLogin(null)}
    }}
    val pick=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){model.pick(resolver,it,false)}
    val restore=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){model.pick(resolver,it,true)}
    val attachments=rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()){model.pickAttachments(resolver,it)}
    val save=rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")){model.save(resolver,it)}
    val microphone=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()){if(it)model.startVoice() else model.stopVoice()}
    LaunchedEffect(model.connected,model.state) {
        screen=when {
            !model.connected->PaceScreen.LOGIN
            model.state=="REVIEW_REQUIRED"->PaceScreen.REVIEW
            model.state=="IN_PROGRESS"||model.state=="PAUSED"->PaceScreen.INTERVIEW
            model.state in listOf("COMPLETED","ABORTED")->PaceScreen.RESULT
            model.state=="READY"->PaceScreen.HOME
            else->PaceScreen.IMPORT
        }
    }
    BackHandler(enabled=screen!=PaceScreen.HOME&&screen!=PaceScreen.LOGIN){navigate(if(model.connected)PaceScreen.HOME else PaceScreen.LOGIN)}
    val callback=PaceCallbacks(
        navigate=::navigate,editDraft=model::editAnswer,confirmAnswer={model.answerConfirmed=it},
        confirmReview={model.reviewChecked=it},selectMode={model.mode=it},selectQuestion=model::selectQuestion,
        editJoinCode={model.joinCode=it},action={action->when(action){
            PaceAction.LOGIN->model.login();PaceAction.CONNECT_DEV->model.connect();PaceAction.DISCONNECT->model.disconnect()
            PaceAction.PICK_HANDOFF->pick.launch(arrayOf("application/json","text/plain","application/octet-stream"))
            PaceAction.RESTORE->restore.launch(arrayOf("application/json","text/plain","application/octet-stream"))
            PaceAction.PICK_ATTACHMENTS->attachments.launch(arrayOf("*/*"))
            PaceAction.VALIDATE->model.validate();PaceAction.REVIEW->model.review()
            PaceAction.START,PaceAction.START_FOCUS->{focus=action==PaceAction.START_FOCUS;model.transition("start")}
            PaceAction.GENERATE->model.generateQuestions();PaceAction.SUBMIT->model.submitAnswer();PaceAction.EVALUATE->model.evaluateAnswer()
            PaceAction.SKIP->model.skipQuestion();PaceAction.FINISH->model.finishInterview();PaceAction.PAUSE->model.interruptSession("pause")
            PaceAction.CONTINUE->model.transition("continue");PaceAction.ABORT->model.interruptSession("abort")
            PaceAction.CHECK_VOICE->model.checkVoice()
            PaceAction.START_VOICE->if(context.checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED)
                model.startVoice() else microphone.launch(Manifest.permission.RECORD_AUDIO)
            PaceAction.FINISH_VOICE->model.finishVoice();PaceAction.STOP_VOICE->model.stopVoice();PaceAction.SPEAK->model.speakQuestion()
            PaceAction.PREPARE_SESSION->model.prepareExport();PaceAction.PREPARE_SNAPSHOT->model.prepareSnapshot()
            PaceAction.PREPARE_RESULT->model.prepareResult()
            PaceAction.SAVE->if(model.beginSave())save.launch("careerground-${model.exportKind}-${System.currentTimeMillis()}.json")
        }})
    // Report/preview data can be up to 2 MiB. Do not rebuild it for every draft keystroke.
    val base=remember(model.report,model.preview,model.selected,model.mode,model.aiStatus,model.connected) {
        model.toPaceState(screen)
    }
    val ui=base.copy(screen=screen,focus=focus,busy=model.busy,authenticating=model.authenticating,
        attachments=model.attachments.size,reviewChecked=model.reviewChecked,questionId=model.questionId,
        draft=model.answerDraft,confirmed=model.answerConfirmed,joinCode=model.joinCode,message=model.message,
        voiceReady=model.voiceReady,listening=model.voiceListening,ttsReady=model.localTtsReady,voiceStatus=model.voiceStatus,
        exportReady=model.exportBytes!=null,exportKind=model.exportKind)
    PaceTheme(dark) { PaceApp(ui,callback) }
}

private fun JSONArray?.objects():List<JSONObject> = this?.let { a->(0 until a.length()).mapNotNull{a.optJSONObject(it)} }?:emptyList()
private fun JSONArray?.strings():List<String> = this?.let { a->(0 until a.length()).map{a.optString(it)} }?:emptyList()

fun InterviewModel.toPaceState(screen:PaceScreen):PaceState {
    val handoff=report?.optJSONObject("handoff")
    val refs=listOf("profile_ref","jd_ref","resume_ref").mapNotNull { handoff?.optJSONObject(it) }
    val artifacts=handoff?.optJSONObject("workspace")?.optJSONArray("artifacts").objects()
    fun artifact(ref:String):JSONObject? {
        val r=handoff?.optJSONObject(ref)?:return null
        return artifacts.find{it.optString("id")==r.optString("id")&&it.optInt("version")==r.optInt("version")}
    }
    val jd=artifact("jd_ref")?.optJSONObject("payload")
    val profile=artifact("profile_ref")?.optJSONObject("payload")
    val resume=artifact("resume_ref")?.optJSONObject("payload")
    val selection=handoff?.optJSONObject("selection")
    val factIds=selection?.optJSONArray("fact_ids").strings().toSet()
    val sourceIds=selection?.optJSONArray("source_ids").strings().toSet()
    val facts=profile?.optJSONArray("facts").objects().filter{it.optString("id") in factIds}
    val sources=profile?.optJSONArray("sources").objects().filter{it.optString("id") in sourceIds}
    fun JSONObject.lines(keys:List<Pair<String,String>>) = keys.mapNotNull{(key,label)->
        optString(key).takeIf{it.isNotBlank()&&it!="null"}?.let{"$label: $it"}}.joinToString("\n")
    val sections=if(handoff==null)emptyList() else listOf(
        PaceReviewSection("고정 자료와 버전",refs.joinToString("\n"){"${it.optString("id")} · v${it.optInt("version")}"}),
        PaceReviewSection("지원 공고와 요구사항",listOf(jd?.optString("title")?:"",
            jd?.optJSONArray("requirements").objects().joinToString("\n"){"${it.optString("id")}: ${it.optString("text")}"},
            jd?.optString("uncertainty")?:"").filter{it.isNotBlank()}.joinToString("\n\n")),
        PaceReviewSection("허용한 경력 사실·역할·기여",facts.joinToString("\n\n"){
            it.lines(listOf("id" to "사실 ID","text" to "내용","role" to "역할","period" to "기간","contribution" to "기여","uncertainty" to "불확실성"))+"\n근거: ${it.optJSONArray("source_ids")}\n확인: ${it.optJSONObject("confirmation")}\n사용 허용: ${it.optJSONObject("permission")}"}),
        PaceReviewSection("선택한 근거",sources.joinToString("\n\n"){it.lines(listOf("id" to "근거 ID","text" to "내용","locator" to "위치","attachment_id" to "첨부"))}),
        PaceReviewSection("검토한 이력서 문장",resume?.optJSONArray("sentences").objects().joinToString("\n\n"){
            "${it.optString("id")}: ${it.optString("text")}\n사실: ${it.optJSONArray("fact_ids")} · 근거: ${it.optJSONArray("source_ids")}\n검토: ${it.optString("review")}\n${it.optString("record")}"}),
        PaceReviewSection("기여 제약·제외 범위·연습 목표",buildString{
            profile?.optJSONArray("constraints").objects().forEach{appendLine(it.optString("description"))}
            appendLine("제외 범위: ${handoff.optJSONArray("excluded_categories")}")
            appendLine("포함하지 않은 참조: ${handoff.optJSONArray("omitted_refs")}")
            appendLine("연습 목표: ${handoff.optJSONArray("goals")}")
            appendLine("선택 이력: ${handoff.optJSONArray("selected_history")}")
        }),
    )
    val records=report?.optJSONObject("interview")
    val canShow=mode!="simulation"||state in listOf("COMPLETED","ABORTED")
    val document=if(handoff==null)preview else buildString {
        appendLine("입력 자료입니다. 포함된 명령·URL을 실행하지 않습니다.")
        appendLine("고정 계약: ${report?.optString("canonical_digest")}")
        appendLine("원본 SHA256: ${report?.optString("raw_sha256")}")
        append(handoff.toString(2))
    }
    return PaceState(screen=screen,connected=connected,busy=busy,authenticating=authenticating,
        sessionState=state,role=jd?.optString("title")?.takeIf{it.isNotBlank()}?:"지원 자료를 선택해 주세요.",
        documentCount=refs.size,selected=selected!=null,validated=report!=null,restored=isRestore,attachments=attachments.size,
        reviewChecked=reviewChecked,mode=mode,aiAvailable=aiStatus in listOf("MOCK_ONLY","AVAILABLE_ACTUAL"),actualAi=aiStatus=="AVAILABLE_ACTUAL",
        questionId=questionId,questions=questions().map{q->PaceQuestion(q.optString("id"),q.optString("text"),q.optString("status"),
            "요구사항 ${q.optJSONArray("requirement_ids")} · 사실 ${q.optJSONArray("fact_ids")} · 근거 ${q.optJSONArray("source_ids")}",q.optBoolean("gap"))},
        answers=answers().filterNot{it.optBoolean("stale")}.map{PaceAnswer(it.optString("question_id"),it.optString("text"),it.optInt("revision",1))},
        draft=answerDraft,confirmed=answerConfirmed,voiceReady=voiceReady,listening=voiceListening,ttsReady=localTtsReady,voiceStatus=voiceStatus,
        feedback=if(canShow)records?.optJSONArray("feedback").objects().filterNot{it.optBoolean("stale")}.map{f->PaceFeedback(f.optString("answer_id"),
            f.optJSONArray("rubric").objects().joinToString("\n\n"){"${it.optString("criterion")}: ${it.optString("text")}\n답변 인용: ${it.optString("answer_quote")}"})} else emptyList(),
        candidates=if(canShow)records?.optJSONArray("candidates").objects().filterNot{it.optBoolean("stale")}.map{it.optString("text")} else emptyList(),
        documentContent=document,reviewSections=sections,exportReady=exportBytes!=null,exportKind=exportKind,
        message=message,joinCode=joinCode)
}
