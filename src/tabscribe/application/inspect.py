"""Save each stage's output as JSON so you can see what every layer produced."""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any


def to_jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        data = {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        return {"type": type(obj).__name__, **data}
    if isinstance(obj, Enum):
        return obj.name.lower()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(to_jsonable(k)): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        items = [to_jsonable(x) for x in obj]
        return sorted(items, key=str) if isinstance(obj, (set, frozenset)) else items
    return obj


def stage_dumper(directory: Path):
    """Returns an `observe` callback for TranscriptionPipeline.run."""
    directory.mkdir(parents=True, exist_ok=True)

    def observe(stage: str, output: object) -> None:
        path = directory / f"{stage}.json"
        path.write_text(json.dumps(to_jsonable(output), indent=1))

    return observe
