"""The agent loop.

A plain provider/tool loop with a step ceiling. Week 2 ports this to LangGraph
for session memory and resumable confirmation; the interfaces here
(`run` -> `AgentResult`) are what the UI and the eval harness depend on, so that
port should not change them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from psa.agent.policy import classify, extract_citations
from psa.config import settings
from psa.mcp_server import call_tool
from psa.providers import Provider, Turn, Usage, get_provider
from psa.roles import ConfirmationRequired, PermissionDenied, PreconditionFailed

MAX_STEPS = 6


@dataclass
class AgentResult:
    query: str
    role: str
    answer: str
    behavior: str
    citations: list[str] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)
    turns: list[Turn] = field(default_factory=list)
    denials: list[str] = field(default_factory=list)
    # Actions the caller was authorized for but that the runbook precondition refused.
    blocked_actions: list[str] = field(default_factory=list)
    pending_confirmation: dict | None = None
    grounded: bool = False
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    hit_step_ceiling: bool = False


def run(
    query: str,
    role: str | None = None,
    user: str | None = None,
    provider: Provider | None = None,
) -> AgentResult:
    cfg = settings()
    role = role or cfg.role
    user = user or cfg.user
    provider = provider or get_provider()

    history: list[Turn] = []
    tools_called: list[str] = []
    denials: list[str] = []
    blocked: list[str] = []
    pending: dict | None = None
    usage = Usage()
    grounded = False
    answer: str | None = None
    ceiling = True

    started = time.perf_counter()

    for _ in range(MAX_STEPS):
        step = provider.next_step(query, role, history)
        usage = usage + step.usage

        if step.is_final:
            answer = step.answer or ""
            ceiling = False
            break

        for request in step.tool_calls:
            tools_called.append(request.name)
            turn = Turn(tool=request.name, args=dict(request.args), call_id=request.call_id)
            try:
                turn.result = call_tool(request.name, request.args, role=role, user=user)
                if request.name == "search_docs":
                    grounded = grounded or bool(turn.result.get("grounded"))
            except ConfirmationRequired as exc:
                # Stop here. A gated action is the human's decision, not the
                # agent's, so the loop surfaces the prompt and exits.
                pending = {
                    "message": str(exc),
                    "confirm_token": exc.confirm_token,
                    **exc.preview,
                }
                turn.error = str(exc)
                history.append(turn)
                answer = (
                    f"{exc}\n\nImpact: {exc.preview.get('impact', 'unknown')}\n"
                    "Confirm to proceed."
                )
                ceiling = False
                break
            except PermissionDenied as exc:
                denials.append(str(exc))
                turn.error = str(exc)
            except PreconditionFailed as exc:
                # Authorized but inappropriate. Keep reasoning: the guidance names
                # the action that *is* correct, and the answer should carry it.
                blocked.append(str(exc))
                turn.error = f"{exc} {exc.guidance}".strip()
            except (TypeError, KeyError) as exc:
                turn.error = f"tool call failed: {exc}"
            history.append(turn)

        if pending is not None:
            break

    if answer is None:
        answer = (
            "I ran out of steps before reaching an answer. Filing a ticket is the "
            "safer outcome here."
        )

    latency_ms = int((time.perf_counter() - started) * 1000)

    return AgentResult(
        query=query,
        role=role,
        answer=answer,
        behavior=classify(
            answer=answer,
            tools_called=tools_called,
            denied=bool(denials) and pending is None,
            pending_confirmation=pending is not None,
            grounded=grounded,
        ),
        citations=extract_citations(answer),
        tools_called=tools_called,
        turns=history,
        denials=denials,
        blocked_actions=blocked,
        pending_confirmation=pending,
        grounded=grounded,
        usage=usage,
        latency_ms=latency_ms,
        hit_step_ceiling=ceiling,
    )
