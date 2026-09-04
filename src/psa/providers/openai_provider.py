"""OpenAI provider.

The client is injectable so the message and tool-schema construction can be
tested without a network call or an API key — that translation layer is where
provider bugs actually live, not in the HTTP request.
"""

from __future__ import annotations

import json
import os
from typing import Any

from psa.agent.prompts import ROLE_NOTE, SYSTEM_PROMPT
from psa.mcp_server import TOOL_SCHEMAS
from psa.providers.base import Provider, Step, ToolRequest, Turn, Usage

# USD per 1M tokens, (input, output). A stale entry here silently corrupts the
# cost column in docs/EVALS.md, so it is data rather than a formula.
PRICE_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, model: str | None = None, client: Any | None = None):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._client = client
        if client is None and not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set; use PROVIDER=stub for offline runs")

    @property
    def client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI()
        return self._client

    # ------------------------------------------------------------------ mapping

    def tools(self) -> list[dict]:
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

    def messages(self, query: str, role: str, history: list[Turn]) -> list[dict]:
        """Build the message list, replaying tool calls in OpenAI's tool protocol.

        Each turn is replayed as one assistant message carrying a single tool_call
        followed by its matching tool message. If a provider originally batched
        several calls into one message they are replayed sequentially instead,
        which is protocol-valid but not a byte-exact transcript.
        """
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n" + ROLE_NOTE.get(role, "")},
            {"role": "user", "content": query},
        ]
        for i, turn in enumerate(history):
            call_id = turn.call_id or f"call_{i}"
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": turn.tool,
                                "arguments": json.dumps(turn.args),
                            },
                        }
                    ],
                }
            )
            # Denials and precondition failures are delivered as tool *content*,
            # not as an exception, so the model can read them and change course.
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(
                        {"error": turn.error} if turn.error else (turn.result or {}),
                        default=str,
                    ),
                }
            )
        return messages

    def usage_from(self, raw: Any) -> Usage:
        if raw is None:
            return Usage()
        input_tokens = getattr(raw, "prompt_tokens", 0) or 0
        output_tokens = getattr(raw, "completion_tokens", 0) or 0
        in_price, out_price = PRICE_PER_1M.get(self.model, (0.0, 0.0))
        cost = (input_tokens * in_price + output_tokens * out_price) / 1_000_000
        return Usage(input_tokens, output_tokens, round(cost, 8))

    @staticmethod
    def _parse_args(raw: str | None) -> dict:
        """Tolerate malformed tool arguments.

        A model occasionally emits invalid JSON. Returning empty args lets the
        tool layer reject the call with a normal error the model can read, which
        is preferable to crashing the whole run.
        """
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    # ------------------------------------------------------------------ protocol

    def next_step(self, query: str, role: str, history: list[Turn]) -> Step:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages(query, role, history),
            tools=self.tools(),
            tool_choice="auto",
            temperature=0,
        )
        message = response.choices[0].message
        usage = self.usage_from(getattr(response, "usage", None))

        requested = getattr(message, "tool_calls", None) or []
        if requested:
            # Tool calls win over any prose in the same message: the run is not
            # finished while the model is still asking for data.
            return Step(
                tool_calls=[
                    ToolRequest(
                        name=call.function.name,
                        args=self._parse_args(call.function.arguments),
                        call_id=call.id,
                    )
                    for call in requested
                ],
                usage=usage,
            )

        return Step(answer=message.content or "", usage=usage)
