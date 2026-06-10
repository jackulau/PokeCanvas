import httpx
import respx

from src import canvas_api as api
from src.canvas_client import CanvasClient

BASE = "https://canvas.test"


def client() -> CanvasClient:
    return CanvasClient(BASE, "tok")


@respx.mock
async def test_fetch_announcements_strips_html_and_requires_ids():
    assert await api.fetch_announcements(client(), []) == []
    route = respx.get(f"{BASE}/api/v1/announcements").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "title": "Exam moved",
                    "message": "<div>Now <strong>Friday</strong></div>",
                    "posted_at": "2026-06-05T00:00:00Z",
                    "context_code": "course_101",
                    "html_url": "https://canvas.test/a/1",
                }
            ],
        )
    )
    items = await api.fetch_announcements(client(), [101, 102])
    assert items[0]["message"] == "Now Friday"
    sent = str(route.calls.last.request.url)
    assert "course_101" in sent and "course_102" in sent


@respx.mock
async def test_fetch_discussions():
    respx.get(f"{BASE}/api/v1/courses/101/discussion_topics").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 4,
                    "title": "Project ideas",
                    "message": "<p>Post here</p>",
                    "posted_at": "2026-06-01T00:00:00Z",
                    "last_reply_at": "2026-06-07T00:00:00Z",
                    "discussion_type": "threaded",
                    "html_url": "https://canvas.test/d/4",
                }
            ],
        )
    )
    items = await api.fetch_discussions(client(), 101)
    assert items[0]["title"] == "Project ideas"
    assert items[0]["message"] == "Post here"
    assert items[0]["last_reply_at"] == "2026-06-07T00:00:00Z"


@respx.mock
async def test_fetch_modules_with_items():
    respx.get(f"{BASE}/api/v1/courses/101/modules").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 10,
                    "name": "Week 1",
                    "position": 1,
                    "state": "started",
                    "items": [
                        {"id": 100, "title": "Syllabus", "type": "Page", "html_url": "u1"},
                        {"id": 101, "title": "HW1", "type": "Assignment", "html_url": "u2", "content_id": 1},
                    ],
                }
            ],
        )
    )
    items = await api.fetch_modules(client(), 101)
    m = items[0]
    assert m["name"] == "Week 1"
    assert len(m["items"]) == 2
    assert m["items"][1]["type"] == "Assignment"


@respx.mock
async def test_fetch_pages_and_page_body():
    respx.get(f"{BASE}/api/v1/courses/101/pages").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "page_id": 1,
                    "url": "syllabus",
                    "title": "Syllabus",
                    "updated_at": "2026-06-01T00:00:00Z",
                    "published": True,
                }
            ],
        )
    )
    pages = await api.fetch_pages(client(), 101)
    assert pages[0]["url"] == "syllabus"

    respx.get(f"{BASE}/api/v1/courses/101/pages/syllabus").mock(
        return_value=httpx.Response(
            200,
            json={"page_id": 1, "url": "syllabus", "title": "Syllabus", "body": "<h1>Welcome</h1><p>Read this.</p>"},
        )
    )
    page = await api.fetch_page(client(), 101, "syllabus")
    assert page["title"] == "Syllabus"
    assert page["body"] == "Welcome Read this."


@respx.mock
async def test_fetch_files():
    respx.get(f"{BASE}/api/v1/courses/101/files").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 50,
                    "display_name": "Lecture1.pdf",
                    "filename": "lecture1.pdf",
                    "content-type": "application/pdf",
                    "size": 12345,
                    "url": "https://canvas.test/files/50/download",
                    "updated_at": "2026-06-03T00:00:00Z",
                    "folder_id": 7,
                }
            ],
        )
    )
    files = await api.fetch_files(client(), 101)
    f = files[0]
    assert f["display_name"] == "Lecture1.pdf"
    assert f["content-type"] == "application/pdf"
    assert f["size"] == 12345
