"""Thin async client for the Canvas LMS REST API.

Responsibilities kept deliberately small and testable:
  * resolve_canvas_credentials() — figure out (base_url, token) from env and/or
    per-request headers, with a clear error when neither is available.
  * CanvasClient — GET + transparent Link-header pagination, errors normalized
    into CanvasError so tools can render a stable {"error", "status"} shape.

No global state: a fresh client is built per request so the server stays
stateless (required by Poke's stateless_http transport).
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

import httpx

API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT = 20.0
DEFAULT_PER_PAGE = 100
# Safety cap so a runaway course (thousands of files) can't blow up a response.
DEFAULT_MAX_ITEMS = 200
DEFAULT_MAX_PAGES = 25

_NEXT_LINK_RE = re.compile(r'<([^>]+)>\s*;\s*rel="next"')


class CanvasError(Exception):
    """Canvas API / configuration error with an HTTP-ish status code."""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")


def normalize_base_url(raw: str) -> str:
    """Turn whatever the user typed into a clean origin (no trailing slash, no
    /api/v1 suffix, https scheme assumed when omitted)."""
    url = (raw or "").strip()
    if not url:
        raise CanvasError(401, "Canvas base URL is empty.")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    url = url.rstrip("/")
    # Tolerate users pasting the full API root.
    if url.lower().endswith(API_PREFIX):
        url = url[: -len(API_PREFIX)]
    return url.rstrip("/")


def resolve_canvas_credentials(
    *,
    auth_header: str | None = None,
    base_url_header: str | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve (base_url, token) for a request.

    Precedence (highest first):
      token     : Bearer token from Authorization header  ->  env CANVAS_API_TOKEN
      base_url  : "base::token" composite in the Bearer    ->  X-Canvas-Base-Url
                  header                                    ->  env CANVAS_BASE_URL

    The composite "https://canvas.school.edu::TOKEN" lets a shared (recipe)
    deployment serve many institutions through Poke's single API-key field.
    """
    env = env if env is not None else os.environ

    bearer = ""
    if auth_header:
        h = auth_header.strip()
        if h.lower().startswith("bearer "):
            bearer = h[7:].strip()
        else:
            bearer = h  # tolerate a raw token without the prefix

    composite_base = ""
    token = ""
    if bearer:
        if "::" in bearer:
            composite_base, token = bearer.split("::", 1)
            composite_base = composite_base.strip()
            token = token.strip()
        else:
            token = bearer
    if not token:
        token = (env.get("CANVAS_API_TOKEN") or "").strip()

    raw_base = composite_base or (base_url_header or "").strip() or (env.get("CANVAS_BASE_URL") or "").strip()

    if not token:
        raise CanvasError(
            401,
            "No Canvas access token. Set CANVAS_API_TOKEN on the server, or pass "
            "it to Poke as the integration API key (Authorization: Bearer <token>).",
        )
    if not raw_base:
        raise CanvasError(
            401,
            "No Canvas base URL. Set CANVAS_BASE_URL on the server (e.g. https://canvas.university.edu).",
        )

    base = normalize_base_url(raw_base)
    # SSRF guard — base URL is caller-supplied on multi-tenant deployments.
    from . import security

    security.assert_safe_canvas_url(base)
    return base, token


def _parse_next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    m = _NEXT_LINK_RE.search(link_header)
    return m.group(1) if m else None


class CanvasClient:
    """Minimal async Canvas REST client. One instance per request."""

    def __init__(self, base_url: str, token: str, *, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        if path.startswith("api/"):
            return f"{self.base_url}/{path}"
        return f"{self.base_url}{API_PREFIX}/{path}"

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.is_success:
            return
        if resp.status_code == 401:
            raise CanvasError(401, "Canvas rejected the access token (401). It may be invalid or expired.")
        if resp.status_code == 403:
            raise CanvasError(403, "Canvas denied access (403). The token may lack scope for this resource.")
        if resp.status_code == 404:
            raise CanvasError(404, "Canvas resource not found (404). Check the id/course.")
        # Surface a short body snippet for everything else.
        snippet = (resp.text or "")[:200]
        raise CanvasError(resp.status_code, f"Canvas API error {resp.status_code}: {snippet}")

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a single resource (or one page) and return parsed JSON."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(self._url(path), params=params, headers=self._headers)
                self._raise_for_status(resp)
                return resp.json()
        except CanvasError:
            raise
        except httpx.TimeoutException as e:
            raise CanvasError(504, f"Canvas request timed out: {e}") from e
        except httpx.HTTPError as e:
            raise CanvasError(502, f"Could not reach Canvas: {e}") from e

    async def get_list(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_items: int = DEFAULT_MAX_ITEMS,
        max_pages: int = DEFAULT_MAX_PAGES,
    ) -> list[Any]:
        """GET a collection, transparently following Canvas Link rel="next"
        pagination, capped at max_items to keep responses bounded."""
        merged = {"per_page": DEFAULT_PER_PAGE, **(params or {})}
        url: str | None = self._url(path)
        next_params: dict[str, Any] | None = merged
        items: list[Any] = []
        pages = 0
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                while url and len(items) < max_items and pages < max_pages:
                    resp = await client.get(url, params=next_params, headers=self._headers)
                    self._raise_for_status(resp)
                    data = resp.json()
                    if isinstance(data, list):
                        items.extend(data)
                    elif isinstance(data, dict):
                        # A few endpoints wrap the list (e.g. {"events": [...]}).
                        wrapped = next((v for v in data.values() if isinstance(v, list)), None)
                        items.extend(wrapped if wrapped is not None else [data])
                    pages += 1
                    url = _parse_next_link(resp.headers.get("link"))
                    next_params = None  # the next URL already carries the query
            return items[:max_items]
        except CanvasError:
            raise
        except httpx.TimeoutException as e:
            raise CanvasError(504, f"Canvas request timed out: {e}") from e
        except httpx.HTTPError as e:
            raise CanvasError(502, f"Could not reach Canvas: {e}") from e
