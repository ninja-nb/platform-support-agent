# ADR-0016: Separate the refusal threshold from the retrieval threshold

- **Status:** Superseded by [ADR-0019](0019-answerability-is-judged-on-retrieved-passages.md)
- **Date:** 2026-09-04
- **Extends:** ADR-0006
- **Requirement:** R2

> **Superseded before implementation.** The premise below — that one knob is serving two
> questions and should be split — did not survive measurement. Three candidate
> answerability metrics were evaluated, including the unmatched-term weighting this
> record suggests in its own consequences, and none separates must-answer from
> must-refuse cases at any threshold. Coverage is confounded by query length. See
> ADR-0019 and regression log R2 in `docs/EVALS.md` for the numbers. Retained because
> the reasoning was sound and the disproof is the useful part.

## Context

ADR-0006 gates refusal on term coverage with `PSA_MIN_SCORE = 0.15`. That value is known
to be too permissive, and there is a concrete failure: `unanswerable-015` asks how to
rotate a TLS certificate on a Snowflake connector, and retrieval returns `vpn-001`
because the query shares the terms "rotate", "tls", and "certificate" with the VPN
certificate document. The agent then answers with a citation, so the case fails all
three of its assertions — behaviour, `no_citations`, and `must_mention`.

This is precisely the failure R2 exists to prevent, and it is the case that keeps the
groundedness number honest.

The naive fix is to raise the threshold. That is a single knob serving two different
questions: "is this chunk worth showing the model?" and "do we know enough to answer at
all?" A threshold high enough to reject the Snowflake query will also drop legitimate
supporting chunks on multi-part questions like `cross-doc-017`.

## Decision (proposed)

Split the knob. Keep a low admission threshold for what enters the result set, and add a
separate, higher **answerability** threshold evaluated on the best hit that determines
whether `search_docs` reports `grounded: true`.

Tune the answerability threshold against the `unanswerable` and `cross_doc` categories
together, since they pull in opposite directions, and record the before/after in
`docs/EVALS.md`.

## Consequences

- Refusal stops competing with recall. Today, fixing `unanswerable-015` by raising one
  number is expected to break `cross-doc-017`.
- `grounded` becomes a deliberate judgement rather than a side effect of the hit list
  being non-empty.
- Two thresholds is more configuration surface, and the second one needs a name that
  does not invite confusion with the first. `PSA_MIN_SCORE` is already a misnomer, since
  it is a coverage floor and not a score.
- Coverage may not be sufficient on its own for answerability. The Snowflake query has
  genuinely high term overlap with `vpn-001`; the terms it *lacks* ("snowflake",
  "connector") are the signal, which suggests the metric should weight unmatched query
  terms rather than only counting matched ones.

## Alternatives considered

**Raise `PSA_MIN_SCORE` and accept the recall loss.** Cheapest, and worth measuring first
to quantify the tradeoff before adding a second threshold.

**Require the retrieved chunk's `service` to plausibly match the query.** Would reject
the Snowflake case cleanly, since no corpus document has that service. Narrower and
possibly better than threshold tuning, but it depends on the query naming a service.

**Have the model judge whether the passages answer the question.** Rejected on the same
grounds as in ADR-0006: the failure being prevented is the model believing it knows.
