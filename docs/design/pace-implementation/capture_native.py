"""Capture only the dedicated PACE AVD. Never targets an attached physical phone."""
from pathlib import Path
import subprocess, json, time, re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
ADB='/home/inno/.local/share/careerground-android/sdk/platform-tools/adb'
SERIAL='emulator-5580'
PACKAGE='dev.careerground.interview.design'
ACTIVITY=PACKAGE+'/.DesignPreviewActivity'
OUT=ROOT/'native'
OUT.mkdir(exist_ok=True)

def adb(*args,binary=False):
    r=subprocess.run([ADB,'-s',SERIAL,*args],check=True,capture_output=True,timeout=45)
    return r.stdout if binary else r.stdout.decode(errors='replace').strip()

assert 'careerground-pace-api36' in adb('emu','avd','name')
assert adb('shell','getprop','sys.boot_completed')=='1'
checks=[]
def save_checks():
    (ROOT/'native-validation.json').write_text(json.dumps({'serial':SERIAL,'scope':'Native Compose preview with synthetic states; no live audio, file or AI calls','checks':checks},ensure_ascii=False,indent=2)+'\n')
def hierarchy(width,height,require_submit=False):
    # Resize can leave a stale accessibility tree briefly even after the frame redraws.
    for attempt in range(6):
        adb('shell','uiautomator','dump','/sdcard/pace-ui.xml')
        xml=adb('shell','cat','/sdcard/pace-ui.xml')
        root=ET.fromstring(xml)
        submit=[n for n in root.iter('node') if n.attrib.get('text') in ['확인한 답변 제출','수정 답변 제출']]
        coords=[list(map(int,re.findall(r'\d+',n.attrib['bounds']))) for n in submit]
        if (coords or not require_submit) and all(b[2]<=width and b[3]<=height for b in coords):return xml,root
        time.sleep(1)
    raise AssertionError(f'Controls outside {width}x{height}: {coords}')


def capture(name,scenario,theme='light',width=1080,height=2340,scale=1.0,keyboard=False):
    adb('shell','wm','size',f'{width}x{height}')
    adb('shell','wm','density','420')
    adb('shell','settings','put','system','font_scale',str(scale))
    adb('shell','am','start','-W','-S','-n',ACTIVITY,'--es','scenario',scenario,'--es','theme',theme)
    time.sleep(1)
    xml,root=hierarchy(width,height,scenario in ['interview','draft','voice','simulation'])
    if keyboard:
        node=next(n for n in root.iter('node') if 'EditText' in n.attrib.get('class',''))
        x1,y1,x2,y2=map(int,re.findall(r'\d+',node.attrib['bounds']))
        adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
        time.sleep(1)
        xml,root=hierarchy(width,height,scenario in ['interview','draft','voice','simulation'])
    png=adb('exec-out','screencap','-p',binary=True)
    assert png[:8]==b'\x89PNG\r\n\x1a\n'
    (OUT/f'{name}.png').write_bytes(png)
    (OUT/f'{name}.xml').write_text(xml)
    controls=[]
    for node in root.iter('node'):
        if node.attrib.get('text') in ['확인한 답변 제출','수정 답변 제출']:
            bounds=list(map(int,re.findall(r'\d+',node.attrib['bounds'])))
            assert bounds[2]<=width and bounds[3]<=height
            controls.append({'text':node.attrib['text'],'bounds':bounds,'textNodeEnabled':node.attrib.get('enabled')})
    ime=adb('shell','dumpsys','input_method') if keyboard else ''
    shown='mInputShown=true' in ime or 'mIsInputViewShown=true' in ime
    if keyboard:assert shown, 'Keyboard was requested but not observed'
    ime_bounds=[list(map(int,re.findall(r'\d+',n.attrib['bounds']))) for n in root.iter('node')
        if 'inputmethod' in n.attrib.get('package','')]
    ime_top=min((b[1] for b in ime_bounds),default=None)
    if keyboard and ime_top is not None:assert all(c['bounds'][3]<=ime_top for c in controls), 'Submit obscured by keyboard'
    checks.append({'name':name,'scenario':scenario,'theme':theme,'width':width,'height':height,'fontScale':scale,
                   'keyboardRequested':keyboard,'submitControls':controls,
                   'imeObserved':shown,'keyboardTop':ime_top})
    save_checks()

try:
    for scenario in ['home','interview','result','import','review','empty','login','voice','generating','error','paused','expired','simulation','saved-ready']:
        capture(scenario+'-light',scenario)
    for scenario in ['home','interview','result','review','import']:
        capture(scenario+'-dark',scenario,'dark')
    capture('interview-narrow','draft',width=884,height=2208)
    capture('interview-wide','draft',width=1768,height=2208)
    capture('interview-landscape','draft',width=2208,height=1768)
    capture('interview-large-font','draft',width=1080,height=2340,scale=1.5)
    capture('home-large-font','home',width=1080,height=2340,scale=1.5)
    capture('interview-keyboard','draft',keyboard=True)
    (ROOT/'native-validation.json').write_text(json.dumps({'serial':SERIAL,'scope':'Native Compose preview with synthetic states; no live audio, file or AI calls','checks':checks},ensure_ascii=False,indent=2)+'\n')
finally:
    adb('shell','settings','put','system','font_scale','1.0')
    adb('shell','wm','size','reset');adb('shell','wm','density','reset')
print('Captured',len(checks),'native configurations.')
