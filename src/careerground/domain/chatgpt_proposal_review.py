"""Bounded, expiring ChatGPT proposals; canonical writes require browser approval.

Source text and proposed wording stay in process memory until explicit approval.
No model is called here. Existing source/ownership/eligibility validators remain
authoritative; plausible model prose cannot authorize a fact, mapping or export.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from sqlalchemy import select

from careerground.domain.browser_form_token import BrowserFormTokenCodec
from careerground.domain.jd_analysis import JDExcerpt, record_pasted_jd_analysis
from careerground.domain.resume_r2_review import R2ProposalService
from careerground.domain.text_proposal_validation import (
    _owner,
    validate_jd_text_proposal,
)
from careerground.storage.jd_artifact_models import Artifact

_KEY = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")


class ChatGPTProposalRejected(ValueError):
    pass


@dataclass(repr=False)
class _Proposal:
    id: str
    account_id: str
    connection: str
    retry_key: str
    digest: str
    kind: str
    profile_id: str
    version: int
    target: str
    payload: object
    source: str
    expires_at: int
    status: str = "WAITING"
    result_id: str | None = None
    result_version: int | None = None
    browser_session: str = ""
    r2_token: str = ""
    form_nonce: str = ""
    selections: tuple[int, ...] = field(default_factory=tuple)


class ChatGPTProposalInbox:
    def __init__(
        self, session_factory, review_secret: bytes, form_secret: bytes, *, clock=time.time
    ):
        self.sessions, self.clock = session_factory, clock
        self.secret = form_secret
        self.forms = BrowserFormTokenCodec(form_secret)
        self.r2 = R2ProposalService(
            hmac.digest(review_secret, b"synthetic-r1-wording-review-v1", "sha256")
        )
        self.rows: dict[str, _Proposal] = {}
        self.lock = RLock()

    def connection(self, token: str) -> str:
        return hmac.new(self.secret, token.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _json(value: str):
        if type(value) is not str or len(value.encode()) > 48000:
            raise ChatGPTProposalRejected

        def unique(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ChatGPTProposalRejected
                result[key] = item
            return result

        try:
            return json.loads(
                value,
                object_pairs_hook=unique,
                parse_constant=lambda _: (_ for _ in ()).throw(ChatGPTProposalRejected()),
            )
        except (ValueError, RecursionError):
            raise ChatGPTProposalRejected from None

    def _now(self):
        return datetime.fromtimestamp(self.clock(), UTC)

    def _purge(self):
        now = self.clock()
        self.rows = {key: row for key, row in self.rows.items() if row.expires_at > now}

    def _add(
        self, *, account_id, connection, key, kind, profile_id, version, target, payload, source
    ):
        if type(key) is not str or not _KEY.fullmatch(key):
            raise ChatGPTProposalRejected
        digest = hashlib.sha256(
            json.dumps(
                [kind, profile_id, version, target, payload, source],
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        with self.lock:
            self._purge()
            for row in self.rows.values():
                if (row.account_id, row.connection, row.retry_key) == (account_id, connection, key):
                    if row.digest != digest:
                        raise ChatGPTProposalRejected
                    return row
            if (
                len(self.rows) >= 128
                or sum(r.account_id == account_id for r in self.rows.values()) >= 8
            ):
                raise ChatGPTProposalRejected
            row = _Proposal(
                str(uuid4()),
                account_id,
                connection,
                key,
                digest,
                kind,
                profile_id,
                version,
                target,
                payload,
                source,
                int(self.clock()) + 180,
            )
            self.rows[row.id] = row
            return row

    def prepare_jd(
        self, *, account_id, connection, profile_id, profile_version, jd_text, proposal_json, key
    ):
        payload = self._json(proposal_json)
        with self.sessions() as session:
            validate_jd_text_proposal(
                session,
                account_id=account_id,
                profile_id=profile_id,
                profile_version=profile_version,
                source_text=jd_text,
                payload=payload,
            )
        return self._add(
            account_id=account_id,
            connection=connection,
            key=key,
            kind="JD",
            profile_id=profile_id,
            version=profile_version,
            target=profile_id,
            payload=payload,
            source=jd_text,
        )

    def prepare_r2(self, *, account_id, connection, artifact_id, proposals_json, key):
        proposals = self._json(proposals_json)
        if type(proposals) is not list or not 1 <= len(proposals) <= 5:
            raise ChatGPTProposalRejected
        with self.sessions() as session:
            # This validation token is never exposed or used for submission.
            view = self.r2.prepare(
                session,
                account_id=account_id,
                browser_session_id="unbound-chatgpt-preview",
                source_artifact_id=artifact_id,
                proposals=tuple(proposals),
                now=self._now(),
            )
            artifact = session.scalar(
                select(Artifact).where(
                    Artifact.id == artifact_id, Artifact.account_id == account_id
                )
            )
            profile_id, version = artifact.profile_id, view.source.profile_version
        return self._add(
            account_id=account_id,
            connection=connection,
            key=key,
            kind="R2",
            profile_id=profile_id,
            version=version,
            target=artifact_id,
            payload=proposals,
            source="",
        )

    def _get(self, proposal_id, account_id, connection=None):
        self._purge()
        row = self.rows.get(proposal_id)
        if (
            row is None
            or row.account_id != account_id
            or (connection is not None and not hmac.compare_digest(row.connection, connection))
        ):
            raise ChatGPTProposalRejected
        with self.sessions() as session:
            _owner(session, account_id, row.profile_id, row.version)
            if row.kind == "JD":
                validate_jd_text_proposal(
                    session,
                    account_id=account_id,
                    profile_id=row.profile_id,
                    profile_version=row.version,
                    source_text=row.source,
                    payload=row.payload,
                )
            else:
                self.r2.prepare(
                    session,
                    account_id=account_id,
                    browser_session_id="unbound-chatgpt-preview",
                    source_artifact_id=row.target,
                    proposals=tuple(row.payload),
                    now=self._now(),
                )
        return row

    def status(self, proposal_id, account_id, connection):
        with self.lock:
            row = self._get(proposal_id, account_id, connection)
            return {
                "proposal_id": row.id,
                "kind": row.kind,
                "review_status": row.status,
                "result_id": row.result_id,
                "profile_version": row.version,
                "canonical_saved": row.status == "DONE",
                "export_approved": False,
            }

    def present(self, proposal_id, principal):
        with self.lock:
            row = self._get(proposal_id, principal.account_id)
            if row.status != "WAITING":
                raise ChatGPTProposalRejected
            with self.sessions() as session:
                if row.kind == "JD":
                    view = validate_jd_text_proposal(
                        session,
                        account_id=row.account_id,
                        profile_id=row.profile_id,
                        profile_version=row.version,
                        source_text=row.source,
                        payload=row.payload,
                    )
                else:
                    view = self.r2.prepare(
                        session,
                        account_id=row.account_id,
                        browser_session_id=principal.session_id,
                        source_artifact_id=row.target,
                        proposals=tuple(row.payload),
                        now=self._now(),
                    )
                    row.r2_token = view.approval_token
            row.browser_session = principal.session_id
            # Rotating form proof on each view also prevents stale parallel tabs.
            row.form_nonce = secrets.token_urlsafe(24)
            token = self.forms.sign(
                {
                    "purpose": "CHATGPT_PROPOSAL_REVIEW",
                    "proposal_id": row.id,
                    "browser_session": principal.session_id,
                    "nonce": row.form_nonce,
                    "expires_at": row.expires_at,
                }
            )
            return row, view, token

    def approve(self, proposal_id, principal, token, selections):
        with self.lock:
            row = self._get(proposal_id, principal.account_id)
            payload = self.forms.verify(
                token,
                expected_keys=frozenset(
                    {"purpose", "proposal_id", "browser_session", "nonce", "expires_at"}
                ),
            )
            if (
                row.status != "WAITING"
                or row.browser_session != principal.session_id
                or payload
                != {
                    "purpose": "CHATGPT_PROPOSAL_REVIEW",
                    "proposal_id": row.id,
                    "browser_session": principal.session_id,
                    "nonce": row.form_nonce,
                    "expires_at": row.expires_at,
                }
                or payload["expires_at"] <= self.clock()
            ):
                raise ChatGPTProposalRejected
            with self.sessions() as session:
                from careerground.storage.models import Account, CareerProfile

                session.scalar(
                    select(Account)
                    .where(Account.id == row.account_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                session.scalar(
                    select(CareerProfile)
                    .where(
                        CareerProfile.id == row.profile_id,
                        CareerProfile.account_id == row.account_id,
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                _owner(session, row.account_id, row.profile_id, row.version)
                if row.kind == "JD":
                    view = validate_jd_text_proposal(
                        session,
                        account_id=row.account_id,
                        profile_id=row.profile_id,
                        profile_version=row.version,
                        source_text=row.source,
                        payload=row.payload,
                    )
                    if (
                        not selections
                        or len(set(selections)) != len(selections)
                        or any(
                            type(n) is not int or not 1 <= n <= len(view.candidates)
                            for n in selections
                        )
                    ):
                        raise ChatGPTProposalRejected
                    jd = record_pasted_jd_analysis(
                        session,
                        account_id=row.account_id,
                        profile_id=row.profile_id,
                        source_text=row.source,
                        excerpts=tuple(
                            JDExcerpt(c.source_start, c.source_end)
                            for c in view.candidates
                            if c.ordinal in selections
                        ),
                        now=self._now(),
                    )
                    result_id = jd.id
                else:
                    if selections:
                        raise ChatGPTProposalRejected
                    artifact = self.r2.submit(
                        session,
                        account_id=row.account_id,
                        browser_session_id=principal.session_id,
                        approval_token=row.r2_token,
                        now=self._now(),
                    )
                    result_id = artifact.id
                session.commit()
            row.result_id, row.status = result_id, "DONE"
            row.selections = tuple(selections)
            return row.result_id
