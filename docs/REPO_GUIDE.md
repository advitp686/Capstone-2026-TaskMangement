# Repo Guide

## Goal

This guide explains the repo structure in a way that helps a teammate learn the project, not just use it.

## Top-Level Folders

### [`docs/`](F:/CAPSTONE/docs)

This is the thinking layer of the project.

Read these first:

- [`PROJECT_DISCUSSION.md`](F:/CAPSTONE/docs/PROJECT_DISCUSSION.md): what the product is and what problem it solves
- [`SYSTEM_DESIGN.md`](F:/CAPSTONE/docs/SYSTEM_DESIGN.md): how the backend should be structured
- [`RESEARCH_DECISIONS.md`](F:/CAPSTONE/docs/RESEARCH_DECISIONS.md): what we decided, what we postponed, and what is still open
- [`BACKEND_CODE_MAP.md`](F:/CAPSTONE/docs/BACKEND_CODE_MAP.md): how the first backend package is organized
- [`API_GUIDE.md`](F:/CAPSTONE/docs/API_GUIDE.md): how to run and use the HTTP API
- [`FRONTEND_GUIDE.md`](F:/CAPSTONE/docs/FRONTEND_GUIDE.md): how to run and learn the web UI and desktop client

### [`docs/source_notes/`](F:/CAPSTONE/docs/source_notes)

This holds raw source material used to shape the product.

Current contents:

- handwritten note pages from the original idea discussion

These notes are important because they show the origin of concepts like:

- adaptive replanning
- reminders
- feedback logic
- the four-part architecture

### [`scripts/benchmarks/`](F:/CAPSTONE/scripts/benchmarks)

This is the experiment layer.

Current scripts:

- [`benchmark_gemma.py`](F:/CAPSTONE/scripts/benchmarks/benchmark_gemma.py): basic Ollama generate benchmark
- [`benchmark_gemma_chat.py`](F:/CAPSTONE/scripts/benchmarks/benchmark_gemma_chat.py): Ollama chat benchmark with prompt suite
- [`benchmark_llama_cpp.py`](F:/CAPSTONE/scripts/benchmarks/benchmark_llama_cpp.py): Python llama.cpp benchmark
- [`benchmark_llama_server.py`](F:/CAPSTONE/scripts/benchmarks/benchmark_llama_server.py): llama-server benchmark with reasoning settings
- [`common_paths.py`](F:/CAPSTONE/scripts/benchmarks/common_paths.py): shared repo-relative paths for benchmark outputs

These scripts are not the product backend. They are learning and evaluation tools.

### [`src/adaptive_planner/`](F:/CAPSTONE/src/adaptive_planner)

This is the product backend package.

Current core modules:

- [`domain.py`](F:/CAPSTONE/src/adaptive_planner/domain.py): enums, request types, and shared dataclasses
- [`state_machine.py`](F:/CAPSTONE/src/adaptive_planner/state_machine.py): allowed plan and task transitions
- [`policies.py`](F:/CAPSTONE/src/adaptive_planner/policies.py): deterministic feedback and replanning policy rules
- [`planner.py`](F:/CAPSTONE/src/adaptive_planner/planner.py): planner interface plus the current mock planner
- [`gemma_adapter.py`](F:/CAPSTONE/src/adaptive_planner/gemma_adapter.py): real Gemma planner adapter using local llama.cpp
- [`api_models.py`](F:/CAPSTONE/src/adaptive_planner/api_models.py): request and response models for the HTTP API
- [`api.py`](F:/CAPSTONE/src/adaptive_planner/api.py): FastAPI app that exposes the backend workflows
- [`webui/index.html`](F:/CAPSTONE/src/adaptive_planner/webui/index.html): minimal browser UI layout
- [`webui/static/app.js`](F:/CAPSTONE/src/adaptive_planner/webui/static/app.js): browser-side workflow logic
- [`webui/static/styles.css`](F:/CAPSTONE/src/adaptive_planner/webui/static/styles.css): plain browser UI styling
- [`client.py`](F:/CAPSTONE/src/adaptive_planner/client.py): reusable HTTP client for the desktop app
- [`desktop_app.py`](F:/CAPSTONE/src/adaptive_planner/desktop_app.py): Tkinter desktop interface over the API
- [`scheduler.py`](F:/CAPSTONE/src/adaptive_planner/scheduler.py): deterministic time-slot allocation and conflict handling
- [`schema.py`](F:/CAPSTONE/src/adaptive_planner/schema.py): SQLite schema
- [`storage.py`](F:/CAPSTONE/src/adaptive_planner/storage.py): persistence and repository-style database access
- [`reminders.py`](F:/CAPSTONE/src/adaptive_planner/reminders.py): narrow reminder-delivery service
- [`services.py`](F:/CAPSTONE/src/adaptive_planner/services.py): orchestration layer for plan creation, scheduling, feedback, and replanning

This package is where the real application backend will grow.

### [`scripts/backend/`](F:/CAPSTONE/scripts/backend)

This is the local backend harness layer.

Current scripts:

- [`run_backend_demo.py`](F:/CAPSTONE/scripts/backend/run_backend_demo.py): creates a sample goal, generates a plan, schedules it, records friction, and creates a replan proposal with either `mock` or `gemma` planner mode
- [`run_system_smoke.py`](F:/CAPSTONE/scripts/backend/run_system_smoke.py): runs a larger end-to-end system flow including multi-plan conflict, rebalance, reminders, task edit, and replanning
- [`run_api.py`](F:/CAPSTONE/scripts/backend/run_api.py): starts the FastAPI server and serves the browser UI at `http://127.0.0.1:8000/`
- [`run_desktop_app.py`](F:/CAPSTONE/scripts/frontend/run_desktop_app.py): starts the desktop client that talks to the API

### [`tests/`](F:/CAPSTONE/tests)

This is the backend verification layer.

Current tests:

- state machine rules
- feedback policy behavior
- scheduler behavior
- basic service flow
- overall system flow
- API route flow
- API client flow

### [`artifacts/`](F:/CAPSTONE/artifacts)

This is the generated-output layer.

Current benchmark subfolders:

- [`results/`](F:/CAPSTONE/artifacts/benchmarks/results): JSON outputs
- [`logs/`](F:/CAPSTONE/artifacts/benchmarks/logs): server logs and run logs

Rule of thumb:

- if a file is produced by a script, it should go into `artifacts/`
- if a file contains source logic, it should not live in `artifacts/`

### [`models/`](F:/CAPSTONE/models)

This holds local model files.

Keep this separate from source code because:

- models are large
- they are runtime assets, not source files
- mixing them with code makes the repo hard to scan

### [`llama-cpp/`](F:/CAPSTONE/llama-cpp)

This is the local runtime/tooling area for llama.cpp.

Treat it like a runtime dependency directory, not your main source folder.

## How To Read The Project

Recommended order:

1. understand the product vision in `docs/`
2. understand the system architecture in `docs/`
3. inspect the benchmark scripts to see how models were evaluated
4. inspect `domain.py`, `state_machine.py`, and `policies.py`
5. inspect `scheduler.py` and `storage.py`
6. inspect `services.py`
7. inspect `api.py`
8. inspect `client.py` and `desktop_app.py`
9. run the backend demo, smoke flow, API, desktop client, and tests

## How To Learn While Building

Your concern is valid: if someone else does all the work, learning becomes shallow.

A good way to use this repo is:

- read the docs before changing code
- own one subsystem at a time
- keep implementation files small and focused
- add short notes about why a design choice exists
- review generated artifacts to understand system behavior

For this repo, a good order is:

- learn the types first
- then learn state transitions
- then learn deterministic policy rules
- then learn scheduling
- only then learn orchestration

The goal is not just a clean repo. The goal is a repo that teaches the project structure naturally.
