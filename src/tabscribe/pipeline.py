"""Audio -> Song pipeline. Audio stages are stubs to fill in."""

from __future__ import annotations

from pathlib import Path

from .model import Note, Song, Track


def separate(audio: Path, out_dir: Path) -> dict[str, Path]:
    """Split the mix into stems with Demucs (htdemucs_6s gives guitar, bass,
    drums, piano, vocals, other). Returns {stem name: path}."""
    raise NotImplementedError


def analyse(audio: Path) -> Song:
    """Tempo, downbeats, key and chords with madmom. Returns a Song with no tracks."""
    raise NotImplementedError


def transcribe_pitched(stem: Path) -> list[Note]:
    """Guitar/bass stem -> notes with Basic Pitch."""
    raise NotImplementedError


def transcribe_drums(stem: Path) -> list[Note]:
    """Drum stem -> hits on General MIDI drum keys (e.g. ADTOF)."""
    raise NotImplementedError


def assign_frets(notes: list[Note], tuning: tuple[int, ...]) -> list[Note]:
    """Pick a playable string/fret for each note, e.g. dynamic programming
    minimising hand movement."""
    raise NotImplementedError


def run(audio: Path, out_dir: Path) -> Song:
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = separate(audio, out_dir)
    song = analyse(audio)
    song.title = audio.stem
    for maker, stem in ((Track.guitar, "guitar"), (Track.bass, "bass")):
        if stem in stems:
            track = maker()
            track.notes = assign_frets(transcribe_pitched(stems[stem]), track.tuning)
            song.tracks.append(track)
    if "drums" in stems:
        drums = Track.drums()
        drums.notes = transcribe_drums(stems["drums"])
        song.tracks.append(drums)
    return song
