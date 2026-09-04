"""Minimal span helper with an OpenTelemetry-shaped API.

Deliberately a no-op-plus-timing shim: it keeps call sites in the agent loop
correct now, so switching to a real tracer later is an import change rather than
a refactor of every function.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class Span:
    name: str
    attributes: dict = field(default_factory=dict)
    duration_ms: int = 0

    def set_attribute(self, key: str, value) -> None:
        self.attributes[key] = value


_collected: list[Span] = []


@contextmanager
def span(name: str, **attributes) -> Iterator[Span]:
    s = Span(name=name, attributes=dict(attributes))
    started = time.perf_counter()
    try:
        yield s
    finally:
        s.duration_ms = int((time.perf_counter() - started) * 1000)
        _collected.append(s)


def collected() -> list[Span]:
    return list(_collected)


def clear() -> None:
    _collected.clear()
