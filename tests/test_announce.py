import httpx
import respx

from src.poke_announce import POKE_INBOUND_API, announce_to_poke


@respx.mock
async def test_announce_posts_with_bearer_and_url():
    route = respx.post(POKE_INBOUND_API).mock(return_value=httpx.Response(200, json={"ok": True}))
    ok = await announce_to_poke("https://svc.onrender.com/mcp", api_key="pk_test_123")
    assert ok is True
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer pk_test_123"
    assert b"svc.onrender.com/mcp" in req.content


async def test_announce_noop_without_key(monkeypatch):
    monkeypatch.delenv("POKE_API_KEY", raising=False)
    # No respx mock registered: if it tried to POST, it would error — proving it didn't.
    ok = await announce_to_poke("https://svc.onrender.com/mcp")
    assert ok is False


@respx.mock
async def test_announce_returns_false_on_http_error():
    respx.post(POKE_INBOUND_API).mock(return_value=httpx.Response(500))
    ok = await announce_to_poke("https://svc.onrender.com/mcp", api_key="pk_test_123")
    assert ok is False
