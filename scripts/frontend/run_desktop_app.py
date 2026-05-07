from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adaptive_planner.client import AdaptivePlannerApiClient  # noqa: E402
from adaptive_planner.desktop_app import AdaptivePlannerDesktopApp  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Adaptive Planner desktop client.")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the Adaptive Planner HTTP API.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = AdaptivePlannerApiClient(base_url=args.api_url)
    app = AdaptivePlannerDesktopApp(client)
    app.mainloop()


if __name__ == "__main__":
    main()
