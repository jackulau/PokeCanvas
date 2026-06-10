"""Registers all Canvas tools on a FastMCP server.

Each tool:
  1. builds a CanvasClient from the incoming request (env creds or the
     Bearer/base-url headers Poke forwards),
  2. calls a pure function in canvas_api,
  3. returns either the projected data or a stable {"error", "status"} object.

Tool functions are thin on purpose — the real logic and its tests live in
canvas_api.py / canvas_client.py.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request

from . import canvas_api as api
from .canvas_client import CanvasClient, CanvasError, resolve_canvas_credentials
from .ratelimit import RateLimiter

Result = Any

# Per-user rate limit for shared (multi-tenant) deployments. In-memory/per-process.
_LIMITER = RateLimiter(max_requests=120, window_seconds=60.0)


def _rate_key(request) -> str:
    """Stable per-user rate-limit key. Prefers Poke's user id; falls back to a
    hash of the auth header so we never key on (or expose) the raw token."""
    uid = request.headers.get("x-poke-user-id")
    if uid:
        return f"user:{uid}"
    auth = request.headers.get("authorization", "") or ""
    return "tok:" + hashlib.sha256(auth.encode()).hexdigest()[:16]


def _build_client(request) -> CanvasClient:
    """Resolve credentials from the request headers + environment."""
    base, token = resolve_canvas_credentials(
        auth_header=request.headers.get("authorization"),
        base_url_header=request.headers.get("x-canvas-base-url"),
    )
    return CanvasClient(base, token)


async def _with_client(fn: Callable[[CanvasClient], Awaitable[Result]]) -> Result:
    request = get_http_request()
    if not _LIMITER.allow(_rate_key(request)):
        return {"error": "Rate limit exceeded. Please slow down and retry shortly.", "status": 429}
    try:
        client = _build_client(request)
    except CanvasError as e:
        return {"error": e.message, "status": e.status}
    try:
        return await fn(client)
    except CanvasError as e:
        return {"error": e.message, "status": e.status}
    except Exception as e:  # noqa: BLE001 - surface a clean error to the assistant
        return {"error": f"Unexpected error: {e}", "status": 500}


def register_tools(mcp: FastMCP) -> None:
    # ---- profile / courses -------------------------------------------------

    @mcp.tool(
        description="Get the signed-in Canvas user's profile (name, email, timezone). "
        "Use to confirm whose account is connected."
    )
    async def get_profile() -> Result:
        return await _with_client(api.fetch_profile)

    @mcp.tool(
        description="List the student's courses with current grade, term, and dates. "
        "By default only active courses; set include_concluded=true to also include past courses. "
        "Most other tools need a course_id from this list."
    )
    async def list_courses(include_concluded: bool = False, limit: int = 50) -> Result:
        return await _with_client(lambda c: api.fetch_courses(c, include_concluded, limit))

    # ---- to-dos / activity / upcoming -------------------------------------

    @mcp.tool(
        description="List the student's Canvas to-do items (things needing action soon, "
        "with due dates and points). Live data."
    )
    async def list_todos() -> Result:
        return await _with_client(api.fetch_todos)

    @mcp.tool(
        description="Get the recent activity stream — the live feed of what just changed in "
        "Canvas: new announcements, grade changes, submission comments, discussion replies. "
        "Use this to answer 'what's new / did anything change?'."
    )
    async def get_recent_activity(limit: int = 25) -> Result:
        return await _with_client(lambda c: api.fetch_recent_activity(c, limit))

    @mcp.tool(description="List upcoming events and assignment due dates across all courses, soonest first.")
    async def list_upcoming_events() -> Result:
        return await _with_client(api.fetch_upcoming)

    # ---- coursework -------------------------------------------------------

    @mcp.tool(
        description="List assignments for a course, including the student's submission status, "
        "score, grade, and whether it's late/missing. Requires course_id (from list_courses)."
    )
    async def list_assignments(course_id: int, limit: int = 50) -> Result:
        return await _with_client(lambda c: api.fetch_assignments(c, course_id, limit))

    @mcp.tool(
        description="List quizzes for a course (title, due date, points, question count, attempts). Requires course_id."
    )
    async def list_quizzes(course_id: int, limit: int = 50) -> Result:
        return await _with_client(lambda c: api.fetch_quizzes(c, course_id, limit))

    @mcp.tool(
        description="List calendar events. Optionally filter by course_id and an ISO date range "
        "(start_date / end_date, e.g. 2026-06-01). Returns events and dated items."
    )
    async def list_calendar_events(
        start_date: str | None = None,
        end_date: str | None = None,
        course_id: int | None = None,
        limit: int = 50,
    ) -> Result:
        return await _with_client(lambda c: api.fetch_calendar_events(c, start_date, end_date, course_id, limit))

    # ---- content ----------------------------------------------------------

    @mcp.tool(
        description="List announcements. Pass a course_id for one course, or omit it to fetch "
        "announcements across your active courses (up to 10; pass a course_id for the rest)."
    )
    async def list_announcements(course_id: int | None = None, limit: int = 50) -> Result:
        async def run(client: CanvasClient) -> Result:
            if course_id:
                ids = [course_id]
            else:
                courses = await api.fetch_courses(client)
                # Canvas caps the announcements endpoint at 10 context_codes.
                ids = [c["id"] for c in courses if c.get("id")][:10]
            return await api.fetch_announcements(client, ids, limit)

        return await _with_client(run)

    @mcp.tool(
        description="List discussion topics for a course (title, message preview, last reply time). Requires course_id."
    )
    async def list_discussions(course_id: int, limit: int = 50) -> Result:
        return await _with_client(lambda c: api.fetch_discussions(c, course_id, limit))

    @mcp.tool(
        description="List a course's modules and the items inside each (pages, assignments, files, "
        "links) with completion state. Requires course_id."
    )
    async def list_modules(course_id: int, limit: int = 50) -> Result:
        return await _with_client(lambda c: api.fetch_modules(c, course_id, limit))

    @mcp.tool(
        description="List a course's wiki pages (title, url slug, last updated), newest first. "
        "Requires course_id. Use get_page to read a page's content."
    )
    async def list_pages(course_id: int, limit: int = 50) -> Result:
        return await _with_client(lambda c: api.fetch_pages(c, course_id, limit))

    @mcp.tool(
        description="Read the content of a single course page. Requires course_id and the page's "
        "url slug (from list_pages)."
    )
    async def get_page(course_id: int, page_url: str) -> Result:
        return await _with_client(lambda c: api.fetch_page(c, course_id, page_url))

    @mcp.tool(
        description="List files in a course (name, type, size, download url, last updated), newest "
        "first. Requires course_id."
    )
    async def list_files(course_id: int, limit: int = 50) -> Result:
        return await _with_client(lambda c: api.fetch_files(c, course_id, limit))
