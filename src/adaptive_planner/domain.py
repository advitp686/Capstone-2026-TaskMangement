from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Any


class PlanStatus(str, Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    REVIEW_NEEDED = "review_needed"
    REPLAN_PROPOSED = "replan_proposed"
    SUPERSEDED = "superseded"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class TaskStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DELAYED = "delayed"
    BLOCKED = "blocked"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELED = "canceled"


class PolicyAction(str, Enum):
    NONE = "none"
    REQUEST_FEEDBACK = "request_feedback"
    SHIFT_SCHEDULE = "shift_schedule"
    REQUEST_REVIEW = "request_review"
    PROPOSE_REPLAN = "propose_replan"


class ProposalKind(str, Enum):
    REBALANCE = "rebalance"
    REPLAN = "replan"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


class ReminderStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    CANCELED = "canceled"


@dataclass(slots=True)
class AvailabilityWindow:
    weekday: int
    start_time: time
    end_time: time


@dataclass(slots=True)
class GoalInput:
    title: str
    description: str
    target_start_date: date
    target_end_date: date
    availability: list[AvailabilityWindow] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskProposal:
    key: str
    title: str
    summary: str
    estimated_minutes: int
    difficulty: str = "medium"
    depends_on_keys: list[str] = field(default_factory=list)
    target_date: date | None = None


@dataclass(slots=True)
class PlanProposal:
    title: str
    summary: str
    rationale: str
    tasks: list[TaskProposal]


@dataclass(slots=True)
class FeedbackInput:
    status: TaskStatus
    actual_minutes: int | None = None
    difficulty: int | None = None
    confidence: float | None = None
    note: str = ""
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class PolicyOutcome:
    action: PolicyAction
    reason: str
    requires_user_confirmation: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlanningRequest:
    goal: GoalInput
    active_plan_context: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class PlanSnapshot:
    goal_id: int
    plan_version_id: int
    goal_title: str
    goal_description: str
    target_start_date: date
    target_end_date: date
    tasks: list[dict[str, Any]]
    dependencies: list[tuple[int, int]]


@dataclass(slots=True)
class ReplanRequest:
    snapshot: PlanSnapshot
    trigger_task_id: int | None
    trigger_reason: str
