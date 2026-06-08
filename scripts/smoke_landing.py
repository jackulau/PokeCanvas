#!/usr/bin/env python3
"""Hit the landing page and health route of a RUNNING server. Prints LANDING_OK.

Usage: python scripts/smoke_landing.py http://127.0.0.1:8765
"""
import sys

import httpx


def main(base: str) -> int:
    base = base.rstrip("/")
    root = httpx.get(base + "/", timeout=10)
    if root.status_code != 200:
        print("landing status", root.status_code)
        return 1
    if "mcp add" not in root.text or "/mcp" not in root.text:
        print("landing missing connect command / url")
        return 1
    health = httpx.get(base + "/health", timeout=10)
    if health.status_code != 200 or "ok" not in health.text:
        print("health failed", health.status_code, health.text[:120])
        return 1
    print("LANDING_OK")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
    raise SystemExit(main(target))
