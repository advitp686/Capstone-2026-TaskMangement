from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, datetime, time
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
    PolicyAction,
    ProposalKind,
    ProposalStatus,
    ReminderService,
    TaskStatus,
)


class OverallSystemFlowTests(unittest.TestCase):
    def test_overall_system_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = PlannerDatabase(Path(temp_dir) / "planner.db")
            database.initialize()
            planner = MockPlannerBackend()
            service = PlanningService(database=database, planner=planner)
            reminder_service = ReminderService(database)

            availability = [
                AvailabilityWindow(weekday=0, start_time=time(18, 0), end_time=time(20, 0)),
                AvailabilityWindow(weekday=1, start_time=time(18, 0), end_time=time(20, 0)),
                AvailabilityWindow(weekday=2, start_time=time(18, 0), end_time=time(20, 0)),
                AvailabilityWindow(weekday=3, start_time=time(18, 0), end_time=time(20, 0)),
            ]

            goal_one = GoalInput(
                title="Plan one",
                description="Primary active plan.",
                target_start_date=date(2026, 4, 6),
                target_end_date=date(2026, 4, 7),
                availability=availability,
            )
            _, plan_one_id = service.create_plan(PlanningRequest(goal=goal_one))
            self._normalize_task_minutes(service, database, plan_one_id)
            result_one = service.approve_and_schedule(plan_one_id)
            self.assertFalse(result_one.conflicts)
            self.assertEqual(database.get_plan_version(plan_one_id)["status"], "active")

            goal_two = GoalInput(
                title="Plan two",
                description="Second plan that should clash with the first active plan.",
                target_start_date=date(2026, 4, 6),
                target_end_date=date(2026, 4, 7),
                availability=availability,
            )
            _, plan_two_id = service.create_plan(PlanningRequest(goal=goal_two))
            self._normalize_task_minutes(service, database, plan_two_id)
            result_two = service.approve_and_schedule(plan_two_id)
            self.assertTrue(result_two.conflicts)

            rebalance = database.list_proposals(
                plan_version_id=plan_two_id,
                proposal_type=ProposalKind.REBALANCE,
                status=ProposalStatus.PENDING,
            )[-1]
            rebalance_result = service.apply_rebalance(rebalance["id"])
            self.assertFalse(rebalance_result.conflicts)
            self.assertEqual(database.get_proposal(rebalance["id"])["status"], ProposalStatus.APPLIED.value)
            self.assertEqual(database.get_plan_version(plan_two_id)["status"], "active")

            delivered = reminder_service.deliver_due_reminders(datetime(2026, 4, 6, 18, 0))
            self.assertTrue(delivered)

            first_task = database.list_tasks(plan_two_id)[0]
            service.edit_task(first_task["id"], estimated_minutes=max(30, first_task["estimated_minutes"] - 10))
            regenerated = service.regenerate_schedule(plan_two_id)
            self.assertFalse(regenerated.conflicts)
            self.assertEqual(database.get_plan_version(plan_two_id)["status"], "active")

            second_task = database.list_tasks(plan_two_id)[1]
            outcome = service.record_feedback(
                second_task["id"],
                FeedbackInput(
                    status=TaskStatus.BLOCKED,
                    actual_minutes=40,
                    difficulty=4,
                    confidence=0.2,
                    note="Blocked during the overall flow test.",
                ),
            )
            self.assertEqual(outcome.action, PolicyAction.PROPOSE_REPLAN)

            service.generate_replan_proposal(plan_two_id, second_task["id"], outcome.reason)
            replan = database.list_proposals(
                plan_version_id=plan_two_id,
                proposal_type=ProposalKind.REPLAN,
                status=ProposalStatus.PENDING,
            )[-1]
            replan_result = service.apply_replan_proposal(replan["id"])
            self.assertFalse(replan_result.conflicts)
            new_plan_version_id = database.get_proposal(replan["id"])["payload"]["new_plan_version_id"]
            self.assertEqual(database.get_proposal(replan["id"])["status"], ProposalStatus.APPLIED.value)
            self.assertEqual(database.get_plan_version(new_plan_version_id)["status"], "active")
            self.assertEqual(database.get_plan_version(plan_two_id)["status"], "superseded")

    def _normalize_task_minutes(
        self,
        service: PlanningService,
        database: PlannerDatabase,
        plan_version_id: int,
    ) -> None:
        tasks = database.list_tasks(plan_version_id)
        per_task_minutes = max(30, 210 // max(len(tasks), 1))
        for task in tasks:
            service.edit_task(task["id"], estimated_minutes=per_task_minutes)


if __name__ == "__main__":
    unittest.main()
