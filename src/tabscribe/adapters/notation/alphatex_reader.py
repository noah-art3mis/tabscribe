"""SongReader for alphaTex, using alphaTab itself (in Node) as the parser.

Using the real parser means the reader accepts exactly what the preview
renders. Requires `node` and `npm install` in the repo root.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ...domain import (
    TICKS_PER_BEAT,
    ChordSymbol,
    DrumPart,
    DrumPiece,
    Instrument,
    PitchedPart,
    Role,
    ScoreHit,
    ScoreNote,
    Song,
    SyncPoint,
    Tuning,
)

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "atex_to_json.mjs"
ALPHATAB_TICKS_PER_BEAT = 960


class AlphaTexParseError(ValueError):
    def __init__(self, message: str, diagnostics: list[dict]):
        detail = "; ".join(f"line {d.get('line')}, col {d.get('col')}: {d.get('message')}"
                           for d in diagnostics)
        super().__init__(f"{message}: {detail}" if detail else message)
        self.diagnostics = diagnostics


def _role(track: dict) -> Role:
    if track["percussion"]:
        return Role.DRUMS
    program = track.get("program", 0)
    if 32 <= program <= 39 or (len(track["tuning"]) in (4, 5) and track["tuning"][0] < 50):
        return Role.BASS
    if 0 <= program <= 7:
        return Role.PIANO
    return Role.GUITAR


def _ticks(alphatab_ticks: int, beat_unit: int) -> int:
    # alphaTab counts 960 per quarter note; we count TICKS_PER_BEAT per beat.
    quarter = TICKS_PER_BEAT * beat_unit // 4
    return round(alphatab_ticks * quarter / ALPHATAB_TICKS_PER_BEAT)


class AlphaTexReader:
    extension = "atex"

    def __init__(self, node: str = "node"):
        self.node = node

    def read(self, text: str) -> Song:
        result = subprocess.run([self.node, str(SCRIPT)], input=text, capture_output=True,
                                text=True, cwd=ROOT)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"alphaTab reader failed: {result.stderr.strip()}") from None
        if result.returncode != 0 or "error" in data:
            raise AlphaTexParseError(data.get("error", "parse failed"), data.get("diagnostics", []))

        unit = data["beatUnit"]
        song = Song(title=data["title"] or "", tempo_bpm=data["tempo"],
                    beats_per_bar=data["beatsPerBar"], beat_unit=unit,
                    sync=[SyncPoint(_ticks(round(p["tick"]), unit), p["ms"] / 1000)
                          for p in data.get("sync", [])])
        for track in data["tracks"]:
            role = _role(track)
            if role is Role.DRUMS:
                hits = [ScoreHit(_ticks(e["start"], unit), DrumPiece(e["drum"]))
                        for e in track["events"] if DrumPiece.from_midi(e["drum"] or -1)]
                song.parts.append(DrumPart(Instrument(role, track["name"]), hits))
                continue
            tuning = Tuning(tuple(track["tuning"])) if track["tuning"] else None
            count = len(track["tuning"])
            notes = [
                ScoreNote(
                    start=_ticks(e["start"], unit),
                    duration=_ticks(e["duration"], unit),
                    pitch=e["pitch"],
                    string=count - e["string"] + 1 if count else None,  # ours: 1 = highest
                    fret=e["fret"] if count else None,
                    effects=frozenset(e["effects"]),
                )
                for e in track["events"]
            ]
            song.parts.append(PitchedPart(Instrument(role, track["name"], tuning), notes))
            if not song.chords:
                song.chords = [ChordSymbol(_ticks(c["start"], unit), c["label"])
                               for c in track["chords"]]
        return song

    def read_file(self, path: Path) -> Song:
        return self.read(Path(path).read_text())
