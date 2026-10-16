package dev.careerground.pace

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
fun PaceApp(state: PaceState, callbacks: PaceCallbacks, modifier: Modifier = Modifier) {
    Surface(modifier.fillMaxSize(), color=MaterialTheme.colorScheme.background) {
        Column(Modifier.safeDrawingPadding().imePadding(), horizontalAlignment=Alignment.CenterHorizontally) {
            Column(Modifier.widthIn(max=1100.dp).fillMaxWidth().weight(1f)) {
                Header(state, callbacks)
                if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth().testTag("busy"))
                if (state.message.isNotBlank()) Surface(color=MaterialTheme.colorScheme.surfaceVariant) {
                    Text(state.message,Modifier.fillMaxWidth().padding(horizontal=24.dp,vertical=10.dp)
                        .testTag("notice"),style=MaterialTheme.typography.bodySmall)
                }
                when(state.screen) {
                    PaceScreen.HOME -> Home(state,callbacks,Modifier.weight(1f))
                    PaceScreen.LOGIN -> Login(state,callbacks,Modifier.weight(1f))
                    PaceScreen.IMPORT -> Import(state,callbacks,Modifier.weight(1f))
                    PaceScreen.REVIEW -> Review(state,callbacks,Modifier.weight(1f))
                    PaceScreen.INTERVIEW -> Interview(state,callbacks,Modifier.weight(1f))
                    PaceScreen.RESULT -> Result(state,callbacks,Modifier.weight(1f))
                }
                if (state.connected && state.screen in listOf(PaceScreen.HOME,PaceScreen.IMPORT)) {
                    BottomNav(state,callbacks)
                }
            }
        }
    }
}

@Composable
private fun Header(s:PaceState,c:PaceCallbacks) {
    Row(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=10.dp),
        verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.SpaceBetween) {
        if(s.screen==PaceScreen.HOME || s.screen==PaceScreen.LOGIN) {
            Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                PaceIcon("brand",Modifier.size(22.dp))
                Text("CareerGround",style=MaterialTheme.typography.titleMedium,fontWeight=FontWeight.SemiBold)
            }
        } else IconButton(onClick={c.navigate(if(s.connected) PaceScreen.HOME else PaceScreen.LOGIN)},
            modifier=Modifier.semantics { contentDescription="홈으로" }) { PaceIcon("back") }
        if(s.screen==PaceScreen.HOME) IconButton(onClick={c.navigate(PaceScreen.IMPORT)},
            enabled=!s.busy,modifier=Modifier.semantics { contentDescription="연습 자료 관리" }) { PaceIcon("plus") }
        else if(s.screen!=PaceScreen.LOGIN) Text(when(s.screen){
            PaceScreen.IMPORT -> "연습 자료"; PaceScreen.REVIEW -> "내용 확인";
            PaceScreen.INTERVIEW -> "면접 연습"; PaceScreen.RESULT -> "연습 결과"; else -> ""
        },style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ScrollBody(modifier:Modifier=Modifier, content:@Composable ColumnScope.()->Unit) {
    Column(modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal=24.dp,vertical=12.dp),
        verticalArrangement=Arrangement.spacedBy(24.dp),content=content)
}
@Composable private fun Kicker(text:String) {
    Text(text,style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
}
@Composable private fun Copy(text:String) {
    Text(text,style=MaterialTheme.typography.bodyMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
}
@Composable private fun Rule() { HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant) }
@Composable private fun Panel(content:@Composable ColumnScope.()->Unit) {
    Surface(Modifier.fillMaxWidth(),color=MaterialTheme.colorScheme.surface,
        shape=RoundedCornerShape(20.dp),border=BorderStroke(1.dp,MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(20.dp),verticalArrangement=Arrangement.spacedBy(14.dp),content=content)
    }
}
@Composable
private fun Primary(text:String,enabled:Boolean=true,tag:String="",onClick:()->Unit) {
    Button(onClick,enabled=enabled,modifier=Modifier.fillMaxWidth().heightIn(min=54.dp).testTag(tag),
        shape=RoundedCornerShape(15.dp),contentPadding=PaddingValues(horizontal=20.dp,vertical=14.dp)) {
        Text(text,Modifier.weight(1f));Spacer(Modifier.width(12.dp));PaceIcon("arrow",Modifier.size(18.dp))
    }
}
@Composable private fun Secondary(text:String,enabled:Boolean=true,onClick:()->Unit) {
    OutlinedButton(onClick,enabled=enabled,modifier=Modifier.fillMaxWidth().heightIn(min=48.dp),
        shape=RoundedCornerShape(13.dp),contentPadding=PaddingValues(horizontal=16.dp,vertical=12.dp)) { Text(text) }
}
@Composable private fun Action(s:PaceState,c:PaceCallbacks,a:PaceAction,text:String,enabled:Boolean=true) {
    val interrupt=a==PaceAction.PAUSE||a==PaceAction.ABORT
    Secondary(text,enabled=enabled&&(!s.busy||interrupt)) { c.action(a) }
}
@Composable private fun CheckLine(checked:Boolean,text:String,enabled:Boolean=true,tag:String="",onChange:(Boolean)->Unit) {
    Row(Modifier.fillMaxWidth().clickable(enabled=enabled){onChange(!checked)}.padding(vertical=4.dp),
        verticalAlignment=Alignment.CenterVertically) {
        Checkbox(checked,onChange,enabled=enabled,modifier=Modifier.testTag(tag))
        Text(text,Modifier.weight(1f),style=MaterialTheme.typography.bodySmall)
    }
}
@Composable private fun RailStep(number:String,title:String,detail:String,done:Boolean=false,last:Boolean=false) {
    Row(horizontalArrangement=Arrangement.spacedBy(14.dp)) {
        Column(horizontalAlignment=Alignment.CenterHorizontally) {
            Surface(shape=RoundedCornerShape(9.dp),color=if(done) MaterialTheme.colorScheme.primaryContainer
                else MaterialTheme.colorScheme.onBackground,contentColor=if(done) MaterialTheme.colorScheme.onPrimaryContainer
                else MaterialTheme.colorScheme.background) {
                Box(Modifier.size(32.dp),contentAlignment=Alignment.Center) {
                    if(done) PaceIcon("check",Modifier.size(16.dp)) else Text(number,style=MaterialTheme.typography.labelMedium)
                }
            }
            if(!last) Box(Modifier.padding(top=5.dp).width(1.dp).height(23.dp)) {
                Canvas(Modifier.fillMaxSize()) { drawLine(Color(0xFF9CAC98),center.copy(y=0f),center.copy(y=size.height),1.dp.toPx()) }
            }
        }
        Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(4.dp)) {
            Text(title,style=MaterialTheme.typography.titleMedium)
            Copy(detail)
        }
    }
}
@Composable
private fun Home(s:PaceState,c:PaceCallbacks,modifier:Modifier) {
    ScrollBody(modifier) {
        Column(verticalArrangement=Arrangement.spacedBy(10.dp)) {
            Kicker("나의 면접 준비")
            Text("쌓아온 경험을,\n나의 답변으로.",style=MaterialTheme.typography.headlineLarge)
            Copy("한 질문부터 차분하게 시작해 보세요.")
        }
        Rule()
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
            Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(5.dp)) {
                Kicker("이번 지원");Text(s.role,style=MaterialTheme.typography.titleLarge)
            }
            IconButton(onClick={c.navigate(PaceScreen.IMPORT)},modifier=Modifier.semantics { contentDescription="지원 자료 확인" }) { PaceIcon("arrow") }
        }
        Rule()
        Column {
            RailStep("1",if(s.validated) "연습 자료가 준비됐어요." else "연습 자료를 준비해 주세요.",
                if(s.validated) "선택한 자료 ${s.documentCount}개 · ${if(s.sessionState=="REVIEW_REQUIRED") "내용 확인 필요" else "내용 검토 완료"}"
                else "면접 준비 파일과 필요한 첨부를 가져옵니다.",done=s.validated)
            RailStep("2",if(s.sessionState=="READY") "나에게 맞는 길이로 시작하세요." else "다음 단계로 이어가세요.",
                when(s.sessionState){"READY"->"내 자료를 바탕으로 답변을 연습합니다.";"PAUSED"->"중지한 연습과 확인 답변이 유지됩니다.";
                    "IN_PROGRESS"->"진행 중인 질문과 답변을 이어갈 수 있어요.";"COMPLETED","ABORTED"->"확인 답변과 결과를 직접 저장해 주세요.";
                    else->"선택한 자료를 확인한 뒤 연습을 시작합니다."},last=true)
        }
        when(s.sessionState) {
            "READY" -> Surface(color=MaterialTheme.colorScheme.primaryContainer,shape=RoundedCornerShape(19.dp)) {
                Column(Modifier.padding(horizontal=18.dp)) {
                    PracticeRow("1","한 답변에 집중","하나의 경험을 선명하게",!s.busy){c.action(PaceAction.START_FOCUS)}
                    Rule()
                    PracticeRow("여러","전체 흐름 연습","질문을 이어가며 답변하기",!s.busy){c.action(PaceAction.START)}
                }
            }
            "IN_PROGRESS" -> Primary("연습 이어가기",!s.busy){c.navigate(PaceScreen.INTERVIEW)}
            "PAUSED" -> Primary("중지한 연습 계속",!s.busy){c.action(PaceAction.CONTINUE)}
            "COMPLETED","ABORTED" -> Primary("연습 결과 보기"){c.navigate(PaceScreen.RESULT)}
            "REVIEW_REQUIRED" -> Primary("내용 확인하기",!s.busy){c.navigate(PaceScreen.REVIEW)}
            else -> Primary("연습 자료 가져오기",!s.busy){c.navigate(PaceScreen.IMPORT)}
        }
        if(s.sessionState=="READY") Copy("두 시작 방식은 같은 고정 세션을 엽니다. 질문 수는 준비된 질문에 따라 달라지며, 한 답변 후에도 직접 종료할 수 있어요.")
        Text("자동 저장되지 않습니다. 앱을 닫기 전에 복구 파일을 저장해 주세요.",style=MaterialTheme.typography.bodySmall,
            color=MaterialTheme.colorScheme.onSurfaceVariant)
        if(s.connected) TextButton(onClick={c.action(PaceAction.DISCONNECT)}) { Text("연결 해제·앱 메모리 비우기") }
    }
}
@Composable private fun PracticeRow(number:String,title:String,detail:String,enabled:Boolean,onClick:()->Unit) {
    Row(Modifier.fillMaxWidth().clickable(enabled=enabled,onClick=onClick).padding(vertical=22.dp),
        verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(15.dp)) {
        Surface(shape=RoundedCornerShape(10.dp),color=MaterialTheme.colorScheme.surface) {
            Column(Modifier.widthIn(min=46.dp).padding(9.dp),horizontalAlignment=Alignment.CenterHorizontally) {
                Text(number,style=MaterialTheme.typography.titleLarge);Text("질문",style=MaterialTheme.typography.labelSmall)
            }
        }
        Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(5.dp)) {
            Text(title,style=MaterialTheme.typography.titleMedium);Text(detail,style=MaterialTheme.typography.bodySmall,
                color=MaterialTheme.colorScheme.onSurfaceVariant)
        }
        PaceIcon("arrow",Modifier.size(18.dp))
    }
}
@Composable private fun BottomNav(s:PaceState,c:PaceCallbacks) {
    Rule()
    Row(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=7.dp),horizontalArrangement=Arrangement.SpaceAround) {
        listOf(Triple("home","홈",PaceScreen.HOME),Triple("mic","연습",PaceScreen.INTERVIEW),
            Triple("files","자료",PaceScreen.IMPORT)).forEach { (icon,label,target) ->
            TextButton(onClick={c.navigate(target)},enabled=!s.busy) {
                Column(horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(4.dp)) {
                    PaceIcon(icon,Modifier.size(19.dp));Text(label,style=MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}
@Composable private fun Login(s:PaceState,c:PaceCallbacks,modifier:Modifier) {
    ScrollBody(modifier) {
        Kicker("내 자료로 시작하는 면접 연습")
        Text("경험을 준비하고,\n답변을 다듬어 보세요.",style=MaterialTheme.typography.headlineLarge)
        Copy("계정 연결 후, 직접 고른 면접 준비 자료로 연습합니다.")
        Primary("개인 계정 로그인",!s.busy&&!s.authenticating,"login"){c.action(PaceAction.LOGIN)}
        Copy("외부 브라우저에서 로그인합니다. 현재 버전은 PC 연결이 필요합니다.")
        Copy("자동 저장되지 않습니다. 앱을 닫기 전에 복구 파일을 저장해 주세요.")
        Details("개발 시험 연결") {
            Copy("합성 자료를 사용하는 개발 시험용입니다.")
            OutlinedTextField(s.joinCode,c.editJoinCode,label={Text("임시 연결 코드")},
                visualTransformation=PasswordVisualTransformation(),keyboardOptions=KeyboardOptions(
                    keyboardType=KeyboardType.Password,autoCorrectEnabled=false),modifier=Modifier.fillMaxWidth(),
                enabled=!s.busy&&!s.authenticating)
            Secondary("합성 개발 연결",!s.busy&&!s.authenticating&&s.joinCode.isNotBlank()){c.action(PaceAction.CONNECT_DEV)}
        }
    }
}
@Composable private fun Import(s:PaceState,c:PaceCallbacks,modifier:Modifier) {
    ScrollBody(modifier) {
        Kicker("자료 준비")
        Text("연습할 경험을\n가져와 주세요.",style=MaterialTheme.typography.headlineLarge)
        Copy("경력·지원 공고·이력서를 선택해 만든 면접 준비 파일을 가져옵니다.")
        RailStep("1","면접 준비 파일 선택",if(s.selected) "파일 선택됨 · ${if(s.restored) "수동 세션 복구" else "검사 전"}" else "직접 선택한 파일만 가져옵니다.",done=s.selected,last=true)
        Primary("면접 준비 파일 가져오기",!s.busy){c.action(PaceAction.PICK_HANDOFF)}
        Action(s,c,PaceAction.RESTORE,"수동 세션 파일 가져오기")
        if(s.selected&&!s.validated) {
            Action(s,c,PaceAction.PICK_ATTACHMENTS,"필요한 첨부 선택 · ${s.attachments}개")
            Copy("검사를 누르면 선택 파일과 첨부만 PC로 전송합니다. 첨부 합계는 최대 20 MiB입니다. 이 단계에서 AI로 전송하지 않습니다.")
            Primary("선택한 파일 검사",!s.busy,"validate"){c.action(PaceAction.VALIDATE)}
        }
        if(s.validated) Primary(if(s.sessionState=="REVIEW_REQUIRED") "포함 내용 확인" else "고정한 자료 확인"){c.navigate(PaceScreen.REVIEW)}
        if(s.documentContent.isNotBlank()) Details("선택 자료 상세 보기") { PagedText(s.documentContent) }
        if(s.validated) Copy("고정 자료를 바꾸려면 준비 파일을 다시 선택해야 합니다. 기존 세션이 교체됩니다.")
    }
}
@Composable private fun Review(s:PaceState,c:PaceCallbacks,modifier:Modifier) {
    ScrollBody(modifier) {
        Kicker("준비 내용을 확인하는 단계")
        Text("내 자료인지,\n함께 확인해 주세요.",style=MaterialTheme.typography.headlineLarge)
        Copy("사실과 근거, 이력서 문장, 직접 한 일과 동료의 기여, 제외할 내용과 고정 버전을 살펴보세요.")
        Panel {
            Text(s.role,style=MaterialTheme.typography.titleLarge)
            Kicker("구조 검사와 사실 확인은 별개입니다.")
            if(s.reviewSections.isEmpty()) PagedText(s.documentContent.ifBlank{"가져온 자료가 없습니다. 자료를 선택하고 검사해 주세요."})
            else s.reviewSections.forEach { section -> Details(section.title,initiallyOpen=section.title=="고정 자료와 버전") {
                PagedText(section.text)
            } }
        }
        if(s.reviewSections.isNotEmpty()) Details("전체 입력 자료·참조 확인") { PagedText(s.documentContent) }
        if(s.sessionState=="REVIEW_REQUIRED") {
            Text("연습 방식",style=MaterialTheme.typography.titleMedium)
            ModeRow(s,c,"coaching","코칭","답변마다 피드백을 살펴봅니다.")
            ModeRow(s,c,"simulation","모의 면접","평가는 면접을 마친 뒤 표시합니다.")
            CheckLine(s.reviewChecked,"포함 범위·고정 버전·처리 경로를 확인했습니다.",!s.busy,"review-confirm",c.confirmReview)
            Primary("범위 확인·세션 고정",!s.busy&&s.reviewChecked,"review"){c.action(PaceAction.REVIEW)}
        } else if(s.sessionState=="READY") Primary("연습 선택으로"){c.navigate(PaceScreen.HOME)}
        else if(!s.validated) Primary("자료 준비로"){c.navigate(PaceScreen.IMPORT)}
        Copy("질문 생성 전에 AI에 전달할 범위를 다시 안내합니다.")
    }
}
@Composable private fun ModeRow(s:PaceState,c:PaceCallbacks,value:String,title:String,detail:String) {
    Row(Modifier.fillMaxWidth().clickable(enabled=!s.busy){c.selectMode(value)},verticalAlignment=Alignment.CenterVertically) {
        RadioButton(s.mode==value,{c.selectMode(value)},enabled=!s.busy)
        Column(Modifier.weight(1f)) { Text(title,style=MaterialTheme.typography.titleMedium);Copy(detail) }
    }
}

@Composable private fun Interview(s:PaceState,c:PaceCallbacks,modifier:Modifier) {
    Column(modifier) {
        ScrollBody(Modifier.weight(1f).testTag("interview-scroll")) {
            if(s.sessionState=="PAUSED") {
                Text("잠시 멈춘 연습입니다.",style=MaterialTheme.typography.headlineSmall)
                Primary("연습 계속",!s.busy){c.action(PaceAction.CONTINUE)}
            } else if(s.sessionState !in listOf("IN_PROGRESS","READY")) {
                Text(if(s.sessionState in listOf("COMPLETED","ABORTED")) "마친 연습입니다." else "연습 준비가 필요합니다.",style=MaterialTheme.typography.headlineSmall)
                Primary(if(s.validated) "연습 결과 보기" else "자료 준비로") { c.navigate(if(s.validated) PaceScreen.RESULT else PaceScreen.IMPORT) }
            }
            if(s.sessionState=="READY") Primary("고정한 자료로 연습 시작",!s.busy){c.action(PaceAction.START)}
            if(s.currentQuestion==null) {
                if(s.sessionState=="IN_PROGRESS" && s.activeQuestions.isEmpty()) {
                    Text("첫 질문을\n준비할 시간입니다.",style=MaterialTheme.typography.headlineLarge)
                    Copy(when {s.actualAi -> "현재 연결에서 실제 AI를 사용합니다. 사용량 한도가 적용됩니다."
                        s.aiAvailable -> "현재 연결은 합성 AI 시험입니다."
                        else -> "연결된 서비스의 AI 지원 상태를 확인해 주세요."})
                    Panel {
                        Text("질문 생성에 전달하는 내용",style=MaterialTheme.typography.titleMedium)
                        Copy("선택한 공고 요구사항, 검토 문장, 허용 사실과 근거, 기여 제약, 연습 목표와 필요한 확인 답변을 보냅니다.")
                    }
                    Primary("선택한 근거로 질문 생성",!s.busy&&s.aiAvailable,"generate"){c.action(PaceAction.GENERATE)}
                    if(!s.aiAvailable) Copy("현재 연결은 AI 질문 생성을 지원하지 않습니다. 연결 상태를 확인해 주세요.")
                } else if(s.activeQuestions.isNotEmpty()) Copy("아래 목록에서 답변할 질문을 선택해 주세요.")
            } else BoxWithConstraints(Modifier.fillMaxWidth()) {
                if(maxWidth>=600.dp) Row(horizontalArrangement=Arrangement.spacedBy(32.dp)) {
                    Box(Modifier.weight(1f)){Question(s)}
                    Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(20.dp)){Answer(s,c)}
                } else Column(verticalArrangement=Arrangement.spacedBy(30.dp)) { Question(s);Answer(s,c) }
            }
            if(s.showFeedback && s.feedback.isNotEmpty()) Feedback(s)
            if(s.showFeedback && s.candidates.isNotEmpty()) Candidates(s)
            if(!s.showFeedback && s.feedback.isNotEmpty()) Copy("모의 면접 평가는 종료 후 표시됩니다.")
            if(s.focus && s.currentAnswer!=null) Copy("한 답변에 집중하는 연습입니다. 평가를 준비한 뒤 현재 답변으로 마치거나 다른 질문을 이어갈 수 있어요.")
            if(s.activeQuestions.isNotEmpty()) Details("질문 목록 · ${s.activeQuestions.size}개") {
                s.activeQuestions.forEachIndexed { i,q ->
                    TextButton(onClick={c.selectQuestion(q.id)},enabled=!s.busy&&!s.listening&&q.status!="skipped") {
                        Text("${i+1}. ${q.text} · ${statusLabel(q.status)}",style=MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            if(s.sessionState in listOf("READY","IN_PROGRESS","PAUSED")) {
                Details("연습 중지·수동 저장") {
                    Copy("세션은 30분 후 만료됩니다. 대기하거나 앱을 닫기 전에 수동 저장해 주세요.")
                    if(s.sessionState=="IN_PROGRESS") Action(s,c,PaceAction.PAUSE,"일시 중지")
                    Action(s,c,PaceAction.ABORT,"평가 없이 중단 · 확인 답변 유지")
                    Export(s,c)
                }
            }
        }
        if(s.currentQuestion!=null && s.sessionState=="IN_PROGRESS") Surface(color=MaterialTheme.colorScheme.background,
            shadowElevation=2.dp) {
            Column(Modifier.fillMaxWidth().padding(horizontal=24.dp,vertical=12.dp)) {
                CheckLine(s.confirmed,"숫자·기간·역할·동료의 기여를 확인했습니다.",s.editable,"answer-confirm",c.confirmAnswer)
                Primary(if(s.currentAnswer==null) "확인한 답변 제출" else "수정 답변 제출",s.canSubmit,"submit"){c.action(PaceAction.SUBMIT)}
            }
        }
    }
}
@Composable private fun Question(s:PaceState) {
    val q=s.currentQuestion ?: return
    Row(horizontalArrangement=Arrangement.spacedBy(18.dp)) {
        Column(horizontalAlignment=Alignment.CenterHorizontally) {
            Surface(shape=RoundedCornerShape(9.dp),color=MaterialTheme.colorScheme.onBackground,
                contentColor=MaterialTheme.colorScheme.background) {
                Text("${s.activeQuestions.indexOf(q)+1}",Modifier.padding(10.dp),style=MaterialTheme.typography.labelMedium)
            }
            Spacer(Modifier.height(12.dp))
            repeat((s.activeQuestions.size-1).coerceIn(0,9)) {
                val color=MaterialTheme.colorScheme.outlineVariant
                Canvas(Modifier.padding(vertical=6.dp).size(5.dp)){drawCircle(color)}
            }
        }
        Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(18.dp)) {
            Kicker("${if(s.focus) "한 답변에 집중" else if(s.mode=="simulation") "모의 면접" else "코칭"} · 질문 ${s.activeQuestions.indexOf(q)+1} / ${s.activeQuestions.size}")
            Text(q.text,style=MaterialTheme.typography.headlineMedium,modifier=Modifier.testTag("question-text"))
            if(q.references.isNotBlank()) Row(horizontalArrangement=Arrangement.spacedBy(7.dp)) {
                PaceIcon("link",Modifier.padding(top=3.dp).size(16.dp));Text(q.references,
                    style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if(q.gap) Copy("근거가 부족한 부분을 탐색하는 질문입니다. 기존 경험으로 확정하지 않습니다.")
        }
    }
}
@Composable private fun Answer(s:PaceState,c:PaceCallbacks) {
    Rule()
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
        Text("답변 초안",style=MaterialTheme.typography.titleMedium);Kicker("제출 전 수정 가능")
    }
    OutlinedTextField(s.draft,c.editDraft,modifier=Modifier.fillMaxWidth().testTag("draft"),
        placeholder={Text("당시 상황과 직접 한 행동부터 이야기해 주세요.")},
        minLines=4,maxLines=8,enabled=s.editable,shape=RoundedCornerShape(13.dp),
        textStyle=MaterialTheme.typography.bodyLarge)
    s.currentAnswer?.let {
        Details("확인 답변 · v${it.revision}") { Text(it.text,style=MaterialTheme.typography.bodyMedium) }
    }
    Details(if(s.listening) "음성 인식 중" else "음성으로 답변·질문 읽기", initiallyOpen=s.listening) {
        Copy(s.voiceStatus)
        Action(s,c,PaceAction.CHECK_VOICE,"음성 준비 상태 확인",s.editable)
        if(s.listening) {
            Action(s,c,PaceAction.FINISH_VOICE,"인식 마치기")
        } else Action(s,c,PaceAction.START_VOICE,"기기 내 음성 시작",s.editable&&s.voiceReady)
        Action(s,c,PaceAction.SPEAK,"질문 읽기",s.editable&&s.ttsReady)
        Action(s,c,PaceAction.STOP_VOICE,"음성·읽기 취소")
        Copy("음성 전사도 제출 전에는 초안입니다. 키보드 받아쓰기는 OS 제공자의 외부 처리가 가능하며 앱의 기기 내 인식과 다릅니다.")
    }
    if(s.currentAnswer!=null && s.sessionState=="IN_PROGRESS") {
        Action(s,c,PaceAction.EVALUATE,if(s.mode=="simulation") "평가 준비 · 종료 후 표시" else "현재 답변 AI 평가",!s.listening)
        Action(s,c,PaceAction.FINISH,"현재 답변으로 면접 완료",!s.listening)
        Copy("미평가 답변이 있으면 평가를 먼저 준비해 주세요. 수정하면 이전 평가는 제외됩니다.")
    }
    if(s.currentQuestion?.status=="pending" && s.sessionState=="IN_PROGRESS") TextButton(
        onClick={c.action(PaceAction.SKIP)},enabled=!s.busy&&!s.listening) { Text("질문 건너뛰기") }
}
@Composable private fun Feedback(s:PaceState) {
    Column(verticalArrangement=Arrangement.spacedBy(14.dp),modifier=Modifier.testTag("feedback")) {
        Kicker(if(s.preview || !s.actualAi) "합성 피드백 예시" else "AI 피드백")
        s.feedback.forEach { item -> Panel {
            Kicker("답변 ${item.answerId}");Text(item.text,style=MaterialTheme.typography.bodyMedium)
        } }
    }
}
@Composable private fun Candidates(s:PaceState) {
    Panel {
        Text("새로운 사실 후보 · 확인 대기",style=MaterialTheme.typography.titleMedium)
        s.candidates.forEach { Text(it,style=MaterialTheme.typography.bodyMedium) }
        Copy("별도의 사실·사용 범위 검토가 필요합니다. 기존 경력에 자동으로 반영되지 않습니다.")
    }
}
@Composable private fun Result(s:PaceState,c:PaceCallbacks,modifier:Modifier) {
    ScrollBody(modifier) {
        Kicker(if(s.sessionState=="ABORTED") "평가 없이 중단한 연습" else "나의 연습 돌아보기")
        Text("말한 경험을,\n다시 살펴보세요.",style=MaterialTheme.typography.headlineLarge)
        Copy("확인 답변과 피드백을 구분해 보여드립니다. 저장은 직접 선택해 주세요.")
        if(s.answers.isEmpty()) Panel { Text("아직 확인한 답변이 없습니다.",style=MaterialTheme.typography.titleMedium);Copy("연습 화면에서 초안을 확인한 뒤 제출해 주세요.") }
        else {
            Kicker("내가 확인한 답변 · ${s.answers.size}개")
            s.answers.forEach { a -> Panel {
                Text(s.questions.find{it.id==a.questionId}?.text?:"확인 답변",style=MaterialTheme.typography.titleMedium)
                Text(a.text,style=MaterialTheme.typography.bodyLarge)
                Kicker("답변 v${a.revision} · 사용자 확인 답변")
            } }
        }
        if(s.showFeedback) {
            if(s.feedback.isEmpty()) Copy("표시할 피드백이 없습니다. 확인 답변은 별도로 저장할 수 있습니다.") else Feedback(s)
            if(s.candidates.isNotEmpty()) Candidates(s)
        } else Copy("모의 면접 피드백은 종료 후 표시됩니다.")
        Export(s,c)
        Secondary("홈으로"){c.navigate(PaceScreen.HOME)}
    }
}
@Composable private fun Export(s:PaceState,c:PaceCallbacks) {
    Column(verticalArrangement=Arrangement.spacedBy(12.dp)) {
        Kicker("수동 저장")
        if(s.sessionState in listOf("COMPLETED","ABORTED")) Action(s,c,PaceAction.PREPARE_RESULT,"면접 결과 파일 준비")
        if(s.validated) {
            Action(s,c,PaceAction.PREPARE_SESSION,"다시 이어갈 세션 파일 준비")
            Action(s,c,PaceAction.PREPARE_SNAPSHOT,"화면 기록으로 복구 파일 준비")
            Primary("저장 위치 선택·내보내기",!s.busy&&s.exportReady,"save"){c.action(PaceAction.SAVE)}
        }
        Copy("화면 기록 복구 파일은 미제출 초안과 화면에 숨긴 평가를 제외합니다. 전체 세션 파일에는 AI 기록이 포함됩니다. 다시 가져온 뒤 검토가 필요합니다.")
        if(s.mode=="simulation" && s.sessionState !in listOf("COMPLETED","ABORTED")) Copy("진행 중인 모의 면접의 전체 세션 파일에는 화면에 숨긴 평가도 포함될 수 있습니다.")
    }
}
@Composable private fun Details(title:String,initiallyOpen:Boolean=false,content:@Composable ColumnScope.()->Unit) {
    var open by remember(title) { mutableStateOf(initiallyOpen) }
    Column(Modifier.fillMaxWidth(),verticalArrangement=Arrangement.spacedBy(10.dp)) {
        TextButton(onClick={open=!open},modifier=Modifier.fillMaxWidth(),contentPadding=PaddingValues(vertical=10.dp)) {
            Text(title,Modifier.weight(1f),style=MaterialTheme.typography.labelLarge)
            Text(if(open) "−" else "+",style=MaterialTheme.typography.titleLarge)
        }
        if(open) Column(verticalArrangement=Arrangement.spacedBy(12.dp),content=content)
    }
}
@Composable private fun PagedText(text:String) {
    val pages=remember(text){text.chunked(12000).ifEmpty{listOf("")}}
    var page by remember(text){mutableIntStateOf(0)}
    if(pages.size>1) Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,
        horizontalArrangement=Arrangement.SpaceBetween) {
        TextButton(onClick={page--},enabled=page>0,modifier=Modifier.testTag("source-previous")){Text("이전")}
        Text("${page+1} / ${pages.size}",style=MaterialTheme.typography.labelMedium,modifier=Modifier.testTag("source-page"))
        TextButton(onClick={page++},enabled=page<pages.lastIndex,modifier=Modifier.testTag("source-next")){Text("다음")}
    }
    Text(pages[page],style=MaterialTheme.typography.bodyMedium)
}
private fun statusLabel(status:String)=when(status){"pending"->"답변 전";"answered"->"답변 확인됨";"skipped"->"건너뜀";else->status}

@Composable private fun PaceIcon(name:String,modifier:Modifier=Modifier) {
    val color=LocalContentColor.current
    Canvas(modifier.size(20.dp)) {
        val k=size.minDimension/24f
        val path=Path()
        fun move(x:Float,y:Float)=path.moveTo(x*k,y*k)
        fun line(x:Float,y:Float)=path.lineTo(x*k,y*k)
        when(name) {
            "arrow"->{move(5f,12f);line(19f,12f);move(13f,6f);line(19f,12f);line(13f,18f)}
            "back"->{move(19f,12f);line(5f,12f);move(11f,6f);line(5f,12f);line(11f,18f)}
            "plus"->{move(12f,5f);line(12f,19f);move(5f,12f);line(19f,12f)}
            "check"->{move(5f,12f);line(10f,17f);line(19f,7f)}
            "home"->{move(3f,11f);line(12f,3f);line(21f,11f);move(5f,10f);line(5f,21f);line(10f,21f);line(10f,15f);line(14f,15f);line(14f,21f);line(19f,21f);line(19f,10f)}
            "files"->{move(3f,7f);line(12f,3f);line(21f,7f);line(12f,11f);path.close();move(3f,12f);line(12f,16f);line(21f,12f);move(3f,17f);line(12f,21f);line(21f,17f)}
            "mic"->{move(9f,4f);line(15f,4f);line(15f,14f);line(9f,14f);path.close();move(6f,10f);line(6f,16f);line(12f,19f);line(18f,16f);line(18f,10f);move(12f,19f);line(12f,22f)}
            "link"->{move(9f,15f);line(15f,9f);move(9f,7f);line(6f,7f);line(3f,10f);line(3f,15f);line(6f,18f);line(10f,18f);move(14f,6f);line(18f,6f);line(21f,9f);line(21f,14f);line(18f,17f);line(15f,17f)}
            else->{move(19f,6f);line(14f,3f);line(7f,5f);line(3f,11f);line(5f,18f);line(12f,21f);line(19f,18f);move(16f,12f);line(20f,12f)}
        }
        drawPath(path,color,style=Stroke(width=1.6f*k))
    }
}
