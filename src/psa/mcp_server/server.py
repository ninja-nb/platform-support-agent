"""MCP stdio server.

A transport in front of `psa.mcp_server.tools`, deliberately thin. Authorization,
the confirmation gate, and auditing all live in `call_tool`, so an MCP client
cannot reach a tool by a path that skips them.

Role comes from the server's own environment (`PSA_ROLE`), never from the client.
A client that could name its own role would make the permission table decorative.

    PSA_ROLE=employee python -m psa.mcp_server.server
"""

from __future__ import annotations

import asyncio
import json

from psa.config import settings
from psa.mcp_server.tools import TOOL_SCHEMAS, call_tool
from psa.roles import ConfirmationRequired, PermissionDenied


def _dispatch(name: str, args: dict) -> str:
    """Run a tool and render the outcome as text for the model.

    Denials and confirmation prompts are returned as *results*, not transport
    errors: the agent needs to read them and change course.
    """
    cfg = settings()
    try:
        return json.dumps(call_tool(name, args, role=cfg.role, user=cfg.user), indent=2)
    except PermissionDenied as exc:
        return json.dumps({"error": "permission_denied", "message": str(exc)}, indent=2)
    except ConfirmationRequired as exc:
        return json.dumps(
            {
                "error": "confirmation_required",
                "message": str(exc),
                "confirm_token": exc.confirm_token,
                "preview": exc.preview,
            },
            indent=2,
        )


async def serve() -> None:
    try:
        import mcp.types as types
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise SystemExit(
            "the MCP server needs the optional dependency: pip install -e '.[mcp]'"
        ) from exc

    server = Server("platform-support-agent")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=schema["name"],
                description=schema["description"],
                inputSchema=schema["input_schema"],
            )
            for schema in TOOL_SCHEMAS
        ]

    @server.call_tool()
    async def handle_call(name: str, arguments: dict | None) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=_dispatch(name, arguments or {}))]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
