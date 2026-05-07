# Research And Decision Log

## Purpose

Capture project decisions, deferred items, assumptions, and open research questions so the team can move faster without losing context.

## Current Build Phase

Backend-first MVP for a single-user adaptive planning system using local SLMs.

## Decisions Already Made

### Product Scope

- Single-user MVP
- Desktop-first MVP
- Text input first
- General-purpose planning engine first
- Focus on simpler structured tasks before harder domains
- Support multiple active plans in MVP
- Allow user edits to generated plans
- Limit user edits to tasks, durations, and dates
- Do not expose dependency editing in MVP

### Model Strategy

- Use existing local 2B and 4B models for now
- Fine-tuned model is not required to begin system development
- Fine-tuning is a later replacement path, not a blocker

### Team Strategy

- Core system can be built now
- Dataset creation can proceed in parallel by other team members
- Research and implementation can move together, but implementation should not wait for all research to finish

### Architecture Direction

- Keep the original four conceptual blocks:
  - SLM Brain
  - Executor
  - Feedbacker
  - Siren
- Add one explicit support layer:
  - State and Policy Layer
- Treat the system as deterministic and state-driven, with SLM assistance rather than prompt-only control

### Delivery Direction

- Python backend first
- Local storage and workflow orchestration first
- UI can remain minimal during early development
- Backend completion matters more immediately than full product polish
- Internal scheduling comes before calendar integration
- Offline-first comes before optional online augmentation

## Deferred Decisions

These are intentionally postponed:

- fine-tuning pipeline
- synthetic dataset as an immediate milestone
- audio input
- native mobile app
- complex domain-specific modes
- advanced multi-agent framework
- complex mathematical feedback formula

## Why These Are Deferred

- They are important but not blockers for validating the core planning engine.
- The team has only 40 to 45 days.
- The biggest unknown is whether the system can create, maintain, and repair plans effectively.

## Current MVP Thesis

If the system can:

- create a realistic plan
- execute it through task state and reminders
- respond intelligently to failure and delay

then the project has validated its core value.

## Example Behavior The MVP Must Handle

Case:

- The plan assumes a seed will germinate in 5 to 7 days.
- The user reports the seed rotted.
- The system should not continue to the next stage blindly.
- The system should identify the broken dependency and revise the plan from the right earlier point.

This is a core test case for adaptive replanning.

## Immediate Research Topics

These are still valuable during MVP development:

1. Best planning heuristics for breaking down tasks.
2. Criteria for asking feedback from the user.
3. Criteria for triggering replanning.
4. Best local model choice for planning quality versus latency.
5. Best local-first offline-friendly framework shape for the backend.

## Current Model Notes

Existing measured direction:

- 2B CPU-only is fast enough for default interaction.
- 4B CPU-only is usable for higher-quality planning but slower.
- Vulkan path on the current hardware is not attractive for this project.

## User Interaction Decisions

- Replanning should ask for user confirmation.
- The system should explain why it suggests a change.
- In-app reminders are sufficient for the first reminder implementation.
- Feedback timing should be dynamic rather than strictly fixed.
- Active-plan conflicts should create a rebalance proposal that the user confirms before schedule truth changes

## Dynamic Feedback Policy Direction

The feedback policy should likely depend on:

- total number of subtasks
- complexity of the task flow
- repeated friction or failure points
- actual time drift versus estimate
- whether the workflow is smooth or repeatedly interrupted

The handwritten formula should be treated as inspiration, not final logic.

Current deterministic MVP direction:

- immediate feedback request on blocked or failed tasks
- immediate feedback request on missed schedule blocks
- faster checkpoints after repeated friction points
- slower checkpoints when the plan is smooth and low-risk

## Planner Architecture Direction

The planning side may use multiple SLM-assisted roles:

- one stage for task decomposition and reasoning
- one stage for replan reasoning

This does not mean the system must become a heavy multi-agent framework. It means the planner logic can be split into specialized reasoning stages.

Important boundary:

- the SLM proposes structure and revision strategy
- deterministic scheduling logic performs final slot placement and conflict checks
- state and policy logic owns approval and transition rules

## Working Assumptions

- The first target hardware class is consumer PCs.
- Current hardware should be treated as a realistic constraint, not a temporary anomaly.
- The system should be designed to avoid paging pressure as much as practical.
- The product value comes from adaptive workflow behavior, not only from raw model intelligence.

## Things We Should Validate Early

- Can the system handle multiple active plans without creating scheduling chaos?
- Can users understand why the system replanned?
- Are reminder timings helpful or annoying?
- Does the user trust the generated plan enough to follow it?
- Can the system gracefully handle niche and uncertain workflows?
- Can the dependency model stay reliable when users edit tasks, dates, and durations but not dependencies?

## Project Risks To Watch

- Overbuilding the model side before validating the workflow side
- Building too generic a planner with weak outputs
- Skipping clear state management and relying too much on prompting alone
- Spending too much time on mobile or dataset work before the core loop works

## Recommended 45-Day Direction

### Phase 1

Lock core entities, plan lifecycle, dependency ownership rules, and replanning rules.

### Phase 2

Build backend services for plan generation, execution state, feedback, and reminders.

### Phase 3

Connect local models and evaluate behavior on representative tasks.

### Phase 4

Add minimal user-facing workflow and polish core experience.

## Open Questions For The Team

1. Which reference scenario should be used first for backend validation even though the product remains general purpose?
2. What is the minimum feedback set that still enables strong replanning?
3. What exact scoring inputs should feed rebalance proposals for two competing active plans?
4. What exactly counts as backend completion for the team?

## Review-Driven Fixes Now Accepted

The following review concerns are accepted and should shape implementation:

- source of truth must be explicit
- component boundaries must be sharpened
- Siren must stay a reminder delivery service, not a logic dump
- dependencies must remain system-owned
- feedback timing needs deterministic MVP triggers
- replanning must separate detection, proposal, and application
- the system needs an explicit lifecycle and data model before deeper backend work
