"""OpenAI provider.

Week 2/3. The tool schemas in `psa.mcp_server.TOOL_SCHEMAS` are already in the
shape the chat-completions tool API expects; the remaining work is the SDK call
and mapping the response back onto `Step`.
"""

from __future__ import annotations

import os

from psa.agent.prompts import ROLE_NOTE, SYSTEM_PROMPT, render_tool_result
from psa.mcp_server import TOOL_SCHEMAS
from psa.providers.base import Provider, Step, Turn

# Per-1M-token prices, used to report $/request in the eval table. Update when
# pricing changes; a stale number here silently corrupts the cost metric.
PRICE_PER_1M = {"gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.50, 10.00)}


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set; use PROVIDER=stub for offline runs")

    def _messages(self, query: str, role: str, history: list[Turn]) -> list[dict]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n" + ROLE_NOTE.get(role, "")},
            {"role": "user", "content": query},
        ]
        for turn in history:
            messages.append(
                {"role": "assistant", "content": f"Calling {turn.tool} with {turn.args}"}
            )
            messages.append(
                {"role": "user", "content": render_tool_result(turn.tool, turn.result, turn.error)}
            )
        return messages

    def _tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema["input_schema"],
                },
            }
            for schema in TOOL_SCHEMAS
        ]

    def next_step(self, query: str, role: str, history: list[Turn]) -> Step:
        raise NotImplementedError(
            "Week 2: call client.chat.completions.create(model=self.model, "
            "messages=self._messages(...), tools=self._tools()) and map "
            "response.choices[0].message into Step(tool_calls=..., answer=...). "
            "Populate Step.usage from response.usage using PRICE_PER_1M so the "
            "eval table's cost column stays honest."
        )
