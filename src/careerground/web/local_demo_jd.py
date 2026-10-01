"""Explicit mocked JD proposal, then separate selected-excerpt confirmation."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from html import escape

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update

from careerground.domain.browser_form_token import BrowserFormTokenRejected
from careerground.domain.jd_analysis_adapter import (
    JDProposalRejected,
    MockJDAnalyzer,
    prepare_jd_analysis,
)
from careerground.domain.jd_paste_presentation import (
    JDPastePresentationRejected,
    JDPastePresentationService,
)
from careerground.local_demo import bounded_form, demo_page
from careerground.storage.models import Account, CareerProfile

_KEYS = frozenset(
    {
        "purpose",
        "session_id",
        "account_id",
        "profile_id",
        "profile_version",
        "source_hash",
        "requirements_hash",
        "paste_token",
        "expires_at",
    }
)


def _digest(items):
    return hashlib.sha256(
        json.dumps([asdict(item) for item in items], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def register_mock_jd_routes(demo):
    paste = JDPastePresentationService(demo.presentation_secret)

    @demo.web.get("/demo/jd-analysis")
    async def show(request: Request):
        state = demo.browser(request)
        with demo.sessions() as session:
            profile = session.get(CareerProfile, state["profile_id"])
            if profile is None or profile.status != "ACTIVE":
                raise HTTPException(404)
            version = profile.version
        body = "<p>모의 분석 체험입니다. 외부 AI나 의미 분석을 사용하지 않습니다. 직접 고른 요구 문구의 위치를 검증하고 연결되지 않은 상태로 표시합니다.</p>"
        body += f"<p>기준 프로필 버전: {version}</p><form method='post' action='/demo/jd-analysis'><input type='hidden' name='form_token' value='{escape(demo.form_token('MOCK_JD_PREPARE', state), quote=True)}'><input type='hidden' name='profile_version' value='{version}'><label for='source_text'>합성 JD 요구 문구 (각 줄 - 또는 * 시작, 1–5개)</label><textarea id='source_text' name='source_text' maxlength='6000' required></textarea><button type='submit'>모의 요구와 원문 위치 확인</button></form>"
        return demo_page("JD 모의 분석", body)

    def proposal(session, state, fields):
        if not fields["profile_version"].isdecimal():
            raise HTTPException(400)
        try:
            return prepare_jd_analysis(
                session,
                account_id=state["account_id"],
                profile_id=state["profile_id"],
                profile_version=int(fields["profile_version"]),
                source_text=fields["source_text"],
                analyzer=MockJDAnalyzer(),
            )
        except JDProposalRejected:
            raise HTTPException(409) from None

    @demo.web.post("/demo/jd-analysis")
    async def prepare(request: Request):
        state = demo.browser(request)
        fields = await bounded_form(request, limit=65536)
        if set(fields) != {"form_token", "profile_version", "source_text"}:
            raise HTTPException(400)
        demo.verify_form(fields["form_token"], "MOCK_JD_PREPARE", state)
        with demo.sessions() as session:
            view = proposal(session, state, fields)
            paste_view = paste.present(
                session,
                account_id=state["account_id"],
                browser_session_id=state["session_id"],
                now=datetime.now(UTC),
            )
        payload = {
            "purpose": "MOCK_JD_EXACT",
            "session_id": state["session_id"],
            "account_id": state["account_id"],
            "profile_id": state["profile_id"],
            "profile_version": int(fields["profile_version"]),
            "source_hash": hashlib.sha256(fields["source_text"].encode()).hexdigest(),
            "requirements_hash": _digest(view.requirements),
            "paste_token": paste_view.paste_token,
            "expires_at": int(time.time()) + 180,
        }
        token = demo.tokens.sign(payload)
        body = "<p>MOCK_ONLY · 미승인 요구 후보입니다. 다음 승인은 표시 문구의 발췌 저장만 허용하며, 의미 분석·요구 충족·경력 사실 승인을 뜻하지 않습니다.</p><ol>"
        for item in view.requirements:
            body += f"<li><blockquote>{escape(item.exact_text)}</blockquote>원문 위치: {item.source_start}–{item.source_end} · 아직 연결하지 않은 요구 (NOT_MAPPED)</li>"
        body += f"</ol><form method='post' action='/demo/jd-analysis/save'><input type='hidden' name='approval_token' value='{escape(token, quote=True)}'><input type='hidden' name='source_text' value='{escape(fields['source_text'], quote=True)}'><input type='hidden' name='profile_version' value='{fields['profile_version']}'><label><input type='checkbox' name='confirm' value='save_selected_excerpts' required>표시한 정확한 문구를 JD 선택 발췌로 저장합니다.</label><button type='submit'>선택 발췌 저장 승인</button></form>"
        return demo_page("모의 JD 요구 직접 확인", body)

    @demo.web.post("/demo/jd-analysis/save")
    async def save(request: Request):
        state = demo.browser(request)
        fields = await bounded_form(request, limit=65536)
        if (
            set(fields) != {"approval_token", "source_text", "profile_version", "confirm"}
            or fields["confirm"] != "save_selected_excerpts"
        ):
            raise HTTPException(400)
        try:
            payload = demo.tokens.verify(fields["approval_token"], expected_keys=_KEYS)
        except BrowserFormTokenRejected:
            raise HTTPException(409) from None
        if (
            not fields["profile_version"].isdecimal()
            or (
                payload["purpose"],
                payload["session_id"],
                payload["account_id"],
                payload["profile_id"],
                payload["profile_version"],
            )
            != (
                "MOCK_JD_EXACT",
                state["session_id"],
                state["account_id"],
                state["profile_id"],
                int(fields["profile_version"]),
            )
            or payload["expires_at"] <= time.time()
            or payload["source_hash"] != hashlib.sha256(fields["source_text"].encode()).hexdigest()
        ):
            raise HTTPException(409)
        with demo.sessions() as session:
            # Reserve the SQLite writer before reading; lock owner before profile on PG.
            if session.bind.dialect.name == "sqlite":
                session.execute(
                    update(Account)
                    .where(Account.id == state["account_id"])
                    .values(status=Account.status)
                )
            session.scalar(
                select(Account).where(Account.id == state["account_id"]).with_for_update()
            )
            session.scalar(
                select(CareerProfile)
                .where(
                    CareerProfile.id == state["profile_id"],
                    CareerProfile.account_id == state["account_id"],
                )
                .with_for_update()
            )
            view = proposal(session, state, fields)
            if payload["requirements_hash"] != _digest(view.requirements):
                raise HTTPException(409)
            try:
                jd = paste.submit(
                    session,
                    account_id=state["account_id"],
                    browser_session_id=state["session_id"],
                    paste_token=payload["paste_token"],
                    selected_text=fields["source_text"],
                    now=datetime.now(UTC),
                )
            except JDPastePresentationRejected:
                raise HTTPException(409) from None
            identifier = jd.id
            session.commit()
        result = RedirectResponse("/jd/" + identifier, status_code=303)
        result.headers["cache-control"] = "no-store"
        return result
