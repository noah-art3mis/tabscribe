"""Audio value objects. The domain never decodes audio; adapters do."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .instruments import Role


@dataclass(frozen=True)
class AudioRef:
    """A reference to an audio file on disk (any format the adapter can read)."""

    path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))


# One isolated audio file per instrument role, e.g. {Role.BASS: AudioRef(...)}.
StemSet = Mapping[Role, AudioRef]
