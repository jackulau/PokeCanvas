# Hosting guide — run the Canvas MCP server anywhere

The server is a standard Python web app: it installs `requirements.txt` and starts
with `python src/server.py`, listening on `$PORT` and serving MCP at **`/mcp`**.
That means it runs on essentially any host. Pick one below.

Every host needs the **same two environment variables**:

| Variable | Value |
|----------|-------|
| `CANVAS_BASE_URL` | Your Canvas login URL, e.g. `https://canvas.university.edu` |
| `CANVAS_API_TOKEN` | Your Canvas token (Canvas → Account → Settings → **+ New Access Token**) |

When both are set on the host, you connect to Poke **with no API key** — the
server already has your credentials. Final URL is always `https://<your-host>/mcp`.

## Which host?

| Host | Free tier | Always-on | One-click | Best for |
|------|-----------|-----------|-----------|----------|
| **Render** | yes | sleeps ~15min idle | ✅ | easiest hosted, default |
| **Railway** | trial credit | yes | ✅ (from repo) | no cold starts, simple |
| **Fly.io** | yes (small) | scale-to-zero | CLI | global, cheap always-on |
| **Heroku** | paid (eco $5) | yes | ✅ | familiar, paid |
| **Docker / VPS** | your box | yes | — | full control |
| **Local + tunnel** | your laptop | while laptop on | `./setup.sh` | fastest test, zero signup |

---

## 1. Render (default, easiest)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/jackulau/PokeCanvas)

1. Click the button (or Render → **New → Blueprint** → pick `jackulau/PokeCanvas`). It reads `render.yaml`.
2. Set `CANVAS_BASE_URL` and `CANVAS_API_TOKEN` when prompted.
3. Deploy → your URL is `https://<service>.onrender.com/mcp`.

Free tier sleeps after ~15 min idle (first request after a nap ~50s). Upgrade the instance for always-on.

## 2. Railway (no cold starts)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

1. Railway → **New Project → Deploy from GitHub repo** → `jackulau/PokeCanvas`. It uses `railway.json` (Dockerfile build).
2. **Variables** tab → add `CANVAS_BASE_URL` and `CANVAS_API_TOKEN`.
3. **Settings → Networking → Generate Domain** → your URL is `https://<app>.up.railway.app/mcp`.

Railway injects `PORT` automatically; the server binds it.

## 3. Fly.io (cheap always-on / global)

```bash
# one-time: install flyctl + log in
brew install flyctl && fly auth login

# from the repo root (uses the included fly.toml + Dockerfile)
fly launch --copy-config --now          # accept the app name or pick your own
fly secrets set CANVAS_BASE_URL=https://canvas.youruni.edu CANVAS_API_TOKEN=YOUR_TOKEN
```

Your URL is `https://<app-name>.fly.dev/mcp`. `fly.toml` is set to scale to zero when idle and wake on request.

## 4. Heroku

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/jackulau/PokeCanvas)

1. Click the button — it reads `app.json` and prompts for the two env vars.
2. Or CLI:
   ```bash
   heroku create
   heroku config:set CANVAS_BASE_URL=https://canvas.youruni.edu CANVAS_API_TOKEN=YOUR_TOKEN
   git push heroku main
   ```
3. Your URL is `https://<app>.herokuapp.com/mcp`. (`Procfile` defines the web process.)

## 5. Docker / any VPS

The repo ships a `Dockerfile`.

```bash
docker build -t canvas-poke-mcp .
docker run -d --restart unless-stopped -p 8000:8000 \
  -e CANVAS_BASE_URL=https://canvas.youruni.edu \
  -e CANVAS_API_TOKEN=YOUR_TOKEN \
  --name canvas-poke canvas-poke-mcp
```

Put it behind a reverse proxy with HTTPS (Caddy/nginx/Traefik). Poke requires
`https://`, so terminate TLS at the proxy. Your URL is `https://your-domain/mcp`.

Same image runs on Google Cloud Run, AWS App Runner, Azure Container Apps, etc. —
point them at the Dockerfile and set the two env vars.

## 6. Local + tunnel (fastest, no signup)

Run it on your own machine and expose it with a tunnel. The included
[`setup.sh`](setup.sh) does the whole thing — installs deps, asks for your Canvas
URL + token once, starts the server, opens a Cloudflare tunnel, and registers the
resulting URL with Poke via the Poke CLI:

```bash
./setup.sh
```

Manual equivalent:

```bash
pip install -r requirements.txt
export CANVAS_BASE_URL=https://canvas.youruni.edu CANVAS_API_TOKEN=YOUR_TOKEN
python src/server.py &                              # serves :8000/mcp
npx cloudflared tunnel --url http://localhost:8000  # prints https://xyz.trycloudflare.com
npx poke@latest mcp add https://xyz.trycloudflare.com/mcp -n "Canvas"
```

The tunnel URL stays up only while the command runs and your laptop is awake — great for testing, not for 24/7.

---

## Connect to Poke (any host)

Once your server is live at `https://<host>/mcp`:

**Option A — web UI:** [poke.com/settings/connections](https://poke.com/settings/connections) → **New integration** → Name `Canvas`, URL `https://<host>/mcp`, leave the API key **blank** (creds live on the server) → Create.

**Option B — one command (Poke CLI):**
```bash
npx poke@latest mcp add https://<host>/mcp -n "Canvas"
```

**Option C — shareable recipe (Poke does the rest):** see [`recipe/recipe.md`](recipe/recipe.md) — bundles this integration + onboarding so any user is ready in one click via a `poke.com/r/<code>` link.

Then message Poke: *"What courses am I taking?"*

### Shared multi-user server (optional)
If one server serves many people/schools, don't bake one token into env. Instead use
**API-key auth**: each user pastes `https://canvas.theirschool.edu::THEIR_TOKEN` as
the Poke integration key. The server splits the composite per request (see
[README](README.md) → Auth modes).
