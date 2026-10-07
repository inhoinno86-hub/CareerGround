"""Prevent reuse of an explicitly erased project scope in local review flows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.storage.models import ProjectScope


def deleted_project_scope_exists(
    session: Session, *, account_id: str, profile_id: str, scope_key: str
) -> bool:
    """Check the owned tombstone, including scopes erased by a prior request."""

    return (
        session.scalar(
            select(ProjectScope.id).where(
                ProjectScope.account_id == account_id,
                ProjectScope.profile_id == profile_id,
                ProjectScope.scope_key == scope_key,
                ProjectScope.status == "DELETING",
            )
        )
        is not None
    )
