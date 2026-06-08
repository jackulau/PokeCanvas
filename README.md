# Canvas LMS integration for Poke

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Protocol: MCP](https://img.shields.io/badge/protocol-MCP-7c3aed)
[![Security](https://img.shields.io/badge/security-SSRF%20guard%20%2B%20rate%20limit-green)](SECURITY.md)

Connect your **Canvas LMS** account to **[Poke](https://poke.com) by The Interaction Company** so you can ask Poke about your classes in plain language:

> "What's due this week?" · "Did my CS101 grade change?" · "Read me the syllabus page" · "Any new announcements?"

It's a small [FastMCP](https://github.com/jlowin/fastmcp) server that wraps the Canvas REST API and speaks the Model Context Protocol (MCP) Poke connects to. Once deployed, Poke discovers the tools automatically and uses them whenever a question is about your coursework.

All data is read **live** on every request, so answers always reflect the current state of Canvas — new assignments, changed grades, fresh announcements, updated due dates. There is nothing to re-sync.

---

## ⚡ 1-click setup

**Hosted — no terminal.** Click, set 2 fields, deploy:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/jackulau/PokeCanvas) &nbsp; [![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/jackulau/PokeCanvas)

On the deploy screen set `CANVAS_BASE_URL` + `CANVAS_API_TOKEN`. Then **open your new service URL in a browser** — the page shows your live MCP link and a one-tap-copy `npx poke@latest mcp add …` command already filled in with your URL. Paste it and Poke is connected. (Set the optional `POKE_API_KEY` too and the server texts you a "Canvas is live" confirmation on boot.)

**Local — one paste:**
```bash
curl -fsSL https://raw.githubusercontent.com/jackulau/PokeCanvas/main/bootstrap.sh | bash
```
This `bootstrap.sh` installs everything, asks for your Canvas URL + token once, opens a public tunnel, and registers it with Poke for you.

Other hosts (Railway, Fly, Docker, VPS) → **[HOSTING.md](HOSTING.md)**. Step-by-step detail below.

---

## How it's hosted — two models

This is built as a **multi-tenant** server, so there are two ways to run it:

- **Shared instance (least setup):** one deployment serves many people. Each user adds the shared `/mcp` URL in Poke and passes their own Canvas credentials as the integration key — `https://canvas.yourschool.edu::YOUR_CANVAS_TOKEN`. No per-user hosting, nothing to deploy. The server is hardened for untrusted callers: SSRF protection on the Canvas URL, per-user rate limiting (`X-Poke-User-Id`), and it never logs or stores tokens. See **[SECURITY.md](SECURITY.md)**.
- **Self-host (most private):** deploy your own (the 1-click above), set `CANVAS_BASE_URL` + `CANVAS_API_TOKEN`, connect with no key. Your token never leaves infrastructure you control.

Not sure which? **Self-host** — it's one click and the token stays yours.

---

## What Poke can see

Every resource you asked for, each as an MCP tool Poke calls on demand:

| Area | Tools |
|------|-------|
| Courses | `list_courses` (with current grade + term), `get_profile` |
| Assignments | `list_assignments` (incl. your score / submission status / late / missing) |
| Files | `list_files` |
| Pages | `list_pages`, `get_page` (full content) |
| Modules | `list_modules` (with the items inside each) |
| Announcements | `list_announcements` (one course, or all at once) |
| Discussions | `list_discussions` |
| Quizzes | `list_quizzes` |
| Calendar | `list_calendar_events`, `list_upcoming_events` |
| To-dos / changes | `list_todos`, `get_recent_activity` (the live "what changed" feed) |

**Read-only by design** — it never submits, posts, or deletes anything in Canvas.

---

## Setup

Three steps. **Fastest path with no signup: `./setup.sh`** — it installs deps, asks for
your Canvas URL + token once, opens a public tunnel, and registers it with Poke for you.
Prefer real 24/7 hosting? Full per-host instructions live in **[HOSTING.md](HOSTING.md)**.

### 1. Get your Canvas access token
In Canvas: **Account → Settings → Approved Integrations → "+ New Access Token"**. Copy it (shown once). Note your Canvas URL — where you log in, e.g. `https://canvas.university.edu`.

### 2. Deploy the server — pick one

**One-click hosted:**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/jackulau/PokeCanvas) &nbsp; [![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/jackulau/PokeCanvas)

**Or local, no signup:**
```bash
git clone https://github.com/jackulau/PokeCanvas && cd PokeCanvas
./setup.sh
```

Set `CANVAS_BASE_URL` + `CANVAS_API_TOKEN` on whichever host you pick. Every option ends with a URL like `https://<host>/mcp` — **note the `/mcp`, no trailing slash.** Render / Railway / Fly / Heroku / Docker / VPS / tunnel details → **[HOSTING.md](HOSTING.md)**.

> Render's free tier sleeps after ~15 min idle (first request after a nap ~50s). Railway/Fly/Heroku or your own Docker host avoid cold starts.

### 3. Connect it to Poke

Because the credentials live on your server, Poke needs **no API key** — just the URL.

- **One command:** `npx poke@latest mcp add https://<host>/mcp -n "Canvas"`
- **Or web UI:** [poke.com/settings/connections](https://poke.com/settings/connections) → **New integration** → Name `Canvas`, URL `https://<host>/mcp`, leave the API key **blank** → Create.
- **Or shareable recipe** (Poke sets it up for any user from one link): [`recipe/recipe.md`](recipe/recipe.md).

Then message Poke **"What courses am I taking?"**

---

## "Dynamically update if anything changes"

There's no stale cache to worry about: **every tool call hits Canvas in real time.** Three things make change-tracking explicit:

- `get_recent_activity` — Canvas's activity stream: new announcements, grade changes, submission comments, discussion replies.
- `list_todos` / `list_upcoming_events` — what needs action and what's due, soonest first.
- `list_assignments` returns your live submission state (graded? late? missing? score?).

Want Poke to *proactively* ping you when something changes (not just when you ask)? Add a scheduled automation — the recipe in [`recipe/`](recipe/) includes a ready-to-use prompt for it ("every morning, check `get_recent_activity` and text me anything new").

---

## Auth modes

| Mode | When | How |
|------|------|-----|
| **Env vars** (default) | You run your own server | Set `CANVAS_BASE_URL` + `CANVAS_API_TOKEN` on the host. Connect to Poke with no key. |
| **Bearer token** | One server, you pass the token from Poke | Put your token in Poke's API-key field. Base URL still comes from `CANVAS_BASE_URL` (or send an `X-Canvas-Base-Url` header). |
| **Composite bearer** | A shared server for many schools (e.g. a recipe) | Poke API key = `https://canvas.yourschool.edu::YOUR_TOKEN`. The server splits it per user. |

Precedence: a token in the request beats the env token; the request base URL (composite or header) beats `CANVAS_BASE_URL`.

---

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Run it
export CANVAS_BASE_URL=https://canvas.youruni.edu
export CANVAS_API_TOKEN=your_token
python src/server.py            # serves http://localhost:8000/mcp

# Verify (no Canvas account needed — uses mocks + a live protocol check)
pytest -q                       # unit tests
python scripts/smoke_tools_list.py   # all tools registered  -> TOOLS_OK
ruff check src tests scripts    # lint
```

To test the live transport the way Poke sees it:
```bash
PORT=8765 python src/server.py &
python scripts/live_http_test.py http://127.0.0.1:8765/mcp   # -> LIVE_OK
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| First request hangs ~50s | Render free-tier cold start; it's awake now. Use a paid/always-on host to avoid. |
| `401 ... access token` | Token wrong/expired, or `CANVAS_API_TOKEN` not set on the host. Regenerate in Canvas. |
| `401 ... base URL` | `CANVAS_BASE_URL` not set, or wrong (must be your login URL, e.g. `https://canvas.uni.edu`). |
| Poke "can't reach the tool" | Confirm the URL ends in `/mcp` (no trailing slash). Try `clearhistory` in Poke, then re-test. |
| Empty course list | The token's user may have no *active* enrollments; try "list all my courses including past ones". |

---

## How it works

```
Poke  ──(MCP over HTTPS, streamable-http at /mcp)──►  this server  ──(REST + Bearer)──►  Canvas LMS API
```

- `src/server.py` — FastMCP app (`transport="http"`, `stateless_http=True`), tool + route registration, landing page (`/`), health (`/health`), optional boot ping.
- `src/tools.py` — the 14 `@mcp.tool` definitions; rate-limit, build a client from the request, call the data layer, return clean errors.
- `src/canvas_api.py` — one function per resource; maps to Canvas endpoints and trims responses to what matters.
- `src/canvas_client.py` — async HTTP, credential resolution, and transparent Canvas `Link`-header pagination.
- `src/security.py` — SSRF guard for the caller-supplied Canvas URL (multi-tenant).
- `src/ratelimit.py` — per-user sliding-window rate limiter.
- `src/landing.py` — the self-configuring connect page served at `/`.

See [`recipe/recipe.md`](recipe/recipe.md) for the Poke recipe and onboarding copy.

---

## Security

Read-only, stateless, tokens never stored or logged, HTTPS-only, with SSRF
protection and per-user rate limiting for shared deployments. Full threat model
and the self-host-vs-shared tradeoff: **[SECURITY.md](SECURITY.md)**. Report
vulnerabilities via a private GitHub security advisory.

## Contributing

Issues and PRs welcome.

```bash
git clone https://github.com/jackulau/PokeCanvas && cd PokeCanvas
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q && ruff check src tests scripts      # keep both green
```

Please add a test for any new tool or behavior and keep `ruff` clean.

## License

[MIT](LICENSE) © 2026 jacklau
