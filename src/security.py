"""SSRF protection for the user-supplied Canvas base URL.

On a multi-tenant deployment the Canvas base URL comes from the caller (the
`base::token` composite in Poke's key field, or the X-Canvas-Base-Url header).
Without validation, a caller could point the server at internal addresses
(cloud metadata, loopback, RFC1918) and use it as an SSRF proxy. This module
rejects those before any outbound request is made.

It blocks the obvious literal forms AND the lenient numeric encodings that a
target's libc would still parse to an internal address (decimal `2130706433`,
hex `0x7f000001`, dotted-octal `0177.0.0.1`, IPv4-mapped IPv6, ...), so the
guard doesn't depend on where it runs.

Caveat (documented in SECURITY.md): hostnames are not resolved, so a
DNS-rebinding attacker could still point a public name at a private IP. The
definitive control for a hardened deployment is an egress-restricted network.
"""
from __future__ import annotations

import ipaddress

# Hostnames that resolve to cloud metadata / internal services.
_BLOCKED_HOSTS = frozenset({"metadata.google.internal", "metadata.goog", "metadata"})


def _parse_int_any_base(s: str) -> int:
    """Parse an int the lenient way libc does: 0x = hex, leading 0 = octal."""
    low = s.lower()
    if low.startswith("0x"):
        return int(s, 16)
    if len(s) > 1 and s[0] == "0":
        return int(s, 8)
    return int(s, 10)


def _inet_aton_assemble(vals: list[int]) -> int | None:
    """inet_aton semantics: the final part absorbs the remaining low bytes."""
    n = len(vals)
    if any(v < 0 for v in vals):
        return None
    if n == 4:
        a, b, c, d = vals
        if max(a, b, c, d) > 0xFF:
            return None
        return (a << 24) | (b << 16) | (c << 8) | d
    if n == 3:
        a, b, c = vals
        if a > 0xFF or b > 0xFF or c > 0xFFFF:
            return None
        return (a << 24) | (b << 16) | c
    if n == 2:
        a, b = vals
        if a > 0xFF or b > 0xFFFFFF:
            return None
        return (a << 24) | b
    return None


def _candidate_ips(host: str) -> list[ipaddress._BaseAddress]:
    """All ways `host` could be interpreted as an IP address."""
    out: list[ipaddress._BaseAddress] = []

    def add(value) -> None:
        try:
            out.append(ipaddress.ip_address(value))
        except (ValueError, OverflowError):
            pass

    add(host)  # standard dotted-quad / IPv6

    # Whole-number host (decimal / hex / octal) -> 32-bit IPv4.
    try:
        n = _parse_int_any_base(host)
        if 0 <= n <= 0xFFFFFFFF:
            add(n)
    except ValueError:
        pass

    # Dotted host with mixed-base parts (inet_aton lenient form).
    parts = host.split(".")
    if 2 <= len(parts) <= 4 and all(parts):
        try:
            n = _inet_aton_assemble([_parse_int_any_base(p) for p in parts])
            if n is not None:
                add(n)
        except ValueError:
            pass

    return out


def _is_unsafe_ip(ip: ipaddress._BaseAddress) -> bool:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True
    mapped = getattr(ip, "ipv4_mapped", None)
    return mapped is not None and _is_unsafe_ip(mapped)


def assert_safe_canvas_url(url: str) -> None:
    """Raise CanvasError(400) if `url` is not a safe public https Canvas origin."""
    from urllib.parse import urlparse

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
    for ip in _candidate_ips(host):
        if _is_unsafe_ip(ip):
            raise CanvasError(400, "Refusing to connect to a private/internal IP address.")
