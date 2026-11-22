"""What was played, in seconds. Produced by transcription, before notation.

Vocabulary: a *Track* lives in performance time (seconds); a *Part* lives
in score time (ticks). See domain/score.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .instruments import DrumPiece, Instrument, Role
from .rhythm import Seconds


@dataclass(frozen=True)
class NoteEvent:
    onset: Seconds
    offset: Seconds
    pitch: int  # MIDI
    velocity: float = 0.8  # 0..1
    confidence: float = 1.0  # 0..1, as reported by the model

    def __post_init__(self) -> None:
        if self.offset < self.onset:
            raise ValueError("note ends before it starts")


@dataclass(frozen=True)
class DrumHit:
    onset: Seconds
    piece: DrumPiece
    velocity: float = 0.8
    confidence: float = 1.0


@dataclass
class PitchedTrack:
    instrument: Instrument
    notes: list[NoteEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.instrument.role is Role.DRUMS:
            raise ValueError("drums belong in a DrumTrack")


@dataclass
class DrumTrack:
    instrument: Instrument
    hits: list[DrumHit] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.instrument.role is not Role.DRUMS:
            raise ValueError("DrumTrack needs a drums instrument")


Track = PitchedTrack | DrumTrack


@dataclass(frozen=True)
class ChordSegment:
    start: Seconds
    end: Seconds
    label: str  # e.g. "Am", "G7", "N" for no chord


@dataclass(frozen=True)
class Harmony:
    key: str | None = None  # e.g. "A minor"
    chords: tuple[ChordSegment, ...] = ()
