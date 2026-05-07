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


class ApiTests(unittest.TestCase):
    def test_api_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir) / "planner_api.db")
            with TestClient(app) as client:
                web_ui = client.get("/")
                self.assertEqual(web_ui.status_code, 200)
                self.assertIn("Adaptive Planner Web UI", web_ui.text)

                asset = client.get("/static/app.js")
                self.assertEqual(asset.status_code, 200)
                self.assertIn("refreshAll", asset.text)

                health = client.get("/health")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["status"], "ok")

                create_response = client.post(
                    "/plans",
                    json={
                        "title": "Learn calculus basics",
                        "description": "Create a plan and keep adapting it.",
                        "target_start_date": "2026-04-06",
                        "target_end_date": "2026-04-08",
                        "availability": [
                            {"weekday": 0, "start_time": "18:00:00", "end_time": "20:00:00"},
                            {"weekday": 1, "start_time": "18:00:00", "end_time": "20:00:00"},
                            {"weekday": 2, "start_time": "18:00:00", "end_time": "20:00:00"},
                        ],
                        "planner": "mock",
                        "auto_approve": True,
                    },
                )
                self.assertEqual(create_response.status_code, 200)
                create_data = create_response.json()
                self.assertEqual(create_data["status"], "active")
                plan_version_id = create_data["plan_version_id"]

                list_response = client.get("/plans")
                self.assertEqual(list_response.status_code, 200)
                self.assertEqual(len(list_response.json()), 1)

                detail_response = client.get(f"/plans/{plan_version_id}")
                self.assertEqual(detail_response.status_code, 200)
                detail_data = detail_response.json()
                self.assertTrue(detail_data["tasks"])
                task_id = detail_data["tasks"][1]["id"]

                reminder_response = client.post(
                    "/reminders/deliver",
                    json={"as_of": "2026-04-06T17:50:00", "limit": 5},
                )
                self.assertEqual(reminder_response.status_code, 200)
                self.assertGreaterEqual(reminder_response.json()["delivered_count"], 1)

                feedback_response = client.post(
                    f"/tasks/{task_id}/feedback?planner=mock",
                    json={
                        "status": "blocked",
                        "actual_minutes": 40,
                        "difficulty": 4,
                        "confidence": 0.2,
                        "note": "Blocked in API test.",
                    },
                )
                self.assertEqual(feedback_response.status_code, 200)
                self.assertEqual(feedback_response.json()["action"], "propose_replan")

                replan_response = client.post(
                    f"/plans/{plan_version_id}/replan",
                    json={
                        "planner": "mock",
                        "trigger_task_id": task_id,
                        "trigger_reason": "Blocked in API test.",
                    },
                )
                self.assertEqual(replan_response.status_code, 200)
                proposal_id = replan_response.json()["id"]
                self.assertEqual(replan_response.json()["proposal_type"], "replan")

                apply_response = client.post(
                    f"/proposals/{proposal_id}?planner=mock",
                    json={"action": "apply"},
                )
                self.assertEqual(apply_response.status_code, 200)
                self.assertEqual(apply_response.json()["status"], "applied")

                refreshed_detail = client.get(f"/plans/{plan_version_id}")
                self.assertEqual(refreshed_detail.status_code, 200)
                self.assertTrue(refreshed_detail.json()["proposals"])


if __name__ == "__main__":
    unittest.main()
