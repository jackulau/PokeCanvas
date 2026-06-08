import httpx
import respx

from src import canvas_api as api
from src.canvas_client import CanvasClient

BASE = "https://canvas.test"


def client() -> CanvasClient:
    return CanvasClient(BASE, "tok")


@respx.mock
async def test_fetch_profile():
    respx.get(f"{BASE}/api/v1/users/self/profile").mock(
        return_value=httpx.Response(
            200, json={"id": 5, "name": "Ada Lovelace", "primary_email": "ada@x.edu", "extra": "drop"}
        )
    )
    p = await api.fetch_profile(client())
    assert p["name"] == "Ada Lovelace"
    assert p["primary_email"] == "ada@x.edu"
    assert "extra" not in p


@respx.mock
async def test_fetch_courses_projects_grade_term_and_filters_restricted():
    respx.get(f"{BASE}/api/v1/courses").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 101,
                    "name": "Intro to CS",
                    "course_code": "CS101",
                    "term": {"name": "Fall 2026"},
                    "enrollments": [
                        {
                            "type": "student",
                            "computed_current_score": 91.5,
                            "computed_current_grade": "A-",
                        }
                    ],
                },
                {"id": 999, "access_restricted_by_date": True},
            ],
        )
    )
    courses = await api.fetch_courses(client())
    assert len(courses) == 1
    c = courses[0]
    assert c["id"] == 101
    assert c["term"] == "Fall 2026"
    assert c["current_score"] == 91.5
    assert c["current_grade"] == "A-"


@respx.mock
async def test_fetch_todos():
    respx.get(f"{BASE}/api/v1/users/self/todo").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "type": "submitting",
                    "course_id": 101,
                    "html_url": "https://canvas.test/courses/101/assignments/1",
                    "assignment": {
                        "name": "Homework 1",
                        "due_at": "2026-06-10T23:59:00Z",
                        "points_possible": 10,
                    },
                }
            ],
        )
    )
    todos = await api.fetch_todos(client())
    assert todos[0]["title"] == "Homework 1"
    assert todos[0]["course_id"] == 101
    assert todos[0]["due_at"] == "2026-06-10T23:59:00Z"


@respx.mock
async def test_fetch_recent_activity_strips_html():
    respx.get(f"{BASE}/api/v1/users/self/activity_stream").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "type": "DiscussionTopic",
                    "title": "Welcome",
                    "message": "<p>Hello <b>class</b>!</p>",
                    "course_id": 101,
                    "created_at": "2026-06-01T00:00:00Z",
                    "updated_at": "2026-06-02T00:00:00Z",
                    "html_url": "https://canvas.test/x",
                }
            ],
        )
    )
    acts = await api.fetch_recent_activity(client())
    assert acts[0]["message"] == "Hello class !"
    assert acts[0]["type"] == "DiscussionTopic"
    assert acts[0]["updated_at"] == "2026-06-02T00:00:00Z"


@respx.mock
async def test_fetch_upcoming():
    respx.get(f"{BASE}/api/v1/users/self/upcoming_events").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "type": "assignment",
                    "title": "Quiz 2",
                    "html_url": "https://canvas.test/q2",
                    "assignment": {"due_at": "2026-06-12T23:59:00Z", "course_id": 101},
                }
            ],
        )
    )
    up = await api.fetch_upcoming(client())
    assert up[0]["title"] == "Quiz 2"
    assert up[0]["due_at"] == "2026-06-12T23:59:00Z"
    assert up[0]["course_id"] == 101
