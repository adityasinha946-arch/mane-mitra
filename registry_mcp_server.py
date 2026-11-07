"""MCP server: "krera-registry".

A real Model Context Protocol server. The chatbot app starts it as a separate
process and talks to it over standard input/output, the same way MCP clients
such as Claude Desktop connect to MCP servers. Tools exposed:
  - check_registration(registration_no)
  - search_projects(project_name, promoter, district)
  - register_summary()
Run on its own for testing:  python registry_mcp_server.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

import registry  # noqa: E402

server = MCPServer(
    name="krera-registry",
    instructions="Look up projects in the Karnataka RERA project register (official snapshot of 7 Nov 2026).",
)


@server.tool(description="Exact lookup of a Karnataka RERA registration number (or acknowledgement number). "
                         "Returns status, promoter, district, completion dates and extensions.")
def check_registration(registration_no: str) -> str:
    return json.dumps(registry.check_registration(registration_no), ensure_ascii=False)


@server.tool(description="Search the Karnataka RERA register by project name and/or promoter name, optionally "
                         "filtered by district or taluk. Similar names that are not exact are returned as DIFFERENT projects.")
def search_projects(project_name: str = "", promoter: str = "", district: str = "") -> str:
    return json.dumps(registry.search_projects(project_name, promoter, district), ensure_ascii=False)


@server.tool(description="Number of records in the register by status, and the data date.")
def register_summary() -> str:
    return json.dumps(registry.register_summary(), ensure_ascii=False)


if __name__ == "__main__":
    server.run("stdio")
