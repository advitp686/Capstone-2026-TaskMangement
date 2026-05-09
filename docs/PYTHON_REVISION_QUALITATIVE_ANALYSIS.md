# Python Revision Qualitative Analysis

## Purpose

This note documents a beginner-style evaluation of the Adaptive Planner using a realistic user goal:

> I want to revise my Python concepts and become confident again.

The goal of this document is not only to check whether the backend works. It is also to record how the app feels to a regular user, where the workflow is understandable, where it becomes confusing, and what design improvements should come next.

## User Scenario

### Assumed User

- The user is not a developer of the app.
- The user wants help turning a broad study goal into scheduled tasks.
- The user expects the app to guide them, not require knowledge of backend concepts.
- The user may not understand terms like plan version, policy decision, proposal, or replan.

### Goal Entered

Title:

```text
Revise Python concepts
```

Description:

```text
I am a regular user who wants to revise Python basics, data structures, functions, OOP,
file handling, exceptions, modules, and practice problems before becoming confident again.
```

Target window:

```text
2026-05-11 to 2026-05-17
```

Availability:

```text
Monday to Friday, 6:00 PM to 8:00 PM
```

Planner mode:

```text
mock
```

The mock planner was used first because it is faster, deterministic, and easier for product testing.

## How A Regular User Should Use The App

1. Start the backend:

```powershell
python F:\CAPSTONE\scripts\backend\run_api.py
```

2. Open the browser UI:

```text
http://127.0.0.1:8000/
```

3. Click **Check Health**.

Expected result:

```text
ok
```

4. Keep planner mode as **mock** for the first test.

5. Open **Create New Plan** and enter the Python revision goal.

6. Keep **Auto approve and schedule** checked.

7. Click **Create Plan**.

8. Select the new plan from the **Plans** list.

9. Review:

- **Overview** for goal summary and rationale
- **Tasks** for generated tasks
- **Schedule** for the time blocks
- **Reminders** for upcoming reminder records

10. After doing some work, go to **Tasks**, select a task, and submit feedback.

Useful feedback examples:

- `done`: the user completed the task
- `blocked`: the user got stuck and needs help changing the plan
- `delayed`: the user needs more time
- `failed`: the current step did not work

11. If the app recommends a replan, generate the proposal.

12. Go to **Proposals** and either apply or reject it.

## Capability Check Result

A throwaway API run was performed for the Python revision scenario. The current system successfully completed the main lifecycle:

- Backend health check succeeded.
- A new plan was created.
- The plan was auto-approved.
- The scheduler created schedule blocks.
- Reminder records were created.
- Feedback was recorded.
- A blocked task triggered a replan recommendation.
- A replan proposal was generated.
- Applying the proposal superseded the original plan and activated the new plan version.

Observed output:

```text
Initial plan status: active
Initial tasks: 4
Initial schedule blocks: 7
Initial reminders: 7
Blocked feedback action: propose_replan
Proposal type: replan
Proposal status after apply: applied
Original plan final status: superseded
New plan status: active
```

## Generated Task Quality

The current mock planner generated these task themes:

1. Clarify the desired outcome, inputs, and constraints.
2. Prepare resources and unblock prerequisites.
3. Do the core execution work in focused sessions.
4. Review progress, refine work, and close gaps.

These tasks are structurally useful, but they are too generic for a Python revision user. A regular user would expect more concrete study tasks, such as:

- Revise Python syntax, variables, loops, and conditionals.
- Practice lists, dictionaries, tuples, and sets.
- Revise functions, scope, modules, and packages.
- Practice OOP concepts with small examples.
- Review file handling, exceptions, and debugging.
- Solve mixed practice problems.
- Take a short self-test and revise weak areas.

Important finding:

The mock planner currently recognizes words like `learn`, `study`, and `exam`, but not `revise`. Because the user said "revise Python concepts," the planner treated the goal as a generic execution project instead of a learning/revision goal.

## Qualitative Analysis

### What Works

- The app can convert a broad goal into a plan.
- The schedule engine can fit tasks into the user's available time.
- The app stores tasks, schedules, reminders, proposals, and policy decisions.
- The feedback loop works: `blocked` feedback causes the system to recommend replanning.
- The user remains in control because proposals must be applied or rejected.

### What Feels Confusing For A Regular User

- The term **Planner: mock/gemma** is technical.
- The term **Plan Version** may confuse non-developers.
- The user may not understand what **Policy** means.
- The **Proposals** tab is powerful, but it needs more user-friendly language.
- The activity log is useful for developers, but too technical for regular use.
- The generated tasks are not specific enough for a study/revision goal.

### What The User Needs Emotionally

The user is likely asking:

- What should I do today?
- Am I on track?
- What should I do if I get stuck?
- Can I trust this plan?
- Will the app help me recover if I miss a task?

The current UI exposes the backend well, but it should make these questions more visible.

## Design Improvement Notes

### High Priority

- Rename technical labels for normal users.
- Add a clear **Today** or **Next Task** section.
- Show a short explanation after plan creation: "Here is what we scheduled and why."
- Improve learning-goal detection so `revise`, `revision`, `practice`, and `brush up` trigger study-style planning.
- Make generated mock tasks more domain-specific when the goal mentions Python or programming.
- In the feedback flow, explain what will happen before asking the user to generate a replan.

### Medium Priority

- Replace **Policy** with a friendlier label such as **Why This Changed**.
- Replace **Proposals** with **Suggested Changes**.
- Hide raw JSON payloads by default and show them only in a developer mode.
- Add empty-state examples that tell the user what to do next.
- Add beginner-friendly helper text near feedback fields like confidence and difficulty.

### Later

- Add a checklist-style task completion view.
- Add a progress timeline.
- Add an "I missed this task" action.
- Add templates for common goals such as study revision, exam prep, coding practice, fitness, and personal projects.
- Add qualitative export: plan summary, user feedback history, and final reflection.

## Suggested Better User Flow

Current flow:

```text
Create plan -> inspect tabs -> select task -> send feedback -> generate replan -> apply proposal
```

Recommended beginner flow:

```text
Create goal -> See today's task -> Mark progress -> Explain blocker if any -> Review suggested change -> Continue
```

The backend already supports much of this. The main improvement is presentation.

## Evaluation Questions For User Critique

Use these questions while testing the app as a regular user:

1. Was it clear what to enter when creating the plan?
2. Did the generated tasks feel useful for revising Python?
3. Did the schedule feel realistic for your available time?
4. Could you quickly understand what to do first?
5. Was it obvious how to mark a task as done, delayed, blocked, or failed?
6. Did the replan suggestion explain itself clearly?
7. Did applying a proposal feel safe and under your control?
8. Which screen felt most confusing?
9. Which words felt too technical?
10. What would make you trust the app more?

## Actual User Feedback Log

### Round 1: Create Plan Discovery And First Impression

User role:

```text
Regular user trying to create a Python revision plan.
```

Observed feedback:

- The user could not quickly find **Create New Plan**.
- It took around 2 to 3 minutes to discover that plan creation was at the bottom of the left sidebar.
- The page has a large empty area on the right while the plan creation form is compressed into the left side.
- The availability form is not fully comfortable to use in the sidebar.
- Time selection felt inefficient because the minute value could appear as `07` or another non-rounded value, requiring manual correction to `00`.
- After creating the plan, the user did not clearly understand what happened next.
- The user expected the created plan to appear instantly in a clear main view.
- The user expected an obvious way to change the plan or tell the assistant that something was wrong.
- Manual editing exists, but the user wanted a more natural request-based interaction, such as asking the assistant to change something.

Interpretation:

The first major issue is not backend capability. It is onboarding and workflow clarity. A regular user expects the app to start with the main action: creating or continuing a plan. The current UI exposes developer controls first, while the most important user action is visually hidden lower in the sidebar.

Design implications:

- **Create New Plan** should become a primary first-screen action.
- The plan creation form should use the main content area or a clear modal, not only the bottom of the sidebar.
- The app should show a clear success state after creation: "Your plan is ready. Here is what to do first."
- The created plan should become immediately selected and visible in a task-first view.
- Availability input needs a simpler preset flow, such as "Every day", "Weekdays", or "Custom".
- Time inputs should default to rounded times and avoid awkward minute values.
- The app needs a visible "Request a change" or "Ask to adjust this plan" interaction, even if the first version only maps that request into an edit/replan workflow.

Potential redesign hypothesis:

```text
First screen should be:
1. What do you want to plan?
2. When do you want to finish?
3. When are you free?
4. Create my plan

After creation, the app should show:
1. Today's / next task
2. Full plan
3. Buttons: Done, Stuck, Delay, Change plan
```

### Round 2: Task List And Plan Quality

User role:

```text
Regular user inspecting the generated task plan for Python revision.
```

Observed feedback:

- The **Tasks** screen feels like raw tabular data, not a usable plan.
- The `Id` column has no value for a normal user and creates confusion.
- The repeated **Select** button is unclear because the user does not know why a task must be selected.
- The generated task list does not feel like a roadmap with Step 1, Step 2, Step 3, and so on.
- The plan feels too generic and not intelligent enough for a complex goal like revising Python.
- The current tasks would be acceptable for a simple procedural goal, such as making tea, but not for a learning goal.
- The plan does not specify Python topics, starting points, subtopics, practice activities, or progression.
- The system did not ask clarifying questions before creating the plan.
- The system did not appear to reason about the complexity of learning Python.
- The user correctly inferred that the mock planner is not using an LLM.
- The user expected deeper planning, possibly with internet or external knowledge support.
- The time estimates feel vague and unsupported.
- The plan looks formally complete, but it is confusing and not practically usable.

Generated tasks that caused this reaction:

```text
1. Revise Python Concepts: Clarify the desired outcome, inputs, and constraints
2. Revise Python Concepts: Prepare resources and unblock prerequisites
3. Revise Python Concepts: Do the core execution work in focused sessions
4. Revise Python Concepts: Review progress, refine work, and close gaps
```

Interpretation:

The current task presentation and mock plan quality are both failing for the Python revision scenario. The backend can produce valid records, but the user does not experience those records as a meaningful plan. For learning goals, the app needs a roadmap structure, topic breakdown, practice tasks, milestones, and clearer sequencing.

The mock planner is useful for testing backend flow, but it should not be presented as if it can create a high-quality plan for a complex goal. If mock mode remains visible, the UI should clearly frame it as a demo/testing planner.

Design implications:

- Replace the task table as the primary user view with a roadmap or step-by-step plan view.
- Hide technical IDs from normal users.
- Replace **Select** with a clearer action such as **Open**, **Work on this**, or make the whole task card clickable.
- Add visible step numbers, milestones, and topic groups.
- For learning goals, generate topic-specific tasks and practice checkpoints.
- Add a clarification step before plan generation for broad goals.
- Ask questions such as:
  - What is your current level?
  - How many days do you have?
  - Do you want theory, practice, or both?
  - Which topics are weakest?
  - Are you preparing for an exam, interview, project, or general revision?
- Add a quality warning or label for mock mode.
- Make time estimates explainable: why 90 minutes, what the user should accomplish in that block, and what counts as complete.
- Consider a separate **Learning Plan** layout instead of treating all plans as flat task lists.

Potential better task structure for this scenario:

```text
Milestone 1: Refresh Python Basics
- Step 1: Revise variables, data types, input/output, and operators.
- Step 2: Practice conditionals and loops with 5 small problems.

Milestone 2: Core Data Structures
- Step 3: Revise lists, tuples, sets, and dictionaries.
- Step 4: Solve mixed data-structure problems.

Milestone 3: Functions And Code Organization
- Step 5: Revise functions, scope, modules, and imports.
- Step 6: Refactor small scripts into reusable functions.

Milestone 4: Intermediate Python
- Step 7: Practice file handling and exceptions.
- Step 8: Revise OOP basics with a small class-based exercise.

Milestone 5: Consolidation
- Step 9: Solve a mixed mini-project.
- Step 10: Review weak areas and create a final revision sheet.
```

### Round 3: Schedule View

User role:

```text
Regular user checking when the Python revision work is scheduled.
```

Observed feedback:

- The **Schedule** tab is understandable.
- The user can see when each study block starts and ends.
- The schedule feels useful because it answers the practical question: "When do I need to do this?"
- The user does not need full topic detail inside the schedule view. The schedule can show the block/task, while detailed task instructions can remain in the task view.
- The time blocks are clear.
- The schedule can motivate the user because it shows the next day or next block of work.
- The user suggested using different colors for different plans or subjects.

Example color idea:

```text
Python learning: blue
Maths: green
Other lesson/activity: white or neutral
```

Interpretation:

The schedule view is closer to what a regular user expects. It does not need to carry all learning details; it mainly needs to show time, plan identity, and what block is next. The main missing improvement is visual grouping, especially when multiple plans exist.

Design implications:

- Keep schedule as a time-block view.
- Do not overload schedule rows with detailed instructions.
- Add plan/category color coding.
- Add a small legend for active plans or subjects.
- Consider showing the next upcoming block at the top.
- Hide technical task IDs in schedule labels for normal users.
- Improve task names first, because schedule usefulness depends on readable task labels.

### Round 4: Feedback, Replan Prompt, And Missing Assistant Behavior

User role:

```text
Regular user reporting that a task is blocked because it is too vague.
```

Feedback entered:

```text
Status: blocked
Actual minutes: 170
Difficulty: 3
Confidence: 0.5
Note: I am stuck because the task is too vague. I need specific Python topics and practice exercises.
```

Observed feedback:

- It was clear that the user could report a problem by selecting `blocked` and writing a note.
- The feedback concept is useful.
- The app moved into the proposal/replan flow after feedback.
- The app did not clearly explain why it made the decision.
- The app did not show enough reasoning for why a replan was recommended.
- The app did not ask follow-up questions to clarify the problem.
- The system took the note and directly replanned, instead of diagnosing the issue first.
- Difficulty and confidence fields are useful ideas, but raw number inputs feel weak.
- Difficulty and confidence would feel better as sliders.
- The same earlier issue remains: if new tasks are added, the process still feels like a mechanical task table.
- The user feels the idea is good, but the current loop has important gaps.

Interpretation:

The feedback form is understandable, but the adaptive intelligence layer is not yet visible enough. A regular user expects the assistant to ask why the problem happened, clarify the user's state, and then propose a better plan. The current system behaves more like a rule-based workflow: blocked feedback triggers replan. That proves the backend loop works, but it does not yet feel like an intelligent planning assistant.

Design implications:

- Add a visible decision explanation after feedback.
- Show a message such as: "Because this task is blocked and confidence is low, I recommend revising the plan."
- Before generating a replan, ask clarifying questions when the note is vague or the task itself is vague.
- Clarifying questions should support multiple-choice answers with a custom option.
- Replace difficulty and confidence number fields with sliders.
- Show the user's feedback history in a human-readable way.
- Avoid using browser `alert` / `confirm` dialogs for important product decisions.
- Replace the popup with an in-app review panel explaining:
  - what the user reported
  - what the system understood
  - why it recommends a replan
  - what will change if the user accepts

### Round 5: Gemma, Agentic Behavior, And Reference Material Expectations

User role:

```text
Power user/developer evaluating whether the real model-backed system can improve the plan quality.
```

Observed feedback:

- Earlier Gemma results did not provide a sufficiently good plan.
- The user believes improving the core application flow is necessary because Gemma alone cannot fix the system.
- The user expects more agent-like behavior:
  - a chat assistant that knows current plans and schedules
  - ability to discuss mistakes in the plan
  - ability to propose replanning from chat
  - ability to decide or recommend plan changes based on context
- Web search or external knowledge support feels missing for richer planning.
- The app should show a working animation while the model is processing.
- The app should show an estimated time to complete long model operations.
- The processing message currently mentions CPU, but the user expects the app to reflect the actual local model/runtime configuration.
- The desired 2B local model/runtime configuration mentioned by the user:

```text
--cache-type-k f16
--cache-type-v f16
--flash-attn off
-c 8192
-dev Vulkan1
-ngl 99
--reasoning on
--reasoning-format deepseek
--reasoning-budget 256
```

- The user wants an extra reference-information area where files can be added for a plan.
- Useful reference inputs:
  - PDF files
  - Markdown files
  - other study material
- If the system does not have enough information, it should ask questions instead of producing a vague plan.
- The user specifically likes a Codex-style question pattern:
  - recommended option first
  - 2 to 3 multiple-choice options
  - final custom/free-text option

Interpretation:

The product expectation is moving beyond "generate tasks" into "planning assistant with memory, context, and tools." For complex learning goals, the app needs to gather more user context and possibly reference material before planning. The model should not be expected to rescue a weak product flow by itself. The app must decide when to ask questions, when to use references, when to search, and when to propose changes.

Design implications:

- Add an assistant/chat panel connected to the current selected plan.
- Add plan-aware chat commands such as:
  - "make this more specific"
  - "I am stuck"
  - "change my schedule"
  - "add practice problems"
  - "make this easier"
  - "replan from this point"
- Add a reference material section during plan creation.
- Add a plan-intake stage before generation:
  - user level
  - deadline
  - desired depth
  - weak areas
  - source material
  - output preference
- Add in-app clarification cards before replan.
- Add model-runtime status that accurately reflects the chosen backend.
- Add long-running-operation UI with progress/estimated wait messaging.
- Decide whether web search is an explicit future feature or out of MVP scope.

## Current Verdict

The system is capable of preparing a task plan, scheduling it, receiving user feedback, and helping the user continue after a blocker.

However, for a regular user, the current app is still closer to a developer-facing MVP than a polished planning assistant. The backend loop is promising, but the UI should become more task-first, less version-first, and more explicit about what the user should do next.

For the Python revision use case, the most important next improvement is better task specificity. A user should see actual Python revision topics, not only generic planning phases.
