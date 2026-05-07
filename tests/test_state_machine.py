from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner.domain import PlanStatus, TaskStatus  # noqa: E402
from adaptive_planner.state_machine import (  # noqa: E402
    ensure_plan_transition,
    ensure_task_transition,
)


class StateMachineTests(unittest.TestCase):
    def test_plan_transition_accepts_review_flow(self) -> None:
        ensure_plan_transition(PlanStatus.ACTIVE, PlanStatus.REVIEW_NEEDED)
        ensure_plan_transition(PlanStatus.REVIEW_NEEDED, PlanStatus.REPLAN_PROPOSED)

    def test_plan_transition_rejects_invalid_jump(self) -> None:
        with self.assertRaises(ValueError):
            ensure_plan_transition(PlanStatus.PROPOSED, PlanStatus.ACTIVE)

    def test_task_transition_accepts_execution_flow(self) -> None:
        ensure_task_transition(TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS)
        ensure_task_transition(TaskStatus.IN_PROGRESS, TaskStatus.DONE)

    def test_task_transition_rejects_invalid_jump(self) -> None:
        with self.assertRaises(ValueError):
            ensure_task_transition(TaskStatus.DONE, TaskStatus.SCHEDULED)


if __name__ == "__main__":
    unittest.main()
