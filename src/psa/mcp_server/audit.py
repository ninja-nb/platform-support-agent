"""Append-only audit log for tool calls.

Every call through `call_tool` is recorded, including denials and confirmation
prompts. Denials are the interesting records: they are the evidence that the
permission boundary held.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from psa.config import AUDIT_LOG_PATH

# Argument names whose values must never reach the log.
_REDACT_KEYS = frozenset({"password", "token", "api_key", "secret", "authorization"})


@dataclass
class AuditRecord:
    ts: str
    user: str
    role: str
    tool: str
    outcome: str  # ok | denied | confirmation_required | error
    args: dict[str, Any] = field(default_factory=dict)
    detail: str = ""
    latency_ms: int = 0


def redact(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in args.items():
        if k.lower() in _REDACT_KEYS:
            out[k] = "***redacted***"
        elif isinstance(v, str) and len(v) > 500:
            out[k] = v[:500] + "\u2026"
        else:
            out[k] = v
    return out


_memory_log: list[AuditRecord] = []


def record(
    *,
    user: str,
    role: str,
    tool: str,
    outcome: str,
    args: dict[str, Any] | None = None,
    detail: str = "",
    latency_ms: int = 0,
    path: Path = AUDIT_LOG_PATH,
) -> AuditRecord:
    rec = AuditRecord(
        ts=datetime.now(UTC).isoformat(timespec="milliseconds"),
        user=user,
        role=role,
        tool=tool,
        outcome=outcome,
        args=redact(args or {}),
        detail=detail,
        latency_ms=latency_ms,
    )
    _memory_log.append(rec)
    if os.environ.get("PSA_AUDIT_DISABLE") != "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(rec)) + "\n")
    return rec


def entries() -> list[AuditRecord]:
    """In-process audit records, used by tests and the UI audit panel."""
    return list(_memory_log)


def clear() -> None:
    _memory_log.clear()
