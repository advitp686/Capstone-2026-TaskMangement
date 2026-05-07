from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from .domain import AvailabilityWindow


@dataclass(slots=True)
class ScheduledBlock:
    task_id: int
    start_at: datetime
    end_at: datetime


@dataclass(slots=True)
class ScheduleConflict:
    task_id: int
    reason: str


@dataclass(slots=True)
class ScheduleResult:
    blocks: list[ScheduledBlock] = field(default_factory=list)
    conflicts: list[ScheduleConflict] = field(default_factory=list)


class DeterministicScheduler:
    def schedule(
        self,
        tasks: list[dict[str, Any]],
        dependencies: list[tuple[int, int]],
        availability: list[AvailabilityWindow],
        schedule_start: date,
        schedule_end: date,
        existing_blocks: list[ScheduledBlock] | None = None,
    ) -> ScheduleResult:
        existing_blocks = existing_blocks or []
        result = ScheduleResult()
        task_end_times: dict[int, datetime] = {}
        occupancy = list(existing_blocks)

        ordered_task_ids = self._topological_sort(tasks, dependencies)
        task_map = {task["id"]: task for task in tasks}

        for task_id in ordered_task_ids:
            task = task_map[task_id]
            earliest_start = self._dependency_ready_at(
                task_id,
                dependencies,
                task_end_times,
                schedule_start,
            )
            remaining = int(task["estimated_minutes"])
            current_day = max(schedule_start, earliest_start.date())

            while current_day <= schedule_end and remaining > 0:
                windows = [window for window in availability if window.weekday == current_day.weekday()]
                for window in windows:
                    slot_start = datetime.combine(current_day, window.start_time)
                    slot_end = datetime.combine(current_day, window.end_time)
                    if current_day == earliest_start.date():
                        slot_start = max(slot_start, earliest_start)
                    if slot_start >= slot_end:
                        continue

                    for gap_start, gap_end in self._available_gaps(slot_start, slot_end, occupancy):
                        if remaining <= 0:
                            break
                        available_minutes = int((gap_end - gap_start).total_seconds() // 60)
                        if available_minutes <= 0:
                            continue
                        block_minutes = min(remaining, available_minutes)
                        block_end = gap_start + timedelta(minutes=block_minutes)
                        block = ScheduledBlock(task_id=task_id, start_at=gap_start, end_at=block_end)
                        result.blocks.append(block)
                        occupancy.append(block)
                        task_end_times[task_id] = block_end
                        remaining -= block_minutes

                current_day += timedelta(days=1)

            if remaining > 0:
                result.conflicts.append(
                    ScheduleConflict(
                        task_id=task_id,
                        reason="Not enough available time before the target end date.",
                    )
                )

        return result

    def _dependency_ready_at(
        self,
        task_id: int,
        dependencies: list[tuple[int, int]],
        task_end_times: dict[int, datetime],
        schedule_start: date,
    ) -> datetime:
        earliest = datetime.combine(schedule_start, time.min)
        predecessors = [predecessor for predecessor, successor in dependencies if successor == task_id]
        for predecessor in predecessors:
            predecessor_end = task_end_times.get(predecessor)
            if predecessor_end is not None:
                earliest = max(earliest, predecessor_end)
        return earliest

    def _available_gaps(
        self,
        window_start: datetime,
        window_end: datetime,
        occupancy: list[ScheduledBlock],
    ) -> list[tuple[datetime, datetime]]:
        day_blocks = sorted(
            (
                block
                for block in occupancy
                if block.start_at < window_end and block.end_at > window_start
            ),
            key=lambda block: block.start_at,
        )

        cursor = window_start
        gaps: list[tuple[datetime, datetime]] = []
        for block in day_blocks:
            if block.start_at > cursor:
                gaps.append((cursor, min(block.start_at, window_end)))
            cursor = max(cursor, block.end_at)
            if cursor >= window_end:
                break
        if cursor < window_end:
            gaps.append((cursor, window_end))
        return gaps

    def _topological_sort(
        self,
        tasks: list[dict[str, Any]],
        dependencies: list[tuple[int, int]],
    ) -> list[int]:
        task_ids = [task["id"] for task in tasks]
        indegree = {task_id: 0 for task_id in task_ids}
        adjacency = {task_id: [] for task_id in task_ids}

        for predecessor, successor in dependencies:
            adjacency.setdefault(predecessor, []).append(successor)
            indegree[successor] = indegree.get(successor, 0) + 1

        ready = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
        ordered: list[int] = []
        while ready:
            task_id = ready.pop(0)
            ordered.append(task_id)
            for successor in adjacency.get(task_id, []):
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    ready.append(successor)
                    ready.sort()

        if len(ordered) != len(task_ids):
            raise ValueError("dependency cycle detected")

        return ordered
