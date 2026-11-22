"""Quantizer: snap onsets to the nearest grid line, following tempo drift."""

from __future__ import annotations

from collections.abc import Sequence

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


class GridQuantizer:
    """`subdivision` grid lines per beat (4 = 16ths). Events below
    `min_confidence` are dropped. Events before beat 1 of bar 1 (pickups)
    are dropped for now."""

    def __init__(self, subdivision: int = 4, min_confidence: float = 0.0):
        if TICKS_PER_BEAT % subdivision:
            raise ValueError(f"subdivision must divide {TICKS_PER_BEAT}")
        self.step = TICKS_PER_BEAT // subdivision
        self.min_confidence = min_confidence

    def _tick(self, rhythm: Rhythm, t: float) -> int:
        return round(rhythm.beats_at(t) * TICKS_PER_BEAT / self.step) * self.step

    def quantize(
        self, tracks: Sequence[Track], rhythm: Rhythm, harmony: Harmony, title: str
    ) -> Song:
        parts = []
        for track in tracks:
            if isinstance(track, DrumTrack):
                hits = {
                    (self._tick(rhythm, h.onset), h.piece)
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
                    start = self._tick(rhythm, n.onset)
                    end = max(self._tick(rhythm, n.offset), start + self.step)
                    if start >= 0:
                        notes.setdefault((start, n.pitch), ScoreNote(start, end - start, n.pitch))
                parts.append(PitchedPart(track.instrument, [notes[k] for k in sorted(notes)]))

        chords: list[ChordSymbol] = []
        for seg in harmony.chords:
            start = self._tick(rhythm, seg.start)
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
