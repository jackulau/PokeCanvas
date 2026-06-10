"""Canvas data layer: pure async functions over a CanvasClient.

Each function maps one student-facing concept (courses, assignments, ...) to the
right Canvas REST endpoint(s) and projects the response down to the fields a
chat assistant actually needs. Keeping these free of any request/HTTP-context
coupling makes them unit-testable with a mocked client.

All data is fetched live on every call, so results always reflect the current
state of Canvas (new assignments, changed grades, fresh announcements, ...).
"""

from __future__ import annotations

import re
from typing import Any

from .canvas_client import CanvasClient

DEFAULT_LIST_LIMIT = 50
ACTIVITY_LIMIT = 25
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _pick(obj: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {k: obj.get(k) for k in keys if k in obj}


def _strip_html(text: str | None, limit: int = 600) -> str | None:
    if not text:
        return text
    plain = _WS_RE.sub(" ", _TAG_RE.sub(" ", text)).strip()
    return plain if len(plain) <= limit else plain[:limit].rstrip() + "…"


def _course_grade(course: dict[str, Any]) -> dict[str, Any]:
    """Extract the student's current grade from an include[]=total_scores course."""
    for enr in course.get("enrollments") or []:
        if enr.get("type") in (None, "student", "StudentEnrollment"):
            g = _pick(enr, ["computed_current_score", "computed_current_grade"])
            if g:
                return {
                    "current_score": g.get("computed_current_score"),
                    "current_grade": g.get("computed_current_grade"),
                }
    return {}


# ---- profile / courses -----------------------------------------------------


async def fetch_profile(client: CanvasClient) -> dict[str, Any]:
    p = await client.get("users/self/profile")
    return _pick(p, ["id", "name", "short_name", "primary_email", "login_id", "time_zone", "bio"])


async def fetch_courses(
    client: CanvasClient, include_concluded: bool = False, limit: int = DEFAULT_LIST_LIMIT
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"include[]": ["term", "total_scores"]}
    if not include_concluded:
        params["enrollment_state"] = "active"
    raw = await client.get_list("courses", params, max_items=limit)
    out = []
    for c in raw:
        if not isinstance(c, dict) or c.get("access_restricted_by_date"):
            continue
        item = _pick(c, ["id", "name", "course_code", "workflow_state", "start_at", "end_at"])
        item["term"] = (c.get("term") or {}).get("name")
        item.update(_course_grade(c))
        out.append(item)
    return out


# ---- to-dos / activity / upcoming (the "what changed" surface) -------------


async def fetch_todos(client: CanvasClient) -> list[dict[str, Any]]:
    raw = await client.get_list("users/self/todo")
    out = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        a = t.get("assignment") or {}
        out.append(
            {
                "type": t.get("type"),
                "title": a.get("name") or t.get("title"),
                "course_id": t.get("course_id") or a.get("course_id"),
                "due_at": a.get("due_at"),
                "points_possible": a.get("points_possible"),
                "html_url": t.get("html_url") or a.get("html_url"),
            }
        )
    return out


async def fetch_recent_activity(client: CanvasClient, limit: int = ACTIVITY_LIMIT) -> list[dict[str, Any]]:
    """Canvas activity stream — the live feed of what recently changed:
    new announcements, submission comments, grade changes, discussion replies."""
    raw = await client.get_list("users/self/activity_stream", {"only_active_courses": "true"}, max_items=limit)
    out = []
    for a in raw:
        if not isinstance(a, dict):
            continue
        out.append(
            {
                "type": a.get("type"),
                "title": a.get("title"),
                "message": _strip_html(a.get("message"), 300),
                "course_id": a.get("course_id"),
                "created_at": a.get("created_at"),
                "updated_at": a.get("updated_at"),
                "html_url": a.get("html_url"),
            }
        )
    return out


async def fetch_upcoming(client: CanvasClient) -> list[dict[str, Any]]:
    raw = await client.get_list("users/self/upcoming_events")
    out = []
    for e in raw:
        if not isinstance(e, dict):
            continue
        a = e.get("assignment") or {}
        out.append(
            {
                "type": e.get("type"),
                "title": e.get("title"),
                "start_at": e.get("start_at"),
                "due_at": a.get("due_at"),
                "course_id": e.get("course_id") or a.get("course_id"),
                "html_url": e.get("html_url"),
            }
        )
    return out


# ---- coursework: assignments / quizzes / calendar --------------------------


async def fetch_assignments(
    client: CanvasClient, course_id: int, limit: int = DEFAULT_LIST_LIMIT
) -> list[dict[str, Any]]:
    raw = await client.get_list(
        f"courses/{course_id}/assignments",
        {"include[]": ["submission"], "order_by": "due_at"},
        max_items=limit,
    )
    out = []
    for a in raw:
        if not isinstance(a, dict):
            continue
        item = _pick(a, ["id", "name", "due_at", "points_possible", "html_url", "locked_for_user"])
        sub = a.get("submission") or {}
        item["submission"] = _pick(
            sub, ["score", "grade", "workflow_state", "submitted_at", "late", "missing", "excused"]
        )
        out.append(item)
    return out


async def fetch_quizzes(client: CanvasClient, course_id: int, limit: int = DEFAULT_LIST_LIMIT) -> list[dict[str, Any]]:
    raw = await client.get_list(f"courses/{course_id}/quizzes", max_items=limit)
    return [
        _pick(
            q,
            [
                "id",
                "title",
                "due_at",
                "points_possible",
                "question_count",
                "quiz_type",
                "time_limit",
                "allowed_attempts",
                "html_url",
            ],
        )
        for q in raw
        if isinstance(q, dict)
    ]


async def fetch_calendar_events(
    client: CanvasClient,
    start_date: str | None = None,
    end_date: str | None = None,
    course_id: int | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if course_id:
        params["context_codes[]"] = [f"course_{course_id}"]
    raw = await client.get_list("calendar_events", params, max_items=limit)
    return [
        _pick(e, ["id", "title", "start_at", "end_at", "type", "context_code", "html_url"])
        for e in raw
        if isinstance(e, dict)
    ]


# ---- content: announcements / discussions / modules / pages / files --------


async def fetch_announcements(
    client: CanvasClient, course_ids: list[int], limit: int = DEFAULT_LIST_LIMIT
) -> list[dict[str, Any]]:
    if not course_ids:
        return []
    params = {"context_codes[]": [f"course_{cid}" for cid in course_ids]}
    raw = await client.get_list("announcements", params, max_items=limit)
    out = []
    for a in raw:
        if not isinstance(a, dict):
            continue
        item = _pick(a, ["id", "title", "posted_at", "html_url", "context_code"])
        item["message"] = _strip_html(a.get("message"))
        out.append(item)
    return out


async def fetch_discussions(
    client: CanvasClient, course_id: int, limit: int = DEFAULT_LIST_LIMIT
) -> list[dict[str, Any]]:
    raw = await client.get_list(f"courses/{course_id}/discussion_topics", max_items=limit)
    out = []
    for d in raw:
        if not isinstance(d, dict):
            continue
        item = _pick(d, ["id", "title", "posted_at", "last_reply_at", "discussion_type", "html_url"])
        item["message"] = _strip_html(d.get("message"))
        out.append(item)
    return out


async def fetch_modules(client: CanvasClient, course_id: int, limit: int = DEFAULT_LIST_LIMIT) -> list[dict[str, Any]]:
    raw = await client.get_list(f"courses/{course_id}/modules", {"include[]": ["items"]}, max_items=limit)
    out = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        item = _pick(m, ["id", "name", "position", "state", "unlock_at"])
        item["items"] = [
            _pick(it, ["id", "title", "type", "html_url", "content_id"])
            for it in (m.get("items") or [])
            if isinstance(it, dict)
        ]
        out.append(item)
    return out


async def fetch_pages(client: CanvasClient, course_id: int, limit: int = DEFAULT_LIST_LIMIT) -> list[dict[str, Any]]:
    raw = await client.get_list(f"courses/{course_id}/pages", {"sort": "updated_at", "order": "desc"}, max_items=limit)
    return [
        _pick(p, ["page_id", "url", "title", "updated_at", "published", "front_page"])
        for p in raw
        if isinstance(p, dict)
    ]


async def fetch_page(client: CanvasClient, course_id: int, page_url: str) -> dict[str, Any]:
    p = await client.get(f"courses/{course_id}/pages/{page_url}")
    item = _pick(p, ["page_id", "url", "title", "updated_at", "published", "front_page"])
    item["body"] = _strip_html(p.get("body"), 4000)
    return item


async def fetch_files(client: CanvasClient, course_id: int, limit: int = DEFAULT_LIST_LIMIT) -> list[dict[str, Any]]:
    raw = await client.get_list(f"courses/{course_id}/files", {"sort": "updated_at", "order": "desc"}, max_items=limit)
    return [
        _pick(
            f,
            ["id", "display_name", "filename", "content-type", "size", "url", "updated_at", "folder_id"],
        )
        for f in raw
        if isinstance(f, dict)
    ]
