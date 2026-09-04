# ADR-0004: Irreversible actions require a target-bound confirmation round-trip

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/mcp_server/tools.py` (`restart_service`, `_confirm_token`)
- **Threats:** T2, T3
- **Tests:** `test_sre_restart_requires_confirmation_first`, `test_confirmation_token_is_not_transferable`
- **Requirement:** R11, R12

## Context

`restart_service` drops in-flight connections and is not reversible. Role gating alone is
insufficient: an `sre` session driven by an agent that has misdiagnosed a saturated
service as a wedged one will restart the wrong thing, and the model is confident either
way.

Two distinct attacks have to be closed. Executing with no confirmation at all, and
obtaining one legitimate confirmation then reusing it against a different target.

## Decision

The first call to `restart_service` cannot execute. It raises `ConfirmationRequired`
carrying a preview (action, service, environment, impact, reversibility) and a token
derived as `sha256("restart|service|environment|user")`, truncated. Execution requires a
second call presenting the matching token.

The agent loop stops immediately on `ConfirmationRequired` and surfaces the prompt
rather than continuing to reason about an action it has not been allowed to take.

## Consequences

- The gate holds even when the model is fully compromised by prompt injection. That
  containment is the actual argument for gating actions rather than filtering prompts.
- Binding the token to service, environment, and user closes the replay: a token minted
  for `billing-worker` in `prod-west` will not authorize `checkout-api` in `prod-east`.
- The agent cannot mint the token from the prompt alone without a human relaying it,
  which is what makes this a gate rather than a speed bump.
- **Residual:** the token is derived deterministically rather than issued and stored, so
  it does not expire and is not single-use. Recorded as T3; a real implementation needs a
  nonce with a TTL marked consumed on execution.

## Alternatives considered

**A boolean `confirmed=true` argument.** Rejected: the model can set it itself, so it
records an intention rather than a human decision.

**Confirm in the UI only.** Rejected: puts the gate in one client. Any other client, or
the eval harness, would bypass it.

**A single global confirmation token.** Rejected: transferable across targets, which is
precisely the replay `test_confirmation_token_is_not_transferable` covers.
