"""Protocol question order and stop guards without text inference or writes."""

from __future__ import annotations

import unittest

from careerground.domain.profiling_questions import (
    ObservationStatus,
    ProtocolObservation,
    ProtocolState,
    plan_next_question,
)


def sourced(state: ProtocolState) -> ProtocolObservation:
    return ProtocolObservation(
        state=state,
        status=ObservationStatus.SATISFIED,
        source_input_id=f"synthetic-input-{state.value}",
    )


class ProfilingQuestionTests(unittest.TestCase):
    def test_explicit_source_is_needed_to_advance_from_context_to_role(self) -> None:
        empty = plan_next_question({}, {})
        self.assertEqual(empty.state, ProtocolState.CONTEXT_DISCOVERY)
        self.assertEqual(empty.question_attempt, 1)
        self.assertFalse(empty.blocked)
        self.assertFalse(empty.complete)
        self.assertEqual(
            plan_next_question({}, {ProtocolState.CONTEXT_DISCOVERY: 1}).question_attempt, 2
        )
        exhausted = plan_next_question({}, {ProtocolState.CONTEXT_DISCOVERY: 2})
        self.assertEqual(exhausted.state, ProtocolState.CONTEXT_DISCOVERY)
        self.assertTrue(exhausted.blocked)
        self.assertIsNone(exhausted.question)
        next_step = plan_next_question(
            {ProtocolState.CONTEXT_DISCOVERY: sourced(ProtocolState.CONTEXT_DISCOVERY)}, {}
        )
        self.assertEqual(next_step.state, ProtocolState.ROLE_DISCOVERY)
        self.assertFalse(next_step.complete)

    def test_optional_unknown_requires_reason_but_never_satisfies_required_guard(self) -> None:
        observations = {
            state: sourced(state)
            for state in (
                ProtocolState.CONTEXT_DISCOVERY,
                ProtocolState.ROLE_DISCOVERY,
                ProtocolState.PROJECT_DISCOVERY,
            )
        }
        observations[ProtocolState.RESPONSIBILITY_DISCOVERY] = ProtocolObservation(
            state=ProtocolState.RESPONSIBILITY_DISCOVERY,
            status=ObservationStatus.UNKNOWN,
            reason="사용자가 공식 책임을 확인할 수 없다고 답함",
        )
        plan = plan_next_question(observations, {})
        self.assertEqual(plan.state, ProtocolState.CONTRIBUTION_DISCOVERY)
        self.assertEqual(plan.unknown_fields, (ProtocolState.RESPONSIBILITY_DISCOVERY,))
        observations[ProtocolState.CONTRIBUTION_DISCOVERY] = ProtocolObservation(
            state=ProtocolState.CONTRIBUTION_DISCOVERY,
            status=ObservationStatus.UNKNOWN,
            reason="직접 수행한 작업을 특정하지 못함",
        )
        blocked = plan_next_question(observations, {})
        self.assertEqual(blocked.state, ProtocolState.CONTRIBUTION_DISCOVERY)
        self.assertTrue(blocked.blocked)
        self.assertFalse(blocked.complete)

    def test_conflict_asks_once_more_then_blocks_without_silent_resolution(self) -> None:
        state = ProtocolState.OWNERSHIP_PROBING
        observations = {earlier: sourced(earlier) for earlier in list(ProtocolState)[:5]}
        observations[state] = ProtocolObservation(
            state=state,
            status=ObservationStatus.CONFLICT,
            source_input_id="synthetic-conflicting-input",
            reason="담당 범위와 최종 결정권이 상충함",
        )
        follow_up = plan_next_question(observations, {state: 1})
        self.assertEqual(follow_up.state, state)
        self.assertEqual(follow_up.question_attempt, 2)
        self.assertIn("최종 결정권", follow_up.question)
        exhausted = plan_next_question(observations, {state: 2})
        self.assertTrue(exhausted.blocked)
        self.assertFalse(exhausted.complete)

    def test_all_question_observations_still_need_separate_completion_review(
        self,
    ) -> None:
        states = [state for state in ProtocolState if state is not ProtocolState.COMPLETE]
        observations = {state: sourced(state) for state in states}
        plan = plan_next_question(observations, {})
        self.assertFalse(plan.complete)
        self.assertEqual(plan.state, ProtocolState.BOUNDARY_CHECK)
        self.assertIsNone(plan.question)
        self.assertTrue(plan.blocked)
        self.assertEqual(plan.unknown_fields, ())
        del observations[ProtocolState.BOUNDARY_CHECK]
        self.assertEqual(
            plan_next_question(observations, {}).state,
            ProtocolState.BOUNDARY_CHECK,
        )

    def test_malformed_observations_and_attempts_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProtocolObservation(ProtocolState.ROLE_DISCOVERY, ObservationStatus.SATISFIED)
        with self.assertRaises(ValueError):
            ProtocolObservation(ProtocolState.OUTCOME_PROBING, ObservationStatus.UNKNOWN)
        with self.assertRaises(ValueError):
            ProtocolObservation(
                ProtocolState.OUTCOME_PROBING,
                ObservationStatus.SATISFIED,
                "synthetic-source",
                reason=" " * 2,
            )
        with self.assertRaises(ValueError):
            plan_next_question({}, {ProtocolState.CONTEXT_DISCOVERY: 3})
        with self.assertRaises(ValueError):
            plan_next_question(
                {ProtocolState.ROLE_DISCOVERY: sourced(ProtocolState.CONTEXT_DISCOVERY)},
                {},
            )


if __name__ == "__main__":
    unittest.main()
