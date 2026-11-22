"""Notation-level model, in ticks. This is what writers and editors work on.

`Song` is the aggregate root: one song, its timing, chord symbols and parts.
Times are absolute ticks from beat 1 of bar 1 (TICKS_PER_BEAT per beat).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .instruments import DrumPiece, Instrument, Role
from .rhythm import TICKS_PER_BEAT, Ticks


@dataclass(frozen=True)
class ScoreNote:
    start: Ticks
    duration: Ticks
    pitch: int
    string: int | None = None  # 1 = highest; None until fretted
    fret: int | None = None
    effects: frozenset[str] = frozenset()  # e.g. {"h", "pm"}; alphaTex names

    @property
    def fretted(self) -> bool:
        return self.string is not None and self.fret is not None

    def at(self, string: int, fret: int) -> ScoreNote:
        return replace(self, string=string, fret=fret)


@dataclass(frozen=True)
class ScoreHit:
    start: Ticks
    piece: DrumPiece
    accent: bool = False


@dataclass(frozen=True)
class ChordSymbol:
    start: Ticks
    label: str


@dataclass
class PitchedPart:
    instrument: Instrument
    notes: list[ScoreNote] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.instrument.role is Role.DRUMS:
            raise ValueError("drums belong in a DrumPart")


@dataclass
class DrumPart:
    instrument: Instrument
    hits: list[ScoreHit] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.instrument.role is not Role.DRUMS:
            raise ValueError("DrumPart needs a drums instrument")


Part = PitchedPart | DrumPart


@dataclass
class Song:
    title: str = ""
    tempo_bpm: float = 120.0
    beats_per_bar: int = 4
    beat_unit: int = 4
    chords: list[ChordSymbol] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)

    @property
    def ticks_per_bar(self) -> Ticks:
        return TICKS_PER_BEAT * self.beats_per_bar

    @property
    def length(self) -> Ticks:
        """End of the last event, rounded up to a whole bar."""
        ends = [c.start for c in self.chords]
        for part in self.parts:
            if isinstance(part, PitchedPart):
                ends += [n.start + n.duration for n in part.notes]
            else:
                ends += [h.start + 1 for h in part.hits]
        last = max(ends, default=0)
        return -(-last // self.ticks_per_bar) * self.ticks_per_bar or self.ticks_per_bar
