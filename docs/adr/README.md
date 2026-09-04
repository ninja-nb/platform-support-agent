# Architecture decision records

One file per decision. Accepted records were extracted from the narrative in
`docs/ARCHITECTURE.md` and are marked as recorded retrospectively — the code came first.
Proposed records are decisions that have **not** been made yet; they exist so the
tradeoff is written down before it is settled rather than after.

Each record names the code it governs, the requirement in `PRD.md` it serves, the threat
in `THREAT_MODEL.md` it addresses, and the test that holds it, where those apply.

## Accepted

| # | Decision | Area |
|---|---|---|
| [0001](0001-mcp-is-a-transport-not-the-boundary.md) | Tools are plain functions behind one dispatcher; MCP is a transport | Tool surface |
| [0002](0002-role-is-established-server-side.md) | Role is established server-side, never asserted by the caller | Authorization |
| [0003](0003-unknown-tools-fail-closed.md) | Unknown tools fail closed | Authorization |
| [0004](0004-irreversible-actions-require-a-bound-confirmation.md) | Irreversible actions require a target-bound confirmation round-trip | Safety |
| [0005](0005-lexical-baseline-behind-a-retriever-protocol.md) | Start with a lexical BM25 baseline behind a `Retriever` protocol | Retrieval |
| [0006](0006-refusal-is-gated-on-coverage-not-score.md) | Refusal is gated on term coverage, not BM25 score | Retrieval |
| [0007](0007-superseding-documents-are-promoted-structurally.md) | Superseding documents are promoted structurally, not by score penalty | Retrieval |
| [0008](0008-chunk-on-heading-boundaries.md) | Chunk on heading boundaries and weight titles at index time | Retrieval |
| [0009](0009-behavior-classification-lives-in-the-policy-layer.md) | Behaviour classification lives in the policy layer with fixed precedence | Evals |
| [0010](0010-safety-is-a-gate-not-an-average.md) | Safety categories are a release gate, not a contributor to an average | Evals |
| [0011](0011-providers-behind-a-protocol.md) | The agent depends on a `Provider` protocol, never on a vendor SDK | Providers |
| [0012](0012-bounded-loop-with-a-ticket-fallback.md) | The loop is bounded, and exhaustion falls back to filing a ticket | Agent loop |

## Proposed

| # | Decision | Trigger |
|---|---|---|
| [0013](0013-port-the-loop-to-langgraph-for-session-memory.md) | Port the agent loop to LangGraph for session memory | Multi-turn cases exist |
| [0014](0014-adopt-vector-retrieval-only-on-eval-evidence.md) | Adopt vector retrieval only on eval evidence | A paraphrase miss is attributable to lexical matching |
| [0015](0015-per-request-identity-from-a-verified-token.md) | Replace `PSA_ROLE` with per-request verified identity | Any multi-user deployment (T1) |
| [0016](0016-separate-the-refusal-threshold-from-the-retrieval-threshold.md) | Separate the refusal threshold from the retrieval threshold | `unanswerable-015` (R2) |
| [0017](0017-treat-retrieved-passages-as-data.md) | Treat retrieved passages as data, not instructions | T6 open |
| [0018](0018-move-the-audit-log-to-an-external-sink.md) | Move the audit log to a sink the serving process cannot rewrite | T9 open |

0013 through 0018 are the answer to "what would you do next, and why haven't you?"
0015 through 0018 are the four that would block turning this on for real users.

## Template

```markdown
# ADR-NNNN: Title stated as a decision, not a topic

- **Status:** Proposed | Accepted | Superseded by ADR-NNNN
- **Date:** YYYY-MM-DD
- **Code:** path
- **Requirement / Threat / Test:** where applicable

## Context
The forces in play. What made this a decision rather than an obvious choice.

## Decision
What was decided, in the active voice.

## Consequences
What follows, including what got worse. An ADR with only upsides is marketing.

## Alternatives considered
What was rejected and on what grounds. Evidence beats reasoning where it exists.
```
