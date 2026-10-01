"""Escaped Korean two-stage policy forms for the isolated browser adapter."""

from html import escape

from careerground.domain.policy_review_presentation import PolicyExactPresentation

_RESOLUTIONS = {
    "KEEP_EXISTING": "기존 설명 유지, 모순 미해결",
    "ACCEPT_CORRECTION": "정정 수용, 사용 금지",
    "KEEP_BOTH_SCOPED": "범위를 구분해 양쪽 설명 보존, 모순 미해결",
    "REMAIN_UNCERTAIN": "불확실 상태 유지",
}


def _context(context):
    body = f"<p>기준 프로필 버전: {context.profile_version}</p><h2>현재 경력 사실</h2><blockquote>{escape(context.claim_text)}</blockquote>"
    body += (
        "<p>현재 평가: " + escape(" / ".join(context.assessment)) + "</p><h2>근거와 출처</h2><ul>"
    )
    for link, evidence, relation, text, reference in context.evidence:
        body += f"<li>{escape(relation)} · {escape(evidence)} · 연결 {escape(link)}<blockquote>{escape(text)}</blockquote>출처 참조: {escape(reference)}</li>"
    body += "</ul><h2>현재 사용 경계</h2><ul>"
    for identifier, text in context.boundaries:
        body += f"<li>{escape(identifier)}: {escape(text)}</li>"
    return body + ("</ul>" if context.boundaries else "<li>표시된 활성 경계가 없습니다.</li></ul>")


def _select(name, label, choices):
    options = "<option value='' selected>직접 선택</option>" + "".join(
        f"<option value='{escape(value, quote=True)}'>{escape(text)}</option>"
        for value, text in choices
    )
    return f"<label for='{name}'>{label}</label><select id='{name}' name='{name}' required>{options}</select>"


def _text(name, label, *, required=True):
    return f"<label for='{name}'>{label}</label><textarea id='{name}' name='{name}' maxlength='2000' {'required' if required else ''}></textarea>"


def render_policy_choices(view, operation_id):
    title = "모순에 대한 결정 준비" if view.action == "CONFLICT_REVIEW" else "사용 경계 변경 준비"
    body = (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        + f"<title>{title}</title><main><h1>{title}</h1>"
    )
    body += (
        "<p>아래 내용을 읽고 직접 결정과 설명을 입력하세요. 다음 화면에서 정확한 변경 내용을 다시 확인합니다. 이 단계는 승인이나 사용 허용이 아닙니다.</p>"
        + _context(view.context)
    )
    body += f"<form method='post' action='/mcp/confirm/{escape(operation_id, quote=True)}/prepare'><input type='hidden' name='choice_token' value='{escape(view.choice_token, quote=True)}'>"
    if view.action == "CONFLICT_REVIEW":
        body += _select(
            "conflict_link_id",
            "검토할 반대 근거 연결",
            ((item[0], item[0]) for item in view.context.evidence if item[2] == "CONTRADICTS"),
        )
        body += _select("resolution", "모순에 대한 결정", _RESOLUTIONS.items())
        body += _text("explanation", "결정의 설명 (최대 2000자)")
    else:
        body += _select(
            "evidence_id",
            "변경 판단에 사용할 근거",
            ((item[1], item[1] + " · " + item[2]) for item in view.context.evidence),
        )
        body += _select(
            "action",
            "경계 변경 종류",
            (
                ("ADD", "금지 경계 추가 (반대 근거 필요)"),
                ("REVOKE", "기존 금지 경계 철회 (더 새로운 지원 근거 필요)"),
            ),
        )
        body += "<label for='constraint_id'>철회할 경계 (추가일 때는 선택하지 마세요)</label><select id='constraint_id' name='constraint_id'><option value='' selected>선택하지 않음</option>"
        body += (
            "".join(
                f"<option value='{escape(identifier, quote=True)}'>{escape(text)}</option>"
                for identifier, text in view.context.boundaries
            )
            + "</select>"
        )
        body += _text(
            "proposed_boundary_text",
            "추가할 금지 경계 문구 (철회일 때는 비워 두세요)",
            required=False,
        )
        body += _text("allowed_wording", "허용 범위에 맞는 정확한 문구")
        body += _text("remaining_prohibited_expansion", "변경 후에도 금지되는 확대 표현")
    return body + "<button type='submit'>정확한 변경 내용 확인하기</button></form></main></html>"


def render_policy_exact(presentation):
    view: PolicyExactPresentation = presentation.view
    row = presentation.operation
    title = (
        "모순 결정 직접 확인" if view.action == "CONFLICT_REVIEW" else "사용 경계 변경 직접 확인"
    )
    body = (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        + f"<title>{title}</title><main><h1>{title}</h1>"
        + _context(view.context)
    )
    body += "<h2>직접 입력한 변경 내용</h2><dl>"
    selected = next(
        item
        for item in view.context.evidence
        if (
            item[0] == view.fields["conflict_link_id"]
            if view.action == "CONFLICT_REVIEW"
            else item[1] == view.fields["evidence_id"]
        )
    )
    body += f"<dt>이 결정에 선택한 근거</dt><dd>연결 {escape(selected[0])} · 근거 {escape(selected[1])} · {escape(selected[2])}<blockquote>{escape(selected[3])}</blockquote>출처 참조: {escape(selected[4])}</dd>"
    if view.action == "CONFLICT_REVIEW":
        body += f"<dt>선택한 결정</dt><dd>{escape(_RESOLUTIONS[view.review.resolution])}</dd><dt>설명</dt><dd>{escape(view.review.explanation)}</dd>"
    else:
        if view.fields["constraint_id"]:
            body += f"<dt>철회할 경계 식별자</dt><dd>{escape(view.fields['constraint_id'])}</dd>"
        for label, value in (
            ("변경 종류", "금지 경계 추가" if view.review.action == "ADD" else "금지 경계 철회"),
            ("변경 전 경계", view.review.old_boundary_text or "해당 없음"),
            ("추가할 경계", view.review.proposed_boundary_text or "해당 없음"),
            ("허용 문구", view.review.allowed_wording),
            ("남은 금지 표현", view.review.remaining_prohibited_expansion),
        ):
            body += f"<dt>{label}</dt><dd>{escape(value)}</dd>"
    body += "</dl><p>반대 근거와 기존 사실은 지우지 않습니다. 이 결정만으로 외부 검증이나 이력서 사용을 허용하지 않습니다. 같은 범위의 사용은 별도 재검토가 필요할 수 있습니다.</p>"
    body += f"<form method='post' action='/mcp/confirm/{escape(row.id, quote=True)}'><input type='hidden' name='confirmation_token' value='{escape(presentation.confirmation_token, quote=True)}'>"
    body += "".join(
        f"<input type='hidden' name='{escape(name, quote=True)}' value='{escape(value, quote=True)}'>"
        for name, value in view.fields.items()
    )
    body += "<label><input type='checkbox' name='confirm' value='confirm_policy' required>표시된 현재 내용과 변경 내용을 직접 확인하고 이 결정을 승인합니다.</label>"
    body += "<label><input type='checkbox' name='allow_connection' value='yes' required>표시된 연결 앱이 이 작업의 결과를 받도록 허용합니다.</label><button type='submit'>결정 승인</button></form></main></html>"
    return body
