# Canvas LMS integration for Poke

Connect your **Canvas LMS** account to **[Poke](https://poke.com) by The Interaction Company** so you can ask Poke about your classes in plain language:

> "What's due this week?" · "Did my CS101 grade change?" · "Read me the syllabus page" · "Any new announcements?"

It's a small [FastMCP](https://github.com/jlowin/fastmcp) server that wraps the Canvas REST API and speaks the Model Context Protocol (MCP) Poke connects to. Once deployed, Poke discovers the tools automatically and uses them whenever a question is about your coursework.

All data is read **live** on every request, so answers always reflect the current state of Canvas — new assignments, changed grades, fresh announcements, updated due dates. There is nothing to re-sync.

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

## Setup (about 5 minutes, then hands-off)

### 1. Get your Canvas access token
In Canvas: **Account → Settings → Approved Integrations → "+ New Access Token"**. Give it a purpose ("Poke"), leave expiry blank or far out, and copy the token (you only see it once).

Also note your Canvas URL — the address you log in at, e.g. `https://canvas.university.edu`.

### 2. Deploy the server

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. Push this repo to your own GitHub account (`gh repo create canvas-poke-mcp --public --source . --push`, or fork it).
2. On [Render](https://render.com): **New → Blueprint** (or **Web Service**) → connect that repo. Render reads `render.yaml` automatically.
3. When prompted, set the two environment variables:
   - `CANVAS_BASE_URL` = your Canvas URL (e.g. `https://canvas.university.edu`)
   - `CANVAS_API_TOKEN` = the token from step 1
4. Deploy. Your server URL will be `https://<your-service>.onrender.com/mcp` — **note the `/mcp` and no trailing slash.**

> Render's free tier sleeps after ~15 min idle, so the *first* request after a nap can take ~50s to wake. Subsequent calls are fast. Upgrade to a paid instance (or any always-on host) if you want zero cold starts.

Any host works (Railway, Fly, Heroku, your own box) — it's a standard Python web service started with `python src/server.py`, reading `PORT` from the environment.

### 3. Connect it to Poke

Because the credentials live on your server (step 2), Poke needs **no API key** — just the URL.

1. Open [poke.com/settings/connections](https://poke.com/settings/connections) → **New integration**.
2. **Name:** `Canvas`   **Server URL:** `https://<your-service>.onrender.com/mcp`
3. Leave the API key blank → **Create integration**. Poke connects and discovers all the tools.
4. Test it: message Poke **"What courses am I taking?"**

For one-message, shareable setup, see [`recipe/`](recipe/) — a Poke **recipe** that bundles this integration with onboarding context so a new user is ready after a single click.

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

- `src/server.py` — FastMCP app (`transport="http"`, `stateless_http=True`), registers the tools.
- `src/tools.py` — the 14 `@mcp.tool` definitions; build a client from the request, call the data layer, return clean errors.
- `src/canvas_api.py` — one function per resource; maps to Canvas endpoints and trims responses to what matters.
- `src/canvas_client.py` — async HTTP, credential resolution, and transparent Canvas `Link`-header pagination.

See [`recipe/recipe.md`](recipe/recipe.md) for the Poke recipe and onboarding copy.
