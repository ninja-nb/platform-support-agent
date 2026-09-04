# ADR-0015: Replace `PSA_ROLE` with per-request identity from a verified token

- **Status:** Proposed
- **Date:** 2026-09-04
- **Extends:** ADR-0002
- **Threat:** T1

## Context

ADR-0002 establishes role server-side, which closes the client-declared-role bypass. It
does so with a process-level environment variable, so one server process serves exactly
one role and one user.

This is the largest gap between this repo and something deployable. Every real
deployment is multi-tenant: `lookup_ticket`'s ownership check compares against
`settings().user`, so a single process cannot serve two employees correctly.

## Decision (proposed)

Derive `role` and `user` per request from a verified bearer token — the customer's IdP in
a real engagement — and pass them through `call_tool` exactly as they are passed today.
`PSA_ROLE` and `PSA_USER` remain as local development and eval defaults only.

## Consequences

- The shape of the authorization check does not change. Only the source of the identity
  does, which is the argument that ADR-0002's design was right even though its
  implementation is a placeholder.
- The audit log gains a real subject. Today `user` is whatever the environment says,
  which makes the log's non-repudiation value approximately zero.
- Requires deciding what happens when a token is absent or expired mid-confirmation: a
  pending gated action is bound to a `user` (ADR-0004), so identity has to outlive the
  round-trip.
- The eval harness must keep working without a token, or every case needs an auth
  fixture.

## Open questions

- Does role map from IdP groups, or from a separate entitlement service? In a real
  engagement this is a discovery question for the customer's support org, not a
  technical choice.
- Should `sre` be a role or a scope? If restart authority is delegated per-service, the
  permission table in `roles.py` needs a resource dimension it does not currently have.

## Alternatives considered

**Per-request role as a signed header from a trusted gateway.** Simpler, and adequate if
the gateway is genuinely the only ingress. Rejected as the default because it makes the
security property depend on deployment topology rather than on verification.

**Keep one process per role.** Workable for a demo and already the status quo. Does not
scale past it, and does not fix the `user` half of the problem at all.
