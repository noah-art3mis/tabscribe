"""RhythmAnalyzer and HarmonyAnalyzer using madmom.

Models: an RNN beat/downbeat tracker and a CNN+CRF chord recogniser.
Install: pip install git+https://github.com/CPJKU/madmom  (the PyPI release
does not support recent Python/NumPy versions).
Status: written against madmom's processors; not yet run in this repo.
"""

from __future__ import annotations

from ...domain import AudioRef, ChordSegment, Harmony, Rhythm

QUALITY = {"maj": "", "min": "m"}


def chord_label(madmom_label: str) -> str:
    """'A:min' -> 'Am', 'C:maj' -> 'C', 'N' -> 'N'."""
    if ":" not in madmom_label:
        return madmom_label
    root, quality = madmom_label.split(":", 1)
    return root + QUALITY.get(quality, quality)


class MadmomRhythm:
    def __init__(self, beats_per_bar: tuple[int, ...] = (3, 4), fps: int = 100):
        self.beats_per_bar = list(beats_per_bar)
        self.fps = fps

    def analyze(self, mix: AudioRef) -> Rhythm:
        from madmom.features.downbeats import DBNDownBeatTrackingProcessor, RNNDownBeatProcessor

        activations = RNNDownBeatProcessor()(str(mix.path))
        beats = DBNDownBeatTrackingProcessor(beats_per_bar=self.beats_per_bar, fps=self.fps)(activations)
        times = [float(t) for t, _ in beats]
        downbeats = [float(t) for t, n in beats if int(n) == 1]
        meter = int(max(n for _, n in beats)) if len(beats) else 4
        if len(times) >= 2:
            intervals = sorted(b - a for a, b in zip(times, times[1:]))
            tempo = 60.0 / intervals[len(intervals) // 2]  # median beat length
        else:
            tempo = 120.0
        return Rhythm(tempo, beats_per_bar=meter, beat_times=tuple(times),
                      downbeat_times=tuple(downbeats))


class MadmomChords:
    def analyze(self, mix: AudioRef, rhythm: Rhythm) -> Harmony:
        from madmom.audio.chroma import DeepChromaProcessor
        from madmom.features.chords import DeepChromaChordRecognitionProcessor

        chroma = DeepChromaProcessor()(str(mix.path))
        segments = DeepChromaChordRecognitionProcessor()(chroma)
        return Harmony(chords=tuple(
            ChordSegment(float(start), float(end), chord_label(label))
            for start, end, label in segments
        ))
