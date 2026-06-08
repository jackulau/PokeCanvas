# Security model

This server can run in two modes. The security properties differ — pick the one
that matches your trust needs.

| Mode | Who holds the Canvas token | Trust required |
|------|----------------------------|----------------|
| **Self-host** (recommended for privacy) | Only you — it's an env var on *your* host | None beyond your host |
| **Shared multi-tenant** (lowest setup) | Each user passes it to Poke; it flows through the shared server per request | You must trust whoever runs the shared instance |

## What the server does and doesn't do with your token

- **Never stored.** The server is stateless — the Canvas token is read from the
  request (or the host's env), used for that one upstream call, and discarded.
  There is no database, cache, or file that holds tokens.
- **Never logged.** Tokens are not written to logs or error messages.
- **Read-only.** Every tool is a Canvas `GET`. The server never writes, submits,
  or deletes anything in Canvas.
- **HTTPS only.** Poke requires `https://` to the server; the server requires
  `https://` to Canvas.

## Hardening for shared (multi-tenant) deployments

When the Canvas base URL comes from the caller (the `canvas-url::token` composite
in Poke's key field, or an `X-Canvas-Base-Url` header), it is untrusted input.

- **SSRF protection** (`src/security.py`): before any outbound request, the base
  URL is validated — non-`https` schemes, literal private/loopback/link-local/
  reserved IPs, and cloud-metadata hostnames (e.g. `169.254.169.254`,
  `metadata.google.internal`) are rejected. This stops the server from being used
  as a proxy into internal infrastructure.
  - *Residual risk:* hostnames are not resolved, so a DNS-rebinding attacker could
    point a public name at a private IP. Accepted at this scale. For a hardened
    deployment, run on an egress-restricted network or resolve + re-check at
    connect time.
- **Per-user rate limiting** (`src/ratelimit.py`): requests are rate-limited per
  Poke user (`X-Poke-User-Id`, falling back to a hash of the auth header — never
  the raw token). Default 120 requests/minute/user. In-memory and per-process; a
  multi-instance deployment that needs a global limit should back this with Redis.
- **Token exposure tradeoff:** in shared mode the Canvas token is stored in *the
  user's own Poke integration settings* and transmitted to the shared server on
  each request. If you are not comfortable with that, **self-host** — then the
  token never leaves infrastructure you control.

## Canvas token scope

A Canvas personal access token carries the permissions of your account. Treat it
like a password:

- Create a dedicated token for this integration (Canvas → Account → Settings →
  New Access Token) so you can revoke it independently.
- Set an expiry if your institution allows it.
- Revoke it in Canvas if it leaks; the server holds no copy.

## Reporting a vulnerability

Open a private security advisory on the GitHub repo
(`https://github.com/jackulau/PokeCanvas` → Security → Report a vulnerability), or
open an issue for non-sensitive reports. Please don't disclose exploitable issues
in public until they're fixed.
