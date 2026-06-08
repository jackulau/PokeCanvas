#!/usr/bin/env bash
#
# One-command setup for the Canvas <-> Poke integration, no hosting account needed.
#
#   ./setup.sh
#
# It will:
#   1. create a virtualenv and install dependencies
#   2. ask for your Canvas URL + token once (or read them from the environment / .env)
#   3. start the MCP server locally
#   4. open a public Cloudflare tunnel to it
#   5. register that URL with Poke via the Poke CLI
#
# The server + tunnel run until you press Ctrl-C. Your laptop must stay awake.
# For 24/7 hosting, see HOSTING.md instead.

set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
INTEGRATION_NAME="${POKE_INTEGRATION_NAME:-Canvas}"
SERVER_PID=""
TUNNEL_PID=""
TUNNEL_LOG="$(mktemp -t canvas-poke-tunnel.XXXXXX)"

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!  \033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mx  \033[0m %s\n' "$*" >&2; exit 1; }

cleanup() {
  [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null || true
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
  rm -f "$TUNNEL_LOG" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ---- 1. dependencies -------------------------------------------------------
command -v python3 >/dev/null 2>&1 || die "python3 is required (https://www.python.org/downloads/)."

if [ ! -d .venv ]; then
  log "Creating virtualenv (.venv)"
  python3 -m venv .venv
fi
log "Installing dependencies"
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt

# ---- 2. credentials --------------------------------------------------------
# Pull from .env if present and not already in the environment.
if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
fi

if [ -z "${CANVAS_BASE_URL:-}" ]; then
  printf 'Canvas URL (e.g. https://canvas.university.edu): '
  read -r CANVAS_BASE_URL
fi
if [ -z "${CANVAS_API_TOKEN:-}" ]; then
  printf 'Canvas access token (Account -> Settings -> New Access Token): '
  read -rs CANVAS_API_TOKEN
  printf '\n'
fi
[ -n "${CANVAS_BASE_URL:-}" ] || die "CANVAS_BASE_URL is required."
[ -n "${CANVAS_API_TOKEN:-}" ] || die "CANVAS_API_TOKEN is required."
export CANVAS_BASE_URL CANVAS_API_TOKEN PORT

# ---- 3. start the server ---------------------------------------------------
log "Starting MCP server on http://localhost:$PORT/mcp"
.venv/bin/python src/server.py >/tmp/canvas-poke-server.log 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 60); do
  if curl -s -o /dev/null "http://127.0.0.1:$PORT/mcp"; then break; fi
  sleep 0.5
done
kill -0 "$SERVER_PID" 2>/dev/null || die "Server failed to start — see /tmp/canvas-poke-server.log"

# ---- 4. public tunnel ------------------------------------------------------
# Prefer an installed cloudflared; otherwise use the npm-wrapped binary via npx.
if command -v cloudflared >/dev/null 2>&1; then
  TUNNEL_CMD=(cloudflared tunnel --url "http://localhost:$PORT")
elif command -v npx >/dev/null 2>&1; then
  TUNNEL_CMD=(npx --yes cloudflared tunnel --url "http://localhost:$PORT")
else
  die "Need cloudflared or npx. Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ — or deploy to a host (see HOSTING.md)."
fi

log "Opening public tunnel"
"${TUNNEL_CMD[@]}" >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

PUBLIC_URL=""
for _ in $(seq 1 60); do
  PUBLIC_URL="$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -1 || true)"
  if [ -n "$PUBLIC_URL" ]; then break; fi
  kill -0 "$TUNNEL_PID" 2>/dev/null || die "Tunnel exited early — see $TUNNEL_LOG"
  sleep 1
done
[ -n "$PUBLIC_URL" ] || die "Could not obtain a tunnel URL — see $TUNNEL_LOG"

MCP_URL="$PUBLIC_URL/mcp"
log "Public MCP endpoint: $MCP_URL"

# ---- 5. register with Poke -------------------------------------------------
if command -v npx >/dev/null 2>&1; then
  log "Registering with Poke (a browser/login prompt may appear)"
  if npx --yes poke@latest mcp add "$MCP_URL" -n "$INTEGRATION_NAME"; then
    log "Connected to Poke as \"$INTEGRATION_NAME\". Try: \"What courses am I taking?\""
  else
    warn "Auto-register didn't complete. Add it manually:"
    warn "  npx poke@latest mcp add $MCP_URL -n \"$INTEGRATION_NAME\""
    warn "  or paste $MCP_URL at https://poke.com/settings/connections (leave API key blank)"
  fi
else
  warn "npx not found — add the integration in Poke manually:"
  warn "  URL: $MCP_URL  (https://poke.com/settings/connections, leave API key blank)"
fi

echo
log "Running. Keep this terminal open. Press Ctrl-C to stop the server + tunnel."
wait "$TUNNEL_PID"
