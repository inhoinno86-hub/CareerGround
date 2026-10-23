from pathlib import Path
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1550,'height':1050},reduced_motion='reduce')
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((ROOT/'index.html').as_uri())
    page.evaluate('document.fonts.ready')
    page.wait_for_function("[...document.images].every(x=>x.complete&&x.naturalWidth>0)")
    page.screenshot(path=str(ROOT/'00-native-overview.png'),full_page=True)
    page.locator('[data-theme]').click()
    page.wait_for_function("[...document.images].every(x=>x.complete&&x.naturalWidth>0)")
    page.screenshot(path=str(ROOT/'01-native-dark-overview.png'),full_page=True)
    page.locator('[data-screen="interview"]').click()
    assert page.locator('#detail').is_visible()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors
    (ROOT/'gallery-validation.json').write_text(json.dumps({'pageErrors':errors,'allNativeImagesLoaded':True,
        'themeSwitch':'PASS','detailSwitch':'PASS','mobileWidth':390,'pageOverflow':False},ensure_ascii=False,indent=2)+'\n')
    browser.close()
print('Native gallery rendering/interaction checks PASS')
