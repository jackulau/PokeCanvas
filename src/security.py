"""SSRF protection for the user-supplied Canvas base URL.

On a multi-tenant deployment the Canvas base URL comes from the caller (the
`base::token` composite in Poke's key field, or the X-Canvas-Base-Url header).
Without validation, a caller could point the server at internal addresses
(cloud metadata, loopback, RFC1918) and use it as an SSRF proxy. This module
rejects those before any outbound request is made.

Caveat (documented in SECURITY.md): this blocks literal internal IPs + known
metadata hostnames + non-https schemes. It does NOT resolve hostnames, so a
DNS-rebinding attacker could still point a public hostname at a private IP.
That's an accepted tradeoff at this scale; a stricter deployment should resolve
+ re-check at connect time or run on an egress-restricted network.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

# Hostnames that resolve to cloud metadata / internal services.
_BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.goog",
        "metadata",
    }
)


def assert_safe_canvas_url(url: str) -> None:
    """Raise CanvasError(400) if `url` is not a safe public https Canvas origin."""
    from .canvas_client import CanvasError  # lazy import avoids a circular import

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()

    if not host:
        raise CanvasError(400, "Invalid Canvas URL: no host.")
    if scheme != "https":
        raise CanvasError(400, "Canvas URL must use https.")
    if host in _BLOCKED_HOSTS:
        raise CanvasError(400, "Refusing to connect to an internal/metadata host.")

    # If the host is a literal IP, block anything not globally routable.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None  # it's a hostname; allowed (see DNS-rebind caveat above)
    if ip is not None and (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise CanvasError(400, "Refusing to connect to a private/internal IP address.")
