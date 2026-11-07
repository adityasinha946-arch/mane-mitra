"""MCP server: "krera-registry".

A real Model Context Protocol server. The chatbot app starts it as a separate
process and talks to it over standard input/output, the same way MCP clients
such as Claude Desktop connect to MCP servers. Tools exposed:
  - check_registration(registration_no)
  - search_projects(project_name, promoter, district)
  - register_summary()
  - complaint_history(project_name, promoter, registration_no)
  - complaints_summary()
Run on its own for testing:  python registry_mcp_server.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

import complaints  # noqa: E402
import registry  # noqa: E402

server = MCPServer(
    name="krera-registry",
    instructions="Look up projects in the Karnataka RERA project register, and complaint and recovery records, "
                 "from the official K-RERA website (snapshot of 7 Nov 2026).",
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


@server.tool(description="K-RERA complaint counts for a project and its promoter, revenue recovery certificates "
                         "(money ordered but not paid) and the complaint realization list. Give a registration number "
                         "or a project and/or promoter name. Counts are allegations, not findings.")
def complaint_history(project_name: str = "", promoter: str = "", registration_no: str = "") -> str:
    return json.dumps(complaints.complaint_history(project_name, promoter, registration_no), ensure_ascii=False)


@server.tool(description="Totals of the K-RERA complaint and recovery data, and the data date.")
def complaints_summary() -> str:
    return json.dumps(complaints.complaints_summary(), ensure_ascii=False)


if __name__ == "__main__":
    server.run("stdio")
