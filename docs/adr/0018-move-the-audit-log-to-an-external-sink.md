# ADR-0018: Move the audit log to a sink the serving process cannot rewrite

- **Status:** Proposed
- **Date:** 2026-09-04
- **Threats:** T9 (open), T8
- **Code:** `src/psa/mcp_server/audit.py`

## Context

`audit.record` appends JSON lines to a local file and keeps an in-process copy for the
UI panel and tests. The file is written by the same process that serves requests, so that
process — or anything that compromises it — can truncate or rewrite it. T9 is the second
of the two threats recorded as not mitigated.

This matters more here than the "append-only" docstring suggests. The audit log is the
only evidence that the permission boundary held. Denials are its most valuable records,
and they are exactly what an attacker would remove.

## Decision (proposed)

Write audit records to an external sink to which the application holds append-only
credentials and no delete or overwrite permission — Cloud Logging with a log sink, or an
object store with retention lock. Keep the local file as a development fallback only.

## Consequences

- Denial records become evidence rather than a claim, which is the whole point of
  auditing an authorization boundary.
- Introduces a write path that can fail. This forces a decision the current code does not
  face: if the audit write fails, does the tool call proceed? For gated and denied
  outcomes the answer should be no, which makes auditing part of the request path rather
  than a side effect of it.
- Adds a cloud dependency to something that currently runs entirely offline. The eval
  suite and `docker compose up` must keep working without credentials, which is what
  `PSA_AUDIT_DISABLE` and the in-memory log already allow for.
- Does not address T8's residual: redaction is key-name based, so a secret pasted into a
  ticket body is logged as ticket text. Moving the sink makes that worse, not better,
  because the record becomes undeletable.

## Open questions

- Retention period. Unanswered in this repo and genuinely a customer question in a real
  engagement, since it interacts with the ticket data in the log.
- Does the in-process `_memory_log` stay? It is convenient for tests and the UI, but it
  is a second copy of audit data with none of the guarantees.

## Alternatives considered

**Chain records with a hash of the previous entry.** Makes tampering detectable without
an external dependency, and would keep the offline story intact. Weaker than
unauthorised-write-prevention but meaningfully better than nothing, and a good
intermediate step.

**Write to a separate local process running as another user.** Closes the direct-rewrite
path with no cloud dependency, at the cost of an operational component. Reasonable for an
on-premise deployment.
