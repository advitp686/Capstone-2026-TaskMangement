from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

import requests

from .domain import TaskStatus


COMPLEX_GOAL_TERMS = {
    "learn",
    "study",
    "revise",
    "revision",
    "practice",
    "exam",
    "interview",
    "python",
    "math",
    "project",
    "roadmap",
}


@dataclass(slots=True)
class AssistantQuestion:
    id: str
    prompt: str
    recommended_option: str
    options: list[str]
    allow_custom: bool = True


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    content: str


@dataclass(slots=True)
class IntakeResult:
    requires_clarification: bool
    questions: list[AssistantQuestion]
    readiness_summary: str
    assistant_summary: str
    references_summary: str = ""
    web_search_used: bool = False
    web_search_available: bool = False
    web_search_message: str = ""
    search_results: list[SearchResult] = field(default_factory=list)


class TavilySearchClient:
    def __init__(self, api_key: str | None = None, timeout_sec: int = 20) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.timeout_sec = timeout_sec

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, *, max_results: int = 3) -> list[SearchResult]:
        if not self.api_key:
            return []
        response = requests.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            },
            timeout=self.timeout_sec,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        parsed: list[SearchResult] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            parsed.append(
                SearchResult(
                    title=str(item.get("title") or "Untitled result"),
                    url=str(item.get("url") or ""),
                    content=str(item.get("content") or "")[:900],
                )
            )
        return parsed


class PlanningAssistant:
    def __init__(self, search_client: TavilySearchClient | None = None) -> None:
        self.search_client = search_client or TavilySearchClient()

    def run_intake(
        self,
        *,
        title: str,
        description: str,
        target_start_date: date,
        target_end_date: date,
        references: list[dict[str, Any]],
        clarification_answers: dict[str, str],
        use_web_search: bool,
    ) -> IntakeResult:
        text = f"{title} {description}".lower()
        is_complex = any(term in text for term in COMPLEX_GOAL_TERMS)
        references_summary = self._summarize_references(references)
        questions = self._questions_for_goal(text, clarification_answers) if is_complex else []

        search_results: list[SearchResult] = []
        web_message = "Web search was not needed for this goal."
        web_available = self.search_client.available
        web_used = False
        if is_complex and use_web_search:
            if not web_available:
                web_message = "Tavily is not configured, so the assistant continued with local goal and reference context."
            else:
                try:
                    search_results = self.search_client.search(
                        f"{title} {description} learning roadmap practical tasks",
                        max_results=3,
                    )
                    web_used = bool(search_results)
                    web_message = (
                        "Web context was added to the planning summary."
                        if web_used
                        else "Tavily returned no usable results, so planning continued with local context."
                    )
                except requests.RequestException as exc:
                    web_message = f"Tavily search failed, so planning continued without web context: {exc}"

        answer_summary = self._summarize_answers(clarification_answers)
        search_summary = self._summarize_search_results(search_results)
        readiness_summary = self._build_readiness_summary(
            title=title,
            target_start_date=target_start_date,
            target_end_date=target_end_date,
            has_questions=bool(questions),
            references_summary=references_summary,
            web_message=web_message,
        )
        assistant_summary = "\n".join(
            part
            for part in [
                readiness_summary,
                answer_summary,
                references_summary,
                search_summary,
            ]
            if part
        )
        return IntakeResult(
            requires_clarification=bool(questions),
            questions=questions,
            readiness_summary=readiness_summary,
            assistant_summary=assistant_summary,
            references_summary=references_summary,
            web_search_used=web_used,
            web_search_available=web_available,
            web_search_message=web_message,
            search_results=search_results,
        )

    def build_feedback_review(
        self,
        *,
        task: dict[str, Any],
        status: TaskStatus,
        note: str,
        policy_reason: str,
        requires_user_confirmation: bool,
    ) -> dict[str, Any]:
        note_clean = note.strip()
        questions: list[AssistantQuestion] = []
        if status in {TaskStatus.BLOCKED, TaskStatus.FAILED}:
            questions = [
                AssistantQuestion(
                    id="blocker_type",
                    prompt="What is the main reason this task is not working?",
                    recommended_option="The plan is too vague",
                    options=[
                        "The plan is too vague",
                        "The topic is too hard right now",
                        "I need more time or a smaller step",
                    ],
                ),
                AssistantQuestion(
                    id="best_fix",
                    prompt="What kind of change would help most?",
                    recommended_option="Break it into smaller practice steps",
                    options=[
                        "Break it into smaller practice steps",
                        "Add prerequisite revision",
                        "Move it to a later time",
                    ],
                ),
            ]
        return {
            "user_report": {
                "task_title": task["title"],
                "status": status.value,
                "note": note_clean,
            },
            "system_understanding": self._understand_feedback(status, note_clean),
            "decision_reason": policy_reason,
            "requires_user_confirmation": requires_user_confirmation,
            "suggested_next_step": (
                "Review a suggested change before applying anything to the plan."
                if requires_user_confirmation
                else "Keep the plan, but collect a little more context."
            ),
            "clarification_questions": [asdict(question) for question in questions],
        }

    def reply_to_message(
        self,
        *,
        message: str,
        plan: dict[str, Any],
        tasks: list[dict[str, Any]],
        schedule_blocks: list[dict[str, Any]],
        current_summary: str,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        text = message.lower()
        title = plan.get("title", "this plan")
        next_task = next(
            (task for task in tasks if task.get("status") not in {"done", "canceled", "skipped"}),
            tasks[0] if tasks else None,
        )
        suggested_actions: list[dict[str, Any]] = []

        if any(term in text for term in ("specific", "vague", "practice", "roadmap", "replan")):
            reply = (
                f"I can help make {title} more specific. The current plan should be reviewed as a roadmap, "
                "then converted into smaller topic and practice steps before anything is applied."
            )
            suggested_actions.append(
                {
                    "action": "assistant_replan",
                    "label": "Suggest a clearer roadmap",
                    "payload": {"reason": message},
                }
            )
        elif any(term in text for term in ("stuck", "blocked", "hard", "confusing")):
            task_text = f" on '{next_task['title']}'" if next_task else ""
            reply = (
                f"It sounds like you are stuck{task_text}. I would first identify whether the issue is missing "
                "prerequisites, vague instructions, or not enough practice time."
            )
            suggested_actions.append(
                {
                    "action": "ask_clarification",
                    "label": "Ask me diagnostic questions",
                    "payload": {"reason": message},
                }
            )
        elif any(term in text for term in ("schedule", "time", "move", "delay")):
            reply = "I can review the schedule blocks and suggest a safer timing change without applying it automatically."
            suggested_actions.append(
                {
                    "action": "reschedule",
                    "label": "Review schedule",
                    "payload": {"reason": message},
                }
            )
        else:
            reply = (
                f"I am looking at {title}. Tell me if you want the plan made more specific, easier, "
                "more practice-heavy, or rescheduled."
            )

        updated_summary = self._merge_summary(current_summary, message, reply, len(schedule_blocks))
        return reply, updated_summary, suggested_actions

    def _questions_for_goal(self, text: str, answers: dict[str, str]) -> list[AssistantQuestion]:
        questions: list[AssistantQuestion] = []
        if "current_level" not in answers:
            questions.append(
                AssistantQuestion(
                    id="current_level",
                    prompt="What is your current comfort level?",
                    recommended_option="I know basics but need revision",
                    options=[
                        "I know basics but need revision",
                        "I am a beginner",
                        "I know intermediate topics but need practice",
                    ],
                )
            )
        if "goal_type" not in answers:
            questions.append(
                AssistantQuestion(
                    id="goal_type",
                    prompt="What are you preparing for?",
                    recommended_option="General confidence",
                    options=["General confidence", "Exam or interview", "A project or assignment"],
                )
            )
        if "practice_style" not in answers:
            questions.append(
                AssistantQuestion(
                    id="practice_style",
                    prompt="What should the plan emphasize?",
                    recommended_option="Revision plus hands-on exercises",
                    options=[
                        "Revision plus hands-on exercises",
                        "Mostly theory review",
                        "Mostly coding problems",
                    ],
                )
            )
        if "python" in text and "weak_areas" not in answers:
            questions.append(
                AssistantQuestion(
                    id="weak_areas",
                    prompt="Which Python areas feel weakest?",
                    recommended_option="OOP, functions, and problem solving",
                    options=[
                        "OOP, functions, and problem solving",
                        "Data structures and loops",
                        "File handling, exceptions, and modules",
                    ],
                )
            )
        return questions[:4]

    def _summarize_references(self, references: list[dict[str, Any]]) -> str:
        if not references:
            return ""
        names = [str(ref.get("filename") or "reference") for ref in references[:5]]
        total_chars = sum(len(str(ref.get("content") or "")) for ref in references)
        preview_words: list[str] = []
        for ref in references[:2]:
            preview_words.extend(str(ref.get("content") or "").strip().split()[:80])
        preview = " ".join(preview_words)
        return (
            f"Reference context: {len(references)} file(s) attached ({', '.join(names)}), "
            f"about {total_chars} characters. Preview: {preview[:500]}"
        )

    def _summarize_answers(self, answers: dict[str, str]) -> str:
        if not answers:
            return ""
        pairs = [f"{key}: {value}" for key, value in sorted(answers.items()) if value]
        return "Clarification answers: " + "; ".join(pairs)

    def _summarize_search_results(self, results: list[SearchResult]) -> str:
        if not results:
            return ""
        lines = [f"- {item.title}: {item.content[:180]} ({item.url})" for item in results]
        return "Web context:\n" + "\n".join(lines)

    def _build_readiness_summary(
        self,
        *,
        title: str,
        target_start_date: date,
        target_end_date: date,
        has_questions: bool,
        references_summary: str,
        web_message: str,
    ) -> str:
        question_text = (
            "The assistant needs a few answers before creating a strong roadmap."
            if has_questions
            else "The assistant has enough context to create the first roadmap."
        )
        reference_text = "References were included." if references_summary else "No reference files were included."
        return (
            f"Planning '{title}' from {target_start_date.isoformat()} to {target_end_date.isoformat()}. "
            f"{question_text} {reference_text} {web_message}"
        )

    def _understand_feedback(self, status: TaskStatus, note: str) -> str:
        if "vague" in note.lower():
            return "The task likely needs clearer topic steps and practice criteria."
        if status == TaskStatus.BLOCKED:
            return "The task is blocked, so continuing without diagnosis may keep the plan stuck."
        if status == TaskStatus.FAILED:
            return "The current approach failed, so the plan should recover from an earlier point."
        return "The feedback is useful evidence for the next planning decision."

    def _merge_summary(self, current_summary: str, message: str, reply: str, schedule_count: int) -> str:
        pieces = [
            current_summary.strip(),
            f"Latest user concern: {message.strip()[:240]}",
            f"Assistant response: {reply[:240]}",
            f"Known scheduled blocks: {schedule_count}",
        ]
        merged = "\n".join(piece for piece in pieces if piece)
        return merged[-3000:]
