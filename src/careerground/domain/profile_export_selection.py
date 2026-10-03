"""Strict, explicit owner/version and personal export selection boundaries."""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from careerground.storage.models import Account, CareerProfile


class ProfileSelectionRejected(ValueError):
    pass


class ProfileExportSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    claims: bool = True
    evidence: bool = True
    boundaries: bool = True
    drafts: bool = False
    unavailable_references: bool = True


VersionSelector = int | Literal["CURRENT"]


def selection_values(value=None):
    if value is None:
        return ProfileExportSelection().model_dump()
    if isinstance(value, ProfileExportSelection):
        return value.model_dump()
    if type(value) is not dict or set(value) != set(ProfileExportSelection.model_fields):
        raise ProfileSelectionRejected
    if any(type(item) is not bool for item in value.values()):
        raise ProfileSelectionRejected
    return dict(value)


def resolve_profile_version(session, *, account_id, profile_id, selector):
    if selector != "CURRENT":
        if type(selector) is not int or selector < 0:
            raise ProfileSelectionRejected
        return selector
    profile = session.scalar(
        select(CareerProfile)
        .join(Account, Account.id == CareerProfile.account_id)
        .where(
            CareerProfile.id == profile_id,
            CareerProfile.account_id == account_id,
            CareerProfile.status == "ACTIVE",
            Account.status == "ACTIVE",
        )
        .with_for_update(of=[Account, CareerProfile], read=True)
        .execution_options(populate_existing=True)
    )
    if profile is None:
        raise ProfileSelectionRejected
    return profile.version
