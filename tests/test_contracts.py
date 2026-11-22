"""Contract tests: every adapter must satisfy its port, and the pipeline
must work with any combination of adapters that do."""

import shutil
import subprocess
from pathlib import Path

import pytest

from tabscribe.adapters.fretting.min_movement import MinMovementFretter
from tabscribe.adapters.notation.alphatex import AlphaTexWriter
from tabscribe.adapters.notation.ascii_tab import AsciiTabWriter
from tabscribe.adapters.quantize.grid import GridQuantizer
from tabscribe.adapters.testing import fakes
from tabscribe.application import ports
from tabscribe.application.config import ADAPTERS, build_pipeline, load_config
from tabscribe.application.pipeline import PipelineConfigError, TranscriptionPipeline
from tabscribe.domain import (
    GUITAR_STANDARD,
    TICKS_PER_BEAT,
    AudioRef,
    DrumPart,
    NoteEvent,
    PitchedPart,
    PitchedTrack,
    Rhythm,
    Harmony,
    ScoreNote,
    bass,
    drums,
    guitar,
)

ROOT = Path(__file__).resolve().parents[1]
MIX = AudioRef(Path("song.wav"))


def fake_pipeline(**overrides):
    kwargs = dict(
        instruments=[guitar(), bass(), drums()],
        rhythm=fakes.FakeRhythm(),
        harmony=fakes.FakeHarmony(),
        quantizer=GridQuantizer(),
        fretter=MinMovementFretter(),
        separator=fakes.FakeSeparator(),
        pitch=fakes.FakePitch(),
        drums=fakes.FakeDrums(),
    )
    kwargs.update(overrides)
    return TranscriptionPipeline(**kwargs)


# --- every adapter implements its port -----------------------------------

@pytest.mark.parametrize("adapter, port", [
    (fakes.FakeSeparator(), ports.SourceSeparator),
    (fakes.FakeRhythm(), ports.RhythmAnalyzer),
    (fakes.FakeHarmony(), ports.HarmonyAnalyzer),
    (fakes.FakePitch(), ports.PitchTranscriber),
    (fakes.FakeDrums(), ports.DrumTranscriber),
    (fakes.FakeMixTranscriber(), ports.MixTranscriber),
    (GridQuantizer(), ports.Quantizer),
    (MinMovementFretter(), ports.FretAssigner),
    (AlphaTexWriter(), ports.SongWriter),
    (AsciiTabWriter(), ports.SongWriter),
])
def test_adapter_satisfies_port(adapter, port):
    assert isinstance(adapter, port)


def test_every_registered_adapter_imports():
    """Built-in names must point at real classes (ML libs are imported lazily)."""
    import importlib
    for name, target in ADAPTERS.items():
        module, cls = target.split(":")
        assert hasattr(importlib.import_module(module), cls), name


# --- pipeline wiring ------------------------------------------------------

def test_modular_and_end_to_end_paths_agree(tmp_path):
    modular = fake_pipeline().run(MIX, tmp_path)
    e2e = fake_pipeline(separator=None, pitch=None, drums=None,
                        mix_transcriber=fakes.FakeMixTranscriber()).run(MIX, tmp_path)
    assert AlphaTexWriter().write(modular) == AlphaTexWriter().write(e2e)


def test_pipeline_rejects_missing_stages():
    with pytest.raises(PipelineConfigError):
        fake_pipeline(separator=None)
    with pytest.raises(PipelineConfigError):
        fake_pipeline(drums=None)
    fake_pipeline(drums=None, instruments=[guitar()])  # fine without drums


def test_observer_sees_every_stage(tmp_path):
    seen = []
    fake_pipeline().run(MIX, tmp_path, observe=lambda stage, _: seen.append(stage))
    assert seen == ["1_rhythm", "2_harmony", "3_stems", "4_tracks", "5_quantized", "6_fretted", "7_refined"]


def test_refiners_run_in_order(tmp_path):
    class Tag:
        def __init__(self, s): self.s = s
        def refine(self, song):
            song.title += self.s
            return song
    song = fake_pipeline(refiners=[Tag("-a"), Tag("-b")]).run(MIX, tmp_path, title="x")
    assert song.title == "x-a-b"


def test_config_swaps_adapters_by_name_or_import_path(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text(
        '[stages]\nmix_transcriber = "tabscribe.adapters.testing.fakes:FakeMixTranscriber"\n'
        'rhythm = "fake_rhythm"\nharmony = "fake_harmony"\n'
    )
    pipeline = build_pipeline(load_config(cfg))
    assert pipeline.separator is None  # replaced by the end-to-end model
    assert isinstance(pipeline.mix_transcriber, fakes.FakeMixTranscriber)


# --- individual stage contracts --------------------------------------------

def test_quantizer_follows_tempo_drift():
    # Beats get slower; a note on beat 3 must still land on beat 3.
    rhythm = Rhythm(120, beat_times=(0.0, 0.5, 1.1, 1.8, 2.6))
    track = PitchedTrack(guitar(), [NoteEvent(1.1, 1.4, 64)])
    song = GridQuantizer().quantize([track], rhythm, Harmony(), "t")
    assert song.parts[0].notes[0].start == 2 * TICKS_PER_BEAT


def test_fretter_keeps_fixed_positions_and_stays_playable():
    notes = [ScoreNote(0, 24, 64, string=2, fret=5)] + [
        ScoreNote(24 * i, 24, p) for i, p in enumerate([67, 69, 71, 72], start=1)
    ]
    out = MinMovementFretter().assign(notes, GUITAR_STANDARD)
    assert (out[0].string, out[0].fret) == (2, 5)
    for n in out:
        assert GUITAR_STANDARD.strings[n.string - 1] + n.fret == n.pitch
    frets = [n.fret for n in out if n.fret]
    assert max(frets) - min(frets) <= 4


def test_fretter_leaves_unplayable_notes_unfretted():
    out = MinMovementFretter().assign([ScoreNote(0, 48, 20)], GUITAR_STANDARD)
    assert not out[0].fretted


def test_writers_handle_empty_parts():
    from tabscribe.domain import Song
    song = Song(parts=[PitchedPart(guitar()), DrumPart(drums())])
    AlphaTexWriter().write(song)
    AsciiTabWriter().write(song)


@pytest.mark.skipif(
    not (shutil.which("node") and (ROOT / "node_modules/@coderline/alphatab").exists()),
    reason="needs node and `npm install`",
)
def test_alphatex_output_parses_in_alphatab(tmp_path):
    path = tmp_path / "song.atex"
    path.write_text(AlphaTexWriter().write(fake_pipeline().run(MIX, tmp_path)))
    result = subprocess.run(["node", str(ROOT / "scripts/check_atex.mjs"), str(path)],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert "Guitar: 4 bars, 32 notes" in result.stdout
    assert "Drums: 4 bars, 48 notes" in result.stdout
