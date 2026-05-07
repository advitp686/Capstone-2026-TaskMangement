from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner.domain import FeedbackInput, PolicyAction, TaskStatus  # noqa: E402
from adaptive_planner.policies import FeedbackContext, FeedbackPolicy  # noqa: E402


class FeedbackPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = FeedbackPolicy()

    def test_blocked_task_proposes_replan(self) -> None:
        outcome = self.policy.evaluate(
            FeedbackInput(status=TaskStatus.BLOCKED, confidence=0.2),
            FeedbackContext(estimated_minutes=60),
        )
        self.assertEqual(outcome.action, PolicyAction.PROPOSE_REPLAN)
        self.assertTrue(outcome.requires_user_confirmation)

    def test_repeated_delay_requests_review(self) -> None:
        outcome = self.policy.evaluate(
            FeedbackInput(status=TaskStatus.DELAYED, actual_minutes=120),
            FeedbackContext(
                estimated_minutes=60,
                recent_statuses=[TaskStatus.DELAYED, TaskStatus.DONE],
                dependency_critical=True,
            ),
        )
        self.assertEqual(outcome.action, PolicyAction.REQUEST_REVIEW)

    def test_low_confidence_requests_feedback(self) -> None:
        outcome = self.policy.evaluate(
            FeedbackInput(status=TaskStatus.DONE, confidence=0.2),
            FeedbackContext(estimated_minutes=60),
        )
        self.assertEqual(outcome.action, PolicyAction.REQUEST_FEEDBACK)


if __name__ == "__main__":
    unittest.main()
