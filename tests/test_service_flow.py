from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner import (  # noqa: E402
    AvailabilityWindow,
    FeedbackInput,
    GoalInput,
    MockPlannerBackend,
    PlannerDatabase,
    PlanningRequest,
    PlanningService,
    PlanStatus,
    TaskStatus,
)


class ServiceFlowTests(unittest.TestCase):
    def test_create_and_activate_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = PlannerDatabase(Path(temp_dir) / "planner.db")
            database.initialize()
            service = PlanningService(database=database, planner=MockPlannerBackend())
            goal = GoalInput(
                title="Build a small demo project",
                description="Create and review a simple plan.",
                target_start_date=date(2026, 4, 6),
                target_end_date=date(2026, 4, 12),
                availability=[
                    AvailabilityWindow(weekday=0, start_time=time(18, 0), end_time=time(21, 0)),
                    AvailabilityWindow(weekday=1, start_time=time(18, 0), end_time=time(21, 0)),
                    AvailabilityWindow(weekday=2, start_time=time(18, 0), end_time=time(21, 0)),
                ],
            )

            _, plan_version_id = service.create_plan(PlanningRequest(goal=goal))
            result = service.approve_and_schedule(plan_version_id)

            self.assertFalse(result.conflicts)
            self.assertTrue(database.list_schedule_blocks(plan_version_id))
            self.assertTrue(database.list_reminders(plan_version_id))
            self.assertEqual(database.get_plan_version(plan_version_id)["status"], PlanStatus.ACTIVE.value)

    def test_replan_can_be_generated_and_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = PlannerDatabase(Path(temp_dir) / "planner.db")
            database.initialize()
            service = PlanningService(database=database, planner=MockPlannerBackend())
            goal = GoalInput(
                title="Learn a new topic",
                description="Create, run, and revise a simple plan.",
                target_start_date=date(2026, 4, 6),
                target_end_date=date(2026, 4, 15),
                availability=[
                    AvailabilityWindow(weekday=0, start_time=time(18, 0), end_time=time(21, 0)),
                    AvailabilityWindow(weekday=1, start_time=time(18, 0), end_time=time(21, 0)),
                    AvailabilityWindow(weekday=2, start_time=time(18, 0), end_time=time(21, 0)),
                    AvailabilityWindow(weekday=3, start_time=time(18, 0), end_time=time(21, 0)),
                ],
            )

            _, plan_version_id = service.create_plan(PlanningRequest(goal=goal))
            service.approve_and_schedule(plan_version_id)
            task_id = database.list_tasks(plan_version_id)[1]["id"]
            outcome = service.record_feedback(
                task_id,
                FeedbackInput(status=TaskStatus.BLOCKED, note="Need to revise the approach."),
            )

            self.assertEqual(outcome.action.value, "propose_replan")
            replan_id = service.generate_replan_proposal(plan_version_id, task_id, outcome.reason)
            result = service.apply_replan(replan_id)

            self.assertFalse(result.conflicts)
            self.assertEqual(database.get_plan_version(replan_id)["status"], PlanStatus.ACTIVE.value)
            self.assertEqual(database.get_plan_version(plan_version_id)["status"], PlanStatus.SUPERSEDED.value)


if __name__ == "__main__":
    unittest.main()
