"""Instruments, tunings and drum pieces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class Role(str, Enum):
    """What an instrument does in the band. Also names a separated stem."""

    GUITAR = "guitar"
    BASS = "bass"
    DRUMS = "drums"
    PIANO = "piano"
    VOCALS = "vocals"
    OTHER = "other"


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def pitch_name(midi: int) -> str:
    """60 -> 'C4'."""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


@dataclass(frozen=True)
class Tuning:
    """Open-string MIDI pitches, highest string first (string 1 = highest)."""

    strings: tuple[int, ...]
    max_fret: int = 24

    def __post_init__(self) -> None:
        if list(self.strings) != sorted(self.strings, reverse=True):
            raise ValueError("tuning must list strings from highest to lowest")

    @property
    def string_count(self) -> int:
        return len(self.strings)

    def positions(self, pitch: int) -> list[tuple[int, int]]:
        """Every (string, fret) that sounds `pitch`."""
        return [
            (i + 1, pitch - open_)
            for i, open_ in enumerate(self.strings)
            if 0 <= pitch - open_ <= self.max_fret
        ]


GUITAR_STANDARD = Tuning((64, 59, 55, 50, 45, 40))
BASS_STANDARD = Tuning((43, 38, 33, 28), max_fret=20)


@dataclass(frozen=True)
class Instrument:
    """A part to transcribe. `tuning` is None for unfretted roles (drums)."""

    role: Role
    name: str
    tuning: Tuning | None = None

    @property
    def fretted(self) -> bool:
        return self.tuning is not None


def guitar(name: str = "Guitar", tuning: Tuning = GUITAR_STANDARD) -> Instrument:
    return Instrument(Role.GUITAR, name, tuning)


def bass(name: str = "Bass", tuning: Tuning = BASS_STANDARD) -> Instrument:
    return Instrument(Role.BASS, name, tuning)


def drums(name: str = "Drums") -> Instrument:
    return Instrument(Role.DRUMS, name)


class DrumPiece(IntEnum):
    """Drum kit pieces, valued by their General MIDI key."""

    KICK = 36
    STICK = 37
    SNARE = 38
    TOM_FLOOR = 41
    HAT_CLOSED = 42
    HAT_PEDAL = 44
    TOM_LOW = 45
    HAT_OPEN = 46
    TOM_HIGH = 48
    CRASH = 49
    RIDE = 51
    RIDE_BELL = 53

    @classmethod
    def from_midi(cls, key: int) -> DrumPiece | None:
        try:
            return cls(key)
        except ValueError:
            return None
