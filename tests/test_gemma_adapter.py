from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner.gemma_adapter import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    DEFAULT_SERVER_PATH,
    GemmaPlannerBackend,
    GemmaPlannerError,
)


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

    def test_default_server_command_uses_prism_vulkan_gemma_2b(self) -> None:
        command = [str(part) for part in self.adapter._build_server_command()]
        command_text = " ".join(command).lower()

        def value_after(flag: str) -> str:
            return command[command.index(flag) + 1]

        self.assertEqual(command[0], str(DEFAULT_SERVER_PATH))
        self.assertEqual(value_after("-m"), str(DEFAULT_MODEL_PATH))
        self.assertEqual(value_after("-c"), "8192")
        self.assertEqual(value_after("-n"), "768")
        self.assertEqual(value_after("-t"), "6")
        self.assertEqual(value_after("-tb"), "6")
        self.assertEqual(value_after("-b"), "256")
        self.assertEqual(value_after("-ub"), "128")
        self.assertEqual(value_after("-np"), "1")
        self.assertEqual(value_after("-dev"), "Vulkan1")
        self.assertEqual(value_after("-ngl"), "99")
        self.assertEqual(value_after("--cache-type-k"), "f16")
        self.assertEqual(value_after("--cache-type-v"), "f16")
        self.assertEqual(value_after("--cache-ram"), "0")
        self.assertEqual(value_after("--reasoning"), "on")
        self.assertEqual(value_after("--reasoning-format"), "deepseek")
        self.assertEqual(value_after("--reasoning-budget"), "256")
        self.assertEqual(value_after("--flash-attn"), "off")
        self.assertIn("--no-mmap", command)
        self.assertNotIn("--mlock", command)
        self.assertNotIn("atomic", command_text)
        self.assertNotIn("mtp", command_text)


if __name__ == "__main__":
    unittest.main()
