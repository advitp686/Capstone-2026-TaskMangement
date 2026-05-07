# Quantization Study: Gemma 4 for Adaptive Planning

## Objective
To evaluate the trade-off between inference speed (latency) and logical consistency (planning accuracy) across different quantization methods for the Gemma 4 model running on CPU-only hardware.

## Hardware Environment
- **CPU:** [Enter CPU Model, e.g., Intel i7-12700K / AMD Ryzen 5 5600X]
- **RAM:** [Enter RAM size, e.g., 16GB DDR4]
- **Backend:** llama.cpp (CPU-only)
- **OS:** Windows 11

## Evaluation Metrics
1. **Throughput (tok/s):** Average generation speed.
2. **Wall Time (s):** Total time to complete a planning prompt.
3. **Planning Accuracy:** A qualitative score (1-5) based on:
    - Constraint following (e.g., "No work on Sundays").
    - Temporal consistency (Correct day-to-day progression).
    - Mathematical accuracy (Subtask hours adding up to total).

## Benchmark Results

| Model Variant | Quantization Method | Avg Speed (tok/s) | Avg Wall Time (s) | Planning Accuracy (1-5) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gemma-4-E2B-it-Q4_K_M` | Standard K-Quant | 19.76 | 36.56 | 4 | Baseline. Best performance/speed ratio. |
| `gemma-4-E2B-it-Q4_K_M` | KV-Cache Q4_0 | 4.34 | 168.20 | 4 | Significant CPU overhead during de-quantization. |
| `gemma-4-e4b-it-Q4_K_M` | Standard K-Quant | 6.96 | 174.38 | 5 | Higher intelligence, but $\approx 4.7\times$ slower. |

## Detailed Observations
### Standard Q4_K_M Analysis (e2b)
- **Strengths:** Extremely responsive on CPU ($\approx 20$ tok/s). Maintains strong structural integrity in planning tables.
- **Weaknesses:** Slight potential for logic drift in very long (30+ day) plans compared to larger models.

### KV-Cache Optimization Analysis (e2b_q4)
- **Finding:** Contrary to GPU expectations, 4-bit KV-cache quantization caused a massive performance drop on CPU.
- **Reasoning:** The computational cost of de-quantizing the cache for every token generation exceeded the memory bandwidth savings.
- **Conclusion:** Not recommended for CPU-only deployments.

### Larger Model Analysis (e4b)
- **Strengths:** Increased verbosity and deeper reasoning.
- **Weaknesses:** Prohibitive latency for an interactive tool (avg 3 mins per plan).

## Conclusion
The **Gemma 4 e2b (Standard Q4_K_M)** is the optimal model for the Adaptive Planner. It provides the necessary intelligence for task decomposition and replanning while maintaining a fluid user experience on CPU-only hardware. The study proves that for this specific hardware target, weight quantization is effective, but runtime KV-cache quantization is counter-productive.
