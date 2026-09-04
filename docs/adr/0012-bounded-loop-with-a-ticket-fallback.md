# ADR-0012: The agent loop is bounded, and exhaustion falls back to filing a ticket

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/agent/orchestrator.py` (`MAX_STEPS`)
- **Threat:** T11

## Context

The loop alternates between asking the provider for a step and executing the tools it
requests. Nothing in that structure terminates on its own: a model that keeps requesting
`get_status` will keep being served, at cost, until something stops it.

There is also the question of what to return when the loop does stop without an answer.

## Decision

`MAX_STEPS = 6` bounds tool calls per request. When the ceiling is reached without a
final answer, the agent returns a message stating it ran out of steps and that filing a
ticket is the safer outcome, and sets `hit_step_ceiling` on the result.

## Consequences

- Bounded worst-case cost and latency per request, which is what makes the eval table's
  cost column meaningful as an input to a spend cap.
- The degraded outcome is an escalation to a human rather than a guess. Running out of
  budget must not become a reason to answer from model knowledge.
- `hit_step_ceiling` is on `AgentResult`, so ceiling hits are visible in the eval output
  instead of looking like ordinary refusals.
- Six steps is a guess, not a measurement. `cross-doc-017` needs `search_docs` twice
  plus `get_status`, so the real ceiling for multi-problem tickets is not far below it.
- **Residual:** there is no per-user rate limit and no spend cap. The step ceiling
  bounds one request, not a caller issuing thousands. Recorded as T11.

## Alternatives considered

**No ceiling, rely on the model stopping.** Rejected: makes cost a function of model
behaviour, and T11 becomes unbounded.

**Return an error on exhaustion.** Rejected: an error tells the user nothing actionable,
where an offer to file a ticket routes the problem to someone who can solve it.
