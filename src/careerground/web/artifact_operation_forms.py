"""Escaped two-stage forms for explicit JD selections and exact R1 drafts."""

from html import escape

TITLES = {
    "JD_PASTE": "JD 선택 발췌",
    "JD_LINK": "JD 요구와 경력 연결",
    "R1_DRAFT": "정확한 R1 초안 선택",
}


def _start(view, suffix):
    title = TITLES[view.action] + suffix
    return f"<!doctype html><html lang='ko'><meta charset='utf-8'><title>{title}</title><main><h1>{title}</h1><p>기준 프로필 버전: {view.profile_version}</p>"


def _select(name, label, choices):
    return (
        f"<label for='{name}'>{label}</label><select id='{name}' name='{name}' required><option value='' selected>직접 선택</option>"
        + "".join(
            f"<option value='{escape(identifier, quote=True)}'>{escape(text)}</option>"
            for identifier, text in choices
        )
        + "</select>"
    )


def render_artifact_choices(view, operation_id):
    body = _start(view, " 준비")
    body += "<p>직접 입력하거나 선택한 뒤, 다음 화면에서 정확한 내용을 확인합니다. 이 단계는 저장 승인이나 문구 사용 허용이 아닙니다.</p>"
    body += f"<form method='post' action='/mcp/confirm/{escape(operation_id, quote=True)}/prepare'><input type='hidden' name='choice_token' value='{escape(view.choice_token, quote=True)}'>"
    if view.action == "JD_PASTE":
        body += "<label for='selected_text'>직접 고른 JD 요구 문구 (각 줄을 - 로 시작, 1–5개, 문구당 1000자 이하)</label><textarea id='selected_text' name='selected_text' maxlength='6000' required></textarea><p>선택 발췌만 기록합니다. JD 의미 분석이나 적합도 평가를 수행하지 않습니다.</p>"
    else:
        body += (
            "<h2>JD에 기록된 요구</h2><ol>"
            + "".join(
                f"<li>{escape(item['exact_text'])}</li>" for item in view.context["requirements"]
            )
            + "</ol>"
        )
        if view.action == "JD_LINK":
            body += _select(
                "requirement_id",
                "연결할 JD 요구",
                (
                    (item["requirement_id"], item["exact_text"])
                    for item in view.context["requirements"]
                ),
            )
            body += _select(
                "claim_id",
                "현재 사용 가능한 경력 사실",
                ((item["claim_id"], item["exact_text"]) for item in view.context["candidates"]),
            )
            body += (
                "<p>연결은 잠재 관련성만 뜻합니다. 요구 충족이나 외부 검증을 인증하지 않습니다.</p>"
            )
        else:
            body += "<fieldset><legend>R1에 그대로 복사할 경력 사실 (1–5개)</legend>"
            for index, item in enumerate(view.context["candidates"]):
                body += f"<label for='claim-choice-{index}'><input id='claim-choice-{index}' type='checkbox' name='claim_ids' value='{escape(item['claim_id'], quote=True)}'>{escape(item['exact_text'])}</label>"
                body += _evidence(item["evidence"])
            body += "</fieldset><p>선택 문구를 그대로 복사합니다. R2/R3 재작성은 제공하지 않으며, 생성 후 별도 문구 검토와 내보내기 승인이 필요합니다.</p>"
    return body + "<button type='submit'>정확한 내용 확인하기</button></form></main></html>"


def _evidence(items):
    return (
        "<ul>"
        + "".join(
            f"<li><blockquote>{escape(text)}</blockquote>출처 참조: {escape(reference)}</li>"
            for text, reference in items
        )
        + "</ul>"
    )


def render_artifact_exact(presentation):
    view, row = presentation.view, presentation.operation
    body = _start(view, " 직접 확인") + "<h2>이번 작업의 정확한 내용</h2>"
    if view.action == "JD_PASTE":
        body += (
            "<ol>"
            + "".join(f"<li>{escape(text)}</li>" for text in view.exact)
            + "</ol><p>표시한 선택 문구와 출처 위치만 저장합니다. 의미 분석 결과가 아닙니다.</p>"
        )
    elif view.action == "JD_LINK":
        body += f"<p>선택한 JD 요구 식별자: {escape(view.fields['requirement_id'])} · 경력 사실 식별자: {escape(view.fields['claim_id'])}</p>"
        body += (
            f"<h3>JD 요구</h3><blockquote>{escape(view.exact.requirement_text)}</blockquote><h3>경력 사실</h3><blockquote>{escape(view.exact.claim_text)}</blockquote><h3>근거와 출처</h3>"
            + _evidence(view.exact.evidence)
        )
        body += "<p>이 연결은 잠재 관련성입니다. 새 사실이나 요구 충족 인증을 만들지 않습니다.</p>"
    else:
        body += (
            "<ol>"
            + "".join(
                f"<li>경력 사실 식별자: {escape(item['claim_id'])}<blockquote>{escape(item['exact_text'])}</blockquote>{_evidence(item['evidence'])}</li>"
                for item in view.exact
            )
            + "</ol><p>표시 순서와 문구를 그대로 복사한 R1 초안입니다. 별도 문구 검토를 마치기 전에는 내보낼 수 없습니다.</p>"
        )
    body += f"<form method='post' action='/mcp/confirm/{escape(row.id, quote=True)}'><input type='hidden' name='confirmation_token' value='{escape(presentation.confirmation_token, quote=True)}'>"
    for name, value in view.fields.items():
        for item in value if isinstance(value, list) else [value]:
            body += f"<input type='hidden' name='{escape(name, quote=True)}' value='{escape(item, quote=True)}'>"
    body += "<label><input type='checkbox' name='confirm' value='confirm_artifact' required>표시한 정확한 내용과 순서를 직접 확인하고 이 작업을 승인합니다.</label>"
    return (
        body
        + "<label><input type='checkbox' name='allow_connection' value='yes' required>표시된 연결 앱이 이 작업의 결과를 받도록 허용합니다.</label><button type='submit'>작업 승인</button></form></main></html>"
    )
