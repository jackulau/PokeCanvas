#!/usr/bin/env python3
"""Drive the running server over real HTTP using the MCP streamable-HTTP wire
protocol (initialize -> tools/list -> tools/call), the same sequence Poke runs.
Verifies tools are discoverable and a credential-less call returns a clean error.
Prints LIVE_OK on success.

Usage: python scripts/live_http_test.py http://127.0.0.1:8765/mcp
"""
import asyncio
import json
import sys

import httpx

HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
EXPECTED_MIN = 14


def parse_sse(text: str) -> dict:
    """Pull the JSON payload out of an SSE 'data:' line (or plain JSON)."""
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return json.loads(text)


async def rpc(client, url, method, params=None, sid=None, id_=None):
    headers = dict(HEADERS)
    if sid:
        headers["mcp-session-id"] = sid
    body = {"jsonrpc": "2.0", "method": method}
    if id_ is not None:
        body["id"] = id_
    if params is not None:
        body["params"] = params
    return await client.post(url, headers=headers, json=body)


async def main(url: str) -> int:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        # 1. initialize
        r = await rpc(
            client, url, "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {},
             "clientInfo": {"name": "livetest", "version": "1"}}, id_=1,
        )
        if r.status_code != 200:
            print("initialize failed", r.status_code, r.text[:300])
            return 1
        sid = r.headers.get("mcp-session-id")
        init = parse_sse(r.text)
        server_name = init["result"]["serverInfo"]["name"]
        print("initialized; server:", server_name, "| session:", "yes" if sid else "stateless")

        # 2. initialized notification
        await rpc(client, url, "notifications/initialized", sid=sid)

        # 3. tools/list
        r = await rpc(client, url, "tools/list", {}, sid=sid, id_=2)
        tools = parse_sse(r.text)["result"]["tools"]
        names = sorted(t["name"] for t in tools)
        print(f"tools/list -> {len(names)}:", ", ".join(names))
        if len(names) < EXPECTED_MIN:
            print(f"FAIL: expected >= {EXPECTED_MIN} tools")
            return 1

        # 4. tools/call without credentials -> clean 401 error, not a crash
        r = await rpc(
            client, url, "tools/call",
            {"name": "list_courses", "arguments": {}}, sid=sid, id_=3,
        )
        payload = json.dumps(parse_sse(r.text))
        print("list_courses (no creds) ->", payload[:200])
        if '"isError": true' not in payload and "401" not in payload and "token" not in payload.lower():
            print("FAIL: expected a credential error from credential-less call")
            return 1

    print("LIVE_OK")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"
    raise SystemExit(asyncio.run(main(target)))
