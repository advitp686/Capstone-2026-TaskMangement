from __future__ import annotations

from datetime import datetime
from typing import Any

import requests


class ApiClientError(RuntimeError):
    pass


class AdaptivePlannerApiClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        session: Any | None = None,
        timeout_sec: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_sec = timeout_sec

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def list_plans(self, *, status: str | None = None) -> list[dict[str, Any]]:
        params = {"status": status} if status else None
        return self._request("GET", "/plans", params=params)

    def get_plan(self, plan_version_id: int) -> dict[str, Any]:
        return self._request("GET", f"/plans/{plan_version_id}")

    def create_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/plans", json=payload)

    def approve_plan(self, plan_version_id: int, *, planner: str = "mock") -> dict[str, Any]:
        return self._request("POST", f"/plans/{plan_version_id}/approve", params={"planner": planner})

    def reschedule_plan(self, plan_version_id: int, *, planner: str = "mock") -> dict[str, Any]:
        return self._request("POST", f"/plans/{plan_version_id}/reschedule", params={"planner": planner})

    def generate_replan(
        self,
        plan_version_id: int,
        *,
        planner: str,
        trigger_task_id: int | None,
        trigger_reason: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/plans/{plan_version_id}/replan",
            json={
                "planner": planner,
                "trigger_task_id": trigger_task_id,
                "trigger_reason": trigger_reason,
            },
        )

    def edit_task(
        self,
        task_id: int,
        *,
        planner: str = "mock",
        title: str | None = None,
        estimated_minutes: int | None = None,
        target_date: str | None = None,
        regenerate_schedule: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"regenerate_schedule": regenerate_schedule}
        if title:
            payload["title"] = title
        if estimated_minutes is not None:
            payload["estimated_minutes"] = estimated_minutes
        if target_date:
            payload["target_date"] = target_date
        return self._request(
            "PATCH",
            f"/tasks/{task_id}",
            json=payload,
            params={"planner": planner},
        )

    def record_feedback(
        self,
        task_id: int,
        *,
        planner: str,
        status: str,
        actual_minutes: int | None = None,
        difficulty: int | None = None,
        confidence: float | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": status, "note": note}
        if actual_minutes is not None:
            payload["actual_minutes"] = actual_minutes
        if difficulty is not None:
            payload["difficulty"] = difficulty
        if confidence is not None:
            payload["confidence"] = confidence
        return self._request(
            "POST",
            f"/tasks/{task_id}/feedback",
            json=payload,
            params={"planner": planner},
        )

    def list_proposals(self, plan_version_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/plans/{plan_version_id}/proposals")

    def apply_proposal(self, proposal_id: int, *, planner: str = "mock") -> dict[str, Any]:
        return self._request(
            "POST",
            f"/proposals/{proposal_id}",
            json={"action": "apply"},
            params={"planner": planner},
        )

    def reject_proposal(self, proposal_id: int, *, planner: str = "mock") -> dict[str, Any]:
        return self._request(
            "POST",
            f"/proposals/{proposal_id}",
            json={"action": "reject"},
            params={"planner": planner},
        )

    def deliver_reminders(
        self,
        *,
        as_of: datetime | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if as_of is not None:
            payload["as_of"] = as_of.isoformat()
        if limit is not None:
            payload["limit"] = limit
        return self._request("POST", "/reminders/deliver", json=payload)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        request_kwargs: dict[str, Any] = {
            "params": params,
            "json": json,
        }
        if not self._is_test_client():
            request_kwargs["timeout"] = self.timeout_sec
        try:
            response = self.session.request(method, url, **request_kwargs)
            response.raise_for_status()
        except Exception as exc:
            raise ApiClientError(f"{method} {url} failed: {exc}") from exc
        return response.json()

    def _is_test_client(self) -> bool:
        module_name = type(self.session).__module__
        return module_name.startswith("starlette.testclient")
