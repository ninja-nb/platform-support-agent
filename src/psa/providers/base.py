"""Provider interface.

The agent depends on `Provider`, never on a vendor SDK. Swapping Gemini for
GPT is a config change, and the golden set is what proves the swap is safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            round(self.cost_usd + other.cost_usd, 6),
        )


@dataclass
class ToolRequest:
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class Step:
    """One model turn: either request tools, or produce the final answer."""

    tool_calls: list[ToolRequest] = field(default_factory=list)
    answer: str | None = None
    usage: Usage = field(default_factory=Usage)

    @property
    def is_final(self) -> bool:
        return not self.tool_calls


@dataclass
class Turn:
    """A tool call and its outcome, fed back to the provider on the next step."""

    tool: str
    args: dict
    result: dict | None = None
    error: str | None = None


@runtime_checkable
class Provider(Protocol):
    name: str

    def next_step(self, query: str, role: str, history: list[Turn]) -> Step:
        """Decide the next action given the query and everything observed so far."""
        ...
