from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel, Field


PlannerMode = Literal["mock", "gemma"]
ReferenceKind = Literal["markdown", "text"]


class AvailabilityWindowModel(BaseModel):
    weekday: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time


class ReferenceInput(BaseModel):
    filename: str
    kind: ReferenceKind
    content: str


class ClarificationQuestion(BaseModel):
    id: str
    prompt: str
    recommended_option: str
    options: list[str]
    allow_custom: bool = True


class SearchResultResponse(BaseModel):
    title: str
    url: str
    content: str


class AssistantIntakeRequest(BaseModel):
    title: str
    description: str
    target_start_date: date
    target_end_date: date
    availability: list[AvailabilityWindowModel]
    references: list[ReferenceInput] = Field(default_factory=list)
    clarification_answers: dict[str, str] = Field(default_factory=dict)
    use_web_search: bool = True


class AssistantIntakeResponse(BaseModel):
    requires_clarification: bool
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    readiness_summary: str
    assistant_summary: str
    references_summary: str = ""
    web_search_used: bool = False
    web_search_available: bool = False
    web_search_message: str = ""
    search_results: list[SearchResultResponse] = Field(default_factory=list)


class SuggestedAction(BaseModel):
    action: str
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AssistantMessageRequest(BaseModel):
    message: str


class AssistantMessageResponse(BaseModel):
    reply: str
    updated_summary: str
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)


class CreatePlanRequest(BaseModel):
    title: str
    description: str
    target_start_date: date
    target_end_date: date
    availability: list[AvailabilityWindowModel]
    constraints: dict[str, Any] = Field(default_factory=dict)
    planner: PlannerMode = "mock"
    auto_approve: bool = False
    references: list[ReferenceInput] = Field(default_factory=list)
    clarification_answers: dict[str, str] = Field(default_factory=dict)
    assistant_summary: str | None = None


class EditTaskRequest(BaseModel):
    title: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)
    target_date: date | None = None
    regenerate_schedule: bool = True


class FeedbackRequest(BaseModel):
    status: str
    actual_minutes: int | None = Field(default=None, ge=1)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    note: str = ""


class DeliverRemindersRequest(BaseModel):
    as_of: datetime | None = None
    limit: int | None = Field(default=None, ge=1)


class ApplyProposalRequest(BaseModel):
    action: Literal["apply", "reject"] = "apply"


class GenerateReplanRequest(BaseModel):
    planner: PlannerMode = "mock"
    trigger_task_id: int | None = None
    trigger_reason: str


class PlanSummaryResponse(BaseModel):
    goal_id: int
    plan_version_id: int
    status: str
    title: str
    summary: str
    rationale: str
    goal_title: str
    goal_description: str
    target_start_date: date
    target_end_date: date


class TaskResponse(BaseModel):
    id: int
    plan_version_id: int
    task_key: str
    position: int
    title: str
    summary: str
    estimated_minutes: int
    difficulty: str
    target_date: date | None
    status: str


class ScheduleBlockResponse(BaseModel):
    id: int
    plan_version_id: int
    task_id: int
    start_at: datetime
    end_at: datetime
    status: str


class ReminderResponse(BaseModel):
    id: int
    plan_version_id: int
    schedule_block_id: int | None
    task_id: int
    reminder_type: str
    remind_at: datetime
    status: str
    delivered_at: datetime | None


class ProposalResponse(BaseModel):
    id: int
    plan_version_id: int
    proposal_type: str
    status: str
    reason: str
    payload: dict[str, Any]
    created_at: datetime


class PolicyDecisionResponse(BaseModel):
    id: int
    plan_version_id: int
    task_id: int | None
    action: str
    reason: str
    requires_confirmation: int
    details: dict[str, Any]
    created_at: datetime


class PlanDetailResponse(BaseModel):
    plan: PlanSummaryResponse
    tasks: list[TaskResponse]
    dependencies: list[tuple[int, int]]
    schedule_blocks: list[ScheduleBlockResponse]
    reminders: list[ReminderResponse]
    proposals: list[ProposalResponse]
    policy_decisions: list[PolicyDecisionResponse]


class CreatePlanResponse(BaseModel):
    goal_id: int
    plan_version_id: int
    status: str
    scheduled_blocks: int = 0
    conflicts: int = 0


class ScheduleActionResponse(BaseModel):
    plan_version_id: int
    status: str
    scheduled_blocks: int
    conflicts: list[dict[str, Any]]


class FeedbackResponse(BaseModel):
    task_id: int
    action: str
    reason: str
    requires_user_confirmation: bool
    details: dict[str, Any]
    assistant_review: dict[str, Any] | None = None


class DeliverRemindersResponse(BaseModel):
    delivered_count: int
    reminders: list[dict[str, Any]]


class PlanReferenceResponse(BaseModel):
    id: int
    filename: str
    kind: ReferenceKind
    content_preview: str
    created_at: datetime


class PlanVersionHistoryItem(BaseModel):
    plan_version_id: int
    version_number: int
    status: str
    title: str
    summary: str
    created_at: datetime


class PlanHistoryResponse(BaseModel):
    goal_id: int
    active_plan_version_id: int | None
    current_plan_version_id: int
    revert_target_plan_version_id: int | None
    revert_eligible: bool
    versions: list[PlanVersionHistoryItem]
