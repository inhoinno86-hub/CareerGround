"""Synthetic pasted-JD excerpt registration with no model or provider calls."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from careerground.storage.jd_artifact_models import JDRequirement, JobDescription
from careerground.storage.models import Account, CareerProfile

MAX_JD_CHARS = 200_000
MAX_REQUIREMENTS = 50


class JDUnavailable(Exception):
    """The JD or owning profile is not available to this account."""


@dataclass(frozen=True)
class JDExcerpt:
    source_start: int
    source_end: int


@dataclass(frozen=True)
class JDAnalysisView:
    jd_id: str
    jd_version: int
    source_hash: str
    source_length: int
    requirements: tuple[tuple[int, str, int, int], ...]


def record_pasted_jd_analysis(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    source_text: str,
    excerpts: tuple[JDExcerpt, ...],
    now: datetime,
    company_name: str | None = None,
    job_title: str | None = None,
) -> JobDescription:
    """Persist only exact selected spans, source hash and bounded metadata.

    The caller owns the transaction. This internal path has no public request
    adapter and does not analyze the meaning of the supplied text.
    """

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware timestamp required")
    if (
        not isinstance(source_text, str)
        or not 1 <= len(source_text) <= MAX_JD_CHARS
        or not isinstance(excerpts, tuple)
        or not 1 <= len(excerpts) <= MAX_REQUIREMENTS
    ):
        raise ValueError("invalid bounded JD source or excerpt count")
    for value in (company_name, job_title):
        if value is not None and (not isinstance(value, str) or len(value) > 200):
            raise ValueError("invalid JD label")
    spans = []
    for excerpt in excerpts:
        if (
            type(excerpt) is not JDExcerpt
            or isinstance(excerpt.source_start, bool)
            or isinstance(excerpt.source_end, bool)
            or not isinstance(excerpt.source_start, int)
            or not isinstance(excerpt.source_end, int)
            or not 0 <= excerpt.source_start < excerpt.source_end <= len(source_text)
            or excerpt.source_end - excerpt.source_start > 20_000
            or not source_text[excerpt.source_start : excerpt.source_end].strip()
        ):
            raise ValueError("invalid exact JD excerpt span")
        spans.append((excerpt.source_start, excerpt.source_end))
    if any(left[1] > right[0] for left, right in zip(sorted(spans), sorted(spans)[1:])):
        raise ValueError("overlapping JD excerpts")

    account = session.scalar(select(Account).where(Account.id == account_id).with_for_update())
    profile = session.scalar(
        select(CareerProfile)
        .where(CareerProfile.id == profile_id, CareerProfile.account_id == account_id)
        .with_for_update()
    )
    if (
        account is None
        or account.status != "ACTIVE"
        or profile is None
        or profile.status != "ACTIVE"
    ):
        raise JDUnavailable
    current = session.scalar(
        select(func.max(JobDescription.jd_version)).where(
            JobDescription.account_id == account_id,
            JobDescription.profile_id == profile_id,
        )
    )
    jd = JobDescription(
        id=str(uuid4()),
        account_id=account_id,
        profile_id=profile_id,
        jd_version=(current or 0) + 1,
        source_kind="PASTED_TEXT",
        source_hash=hashlib.sha256(source_text.encode()).hexdigest(),
        source_length=len(source_text),
        company_name=company_name,
        job_title=job_title,
        status="ACTIVE",
        created_at=now.astimezone(UTC),
    )
    session.add(jd)
    session.flush()
    for ordinal, (start, end) in enumerate(sorted(spans), start=1):
        session.add(
            JDRequirement(
                id=str(uuid4()),
                account_id=account_id,
                profile_id=profile_id,
                jd_id=jd.id,
                ordinal=ordinal,
                requirement_type="UNCLASSIFIED",
                exact_text=source_text[start:end],
                source_start=start,
                source_end=end,
            )
        )
    session.flush()
    return jd


def get_jd_analysis(session: Session, *, account_id: str, jd_id: str) -> JDAnalysisView:
    """Read one exact JD version through an active owner; no raw source fallback."""

    jd = session.scalar(
        select(JobDescription)
        .join(Account, Account.id == JobDescription.account_id)
        .join(CareerProfile, CareerProfile.id == JobDescription.profile_id)
        .where(
            JobDescription.id == jd_id,
            JobDescription.account_id == account_id,
            JobDescription.status == "ACTIVE",
            Account.status == "ACTIVE",
            CareerProfile.account_id == account_id,
            CareerProfile.status == "ACTIVE",
        )
        .with_for_update(of=[Account, CareerProfile, JobDescription], read=True)
        .execution_options(populate_existing=True)
    )
    if jd is None:
        raise JDUnavailable
    requirements = tuple(
        session.scalars(
            select(JDRequirement)
            .where(
                JDRequirement.jd_id == jd.id,
                JDRequirement.account_id == account_id,
                JDRequirement.profile_id == jd.profile_id,
            )
            .order_by(JDRequirement.ordinal)
        )
    )
    if not 1 <= len(requirements) <= MAX_REQUIREMENTS or any(
        item.source_end > jd.source_length
        or len(item.exact_text) != item.source_end - item.source_start
        for item in requirements
    ):
        raise JDUnavailable
    return JDAnalysisView(
        jd_id=jd.id,
        jd_version=jd.jd_version,
        source_hash=jd.source_hash,
        source_length=jd.source_length,
        requirements=tuple(
            (item.ordinal, item.exact_text, item.source_start, item.source_end)
            for item in requirements
        ),
    )
