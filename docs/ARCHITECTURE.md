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

### Tools are functions; MCP is a transport

Authorization, the confirmation gate, and the audit log live in `call_tool`, not in the
MCP server. `mcp_server/server.py` is a thin adapter.

The alternative — enforcing permissions in the MCP handler — would mean the eval suite
exercised a different code path than a real MCP client, so the tests would not be
evidence about the deployed behaviour. It also would have left a second, unguarded path
to the tool implementations for any in-process caller.

Denials and confirmation prompts are returned to the model as tool *results*, not
transport errors. The agent has to read them and change course, which it cannot do if
the transport swallows them.

### Roles come from the server environment

`PSA_ROLE` is read server-side and never accepted from the client. Letting a client
declare its own role would reduce the permission table to documentation.

In a real deployment this is where the customer's IdP goes, and the role would be
derived from a verified token rather than an environment variable. The shape of the
check does not change; only the source of the identity does.

### Unknown tools fail closed

`policy_for` raises on any tool without an explicit entry in `TOOL_POLICIES`. Adding a
tool without deciding its permissions is therefore a hard error at call time rather
than an accidental grant. This is the one place where being annoying is correct.

### Confirmation tokens are bound to their target

The token is `sha256("restart|service|environment|user")`, truncated. A token minted for
`billing-worker` in `prod-west` will not authorize `checkout-api` in `prod-east`, which
closes the obvious replay: the agent obtains one legitimate confirmation and then reuses
it for a different, unapproved action. `test_confirmation_token_is_not_transferable`
covers this.

The gate is a round-trip, not a flag on the call. The first call *cannot* execute; it
can only return the prompt.

### Coverage, not BM25 score, decides refusal

BM25 scores are unbounded and corpus-dependent, so no fixed threshold on them means
anything. Refusal is instead gated on *coverage*: the fraction of distinct content terms
in the query that appear in the chunk. Coverage is bounded 0..1 and is comparable across
queries, which makes it usable as an absolute "do we actually know this?" test.

`PSA_MIN_SCORE` (default 0.15) is the threshold, and it is a tuning knob to be moved
only with eval evidence. The current value is known to be too permissive — see the
`unanswerable-015` failure in `docs/EVALS.md`, where a query about Snowflake
certificate rotation still retrieves the VPN certificate document.

### Superseding documents are promoted structurally

Deprecated documents stay in the index because users quote them. They take a relevance
penalty (`DEPRECATED_PENALTY = 0.35`), but the penalty is not what provides the
guarantee — `_promote_replacements` does, by injecting a document's replacement above it
whenever the deprecated document appears in the results.

This was driven by an actual test failure: for "VPN pre-shared key rotate shared key",
the retired document beat its replacement even with the penalty applied, because the
retired document is genuinely the better lexical match for a user reading from it. Score
tuning would have papered over that for one query while leaving the invariant unproven.

### Heading-aware chunking

Documents split on `##` boundaries, which keeps "Resolution" and "Escalate when" as
separate retrievable units. The escalation eval cases depend on this: an escalation
condition buried in a whole-document chunk competes with the resolution steps instead of
being retrievable on its own.

Titles and headings are weighted by repetition at index time, so a query naming a
symptom reaches the right document even when the body phrases it differently.

### Behaviour classification lives in the policy layer

The eval harness scores a `behavior` label, so how that label is derived is part of the
contract and lives in `agent/policy.py` rather than being inferred inside the runner.

Precedence is deliberate: `propose_action` > `deny` > `refuse` > `ask` > `escalate` >
`create_ticket` > `answer`. Denial outranks answering because a run that denied
something and then answered anyway is a denial, and reporting it as an answer would hide
exactly the case that matters most.

## Known gaps

- Providers are interfaces only; `next_step` raises `NotImplementedError`.
- Single-turn. No session memory, so "restart it" does not resolve against the previous
  turn's service. That is the main reason to port to LangGraph.
- `PSA_MIN_SCORE` is too permissive; see above.
- The audit log is a local file. Real deployment needs an append-only sink the
  application cannot rewrite.
- No rate limiting or prompt-injection defence on retrieved content. A corpus document
  is currently trusted text; see `THREAT_MODEL.md`.
