import httpx
import respx

from src import canvas_api as api
from src.canvas_client import CanvasClient

BASE = "https://canvas.test"


def client() -> CanvasClient:
    return CanvasClient(BASE, "tok")


@respx.mock
async def test_fetch_assignments_includes_submission():
    respx.get(f"{BASE}/api/v1/courses/101/assignments").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "Essay",
                    "due_at": "2026-06-15T23:59:00Z",
                    "points_possible": 100,
                    "html_url": "https://canvas.test/courses/101/assignments/1",
                    "submission": {
                        "score": 88,
                        "grade": "B+",
                        "workflow_state": "graded",
                        "submitted_at": "2026-06-14T10:00:00Z",
                        "late": False,
                        "missing": False,
                    },
                }
            ],
        )
    )
    items = await api.fetch_assignments(client(), 101)
    a = items[0]
    assert a["name"] == "Essay"
    assert a["submission"]["score"] == 88
    assert a["submission"]["workflow_state"] == "graded"
    assert a["submission"]["missing"] is False


@respx.mock
async def test_fetch_assignments_handles_no_submission():
    respx.get(f"{BASE}/api/v1/courses/101/assignments").mock(
        return_value=httpx.Response(
            200, json=[{"id": 2, "name": "Reading", "due_at": None, "points_possible": 0}]
        )
    )
    items = await api.fetch_assignments(client(), 101)
    assert items[0]["submission"] == {}


@respx.mock
async def test_fetch_quizzes():
    respx.get(f"{BASE}/api/v1/courses/101/quizzes").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 9,
                    "title": "Midterm",
                    "due_at": "2026-06-20T23:59:00Z",
                    "points_possible": 50,
                    "question_count": 25,
                    "quiz_type": "assignment",
                    "allowed_attempts": 1,
                    "html_url": "https://canvas.test/courses/101/quizzes/9",
                    "drop_me": "x",
                }
            ],
        )
    )
    items = await api.fetch_quizzes(client(), 101)
    q = items[0]
    assert q["title"] == "Midterm"
    assert q["question_count"] == 25
    assert "drop_me" not in q


@respx.mock
async def test_fetch_calendar_events_with_filters():
    route = respx.get(f"{BASE}/api/v1/calendar_events").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 3,
                    "title": "Lecture",
                    "start_at": "2026-06-09T14:00:00Z",
                    "end_at": "2026-06-09T15:00:00Z",
                    "type": "event",
                    "context_code": "course_101",
                    "html_url": "https://canvas.test/calendar?event_id=3",
                }
            ],
        )
    )
    items = await api.fetch_calendar_events(
        client(), start_date="2026-06-01", end_date="2026-06-30", course_id=101
    )
    assert items[0]["title"] == "Lecture"
    assert items[0]["context_code"] == "course_101"
    # Verify the filters were actually sent to Canvas.
    sent = route.calls.last.request.url
    assert "start_date=2026-06-01" in str(sent)
    assert "context_codes%5B%5D=course_101" in str(sent) or "context_codes[]=course_101" in str(sent)
