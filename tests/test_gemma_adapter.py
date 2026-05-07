from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner.gemma_adapter import GemmaPlannerBackend, GemmaPlannerError  # noqa: E402


class GemmaAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = GemmaPlannerBackend()

    def tearDown(self) -> None:
        self.adapter.close()

    def test_extract_json_payload_from_fenced_block(self) -> None:
        payload = self.adapter._extract_json_payload(
            '```json\n{"title":"Plan","summary":"S","rationale":"R","tasks":[]}\n```'
        )
        self.assertEqual(payload["title"], "Plan")

    def test_proposal_normalizes_dependencies_and_task_keys(self) -> None:
        proposal = self.adapter._proposal_from_dict(
            {
                "title": "Plan",
                "summary": "Summary",
                "rationale": "Rationale",
                "tasks": [
                    {
                        "key": "First Task",
                        "title": "First",
                        "summary": "Start here",
                        "estimated_minutes": 120,
                        "difficulty": "medium",
                        "depends_on_keys": [],
                    },
                    {
                        "key": "Second Task",
                        "title": "Second",
                        "summary": "Continue",
                        "estimated_minutes": 90,
                        "difficulty": "high",
                        "depends_on_keys": ["First Task", "Missing Task"],
                    },
                ],
            },
            fallback_title="Fallback",
        )
        self.assertEqual(proposal.tasks[0].key, "first_task")
        self.assertEqual(proposal.tasks[1].depends_on_keys, ["first_task"])

    def test_invalid_task_list_raises(self) -> None:
        with self.assertRaises(GemmaPlannerError):
            self.adapter._proposal_from_dict(
                {"title": "Plan", "summary": "Summary", "rationale": "Rationale", "tasks": []},
                fallback_title="Fallback",
            )


if __name__ == "__main__":
    unittest.main()
