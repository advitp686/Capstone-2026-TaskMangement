from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .storage import PlannerDatabase


@dataclass(slots=True)
class DeliveredReminder:
    reminder_id: int
    task_id: int
    task_title: str
    reminder_type: str
    remind_at: str


class ReminderService:
    def __init__(self, database: PlannerDatabase) -> None:
        self.database = database

    def get_due_reminders(self, as_of: datetime, *, limit: int | None = None) -> list[dict]:
        return self.database.get_due_reminders(as_of, limit=limit)

    def deliver_due_reminders(
        self,
        as_of: datetime,
        *,
        limit: int | None = None,
    ) -> list[DeliveredReminder]:
        reminders = self.database.get_due_reminders(as_of, limit=limit)
        delivered: list[DeliveredReminder] = []
        for reminder in reminders:
            self.database.mark_reminder_delivered(reminder["id"], delivered_at=as_of)
            delivered.append(
                DeliveredReminder(
                    reminder_id=reminder["id"],
                    task_id=reminder["task_id"],
                    task_title=reminder["task_title"],
                    reminder_type=reminder["reminder_type"],
                    remind_at=reminder["remind_at"],
                )
            )
        return delivered
