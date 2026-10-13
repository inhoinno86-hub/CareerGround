"""Mock-only interview state, evidence, revision and portable result tests."""

import json
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/mock-interview/runtime"))
from cg_mock.api import create_app
from cg_mock.interview import CRITERIA, InterviewSessions, selected_context
from cg_mock.session import Rejected, exchange


def question(text="체크리스트에서 본인과 동료의 기여를 구분해 설명해 주세요."):
    return {
        "text": text,
        "gap": False,
        "requirement_ids": ["req-document"],
        "fact_ids": ["fact-1"],
        "source_ids": ["source-1"],
        "sentence_ids": ["sentence-tailored-1"],
    }


class MockProvider:
    actual, name = False, "Mock"

    def __init__(self):
        self.calls, self.hook, self.bad_quote = 0, None, False

    def generate(self, task, context, schema):
        self.calls += 1
        if self.hook:
            self.hook()
        if task.startswith("Generate"):
            payload = {
                "questions": [
                    question(f"질문 {i}: 본인과 동료의 기여를 구분해 주세요.") for i in range(5)
                ]
            }
        else:
            quote = "not in user answer" if self.bad_quote else context["confirmed_answer"]["text"]
            payload = {
                "rubric": [
                    {
                        "criterion": c,
                        "text": "고정 자료와 비교한 합성 피드백",
                        "answer_quote": quote,
                    }
                    for c in CRITERIA
                ],
                "candidate_quotes": [quote],
                "followup": question(),
            }
        return {
            "payload": payload,
            "provider": "Mock",
            "actual": False,
            "requested_model": "mock-only",
            "attempt": self.calls,
            "usage": {},
        }


class InterviewEngineTests(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT / "fixtures/portable/handoff-v1.json").read_bytes()
        self.original = json.loads(self.raw)
        self.provider = MockProvider()
        self.store = InterviewSessions(self.provider)
        self.owner = "synthetic-owner"
        self.view = self.store.create(self.owner, self.raw, {})
        self.sid = self.view["session_id"]

    def start(self, mode="coaching"):
        self.store.review(
            self.sid, self.owner, self.view["canonical_digest"], "synthetic review", mode
        )
        self.store.transition(self.sid, self.owner, "start")
        return self.store.questions(self.sid, self.owner)

    def submit(
        self, qid, text="동료 의견을 받아 체크리스트 순서를 수정했습니다.", request="submit-1"
    ):
        view = self.store.answer(self.sid, self.owner, qid, text, "text", request)
        return next(a for a in view["interview"]["answers"] if a["request_id"] == request)

    def test_minimum_context_excludes_history_attachments_contacts_and_commands(self):
        context = selected_context(self.original)
        for key in (
            "workspace",
            "selected_history",
            "attachments",
            "omitted_refs",
            "original_text",
        ):
            self.assertNotIn(key, context)
        self.assertEqual(context["facts"][0]["period"], "2024-03 ~ 2024-06")
        self.assertIn("동료", context["facts"][0]["contribution"])
        self.assertIn("미측정", context["facts"][0]["uncertainty"])
        self.assertEqual(
            context["constraints"],
            self.original["workspace"]["artifacts"][0]["payload"]["constraints"],
        )

    def test_partial_mapping_keeps_factual_and_missing_experience_questions_separate(self):
        context = selected_context(self.original)
        context["mappings"][0]["assessment"] = "partial"
        self.store.validate_question(question(), context)
        gap = {**question(), "gap": True, "fact_ids": [], "source_ids": [], "sentence_ids": []}
        self.store.validate_question(gap, context)
        for field in ("fact_ids", "source_ids", "sentence_ids"):
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(Rejected, "QUESTION_GAP_REFERENCE"),
            ):
                self.store.validate_question({**gap, field: question()[field]}, context)
        context["mappings"][0]["assessment"] = "supported"
        with self.assertRaisesRegex(Rejected, "QUESTION_GAP_REFERENCE"):
            self.store.validate_question(gap, context)

    def test_mixed_gap_references_reject_whole_batch_and_corrected_retry_can_commit(self):
        for a in self.original["workspace"]["artifacts"]:
            if a["kind"] == "resume":
                for m in a["payload"]["mappings"]:
                    if m["fact_ids"]:
                        m["assessment"] = "partial"
        raw = json.dumps(self.original, ensure_ascii=False).encode()
        view = self.store.create(self.owner, raw, {})
        sid = view["session_id"]
        self.store.review(sid, self.owner, view["canonical_digest"], "synthetic review", "coaching")
        self.store.transition(sid, self.owner, "start")
        generate = self.provider.generate

        def mixed(task, context, schema):
            output = generate(task, context, schema)
            q = output["payload"]["questions"][-1]
            q["gap"] = True
            if self.provider.calls > 1:
                q.update(fact_ids=[], source_ids=[], sentence_ids=[])
            return output

        self.provider.generate = mixed
        with self.assertRaisesRegex(Rejected, "QUESTION_GAP_REFERENCE"):
            self.store.questions(sid, self.owner)
        self.assertEqual(self.store.view(sid, self.owner)["interview"]["questions"], [])
        corrected = self.store.questions(sid, self.owner)
        self.assertEqual(len(corrected["interview"]["questions"]), 5)
        self.assertEqual(self.provider.calls, 2)

    def test_review_gate_retry_idempotence_and_confirmation(self):
        with self.assertRaises(Rejected):
            self.store.questions(self.sid, self.owner)
        self.assertEqual(self.provider.calls, 0)
        view = self.start()
        self.store.questions(self.sid, self.owner)
        self.assertEqual(self.provider.calls, 1)
        qid = view["interview"]["questions"][0]["id"]
        answer = self.submit(qid)
        self.assertEqual(answer, self.submit(qid))
        with self.assertRaises(Rejected):
            self.submit(qid, "different", request="submit-1")
        app = create_app(credentials={"synthetic-token": self.owner}, sessions=self.store)
        with TestClient(app) as client:
            result = client.post(
                f"/v1/sessions/{self.sid}/answer",
                headers={"Authorization": "Bearer synthetic-token"},
                json={
                    "question_id": qid,
                    "text": "未確認",
                    "input_kind": "text",
                    "request_id": "unconfirmed",
                    "confirmed": False,
                },
            )
            self.assertEqual(result.status_code, 400)
            self.assertEqual(result.json()["errors"], ["ANSWER_CONFIRMATION_REQUIRED"])

    def test_revision_invalidates_old_feedback_candidate_and_followup(self):
        view = self.start()
        qid = view["interview"]["questions"][0]["id"]
        old = self.submit(qid)
        self.store.evaluate(self.sid, self.owner, old["id"])
        child = next(
            q
            for q in self.store.view(self.sid, self.owner)["interview"]["questions"]
            if q["parent_question_id"] == qid
        )
        self.submit(child["id"], "後続の合成回答", request="child-answer")
        current = self.submit(qid, "同僚の意見を反映して順序を修正しました。", request="revision-2")
        with self.assertRaises(Rejected):
            self.store.evaluate(self.sid, self.owner, old["id"])
        self.store.evaluate(self.sid, self.owner, current["id"])
        self.store.finish(self.sid, self.owner)
        result = json.loads(self.store.result(self.sid, self.owner))
        self.assertEqual([a["id"] for a in result["answers"]], [current["id"]])
        self.assertTrue(
            all(x["answer_id"] == current["id"] for x in result["feedback"] + result["candidates"])
        )
        self.assertEqual(exchange.validate_result(result, self.original), [])
        self.assertEqual(exchange.import_result(result, self.original), result)
        self.assertEqual(json.loads(self.raw), self.original)
        self.assertTrue(all(c["status"] == "pending" for c in result["candidates"]))
        with self.assertRaises(Rejected):
            self.store.transition(self.sid, self.owner, "continue")

    def test_simulation_hides_feedback_until_finish_and_skip_works(self):
        view = self.start("simulation")
        first, second = view["interview"]["questions"][:2]
        self.store.skip(self.sid, self.owner, second["id"])
        answer = self.submit(first["id"])
        during = self.store.evaluate(self.sid, self.owner, answer["id"])
        self.assertEqual(during["interview"]["feedback"], [])
        self.assertEqual(during["interview"]["candidates"], [])
        end = self.store.finish(self.sid, self.owner)
        self.assertEqual(len(end["interview"]["feedback"]), 1)

    def test_bad_answer_citation_and_late_response_are_not_committed(self):
        view = self.start()
        answer = self.submit(view["interview"]["questions"][0]["id"])
        self.provider.bad_quote = True
        with self.assertRaisesRegex(Rejected, "FEEDBACK_ANSWER_REFERENCE"):
            self.store.evaluate(self.sid, self.owner, answer["id"])
        self.assertEqual(self.store.view(self.sid, self.owner)["interview"]["feedback"], [])
        self.provider.bad_quote = False

        def pause_and_resume():
            self.store.transition(self.sid, self.owner, "pause")
            self.store.transition(self.sid, self.owner, "continue")

        self.provider.hook = pause_and_resume
        with self.assertRaisesRegex(Rejected, "STALE_MODEL_RESPONSE"):
            self.store.evaluate(self.sid, self.owner, answer["id"])
        self.assertEqual(self.store.view(self.sid, self.owner)["interview"]["feedback"], [])

    def test_trace_export_restore_requires_review_and_distrusts_model_provenance(self):
        view = self.start()
        answer = self.submit(view["interview"]["questions"][0]["id"])
        self.store.evaluate(self.sid, self.owner, answer["id"])
        raw = self.store.export(self.sid, self.owner)
        restored = self.store.restore(self.owner, raw, {})
        self.assertEqual(restored["state"], "REVIEW_REQUIRED")
        self.assertEqual(restored["canonical_digest"], self.view["canonical_digest"])
        self.assertTrue(all(f["stale"] for f in restored["interview"]["feedback"]))
        self.assertTrue(
            all(
                e["provenance"] == "imported_unverified" and not e["actual"]
                for e in restored["interview"]["events"]
            )
        )
        modified = json.loads(raw)
        modified["answers"][0]["question_id"] = "missing-question"
        before = len(self.store._items)
        with self.assertRaisesRegex(Rejected, "SESSION_RECORD_REFERENCE"):
            self.store.restore(self.owner, json.dumps(modified).encode(), {})
        self.assertEqual(len(self.store._items), before)

    def test_extended_attempt_numbers_export_and_restore_without_reclaiming_actual_provenance(self):
        self.provider.calls = 12
        view = self.start()
        answer = self.submit(view["interview"]["questions"][0]["id"])
        self.store.evaluate(self.sid, self.owner, answer["id"])
        raw = self.store.export(self.sid, self.owner)
        data = json.loads(raw)
        self.assertEqual([e["attempt"] for e in data["events"]], [13, 14])
        restored = self.store.restore(self.owner, raw, {})
        self.assertTrue(all(not e["actual"] for e in restored["interview"]["events"]))
        from cg_mock.session import validate_session

        data["events"][0]["attempt"] = 15
        validate_session(json.dumps(data).encode())
        data["events"][0]["attempt"] = 16
        with self.assertRaisesRegex(Rejected, "SESSION_SCHEMA"):
            validate_session(json.dumps(data).encode())

    def test_concurrent_duplicate_evaluation_is_rejected_without_second_call(self):
        view = self.start()
        answer = self.submit(view["interview"]["questions"][0]["id"])

        def overlap():
            with self.assertRaisesRegex(Rejected, "MODEL_BUSY"):
                self.store.evaluate(self.sid, self.owner, answer["id"])

        self.provider.hook = overlap
        self.store.evaluate(self.sid, self.owner, answer["id"])
        self.assertEqual(self.provider.calls, 2)

    def test_provider_failure_keeps_answer_and_records_only_error_metadata(self):
        view = self.start()
        answer = self.submit(view["interview"]["questions"][0]["id"])

        def failed():
            raise Rejected("CODEX_USAGE_LIMIT", status=503)

        self.provider.hook = failed
        with self.assertRaisesRegex(Rejected, "CODEX_USAGE_LIMIT"):
            self.store.evaluate(self.sid, self.owner, answer["id"])
        current = self.store.view(self.sid, self.owner)["interview"]
        self.assertEqual(current["answers"], [answer])
        self.assertEqual(current["feedback"], [])
        self.assertEqual(current["candidates"], [])
        self.assertEqual(current["events"][-1]["error_codes"], ["CODEX_USAGE_LIMIT"])
        self.assertNotIn("text", current["events"][-1])
        self.store.export(self.sid, self.owner)


if __name__ == "__main__":
    unittest.main()
