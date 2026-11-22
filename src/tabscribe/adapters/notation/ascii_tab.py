"""SongWriter for plain-text tab (read-only export).

Guitar/bass parts are drawn as tab; drum parts as one row per drum with an
x on each hit. The grid coarsens automatically when the notes allow it.
"""

from __future__ import annotations

from ...domain import TICKS_PER_BEAT, DrumPart, PitchedPart, Role, Song
from ...domain.instruments import NOTE_NAMES
from .alphatex import ARTICULATIONS


class AsciiTabWriter:
    extension = "txt"

    def __init__(self, bars_per_line: int = 4):
        self.bars_per_line = bars_per_line

    def write(self, song: Song) -> str:
        return "\n".join(self._part(p, song) for p in song.parts).rstrip() + "\n"

    def _part(self, part, song: Song) -> str:
        if isinstance(part, DrumPart):
            starts = [h.start for h in part.hits]
            pieces = [p for p in ARTICULATIONS if any(h.piece == p for h in part.hits)]
            labels = [ARTICULATIONS[p][:5].ljust(5) for p in pieces]
            cells = {(pieces.index(h.piece), h.start): "x" for h in part.hits}
            col = 2
        else:
            notes = [n for n in part.notes if n.fretted]
            starts = [n.start for n in notes]
            tuning = part.instrument.tuning
            labels = [NOTE_NAMES[p % 12] for p in tuning.strings] if tuning else []
            if part.instrument.role is Role.GUITAR and labels and labels[0] == "E":
                labels[0] = "e"
            cells = {(n.string - 1, n.start): str(n.fret) for n in notes}
            col = 3 if any(n.fret >= 10 for n in notes) else 2
        if not starts:
            return f"[{part.instrument.name}]\n(empty)\n"

        step = TICKS_PER_BEAT  # coarsest grid that fits every onset
        while step > 3 and any(s % step for s in starts):
            step //= 2
        if any(s % step for s in starts):
            step = 1
        show_chords = isinstance(part, PitchedPart) and part.instrument.role is Role.GUITAR
        chords = {c.start: c.label for c in song.chords} if show_chords else {}

        bar = song.ticks_per_bar
        n_bars = song.length // bar
        pad = " " * (len(labels[0]) + 1)
        out = [f"[{part.instrument.name}]"]
        for first in range(0, n_bars, self.bars_per_line):
            chord_line = pad
            rows = [f"{lab}|" for lab in labels]
            for b in range(first, min(first + self.bars_per_line, n_bars)):
                for t in range(b * bar, (b + 1) * bar, step):
                    label = next((chords[c] for c in chords if t <= c < t + step), "")
                    chord_line += label.ljust(col)[:col]
                    for i in range(len(labels)):
                        rows[i] += cells.get((i, t), "-").ljust(col, "-")
                chord_line += " "
                rows = [r + "|" for r in rows]
            if chord_line.strip():
                out.append(chord_line.rstrip())
            out += rows
            out.append("")
        return "\n".join(out)
