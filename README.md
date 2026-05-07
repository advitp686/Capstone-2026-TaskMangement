# CAPSTONE

This repo is organized to make the project easier to learn and easier to grow.

## Repo Map

- [`docs/`](F:/CAPSTONE/docs): product thinking, system design, and decisions
- [`docs/source_notes/`](F:/CAPSTONE/docs/source_notes): source material such as handwritten planning notes
- [`docs/API_GUIDE.md`](F:/CAPSTONE/docs/API_GUIDE.md): how to run and use the HTTP API
- [`docs/FRONTEND_GUIDE.md`](F:/CAPSTONE/docs/FRONTEND_GUIDE.md): how to run and learn the web UI and desktop client
- [`src/adaptive_planner/`](F:/CAPSTONE/src/adaptive_planner): backend source package for planning, scheduling, storage, and policies
- [`scripts/benchmarks/`](F:/CAPSTONE/scripts/benchmarks): benchmark and experiment scripts
- [`scripts/backend/`](F:/CAPSTONE/scripts/backend): runnable backend demos and local harnesses
- [`scripts/frontend/`](F:/CAPSTONE/scripts/frontend): desktop client entrypoints
- [`tests/`](F:/CAPSTONE/tests): backend tests
- [`artifacts/benchmarks/results/`](F:/CAPSTONE/artifacts/benchmarks/results): saved benchmark JSON outputs
- [`artifacts/benchmarks/logs/`](F:/CAPSTONE/artifacts/benchmarks/logs): benchmark runtime logs
- [`artifacts/runtime/`](F:/CAPSTONE/artifacts/runtime): local runtime outputs such as SQLite demo databases
- [`models/`](F:/CAPSTONE/models): local model files
- [`llama-cpp/`](F:/CAPSTONE/llama-cpp): local llama.cpp binaries and runtime files

## Learning Path

If you want to understand the project instead of just running it, start here:

1. Read [`docs/PROJECT_DISCUSSION.md`](F:/CAPSTONE/docs/PROJECT_DISCUSSION.md)
2. Read [`docs/SYSTEM_DESIGN.md`](F:/CAPSTONE/docs/SYSTEM_DESIGN.md)
3. Read [`docs/RESEARCH_DECISIONS.md`](F:/CAPSTONE/docs/RESEARCH_DECISIONS.md)
4. Read [`docs/REPO_GUIDE.md`](F:/CAPSTONE/docs/REPO_GUIDE.md)
5. Read [`docs/BACKEND_CODE_MAP.md`](F:/CAPSTONE/docs/BACKEND_CODE_MAP.md)
6. Inspect the files in [`src/adaptive_planner/`](F:/CAPSTONE/src/adaptive_planner)
7. Run [`scripts/backend/run_backend_demo.py`](F:/CAPSTONE/scripts/backend/run_backend_demo.py)
   Recommended first: `python F:\CAPSTONE\scripts\backend\run_backend_demo.py --planner mock`
   Real model path: `python F:\CAPSTONE\scripts\backend\run_backend_demo.py --planner gemma`
8. Run [`scripts/backend/run_system_smoke.py`](F:/CAPSTONE/scripts/backend/run_system_smoke.py)
   Recommended first: `python F:\CAPSTONE\scripts\backend\run_system_smoke.py --planner mock --reset-db`
9. Read [`docs/API_GUIDE.md`](F:/CAPSTONE/docs/API_GUIDE.md) and run [`scripts/backend/run_api.py`](F:/CAPSTONE/scripts/backend/run_api.py)
10. Read [`docs/FRONTEND_GUIDE.md`](F:/CAPSTONE/docs/FRONTEND_GUIDE.md), run [`scripts/backend/run_api.py`](F:/CAPSTONE/scripts/backend/run_api.py), and open `http://127.0.0.1:8000/`
11. Optional: run [`scripts/frontend/run_desktop_app.py`](F:/CAPSTONE/scripts/frontend/run_desktop_app.py)
12. Only then start reading the scripts in [`scripts/benchmarks/`](F:/CAPSTONE/scripts/benchmarks)

## Why This Layout

The root is intentionally kept small so the important parts are obvious:

- docs explain what we are building
- src contains the actual product backend
- scripts hold runnable tooling
- tests keep the backend behavior verifiable
- artifacts hold generated outputs
- models and runtimes stay isolated from source files

This keeps the repo cleaner and makes it easier to learn by purpose instead of by file name clutter.
