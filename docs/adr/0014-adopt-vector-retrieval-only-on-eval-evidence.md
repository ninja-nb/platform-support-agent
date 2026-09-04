# ADR-0014: Adopt vector retrieval only when the golden set shows lexical retrieval is the bottleneck

- **Status:** Proposed
- **Date:** 2026-09-04
- **Extends:** ADR-0005

## Context

ADR-0005 chose BM25 as a control, explicitly so that a later vector store could be
measured rather than assumed. The question now is what evidence justifies the swap, since
the temptation is to do it because the résumé line wants "Vertex Vector Search" on it.

The corpus is a few dozen documents. At that size lexical retrieval is a strong baseline
and an embedding model is not obviously better.

## Decision (proposed)

Do not adopt vector retrieval until a retrieval failure in the golden or holdout set is
attributable to lexical matching specifically. The trigger is a case where the correct
document exists in the corpus and is not retrieved because the query paraphrases it.

When that trigger fires, implement embeddings behind the existing `Retriever` protocol
and report before/after numbers on the same case set in `docs/EVALS.md`.

## Consequences

- If the swap does not move the numbers, that is a publishable result and a better
  interview answer than an unmeasured migration.
- Keeps CI offline until there is a reason to give that up. An embedding call in the
  retrieval path means the eval suite needs credentials.
- Delays the point at which "vector databases" is honestly claimable.
- Risk: the current failures may all be provider failures rather than retrieval
  failures, in which case this trigger never fires and the decision stays open
  indefinitely. That is an acceptable outcome, but it should be a stated one.

## Candidate evidence

- `holdout-001` — "VPN connects fine but none of our internal hostnames work" must reach
  a DNS document while the user's words are all about VPN. The clearest paraphrase case.
- `cross-doc-017` currently misses `net-002` while retrieving `dep-004`. Diagnose before
  concluding: this may be a `top_k` or multi-query problem rather than a lexical one, and
  swapping retrievers would hide which.

## Alternatives considered

**Hybrid lexical + dense with reciprocal rank fusion.** Probably the right end state,
but it should follow the measurement rather than replace it.

**Raise `top_k` first.** Cheaper and should be tried before any retriever change, since
`cross-doc-017` may simply need more than four hits to cover two problems.
