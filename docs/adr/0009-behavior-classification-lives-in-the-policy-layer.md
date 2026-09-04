# ADR-0009: Behaviour classification lives in the policy layer with fixed precedence

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/agent/policy.py` (`classify`)
- **Tests:** `test_denial_outranks_answer`, `test_pending_confirmation_outranks_denial`

## Context

The eval harness scores a single `behavior` label per case against a list of acceptable
labels. That label is the primary signal in the eval table, so how it is derived is part
of the contract rather than an implementation detail of the runner.

A run can also satisfy several labels at once. A run that hit a permission denial and
then produced a prose answer is simultaneously a denial and an answer.

## Decision

`classify` lives in `agent/policy.py` alongside citation extraction, not in the eval
runner, and resolves multiple applicable labels by fixed precedence:

`propose_action` > `deny` > `refuse` > `ask` > `escalate` > `create_ticket` > `answer`

## Consequences

- The agent, the UI, and the eval harness all report the same label for the same run.
- Denial outranks answering because a run that denied something and then answered anyway
  *is* a denial. Reporting it as an answer would hide exactly the case that matters most.
- `propose_action` sits at the top because a pending confirmation means the run stopped
  at the gate, which is the outcome to report regardless of what prose accompanied it.
- Refusal is inferred partly from marker phrases in the answer text
  (`_REFUSAL_MARKERS`, `_ASK_MARKERS`, `_ESCALATION_MARKERS`). This is brittle: a real
  provider phrasing a refusal in unlisted words will be classified as `answer`. The
  marker lists are the most likely source of false eval failures when the OpenAI and
  Vertex providers land.

## Alternatives considered

**Classify inside the eval runner.** Rejected: the label the eval reports would then
differ from what the UI shows, and the contract would live in test code.

**Ask the model to self-report its behaviour.** Rejected: the eval would be scoring the
model's claim about itself rather than what it did. `deny` in particular must be derived
from whether a `PermissionDenied` was actually raised.

**Return a set of labels instead of one.** Rejected for now: a single label keeps the
eval table readable, and precedence encodes the judgement about which outcome dominates.
