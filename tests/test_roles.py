"""The permission boundary. These tests are the ones that must never go red."""

from __future__ import annotations

import pytest

from psa.mcp_server import call_tool, reset_runtime_state
from psa.mcp_server.tools import _confirm_token
from psa.roles import ConfirmationRequired, PermissionDenied, authorize, normalize_role

DANA = "dana@meridiancloud.example"
ONCALL = "oncall@meridiancloud.example"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("PSA_AUDIT_DISABLE", "1")
    reset_runtime_state()


def test_intern_is_an_employee():
    assert normalize_role("intern") == "employee"


def test_unknown_role_is_rejected():
    with pytest.raises(PermissionDenied):
        normalize_role("root")


def test_unknown_tool_fails_closed():
    with pytest.raises(PermissionDenied):
        authorize("delete_everything", "sre")


def test_employee_cannot_restart():
    with pytest.raises(PermissionDenied):
        call_tool(
            "restart_service",
            {"service": "billing-worker", "environment": "prod-west"},
            role="employee",
            user=DANA,
        )


def test_sre_restart_requires_confirmation_first():
    with pytest.raises(ConfirmationRequired) as excinfo:
        call_tool(
            "restart_service",
            {"service": "billing-worker", "environment": "prod-west"},
            role="sre",
            user=ONCALL,
        )
    assert excinfo.value.confirm_token
    assert excinfo.value.preview["reversible"] is False


def test_sre_restart_succeeds_with_token():
    token = _confirm_token("billing-worker", "prod-west", ONCALL)
    result = call_tool(
        "restart_service",
        {"service": "billing-worker", "environment": "prod-west", "confirm_token": token},
        role="sre",
        user=ONCALL,
    )
    assert result["status"] == "ACCEPTED"


def test_confirmation_token_is_not_transferable():
    """A token minted for one target must not authorize a different one.

    Both targets are wedged services so the runbook precondition passes for each,
    isolating the token check as the thing under test.
    """
    token = _confirm_token("billing-worker", "prod-west", ONCALL)
    with pytest.raises(ConfirmationRequired):
        call_tool(
            "restart_service",
            {"service": "reports-worker", "environment": "staging-west", "confirm_token": token},
            role="sre",
            user=ONCALL,
        )


def test_employee_cannot_read_another_users_ticket():
    with pytest.raises(PermissionDenied):
        call_tool("lookup_ticket", {"ticket_id": "TIC-1002"}, role="employee", user=DANA)


def test_employee_can_read_own_ticket():
    ticket = call_tool("lookup_ticket", {"ticket_id": "TIC-1001"}, role="employee", user=DANA)
    assert ticket["requester"] == DANA


def test_sre_can_read_any_ticket():
    ticket = call_tool("lookup_ticket", {"ticket_id": "TIC-1002"}, role="sre", user=ONCALL)
    assert ticket["ticket_id"] == "TIC-1002"
