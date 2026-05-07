from __future__ import annotations

from .domain import PlanStatus, TaskStatus


PLAN_TRANSITIONS: dict[PlanStatus, set[PlanStatus]] = {
    PlanStatus.DRAFT: {PlanStatus.PROPOSED, PlanStatus.ABANDONED},
    PlanStatus.PROPOSED: {PlanStatus.APPROVED, PlanStatus.ABANDONED},
    PlanStatus.APPROVED: {
        PlanStatus.ACTIVE,
        PlanStatus.REVIEW_NEEDED,
        PlanStatus.ABANDONED,
        PlanStatus.SUPERSEDED,
    },
    PlanStatus.ACTIVE: {
        PlanStatus.REVIEW_NEEDED,
        PlanStatus.COMPLETED,
        PlanStatus.ABANDONED,
        PlanStatus.SUPERSEDED,
    },
    PlanStatus.REVIEW_NEEDED: {
        PlanStatus.ACTIVE,
        PlanStatus.REPLAN_PROPOSED,
        PlanStatus.ABANDONED,
        PlanStatus.SUPERSEDED,
    },
    PlanStatus.REPLAN_PROPOSED: {
        PlanStatus.APPROVED,
        PlanStatus.ABANDONED,
        PlanStatus.SUPERSEDED,
    },
    PlanStatus.SUPERSEDED: set(),
    PlanStatus.COMPLETED: set(),
    PlanStatus.ABANDONED: set(),
}


TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {
        TaskStatus.SCHEDULED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.DONE,
        TaskStatus.DELAYED,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.SKIPPED,
        TaskStatus.CANCELED,
    },
    TaskStatus.SCHEDULED: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.DONE,
        TaskStatus.DELAYED,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.SKIPPED,
        TaskStatus.CANCELED,
    },
    TaskStatus.IN_PROGRESS: {
        TaskStatus.DONE,
        TaskStatus.DELAYED,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELED,
    },
    TaskStatus.DONE: set(),
    TaskStatus.DELAYED: {
        TaskStatus.SCHEDULED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.CANCELED,
    },
    TaskStatus.BLOCKED: {
        TaskStatus.SCHEDULED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.FAILED,
        TaskStatus.CANCELED,
    },
    TaskStatus.FAILED: {TaskStatus.CANCELED},
    TaskStatus.SKIPPED: set(),
    TaskStatus.CANCELED: set(),
}


def ensure_plan_transition(current: PlanStatus, new: PlanStatus) -> None:
    if current == new:
        return
    allowed = PLAN_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ValueError(f"invalid plan transition: {current.value} -> {new.value}")


def ensure_task_transition(current: TaskStatus, new: TaskStatus) -> None:
    if current == new:
        return
    allowed = TASK_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ValueError(f"invalid task transition: {current.value} -> {new.value}")
