"""Optional boot-time confirmation ping to Poke.

If POKE_API_KEY is set, the server sends one message to the user's Poke on
startup via Poke's documented inbound message API, confirming the integration
is live and suggesting what to ask. This does NOT add the MCP integration
itself (Poke only supports that via its web UI or the `poke mcp add` CLI) — it's
a best-effort, non-fatal "you're connected" nudge.
"""
from __future__ import annotations

import os

import httpx

# Documented inbound message endpoint (Bearer auth with a key from
# poke.com/settings/advanced/api-keys/create).
POKE_INBOUND_API = "https://poke.com/api/v1/inbound/api-message"


async def announce_to_poke(
    mcp_url: str, *, api_key: str | None = None, timeout: float = 10.0
) -> bool:
    """Send a one-off confirmation message to Poke. Returns True on success,
    False if there's no key or the request fails (never raises)."""
    key = (api_key or os.environ.get("POKE_API_KEY") or "").strip()
    if not key:
        return False
    message = (
        f"✅ Your Canvas integration is live at {mcp_url} — ask me things like "
        '"what\'s due this week?", "did my grades change?", or "any new announcements?"'
    )
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                POKE_INBOUND_API,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={"message": message},
            )
            return resp.is_success
    except httpx.HTTPError:
        return False
