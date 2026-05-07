from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner.api import create_app  # noqa: E402
from adaptive_planner.client import AdaptivePlannerApiClient  # noqa: E402


class ClientTests(unittest.TestCase):
    def test_client_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir) / "planner_client.db")
            with TestClient(app) as session:
                client = AdaptivePlannerApiClient(base_url="http://testserver", session=session)

                self.assertEqual(client.health()["status"], "ok")
                created = client.create_plan(
                    {
                        "title": "Client flow plan",
                        "description": "Create and approve a plan through the API client.",
                        "target_start_date": "2026-04-06",
                        "target_end_date": "2026-04-08",
                        "availability": [
                            {"weekday": 0, "start_time": "18:00:00", "end_time": "20:00:00"},
                            {"weekday": 1, "start_time": "18:00:00", "end_time": "20:00:00"},
                            {"weekday": 2, "start_time": "18:00:00", "end_time": "20:00:00"},
                        ],
                        "planner": "mock",
                        "auto_approve": True,
                    }
                )
                plan_version_id = created["plan_version_id"]
                self.assertEqual(created["status"], "active")

                plans = client.list_plans()
                self.assertEqual(len(plans), 1)
                detail = client.get_plan(plan_version_id)
                task_id = detail["tasks"][1]["id"]

                feedback = client.record_feedback(
                    task_id,
                    planner="mock",
                    status="blocked",
                    actual_minutes=35,
                    difficulty=4,
                    confidence=0.2,
                    note="Blocked in client flow test.",
                )
                self.assertEqual(feedback["action"], "propose_replan")

                proposal = client.generate_replan(
                    plan_version_id,
                    planner="mock",
                    trigger_task_id=task_id,
                    trigger_reason=feedback["reason"],
                )
                self.assertEqual(proposal["proposal_type"], "replan")
                applied = client.apply_proposal(proposal["id"], planner="mock")
                self.assertEqual(applied["status"], "applied")
