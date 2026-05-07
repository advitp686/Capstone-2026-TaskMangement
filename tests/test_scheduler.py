from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner import AvailabilityWindow  # noqa: E402
from adaptive_planner.scheduler import DeterministicScheduler, ScheduledBlock  # noqa: E402


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scheduler = DeterministicScheduler()

    def test_scheduler_respects_existing_blocks_and_dependencies(self) -> None:
        tasks = [
            {"id": 1, "estimated_minutes": 90},
            {"id": 2, "estimated_minutes": 60},
        ]
        dependencies = [(1, 2)]
        availability = [
            AvailabilityWindow(weekday=0, start_time=time(18, 0), end_time=time(20, 0)),
            AvailabilityWindow(weekday=1, start_time=time(18, 0), end_time=time(20, 0)),
        ]
        existing_blocks = [
            ScheduledBlock(
                task_id=99,
                start_at=datetime(2026, 4, 6, 18, 0),
                end_at=datetime(2026, 4, 6, 19, 0),
            )
        ]

        result = self.scheduler.schedule(
            tasks=tasks,
            dependencies=dependencies,
            availability=availability,
            schedule_start=date(2026, 4, 6),
            schedule_end=date(2026, 4, 7),
            existing_blocks=existing_blocks,
        )

        self.assertEqual(len(result.conflicts), 0)
        self.assertEqual(sum(int((block.end_at - block.start_at).total_seconds() // 60) for block in result.blocks), 150)
        first_task_blocks = [block for block in result.blocks if block.task_id == 1]
        second_task_blocks = [block for block in result.blocks if block.task_id == 2]
        self.assertTrue(first_task_blocks)
        self.assertTrue(second_task_blocks)
        self.assertGreaterEqual(second_task_blocks[0].start_at, first_task_blocks[-1].end_at)


if __name__ == "__main__":
    unittest.main()
