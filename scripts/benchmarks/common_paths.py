from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]

LLAMA_CPP_DIR = REPO_ROOT / "llama-cpp"
MODELS_DIR = REPO_ROOT / "models"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
BENCHMARK_ARTIFACTS_DIR = ARTIFACTS_DIR / "benchmarks"
RESULTS_DIR = BENCHMARK_ARTIFACTS_DIR / "results"
LOGS_DIR = BENCHMARK_ARTIFACTS_DIR / "logs"


for path in (RESULTS_DIR, LOGS_DIR):
    path.mkdir(parents=True, exist_ok=True)
