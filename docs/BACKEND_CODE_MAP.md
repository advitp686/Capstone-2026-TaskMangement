# Backend Code Map

## Goal

This file explains the first backend package in the same order the system should be learned.

## Read Order

1. [`domain.py`](F:/CAPSTONE/src/adaptive_planner/domain.py)
2. [`state_machine.py`](F:/CAPSTONE/src/adaptive_planner/state_machine.py)
3. [`policies.py`](F:/CAPSTONE/src/adaptive_planner/policies.py)
4. [`planner.py`](F:/CAPSTONE/src/adaptive_planner/planner.py)
5. [`gemma_adapter.py`](F:/CAPSTONE/src/adaptive_planner/gemma_adapter.py)
6. [`scheduler.py`](F:/CAPSTONE/src/adaptive_planner/scheduler.py)
7. [`schema.py`](F:/CAPSTONE/src/adaptive_planner/schema.py)
8. [`storage.py`](F:/CAPSTONE/src/adaptive_planner/storage.py)
9. [`reminders.py`](F:/CAPSTONE/src/adaptive_planner/reminders.py)
10. [`services.py`](F:/CAPSTONE/src/adaptive_planner/services.py)
11. [`api_models.py`](F:/CAPSTONE/src/adaptive_planner/api_models.py)
12. [`api.py`](F:/CAPSTONE/src/adaptive_planner/api.py)
13. [`client.py`](F:/CAPSTONE/src/adaptive_planner/client.py)
14. [`desktop_app.py`](F:/CAPSTONE/src/adaptive_planner/desktop_app.py)
15. [`run_backend_demo.py`](F:/CAPSTONE/scripts/backend/run_backend_demo.py)
16. [`run_system_smoke.py`](F:/CAPSTONE/scripts/backend/run_system_smoke.py)
17. [`run_api.py`](F:/CAPSTONE/scripts/backend/run_api.py)
18. [`run_desktop_app.py`](F:/CAPSTONE/scripts/frontend/run_desktop_app.py)

## Module Roles

### [`domain.py`](F:/CAPSTONE/src/adaptive_planner/domain.py)

Defines the shared language of the backend:

- plan statuses
- task statuses
- policy actions
- planner request and response types

If this file is confusing, the rest of the backend will feel confusing too.

### [`state_machine.py`](F:/CAPSTONE/src/adaptive_planner/state_machine.py)

Defines what transitions are legal.

This keeps the system state-driven instead of prompt-driven.

Examples:

- a plan cannot jump from `proposed` directly to `active`
- a task cannot jump from `pending` directly to `done`

### [`policies.py`](F:/CAPSTONE/src/adaptive_planner/policies.py)

Defines deterministic policy rules.

This is where the backend decides things like:

- when friction is serious
- when feedback should be requested
- when a replan should be proposed

### [`planner.py`](F:/CAPSTONE/src/adaptive_planner/planner.py)

Defines the planner interface and the mock backend.

This layer stays intentionally small so different planners can plug into the same deterministic backend.

### [`gemma_adapter.py`](F:/CAPSTONE/src/adaptive_planner/gemma_adapter.py)

Defines the real Gemma planner adapter on top of local `llama.cpp`.

It owns:

- local `llama-server` lifecycle
- prompt construction
- JSON extraction and normalization
- turning model output into `PlanProposal`

This is the only place where the backend should directly talk to the local SLM runtime.

### [`scheduler.py`](F:/CAPSTONE/src/adaptive_planner/scheduler.py)

Handles deterministic time placement.

It:

- respects dependencies
- respects availability windows
- avoids existing occupied blocks
- returns conflicts when time is insufficient

### [`schema.py`](F:/CAPSTONE/src/adaptive_planner/schema.py)

Defines the SQLite tables for the current MVP backend slice.

The schema already includes:

- goals
- plan versions
- tasks
- dependencies
- schedule blocks
- reminders
- feedback events
- policy decisions
- proposals
- user edit events

### [`storage.py`](F:/CAPSTONE/src/adaptive_planner/storage.py)

Wraps SQLite access and keeps persistence logic out of services.

This file is the practical source of truth layer in code.

### [`reminders.py`](F:/CAPSTONE/src/adaptive_planner/reminders.py)

Implements the narrow Siren-side reminder delivery service.

It:

- fetches due reminders
- marks them as delivered
- avoids mixing reminder delivery with planning logic

### [`services.py`](F:/CAPSTONE/src/adaptive_planner/services.py)

Orchestrates the workflow:

- create plan
- approve and schedule
- regenerate schedule after edits
- apply rebalance proposals
- record feedback
- generate replan proposal
- apply replan proposals
- edit task

This is the first thin application-service layer.

### [`api_models.py`](F:/CAPSTONE/src/adaptive_planner/api_models.py)

Defines request and response models for the HTTP layer.

### [`api.py`](F:/CAPSTONE/src/adaptive_planner/api.py)

Defines the FastAPI application and maps HTTP routes onto the service layer.

This is intentionally thin so the API does not become a second implementation of the backend logic.

### [`client.py`](F:/CAPSTONE/src/adaptive_planner/client.py)

Defines the reusable API client that the desktop app uses.

### [`desktop_app.py`](F:/CAPSTONE/src/adaptive_planner/desktop_app.py)

Defines the first desktop-first UI over the API using Tkinter.

## What Is Real Versus Mocked Right Now

The deterministic backend is real.

The planner layer now has two options:

- `MockPlannerBackend` for fast local development and tests
- `GemmaPlannerBackend` for real local planning through `llama.cpp`

The remaining limitations are:

- prompt quality still needs iteration
- replan prompts are functional but still early
- no API or UI layer is built on top yet

## What Is Already Deterministic

- state transitions
- schedule placement
- conflict detection
- reminder persistence
- feedback persistence
- policy decisions
- user edit logging

## Best Way To Learn This Code

1. Read one file.
2. Run the demo.
3. Check the SQLite-backed runtime output.
4. Run the tests.
5. Only then move to the next file.

Useful demo commands:

- mock planner: `python F:\CAPSTONE\scripts\backend\run_backend_demo.py --planner mock`
- Gemma planner: `python F:\CAPSTONE\scripts\backend\run_backend_demo.py --planner gemma`
- overall mock system: `python F:\CAPSTONE\scripts\backend\run_system_smoke.py --planner mock --reset-db`
- overall Gemma system: `python F:\CAPSTONE\scripts\backend\run_system_smoke.py --planner gemma --reset-db`
- API server: `python F:\CAPSTONE\scripts\backend\run_api.py`

This project will be much easier to learn if you follow the flow of data rather than reading files randomly.
