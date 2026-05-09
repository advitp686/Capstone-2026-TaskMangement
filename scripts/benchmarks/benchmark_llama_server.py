import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

from common_paths import LOGS_DIR, REPO_ROOT, RESULTS_DIR
from benchmark_gemma_chat import PROMPTS, SYSTEM_PROMPT

DEFAULT_SERVER = Path(
    r"F:\CAPSTONE - Copy\artifacts\benchmarks\tools\prism-win-vulkan-merged\llama-server.exe"
)
DEFAULT_MODEL = Path(r"F:\CAPSTONE - Copy\models\gemma4\gemma-4-E2B-it-Q4_K_M.gguf")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark llama-server with reasoning enabled on the planning prompt suite."
    )
    parser.add_argument(
        "--model-path",
        default=str(DEFAULT_MODEL),
        help="Path to the GGUF model file.",
    )
    parser.add_argument(
        "--server-path",
        default=str(DEFAULT_SERVER),
        help="Path to llama-server.exe.",
    )
    parser.add_argument(
        "--tag",
        default="gemma4-e2b-reasoning",
        help="Tag used for output filenames.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for llama-server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for llama-server.",
    )
    parser.add_argument(
        "--ctx",
        type=int,
        default=8192,
        help="Context size for llama-server.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=768,
        help="Maximum completion tokens per prompt.",
    )
    parser.add_argument(
        "--reasoning-mode",
        choices=("on", "off"),
        default="on",
        help="Whether to launch llama-server with reasoning enabled or disabled.",
    )
    parser.add_argument(
        "--reasoning-budget",
        type=int,
        default=256,
        help="Reasoning token budget passed to llama-server.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=6,
        help="Generation threads.",
    )
    parser.add_argument(
        "--threads-batch",
        type=int,
        default=6,
        help="Prompt processing threads.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="Logical batch size to limit memory spikes.",
    )
    parser.add_argument(
        "--ubatch-size",
        type=int,
        default=128,
        help="Physical batch size to limit memory spikes.",
    )
    parser.add_argument(
        "--cache-type-k",
        default="f16",
        help="K cache type passed to llama-server, e.g. f16 or q4_0.",
    )
    parser.add_argument(
        "--cache-type-v",
        default="f16",
        help="V cache type passed to llama-server, e.g. f16 or q4_0.",
    )
    parser.add_argument(
        "--gpu-layers",
        default="99",
        help="GPU layers argument for llama-server.",
    )
    parser.add_argument(
        "--device",
        default="Vulkan1",
        help="Device name list for llama-server, e.g. Vulkan0 or Vulkan0,Vulkan1.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel decode slots for the server.",
    )
    parser.add_argument(
        "--cache-ram",
        "--cache-ram-mib",
        dest="cache_ram",
        type=int,
        default=0,
        help="Prompt-cache RAM budget passed to llama-server. Use 0 to disable prompt cache.",
    )
    parser.add_argument(
        "--mlock",
        choices=("on", "off"),
        default="off",
        help="Whether to pass --mlock to llama-server.",
    )
    parser.add_argument(
        "--flash-attn",
        choices=("on", "off", "auto"),
        default="off",
        help="Flash attention mode passed to llama-server.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.4,
        help="Sampling temperature for prompt runs.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for reproducible sampling.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=180,
        help="Seconds to wait for llama-server to become ready.",
    )
    parser.add_argument(
        "--max-prompts",
        type=int,
        default=0,
        help="Limit benchmark to the first N prompts for quick testing. 0 runs all prompts.",
    )
    return parser.parse_args()


def build_server_command(args, log_path):
    use_gpu = str(args.device).strip().lower() != "none"

    cmd = [
        str(Path(args.server_path)),
        "-m",
        str(Path(args.model_path)),
        "-c",
        str(args.ctx),
        "-n",
        str(args.max_tokens),
        "-t",
        str(args.threads),
        "-tb",
        str(args.threads_batch),
        "-b",
        str(args.batch_size),
        "-ub",
        str(args.ubatch_size),
        "-np",
        str(args.parallel),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--no-mmap",
        "--perf",
        "--cache-ram",
        str(args.cache_ram),
        "--cache-type-k",
        str(args.cache_type_k),
        "--cache-type-v",
        str(args.cache_type_v),
        "--log-file",
        str(log_path),
    ]

    if args.mlock == "on":
        cmd.append("--mlock")

    cmd.extend(["--reasoning", args.reasoning_mode])
    if args.reasoning_mode == "on":
        cmd.extend(
            [
                "--reasoning-format",
                "deepseek",
                "--reasoning-budget",
                str(args.reasoning_budget),
            ]
        )

    if use_gpu:
        cmd.extend(
            [
                "-ngl",
                str(args.gpu_layers),
                "-dev",
                str(args.device),
                "--flash-attn",
                args.flash_attn,
            ]
        )
    else:
        cmd.extend(
            [
                "-ngl",
                "0",
                "-dev",
                "none",
                "--no-op-offload",
                "--flash-attn",
                args.flash_attn,
            ]
        )

    return cmd


def wait_for_server(base_url, timeout_sec):
    deadline = time.time() + timeout_sec
    health_url = f"{base_url}/health"
    models_url = f"{base_url}/v1/models"

    while time.time() < deadline:
        for url in (health_url, models_url):
            try:
                resp = requests.get(url, timeout=5)
                if resp.ok:
                    return
            except requests.RequestException:
                pass
        time.sleep(1)

    raise RuntimeError(f"llama-server did not become ready within {timeout_sec} seconds")


def start_server(args, output_dir):
    base_url = f"http://{args.host}:{args.port}"
    log_path = LOGS_DIR / f"{args.tag}.server.log"
    cmd = build_server_command(args, log_path)

    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    try:
        wait_for_server(base_url, args.startup_timeout)
    except Exception:
        stop_server(process)
        raise

    return process, log_path, base_url


def stop_server(process):
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def extract_latest_timings(log_path):
    if not Path(log_path).exists():
        return {}

    text = Path(log_path).read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)

    prompt_matches = []
    eval_matches = []
    total_matches = []

    for line in text.splitlines():
        prompt_match = re.search(
            r"prompt eval time =\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens.*?([\d.]+)\s*tokens per second\)",
            line,
        )
        eval_match = re.search(
            r"(?:^|\s)eval time =\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens.*?([\d.]+)\s*tokens per second\)",
            line,
        )
        total_match = re.search(
            r"total time =\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens",
            line,
        )

        if prompt_match:
            prompt_matches.append(prompt_match.groups())
        if eval_match:
            eval_matches.append(eval_match.groups())
        if total_match:
            total_matches.append(total_match.groups())

    timings = {}
    if prompt_matches:
        ms, tokens, tok_s = prompt_matches[-1]
        timings["prompt_eval_time_ms"] = float(ms)
        timings["prompt_eval_tokens"] = int(tokens)
        timings["prompt_eval_tok_per_sec"] = float(tok_s)
    if eval_matches:
        ms, tokens, tok_s = eval_matches[-1]
        timings["eval_time_ms"] = float(ms)
        timings["eval_tokens"] = int(tokens)
        timings["eval_tok_per_sec"] = float(tok_s)
    if total_matches:
        ms, tokens = total_matches[-1]
        timings["total_time_ms"] = float(ms)
        timings["total_time_tokens"] = int(tokens)

    return timings


def run_benchmark(args, base_url, log_path):
    endpoint = f"{base_url}/v1/chat/completions"
    results = []

    print(f"\n{'=' * 70}")
    print(f"  BENCHMARKING llama-server: {args.tag}")
    print(f"{'=' * 70}\n")

    prompt_list = PROMPTS[: args.max_prompts] if args.max_prompts > 0 else PROMPTS

    for test in prompt_list:
        print(f"\n--- {test['category']} ({test['id']}) ---")
        print(f"Prompt: {test['prompt'][:100]}...")

        payload = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": test["prompt"]},
            ],
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "stream": False,
            "seed": args.seed,
        }

        start = time.time()
        try:
            resp = requests.post(endpoint, json=payload, timeout=900)
            elapsed = time.time() - start
            resp.raise_for_status()
            data = resp.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            response_text = message.get("content", "")
            reasoning_text = (
                message.get("reasoning_content")
                or choice.get("reasoning_content")
                or ""
            )
            usage = data.get("usage", {})
            eval_count = usage.get("completion_tokens", 0)
            prompt_eval_count = usage.get("prompt_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_eval_count + eval_count)
            timing_data = extract_latest_timings(log_path)
            wall_tokens_per_sec = eval_count / elapsed if elapsed > 0 else 0
            prompt_tps = timing_data.get("prompt_eval_tok_per_sec")
            gen_tps = timing_data.get("eval_tok_per_sec", wall_tokens_per_sec)

            result = {
                "id": test["id"],
                "category": test["category"],
                "model_path": str(Path(args.model_path)),
                "response": response_text,
                "reasoning_content": reasoning_text,
                "reasoning_detected": bool(reasoning_text.strip()),
                "wall_time_sec": round(elapsed, 2),
                "tokens_generated": eval_count,
                "generation_tok_per_sec": round(gen_tps, 2),
                "generation_tok_per_sec_wall": round(wall_tokens_per_sec, 2),
                "prompt_tokens": prompt_eval_count,
                "prompt_eval_tok_per_sec": round(prompt_tps, 2) if prompt_tps else None,
                "total_tokens": total_tokens,
                "finish_reason": choice.get("finish_reason"),
                "raw_usage": usage,
                "timings": timing_data,
            }
            results.append(result)

            print(f"  Wall time: {result['wall_time_sec']}s")
            print(f"  Prompt tokens: {prompt_eval_count}")
            print(f"  Completion tokens: {eval_count}")
            print(f"  Generation speed: {result['generation_tok_per_sec']} tok/s")
            if result["prompt_eval_tok_per_sec"] is not None:
                print(f"  Prompt eval speed: {result['prompt_eval_tok_per_sec']} tok/s")
            print(f"  Reasoning detected: {result['reasoning_detected']}")
            print(f"\n  === RESPONSE PREVIEW ===")
            print(f"  {response_text[:600]}")
            if len(response_text) > 600:
                print(f"  ... [{len(response_text) - 600} more chars]")
            if reasoning_text:
                print(f"\n  === REASONING PREVIEW ===")
                print(f"  {reasoning_text[:400]}")
                if len(reasoning_text) > 400:
                    print(f"  ... [{len(reasoning_text) - 400} more chars]")
            print()

        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append(
                {
                    "id": test["id"],
                    "category": test["category"],
                    "model_path": str(Path(args.model_path)),
                    "error": str(exc),
                }
            )

    return results


def summarize_results(results):
    valid = [item for item in results if "error" not in item]
    if not valid:
        return {
            "tests_completed": 0,
            "avg_generation_tok_per_sec": 0,
            "avg_prompt_eval_tok_per_sec": 0,
            "avg_wall_time_sec": 0,
            "total_tokens_generated": 0,
            "reasoning_hits": 0,
        }

    prompt_speeds = [
        item["prompt_eval_tok_per_sec"]
        for item in valid
        if item.get("prompt_eval_tok_per_sec") is not None
    ]

    return {
        "tests_completed": len(valid),
        "avg_generation_tok_per_sec": round(
            sum(item["generation_tok_per_sec"] for item in valid) / len(valid), 2
        ),
        "avg_prompt_eval_tok_per_sec": round(
            sum(prompt_speeds) / len(prompt_speeds), 2
        )
        if prompt_speeds
        else None,
        "avg_wall_time_sec": round(
            sum(item["wall_time_sec"] for item in valid) / len(valid), 2
        ),
        "total_tokens_generated": sum(item["tokens_generated"] for item in valid),
        "reasoning_hits": sum(1 for item in valid if item["reasoning_detected"]),
    }


def save_results(args, log_path, results, summary, output_dir):
    output = {
        "config": {
            "tag": args.tag,
            "model_path": str(Path(args.model_path)),
            "server_path": str(Path(args.server_path)),
            "host": args.host,
            "port": args.port,
            "ctx": args.ctx,
            "max_tokens": args.max_tokens,
            "reasoning_mode": args.reasoning_mode,
            "reasoning_budget": args.reasoning_budget,
            "threads": args.threads,
            "threads_batch": args.threads_batch,
            "batch_size": args.batch_size,
            "ubatch_size": args.ubatch_size,
            "cache_type_k": args.cache_type_k,
            "cache_type_v": args.cache_type_v,
            "cache_ram": args.cache_ram,
            "gpu_layers": args.gpu_layers,
            "device": args.device,
            "parallel": args.parallel,
            "mlock": args.mlock,
            "no_mmap": True,
            "flash_attn": args.flash_attn,
            "temperature": args.temperature,
            "seed": args.seed,
            "max_prompts": args.max_prompts,
            "server_log": str(log_path),
        },
        "summary": summary,
        "results": results,
    }

    filename = RESULTS_DIR / f"benchmark_llamaserver_{args.tag}.json"
    with open(filename, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {filename}")
    return filename


def main():
    args = parse_args()
    output_dir = REPO_ROOT

    process, log_path, base_url = start_server(args, output_dir)
    try:
        results = run_benchmark(args, base_url, log_path)
    finally:
        stop_server(process)

    summary = summarize_results(results)
    save_results(args, log_path, results, summary, output_dir)

    print("\n" + "=" * 70)
    print(f"  SUMMARY - {args.tag}")
    print("=" * 70)
    expected = args.max_prompts if args.max_prompts > 0 else len(PROMPTS)
    print(f"  Tests completed: {summary['tests_completed']}/{expected}")
    print(f"  Avg generation speed: {summary['avg_generation_tok_per_sec']:.2f} tok/s")
    if summary["avg_prompt_eval_tok_per_sec"] is not None:
        print(
            f"  Avg prompt eval speed: {summary['avg_prompt_eval_tok_per_sec']:.2f} tok/s"
        )
    print(f"  Avg wall time per prompt: {summary['avg_wall_time_sec']:.2f}s")
    print(f"  Total tokens generated: {summary['total_tokens_generated']}")
    print(f"  Prompts with reasoning traces: {summary['reasoning_hits']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
