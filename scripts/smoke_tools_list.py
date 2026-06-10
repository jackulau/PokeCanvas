#!/usr/bin/env python3
"""Smoke test: import the server and assert every expected tool is registered
with a usable schema. Prints TOOLS_OK on success. No network required."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.server import mcp  # noqa: E402

EXPECTED = {
    "get_profile",
    "list_courses",
    "list_todos",
    "get_recent_activity",
    "list_upcoming_events",
    "list_assignments",
    "list_quizzes",
    "list_calendar_events",
    "list_announcements",
    "list_discussions",
    "list_modules",
    "list_pages",
    "get_page",
    "list_files",
}


async def main() -> int:
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    print("REGISTERED", len(names), "tools:", ", ".join(sorted(names)))
    missing = EXPECTED - names
    if missing:
        print("MISSING:", ", ".join(sorted(missing)))
        return 1
    # Every tool must expose a description and a valid JSON-schema for its params.
    # In FastMCP v3 the schema lives on `.parameters`; the MCP wire form
    # (`.inputSchema`) is produced by `to_mcp_tool()`.
    for t in tools:
        if not getattr(t, "description", None):
            print("NO DESCRIPTION:", t.name)
            return 1
        schema = getattr(t, "parameters", None)
        if not isinstance(schema, dict) or schema.get("type") != "object":
            print("BAD SCHEMA:", t.name, repr(schema))
            return 1
        # Confirm it also serializes to the MCP wire format Poke consumes.
        wire = t.to_mcp_tool()
        if getattr(wire, "inputSchema", None) is None:
            print("NO WIRE SCHEMA:", t.name)
            return 1
    print("TOOLS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
