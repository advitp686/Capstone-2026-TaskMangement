(function () {
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const DEFAULT_AVAILABILITY = {
    0: ["18:00", "20:00"],
    1: ["18:00", "20:00"],
    2: ["18:00", "20:00"],
    3: ["18:00", "20:00"],
    4: ["18:00", "20:00"],
  };
  const PLAN_COLORS = ["blue", "green", "neutral", "rose", "amber"];

  const state = {
    currentPlanId: null,
    currentTaskId: null,
    currentProposalId: null,
    currentProposalTargetPlanId: null,
    currentTab: "roadmap",
    planDetail: null,
    planHistory: null,
    clarificationAnswers: {},
    assistantSummary: "",
    references: [],
  };

  const el = {};

  document.addEventListener("DOMContentLoaded", () => {
    cacheElements();
    buildAvailabilityGrid();
    seedDefaultDates();
    bindEvents();
    setActiveTab("roadmap");
    refreshAll();
  });

  function cacheElements() {
    [
      "healthStatus", "backendDot", "backendLabel", "plannerMode", "autoApprove", "healthButton",
      "refreshPlansButton", "planList", "newPlanButton", "createPlanPanel", "createPlanForm",
      "createTitle", "createDescription", "createStartDate", "createEndDate", "referenceFiles",
      "availabilityGrid", "assistantIntakeButton", "createPlanButton", "clarificationPanel",
      "webSearchStatus", "readinessSummary", "clarificationQuestions", "planPanel", "currentPlanTitle",
      "refreshPlanButton", "revertPlanButton", "planSummary", "nextBlockPanel", "roadmapPanel",
      "schedulePanel", "historyPanel", "activityLog", "assistantMessages", "assistantForm",
      "assistantInput", "loadingOverlay", "loadingTitle", "loadingHint",
    ].forEach((id) => {
      el[id] = document.getElementById(id);
    });
    el.tabButtons = Array.from(document.querySelectorAll("[data-tab-target]"));
    el.presetButtons = Array.from(document.querySelectorAll("[data-availability-preset]"));
  }

  function bindEvents() {
    el.healthButton.addEventListener("click", checkHealth);
    el.refreshPlansButton.addEventListener("click", refreshPlans);
    el.refreshPlanButton.addEventListener("click", refreshSelectedPlan);
    el.newPlanButton.addEventListener("click", () => {
      state.currentPlanId = null;
      state.planDetail = null;
      renderEmptyPlan();
      el.createPlanPanel.classList.remove("collapsed");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    el.assistantIntakeButton.addEventListener("click", runAssistantIntake);
    el.createPlanForm.addEventListener("submit", createPlan);
    el.revertPlanButton.addEventListener("click", revertPlan);
    el.assistantForm.addEventListener("submit", sendAssistantMessage);
    el.tabButtons.forEach((button) => {
      button.addEventListener("click", () => setActiveTab(button.dataset.tabTarget));
    });
    el.presetButtons.forEach((button) => {
      button.addEventListener("click", () => applyAvailabilityPreset(button.dataset.availabilityPreset));
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
      el.healthStatus.textContent = health.status || "ok";
      setBackendStatus("idle");
    } catch (error) {
      el.healthStatus.textContent = "offline";
      setBackendStatus("offline");
      log(error.message || String(error));
    }
  }

  async function refreshPlans() {
    try {
      const plans = await apiRequest("/plans");
      renderPlanList(plans);
      const activePlan = plans.find((plan) => plan.status === "active") || plans[plans.length - 1];
      if (!state.currentPlanId && activePlan) {
        state.currentPlanId = activePlan.plan_version_id;
        await refreshSelectedPlan();
      }
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
      const [detail, history] = await Promise.all([
        apiRequest(`/plans/${state.currentPlanId}`),
        apiRequest(`/plans/${state.currentPlanId}/history`),
      ]);
      state.planDetail = detail;
      state.planHistory = history;
      renderPlanDetail(detail, history);
      el.planPanel.classList.remove("hidden");
      el.createPlanPanel.classList.add("collapsed");
      log(`Loaded plan ${state.currentPlanId}.`);
    } catch (error) {
      showError(error);
    }
  }

  async function runAssistantIntake() {
    const payload = await buildPlanPayload(false);
    if (!payload) {
      return;
    }
    try {
      setLoading(true, "Preparing plan context...", modelHint());
      const response = await apiRequest("/assistant/intake", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.assistantSummary = response.assistant_summary || "";
      renderClarifications(response);
      addAssistantMessage("assistant", response.readiness_summary);
      if (response.web_search_message) {
        addAssistantMessage("assistant", response.web_search_message);
      }
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function createPlan(event) {
    event.preventDefault();
    const payload = await buildPlanPayload(true);
    if (!payload) {
      return;
    }
    try {
      setLoading(true, "Creating roadmap...", modelHint());
      const created = await apiRequest("/plans", {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          planner: plannerMode(),
          auto_approve: el.autoApprove.checked,
          assistant_summary: state.assistantSummary,
        }),
      });
      state.currentPlanId = created.plan_version_id;
      state.currentTaskId = null;
      state.currentProposalId = null;
      addAssistantMessage("assistant", "Your roadmap is ready. I selected it and highlighted what comes next.");
      await refreshPlans();
      await refreshSelectedPlan();
      setActiveTab("roadmap");
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function buildPlanPayload(includeAnswers) {
    const title = el.createTitle.value.trim();
    const description = el.createDescription.value.trim();
    if (!title || !description) {
      window.alert("Title and description are required.");
      return null;
    }
    state.references = await readReferenceFiles();
    if (includeAnswers) {
      state.clarificationAnswers = collectClarificationAnswers();
    }
    return {
      title,
      description,
      target_start_date: el.createStartDate.value,
      target_end_date: el.createEndDate.value,
      availability: collectAvailability(),
      references: state.references,
      clarification_answers: includeAnswers ? state.clarificationAnswers : {},
      use_web_search: true,
      constraints: {},
    };
  }

  function renderClarifications(response) {
    el.clarificationPanel.classList.remove("hidden");
    el.readinessSummary.textContent = response.readiness_summary || "";
    el.webSearchStatus.textContent = response.web_search_used ? "web added" : "local context";
    el.webSearchStatus.className = response.web_search_used ? "status-badge active" : "status-badge idle";
    el.clarificationQuestions.innerHTML = "";
    if (!response.questions.length) {
      el.clarificationQuestions.innerHTML = '<div class="empty-state">No extra questions needed. You can create the roadmap now.</div>';
      return;
    }
    response.questions.forEach((question) => {
      const card = document.createElement("div");
      card.className = "question-card";
      const options = [...new Set([question.recommended_option, ...question.options])];
      card.innerHTML = `
        <strong>${escapeHtml(question.prompt)}</strong>
        <div class="option-list">
          ${options.map((option, index) => `
            <label class="option-row">
              <input type="radio" name="clarification-${escapeHtml(question.id)}" value="${escapeHtml(option)}" ${index === 0 ? "checked" : ""}>
              <span>${escapeHtml(option)}${index === 0 ? " (Recommended)" : ""}</span>
            </label>
          `).join("")}
          <label class="option-row custom-option">
            <input type="radio" name="clarification-${escapeHtml(question.id)}" value="__custom__">
            <input type="text" data-custom-answer="${escapeHtml(question.id)}" placeholder="Custom answer">
          </label>
        </div>
      `;
      el.clarificationQuestions.appendChild(card);
    });
  }

  function collectClarificationAnswers() {
    const answers = {};
    el.clarificationQuestions.querySelectorAll(".question-card").forEach((card) => {
      const selected = card.querySelector("input[type='radio']:checked");
      if (!selected) {
        return;
      }
      const id = selected.name.replace("clarification-", "");
      if (selected.value === "__custom__") {
        const custom = card.querySelector(`[data-custom-answer="${CSS.escape(id)}"]`);
        answers[id] = custom && custom.value.trim() ? custom.value.trim() : "Custom answer not provided";
      } else {
        answers[id] = selected.value;
      }
    });
    return answers;
  }

  async function readReferenceFiles() {
    const files = Array.from(el.referenceFiles.files || []);
    const allowed = files.filter((file) => {
      const name = file.name.toLowerCase();
      return name.endsWith(".md") || name.endsWith(".markdown") || name.endsWith(".txt") || file.type === "text/plain";
    });
    const references = [];
    for (const file of allowed) {
      const content = await file.text();
      references.push({
        filename: file.name,
        kind: file.name.toLowerCase().endsWith(".md") || file.name.toLowerCase().endsWith(".markdown") ? "markdown" : "text",
        content,
      });
    }
    return references;
  }

  function renderPlanList(plans) {
    el.planList.innerHTML = "";
    if (!plans.length) {
      el.planList.innerHTML = '<div class="empty-state">No plans yet. Create one from the main panel.</div>';
      return;
    }
    plans.slice().reverse().forEach((plan, index) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = `plan-item ${plan.plan_version_id === state.currentPlanId ? "active" : ""} color-${PLAN_COLORS[index % PLAN_COLORS.length]}`;
      item.innerHTML = `
        <strong>${escapeHtml(plan.title)}</strong>
        <span>${escapeHtml(plan.status)} | ${escapeHtml(plan.target_start_date)} to ${escapeHtml(plan.target_end_date)}</span>
      `;
      item.addEventListener("click", async () => {
        state.currentPlanId = plan.plan_version_id;
        await refreshPlans();
        await refreshSelectedPlan();
      });
      el.planList.appendChild(item);
    });
  }

  function renderPlanDetail(detail, history) {
    const plan = detail.plan;
    const progress = computeProgress(detail.tasks);
    state.currentProposalId = null;
    state.currentProposalTargetPlanId = null;
    el.currentPlanTitle.textContent = plan.title;
    el.planSummary.innerHTML = [
      summaryCard("Status", plan.status),
      summaryCard("Window", `${plan.target_start_date} to ${plan.target_end_date}`),
      summaryCard("Roadmap Steps", String(detail.tasks.length)),
      progressCard(progress),
    ].join("");
    renderNextBlock(detail);
    renderRoadmap(detail.tasks);
    renderSchedule(detail);
    renderHistory(history);
    el.revertPlanButton.classList.toggle("hidden", !history.revert_eligible);
  }

  function renderRoadmap(tasks) {
    el.roadmapPanel.innerHTML = "";
    if (!tasks.length) {
      el.roadmapPanel.innerHTML = '<div class="empty-state">No roadmap steps yet.</div>';
      return;
    }
    tasks.forEach((task, index) => {
      const card = document.createElement("article");
      const selected = task.id === state.currentTaskId;
      card.className = `roadmap-card ${selected ? "selected" : ""}`;
      const milestone = milestoneForTask(task, index);
      card.innerHTML = `
        <div class="step-number">Step ${index + 1}</div>
        <div class="roadmap-body">
          <div class="roadmap-head">
            <div>
              <span class="milestone">${escapeHtml(milestone)}</span>
              <h3>${escapeHtml(cleanTaskTitle(task.title))}</h3>
            </div>
            <span class="status-badge ${statusClass(task.status)}">${escapeHtml(task.status)}</span>
          </div>
          <p>${escapeHtml(task.summary || "Complete this step and record what changed.")}</p>
          <div class="task-meta">
            <span>${task.estimated_minutes} min</span>
            <span>${task.target_date ? escapeHtml(task.target_date) : "scheduled by availability"}</span>
          </div>
          <div class="task-actions">
            <button type="button" data-task-action="work">Work on this</button>
            <button type="button" class="secondary-button" data-task-action="done">Done</button>
            <button type="button" class="secondary-button" data-task-action="blocked">Blocked</button>
            <button type="button" class="secondary-button" data-task-action="change">Change plan</button>
          </div>
          <form class="feedback-card ${selected ? "" : "hidden"}">
            <label>
              What happened?
              <select data-feedback-status>
                <option value="done">Done</option>
                <option value="delayed">Delayed</option>
                <option value="blocked" selected>Blocked</option>
                <option value="failed">Failed</option>
                <option value="skipped">Skipped</option>
              </select>
            </label>
            <label>
              Actual minutes
              <input type="number" min="1" data-feedback-minutes value="${task.estimated_minutes || 60}">
            </label>
            <label>
              Difficulty <span data-difficulty-label>3</span>/5
              <input type="range" min="1" max="5" value="3" data-feedback-difficulty>
            </label>
            <label>
              Confidence <span data-confidence-label>0.5</span>
              <input type="range" min="0" max="1" step="0.1" value="0.5" data-feedback-confidence>
            </label>
            <label class="wide">
              Note
              <textarea rows="3" data-feedback-note placeholder="Tell the assistant what felt wrong or what changed."></textarea>
            </label>
            <button type="submit">Send Feedback</button>
          </form>
        </div>
      `;
      card.querySelector("[data-task-action='work']").addEventListener("click", () => selectTask(task.id));
      card.querySelector("[data-task-action='done']").addEventListener("click", () => quickFeedback(task, "done"));
      card.querySelector("[data-task-action='blocked']").addEventListener("click", () => selectTask(task.id, "blocked"));
      card.querySelector("[data-task-action='change']").addEventListener("click", () => {
        addAssistantMessage("user", `Please change this step: ${task.title}`);
        addAssistantMessage("assistant", "Tell me what feels wrong. I can suggest a change without applying it automatically.");
        selectTask(task.id, "blocked");
      });
      const difficulty = card.querySelector("[data-feedback-difficulty]");
      const confidence = card.querySelector("[data-feedback-confidence]");
      difficulty.addEventListener("input", () => {
        card.querySelector("[data-difficulty-label]").textContent = difficulty.value;
      });
      confidence.addEventListener("input", () => {
        card.querySelector("[data-confidence-label]").textContent = confidence.value;
      });
      card.querySelector(".feedback-card").addEventListener("submit", (event) => submitFeedback(event, task));
      el.roadmapPanel.appendChild(card);
    });
  }

  function renderNextBlock(detail) {
    const taskMap = new Map(detail.tasks.map((task) => [task.id, task]));
    const blocks = detail.schedule_blocks.slice().sort((a, b) => new Date(a.start_at) - new Date(b.start_at));
    const now = Date.now();
    const next = blocks.find((block) => new Date(block.end_at).getTime() >= now) || blocks[0];
    if (!next) {
      el.nextBlockPanel.innerHTML = '<div class="empty-state">No schedule block yet. Reschedule after creating tasks.</div>';
      return;
    }
    const task = taskMap.get(next.task_id);
    el.nextBlockPanel.innerHTML = `
      <div>
        <span class="eyebrow">Next Block</span>
        <h3>${escapeHtml(cleanTaskTitle(task?.title || "Scheduled work"))}</h3>
      </div>
      <strong>${escapeHtml(formatDateTime(next.start_at))} to ${escapeHtml(formatTime(next.end_at))}</strong>
    `;
  }

  function renderSchedule(detail) {
    const taskMap = new Map(detail.tasks.map((task) => [task.id, task]));
    el.schedulePanel.innerHTML = "";
    if (!detail.schedule_blocks.length) {
      el.schedulePanel.innerHTML = '<div class="empty-state">No schedule blocks yet.</div>';
      return;
    }
    detail.schedule_blocks.forEach((block, index) => {
      const task = taskMap.get(block.task_id);
      const row = document.createElement("div");
      row.className = `schedule-card color-${PLAN_COLORS[index % PLAN_COLORS.length]}`;
      row.innerHTML = `
        <div>
          <strong>${escapeHtml(formatDateTime(block.start_at))}</strong>
          <span>${escapeHtml(formatTime(block.end_at))}</span>
        </div>
        <p>${escapeHtml(cleanTaskTitle(task?.title || "Scheduled work"))}</p>
        <span class="status-badge ${statusClass(block.status)}">${escapeHtml(block.status)}</span>
      `;
      el.schedulePanel.appendChild(row);
    });
  }

  function renderHistory(history) {
    el.historyPanel.innerHTML = "";
    if (!history || !history.versions.length) {
      el.historyPanel.innerHTML = '<div class="empty-state">No version history yet.</div>';
      return;
    }
    history.versions.slice().reverse().forEach((version) => {
      const item = document.createElement("div");
      item.className = "history-card";
      const canRevert = version.plan_version_id === history.revert_target_plan_version_id;
      item.innerHTML = `
        <div>
          <strong>Version ${version.version_number}: ${escapeHtml(version.title)}</strong>
          <p>${escapeHtml(version.summary || "")}</p>
          <span class="status-badge ${statusClass(version.status)}">${escapeHtml(version.status)}</span>
        </div>
        ${canRevert ? '<button type="button" class="warning-button">Revert to this</button>' : ""}
      `;
      const button = item.querySelector("button");
      if (button) {
        button.addEventListener("click", revertPlan);
      }
      el.historyPanel.appendChild(item);
    });
  }

  function selectTask(taskId, status = "blocked") {
    state.currentTaskId = taskId;
    renderRoadmap(state.planDetail.tasks);
    const card = Array.from(document.querySelectorAll(".roadmap-card")).find((item) => item.classList.contains("selected"));
    if (card) {
      const statusSelect = card.querySelector("[data-feedback-status]");
      if (statusSelect) {
        statusSelect.value = status;
      }
      card.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  async function quickFeedback(task, status) {
    await sendFeedbackPayload(task, {
      status,
      actual_minutes: task.estimated_minutes,
      difficulty: 2,
      confidence: status === "done" ? 0.8 : 0.4,
      note: status === "done" ? "Completed this step." : "This step needs review.",
    });
  }

  async function submitFeedback(event, task) {
    event.preventDefault();
    const form = event.currentTarget;
    await sendFeedbackPayload(task, {
      status: form.querySelector("[data-feedback-status]").value,
      actual_minutes: parseOptionalInt(form.querySelector("[data-feedback-minutes]").value),
      difficulty: parseOptionalInt(form.querySelector("[data-feedback-difficulty]").value),
      confidence: parseOptionalFloat(form.querySelector("[data-feedback-confidence]").value),
      note: form.querySelector("[data-feedback-note]").value.trim(),
    });
  }

  async function sendFeedbackPayload(task, payload) {
    try {
      setLoading(true, "Reviewing feedback...", "The assistant is checking whether this should become a suggested change.");
      const response = await apiRequest(`/tasks/${task.id}/feedback?planner=${encodeURIComponent(plannerMode())}`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      addAssistantMessage("user", `${payload.status}: ${payload.note || task.title}`);
      renderAssistantReview(response);
      await refreshPlans();
      await refreshSelectedPlan();
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  function renderAssistantReview(response) {
    const review = response.assistant_review || {};
    const message = [
      review.system_understanding || "I recorded your feedback.",
      response.reason ? `Decision: ${response.reason}` : "",
      review.suggested_next_step || "",
    ].filter(Boolean).join("\n\n");
    addAssistantMessage("assistant", message, response.action === "propose_replan" ? [
      {
        label: "Review suggested change",
        handler: () => requestAssistantReplan(response.task_id, response.reason),
      },
    ] : []);
    if (review.clarification_questions && review.clarification_questions.length) {
      const prompts = review.clarification_questions.map((question) => `- ${question.prompt}`).join("\n");
      addAssistantMessage("assistant", `Before changing the roadmap, I would ask:\n${prompts}`);
    }
  }

  async function requestAssistantReplan(taskId, reason) {
    if (!state.currentPlanId) {
      return;
    }
    try {
      setLoading(true, "Preparing suggested change...", modelHint());
      const proposal = await apiRequest(`/plans/${state.currentPlanId}/assistant/replan`, {
        method: "POST",
        body: JSON.stringify({
          planner: plannerMode(),
          trigger_task_id: taskId,
          trigger_reason: reason || "Assistant suggested making the roadmap clearer.",
        }),
      });
      state.currentProposalId = proposal.id;
      state.currentProposalTargetPlanId = proposal.payload && proposal.payload.new_plan_version_id;
      addAssistantMessage("assistant", `I prepared a suggested change. It will not apply until you approve it.\n\nReason: ${proposal.reason}`, [
        { label: "Apply suggested change", handler: applyCurrentProposal },
        { label: "Reject", handler: rejectCurrentProposal },
      ]);
      await refreshSelectedPlan();
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function applyCurrentProposal() {
    if (!state.currentProposalId) {
      return;
    }
    try {
      setLoading(true, "Applying approved change...", "The previous version will remain available in History.");
      const proposal = await apiRequest(`/proposals/${state.currentProposalId}?planner=${encodeURIComponent(plannerMode())}`, {
        method: "POST",
        body: JSON.stringify({ action: "apply" }),
      });
      if (proposal.proposal_type === "replan" && proposal.payload && proposal.payload.new_plan_version_id) {
        state.currentPlanId = Number(proposal.payload.new_plan_version_id);
      }
      addAssistantMessage("assistant", "Applied. The earlier roadmap is still available from History if this version is not better.");
      await refreshPlans();
      await refreshSelectedPlan();
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function rejectCurrentProposal() {
    if (!state.currentProposalId) {
      return;
    }
    try {
      await apiRequest(`/proposals/${state.currentProposalId}?planner=${encodeURIComponent(plannerMode())}`, {
        method: "POST",
        body: JSON.stringify({ action: "reject" }),
      });
      addAssistantMessage("assistant", "Rejected. I left the current roadmap unchanged.");
      state.currentProposalId = null;
    } catch (error) {
      showError(error);
    }
  }

  async function revertPlan() {
    if (!state.currentPlanId || !state.planHistory || !state.planHistory.revert_eligible) {
      addAssistantMessage("assistant", "There is no previous version available to restore.");
      return;
    }
    try {
      setLoading(true, "Restoring previous roadmap...", "The schedule and reminders will be regenerated.");
      const result = await apiRequest(`/plans/${state.currentPlanId}/revert?planner=${encodeURIComponent(plannerMode())}`, {
        method: "POST",
      });
      state.currentPlanId = result.plan_version_id;
      addAssistantMessage("assistant", "Restored the previous roadmap and regenerated the schedule.");
      await refreshPlans();
      await refreshSelectedPlan();
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function sendAssistantMessage(event) {
    event.preventDefault();
    const message = el.assistantInput.value.trim();
    if (!message) {
      return;
    }
    el.assistantInput.value = "";
    addAssistantMessage("user", message);
    if (!state.currentPlanId) {
      addAssistantMessage("assistant", "Create or select a plan first, then I can reason over its tasks and schedule.");
      return;
    }
    try {
      const response = await apiRequest(`/plans/${state.currentPlanId}/assistant/messages`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      state.assistantSummary = response.updated_summary || state.assistantSummary;
      addAssistantMessage("assistant", response.reply, response.suggested_actions.map((action) => ({
        label: action.label,
        handler: () => handleAssistantAction(action, message),
      })));
    } catch (error) {
      showError(error);
    }
  }

  function handleAssistantAction(action, message) {
    if (action.action === "assistant_replan") {
      requestAssistantReplan(state.currentTaskId, action.payload.reason || message);
      return;
    }
    addAssistantMessage("assistant", "I can use that signal in the next suggested change. No plan change has been applied.");
  }

  function addAssistantMessage(role, text, actions = []) {
    const message = document.createElement("div");
    message.className = `assistant-message ${role}`;
    message.innerHTML = `<p>${escapeHtml(text).replaceAll("\n", "<br>")}</p>`;
    if (actions.length) {
      const actionRow = document.createElement("div");
      actionRow.className = "assistant-actions";
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = action.label;
        button.addEventListener("click", action.handler);
        actionRow.appendChild(button);
      });
      message.appendChild(actionRow);
    }
    el.assistantMessages.appendChild(message);
    el.assistantMessages.scrollTop = el.assistantMessages.scrollHeight;
  }

  function renderEmptyPlan() {
    el.planPanel.classList.add("hidden");
    el.planSummary.innerHTML = "";
    el.roadmapPanel.innerHTML = "";
    el.schedulePanel.innerHTML = "";
    el.historyPanel.innerHTML = "";
    el.revertPlanButton.classList.add("hidden");
  }

  function setActiveTab(name) {
    state.currentTab = name;
    el.tabButtons.forEach((button) => {
      button.classList.toggle("active", button.dataset.tabTarget === name);
    });
    document.querySelectorAll(".tab-pane").forEach((pane) => {
      pane.classList.toggle("active", pane.id === `tab-${name}`);
    });
  }

  function buildAvailabilityGrid() {
    el.availabilityGrid.innerHTML = "";
    ["Day", "Use", "Start", "End"].forEach((header) => {
      const strong = document.createElement("strong");
      strong.textContent = header;
      el.availabilityGrid.appendChild(strong);
    });
    DAYS.forEach((label, weekday) => {
      const row = document.createElement("div");
      row.className = "availability-row";
      row.innerHTML = `
        <span>${label}</span>
        <input type="checkbox" data-role="enabled" data-weekday="${weekday}">
        <input type="time" step="900" data-role="start" data-weekday="${weekday}">
        <input type="time" step="900" data-role="end" data-weekday="${weekday}">
      `;
      el.availabilityGrid.appendChild(row);
    });
    setAvailability(DEFAULT_AVAILABILITY);
  }

  function applyAvailabilityPreset(preset) {
    if (preset === "clear") {
      setAvailability({});
      return;
    }
    if (preset === "weekend") {
      setAvailability({ 5: ["10:00", "12:00"], 6: ["10:00", "12:00"] });
      return;
    }
    setAvailability(DEFAULT_AVAILABILITY);
  }

  function setAvailability(windows) {
    for (let weekday = 0; weekday < DAYS.length; weekday += 1) {
      const enabled = el.availabilityGrid.querySelector(`[data-role="enabled"][data-weekday="${weekday}"]`);
      const start = el.availabilityGrid.querySelector(`[data-role="start"][data-weekday="${weekday}"]`);
      const end = el.availabilityGrid.querySelector(`[data-role="end"][data-weekday="${weekday}"]`);
      const value = windows[weekday];
      enabled.checked = Boolean(value);
      start.value = value ? value[0] : "";
      end.value = value ? value[1] : "";
    }
  }

  function collectAvailability() {
    const windows = [];
    for (let weekday = 0; weekday < DAYS.length; weekday += 1) {
      const enabled = el.availabilityGrid.querySelector(`[data-role="enabled"][data-weekday="${weekday}"]`).checked;
      if (!enabled) {
        continue;
      }
      const start = el.availabilityGrid.querySelector(`[data-role="start"][data-weekday="${weekday}"]`).value || "18:00";
      const end = el.availabilityGrid.querySelector(`[data-role="end"][data-weekday="${weekday}"]`).value || "20:00";
      windows.push({ weekday, start_time: normalizeTime(start), end_time: normalizeTime(end) });
    }
    return windows;
  }

  function seedDefaultDates() {
    const today = new Date();
    const endDate = new Date(today.getTime() + (7 * 24 * 60 * 60 * 1000));
    el.createStartDate.value = formatDateInput(today);
    el.createEndDate.value = formatDateInput(endDate);
  }

  async function apiRequest(path, options = {}) {
    const requestOptions = {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
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

  function modelHint() {
    return plannerMode() === "gemma"
      ? "Gemma may use the configured local llama.cpp/Vulkan runtime and can take a while."
      : "Mock testing mode is deterministic and usually fast.";
  }

  function setLoading(isLoading, title = "Working...", hint = "Please wait.") {
    el.loadingTitle.textContent = title;
    el.loadingHint.textContent = hint;
    el.loadingOverlay.classList.toggle("hidden", !isLoading);
    setBackendStatus(isLoading ? "working" : "idle");
  }

  function setBackendStatus(label) {
    el.backendLabel.textContent = label;
    el.backendDot.classList.remove("idle", "working", "active");
    el.backendDot.classList.add(label === "working" ? "working" : label === "offline" ? "idle" : "active");
  }

  function showError(error) {
    const message = error.message || String(error);
    log(message);
    addAssistantMessage("assistant", message);
  }

  function log(message) {
    if (!el.activityLog) {
      return;
    }
    const line = `[${new Date().toLocaleTimeString()}] ${message}`;
    el.activityLog.textContent = `${line}\n${el.activityLog.textContent || ""}`.trim();
  }

  function summaryCard(label, value) {
    return `<div class="summary-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
  }

  function progressCard(progress) {
    return `
      <div class="summary-card">
        <span>Progress</span>
        <strong>${progress.percent}%</strong>
        <div class="progress-bar"><div class="progress-fill" style="width: ${progress.percent}%"></div></div>
        <small>Done ${progress.done} of ${progress.total} steps</small>
      </div>
    `;
  }

  function computeProgress(tasks) {
    if (!tasks.length) {
      return { percent: 0, done: 0, total: 0 };
    }
    const done = tasks.filter((task) => task.status === "done").length;
    return { percent: Math.round((done / tasks.length) * 100), done, total: tasks.length };
  }

  function milestoneForTask(task, index) {
    const text = `${task.title} ${task.summary}`.toLowerCase();
    if (text.includes("basic") || text.includes("syntax")) return "Foundation";
    if (text.includes("practice") || text.includes("problem")) return "Practice";
    if (text.includes("oop") || text.includes("file") || text.includes("exception")) return "Intermediate";
    if (text.includes("review") || text.includes("final")) return "Consolidation";
    return `Milestone ${Math.floor(index / 2) + 1}`;
  }

  function cleanTaskTitle(title) {
    return String(title || "").replace(/^.+?:\s*/, "");
  }

  function statusClass(status) {
    if (["done", "active", "scheduled"].includes(status)) return "active";
    if (["blocked", "failed", "delayed", "review_needed"].includes(status)) return "warn";
    return "idle";
  }

  function normalizeTime(value) {
    return value && value.length === 5 ? `${value}:00` : (value || "18:00:00");
  }

  function parseOptionalInt(value) {
    const parsed = Number.parseInt(String(value || "").trim(), 10);
    return Number.isNaN(parsed) ? null : parsed;
  }

  function parseOptionalFloat(value) {
    const parsed = Number.parseFloat(String(value || "").trim());
    return Number.isNaN(parsed) ? null : parsed;
  }

  function formatDateInput(date) {
    return new Date(date.getTime() - (date.getTimezoneOffset() * 60000)).toISOString().slice(0, 10);
  }

  function formatDateTime(value) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value || "") : parsed.toLocaleString();
  }

  function formatTime(value) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value || "") : parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
})();
