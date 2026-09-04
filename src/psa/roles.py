"""Role-based access control for the tool surface.

The permission table is the security boundary of this project, so it lives in one
small file with no dependencies. Every tool call passes through `authorize`.
"""

from __future__ import annotations

from dataclasses import dataclass

EMPLOYEE = "employee"
SRE = "sre"

# `intern` is a synonym for `employee`; kept because tickets and demos use both.
_ROLE_ALIASES = {"intern": EMPLOYEE, "l2": SRE}

ROLES = (EMPLOYEE, SRE)


class PermissionDenied(Exception):
    """Raised when a caller's role does not permit a tool call.

    Denial is a first-class outcome, not an error path: the agent is expected to
    explain the denial and offer `create_ticket` instead.
    """


class ConfirmationRequired(Exception):
    """Raised when a gated action needs explicit human confirmation."""

    def __init__(self, message: str, confirm_token: str, preview: dict):
        super().__init__(message)
        self.confirm_token = confirm_token
        self.preview = preview


@dataclass(frozen=True)
class ToolPolicy:
    allowed_roles: frozenset[str]
    # Caller may only see records they own, regardless of role.
    own_records_only_for: frozenset[str] = frozenset()
    # Requires a human confirmation round-trip before executing.
    requires_confirmation: bool = False


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "search_docs": ToolPolicy(allowed_roles=frozenset({EMPLOYEE, SRE})),
    "lookup_ticket": ToolPolicy(
        allowed_roles=frozenset({EMPLOYEE, SRE}),
        own_records_only_for=frozenset({EMPLOYEE}),
    ),
    "get_status": ToolPolicy(allowed_roles=frozenset({EMPLOYEE, SRE})),
    "get_deploys": ToolPolicy(allowed_roles=frozenset({EMPLOYEE, SRE})),
    "create_ticket": ToolPolicy(allowed_roles=frozenset({EMPLOYEE, SRE})),
    "restart_service": ToolPolicy(
        allowed_roles=frozenset({SRE}),
        requires_confirmation=True,
    ),
}


def normalize_role(role: str | None) -> str:
    r = (role or EMPLOYEE).strip().lower()
    r = _ROLE_ALIASES.get(r, r)
    if r not in ROLES:
        raise PermissionDenied(f"unknown role: {role!r}")
    return r


def policy_for(tool: str) -> ToolPolicy:
    try:
        return TOOL_POLICIES[tool]
    except KeyError:
        # Unknown tools are denied, not allowed. Fail closed.
        raise PermissionDenied(f"no policy defined for tool {tool!r}") from None


def authorize(tool: str, role: str) -> ToolPolicy:
    """Return the policy if `role` may call `tool`, else raise PermissionDenied."""
    pol = policy_for(tool)
    r = normalize_role(role)
    if r not in pol.allowed_roles:
        raise PermissionDenied(
            f"role {r!r} may not call {tool!r}; "
            f"allowed roles: {', '.join(sorted(pol.allowed_roles))}"
        )
    return pol


def restricted_to_own_records(tool: str, role: str) -> bool:
    return normalize_role(role) in policy_for(tool).own_records_only_for
