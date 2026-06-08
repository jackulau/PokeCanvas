#!/usr/bin/env python3
"""Canvas LMS MCP server for Poke (The Interaction Company).

Run locally:   python src/server.py        (serves streamable HTTP at /mcp)
Render uses:   python src/server.py         (PORT injected by the platform)
"""
import os
import sys

# Make `import src.*` resolve whether launched as `python src/server.py`
# (script mode) or `python -m src.server` (module mode).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP  # noqa: E402

from src.tools import register_tools  # noqa: E402

mcp = FastMCP(
    "Canvas LMS",
    instructions=(
        "Read-only access to the student's Canvas LMS account: courses, assignments, "
        "files, pages, modules, announcements, discussions, quizzes, calendar events, "
        "and to-dos. All data is fetched live. Start with list_courses to get course_ids, "
        "then call resource tools with a course_id. Use get_recent_activity or list_todos "
        "to see what recently changed."
    ),
)
register_tools(mcp)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    print(f"Starting Canvas LMS MCP server on {host}:{port} (connect at /mcp)")
    mcp.run(transport="http", host=host, port=port, stateless_http=True)
