/* Local, synthetic design studies. No network, storage, microphone or functional app bindings. */
const paths = {
  arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
  back:'<path d="M19 12H5m6-6-6 6 6 6"/>',
  mic:'<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M6 10v2a6 6 0 0 0 12 0v-2M12 18v3m-3 0h6"/>',
  layers:'<path d="m3 7 9-4 9 4-9 4-9-4Zm0 5 9 4 9-4M3 17l9 4 9-4"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  file:'<path d="M6 3h8l4 4v14H6V3Zm8 0v5h4M9 12h6m-6 4h6"/>',
  home:'<path d="m3 11 9-8 9 8M5 9v12h5v-7h4v7h5V9"/>',
  grid:'<rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/>',
  moon:'<path d="M20 14a8 8 0 0 1-10-10 8 8 0 1 0 10 10Z"/>',
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
  wifi:'<path d="M3 8a14 14 0 0 1 18 0M6 12a9 9 0 0 1 12 0m-9 4a4 4 0 0 1 6 0"/><circle cx="12" cy="20" r=".5" fill="currentColor"/>',
  sparkle:'<path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z"/>',
  link:'<path d="m10 13 4-4M8 15l-2 2a3 3 0 0 1-4-4l4-4a3 3 0 0 1 4 0m4 0 2-2a3 3 0 0 1 4 4l-4 4a3 3 0 0 1-4 0"/>',
};
const icon=(name,size=20)=>`<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.arrow}</svg>`;
const mark='<svg class="brand-symbol" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M18.5 6.5a8 8 0 1 0 0 11" stroke="currentColor" stroke-width="3.2"/><circle cx="18" cy="12" r="2.4" fill="currentColor"/></svg>';
const status=()=>`<div class="status"><span>9:41</span><div class="status-icons">${icon('wifi',15)}<span class="battery"></span></div></div>`;
const circle=(name,label,attributes='',extra='')=>`<button class="circle-button ${extra}" aria-label="${label}" ${attributes}>${icon(name)}</button>`;
const appbar=(question=false,word='CareerGround')=>`<div class="appbar">${question?circle('back','시작 화면 보기','data-focus="home"'):`<div class="wordmark">${mark}${word}</div>`}${question?'<span class="eyebrow muted">면접 연습</span>':circle('plus','연습 자료 가져오기','data-demo="자료 가져오기 화면은 선택한 디자인 방향에 맞춰 이어서 설계합니다."')}</div>`;
const primary=(label='연습 시작',attributes='data-focus="question"',extra='')=>`<button class="primary-action ${extra}" ${attributes}><span>${label}</span>${icon('arrow')}</button>`;
const confirm=()=>'<label class="confirm"><input type="checkbox" data-confirm><span>숫자·기간·역할·동료의 기여를 확인했습니다.</span></label>';
const field=(height='',label='답변 초안')=>`<textarea class="field" aria-label="${label}" ${height?`style="height:${height}px"`:''} placeholder="당시 상황과 직접 한 행동부터 이야기해 주세요."></textarea>`;
const dots=(className)=>`<div class="${className}" aria-label="질문 1 / 5">${'<i></i>'.repeat(5)}</div>`;
const phone=(id,screen,alt=false)=>`<div class="phone ${id==='field'?'clear':id}${alt?' alt':''}" data-concept="${id}"><div class="screen">${status()}${screen}<div class="home-indicator"></div></div></div>`;
const chip=(text,name='link')=>`<span class="chip">${icon(name,12)}${text}</span>`;

const questionText='문제를 해결했던 경험과<br>직접 맡은 역할을<br>알려주세요.';
const hint='<span>팀 프로젝트</span><span>문제 해결 역량</span>';
const homeTitle=()=>'<div class="home-intro"><span class="kicker">나의 면접 준비</span><h2>쌓아온 경험을,<br>나의 답변으로.</h2><p>한 질문부터 차분하게 시작해 보세요.</p></div>';
const done=()=>`<span class="done">${icon('check',13)}검토 완료</span>`;
const docStrip=()=>`<div class="doc-strip">${icon('layers',17)}<span>경력 · 이력서 · 지원 공고</span>${done()}</div>`;
const nav=(floating=false)=>`<div class="bottom-nav ${floating?'floating':''}"><button class="selected" aria-pressed="true" data-focus="home">${icon('home',19)}<span>홈</span></button><button data-focus="question">${icon('mic',19)}<span>연습</span></button><button data-demo="자료 화면은 선택한 디자인으로 이어서 설계합니다.">${icon('layers',19)}<span>자료</span></button></div>`;
const modes=()=>'<div class="input-modes" data-mode-group><button class="selected" aria-pressed="true">직접 입력</button><button aria-pressed="false" data-demo="음성 입력의 시각 예시입니다. 마이크는 켜지지 않습니다.">음성 입력</button></div>';
const step=()=>'<div class="step-progress" aria-label="질문 1 / 5"><span>질문 <b>1</b> / 5</span><div><i></i><i></i><i></i><i></i><i></i></div></div>';
const answerLabel=()=>'<div class="row answer-label"><strong>답변 초안</strong><span class="micro">제출 전 수정 가능</span></div>';
const factDock=()=>`<div class="dock">${confirm()}${primary('확인한 답변 제출','data-submit')}</div>`;
const choiceTile=(full=false)=>`<button class="practice-tile ${full?'full':''}" data-focus="question"><span class="tile-label">${full?'흐름을 이어서':'가볍게 시작'}</span><h3>${full?'한 회차':'한 질문'}</h3><span class="tile-bottom"><span>${full?'질문 5개':'질문 1개'}</span>${icon('arrow',20)}</span></button>`;
const reviewSummary=()=>`<div class="review-summary"><span>${icon('check',16)}자료 가져오기</span><i></i><span>${icon('check',16)}내용 확인</span><i></i><strong>연습 준비</strong></div>`;

function sageHome(){return `${appbar()}<div class="body">${homeTitle()}<div class="sage-grid"><section class="role-tile"><span class="kicker">이번 지원</span><h3>서비스<br>운영 직무</h3><span class="role-foot">내 경험에 맞춘 면접 연습</span><div class="role-lines" aria-hidden="true"><i></i><i></i><i></i></div></section><button class="docs-tile" data-demo="검토한 자료 3개의 합성 예시입니다.">${icon('layers',22)}<strong>3<span>개</span></strong><span>준비한 자료</span>${done()}</button>${choiceTile()}${choiceTile(true)}</div>${docStrip()}</div>${nav(true)}`;}
function sageQuestion(){return `${appbar(true)}<div class="body">${step()}<section class="sage-question"><div class="row"><span class="kicker">문제 해결 · 역할과 기여</span><span class="question-index">01</span></div><h2>${questionText}</h2><p>상황 → 직접 한 일 → 결과</p></section><div class="reference-line">${icon('link',16)}<span>팀 프로젝트에서 경험을 떠올려 보세요.</span></div><section class="sage-answer">${answerLabel()}${modes()}${field()}<p class="micro">직접 한 일과 동료의 기여를 구분해 주세요.</p></section></div>${factDock()}`;}

function frameHome(){return `${appbar()}<div class="body">${homeTitle()}<section class="workspace-panel"><div class="panel-heading"><span class="kicker">준비된 연습</span>${done()}</div><h3>서비스 운영 직무</h3><div class="panel-documents"><span>${icon('file',17)}경력</span><span>${icon('file',17)}이력서</span><span>${icon('file',17)}지원 공고</span></div><div class="panel-divider"></div><div class="row panel-label"><strong>어떻게 연습할까요?</strong><span>자료 3개</span></div><div class="panel-choices" data-mode-group><button class="selected" aria-pressed="true"><span class="select-dot"></span><div><h4>한 질문</h4><p>하나의 경험에 집중 · 질문 1개</p></div>${icon('arrow',18)}</button><button aria-pressed="false"><span class="select-dot"></span><div><h4>한 회차</h4><p>답변의 흐름을 따라 · 질문 5개</p></div>${icon('arrow',18)}</button></div></section><div class="quiet-tip"><span class="tip-mark">i</span><p>답변은 제출하기 전에 수정할 수 있어요.</p></div></div><div class="dock">${primary('선택한 연습 시작')}<p class="bottom-note">지금 준비한 자료로 첫 질문을 확인합니다.</p></div>`;}
function frameQuestion(){return `${appbar(true)}<div class="body">${step()}<section class="editor-panel"><div class="panel-heading"><span class="kicker">문제 해결 · 역할과 기여</span>${icon('link',16)}</div><h2>${questionText}</h2><div class="context-tags">${hint}</div><div class="editor-divider"><span>나의 답변</span></div>${modes()}${field()}<div class="editor-foot">${icon('file',14)}<span>초안을 다듬은 뒤 제출해 주세요.</span></div></section></div>${factDock()}`;}

function paceHome(){return `${appbar()}<div class="body">${homeTitle()}<div class="pace-role"><div><span class="kicker">이번 지원</span><h3>서비스 운영 직무</h3></div>${icon('arrow',20)}</div><section class="prep-rail"><div class="rail-node finished">${icon('check',15)}</div><div class="rail-copy"><strong>연습 자료가 준비됐어요.</strong><p>선택한 자료 3개 · 내용 검토 완료</p></div><div class="rail-node current">${icon('mic',16)}</div><div class="rail-copy"><strong>나에게 맞는 길이로 시작하세요.</strong><p>두 연습 모두 내 자료를 바탕으로 진행해요.</p></div></section><div class="practice-list"><button data-focus="question"><span class="length-block"><b>1</b><small>질문</small></span><div><h3>한 질문에 집중</h3><p>하나의 경험을 선명하게</p></div>${icon('arrow',20)}</button><button data-focus="question"><span class="length-block"><b>5</b><small>질문</small></span><div><h3>한 회차 이어서</h3><p>답변의 흐름을 자연스럽게</p></div>${icon('arrow',20)}</button></div></div>${nav()}`;}
function paceQuestion(){return `${appbar(true)}<div class="body"><div class="pace-counter"><span class="kicker">한 회차 연습</span><span>질문 1 / 5</span></div><section class="question-rail"><div class="vertical-steps" aria-label="질문 1 / 5"><b>1</b><i></i><i></i><i></i><i></i></div><div class="rail-question"><span class="kicker">문제 해결 · 역할과 기여</span><h2>문제를 해결했던<br>경험과 직접 맡은<br>역할을 알려주세요.</h2><div class="context-tags">${hint}</div></div></section><section class="pace-answer">${answerLabel()}${field()}<button class="voice-row" data-demo="음성 입력의 시각 예시입니다. 마이크는 켜지지 않습니다.">${icon('mic',18)}말로 답변하기<span>직접 입력도 가능해요</span></button></section></div>${factDock()}`;}

function fieldHome(){return `${appbar()}<div class="body"><div class="field-title"><span class="kicker">나의 면접 준비</span><h2>경험은 준비됐어요.<br><span>이제, 말해볼까요?</span></h2></div><div class="field-context"><div class="row"><h3>서비스 운영 직무</h3>${done()}</div><p>경력 · 이력서 · 지원 공고 <span>3개</span></p></div><div class="field-practice"><div class="row"><span class="kicker">오늘의 연습</span><span class="micro">나의 속도로</span></div><div class="field-choices">${choiceTile()}${choiceTile(true)}</div><p class="field-note">먼저 질문을 확인한 뒤 답변해 주세요.</p></div></div>${nav()}`;}
function fieldQuestion(){return `${appbar(true)}<div class="body"><div class="field-count"><span class="question-index">01</span><span>/ 05</span><span class="kicker">문제 해결</span></div><h2 class="field-question">문제를 해결했던<br>경험과 직접 맡은<br>역할을 알려주세요.</h2><div class="field-reference">${icon('link',15)}팀 프로젝트 · 문제 해결 역량</div></div><div class="field-answer"><div class="row"><strong>답변 초안</strong><button class="voice-button" data-demo="음성 입력의 시각 예시입니다. 마이크는 켜지지 않습니다.">${icon('mic',17)}말로 답변</button></div>${field()}${confirm()}${primary('확인한 답변 제출','data-submit')}<p class="bottom-note">제출 전까지 답변을 자유롭게 다듬을 수 있습니다.</p></div>`;}

function layerHome(){return `${appbar()}<div class="body"><h2 class="layer-title">나의 경험으로<br>준비하는 다음 면접.</h2><section class="layer-role"><div class="row"><span class="kicker">이번 지원</span>${done()}</div><h3>서비스 운영 직무</h3><p>답변의 재료가 준비되어 있어요.</p><div class="layer-docs"><span>경력</span><span>이력서</span><span>지원 공고</span><b>3개</b></div></section><div class="layer-heading"><span class="kicker">연습 길이 선택</span><span class="micro">나에게 맞게</span></div><div class="layer-options" data-mode-group><button class="selected" aria-pressed="true"><div><h3>한 질문</h3><p>하나의 경험에 집중</p></div><span class="option-count">1<span>개</span></span><span class="select-dot"></span></button><button aria-pressed="false"><div><h3>한 회차</h3><p>답변의 흐름을 따라</p></div><span class="option-count">5<span>개</span></span><span class="select-dot"></span></button></div></div><div class="dock">${primary('선택한 연습 시작')}<p class="bottom-note">답변 확인부터 결과 저장까지 직접 선택합니다.</p></div>`;}
function layerQuestion(){return `<div class="layer-question-zone">${appbar(true)}<div class="body">${step()}<span class="kicker">문제 해결 · 역할과 기여</span><h2>${questionText}</h2><div class="layer-question-reference">${icon('link',15)}팀 프로젝트 · 문제 해결 역량</div></div></div><section class="layer-answer"><div class="row"><strong>나의 답변</strong><span class="draft-badge">초안</span></div>${modes()}${field()}<p class="micro">제출 전에 답변을 다듬어 주세요.</p><div class="layer-submit">${confirm()}${primary('확인한 답변 제출','data-submit')}</div></section>`;}

const studies=[
 {id:'sage',name:'SAGE',ko:'정돈된 비대칭 모듈',detail:'이전 03의 구성을 가장 가깝게 다듬은 안. 직무·자료·연습을 크기가 다른 블록으로 나누고, 녹색과 여백으로 정돈했습니다.',home:sageHome,question:sageQuestion},
 {id:'frame',name:'FRAME',ko:'하나로 묶인 준비 패널',detail:'준비한 자료와 연습 선택을 한 장의 패널로 묶었습니다. 면접에서도 질문과 답변이 한 공간 안에서 자연스럽게 이어집니다.',home:frameHome,question:frameQuestion},
 {id:'pace',name:'PACE',ko:'순서가 보이는 열린 모듈',detail:'자료 준비에서 답변 연습으로 이어지는 짧은 세로 레일. 넓은 가로형 선택 행과 열린 질문 영역으로 다음 행동을 안내합니다.',home:paceHome,question:paceQuestion},
 {id:'field',name:'FIELD',ko:'여백을 넓힌 최소 구성',detail:'이전 05의 깔끔함에 가장 가까운 안. 자료는 얇은 요약선으로 줄이고, 연습 선택과 면접 질문에 넓은 공간을 줬습니다.',home:fieldHome,question:fieldQuestion},
 {id:'layer',name:'LAYER',ko:'녹색 헤더와 밝은 조작 영역',detail:'진한 녹색 영역에 준비한 직무와 질문을 담고, 밝은 영역에서 선택하고 답변합니다. 한 화면에서도 읽기와 조작의 구역이 뚜렷합니다.',home:layerHome,question:layerQuestion},
];
const params=new URLSearchParams(location.search);
let selected=Math.min(4,Math.max(0,(parseInt(params.get('concept')||'1',10)||1)-1));
let overview=params.get('view')==='overview'||!params.has('concept');
let alternate=false;
let toastTimer;
function notify(message){const el=document.querySelector('.toast');el.textContent=message;el.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.hidden=true,4500);}
function sizeOverview(){document.querySelectorAll('.scaled-phone').forEach(w=>{const factor=w.clientWidth/390;w.style.height=`${844*factor}px`;w.querySelector('.phone').style.transform=`scale(${factor})`;});}
function render(){
  const s=studies[selected];
  document.querySelector('main').classList.toggle('overview-mode',overview);
  document.querySelector('.concept-nav').innerHTML=studies.map((x,i)=>`<button class="nav-choice" data-select="${i}" aria-current="${!overview&&i===selected}"><span class="index">0${i+1}</span>${x.name}</button>`).join('')+`<button class="nav-choice nav-overview" data-overview aria-current="${overview}">${icon('grid',14)}5개 한눈에</button>`;
  const header=document.querySelector('.study-header');header.hidden=overview;
  header.innerHTML=`<div class="study-title"><h2>0${selected+1} / ${s.name}</h2><span>${s.ko}</span></div><p class="study-description">${s.detail}</p><button class="theme-control" data-theme aria-pressed="${alternate}">${icon(alternate?'sun':'moon',13)}${alternate?'기본 테마':'반대 테마'}</button>`;
  const stage=document.querySelector('.study-stage');stage.hidden=overview;
  stage.innerHTML=`<article class="phone-frame" id="home-frame"><div class="screen-label">START / 시작</div>${phone(s.id,s.home(),alternate)}</article><article class="phone-frame" id="question-frame"><div class="screen-label">PRACTICE / 질문과 답변</div>${phone(s.id,s.question(),alternate)}</article>`;
  const overviewStage=document.querySelector('.overview-stage');overviewStage.hidden=!overview;
  overviewStage.innerHTML=overview?studies.map((x,i)=>`<article class="overview-item"><h2>0${i+1} / ${x.name}</h2><p class="overview-desc">${x.ko}</p><div class="scaled-phone">${phone(x.id,x.home())}</div><button class="overview-choose" data-select="${i}">이 방향 크게 보기 ↗</button></article>`).join(''):'';
  if(overview)sizeOverview();
  document.title=`CareerGround — ${overview?'다섯 가지 디자인 방향':s.name+' / '+s.ko}`;
}
document.addEventListener('click',e=>{
  const button=e.target.closest('button');if(!button)return;
  if(button.hasAttribute('data-select')){selected=Number(button.dataset.select);overview=false;alternate=false;render();}
  else if(button.hasAttribute('data-overview')){overview=true;render();}
  else if(button.hasAttribute('data-theme')){alternate=!alternate;render();}
  else if(button.dataset.demo){notify(button.dataset.demo);}
  else if(button.dataset.focus){if(overview){selected=studies.findIndex(x=>x.id===button.closest('.phone').dataset.concept);overview=false;render();}document.getElementById(button.dataset.focus+'-frame').scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});notify(button.dataset.focus==='question'?'오른쪽의 질문·답변 화면에서 이 방향의 구성을 살펴보세요.':'시작 화면의 구성을 살펴보세요.');}
  else if(button.hasAttribute('data-submit')){const screen=button.closest('.screen');const box=screen.querySelector('[data-confirm]');if(!box.checked){box.focus();notify('내용 확인 체크를 선택한 뒤 제출 화면을 검토할 수 있습니다.');}else notify('제출 조작의 시각 예시입니다. 실제 답변 전송이나 AI 호출은 없습니다.');}
  const group=button.closest('[data-mode-group]');if(group){group.querySelectorAll('button').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});}
});
window.addEventListener('resize',sizeOverview);
render();
