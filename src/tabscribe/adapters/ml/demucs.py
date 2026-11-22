"""SourceSeparator using Demucs v4 (Meta).

Model: htdemucs_6s splits a mix into guitar, bass, drums, piano, vocals
and other. Install: pip install demucs
Status: written against Demucs' CLI entry point; not yet run in this repo.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ...domain import AudioRef, Role, StemSet

STEM_FILES = {
    Role.GUITAR: "guitar",
    Role.BASS: "bass",
    Role.DRUMS: "drums",
    Role.PIANO: "piano",
    Role.VOCALS: "vocals",
    Role.OTHER: "other",
}


class DemucsSeparator:
    def __init__(self, model: str = "htdemucs_6s", device: str | None = None):
        self.model = model
        self.device = device

    def separate(self, mix: AudioRef, roles: Sequence[Role], workdir: Path) -> StemSet:
        import demucs.separate  # heavy import, only when used

        out = workdir / "stems"
        args = ["-n", self.model, "-o", str(out)]
        if self.device:
            args += ["-d", self.device]
        demucs.separate.main([*args, str(mix.path)])

        folder = out / self.model / mix.path.stem
        stems = {}
        for role in roles:
            path = folder / f"{STEM_FILES.get(role, '')}.wav"
            if path.exists():
                stems[role] = AudioRef(path)
        return stems
