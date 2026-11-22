"""Export a Song to alphaTex (.atex), the editable source of truth.

Timing is quantised to a 16th-note grid. Each note lasts until the next
onset in its track, rounded down to a plain duration (whole..16th); any
leftover time becomes rests. Good enough for a draft you then clean up.
"""

from __future__ import annotations

from .model import DRUMS, Note, Song, Track, pitch_name

STEPS_PER_BEAT = 4  # 16th-note grid
# (steps, alphaTex duration), longest first
DURATIONS = ((16, 1), (8, 2), (4, 4), (2, 8), (1, 16))

INSTRUMENT = {
    "guitar": "Electric Guitar Clean",
    "bass": "Electric Bass Finger",
}


def _fill(steps: int) -> list[int]:
    """Split a gap of `steps` 16ths into plain durations."""
    out = []
    for size, dur in DURATIONS:
        while steps >= size:
            out.append(dur)
            steps -= size
    return out


def _note_value(n: Note, track: Track) -> str:
    if track.kind == "drums":
        return DRUMS.get(n.pitch, "Snare")
    return f"{n.fret}.{n.string}"


def _track_body(track: Track, song: Song) -> list[str]:
    step = 60.0 / song.tempo / STEPS_PER_BEAT
    bar_steps = STEPS_PER_BEAT * song.beats_per_bar

    usable = [n for n in track.notes if track.kind == "drums" or n.fret is not None]
    by_step: dict[int, list[Note]] = {}
    for n in usable:
        by_step.setdefault(round(n.onset / step), []).append(n)

    chord_at: dict[int, str] = {}
    for start, _end, name in song.chords:
        chord_at.setdefault(round(start / step), name)

    last = max([*by_step, *chord_at], default=0)
    n_bars = last // bar_steps + 1
    bars: list[str] = []
    for b in range(n_bars):
        start, end = b * bar_steps, (b + 1) * bar_steps
        onsets = sorted(s for s in by_step if start <= s < end)
        beats: list[str] = []
        cursor = start
        for i, s in enumerate(onsets):
            beats += [f"r.{d}" for d in _fill(s - cursor)]
            nxt = onsets[i + 1] if i + 1 < len(onsets) else end
            parts = _fill(nxt - s)
            values = sorted({_note_value(n, track) for n in by_step[s]})
            head = values[0] if len(values) == 1 else "(" + " ".join(values) + ")"
            beat = f"{head}.{parts[0]}"
            if track.kind == "guitar" and s in chord_at:
                beat += f' {{ch "{chord_at[s]}"}}'
            beats.append(beat)
            beats += [f"r.{d}" for d in parts[1:]]
            cursor = nxt
        beats += [f"r.{d}" for d in _fill(end - cursor)]
        bars.append(" ".join(beats))
    return [bar + " |" for bar in bars]


def export(song: Song) -> str:
    lines = []
    if song.title:
        lines.append(f'\\title "{song.title}"')
    lines.append(f"\\tempo {round(song.tempo)}")
    lines.append(f"\\ts {song.beats_per_bar} 4")
    lines.append(".")

    for track in song.tracks:
        if track.kind == "drums":
            lines.append(f'\\track "{track.name}" {{ instrument percussion }}')
            lines.append("\\clef neutral")
            for key, name in DRUMS.items():
                lines.append(f"\\articulation {name} {key}")
        else:
            lines.append(f'\\track "{track.name}" {{ instrument "{INSTRUMENT[track.kind]}" }}')
            lines.append("\\staff {tabs}")
            lines.append("\\tuning " + " ".join(pitch_name(p) for p in track.tuning))
        lines += _track_body(track, song)
        lines.append("")
    return "\n".join(lines)
