"""Render notes as plain-text guitar tab."""

from __future__ import annotations

from .pipeline import Analysis, Note

STRING_NAMES = ("e", "B", "G", "D", "A", "E")  # string 1 = high e


def render(
    notes: list[Note],
    analysis: Analysis,
    steps_per_beat: int = 4,
    beats_per_bar: int = 4,
    bars_per_line: int = 4,
) -> str:
    """Quantise onsets to a grid (default 16th notes) and draw bars of tab.

    The grid coarsens automatically when the notes allow it. Columns are 2
    characters wide, or 3 when any fret has two digits.
    Chord names from `analysis.chords` are written above the bar they start in.
    """
    tempo = analysis.tempo or 120.0
    step = 60.0 / tempo / steps_per_beat

    placed = [n for n in notes if n.string is not None and n.fret is not None]
    if not placed:
        return ""

    # Use the coarsest grid that still fits every onset (e.g. 8ths, not 16ths).
    while steps_per_beat > 1 and all(round(n.onset / step) % 2 == 0 for n in placed):
        steps_per_beat //= 2
        step *= 2
    steps_per_bar = steps_per_beat * beats_per_bar

    total_steps = max(round(n.onset / step) for n in placed) + 1
    n_bars = -(-total_steps // steps_per_bar)

    # grid[string_index][step] -> fret text
    grid: list[dict[int, str]] = [{} for _ in STRING_NAMES]
    for n in placed:
        grid[n.string - 1][round(n.onset / step)] = str(n.fret)

    chord_at: dict[int, str] = {}
    for start, _end, name in analysis.chords:
        chord_at.setdefault(round(start / step), name)

    col = 3 if any(n.fret >= 10 for n in placed) else 2
    lines_out: list[str] = []
    for first_bar in range(0, n_bars, bars_per_line):
        bars = range(first_bar, min(first_bar + bars_per_line, n_bars))
        chord_line = "  "
        rows = [f"{name}|" for name in STRING_NAMES]
        for b in bars:
            for s in range(b * steps_per_bar, (b + 1) * steps_per_bar):
                chord_line += chord_at.get(s, "").ljust(col)[:col]
                for i in range(len(STRING_NAMES)):
                    rows[i] += grid[i].get(s, "-").ljust(col, "-")
            chord_line += " "
            rows = [r + "|" for r in rows]
        if chord_line.strip():
            lines_out.append(chord_line.rstrip())
        lines_out.extend(rows)
        lines_out.append("")
    return "\n".join(lines_out)
