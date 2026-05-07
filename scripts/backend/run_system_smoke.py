from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner import (  # noqa: E402
    AvailabilityWindow,
    FeedbackInput,
    GemmaPlannerBackend,
    GemmaPlannerConfig,
    GoalInput,
    MockPlannerBackend,
    PlannerBackend,
    PlannerDatabase,
    PlanningRequest,
    PlanningService,
    PolicyAction,
    ProposalKind,
    ProposalStatus,
    ReminderService,
    TaskStatus,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an end-to-end adaptive planner smoke test.")
    parser.add_argument("--planner", choices=("mock", "gemma"), default="mock")
    parser.add_argument("--port", type=int, default=8093)
    parser.add_argument(
        "--db-path",
        default=str(REPO_ROOT / "artifacts" / "runtime" / "system_smoke.db"),
        help="SQLite database path for the smoke test.",
    )
    parser.add_argument("--reset-db", action="store_true", help="Delete the smoke-test DB before running.")
    return parser.parse_args()


def build_planner(args: argparse.Namespace) -> PlannerBackend:
    if args.planner == "gemma":
        return GemmaPlannerBackend(
            GemmaPlannerConfig(
                port=args.port,
                max_completion_tokens=1200,
                reasoning_budget=128,
            )
        )
    return MockPlannerBackend()


def availability_windows() -> list[AvailabilityWindow]:
    return [
        AvailabilityWindow(weekday=0, start_time=time(18, 0), end_time=time(20, 0)),
        AvailabilityWindow(weekday=1, start_time=time(18, 0), end_time=time(20, 0)),
        AvailabilityWindow(weekday=2, start_time=time(18, 0), end_time=time(20, 0)),
        AvailabilityWindow(weekday=3, start_time=time(18, 0), end_time=time(20, 0)),
    ]


def normalize_task_minutes(service: PlanningService, database: PlannerDatabase, plan_version_id: int) -> None:
    tasks = database.list_tasks(plan_version_id)
    per_task_minutes = max(30, 210 // max(len(tasks), 1))
    for task in tasks:
        service.edit_task(task["id"], estimated_minutes=per_task_minutes)


def create_goal(title: str, description: str) -> GoalInput:
    return GoalInput(
        title=title,
        description=description,
        target_start_date=date(2026, 4, 6),
        target_end_date=date(2026, 4, 7),
        availability=availability_windows(),
    )


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path)
    if args.reset_db and db_path.exists():
        db_path.unlink()

    database = PlannerDatabase(db_path)
    database.initialize()
    planner = build_planner(args)
    reminder_service = ReminderService(database)
    service = PlanningService(database=database, planner=planner)

    try:
        goal_one = create_goal("Ship the first backend slice", "Build and verify the deterministic backend core.")
        _, plan_one_id = service.create_plan(PlanningRequest(goal=goal_one))
        normalize_task_minutes(service, database, plan_one_id)
        result_one = service.approve_and_schedule(plan_one_id)
        print(f"plan_one_id={plan_one_id} conflicts={len(result_one.conflicts)} status={database.get_plan_version(plan_one_id)['status']}")

        goal_two = create_goal("Prepare ML revision notes", "Create a focused second plan that competes for the same time.")
        _, plan_two_id = service.create_plan(PlanningRequest(goal=goal_two))
        normalize_task_minutes(service, database, plan_two_id)
        result_two = service.approve_and_schedule(plan_two_id)
        pending_rebalances = database.list_proposals(
            plan_version_id=plan_two_id,
            proposal_type=ProposalKind.REBALANCE,
            status=ProposalStatus.PENDING,
        )
        print(
            f"plan_two_id={plan_two_id} conflicts={len(result_two.conflicts)} "
            f"status={database.get_plan_version(plan_two_id)['status']} "
            f"pending_rebalances={len(pending_rebalances)}"
        )

        if pending_rebalances:
            rebalance = pending_rebalances[-1]
            result_two = service.apply_rebalance(rebalance["id"])
            updated_goal_two = database.get_goal(database.get_plan_version(plan_two_id)["goal_id"])
            print(
                f"rebalance_applied proposal_id={rebalance['id']} "
                f"new_end_date={updated_goal_two['target_end_date']} "
                f"conflicts={len(result_two.conflicts)} "
                f"status={database.get_plan_version(plan_two_id)['status']}"
            )

        delivered = reminder_service.deliver_due_reminders(datetime(2026, 4, 6, 17, 50))
        print(f"delivered_reminders={len(delivered)}")
        for item in delivered:
            print(f"reminder[{item.reminder_id}] {item.reminder_type}: {item.task_title}")

        first_task_plan_two = database.list_tasks(plan_two_id)[0]
        edited = service.edit_task(first_task_plan_two["id"], estimated_minutes=max(30, int(first_task_plan_two["estimated_minutes"]) - 10))
        regenerated = service.regenerate_schedule(plan_two_id)
        print(
            f"edited_task_id={edited['id']} regenerated_conflicts={len(regenerated.conflicts)} "
            f"status={database.get_plan_version(plan_two_id)['status']}"
        )

        second_task_plan_two = database.list_tasks(plan_two_id)[1]
        outcome = service.record_feedback(
            second_task_plan_two["id"],
            FeedbackInput(
                status=TaskStatus.BLOCKED,
                actual_minutes=35,
                difficulty=4,
                confidence=0.25,
                note="Blocked during execution in the smoke test.",
            ),
        )
        print(f"policy_action={outcome.action.value}")

        if outcome.action == PolicyAction.PROPOSE_REPLAN:
            service.generate_replan_proposal(plan_two_id, second_task_plan_two["id"], outcome.reason)
            pending_replans = database.list_proposals(
                plan_version_id=plan_two_id,
                proposal_type=ProposalKind.REPLAN,
                status=ProposalStatus.PENDING,
            )
            replan = pending_replans[-1]
            replan_result = service.apply_replan_proposal(replan["id"])
            applied_replan = database.get_proposal(replan["id"])
            new_plan_version_id = applied_replan["payload"]["new_plan_version_id"]
            print(
                f"replan_applied proposal_id={replan['id']} "
                f"new_plan_version_id={new_plan_version_id} "
                f"conflicts={len(replan_result.conflicts)} "
                f"new_status={database.get_plan_version(new_plan_version_id)['status']} "
                f"old_status={database.get_plan_version(plan_two_id)['status']}"
            )

    finally:
        close_method = getattr(planner, "close", None)
        if callable(close_method):
            close_method()


if __name__ == "__main__":
    main()
