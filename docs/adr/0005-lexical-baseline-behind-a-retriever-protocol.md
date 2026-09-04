# ADR-0005: Start with a lexical BM25 baseline behind a `Retriever` protocol

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/rag/index.py`, `src/psa/rag/retrieve.py`
- **Superseded by:** nothing yet; see ADR-0014 for the vector-store decision

## Context

The corpus is a few dozen synthetic help-center and runbook documents. Embeddings plus a
vector store is the default choice for RAG, and it is also the thing the résumé line
wants to claim.

The problem with starting there is that it makes the retrieval quality unattributable.
If the first implementation is embeddings, there is no control to compare against, so
"the vector store helped" is an assumption rather than a measurement.

## Decision

Implement BM25 over heading-aware chunks using only the standard library, and put it
behind a `Retriever` protocol that returns `Hit` objects. Nothing downstream depends on
BM25 — the agent, the tool layer, and the eval harness depend on `Hit`.

## Consequences

- The eval suite runs in CI with no API keys, no network, and deterministically, which
  is what makes `PROVIDER=stub` runs meaningful.
- When embeddings or Vertex Vector Search land behind the same interface, the golden set
  measures whether the swap helped instead of assuming it did.
- Lexical retrieval is genuinely weak on paraphrase. `holdout-001` ("VPN connects but
  hostnames don't work" → a DNS document) is the case most likely to expose this, and it
  is the intended trigger for ADR-0014.
- BM25 `K1`/`B` stay at standard defaults. Retuning them without eval evidence is
  fitting noise on a 20-case set.

## Alternatives considered

**Embeddings plus a vector store first.** Rejected for this stage: no baseline to
attribute improvement to, adds an API dependency to CI, and on a corpus this size
lexical retrieval is a legitimately strong baseline.

**Hybrid from the start.** Rejected: two untuned systems and no control is worse than
one control.
