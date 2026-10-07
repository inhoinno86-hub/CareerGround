"""Offline operator recovery for one active account and explicit client only."""

from sqlalchemy import select

from careerground.domain.authorization import VerifiedIdentity, resolve_account_id
from careerground.storage.development_files import DevelopmentStoreRejected
from careerground.storage.models import Account, AuthIdentity


def recover_connection(store, registry, *, account_id, client_id, acknowledged=False) -> bool:
    if (
        type(acknowledged) is not bool
        or not acknowledged
        or type(account_id) is not str
        or not 1 <= len(account_id) <= 255
        or type(client_id) is not str
        or not 1 <= len(client_id) <= 255
        or registry.issuer != store.client.issuer
    ):
        raise DevelopmentStoreRejected
    with store.sessions() as session:
        rows = list(
            session.scalars(
                select(AuthIdentity)
                .join(Account, Account.id == AuthIdentity.account_id)
                .where(
                    AuthIdentity.account_id == account_id,
                    AuthIdentity.issuer == registry.issuer,
                    Account.status == "ACTIVE",
                )
            )
        )
        if len(rows) != 1:
            raise DevelopmentStoreRejected
        identity = VerifiedIdentity(rows[0].issuer, rows[0].subject)
        if resolve_account_id(session, identity) != account_id:
            raise DevelopmentStoreRejected
        return registry.unblock(identity, client_id, acknowledged=True)
