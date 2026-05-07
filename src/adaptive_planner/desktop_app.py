from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from .client import AdaptivePlannerApiClient, ApiClientError


DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TASK_STATUS_OPTIONS = ["done", "delayed", "blocked", "failed", "skipped"]
PLANNER_OPTIONS = ["mock", "gemma"]


class AvailabilityEditor(ttk.LabelFrame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, text="Availability")
        self._rows: list[tuple[tk.BooleanVar, tk.StringVar, tk.StringVar]] = []
        header = ["Day", "Use", "Start", "End"]
        for column, text in enumerate(header):
            ttk.Label(self, text=text).grid(row=0, column=column, sticky="w", padx=4, pady=2)

        defaults = {0: ("18:00", "20:00"), 1: ("18:00", "20:00"), 2: ("18:00", "20:00"), 3: ("18:00", "20:00")}
        for weekday, label in enumerate(DAY_LABELS):
            enabled = tk.BooleanVar(value=weekday in defaults)
            start_var = tk.StringVar(value=defaults.get(weekday, ("18:00", "20:00"))[0])
            end_var = tk.StringVar(value=defaults.get(weekday, ("18:00", "20:00"))[1])
            self._rows.append((enabled, start_var, end_var))

            ttk.Label(self, text=label).grid(row=weekday + 1, column=0, sticky="w", padx=4, pady=2)
            ttk.Checkbutton(self, variable=enabled).grid(row=weekday + 1, column=1, padx=4, pady=2)
            ttk.Entry(self, width=8, textvariable=start_var).grid(row=weekday + 1, column=2, padx=4, pady=2)
            ttk.Entry(self, width=8, textvariable=end_var).grid(row=weekday + 1, column=3, padx=4, pady=2)

    def get_payload(self) -> list[dict[str, str | int]]:
        windows: list[dict[str, str | int]] = []
        for weekday, row in enumerate(self._rows):
            enabled, start_var, end_var = row
            if enabled.get():
                windows.append(
                    {
                        "weekday": weekday,
                        "start_time": self._normalize_time(start_var.get()),
                        "end_time": self._normalize_time(end_var.get()),
                    }
                )
        return windows

    def _normalize_time(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) == 5:
            return f"{cleaned}:00"
        return cleaned


class AdaptivePlannerDesktopApp(tk.Tk):
    def __init__(self, client: AdaptivePlannerApiClient) -> None:
        super().__init__()
        self.client = client
        self.title("Adaptive Planner Desktop")
        self.geometry("1280x820")
        self.minsize(1100, 760)

        self.current_plan_version_id: int | None = None
        self.current_task_id: int | None = None
        self.current_proposal_id: int | None = None
        self.plan_ids_by_index: list[int] = []
        self.task_ids_by_index: list[int] = []
        self.proposal_ids_by_index: list[int] = []

        self.base_url_var = tk.StringVar(value=self.client.base_url)
        self.planner_var = tk.StringVar(value="mock")
        self.create_auto_approve_var = tk.BooleanVar(value=True)
        self.selected_feedback_status = tk.StringVar(value="blocked")
        self.feedback_minutes_var = tk.StringVar(value="")
        self.feedback_difficulty_var = tk.StringVar(value="3")
        self.feedback_confidence_var = tk.StringVar(value="0.5")
        self.edit_title_var = tk.StringVar(value="")
        self.edit_minutes_var = tk.StringVar(value="")
        self.edit_target_date_var = tk.StringVar(value="")

        self._build_layout()
        self.after(150, self.refresh_all)

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=10)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(7, weight=1)

        ttk.Label(toolbar, text="API URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(toolbar, textvariable=self.base_url_var, width=30).grid(row=0, column=1, padx=6)
        ttk.Label(toolbar, text="Planner").grid(row=0, column=2, sticky="w")
        ttk.Combobox(toolbar, values=PLANNER_OPTIONS, textvariable=self.planner_var, state="readonly", width=8).grid(row=0, column=3, padx=6)
        ttk.Button(toolbar, text="Check Health", command=self.check_health).grid(row=0, column=4, padx=6)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_all).grid(row=0, column=5, padx=6)
        ttk.Button(toolbar, text="Deliver Reminders", command=self.deliver_reminders).grid(row=0, column=6, padx=6)
        self.health_label = ttk.Label(toolbar, text="unknown")
        self.health_label.grid(row=0, column=7, sticky="e")

        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky="nsew")

        left = ttk.Frame(body, padding=10)
        right = ttk.Frame(body, padding=10)
        body.add(left, weight=1)
        body.add(right, weight=2)

        self._build_create_panel(left)
        self._build_plan_list_panel(left)
        self._build_detail_panel(right)

    def _build_create_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Create Plan", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Title").grid(row=0, column=0, sticky="w")
        self.create_title_entry = ttk.Entry(frame, width=42)
        self.create_title_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(frame, text="Description").grid(row=1, column=0, sticky="nw")
        self.create_description_text = ScrolledText(frame, width=32, height=5, wrap="word")
        self.create_description_text.grid(row=1, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(frame, text="Start Date").grid(row=2, column=0, sticky="w")
        self.create_start_entry = ttk.Entry(frame, width=18)
        self.create_start_entry.insert(0, "2026-04-06")
        self.create_start_entry.grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(frame, text="End Date").grid(row=3, column=0, sticky="w")
        self.create_end_entry = ttk.Entry(frame, width=18)
        self.create_end_entry.insert(0, "2026-04-25")
        self.create_end_entry.grid(row=3, column=1, sticky="w", padx=6, pady=4)

        self.availability_editor = AvailabilityEditor(frame)
        self.availability_editor.grid(row=4, column=0, columnspan=2, sticky="ew", pady=6)

        options_frame = ttk.Frame(frame)
        options_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Checkbutton(options_frame, text="Auto approve and schedule", variable=self.create_auto_approve_var).pack(side="left")
        ttk.Button(options_frame, text="Create Plan", command=self.create_plan).pack(side="right")

        frame.columnconfigure(1, weight=1)

    def _build_plan_list_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Plans", padding=10)
        frame.pack(fill="both", expand=True)
        self.plan_listbox = tk.Listbox(frame, height=18)
        self.plan_listbox.pack(fill="both", expand=True)
        self.plan_listbox.bind("<<ListboxSelect>>", self.on_plan_selected)

    def _build_detail_panel(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)

        overview_tab = ttk.Frame(notebook, padding=10)
        tasks_tab = ttk.Frame(notebook, padding=10)
        proposals_tab = ttk.Frame(notebook, padding=10)
        reminders_tab = ttk.Frame(notebook, padding=10)
        log_tab = ttk.Frame(notebook, padding=10)

        notebook.add(overview_tab, text="Overview")
        notebook.add(tasks_tab, text="Tasks")
        notebook.add(proposals_tab, text="Proposals")
        notebook.add(reminders_tab, text="Reminders")
        notebook.add(log_tab, text="Activity")

        controls = ttk.Frame(overview_tab)
        controls.pack(fill="x", pady=(0, 8))
        ttk.Button(controls, text="Approve", command=self.approve_selected_plan).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Reschedule", command=self.reschedule_selected_plan).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Refresh Detail", command=self.refresh_selected_plan).pack(side="left")

        self.overview_text = ScrolledText(overview_tab, wrap="word", height=20)
        self.overview_text.pack(fill="both", expand=True)

        tasks_split = ttk.Panedwindow(tasks_tab, orient=tk.HORIZONTAL)
        tasks_split.pack(fill="both", expand=True)
        task_list_frame = ttk.Frame(tasks_split)
        task_form_frame = ttk.Frame(tasks_split)
        tasks_split.add(task_list_frame, weight=1)
        tasks_split.add(task_form_frame, weight=1)

        self.task_listbox = tk.Listbox(task_list_frame)
        self.task_listbox.pack(fill="both", expand=True)
        self.task_listbox.bind("<<ListboxSelect>>", self.on_task_selected)

        edit_frame = ttk.LabelFrame(task_form_frame, text="Edit Task", padding=8)
        edit_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(edit_frame, text="Title").grid(row=0, column=0, sticky="w")
        ttk.Entry(edit_frame, textvariable=self.edit_title_var, width=34).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(edit_frame, text="Minutes").grid(row=1, column=0, sticky="w")
        ttk.Entry(edit_frame, textvariable=self.edit_minutes_var, width=12).grid(row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(edit_frame, text="Target Date").grid(row=2, column=0, sticky="w")
        ttk.Entry(edit_frame, textvariable=self.edit_target_date_var, width=16).grid(row=2, column=1, sticky="w", padx=6, pady=4)
        ttk.Button(edit_frame, text="Save Task Edit", command=self.save_task_edit).grid(row=3, column=1, sticky="e", padx=6, pady=6)
        edit_frame.columnconfigure(1, weight=1)

        feedback_frame = ttk.LabelFrame(task_form_frame, text="Task Feedback", padding=8)
        feedback_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(feedback_frame, text="Status").grid(row=0, column=0, sticky="w")
        ttk.Combobox(feedback_frame, values=TASK_STATUS_OPTIONS, textvariable=self.selected_feedback_status, state="readonly", width=14).grid(row=0, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(feedback_frame, text="Actual Minutes").grid(row=1, column=0, sticky="w")
        ttk.Entry(feedback_frame, textvariable=self.feedback_minutes_var, width=12).grid(row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(feedback_frame, text="Difficulty 1-5").grid(row=2, column=0, sticky="w")
        ttk.Entry(feedback_frame, textvariable=self.feedback_difficulty_var, width=12).grid(row=2, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(feedback_frame, text="Confidence 0-1").grid(row=3, column=0, sticky="w")
        ttk.Entry(feedback_frame, textvariable=self.feedback_confidence_var, width=12).grid(row=3, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(feedback_frame, text="Reason or Note").grid(row=4, column=0, sticky="nw")
        self.feedback_note_text = ScrolledText(feedback_frame, width=28, height=4, wrap="word")
        self.feedback_note_text.insert("1.0", "Plan needs revision after execution friction.")
        self.feedback_note_text.grid(row=4, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(feedback_frame, text="Send Feedback", command=self.send_feedback).grid(row=5, column=1, sticky="e", padx=6, pady=6)
        feedback_frame.columnconfigure(1, weight=1)

        proposal_controls = ttk.Frame(proposals_tab)
        proposal_controls.pack(fill="x", pady=(0, 6))
        ttk.Button(proposal_controls, text="Apply Proposal", command=self.apply_selected_proposal).pack(side="left", padx=(0, 6))
        ttk.Button(proposal_controls, text="Reject Proposal", command=self.reject_selected_proposal).pack(side="left")
        self.proposal_listbox = tk.Listbox(proposals_tab)
        self.proposal_listbox.pack(fill="both", expand=True)
        self.proposal_listbox.bind("<<ListboxSelect>>", self.on_proposal_selected)

        reminders_controls = ttk.Frame(reminders_tab)
        reminders_controls.pack(fill="x", pady=(0, 6))
        ttk.Button(reminders_controls, text="Deliver Due Reminders", command=self.deliver_reminders).pack(side="left")
        self.reminder_listbox = tk.Listbox(reminders_tab)
        self.reminder_listbox.pack(fill="both", expand=True)

        self.log_text = ScrolledText(log_tab, wrap="word", height=20)
        self.log_text.pack(fill="both", expand=True)

    def refresh_all(self) -> None:
        self.client.base_url = self.base_url_var.get().rstrip("/")
        self.check_health()
        self.refresh_plans()
        if self.current_plan_version_id is not None:
            self.refresh_selected_plan()

    def check_health(self) -> None:
        try:
            health = self.client.health()
            self.health_label.config(text=health.get("status", "unknown"))
            self._log("Health check succeeded.")
        except ApiClientError as exc:
            self.health_label.config(text="offline")
            self._show_error(exc)

    def create_plan(self) -> None:
        title = self.create_title_entry.get().strip()
        description = self.create_description_text.get("1.0", "end").strip()
        if not title or not description:
            messagebox.showwarning("Missing data", "Title and description are required.")
            return
        payload = {
            "title": title,
            "description": description,
            "target_start_date": self.create_start_entry.get().strip(),
            "target_end_date": self.create_end_entry.get().strip(),
            "availability": self.availability_editor.get_payload(),
            "constraints": {},
            "planner": self.planner_var.get(),
            "auto_approve": self.create_auto_approve_var.get(),
        }
        try:
            response = self.client.create_plan(payload)
            self.current_plan_version_id = response["plan_version_id"]
            self._log(f"Created plan {response['plan_version_id']} with status {response['status']}.")
            self.refresh_plans()
            self.refresh_selected_plan()
        except ApiClientError as exc:
            self._show_error(exc)

    def refresh_plans(self) -> None:
        try:
            plans = self.client.list_plans()
        except ApiClientError as exc:
            self._show_error(exc)
            return

        self.plan_ids_by_index = [plan["plan_version_id"] for plan in plans]
        self.plan_listbox.delete(0, tk.END)
        for plan in plans:
            label = f"[{plan['status']}] #{plan['plan_version_id']} {plan['title']}"
            self.plan_listbox.insert(tk.END, label)

        if self.current_plan_version_id in self.plan_ids_by_index:
            index = self.plan_ids_by_index.index(self.current_plan_version_id)
            self.plan_listbox.selection_clear(0, tk.END)
            self.plan_listbox.selection_set(index)
            self.plan_listbox.activate(index)
        elif self.plan_ids_by_index:
            self.plan_listbox.selection_set(0)
            self.on_plan_selected()

    def on_plan_selected(self, _event: Any | None = None) -> None:
        selection = self.plan_listbox.curselection()
        if not selection:
            return
        self.current_plan_version_id = self.plan_ids_by_index[selection[0]]
        self.refresh_selected_plan()

    def refresh_selected_plan(self) -> None:
        if self.current_plan_version_id is None:
            return
        try:
            detail = self.client.get_plan(self.current_plan_version_id)
        except ApiClientError as exc:
            self._show_error(exc)
            return

        plan = detail["plan"]
        self.overview_text.delete("1.0", tk.END)
        self.overview_text.insert(
            tk.END,
            "\n".join(
                [
                    f"Plan Version: {plan['plan_version_id']}",
                    f"Status: {plan['status']}",
                    f"Title: {plan['title']}",
                    f"Goal: {plan['goal_title']}",
                    f"Window: {plan['target_start_date']} -> {plan['target_end_date']}",
                    "",
                    "Summary:",
                    plan["summary"],
                    "",
                    "Rationale:",
                    plan["rationale"],
                ]
            ),
        )

        tasks = detail["tasks"]
        self.task_ids_by_index = [task["id"] for task in tasks]
        self.task_listbox.delete(0, tk.END)
        for task in tasks:
            self.task_listbox.insert(
                tk.END,
                f"[{task['status']}] #{task['id']} {task['title']} ({task['estimated_minutes']}m)",
            )

        proposals = detail["proposals"]
        self.proposal_ids_by_index = [proposal["id"] for proposal in proposals]
        self.proposal_listbox.delete(0, tk.END)
        for proposal in proposals:
            self.proposal_listbox.insert(
                tk.END,
                f"[{proposal['status']}] #{proposal['id']} {proposal['proposal_type']} - {proposal['reason']}",
            )

        self.reminder_listbox.delete(0, tk.END)
        for reminder in detail["reminders"]:
            self.reminder_listbox.insert(
                tk.END,
                f"[{reminder['status']}] {reminder['reminder_type']} -> task #{reminder['task_id']} at {reminder['remind_at']}",
            )

        self._log(f"Loaded plan detail for plan version {self.current_plan_version_id}.")

    def on_task_selected(self, _event: Any | None = None) -> None:
        selection = self.task_listbox.curselection()
        if not selection or self.current_plan_version_id is None:
            return
        self.current_task_id = self.task_ids_by_index[selection[0]]
        try:
            detail = self.client.get_plan(self.current_plan_version_id)
        except ApiClientError as exc:
            self._show_error(exc)
            return
        task = next((item for item in detail["tasks"] if item["id"] == self.current_task_id), None)
        if task is None:
            return
        self.edit_title_var.set(task["title"])
        self.edit_minutes_var.set(str(task["estimated_minutes"]))
        self.edit_target_date_var.set(task["target_date"] or "")
        self.feedback_note_text.delete("1.0", tk.END)
        self.feedback_note_text.insert("1.0", f"Revise plan after issue with task: {task['title']}")

    def on_proposal_selected(self, _event: Any | None = None) -> None:
        selection = self.proposal_listbox.curselection()
        if not selection:
            return
        self.current_proposal_id = self.proposal_ids_by_index[selection[0]]

    def approve_selected_plan(self) -> None:
        if self.current_plan_version_id is None:
            return
        try:
            response = self.client.approve_plan(self.current_plan_version_id, planner=self.planner_var.get())
            self._log(f"Approved plan {self.current_plan_version_id}: status={response['status']}.")
            self.refresh_selected_plan()
            self.refresh_plans()
        except ApiClientError as exc:
            self._show_error(exc)

    def reschedule_selected_plan(self) -> None:
        if self.current_plan_version_id is None:
            return
        try:
            response = self.client.reschedule_plan(self.current_plan_version_id, planner=self.planner_var.get())
            self._log(f"Rescheduled plan {self.current_plan_version_id}: conflicts={len(response['conflicts'])}.")
            self.refresh_selected_plan()
            self.refresh_plans()
        except ApiClientError as exc:
            self._show_error(exc)

    def save_task_edit(self) -> None:
        if self.current_task_id is None:
            messagebox.showinfo("Select task", "Choose a task first.")
            return
        try:
            minutes = int(self.edit_minutes_var.get()) if self.edit_minutes_var.get().strip() else None
        except ValueError:
            messagebox.showwarning("Invalid minutes", "Estimated minutes must be a number.")
            return
        target_date = self.edit_target_date_var.get().strip() or None
        try:
            response = self.client.edit_task(
                self.current_task_id,
                planner=self.planner_var.get(),
                title=self.edit_title_var.get().strip() or None,
                estimated_minutes=minutes,
                target_date=target_date,
                regenerate_schedule=True,
            )
            self._log(f"Edited task {self.current_task_id}. Plan status={response['status']}.")
            self.refresh_selected_plan()
            self.refresh_plans()
        except ApiClientError as exc:
            self._show_error(exc)

    def send_feedback(self) -> None:
        if self.current_task_id is None or self.current_plan_version_id is None:
            messagebox.showinfo("Select task", "Choose a task first.")
            return

        actual_minutes = self._parse_optional_int(self.feedback_minutes_var.get())
        difficulty = self._parse_optional_int(self.feedback_difficulty_var.get())
        confidence = self._parse_optional_float(self.feedback_confidence_var.get())
        if self.feedback_confidence_var.get().strip() and confidence is None:
            messagebox.showwarning("Invalid confidence", "Confidence must be a number between 0 and 1.")
            return

        try:
            response = self.client.record_feedback(
                self.current_task_id,
                planner=self.planner_var.get(),
                status=self.selected_feedback_status.get(),
                actual_minutes=actual_minutes,
                difficulty=difficulty,
                confidence=confidence,
                note=self.feedback_note_text.get("1.0", "end").strip(),
            )
            self._log(f"Feedback on task {self.current_task_id}: {response['action']}.")
            self.refresh_selected_plan()
            self.refresh_plans()
        except ApiClientError as exc:
            self._show_error(exc)
            return

        if response["action"] == "propose_replan":
            should_generate = messagebox.askyesno(
                "Generate Replan",
                "The backend recommends a replan proposal. Generate it now?",
            )
            if should_generate:
                try:
                    proposal = self.client.generate_replan(
                        self.current_plan_version_id,
                        planner=self.planner_var.get(),
                        trigger_task_id=self.current_task_id,
                        trigger_reason=response["reason"],
                    )
                    self._log(f"Generated replan proposal #{proposal['id']}.")
                    self.refresh_selected_plan()
                except ApiClientError as exc:
                    self._show_error(exc)

    def apply_selected_proposal(self) -> None:
        if self.current_proposal_id is None:
            messagebox.showinfo("Select proposal", "Choose a proposal first.")
            return
        try:
            proposal = self.client.apply_proposal(self.current_proposal_id, planner=self.planner_var.get())
            payload = proposal.get("payload", {})
            if proposal["proposal_type"] == "replan" and payload.get("new_plan_version_id"):
                self.current_plan_version_id = int(payload["new_plan_version_id"])
            self._log(f"Applied proposal #{self.current_proposal_id}.")
            self.refresh_plans()
            self.refresh_selected_plan()
        except ApiClientError as exc:
            self._show_error(exc)

    def reject_selected_proposal(self) -> None:
        if self.current_proposal_id is None:
            messagebox.showinfo("Select proposal", "Choose a proposal first.")
            return
        try:
            self.client.reject_proposal(self.current_proposal_id, planner=self.planner_var.get())
            self._log(f"Rejected proposal #{self.current_proposal_id}.")
            self.refresh_selected_plan()
        except ApiClientError as exc:
            self._show_error(exc)

    def deliver_reminders(self) -> None:
        try:
            result = self.client.deliver_reminders(limit=20)
            self._log(f"Delivered {result['delivered_count']} reminders.")
            if result["reminders"]:
                lines = [f"{item['reminder_type']}: {item['task_title']}" for item in result["reminders"]]
                messagebox.showinfo("Delivered Reminders", "\n".join(lines))
            self.refresh_selected_plan()
        except ApiClientError as exc:
            self._show_error(exc)

    def _parse_optional_int(self, value: str) -> int | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None

    def _parse_optional_float(self, value: str) -> float | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _show_error(self, error: Exception) -> None:
        self._log(str(error))
        messagebox.showerror("Adaptive Planner", str(error))

    def _log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
