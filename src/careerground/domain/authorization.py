"""Provider-neutral identity mapping and tenant-scope checks."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.storage.models import Account, AuthIdentity, CareerProfile


class AuthenticationRequired(Exception):
    """No active account exists for a *validated* external identity."""


class ResourceNotFound(Exception):
    """Resource is absent from this account's authorized view."""


@dataclass(frozen=True)
class VerifiedIdentity:
    """Input from a future verified OIDC/OAuth adapter, never from request body fields."""

    issuer: str
    subject: str


def resolve_account_id(session: Session, identity: VerifiedIdentity) -> str:
    """Map a verified (issuer, subject) to one active account; never trust email."""

    account_id = session.scalar(
        select(Account.id)
        .join(AuthIdentity, AuthIdentity.account_id == Account.id)
        .where(
            AuthIdentity.issuer == identity.issuer,
            AuthIdentity.subject == identity.subject,
            Account.status == "ACTIVE",
        )
    )
    if account_id is None:
        raise AuthenticationRequired
    return account_id


def get_owned_profile(session: Session, *, account_id: str, profile_id: str) -> CareerProfile:
    """Scope the lookup itself; never fetch by ID first and authorize later."""

    profile = session.scalar(
        select(CareerProfile).where(
            CareerProfile.id == profile_id,
            CareerProfile.account_id == account_id,
        )
    )
    if profile is None:
        raise ResourceNotFound
    return profile
