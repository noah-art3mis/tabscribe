"""Build a pipeline from configuration.

Each stage names an adapter, either a short name from ADAPTERS or any
importable "package.module:ClassName". Options under [adapters.<name>] are
passed to the adapter's constructor. So swapping in a new model is a
config change, not a code change:

    [stages]
    pitch = "basic_pitch"                 # built-in
    drums = "my_package.models:MyDrums"  # your own class

    [adapters.basic_pitch]
    onset_threshold = 0.6
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path
from typing import Any

from ..domain import Instrument, bass, drums, guitar
from .pipeline import TranscriptionPipeline

# Short names for built-in adapters. Imported lazily so heavy ML
# dependencies load only for the adapters actually configured.
ADAPTERS: dict[str, str] = {
    # stems
    "demucs": "tabscribe.adapters.ml.demucs:DemucsSeparator",
    "folder_stems": "tabscribe.adapters.audio.folder_stems:FolderStems",
    # rhythm and harmony
    "madmom_rhythm": "tabscribe.adapters.ml.madmom:MadmomRhythm",
    "madmom_chords": "tabscribe.adapters.ml.madmom:MadmomChords",
    # transcription
    "basic_pitch": "tabscribe.adapters.ml.basic_pitch:BasicPitchTranscriber",
    "adtof": "tabscribe.adapters.ml.adtof:AdtofDrums",
    "muscriptor": "tabscribe.adapters.ml.muscriptor:MuScriptorTranscriber",
    # score
    "grid": "tabscribe.adapters.quantize.grid:GridQuantizer",
    "min_movement": "tabscribe.adapters.fretting.min_movement:MinMovementFretter",
    # writers
    "alphatex": "tabscribe.adapters.notation.alphatex:AlphaTexWriter",
    "ascii": "tabscribe.adapters.notation.ascii_tab:AsciiTabWriter",
    # fakes: run the whole pipeline without any models (see examples/fake.toml)
    "fake_separator": "tabscribe.adapters.testing.fakes:FakeSeparator",
    "fake_rhythm": "tabscribe.adapters.testing.fakes:FakeRhythm",
    "fake_harmony": "tabscribe.adapters.testing.fakes:FakeHarmony",
    "fake_pitch": "tabscribe.adapters.testing.fakes:FakePitch",
    "fake_drums": "tabscribe.adapters.testing.fakes:FakeDrums",
    "fake_mix": "tabscribe.adapters.testing.fakes:FakeMixTranscriber",
}

DEFAULT_CONFIG = """
instruments = ["guitar", "bass", "drums"]
writers = ["alphatex", "ascii"]

[stages]
separator = "demucs"
rhythm = "madmom_rhythm"
harmony = "madmom_chords"
pitch = "basic_pitch"
drums = "adtof"
quantizer = "grid"
fretter = "min_movement"
refiners = []
# mix_transcriber = "muscriptor"   # replaces separator + pitch + drums
"""

INSTRUMENTS = {"guitar": guitar, "bass": bass, "drums": drums}
STAGES = ("separator", "rhythm", "harmony", "pitch", "drums", "mix_transcriber",
          "quantizer", "fretter")


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Defaults, overlaid with the user's file. User stages override default
    stages one by one; other top-level keys replace the defaults."""
    config = tomllib.loads(DEFAULT_CONFIG)
    if path is not None:
        user = tomllib.loads(path.read_text())
        config["stages"].update(user.pop("stages", {}))
        config.update(user)
    return config


def build(name: str, config: dict[str, Any]) -> Any:
    target = ADAPTERS.get(name, name)
    if ":" not in target:
        raise ValueError(f"unknown adapter {name!r}; use a built-in name or 'module:Class'")
    module, cls = target.split(":")
    options = config.get("adapters", {}).get(name, {})
    return getattr(importlib.import_module(module), cls)(**options)


def instruments_from(config: dict[str, Any]) -> list[Instrument]:
    try:
        return [INSTRUMENTS[name]() for name in config["instruments"]]
    except KeyError as e:
        raise ValueError(f"unknown instrument {e}; choose from {sorted(INSTRUMENTS)}") from None


def build_pipeline(config: dict[str, Any]) -> TranscriptionPipeline:
    stages = dict(config["stages"])
    if stages.get("mix_transcriber"):
        # An end-to-end model replaces these, so don't load them.
        for replaced in ("separator", "pitch", "drums"):
            stages.pop(replaced, None)
    kwargs = {s: build(stages[s], config) for s in STAGES if stages.get(s)}
    refiners = [build(name, config) for name in stages.get("refiners", [])]
    return TranscriptionPipeline(instruments=instruments_from(config), refiners=refiners, **kwargs)


def build_writers(config: dict[str, Any]) -> list[Any]:
    return [build(name, config) for name in config["writers"]]
