package dev.careerground.interview.design

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.LocalActivity
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.core.view.WindowCompat
import dev.careerground.pace.*

class DesignPreviewActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState); enableEdgeToEdge()
        val scenario=intent.getStringExtra("scenario")?:"home"
        val theme=intent.getStringExtra("theme")?:"system"
        val preview=ViewModelProvider(this)[PacePreviewModel::class.java]
        if(!preview.initialized){preview.state.value=exampleState(scenario);preview.theme.value=theme;preview.initialized=true}
        setContent { Preview(preview) }
    }
}
private val questions=listOf(
    PaceQuestion("q1","문제를 해결했던 경험과 직접 맡은 역할을 알려주세요.",references="팀 프로젝트 · 문제 해결 역량"),
    PaceQuestion("q2","여러 요청이 겹쳤을 때 우선순위를 어떻게 정했나요?",references="서비스 운영 · 업무 조율"),
    PaceQuestion("q3","동료와 의견이 달랐던 상황을 어떻게 풀었나요?",references="팀 협업"),
    PaceQuestion("q4","결과를 어떤 근거로 확인했나요?",references="성과 확인"),
    PaceQuestion("q5","같은 상황에서 다음에는 무엇을 바꾸고 싶나요?",references="개선 방향"))
private const val answer="팀 프로젝트에서 문의 분류 기준을 정리하는 역할을 맡았습니다. 팀원들과 반복 문의를 살펴보고 공통 기준을 제안했습니다. 최종 결정과 운영 적용은 팀이 함께 진행했습니다."
private const val documents="""선택한 자료 · 합성 예시

지원 공고 v1 · 서비스 운영
반복되는 문제를 정리하고 동료와 해결 방법을 조율하는 경험

경력 자료 v2 · 사용자 확인 사실
팀 프로젝트에서 문의 분류 기준 정리를 담당했습니다.
직접 한 일: 반복 문의 검토, 공통 분류 기준 제안
동료의 기여: 최종 결정 및 운영 적용은 팀 공동 작업

이력서 v1 · 검토 문장
반복 문의의 분류 기준을 정리하고 팀에 제안했습니다.

제외 범위
미확인 성과 수치, 개인 연락처, 선택하지 않은 경력

고정 참조
profile-sample@v2 · jd-sample@v1 · resume-sample@v1
근거 source-team · 허용 사실 fact-role
내용과 처리 경로를 확인한 뒤 세션을 고정합니다."""
fun exampleState(scenario:String="home"):PaceState {
    val base=PaceState(role="서비스 운영 직무",documentCount=3,selected=true,validated=true,preview=true,
        aiAvailable=true,voiceReady=true,ttsReady=true,documentContent=documents,
        voiceStatus="합성 음성 상태 · 실제 마이크는 사용하지 않습니다.")
    val active=base.copy(screen=PaceScreen.INTERVIEW,sessionState="IN_PROGRESS",questions=questions,questionId="q1")
    val answered=active.copy(draft=answer,answers=listOf(PaceAnswer("q1",answer)),
        questions=questions.map{if(it.id=="q1")it.copy(status="answered") else it},
        feedback=listOf(PaceFeedback("q1","직접 맡은 역할과 팀의 기여를 구분했습니다. 제안한 기준의 구체적인 예를 더 설명해 보세요.\n답변 인용: 공통 기준을 제안했습니다.")),
        candidates=listOf("문의 분류 기준을 정리한 경험 · 별도 확인 전 후보"))
    return when(scenario){
        "login"->base.copy(screen=PaceScreen.LOGIN,connected=false,selected=false,validated=false,sessionState="EMPTY")
        "empty"->base.copy(selected=false,validated=false,sessionState="EMPTY",documentCount=0,role="아직 선택한 직무가 없어요.")
        "import"->base.copy(screen=PaceScreen.IMPORT,validated=false,sessionState="EMPTY",attachments=2)
        "review"->base.copy(screen=PaceScreen.REVIEW,sessionState="REVIEW_REQUIRED")
        "interview"->active
        "draft"->active.copy(draft=answer)
        "voice"->active.copy(draft=answer,listening=true,voiceStatus="기기 내 음성 인식 중 · 합성 상태")
        "generating"->active.copy(questions=emptyList(),questionId="",busy=true,message="질문을 준비하고 있습니다. 잠시 기다려 주세요.")
        "error"->active.copy(questions=emptyList(),questionId="",message="질문을 가져오지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요.")
        "paused"->active.copy(sessionState="PAUSED",draft=answer)
        "expired"->answered.copy(sessionState="PAUSED",message="세션을 사용할 수 없습니다. 화면 기록으로 복구 파일을 준비하고 다시 가져와 주세요.")
        "simulation"->answered.copy(mode="simulation")
        "result"->answered.copy(screen=PaceScreen.RESULT,sessionState="COMPLETED")
        "saved-ready"->answered.copy(screen=PaceScreen.RESULT,sessionState="COMPLETED",exportReady=true,exportKind="result")
        else->base
    }
}
private val scenarios=listOf("home" to "준비된 홈","empty" to "자료 없는 홈","login" to "계정 연결",
    "import" to "자료 가져오기","review" to "내용 검토","interview" to "질문·답변","voice" to "음성 인식 중",
    "generating" to "질문 준비 중","error" to "연결 오류","paused" to "일시 중지","expired" to "만료·복구 안내",
    "simulation" to "모의 면접 평가 숨김","result" to "결과","saved-ready" to "파일 준비 완료")

// RAM-only preview state survives configuration changes. Nothing is saved to disk.
class PacePreviewModel:ViewModel() {
    val state=mutableStateOf(exampleState())
    val theme=mutableStateOf("system")
    var initialized=false
}
@Composable private fun Preview(model:PacePreviewModel) {
    var state by model.state
    var theme by model.theme
    var tools by remember { mutableStateOf(false) }
    val dark=if(theme=="system") isSystemInDarkTheme() else theme=="dark"
    val activity=LocalActivity.current
    SideEffect {
        activity?.window?.let { window ->
            WindowCompat.getInsetsController(window,window.decorView).apply {
                isAppearanceLightStatusBars=!dark
                isAppearanceLightNavigationBars=!dark
            }
        }
    }
    fun notice(text:String){state=state.copy(message=text)}
    val callbacks=PaceCallbacks(
        navigate={state=state.copy(screen=it,message="")},
        editDraft={state=state.copy(draft=it.take(20000),confirmed=false)},confirmAnswer={state=state.copy(confirmed=it)},
        confirmReview={state=state.copy(reviewChecked=it)},selectMode={state=state.copy(mode=it)},
        selectQuestion={id->state=state.copy(questionId=id,draft=state.answers.lastOrNull{it.questionId==id}?.text?:"",confirmed=false,listening=false)},
        editJoinCode={state=state.copy(joinCode=it)},action={action->when(action){
            PaceAction.LOGIN,PaceAction.CONNECT_DEV->state=exampleState("empty").copy(message="합성 계정 연결 예시 · 실제 로그인 없음")
            PaceAction.DISCONNECT->state=exampleState("login")
            PaceAction.PICK_HANDOFF->state=exampleState("import").copy(message="합성 준비 파일 선택 예시 · 실제 파일 접근 없음")
            PaceAction.RESTORE->state=exampleState("import").copy(restored=true,message="수동 세션 가져오기의 합성 예시")
            PaceAction.PICK_ATTACHMENTS->state=state.copy(attachments=3,message="첨부 선택 예시 · 실제 파일 접근 없음")
            PaceAction.VALIDATE->state=exampleState("review")
            PaceAction.REVIEW->if(state.reviewChecked)state=state.copy(screen=PaceScreen.HOME,sessionState="READY",message="")
            PaceAction.START,PaceAction.START_FOCUS->state=state.copy(screen=PaceScreen.INTERVIEW,sessionState="IN_PROGRESS",questions=emptyList(),questionId="",message="",focus=action==PaceAction.START_FOCUS)
            PaceAction.GENERATE->state=state.copy(questions=questions,questionId="q1",message="")
            PaceAction.SUBMIT->if(state.canSubmit){
                val old=state.currentAnswer
                state=state.copy(confirmed=false,questions=state.questions.map{if(it.id==state.questionId)it.copy(status="answered") else it},
                    answers=state.answers.filterNot{it.questionId==state.questionId}+PaceAnswer(state.questionId,state.draft,(old?.revision?:0)+1),
                    feedback=state.feedback.filterNot{it.answerId==state.questionId},candidates=emptyList(),exportReady=false,
                    message="확인 답변 제출 예시 · 실제 전송은 없습니다.")
            }
            PaceAction.EVALUATE->if(state.currentAnswer!=null)state=state.copy(
                feedback=state.feedback.filterNot{it.answerId==state.questionId}+PaceFeedback(state.questionId,"직접 한 일과 팀의 기여를 구분해 주세요. 제안한 기준의 구체적인 예를 더해 보세요."),
                candidates=listOf("프로젝트에서 분류 기준을 정리한 경험 · 확인 전 후보"),
                message=if(state.mode=="simulation") "평가 준비 예시 · 종료 후 표시합니다." else "합성 피드백 예시 · 실제 AI 평가가 아닙니다.")
            PaceAction.FINISH->if(state.answers.isNotEmpty()&&state.answers.all{a->state.feedback.any{it.answerId==a.questionId}})
                state=state.copy(screen=PaceScreen.RESULT,sessionState="COMPLETED",message="",confirmed=false)
                else notice("확인한 답변의 평가를 먼저 준비해 주세요.")
            PaceAction.SKIP->state=state.copy(questions=state.questions.map{if(it.id==state.questionId)it.copy(status="skipped") else it},questionId="",draft="",confirmed=false)
            PaceAction.PAUSE->state=state.copy(sessionState="PAUSED",listening=false,confirmed=false,message="일시 중지했습니다.")
            PaceAction.CONTINUE->state=state.copy(screen=PaceScreen.INTERVIEW,sessionState="IN_PROGRESS",message="")
            PaceAction.ABORT->state=state.copy(screen=PaceScreen.RESULT,sessionState="ABORTED",listening=false,confirmed=false,message="평가 없이 중단한 예시입니다.")
            PaceAction.CHECK_VOICE->notice("음성 준비 상태의 합성 예시입니다.")
            PaceAction.START_VOICE->state=state.copy(listening=true,confirmed=false,voiceStatus="기기 내 음성 인식 중 · 실제 마이크 접근 없음")
            PaceAction.FINISH_VOICE->state=state.copy(listening=false,confirmed=false,draft=state.draft.ifBlank{answer},voiceStatus="전사 초안 · 내용을 확인해 주세요.")
            PaceAction.STOP_VOICE->state=state.copy(listening=false,confirmed=false)
            PaceAction.SPEAK->notice("질문 읽기 예시 · 실제 음성 재생 없음")
            PaceAction.PREPARE_RESULT,PaceAction.PREPARE_SESSION,PaceAction.PREPARE_SNAPSHOT->state=state.copy(exportReady=true,
                exportKind=if(action==PaceAction.PREPARE_RESULT)"result" else "session",message="파일 준비 예시 · 실제 파일 생성 없음")
            PaceAction.SAVE->notice("저장 위치 선택의 예시입니다. 실제 저장은 실행하지 않았습니다.")
        }})
    PaceTheme(dark){
        Surface(Modifier.fillMaxSize(),color=MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().statusBarsPadding()) {
            TextButton(onClick={tools=true},modifier=Modifier.fillMaxWidth()) {
                Text("PACE · 합성 디자인 미리보기 / 설정",style=MaterialTheme.typography.labelSmall)
            }
            PaceApp(state,callbacks,Modifier.weight(1f))
        }
        }
        if(tools)AlertDialog(onDismissRequest={tools=false},title={Text("미리보기 설정")},text={
            Column(Modifier.heightIn(max=500.dp).verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)){
                Text("합성 화면만 전환합니다. 실제 로그인·파일·음성·AI·저장 없음.")
                listOf("system" to "휴대폰 설정 따르기","light" to "밝게","dark" to "어둡게").forEach{(value,label)->
                    FilterChip(theme==value,{theme=value},{Text(label)})}
                scenarios.forEach{(value,label)->TextButton(onClick={state=exampleState(value);tools=false}){Text(label)}}
            }
        },confirmButton={TextButton(onClick={tools=false}){Text("닫기")}})
    }
}
