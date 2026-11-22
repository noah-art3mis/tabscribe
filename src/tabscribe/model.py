"""Song data model shared by every stage and exporter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["guitar", "bass", "drums"]

# MIDI pitches, highest string first (string 1 = highest).
GUITAR_STANDARD = (64, 59, 55, 50, 45, 40)
BASS_STANDARD = (43, 38, 33, 28)

# General MIDI drum keys -> short names used in alphaTex and text output.
DRUMS = {
    36: "Kick",
    38: "Snare",
    37: "Stick",
    42: "HatClosed",
    44: "HatPedal",
    46: "HatOpen",
    41: "TomFloor",
    45: "TomLow",
    48: "TomHigh",
    49: "Crash",
    51: "Ride",
    53: "RideBell",
}


@dataclass
class Note:
    onset: float  # seconds
    offset: float  # seconds
    pitch: int  # MIDI note number (GM drum key for drums)
    string: int | None = None  # 1 = highest string
    fret: int | None = None


@dataclass
class Track:
    name: str
    kind: Kind
    notes: list[Note] = field(default_factory=list)
    tuning: tuple[int, ...] = GUITAR_STANDARD

    @classmethod
    def guitar(cls, name: str = "Guitar") -> Track:
        return cls(name, "guitar", tuning=GUITAR_STANDARD)

    @classmethod
    def bass(cls, name: str = "Bass") -> Track:
        return cls(name, "bass", tuning=BASS_STANDARD)

    @classmethod
    def drums(cls, name: str = "Drums") -> Track:
        return cls(name, "drums", tuning=())


@dataclass
class Song:
    title: str = ""
    tempo: float = 120.0
    beats_per_bar: int = 4
    chords: list[tuple[float, float, str]] = field(default_factory=list)  # (start, end, name)
    tracks: list[Track] = field(default_factory=list)


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def pitch_name(midi: int) -> str:
    """60 -> 'C4'."""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"
