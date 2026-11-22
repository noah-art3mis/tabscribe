"""Live browser preview of an .atex file. Re-renders whenever the file changes,
so edits made by you or by Claude Code show up within a second."""

from __future__ import annotations

import http.server
import webbrowser
from functools import partial
from pathlib import Path

ALPHATAB = "https://cdn.jsdelivr.net/npm/@coderline/alphatab@1.9/dist"

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tabscribe: {name}</title>
<style>
  body {{ margin: 0; font-family: system-ui, sans-serif; }}
  header {{ position: sticky; top: 0; z-index: 10; background: #fff;
           display: flex; gap: .75rem; align-items: center;
           padding: .5rem 1rem; border-bottom: 1px solid #ddd; }}
  #status {{ color: #666; font-size: .9rem; }}
  #status.error {{ color: #b00020; white-space: pre-wrap; }}
  button {{ font-size: 1rem; padding: .3rem .8rem; }}
</style>
</head>
<body>
<header>
  <button id="play" disabled>Play</button>
  <strong>{name}</strong>
  <span id="status">loading...</span>
</header>
<div id="score"></div>
<script src="{cdn}/alphaTab.js"></script>
<script>
const status = document.getElementById('status');
const playBtn = document.getElementById('play');
const api = new alphaTab.AlphaTabApi(document.getElementById('score'), {{
  core: {{ fontDirectory: '{cdn}/font/' }},
  player: {{ enablePlayer: true, enableCursor: true,
            soundFont: '{cdn}/soundfont/sonivox.sf2' }},
}});
api.error.on(e => {{
  status.className = 'error';
  status.textContent = 'Could not render: ' + (e && e.message ? e.message : e);
}});
api.renderFinished.on(() => {{
  status.className = '';
  status.textContent = 'updated ' + new Date().toLocaleTimeString();
}});
api.scoreLoaded.on(score => api.renderTracks(score.tracks));
api.playerReady.on(() => playBtn.disabled = false);
api.playerStateChanged.on(e => playBtn.textContent = e.state === 1 ? 'Pause' : 'Play');
playBtn.onclick = () => api.playPause();

let last = null;
async function poll() {{
  try {{
    const res = await fetch('score.atex?t=' + Date.now());
    const text = await res.text();
    if (text !== last) {{ last = text; api.tex(text); }}
  }} catch (e) {{ status.textContent = 'server stopped'; }}
  setTimeout(poll, 1000);
}}
poll();
</script>
</body>
</html>
"""


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, atex: Path, **kwargs):
        self.atex = atex
        super().__init__(*args, **kwargs)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            body = PAGE.format(name=self.atex.name, cdn=ALPHATAB).encode()
            ctype = "text/html; charset=utf-8"
        elif path == "/score.atex":
            body = self.atex.read_bytes()
            ctype = "text/plain; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve(atex: Path, port: int = 8765, open_browser: bool = True) -> None:
    handler = partial(_Handler, atex=atex.resolve())
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        print(f"Previewing {atex} at {url} (Ctrl-C to stop)")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
