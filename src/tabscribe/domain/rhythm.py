"""Musical time: how seconds in the recording map to beats and bars."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

Seconds = float
Ticks = int

TICKS_PER_BEAT: Ticks = 48  # divisible by 16ths (12), 32nds (6) and 8th triplets (16)


@dataclass(frozen=True)
class Rhythm:
    """Beat grid of a recording.

    `beat_times` and `downbeat_times` are in seconds. When `beat_times` is
    empty, the grid is a constant `tempo_bpm` starting at 0. Real recordings
    drift, so analysers should fill `beat_times` when they can.
    """

    tempo_bpm: float
    beats_per_bar: int = 4
    beat_unit: int = 4
    beat_times: tuple[Seconds, ...] = ()
    downbeat_times: tuple[Seconds, ...] = ()

    def __post_init__(self) -> None:
        if self.tempo_bpm <= 0:
            raise ValueError("tempo must be positive")
        if list(self.beat_times) != sorted(self.beat_times):
            raise ValueError("beat_times must be increasing")

    @property
    def ticks_per_bar(self) -> Ticks:
        return TICKS_PER_BEAT * self.beats_per_bar

    @property
    def origin(self) -> Seconds:
        """Time of beat 1 of bar 1. Anything earlier is a pickup."""
        if self.downbeat_times:
            return self.downbeat_times[0]
        return self.beat_times[0] if self.beat_times else 0.0

    def beats_at(self, t: Seconds) -> float:
        """Position of `t` in beats from `origin`, following tempo drift."""
        return self._beat_index(t) - self._beat_index(self.origin)

    def _beat_index(self, t: Seconds) -> float:
        beats = self.beat_times
        if len(beats) < 2:
            return t * self.tempo_bpm / 60.0
        i = bisect_right(beats, t) - 1
        i = min(max(i, 0), len(beats) - 2)  # extrapolate with edge intervals
        return i + (t - beats[i]) / (beats[i + 1] - beats[i])
