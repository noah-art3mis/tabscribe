"""Render a Song as plain-text tab (read-only export)."""

from __future__ import annotations

from .model import DRUMS, NOTE_NAMES, Song, Track


def _string_names(track: Track) -> list[str]:
    names = [NOTE_NAMES[p % 12] for p in track.tuning]
    if track.kind == "guitar" and names[0] == "E":
        names[0] = "e"  # tab convention: lowercase high e
    return names


def render_track(
    track: Track,
    song: Song,
    steps_per_beat: int = 4,
    bars_per_line: int = 4,
) -> str:
    """Quantise onsets to a grid (default 16ths) and draw bars of tab.

    The grid coarsens automatically when the notes allow it. Columns are 2
    characters wide, or 3 when any fret has two digits. Drums are drawn as
    one row per drum, with an x on each hit.
    """
    step = 60.0 / song.tempo / steps_per_beat
    drums = track.kind == "drums"
    placed = [n for n in track.notes if drums or n.fret is not None]
    if not placed:
        return ""

    while steps_per_beat > 1 and all(round(n.onset / step) % 2 == 0 for n in placed):
        steps_per_beat //= 2
        step *= 2
    steps_per_bar = steps_per_beat * song.beats_per_bar

    if drums:
        keys = [k for k in DRUMS if any(n.pitch == k for n in placed)]
        labels = [DRUMS[k][:5].ljust(5) for k in keys]
        row_of = {k: i for i, k in enumerate(keys)}
    else:
        labels = _string_names(track)
    grid: list[dict[int, str]] = [{} for _ in labels]
    for n in placed:
        s = round(n.onset / step)
        if drums:
            grid[row_of[n.pitch]][s] = "x"
        else:
            grid[n.string - 1][s] = str(n.fret)

    chord_at: dict[int, str] = {}
    if track.kind == "guitar":
        for start, _end, name in song.chords:
            chord_at.setdefault(round(start / step), name)

    total_steps = max(round(n.onset / step) for n in placed) + 1
    n_bars = -(-total_steps // steps_per_bar)
    col = 3 if not drums and any(n.fret >= 10 for n in placed) else 2
    pad = " " * (len(labels[0]) + 1)

    out: list[str] = [f"[{track.name}]"]
    for first in range(0, n_bars, bars_per_line):
        chord_line = pad
        rows = [f"{lab}|" for lab in labels]
        for b in range(first, min(first + bars_per_line, n_bars)):
            for s in range(b * steps_per_bar, (b + 1) * steps_per_bar):
                chord_line += chord_at.get(s, "").ljust(col)[:col]
                for i in range(len(labels)):
                    rows[i] += grid[i].get(s, "-").ljust(col, "-")
            chord_line += " "
            rows = [r + "|" for r in rows]
        if chord_line.strip():
            out.append(chord_line.rstrip())
        out += rows
        out.append("")
    return "\n".join(out)


def render(song: Song) -> str:
    return "\n".join(render_track(t, song) for t in song.tracks)
