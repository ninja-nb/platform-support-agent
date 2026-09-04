# ADR-0002: Role is established server-side, never asserted by the caller

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/roles.py`, `src/psa/mcp_server/tools.py`
- **Threat:** T1

## Context

Every tool call is authorized against a role. The role has to come from somewhere, and
the convenient option is to accept it as a tool argument, since the agent already passes
arguments through.

## Decision

Role is read from the server environment (`PSA_ROLE`) and injected by `call_tool`. It is
not a property in any entry of `TOOL_SCHEMAS`, so a client cannot supply it and the
model cannot request it.

## Consequences

- A compromised or injected model cannot escalate its own privileges; the worst it can
  do is request a tool it is not permitted to call, which is denied and audited.
- One server process serves exactly one role. This is the largest gap between this repo
  and something deployable, recorded as T1 and addressed by ADR-0015.
- Role-varying tests and the Streamlit role picker work by varying the environment per
  call, which is why `settings()` re-reads the environment rather than caching.

## Alternatives considered

**Accept `role` as a tool argument.** Rejected: reduces the permission table to
documentation. Any caller could claim `sre`.

**Derive role from the query text.** Rejected outright — it makes authorization a
function of attacker-controlled input.
