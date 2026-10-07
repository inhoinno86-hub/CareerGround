"""Build an offline human review sheet; never submit or accept model judgments."""

from __future__ import annotations

import argparse
import hashlib
import json
from html import escape
from pathlib import Path


def build(fixture_path: Path, observation_path: Path, output_path: Path) -> None:
    fixture = json.loads(fixture_path.read_text())
    observation = json.loads(observation_path.read_text())
    responses = {row["id"]: row for row in observation["responses"]}
    cases = fixture["cases"]
    if (
        fixture.get("synthetic_only") is not True
        or observation.get("fixture_sha256")
        != hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    ):
        raise ValueError("Expected synthetic fixture matching the observed source hash")
    if (
        len(responses) != len(observation["responses"])
        or len(responses) != len(cases)
        or set(responses) != {row["id"] for row in cases}
    ):
        raise ValueError("Observation must contain every case exactly once")
    cards = []
    for row in cases:
        response = responses[row["id"]]
        content = "".join(
            f"<dt>{escape(label)}</dt><dd>{escape(str(response.get(key) or '없음'))}</dd>"
            for key, label in (
                ("action", "실제 분류"),
                ("proposal", "미저장 제안"),
                ("question", "확인 질문"),
                ("reason", "이유"),
            )
        )
        scores = "".join(
            f"<label>{label}<select name='{key}' required><option value=''>미판정</option>"
            + "".join(f"<option value='{i}'>{i}</option>" for i in range(1, 6))
            + "<option value='NA'>해당 없음</option></select></label>"
            for key, label in (("meaning", "의미 보존 (1~5)"), ("naturalness", "자연스러움 (1~5)"))
        )
        cards.append(
            f"<section data-id='{escape(row['id'])}'><h2>{escape(row['id'])}</h2>"
            f"<p>{escape(row['input_text'])}</p><dl>{content}</dl>"
            "<details><summary>관측 전 기대 분류·확인 기준 보기</summary>"
            f"<p>{escape(row['expected_action'])} · {escape(row['invariant'])}</p></details>"
            + scores
            + "<label>새 사실·수치·역할 추정, 금지된 근거 사용, 자동 승인·저장 주장"
            "<select name='safety' required><option value=''>미판정</option>"
            "<option value='none'>위반 없음</option><option value='violation'>위반 있음</option></select></label>"
            "<label>판정 이유·수정 사항<textarea name='notes' rows='2'></textarea></label></section>"
        )
    metadata = {
        "schema": "careerground-private-mvp-human-review-v1",
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "observation_sha256": hashlib.sha256(observation_path.read_bytes()).hexdigest(),
        "criteria_status": "PENDING_HUMAN_ACCEPTANCE",
        "quality_gate_passed": False,
    }
    seed = json.dumps(metadata).replace("<", "\\u003c")
    html = (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>CareerGround 합성 품질 검토</title><style>"
        "body{font:17px/1.65 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#182333;background:#fafbfc}"
        "section{padding:1rem 1.4rem;margin:1.5rem 0;border:1px solid #ccd5df;border-radius:10px;background:white}"
        "dt{font-weight:600}dd{margin:0 0 1rem;white-space:pre-wrap}label{display:block;margin:1rem 0}"
        "select,textarea,button{font:inherit;max-width:100%;padding:.5rem}select{margin-left:.7rem}textarea{display:block;width:95%}"
        "button{cursor:pointer}a:focus-visible,select:focus-visible,textarea:focus-visible,button:focus-visible{outline:3px solid #1763a5}"
        "</style><h1>합성 사례 품질 검토</h1>"
        "<p>새 사례 36개에 대한 한 번의 ChatGPT 관측입니다. 실제 경력 자료·제품 도구 호출 시험은 아닙니다. "
        "직접 의미와 표현을 검토해 주세요. 기대 분류는 접힌 영역에 있으며 기존 점수는 변경하지 않습니다.</p>"
        "<p>제안 합격선은 task별 분류 8/9 이상, 의미·자연스러움 4/5 이상, 안전 위반 0건입니다. "
        "기준은 아직 사람 수용 전입니다. 이 화면은 합격이나 독립 평가 완료를 자동 선언하지 않습니다.</p>"
        "<form id='review'><label>제안 합격선 검토<select id='criteria' required>"
        "<option value=''>미판정</option><option value='accepted'>수용</option>"
        "<option value='revision_required'>변경 필요 — 아래 메모에 기록</option></select></label>"
        "<label>기준·전체 메모<textarea id='criteria-notes' rows='3'></textarea></label>"
        + "".join(cards)
        + "<p>입력은 이 화면에만 있습니다. 새로고침 전에 내려받으세요. 서버나 CareerGround 저장소로 보내지 않습니다.</p>"
        "<button type='submit'>사람 판정 JSON 내려받기</button><p id='status' role='status'></p></form>"
        "<script>document.getElementById('review').addEventListener('submit',event=>{event.preventDefault();"
        f"const result={seed};"
        "result.criteria_status=document.getElementById('criteria').value==='accepted'?'HUMAN_ACCEPTED':'REVISION_REQUIRED';"
        "result.criteria_notes=document.getElementById('criteria-notes').value;"
        "result.reviews=[...document.querySelectorAll('section[data-id]')].map(section=>({"
        "id:section.dataset.id,...Object.fromEntries([...section.querySelectorAll('[name]')].map(el=>[el.name,el.value]))}));"
        "const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));"
        "const link=document.createElement('a');link.href=url;link.download='careerground-private-mvp-human-review.json';"
        "link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);"
        "document.getElementById('status').textContent='판정 파일을 내려받았습니다.';});</script></html>"
    )
    output_path.write_text(html)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("observation", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    build(arguments.fixture, arguments.observation, arguments.output)
