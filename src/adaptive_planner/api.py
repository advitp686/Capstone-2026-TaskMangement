from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api_models import (
    ApplyProposalRequest,
    CreatePlanRequest,
    CreatePlanResponse,
    DeliverRemindersRequest,
    DeliverRemindersResponse,
    EditTaskRequest,
    FeedbackRequest,
    FeedbackResponse,
    GenerateReplanRequest,
    PlanDetailResponse,
    PlanSummaryResponse,
    ProposalResponse,
    ScheduleActionResponse,
)
from .domain import FeedbackInput, GoalInput, PlanStatus, PlanningRequest, ProposalKind, TaskStatus
from .gemma_adapter import GemmaPlannerBackend, GemmaPlannerConfig
from .planner import MockPlannerBackend, PlannerBackend
from .reminders import ReminderService
from .services import PlanningService
from .storage import PlannerDatabase

WEB_UI_DIR = Path(__file__).resolve().parent / "webui"
WEB_UI_STATIC_DIR = WEB_UI_DIR / "static"


class AppContainer:
    def __init__(
        self,
        database_path: str | Path,
        *,
        gemma_config: GemmaPlannerConfig | None = None,
    ) -> None:
        self.database = PlannerDatabase(database_path)
        self.database.initialize()
        self.reminder_service = ReminderService(self.database)
        self.gemma_config = gemma_config or GemmaPlannerConfig()
        self._planners: dict[str, PlannerBackend] = {}

    def get_planner(self, planner_mode: str) -> PlannerBackend:
        if planner_mode not in self._planners:
            if planner_mode == "gemma":
                self._planners[planner_mode] = GemmaPlannerBackend(self.gemma_config)
            else:
                self._planners[planner_mode] = MockPlannerBackend()
        return self._planners[planner_mode]

    def get_service(self, planner_mode: str) -> PlanningService:
        return PlanningService(
            database=self.database,
            planner=self.get_planner(planner_mode),
        )

    def close(self) -> None:
        for planner in self._planners.values():
            close_method = getattr(planner, "close", None)
            if callable(close_method):
                close_method()


def create_app(
    database_path: str | Path,
    *,
    gemma_config: GemmaPlannerConfig | None = None,
) -> FastAPI:
    container = AppContainer(database_path=database_path, gemma_config=gemma_config)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            container.close()

    app = FastAPI(title="Adaptive Planner API", version="0.1.0", lifespan=lifespan)
    app.state.container = container

    if WEB_UI_STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=WEB_UI_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def web_ui() -> FileResponse:
        if not WEB_UI_DIR.exists():
            raise HTTPException(status_code=404, detail="web UI files not found")
        return FileResponse(WEB_UI_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/plans", response_model=list[PlanSummaryResponse])
    def list_plans(status: str | None = Query(default=None)) -> list[PlanSummaryResponse]:
        plan_status = _parse_optional_plan_status(status)
        plans = container.database.list_plan_versions(plan_status)
        return [_build_plan_summary(container.database, plan["id"]) for plan in plans]

    @app.post("/plans", response_model=CreatePlanResponse)
    def create_plan(request: CreatePlanRequest) -> CreatePlanResponse:
        goal = GoalInput(
            title=request.title,
            description=request.description,
            target_start_date=request.target_start_date,
            target_end_date=request.target_end_date,
            availability=[
                _availability_from_model(window)
                for window in request.availability
            ],
            constraints=request.constraints,
        )
        service = container.get_service(request.planner)
        goal_id, plan_version_id = service.create_plan(PlanningRequest(goal=goal))

        if request.auto_approve:
            result = service.approve_and_schedule(plan_version_id)
            status_value = container.database.get_plan_version(plan_version_id)["status"]
            return CreatePlanResponse(
                goal_id=goal_id,
                plan_version_id=plan_version_id,
                status=status_value,
                scheduled_blocks=len(result.blocks),
                conflicts=len(result.conflicts),
            )

        return CreatePlanResponse(
            goal_id=goal_id,
            plan_version_id=plan_version_id,
            status=container.database.get_plan_version(plan_version_id)["status"],
        )

    @app.get("/plans/{plan_version_id}", response_model=PlanDetailResponse)
    def get_plan(plan_version_id: int) -> PlanDetailResponse:
        return _build_plan_detail(container.database, plan_version_id)

    @app.post("/plans/{plan_version_id}/approve", response_model=ScheduleActionResponse)
    def approve_plan(plan_version_id: int, planner: str = Query(default="mock")) -> ScheduleActionResponse:
        _ensure_plan_exists(container.database, plan_version_id)
        result = container.get_service(planner).approve_and_schedule(plan_version_id)
        return ScheduleActionResponse(
            plan_version_id=plan_version_id,
            status=container.database.get_plan_version(plan_version_id)["status"],
            scheduled_blocks=len(result.blocks),
            conflicts=[asdict(conflict) for conflict in result.conflicts],
        )

    @app.post("/plans/{plan_version_id}/reschedule", response_model=ScheduleActionResponse)
    def reschedule_plan(plan_version_id: int, planner: str = Query(default="mock")) -> ScheduleActionResponse:
        _ensure_plan_exists(container.database, plan_version_id)
        result = container.get_service(planner).regenerate_schedule(plan_version_id)
        return ScheduleActionResponse(
            plan_version_id=plan_version_id,
            status=container.database.get_plan_version(plan_version_id)["status"],
            scheduled_blocks=len(result.blocks),
            conflicts=[asdict(conflict) for conflict in result.conflicts],
        )

    @app.post("/plans/{plan_version_id}/replan", response_model=ProposalResponse)
    def generate_replan(plan_version_id: int, request: GenerateReplanRequest) -> ProposalResponse:
        _ensure_plan_exists(container.database, plan_version_id)
        service = container.get_service(request.planner)
        new_plan_version_id = service.generate_replan_proposal(
            plan_version_id=plan_version_id,
            trigger_task_id=request.trigger_task_id,
            trigger_reason=request.trigger_reason,
        )
        proposals = container.database.list_proposals(
            plan_version_id=plan_version_id,
            proposal_type=ProposalKind.REPLAN,
        )
        proposal = proposals[-1]
        proposal["payload"]["new_plan_version_id"] = new_plan_version_id
        return ProposalResponse(**proposal)

    @app.patch("/tasks/{task_id}", response_model=ScheduleActionResponse)
    def edit_task(task_id: int, request: EditTaskRequest, planner: str = Query(default="mock")) -> ScheduleActionResponse:
        task = _ensure_task_exists(container.database, task_id)
        service = container.get_service(planner)
        service.edit_task(
            task_id,
            title=request.title,
            estimated_minutes=request.estimated_minutes,
            target_date=request.target_date,
        )
        if request.regenerate_schedule:
            result = service.regenerate_schedule(task["plan_version_id"])
            return ScheduleActionResponse(
                plan_version_id=task["plan_version_id"],
                status=container.database.get_plan_version(task["plan_version_id"])["status"],
                scheduled_blocks=len(result.blocks),
                conflicts=[asdict(conflict) for conflict in result.conflicts],
            )
        return ScheduleActionResponse(
            plan_version_id=task["plan_version_id"],
            status=container.database.get_plan_version(task["plan_version_id"])["status"],
            scheduled_blocks=len(container.database.list_schedule_blocks(task["plan_version_id"])),
            conflicts=[],
        )

    @app.post("/tasks/{task_id}/feedback", response_model=FeedbackResponse)
    def record_feedback(task_id: int, request: FeedbackRequest, planner: str = Query(default="mock")) -> FeedbackResponse:
        _ensure_task_exists(container.database, task_id)
        try:
            task_status = TaskStatus(request.status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid task status: {request.status}") from exc
        try:
            outcome = container.get_service(planner).record_feedback(
                task_id,
                FeedbackInput(
                    status=task_status,
                    actual_minutes=request.actual_minutes,
                    difficulty=request.difficulty,
                    confidence=request.confidence,
                    note=request.note,
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return FeedbackResponse(
            task_id=task_id,
            action=outcome.action.value,
            reason=outcome.reason,
            requires_user_confirmation=outcome.requires_user_confirmation,
            details=outcome.details,
        )

    @app.get("/plans/{plan_version_id}/proposals", response_model=list[ProposalResponse])
    def list_proposals(plan_version_id: int) -> list[ProposalResponse]:
        _ensure_plan_exists(container.database, plan_version_id)
        proposals = container.database.list_proposals(plan_version_id=plan_version_id)
        return [ProposalResponse(**proposal) for proposal in proposals]

    @app.post("/proposals/{proposal_id}", response_model=ProposalResponse)
    def act_on_proposal(proposal_id: int, request: ApplyProposalRequest, planner: str = Query(default="mock")) -> ProposalResponse:
        proposal = _ensure_proposal_exists(container.database, proposal_id)
        service = container.get_service(planner)
        if request.action == "apply":
            if proposal["proposal_type"] == ProposalKind.REBALANCE.value:
                service.apply_rebalance(proposal_id)
            elif proposal["proposal_type"] == ProposalKind.REPLAN.value:
                service.apply_replan_proposal(proposal_id)
            else:
                raise HTTPException(status_code=400, detail="unsupported proposal type")
        else:
            service.reject_proposal(proposal_id)
        updated = container.database.get_proposal(proposal_id)
        return ProposalResponse(**updated)

    @app.post("/reminders/deliver", response_model=DeliverRemindersResponse)
    def deliver_reminders(request: DeliverRemindersRequest) -> DeliverRemindersResponse:
        as_of = request.as_of or datetime.now()
        delivered = container.reminder_service.deliver_due_reminders(as_of, limit=request.limit)
        return DeliverRemindersResponse(
            delivered_count=len(delivered),
            reminders=[asdict(item) for item in delivered],
        )

    return app


def _availability_from_model(model) -> Any:
    from .domain import AvailabilityWindow

    return AvailabilityWindow(
        weekday=model.weekday,
        start_time=model.start_time,
        end_time=model.end_time,
    )


def _parse_optional_plan_status(status: str | None) -> PlanStatus | None:
    if status is None:
        return None
    try:
        return PlanStatus(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid plan status: {status}") from exc


def _build_plan_summary(database: PlannerDatabase, plan_version_id: int) -> PlanSummaryResponse:
    plan = database.get_plan_version(plan_version_id)
    goal = database.get_goal(plan["goal_id"])
    return PlanSummaryResponse(
        goal_id=goal["id"],
        plan_version_id=plan["id"],
        status=plan["status"],
        title=plan["title"],
        summary=plan["summary"],
        rationale=plan["rationale"],
        goal_title=goal["title"],
        goal_description=goal["description"],
        target_start_date=goal["target_start_date"],
        target_end_date=goal["target_end_date"],
    )


def _build_plan_detail(database: PlannerDatabase, plan_version_id: int) -> PlanDetailResponse:
    _ensure_plan_exists(database, plan_version_id)
    plan = _build_plan_summary(database, plan_version_id)
    tasks = database.list_tasks(plan_version_id)
    schedule_blocks = database.list_schedule_blocks(plan_version_id)
    reminders = database.list_reminders(plan_version_id)
    proposals = database.list_proposals(plan_version_id=plan_version_id)
    policy_decisions = database.list_policy_decisions(plan_version_id)
    return PlanDetailResponse(
        plan=plan,
        tasks=tasks,
        dependencies=database.list_dependencies(plan_version_id),
        schedule_blocks=schedule_blocks,
        reminders=reminders,
        proposals=proposals,
        policy_decisions=policy_decisions,
    )


def _ensure_plan_exists(database: PlannerDatabase, plan_version_id: int) -> dict[str, Any]:
    try:
        return database.get_plan_version(plan_version_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ensure_task_exists(database: PlannerDatabase, task_id: int) -> dict[str, Any]:
    try:
        return database.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ensure_proposal_exists(database: PlannerDatabase, proposal_id: int) -> dict[str, Any]:
    try:
        return database.get_proposal(proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
