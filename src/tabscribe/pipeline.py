"""Audio -> guitar tab pipeline. Each stage is a stub to fill in."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Note:
    onset: float  # seconds
    offset: float  # seconds
    pitch: int  # MIDI note number
    string: int | None = None  # 1 = high E
    fret: int | None = None


@dataclass
class Analysis:
    key: str | None = None
    tempo: float | None = None
    downbeats: list[float] = field(default_factory=list)
    chords: list[tuple[float, float, str]] = field(default_factory=list)


def separate(audio: Path, out_dir: Path) -> Path:
    """Isolate the guitar stem with Demucs (htdemucs_6s). Returns stem path."""
    raise NotImplementedError


def analyse(audio: Path) -> Analysis:
    """Key, chords, beats and downbeats with madmom."""
    raise NotImplementedError


def transcribe(stem: Path) -> list[Note]:
    """Audio -> notes with Basic Pitch."""
    raise NotImplementedError


def assign_frets(notes: list[Note], tuning: tuple[int, ...] = (64, 59, 55, 50, 45, 40)) -> list[Note]:
    """Pick a playable string/fret for each note (e.g. dynamic programming
    minimising hand movement). Tuning is MIDI pitches, high E to low E."""
    raise NotImplementedError


def export_txt(notes: list[Note], analysis: Analysis, path: Path) -> None:
    """Plain-text tab, readable anywhere."""
    from .ascii_tab import render

    path.write_text(render(notes, analysis))


def export_musicxml(notes: list[Note], analysis: Analysis, path: Path) -> None:
    """MusicXML with a tab staff (string/fret technicals). Opens in MuseScore
    and TuxGuitar."""
    raise NotImplementedError


def export_gp5(notes: list[Note], analysis: Analysis, path: Path) -> None:
    """Optional: Guitar Pro 5 file with PyGuitarPro."""
    raise NotImplementedError


EXPORTERS = {"txt": export_txt, "musicxml": export_musicxml, "gp5": export_gp5}


def run(audio: Path, out_dir: Path, fmt: str = "txt") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = separate(audio, out_dir)
    analysis = analyse(audio)
    notes = assign_frets(transcribe(stem))
    ext = "musicxml" if fmt == "musicxml" else fmt
    out = out_dir / f"{audio.stem}.{ext}"
    EXPORTERS[fmt](notes, analysis, out)
    return out
