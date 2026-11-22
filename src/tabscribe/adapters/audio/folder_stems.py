"""SourceSeparator that reads stems you already have, instead of separating.

Looks for <role>.wav (or .flac/.mp3) in `directory`, or by default in a
folder named "<mix name>_stems" next to the mix. Useful when a song comes
with multitracks, and for evaluation with perfectly separated stems.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ...domain import AudioRef, Role, StemSet

EXTENSIONS = (".wav", ".flac", ".mp3", ".ogg")


class FolderStems:
    def __init__(self, directory: str | None = None):
        self.directory = Path(directory) if directory else None

    def separate(self, mix: AudioRef, roles: Sequence[Role], workdir: Path) -> StemSet:
        folder = self.directory or mix.path.with_name(f"{mix.path.stem}_stems")
        stems = {}
        for role in roles:
            for ext in EXTENSIONS:
                path = folder / f"{role.value}{ext}"
                if path.exists():
                    stems[role] = AudioRef(path)
                    break
        return stems
