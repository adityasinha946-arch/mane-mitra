"""MCP client side: the app connects to the krera-registry MCP server.

Each call starts the server process, performs the MCP handshake, calls the
tool and closes. If MCP fails for any reason, the same function is called
directly and the trace says "direct (MCP unavailable)", so the demo never
claims MCP when MCP was not used.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import registry

SERVER = Path(__file__).parent / "registry_mcp_server.py"

_DIRECT = {
    "check_registration": lambda a: registry.check_registration(a.get("registration_no", "")),
    "search_projects": lambda a: registry.search_projects(a.get("project_name", ""), a.get("promoter", ""), a.get("district", "")),
    "register_summary": lambda a: registry.register_summary(),
}


def _text_of(result) -> str:
    parts = []
    for c in getattr(result, "content", []) or []:
        t = getattr(c, "text", None)
        if t:
            parts.append(t)
    return "\n".join(parts)


async def _session_call(tool: str | None, args: dict | None):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], cwd=str(SERVER.parent))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if tool is None:
                listed = await session.list_tools()
                return [t.name for t in listed.tools]
            res = await session.call_tool(tool, args or {})
            if getattr(res, "is_error", False) or getattr(res, "isError", False):
                raise RuntimeError(_text_of(res) or "MCP tool error")
            return _text_of(res)


def _run(coro, timeout: float = 30):
    return asyncio.run(asyncio.wait_for(coro, timeout))


def list_tools() -> tuple[list[str], str]:
    """Returns (tool names, error message or '')."""
    try:
        return _run(_session_call(None, None)), ""
    except Exception as e:  # noqa: BLE001
        return list(_DIRECT), f"{type(e).__name__}: {e}"


def call(tool: str, args: dict) -> tuple[dict, dict]:
    """Returns (result, trace info)."""
    t0 = time.time()
    try:
        text = _run(_session_call(tool, args))
        data = json.loads(text)
        return data, {"via": "MCP server krera-registry (stdio)", "ms": int((time.time() - t0) * 1000)}
    except Exception as e:  # noqa: BLE001
        data = _DIRECT[tool](args)
        return data, {"via": "direct (MCP unavailable)", "error": f"{type(e).__name__}: {e}",
                      "ms": int((time.time() - t0) * 1000)}
