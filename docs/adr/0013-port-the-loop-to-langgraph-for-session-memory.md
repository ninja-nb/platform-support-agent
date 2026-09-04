# ADR-0013: Port the agent loop to LangGraph for session memory and resumable confirmation

- **Status:** Proposed
- **Date:** 2026-09-04
- **Code:** `src/psa/agent/orchestrator.py`

## Context

The loop is currently single-turn. Two consequences follow, and only one of them is
cosmetic.

The cosmetic one: "restart it" does not resolve against the previous turn's service,
so the demo cannot hold a conversation.

The load-bearing one: the confirmation gate in ADR-0004 produces a `pending_confirmation`
and exits. Resuming it means the caller re-issues `restart_service` with the token, which
works, but nothing in the agent remembers *why* the restart was proposed. The human
confirms an action whose justification lives only in the previous HTTP response.

## Decision (proposed)

Port `run()` to a LangGraph graph with checkpointed state, keeping the `run() ->
AgentResult` signature and the `AgentResult` shape unchanged. Session state holds
conversation history and any pending confirmation with the reasoning that produced it.

## Consequences

- The UI and the eval harness depend on `AgentResult`, so the port must not change it.
  This is the constraint that makes the port safe to attempt, and the reason the shape
  was fixed before the port.
- The golden set is single-turn and will not detect a regression in multi-turn state.
  Multi-turn cases have to be added *before* the port, not after, or the port is
  unverified.
- Adds a substantial dependency to a project whose current appeal is that it runs on the
  standard library. The eval suite must still run offline.
- Checkpointed state containing a pending gated action is a new asset in the threat
  model: whoever can read or write it can change what a human is about to confirm.

## Open questions

- Does the confirmation token need to move into checkpointed state, or stay derived? If
  it moves, ADR-0004's residual (no TTL, not single-use) becomes fixable at the same
  time.
- Is `MAX_STEPS` still the right bound once a turn can continue an earlier one, or does
  the ceiling need to be per-session rather than per-request?

## Alternatives considered

**Keep the plain loop and add a session dict.** Cheaper and has no new dependency.
Genuinely viable — the argument against is that the ADK/LangGraph line is part of what
the project is meant to demonstrate, which is a résumé reason rather than an engineering
one and should be named as such.

**Port to ADK instead.** Overlaps with the Vertex track. Worth deciding alongside
ADR-0014 rather than separately, since both touch the Google skin.
