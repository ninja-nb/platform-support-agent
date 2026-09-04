# ADR-0008: Chunk on heading boundaries and weight titles at index time

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/rag/chunk.py` (`split_sections`), `src/psa/rag/index.py`
- **Test:** `test_sections_split_on_h2`
- **Requirement:** R8

## Context

Runbooks in this corpus have a consistent shape: symptom, diagnosis, resolution steps,
and an "Escalate when" section. Requirement R8 is that the agent escalates when a
runbook's escalation condition is met.

With whole-document chunks, the escalation condition competes with the resolution steps
inside a single unit. A query matching the symptom retrieves the document, and the
resolution steps dominate the passage, so the agent walks the user through a fix in a
situation the runbook says to escalate.

## Decision

Split documents on `##` boundaries into `(heading, text)` chunks, so "Resolution" and
"Escalate when" are separately retrievable. At index time, weight the title and heading
by repeating them in the token stream.

## Consequences

- The escalation eval cases become answerable at all: `escalate-018`, `escalate-019`,
  and `escalate-020` depend on the escalation condition being retrievable on its own.
- Title/heading weighting means a query naming a symptom reaches the right document even
  when the body phrases it differently, which partially offsets the lexical weakness in
  ADR-0005.
- Chunks are uneven in length. BM25 length normalisation (`B = 0.75`) handles this, but
  a very short section can rank on a single term match.
- Chunk boundaries are now a property of corpus authoring. A runbook written without
  `##` headings degrades to one chunk and loses the benefit silently.

## Alternatives considered

**Fixed-size overlapping windows.** Rejected: splits "Escalate when" across two chunks
as often as not, and the boundary lands arbitrarily relative to meaning.

**Whole documents as chunks.** Rejected: the failure described above, which is the
direct cause of escalation cases failing.
