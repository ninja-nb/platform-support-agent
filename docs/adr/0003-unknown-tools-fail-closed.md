# ADR-0003: Unknown tools fail closed

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/roles.py` (`policy_for`)
- **Threat:** T5
- **Test:** `test_unknown_tool_fails_closed`

## Context

`TOOL_POLICIES` maps a tool name to its permission policy. A tool can be implemented and
registered in `_IMPLEMENTATIONS` without a corresponding policy entry — an easy omission
when adding a tool in a hurry.

## Decision

`policy_for` raises `PermissionDenied` for any tool absent from `TOOL_POLICIES`. There is
no default policy.

## Consequences

- Adding a tool without deciding its permissions is a hard error at call time rather
  than an accidental grant to every role.
- The failure is loud and arrives during development, not in an audit months later.
- It is mildly annoying to add a tool. This is the one place where being annoying is
  correct.

## Alternatives considered

**Default to the most restrictive role (`sre`-only).** Rejected: still a silent grant,
just a narrower one, and it would let a tool ship without anyone deciding whether an
`sre` should have it either.

**Default to deny with a warning log.** Rejected: a warning in a log nobody reads is
indistinguishable from no check.
