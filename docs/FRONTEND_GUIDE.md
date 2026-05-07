# Frontend Guide

## Goal

This guide explains the first usable UI layers for the adaptive planner.

## What It Is

The primary frontend is now a minimal web UI served directly by the FastAPI app.

It is intentionally simple, but it exposes the full working system:

- create plan
- approve and reschedule
- inspect tasks, dependencies, schedule blocks, reminders, proposals, and policy decisions
- edit tasks
- send feedback
- generate replans
- apply or reject proposals
- deliver reminders

The Tkinter desktop client still exists, but the browser UI is now the easiest way to drive the full system.

## Run Order

1. Start the API server:

```powershell
python F:\CAPSTONE\scripts\backend\run_api.py
```

2. Open the web UI in your browser:

```text
http://127.0.0.1:8000/
```

3. Optional desktop client:

```powershell
python F:\CAPSTONE\scripts\frontend\run_desktop_app.py
```

## Important Files

- [`api.py`](F:/CAPSTONE/src/adaptive_planner/api.py): FastAPI app and web UI serving
- [`webui/index.html`](F:/CAPSTONE/src/adaptive_planner/webui/index.html): browser UI layout
- [`webui/static/app.js`](F:/CAPSTONE/src/adaptive_planner/webui/static/app.js): browser workflow logic
- [`webui/static/styles.css`](F:/CAPSTONE/src/adaptive_planner/webui/static/styles.css): plain UI styling
- [`client.py`](F:/CAPSTONE/src/adaptive_planner/client.py): reusable HTTP client used by the desktop app
- [`desktop_app.py`](F:/CAPSTONE/src/adaptive_planner/desktop_app.py): Tkinter desktop UI

## Learning Advice

Read these in order:

1. [`api.py`](F:/CAPSTONE/src/adaptive_planner/api.py)
2. [`webui/index.html`](F:/CAPSTONE/src/adaptive_planner/webui/index.html)
3. [`webui/static/app.js`](F:/CAPSTONE/src/adaptive_planner/webui/static/app.js)
4. [`client.py`](F:/CAPSTONE/src/adaptive_planner/client.py)
5. [`desktop_app.py`](F:/CAPSTONE/src/adaptive_planner/desktop_app.py)

That order makes the browser flow easier to understand:

- HTTP route serves UI
- UI sends fetch requests
- API endpoints call backend services

## Scope Notes

This is still an MVP UI.

The goal is not polish yet. The goal is:

- expose all current backend functionality
- keep the frontend thin
- make the full workflow easier to test than raw scripts
