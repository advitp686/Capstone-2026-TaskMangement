from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from .domain import (
    AvailabilityWindow,
    FeedbackInput,
    GoalInput,
    PlanProposal,
    PlanStatus,
    PolicyOutcome,
    ProposalKind,
    ProposalStatus,
    ReminderStatus,
    TaskStatus,
)
from .schema import create_schema
from .scheduler import ScheduledBlock
from .state_machine import ensure_plan_transition, ensure_task_transition


class PlannerDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            create_schema(connection)

    def create_goal(self, goal: GoalInput) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO goals (title, description, target_start_date, target_end_date, constraints_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    goal.title,
                    goal.description,
                    goal.target_start_date.isoformat(),
                    goal.target_end_date.isoformat(),
                    self._json(goal.constraints),
                    datetime.now().isoformat(),
                ),
            )
            goal_id = int(cursor.lastrowid)
            self._replace_availability(connection, goal_id, goal.availability)
            return goal_id

    def save_plan_proposal(
        self,
        goal_id: int,
        proposal: PlanProposal,
        status: PlanStatus = PlanStatus.PROPOSED,
    ) -> int:
        with self._connect() as connection:
            version_number = self._next_version_number(connection, goal_id)
            cursor = connection.execute(
                """
                INSERT INTO plan_versions (goal_id, version_number, status, title, summary, rationale, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    goal_id,
                    version_number,
                    status.value,
                    proposal.title,
                    proposal.summary,
                    proposal.rationale,
                    datetime.now().isoformat(),
                ),
            )
            plan_version_id = int(cursor.lastrowid)

            task_id_by_key: dict[str, int] = {}
            for position, task in enumerate(proposal.tasks, start=1):
                task_cursor = connection.execute(
                    """
                    INSERT INTO tasks (
                        plan_version_id, task_key, position, title, summary, estimated_minutes,
                        difficulty, target_date, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_version_id,
                        task.key,
                        position,
                        task.title,
                        task.summary,
                        task.estimated_minutes,
                        task.difficulty,
                        task.target_date.isoformat() if task.target_date else None,
                        TaskStatus.PENDING.value,
                    ),
                )
                task_id_by_key[task.key] = int(task_cursor.lastrowid)

            for task in proposal.tasks:
                successor_id = task_id_by_key[task.key]
                for predecessor_key in task.depends_on_keys:
                    connection.execute(
                        """
                        INSERT INTO dependencies (plan_version_id, predecessor_task_id, successor_task_id)
                        VALUES (?, ?, ?)
                        """,
                        (plan_version_id, task_id_by_key[predecessor_key], successor_id),
                    )

            return plan_version_id

    def get_goal(self, goal_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
            if row is None:
                raise KeyError(f"goal {goal_id} not found")
            return dict(row)

    def update_goal_dates(
        self,
        goal_id: int,
        *,
        target_start_date: date | None = None,
        target_end_date: date | None = None,
    ) -> None:
        updates: dict[str, str] = {}
        if target_start_date is not None:
            updates["target_start_date"] = target_start_date.isoformat()
        if target_end_date is not None:
            updates["target_end_date"] = target_end_date.isoformat()
        if not updates:
            return

        with self._connect() as connection:
            set_clause = ", ".join(f"{field_name} = ?" for field_name in updates)
            connection.execute(
                f"UPDATE goals SET {set_clause} WHERE id = ?",
                (*updates.values(), goal_id),
            )

    def get_plan_version(self, plan_version_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM plan_versions WHERE id = ?",
                (plan_version_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"plan version {plan_version_id} not found")
            return dict(row)

    def list_plan_versions(self, status: PlanStatus | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM plan_versions ORDER BY created_at, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM plan_versions WHERE status = ? ORDER BY created_at, id",
                    (status.value,),
                ).fetchall()
            return [dict(row) for row in rows]

    def list_plan_versions_for_goal(self, goal_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM plan_versions
                WHERE goal_id = ?
                ORDER BY version_number, id
                """,
                (goal_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def find_previous_plan_version_id(self, plan_version_id: int) -> int | None:
        current = self.get_plan_version(plan_version_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM plan_versions
                WHERE goal_id = ?
                  AND version_number < ?
                  AND status = ?
                ORDER BY version_number DESC, id DESC
                LIMIT 1
                """,
                (
                    current["goal_id"],
                    current["version_number"],
                    PlanStatus.SUPERSEDED.value,
                ),
            ).fetchone()
            return int(row["id"]) if row is not None else None

    def list_tasks(self, plan_version_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks WHERE plan_version_id = ? ORDER BY position",
                (plan_version_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_task(self, task_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"task {task_id} not found")
            return dict(row)

    def list_dependencies(self, plan_version_id: int) -> list[tuple[int, int]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT predecessor_task_id, successor_task_id
                FROM dependencies
                WHERE plan_version_id = ?
                ORDER BY predecessor_task_id, successor_task_id
                """,
                (plan_version_id,),
            ).fetchall()
            return [(row["predecessor_task_id"], row["successor_task_id"]) for row in rows]

    def list_availability(self, goal_id: int) -> list[AvailabilityWindow]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT weekday, start_time, end_time
                FROM availability_windows
                WHERE goal_id = ?
                ORDER BY weekday, start_time
                """,
                (goal_id,),
            ).fetchall()
            return [
                AvailabilityWindow(
                    weekday=row["weekday"],
                    start_time=time.fromisoformat(row["start_time"]),
                    end_time=time.fromisoformat(row["end_time"]),
                )
                for row in rows
            ]

    def list_active_schedule_blocks(self, exclude_goal_id: int | None = None) -> list[ScheduledBlock]:
        with self._connect() as connection:
            if exclude_goal_id is None:
                rows = connection.execute(
                    """
                    SELECT sb.task_id, sb.start_at, sb.end_at
                    FROM schedule_blocks sb
                    JOIN plan_versions pv ON pv.id = sb.plan_version_id
                    WHERE pv.status = ?
                    """,
                    (PlanStatus.ACTIVE.value,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT sb.task_id, sb.start_at, sb.end_at
                    FROM schedule_blocks sb
                    JOIN plan_versions pv ON pv.id = sb.plan_version_id
                    WHERE pv.status = ? AND pv.goal_id != ?
                    """,
                    (PlanStatus.ACTIVE.value, exclude_goal_id),
                ).fetchall()
            return [
                ScheduledBlock(
                    task_id=row["task_id"],
                    start_at=datetime.fromisoformat(row["start_at"]),
                    end_at=datetime.fromisoformat(row["end_at"]),
                )
                for row in rows
            ]

    def list_schedule_blocks(self, plan_version_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM schedule_blocks
                WHERE plan_version_id = ?
                ORDER BY start_at
                """,
                (plan_version_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_active_plan_context(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    pv.id AS plan_version_id,
                    pv.goal_id AS goal_id,
                    pv.title AS plan_title,
                    pv.summary AS plan_summary,
                    g.target_start_date AS target_start_date,
                    g.target_end_date AS target_end_date
                FROM plan_versions pv
                JOIN goals g ON g.id = pv.goal_id
                WHERE pv.status = ?
                ORDER BY pv.id
                """,
                (PlanStatus.ACTIVE.value,),
            ).fetchall()

            context: list[dict[str, Any]] = []
            for row in rows:
                tasks = connection.execute(
                    """
                    SELECT id, title, status, estimated_minutes, target_date
                    FROM tasks
                    WHERE plan_version_id = ?
                    ORDER BY position
                    """,
                    (row["plan_version_id"],),
                ).fetchall()
                blocks = connection.execute(
                    """
                    SELECT task_id, start_at, end_at
                    FROM schedule_blocks
                    WHERE plan_version_id = ?
                    ORDER BY start_at
                    """,
                    (row["plan_version_id"],),
                ).fetchall()
                context.append(
                    {
                        "plan_version_id": row["plan_version_id"],
                        "goal_id": row["goal_id"],
                        "title": row["plan_title"],
                        "summary": row["plan_summary"],
                        "target_start_date": row["target_start_date"],
                        "target_end_date": row["target_end_date"],
                        "tasks": [dict(task) for task in tasks],
                        "schedule_blocks": [dict(block) for block in blocks],
                    }
                )
            return context

    def list_reminders(self, plan_version_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reminders WHERE plan_version_id = ? ORDER BY remind_at",
                (plan_version_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def create_plan_references(
        self,
        goal_id: int,
        plan_version_id: int | None,
        references: list[dict[str, Any]],
    ) -> None:
        if not references:
            return
        with self._connect() as connection:
            for reference in references:
                filename = str(reference.get("filename") or "reference.txt").strip() or "reference.txt"
                kind = str(reference.get("kind") or "text").strip().lower()
                if kind not in {"markdown", "text"}:
                    kind = "text"
                content = str(reference.get("content") or "")
                if not content.strip():
                    continue
                connection.execute(
                    """
                    INSERT INTO plan_references (goal_id, plan_version_id, filename, kind, content, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        goal_id,
                        plan_version_id,
                        filename[:240],
                        kind,
                        content,
                        datetime.now().isoformat(),
                    ),
                )

    def list_plan_references(self, plan_version_id: int) -> list[dict[str, Any]]:
        plan = self.get_plan_version(plan_version_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM plan_references
                WHERE plan_version_id = ? OR goal_id = ?
                ORDER BY created_at, id
                """,
                (plan_version_id, plan["goal_id"]),
            ).fetchall()
            return [dict(row) for row in rows]

    def upsert_assistant_summary(self, plan_version_id: int, summary: str) -> None:
        cleaned = summary.strip()
        if not cleaned:
            return
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO assistant_summaries (plan_version_id, summary, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(plan_version_id) DO UPDATE SET
                    summary = excluded.summary,
                    updated_at = excluded.updated_at
                """,
                (plan_version_id, cleaned, datetime.now().isoformat()),
            )

    def get_assistant_summary(self, plan_version_id: int) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT summary FROM assistant_summaries WHERE plan_version_id = ?",
                (plan_version_id,),
            ).fetchone()
            return str(row["summary"]) if row is not None else ""

    def get_due_reminders(
        self,
        as_of: datetime,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            sql = """
                SELECT r.*, t.title AS task_title
                FROM reminders r
                JOIN tasks t ON t.id = r.task_id
                WHERE r.status = ? AND r.remind_at <= ?
                ORDER BY r.remind_at
            """
            params: list[Any] = [ReminderStatus.PENDING.value, as_of.isoformat()]
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
            rows = connection.execute(sql, tuple(params)).fetchall()
            return [dict(row) for row in rows]

    def mark_reminder_delivered(
        self,
        reminder_id: int,
        *,
        delivered_at: datetime | None = None,
    ) -> None:
        delivered_at = delivered_at or datetime.now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE reminders
                SET status = ?, delivered_at = ?
                WHERE id = ?
                """,
                (ReminderStatus.DELIVERED.value, delivered_at.isoformat(), reminder_id),
            )

    def replace_schedule(self, plan_version_id: int, blocks: list[ScheduledBlock]) -> list[int]:
        with self._connect() as connection:
            connection.execute("DELETE FROM reminders WHERE plan_version_id = ?", (plan_version_id,))
            connection.execute("DELETE FROM schedule_blocks WHERE plan_version_id = ?", (plan_version_id,))
            created_ids: list[int] = []
            current_status_rows = connection.execute(
                "SELECT id, status FROM tasks WHERE plan_version_id = ?",
                (plan_version_id,),
            ).fetchall()
            current_statuses = {
                row["id"]: TaskStatus(row["status"])
                for row in current_status_rows
            }
            for block in blocks:
                cursor = connection.execute(
                    """
                    INSERT INTO schedule_blocks (plan_version_id, task_id, start_at, end_at, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        plan_version_id,
                        block.task_id,
                        block.start_at.isoformat(),
                        block.end_at.isoformat(),
                        TaskStatus.SCHEDULED.value,
                    ),
                )
                created_ids.append(int(cursor.lastrowid))
                if current_statuses.get(block.task_id) == TaskStatus.PENDING:
                    self._transition_task_status(connection, block.task_id, TaskStatus.SCHEDULED)
            return created_ids

    def create_reminders(self, reminders: list[dict[str, Any]]) -> None:
        with self._connect() as connection:
            for reminder in reminders:
                connection.execute(
                    """
                    INSERT INTO reminders (plan_version_id, schedule_block_id, task_id, reminder_type, remind_at, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        reminder["plan_version_id"],
                        reminder["schedule_block_id"],
                        reminder["task_id"],
                        reminder["reminder_type"],
                        reminder["remind_at"].isoformat(),
                        ReminderStatus.PENDING.value,
                    ),
                )

    def transition_plan_status(self, plan_version_id: int, new_status: PlanStatus) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM plan_versions WHERE id = ?",
                (plan_version_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"plan version {plan_version_id} not found")
            current = PlanStatus(row["status"])
            ensure_plan_transition(current, new_status)
            connection.execute(
                "UPDATE plan_versions SET status = ? WHERE id = ?",
                (new_status.value, plan_version_id),
            )

    def activate_plan(self, plan_version_id: int) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT goal_id, status FROM plan_versions WHERE id = ?",
                (plan_version_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"plan version {plan_version_id} not found")
            current_status = PlanStatus(row["status"])
            goal_id = row["goal_id"]
            if current_status != PlanStatus.ACTIVE:
                if current_status in {PlanStatus.PROPOSED, PlanStatus.REPLAN_PROPOSED}:
                    ensure_plan_transition(current_status, PlanStatus.APPROVED)
                    connection.execute(
                        "UPDATE plan_versions SET status = ? WHERE id = ?",
                        (PlanStatus.APPROVED.value, plan_version_id),
                    )
                    current_status = PlanStatus.APPROVED
                ensure_plan_transition(current_status, PlanStatus.ACTIVE)
                connection.execute(
                    """
                    UPDATE plan_versions
                    SET status = ?
                    WHERE goal_id = ? AND id != ? AND status IN (?, ?, ?, ?)
                    """,
                    (
                        PlanStatus.SUPERSEDED.value,
                        goal_id,
                        plan_version_id,
                        PlanStatus.ACTIVE.value,
                        PlanStatus.APPROVED.value,
                        PlanStatus.REVIEW_NEEDED.value,
                        PlanStatus.REPLAN_PROPOSED.value,
                    ),
                )
                connection.execute(
                    "UPDATE plan_versions SET status = ? WHERE id = ?",
                    (PlanStatus.ACTIVE.value, plan_version_id),
                )

    def transition_task_status(self, task_id: int, new_status: TaskStatus) -> None:
        with self._connect() as connection:
            self._transition_task_status(connection, task_id, new_status)

    def create_feedback_event(self, task_id: int, feedback: FeedbackInput) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO feedback_events (task_id, status, actual_minutes, difficulty, confidence, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    feedback.status.value,
                    feedback.actual_minutes,
                    feedback.difficulty,
                    feedback.confidence,
                    feedback.note,
                    feedback.occurred_at.isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def get_recent_feedback_statuses(self, task_id: int, limit: int = 5) -> list[TaskStatus]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status
                FROM feedback_events
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (task_id, limit),
            ).fetchall()
            return [TaskStatus(row["status"]) for row in rows]

    def create_policy_decision(
        self,
        plan_version_id: int,
        task_id: int | None,
        outcome: PolicyOutcome,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO policy_decisions (plan_version_id, task_id, action, reason, requires_confirmation, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_version_id,
                    task_id,
                    outcome.action.value,
                    outcome.reason,
                    int(outcome.requires_user_confirmation),
                    self._json(outcome.details),
                    datetime.now().isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def create_proposal(
        self,
        plan_version_id: int,
        proposal_type: ProposalKind,
        reason: str,
        payload: dict[str, Any],
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO proposals (plan_version_id, proposal_type, reason, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    plan_version_id,
                    proposal_type.value,
                    reason,
                    self._json(payload),
                    datetime.now().isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def get_proposal(self, proposal_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
            if row is None:
                raise KeyError(f"proposal {proposal_id} not found")
            data = dict(row)
            data["payload"] = json.loads(data.pop("payload_json"))
            return data

    def list_proposals(
        self,
        *,
        plan_version_id: int | None = None,
        proposal_type: ProposalKind | None = None,
        status: ProposalStatus | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if plan_version_id is not None:
            clauses.append("plan_version_id = ?")
            params.append(plan_version_id)
        if proposal_type is not None:
            clauses.append("proposal_type = ?")
            params.append(proposal_type.value)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)

        sql = "SELECT * FROM proposals"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at"

        with self._connect() as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                data = dict(row)
                data["payload"] = json.loads(data.pop("payload_json"))
                result.append(data)
            return result

    def update_proposal_status(self, proposal_id: int, status: ProposalStatus) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE proposals SET status = ? WHERE id = ?",
                (status.value, proposal_id),
            )

    def list_policy_decisions(self, plan_version_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM policy_decisions
                WHERE plan_version_id = ?
                ORDER BY created_at
                """,
                (plan_version_id,),
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                data = dict(row)
                data["details"] = json.loads(data.pop("details_json"))
                result.append(data)
            return result

    def edit_task(
        self,
        task_id: int,
        *,
        title: str | None = None,
        estimated_minutes: int | None = None,
        target_date: date | None = None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"task {task_id} not found")
            task = dict(row)
            updates: dict[str, Any] = {}
            if title is not None and title != task["title"]:
                updates["title"] = title
            if estimated_minutes is not None and estimated_minutes != task["estimated_minutes"]:
                updates["estimated_minutes"] = estimated_minutes
            if target_date is not None and target_date.isoformat() != task["target_date"]:
                updates["target_date"] = target_date.isoformat()

            if not updates:
                return task

            for field_name, new_value in updates.items():
                connection.execute(
                    """
                    INSERT INTO user_edit_events (task_id, field_name, old_value, new_value, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        field_name,
                        str(task[field_name]) if task[field_name] is not None else None,
                        str(new_value),
                        datetime.now().isoformat(),
                    ),
                )

            set_clause = ", ".join(f"{field_name} = ?" for field_name in updates)
            connection.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?",
                (*updates.values(), task_id),
            )
            updated = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(updated)

    def get_plan_snapshot_data(self, plan_version_id: int) -> dict[str, Any]:
        plan = self.get_plan_version(plan_version_id)
        goal = self.get_goal(plan["goal_id"])
        return {
            "goal": goal,
            "plan_version": plan,
            "tasks": self.list_tasks(plan_version_id),
            "dependencies": self.list_dependencies(plan_version_id),
        }

    def _next_version_number(self, connection: sqlite3.Connection, goal_id: int) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) AS max_version FROM plan_versions WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()
        return int(row["max_version"]) + 1

    def _replace_availability(
        self,
        connection: sqlite3.Connection,
        goal_id: int,
        availability: list[AvailabilityWindow],
    ) -> None:
        connection.execute("DELETE FROM availability_windows WHERE goal_id = ?", (goal_id,))
        for window in availability:
            connection.execute(
                """
                INSERT INTO availability_windows (goal_id, weekday, start_time, end_time)
                VALUES (?, ?, ?, ?)
                """,
                (
                    goal_id,
                    window.weekday,
                    window.start_time.isoformat(),
                    window.end_time.isoformat(),
                ),
            )

    def _transition_task_status(
        self,
        connection: sqlite3.Connection,
        task_id: int,
        new_status: TaskStatus,
    ) -> None:
        row = connection.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"task {task_id} not found")
        current = TaskStatus(row["status"])
        ensure_task_transition(current, new_status)
        connection.execute(
            "UPDATE tasks SET status = ? WHERE id = ?",
            (new_status.value, task_id),
        )

    def _json(self, value: Any) -> str:
        return json.dumps(value, default=self._json_default, sort_keys=True)

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if is_dataclass(value):
            return asdict(value)
        raise TypeError(f"cannot serialize value of type {type(value)!r}")
