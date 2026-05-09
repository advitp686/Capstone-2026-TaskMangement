from __future__ import annotations

from datetime import date, datetime, timedelta

from .domain import (
    FeedbackInput,
    PlanSnapshot,
    PlanStatus,
    PlanningRequest,
    PolicyAction,
    ProposalKind,
    ProposalStatus,
    ReplanRequest,
    TaskStatus,
)
from .planner import PlannerBackend
from .policies import FeedbackContext, FeedbackPolicy
from .scheduler import DeterministicScheduler, ScheduleResult
from .storage import PlannerDatabase


class PlanningService:
    def __init__(
        self,
        database: PlannerDatabase,
        planner: PlannerBackend,
        scheduler: DeterministicScheduler | None = None,
        feedback_policy: FeedbackPolicy | None = None,
    ) -> None:
        self.database = database
        self.planner = planner
        self.scheduler = scheduler or DeterministicScheduler()
        self.feedback_policy = feedback_policy or FeedbackPolicy()

    def create_plan(
        self,
        request: PlanningRequest,
        *,
        references: list[dict] | None = None,
        assistant_summary: str | None = None,
    ) -> tuple[int, int]:
        active_plan_context = self.database.list_active_plan_context()
        enriched_request = PlanningRequest(
            goal=request.goal,
            active_plan_context=active_plan_context,
        )
        goal_id = self.database.create_goal(request.goal)
        proposal = self.planner.create_plan(enriched_request)
        plan_version_id = self.database.save_plan_proposal(goal_id, proposal, status=PlanStatus.PROPOSED)
        self.database.create_plan_references(goal_id, plan_version_id, references or [])
        if assistant_summary:
            self.database.upsert_assistant_summary(plan_version_id, assistant_summary)
        return goal_id, plan_version_id

    def approve_and_schedule(self, plan_version_id: int) -> ScheduleResult:
        return self._schedule_plan(plan_version_id)

    def regenerate_schedule(self, plan_version_id: int) -> ScheduleResult:
        return self._schedule_plan(plan_version_id)

    def _schedule_plan(self, plan_version_id: int) -> ScheduleResult:
        plan_version = self.database.get_plan_version(plan_version_id)
        goal = self.database.get_goal(plan_version["goal_id"])
        tasks = self.database.list_tasks(plan_version_id)
        dependencies = self.database.list_dependencies(plan_version_id)
        availability = self.database.list_availability(goal["id"])
        existing_blocks = self.database.list_active_schedule_blocks(exclude_goal_id=goal["id"])

        result = self.scheduler.schedule(
            tasks=tasks,
            dependencies=dependencies,
            availability=availability,
            schedule_start=date.fromisoformat(goal["target_start_date"]),
            schedule_end=date.fromisoformat(goal["target_end_date"]),
            existing_blocks=existing_blocks,
        )

        if result.conflicts:
            current_status = PlanStatus(self.database.get_plan_version(plan_version_id)["status"])
            if current_status == PlanStatus.PROPOSED:
                self.database.transition_plan_status(plan_version_id, PlanStatus.APPROVED)
                current_status = PlanStatus.APPROVED
            if current_status == PlanStatus.APPROVED:
                self.database.transition_plan_status(plan_version_id, PlanStatus.REVIEW_NEEDED)
            suggested_end_date = self._suggest_target_end_date(
                tasks=tasks,
                dependencies=dependencies,
                availability=availability,
                existing_blocks=existing_blocks,
                schedule_start=date.fromisoformat(goal["target_start_date"]),
                current_end_date=date.fromisoformat(goal["target_end_date"]),
                max_extension_days=30,
            )
            self.database.create_proposal(
                plan_version_id,
                ProposalKind.REBALANCE,
                "The proposed schedule could not fit inside the available time windows.",
                {
                    "conflicts": [
                        {"task_id": conflict.task_id, "reason": conflict.reason}
                        for conflict in result.conflicts
                    ],
                    "current_target_end_date": goal["target_end_date"],
                    "suggested_target_end_date": suggested_end_date.isoformat() if suggested_end_date else None,
                },
            )
            return result

        schedule_block_ids = self.database.replace_schedule(plan_version_id, result.blocks)
        reminders = self._build_reminders(plan_version_id, result.blocks, schedule_block_ids)
        self.database.create_reminders(reminders)
        self.database.activate_plan(plan_version_id)
        return result

    def record_feedback(self, task_id: int, feedback: FeedbackInput):
        task = self.database.get_task(task_id)
        self.database.create_feedback_event(task_id, feedback)
        self.database.transition_task_status(task_id, feedback.status)

        recent_statuses = self.database.get_recent_feedback_statuses(task_id)
        context = FeedbackContext(
            estimated_minutes=task["estimated_minutes"],
            recent_statuses=recent_statuses,
            friction_points_in_milestone=sum(
                1
                for status in recent_statuses
                if status in {TaskStatus.DELAYED, TaskStatus.BLOCKED, TaskStatus.FAILED}
            ),
        )
        outcome = self.feedback_policy.evaluate(feedback, context)
        self.database.create_policy_decision(task["plan_version_id"], task_id, outcome)

        if outcome.action in {PolicyAction.REQUEST_REVIEW, PolicyAction.PROPOSE_REPLAN}:
            plan_version = self.database.get_plan_version(task["plan_version_id"])
            if PlanStatus(plan_version["status"]) == PlanStatus.ACTIVE:
                self.database.transition_plan_status(task["plan_version_id"], PlanStatus.REVIEW_NEEDED)

        return outcome

    def generate_replan_proposal(
        self,
        plan_version_id: int,
        trigger_task_id: int | None,
        trigger_reason: str,
    ) -> int:
        snapshot_data = self.database.get_plan_snapshot_data(plan_version_id)
        snapshot = PlanSnapshot(
            goal_id=snapshot_data["goal"]["id"],
            plan_version_id=plan_version_id,
            goal_title=snapshot_data["goal"]["title"],
            goal_description=snapshot_data["goal"]["description"],
            target_start_date=date.fromisoformat(snapshot_data["goal"]["target_start_date"]),
            target_end_date=date.fromisoformat(snapshot_data["goal"]["target_end_date"]),
            tasks=snapshot_data["tasks"],
            dependencies=snapshot_data["dependencies"],
        )
        request = ReplanRequest(
            snapshot=snapshot,
            trigger_task_id=trigger_task_id,
            trigger_reason=trigger_reason,
        )
        proposal = self.planner.replan(request)
        new_plan_version_id = self.database.save_plan_proposal(
            snapshot.goal_id,
            proposal,
            status=PlanStatus.REPLAN_PROPOSED,
        )
        self.database.create_proposal(
            plan_version_id,
            ProposalKind.REPLAN,
            trigger_reason,
            {"new_plan_version_id": new_plan_version_id},
        )
        return new_plan_version_id

    def apply_replan(self, new_plan_version_id: int) -> ScheduleResult:
        return self.approve_and_schedule(new_plan_version_id)

    def apply_replan_proposal(self, proposal_id: int) -> ScheduleResult:
        proposal = self.database.get_proposal(proposal_id)
        if proposal["proposal_type"] != ProposalKind.REPLAN.value:
            raise ValueError("proposal is not a replan proposal")
        new_plan_version_id = proposal["payload"].get("new_plan_version_id")
        if not new_plan_version_id:
            raise ValueError("replan proposal does not include a target plan version")
        result = self.apply_replan(int(new_plan_version_id))
        self.database.update_proposal_status(proposal_id, ProposalStatus.APPLIED)
        return result

    def apply_rebalance(self, proposal_id: int) -> ScheduleResult:
        proposal = self.database.get_proposal(proposal_id)
        if proposal["proposal_type"] != ProposalKind.REBALANCE.value:
            raise ValueError("proposal is not a rebalance proposal")
        suggested_end_date = proposal["payload"].get("suggested_target_end_date")
        if not suggested_end_date:
            raise ValueError("rebalance proposal does not include a suggested target end date")

        plan_version = self.database.get_plan_version(proposal["plan_version_id"])
        goal_id = plan_version["goal_id"]
        self.database.update_goal_dates(goal_id, target_end_date=date.fromisoformat(suggested_end_date))
        result = self._schedule_plan(proposal["plan_version_id"])
        self.database.update_proposal_status(proposal_id, ProposalStatus.APPLIED)
        return result

    def reject_proposal(self, proposal_id: int) -> None:
        self.database.update_proposal_status(proposal_id, ProposalStatus.REJECTED)

    def revert_plan(self, plan_version_id: int) -> tuple[int, ScheduleResult]:
        plan_version = self.database.get_plan_version(plan_version_id)
        if PlanStatus(plan_version["status"]) == PlanStatus.SUPERSEDED:
            target_plan_version_id = plan_version_id
        else:
            target_plan_version_id = self.database.find_previous_plan_version_id(plan_version_id)
            if target_plan_version_id is None:
                raise ValueError("no previous plan version is available to restore")

        result = self._schedule_plan(target_plan_version_id)
        return target_plan_version_id, result

    def edit_task(
        self,
        task_id: int,
        *,
        title: str | None = None,
        estimated_minutes: int | None = None,
        target_date: date | None = None,
    ) -> dict:
        updated_task = self.database.edit_task(
            task_id,
            title=title,
            estimated_minutes=estimated_minutes,
            target_date=target_date,
        )
        plan_version = self.database.get_plan_version(updated_task["plan_version_id"])
        if PlanStatus(plan_version["status"]) == PlanStatus.ACTIVE:
            self.database.transition_plan_status(updated_task["plan_version_id"], PlanStatus.REVIEW_NEEDED)
        return updated_task

    def _suggest_target_end_date(
        self,
        *,
        tasks,
        dependencies,
        availability,
        existing_blocks,
        schedule_start: date,
        current_end_date: date,
        max_extension_days: int,
    ) -> date | None:
        for extra_days in range(1, max_extension_days + 1):
            candidate_end = current_end_date + timedelta(days=extra_days)
            candidate_result = self.scheduler.schedule(
                tasks=tasks,
                dependencies=dependencies,
                availability=availability,
                schedule_start=schedule_start,
                schedule_end=candidate_end,
                existing_blocks=existing_blocks,
            )
            if not candidate_result.conflicts:
                return candidate_end
        return None

    def _build_reminders(self, plan_version_id, blocks, schedule_block_ids):
        reminders = []
        for schedule_block_id, block in zip(schedule_block_ids, blocks, strict=True):
            remind_at = block.start_at - timedelta(minutes=15)
            if remind_at < datetime.now():
                remind_at = block.start_at
            reminders.append(
                {
                    "plan_version_id": plan_version_id,
                    "schedule_block_id": schedule_block_id,
                    "task_id": block.task_id,
                    "reminder_type": "upcoming_task",
                    "remind_at": remind_at,
                }
            )
        return reminders
