from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner.api import create_app  # noqa: E402
from adaptive_planner.gemma_adapter import GemmaPlannerConfig  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Adaptive Planner HTTP API and web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--db-path",
        default=str(REPO_ROOT / "artifacts" / "runtime" / "adaptive_planner_api.db"),
        help="SQLite database path for the API.",
    )
    parser.add_argument(
        "--gemma-port",
        type=int,
        default=8095,
        help="Port used by the internal Gemma llama.cpp server.",
    )
    parser.add_argument(
        "--model-path",
        default=str(REPO_ROOT / "models" / "gemma4" / "gemma-4-E2B-it-Q4_K_M.gguf"),
        help="GGUF model path for Gemma planner requests.",
    )
    parser.add_argument(
        "--server-path",
        default=str(REPO_ROOT / "llama-cpp" / "llama-server.exe"),
        help="llama-server executable path for Gemma planner requests.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app(
        database_path=args.db_path,
        gemma_config=GemmaPlannerConfig(
            port=args.gemma_port,
            model_path=Path(args.model_path),
            server_path=Path(args.server_path),
        ),
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
