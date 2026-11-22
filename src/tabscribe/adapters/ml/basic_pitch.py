"""PitchTranscriber using Basic Pitch (Spotify).

Model: a small polyphonic note transcriber, instrument-agnostic.
Install: pip install basic-pitch
License: CC BY-NC 4.0 (non-commercial use only).
Status: written against basic_pitch.inference.predict; not yet run in this repo.
"""

from __future__ import annotations

from ...domain import AudioRef, Instrument, NoteEvent


class BasicPitchTranscriber:
    def __init__(self, onset_threshold: float = 0.5, frame_threshold: float = 0.3,
                 min_note_length_ms: float = 60.0):
        self.onset_threshold = onset_threshold
        self.frame_threshold = frame_threshold
        self.min_note_length_ms = min_note_length_ms

    def transcribe(self, stem: AudioRef, instrument: Instrument) -> list[NoteEvent]:
        from basic_pitch.inference import predict  # heavy import, only when used

        _, _, events = predict(
            str(stem.path),
            onset_threshold=self.onset_threshold,
            frame_threshold=self.frame_threshold,
            minimum_note_length=self.min_note_length_ms,
        )
        # Keep only pitches the instrument can play.
        tuning = instrument.tuning
        low = tuning.strings[-1] if tuning else 0
        high = tuning.strings[0] + tuning.max_fret if tuning else 127
        notes = []
        for start, end, pitch, amplitude, *_ in events:
            if low <= pitch <= high:
                notes.append(NoteEvent(float(start), float(end), int(pitch),
                                       velocity=float(amplitude), confidence=float(amplitude)))
        return sorted(notes, key=lambda n: (n.onset, n.pitch))
