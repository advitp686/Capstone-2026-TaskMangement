# Frontend Guide

## Goal

This guide explains the first usable UI layers for the adaptive planner.

## What It Is

The primary frontend is now an assistant-centered web UI served directly by the FastAPI app.

It exposes the full working system while keeping the regular-user flow focused on:

- create a plan from the main screen
- answer assistant clarification questions before planning
- attach Markdown/text reference files
- inspect a roadmap instead of raw task rows
- send task feedback with sliders
- review suggested changes in the assistant panel
- apply or reject suggestions
- revert to a previous plan version if a change is not useful
- inspect schedule blocks and plan history

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
- [`assistant.py`](F:/CAPSTONE/src/adaptive_planner/assistant.py): assistant intake, Tavily search wrapper, feedback review, and chat suggestions
- [`client.py`](F:/CAPSTONE/src/adaptive_planner/client.py): reusable HTTP client used by the desktop app
- [`desktop_app.py`](F:/CAPSTONE/src/adaptive_planner/desktop_app.py): Tkinter desktop UI

## Learning Advice

Read these in order:

1. [`api.py`](F:/CAPSTONE/src/adaptive_planner/api.py)
2. [`webui/index.html`](F:/CAPSTONE/src/adaptive_planner/webui/index.html)
3. [`webui/static/app.js`](F:/CAPSTONE/src/adaptive_planner/webui/static/app.js)
4. [`assistant.py`](F:/CAPSTONE/src/adaptive_planner/assistant.py)
5. [`client.py`](F:/CAPSTONE/src/adaptive_planner/client.py)
6. [`desktop_app.py`](F:/CAPSTONE/src/adaptive_planner/desktop_app.py)

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
