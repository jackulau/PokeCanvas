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
from starlette.requests import Request  # noqa: E402
from starlette.responses import HTMLResponse, JSONResponse  # noqa: E402

from src.landing import render_landing  # noqa: E402
from src.tools import register_tools  # noqa: E402


def public_base_url(request: Request | None = None) -> str:
    """Best guess at this server's public origin (no trailing slash).

    Prefers an explicit env URL set by the host (Render/Heroku/Fly/etc.), then
    falls back to the proxy's forwarded Host headers, then localhost.
    """
    for key in ("PUBLIC_URL", "RENDER_EXTERNAL_URL"):
        val = os.environ.get(key)
        if val:
            return val.rstrip("/")
    if request is not None:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host:
            proto = request.headers.get("x-forwarded-proto") or (
                "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
            )
            return f"{proto}://{host}"
    port = os.environ.get("PORT", "8000")
    return f"http://localhost:{port}"


def _creds_configured() -> bool:
    return bool(os.environ.get("CANVAS_BASE_URL") and os.environ.get("CANVAS_API_TOKEN"))


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


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "canvas-poke-mcp"})


@mcp.custom_route("/", methods=["GET"])
async def landing(request: Request) -> HTMLResponse:
    mcp_url = f"{public_base_url(request)}/mcp"
    return HTMLResponse(render_landing(mcp_url, _creds_configured()))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    mcp_url = f"{public_base_url(None)}/mcp"
    print(f"Starting Canvas LMS MCP server on {host}:{port} (connect at {mcp_url})")

    # Optional: confirm to Poke that we're live (no-op unless POKE_API_KEY is set).
    if os.environ.get("POKE_API_KEY"):
        try:
            import asyncio

            from src.poke_announce import announce_to_poke

            sent = asyncio.run(announce_to_poke(mcp_url))
            print(f"Poke boot ping: {'sent' if sent else 'skipped/failed'}")
        except Exception as e:  # noqa: BLE001 - boot ping must never block startup
            print(f"Poke boot ping error (non-fatal): {e}")

    mcp.run(transport="http", host=host, port=port, stateless_http=True)
