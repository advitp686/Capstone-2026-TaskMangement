# API Guide

## Goal

This guide explains the first HTTP API layer for the adaptive planner backend.

## Run The API

Mock-first:

```powershell
python F:\CAPSTONE\scripts\backend\run_api.py
```

The API starts on `http://127.0.0.1:8000` by default.

Useful docs:

- Web UI: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

If you want the API to be able to use Gemma requests, the same API can handle them through the `planner` field on relevant requests. The API internally manages a separate local `llama.cpp` server for Gemma when needed.

## Main Endpoints

### `GET /health`

Basic liveness check.

### `POST /plans`

Create a new plan.

Important fields:

- `planner`: `mock` or `gemma`
- `auto_approve`: if `true`, the backend immediately tries to schedule the plan

### `GET /plans`

List plan versions.

Optional query:

- `status`

### `GET /plans/{plan_version_id}`

Get one full plan view with:

- plan summary
- tasks
- dependencies
- schedule blocks
- reminders
- proposals
- policy decisions

### `POST /plans/{plan_version_id}/approve`

Approve and schedule a plan version.

### `POST /plans/{plan_version_id}/reschedule`

Regenerate the schedule for a plan version after edits.

### `POST /plans/{plan_version_id}/replan`

Generate a replan proposal.

Important fields:

- `planner`
- `trigger_task_id`
- `trigger_reason`

### `PATCH /tasks/{task_id}`

Edit task fields allowed by the MVP:

- `title`
- `estimated_minutes`
- `target_date`

Optional:

- `regenerate_schedule`

### `POST /tasks/{task_id}/feedback`

Record feedback such as:

- `done`
- `delayed`
- `blocked`
- `failed`

### `GET /plans/{plan_version_id}/proposals`

List rebalance and replan proposals for a plan version.

### `POST /proposals/{proposal_id}`

Apply or reject a proposal.

Body:

- `{"action": "apply"}`
- `{"action": "reject"}`

### `POST /reminders/deliver`

Deliver due reminders and mark them as delivered.

Useful for testing the reminder workflow directly from the API.

## Suggested First API Flow

1. `POST /plans` with `planner=mock` and `auto_approve=true`
2. `GET /plans/{id}`
3. `POST /tasks/{task_id}/feedback`
4. `POST /plans/{id}/replan`
5. `POST /proposals/{proposal_id}` with `action=apply`

## Notes

- The API is thin by design. It calls the deterministic backend services instead of duplicating logic.
- For learning, read [`api.py`](F:/CAPSTONE/src/adaptive_planner/api.py) after reading the service layer.
- For verification, see [`test_api.py`](F:/CAPSTONE/tests/test_api.py).
