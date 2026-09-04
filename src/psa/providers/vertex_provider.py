"""Vertex AI / Gemini provider.

Week 3. Google Cloud runs the largest FDE program of the three targets and its
loop probes Vertex specifically, so this is the skin worth finishing first if
time runs short.

Note the schema difference from OpenAI: Gemini function declarations do not accept
the full JSON Schema vocabulary (no `default`, limited `format`), so
`_function_declarations` prunes rather than passing TOOL_SCHEMAS through directly.
"""

from __future__ import annotations

import os

from psa.agent.prompts import ROLE_NOTE, SYSTEM_PROMPT
from psa.mcp_server import TOOL_SCHEMAS
from psa.providers.base import Provider, Step, Turn

PRICE_PER_1M = {"gemini-2.0-flash": (0.10, 0.40)}

_ALLOWED_SCHEMA_KEYS = {"type", "properties", "required", "description", "items", "enum"}


class VertexProvider(Provider):
    name = "vertex"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("VERTEX_MODEL", "gemini-2.0-flash")
        self.project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        if not self.project:
            raise RuntimeError(
                "GOOGLE_CLOUD_PROJECT is not set; use PROVIDER=stub for offline runs"
            )

    @staticmethod
    def _prune(schema: dict) -> dict:
        pruned = {k: v for k, v in schema.items() if k in _ALLOWED_SCHEMA_KEYS}
        if "properties" in pruned:
            pruned["properties"] = {
                name: {k: v for k, v in spec.items() if k in _ALLOWED_SCHEMA_KEYS}
                for name, spec in pruned["properties"].items()
            }
        return pruned

    def _function_declarations(self) -> list[dict]:
        return [
            {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": self._prune(schema["input_schema"]),
            }
            for schema in TOOL_SCHEMAS
        ]

    def system_instruction(self, role: str) -> str:
        return SYSTEM_PROMPT + "\n" + ROLE_NOTE.get(role, "")

    def next_step(self, query: str, role: str, history: list[Turn]) -> Step:
        raise NotImplementedError(
            "Week 3: initialise vertexai with project/location, build a GenerativeModel "
            "with system_instruction=self.system_instruction(role) and "
            "tools=[Tool(function_declarations=self._function_declarations())], then map "
            "candidate function_calls into Step.tool_calls. Run `make eval` against the "
            "same golden.jsonl and record both providers in docs/EVALS.md."
        )
