# ADR-0011: The agent depends on a `Provider` protocol, never on a vendor SDK

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/providers/base.py`
- **Requirement:** R15

## Context

The project has to demonstrate the same agent running on Vertex/Gemini and on
OpenAI or Claude, and the eval numbers only mean something if both run the same golden
set. Vendor SDKs differ in message shape, tool-call representation, and usage reporting.

The eval suite also needs to run in CI with no API keys.

## Decision

The agent depends on a single method: `Provider.next_step(query, role, history) -> Step`,
where a `Step` either requests tool calls or carries a final answer. Vendor code is
confined to `providers/`. A rule-based `stub` provider implements the same protocol so
`make eval` runs offline and deterministically.

`Usage` carries tokens and cost, and each provider owns its own price table so the eval
table's `$/request` column comes from the provider that actually served the request.

## Consequences

- Switching providers is a `PROVIDER=` change, and the golden set is what proves the
  swap is safe rather than a claim that it is.
- `TOOL_SCHEMAS` is already in the shape the chat-completions tool API expects, so
  provider work is the SDK call plus mapping the response onto `Step`.
- The stub makes CI free and deterministic, but every number currently in `EVALS.md`
  comes from it. R15 is unproven until `next_step` is implemented for both real
  providers — it currently raises `NotImplementedError`.
- Price tables are hand-maintained. A stale entry silently corrupts the cost metric
  rather than failing.

## Alternatives considered

**Use LangChain's model abstraction.** Rejected for the provider seam: it brings a large
dependency to hide a one-method interface, and the mapping work does not disappear.

**Target one provider and port later.** Rejected: the abstraction is cheap now and
retrofitting it after the agent loop, prompts, and eval harness assume one vendor's
message shape is not.
