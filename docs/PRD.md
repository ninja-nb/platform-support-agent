# Product requirements: Meridian platform support agent

Engagement framing. Meridian Cloud is a mid-size SaaS platform company. Its internal
platform team runs a help center and a set of runbooks, and fields tickets from two
populations: employees who hit VPN, DNS, and deploy problems, and L2/SRE responders who
handle production incidents. This document states what the agent must do to be
considered correct, and what "done" means. `ARCHITECTURE.md` covers how it is built,
`EVALS.md` covers how well it currently does it, and `THREAT_MODEL.md` covers what an
adversary can do to it.

## Problem

Support volume is dominated by questions the help center already answers, but answering
them requires knowing which of several near-identical failure modes applies. A deploy
rejected for `INSUFFICIENT_CAPACITY` and one rejected for `QUOTA_EXCEEDED` read almost
identically to the reporter and have completely different resolutions. Meanwhile the
resolution path for a genuinely wedged service requires privileges most reporters do not
have, so tickets bounce between queues.

The failure mode that matters is not an unanswered question. It is a confident wrong
answer that sends someone to file a quota increase for a capacity problem, or that
restarts a saturated service and removes the capacity that was still serving traffic.

## Users and roles

| Role | Who | May do |
|---|---|---|
| `employee` (alias `intern`) | Any Meridian employee filing a ticket | Search docs, read **own** tickets, read environment and deploy status, file tickets |
| `sre` (alias `l2`) | L2 responders and on-call | All of the above across all tickets, plus restart a service after human confirmation |

Role is established by the server, never asserted by the caller. In this build it comes
from `PSA_ROLE`; in a real deployment it comes from the customer's IdP.

## Requirements

Each requirement is stated as an observable behavior and is owned by at least one case
in `data/evals/golden.jsonl`. A requirement with no case behind it is not a requirement,
it is an intention. Behavior labels are the ones defined in `src/psa/agent/policy.py`.

### Knowledge

| # | Requirement | Behavior | Cases |
|---|---|---|---|
| R1 | Answer from the corpus with a citable `doc_id` for every claim | `answer` | `howto-001`, `howto-002` |
| R2 | When the corpus does not cover the question, say so and offer to file a ticket rather than answer from model knowledge | `refuse`, `create_ticket` | `unanswerable-015`, `unanswerable-016`, `holdout-003` |
| R3 | Name a retired procedure as retired and point at its replacement, even when the user is quoting the retired doc | `answer`, `refuse` | `stale-003` |
| R4 | Cover every distinct problem in a multi-problem ticket, not just the first | `answer`, `escalate` | `cross-doc-017`, `holdout-004` |

### Judgment

| # | Requirement | Behavior | Cases |
|---|---|---|---|
| R5 | Distinguish confusable causes that share a symptom (capacity vs. quota, VPN vs. DNS) and cite only the applicable doc | `answer` | `discriminate-004`, `discriminate-005`, `holdout-001` |
| R6 | Ask for the missing identifier instead of guessing between failure modes | `ask`, `refuse` | `missing-evidence-013` |
| R7 | State plainly when a named service or environment does not exist rather than inventing state for it | `ask`, `refuse` | `wrong-service-014` |
| R8 | Escalate to the named owning team when a runbook's escalation condition is met | `escalate` | `escalate-018`, `escalate-019`, `escalate-020` |

### Authorization and safety

| # | Requirement | Behavior | Cases |
|---|---|---|---|
| R9 | Deny actions outside the caller's role, explain the denial, and offer a ticket | `deny` | `permission-009` |
| R10 | Restrict employees to records they filed, without leaking the contents of a refused record | `deny` | `permission-010`, `ticket-011` |
| R11 | Stop at a human confirmation prompt before any irreversible action, including when the action is legitimate | `propose_action` | `gated-restart-008` |
| R12 | Refuse a directly requested action that the runbook says is wrong, rather than complying | `answer`, `escalate`, `propose_action` | `unsafe-restart-007`, `holdout-002` |
| R13 | Never state or imply that an action was taken when it was not | asserted via `must_not_mention` | `unsafe-restart-007`, `permission-009` |

R13 is separate from R9–R12 on purpose. An agent that correctly refuses to restart and
then reports "I restarted it" has failed as badly as one that restarted the wrong
service, because the human acts on the report.

### Operations

| # | Requirement | Verified by |
|---|---|---|
| R14 | Every tool call is authorized and audited, including denials and confirmation prompts | `src/psa/mcp_server/audit.py`, threat model T8 |
| R15 | The same golden set passes under `PROVIDER=vertex` and `PROVIDER=openai` | `make eval` under both providers |
| R16 | A stranger can clone the repo, run `docker compose up`, and see the eval table | `infra/docker-compose.yml`, `make up` |

## Launch bar

The project is presentable when all of the following hold. Current values are from
`docs/EVALS.md` and are regenerated by `make eval`.

| Gate | Bar | Current (`stub`) |
|---|---|---|
| Safety categories (`permission_denied`, `unsafe_restart`, `unanswerable`) | 100%, not an average | 33% (2/6) |
| Cases passed | ≥90% | 50% (10/20) |
| Groundedness | ≥90% | 73% (11/15) |
| Correct tool | 100% | 100% (10/10) |
| Providers passing | `vertex` and `openai`, not just `stub` | stub only |
| Regression log | ≥1 miss diagnosed and fixed in writing | empty |

Safety is a gate rather than a contributor to an average score. A groundedness number
that hides a permission bypass is worth nothing, which is why `metrics.py` reports the
safety categories separately.

## Non-goals

- **Not a coding or SDLC agent.** That comparison invites being measured against Cursor.
- **Not an SRE incident copilot.** Incident diagnosis is one ticket type here, not the
  product.
- **No real customer or Salesforce data.** The corpus, tickets, and environments are all
  synthetic.
- **No autonomous remediation.** There is no configuration in which the agent restarts a
  service without a human confirming. This is a product decision, not a limitation to be
  relaxed later.
- **No fine-tuning.** Retrieval and policy carry the quality, so that eval movement is
  attributable.
- **No multi-tenancy.** One process serves one role; see threat model T1.

## Known gaps at time of writing

The two things that would block turning this on for real users are recorded as open in
the threat model: prompt injection via corpus content (T6) and an audit log the serving
process can rewrite (T9). The retrieval refusal threshold `PSA_MIN_SCORE` is also known
to be too permissive — `unanswerable-015` currently answers a Snowflake certificate
question by retrieving a VPN certificate document, which is exactly the failure R2
exists to prevent.

Providers are interfaces only at present; `next_step` is unimplemented for Vertex and
OpenAI, so R15 is unproven and every current number comes from the rule-based stub.
