"""Bounded owner-scoped navigation for synthetic resume text drafts."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.storage.jd_artifact_models import Artifact, JobDescription
from careerground.storage.models import Account, CareerProfile


@dataclass(frozen=True)
class ResumeArtifactListItem:
    artifact_id: str
    artifact_version: int
    profile_version: int
    status: str


@dataclass(frozen=True)
class ResumeArtifactList:
    items: tuple[ResumeArtifactListItem, ...]
    more_items: bool


@dataclass(frozen=True)
class JDListItem:
    jd_id: str
    jd_version: int
    company_name: str | None
    job_title: str | None


@dataclass(frozen=True)
class JDList:
    items: tuple[JDListItem, ...]
    more_items: bool


def list_jd_analyses(session: Session, *, account_id: str) -> JDList:
    """List active-owner JD metadata, never the unselected pasted source."""

    rows = tuple(
        session.scalars(
            select(JobDescription)
            .join(Account, Account.id == JobDescription.account_id)
            .join(CareerProfile, CareerProfile.id == JobDescription.profile_id)
            .where(
                JobDescription.account_id == account_id,
                JobDescription.status == "ACTIVE",
                Account.status == "ACTIVE",
                CareerProfile.account_id == account_id,
                CareerProfile.status == "ACTIVE",
            )
            .order_by(JobDescription.created_at.desc(), JobDescription.id)
            .limit(21)
        )
    )
    return JDList(
        items=tuple(
            JDListItem(item.id, item.jd_version, item.company_name, item.job_title)
            for item in rows[:20]
        ),
        more_items=len(rows) > 20,
    )


def list_resume_artifacts(session: Session, *, account_id: str) -> ResumeArtifactList:
    """List only active-owner metadata; exact trace rechecks every linked source."""

    rows = tuple(
        session.scalars(
            select(Artifact)
            .join(Account, Account.id == Artifact.account_id)
            .join(CareerProfile, CareerProfile.id == Artifact.profile_id)
            .where(
                Artifact.account_id == account_id,
                Artifact.artifact_type == "RESUME_TEXT",
                Artifact.status.in_(("DRAFT", "REVIEW_REQUIRED", "WORDING_REVIEWED")),
                Account.status == "ACTIVE",
                CareerProfile.account_id == account_id,
                CareerProfile.status == "ACTIVE",
            )
            .order_by(Artifact.created_at.desc(), Artifact.id)
            .limit(21)
        )
    )
    return ResumeArtifactList(
        items=tuple(
            ResumeArtifactListItem(
                item.id, item.artifact_version, item.profile_version, item.status
            )
            for item in rows[:20]
        ),
        more_items=len(rows) > 20,
    )
