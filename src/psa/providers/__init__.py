"""Provider registry. `PROVIDER=stub|openai|vertex` selects the implementation."""

from __future__ import annotations

from psa.config import settings
from psa.providers.base import Provider, Step, ToolRequest, Turn, Usage
from psa.providers.stub import StubProvider

__all__ = ["Provider", "Step", "ToolRequest", "Turn", "Usage", "get_provider"]


def get_provider(name: str | None = None) -> Provider:
    key = (name or settings().provider).strip().lower()
    if key == "stub":
        return StubProvider()
    if key == "openai":
        from psa.providers.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if key == "vertex":
        from psa.providers.vertex_provider import VertexProvider

        return VertexProvider()
    raise ValueError(f"unknown PROVIDER={key!r}; expected one of: stub, openai, vertex")
