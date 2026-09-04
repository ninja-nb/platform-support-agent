# Architecture

## Request path

```
query + role + user
    |
agent.run()                          src/psa/agent/orchestrator.py
    |
    +-- provider.next_step(query, role, history)
    |       returns Step(tool_calls=[...]) or Step(answer="...")
    |
    +-- for each tool call: call_tool(name, args, role, user)
    |       src/psa/mcp_server/tools.py
    |         1. authorize(tool, role)          -> PermissionDenied
    |         2. execute implementation         -> ConfirmationRequired
    |         3. audit.record(outcome)
    |
    +-- loop, max 6 steps
    |
    v
AgentResult(answer, citations, behavior, tools_called, turns, denials,
            pending_confirmation, usage, latency_ms)
```

The loop stops immediately on `ConfirmationRequired`. A gated action is the human's
decision, so the agent surfaces the prompt and exits rather than continuing to reason
about an action it has not been allowed to take.

## Seams

Four interfaces exist so that the expensive parts can be replaced without touching
anything downstream:

| Interface | Today | Replaced by | Why it is a seam |
|---|---|---|---|
| `Retriever` (`rag/retrieve.py`) | BM25, stdlib | embeddings, Vertex Vector Search | The golden set can then measure whether the upgrade helped, rather than assuming it. |
| `Provider` (`providers/base.py`) | rule-based stub | OpenAI, Vertex/Gemini | Provider choice is a config change; the same golden set proves the swap. |
| `call_tool` (`mcp_server/tools.py`) | direct call | MCP stdio, HTTP | Transport changes must not move the authorization code. |
| `AgentResult` | plain loop | LangGraph | The UI and eval harness depend on this shape, so the port must preserve it. |

## Decisions

Each decision has its own record in [`docs/adr/`](adr/README.md), with the context, the
consequences including what got worse, and the alternatives rejected. This section is an
index; the records are the content.

| Area | Decision | ADR |
|---|---|---|
| Tool surface | Tools are plain functions behind one dispatcher; MCP is a transport | [0001](adr/0001-mcp-is-a-transport-not-the-boundary.md) |
| Authorization | Role is established server-side, never asserted by the caller | [0002](adr/0002-role-is-established-server-side.md) |
| Authorization | Unknown tools fail closed | [0003](adr/0003-unknown-tools-fail-closed.md) |
| Safety | Irreversible actions require a target-bound confirmation round-trip | [0004](adr/0004-irreversible-actions-require-a-bound-confirmation.md) |
| Retrieval | Lexical BM25 baseline behind a `Retriever` protocol | [0005](adr/0005-lexical-baseline-behind-a-retriever-protocol.md) |
| Retrieval | Refusal is gated on term coverage, not BM25 score | [0006](adr/0006-refusal-is-gated-on-coverage-not-score.md) |
| Retrieval | Superseding documents are promoted structurally, not by score penalty | [0007](adr/0007-superseding-documents-are-promoted-structurally.md) |
| Retrieval | Chunk on heading boundaries; weight titles at index time | [0008](adr/0008-chunk-on-heading-boundaries.md) |
| Evals | Behaviour classification lives in the policy layer, with fixed precedence | [0009](adr/0009-behavior-classification-lives-in-the-policy-layer.md) |
| Evals | Safety categories are a release gate, not a contributor to an average | [0010](adr/0010-safety-is-a-gate-not-an-average.md) |
| Providers | The agent depends on a `Provider` protocol, never on a vendor SDK | [0011](adr/0011-providers-behind-a-protocol.md) |
| Agent loop | The loop is bounded; exhaustion falls back to filing a ticket | [0012](adr/0012-bounded-loop-with-a-ticket-fallback.md) |

Decisions that have **not** been made yet are recorded as proposals in ADR-0013 through
ADR-0018, so the tradeoff is written down before it is settled.

## Known gaps

Each gap below has a proposed ADR stating what would be done about it and what evidence
should trigger it.

| Gap | Consequence | ADR |
|---|---|---|
| Providers are interfaces only; `next_step` raises `NotImplementedError` | Every number in `EVALS.md` comes from the rule-based stub, so provider portability (R15) is unproven | [0011](adr/0011-providers-behind-a-protocol.md) |
| Single-turn; no session memory, so "restart it" does not resolve against the previous turn's service | A confirmation is approved without the agent retaining why it was proposed | [0013](adr/0013-port-the-loop-to-langgraph-for-session-memory.md) |
| `PSA_MIN_SCORE` is too permissive | `unanswerable-015` answers an off-corpus question with a citation, which is the failure R2 exists to prevent | [0016](adr/0016-separate-the-refusal-threshold-from-the-retrieval-threshold.md) |
| Retrieved corpus content is trusted text; no prompt-injection defence | Threat T6, open | [0017](adr/0017-treat-retrieved-passages-as-data.md) |
| The audit log is a local file the serving process can rewrite | Threat T9, open. Denial records are a claim rather than evidence | [0018](adr/0018-move-the-audit-log-to-an-external-sink.md) |
| One process serves one role and one user | Threat T1. Not deployable for more than one caller | [0015](adr/0015-per-request-identity-from-a-verified-token.md) |
| No rate limiting and no spend cap | Threat T11; the step ceiling bounds one request, not a caller issuing thousands | [0012](adr/0012-bounded-loop-with-a-ticket-fallback.md) |
