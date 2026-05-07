from __future__ import annotations

import argparse
import sys
from datetime import date, time
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
    TaskStatus,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the adaptive planner backend demo.")
    parser.add_argument(
        "--planner",
        choices=("mock", "gemma"),
        default="mock",
        help="Planner backend to use.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8091,
        help="Port for the Gemma llama.cpp server when --planner gemma is used.",
    )
    parser.add_argument(
        "--model-path",
        default=str(REPO_ROOT / "models" / "gemma4" / "gemma-4-E2B-it-Q4_K_M.gguf"),
        help="GGUF model path for the Gemma planner.",
    )
    parser.add_argument(
        "--server-path",
        default=str(REPO_ROOT / "llama-cpp" / "llama-server.exe"),
        help="llama-server executable path for the Gemma planner.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1200,
        help="Maximum completion tokens for the Gemma planner.",
    )
    parser.add_argument(
        "--reasoning-budget",
        type=int,
        default=192,
        help="Reasoning budget for the Gemma planner.",
    )
    return parser.parse_args()


def build_planner(args: argparse.Namespace) -> PlannerBackend:
    if args.planner == "gemma":
        return GemmaPlannerBackend(
            GemmaPlannerConfig(
                port=args.port,
                model_path=Path(args.model_path),
                server_path=Path(args.server_path),
                max_completion_tokens=args.max_tokens,
                reasoning_budget=args.reasoning_budget,
            )
        )
    return MockPlannerBackend()


def main() -> None:
    args = parse_args()
    database_path = REPO_ROOT / "artifacts" / "runtime" / "adaptive_planner.db"
    database = PlannerDatabase(database_path)
    database.initialize()

    planner = build_planner(args)
    service = PlanningService(database=database, planner=planner)
    goal = GoalInput(
        title="Learn linear algebra for machine learning in 20 days",
        description="Build a structured plan with study, practice, and review time.",
        target_start_date=date(2026, 4, 6),
        target_end_date=date(2026, 4, 25),
        availability=[
            AvailabilityWindow(weekday=0, start_time=time(18, 0), end_time=time(21, 0)),
            AvailabilityWindow(weekday=1, start_time=time(18, 0), end_time=time(21, 0)),
            AvailabilityWindow(weekday=2, start_time=time(18, 0), end_time=time(21, 0)),
            AvailabilityWindow(weekday=3, start_time=time(18, 0), end_time=time(21, 0)),
            AvailabilityWindow(weekday=4, start_time=time(18, 0), end_time=time(21, 0)),
            AvailabilityWindow(weekday=5, start_time=time(10, 0), end_time=time(14, 0)),
        ],
    )

    try:
        goal_id, plan_version_id = service.create_plan(PlanningRequest(goal=goal))
        schedule = service.approve_and_schedule(plan_version_id)

        print(f"goal_id={goal_id}")
        print(f"plan_version_id={plan_version_id}")
        print(f"planner={args.planner}")
        print(f"scheduled_blocks={len(schedule.blocks)}")
        print(f"conflicts={len(schedule.conflicts)}")

        tasks = database.list_tasks(plan_version_id)
        for task in tasks:
            print(f"task[{task['id']}] {task['status']}: {task['title']}")

        blocks = database.list_schedule_blocks(plan_version_id)
        for block in blocks[:6]:
            print(
                "block"
                f" task_id={block['task_id']}"
                f" start={block['start_at']}"
                f" end={block['end_at']}"
            )

        if len(tasks) < 2:
            return

        second_task_id = tasks[1]["id"]
        outcome = service.record_feedback(
            second_task_id,
            FeedbackInput(
                status=TaskStatus.BLOCKED,
                actual_minutes=45,
                difficulty=4,
                confidence=0.2,
                note="I could not connect the matrix operations to the current examples.",
            ),
        )
        print(f"policy_action={outcome.action.value}")
        print(f"policy_reason={outcome.reason}")

        if outcome.action == PolicyAction.PROPOSE_REPLAN:
            replan_id = service.generate_replan_proposal(plan_version_id, second_task_id, outcome.reason)
            print(f"replan_version_id={replan_id}")
            for task in database.list_tasks(replan_id):
                print(f"replan_task[{task['id']}] {task['title']}")
    finally:
        close_method = getattr(planner, "close", None)
        if callable(close_method):
            close_method()


if __name__ == "__main__":
    main()
