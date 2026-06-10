"""HTML landing page for the deployed server.

Visiting the service root shows the user their own live MCP URL and the exact,
pre-filled command to connect it to Poke — so after a one-click deploy there's
nothing to look up or assemble. Kept as a pure function for easy testing.
"""

from __future__ import annotations

import html


def render_landing(mcp_url: str, creds_ok: bool) -> str:
    # Escape each value exactly once for HTML embedding.
    url_e = html.escape(mcp_url, quote=True)
    cli_e = html.escape(f'npx poke@latest mcp add {mcp_url} -n "Canvas"')
    status = (
        '<p class="ok">✅ Canvas credentials are configured on this server. Connect to Poke with no API key.</p>'
        if creds_ok
        else '<p class="warn">⚠️ Set <code>CANVAS_BASE_URL</code> and '
        "<code>CANVAS_API_TOKEN</code> in this host's environment, then redeploy.</p>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Canvas → Poke</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 16px/1.6 system-ui, sans-serif; max-width: 680px; margin: 3rem auto; padding: 0 1.2rem; }}
  h1 {{ font-size: 1.5rem; margin-bottom: .2rem; }}
  .sub {{ color: #666; margin-top: 0; }}
  .ok {{ color: #0a7a3b; }} .warn {{ color: #b25e00; }}
  code {{ background: rgba(127,127,127,.15); padding: .1em .35em; border-radius: 4px; }}
  .cmd {{ display: flex; gap: .5rem; align-items: stretch; margin: .4rem 0 1.2rem; }}
  .cmd pre {{ flex: 1; margin: 0; padding: .7rem .8rem; background: rgba(127,127,127,.12);
             border-radius: 8px; overflow-x: auto; }}
  button {{ padding: 0 .9rem; border: 1px solid rgba(127,127,127,.4); border-radius: 8px;
            background: rgba(127,127,127,.1); cursor: pointer; font: inherit; }}
  ol {{ padding-left: 1.2rem; }} li {{ margin: .25rem 0; }}
  footer {{ margin-top: 2rem; color: #888; font-size: .9rem; }}
  a {{ color: #2a6df4; }}
</style></head><body>
  <h1>Canvas → Poke</h1>
  <p class="sub">Your Canvas LMS integration for <a href="https://poke.com">Poke</a> is running.</p>
  {status}

  <h2>Connect to Poke — one command</h2>
  <div class="cmd">
    <pre id="cli">{cli_e}</pre>
    <button onclick="navigator.clipboard.writeText(document.getElementById('cli').textContent)">Copy</button>
  </div>

  <h2>…or in the Poke app</h2>
  <ol>
    <li>Open <a href="https://poke.com/settings/connections">poke.com/settings/connections</a> → <b>New integration</b>.</li>
    <li>Name <code>Canvas</code>, Server URL <code>{url_e}</code>, leave the API key <b>blank</b>.</li>
    <li>Create, then message Poke: <i>"What courses am I taking?"</i></li>
  </ol>

  <footer>
    MCP endpoint: <code>{url_e}</code> ·
    <a href="https://github.com/jackulau/PokeCanvas">source &amp; docs</a>
  </footer>
</body></html>"""
