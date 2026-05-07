"""
Gemma 4 Chat Benchmark for Task Management Use Case
Uses /api/chat endpoint with system prompt for proper instruction following.
"""
import requests
import json
import time
import sys

from common_paths import RESULTS_DIR

OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM_PROMPT = (
    "You are a task management AI assistant. Your job is to help users plan, "
    "organize, and manage their tasks and goals. You break down complex goals "
    "into actionable subtasks with realistic time estimates and deadlines. "
    "You respond in English. Be structured, concise, and practical."
)

PROMPTS = [
    {
        "id": "T1_task_decomposition",
        "category": "Task Decomposition",
        "prompt": (
            "I want to build a personal portfolio website. I have 14 days. "
            "Break this down into subtasks with estimated hours for each subtask. "
            "Return the result as a structured plan with daily deadlines."
        ),
    },
    {
        "id": "T2_priority_assignment",
        "category": "Priority Assignment",
        "prompt": (
            "I have these tasks for today:\n"
            "1. Submit assignment (due tonight)\n"
            "2. Grocery shopping\n"
            "3. Gym workout\n"
            "4. Study for exam (exam in 3 days)\n"
            "5. Call dentist for appointment\n"
            "6. Fix laptop charger\n"
            "Assign priority (High/Medium/Low) to each and suggest an optimal order."
        ),
    },
    {
        "id": "T3_replanning",
        "category": "Adaptive Replanning",
        "prompt": (
            "I had a 10-day plan to learn Python with these subtasks:\n"
            "Day 1-2: Variables & Data Types (Done)\n"
            "Day 3-4: Control Flow (Done)\n"
            "Day 5-6: Functions (Not started)\n"
            "Day 7-8: OOP (Not started)\n"
            "Day 9-10: File I/O & Projects (Not started)\n\n"
            "I completed Day 1-4 work in just 2 days. I now have 8 remaining days. "
            "Reorganize my plan to make better use of the extra time."
        ),
    },
    {
        "id": "T4_conflict_detection",
        "category": "Schedule Conflict Detection",
        "prompt": (
            "I have an existing schedule:\n"
            "- Mon to Fri: College 9AM-4PM\n"
            "- Mon,Wed,Fri: Gym 5PM-6:30PM\n"
            "- Sat: Part-time job 10AM-6PM\n"
            "- Sun: Free\n\n"
            "I want to add a new 3-week plan to prepare for a certification exam "
            "requiring 2 hours of study per day. "
            "Check for conflicts and suggest a feasible schedule."
        ),
    },
    {
        "id": "T5_feedback_reorg",
        "category": "Feedback-Based Reorganization",
        "prompt": (
            "I'm working on a machine learning project. Here's my status:\n"
            "Subtask 1: Data collection - COMPLETED (took 2 days, estimated 3)\n"
            "Subtask 2: Data cleaning - COMPLETED (took 4 days, estimated 2) - data was messier than expected\n"
            "Subtask 3: Feature engineering - IN PROGRESS\n"
            "Subtask 4: Model training - NOT STARTED\n"
            "Subtask 5: Evaluation - NOT STARTED\n"
            "Subtask 6: Deployment - NOT STARTED\n"
            "Total deadline: 20 days from start. 6 days have passed.\n"
            "Based on this feedback, reassess the remaining timeline and suggest adjustments."
        ),
    },
    {
        "id": "T6_linear_algebra_ml_plan",
        "category": "Study Planning",
        "prompt": (
            "I want to prepare linear algebra for machine learning in 20 days while attending classes. "
            "I can study 2 hours on weekdays and 4 hours on weekends. "
            "Topics I need to cover are vectors, matrices, matrix multiplication, determinants, "
            "eigenvalues and eigenvectors, SVD, gradients, and practice problems. "
            "Create a 20-day study plan with daily goals, revision checkpoints, and one mock test."
        ),
    },
    {
        "id": "T7_exam_recovery_plan",
        "category": "Recovery Planning",
        "prompt": (
            "I have 18 days left before a machine learning exam. "
            "My original plan was to finish linear algebra, probability, and model evaluation by now, "
            "but I lost 5 days due to illness and only completed half of linear algebra. "
            "I can now study 3 hours on weekdays and 6 hours on weekends. "
            "Rebuild my plan so I can still cover the most important topics, practice questions, "
            "and leave time for two revision days."
        ),
    },
]


def run_benchmark(model_name):
    results = []
    print(f"\n{'='*70}")
    print(f"  BENCHMARKING (CHAT MODE): {model_name}")
    print(f"{'='*70}\n")

    for test in PROMPTS:
        print(f"\n--- {test['category']} ({test['id']}) ---")
        print(f"Prompt: {test['prompt'][:80]}...")

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": test["prompt"]},
            ],
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1024,
            },
        }

        try:
            start = time.time()
            resp = requests.post(OLLAMA_URL, json=payload, timeout=600)
            elapsed = time.time() - start
            data = resp.json()

            response_text = data.get("message", {}).get("content", "")
            total_duration_ns = data.get("total_duration", 0)
            eval_count = data.get("eval_count", 0)
            eval_duration_ns = data.get("eval_duration", 1)
            prompt_eval_count = data.get("prompt_eval_count", 0)
            prompt_eval_duration_ns = data.get("prompt_eval_duration", 1)

            tokens_per_sec = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0
            prompt_tps = (prompt_eval_count / (prompt_eval_duration_ns / 1e9)) if prompt_eval_duration_ns > 0 else 0

            result = {
                "id": test["id"],
                "category": test["category"],
                "model": model_name,
                "response": response_text,
                "wall_time_sec": round(elapsed, 2),
                "total_duration_sec": round(total_duration_ns / 1e9, 2),
                "tokens_generated": eval_count,
                "generation_tok_per_sec": round(tokens_per_sec, 2),
                "prompt_tokens": prompt_eval_count,
                "prompt_eval_tok_per_sec": round(prompt_tps, 2),
            }
            results.append(result)

            print(f"  Wall time: {result['wall_time_sec']}s")
            print(f"  Tokens generated: {eval_count}")
            print(f"  Generation speed: {result['generation_tok_per_sec']} tok/s")
            print(f"  Prompt eval speed: {result['prompt_eval_tok_per_sec']} tok/s")
            print(f"\n  === FULL RESPONSE ===")
            print(f"  {response_text[:600]}")
            if len(response_text) > 600:
                print(f"  ... [{len(response_text) - 600} more chars]")
            print()

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "id": test["id"],
                "category": test["category"],
                "model": model_name,
                "error": str(e),
            })

    return results


def save_results(results, model_tag):
    filename = RESULTS_DIR / f"benchmark_chat_{model_tag}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {filename}")


if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "gemma4:e2b"
    tag = model.replace(":", "_").replace("/", "_")
    results = run_benchmark(model)
    save_results(results, tag)

    print("\n" + "="*70)
    print(f"  SUMMARY — {model}")
    print("="*70)
    valid = [r for r in results if "error" not in r]
    if valid:
        avg_speed = sum(r["generation_tok_per_sec"] for r in valid) / len(valid)
        avg_time = sum(r["wall_time_sec"] for r in valid) / len(valid)
        total_tokens = sum(r["tokens_generated"] for r in valid)
        print(f"  Tests completed: {len(valid)}/{len(results)}")
        print(f"  Avg generation speed: {avg_speed:.2f} tok/s")
        print(f"  Avg wall time per prompt: {avg_time:.2f}s")
        print(f"  Total tokens generated: {total_tokens}")
    print("="*70)
