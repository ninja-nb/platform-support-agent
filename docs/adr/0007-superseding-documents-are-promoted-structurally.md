# ADR-0007: Superseding documents are promoted structurally, not by score penalty

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/rag/retrieve.py` (`_promote_replacements`, `DEPRECATED_PENALTY`)
- **Test:** `test_deprecated_doc_is_outranked_by_its_replacement`
- **Requirement:** R3

## Context

Retired runbooks cannot simply be deleted from the index, because users quote them —
`stale-003` is a user asking where to get the VPN pre-shared key because a retired
document told them to. The agent needs to retrieve the retired document in order to say
"that procedure is retired, use X instead" rather than silently answering from stale text
or refusing.

The first implementation applied a relevance penalty (`DEPRECATED_PENALTY = 0.35`) and
assumed that would push replacements above the documents they replace.

## Decision

Keep the penalty, but do not rely on it for the guarantee. `_promote_replacements`
injects a document's replacement above it whenever the deprecated document appears in the
results, using the replacement's opening chunk and ignoring its query score.

## Consequences

- The ordering invariant holds regardless of what the scores happen to be: the agent
  always sees the current procedure before the stale one.
- A replacement document is retrieved even when the query terms alone would never
  surface it, which is the normal case — the user is describing the retired procedure,
  not the new one.
- The promoted hit carries no meaningful relevance score, so score is not a usable proxy
  for confidence on those hits.

## Alternatives considered

**Tune `DEPRECATED_PENALTY` harder.** Rejected on evidence. For the query "VPN
pre-shared key rotate shared key" the retired document beat its replacement even with the
penalty applied, because the retired document is genuinely the better lexical match for
a user reading from it. Tuning would have fixed that one query while leaving the
invariant unproven for every other one.

**Drop deprecated documents from the index.** Rejected: the agent then cannot name the
supersession, and `stale-003` degrades from a correct answer to a refusal.
