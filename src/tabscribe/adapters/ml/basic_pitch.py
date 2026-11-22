"""PitchTranscriber using Basic Pitch (Spotify).

Model: a small polyphonic note transcriber, instrument-agnostic.
Install: pip install basic-pitch onnxruntime   (the ONNX model ships with it;
TensorFlow is not needed)
License: CC BY-NC 4.0 (non-commercial use only).

Known weakness: it reports strong overtones of a note as extra, quieter
notes (an octave, a twelfth, two octaves above). `overtone_ratio` removes a
note when a louder note is sounding at an overtone interval below it and the
note's confidence is below that fraction of the louder one. Real notes in
chords (e.g. the octaves in an open E chord) have similar confidence to their
neighbours, so they survive. Set it to None to keep everything.

`relative_floor` then drops faint ghost notes: anything below that fraction
of the part's median confidence. Both values were tuned on evals/cases
(see `tabscribe eval`).
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from ...domain import AudioRef, Instrument, NoteEvent

# Semitones from a fundamental to its 2nd..6th harmonics.
OVERTONES = (12, 19, 24, 28, 31)


def suppress_overtones(notes: Sequence[NoteEvent], ratio: float,
                       slack: float = 0.05) -> list[NoteEvent]:
    """Drop notes that look like overtones of a louder, lower note sounding
    at the same time (within `slack` seconds of its start)."""
    kept = []
    for n in notes:
        is_overtone = any(
            m.pitch == n.pitch - interval
            and m.onset - slack <= n.onset <= m.offset
            and n.confidence < ratio * m.confidence
            for m in notes
            for interval in OVERTONES
        )
        if not is_overtone:
            kept.append(n)
    return kept


class BasicPitchTranscriber:
    def __init__(self, onset_threshold: float = 0.5, frame_threshold: float = 0.3,
                 min_note_length_ms: float = 60.0, overtone_ratio: float | None = 0.8,
                 relative_floor: float | None = 0.65):
        self.onset_threshold = onset_threshold
        self.frame_threshold = frame_threshold
        self.min_note_length_ms = min_note_length_ms
        self.overtone_ratio = overtone_ratio
        self.relative_floor = relative_floor

    def raw(self, stem: AudioRef) -> list[NoteEvent]:
        """The model's notes before any filtering."""
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import predict  # heavy import, only when used

        _, _, events = predict(
            str(stem.path),
            ICASSP_2022_MODEL_PATH,
            onset_threshold=self.onset_threshold,
            frame_threshold=self.frame_threshold,
            minimum_note_length=self.min_note_length_ms,
        )
        return sorted(
            (NoteEvent(float(s), float(e), int(p), velocity=float(a), confidence=float(a))
             for s, e, p, a, *_ in events),
            key=lambda n: (n.onset, n.pitch),
        )

    def filter(self, notes: Sequence[NoteEvent], instrument: Instrument) -> list[NoteEvent]:
        tuning = instrument.tuning
        if tuning is not None:  # keep only what the instrument can play
            low, high = tuning.strings[-1], tuning.strings[0] + tuning.max_fret
            notes = [n for n in notes if low <= n.pitch <= high]
        if self.overtone_ratio is not None:
            notes = suppress_overtones(notes, self.overtone_ratio)
        if self.relative_floor is not None and notes:
            typical = statistics.median(n.confidence for n in notes)
            notes = [n for n in notes if n.confidence >= self.relative_floor * typical]
        return list(notes)

    def transcribe(self, stem: AudioRef, instrument: Instrument) -> list[NoteEvent]:
        return self.filter(self.raw(stem), instrument)
