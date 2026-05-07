from __future__ import annotations

from dataclasses import dataclass, field

from .domain import FeedbackInput, PolicyAction, PolicyOutcome, TaskStatus


@dataclass(slots=True)
class FeedbackContext:
    estimated_minutes: int
    recent_statuses: list[TaskStatus] = field(default_factory=list)
    friction_points_in_milestone: int = 0
    dependency_critical: bool = False


class FeedbackPolicy:
    def evaluate(self, feedback: FeedbackInput, context: FeedbackContext) -> PolicyOutcome:
        if feedback.status in {TaskStatus.BLOCKED, TaskStatus.FAILED}:
            return PolicyOutcome(
                action=PolicyAction.PROPOSE_REPLAN,
                reason="A critical task is blocked or failed, so the plan should be reviewed.",
                requires_user_confirmation=True,
                details={"friction_points": context.friction_points_in_milestone},
            )

        repeated_delays = context.recent_statuses.count(TaskStatus.DELAYED)
        is_large_overrun = (
            feedback.actual_minutes is not None
            and context.estimated_minutes > 0
            and feedback.actual_minutes > int(context.estimated_minutes * 1.5)
        )
        low_confidence = feedback.confidence is not None and feedback.confidence < 0.35

        if feedback.status == TaskStatus.DELAYED and (repeated_delays >= 1 or context.dependency_critical):
            return PolicyOutcome(
                action=PolicyAction.REQUEST_REVIEW,
                reason="Repeated delay on a sensitive task should trigger a plan review.",
                requires_user_confirmation=False,
            )

        if is_large_overrun or low_confidence or context.friction_points_in_milestone >= 2:
            return PolicyOutcome(
                action=PolicyAction.REQUEST_FEEDBACK,
                reason="Execution friction increased, so the system should ask for more feedback.",
                requires_user_confirmation=False,
            )

        return PolicyOutcome(
            action=PolicyAction.NONE,
            reason="No plan change is needed yet.",
            requires_user_confirmation=False,
        )

    def should_request_checkpoint(
        self,
        completed_since_last_feedback: int,
        high_complexity: bool,
        friction_points: int,
    ) -> bool:
        if friction_points >= 2:
            return True
        if high_complexity:
            return completed_since_last_feedback >= 2
        return completed_since_last_feedback >= 4
