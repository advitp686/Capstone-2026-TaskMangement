import sys
import time
import json
from llama_cpp import Llama, GGML_TYPE_F16, GGML_TYPE_Q4_0, GGML_TYPE_Q8_0


from common_paths import RESULTS_DIR

# Import prompts from existing benchmark script
from benchmark_gemma_chat import SYSTEM_PROMPT, PROMPTS

def run_benchmark(model_path, model_name):
    print(f"\n{'='*70}")
    print(f"  BENCHMARKING llama.cpp (Vulkan): {model_name}")
    print(f"{'='*70}\n")

    try:
        # Map string input to integer types for KV cache overrides
        # 0 = F16, 4 = Q4_0, 8 = Q8_0 (approximate GGML mappings)
        type_map = {
            "f16": 0,
            "q8_0": 8,
            "q4_0": 4
        }

        k_val = type_map.get(sys.argv[3] if len(sys.argv) > 3 else "f16", 0)
        v_val = type_map.get(sys.argv[4] if len(sys.argv) > 4 else "f16", 0)

        # Use kv_overrides to bypass Python type-checking and send flags directly to C++ backend
        kv_overrides = {
            "type_k": k_val,
            "type_v": v_val
        }

        # Load the model
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1,
            n_ctx=2048,
            verbose=False,
            kv_overrides=kv_overrides
        )
    except Exception as e:
        print(f"Failed to load model: {e}")
        return []

    results = []
    
    for test in PROMPTS:
        print(f"\n--- {test['category']} ({test['id']}) ---")
        print(f"Prompt: {test['prompt'][:80]}...")
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": test["prompt"]},
        ]
        
        start = time.time()
        try:
            res = llm.create_chat_completion(
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"id": test["id"], "error": str(e)})
            continue
            
        elapsed = time.time() - start
        
        choice = res["choices"][0]
        response_text = choice.get("message", {}).get("content", "")
        
        # Llama.cpp stats:
        usage = res.get("usage", {})
        eval_count = usage.get("completion_tokens", 0)
        prompt_eval_count = usage.get("prompt_tokens", 0)
        
        tokens_per_sec = eval_count / elapsed if elapsed > 0 else 0
        
        result = {
            "id": test["id"],
            "category": test["category"],
            "model": model_name,
            "response": response_text,
            "wall_time_sec": round(elapsed, 2),
            "tokens_generated": eval_count,
            "generation_tok_per_sec": round(tokens_per_sec, 2),
            "prompt_tokens": prompt_eval_count,
        }
        results.append(result)
        
        print(f"  Wall time: {result['wall_time_sec']}s")
        print(f"  Tokens generated: {eval_count}")
        print(f"  Generation speed (approx wall): {result['generation_tok_per_sec']} tok/s")
        print(f"\n  === FULL RESPONSE ===")
        # Use a more robust way to print to Windows console (avoiding cp1252 errors)
        cleaned_text = response_text[:600].encode('ascii', errors='replace').decode('ascii')
        print(f"  {cleaned_text}")


        if len(response_text) > 600:
            print(f"  ... [{len(response_text) - 600} more chars]")
        print()
        
    return results


def save_results(results, model_tag):
    filename = RESULTS_DIR / f"benchmark_llamacpp_{model_tag}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {filename}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python benchmark_llama_cpp.py <model_name_tag> <path_to_gguf_blob> [type_k] [type_v]")
        print("Example: python benchmark_llama_cpp.py gemma4_e2b models/gemma4/model.gguf q4_0 q4_0")
        sys.exit(1)
    
    tag = sys.argv[1]
    model_path = sys.argv[2]
    
    results = run_benchmark(model_path, tag)
    save_results(results, tag)

    print("\n" + "="*70)
    print(f"  SUMMARY — {tag} (llama.cpp)")
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
