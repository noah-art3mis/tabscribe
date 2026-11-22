"""Quantizer: snap onsets to the nearest grid line, following tempo drift.

Before snapping, three corrections to the analysed rhythm:

- Beat phase. Trackers sometimes put every beat on the off-beat. Kick,
  snare and note onsets decide between the grid and the half-shifted grid.
- Bar-line phase. Beat trackers often get the beats right but put beat 1
  in the wrong place (e.g. on beat 3). We pick the phase that puts the
  most chord changes on beat 1, with a smaller bonus if the music starts
  on beat 1, and a tie-break in favour of the tracker's own choice.
- Pickups. Notes before the first bar line are kept by starting the grid
  as many whole bars earlier as needed, instead of being dropped.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace

from ...domain import (
    TICKS_PER_BEAT,
    ChordSymbol,
    DrumPart,
    DrumTrack,
    Harmony,
    PitchedPart,
    Rhythm,
    ScoreHit,
    ScoreNote,
    Song,
    Track,
)


def _onsets(tracks: Sequence[Track]) -> list[float]:
    times = []
    for t in tracks:
        times += [h.onset for h in t.hits] if isinstance(t, DrumTrack) else [n.onset for n in t.notes]
    return sorted(times)


class GridQuantizer:
    """`subdivision` grid lines per beat (4 = 16ths). Events below
    `min_confidence` are dropped."""

    def __init__(self, subdivision: int = 4, min_confidence: float = 0.0,
                 fix_beat_phase: bool = True, fix_bar_phase: bool = True,
                 keep_pickups: bool = True):
        if TICKS_PER_BEAT % subdivision:
            raise ValueError(f"subdivision must divide {TICKS_PER_BEAT}")
        self.step = TICKS_PER_BEAT // subdivision
        self.min_confidence = min_confidence
        self.fix_beat_phase = fix_beat_phase
        self.fix_bar_phase = fix_bar_phase
        self.keep_pickups = keep_pickups

    # --- rhythm corrections -------------------------------------------------

    @staticmethod
    def best_beat_phase(rhythm: Rhythm, tracks: Sequence[Track]) -> Rhythm:
        """Beat trackers sometimes lock onto the off-beats ("and"s). Kick and
        snare hits, and note onsets, mostly fall on beats, so compare the
        detected grid with the same grid shifted half a beat and keep the one
        more of them line up with."""
        beats = rhythm.beat_times
        if len(beats) < 4:
            return rhythm
        half = [(a + b) / 2 for a, b in zip(beats, beats[1:])]
        anchors = []
        for t in tracks:
            if isinstance(t, DrumTrack):
                anchors += [h.onset for h in t.hits
                            if h.piece.name in ("KICK", "SNARE")]
            else:
                anchors += [n.onset for n in t.notes]
        if not anchors:
            return rhythm
        tolerance = 0.12 * 60.0 / rhythm.tempo_bpm

        def hits(grid: Sequence[float]) -> int:
            from bisect import bisect_left
            count = 0
            for a in anchors:
                i = bisect_left(grid, a)
                near = [grid[j] for j in (i - 1, i) if 0 <= j < len(grid)]
                count += any(abs(a - g) <= tolerance for g in near)
            return count

        if hits(half) > 1.5 * hits(beats):  # clear evidence only
            step = (beats[1] - beats[0]) / 2
            shifted = tuple([max(0.0, beats[0] - step)] + half)
            downbeats = tuple(min(shifted, key=lambda s: abs(s - (d - step)))
                              for d in rhythm.downbeat_times)
            return replace(rhythm, beat_times=shifted, downbeat_times=downbeats)
        return rhythm

    def best_bar_phase(self, rhythm: Rhythm, harmony: Harmony, first_onset: float | None) -> Rhythm:
        beats, per_bar = rhythm.beat_times, rhythm.beats_per_bar
        if len(beats) < per_bar * 2:
            return rhythm
        tolerance = 0.25 * 60.0 / rhythm.tempo_bpm  # a quarter of a beat
        current = beats.index(rhythm.downbeat_times[0]) % per_bar if rhythm.downbeat_times and \
            rhythm.downbeat_times[0] in beats else 0
        changes = [c.start for c in harmony.chords[1:]
                   if c.label != "N"]  # the first segment's start says nothing

        def score(phase: int) -> float:
            bar_starts = beats[phase::per_bar]
            hit = sum(any(abs(t - b) <= tolerance for b in bar_starts) for t in changes)
            starts_on_one = first_onset is not None and any(
                abs(first_onset - b) <= tolerance for b in bar_starts[:1])
            return hit + 0.5 * starts_on_one + 0.25 * (phase == current)

        phase = max(range(per_bar), key=score)
        return replace(rhythm, downbeat_times=tuple(beats[phase::per_bar]))

    # --- quantizing -----------------------------------------------------------

    def _tick(self, rhythm: Rhythm, t: float, shift: int) -> int:
        return round(rhythm.beats_at(t) * TICKS_PER_BEAT / self.step) * self.step + shift

    def quantize(
        self, tracks: Sequence[Track], rhythm: Rhythm, harmony: Harmony, title: str
    ) -> Song:
        onsets = _onsets(tracks)
        if self.fix_beat_phase:
            rhythm = self.best_beat_phase(rhythm, tracks)
        if self.fix_bar_phase:
            rhythm = self.best_bar_phase(rhythm, harmony, onsets[0] if onsets else None)

        shift = 0  # ticks added so that pickups land in a bar of their own
        if self.keep_pickups and onsets:
            earliest = rhythm.beats_at(onsets[0]) * TICKS_PER_BEAT
            bar = rhythm.ticks_per_bar
            if earliest < -self.step / 2:
                shift = math.ceil(-earliest / bar) * bar

        parts = []
        for track in tracks:
            if isinstance(track, DrumTrack):
                hits = {
                    (self._tick(rhythm, h.onset, shift), h.piece)
                    for h in track.hits
                    if h.confidence >= self.min_confidence
                }
                parts.append(DrumPart(
                    track.instrument,
                    [ScoreHit(start, piece) for start, piece in sorted(hits) if start >= 0],
                ))
            else:
                notes: dict[tuple[int, int], ScoreNote] = {}
                for n in track.notes:
                    if n.confidence < self.min_confidence:
                        continue
                    start = self._tick(rhythm, n.onset, shift)
                    end = max(self._tick(rhythm, n.offset, shift), start + self.step)
                    if start >= 0:
                        notes.setdefault((start, n.pitch), ScoreNote(start, end - start, n.pitch))
                parts.append(PitchedPart(track.instrument, [notes[k] for k in sorted(notes)]))

        chords: list[ChordSymbol] = []
        for seg in harmony.chords:
            start = self._tick(rhythm, seg.start, shift)
            if seg.label == "N" or start < 0 or (chords and chords[-1].label == seg.label):
                continue
            chords.append(ChordSymbol(start, seg.label))

        return Song(
            title=title,
            tempo_bpm=rhythm.tempo_bpm,
            beats_per_bar=rhythm.beats_per_bar,
            beat_unit=rhythm.beat_unit,
            chords=chords,
            parts=parts,
        )
