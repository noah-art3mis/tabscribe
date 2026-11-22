"""FretAssigner: pick fingerings that keep the hand still.

Notes starting together form a chord. For each chord we list candidate
fingerings (one string per note, within a hand span), then run dynamic
programming over the chords.

The hand covers `max_span` frets. Instead of guessing where it is, we track
the *range* of hand positions consistent with the notes played since it
last moved. A new fingering that fits that range costs nothing and narrows
it; one that doesn't forces a shift, costing the distance moved. Open
strings fit anywhere. A small penalty for height keeps parts low on the
neck when everything else is equal.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import groupby, product

from ...domain import ScoreNote, Tuning

Fingering = tuple[tuple[int, int], ...]  # (string, fret) per note, in chord order
Window = tuple[int, int]  # inclusive range of possible index-finger frets


class MinMovementFretter:
    def __init__(self, max_span: int = 4, move_weight: float = 2.0,
                 height_weight: float = 0.05, beam: int = 12):
        self.max_span = max_span  # frets the hand covers without shifting
        self.move_weight = move_weight  # cost per fret of hand shift
        self.height_weight = height_weight  # cost per fret of average height
        self.beam = beam  # candidate fingerings kept per chord

    def _candidates(self, chord: list[ScoreNote], tuning: Tuning) -> list[Fingering]:
        options = [[(n.string, n.fret)] if n.fretted else tuning.positions(n.pitch) for n in chord]
        found = []
        for combo in product(*options):
            strings = [s for s, _ in combo]
            fretted = [f for _, f in combo if f > 0]
            if len(set(strings)) < len(strings):
                continue  # two notes on one string
            if fretted and max(fretted) - min(fretted) > self.max_span:
                continue
            found.append(combo)
        found.sort(key=self._shape_cost)
        return found[: self.beam]

    def _shape_cost(self, fingering: Fingering) -> float:
        fretted = [f for _, f in fingering if f > 0]
        span = max(fretted) - min(fretted) if fretted else 0
        return 0.5 * span + self.height_weight * sum(fretted) / max(len(fretted), 1)

    def _window(self, fingering: Fingering, max_fret: int) -> Window | None:
        """Hand positions that can reach every fretted note; None if all open."""
        fretted = [f for _, f in fingering if f > 0]
        if not fretted:
            return None
        return max(1, max(fretted) - self.max_span), min(min(fretted), max_fret)

    @staticmethod
    def _move(current: Window, new: Window | None) -> tuple[float, Window]:
        if new is None:
            return 0.0, current
        a, b = current
        c, d = new
        if c <= b and a <= d:  # overlap: no shift, position is now better known
            return 0.0, (max(a, c), min(b, d))
        return float(c - b if c > b else a - d), new

    def assign(self, notes: Sequence[ScoreNote], tuning: Tuning) -> list[ScoreNote]:
        ordered = sorted(notes, key=lambda n: (n.start, -n.pitch))
        chords = [list(g) for _, g in groupby(ordered, key=lambda n: n.start)]

        # DP over chords. State: (total cost, hand window, chosen fingerings).
        start_window: Window = (1, tuning.max_fret)
        states: list[tuple[float, Window, list[Fingering | None]]] = [(0.0, start_window, [])]
        for chord in chords:
            cands = self._candidates(chord, tuning)
            if not cands:  # unplayable on this tuning: leave unfretted
                states = [(c, w, path + [None]) for c, w, path in states]
                continue
            # Keep the cheapest path per (fingering, hand window): two paths to
            # the same fingering can leave the hand in different places.
            best: dict[tuple[Fingering, Window], tuple[float, Window, list]] = {}
            for fingering in cands:
                target = self._window(fingering, tuning.max_fret)
                shape = self._shape_cost(fingering)
                for cost, window, path in states:
                    move, new_window = self._move(window, target)
                    total = cost + self.move_weight * move + shape
                    key = (fingering, new_window)
                    if key not in best or total < best[key][0]:
                        best[key] = (total, new_window, path + [fingering])
            states = sorted(best.values(), key=lambda s: s[0])[: self.beam * 8]

        _, _, path = min(states, key=lambda s: s[0])
        out: list[ScoreNote] = []
        for chord, fingering in zip(chords, path):
            if fingering is None:
                out += chord
            else:
                out += [n.at(s, f) for n, (s, f) in zip(chord, fingering)]
        return out
