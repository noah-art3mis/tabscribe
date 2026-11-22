"""SongWriter for alphaTex (.atex), the editable source of truth.

Each beat lasts until the next onset in its part or the end of its longest
note, whichever comes first; the rest of the gap becomes rests. Notes that
cross a bar line are cut at the bar line (ties are not written yet).
"""

from __future__ import annotations

from ...domain import (
    TICKS_PER_BEAT,
    DrumPart,
    DrumPiece,
    Part,
    PitchedPart,
    Role,
    ScoreNote,
    Song,
    pitch_name,
)

# (ticks, alphaTex duration), longest first. 32nds are the finest value.
DURATIONS = tuple((TICKS_PER_BEAT * 4 // d, d) for d in (1, 2, 4, 8, 16, 32))

INSTRUMENT_NAMES = {
    Role.GUITAR: "Electric Guitar Clean",
    Role.BASS: "Electric Bass Finger",
    Role.PIANO: "Acoustic Grand Piano",
}

# alphaTex articulation names for drum pieces, defined in each drum track.
ARTICULATIONS = {
    DrumPiece.KICK: "Kick",
    DrumPiece.STICK: "Stick",
    DrumPiece.SNARE: "Snare",
    DrumPiece.TOM_FLOOR: "TomFloor",
    DrumPiece.HAT_CLOSED: "HatClosed",
    DrumPiece.HAT_PEDAL: "HatPedal",
    DrumPiece.TOM_LOW: "TomLow",
    DrumPiece.HAT_OPEN: "HatOpen",
    DrumPiece.TOM_HIGH: "TomHigh",
    DrumPiece.CRASH: "Crash",
    DrumPiece.RIDE: "Ride",
    DrumPiece.RIDE_BELL: "RideBell",
}


def split_ticks(ticks: int) -> list[int]:
    """A gap in ticks -> plain alphaTex durations (anything under a 32nd is dropped)."""
    out = []
    for size, dur in DURATIONS:
        while ticks >= size:
            out.append(dur)
            ticks -= size
    return out


def _note_text(n: ScoreNote) -> str:
    fx = "{" + " ".join(sorted(n.effects)) + "}" if n.effects else ""
    return f"{n.fret}.{n.string}{fx}"


class AlphaTexWriter:
    extension = "atex"

    def write(self, song: Song) -> str:
        lines = []
        if song.title:
            lines.append(f'\\title "{song.title}"')
        lines.append(f"\\tempo {round(song.tempo_bpm)}")
        lines.append(f"\\ts {song.beats_per_bar} {song.beat_unit}")
        lines.append(".")
        chords = {c.start: c.label for c in song.chords}
        chord_part = next((p for p in song.parts if p.instrument.role is Role.GUITAR), None)
        for part in song.parts:
            lines += self._header(part)
            lines += self._bars(part, song, chords if part is chord_part else {})
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _header(part: Part) -> list[str]:
        inst = part.instrument
        if isinstance(part, DrumPart):
            out = [f'\\track "{inst.name}" {{ instrument percussion }}', "\\clef neutral"]
            out += [f"\\articulation {name} {piece.value}" for piece, name in ARTICULATIONS.items()]
            return out
        name = INSTRUMENT_NAMES.get(inst.role, "Electric Guitar Clean")
        out = [f'\\track "{inst.name}" {{ instrument "{name}" }}', "\\staff {tabs}"]
        if inst.tuning is not None:
            out.append("\\tuning " + " ".join(pitch_name(p) for p in inst.tuning.strings))
        return out

    def _bars(self, part: Part, song: Song, chords: dict[int, str]) -> list[str]:
        # start tick -> (beat value text, length in ticks)
        events: dict[int, tuple[str, int]] = {}
        if isinstance(part, PitchedPart):
            by_start: dict[int, list[ScoreNote]] = {}
            for n in part.notes:
                if n.fretted:
                    by_start.setdefault(n.start, []).append(n)
            for start, group in by_start.items():
                texts = [_note_text(n) for n in sorted(group, key=lambda n: n.string)]
                head = texts[0] if len(texts) == 1 else "(" + " ".join(texts) + ")"
                events[start] = (head, max(n.duration for n in group))
        else:
            by_start_hits: dict[int, set[str]] = {}
            for h in part.hits:
                by_start_hits.setdefault(h.start, set()).add(ARTICULATIONS.get(h.piece, "Snare"))
            for start, names in by_start_hits.items():
                head = next(iter(names)) if len(names) == 1 else "(" + " ".join(sorted(names)) + ")"
                events[start] = (head, song.ticks_per_bar)  # hits ring until the next one

        bar = song.ticks_per_bar
        out = []
        for bar_start in range(0, song.length, bar):
            bar_end = bar_start + bar
            starts = sorted(s for s in events if bar_start <= s < bar_end)
            beats: list[str] = []
            cursor = bar_start
            for i, s in enumerate(starts):
                beats += [f"r.{d}" for d in split_ticks(s - cursor)]
                nxt = starts[i + 1] if i + 1 < len(starts) else bar_end
                head, length = events[s]
                sound = split_ticks(min(length, nxt - s)) or [32]
                beat = f"{head}.{sound[0]}"
                if s in chords:
                    beat += f' {{ch "{chords[s]}"}}'
                beats.append(beat)
                played = TICKS_PER_BEAT * 4 // sound[0]
                beats += [f"r.{d}" for d in split_ticks(nxt - s - played)]
                cursor = nxt
            beats += [f"r.{d}" for d in split_ticks(bar_end - cursor)]
            out.append(" ".join(beats) + " |")
        return out
