# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An internal platform-support agent for a fictional SaaS company ("Meridian Cloud"). A
user pastes a ticket (VPN, deploy failure, 5xx, quota), the agent retrieves cited
help-center/runbook passages, calls role-gated tools over MCP, and answers, refuses,
escalates, or *proposes* an action (never executes a restart without the `sre` role and
a human confirmation round-trip).

Core (retrieval, RBAC, tools, eval harness) is **stdlib-only** on purpose: `make eval`
must run on a clean checkout with no API key and no network. Model SDKs are optional
extras (`openai`, `vertex`, `agent` for LangGraph, `mcp`, `ui`).

Everything in `data/` is synthetic — no real company/customer data, ever.

## Commands

```bash
make setup    # uv venv + install -e '.[dev]'
make index    # build the BM25 index from data/corpus -> .index/index.json
make eval     # run golden.jsonl with PROVIDER=stub, write docs/EVALS.md
make test     # pytest -q
make lint     # ruff check src tests ui
make ui       # streamlit run ui/app.py, on :8501
make up/down  # docker compose
```

Single test / single case:

```bash
pytest tests/test_roles.py::test_employee_cannot_restart -q
psa-eval --file holdout.jsonl                    # held-out set; never tune against this
psa-eval --provider openai --file golden.jsonl   # run a real provider against the golden set
psa-eval --require-safety --fail-under 0.8       # CI-style gates, no report written
```

`PROVIDER` env var (or `--provider`) selects `stub` | `openai` | `vertex`. `PSA_ROLE`
(`employee`|`sre`) and `PSA_USER` set caller identity for local runs — see
`.env.example`. Copy it to `.env` before running against `openai`/`vertex`.

`make eval` and CI set `PSA_AUDIT_DISABLE=1` implicitly via the runner so eval runs
don't spam `audit.log`.

## Architecture

Request path (`docs/ARCHITECTURE.md` has the full diagram and the ADR index):

```
agent.run(query, role, user)              src/psa/agent/orchestrator.py
  -> provider.next_step(query, role, history) -> Step(tool_calls=[...]) or Step(answer=...)
  -> for each tool call: call_tool(name, args, role, user)   src/psa/mcp_server/tools.py
       1. authorize(tool, role)        -> may raise PermissionDenied
       2. run the implementation       -> may raise ConfirmationRequired / PreconditionFailed
       3. audit.record(outcome)
  -> loop, MAX_STEPS = 6
  -> AgentResult(answer, citations, behavior, tools_called, turns, denials, pending_confirmation, usage, latency_ms)
```

The loop stops immediately on `ConfirmationRequired` — a gated action is the human's
decision, so the agent surfaces the confirm prompt and exits rather than reasoning
further about an action it isn't allowed to take yet.

**`call_tool` is the single choke point for every tool call** — the agent, the eval
harness, and any MCP client (`mcp_server/server.py` is just a stdio transport in front
of it) all go through the same authorize → execute → audit path. Never call a tool
implementation in `mcp_server/tools.py` directly; always go through `call_tool` so
authorization and the audit log stay in the loop. This is ADR-0001.

**Permissions (`src/psa/roles.py`)** are the security boundary, deliberately isolated
in one small, dependency-free file. `TOOL_POLICIES` maps each tool to allowed roles, an
`own_records_only_for` restriction (e.g. `employee` can only `lookup_ticket` on tickets
they filed), and whether it `requires_confirmation`. Roles are resolved server-side
from `PSA_ROLE`/case fixtures, never from client input (ADR-0002). Unknown tools/roles
fail closed (`PermissionDenied`), not open (ADR-0003).

**Runbook preconditions are enforced in the tool layer, not left to the model.**
`restart_service` (`mcp_server/tools.py`) checks `_assert_restart_is_appropriate` (are
workers actually wedged, per `err-005`) *before* the confirmation prompt — order
matters, so a human is never asked to approve something that will be refused anyway.
Confirmation tokens are HMAC-style hashes bound to `(service, environment, user)`
(`_confirm_token`), so a token cannot be replayed against a different target (ADR-0004).

**Retrieval (`src/psa/rag/`)** is BM25 over `data/corpus/*.md`, behind the `Retriever`
protocol (`rag/retrieve.py`) so a vector store can be swapped in later without touching
callers (ADR-0005, ADR-0014). Two scores matter and are not the same thing:
- `score` — BM25 relevance, used for ranking.
- `coverage` — fraction of distinct query terms present in the chunk, bounded 0..1.
  This is what `min_score`/`PSA_MIN_SCORE` gates refusal on, *not* the BM25 score,
  because BM25 has no natural absolute threshold for "do we actually know this?"
  (ADR-0006, ADR-0016, ADR-0019 — the last supersedes 0016 on how answerability is judged).

**Deprecated docs are never deleted, and are structurally promoted, not just
score-penalized** (`_promote_replacements` in `rag/retrieve.py`, ADR-0007). A retired
runbook is often the single best lexical match because the user is quoting it, so a
relevance penalty alone can't guarantee its replacement ranks first — the retriever
pulls the replacement doc in explicitly when a deprecated hit names a
`superseded_by`. The agent is expected to name the supersession in its answer, not
silently follow the retired steps.

**Providers (`src/psa/providers/`)** implement the `Provider` protocol
(`next_step(query, role, history) -> Step`): either request tool calls or produce a
final answer. `stub` is a rule-based planner with no model behind it — the default,
used by CI and `make eval`, and the published baseline (13/20 golden cases) that a real
provider has to beat. `openai_provider.py` is implemented and unit-tested but **not yet
run against the live API**; `vertex_provider.py` is interface-only. Swapping providers
is a config change (`PROVIDER=`); the golden set is what proves the swap didn't
regress (ADR-0011).

**Behavior classification (`src/psa/agent/policy.py`)** derives the `behavior` label
(`answer`|`refuse`|`escalate`|`deny`|`propose_action`|`create_ticket`|`ask`) from the
final answer text and loop state — this is part of the eval contract, so change it
carefully; `data/evals/golden.jsonl` cases assert on these exact labels (ADR-0009).

**Eval harness (`src/psa/evals/`)** is the part of this repo worth reading first per
the README. Each case in `data/evals/golden.jsonl` (20 cases) and `holdout.jsonl` (4,
never tuned against) declares independent assertions: required/forbidden citations,
required/forbidden tools, expected behavior label, content checks. Scores roll up into
four families (groundedness, correct-tool, behavior, content) plus a separate **safety
gate** — permission, unsafe-restart, and unanswerable categories must hit 100% or the
build fails (`--require-safety`); it is a gate, not something that can be averaged away
by other categories (ADR-0010). `runner.py`'s `render_report` regenerates
`docs/EVALS.md` but always preserves everything from `## Regression log` onward — that
section is hand-written prose and the most valuable content in the file; never truncate
or overwrite it when touching the runner.

## Where things live

- `src/psa/roles.py` — permission table, the security boundary
- `src/psa/rag/` — chunking (`chunk.py`, heading-boundary chunks per ADR-0008),
  BM25 index build (`index.py`), retrieval (`retrieve.py`)
- `src/psa/mcp_server/` — tool implementations, `call_tool` dispatcher, audit log,
  MCP stdio transport (`server.py`)
- `src/psa/agent/` — the loop (`orchestrator.py`), behavior policy (`policy.py`),
  system prompt (`prompts.py`)
- `src/psa/providers/` — protocol (`base.py`), `stub`, `openai_provider`, `vertex_provider`
- `src/psa/evals/` — scoring (`metrics.py`) and the runner (`runner.py`)
- `ui/app.py` — Streamlit support console (imports `psa` by prepending `src/` to
  `sys.path`, hence the `E402` ruff ignore for that file)
- `data/corpus/` — 7 synthetic help-center articles (`dep-003`/`dep-004` are the
  deprecated/superseding pair; `err-005` defines the restart precondition)
- `data/fixtures/` — fake tickets, environments, deploy history used by tools
- `data/evals/` — `golden.jsonl` (20 cases), `holdout.jsonl` (4, never tune against)
- `docs/adr/` — one file per architecture decision, including decisions *not yet made*;
  read the relevant ADR before changing behavior in the area it covers
- `docs/EVALS.md` — regenerated by `make eval`; the regression log at the bottom is
  hand-maintained and must survive regeneration

## Conventions

- Ruff rule set is pinned explicitly in `pyproject.toml` (`select = [...]`), not left
  at ruff's shifting defaults, so a routine `pip install ruff` upgrade can't turn CI red.
- `PermissionDenied`, `ConfirmationRequired`, and `PreconditionFailed`
  (`src/psa/roles.py`) are three distinct, intentional outcomes, not generic errors —
  denial/precondition-failure are expected paths the agent explains to the user, not
  bugs to swallow. Keep them distinct when writing new tools.
- Audit records redact `password`/`token`/`api_key`/`secret`/`authorization` args
  (`mcp_server/audit.py:_REDACT_KEYS`) and truncate long string args before writing to
  `audit.log` — extend `_REDACT_KEYS` rather than special-casing a new sensitive field
  elsewhere.
- `reset_runtime_state()` (`mcp_server/tools.py`) must be called between eval cases
  (the runner already does this) so created tickets / restart history from one case
  never leak into another.
