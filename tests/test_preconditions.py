"""The restart precondition.

`err-005` says a restart applies only to a wedged service, and that restarting a
saturated one makes things worse. That rule is enforced in the tool layer so it
does not depend on the model reasoning correctly.
"""

from __future__ import annotations

import pytest

from psa.mcp_server import call_tool, reset_runtime_state
from psa.mcp_server.tools import _confirm_token
from psa.roles import ConfirmationRequired, PermissionDenied, PreconditionFailed

ONCALL = "oncall@meridiancloud.example"
DANA = "dana@meridiancloud.example"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("PSA_AUDIT_DISABLE", "1")
    reset_runtime_state()


def _restart(service: str, environment: str, role: str = "sre", user: str = ONCALL, **extra):
    return call_tool(
        "restart_service",
        {"service": service, "environment": environment, **extra},
        role=role,
        user=user,
    )


def test_saturated_service_cannot_be_restarted():
    """checkout-api in prod-east has 2 of 6 ready: still serving, so not wedged."""
    with pytest.raises(PreconditionFailed) as excinfo:
        _restart("checkout-api", "prod-east")
    assert "scale out" in excinfo.value.guidance.lower()


def test_wedged_service_reaches_the_confirmation_gate():
    """billing-worker in prod-west has 0 ready, so a restart is legitimate."""
    with pytest.raises(ConfirmationRequired):
        _restart("billing-worker", "prod-west")


def test_unknown_environment_fails_closed():
    with pytest.raises(PreconditionFailed, match="Cannot verify"):
        _restart("billing-worker", "prod-nowhere")


def test_unknown_service_fails_closed():
    with pytest.raises(PreconditionFailed, match="not found"):
        _restart("ghost-api", "prod-west")


def test_permission_is_checked_before_state():
    """An employee is refused for lacking the role, not for the service being healthy."""
    with pytest.raises(PermissionDenied):
        _restart("checkout-api", "prod-east", role="employee", user=DANA)


def test_precondition_is_checked_before_asking_a_human():
    """Never ask for confirmation of an action that would be refused anyway."""
    with pytest.raises(PreconditionFailed):
        _restart(
            "checkout-api",
            "prod-east",
            confirm_token=_confirm_token("checkout-api", "prod-east", ONCALL),
        )


def test_confirmed_restart_of_a_wedged_service_succeeds():
    token = _confirm_token("billing-worker", "prod-west", ONCALL)
    result = _restart("billing-worker", "prod-west", confirm_token=token)
    assert result["status"] == "ACCEPTED"
    assert result["confirmed_by"] == ONCALL
