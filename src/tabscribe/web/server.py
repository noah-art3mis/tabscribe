"""Local web app: a Guitar Pro-style viewer and editor for the song library.

This is an interface layer, like the CLI: it reads and writes .atex files
and runs the same TranscriptionPipeline, nothing more.

Routes
  GET  /                       the app
  GET  /static/...             app assets
  GET  /alphatab/...           alphaTab (from node_modules if installed, else the CDN)
  GET  /api/songs              library listing
  GET  /api/songs/<name>       {name, text, mtime}
  PUT  /api/songs/<name>       save text (body); returns {mtime}
  POST /api/transcribe         body = audio bytes, header X-Filename; returns {job}
  GET  /api/jobs/<id>          {status, stage, done, error, song}
  GET  /api/pipeline           which adapter fills each stage
  GET  /api/media/<name>       the song's recording and stems, if any
  GET  /media/<name>/<file>    audio file (supports Range requests, for seeking)
"""

from __future__ import annotations

import http.server
import json
import mimetypes
import re
import threading
import traceback
import uuid
import webbrowser
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from ..library import list_media, media_dir, save_media

STATIC = Path(__file__).parent / "static"
ROOT = Path(__file__).resolve().parents[3]
ALPHATAB_LOCAL = ROOT / "node_modules" / "@coderline" / "alphatab" / "dist"
ALPHATAB_CDN = "https://cdn.jsdelivr.net/npm/@coderline/alphatab@1.9/dist"
SAFE_NAME = re.compile(r"^[\w\- .()]+$")
STAGE_LABELS = {
    "1_rhythm": "Beats and bars",
    "2_harmony": "Chords",
    "3_stems": "Separate instruments",
    "4_tracks": "Notes and drums",
    "5_quantized": "Snap to grid",
    "6_fretted": "Strings and frets",
    "7_refined": "Clean-up",
}

mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/otf", ".otf")
mimetypes.add_type("audio/x-soundfont", ".sf2")
mimetypes.add_type("text/javascript", ".mjs")


@dataclass
class Job:
    id: str
    name: str
    status: str = "running"  # running | done | error
    stage: str = "Beats and bars"
    done: list[str] = field(default_factory=list)
    error: str | None = None
    song: str | None = None


class App:
    def __init__(self, library: Path, config_path: Path | None = None):
        self.library = library
        self.library.mkdir(parents=True, exist_ok=True)
        self.config_path = config_path
        self.jobs: dict[str, Job] = {}

    # --- library ---------------------------------------------------------------

    def path_for(self, name: str) -> Path:
        name = unquote(name)
        if not name.endswith(".atex"):
            name += ".atex"
        if not SAFE_NAME.match(name) or ".." in name:
            raise ValueError("bad song name")
        return self.library / name

    def list_songs(self) -> list[dict[str, Any]]:
        songs = []
        for p in sorted(self.library.glob("*.atex"), key=lambda p: -p.stat().st_mtime):
            head = p.read_text(errors="replace")[:2000]
            title = re.search(r'\\title\s+"([^"]*)"', head)
            tracks = re.findall(r'\\track\s+"([^"]*)"', p.read_text(errors="replace"))
            songs.append({"name": p.stem, "title": title.group(1) if title else p.stem,
                          "tracks": tracks, "mtime": p.stat().st_mtime,
                          "media": bool(list_media(self.library, p.stem))})
        return songs

    # --- transcription -----------------------------------------------------------

    def start_job(self, filename: str, audio: bytes) -> Job:
        stem = re.sub(r"[^\w\- .()]", "_", Path(filename).stem) or "song"
        job = Job(uuid.uuid4().hex[:12], stem)
        self.jobs[job.id] = job
        uploads = self.library / ".uploads"
        uploads.mkdir(exist_ok=True)
        audio_path = uploads / f"{stem}{Path(filename).suffix or '.wav'}"
        audio_path.write_bytes(audio)
        threading.Thread(target=self._run, args=(job, audio_path), daemon=True).start()
        return job

    def _run(self, job: Job, audio_path: Path) -> None:
        try:
            from ..adapters.notation.alphatex import AlphaTexWriter
            from ..application.config import build_pipeline, load_config
            from ..domain import AudioRef

            pipeline = build_pipeline(load_config(self.config_path))
            stage_names = list(STAGE_LABELS)
            outputs: dict[str, object] = {}

            def observe(stage: str, output: object) -> None:
                outputs[stage] = output
                job.done.append(STAGE_LABELS.get(stage, stage))
                i = stage_names.index(stage) if stage in stage_names else -1
                job.stage = STAGE_LABELS[stage_names[i + 1]] if 0 <= i < len(stage_names) - 1 \
                    else "Writing tab"

            job.stage = "Beats and bars"
            song = pipeline.run(AudioRef(audio_path), self.library / ".work" / job.name,
                                job.name, observe)
            target = self.path_for(job.name)
            n = 2
            while target.exists():
                target = self.path_for(f"{job.name} ({n})")
                n += 1
            target.write_text(AlphaTexWriter().write(song))
            save_media(self.library, target.stem, audio_path, outputs.get("3_stems") or {})
            job.song, job.status = target.stem, "done"
        except Exception as e:  # report to the browser instead of dying silently
            job.status, job.error = "error", f"{type(e).__name__}: {e}"
            traceback.print_exc()

    def pipeline_info(self) -> dict[str, Any]:
        from ..application.config import load_config

        config = load_config(self.config_path)
        return {"stages": config["stages"], "instruments": config["instruments"]}


class Handler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, app: App, **kwargs):
        self.app = app
        super().__init__(*args, **kwargs)

    def log_message(self, *args):
        pass

    # --- helpers -----------------------------------------------------------------

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: Any, status: int = 200) -> None:
        self._send(status, json.dumps(data).encode(), "application/json")

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self._json({"error": "not found"}, 404)
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send(200, path.read_bytes(), ctype)

    def _media(self, name: str, filename: str) -> None:
        """Serve an audio file, honouring Range requests so the player can seek."""
        folder = media_dir(self.app.library, self.app.path_for(name).stem)
        path = (folder / Path(unquote(filename)).name)
        if not path.is_file():
            self._json({"error": "not found"}, 404)
            return
        size = path.stat().st_size
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        start, end = 0, size - 1
        match = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if match and (match.group(1) or match.group(2)):
            if match.group(1):
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else size - 1
            else:  # suffix range: last N bytes
                start = max(0, size - int(match.group(2)))
            end = min(end, size - 1)
            if start > end:
                self._send(416, b"", "text/plain", {"Content-Range": f"bytes */{size}"})
                return
        with path.open("rb") as f:
            f.seek(start)
            body = f.read(end - start + 1)
        headers = {"Accept-Ranges": "bytes"}
        status = 200
        if match and (match.group(1) or match.group(2)):
            status = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        self._send(status, body, ctype, headers)

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length", 0)))

    # --- routes ------------------------------------------------------------------

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/index.html"):
                self._file(STATIC / "index.html")
            elif path.startswith("/static/"):
                self._file(STATIC / Path(path.removeprefix("/static/")).name)
            elif path.startswith("/alphatab/"):
                rel = path.removeprefix("/alphatab/")
                local = (ALPHATAB_LOCAL / rel).resolve()
                if ALPHATAB_LOCAL.exists() and str(local).startswith(str(ALPHATAB_LOCAL)):
                    self._file(local)
                else:
                    self._send(302, b"", "text/plain", {"Location": f"{ALPHATAB_CDN}/{rel}"})
            elif path == "/api/songs":
                self._json(self.app.list_songs())
            elif path.startswith("/api/songs/"):
                p = self.app.path_for(path.removeprefix("/api/songs/"))
                if not p.exists():
                    self._json({"error": "not found"}, 404)
                else:
                    self._json({"name": p.stem, "text": p.read_text(), "mtime": p.stat().st_mtime})
            elif path.startswith("/api/jobs/"):
                job = self.app.jobs.get(path.removeprefix("/api/jobs/"))
                self._json(job.__dict__ if job else {"error": "not found"}, 200 if job else 404)
            elif path == "/api/pipeline":
                self._json(self.app.pipeline_info())
            elif path.startswith("/api/media/"):
                name = self.app.path_for(path.removeprefix("/api/media/")).stem
                self._json(list_media(self.app.library, name))
            elif path.startswith("/media/"):
                name, _, filename = path.removeprefix("/media/").partition("/")
                self._media(name, filename)
            else:
                self._json({"error": "not found"}, 404)
        except ValueError as e:
            self._json({"error": str(e)}, 400)

    def do_PUT(self):  # noqa: N802
        path = self.path.split("?")[0]
        if not path.startswith("/api/songs/"):
            self._json({"error": "not found"}, 404)
            return
        try:
            p = self.app.path_for(path.removeprefix("/api/songs/"))
        except ValueError as e:
            self._json({"error": str(e)}, 400)
            return
        p.write_text(self._body().decode())
        self._json({"name": p.stem, "mtime": p.stat().st_mtime})

    def do_POST(self):  # noqa: N802
        if self.path.split("?")[0] != "/api/transcribe":
            self._json({"error": "not found"}, 404)
            return
        audio = self._body()
        if not audio:
            self._json({"error": "empty upload"}, 400)
            return
        job = self.app.start_job(unquote(self.headers.get("X-Filename", "song.wav")), audio)
        self._json({"job": job.id})


def serve(library: Path, port: int = 8765, config: Path | None = None,
          open_browser: bool = True, host: str = "127.0.0.1", song: str | None = None) -> None:
    app = App(library, config)
    with http.server.ThreadingHTTPServer((host, port), partial(Handler, app=app)) as httpd:
        url = f"http://{host}:{port}/" + (f"#song={quote(song)}" if song else "")
        print(f"tabscribe: library {library.resolve()} at {url} (Ctrl-C to stop)")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
