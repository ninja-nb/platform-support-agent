"""The tool surface, its schemas, and the single dispatcher every call goes through.

Tools are plain Python functions. `call_tool` is the only choke point: it
authorizes, enforces the confirmation gate, audits, and then executes. MCP
(`server.py`) is a transport in front of this module, which means the agent and
the eval suite exercise the same authorization code that a real MCP client would.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from psa.config import FIXTURES_DIR, settings
from psa.mcp_server import audit
from psa.rag.retrieve import search as search_index
from psa.roles import (
    ConfirmationRequired,
    PermissionDenied,
    authorize,
    restricted_to_own_records,
)

# ---------------------------------------------------------------- fixture loading


def _load(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


# Tickets created during a session live here so `create_ticket` is observable
# without a database. Reset between eval cases via `reset_runtime_state`.
_created_tickets: list[dict] = []
_restart_history: list[dict] = []


def reset_runtime_state() -> None:
    _created_tickets.clear()
    _restart_history.clear()


def _all_tickets() -> list[dict]:
    return _load("tickets.json") + _created_tickets


# ---------------------------------------------------------------- tools


def search_docs(query: str, top_k: int = 4, role: str = "employee", user: str = "") -> dict:
    """Retrieve help-center and runbook passages with citable doc_ids."""
    hits = search_index(query, top_k=top_k)
    return {
        "query": query,
        "hits": [
            {
                "doc_id": h.doc_id,
                "title": h.title,
                "heading": h.heading,
                "service": h.service,
                "snippet": h.snippet(),
                "score": h.score,
                "coverage": h.coverage,
                "updated": h.updated,
                "deprecated": h.deprecated,
                "superseded_by": h.superseded_by,
            }
            for h in hits
        ],
        # An empty hit list is a legitimate, expected outcome. The agent must
        # refuse and offer create_ticket rather than answer from prior knowledge.
        "grounded": bool(hits),
    }


def lookup_ticket(ticket_id: str, role: str = "employee", user: str = "") -> dict:
    """Fetch one ticket. Employees may only read tickets they filed."""
    for ticket in _all_tickets():
        if ticket["ticket_id"].lower() == ticket_id.strip().lower():
            if restricted_to_own_records("lookup_ticket", role) and ticket["requester"] != user:
                raise PermissionDenied(
                    f"{ticket_id} was filed by another user; "
                    f"role 'employee' may only read its own tickets"
                )
            return dict(ticket)
    return {"ticket_id": ticket_id, "found": False}


def get_status(environment: str, service: str | None = None, role: str = "employee",
               user: str = "") -> dict:
    """Read current environment and service state: worker counts, metrics, network."""
    envs = _load("environments.json")
    env = envs.get(environment)
    if env is None:
        return {"environment": environment, "found": False,
                "known_environments": sorted(envs.keys())}
    if service:
        svc = env["services"].get(service)
        if svc is None:
            return {
                "environment": environment,
                "service": service,
                "found": False,
                "known_services": sorted(env["services"].keys()),
            }
        return {"environment": environment, "region": env["region"], "service": service,
                "network": env["network"], **svc}
    return dict(env)


def get_deploys(environment: str | None = None, service: str | None = None,
                role: str = "employee", user: str = "") -> dict:
    """Recent deploy attempts, including rejection reasons."""
    deploys = _load("deploys.json")
    if environment:
        deploys = [d for d in deploys if d["environment"] == environment]
    if service:
        deploys = [d for d in deploys if d["service"] == service]
    return {"deploys": sorted(deploys, key=lambda d: d["started"], reverse=True)}


def create_ticket(subject: str, body: str, service: str = "unknown",
                  environment: str | None = None, role: str = "employee",
                  user: str = "") -> dict:
    """File a support ticket. The correct fallback whenever the agent cannot ground an answer."""
    ticket = {
        "ticket_id": f"TIC-{2000 + len(_created_tickets) + 1}",
        "requester": user or settings().user,
        "subject": subject,
        "body": body,
        "service": service,
        "environment": environment,
        "status": "open",
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _created_tickets.append(ticket)
    return ticket


def _confirm_token(service: str, environment: str, user: str) -> str:
    return hashlib.sha256(f"restart|{service}|{environment}|{user}".encode()).hexdigest()[:12]


def restart_service(service: str, environment: str, confirm_token: str | None = None,
                    role: str = "sre", user: str = "") -> dict:
    """Restart a service. Requires the `sre` role AND a human confirmation round-trip.

    First call returns a confirmation prompt rather than acting. The caller must
    re-issue the call with the returned token. The agent cannot mint the token
    itself from the prompt alone without a human relaying it, which is what makes
    this a gate rather than a speed bump.
    """
    expected = _confirm_token(service, environment, user)
    if confirm_token != expected:
        raise ConfirmationRequired(
            f"Restarting {service} in {environment} needs human confirmation.",
            confirm_token=expected,
            preview={
                "action": "restart_service",
                "service": service,
                "environment": environment,
                "impact": "Drops in-flight connections on all workers of this service.",
                "reversible": False,
            },
        )
    event = {
        "action": "restart_service",
        "service": service,
        "environment": environment,
        "status": "ACCEPTED",
        "confirmed_by": user,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _restart_history.append(event)
    return event


# ---------------------------------------------------------------- schemas + dispatch

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "search_docs",
        "description": (
            "Search the help center and runbooks. Returns passages with citable doc_ids."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language search query."},
                "top_k": {"type": "integer", "default": 4},
            },
            "required": ["query"],
        },
    },
    {
        "name": "lookup_ticket",
        "description": "Fetch a ticket by id. Employees can only read their own tickets.",
        "input_schema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
        },
    },
    {
        "name": "get_status",
        "description": "Current state of an environment or one service in it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "environment": {"type": "string"},
                "service": {"type": "string"},
            },
            "required": ["environment"],
        },
    },
    {
        "name": "get_deploys",
        "description": "Recent deploy attempts with rejection reasons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "environment": {"type": "string"},
                "service": {"type": "string"},
            },
        },
    },
    {
        "name": "create_ticket",
        "description": (
            "File a support ticket. Use when an answer cannot be grounded or must escalate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "service": {"type": "string"},
                "environment": {"type": "string"},
            },
            "required": ["subject", "body"],
        },
    },
    {
        "name": "restart_service",
        "description": (
            "Restart a service. Requires the sre role and explicit human confirmation. "
            "Call without confirm_token first to obtain the confirmation prompt."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "environment": {"type": "string"},
                "confirm_token": {"type": "string"},
            },
            "required": ["service", "environment"],
        },
    },
]

_IMPLEMENTATIONS: dict[str, Callable[..., dict]] = {
    "search_docs": search_docs,
    "lookup_ticket": lookup_ticket,
    "get_status": get_status,
    "get_deploys": get_deploys,
    "create_ticket": create_ticket,
    "restart_service": restart_service,
}

def call_tool(name: str, args: dict | None = None, *, role: str | None = None,
              user: str | None = None) -> dict:
    """Authorize, audit, and execute a tool call. The only supported entry point."""
    cfg = settings()
    role = role or cfg.role
    user = user or cfg.user
    args = dict(args or {})
    started = time.perf_counter()

    def elapsed() -> int:
        return int((time.perf_counter() - started) * 1000)

    try:
        authorize(name, role)
    except PermissionDenied as exc:
        audit.record(user=user, role=role, tool=name, outcome="denied",
                     args=args, detail=str(exc), latency_ms=elapsed())
        raise

    impl = _IMPLEMENTATIONS[name]
    try:
        result = impl(**args, role=role, user=user)
    except ConfirmationRequired as exc:
        audit.record(user=user, role=role, tool=name, outcome="confirmation_required",
                     args=args, detail=str(exc), latency_ms=elapsed())
        raise
    except PermissionDenied as exc:
        audit.record(user=user, role=role, tool=name, outcome="denied",
                     args=args, detail=str(exc), latency_ms=elapsed())
        raise
    except TypeError as exc:
        audit.record(user=user, role=role, tool=name, outcome="error",
                     args=args, detail=f"bad arguments: {exc}", latency_ms=elapsed())
        raise

    audit.record(user=user, role=role, tool=name, outcome="ok",
                 args=args, latency_ms=elapsed())
    return result
