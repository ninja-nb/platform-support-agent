# ADR-0006: Refusal is gated on term coverage, not BM25 score

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/rag/retrieve.py` (`_coverage`), `PSA_MIN_SCORE`
- **Test:** `test_coverage_threshold_rejects_off_corpus_queries`
- **Requirement:** R2

## Context

The agent must refuse rather than answer when the corpus does not cover a question —
requirement R2, and the property that keeps the groundedness number honest. That needs a
numeric test for "do we actually know this?"

BM25 scores are the obvious candidate and are unusable for it. They are unbounded above
and depend on corpus statistics, so a score of 4.0 means something different for a
two-word query than a twenty-word one, and any fixed threshold on them is arbitrary.

## Decision

Refusal is gated on **coverage**: the fraction of distinct content terms in the query
that appear in the chunk. Coverage is bounded 0..1 and comparable across queries, which
makes it usable as an absolute threshold. `PSA_MIN_SCORE` (default 0.15) is the cutoff.
BM25 score is still used for *ranking*; coverage decides *admission*.

## Consequences

- An empty hit list is a legitimate, expected outcome rather than an error, and
  `search_docs` reports `grounded: false` so the agent refuses and offers
  `create_ticket`.
- Coverage is computed over title, heading, and text, so a chunk whose heading names the
  symptom is admitted even when the body phrases it differently.
- The threshold is a tuning knob to be moved only with eval evidence. The current value
  is known to be too permissive — see the `unanswerable-015` failure.
- **Corrected by [ADR-0019](0019-answerability-is-judged-on-retrieved-passages.md).** The
  claim above that coverage is "comparable across queries" is too strong. Coverage is
  *bounded*, which is not the same property. Because it divides by the number of distinct
  query terms, a verbose but answerable question is diluted by narrative words absent
  from any runbook, and scores below a terse question the corpus cannot answer at all.
  Coverage is therefore retained for admission only; it is not an answerability signal,
  and refusal is decided per ADR-0019.
- Coverage is term-presence based, so it inherits the paraphrase weakness of ADR-0005: a
  correctly-covered question phrased in different words scores low.

## Alternatives considered

**Threshold on BM25 score.** Rejected: not comparable across queries, so the number
would have to be retuned per query shape and would still be arbitrary.

**Ask the model whether it knows.** Rejected: the failure being prevented *is* the model
believing it knows. Self-assessment is not independent evidence.

**Normalise BM25 by the top hit's score.** Rejected: makes every query look confident,
because the best hit always scores 1.0 relative to itself — which is exactly wrong for
an off-corpus query.
