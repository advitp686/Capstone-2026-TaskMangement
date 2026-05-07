from __future__ import annotations

from abc import ABC, abstractmethod

from .domain import PlanProposal, PlanningRequest, ReplanRequest, TaskProposal, TaskStatus


class PlannerBackend(ABC):
    @abstractmethod
    def create_plan(self, request: PlanningRequest) -> PlanProposal:
        raise NotImplementedError

    @abstractmethod
    def replan(self, request: ReplanRequest) -> PlanProposal:
        raise NotImplementedError


class MockPlannerBackend(PlannerBackend):
    def create_plan(self, request: PlanningRequest) -> PlanProposal:
        duration_days = max(
            1,
            (request.goal.target_end_date - request.goal.target_start_date).days + 1,
        )
        base_minutes = max(90, (duration_days * 60) // 4)
        goal_text = f"{request.goal.title} {request.goal.description}".lower()

        if "learn" in goal_text or "study" in goal_text or "exam" in goal_text:
            task_templates = [
                ("scope", "Define the learning scope and gather the core resources."),
                ("concepts", "Study the core concepts in a structured sequence."),
                ("practice", "Practice the concepts and identify weak areas."),
                ("review", "Review mistakes, revise weak areas, and consolidate."),
            ]
        else:
            task_templates = [
                ("scope", "Clarify the desired outcome, inputs, and constraints."),
                ("setup", "Prepare resources and unblock prerequisites."),
                ("execute", "Do the core execution work in focused sessions."),
                ("review", "Review progress, refine work, and close gaps."),
            ]

        tasks: list[TaskProposal] = []
        previous_key: str | None = None
        for index, (key, summary) in enumerate(task_templates, start=1):
            task_key = f"{key}-{index}"
            tasks.append(
                TaskProposal(
                    key=task_key,
                    title=self._task_title(request.goal.title, summary),
                    summary=summary,
                    estimated_minutes=base_minutes,
                    depends_on_keys=[previous_key] if previous_key else [],
                )
            )
            previous_key = task_key

        return PlanProposal(
            title=request.goal.title,
            summary=f"Structured draft plan for: {request.goal.title}",
            rationale="The mock planner decomposed the goal into a small sequence of phases. "
            "A real SLM backend will later replace this deterministic scaffold.",
            tasks=tasks,
        )

    def replan(self, request: ReplanRequest) -> PlanProposal:
        blocked_task = next(
            (task for task in request.snapshot.tasks if task["id"] == request.trigger_task_id),
            None,
        )
        pending_tasks = [
            task
            for task in request.snapshot.tasks
            if task["status"] not in {TaskStatus.DONE.value, TaskStatus.CANCELED.value}
        ]

        tasks: list[TaskProposal] = []
        recovery_key = "recovery-1"
        if blocked_task is not None:
            tasks.append(
                TaskProposal(
                    key=recovery_key,
                    title=f"Resolve blocker for {blocked_task['title']}",
                    summary=request.trigger_reason,
                    estimated_minutes=max(45, blocked_task["estimated_minutes"] // 2),
                )
            )

        previous_key = recovery_key if tasks else None
        for index, task in enumerate(pending_tasks, start=1):
            new_key = f"carry-{index}"
            tasks.append(
                TaskProposal(
                    key=new_key,
                    title=task["title"],
                    summary=task["summary"],
                    estimated_minutes=task["estimated_minutes"],
                    depends_on_keys=[previous_key] if previous_key else [],
                )
            )
            previous_key = new_key

        return PlanProposal(
            title=f"{request.snapshot.goal_title} (Replan)",
            summary="Revised plan proposal after execution friction.",
            rationale="The mock replanner inserted a recovery step before the remaining work so the "
            "system can recover from the reported blocker before continuing.",
            tasks=tasks,
        )

    def _task_title(self, goal_title: str, summary: str) -> str:
        prefix = goal_title[:40].strip()
        return f"{prefix}: {summary.split('.')[0]}"
