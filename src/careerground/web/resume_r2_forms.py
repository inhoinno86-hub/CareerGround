"""Escaped local browser forms for exact R2 wording approval."""

from __future__ import annotations

import hashlib
from html import escape

from careerground.domain.resume_draft import ResumeTrace
from careerground.domain.resume_r2_review import R2ProposalView


def render_r2_input(source: ResumeTrace, input_token: str) -> str:
    """Display fixed R1 sources and gather a proposed sentence for each unit."""
    body = (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<title>R2 문구 제안</title><main><h1>R2 문구 제안</h1>"
        "<p>각 R1 문장의 표현을 직접 바꾸세요. 새로운 사실은 경력 사실 검토에서 따로 입력해야 합니다.</p>"
        f"<form method='post' action='/resume/{escape(source.artifact_id, quote=True)}/r2/prepare'>"
        f"<input type='hidden' name='input_token' value='{escape(input_token, quote=True)}'>"
    )
    for index, unit in enumerate(source.units):
        body += (
            f"<section><h2>문장 {index + 1}</h2>"
            f"<p>기존 R1 문구</p><blockquote>{escape(unit.exact_text)}</blockquote>"
            f"<p>근거 사실: {escape(unit.claim_id)}</p>"
            f"<ul>{''.join(f'<li>{escape(excerpt)} · 출처 {escape(ref)}</li>' for excerpt, ref in zip(unit.evidence_excerpts, unit.original_input_refs, strict=True))}</ul>"
            f"<input type='hidden' name='unit_id_{index}' value='{escape(unit.unit_id, quote=True)}'>"
            f"<input type='hidden' name='source_hash_{index}' value='{hashlib.sha256(unit.exact_text.encode()).hexdigest()}'>"
            f"<input type='hidden' name='claim_id_{index}' value='{escape(unit.claim_id, quote=True)}'>"
            + "".join(
                f"<input type='hidden' name='evidence_id_{index}' value='{escape(identifier, quote=True)}'>"
                for identifier in unit.evidence_ids
            )
            + f"<label for='proposed_text_{index}'>제안 R2 문구 {index + 1}</label>"
            f"<textarea id='proposed_text_{index}' name='proposed_text_{index}' maxlength='2000' required>{escape(unit.exact_text)}</textarea>"
            f"<label for='fact_review_{index}'>새 사실 포함 여부 {index + 1}</label>"
            f"<select id='fact_review_{index}' name='fact_review_{index}' required>"
            "<option value='NO_NEW_FACTS' selected>새 사실 없음: R2 표현만 검토</option>"
            "<option value='R3_NEEDS_FACT_REVIEW'>새 사실 포함: 별도 경력 사실 검토로 이동</option>"
            "</select>"
            "</section>"
        )
    return (
        body + "<button type='submit'>변경 전후 직접 확인</button></form>"
        "<p>새 역할·성과·기간 등은 이 화면에서 승인되지 않습니다. "
        "<a href='/profiling/start'>새 경력 사실을 별도로 검토하기</a></p></main></html>"
    )


def render_r2_exact(view: R2ProposalView) -> str:
    """Show exact before/after and retained evidence before browser approval."""
    body = (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<title>R2 문구 직접 승인</title><main><h1>R2 문구 직접 승인</h1>"
        "<p>아래 문구를 승인하면 별도 R2 이력서가 저장됩니다. 원본 R1은 보존됩니다. 내보내기는 다음 단계에서 다시 승인합니다.</p>"
        "<ol>"
    )
    for original, preview in zip(view.source.units, view.previews, strict=True):
        body += (
            "<li><h2>변경 전 R1</h2>"
            f"<blockquote>{escape(original.exact_text)}</blockquote>"
            "<h2>변경 후 R2</h2>"
            f"<blockquote>{escape(preview.proposed_text)}</blockquote>"
            f"<p>근거 사실: {escape(original.claim_id)}</p>"
            f"<ul>{''.join(f'<li>{escape(excerpt)} · 출처 {escape(ref)}</li>' for excerpt, ref in zip(original.evidence_excerpts, original.original_input_refs, strict=True))}</ul>"
            "</li>"
        )
    return (
        body + "</ol>"
        f"<form method='post' action='/resume/{escape(view.source.artifact_id, quote=True)}/r2/approve'>"
        f"<input type='hidden' name='approval_token' value='{escape(view.approval_token, quote=True)}'>"
        "<label><input type='checkbox' name='confirm' value='approve_r2' required>변경 전후 문구와 근거를 직접 확인하고 R2 저장을 승인합니다.</label>"
        "<button type='submit'>R2 문구 승인 및 저장</button></form></main></html>"
    )
