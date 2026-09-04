# ADR-0001: Tools are plain functions behind one dispatcher; MCP is a transport

- **Status:** Accepted
- **Date:** 2026-09-04 (recorded retrospectively)
- **Code:** `src/psa/mcp_server/tools.py`

## Context

The tool surface needs authorization, a confirmation gate for irreversible actions, and
an audit record for every call. MCP is the intended transport, so the obvious place to
put those checks is the MCP request handler.

But the eval suite and the agent loop call tools in-process. If enforcement lives in the
handler, those callers take a different path than a real MCP client, and the tests stop
being evidence about deployed behaviour.

## Decision

Tools are plain Python functions. `call_tool` is the single entry point and does, in
order: `authorize`, execute, `audit.record`. The MCP server is a thin adapter in front
of it. Denials and confirmation prompts are returned to the model as tool *results*, not
as transport errors.

## Consequences

- The agent, the eval harness, and an MCP client all exercise the same authorization
  code, so eval numbers describe the real boundary.
- Transport can change — stdio, HTTP, direct call — without touching security code.
- Returning denials as results means the model must read and react to them, which is
  what golden case `permission-009` asserts. A transport that swallowed them would make
  that behaviour impossible.
- `call_tool` is a chokepoint and therefore a hot spot for review. That is deliberate.

## Alternatives considered

**Enforce in the MCP handler.** Rejected: leaves a second, unguarded path to the tool
implementations for any in-process caller, and decouples what the tests prove from what
ships.

**Decorator-based permissions on each tool function.** Rejected: enforcement becomes
opt-in per function, so a new tool added without the decorator is silently public. See
ADR-0003 on failing closed.
