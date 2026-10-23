"""Render local design artifacts with an independent headless browser."""
from pathlib import Path
import json

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent


def metrics(page):
    return page.evaluate("""() => ({
      width:innerWidth,
      pageOverflow:document.documentElement.scrollWidth>innerWidth,
      phones:[...document.querySelectorAll('.study-stage .phone')].map(p=>({
        concept:p.dataset.concept,width:p.clientWidth,
        overflow:p.scrollHeight-p.clientHeight,
        scrollWidth:p.scrollWidth-p.clientWidth,
        controls:[...p.querySelectorAll('.primary-action,.control-line,.bottom-nav')].map(b=>({
          bottom:Math.round(b.getBoundingClientRect().bottom-p.getBoundingClientRect().top),
          height:Math.round(b.getBoundingClientRect().height)
        }))
      }))
    })""")


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"]
    )
    page = browser.new_page(
        viewport={"width": 1380, "height": 1250},
        color_scheme="light", reduced_motion="reduce",
    )
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto((ROOT / "index.html").as_uri())
    page.evaluate("document.fonts.ready")
    checks = []
    for i, name in enumerate(["sage", "frame", "pace", "field", "layer"]):
        page.evaluate("i=>{selected=i;overview=false;alternate=false;render()}", i)
        page.screenshot(path=str(ROOT / f"0{i+1}-{name}.png"), full_page=True)
        checks.append({"concept": name, "theme": "default", **metrics(page)})
        page.locator("[data-theme]").click()
        checks.append({"concept": name, "theme": "alternate", **metrics(page)})
    page.set_viewport_size({"width": 1640, "height": 1000})
    page.locator("[data-overview]").click()
    page.screenshot(path=str(ROOT / "00-overview.png"), full_page=True)
    page.evaluate("document.querySelectorAll('.overview-stage .phone').forEach(p=>p.classList.add('alt'))")
    page.screenshot(path=str(ROOT / "06-dark-overview.png"), full_page=True)
    for i, name in enumerate(["sage", "frame", "pace", "field", "layer"]):
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("i=>{selected=i;overview=false;alternate=false;render()}", i)
        checks.append({"concept": name, "theme": "mobile-default", **metrics(page)})
        page.locator("[data-theme]").click()
        checks.append({"concept": name, "theme": "mobile-alternate", **metrics(page)})
    page.set_viewport_size({"width": 1380, "height": 1250})
    page.evaluate("selected=0;overview=false;alternate=false;render()")
    # Check that submitting the visual prototype never reaches a real service.
    page.locator("[data-submit]").click()
    assert "체크" in page.locator(".toast").inner_text()
    page.locator("[data-confirm]").check()
    page.locator("[data-submit]").click()
    assert "실제 답변 전송이나 AI 호출은 없습니다" in page.locator(".toast").inner_text()
    browser.close()
    result = {
        "scope": "HTML visual prototypes, not Android rendering or device validation",
        "renderer": "Independent headless Chrome, existing local fonts, no external resources",
        "pageErrors": errors,
        "layoutChecks": checks,
    }
    (ROOT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    assert not errors
    assert all(not c["pageOverflow"] for c in checks)
    assert all(p["overflow"] == 0 and p["scrollWidth"] == 0 for c in checks for p in c["phones"])
    assert all(b["bottom"] <= 820 for c in checks for p in c["phones"] for b in p["controls"])
