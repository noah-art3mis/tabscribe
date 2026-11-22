"""Use case: transcribe a recording into a Song.

The pipeline only knows the ports. Which adapter fills each port is decided
by whoever builds it (see application/config.py).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from ..domain import (
    AudioRef,
    DrumTrack,
    Harmony,
    Instrument,
    PitchedPart,
    PitchedTrack,
    Role,
    Song,
    StemSet,
    Track,
)
from .ports import (
    DrumTranscriber,
    FretAssigner,
    HarmonyAnalyzer,
    MixTranscriber,
    PitchTranscriber,
    Quantizer,
    Refiner,
    RhythmAnalyzer,
    SourceSeparator,
)


class PipelineConfigError(ValueError):
    pass


@dataclass
class TranscriptionPipeline:
    instruments: Sequence[Instrument]
    rhythm: RhythmAnalyzer
    quantizer: Quantizer
    fretter: FretAssigner
    # Either a MixTranscriber, or a separator plus the per-stem transcribers.
    mix_transcriber: MixTranscriber | None = None
    separator: SourceSeparator | None = None
    pitch: PitchTranscriber | None = None
    drums: DrumTranscriber | None = None
    harmony: HarmonyAnalyzer | None = None
    refiners: Sequence[Refiner] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.instruments:
            raise PipelineConfigError("no instruments requested")
        if self.mix_transcriber is not None:
            return
        if self.separator is None:
            raise PipelineConfigError("need a mix_transcriber or a separator")
        if self.pitch is None and any(i.role is not Role.DRUMS for i in self.instruments):
            raise PipelineConfigError("pitched instruments requested but no pitch transcriber")
        if self.drums is None and any(i.role is Role.DRUMS for i in self.instruments):
            raise PipelineConfigError("drums requested but no drum transcriber")

    # Stages are separate methods so callers (or tests) can run them one at a time.

    def separate(self, mix: AudioRef, workdir: Path) -> StemSet:
        """Stems for the requested instruments (empty with an end-to-end model)."""
        if self.mix_transcriber is not None:
            return {}
        roles = list(dict.fromkeys(i.role for i in self.instruments))
        return self.separator.separate(mix, roles, workdir)

    def transcribe(self, mix: AudioRef, workdir: Path, stems: StemSet | None = None) -> list[Track]:
        if self.mix_transcriber is not None:
            return self.mix_transcriber.transcribe(mix, self.instruments)
        if stems is None:
            stems = self.separate(mix, workdir)
        tracks: list[Track] = []
        for inst in self.instruments:
            stem = stems.get(inst.role)
            if stem is None:
                continue  # separator can't produce this role
            if inst.role is Role.DRUMS:
                tracks.append(DrumTrack(inst, self.drums.transcribe(stem)))
            else:
                tracks.append(PitchedTrack(inst, self.pitch.transcribe(stem, inst)))
        return tracks

    def fret(self, song: Song) -> Song:
        parts = []
        for part in song.parts:
            if isinstance(part, PitchedPart) and part.instrument.tuning is not None:
                part = PitchedPart(
                    part.instrument, self.fretter.assign(part.notes, part.instrument.tuning)
                )
            parts.append(part)
        return replace(song, parts=parts)

    def refine(self, song: Song) -> Song:
        for refiner in self.refiners:
            song = refiner.refine(song)
        return song

    def run(
        self,
        mix: AudioRef,
        workdir: Path,
        title: str = "",
        observe: Callable[[str, object], None] | None = None,
    ) -> Song:
        """Run every stage. `observe(stage_name, output)` is called after each
        stage, e.g. to save intermediate results for inspection."""
        seen = observe or (lambda _stage, _output: None)
        workdir.mkdir(parents=True, exist_ok=True)

        rhythm = self.rhythm.analyze(mix)
        seen("1_rhythm", rhythm)
        harmony = self.harmony.analyze(mix, rhythm) if self.harmony else Harmony()
        seen("2_harmony", harmony)
        stems = self.separate(mix, workdir)
        seen("3_stems", stems)
        tracks = self.transcribe(mix, workdir, stems)
        seen("4_tracks", tracks)
        song = self.quantizer.quantize(tracks, rhythm, harmony, title or mix.path.stem)
        seen("5_quantized", song)
        song = self.fret(song)
        seen("6_fretted", song)
        song = self.refine(song)
        seen("7_refined", song)
        return song
