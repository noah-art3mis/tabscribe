"""A song library on disk: one `<name>.atex` per song, and next to it an
optional `<name>.media/` folder with the original recording and its stems,
so the tab can be played alongside what it was transcribed from.

    songs/
      My Song.atex
      My Song.media/
        mix.mp3         the original recording
        guitar.wav      separated stems, when the pipeline produced them
        bass.wav
        ...
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

from .domain import AudioRef, Role

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".webm"}
LABELS = {
    "mix": "Full recording",
    Role.GUITAR.value: "Guitar stem",
    Role.BASS.value: "Bass stem",
    Role.DRUMS.value: "Drums stem",
    Role.VOCALS.value: "Vocals stem",
    Role.PIANO.value: "Piano stem",
    Role.OTHER.value: "Other stem",
}
ORDER = ["mix", "guitar", "bass", "drums", "vocals", "piano", "other"]


def media_dir(library: Path, name: str) -> Path:
    return library / f"{name}.media"


def save_media(library: Path, name: str, mix: Path, stems: Mapping[Role, AudioRef]) -> Path:
    """Copy the recording and its stems next to the song."""
    folder = media_dir(library, name)
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mix, folder / f"mix{mix.suffix.lower() or '.wav'}")
    for role, stem in stems.items():
        if stem.path.resolve() != mix.resolve():  # some separators hand back the mix itself
            shutil.copy2(stem.path, folder / f"{role.value}{stem.path.suffix.lower() or '.wav'}")
    return folder


def list_media(library: Path, name: str) -> list[dict[str, str]]:
    folder = media_dir(library, name)
    if not folder.is_dir():
        return []
    found = [p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTENSIONS]
    found.sort(key=lambda p: (ORDER.index(p.stem) if p.stem in ORDER else len(ORDER), p.stem))
    return [{"id": p.stem, "label": LABELS.get(p.stem, p.stem), "file": p.name} for p in found]
