# ADR-0019: Answerability is judged by the model on retrieved passages, not by a coverage threshold

- **Status:** Accepted
- **Date:** 2026-09-04
- **Supersedes:** ADR-0016
- **Amends:** ADR-0006
- **Code:** `src/psa/agent/prompts.py` (grounding rules), `src/psa/rag/retrieve.py`
- **Requirement:** R2
- **Evidence:** `docs/EVALS.md` regression log R2

## Context

ADR-0006 gates refusal on term coverage and calls the threshold "a tuning knob to be
moved only with eval evidence". ADR-0016 proposed splitting that knob into an admission
threshold and a separate, higher answerability threshold, on the reasoning that one
number was serving two different questions.

Before tuning anything, three candidate answerability metrics were measured on the top
hit for every golden and holdout case that pulls in either direction. `plain` is current
coverage. `weighted` is IDF-weighted coverage that penalises unmatched query terms,
including a maximum penalty for terms absent from the corpus entirely — the metric
ADR-0016 suggests in its own consequences. `topic` excludes entity identifiers such as
service and environment names, on the grounds that those are resolved by `get_status`
rather than by a runbook.

| Case | Required | plain | weighted | topic |
|---|---|---|---|---|
| `unanswerable-015` Snowflake | refuse | 0.40 | 0.34 | 0.40 |
| `unanswerable-016` SLA credit | refuse | 0.11 | 0.11 | 0.11 |
| `holdout-003` log retention | refuse | 0.33 | 0.34 | 0.33 |
| `howto-001` VPN | answer | 0.82 | 0.78 | 0.82 |
| `discriminate-004` capacity | answer | 0.50 | 0.43 | 0.75 |
| `cross-doc-017` two problems | answer | **0.31** | **0.17** | **0.33** |
| `incident-006` 503s | answer | **0.11** | **0.08** | **0.20** |

No threshold on any of the three separates the classes. Each places at least two
must-answer cases below at least one must-refuse case. IDF weighting is the worst of the
three, dropping `incident-006` to 0.08 — far under the 0.34 of a question the corpus
cannot answer at all.

The confound is query length, not relevance. Coverage divides by the number of distinct
query terms, so a long, descriptive, entirely answerable question is diluted by narrative
words no runbook contains, while a terse off-corpus question with two generic matches
(`tls`, `certificate`) scores 0.40. This also corrects ADR-0006, which claims coverage is
"comparable across queries": it is bounded, which is not the same thing, and the
comparison degrades as query verbosity varies.

Splitting the knob therefore has nothing to split. A second threshold over the same
family of metrics inherits the same confound.

## Decision

Coverage remains an **admission** filter only. It decides what is worth showing the
model and is explicitly not treated as an answerability signal. `PSA_MIN_SCORE` stays at
0.15 rather than being tuned to make one case pass.

Answerability is judged by the model on the passages it was given. The system prompt
states that `search_docs` returns the closest passages rather than necessarily relevant
ones, requires the model to judge relevance before use, and names this specific trap: a
passage about VPN device certificates is not an answer about a third-party connector's
certificates, however similar the wording. A standing prohibition is added on emitting
any specific number — quota, timeout, SLA credit — absent from a cited passage.

ADR-0006 and ADR-0016 both rejected model self-assessment because "the failure being
prevented is the model believing it knows". That objection is accepted for one failure
and rejected for another. Answering from parametric knowledge with no retrieval is the
failure it describes, and the grounding rules plus the `no_citations` assertions target
it. Deciding whether a passage that *was* retrieved is on-topic is a reading-comprehension
task performed against text in the context window, and is not self-assessment of internal
knowledge.

## Consequences

- Refusal correctness now depends on the provider, so it cannot be validated under the
  `stub` provider, which has no relevance judgment to apply. `unanswerable-015` is the
  one safety case still failing, and the safety gate sits at 5/6 until a real provider
  runs. This ADR is Accepted as a decision but **unvalidated as an outcome**, which is a
  worse position than a passing test and is recorded rather than hidden.
- A prompt is a weaker guarantee than a threshold. It is not enforceable, varies by
  model, and can regress silently on a model upgrade. The golden `unanswerable` cases
  are the only thing that will catch that, which raises their value and argues for more
  of them than the three that exist.
- The refusal decision moves out of code that can be unit-tested and into behaviour that
  can only be evaluated. This is a real loss of determinism, accepted because the
  measurements show the deterministic option does not work.
- If model judgment does not close `unanswerable-015`, the next lever is embeddings
  behind the existing `Retriever` interface (ADR-0014). Cosine similarity is
  length-normalised, so it does not suffer the dilution effect above, and `snowflake`
  and `connector` having no semantic neighbours in the corpus is usable signal in a way
  their lexical absence is not.

## Alternatives considered

**Raise `PSA_MIN_SCORE`, as ADR-0016 proposed measuring first.** Measured and rejected.
Refusing `unanswerable-015` at 0.40 requires a threshold that also refuses
`cross-doc-017` at 0.31 and `incident-006` at 0.11, both of which must be answered.

**Split into admission and answerability thresholds (ADR-0016's decision).** Rejected.
The premise was that one knob served two questions; the measurements show the metric
family cannot answer the second question at any threshold.

**IDF-weight the unmatched query terms, as ADR-0016 suggests in its consequences.**
Measured and rejected as the worst of the three candidates.

**Require the retrieved chunk's `service` to plausibly match the query.** Still open and
narrower than threshold tuning. Rejected for now because it depends on the query naming
a service, which `unanswerable-016` and `holdout-003` do not.

**Exclude entity identifiers from the metric (`topic`).** Measured. It is the best of the
three and helps `discriminate-004` materially (0.50 to 0.75), but still fails to separate
`cross-doc-017` from `holdout-003`. Worth revisiting as a ranking input rather than as a
refusal gate.
