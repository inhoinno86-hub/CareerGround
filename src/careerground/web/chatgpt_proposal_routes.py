"""Authenticated, escaped browser review of short-lived ChatGPT suggestions."""

import asyncio
from html import escape
from urllib.parse import parse_qs

from fastapi import HTTPException, Request, Response

from careerground.domain.browser_form_token import BrowserFormTokenRejected
from careerground.domain.chatgpt_proposal_review import ChatGPTProposalRejected
from careerground.domain.jd_analysis import JDUnavailable
from careerground.domain.resume_r2_review import R2ProposalRejected
from careerground.domain.text_proposal_validation import TextProposalRejected

_REJECT = (
    ChatGPTProposalRejected,
    BrowserFormTokenRejected,
    R2ProposalRejected,
    TextProposalRejected,
    JDUnavailable,
)


def attach_chatgpt_proposal_routes(app, *, inbox, authenticate):
    from careerground.web.review_foundation import _html_response

    async def principal(request):
        value = await authenticate(request, Response())
        if value is None:
            raise HTTPException(401)
        return value

    @app.get("/chatgpt/proposals/{proposal_id}", include_in_schema=False)
    async def show(proposal_id: str, request: Request):
        user = await principal(request)
        try:
            row, view, token = await asyncio.to_thread(inbox.present, proposal_id, user)
        except _REJECT:
            raise HTTPException(404) from None
        title = "ChatGPT JD 발췌 직접 검토" if row.kind == "JD" else "ChatGPT R2 문구 직접 검토"
        body = (
            "<!doctype html><html lang='ko'><meta charset='utf-8'>"
            + f"<title>{title}</title><main><h1>{title}</h1>"
        )
        body += (
            "<p>ChatGPT의 미승인 제안입니다. 의미적 적합성·사실·사용·내보내기 승인을 대신하지 않습니다.</p>"
            f"<p>기준 프로필 버전: {row.version}. 이 제안을 보낸 OAuth 연결에서만 결과를 확인할 수 있습니다.</p>"
            f"<form method='post' action='/chatgpt/proposals/{escape(proposal_id, quote=True)}'>"
            f"<input type='hidden' name='token' value='{escape(token, quote=True)}'>"
        )
        if row.kind == "JD":
            body += "<p>원문과 일치하는 아래 발췌 중 저장할 항목만 선택하세요. 제안한 근거 연결은 이 승인으로 저장되지 않습니다.</p><ol>"
            for c in view.candidates:
                body += (
                    f"<li><blockquote>{escape(c.exact_text)}</blockquote><p>원문 위치: {c.source_start}–{c.source_end}</p>"
                    f"<p>잠재 근거 제안: {escape(c.claim_id or '연결 없음')} · 의미 적합성 미확인</p>"
                    f"<label><input type='checkbox' name='selected_{c.ordinal}' value='yes'>발췌 {c.ordinal} 저장</label></li>"
                )
            body += "</ol>"
        else:
            body += "<p>승인하면 별도 R2가 저장되고 원본 R1과 사실은 보존됩니다. 허용된 표현 변경만 받을 수 있습니다.</p><ol>"
            for before, after in zip(view.source.units, view.previews, strict=True):
                body += (
                    f"<li><h2>기존 R1</h2><blockquote>{escape(before.exact_text)}</blockquote>"
                    f"<h2>제안 R2</h2><blockquote>{escape(after.proposed_text)}</blockquote>"
                    "<h2>기존 근거</h2><ul>"
                    + "".join(f"<li>{escape(e)}</li>" for e in before.evidence_excerpts)
                    + "</ul></li>"
                )
            body += "</ol>"
        body += (
            "<label><input type='checkbox' name='confirm' value='reviewed' required>"
            "표시된 내용과 저장 범위를 직접 확인하고 저장을 승인합니다.</label>"
            "<button type='submit'>검토한 내용 저장</button></form>"
            "<p>저장하지 않으려면 화면을 닫으세요. 제안은 3분 뒤 만료됩니다.</p></main></html>"
        )
        return _html_response(body)

    @app.post("/chatgpt/proposals/{proposal_id}", include_in_schema=False)
    async def approve(proposal_id: str, request: Request):
        user = await principal(request)
        if (
            request.headers.get("content-type", "").split(";", 1)[0]
            != "application/x-www-form-urlencoded"
        ):
            raise HTTPException(415)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 8192:
                raise HTTPException(413)
        try:
            form = parse_qs(
                data.decode(), keep_blank_values=True, strict_parsing=True, max_num_fields=7
            )
            if (
                any(len(v) != 1 for v in form.values())
                or not {"token", "confirm"} <= set(form)
                or form["confirm"] != ["reviewed"]
                or any(
                    key not in {"token", "confirm", *(f"selected_{n}" for n in range(1, 6))}
                    for key in form
                )
            ):
                raise ValueError
            selected = [
                int(key.removeprefix("selected_")) for key in form if key.startswith("selected_")
            ]
            if any(form[f"selected_{n}"] != ["yes"] for n in selected):
                raise ValueError
            result = await asyncio.to_thread(
                inbox.approve, proposal_id, user, form["token"][0], selected
            )
        except (*_REJECT, ValueError, UnicodeError):
            raise HTTPException(409) from None
        return _html_response(
            "<!doctype html><html lang='ko'><meta charset='utf-8'><title>ChatGPT 제안 검토 완료</title>"
            "<main><h1>ChatGPT 제안 검토 완료</h1><p>직접 승인한 자료가 저장됐습니다. 내보내기 승인은 별도로 필요합니다.</p>"
            f"<p>저장 항목: {escape(result)}</p><p>같은 ChatGPT 대화로 돌아가 결과를 확인하세요.</p></main></html>"
        )
