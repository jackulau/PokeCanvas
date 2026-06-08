from src.landing import render_landing
from src.server import _creds_configured, public_base_url


def test_render_landing_shows_url_and_connect_command():
    h = render_landing("https://svc.onrender.com/mcp", creds_ok=True)
    assert "https://svc.onrender.com/mcp" in h
    assert "npx poke@latest mcp add" in h
    assert "mcp add" in h
    assert "✅" in h


def test_render_landing_warns_without_creds():
    h = render_landing("https://svc.onrender.com/mcp", creds_ok=False)
    assert "CANVAS_API_TOKEN" in h
    assert "⚠️" in h


def test_public_base_prefers_render_env(monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://svc.onrender.com/")
    assert public_base_url(None) == "https://svc.onrender.com"


def test_public_base_public_url_overrides(monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://custom.example.com")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://svc.onrender.com")
    assert public_base_url(None) == "https://custom.example.com"


def test_public_base_falls_back_to_localhost(monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.setenv("PORT", "8000")
    assert public_base_url(None) == "http://localhost:8000"


def test_creds_configured(monkeypatch):
    monkeypatch.setenv("CANVAS_BASE_URL", "https://canvas.edu")
    monkeypatch.setenv("CANVAS_API_TOKEN", "tok")
    assert _creds_configured() is True
    monkeypatch.delenv("CANVAS_API_TOKEN", raising=False)
    assert _creds_configured() is False
