"""Explicit first-use provisioning from an already verified adapter identity.

An enrollment adapter assigns a stable opaque account ID before admitting a new
identity. It must reuse that ID after retries and identity erasure: a retained
disabled/deleting/erased account can never become a new enrollment. This module
does not verify JWTs, accept email identity, or establish production enrollment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from careerground.domain.authorization import AuthenticationRequired, VerifiedIdentity
from careerground.domain.profile_archive import ensure_profile_archive
from careerground.storage.models import Account, AuthIdentity, CareerProfile


def initialize_account_profile(
    session: Session,
    *,
    identity: VerifiedIdentity,
    enrollment_account_id: str | None = None,
) -> CareerProfile:
    """Create only an admitted identity, or return an active linked profile.

    The caller owns the transaction. IDs for enrollment come from a trusted
    server adapter, never tool arguments. Existing blocked identities/profiles
    and orphaned enrollment IDs are denied rather than repaired.
    """
    if (
        type(identity) is not VerifiedIdentity
        or not identity.issuer
        or not identity.subject
        or len(identity.issuer) > 512
        or len(identity.subject) > 512
    ):
        raise AuthenticationRequired
    linked = session.scalar(
        select(AuthIdentity).where(
            AuthIdentity.issuer == identity.issuer, AuthIdentity.subject == identity.subject
        )
    )
    if linked is not None:
        account = session.scalar(
            select(Account).where(Account.id == linked.account_id).with_for_update()
        )
        if account is None or account.status != "ACTIVE":
            raise AuthenticationRequired
    else:
        try:
            if type(enrollment_account_id) is not str:
                raise ValueError
            if str(UUID(enrollment_account_id)) != enrollment_account_id:
                raise ValueError
        except (ValueError, AttributeError):
            raise AuthenticationRequired from None
        # Account tombstones survive removal of AuthIdentity. A stable adapter
        # admission ID cannot recreate a deleted identity under a new account.
        if session.get(Account, enrollment_account_id) is not None:
            raise AuthenticationRequired
        try:
            with session.begin_nested():
                account = Account(id=enrollment_account_id, status="ACTIVE")
                session.add(account)
                session.flush()
                session.add(
                    AuthIdentity(
                        id=str(uuid4()),
                        account_id=account.id,
                        issuer=identity.issuer,
                        subject=identity.subject,
                    )
                )
                session.flush()
        except IntegrityError:
            # The winning enrollment must map to this exact verified identity.
            return initialize_account_profile(session, identity=identity)
    profile = session.scalar(
        select(CareerProfile).where(CareerProfile.account_id == account.id).with_for_update()
    )
    if profile is not None:
        if profile.status != "ACTIVE":
            raise AuthenticationRequired
        return profile
    profile = CareerProfile(id=str(uuid4()), account_id=account.id, version=0, status="ACTIVE")
    session.add(profile)
    session.flush()
    ensure_profile_archive(
        session,
        account_id=account.id,
        profile_id=profile.id,
        profile_version=0,
        now=datetime.now(UTC),
    )
    return profile
