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
const phone=(id,screen,alt=false)=>`<div class="phone ${id}${alt?' alt':''}" data-concept="${id}"><div class="screen">${status()}${screen}<div class="home-indicator"></div></div></div>`;
const chip=(text,name='link')=>`<span class="chip">${icon(name,12)}${text}</span>`;
const wave=()=>`<div class="wave" aria-hidden="true">${[4,7,12,19,9,16,7,12,20,13,7,16,10,5,11,18,8,4].map(h=>`<i style="--h:${h}px"></i>`).join('')}</div>`;
const orb=(question=false)=>`<div class="orb-scene ${question?'question-orb':''}" aria-hidden="true"><span class="orb-dot"></span><div class="orb">${icon('mic',42)}</div>${!question?'<span class="orb-caption">A SPACE FOR YOUR STORY</span>':''}</div>`;

function folioHome(){return `${appbar()}<div class="body"><div class="eyebrow muted">YOUR NEXT CHAPTER</div><h2 class="folio-title">경험은 이미,<br><strong>당신 안에.</strong></h2><p class="subtext">이제, 면접에서 전할 차례입니다.</p>
<div class="document-scene" aria-label="경력, 이력서, 지원 공고가 연결된 자료"><div class="document doc-a">PROFILE<div class="doc-title">My story.</div><div class="doc-lines"><i></i><i></i><i></i><i></i></div></div><div class="document doc-b">RESUME<div class="doc-title">A new<br>chapter.</div><div class="doc-lines"><i></i><i></i><i></i></div></div><div class="document doc-c">JOB DESCRIPTION<div class="doc-title">Next step.</div><div class="doc-lines"><i></i><i></i><i></i></div></div><span class="document-stamp">READY<br>TO TELL</span></div>
<div class="row section-heading"><span>오늘의 연습</span><span class="micro">서비스 운영 직무</span></div>
<div class="practice-row"><span class="number">01</span><div><h3>짧게, 한 질문</h3><p>한 가지 경험에 집중하기</p></div>${circle('arrow','한 질문 연습 화면 보기','data-focus="question"')}</div>
<div class="practice-row"><span class="number">05</span><div><h3>차분하게, 한 회차</h3><p>답변의 흐름을 이어가기</p></div>${circle('arrow','한 회차 연습 화면 보기','data-focus="question"')}</div></div>
<div class="dock">${primary('나의 이야기 시작하기')}<div class="session-ref"><span>선택한 자료 3개 · 검토 완료</span><span>수동 저장</span></div></div>`;}
function folioQuestion(){return `${appbar(true)}<div class="body"><div class="row"><span class="eyebrow muted">THE FIRST QUESTION</span><span class="micro">01 / 05</span></div><div class="question-number">01</div><h2 class="question-title">문제를 해결했던 경험과<br>직접 맡은 역할을<br>알려주세요.</h2><div class="evidence">${chip('팀 프로젝트')}${chip('문제 해결 역량','file')}</div>
<div class="answer-section"><div class="row"><label>나의 답변</label><span class="micro">제출 전 수정할 수 있어요</span></div>${field()}<div class="answer-tools">${circle('mic','말로 답변하기','data-demo="음성 조작의 디자인 예시입니다. 실제 마이크는 켜지지 않습니다."','filled')}<span>말로 답변하기</span></div></div></div>
<div class="dock">${confirm()}${primary('확인한 답변 제출','data-submit')}<p class="bottom-note">답변을 확인한 뒤 제출해 주세요. 자동 제출되지 않습니다.</p></div>`;}

function orbitHome(){return `${appbar()}<div class="orbit-intro">${chip('VOICE PRACTICE','mic')}<h2>당신의 이야기에,<br>귀 기울이는 시간.</h2><p>말하고, 돌아보고, 조금 더 나답게.</p></div>${orb()}
<div class="voice-sheet"><div class="mode-switch" data-mode-group><button class="selected" aria-pressed="true">한 질문 연습</button><button aria-pressed="false">한 회차 연습</button></div><h3 class="sheet-title">준비되면 시작해 주세요.</h3>${primary('답변 연습 시작')}<div class="sheet-meta"><span>서비스 운영 · 자료 3개</span><span>한국어 음성</span></div></div>`;}
function orbitQuestion(){return `${appbar(true)}<div class="question-intro">${dots('progress-dots')}<h2>문제를 해결했던 경험과<br>직접 맡은 역할을<br>알려주세요.</h2>${chip('팀 프로젝트 · 문제 해결 역량')}</div>${orb(true)}
<div class="voice-sheet">${wave()}<div class="row"><label>답변 초안</label><span class="micro">말하거나 직접 입력하세요</span></div>${field()}${confirm()}${primary('확인한 답변 제출','data-submit')}<div class="sheet-meta"><button class="chip" data-demo="음성 조작의 디자인 예시입니다. 실제 마이크는 켜지지 않습니다.">${icon('mic',12)}말로 답변하기</button><span>질문 1 / 5</span></div></div>`;}

function blocksHome(){return `${appbar()}<div class="body"><div class="eyebrow">MY INTERVIEW WORKSPACE</div><h2>준비된 경험,<br>꺼내어 말해요.</h2><div class="bento"><div class="tile tile-feature"><div class="eyebrow">이번 지원</div><h3>서비스<br>운영 직무</h3><div class="mini-folders" aria-hidden="true"><i></i><i></i><i></i></div><span class="tile-caption">내 경험에서 시작하는 답변</span></div><div class="tile tile-docs"><div class="tile-icon">${icon('layers',17)}</div><div class="big-number">3</div><p>선택한 자료<br>검토 완료</p></div><button class="tile tile-choice" data-focus="question"><div><h3>한 질문</h3><p>한 번에 하나씩</p></div>${icon('arrow')}</button><button class="tile tile-choice secondary" data-focus="question"><div><h3>한 회차</h3><p>답변의 흐름을 따라</p></div>${icon('arrow')}</button></div><div class="context-row">${icon('file')}<span>경력 · 이력서 · 지원 공고</span>${icon('check',15)}</div></div>
<div class="bottom-nav"><button class="selected" aria-pressed="true" data-focus="home">${icon('home')}홈</button><button data-focus="question">${icon('mic')}연습</button><button data-demo="자료 목록은 선택한 디자인 방향에 맞춰 이어서 설계합니다.">${icon('layers')}자료</button></div>`;}
function blocksQuestion(){return `${appbar(true)}${dots('segmented-progress')}<div class="body"><div class="question-module"><div class="row"><span class="eyebrow">문제 해결 · 역할과 기여</span><span class="q-number">01</span></div><h2>문제를 해결했던 경험과<br>직접 맡은 역할을<br>알려주세요.</h2><span class="micro">상황 → 직접 한 일 → 결과</span></div><div class="evidence-module">${icon('link',15)}<span>팀 프로젝트에서 경험을 떠올려 보세요.</span></div><div class="answer-module"><div class="row"><span>나의 답변</span><div class="mini-tabs" data-mode-group><button class="selected" aria-pressed="true">입력</button><button aria-pressed="false" data-demo="음성 모드의 디자인 예시입니다. 실제 마이크는 켜지지 않습니다.">음성</button></div></div>${field()}<p class="micro">초안은 자유롭게 수정할 수 있습니다.</p></div></div><div class="dock">${confirm()}${primary('확인한 답변 제출','data-submit')}</div>`;}

function trailHome(){return `${appbar()}<div class="body"><h2 class="trail-title">준비는 한 걸음씩.<br><span>답변은 나답게.</span></h2><p class="subtext">지금 할 일부터, 차근차근 안내할게요.</p><div class="journey"><svg class="journey-line" viewBox="0 0 48 292" fill="none" aria-hidden="true"><path d="M20 5C20 40 33 46 22 82S8 130 20 165s10 64 0 115" stroke="currentColor" stroke-width="2" stroke-dasharray="3 5" stroke-linecap="round"/></svg><div class="journey-step"><span class="node">${icon('check')}</span><div><h3>자료 가져오기</h3><p>경력 · 이력서 · 지원 공고 3개</p></div></div><div class="journey-step"><span class="node">${icon('check')}</span><div><h3>내용 확인하기</h3><p>지원 직무와 포함한 경험을 확인했어요.</p></div></div><div class="journey-step active"><span class="node">3</span><div class="step-content"><h3>답변 연습하기</h3><div class="journey-preview"><span class="eyebrow">오늘의 첫 질문</span><p>문제를 해결했던 경험,<br>어떻게 이야기할까요?</p><div class="journey-switch" data-mode-group><button class="selected" aria-pressed="true">한 질문</button><button aria-pressed="false">한 회차</button></div></div></div></div></div><div class="prepared-note">${icon('sparkle')}이번에는 서비스 운영 직무를 연습해요.</div></div><div class="dock">${primary('첫 질문으로 가기')}<p class="bottom-note">연습을 마치면 결과를 직접 저장할 수 있어요.</p></div>`;}
function trailQuestion(){return `${appbar(true)}<div class="body"><div class="session-trail"><span>나의 연습</span>${'<i></i>'.repeat(5)}<span>1 / 5</span></div><div class="question-paper"><span class="eyebrow">첫 번째 질문</span><h2>문제를 해결했던 경험과<br>직접 맡은 역할을<br>알려주세요.</h2><p class="micro">상황부터 천천히 이야기해 보세요.</p></div><div class="prompt-note"><strong>경험을 떠올릴 실마리</strong><p>팀 프로젝트 · 문제 해결 역량</p></div><div class="answer-paper"><div class="row"><span>나의 답변 초안</span>${circle('mic','말로 답변하기','data-demo="음성 조작의 디자인 예시입니다. 실제 마이크는 켜지지 않습니다."')}</div>${field()}<p class="micro">떠오르는 내용을 적고, 제출 전에 다듬어 주세요.</p></div></div><div class="dock">${confirm()}${primary('확인한 답변 제출','data-submit')}<p class="bottom-note">내가 한 일과 동료의 기여를 구분해 주세요.</p></div>`;}

const speechObject=()=>`<div class="speech-object" aria-hidden="true"><svg viewBox="0 0 240 176" fill="none"><path d="M42 28h126a29 29 0 0 1 29 29v41a29 29 0 0 1-29 29h-31l-35 29v-29H42a29 29 0 0 1-29-29V57a29 29 0 0 1 29-29Z" stroke="currentColor" stroke-width="1.2"/><path d="M75 11h126a26 26 0 0 1 26 26v46a26 26 0 0 1-26 26h-25" stroke="currentColor" stroke-width="1.2"/><path d="M73 66h17v17H73V66Zm38 0h17v17h-17V66Z" fill="currentColor"/><circle cx="205" cy="123" r="10" fill="var(--signal)"/></svg><span class="object-caption">MY EXPERIENCE. MY WORDS.</span></div>`;
function stillHome(){return `<div class="appbar"><div class="wordmark">CG / PRACTICE</div><button class="circle-button" aria-label="연습 메뉴" data-demo="메뉴는 선택한 디자인 방향에 맞춰 이어서 설계합니다."><span class="menu-lines"></span></button></div><div class="body"><h2 class="still-title"><span class="light">말할 준비가</span><br>되는 순간.</h2>${speechObject()}<p class="still-copy">오늘은 한 가지 경험만<br>명확하게 말해보세요.</p><div class="mode-line" data-mode-group><button class="selected" aria-pressed="true">한 질문</button><button aria-pressed="false">한 회차</button><span class="micro" style="margin-left:auto">나의 속도로</span></div></div><div class="dock"><button class="primary-action" data-focus="question"><span>연습 시작</span><span class="action-disc">${icon('arrow')}</span></button><button class="text-action" data-demo="현재는 자료 3개가 준비된 합성 상태입니다. 자료 검토 과정은 추후 설계합니다.">서비스 운영 직무 · 자료 3개 확인</button></div>`;}
function stillQuestion(){return `<div class="appbar">${circle('back','시작 화면 보기','data-focus="home"')}<span class="eyebrow muted">STAY WITH YOUR STORY</span></div><div class="body"><div class="question-counter"><strong>01</strong><span>/ 05</span><i class="small-dot"></i></div><h2 class="question-main">문제를 해결했던<br>경험과 직접 맡은<br>역할을 알려주세요.</h2><div class="question-context">팀 프로젝트 · 문제 해결 역량</div></div><div class="answer-dock"><span class="eyebrow">YOUR ANSWER</span>${field()}${confirm()}<div class="control-line"><div class="record-control">${circle('mic','말로 답변하기','data-demo="음성 조작의 디자인 예시입니다. 실제 마이크는 켜지지 않습니다."')}<span>말로 답변하기</span></div><button class="next-control" data-submit aria-label="확인한 답변 제출">${icon('arrow')}</button></div><p class="bottom-note">확인한 답변만 제출됩니다. 자동 저장되지 않습니다.</p></div>`;}

const studies=[
  {id:'folio',name:'FOLIO',ko:'에디토리얼',desc:'문서에서 시작해, 나의 이야기로.',detail:'세리프와 산세리프의 대비, 비대칭 문서 오브젝트, 열린 목록. 개인의 경험을 한 편의 이야기처럼 다룹니다.',home:folioHome,question:folioQuestion},
  {id:'orbit',name:'ORBIT',ko:'보이스 스튜디오',desc:'목소리에 집중하는 작은 스튜디오.',detail:'입체 음성 오브젝트, 중앙 정렬 질문, 반투명 컨트롤 시트. 자료 관리보다 말하는 순간을 중심에 둡니다.',home:orbitHome,question:orbitQuestion},
  {id:'blocks',name:'BLOCKS',ko:'모듈러 워크스페이스',desc:'준비된 경험을 손에 잡히는 블록으로.',detail:'비대칭 모듈, 크기로 구분한 정보, 색으로 나눈 기능. 자료와 연습을 한눈에 조작하는 도구의 감각입니다.',home:blocksHome,question:blocksQuestion},
  {id:'trail',name:'TRAIL',ko:'가이드 저니',desc:'무엇부터 할지, 길이 보이는 연습.',detail:'준비 순서를 잇는 경로, 종이처럼 겹치는 질문, 부드러운 문장. 처음 쓰는 사람도 현재 위치를 알 수 있습니다.',home:trailHome,question:trailQuestion},
  {id:'still',name:'STILL',ko:'타이포 미니멀',desc:'하나의 질문. 충분한 여백.',detail:'넓은 여백, 큰 질문, 절제된 선, 하단 조작부. 조용하고 단정한 화면에서 다음 한 문장에 집중합니다.',home:stillHome,question:stillQuestion},
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
