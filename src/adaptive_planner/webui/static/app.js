(function () {
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const DEFAULT_AVAILABILITY = {
    0: ["18:00:00", "20:00:00"],
    1: ["18:00:00", "20:00:00"],
    2: ["18:00:00", "20:00:00"],
    3: ["18:00:00", "20:00:00"],
  };

  const state = {
    currentPlanId: null,
    currentTaskId: null,
    currentProposalId: null,
    planDetail: null,
    currentTab: "overview",
  };

  const el = {};

  document.addEventListener("DOMContentLoaded", () => {
    cacheElements();
    buildAvailabilityGrid();
    seedDefaultDates();
    bindEvents();
    setActiveTab("overview");
    refreshAll();
  });

  function cacheElements() {
    const ids = [
      "plannerMode", "healthButton", "refreshButton", "deliverRemindersButton", "healthStatus",
      "refreshPlansButton", "planList", "createPanel", "createPlanForm", "createTitle",
      "createDescription", "createStartDate", "createEndDate", "availabilityGrid", "autoApprove",
      "currentPlanTitle", "approvePlanButton", "reschedulePlanButton", "refreshPlanButton",
      "planSummary", "overviewNarrative", "generateReplanButton", "replanTaskId", "replanReason",
      "tasksTableBody", "selectedTaskLabel", "taskWorkspaceEmpty", "taskWorkspace", "editTaskForm",
      "editTitle", "editMinutes", "editTargetDate", "regenerateSchedule", "feedbackForm",
      "feedbackStatus", "feedbackMinutes", "feedbackDifficulty", "feedbackConfidence", "feedbackNote",
      "proposalsTableBody", "proposalWorkspaceEmpty", "proposalWorkspace", "selectedProposalLabel",
      "proposalPayload", "applyProposalButton", "rejectProposalButton", "dependenciesPanel",
      "scheduleTableBody", "remindersTableBody", "policyTableBody", "activityLog",
      "loadingOverlay", "loadingTitle", "loadingHint",
      "backendIndicator", "backendDot", "backendLabel", "taskStatusBadge",
    ];
    for (const id of ids) {
      el[id] = document.getElementById(id);
    }
    el.tabButtons = Array.from(document.querySelectorAll("[data-tab-target]"));
    el.tabPanes = Array.from(document.querySelectorAll(".tab-pane"));
  }

  function bindEvents() {
    el.healthButton.addEventListener("click", checkHealth);
    el.refreshButton.addEventListener("click", refreshAll);
    el.deliverRemindersButton.addEventListener("click", deliverReminders);
    el.refreshPlansButton.addEventListener("click", refreshPlans);
    el.createPlanForm.addEventListener("submit", handleCreatePlan);
    el.approvePlanButton.addEventListener("click", approvePlan);
    el.reschedulePlanButton.addEventListener("click", reschedulePlan);
    el.refreshPlanButton.addEventListener("click", refreshSelectedPlan);
    el.generateReplanButton.addEventListener("click", generateReplan);
    el.editTaskForm.addEventListener("submit", saveTaskEdit);
    el.feedbackForm.addEventListener("submit", sendFeedback);
    el.applyProposalButton.addEventListener("click", () => actOnProposal("apply"));
    el.rejectProposalButton.addEventListener("click", () => actOnProposal("reject"));
    el.tabButtons.forEach((button) => {
      button.addEventListener("click", () => setActiveTab(button.dataset.tabTarget));
    });
  }

  function setActiveTab(name) {
    state.currentTab = name;
    el.tabButtons.forEach((button) => {
      button.classList.toggle("active", button.dataset.tabTarget === name);
    });
    el.tabPanes.forEach((pane) => {
      pane.classList.toggle("active", pane.id === `tab-${name}`);
    });
  }

  async function refreshAll() {
    await checkHealth();
    await refreshPlans();
    if (state.currentPlanId) {
      await refreshSelectedPlan();
    }
  }

  async function checkHealth() {
    try {
      const health = await apiRequest("/health");
      el.healthStatus.textContent = health.status || "unknown";
      log(`Health check succeeded: ${health.status}.`);
    } catch (error) {
      el.healthStatus.textContent = "offline";
      showError(error);
    }
  }

  async function refreshPlans() {
    try {
      const plans = await apiRequest("/plans");
      renderPlanList(plans);
    } catch (error) {
      showError(error);
    }
  }

  async function refreshSelectedPlan() {
    if (!state.currentPlanId) {
      renderEmptyPlan();
      return;
    }
    try {
      const detail = await apiRequest(`/plans/${state.currentPlanId}`);
      state.planDetail = detail;
      renderPlanDetail(detail);
      log(`Loaded plan detail for plan version ${state.currentPlanId}.`);
    } catch (error) {
      showError(error);
    }
  }

  async function handleCreatePlan(event) {
    event.preventDefault();
    const payload = {
      title: el.createTitle.value.trim(),
      description: el.createDescription.value.trim(),
      target_start_date: el.createStartDate.value,
      target_end_date: el.createEndDate.value,
      availability: collectAvailability(),
      constraints: {},
      planner: plannerMode(),
      auto_approve: el.autoApprove.checked,
    };

    if (!payload.title || !payload.description) {
      window.alert("Title and description are required.");
      return;
    }

    try {
      setLoading(true, "Creating plan...", "Gemma planning can take up to a minute on CPU.");
      const response = await apiRequest("/plans", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.currentPlanId = response.plan_version_id;
      state.currentTaskId = null;
      state.currentProposalId = null;
      if (el.createPanel) {
        el.createPanel.open = false;
      }
      log(`Created plan ${response.plan_version_id} with status ${response.status}.`);
      await refreshPlans();
      await refreshSelectedPlan();
      setActiveTab("overview");
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function approvePlan() {
    if (!requirePlan()) {
      return;
    }
    try {
      setLoading(true, "Approving plan...", "Scheduling can take a few seconds.");
      const response = await apiRequest(
        `/plans/${state.currentPlanId}/approve?planner=${encodeURIComponent(plannerMode())}`,
        { method: "POST" },
      );
      log(`Approved plan ${state.currentPlanId}. Scheduled blocks=${response.scheduled_blocks}.`);
      if (response.conflicts.length) {
        log(`Approval conflicts: ${JSON.stringify(response.conflicts)}`);
      }
      await refreshPlans();
      await refreshSelectedPlan();
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function reschedulePlan() {
    if (!requirePlan()) {
      return;
    }
    try {
      setLoading(true, "Rescheduling plan...", "Scheduling can take a few seconds.");
      const response = await apiRequest(
        `/plans/${state.currentPlanId}/reschedule?planner=${encodeURIComponent(plannerMode())}`,
        { method: "POST" },
      );
      log(`Rescheduled plan ${state.currentPlanId}. Conflicts=${response.conflicts.length}.`);
      if (response.conflicts.length) {
        log(`Reschedule conflicts: ${JSON.stringify(response.conflicts)}`);
      }
      await refreshPlans();
      await refreshSelectedPlan();
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function generateReplan() {
    if (!requirePlan()) {
      return;
    }
    const reason = el.replanReason.value.trim();
    if (!reason) {
      window.alert("A replan reason is required.");
      return;
    }
    try {
      setLoading(true, "Generating replan...", "Gemma replanning can take up to a minute on CPU.");
      const proposal = await apiRequest(`/plans/${state.currentPlanId}/replan`, {
        method: "POST",
        body: JSON.stringify({
          planner: plannerMode(),
          trigger_task_id: parseOptionalInt(el.replanTaskId.value),
          trigger_reason: reason,
        }),
      });
      state.currentProposalId = proposal.id;
      log(`Generated replan proposal #${proposal.id}.`);
      await refreshSelectedPlan();
      setActiveTab("proposals");
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function saveTaskEdit(event) {
    event.preventDefault();
    if (!requireTask()) {
      return;
    }
    try {
      setLoading(true, "Saving task edit...", "Updating schedule if requested.");
      const response = await apiRequest(
        `/tasks/${state.currentTaskId}?planner=${encodeURIComponent(plannerMode())}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            title: emptyToNull(el.editTitle.value),
            estimated_minutes: parseOptionalInt(el.editMinutes.value),
            target_date: emptyToNull(el.editTargetDate.value),
            regenerate_schedule: el.regenerateSchedule.checked,
          }),
        },
      );
      log(`Edited task ${state.currentTaskId}. Plan status=${response.status}.`);
      await refreshPlans();
      await refreshSelectedPlan();
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function sendFeedback(event) {
    event.preventDefault();
    if (!requireTask()) {
      return;
    }
    try {
      setLoading(true, "Sending feedback...", "Updating plan status and policy decisions.");
      const response = await apiRequest(
        `/tasks/${state.currentTaskId}/feedback?planner=${encodeURIComponent(plannerMode())}`,
        {
          method: "POST",
          body: JSON.stringify({
            status: el.feedbackStatus.value,
            actual_minutes: parseOptionalInt(el.feedbackMinutes.value),
            difficulty: parseOptionalInt(el.feedbackDifficulty.value),
            confidence: parseOptionalFloat(el.feedbackConfidence.value),
            note: el.feedbackNote.value.trim(),
          }),
        },
      );
      log(`Feedback on task ${state.currentTaskId}: action=${response.action}.`);
      await refreshPlans();
      await refreshSelectedPlan();

      if (response.action === "propose_replan") {
        el.replanTaskId.value = String(state.currentTaskId);
        el.replanReason.value = response.reason;
        if (window.confirm("Backend recommends a replan proposal. Generate it now?")) {
          await generateReplan();
        }
      }
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function actOnProposal(action) {
    if (!requireProposal()) {
      return;
    }
    try {
      setLoading(true, `${capitalize(action)}ing proposal...`, "Applying changes to the schedule.");
      const proposal = await apiRequest(
        `/proposals/${state.currentProposalId}?planner=${encodeURIComponent(plannerMode())}`,
        {
          method: "POST",
          body: JSON.stringify({ action }),
        },
      );
      if (action === "apply" && proposal.proposal_type === "replan") {
        const newPlanVersionId = proposal.payload && proposal.payload.new_plan_version_id;
        if (newPlanVersionId) {
          state.currentPlanId = Number(newPlanVersionId);
        }
      }
      log(`${capitalize(action)}d proposal #${state.currentProposalId}.`);
      await refreshPlans();
      await refreshSelectedPlan();
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function deliverReminders() {
    try {
      setLoading(true, "Delivering reminders...", "Marking due reminders as delivered.");
      const result = await apiRequest("/reminders/deliver", {
        method: "POST",
        body: JSON.stringify({ limit: 20 }),
      });
      log(`Delivered ${result.delivered_count} reminders.`);
      if (result.reminders.length) {
        const lines = result.reminders.map((item) => `${item.reminder_type}: ${item.task_title}`);
        window.alert(lines.join("\n"));
      }
      await refreshSelectedPlan();
      setActiveTab("reminders");
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  function renderPlanList(plans) {
    el.planList.innerHTML = "";
    if (!plans.length) {
      el.planList.innerHTML = '<div class="empty-state">No plans yet.</div>';
      return;
    }

    for (const plan of plans) {
      const item = document.createElement("div");
      item.className = "plan-item" + (plan.plan_version_id === state.currentPlanId ? " active" : "");
      item.innerHTML = `
        <div><strong>#${plan.plan_version_id}</strong> ${escapeHtml(plan.title)}</div>
        <div class="subtle">${escapeHtml(plan.status)} | ${escapeHtml(plan.target_start_date)} -> ${escapeHtml(plan.target_end_date)}</div>
        <div class="subtle">${escapeHtml(plan.summary || "")}</div>
      `;

      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Select";
      button.addEventListener("click", async () => {
        state.currentPlanId = plan.plan_version_id;
        state.currentTaskId = null;
        state.currentProposalId = null;
        await refreshPlans();
        await refreshSelectedPlan();
      });
      item.appendChild(button);
      el.planList.appendChild(item);
    }
  }

  function renderPlanDetail(detail) {
    const plan = detail.plan;
    const taskMap = new Map(detail.tasks.map((task) => [task.id, task]));

    el.currentPlanTitle.textContent = `${plan.title} (#${plan.plan_version_id})`;
    const progress = computeProgress(detail.tasks);
    el.planSummary.innerHTML = [
      metricCard("Status", plan.status),
      metricCard("Window", `${plan.target_start_date} -> ${plan.target_end_date}`),
      metricCard("Tasks", String(detail.tasks.length)),
      progressCard(progress),
    ].join("");

    el.overviewNarrative.textContent = [
      `Goal: ${plan.goal_title}`,
      "",
      `Summary: ${plan.summary || "No summary yet."}`,
      "",
      `Rationale: ${plan.rationale || "No rationale yet."}`,
      "",
      `Description: ${plan.goal_description || "No description."}`,
    ].join("\n");

    renderTasks(detail.tasks);
    renderProposals(detail.proposals);
    renderDependencies(detail.dependencies, taskMap);
    renderScheduleBlocks(detail.schedule_blocks, taskMap);
    renderReminders(detail.reminders, taskMap);
    renderPolicyDecisions(detail.policy_decisions, taskMap);
  }

  function renderTasks(tasks) {
    if (!tasks.some((task) => task.id === state.currentTaskId)) {
      state.currentTaskId = null;
    }

    el.tasksTableBody.innerHTML = "";
    if (!tasks.length) {
      el.tasksTableBody.innerHTML = '<tr><td colspan="6">No tasks.</td></tr>';
      setTaskWorkspace(null);
      return;
    }

    for (const task of tasks) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><button type="button">${task.id === state.currentTaskId ? "Selected" : "Select"}</button></td>
        <td>${task.id}</td>
        <td>${escapeHtml(task.status)}</td>
        <td>${escapeHtml(task.title)}</td>
        <td>${task.estimated_minutes}</td>
        <td>${escapeHtml(task.target_date || "")}</td>
      `;
      row.querySelector("button").addEventListener("click", () => {
        state.currentTaskId = task.id;
        setTaskWorkspace(task);
        renderTasks(state.planDetail.tasks);
        setActiveTab("tasks");
      });
      el.tasksTableBody.appendChild(row);
    }

    const selectedTask = tasks.find((task) => task.id === state.currentTaskId) || null;
    setTaskWorkspace(selectedTask);
  }

  function setTaskWorkspace(task) {
    if (!task) {
      el.selectedTaskLabel.textContent = "No task selected";
      updateTaskStatusBadge(null);
      el.taskWorkspace.classList.add("hidden");
      el.taskWorkspaceEmpty.classList.remove("hidden");
      return;
    }

    el.selectedTaskLabel.textContent = `Selected task #${task.id}: ${task.title}`;
    updateTaskStatusBadge(task.status);
    el.editTitle.value = task.title || "";
    el.editMinutes.value = String(task.estimated_minutes || "");
    el.editTargetDate.value = task.target_date || "";
    el.feedbackNote.value = `Revise plan after issue with task: ${task.title}`;
    el.replanTaskId.value = String(task.id);
    el.taskWorkspace.classList.remove("hidden");
    el.taskWorkspaceEmpty.classList.add("hidden");
  }

  function renderProposals(proposals) {
    if (!proposals.some((proposal) => proposal.id === state.currentProposalId)) {
      state.currentProposalId = null;
    }

    el.proposalsTableBody.innerHTML = "";
    if (!proposals.length) {
      el.proposalsTableBody.innerHTML = '<tr><td colspan="5">No proposals.</td></tr>';
      setProposalWorkspace(null);
      return;
    }

    for (const proposal of proposals) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><button type="button">${proposal.id === state.currentProposalId ? "Selected" : "Select"}</button></td>
        <td>${proposal.id}</td>
        <td>${escapeHtml(proposal.proposal_type)}</td>
        <td>${escapeHtml(proposal.status)}</td>
        <td>${escapeHtml(proposal.reason)}</td>
      `;
      row.querySelector("button").addEventListener("click", () => {
        state.currentProposalId = proposal.id;
        setProposalWorkspace(proposal);
        renderProposals(state.planDetail.proposals);
        setActiveTab("proposals");
      });
      el.proposalsTableBody.appendChild(row);
    }

    const selectedProposal = proposals.find((proposal) => proposal.id === state.currentProposalId) || null;
    setProposalWorkspace(selectedProposal);
  }

  function setProposalWorkspace(proposal) {
    if (!proposal) {
      el.proposalWorkspace.classList.add("hidden");
      el.proposalWorkspaceEmpty.classList.remove("hidden");
      el.selectedProposalLabel.textContent = "No proposal selected";
      el.proposalPayload.textContent = "Select a proposal to inspect its payload.";
      return;
    }

    el.proposalWorkspace.classList.remove("hidden");
    el.proposalWorkspaceEmpty.classList.add("hidden");
    el.selectedProposalLabel.textContent = `Proposal #${proposal.id} (${proposal.proposal_type})`;
    el.proposalPayload.textContent = JSON.stringify(proposal.payload, null, 2);
  }

  function renderDependencies(dependencies, taskMap) {
    el.dependenciesPanel.innerHTML = "";
    if (!dependencies.length) {
      el.dependenciesPanel.innerHTML = '<div class="empty-state">No dependencies.</div>';
      return;
    }

    for (const [fromTaskId, toTaskId] of dependencies) {
      const item = document.createElement("div");
      item.className = "dependency-item";
      item.textContent = `#${fromTaskId} ${taskMap.get(fromTaskId)?.title || ""} -> #${toTaskId} ${taskMap.get(toTaskId)?.title || ""}`;
      el.dependenciesPanel.appendChild(item);
    }
  }

  function renderScheduleBlocks(blocks, taskMap) {
    el.scheduleTableBody.innerHTML = "";
    if (!blocks.length) {
      el.scheduleTableBody.innerHTML = '<tr><td colspan="4">No schedule blocks.</td></tr>';
      return;
    }

    for (const block of blocks) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>#${block.task_id} ${escapeHtml(taskMap.get(block.task_id)?.title || "")}</td>
        <td>${escapeHtml(formatDateTime(block.start_at))}</td>
        <td>${escapeHtml(formatDateTime(block.end_at))}</td>
        <td>${escapeHtml(block.status)}</td>
      `;
      el.scheduleTableBody.appendChild(row);
    }
  }

  function renderReminders(reminders, taskMap) {
    el.remindersTableBody.innerHTML = "";
    if (!reminders.length) {
      el.remindersTableBody.innerHTML = '<tr><td colspan="4">No reminders.</td></tr>';
      return;
    }

    for (const reminder of reminders) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${escapeHtml(reminder.reminder_type)}</td>
        <td>#${reminder.task_id} ${escapeHtml(taskMap.get(reminder.task_id)?.title || "")}</td>
        <td>${escapeHtml(formatDateTime(reminder.remind_at))}</td>
        <td>${escapeHtml(reminder.status)}</td>
      `;
      el.remindersTableBody.appendChild(row);
    }
  }

  function renderPolicyDecisions(decisions, taskMap) {
    el.policyTableBody.innerHTML = "";
    if (!decisions.length) {
      el.policyTableBody.innerHTML = '<tr><td colspan="4">No policy decisions yet.</td></tr>';
      return;
    }

    for (const decision of decisions) {
      const taskTitle = decision.task_id ? taskMap.get(decision.task_id)?.title || "" : "-";
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${escapeHtml(formatDateTime(decision.created_at))}</td>
        <td>${decision.task_id ? `#${decision.task_id} ${escapeHtml(taskTitle)}` : "-"}</td>
        <td>${escapeHtml(decision.action)}</td>
        <td>${escapeHtml(decision.reason)}</td>
      `;
      el.policyTableBody.appendChild(row);
    }
  }

  function renderEmptyPlan() {
    el.currentPlanTitle.textContent = "No plan selected";
    el.planSummary.innerHTML = '<div class="empty-state">Select a plan to inspect it.</div>';
    el.overviewNarrative.textContent = "Select a plan to see summary, rationale, and goal details.";
    el.tasksTableBody.innerHTML = '<tr><td colspan="6">No tasks.</td></tr>';
    el.proposalsTableBody.innerHTML = '<tr><td colspan="5">No proposals.</td></tr>';
    el.dependenciesPanel.innerHTML = '<div class="empty-state">No dependencies.</div>';
    el.scheduleTableBody.innerHTML = '<tr><td colspan="4">No schedule blocks.</td></tr>';
    el.remindersTableBody.innerHTML = '<tr><td colspan="4">No reminders.</td></tr>';
    el.policyTableBody.innerHTML = '<tr><td colspan="4">No policy decisions yet.</td></tr>';
    setTaskWorkspace(null);
    setProposalWorkspace(null);
  }

  function buildAvailabilityGrid() {
    el.availabilityGrid.className = "availability-grid";
    ["Day", "Use", "Start", "End"].forEach((header) => {
      const strong = document.createElement("strong");
      strong.textContent = header;
      el.availabilityGrid.appendChild(strong);
    });

    DAYS.forEach((dayLabel, index) => {
      const row = document.createElement("div");
      row.className = "availability-row";
      row.innerHTML = `
        <span>${dayLabel}</span>
        <input type="checkbox" data-role="enabled" data-weekday="${index}">
        <input type="time" step="60" data-role="start" data-weekday="${index}">
        <input type="time" step="60" data-role="end" data-weekday="${index}">
      `;
      el.availabilityGrid.appendChild(row);
    });

    for (const [weekday, [start, end]] of Object.entries(DEFAULT_AVAILABILITY)) {
      el.availabilityGrid.querySelector(`[data-role="enabled"][data-weekday="${weekday}"]`).checked = true;
      el.availabilityGrid.querySelector(`[data-role="start"][data-weekday="${weekday}"]`).value = start.slice(0, 5);
      el.availabilityGrid.querySelector(`[data-role="end"][data-weekday="${weekday}"]`).value = end.slice(0, 5);
    }
  }

  function collectAvailability() {
    const windows = [];
    for (let weekday = 0; weekday < DAYS.length; weekday += 1) {
      const enabled = el.availabilityGrid.querySelector(`[data-role="enabled"][data-weekday="${weekday}"]`).checked;
      if (!enabled) {
        continue;
      }
      const start = el.availabilityGrid.querySelector(`[data-role="start"][data-weekday="${weekday}"]`).value;
      const end = el.availabilityGrid.querySelector(`[data-role="end"][data-weekday="${weekday}"]`).value;
      windows.push({
        weekday,
        start_time: normalizeTime(start),
        end_time: normalizeTime(end),
      });
    }
    return windows;
  }

  function seedDefaultDates() {
    const today = new Date();
    const endDate = new Date(today.getTime() + (19 * 24 * 60 * 60 * 1000));
    el.createStartDate.value = formatDateInput(today);
    el.createEndDate.value = formatDateInput(endDate);
  }

  async function apiRequest(path, options = {}) {
    const requestOptions = {
      method: options.method || "GET",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      body: options.body,
    };

    if (!options.body) {
      delete requestOptions.body;
    }

    const response = await fetch(path, requestOptions);
    if (!response.ok) {
      throw new Error(`${requestOptions.method} ${path} failed: ${await response.text()}`);
    }
    return response.json();
  }

  function plannerMode() {
    return el.plannerMode.value;
  }

  function requirePlan() {
    if (state.currentPlanId) {
      return true;
    }
    window.alert("Select a plan first.");
    return false;
  }

  function requireTask() {
    if (state.currentTaskId) {
      return true;
    }
    window.alert("Select a task first.");
    return false;
  }

  function requireProposal() {
    if (state.currentProposalId) {
      return true;
    }
    window.alert("Select a proposal first.");
    return false;
  }

  function showError(error) {
    log(error.message || String(error));
    window.alert(error.message || String(error));
  }

  function log(message) {
    const line = `[${new Date().toLocaleTimeString()}] ${message}`;
    el.activityLog.textContent = `${line}\n${el.activityLog.textContent}`.trim();
  }

  function setLoading(isLoading, title = "Working...", hint = "Please wait.") {
    if (!el.loadingOverlay) {
      return;
    }
    if (isLoading) {
      el.loadingTitle.textContent = title;
      el.loadingHint.textContent = hint;
      el.loadingOverlay.classList.remove("hidden");
      setBackendStatus("working");
    } else {
      el.loadingOverlay.classList.add("hidden");
      setBackendStatus("idle");
    }
  }

  function setBackendStatus(stateLabel) {
    if (!el.backendLabel || !el.backendDot) {
      return;
    }
    el.backendLabel.textContent = stateLabel;
    el.backendDot.classList.remove("idle", "active", "working");
    if (stateLabel === "working") {
      el.backendDot.classList.add("working");
      return;
    }
    el.backendDot.classList.add("active");
  }

  function updateTaskStatusBadge(status) {
    if (!el.taskStatusBadge) {
      return;
    }
    const normalized = status || "pending";
    el.taskStatusBadge.textContent = normalized;
    el.taskStatusBadge.classList.remove("idle", "active", "warn");
    if (["done", "in_progress", "scheduled"].includes(normalized)) {
      el.taskStatusBadge.classList.add("active");
    } else if (["blocked", "failed", "delayed"].includes(normalized)) {
      el.taskStatusBadge.classList.add("warn");
    } else {
      el.taskStatusBadge.classList.add("idle");
    }
  }

  function computeProgress(tasks) {
    if (!tasks.length) {
      return { percent: 0, done: 0, total: 0 };
    }
    const doneCount = tasks.filter((task) => task.status === "done").length;
    const percent = Math.round((doneCount / tasks.length) * 100);
    return { percent, done: doneCount, total: tasks.length };
  }

  function progressCard(progress) {
    return `
      <div class="summary-card">
        <span>Progress</span>
        <strong>${progress.percent}%</strong>
        <div class="progress-bar">
          <div class="progress-fill" style="width: ${progress.percent}%"></div>
        </div>
        <div class="progress-detail">Done ${progress.done} of ${progress.total} tasks</div>
      </div>
    `;
  }

  function metricCard(label, value) {
    return `
      <div class="summary-card">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `;
  }

  function parseOptionalInt(value) {
    const cleaned = String(value || "").trim();
    if (!cleaned) {
      return null;
    }
    const parsed = Number.parseInt(cleaned, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }

  function parseOptionalFloat(value) {
    const cleaned = String(value || "").trim();
    if (!cleaned) {
      return null;
    }
    const parsed = Number.parseFloat(cleaned);
    return Number.isNaN(parsed) ? null : parsed;
  }

  function emptyToNull(value) {
    const cleaned = String(value || "").trim();
    return cleaned ? cleaned : null;
  }

  function normalizeTime(value) {
    return value && value.length === 5 ? `${value}:00` : (value || "18:00:00");
  }

  function formatDateTime(value) {
    if (!value) {
      return "";
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
  }

  function formatDateInput(date) {
    return new Date(date.getTime() - (date.getTimezoneOffset() * 60000)).toISOString().slice(0, 10);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function capitalize(value) {
    return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
  }
})();
