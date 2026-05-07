# System Design

## Goal

Define a backend-first architecture for an adaptive single-user planning system powered by local SLMs.

## Core Engineering Principle

This system should be treated as a deterministic state-driven planner with SLM assistance, not as a prompt-driven agent that implicitly remembers everything.

That means:

- the SLM proposes plans, revisions, and explanations
- deterministic services validate, store, schedule, and apply those proposals
- the source of truth lives in persistent state, not inside prompts

## Source Of Truth

The State and Policy Layer is the system of record.

Only this layer should own:

- approved plan versions
- current task states
- dependency graph
- schedule allocations
- reminder state
- feedback history
- replanning triggers and pending proposals

The SLM Brain must never directly mutate production state. It only returns structured proposals.

## High-Level Architecture

Main subsystems:

- Interface Layer
- SLM Brain
- Scheduling and Execution Layer
- Feedbacker
- Siren
- State and Policy Layer

Inside the SLM Brain, the planner may use multiple model-assisted roles rather than one single reasoning step.

## Deterministic Control Loop

The core loop should be:

1. User submits or edits a goal.
2. State layer creates a request snapshot.
3. SLM Brain returns a structured proposal.
4. State and Policy Layer validates the proposal.
5. Scheduling and Execution Layer converts approved work into actionable schedule entries.
6. Siren delivers reminders based on approved reminder records.
7. Feedbacker captures execution feedback.
8. State and Policy Layer decides whether to continue, request feedback, shift dates, or propose replanning.
9. If replanning is needed, the SLM Brain returns a replan proposal.
10. User confirms before the new plan version replaces the old schedule.

## 1. Interface Layer

Responsibility:

- collect text input from the user
- collect schedule constraints and preferences
- show plans, statuses, alerts, and history
- capture feedback such as done, delayed, blocked, failed, or note
- present rebalance and replan proposals for approval

MVP form:

- desktop-first
- text input only
- minimal UI is acceptable
- user should retain visible control over plan changes

## 2. SLM Brain

Responsibility:

- understand the user goal
- generate an initial plan proposal
- break plans into tasks and subtasks
- estimate order, dependencies, and effort
- revise plans when feedback invalidates assumptions
- explain why a replan or rebalance was suggested

Model strategy:

- default model: 2B for interactive planning
- optional deeper planning: 4B for higher-quality replanning or harder tasks
- fine-tuned model can replace the current base later

Brain outputs:

- plan title
- milestone list
- tasks and subtasks
- dependencies
- estimated effort
- suggested schedule preferences
- reasoning summary for why the plan was created that way

The Brain should propose, not silently override user intent.

Recommended internal split:

- Goal Reasoner: understands the goal and decomposes it into milestones and subtasks
- Replan Reasoner: revises plans when assumptions break

Recommended boundary:

- the SLM may suggest timing preferences and sequencing logic
- the deterministic scheduler performs final slot placement and conflict checks against approved state

## 3. Scheduling and Execution Layer

Responsibility:

- convert approved planned items into scheduled actionable units
- allocate tasks into available time blocks
- detect clashes with existing approved schedule
- place work into the internal task system
- later sync or export to calendar or reminder systems
- track current active tasks and due dates

MVP behavior:

- create internal schedule first
- optional calendar integration second

This layer should not invent plan logic or rewrite dependencies. It should translate approved decisions into execution state.

Because the MVP supports multiple active plans, this layer must detect schedule conflicts across plans.

Important boundary:

- the planner stack proposes structure and revision strategy
- the scheduler allocates approved work into time
- the state layer stores approved schedule truth

## 4. Feedbacker

Responsibility:

- collect user feedback during execution
- summarize progress and failure signals
- package a structured report back to the SLM Brain and policy logic

Possible feedback inputs:

- done
- delayed
- blocked
- failed
- skipped
- note from user
- observed time spent

Recommended MVP fields:

- status
- actual_time_spent
- difficulty
- confidence
- free-text note

Important terminology:

- friction point = a place where execution becomes difficult, delayed, unstable, or repeatedly blocked

## 5. Siren

Responsibility:

- deliver reminders

The name is good for the project. It should be implemented as a narrow reminder-delivery service rather than mixed with planning code.

Important boundary:

- Siren does not decide policy
- Siren does not detect risk
- Siren only delivers reminder events that were already created by the State and Policy Layer

MVP reminder types:

- upcoming task reminder
- task due soon reminder
- missed task reminder
- overdue task reminder
- feedback request reminder

MVP reminder channel:

- in-app reminders first

## 6. State and Policy Layer

This is the extra layer that should be added explicitly to the original four-part architecture.

Responsibility:

- store all plan state
- validate SLM outputs against schema and rules
- maintain task status truth
- own dependency truth
- create approved schedule truth
- store user availability and commitments
- decide when to ask for feedback
- decide when to trigger replanning
- create pending rebalance and replan proposals
- store task history and plan revisions

This layer is the operational memory and decision boundary controller of the system.

Without this layer, the Brain will have to remember too much, and behavior will become inconsistent.

## Explicit Data Model

Suggested backend entities:

- UserProfile
- Goal
- GoalConstraint
- Plan
- PlanVersion
- Milestone
- Task
- Dependency
- ScheduleBlock
- AvailabilityWindow
- ExternalCommitment
- FeedbackEvent
- Reminder
- RebalanceProposal
- ReplanProposal
- PolicyDecision
- UserEditEvent
- ExecutionLog

### Entity Intent

- Goal = the user intent and high-level outcome
- Plan = stable container for the evolving goal execution
- PlanVersion = one proposed or approved version of the plan
- Task = unit of actionable work
- Dependency = system-owned ordering rule between tasks
- ScheduleBlock = a concrete reservation of time for a task
- FeedbackEvent = structured evidence from execution
- Reminder = future event Siren will deliver
- RebalanceProposal = schedule adjustment proposal caused by conflicts
- ReplanProposal = structural plan revision proposal caused by state change
- PolicyDecision = deterministic record of why the system requested feedback, shifted dates, or proposed replanning

## Plan And Task State Machines

### Plan Lifecycle

- draft
- proposed
- approved
- active
- review_needed
- replan_proposed
- superseded
- completed
- abandoned

### Task Lifecycle

- pending
- scheduled
- in_progress
- done
- delayed
- blocked
- failed
- skipped
- canceled

### Ownership Rules

- only the user can approve a proposed plan version
- only the State and Policy Layer can mark a plan version as active
- only approved plans may create schedule blocks and reminders
- user edits create a UserEditEvent and may force schedule regeneration

## Dependency Ownership Rule

Users should not directly edit dependencies in the MVP.

To keep this safe:

- dependencies are owned by the system
- any user edit to task date or duration triggers dependency validation
- if a dependency looks broken, the system creates a review_needed state
- the user may request re-analysis, but not manually rewrite the graph

This preserves limited user control without making the dependency model fragile.

## Conflict Arbitration Rule

When multiple active plans compete for the same time:

1. Scheduling and Execution Layer detects the collision.
2. State and Policy Layer generates a rebalance request.
3. The planner or scheduler prepares one or more rebalance options.
4. A RebalanceProposal is stored with:
   - affected tasks
   - old schedule
   - proposed new schedule
   - reason summary
5. The user confirms before any approved schedule is replaced.

Recommended weighted inputs:

- due date proximity
- user priority
- dependency criticality
- estimated remaining effort
- manual user locks on tasks or dates

## Feedback Policy V1

Dynamic feedback timing needs concrete triggers, even in the MVP.

Recommended triggers:

- immediate feedback request on `blocked` or `failed`
- immediate feedback request after a missed scheduled block
- early feedback request after two friction points inside the same milestone
- scheduled checkpoint after every 3 to 5 completed tasks for low-complexity flows
- scheduled checkpoint after every 1 to 2 tasks for high-dependency or high-difficulty flows
- review request when actual time drift exceeds a configured threshold

Simple friction signals:

- repeated delay
- blocked status
- confidence drop
- large time overrun
- repeated note text indicating confusion or uncertainty

## Replanning Semantics

The system should separate detection, proposal, and application.

- detection may be automatic
- proposal generation may be automatic
- application must require user confirmation in MVP

This removes the contradiction between "automatic revision" and "user remains in control."

## Canonical Validation Scenario

The product remains general purpose, but the backend should still be validated on one reference flow.

Recommended reference flow:

- user gives a 20 to 30 day learning or project goal
- planner decomposes it into milestones and tasks
- scheduler fits it around existing commitments
- user completes some tasks, delays some tasks, and hits one friction point
- system requests feedback
- system proposes a replan
- user confirms the replan

This is a validation scenario, not a limitation of product scope.

## Main Flows

### Flow A: Create Plan

1. User enters goal and constraints.
2. Interface sends request to SLM Brain.
3. SLM Brain returns a structured plan proposal.
4. State layer validates and stores the proposal as `proposed`.
5. User approves the plan.
6. State layer marks the plan version as `approved`.
7. Scheduling and Execution Layer creates actionable schedule entries.
8. Siren registers reminders.
9. User may manually adjust tasks, durations, or dates before or during execution.

Users should not directly edit dependencies in the MVP.

### Flow B: Execute Plan

1. User works on scheduled tasks.
2. System shows current step and next deadlines.
3. Siren sends reminders at configured times.

### Flow C: Feedback Cycle

1. User marks work as done, delayed, blocked, failed, or adds a note.
2. Feedbacker creates a structured feedback report.
3. State layer records a PolicyDecision.
4. State layer decides whether to continue, shift dates, request more feedback, or propose replanning.
5. If replanning is needed, the system asks the user whether they want to review a replan proposal.
6. If confirmed, a ReplanProposal request is sent to the SLM Brain.

### Flow D: Replan

1. SLM Brain receives the current approved state, dependency graph, and failure or progress report.
2. It revises the plan from the correct dependency point.
3. State layer stores the result as `replan_proposed`.
4. Interface shows a short explanation of why the plan changed.
5. User confirms the replan.
6. State layer creates a new approved PlanVersion and supersedes the old one.
7. Scheduling and Execution Layer updates actionable items.
8. Siren refreshes future reminders.

## Replanning Decision Boundaries

Replanning should happen when:

- a prerequisite task fails
- a task is blocked beyond a threshold
- the user finishes far earlier than expected
- the user falls sufficiently behind the current schedule
- a new major external commitment makes the plan unrealistic
- user explicitly requests a replan

Replanning should not always happen for every tiny slip. Some delays should only shift dates.

## Feasibility Checking

The system should verify:

- available hours versus required hours
- existing commitments versus proposed slots
- dependency ordering
- overload risk from too many tasks on one day
- whether the plan leaves zero recovery buffer
- overlap between multiple active plans

If a plan is not feasible, the system should say so and propose alternatives.

## Persistence Recommendation

Suggested MVP persistence:

- SQLite for local structured data
- optional JSON logs for debugging and plan history exports

Reason:

- easy local setup
- Python-friendly
- enough for single-user MVP

## Backend Recommendation

Suggested Python backend modules:

- planner
- scheduler
- executor
- feedback
- reminders
- policies
- storage
- integrations
- evaluation
- schemas

This is not final code structure, only a recommended direction.

Additional likely modules:

- conflict_resolution
- replan_explainer

## Model Runtime Recommendation

Based on current local benchmarks:

- CPU-only is the preferred runtime on current hardware
- 2B should be default
- 4B should be optional for harder planning calls
- design for no paging pressure, even though Windows still uses virtual address space internally

Operational direction:

- offline-first
- online augmentation later if needed

Practical target:

- avoid memory pressure that causes pagefile-backed slowdown
- keep context and concurrency low in MVP

## Risks

- plan generation may look good but be unrealistic
- repeated replanning may become unstable if task state is weak
- reminder noise may annoy the user
- generic planning may be weak for niche domains without domain guidance
- too much SLM dependence may slow down the product loop

## MVP System Principle

The brain should reason.
The scheduler should allocate time.
The executor should apply approved work.
The feedbacker should observe.
The siren should deliver reminders.
The state and policy layer should decide when the system changes course and remain the source of truth.
The user should remain in control of final plan changes.
