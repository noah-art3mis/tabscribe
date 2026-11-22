"""Stage contracts. Every pipeline stage is one of these protocols.

An adapter satisfies a port by having the method with the same signature;
no inheritance needed. Adapters must not mutate their inputs and must
return new objects.

    mix audio
      |-- SourceSeparator ----> StemSet ------------------------+
      |-- RhythmAnalyzer -----> Rhythm                          |
      |-- HarmonyAnalyzer ----> Harmony                         |
      |                                                         v
      |                   PitchTranscriber / DrumTranscriber --> Tracks
      |-- MixTranscriber (end-to-end alternative) ------------> Tracks
                                                                |
                      Quantizer (Tracks + Rhythm + Harmony) --> Song
                      FretAssigner (per pitched part) --------> Song
                      Refiner* (any Song -> Song cleanup) ----> Song
                      SongWriter -----------------------------> text
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..domain import (
    AudioRef,
    DrumHit,
    Harmony,
    Instrument,
    NoteEvent,
    Rhythm,
    Role,
    ScoreNote,
    Song,
    StemSet,
    Track,
    Tuning,
)


@runtime_checkable
class SourceSeparator(Protocol):
    """Mix -> one audio file per requested role.

    Must return a stem for every role in `roles` it supports and may omit
    the rest. Writes stems under `workdir`.
    """

    def separate(self, mix: AudioRef, roles: Sequence[Role], workdir: Path) -> StemSet: ...


@runtime_checkable
class RhythmAnalyzer(Protocol):
    """Mix -> tempo, meter, beat and downbeat times."""

    def analyze(self, mix: AudioRef) -> Rhythm: ...


@runtime_checkable
class HarmonyAnalyzer(Protocol):
    """Mix -> key and chord segments (seconds). `rhythm` may be used to align
    chord changes to beats."""

    def analyze(self, mix: AudioRef, rhythm: Rhythm) -> Harmony: ...


@runtime_checkable
class PitchTranscriber(Protocol):
    """One pitched stem -> note events (seconds).

    `instrument` tells the model what it is listening to (e.g. to restrict
    the pitch range). Output need not be quantised or fretted.
    """

    def transcribe(self, stem: AudioRef, instrument: Instrument) -> list[NoteEvent]: ...


@runtime_checkable
class DrumTranscriber(Protocol):
    """Drum stem -> drum hits (seconds)."""

    def transcribe(self, stem: AudioRef) -> list[DrumHit]: ...


@runtime_checkable
class MixTranscriber(Protocol):
    """End-to-end alternative to SourceSeparator + Pitch/DrumTranscriber:
    full mix -> one track per requested instrument it can produce.

    This is the slot for multi-instrument models such as MuScriptor.
    """

    def transcribe(self, mix: AudioRef, instruments: Sequence[Instrument]) -> list[Track]: ...


@runtime_checkable
class Quantizer(Protocol):
    """Performance (seconds) -> score (ticks): snap tracks and chords to the
    beat grid and build the Song. Pitched notes come out unfretted."""

    def quantize(
        self, tracks: Sequence[Track], rhythm: Rhythm, harmony: Harmony, title: str
    ) -> Song: ...


@runtime_checkable
class FretAssigner(Protocol):
    """Give every note a playable (string, fret) on `tuning`.

    Notes that already have a position must keep it. Notes that cannot be
    played on the tuning are returned unfretted (writers skip them).
    """

    def assign(self, notes: Sequence[ScoreNote], tuning: Tuning) -> list[ScoreNote]: ...


@runtime_checkable
class Refiner(Protocol):
    """Optional Song -> Song cleanup, run in order after fretting.

    The slot for anything that improves a draft: removing ghost notes,
    detecting hammer-ons, or an LLM pass that rewrites the tab.
    """

    def refine(self, song: Song) -> Song: ...


@runtime_checkable
class SongWriter(Protocol):
    """Song -> text in some notation format."""

    extension: str  # e.g. "atex", "txt"

    def write(self, song: Song) -> str: ...
