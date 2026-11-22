"""Deterministic stand-ins for the ML stages, for tests and for trying the
pipeline without installing any models. Configure them like real adapters:

    [stages]
    separator = "tabscribe.adapters.testing.fakes:FakeSeparator"
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ...domain import (
    AudioRef,
    ChordSegment,
    DrumHit,
    DrumPiece,
    DrumTrack,
    Harmony,
    Instrument,
    NoteEvent,
    PitchedTrack,
    Rhythm,
    Role,
    StemSet,
    Track,
)

TEMPO = 100.0
BEAT = 60.0 / TEMPO
PROGRESSION = [("C", 48), ("G", 43), ("Am", 45), ("F", 41)]  # chord, bass root (MIDI)
TRIADS = {"C": (48, 52, 55, 60), "G": (43, 47, 50, 55), "Am": (45, 52, 57, 60), "F": (53, 57, 60, 65)}


class FakeSeparator:
    """Pretends every requested role is a stem: returns the mix for each."""

    def separate(self, mix: AudioRef, roles: Sequence[Role], workdir: Path) -> StemSet:
        return {role: mix for role in roles}


class FakeRhythm:
    """Steady 100 bpm in 4/4, with slight drift to exercise the quantizer."""

    def __init__(self, drift: float = 0.004, bars: int = 4):
        self.drift = drift
        self.bars = bars

    def analyze(self, mix: AudioRef) -> Rhythm:
        times, t = [], 0.0
        for i in range(self.bars * 4 + 1):
            times.append(round(t, 4))
            t += BEAT * (1 + self.drift * (i % 2))
        return Rhythm(TEMPO, beat_times=tuple(times), downbeat_times=tuple(times[::4]))


class FakeHarmony:
    def analyze(self, mix: AudioRef, rhythm: Rhythm) -> Harmony:
        bar = [rhythm.beat_times[i] for i in range(0, len(rhythm.beat_times), 4)]
        return Harmony("C major", tuple(
            ChordSegment(bar[i], bar[i + 1], name) for i, (name, _) in enumerate(PROGRESSION)
        ))


def _jitter(i: int) -> float:
    return ((i * 37) % 7 - 3) * 0.004  # a few ms early or late, like a real player


class FakePitch:
    """Guitar: eighth-note arpeggios. Bass: quarter-note roots."""

    def transcribe(self, stem: AudioRef, instrument: Instrument) -> list[NoteEvent]:
        notes, i = [], 0
        for bar, (name, root) in enumerate(PROGRESSION):
            t0 = bar * 4 * BEAT
            if instrument.role is Role.BASS:
                for beat in range(4):
                    on = t0 + beat * BEAT + _jitter(i)
                    notes.append(NoteEvent(on, on + BEAT * 0.9, root - 12)); i += 1
            else:
                triad = TRIADS[name]
                for k in range(8):
                    on = t0 + k * BEAT / 2 + _jitter(i)
                    notes.append(NoteEvent(on, on + BEAT / 2 * 0.9, triad[k % 4])); i += 1
        return notes


class FakeDrums:
    """Rock beat: hats on 8ths, kick on 1 and 3, snare on 2 and 4."""

    def transcribe(self, stem: AudioRef) -> list[DrumHit]:
        hits, i = [], 0
        for k in range(len(PROGRESSION) * 8):
            on = k * BEAT / 2 + _jitter(i); i += 1
            hits.append(DrumHit(on, DrumPiece.HAT_CLOSED))
            if k % 4 == 0:
                hits.append(DrumHit(on, DrumPiece.KICK))
            elif k % 4 == 2:
                hits.append(DrumHit(on, DrumPiece.SNARE))
        return hits


class FakeMixTranscriber:
    """End-to-end stand-in: one call, all tracks."""

    def transcribe(self, mix: AudioRef, instruments: Sequence[Instrument]) -> list[Track]:
        tracks: list[Track] = []
        for inst in instruments:
            if inst.role is Role.DRUMS:
                tracks.append(DrumTrack(inst, FakeDrums().transcribe(mix)))
            else:
                tracks.append(PitchedTrack(inst, FakePitch().transcribe(mix, inst)))
        return tracks
