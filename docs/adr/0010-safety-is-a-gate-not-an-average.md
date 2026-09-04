# ADR-0010: Safety categories are a release gate, not a contributor to an average

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/evals/metrics.py` (`SAFETY_CATEGORIES`)
- **Tests:** `test_safety_rate_isolates_safety_categories`, `test_unmeasured_family_reports_na_not_zero`

## Context

The eval suite reports aggregate rates: pass rate, groundedness, correct-tool, content.
Aggregates are how eval results get communicated, and they hide the distribution. A
permission bypass and a missing keyword both cost one case.

Those two failures are not comparable. One is a quality miss, the other means the
product cannot ship.

## Decision

Cases in the `permission_denied`, `unsafe_restart`, and `unanswerable` categories are
reported as a separate **safety** figure that must be 100%. It is a gate, not an input to
the headline score. Assertions are also grouped into families (groundedness,
correct_tool, behavior, content) and scored independently, so a regression says *which*
property broke rather than that a case went red.

## Consequences

- A groundedness average that hides a permission bypass is worth nothing, and the report
  makes that impossible to present accidentally.
- Current state is visible and uncomfortable: safety sits at 2/6 while the overall pass
  rate is 10/20. That asymmetry is the point of separating them.
- A family with no assertions prints `n/a` rather than 0%, because "never measured" must
  not read as "total failure of something."
- The category list is hand-maintained. A new safety-relevant case filed under a
  different category silently escapes the gate.

## Alternatives considered

**Weight safety cases higher in one score.** Rejected: any weighting still permits a
passing overall number with a failing bypass, which is the outcome being prevented.

**Fail the whole suite on any safety failure.** Rejected during development, since the
suite currently has known safety failures and needs to stay runnable to fix them. This
becomes the right behaviour in CI once the gate is met.
