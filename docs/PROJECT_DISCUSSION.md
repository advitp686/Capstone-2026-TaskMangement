# Project Discussion

## Working Title

Adaptive Task Management with Local SLMs

## Problem Statement

Many users can start a goal, but they do not know:

- how many steps are actually required
- how much time each step may take
- whether the plan is realistic with their current schedule
- how to recover when reality breaks the original plan

Most task tools store tasks, but they do not actively guide the user through planning, execution, feedback, and replanning.

## Product Vision

Build a local-first adaptive task planning system for a single user that can:

- take a vague natural-language goal
- convert it into a realistic plan with subtasks and deadlines
- check feasibility against availability and existing commitments
- remind the user at the right time
- collect progress and failure feedback
- automatically revise the plan when the situation changes

The system should feel like a planning agent, not just a static to-do app.

Important correction after design review:

The system should not be treated as "the model understands everything." It should be treated as a state-driven application where the model proposes and the backend validates, stores, and applies.

## Current Project Constraints

- Target completion window: 40 to 45 days
- Primary personal contribution: about 4 hours per day
- Team size: about 5 members
- Core implementation language: Python
- Backend-first approach
- Single-user MVP
- Desktop-first MVP
- Text input first
- Existing local models available:
  - Gemma 4 E2B
  - Gemma 4 E4B

## What The User Has Already Clarified

- We do not need fine-tuning immediately.
- We can use the current 2B and 4B models as temporary replacements for a future fine-tuned model.
- Dataset creation is not the first milestone.
- Other team members can work on dataset preparation in parallel while the core system is being built.
- Mobile can be deferred unless the desktop system becomes stable and there is time left.
- Feedback formulas are not fixed yet and should be improved later.
- The MVP should support statuses like done, delayed, and blocked.
- The system should replan when reality changes, not just keep following the original schedule.

## Core Idea In Plain Language

Example:

- The system creates a plan to plant a tree.
- It expects germination after a number of days.
- The user reports that the seed rotted.
- The system should not blindly continue to later tasks.
- It should return to the right earlier step, revise the assumptions, and build a new plan.

This is the core behavior that differentiates the product from a normal planner.

## First Practical User Scope

The long-term vision is general purpose planning, and the MVP should preserve that general-purpose identity.

However, the first validation targets should be simpler, tractable, intermediate-complexity cases such as:

- learning a subject in 30 days
- preparing for an exam
- completing a personal project with milestones
- following a skill roadmap with daily or weekly feedback

This gives us enough structure to validate planning, reminders, and replanning without prematurely narrowing the product to one domain.

## Mode Strategy

The product can later support multiple modes, for example:

- student mode
- developer mode
- creator mode
- farmer mode
- homemaker mode

But the first release should avoid deep domain branching. The system should be general enough to support structured tasks, while future modes can add domain-specific prompts, heuristics, and feedback rules.

The product should not present itself as an education-only tool or a developer-only tool in the MVP.

## Recommended MVP Scope

The MVP should include:

- goal intake via text
- user availability input
- optional current commitments input
- automatic plan creation
- support for multiple active plans
- subtask generation with target dates
- feasibility check against schedule
- user ability to edit generated tasks, durations, and deadlines
- execution tracking
- feedback capture using simple statuses and notes
- replan logic when the plan becomes unrealistic
- reminders for upcoming work and missed work

The user should not be able to directly edit task dependencies in the MVP.

## Not MVP Right Now

- model fine-tuning
- synthetic dataset pipeline as a blocker
- native mobile app
- audio input
- complex multi-agent research framework
- highly specialized domain packs
- advanced feedback math before baseline heuristics exist

## Product Success For The User

At the MVP stage, success means:

- the user can start from a vague goal
- the system gives a plan that feels realistic and useful
- the user can keep the plan updated without friction
- the system responds intelligently when tasks fail, slip, or change
- the user feels guided instead of overwhelmed

The user does not need to fully finish a long mission like UPSC preparation for the MVP to be successful. It is enough if the system can keep the plan alive, relevant, and restartable.

The system should feel like a co-pilot. It should help the user decide, not remove the user's control over the plan.

## Recommended Core Architecture

The original four-part view is good:

- SLM Brain
- Executor
- Feedbacker
- Siren

One more supporting layer should be made explicit:

- State and Policy Layer

Inside the planning side, the system may use multiple SLM roles rather than one single monolithic reasoning call.

This layer stores plan state, task history, schedule assumptions, reminder rules, and replanning decisions. Without it, the four main parts will become tightly coupled and harder to evolve.

## Source Of Truth Rule

The State and Policy Layer should be the source of truth.

This means:

- the SLM Brain returns proposals
- deterministic logic validates those proposals
- approved plan versions, dependencies, schedule blocks, reminders, and feedback history live in persistent state
- no runtime behavior should depend on the model "remembering" past events from prompt context alone

## Why The State And Policy Layer Matters

It answers questions like:

- What is the current truth of the plan?
- Which tasks are active, blocked, failed, or complete?
- When should feedback be requested?
- When is replanning required versus optional?
- Which reminders have already been sent?

This should likely become the backbone of the backend.

## Planning And Scheduling Clarification

The system should not blindly plan in isolation.

If the user already has active plans, the planning flow should receive that context before proposing new time allocations.

This means:

- one part of the planner can decompose the goal into milestones, tasks, and subtasks
- another planning or scheduling stage can decide where those tasks fit in time
- the active plan context should be part of the SLM input for schedule-aware planning

In practice, planning and time placement may be handled by separate SLM-assisted stages.

Even then, final approved timing should still be validated by deterministic scheduling logic.

## Delivery Strategy For 40 To 45 Days

Suggested order:

1. Define backend data model and workflow rules.
2. Build planning and replanning core.
3. Add execution state tracking.
4. Add reminder and feedback loop.
5. Add a minimal desktop interface or CLI/test harness.
6. Evaluate model behavior and adjust prompts.

The immediate engineering target should be backend completion first. The larger project deadline matters, but backend completeness should drive short-term decisions.

## Current Product Position

The project is already clearer than a raw idea. It is best described as:

"A local, adaptive task planning and replanning assistant for a single user, focused on converting goals into realistic plans and keeping those plans alive when reality changes."

## Decisions Confirmed In Discussion

- The MVP remains general purpose.
- The MVP should support multiple active plans.
- Users should be able to edit generated tasks, estimated durations, and deadlines.
- Users should not be able to edit task dependencies in the MVP.
- Replanning should require user confirmation.
- The system should explain why it suggests a plan change.
- In-app reminders are enough for the first reminder implementation.
- Feedback timing should be dynamic rather than fixed after every task.
- Internal scheduling should come before Google Calendar integration.
- The product should be offline-first, with online help later if needed.
- Friction points should influence feedback timing and replanning sensitivity.
- When active plans conflict, the system should propose a rebalance and ask the user to confirm.
- Dependency editing remains system-owned even when user task edits are allowed.
- Replanning detection may be automatic, but applying a new plan version requires confirmation.

## Design Corrections From Review

The review highlighted several important places where the project needed sharper boundaries.

The adopted fixes are:

- clarify that the project is state-driven, not prompt-driven
- make the State and Policy Layer the system of record
- narrow Siren to reminder delivery only
- make conflict handling explicit through rebalance proposals
- keep dependencies system-owned and validate them after user edits
- define deterministic feedback triggers instead of vague "dynamic feedback"
- separate replan detection, proposal, and application
- define a clearer data model and lifecycle states

## Validation Strategy

The product remains general purpose.

However, to avoid an over-broad MVP, the backend should still be tested on one reference scenario at a time. This is a validation tactic, not a product restriction.

Recommended shape of a reference scenario:

- 20 to 30 day goal
- multiple milestones
- at least one delayed task
- at least one friction point
- at least one replan proposal
- user confirmation before plan replacement

## Remaining Open Questions

- Which reference scenario should we use first for backend validation?
- How much external web help should the planner be allowed to use in MVP?
