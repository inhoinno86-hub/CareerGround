"""Explicit offline connection unblock; no provider calls or token extraction.

Stop the development runtime first. Supply its unchanged private environment,
state/denial paths and the exact account/client reviewed for this recovery.
"""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from careerground.config import Auth0Settings
from careerground.providers.oidc_identity import IdentityClientSettings
from careerground.storage.authenticated_development_store import AuthenticatedDevelopmentStore
from careerground.storage.development_connection_recovery import recover_connection
from careerground.storage.development_connection_revocations import DevelopmentConnectionRevocations


def recover(args):
    settings = Auth0Settings.from_environment()
    if settings is None:
        raise ValueError("Missing existing development configuration")
    origin = urlsplit(settings.app_base_url)
    if (
        origin.scheme != "http"
        or origin.hostname not in {"localhost", "127.0.0.1"}
        or origin.username
        or origin.password
        or origin.path
        or origin.query
        or origin.fragment
        or not settings.domain
        or "." not in settings.domain
        or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in settings.domain)
    ):
        raise ValueError("Expected existing loopback development configuration")
    issuer = "https://" + settings.domain + "/"
    if os.environ.get("CAREERGROUND_POC_ISSUER") != issuer:
        raise ValueError("Issuer binding mismatch")
    if not args.state_dir.is_dir() or not args.connection_denials_dir.is_dir():
        raise ValueError("Recovery never initializes missing stores")
    client = IdentityClientSettings(
        issuer,
        settings.client_id,
        issuer + "authorize",
        issuer + "oauth/token",
        settings.app_base_url + "/auth/callback",
    )
    store = AuthenticatedDevelopmentStore(
        args.state_dir, client, os.environ.get("CAREERGROUND_POC_RESOURCE_URL", "")
    )
    try:
        registry = DevelopmentConnectionRevocations(args.connection_denials_dir, issuer=issuer)
        try:
            return recover_connection(
                store,
                registry,
                account_id=args.account_id,
                client_id=args.connection_client_id,
                acknowledged=args.confirm_unblock,
            )
        finally:
            registry.close()
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--connection-denials-dir", type=Path, required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--connection-client-id", required=True)
    parser.add_argument("--confirm-unblock", action="store_true", required=True)
    args = parser.parse_args()
    try:
        changed = recover(args)
    except Exception:  # noqa: BLE001 - suppress configuration/identity/provider details
        print(json.dumps({"result": "RECOVERY_REFUSED", "provider_changed": False}))
        raise SystemExit(1) from None
    print(
        json.dumps(
            {"result": "UNBLOCKED" if changed else "ALREADY_UNBLOCKED", "provider_changed": False}
        )
    )


if __name__ == "__main__":
    main()
