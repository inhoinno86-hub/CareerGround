"""Offline, explicit, account/client-scoped unblock; no automatic recovery."""

import argparse
import os
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

from careerground.domain.authorization import VerifiedIdentity
from careerground.storage.development_connection_recovery import recover_connection
from careerground.storage.development_connection_revocations import DevelopmentConnectionRevocations
from careerground.storage.development_files import DevelopmentStoreRejected
from careerground.storage.models import Account
from scripts.recover_development_connection import recover
from tests import test_authenticated_deletion as deletion
from tests import test_authenticated_management as foundation


class DevelopmentConnectionRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        deletion.AuthenticatedDeletionTests.setUpClass()

    def setUp(self):
        self.fx = deletion.AuthenticatedDeletionTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.base = self.fx.fx
        with self.base.client() as a, self.base.other_browser() as b:
            self.base.enroll(a)
            self.base.enroll(b, "user-b")
        self.path = self.fx.path.parent / "denials"
        self.registry = DevelopmentConnectionRevocations(
            self.path, issuer=foundation.ISSUER, initialize=True
        )
        self.addCleanup(lambda: self.registry.close())
        self.a = VerifiedIdentity(foundation.ISSUER, "user-a")
        self.b = VerifiedIdentity(foundation.ISSUER, "user-b")
        for identity, client in (
            (self.a, "target-client"),
            (self.b, "target-client"),
            (self.a, "other-client"),
        ):
            self.registry.block(identity, client)
        self.account = self.fx.store.admit(self.a)
        self.args = argparse.Namespace(
            state_dir=self.fx.path,
            connection_denials_dir=self.path,
            account_id=self.account,
            connection_client_id="target-client",
            confirm_unblock=True,
        )
        self.environment = {
            "AUTH0_DOMAIN": "auth.management.synthetic.example",
            "AUTH0_CLIENT_ID": foundation.CLIENT_ID,
            "AUTH0_CLIENT_SECRET": "synthetic-unused",
            "AUTH0_SECRET": "synthetic-unused",
            "APP_BASE_URL": "http://localhost:5000",
            "CAREERGROUND_POC_ISSUER": foundation.ISSUER,
            "CAREERGROUND_POC_RESOURCE_URL": foundation.RESOURCE,
        }

    def counts(self):
        with closing(sqlite3.connect(self.fx.path / "authenticated.sqlite")) as connection:
            tables = [
                r[0]
                for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            ]
            return {
                t: connection.execute('SELECT COUNT(*) FROM "' + t + '"').fetchone()[0]
                for t in tables
            }

    def test_offline_command_refuses_live_runtime_then_unblocks_only_reviewed_pair(self):
        before = (self.path / "denials.json").read_bytes()
        counts = self.counts()
        with (
            patch.dict(os.environ, self.environment, clear=True),
            self.assertRaises((BlockingIOError, DevelopmentStoreRejected)),
        ):
            recover(self.args)
        self.assertEqual((self.path / "denials.json").read_bytes(), before)
        self.registry.close()
        self.fx.store.close()
        with patch.dict(os.environ, self.environment, clear=True):
            self.assertTrue(recover(self.args))
            self.assertFalse(recover(self.args))
        self.assertEqual(self.counts(), counts)
        registry = DevelopmentConnectionRevocations(self.path, issuer=foundation.ISSUER)
        try:
            self.assertFalse(registry.is_blocked(self.a, "target-client"))
            self.assertTrue(registry.is_blocked(self.b, "target-client"))
            self.assertTrue(registry.is_blocked(self.a, "other-client"))
        finally:
            registry.close()

    def test_unacknowledged_unknown_inactive_and_corrupt_recovery_are_refused(self):
        before = (self.path / "denials.json").read_bytes()
        for ack in (False, 1, "yes"):
            with self.subTest(ack=ack), self.assertRaises(DevelopmentStoreRejected):
                recover_connection(
                    self.fx.store,
                    self.registry,
                    account_id=self.account,
                    client_id="target-client",
                    acknowledged=ack,
                )
        with self.assertRaises(DevelopmentStoreRejected):
            recover_connection(
                self.fx.store,
                self.registry,
                account_id="absent",
                client_id="target-client",
                acknowledged=True,
            )
        with self.fx.store.sessions() as session:
            session.get(Account, self.account).status = "DELETING"
            session.commit()
        with self.assertRaises(DevelopmentStoreRejected):
            recover_connection(
                self.fx.store,
                self.registry,
                account_id=self.account,
                client_id="target-client",
                acknowledged=True,
            )
        self.assertEqual((self.path / "denials.json").read_bytes(), before)
        with self.fx.store.sessions() as session:
            session.get(Account, self.account).status = "ACTIVE"
            session.commit()
        (self.path / "denials.json").write_text("{}")
        with self.assertRaises(DevelopmentStoreRejected):
            recover_connection(
                self.fx.store,
                self.registry,
                account_id=self.account,
                client_id="target-client",
                acknowledged=True,
            )

    def test_offline_command_never_initializes_a_missing_store(self):
        missing = self.fx.path.parent / "absent-state"
        self.args.state_dir = missing
        with patch.dict(os.environ, self.environment, clear=True), self.assertRaises(ValueError):
            recover(self.args)
        self.assertFalse(missing.exists())
