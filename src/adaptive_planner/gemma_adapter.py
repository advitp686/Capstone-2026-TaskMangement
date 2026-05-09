from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import requests

from .domain import GoalInput, PlanProposal, PlanningRequest, ReplanRequest, TaskProposal
from .planner import PlannerBackend


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SERVER_PATH = Path(
    r"F:\CAPSTONE - Copy\artifacts\benchmarks\tools\prism-win-vulkan-merged\llama-server.exe"
)
DEFAULT_MODEL_PATH = Path(r"F:\CAPSTONE - Copy\models\gemma4\gemma-4-E2B-it-Q4_K_M.gguf")
DEFAULT_LOG_PATH = REPO_ROOT / "artifacts" / "runtime" / "gemma_planner.server.log"


class GemmaPlannerError(RuntimeError):
    pass


@dataclass(slots=True)
class GemmaPlannerConfig:
    model_path: Path = DEFAULT_MODEL_PATH
    server_path: Path = DEFAULT_SERVER_PATH
    host: str = "127.0.0.1"
    port: int = 8091
    context_size: int = 8192
    max_completion_tokens: int = 768
    reasoning_budget: int = 256
    temperature: float = 0.1
    threads: int = 6
    threads_batch: int = 6
    batch_size: int = 256
    ubatch_size: int = 128
    parallel: int = 1
    seed: int = 42
    startup_timeout_sec: int = 180
    request_timeout_sec: int = 900
    reuse_existing_server: bool = True
    auto_start_server: bool = True
    reasoning_enabled: bool = True
    no_mmap: bool = True
    mlock: bool = False
    cache_ram_mib: int = 0
    cache_type_k: str = "f16"
    cache_type_v: str = "f16"
    flash_attn: str = "off"
    device: str = "Vulkan1"
    gpu_layers: int = 99
    log_path: Path = DEFAULT_LOG_PATH

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class GemmaPlannerBackend(PlannerBackend):
    def __init__(self, config: GemmaPlannerConfig | None = None) -> None:
        self.config = config or GemmaPlannerConfig()
        self._process: subprocess.Popen[str] | None = None
        self._started_server = False

    def create_plan(self, request: PlanningRequest) -> PlanProposal:
        self._ensure_server()
        payload = self._build_create_plan_payload(request)
        data = self._request_json_with_retry(
            payload,
            retry_hint=(
                "Retry with shorter fields. Keep the summary and rationale brief, and return only 4 to 5 tasks."
            ),
        )
        return self._proposal_from_dict(data, fallback_title=request.goal.title)

    def replan(self, request: ReplanRequest) -> PlanProposal:
        self._ensure_server()
        payload = self._build_replan_payload(request)
        data = self._request_json_with_retry(
            payload,
            retry_hint=(
                "Retry with shorter fields. Keep the rationale brief, preserve only the necessary tasks, and return valid JSON."
            ),
        )
        return self._proposal_from_dict(data, fallback_title=f"{request.snapshot.goal_title} (Replan)")

    def close(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=10)
        self._process = None
        self._started_server = False

    def __enter__(self) -> GemmaPlannerBackend:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_server(self) -> None:
        if self._server_ready():
            return
        if not self.config.auto_start_server:
            raise GemmaPlannerError("Gemma planner server is not reachable and auto_start_server is disabled.")
        self._start_server()
        if not self._wait_for_server():
            self.close()
            raise GemmaPlannerError("Gemma planner server did not become ready in time.")

    def _start_server(self) -> None:
        self.config.log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = self._build_server_command()
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        self._process = subprocess.Popen(
            [str(part) for part in cmd],
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        self._started_server = True

    def _build_server_command(self) -> list[str | Path]:
        cfg = self.config
        cmd: list[str | Path] = [
            cfg.server_path,
            "-m",
            cfg.model_path,
            "-c",
            str(cfg.context_size),
            "-n",
            str(cfg.max_completion_tokens),
            "-t",
            str(cfg.threads),
            "-tb",
            str(cfg.threads_batch),
            "-b",
            str(cfg.batch_size),
            "-ub",
            str(cfg.ubatch_size),
            "-np",
            str(cfg.parallel),
            "--host",
            cfg.host,
            "--port",
            str(cfg.port),
            "--reasoning",
            "on" if cfg.reasoning_enabled else "off",
            "--reasoning-budget",
            str(cfg.reasoning_budget),
            "--reasoning-format",
            "deepseek",
            "--cache-ram",
            str(cfg.cache_ram_mib),
            "--cache-type-k",
            cfg.cache_type_k,
            "--cache-type-v",
            cfg.cache_type_v,
            "--log-file",
            cfg.log_path,
        ]
        if cfg.mlock:
            cmd.append("--mlock")
        if cfg.no_mmap:
            cmd.append("--no-mmap")

        if cfg.device.strip().lower() == "none":
            cmd.extend(
                [
                    "-ngl",
                    "0",
                    "-dev",
                    "none",
                    "--no-op-offload",
                    "--flash-attn",
                    cfg.flash_attn,
                ]
            )
        else:
            cmd.extend(
                [
                    "-ngl",
                    str(cfg.gpu_layers),
                    "-dev",
                    cfg.device,
                    "--flash-attn",
                    cfg.flash_attn,
                ]
            )
        return cmd

    def _wait_for_server(self) -> bool:
        deadline = time.time() + self.config.startup_timeout_sec
        while time.time() < deadline:
            if self._server_ready():
                return True
            time.sleep(1)
        return False

    def _server_ready(self) -> bool:
        for endpoint in ("/health", "/v1/models"):
            try:
                response = requests.get(
                    f"{self.config.base_url}{endpoint}",
                    timeout=5,
                )
                if response.ok:
                    return True
            except requests.RequestException:
                pass
        return False

    def _chat(self, payload: dict[str, Any]) -> str:
        try:
            response = requests.post(
                f"{self.config.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.config.request_timeout_sec,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise GemmaPlannerError(f"Gemma planner request failed: {exc}") from exc

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise GemmaPlannerError("Gemma planner returned no choices.")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise GemmaPlannerError("Gemma planner returned an empty response.")
        return content

    def _request_json_with_retry(self, payload: dict[str, Any], retry_hint: str) -> dict[str, Any]:
        first_text = self._chat(payload)
        try:
            return self._extract_json_payload(first_text)
        except GemmaPlannerError as first_error:
            retry_payload = dict(payload)
            retry_payload["messages"] = list(payload["messages"]) + [
                {
                    "role": "user",
                    "content": (
                        "Your previous answer was not valid complete JSON. "
                        f"{retry_hint}"
                    ),
                }
            ]
            retry_payload["max_tokens"] = min(
                max(int(payload.get("max_tokens", self.config.max_completion_tokens) * 1.6), 1200),
                2200,
            )
            second_text = self._chat(retry_payload)
            try:
                return self._extract_json_payload(second_text)
            except GemmaPlannerError as second_error:
                raise GemmaPlannerError(
                    f"{first_error} Retry also failed: {second_error}"
                ) from second_error

    def _build_create_plan_payload(self, request: PlanningRequest) -> dict[str, Any]:
        goal = request.goal
        system_prompt = (
            "You are a planning model inside an adaptive task planner. "
            "Return only valid JSON. Do not use markdown fences. "
            "Do not add commentary before or after the JSON."
        )
        user_prompt = (
            "Create a structured plan proposal for the following goal.\n\n"
            f"Goal title: {goal.title}\n"
            f"Goal description: {goal.description}\n"
            f"Plan start date: {goal.target_start_date.isoformat()}\n"
            f"Plan end date: {goal.target_end_date.isoformat()}\n"
            f"Availability windows: {self._format_availability(goal)}\n"
            f"Constraints: {json.dumps(goal.constraints, ensure_ascii=False)}\n"
            f"Assistant planning context: {self._format_assistant_context(goal.constraints)}\n"
            f"Existing active plan context: {json.dumps(request.active_plan_context, ensure_ascii=False)}\n\n"
            "Return a JSON object with this exact shape:\n"
            "{\n"
            '  "title": "short plan title",\n'
            '  "summary": "one-paragraph plan summary",\n'
            '  "rationale": "short explanation of the decomposition strategy",\n'
            '  "tasks": [\n'
            "    {\n"
            '      "key": "task_1",\n'
            '      "title": "task title",\n'
            '      "summary": "task description",\n'
            '      "estimated_minutes": 120,\n'
            '      "difficulty": "low|medium|high",\n'
            '      "depends_on_keys": [],\n'
            '      "target_date": "YYYY-MM-DD or null"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Return between 6 and 10 tasks for learning, revision, interview, or technical study goals.\n"
            "- For Python or programming goals, name concrete topics and hands-on practice work.\n"
            "- Use task summaries to include what counts as complete.\n"
            "- Use dependency links only when necessary.\n"
            "- Do not assign exact clock times.\n"
            "- Keep tasks realistic for the date range.\n"
            "- Keep the plan summary under 70 words.\n"
            "- Keep the rationale under 80 words.\n"
            "- Keep each task summary under 30 words.\n"
            "- Prefer estimated_minutes in multiples of 30.\n"
            "- Make the output parseable JSON only."
        )
        return self._base_payload(system_prompt, user_prompt)

    def _build_replan_payload(self, request: ReplanRequest) -> dict[str, Any]:
        system_prompt = (
            "You are a replanning model inside an adaptive task planner. "
            "Return only valid JSON. Do not use markdown fences. "
            "Do not add commentary before or after the JSON."
        )
        tasks_json = json.dumps(request.snapshot.tasks, ensure_ascii=False, indent=2)
        dependencies_json = json.dumps(request.snapshot.dependencies, ensure_ascii=False)
        user_prompt = (
            "Revise the plan after execution friction.\n\n"
            f"Goal title: {request.snapshot.goal_title}\n"
            f"Goal description: {request.snapshot.goal_description}\n"
            f"Plan start date: {request.snapshot.target_start_date.isoformat()}\n"
            f"Plan end date: {request.snapshot.target_end_date.isoformat()}\n"
            f"Trigger reason: {request.trigger_reason}\n"
            f"Trigger task id: {request.trigger_task_id}\n"
            "Current tasks:\n"
            f"{tasks_json}\n"
            "Current dependencies:\n"
            f"{dependencies_json}\n\n"
            "Return a revised full plan as JSON with this exact shape:\n"
            "{\n"
            '  "title": "short replan title",\n'
            '  "summary": "one-paragraph replan summary",\n'
            '  "rationale": "short explanation of what changed and why",\n'
            '  "tasks": [\n'
            "    {\n"
            '      "key": "task_1",\n'
            '      "title": "task title",\n'
            '      "summary": "task description",\n'
            '      "estimated_minutes": 120,\n'
            '      "difficulty": "low|medium|high",\n'
            '      "depends_on_keys": [],\n'
            '      "target_date": "YYYY-MM-DD or null"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Insert recovery or prerequisite steps if needed.\n"
            "- If the user says the plan is vague, replace vague work with concrete topic and practice steps.\n"
            "- Keep unaffected work when possible.\n"
            "- Do not assign exact clock times.\n"
            "- Keep the replan summary under 70 words.\n"
            "- Keep the rationale under 80 words.\n"
            "- Keep each task summary under 30 words.\n"
            "- Make the output parseable JSON only."
        )
        return self._base_payload(system_prompt, user_prompt)

    def _base_payload(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.config.max_completion_tokens,
            "temperature": self.config.temperature,
            "stream": False,
            "seed": self.config.seed,
        }

    def _extract_json_payload(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
        if fenced_match:
            cleaned = fenced_match.group(1)
        else:
            cleaned = self._extract_first_json_object(cleaned)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise GemmaPlannerError(f"Gemma planner returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise GemmaPlannerError("Gemma planner JSON must be an object.")
        return payload

    def _extract_first_json_object(self, text: str) -> str:
        start = text.find("{")
        if start == -1:
            raise GemmaPlannerError("Gemma planner response did not contain a JSON object.")
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        raise GemmaPlannerError("Gemma planner response contained an incomplete JSON object.")

    def _proposal_from_dict(self, data: dict[str, Any], fallback_title: str) -> PlanProposal:
        tasks_raw = data.get("tasks")
        if not isinstance(tasks_raw, list) or not tasks_raw:
            raise GemmaPlannerError("Gemma planner response must include a non-empty tasks list.")

        tasks: list[TaskProposal] = []
        seen_keys: set[str] = set()
        for index, raw_task in enumerate(tasks_raw, start=1):
            if not isinstance(raw_task, dict):
                raise GemmaPlannerError("Each task must be a JSON object.")
            key = self._normalize_key(raw_task.get("key") or f"task_{index}", index)
            while key in seen_keys:
                key = f"{key}_{index}"
            seen_keys.add(key)

            estimated_minutes = self._coerce_positive_int(raw_task.get("estimated_minutes"), default=90)
            difficulty = self._normalize_difficulty(raw_task.get("difficulty"))
            target_date = self._parse_optional_date(raw_task.get("target_date"))

            tasks.append(
                TaskProposal(
                    key=key,
                    title=str(raw_task.get("title") or f"Task {index}"),
                    summary=str(raw_task.get("summary") or ""),
                    estimated_minutes=estimated_minutes,
                    difficulty=difficulty,
                    depends_on_keys=self._normalize_depends(raw_task.get("depends_on_keys")),
                    target_date=target_date,
                )
            )

        valid_keys = {task.key for task in tasks}
        normalized_tasks: list[TaskProposal] = []
        prior_keys: set[str] = set()
        for task in tasks:
            allowed_depends = [
                key
                for key in task.depends_on_keys
                if key in valid_keys and key in prior_keys and key != task.key
            ]
            normalized_tasks.append(
                TaskProposal(
                    key=task.key,
                    title=task.title,
                    summary=task.summary,
                    estimated_minutes=task.estimated_minutes,
                    difficulty=task.difficulty,
                    depends_on_keys=allowed_depends,
                    target_date=task.target_date,
                )
            )
            prior_keys.add(task.key)

        title = str(data.get("title") or fallback_title).strip() or fallback_title
        summary = str(data.get("summary") or f"Plan proposal for {fallback_title}.").strip()
        rationale = str(data.get("rationale") or "Model-generated plan proposal.").strip()
        return PlanProposal(title=title, summary=summary, rationale=rationale, tasks=normalized_tasks)

    def _normalize_key(self, value: Any, index: int) -> str:
        raw = str(value).strip().lower()
        raw = re.sub(r"[^a-z0-9]+", "_", raw)
        raw = raw.strip("_")
        return raw or f"task_{index}"

    def _normalize_difficulty(self, value: Any) -> str:
        normalized = str(value or "medium").strip().lower()
        if normalized not in {"low", "medium", "high"}:
            return "medium"
        return normalized

    def _normalize_depends(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [self._normalize_key(item, index + 1) for index, item in enumerate(value)]

    def _coerce_positive_int(self, value: Any, default: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        if number <= 0:
            return default
        return min(number, 24 * 60)

    def _parse_optional_date(self, value: Any) -> date | None:
        if value in (None, "", "null"):
            return None
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None

    def _format_availability(self, goal: GoalInput) -> str:
        if not goal.availability:
            return "[]"
        formatted = []
        for window in goal.availability:
            formatted.append(
                {
                    "weekday": window.weekday,
                    "start_time": window.start_time.isoformat(timespec="minutes"),
                    "end_time": window.end_time.isoformat(timespec="minutes"),
                }
            )
        return json.dumps(formatted, ensure_ascii=False)

    def _format_assistant_context(self, constraints: dict[str, Any]) -> str:
        keys = (
            "assistant_summary",
            "clarification_answers",
            "references_summary",
            "web_search_summary",
        )
        context = {key: constraints.get(key) for key in keys if constraints.get(key)}
        return json.dumps(context, ensure_ascii=False)
