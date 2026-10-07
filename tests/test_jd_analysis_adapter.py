"""Offline proposal boundary tests; no canonical writes or provider connection."""

from __future__ import annotations

import hashlib
import unittest

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.jd_analysis_adapter import (
    JDProposalRejected,
    MockJDAnalyzer,
    prepare_jd_analysis,
)
from careerground.storage.graph_models import Claim
from careerground.storage.jd_artifact_models import JDRequirement, JobDescription
from careerground.storage.models import Account, Base, CareerProfile


class StaticAnalyzer:
    mode = "MOCK_ONLY"

    def __init__(self, payload):
        self.payload = payload
        self.received = []

    def propose(self, source_text):
        self.received.append(source_text)
        return self.payload


class JDAnalysisAdapterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add_all([Account(id="account-a"), Account(id="account-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="account-a", version=3),
                    CareerProfile(id="profile-b", account_id="account-b", version=1),
                ]
            )
            session.commit()

    def tearDown(self):
        self.engine.dispose()

    def prepare(self, analyzer, source="- Python API\n- SQL reports\n", **overrides):
        options = {
            "account_id": "account-a",
            "profile_id": "profile-a",
            "profile_version": 3,
            "source_text": source,
            "analyzer": analyzer,
        }
        options.update(overrides)
        with Session(self.engine) as session:
            proposal = prepare_jd_analysis(session, **options)
            self.assertFalse(session.new)
            self.assertFalse(session.dirty)
            return proposal

    def test_mock_proposes_verbatim_ordered_bullets_without_writes(self):
        source = "- Python API\n- SQL reports\n"
        proposal = self.prepare(MockJDAnalyzer(), source)
        self.assertEqual(proposal.mode, "MOCK_ONLY")
        self.assertEqual(proposal.profile_version, 3)
        self.assertEqual(proposal.source_hash, hashlib.sha256(source.encode()).hexdigest())
        self.assertEqual(proposal.source_length, len(source))
        self.assertEqual(
            [
                (r.ordinal, r.exact_text, r.source_start, r.source_end)
                for r in proposal.requirements
            ],
            [(1, "Python API", 2, 12), (2, "SQL reports", 15, 26)],
        )
        self.assertEqual(
            {(r.requirement_type, r.gap_status) for r in proposal.requirements},
            {("UNCLASSIFIED", "NOT_MAPPED")},
        )
        with Session(self.engine) as session:
            for model in (JobDescription, JDRequirement, Claim):
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)

    def test_provider_receives_only_explicit_source_and_commands_remain_data(self):
        source = "- $(touch /tmp/never-run) and `rm -rf /`\n"
        start, end = source.index("$("), source.index("\n")
        analyzer = StaticAnalyzer(
            {
                "source_hash": hashlib.sha256(source.encode()).hexdigest(),
                "spans": [{"start": start, "end": end}],
            }
        )
        proposal = self.prepare(analyzer, source)
        self.assertEqual(analyzer.received, [source])
        self.assertEqual(proposal.requirements[0].exact_text, source[start:end])

    def test_rejects_untrusted_hash_span_and_extra_inference(self):
        source = "- Python API\n- SQL reports\n"
        digest = hashlib.sha256(source.encode()).hexdigest()
        bad_payloads = [
            {"source_hash": "0" * 64, "spans": [{"start": 2, "end": 12}]},
            {"source_hash": digest, "spans": [{"start": 2, "end": 1000}]},
            {"source_hash": digest, "spans": [{"start": True, "end": 12}]},
            {"source_hash": digest, "spans": [{"start": "2", "end": 12}]},
            {"source_hash": digest, "spans": [{"start": 2, "end": 12, "claim_id": "x"}]},
            {"source_hash": digest, "spans": [{"start": 2, "end": 12}], "coverage": "MATCH"},
            {"source_hash": digest, "spans": [{"start": 2, "end": 12}, {"start": 5, "end": 16}]},
            {"source_hash": digest, "spans": [{"start": 15, "end": 26}, {"start": 2, "end": 12}]},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload), self.assertRaises(JDProposalRejected):
                self.prepare(StaticAnalyzer(payload), source)

    def test_rejects_duplicate_and_multiline_proposals(self):
        source = "- repeat\n- repeat\n"
        with self.assertRaises(JDProposalRejected):
            self.prepare(MockJDAnalyzer(), source)
        source = "prefix\nnext"
        payload = {
            "source_hash": hashlib.sha256(source.encode()).hexdigest(),
            "spans": [{"start": 0, "end": len(source)}],
        }
        with self.assertRaises(JDProposalRejected):
            self.prepare(StaticAnalyzer(payload), source)

    def test_rejects_foreign_stale_inactive_and_bad_source_before_provider(self):
        analyzer = StaticAnalyzer({})
        for changes in (
            {"account_id": "account-b"},
            {"profile_id": "profile-b"},
            {"profile_version": 2},
            {"profile_version": True},
            {"source_text": "x" * 6001},
        ):
            with self.subTest(changes=changes), self.assertRaises(JDProposalRejected):
                self.prepare(analyzer, **changes)
        self.assertEqual(analyzer.received, [])
        with Session(self.engine) as session:
            session.get(CareerProfile, "profile-a").status = "DELETING"
            session.commit()
        with self.assertRaises(JDProposalRejected):
            self.prepare(analyzer)
        self.assertEqual(analyzer.received, [])

    def test_provider_exception_is_private(self):
        class Failing:
            def propose(self, source_text):
                raise RuntimeError("private JD text: " + source_text)

        with self.assertRaises(JDProposalRejected) as caught:
            self.prepare(Failing())
        self.assertEqual(str(caught.exception), "")
        self.assertIsNone(caught.exception.__cause__)


if __name__ == "__main__":
    unittest.main()
