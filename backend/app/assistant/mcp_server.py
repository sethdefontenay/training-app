"""MCP server exposing the assistant's tool registry over authed Streamable HTTP.

The same read+write tools the in-app agent uses, made available to external MCP clients
(Claude Desktop / Code / claude.ai). Gated: only mounted when MCP_TOKEN is set, and every
request must carry `Authorization: Bearer <MCP_TOKEN>`. It's an authed capability API over
the existing services — not raw DB access.
"""

import json

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from sqlalchemy import select
from starlette.types import ASGIApp, Receive, Scope, Send

from app.assistant.tools import TOOLS, TOOLS_BY_NAME
from app.database import SessionLocal
from app.models import User


def mcp_tool_defs() -> list[types.Tool]:
    return [
        types.Tool(name=t.name, description=t.description, inputSchema=t.input_schema)
        for t in TOOLS
    ]


async def call_mcp_tool(name: str, arguments: dict[str, object]) -> str:
    """Dispatch a tool call to the registry, with its own DB session. Returns JSON text."""
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return json.dumps({"error": f"unknown tool {name}"})
    try:
        async with SessionLocal() as session:
            # The MCP server is gated behind a single MCP_TOKEN — the owner's external
            # access — so tools operate over the admin (owner) account's data.
            owner = await session.scalar(
                select(User).where(User.is_admin.is_(True)).order_by(User.id).limit(1)
            )
            if owner is None:
                return json.dumps({"error": "no admin user configured"})
            result = await tool.handler(session, arguments, owner.id)
        return json.dumps(result, default=str)
    except Exception as e:  # surface to the MCP client rather than 500
        return json.dumps({"error": str(e)})


def _build_server() -> Server:
    server: Server = Server("training-app")

    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
    async def _list() -> list[types.Tool]:
        return mcp_tool_defs()

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def _call(name: str, arguments: dict[str, object]) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=await call_mcp_tool(name, arguments or {}))]

    return server


_manager: StreamableHTTPSessionManager | None = None


def session_manager() -> StreamableHTTPSessionManager:
    global _manager
    if _manager is None:
        _manager = StreamableHTTPSessionManager(
            app=_build_server(), json_response=True, stateless=True
        )
    return _manager


def bearer_guard(asgi: ASGIApp, token: str) -> ASGIApp:
    """ASGI wrapper that rejects any request without the exact bearer token."""

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http":
            headers = dict(scope.get("headers") or [])
            if headers.get(b"authorization", b"").decode() != f"Bearer {token}":
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await asgi(scope, receive, send)

    return guarded


async def mcp_asgi(scope: Scope, receive: Receive, send: Send) -> None:
    await session_manager().handle_request(scope, receive, send)
