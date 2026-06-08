import httpx
import pytest
import respx

from src.canvas_client import (
    CanvasClient,
    CanvasError,
    _parse_next_link,
    normalize_base_url,
    resolve_canvas_credentials,
)

# ---- credential resolution -------------------------------------------------


def test_resolve_from_env():
    env = {"CANVAS_BASE_URL": "https://canvas.school.edu", "CANVAS_API_TOKEN": "tok123"}
    base, token = resolve_canvas_credentials(env=env)
    assert base == "https://canvas.school.edu"
    assert token == "tok123"


def test_bearer_overrides_env_token():
    env = {"CANVAS_BASE_URL": "https://canvas.school.edu", "CANVAS_API_TOKEN": "envtok"}
    base, token = resolve_canvas_credentials(auth_header="Bearer reqtok", env=env)
    assert token == "reqtok"
    assert base == "https://canvas.school.edu"


def test_raw_token_without_bearer_prefix():
    env = {"CANVAS_BASE_URL": "https://canvas.school.edu"}
    base, token = resolve_canvas_credentials(auth_header="just-a-token", env=env)
    assert token == "just-a-token"


def test_composite_base_and_token_in_bearer():
    base, token = resolve_canvas_credentials(
        auth_header="Bearer https://canvas.uni.edu::abc999", env={}
    )
    assert base == "https://canvas.uni.edu"
    assert token == "abc999"


def test_base_url_header_used():
    env = {"CANVAS_API_TOKEN": "tok"}
    base, _ = resolve_canvas_credentials(base_url_header="canvas.headers.edu", env=env)
    assert base == "https://canvas.headers.edu"


def test_missing_token_raises():
    with pytest.raises(CanvasError) as exc:
        resolve_canvas_credentials(env={"CANVAS_BASE_URL": "https://x.edu"})
    assert exc.value.status == 401


def test_missing_base_raises():
    with pytest.raises(CanvasError) as exc:
        resolve_canvas_credentials(env={"CANVAS_API_TOKEN": "tok"})
    assert exc.value.status == 401


# ---- base url normalization ------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://canvas.edu/", "https://canvas.edu"),
        ("canvas.edu", "https://canvas.edu"),
        ("https://canvas.edu/api/v1", "https://canvas.edu"),
        ("https://canvas.edu/api/v1/", "https://canvas.edu"),
        ("HTTP://canvas.edu", "HTTP://canvas.edu"),
    ],
)
def test_normalize_base_url(raw, expected):
    assert normalize_base_url(raw) == expected


def test_normalize_empty_raises():
    with pytest.raises(CanvasError):
        normalize_base_url("")


# ---- link header parsing ---------------------------------------------------


def test_parse_next_link():
    header = (
        '<https://c.edu/api/v1/courses?page=1>; rel="current", '
        '<https://c.edu/api/v1/courses?page=2>; rel="next", '
        '<https://c.edu/api/v1/courses?page=5>; rel="last"'
    )
    assert _parse_next_link(header) == "https://c.edu/api/v1/courses?page=2"


def test_parse_next_link_none():
    assert _parse_next_link(None) is None
    assert _parse_next_link('<https://c.edu>; rel="last"') is None


# ---- client GET ------------------------------------------------------------


@respx.mock
async def test_get_returns_json():
    respx.get("https://canvas.test/api/v1/users/self").mock(
        return_value=httpx.Response(200, json={"id": 1, "name": "Ada"})
    )
    client = CanvasClient("https://canvas.test", "tok")
    data = await client.get("users/self")
    assert data["name"] == "Ada"


@respx.mock
async def test_get_sends_bearer_header():
    route = respx.get("https://canvas.test/api/v1/users/self").mock(
        return_value=httpx.Response(200, json={"id": 1})
    )
    client = CanvasClient("https://canvas.test", "secret-tok")
    await client.get("users/self")
    assert route.calls.last.request.headers["Authorization"] == "Bearer secret-tok"


@respx.mock
async def test_get_401_raises_canvas_error():
    respx.get("https://canvas.test/api/v1/users/self").mock(
        return_value=httpx.Response(401, text="unauthorized")
    )
    client = CanvasClient("https://canvas.test", "bad")
    with pytest.raises(CanvasError) as exc:
        await client.get("users/self")
    assert exc.value.status == 401


# ---- client pagination -----------------------------------------------------


@respx.mock
async def test_get_list_follows_next_link():
    calls = {"n": 0}

    def responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json=[{"id": 1}, {"id": 2}],
                headers={"Link": '<https://canvas.test/api/v1/courses?page=2&per_page=100>; rel="next"'},
            )
        return httpx.Response(200, json=[{"id": 3}])

    respx.route(method="GET", host="canvas.test").mock(side_effect=responder)
    client = CanvasClient("https://canvas.test", "tok")
    items = await client.get_list("courses")
    assert [i["id"] for i in items] == [1, 2, 3]
    assert calls["n"] == 2


@respx.mock
async def test_get_list_respects_max_items():
    def responder(request):
        # Always offer a next page; the cap must stop the loop.
        return httpx.Response(
            200,
            json=[{"id": 1}, {"id": 2}],
            headers={"Link": '<https://canvas.test/api/v1/courses?page=99>; rel="next"'},
        )

    respx.route(method="GET", host="canvas.test").mock(side_effect=responder)
    client = CanvasClient("https://canvas.test", "tok")
    items = await client.get_list("courses", max_items=3)
    assert len(items) == 3


@respx.mock
async def test_get_list_unwraps_dict_payload():
    respx.route(method="GET", host="canvas.test").mock(
        return_value=httpx.Response(200, json={"events": [{"id": 7}, {"id": 8}]})
    )
    client = CanvasClient("https://canvas.test", "tok")
    items = await client.get_list("calendar_events")
    assert [i["id"] for i in items] == [7, 8]
